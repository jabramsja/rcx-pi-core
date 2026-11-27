#!/usr/bin/env python3
"""Shared utilities for executor scripts.

Canonical implementations of functions previously duplicated across
executor_dispatch.py, phase_a_executor.py, phase_b_executor.py, and
dialectic_executor.py.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import signal
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NamedTuple

VALIDATION_EXECUTION_API = 1
EXECUTOR_COMMON_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
# Execution witness: the module code object the interpreter actually ran for
# this namespace, from source or from any accepted bytecode cache. The supervisor
# handoff compares it with the code its bound source bytes compile to and never
# trusts it alone; a stale cache runs, and so records, different code. The disk
# hash above is a diagnostic only and cannot show which code executed.
EXECUTED_MODULE_CODE = sys._getframe(0).f_code if hasattr(sys, "_getframe") else None

DEFAULT_AGENT_BUS_DIR = Path(".agent_bus")
ROUTING_RECORD_PATH = DEFAULT_AGENT_BUS_DIR / "meta" / "post_merge_routing.json"
BRIDGE_CONFIG_PATH = DEFAULT_AGENT_BUS_DIR / "bridge_config.json"
AGENT_BUS_NAMESPACE_RE = re.compile(r"^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$")
MAX_WAVE_ID_LEN = 80
WAVE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
REVIEW_MODE_ENV_VARS = ("RCX_AGENT_REVIEW_MODE", "RCX_REVIEW_MODE")
ROLE_AGENT_ENV_VARS = {
    "implementer": ("RCX_IMPLEMENTER_AGENT_OVERRIDE",),
    "reviewer": (
        "RCX_REVIEWER_AGENT_OVERRIDE",
        "RCX_BRIDGE_REVIEWER_OVERRIDE",
    ),
}
ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV = "RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT"
ROLE_AGENT_ENV_OVERRIDES_APPLY_KEY = "_role_agent_env_overrides_apply"
IMPLEMENTER_BACKEND_KEYS = frozenset(
    {
        "phase_a_executor",
        "phase_b_executor",
        "bot_remediation",
    }
)
REVIEWER_BRIDGE_KEYS = frozenset({"phase_a", "phase_b"})
DEFAULT_EXECUTOR_CONFIG: dict[str, Any] = {
    "role_agents": {
        "implementer": "claude",
        "reviewer": "claude",
    },
    "bridge_agent_defaults": {
        "claude": {
            "display_name": "Claude Opus 5.5 max",
            "model": "claude-opus-5-5",
            "effort": "max",
        },
        "codex": {
            "display_name": "Codex GPT-6 Astra max",
            "model": "gpt-6-astra",
            "reasoning_effort": "max",
        },
    },
    "backends": {
        "post_merge_supervisor": "claude",
        "dialectic_executor": "claude",
        "phase_a_executor": "claude",
        "phase_b_executor": "claude",
        "bot_remediation": "claude",
        "commit_executor": None,
    },
    "bridge_reviewers": {
        "phase_a": "claude",
        "phase_b": "claude",
    },
    "bridge_turn_timeouts": {
        "phase_a": 600,
        "phase_b": 900,
    },
    "model_overrides": {
        "phase_b_executor": None,
    },
    "hybrid_recovery_enabled": True,
    "pipeline_agent_pager": {
        "enabled": True,
        "route": "claude",
    },
    "review_depths": {
        "phase_a": "quick",
        "phase_b": "quick",
    },
    "timeouts": {
        "dialectic_executor": 600,
        "phase_a_executor": 3600,
        "phase_b_executor": 18000,
        "phase_b_implementer_stale": 300,
        "commit_executor": 3600,
        "pre_commit_supervisor": 900,
        "post_merge_supervisor": 900,
        "pre_push_fast": 2400,
        "commit_ci_watch": 3300,
        "commit_ci_poll": 3300,
        "commit_ci_verify": 900,
        "bot_remediation": 600,
        "agent_review": 900,
        "pipeline_agent_pager_trigger": 30,
        "pipeline_agent_pager_codex_ack": 20,
        "pipeline_agent_pager_claude_ack": 20,
    },
    "bridge_loop_limits": {
        "phase_a": 15,
        "phase_b": 10,
        "dialectic": 3,
    },
}
ALLOWED_PIPELINE_AGENT_PAGER_ROUTES = frozenset({"codex", "claude", "both", "notify-only"})
REVIEWER_LAUNCH_PROVENANCE_VERSION = 1

DEFAULT_AGENT_DISPLAY_NAMES = {
    name: str(data.get("display_name")).strip()
    for name, data in DEFAULT_EXECUTOR_CONFIG.get("bridge_agent_defaults", {}).items()
    if isinstance(name, str)
    and isinstance(data, dict)
    and str(data.get("display_name") or "").strip()
}

REVIEW_OVERRIDE_BACKEND_KEYS = frozenset(
    {
        "post_merge_supervisor",
        "dialectic_executor",
    }
)

# ---------------------------------------------------------------------------
# Finding disposition classification contract
# ---------------------------------------------------------------------------
# Shared between bridge_reviewer_prompt.txt and phase_b_executor.py.
# If you change these criteria, update BOTH the prompt template and the
# executor's _disposition_for_finding fallback logic.
#
# Severity floor (authoritative): HIGH/CRITICAL severity is genuinely blocking
# and is honored even against an explicit ``disposition: non_blocking``. BELOW
# that floor (medium/low/absent severity) an explicit ``disposition: blocking``
# is DEFERRED to non_blocking by phase_b_executor._disposition_for_finding via
# the single shared rule recovery_gate._finding_is_deferrable_on_go (one rule,
# no divergent local copy) — so a bridge GO carrying only sub-floor findings
# defers and commits instead of stranding. To mark a GENUINE sub-floor blocker,
# set severity=high (or critical); an explicit blocking disposition alone is NOT
# sufficient below the floor. (bridge_reviewer_prompt.txt still states the
# pre-floor "explicit disposition is honored" contract; syncing that template
# note is a deferred follow-up — the executor behavior here is authoritative.)

BLOCKING_CRITERIA = (
    "Causes runtime failure, crash, or data loss in the live pipeline",
    "Violates a hard invariant (receipt authority, fail-closed behavior, process cleanup)",
    "Security bypass or privilege escalation",
    "Breaks an existing test or causes test regression",
    "Makes a pipeline step silently skip or produce wrong output",
)

NON_BLOCKING_CRITERIA = (
    "Hardening improvement that does not affect current correctness",
    "Theoretical edge case that requires synthetic/adversarial setup to trigger",
    "Code quality, style, or naming suggestion",
    "Defense-in-depth addition",
    "Documentation accuracy without behavioral impact",
    "Performance optimization",
)

# Keyword patterns used by the executor to infer disposition when the reviewer
# omits the disposition field.  Checked against the finding's title + summary.
BLOCKING_KEYWORDS = (
    "runtime failure", "crash", "data loss",
    "test failure", "test regression", "breaks test",
    "invariant violation", "invariant violated",
    "security bypass", "privilege escalation",
    "silently skip", "wrong output", "silent failure",
    "receipt authority", "fail-closed", "fail closed",
    "process cleanup", "orphan",
)

NON_BLOCKING_KEYWORDS = (
    "hardening", "defense-in-depth", "defence-in-depth",
    "theoretical", "adversarial setup", "synthetic scenario",
    "style", "naming", "readability",
    "documentation", "doc accuracy", "docstring",
    "performance", "optimization",
    "edge case",
)

# Detail-text indicators for high-severity findings that lack keyword matches.
# Used to distinguish hardening items from real defects when the reviewer
# omits disposition and no primary keywords match.
HARDENING_INDICATORS = (
    "theoretical", "synthetic", "adversarial setup",
    "spoofable", "could be bypassed", "could be spoofed",
    "hypothetical", "unlikely in practice",
)
DEFECT_INDICATORS = (
    "returns success", "still proceeds", "accepted",
    "reaches commit_ready", "silently passes",
    "no error raised", "skips validation",
    "orphaned", "not cleaned up", "leaked process",
    "receipt not checked", "receipt ignored",
    "proceeds without receipt", "skips receipt",
)

# Repeat-finding hard-failure cap: if the same blocking finding appears in
# this many consecutive bridge rounds without resolution, the bridge loop
# terminates as a hard failure.  Blocking findings are NEVER auto-downgraded.
REPEAT_FINDING_CAP = 3


class ExecutorCommonError(RuntimeError):
    """Raised when a shared executor utility fails."""


VALIDATION_CEILING_SECONDS = 7200
PHASE_B_PYTEST_FLOOR_SECONDS = 300
NATIVE_STAGE_BUDGET_ENV = "RCX_NATIVE_STAGE_BUDGET"
VALIDATION_SCHEDULE_ENV = "RCX_VALIDATION_SCHEDULE"


class ValidationBudgetError(ExecutorCommonError):
    """An inadmissible validation schedule is a HOLD, never a test failure."""


def validation_child_environment(env: dict[str, str] | None = None) -> dict[str, str]:
    """Isolate test authority while retaining ownership and ordinary environment.

    This constructor is only for validation children. Production recovery,
    review, hook and dispatcher processes retain their invocation authority.
    """
    protected = {NATIVE_STAGE_BUDGET_ENV, VALIDATION_SCHEDULE_ENV, "RCX_AGENT_BUS_DIR",
                 ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV, "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE",
                 "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY", "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE"}
    for names in ROLE_AGENT_ENV_VARS.values():
        protected.update(names)
    return {key: value for key, value in (os.environ if env is None else env).items()
            if key not in protected and not key.startswith("RCX_SKIP_")}


def validation_hold_result(validation: dict[str, Any], *, step: str) -> dict[str, Any] | None:
    """Carry a native HOLD across caller boundaries without authorizing recovery.

    Keep the complete validation evidence, including receipts and ownership
    diagnostics. Only the structured signal is authoritative; failure text alone
    must not turn an ordinary test failure into a terminal policy outcome.
    """
    if (validation.get("validation_budget_hold") is not True
            and validation.get("status") != "validation_budget_hold"
            and validation.get("error_code") != "VALIDATION_BUDGET_HOLD"):
        return None
    return {
        "status": "validation_budget_hold", "step": step,
        "passed": False, "validation_budget_hold": True,
        "errors": list(validation.get("errors") or [
            validation.get("error_detail") or validation.get("stderr") or validation.get("diagnostic")
            or "Validation HOLD; automatic recovery is prohibited.",
        ]),
        "error_code": "VALIDATION_BUDGET_HOLD",
        "error_detail": validation.get("error_detail", ""),
        "stdout": validation.get("stdout", ""),
        "stderr": validation.get("stderr", ""),
        "validation": validation,
    }


class NativeStageBudget(NamedTuple):
    """Immutable, same-host invocation authority; clocks never restart on decode.

    This is a finite allocation, not a scheduler or process-release receipt.
    The original baseline and each sequential allocation retain their own key.
    """

    version: int
    invocation: str
    repo: str
    key: str
    command: tuple[str, ...]
    baseline: int
    seconds: int
    ceiling: int
    allocations: tuple[tuple[str, int], ...]
    environment: tuple[tuple[str, str | None], ...]
    started_ns: int
    wall_started_ns: int
    bindings: tuple[tuple[str, str], ...]

    def encode(self) -> str:
        body = self._asdict()
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return json.dumps({**body, "digest": hashlib.sha256(canonical.encode()).hexdigest()},
                          sort_keys=True, separators=(",", ":"))

    def remaining(self) -> float:
        # Use both clocks: neither a wall-clock rollback nor a reboot/monotonic
        # reset grants more time. An observation before either origin is stale.
        elapsed = time.monotonic_ns() - self.started_ns
        wall_elapsed = time.time_ns() - self.wall_started_ns
        if min(elapsed, wall_elapsed) < 0:
            raise ValidationBudgetError("HOLD: validation budget clock/source is stale")
        remaining = self.seconds - max(elapsed, wall_elapsed) / 1_000_000_000
        if remaining <= 0:
            raise ValidationBudgetError(f"HOLD: {self.key} budget exhausted; retry cannot reset it")
        return remaining


def _budget_positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValidationBudgetError(f"HOLD: {label} must be a positive integer")
    return value


def validation_source_bindings(repo_root: Path, command: tuple[str, ...] = (), *,
                               bus_dir: str | Path | None = None) -> tuple[tuple[str, str], ...]:
    """Bind the executing policy and physical config, without role overrides.

    Fixtures may have no repository config. Its absence is explicitly bound;
    introducing one later is drift, not a fallback to a new authority.
    """
    policy_dir = Path(__file__).resolve().parent
    paths = [policy_dir / name for name in (
        "executor_common.py", "validation_execution.py", "phase_b_executor.py",
        "commit_executor.py", "executor_dispatch.py", "launch_wave.py", "recovery_gate.py")]
    paths += [policy_dir.parent / "agents/meta_bridge_supervisor.py",
              policy_dir.parent / "agents/meta_bridge_client.py",
              Path(repo_root).resolve() / "mu/tools/executors/executor_config.json"]
    if bus_dir is None and "--bus-dir" in command:
        try:
            bus_dir = command[command.index("--bus-dir") + 1]
        except IndexError as exc:
            raise ValidationBudgetError("HOLD: missing validation bus identity") from exc
    bus = normalize_agent_bus_dir(bus_dir if bus_dir is not None else os.environ.get("RCX_AGENT_BUS_DIR"))
    paths.append(Path(repo_root).resolve() / bus / "bridge_config.json")
    output_value = False
    for arg in command:
        # Native pytest output locations are immutable argv, not input source.
        # A newly written JUnit file must not become a new policy binding on the
        # next sequential leaf. Selected tests and discovered config stay bound.
        if output_value:
            output_value = False
            continue
        if arg in {"--junitxml", "--junit-xml", "--basetemp"}:
            output_value = True
            continue
        candidate = Path(repo_root) / arg.split("::", 1)[0]
        try:
            if candidate.is_file():
                paths.append(candidate.resolve())
        except OSError:
            pass  # -c source and shell commands are bound by the exact argv.
    return tuple((str(path), hashlib.sha256(path.read_bytes()).hexdigest()
                  if path.is_file() else "absent") for path in dict.fromkeys(paths))


def validation_environment_binding(env: dict[str, str]) -> tuple[tuple[str, str | None], ...]:
    return tuple((key, env.get(key)) for key in (
        "PYTHONHASHSEED", "RCX_CI", "HYPOTHESIS_PROFILE", "PYTHONDONTWRITEBYTECODE",
        "PYTEST_ADDOPTS", "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "PYTHONPATH", "PATH",
        "RCX_META_VALIDATION_TIMEOUT_S"))


def admit_stage_budget(
    repo_root: Path, *, key: str, command: list[str], baseline: int,
    seconds: int, ceiling: int, allocations: tuple[tuple[str, int], ...] = (),
    env: dict[str, str] | None = None,
) -> NativeStageBudget:
    """Reject an enclosing conflict before the child or its expensive work starts."""
    import uuid

    for label, value in (("baseline", baseline), ("seconds", seconds), ("ceiling", ceiling)):
        _budget_positive_int(value, label)
    if type(key) is not str or key not in {"pytest_full", "pytest_fast", "meta_validation", "phase_b_executor", "commit_executor"}:
        raise ValidationBudgetError("HOLD: unknown validation budget key")
    if key in {"pytest_full", "pytest_fast", "meta_validation"} and ceiling > VALIDATION_CEILING_SECONDS:
        raise ValidationBudgetError("HOLD: validation ceiling exceeds 7200s")
    if key in {"phase_b_executor", "commit_executor"}:
        maximum = sum(value for _, value in validation_schedule_requirements(repo_root, VALIDATION_CEILING_SECONDS)[key])
        if ceiling > maximum:
            raise ValidationBudgetError("HOLD: native stage exceeds its source-derived finite ceiling")
    if type(command) is not list or not command or any(type(arg) is not str or not arg or "\0" in arg for arg in command):
        raise ValidationBudgetError("HOLD: missing budget key or exact command")
    names = set()
    for name, value in allocations:
        if not name or name in names:
            raise ValidationBudgetError("HOLD: duplicate/empty stage allocation")
        names.add(name)
        _budget_positive_int(value, name)
    required = sum(value for _, value in allocations)
    if baseline > ceiling or seconds > ceiling or seconds < required:
        raise ValidationBudgetError(
            f"HOLD: {key} schedule requires {required}s, allocation={seconds}s, "
            f"baseline={baseline}s, ceiling={ceiling}s"
        )
    return NativeStageBudget(1, uuid.uuid4().hex, str(Path(repo_root).resolve()), key,
                             tuple(command), baseline, seconds, ceiling, tuple(allocations),
                             validation_environment_binding(os.environ if env is None else env),
                             time.monotonic_ns(), time.time_ns(), validation_source_bindings(repo_root, tuple(command)))


def decode_stage_budget(raw: str, repo_root: Path, *, key: str | None = None,
                        command: list[str] | None = None, env: dict[str, str] | None = None) -> NativeStageBudget:
    """Strict immutable transport: unknown fields, source drift and resets HOLD."""
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValidationBudgetError("HOLD: duplicate budget field")
            result[name] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique)
        if type(value) is not dict or set(value) != set(NativeStageBudget._fields) | {"digest"}:
            raise ValueError("unknown/missing fields")
        digest = value.pop("digest")
        canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if digest != hashlib.sha256(canonical.encode()).hexdigest():
            raise ValueError("immutable budget digest mismatch (including clock/reset)")
        if type(value["version"]) is not int or value["version"] != 1:
            raise ValueError("version")
        if type(value["invocation"]) is not str or not re.fullmatch(r"[0-9a-f]{32}", value["invocation"]):
            raise ValueError("invocation")
        for field in ("baseline", "seconds", "ceiling", "started_ns", "wall_started_ns"):
            _budget_positive_int(value[field], field)
        if (type(value["command"]) is not list or not value["command"]
                or any(type(arg) is not str or not arg for arg in value["command"])):
            raise ValueError("command")
        allocations = value["allocations"]
        if type(allocations) is not list or any(type(pair) is not list or len(pair) != 2
                                              or type(pair[0]) is not str or not pair[0]
                                              for pair in allocations):
            raise ValueError("allocations")
        for name, seconds in allocations:
            _budget_positive_int(seconds, name)
        if len({name for name, _ in allocations}) != len(allocations):
            raise ValueError("duplicate allocation")
        if (value["baseline"] > value["ceiling"] or value["seconds"] > value["ceiling"]
                or sum(seconds for _, seconds in allocations) > value["seconds"]):
            raise ValueError("over-cap/incoherent budget")
        if value["key"] in {"pytest_full", "pytest_fast", "meta_validation"} and value["ceiling"] > VALIDATION_CEILING_SECONDS:
            raise ValueError("validation ceiling exceeds 7200s")
        if value["key"] in {"phase_b_executor", "commit_executor"}:
            maximum = sum(seconds for _, seconds in validation_schedule_requirements(repo_root, VALIDATION_CEILING_SECONDS)[value["key"]])
            if value["ceiling"] > maximum:
                raise ValueError("native stage exceeds its source-derived finite ceiling")
        if (value["repo"] != str(Path(repo_root).resolve())
                or value["key"] not in {"pytest_full", "pytest_fast", "meta_validation", "phase_b_executor", "commit_executor"}):
            raise ValueError("repo/key")
        if key is not None and value["key"] != key:
            raise ValueError("key mismatch")
        if command is not None and value["command"] != command:
            raise ValueError("command mismatch")
        if value["bindings"] != [list(pair) for pair in validation_source_bindings(repo_root, tuple(value["command"]))]:
            raise ValueError("policy/config source drift")
        if value["environment"] != [list(pair) for pair in validation_environment_binding(os.environ if env is None else env)]:
            raise ValueError("validation environment drift")
        value.update(command=tuple(value["command"]), allocations=tuple(map(tuple, allocations)),
                     bindings=tuple(map(tuple, value["bindings"])), environment=tuple(map(tuple, value["environment"])))
        budget = NativeStageBudget(**value)
        budget.remaining()
        return budget
    except (TypeError, ValueError, KeyError, OSError) as exc:
        raise ValidationBudgetError(f"HOLD: invalid validation budget: {exc}") from exc


def validation_parent_remaining(repo_root: Path, *, seconds: int, key: str) -> float | None:
    """A leaf needs its finite budget plus the parent's remaining stage reserve."""
    raw = os.environ.get(NATIVE_STAGE_BUDGET_ENV)
    if raw is None:
        return None
    parent = decode_stage_budget(raw, repo_root)
    allocation = dict(parent.allocations).get(key)
    if allocation is None or seconds > allocation:
        raise ValidationBudgetError(f"HOLD: {key} is absent/over-cap in {parent.key}")
    remaining = parent.remaining()
    # Reserve the explicitly budgeted review/other sequential work. Validation
    # must never borrow another key's allowance or extend the parent's deadline.
    position = [name for name, _ in parent.allocations].index(key)
    reserve = sum(value for _, value in parent.allocations[position + 1:])
    if seconds + reserve > remaining:
        raise ValidationBudgetError(
            f"HOLD: {key} needs {seconds}s + {reserve}s sequential reserve; "
            f"{parent.key} has {remaining:.3f}s remaining"
        )
    return remaining


def phase_b_pytest_timeout(raw_timeout: Any) -> int:
    """The existing Phase B leaf floor/cap, shared with parent admission."""
    try:
        seconds = int(float(raw_timeout))
    except (TypeError, ValueError):
        return PHASE_B_PYTEST_FLOOR_SECONDS
    if seconds <= 0:
        return PHASE_B_PYTEST_FLOOR_SECONDS
    return max(PHASE_B_PYTEST_FLOOR_SECONDS, min(seconds, VALIDATION_CEILING_SECONDS))


def validation_schedule_requirements(repo_root: Path, validation_seconds: int) -> dict[str, tuple[tuple[str, int], ...]]:
    """Account for sequential validation and existing non-validation envelopes.

    The old Phase B budget remains the implementation/convergence allowance;
    the old commit budget remains its hooks, remediation, review and delivery
    allowance. validation_seconds is the requested evidence allowance; it must
    not shrink a different pytest key. Phase B retains its configured leaf
    floor/cap. Commit reserves the finite shared pytest ceiling because its
    final selectors can include generated tests discovered after admission.
    These are ceilings, not typical runtimes. No config default is increased.
    """
    _budget_positive_int(validation_seconds, "validation_seconds")
    if validation_seconds > VALIDATION_CEILING_SECONDS:
        raise ValidationBudgetError("HOLD: validation_seconds exceeds 7200s")
    path = Path(repo_root) / "mu/tools/executors/executor_config.json"
    raw = json.loads(path.read_text()) if path.is_file() else {}
    timeouts = merge_executor_config_overrides(raw)["timeouts"]
    for key in ("phase_b_executor", "commit_executor", "pre_commit_supervisor", "pre_push_fast",
                "commit_ci_watch", "commit_ci_poll", "commit_ci_verify"):
        _budget_positive_int(timeouts[key], key)
    return {
        "phase_b_executor": (("implementation_convergence", timeouts["phase_b_executor"]),
                             ("pytest_full", phase_b_pytest_timeout(timeouts["phase_b_executor"])),
                             ("meta_validation", validation_seconds),
                             ("supervisor_review", timeouts["pre_commit_supervisor"])),
        "commit_executor": (("hooks_review_delivery", timeouts["commit_executor"]),
                            ("meta_validation", validation_seconds), ("pytest_fast", VALIDATION_CEILING_SECONDS),
                            ("pre_push_fast", timeouts["pre_push_fast"]),
                            ("commit_ci_watch", timeouts["commit_ci_watch"]),
                            ("commit_ci_poll", timeouts["commit_ci_poll"]),
                            ("commit_ci_verify", timeouts["commit_ci_verify"])),
    }


def validate_validation_schedule(request: Any, repo_root: Path) -> dict[str, Any]:
    """Validate an explicit per-launch request; never infer larger defaults."""
    fields = {"validation_seconds", "phase_b_executor", "commit_executor"}
    if type(request) is not dict or set(request) != fields:
        raise ValidationBudgetError("HOLD: validation_schedule requires exact per-key allocations")
    requirements = validation_schedule_requirements(repo_root, request["validation_seconds"])
    try:
        ordinary = int(os.environ.get("RCX_META_VALIDATION_TIMEOUT_S", "1200"))
    except ValueError:
        ordinary = 1200
    if not 1 <= ordinary <= VALIDATION_CEILING_SECONDS:
        ordinary = 1200
    if request["validation_seconds"] < ordinary:
        raise ValidationBudgetError(
            f"HOLD: evidence allowance cannot contain the existing {ordinary}s supervisor leaf; "
            "small evidence schedules require separate non-evidence allocation"
        )
    for key, allocations in requirements.items():
        required = sum(value for _, value in allocations)
        _budget_positive_int(request[key], key)
        # This wave admits only the deterministically accounted envelope. A
        # larger envelope needs a new policy, not a free-form timeout override.
        if request[key] != required:
            raise ValidationBudgetError(f"HOLD: {key} admitted envelope must equal accounted {required}s")
    return copy.deepcopy(request)


def build_validation_schedule_transport(repo_root: Path, request: dict[str, Any], *,
                                        wave_id: str, evidence_command: str,
                                        bus_dir: str | Path | None = None) -> str:
    import uuid
    validated = validate_validation_schedule(request, repo_root)
    bus = str(normalize_agent_bus_dir(bus_dir if bus_dir is not None else os.environ.get("RCX_AGENT_BUS_DIR")))
    body = {"version": 1, "invocation": uuid.uuid4().hex, "wave_id": wave_id, "bus_dir": bus,
                       "repo": str(Path(repo_root).resolve()), "request": validated,
                       "evidence_command": evidence_command,
                       "supervisor_timeout_env": os.environ.get("RCX_META_VALIDATION_TIMEOUT_S"),
                       "bindings": validation_source_bindings(repo_root, bus_dir=bus)}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return json.dumps({**body, "digest": hashlib.sha256(canonical.encode()).hexdigest()}, sort_keys=True)


def read_validation_schedule_transport(repo_root: Path, raw: str | None = None, *,
                                       bus_dir: str | Path | None = None) -> dict[str, Any] | None:
    raw = os.environ.get(VALIDATION_SCHEDULE_ENV) if raw is None else raw
    if raw is None:
        return None
    try:
        def unique(pairs):
            value = {}
            for name, item in pairs:
                if name in value:
                    raise ValueError("duplicate schedule field")
                value[name] = item
            return value
        value = json.loads(raw, object_pairs_hook=unique)
        if type(value) is not dict or set(value) != {"version", "invocation", "wave_id", "repo", "bus_dir", "request", "evidence_command", "supervisor_timeout_env", "bindings", "digest"}:
            raise ValueError("unknown/missing schedule fields")
        digest = value.pop("digest")
        if digest != hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest():
            raise ValueError("immutable schedule digest mismatch")
        if type(value["version"]) is not int or value["version"] != 1:
            raise ValueError("schedule version")
        if not re.fullmatch(r"[0-9a-f]{32}", value["invocation"]):
            raise ValueError("invocation")
        if value["repo"] != str(Path(repo_root).resolve()):
            raise ValueError("repo mismatch")
        if value["supervisor_timeout_env"] != os.environ.get("RCX_META_VALIDATION_TIMEOUT_S"):
            raise ValueError("supervisor timeout environment drift")
        bus = str(normalize_agent_bus_dir(bus_dir if bus_dir is not None else os.environ.get("RCX_AGENT_BUS_DIR")))
        if value["bus_dir"] != bus:
            raise ValueError("active catalog/bus mismatch")
        if value["bindings"] != [list(pair) for pair in validation_source_bindings(repo_root, bus_dir=bus)]:
            raise ValueError("schedule source/config drift")
        if not isinstance(value["evidence_command"], str) or not isinstance(value["wave_id"], str):
            raise ValueError("command/wave type")
        validate_validation_schedule(value["request"], repo_root)
        return value
    except (ValueError, TypeError, OSError, KeyError) as exc:
        raise ValidationBudgetError(f"HOLD: invalid validation schedule: {exc}") from exc


def retain_validation_schedule(repo_root: Path, request: dict[str, Any], *, wave_id: str,
                               evidence_command: str, bus_dir: str | Path | None = None) -> str:
    """Keep one immutable launch request across authorized native continuations."""
    if type(wave_id) is not str or not WAVE_ID_RE.fullmatch(wave_id):
        raise ValidationBudgetError("HOLD: invalid validation schedule wave")
    path = agent_bus_path(repo_root, bus_dir, "executors", "validation", wave_id + ".schedule.json")
    if path.is_symlink() or not path.parent.resolve().is_relative_to(Path(repo_root).resolve()):
        raise ValidationBudgetError("HOLD: validation schedule storage identity is uncertain")
    path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    if not path.exists():
        raw = build_validation_schedule_transport(repo_root, request, wave_id=wave_id,
                                                   evidence_command=evidence_command, bus_dir=bus_dir)
        try:
            with path.open("x") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            created = True
        except FileExistsError:
            pass
    raw = path.read_text()
    admitted = read_validation_schedule_transport(repo_root, raw, bus_dir=bus_dir)
    if (admitted is None or admitted["wave_id"] != wave_id or admitted["request"] != request
            or admitted["evidence_command"] != evidence_command):
        raise ValidationBudgetError("HOLD: existing validation request cannot be replaced or reset")
    ledger = path.with_suffix(".admissions.json")
    if created:
        with ledger.open("x") as handle:
            json.dump({"transport": raw, "stages": {"phase_b_executor": None, "commit_executor": None}}, handle)
            handle.flush()
            os.fsync(handle.fileno())
    if ledger.is_symlink() or not ledger.is_file():
        raise ValidationBudgetError("HOLD: missing/interrupted validation admission ledger")
    return raw


def retain_native_stage_budget(repo_root: Path, schedule: dict[str, Any], *,
                              command: list[str], key: str, baseline: int,
                              seconds: int, ceiling: int,
                              allocations: tuple[tuple[str, int], ...]) -> NativeStageBudget:
    """One durable first-admission transition; missing records never mint clocks.

    The launcher creates both the immutable schedule and its empty ledger. Under
    the ledger's retained inode lock, record the admitted clock *before* creating
    the budget file. Interruption, deletion or mismatched copies therefore HOLD.
    The ledger is never unlinked/recreated by a consumer.
    """
    root = Path(repo_root).resolve()
    path = agent_bus_path(root, schedule["bus_dir"], "executors", "validation",
                          schedule["wave_id"] + ".schedule.json")
    ledger = path.with_suffix(".admissions.json")
    budget_path = path.parent / f"{schedule['invocation']}.{key}.budget.json"
    witness = budget_path.with_suffix(".admitted.json")
    for candidate in (path, ledger, budget_path, witness):
        if candidate.is_symlink() or not candidate.parent.resolve().is_relative_to(root):
            raise ValidationBudgetError("HOLD: validation storage identity is uncertain")
    if not path.is_file() or not ledger.is_file():
        raise ValidationBudgetError("HOLD: retained validation admission ledger disappeared")
    raw = path.read_text()
    if read_validation_schedule_transport(root, raw, bus_dir=schedule["bus_dir"]) != schedule:
        raise ValidationBudgetError("HOLD: retained validation schedule differs")
    with ledger.open("r+") as handle:
        # Admission has no stage clock yet. Never wait indefinitely for another
        # consumer or turn contention into a second first-admission attempt.
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValidationBudgetError("HOLD: validation admission ledger is already locked") from exc
        try:
            record = json.load(handle)
            if (set(record) != {"transport", "stages"} or record["transport"] != raw
                    or set(record["stages"]) != {"phase_b_executor", "commit_executor"}):
                raise ValueError("admission ledger identity")
            previous = record["stages"][key]
            if previous is None:
                if budget_path.exists() or witness.exists():
                    raise ValueError("unexplained budget without first admission")
                budget = admit_stage_budget(root, key=key, command=command, baseline=baseline,
                    seconds=seconds, ceiling=ceiling, allocations=allocations)._replace(invocation=schedule["invocation"])
                previous = budget.encode()
                record["stages"][key] = previous
                handle.seek(0)
                json.dump(record, handle)
                handle.truncate()
                handle.flush()
                os.fsync(handle.fileno())
                with witness.open("x") as target:
                    target.write(previous)
                    target.flush()
                    os.fsync(target.fileno())
                with budget_path.open("x") as target:
                    target.write(previous)
                    target.flush()
                    os.fsync(target.fileno())
            if (not budget_path.is_file() or budget_path.read_text() != previous
                    or not witness.is_file() or witness.read_text() != previous):
                raise ValueError("retained budget disappeared or differs; do not reset")
            budget = decode_stage_budget(previous, root, key=key, command=command)
            if (budget.invocation != schedule["invocation"] or budget.baseline != baseline
                    or budget.seconds != seconds or budget.ceiling != ceiling or budget.allocations != allocations):
                raise ValueError("retry cannot reset/change admitted allocation")
            return budget
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ValidationBudgetError(f"HOLD: invalid retained stage admission: {exc}") from exc


def validate_native_stage_context(repo_root: Path, *, key: str, wave_id: str | None = None,
                                  transport: str | None = None) -> NativeStageBudget | None:
    """A native entry point cannot drop the launch request or its elapsed clock."""
    raw = os.environ.get(VALIDATION_SCHEDULE_ENV)
    stage = os.environ.get(NATIVE_STAGE_BUDGET_ENV)
    if transport is not None and (type(transport) is not str or transport != raw):
        raise ValidationBudgetError("HOLD: native handoff lost/differs from admitted validation transport")
    if raw is None and stage is None:
        return None  # Existing scalar-timeout invocation, with no new authority.
    if raw is None or stage is None:
        raise ValidationBudgetError("HOLD: native validation request requires its admitted stage clock")
    schedule = read_validation_schedule_transport(repo_root, raw)
    budget = decode_stage_budget(stage, repo_root, key=key, command=[sys.executable, *sys.argv])
    if wave_id is not None and schedule["wave_id"] != wave_id:
        raise ValidationBudgetError("HOLD: native stage wave mismatch")
    allocations = validation_schedule_requirements(repo_root, schedule["request"]["validation_seconds"])[key]
    if (budget.invocation != schedule["invocation"] or budget.seconds != schedule["request"][key]
            or budget.allocations != allocations):
        raise ValidationBudgetError("HOLD: native stage allocation/invocation mismatch")
    return budget


def copy_launch_wave_override_authority(
    record: dict[str, Any], *, required: bool = False,
) -> dict[str, Any]:
    """Copy admitted launch overrides without inferring defaults or role pins.

    This is transport/schema validation only. The launcher separately compares
    these exact values against its frozen config and single-use receipt.
    Agent names remain configuration-owned, not a provider allowlist here.
    """
    key = "launch_wave_override_authority"
    if key not in record and not required:
        return {}
    value = record.get(key)
    fields = {"version", "implementer_agent", "reviewer_agent", "pager_route", "max_turns"}
    if type(value) is not dict or set(value) not in (fields, fields | {"validation_schedule"}):
        raise ExecutorCommonError(f"{key} requires the complete version-1 object")
    if "validation_schedule" in value:
        request = value["validation_schedule"]
        if type(request) is not dict or set(request) != {"validation_seconds", "phase_b_executor", "commit_executor"}:
            raise ValidationBudgetError("HOLD: malformed launch validation schedule")
        for name, seconds in request.items():
            _budget_positive_int(seconds, name)
    if type(value["version"]) is not int or value["version"] != 1:
        raise ExecutorCommonError(f"{key} version must be exactly integer 1")
    for field in ("implementer_agent", "reviewer_agent", "pager_route"):
        item = value[field]
        if type(item) is not str or item != item.strip():
            raise ExecutorCommonError(f"{key}.{field} must be an exact string")
    if value["pager_route"] not in {"", "codex", "claude", "both", "notify-only"}:
        raise ExecutorCommonError(f"{key}.pager_route is unsupported")
    turns = value["max_turns"]
    if turns is not None and (type(turns) is not int or not 1 <= turns <= 1000):
        raise ExecutorCommonError(f"{key}.max_turns must be null or an integer in 1..1000")
    return {key: copy.deepcopy(value)}


def normalize_agent_bus_dir(bus_dir: str | Path | None = None) -> Path:
    """Return the repo-relative active agent bus directory.

    The executor owns exactly two runtime bus shapes in this wave:
    ``.agent_bus`` and repo-root namespaced buses like ``.agent_bus-test``.
    Arbitrary in-repo directories, nested paths, absolute paths, traversal, and
    symlink indirection are deliberately rejected by the resolver below.
    """
    if bus_dir is None:
        return DEFAULT_AGENT_BUS_DIR
    raw = str(bus_dir).strip()
    if not raw:
        return DEFAULT_AGENT_BUS_DIR
    if "\\" in raw:
        raise ExecutorCommonError(f"Invalid --bus-dir {raw!r}: backslashes are not allowed")
    raw = raw.rstrip("/")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise ExecutorCommonError(f"Invalid --bus-dir {raw!r}: absolute paths are not allowed")
    parts = candidate.parts
    if len(parts) != 1 or any(part in {"", ".", ".."} for part in parts):
        raise ExecutorCommonError(
            f"Invalid --bus-dir {raw!r}: only repo-root .agent_bus or .agent_bus-<id> is allowed"
        )
    name = parts[0]
    if name == DEFAULT_AGENT_BUS_DIR.name:
        return DEFAULT_AGENT_BUS_DIR
    if AGENT_BUS_NAMESPACE_RE.fullmatch(name):
        return Path(name)
    raise ExecutorCommonError(
        f"Invalid --bus-dir {raw!r}: expected .agent_bus or .agent_bus-<id>"
    )


def resolve_agent_bus_dir(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
    """Resolve and validate the active agent bus directory under repo_root."""
    root = Path(repo_root).resolve()
    rel = normalize_agent_bus_dir(bus_dir)
    candidate = root / rel.name
    if candidate.exists():
        if candidate.is_symlink():
            raise ExecutorCommonError(f"Invalid --bus-dir {rel}: bus directory must not be a symlink")
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise ExecutorCommonError(f"Invalid --bus-dir {rel}: cannot resolve bus directory: {exc}") from exc
        if resolved != candidate:
            raise ExecutorCommonError(f"Invalid --bus-dir {rel}: resolved path escapes repo-root bus directory")
    else:
        resolved = candidate.resolve(strict=False)
        if resolved != candidate:
            raise ExecutorCommonError(f"Invalid --bus-dir {rel}: resolved path escapes repo-root bus directory")
    return candidate


def agent_bus_relpath(bus_dir: str | Path | None = None, *parts: str | Path) -> Path:
    """Build a repo-relative path under the active bus."""
    rel = normalize_agent_bus_dir(bus_dir)
    for part in parts:
        rel = rel / part
    return rel


def agent_bus_path(repo_root: Path, bus_dir: str | Path | None = None, *parts: str | Path) -> Path:
    """Build an absolute path under the active bus after resolver validation."""
    path = resolve_agent_bus_dir(repo_root, bus_dir)
    for part in parts:
        path = path / part
    return path


def routing_record_path(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
    return agent_bus_path(repo_root, bus_dir, "meta", "post_merge_routing.json")


def bridge_config_path(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
    return agent_bus_path(repo_root, bus_dir, "bridge_config.json")


def _bridge_config_seed_candidates(repo_root: Path, bus_dir: str | Path | None = None) -> list[Path]:
    """Return trusted bridge_config sources for seeding an active bus."""
    root = Path(repo_root)
    active_rel = agent_bus_relpath(bus_dir)
    candidates: list[Path] = []

    same_repo_default = root / DEFAULT_AGENT_BUS_DIR / "bridge_config.json"
    if active_rel != DEFAULT_AGENT_BUS_DIR:
        candidates.append(same_repo_default)

    try:
        wt_out = subprocess.check_output(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(root),
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        wt_out = ""
    main_path: Path | None = None
    for line in wt_out.splitlines():
        if line.startswith("worktree "):
            main_path = Path(line[len("worktree "):].strip())
            break
    if main_path is not None:
        try:
            same_worktree = main_path.resolve() == root.resolve()
        except OSError:
            same_worktree = False
        if not same_worktree:
            candidates.append(main_path / active_rel / "bridge_config.json")
            if active_rel != DEFAULT_AGENT_BUS_DIR:
                candidates.append(main_path / DEFAULT_AGENT_BUS_DIR / "bridge_config.json")

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        key = candidate.resolve(strict=False)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def ensure_bridge_config_path(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
    """Return the active bridge config path, seeding namespaced buses if needed.

    The bridge config is invocation configuration, not pipeline runtime state.
    A fresh namespaced bus may start empty because bus directories are ignored,
    so copy the canonical default config into the active bus before adapter
    loading. If no trusted source exists, the caller's normal config load still
    fails closed with its existing error.
    """
    config_path = bridge_config_path(repo_root, bus_dir)
    if config_path.exists():
        return config_path
    for source in _bridge_config_seed_candidates(repo_root, bus_dir):
        if not source.exists() or source == config_path:
            continue
        if source.is_symlink() or source.parent.is_symlink():
            continue
        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, config_path)
        break
    return config_path


def is_agent_bus_runtime_path(path: str | Path) -> bool:
    """Return True for repo-root .agent_bus or .agent_bus-* runtime paths."""
    raw = str(path).replace("\\", "/").strip()
    if not raw:
        return False
    raw = raw[2:] if raw.startswith("./") else raw
    first = raw.split("/", 1)[0]
    return first == ".agent_bus" or first.startswith(".agent_bus-")


def ensure_git_worktree_clean(repo_root: Path, *, context: str = "worktree") -> None:
    """Fail closed when a git worktree has dirty non-runtime state."""
    root = Path(repo_root)
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ExecutorCommonError(
            f"Cannot inspect {context} dirty-worktree state: {exc}"
        ) from exc
    dirty = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        path_part = line[3:].strip()
        if is_agent_bus_runtime_path(path_part):
            continue
        dirty.append(line)
    if dirty:
        sample = ", ".join(line[3:].strip() or line.strip() for line in dirty[:5])
        suffix = "" if len(dirty) <= 5 else f", +{len(dirty) - 5} more"
        raise ExecutorCommonError(
            f"dirty-worktree scope creep: {context} has {len(dirty)} dirty path(s) "
            f"({sample}{suffix}); teammate worktree dispatch refuses to hide local changes"
        )


def current_review_mode_reason() -> str | None:
    """Return the first active agent-review mode marker, if any."""
    for name in REVIEW_MODE_ENV_VARS:
        raw = os.getenv(name, "").strip()
        if raw and raw.lower() not in {"0", "false", "no", "off"}:
            return f"{name}={raw}"
    return None


def ensure_not_agent_review_mode(surface: str) -> None:
    """Fail closed when live control-plane surfaces are invoked from review mode."""
    reason = current_review_mode_reason()
    if reason is None:
        return
    raise ExecutorCommonError(
        f"{surface} cannot run inside agent review mode ({reason}). "
        "Review agents may inspect control-plane code, diffs, and tests, but "
        "must not invoke live executor/supervisor paths."
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge nested config dicts without discarding default subkeys."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def merge_executor_config_overrides(overrides: dict[str, Any]) -> dict[str, Any]:
    """Apply config overrides on top of the canonical executor defaults.

    After the deep-merge, derive ``backends`` and ``bridge_reviewers`` from the
    merged ``role_agents`` via the single canonical rule (:func:`apply_role_agents`,
    invoked through :func:`_materialize_role_agents`). This makes the bare-defaults
    fallback (``merge_executor_config_overrides({})``) and every caller that routes a
    config fallback through this function — notably ``executor_dispatch.load_config``'s
    missing-config and role-only ``--config`` branches — fully consistent: the static
    ``DEFAULT_EXECUTOR_CONFIG`` ``reviewer`` / ``post_merge_supervisor`` /
    ``dialectic_executor`` / ``bridge_reviewers`` literals can no longer drift from
    ``role_agents``, and a role-only override config materializes its derived reviewer
    backends here instead of leaking the default provider through.

    Derivation here is CONFIG-ONLY (``use_env_overrides=False``); the runtime loader
    (:func:`load_executor_config`) re-materializes WITH environment overrides on top,
    so env-shadow precedence is unchanged. ``commit_executor`` is never derived (it is
    not in the implementer/reviewer backend key sets), so it stays as configured.

    When *overrides* does not pin ``role_agents`` (the bare/missing-config fallback —
    ``merge_executor_config_overrides({})`` and ``load_executor_config``'s missing
    branch), the role selection is sourced from the committed ``executor_config.json``
    via :func:`_fallback_role_agents` rather than the static
    ``DEFAULT_EXECUTOR_CONFIG['role_agents']`` literal. ``set_roles.py`` writes that
    committed file, so the fallback can never drift from a switch and no manual DEFAULT
    edit is ever required; the literal is used only when the committed file is truly
    absent.

    On that same bare/missing-config branch, :func:`_import_menu_only_agent_defaults`
    additively copies the ``bridge_agent_defaults`` menu entry of any SELECTED agent that
    is declared in the committed menu but ABSENT from ``DEFAULT_EXECUTOR_CONFIG`` (a
    menu-only provider, e.g. a ``fable`` the founder added to the menu), so the
    materialized config keeps that agent's model / effort / display_name / adapter
    settings instead of routing backends/bridge_reviewers to an agent with no resolvable
    defs. Agents already supplied by ``DEFAULT_EXECUTOR_CONFIG`` (claude/codex) are never
    overwritten. An override that DOES carry ``role_agents`` is authoritative and is left
    untouched (its explicit selection wins through :func:`_materialize_role_agents`, and
    its committed menu already deep-merges in, so no import is needed there).
    """
    if not isinstance(overrides, dict):
        raise ExecutorCommonError("executor config overrides must be a JSON object")
    merged = _deep_merge(DEFAULT_EXECUTOR_CONFIG, overrides)
    if "role_agents" not in overrides:
        merged["role_agents"] = _fallback_role_agents()
        _import_menu_only_agent_defaults(merged)
    return _materialize_role_agents(merged, raw_overrides=overrides, use_env_overrides=False)


def _apply_int_env_override(
    section: dict[str, Any],
    key: str,
    raw_value: str | None,
) -> None:
    if not raw_value:
        return
    try:
        section[key] = int(raw_value)
    except (TypeError, ValueError):
        return


def apply_recovery_config_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Materialize dispatcher recovery overrides without mutating config files.

    Recovery gate communicates Tier 2 timeout adjustments through environment
    variables so dispatcher retries and child executors can share the same
    adjusted config while tracked executor_config.json stays read-only.
    """
    if not isinstance(config, dict):
        return config
    if (NATIVE_STAGE_BUDGET_ENV in os.environ or VALIDATION_SCHEDULE_ENV in os.environ) and any(
        key in os.environ for key in (
            "RCX_RECOVERY_TIMEOUT_OVERRIDE", "RCX_RECOVERY_TIMEOUT_KEY",
            "RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE",
            "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY",
        )
    ):
        raise ValidationBudgetError("HOLD: scalar recovery overrides cannot change an admitted budget key or baseline")

    timeouts = config.setdefault("timeouts", {})
    if isinstance(timeouts, dict):
        timeout_key = os.environ.get("RCX_RECOVERY_TIMEOUT_KEY", "phase_b_executor")
        _apply_int_env_override(
            timeouts,
            timeout_key,
            os.environ.get("RCX_RECOVERY_TIMEOUT_OVERRIDE"),
        )
        _apply_int_env_override(
            timeouts,
            "phase_b_implementer_stale",
            os.environ.get("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE"),
        )

    bridge_turn_timeouts = config.setdefault("bridge_turn_timeouts", {})
    if isinstance(bridge_turn_timeouts, dict):
        bridge_turn_key = os.environ.get(
            "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY",
            "phase_b",
        )
        _apply_int_env_override(
            bridge_turn_timeouts,
            bridge_turn_key,
            os.environ.get("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE"),
        )

    return config


def _nonempty_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _legacy_role_agent_override(raw_overrides: dict[str, Any], role: str) -> str | None:
    if not isinstance(raw_overrides, dict):
        return None
    if role == "implementer":
        backends = raw_overrides.get("backends", {})
        if isinstance(backends, dict):
            for key in ("phase_b_executor", "phase_a_executor", "bot_remediation"):
                candidate = _nonempty_str(backends.get(key))
                if candidate is not None:
                    return candidate
        return None
    if role == "reviewer":
        bridge_reviewers = raw_overrides.get("bridge_reviewers", {})
        if isinstance(bridge_reviewers, dict):
            for key in ("phase_a", "phase_b"):
                candidate = _nonempty_str(bridge_reviewers.get(key))
                if candidate is not None:
                    return candidate
        backends = raw_overrides.get("backends", {})
        if isinstance(backends, dict):
            for key in REVIEW_OVERRIDE_BACKEND_KEYS:
                candidate = _nonempty_str(backends.get(key))
                if candidate is not None:
                    return candidate
    return None


def _explicit_role_agent_override(raw_overrides: dict[str, Any], role: str) -> str | None:
    if not isinstance(raw_overrides, dict):
        return None
    role_agents = raw_overrides.get("role_agents", {})
    if not isinstance(role_agents, dict):
        return None
    return _nonempty_str(role_agents.get(role))


def resolve_role_agent(
    config: dict[str, Any],
    role: str,
    *,
    raw_overrides: dict[str, Any] | None = None,
    use_env_overrides: bool = True,
) -> str:
    """Resolve the configured bridge agent for a role family.

    Roles are currently:
    - implementer: Phase A, Phase B, bot remediation
    - reviewer: bridge reviewers, post-merge supervisor, dialectic reviewer

    Backward compatibility:
    - Old configs that only set `backends` / `bridge_reviewers` still work.
    - `RCX_BRIDGE_REVIEWER_OVERRIDE` remains an alias for reviewer override.
    """
    default_role_agents = DEFAULT_EXECUTOR_CONFIG.get("role_agents", {})
    default_agent = _nonempty_str(default_role_agents.get(role)) or "codex"
    raw_overrides = raw_overrides if isinstance(raw_overrides, dict) else {}

    if (
        use_env_overrides
        and config.get(ROLE_AGENT_ENV_OVERRIDES_APPLY_KEY) is False
        and (not raw_overrides or raw_overrides is config)
    ):
        use_env_overrides = False

    if use_env_overrides:
        for env_name in ROLE_AGENT_ENV_VARS.get(role, ()):
            candidate = _nonempty_str(os.environ.get(env_name))
            if candidate is not None:
                return candidate

    explicit = _explicit_role_agent_override(raw_overrides, role)
    if explicit is not None:
        return explicit

    legacy = _legacy_role_agent_override(raw_overrides, role)
    if legacy is not None:
        return legacy

    role_agents = config.get("role_agents", {})
    if isinstance(role_agents, dict):
        candidate = _nonempty_str(role_agents.get(role))
        if candidate is not None:
            return candidate

    return default_agent


def resolve_committed_role_agent(config: dict[str, Any], role: str) -> str:
    """Resolve a role's agent from committed config only, ignoring env shadows.

    Read-side counterpart to apply_role_agents: same precedence as
    resolve_role_agent (explicit role_agents -> legacy backends/bridge_reviewers
    -> role-aware default) MINUS the environment-variable override loop.

    set_roles.py uses this so a partial switch (e.g. only --reviewer) preserves
    the role it is NOT changing from the actual committed file state — including
    legacy configs that predate role_agents and carry only backends/
    bridge_reviewers. Env overrides are deliberately excluded so a transient
    runtime shadow is never baked into the written config; set_roles reports an
    active shadow as a separate warning instead.
    """
    explicit = _explicit_role_agent_override(config, role)
    if explicit is not None:
        return explicit
    legacy = _legacy_role_agent_override(config, role)
    if legacy is not None:
        return legacy
    default_role_agents = DEFAULT_EXECUTOR_CONFIG.get("role_agents", {})
    return _nonempty_str(default_role_agents.get(role)) or "codex"


def _committed_executor_config_path() -> Path:
    """Path to the committed executor_config.json that set_roles.py maintains.

    It sits next to this module (``mu/tools/executors/``), so every checkout and
    linked worktree carries it, and it is exactly the file ``set_roles.py`` writes.
    Factored out as the single seam the bare/missing-config ``role_agents`` fallback
    reads (:func:`_fallback_role_agents`) so the resolution can be redirected in
    tests without mutating the real tracked file.
    """
    return Path(__file__).resolve().parent / "executor_config.json"


def _fallback_role_agents() -> dict[str, str]:
    """Resolve ``role_agents`` for the bare/missing-config fallback from the committed file.

    ``set_roles.py`` is the single role switch; it writes ``role_agents`` into the
    committed ``executor_config.json`` next to this module. The bare/missing-config
    fallback therefore reads THAT committed file so a switch can never leave the
    fallback resolving a stale provider — no manual ``DEFAULT_EXECUTOR_CONFIG``
    ``role_agents`` hand-edit is ever required after a switch. The static
    ``DEFAULT_EXECUTOR_CONFIG['role_agents']`` literal is the last-resort source, used
    only when that committed file is truly absent or unreadable.

    Polymorphic: whatever implementer/reviewer the committed file names is returned
    verbatim (via the same committed-config precedence as
    :func:`resolve_committed_role_agent`: explicit ``role_agents`` -> legacy
    ``backends`` / ``bridge_reviewers`` -> the literal). No provider is hardcoded in
    this path.
    """
    committed: dict[str, Any] = {}
    try:
        loaded = json.loads(_committed_executor_config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        loaded = None
    if isinstance(loaded, dict):
        committed = loaded
    return {
        role: resolve_committed_role_agent(committed, role)
        for role in ("implementer", "reviewer")
    }


def _committed_bridge_agent_defaults() -> dict[str, dict[str, Any]]:
    """Return the committed ``executor_config.json``'s ``bridge_agent_defaults`` menu.

    Reads the SAME committed-file seam (:func:`_committed_executor_config_path`) that
    :func:`_fallback_role_agents` uses for the bare/missing-config role selection, so the
    menu-def import on that fallback branch resolves the agent MENU from exactly the file
    ``set_roles.py`` writes — no second file path is introduced. Returns ``{}`` when the
    committed file is absent, unreadable, not a JSON object, or carries no
    ``bridge_agent_defaults`` object; only ``str`` -> ``dict`` menu entries are retained.
    """
    try:
        loaded = json.loads(_committed_executor_config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    defaults = loaded.get("bridge_agent_defaults")
    if not isinstance(defaults, dict):
        return {}
    return {
        name: entry
        for name, entry in defaults.items()
        if isinstance(name, str) and isinstance(entry, dict)
    }


def _import_menu_only_agent_defaults(merged: dict[str, Any]) -> None:
    """Import committed MENU-ONLY agents' ``bridge_agent_defaults`` into the bare fallback.

    On the bare/missing-config fallback branch of :func:`merge_executor_config_overrides`
    the role selection is imported from the committed ``executor_config.json`` (via
    :func:`_fallback_role_agents`), but the static ``DEFAULT_EXECUTOR_CONFIG`` supplies only
    the claude/codex ``bridge_agent_defaults`` menu. If the committed file SELECTS a
    MENU-ONLY agent — one declared in the committed ``bridge_agent_defaults`` menu but
    ABSENT from ``DEFAULT_EXECUTOR_CONFIG['bridge_agent_defaults']`` (e.g. a provider the
    founder added to the menu) — its menu definition (model / effort / display_name /
    adapter settings) would otherwise be lost, leaving the routed backends/bridge_reviewers
    pointing at an agent with no resolvable defs.

    For every agent NAMED by the resolved ``role_agents`` (the same names the derived
    ``backends`` / ``bridge_reviewers`` carry) that is present in the committed menu but
    ABSENT from ``DEFAULT_EXECUTOR_CONFIG``, copy its committed ``bridge_agent_defaults``
    entry into the materialized config's menu. Additive only: an agent already supplied by
    ``DEFAULT_EXECUTOR_CONFIG`` (claude/codex) is skipped and never overwritten, and an
    entry already present in the materialized menu is left intact. Polymorphic — no provider
    name is hardcoded; the copy keys off "in the committed menu, not in DEFAULT". Mutates
    *merged* in place; role resolution and the derived backends are untouched (only the
    ``bridge_agent_defaults`` menu grows).
    """
    role_agents = merged.get("role_agents")
    if not isinstance(role_agents, dict):
        return
    referenced = {
        name
        for name in (_nonempty_str(value) for value in role_agents.values())
        if name is not None
    }
    default_defaults = DEFAULT_EXECUTOR_CONFIG.get("bridge_agent_defaults", {})
    default_names = set(default_defaults) if isinstance(default_defaults, dict) else set()
    menu_only = {name for name in referenced if name not in default_names}
    if not menu_only:
        return
    committed_defaults = _committed_bridge_agent_defaults()
    if not committed_defaults:
        return
    materialized_defaults = merged.setdefault("bridge_agent_defaults", {})
    if not isinstance(materialized_defaults, dict):
        return
    for name in menu_only:
        if name in materialized_defaults:
            continue
        committed_entry = committed_defaults.get(name)
        if isinstance(committed_entry, dict):
            materialized_defaults[name] = copy.deepcopy(committed_entry)


def apply_role_agents(
    config: dict[str, Any],
    implementer_agent: str,
    reviewer_agent: str,
) -> dict[str, Any]:
    """Write role_agents and the derived backends/bridge_reviewers into config in place.

    Single source of the derivation rule, shared by _materialize_role_agents (runtime
    load) and set_roles.py (config writer) so the role_agents switch and every derived
    field stay consistent.
    """
    role_agents = config.setdefault("role_agents", {})
    role_agents["implementer"] = implementer_agent
    role_agents["reviewer"] = reviewer_agent

    backends = config.setdefault("backends", {})
    for key in IMPLEMENTER_BACKEND_KEYS:
        backends[key] = implementer_agent
    for key in REVIEW_OVERRIDE_BACKEND_KEYS:
        backends[key] = reviewer_agent

    bridge_reviewers = config.setdefault("bridge_reviewers", {})
    for key in REVIEWER_BRIDGE_KEYS:
        bridge_reviewers[key] = reviewer_agent

    return config


def _role_agent_env_overrides_apply(repo_root: Path) -> bool:
    """Return whether role-agent env overrides are scoped to this repo root.

    Unscoped overrides keep the historical behavior. Launch-wave scoped overrides
    include a root marker so those env vars do not rewrite temporary config roots
    created by broad commit/pre-push tests.
    """
    scope_root = _nonempty_str(os.environ.get(ROLE_AGENT_OVERRIDE_REPO_ROOT_ENV))
    if scope_root is None:
        return True
    try:
        return Path(scope_root).expanduser().resolve() == Path(repo_root).expanduser().resolve()
    except OSError:
        return False


def _materialize_role_agents(
    config: dict[str, Any],
    *,
    raw_overrides: dict[str, Any] | None = None,
    use_env_overrides: bool = True,
) -> dict[str, Any]:
    implementer_agent = resolve_role_agent(
        config,
        "implementer",
        raw_overrides=raw_overrides,
        use_env_overrides=use_env_overrides,
    )
    reviewer_agent = resolve_role_agent(
        config,
        "reviewer",
        raw_overrides=raw_overrides,
        use_env_overrides=use_env_overrides,
    )
    return apply_role_agents(config, implementer_agent, reviewer_agent)


def load_bridge_agent_catalog(
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load optional display metadata for configured bridge agents."""
    config_path = bridge_config_path(repo_root, bus_dir)
    payload: dict[str, Any] = {}
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            loaded = {}
        if isinstance(loaded, dict):
            payload = loaded
    agents = payload.get("agents", {})
    if not isinstance(agents, dict):
        agents = {}
    catalog = {
        name: data
        for name, data in agents.items()
        if isinstance(name, str) and isinstance(data, dict)
    }
    defaults = load_executor_config(repo_root).get("bridge_agent_defaults", {})
    if isinstance(defaults, dict):
        for name, data in defaults.items():
            if not isinstance(name, str) or not isinstance(data, dict):
                continue
            display_name = _nonempty_str(data.get("display_name"))
            if display_name is not None:
                catalog.setdefault(name, {})["display_name"] = display_name
    return catalog


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _selector_value(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ExecutorCommonError(f"{label} selector value must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise ExecutorCommonError(f"{label} selector value cannot be empty")
    if cleaned != value:
        raise ExecutorCommonError(f"{label} selector value must not contain outer whitespace")
    if cleaned.startswith("-"):
        raise ExecutorCommonError(f"{label} selector value is missing before {cleaned!r}")
    return cleaned


def _bridge_command_tokens(cmd: Any, *, selected_agent: str) -> list[str]:
    if not isinstance(cmd, list) or not cmd:
        raise ExecutorCommonError(
            f"bridge_config agent {selected_agent!r} cmd must be a non-empty list"
        )
    tokens: list[str] = []
    for index, token in enumerate(cmd):
        if not isinstance(token, str):
            raise ExecutorCommonError(
                f"bridge_config agent {selected_agent!r} cmd token {index} "
                "must be a string"
            )
        tokens.append(token)
    return tokens


def _single_flag_selector(
    cmd: list[str],
    flags: tuple[str, ...],
    label: str,
) -> tuple[str, str] | None:
    values: list[tuple[str, str]] = []
    for index, token in enumerate(cmd):
        if token not in flags:
            continue
        if index + 1 >= len(cmd):
            raise ExecutorCommonError(f"{label} selector {token!r} is missing a value")
        values.append((token, _selector_value(cmd[index + 1], label)))
    if len(values) > 1:
        raise ExecutorCommonError(
            f"{label} selector is duplicate or conflicting: "
            + ", ".join(flag for flag, _value in values)
        )
    return values[0] if values else None


def _model_reasoning_effort_value(raw: str) -> str:
    try:
        parts = shlex.split(raw)
    except ValueError as exc:
        raise ExecutorCommonError(
            f"model_reasoning_effort selector is malformed: {exc}"
        ) from exc
    if len(parts) != 1:
        raise ExecutorCommonError(
            "model_reasoning_effort selector must contain exactly one value"
        )
    return _selector_value(parts[0], "model_reasoning_effort")


def _single_effort_selector(cmd: list[str]) -> tuple[str, str] | None:
    values: list[tuple[str, str]] = []
    flag_value = _single_flag_selector(cmd, ("--effort",), "effort")
    if flag_value is not None:
        values.append(flag_value)
    prefix = "model_reasoning_effort="
    for token in cmd:
        if token.startswith(prefix):
            values.append(
                (
                    "model_reasoning_effort",
                    _model_reasoning_effort_value(token[len(prefix):]),
                )
            )
    if len(values) > 1:
        raise ExecutorCommonError(
            "effort selector is duplicate or conflicting: "
            + ", ".join(flag for flag, _value in values)
        )
    return values[0] if values else None


def reviewer_launch_provenance(
    repo_root: Path,
    *,
    bus_dir: str | Path | None,
    selected_agent: str,
) -> dict[str, Any]:
    """Return launch-bound reviewer command provenance from a namespaced bus.

    The receipt needs enough identity to detect selected-agent, command, and
    bridge-config drift without serializing command tokens, environment values,
    or other adapter secrets. The only unhashed selector values retained are
    the model and effort values required for reviewer authority.
    """
    selected = _selector_value(selected_agent, "selected agent")
    rel_bus = normalize_agent_bus_dir(bus_dir)
    if rel_bus == DEFAULT_AGENT_BUS_DIR:
        raise ExecutorCommonError(
            "reviewer launch provenance requires a namespaced .agent_bus-<id> bus"
        )
    config_path = bridge_config_path(repo_root, rel_bus)
    try:
        config_bytes = config_path.read_bytes()
    except OSError as exc:
        raise ExecutorCommonError(
            f"cannot read launch-bound bridge_config at {config_path}: {exc}"
        ) from exc
    try:
        loaded = json.loads(config_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutorCommonError(
            f"launch-bound bridge_config is malformed at {config_path}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise ExecutorCommonError("launch-bound bridge_config must be a JSON object")
    agents = loaded.get("agents")
    if not isinstance(agents, dict):
        raise ExecutorCommonError("launch-bound bridge_config must contain an agents object")
    agent_config = agents.get(selected)
    if not isinstance(agent_config, dict):
        raise ExecutorCommonError(
            f"selected reviewer agent {selected!r} is absent from launch-bound bridge_config"
        )
    cmd = _bridge_command_tokens(agent_config.get("cmd"), selected_agent=selected)
    model = _single_flag_selector(cmd, ("--model", "-m"), "model")
    if model is None:
        raise ExecutorCommonError(
            f"selected reviewer agent {selected!r} command is missing --model/-m"
        )
    effort = _single_effort_selector(cmd)
    if effort is None:
        raise ExecutorCommonError(
            f"selected reviewer agent {selected!r} command is missing effort selector"
        )
    return {
        "version": REVIEWER_LAUNCH_PROVENANCE_VERSION,
        "selected_agent": selected,
        "model": model[1],
        "effort": effort[1],
        "command_sha256": _json_sha256(cmd),
        "bridge_config_path": agent_bus_relpath(rel_bus, "bridge_config.json").as_posix(),
        "bridge_config_sha256": hashlib.sha256(config_bytes).hexdigest(),
    }


def _set_bridge_cmd_model(cmd: list[Any], model: str) -> bool:
    """Overwrite the model token (the value after ``--model`` or ``-m``) in *cmd*.

    Returns True if the token changed. Only the single model value is rewritten; the
    flag itself and every other cmd arg are left in place. A flag with no following
    value (trailing position) is ignored rather than indexed out of range.
    """
    for index in range(len(cmd) - 1):
        if cmd[index] in ("--model", "-m"):
            if cmd[index + 1] == model:
                return False
            cmd[index + 1] = model
            return True
    return False


def _set_bridge_cmd_effort(cmd: list[Any], effort: str) -> bool:
    """Overwrite the reasoning-effort token in *cmd*.

    Handles both shapes the live bridge_config uses: an explicit ``--effort <value>``
    flag (Claude) and a ``-c model_reasoning_effort="<value>"`` arg (Codex). Returns
    True if the token changed; only the effort value is rewritten.
    """
    for index in range(len(cmd) - 1):
        if cmd[index] == "--effort":
            if cmd[index + 1] == effort:
                return False
            cmd[index + 1] = effort
            return True
    prefix = "model_reasoning_effort="
    for index, token in enumerate(cmd):
        if isinstance(token, str) and token.startswith(prefix):
            replacement = f'{prefix}"{effort}"'
            if token == replacement:
                return False
            cmd[index] = replacement
            return True
    return False


def _bridge_cmd_max_turns_value(cmd: list[Any]) -> str | None:
    """Return the value after ``--max-turns`` in *cmd* (as a string), or None if absent."""
    for index in range(len(cmd) - 1):
        if cmd[index] == "--max-turns":
            return str(cmd[index + 1])
    return None


def _set_bridge_cmd_max_turns(cmd: list[Any], max_turns: str) -> bool:
    """Overwrite the value after ``--max-turns`` in *cmd*. Returns True if it changed.

    Only the single value token is rewritten; the flag and every other arg are left in
    place. A ``--max-turns`` flag with no following value (trailing) is ignored.
    """
    for index in range(len(cmd) - 1):
        if cmd[index] == "--max-turns":
            if str(cmd[index + 1]) == str(max_turns):
                return False
            cmd[index + 1] = str(max_turns)
            return True
    return False


def _bridge_cmd_executable_name(cmd: list[Any]) -> str:
    if not cmd:
        return ""
    token = str(cmd[0]).strip()
    return Path(token).name


def _looks_like_codex_exec_cmd(cmd: list[Any]) -> bool:
    return (
        len(cmd) >= 2
        and _bridge_cmd_executable_name(cmd) == "codex"
        and cmd[1] == "exec"
    )


def _looks_like_claude_cmd(cmd: list[Any]) -> bool:
    return _bridge_cmd_executable_name(cmd) == "claude"


def _ensure_bridge_cmd_max_turns(
    cmd: list[Any], max_turns: int | str
) -> tuple[bool, str | None]:
    """Ensure *cmd* carries a supported max-turn override.

    Returns ``(changed, error)``. Existing ``--max-turns`` tokens are updated
    in place, except for Codex ``exec`` where no verified max-turn command or
    config key exists. Claude commands without the token receive the CLI flag.
    """
    max_turns_text = str(max_turns)
    if _looks_like_codex_exec_cmd(cmd):
        return (
            False,
            "codex exec has no verified max-turn override; refusing to append "
            "unsupported --max-turns or -c max_turns=<n>",
        )
    for index, token in enumerate(cmd):
        if token != "--max-turns":
            continue
        if index == len(cmd) - 1:
            cmd.append(max_turns_text)
            return True, None
        if str(cmd[index + 1]) == max_turns_text:
            return False, None
        cmd[index + 1] = max_turns_text
        return True, None
    if not _looks_like_claude_cmd(cmd):
        return False, "agent command has no supported --max-turns position"
    cmd.extend(["--max-turns", max_turns_text])
    return True, None


def apply_bridge_config_max_turns_override(
    repo_root: Path,
    max_turns: int,
    agent_names: list[str] | tuple[str, ...] | set[str] | frozenset[str],
    bus_dir: str | Path | None = None,
) -> dict[str, Any] | None:
    """Apply a per-wave max-turn override to selected live bridge adapters.

    This intentionally edits only the active bus-local ``bridge_config.json``.
    It does not mutate committed executor defaults or discover unrelated buses.
    """
    config_path = bridge_config_path(repo_root, bus_dir)
    if not config_path.exists():
        return None
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(loaded, dict):
        return None
    agents = loaded.get("agents")
    if not isinstance(agents, dict):
        return None

    candidate = copy.deepcopy(loaded)
    candidate_agents = candidate.get("agents")
    if not isinstance(candidate_agents, dict):
        return None

    changed = False
    applied_agents: list[str] = []
    missing_agents: list[str] = []
    unsupported_agents: dict[str, str] = {}
    for name in sorted({str(agent).strip() for agent in agent_names if str(agent).strip()}):
        agent = candidate_agents.get(name)
        cmd = agent.get("cmd") if isinstance(agent, dict) else None
        if not isinstance(cmd, list):
            missing_agents.append(name)
            continue
        command_changed, error = _ensure_bridge_cmd_max_turns(cmd, max_turns)
        if error is not None:
            unsupported_agents[name] = error
            continue
        if command_changed:
            changed = True
        applied_agents.append(name)

    if missing_agents or unsupported_agents:
        return {
            "path": str(config_path),
            "max_turns": max_turns,
            "agents": [],
            "missing_agents": missing_agents,
            "unsupported_agents": unsupported_agents,
            "changed": False,
        }
    if changed:
        _atomic_write_text(config_path, json.dumps(candidate, indent=2) + "\n")
    return {
        "path": str(config_path),
        "max_turns": max_turns,
        "agents": applied_agents,
        "missing_agents": missing_agents,
        "unsupported_agents": unsupported_agents,
        "changed": changed,
    }


def _atomic_write_text(path: Path, text: str) -> None:
    """Write *text* to *path* atomically so readers never observe a torn write.

    Runtime loaders read these executor config files (executor_config.json and
    the live ``.agent_bus/bridge_config.json``) with an unguarded ``json.loads``,
    so a partial/truncated write would break every later config/adapter load.
    Write to a temp file in the SAME directory, flush+fsync it, then
    ``os.replace()`` onto the target -- an atomic rename on the same filesystem,
    so a crash mid-write leaves the complete old file, never invalid JSON.

    Preserve the target's existing permission bits across the swap: ``os.replace``
    is a rename, so the installed file would otherwise inherit
    ``tempfile.mkstemp``'s restrictive 0600 and lock out executor/observability
    processes running as a different user. Re-apply the prior mode before the
    rename; for a brand-new target fall back to the umask-aware default a normal
    create would produce.

    A per-module atomic writer matching the ones in set_roles.py and
    recovery_gate.py (set_roles uses its own copy for executor_config.json).
    """
    directory = path.parent
    try:
        preserve_mode: int | None = stat.S_IMODE(os.stat(path).st_mode)
    except FileNotFoundError:
        preserve_mode = None
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=f".{path.name}.", suffix=".tmp")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if preserve_mode is None:
            # Brand-new target: match what open()+write would produce under the
            # active umask instead of mkstemp's restrictive 0600.
            current_umask = os.umask(0)
            os.umask(current_umask)
            preserve_mode = 0o666 & ~current_umask
        os.chmod(tmp_path, preserve_mode)
        os.replace(tmp_path, path)
    except BaseException:
        # Never leave truncated temp residue behind on a failed write.
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise


def _load_example_bridge_agents(repo_root: Path) -> dict[str, Any]:
    """Load adapter shapes from the committed bridge_config example seed.

    Used to seed an adapter that is DECLARED in ``bridge_agent_defaults`` but ABSENT
    from a pre-existing live ``bridge_config['agents']`` (e.g. a newly-added menu agent
    such as ``fable`` on a bus created before that agent existed). Without seeding,
    activating such an agent as a role fails closed at ``get_adapter()`` with a missing
    adapter. Returns ``{}`` when the example is missing or unreadable.
    """
    example = Path(repo_root) / "mu" / "tools" / "agents" / "bridge_config.example.json"
    if not example.exists():
        return {}
    try:
        loaded = json.loads(example.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    agents = loaded.get("agents") if isinstance(loaded, dict) else None
    if not isinstance(agents, dict):
        return {}
    return {n: a for n, a in agents.items() if isinstance(n, str) and isinstance(a, dict)}


def sync_bridge_config_agents_from_defaults(
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> Path | None:
    """Sync bridge_config agents' model / effort / display_name from bridge_agent_defaults.

    Keep ``.agent_bus/bridge_config.json``'s per-agent provider settings aligned with
    ``executor_config.json``'s ``bridge_agent_defaults`` so the live provider config
    cannot drift from the committed default (2026-06-02: bridge_config ran the claude
    implementer on ``claude-opus-4-7`` while ``bridge_agent_defaults.claude`` said
    ``claude-opus-4-8``).

    Resolve the SINGLE primary bus via :func:`bridge_config_path` (no multi-bus / lane
    discovery) and mirror :func:`load_bridge_agent_catalog`'s read pattern. For each
    agent present in BOTH ``bridge_config['agents']`` and ``bridge_agent_defaults``,
    overwrite ONLY: the model token (after ``--model`` / ``-m`` in ``cmd``), the
    reasoning-effort token (the ``--effort`` value or the
    ``model_reasoning_effort="..."`` ``-c`` arg), and ``display_name``. Every other cmd
    arg, ``timeout_s``, ``mode``, ``prompt_via_stdin``, and ``env`` is left intact, and
    the file is rewritten only when a field actually changed.

    An agent DECLARED in ``bridge_agent_defaults`` but ABSENT from ``bridge_config``
    is SEEDED from the committed example (:func:`_load_example_bridge_agents`) before the
    update pass, so a newly-added menu agent (e.g. ``fable``) is invokable on a
    pre-existing bus instead of failing closed at ``get_adapter()``; an agent missing
    from BOTH ``bridge_agent_defaults`` and the example is left untouched.

    Graceful no-op (returns ``None``) when ``bridge_config.json`` is absent or
    unreadable; an agent missing from ``bridge_agent_defaults`` is skipped. Returns the
    resolved config path when the file was read (whether or not it changed).
    """
    config_path = bridge_config_path(repo_root, bus_dir)
    if not config_path.exists():
        return None
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(loaded, dict):
        return None
    agents = loaded.get("agents")
    if not isinstance(agents, dict):
        return None
    defaults = load_executor_config(repo_root).get("bridge_agent_defaults", {})
    if not isinstance(defaults, dict):
        return None

    changed = False
    # Seed adapters DECLARED in bridge_agent_defaults but ABSENT from this bus's
    # bridge_config (e.g. a newly-added menu agent such as 'fable' on a bus created
    # before that agent existed). Without this, activating such an agent as a role
    # fails closed at get_adapter() with "missing adapter ...". Copy the adapter shape
    # from the committed example seed; the update loop below then applies the default
    # model/effort/display. An agent missing from BOTH defaults and the example is left
    # untouched (the existing get_adapter fail-closed still guards it).
    example_agents = _load_example_bridge_agents(repo_root)
    for missing_name, missing_default in defaults.items():
        if (
            isinstance(missing_name, str)
            and isinstance(missing_default, dict)
            and missing_name not in agents
            and isinstance(example_agents.get(missing_name), dict)
        ):
            agents[missing_name] = copy.deepcopy(example_agents[missing_name])
            changed = True
    for name, agent in agents.items():
        if not isinstance(name, str) or not isinstance(agent, dict):
            continue
        default = defaults.get(name)
        if not isinstance(default, dict):
            # Agent absent from bridge_agent_defaults -> leave it untouched.
            continue
        cmd = agent.get("cmd")
        if isinstance(cmd, list):
            model = _nonempty_str(default.get("model"))
            if model is not None and _set_bridge_cmd_model(cmd, model):
                changed = True
            effort = _nonempty_str(default.get("effort")) or _nonempty_str(
                default.get("reasoning_effort")
            )
            if effort is not None and _set_bridge_cmd_effort(cmd, effort):
                changed = True
            # Sync --max-turns from the committed example adapter cmd (the canonical
            # adapter-shape source) so an EXISTING adapter with a stale --max-turns is
            # updated too, not only newly-seeded ones (PR #1098 bot P1: a bus that already
            # had fable/claude at --max-turns 50 kept 50 after the sync). model/effort/
            # display still come from bridge_agent_defaults; the turn budget lives in the
            # adapter cmd, whose canonical value is the example seed.
            example_entry = example_agents.get(name)
            example_cmd = example_entry.get("cmd") if isinstance(example_entry, dict) else None
            if isinstance(example_cmd, list):
                example_max_turns = _bridge_cmd_max_turns_value(example_cmd)
                if example_max_turns is not None and _set_bridge_cmd_max_turns(cmd, example_max_turns):
                    changed = True
        display_name = _nonempty_str(default.get("display_name"))
        if display_name is not None and agent.get("display_name") != display_name:
            agent["display_name"] = display_name
            changed = True

    if changed:
        _atomic_write_text(config_path, json.dumps(loaded, indent=2) + "\n")
    return config_path


def bridge_agent_display_name(
    repo_root: Path,
    agent_name: str,
    bus_dir: str | Path | None = None,
) -> str:
    catalog = load_bridge_agent_catalog(repo_root, bus_dir)
    raw = catalog.get(agent_name, {})
    display_name = _nonempty_str(raw.get("display_name"))
    if display_name is not None:
        return display_name
    return DEFAULT_AGENT_DISPLAY_NAMES.get(agent_name, agent_name.replace("_", " ").title())


def bridge_agent_status_name(
    repo_root: Path,
    agent_name: str,
    bus_dir: str | Path | None = None,
) -> str:
    display_name = bridge_agent_display_name(repo_root, agent_name, bus_dir)
    head = display_name.split()
    if head:
        return head[0]
    return agent_name.capitalize()


def configured_role_agents(
    repo_root: Path,
    config: dict[str, Any] | None = None,
    bus_dir: str | Path | None = None,
) -> dict[str, dict[str, str]]:
    config = config or load_executor_config(repo_root)
    roles: dict[str, dict[str, str]] = {}
    for role in ("implementer", "reviewer"):
        agent = resolve_role_agent(config, role, raw_overrides=config, use_env_overrides=False)
        roles[role] = {
            "agent": agent,
            "display_name": bridge_agent_display_name(repo_root, agent, bus_dir),
            "status_name": bridge_agent_status_name(repo_root, agent, bus_dir),
        }
    return roles


def load_executor_config(repo_root: Path) -> dict[str, Any]:
    """Load executor config, preserving default nested keys when partially set.

    Supports role-level agent switching via:
    - `role_agents.implementer` / `role_agents.reviewer` in executor_config.json
    - `RCX_IMPLEMENTER_AGENT_OVERRIDE`
    - `RCX_REVIEWER_AGENT_OVERRIDE`
    - legacy reviewer alias: `RCX_BRIDGE_REVIEWER_OVERRIDE`
    """
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    if not config_path.exists():
        # Missing-config fallback: route through the bare-defaults merge so the
        # role selection comes from the committed executor_config.json (the file
        # set_roles.py writes) via _fallback_role_agents, not the static
        # DEFAULT_EXECUTOR_CONFIG['role_agents'] literal. Keeps the fallback in
        # sync with a switch (no manual DEFAULT edit); the literal is used only
        # when that committed file is truly absent too.
        raw_overrides: dict[str, Any] = {}
        config = merge_executor_config_overrides({})
    else:
        raw_overrides = json.loads(config_path.read_text(encoding="utf-8"))
        config = merge_executor_config_overrides(raw_overrides)
    apply_recovery_config_env_overrides(config)
    role_env_overrides_apply = _role_agent_env_overrides_apply(repo_root)
    materialized = _materialize_role_agents(
        config,
        raw_overrides=raw_overrides,
        use_env_overrides=role_env_overrides_apply,
    )
    materialized[ROLE_AGENT_ENV_OVERRIDES_APPLY_KEY] = role_env_overrides_apply
    return materialized


def emit_pipeline_agent_event(
    repo_root: Path,
    *,
    bus_dir: str | Path | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Emit a pipeline pager event through the shared observability entrypoint."""
    try:
        from pipeline_agent_pager import emit_transition_event
    except ImportError:
        import importlib.util as _ilu
        import sys as _sys

        pager_path = (
            Path(__file__).resolve().parent.parent / "observability" / "pipeline_agent_pager.py"
        )
        spec = _ilu.spec_from_file_location("pipeline_agent_pager", str(pager_path))
        module = _ilu.module_from_spec(spec)
        assert spec.loader is not None
        # Cache before exec so a later emit resolves from sys.modules after the worktree (and __file__) is removed.
        _sys.modules["pipeline_agent_pager"] = module
        spec.loader.exec_module(module)
        emit_transition_event = module.emit_transition_event
    return emit_transition_event(repo_root, bus_dir=bus_dir, **kwargs)


def normalize_wave_id(raw: str) -> str:
    """Normalize arbitrary routing-record text into a bounded safe wave_id."""
    wave_id = re.sub(r"[^a-z0-9-]", "-", (raw or "").lower())
    wave_id = re.sub(r"-{2,}", "-", wave_id).strip("-")
    if not wave_id:
        wave_id = "wave-unknown"
    if len(wave_id) > MAX_WAVE_ID_LEN:
        wave_id = wave_id[:MAX_WAVE_ID_LEN].strip("-")
    if not WAVE_ID_RE.fullmatch(wave_id):
        prefixed = f"wave-{wave_id}".strip("-")
        if len(prefixed) > MAX_WAVE_ID_LEN:
            prefixed = prefixed[:MAX_WAVE_ID_LEN].strip("-")
        wave_id = prefixed or "wave-unknown"
    if not WAVE_ID_RE.fullmatch(wave_id):
        wave_id = "wave-unknown"
    return wave_id


EXECUTOR_PROCESS_OWNER_ENV = "RCX_EXECUTOR_PROCESS_OWNERS"


class ExecutorProcessIdentity(NamedTuple):
    pid: int
    ppid: int
    started: str
    owned: bool


class ExecutorProcessObservation(NamedTuple):
    complete: bool
    parents: dict[int, int]
    identities: dict[int, ExecutorProcessIdentity]
    error: str


def observe_executor_processes(
    owner: str, *, cwd: Path | None = None,
) -> ExecutorProcessObservation:
    """Observe process identities without conflating query failure and absence.

    The inherited launch marker finds setsid/reparented children that a PPID
    snapshot cannot recover. Both full queries must succeed and parse, include
    init and this observer, and agree on every observed live process. A missing
    row remains unresolved until it is present in both queries or a fresh probe
    proves it exited. No environment or command text leaves this function.
    This is OS snapshot evidence for
    environment-inheriting executors, not containment of arbitrary programs
    that deliberately discard ownership or an atomic process-lifetime census.
    """
    def uncertain(reason: str) -> ExecutorProcessObservation:
        return ExecutorProcessObservation(False, {}, {}, reason)

    if not isinstance(owner, str) or not re.fullmatch(r"[0-9a-f]{32}", owner):
        return uncertain("invalid process owner")
    known_pids: set[int] = set()
    known_identities: dict[int, ExecutorProcessIdentity] = {}
    try:
        # Resample boundedly for processes born between the two queries. Keep
        # every earlier PID so a later partial table cannot erase a live gap.
        for _ in range(5):
            graph = subprocess.run(
                ["ps", "-axo", "pid=,ppid="], cwd=cwd, capture_output=True,
                text=True, check=True, timeout=5,
            )
            identities = subprocess.run(
                ["ps", "axeww", "-o", "pid=,ppid=,lstart=,stat=,command="],
                cwd=cwd, capture_output=True, text=True, check=True, timeout=5,
                env={**os.environ, "LC_ALL": "C"},
            )
            if graph.returncode != 0 or identities.returncode != 0:
                return uncertain("process query failed")
            parents: dict[int, int] = {}
            for line in graph.stdout.splitlines():
                fields = line.split()
                if len(fields) != 2:
                    return uncertain("malformed process graph")
                pid, ppid = map(int, fields)
                if pid <= 0 or ppid < 0 or pid == ppid or pid in parents:
                    return uncertain("ambiguous process graph")
                parents[pid] = ppid
            observed: dict[int, ExecutorProcessIdentity] = {}
            for line in identities.stdout.splitlines():
                fields = line.split(None, 8)
                if len(fields) != 9:
                    return uncertain("malformed process identities")
                pid, ppid = int(fields[0]), int(fields[1])
                started = " ".join(fields[2:7])
                datetime.strptime(started, "%a %b %d %H:%M:%S %Y")
                if pid <= 0 or ppid < 0 or pid == ppid or pid in observed:
                    return uncertain("ambiguous process identities")
                markers = [word.partition("=")[2] for word in fields[8].split()
                           if word.startswith(EXECUTOR_PROCESS_OWNER_ENV + "=")]
                owned = any(owner in marker.split(":") for marker in markers)
                observed[pid] = ExecutorProcessIdentity(pid, ppid, started, owned)
            if not {1, os.getpid()} <= parents.keys() & observed.keys():
                return uncertain("partial or empty process observation")
            for pid in parents.keys() & observed.keys():
                if parents[pid] != observed[pid].ppid:
                    return uncertain("process ancestry changed between observations")
            for pid, identity in observed.items():
                previous = known_identities.get(pid)
                if previous is not None and previous != identity:
                    return uncertain("process identity changed during observation")
            known_identities.update(observed)
            known_pids.update(parents.keys() | observed.keys())
            unresolved = False
            for pid in known_pids - (parents.keys() & observed.keys()):
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    continue
                except (OSError, OverflowError):
                    return uncertain("process observation gap absence is uncertain")
                unresolved = True
            if not unresolved:
                return ExecutorProcessObservation(True, parents, observed, "")
        return uncertain("live process missing from process observation")
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError, UnicodeError):
        return uncertain("process observation unavailable or malformed")


def signal_owned_executor_process(
    identity: ExecutorProcessIdentity, owner: str, signum: int, *, cwd: Path | None = None,
) -> bool:
    """Recheck start identity and inherited owner immediately before signaling.

    PID absence is harmless; query uncertainty or reuse must never select a
    different actor. POSIX PID signaling is not atomic with the observation.
    """
    if (type(identity.pid) is not int or identity.pid <= 0
            or identity.owned is not True or type(identity.started) is not str):
        return False
    observation = observe_executor_processes(owner, cwd=cwd)
    if not observation.complete:
        return False
    current = observation.identities.get(identity.pid)
    if current is None:
        try:
            os.kill(identity.pid, 0)
        except ProcessLookupError:
            return True
        except OSError:
            pass
        return False
    if not current.owned or current.started != identity.started:
        return False
    try:
        os.kill(identity.pid, signum)
        return True
    except ProcessLookupError:
        return True
    except OSError:
        return False


def executor_release_evidence_error(evidence: Any, *, cwd: Path | None = None) -> str | None:
    """Revalidate native release at each late consumer; never signal from a receipt."""
    if (type(evidence) is not dict
            or set(evidence) != {"version", "owner", "root_pid", "members"}
            or type(evidence["version"]) is not int or evidence["version"] != 1
            or type(evidence["root_pid"]) is not int or evidence["root_pid"] <= 0
            or type(evidence["owner"]) is not str
            or not re.fullmatch(r"[0-9a-f]{32}", evidence["owner"])
            or type(evidence["members"]) is not list or not evidence["members"]):
        return "missing or malformed native process release evidence"
    pids: set[int] = set()
    for member in evidence["members"]:
        if (type(member) is not dict or set(member) != {"pid", "started"}
                or type(member["pid"]) is not int or member["pid"] <= 0
                or member["pid"] in pids or type(member["started"]) is not str):
            return "invalid native process identity"
        try:
            datetime.strptime(member["started"], "%a %b %d %H:%M:%S %Y")
        except ValueError:
            return "invalid native process start identity"
        pids.add(member["pid"])
    if evidence["root_pid"] not in pids:
        return "native process release lacks its root identity"
    observation = observe_executor_processes(evidence["owner"], cwd=cwd)
    if not observation.complete:
        return observation.error
    if any(identity.owned for identity in observation.identities.values()):
        return "native executor still has owned processes"
    try:
        os.killpg(evidence["root_pid"], 0)
    except ProcessLookupError:
        pass
    except OSError:
        return "native process group absence is uncertain"
    else:
        return "native process group is still present"
    for pid in pids:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        except OSError:
            return "native process absence is uncertain"
        return "native process identity remains or its PID was reused"
    return None


def terminate_owned_executor(
    proc: subprocess.Popen, owner: str, *, cwd: Path | None = None,
) -> dict[str, Any] | None:
    """Release a live, completely observed owned tree, or preserve a HOLD.

    An exited root or a reparented marked descendant makes ancestry uncertain.
    In that case only the still-owned Popen child is stopped: best-effort tree
    cleanup must not signal unverified PIDs or manufacture continuation proof.
    """
    observation = observe_executor_processes(owner, cwd=cwd)
    root = observation.identities.get(proc.pid)
    reliable = (observation.complete and proc.poll() is None and root is not None
                and root.owned and root.ppid == os.getpid())
    members: dict[int, ExecutorProcessIdentity] = {}
    if reliable:
        reachable = {proc.pid}
        while True:
            children = {pid for pid, ppid in observation.parents.items() if ppid in reachable}
            if children <= reachable:
                break
            reachable.update(children)
        members = {pid: identity for pid, identity in observation.identities.items() if identity.owned}
        reliable = reachable == members.keys()
    if reliable:
        for pid in sorted(members.keys() - {proc.pid}, reverse=True):
            if not signal_owned_executor_process(members[pid], owner, signal.SIGKILL, cwd=cwd):
                reliable = False
                break
        if reliable:
            reliable = signal_owned_executor_process(root, owner, signal.SIGKILL, cwd=cwd)
    # Popen retains direct child ownership even if ps is unavailable. Its kill
    # method polls/reaps before signaling, unlike a bare historical PID sweep.
    try:
        proc.kill()
        proc.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if not reliable:
        return None
    evidence = {
        "version": 1, "owner": owner, "root_pid": proc.pid,
        "members": [{"pid": pid, "started": member.started} for pid, member in sorted(members.items())],
    }
    return evidence if executor_release_evidence_error(evidence, cwd=cwd) is None else None


def process_descendants(root_pid: int, *, cwd: Path | None = None) -> set[int]:
    """Return descendant PIDs for a process tree.

    Collects the PPID tree from ALL processes (``ps -axo pid=,ppid=``)
    and walks from *root_pid* down.  The root does NOT need to be alive —
    descendants that were spawned before the root died still show the
    original PPID in the snapshot (reparenting to PID 1 happens
    asynchronously and may not have occurred yet). This legacy best-effort
    cleanup interface deliberately retains its empty-set failure behavior.
    It must never be used as process-release or lifetime ownership evidence.
    """
    if root_pid <= 0:
        return set()

    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,ppid="],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (PermissionError, OSError, subprocess.CalledProcessError):
        return set()

    children_by_parent: dict[int, set[int]] = {}
    for raw in proc.stdout.splitlines():
        parts = raw.split()
        if len(parts) != 2:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        children_by_parent.setdefault(ppid, set()).add(pid)

    descendants: set[int] = set()
    stack = list(children_by_parent.get(root_pid, set()))
    while stack:
        pid = stack.pop()
        if pid in descendants:
            continue
        descendants.add(pid)
        stack.extend(children_by_parent.get(pid, set()))
    return descendants


def artifact_size_mtime_ns(path: Path) -> tuple[int, int | None]:
    """Return artifact size and nanosecond mtime, or a missing sentinel."""
    if not path.exists():
        return 0, None
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns


def terminate_process_tree(
    root_pid: int,
    *,
    cwd: Path | None = None,
    settle_seconds: float = 0.2,
) -> None:
    """Best-effort terminate a process tree rooted at root_pid."""
    pids = sorted(process_descendants(root_pid, cwd=cwd), reverse=True)
    for pid in pids + [root_pid]:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue
    time.sleep(settle_seconds)
    for pid in pids + [root_pid]:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            continue


def load_routing_record(
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load and validate the post-merge routing record.

    This is the canonical implementation. All executors should import
    this instead of maintaining their own copy.

    Returns the parsed JSON record.
    Raises ExecutorCommonError if the file is missing, invalid JSON,
    or missing required keys.
    """
    record_path = routing_record_path(repo_root, bus_dir)
    if not record_path.exists():
        raise ExecutorCommonError(f"Routing record not found: {record_path}")

    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExecutorCommonError(f"Routing record is not valid JSON: {exc}") from exc

    required = {"decision", "summary"}
    missing = required - set(record.keys())
    if missing:
        raise ExecutorCommonError(f"Routing record missing keys: {sorted(missing)}")

    return record


def _load_meta_bridge_symbol(symbol_name: str) -> Any:
    """Lazy-load a symbol from meta_bridge_supervisor without a module-scope import.

    meta_bridge_supervisor.py imports executor_common at module scope
    (meta_bridge_supervisor.py:38), so the reverse direction must remain
    function-local to avoid a circular import at module load time. Mirrors
    the pattern used by executor_dispatch.py:73-83.
    """
    try:
        import meta_bridge_supervisor as _meta_mod  # type: ignore[import-not-found]
    except ImportError:
        import importlib.util as _ilu
        import sys as _sys
        _repo_root = Path(__file__).resolve().parents[3]
        _meta_path = _repo_root / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
        _spec = _ilu.spec_from_file_location("meta_bridge_supervisor", str(_meta_path))
        assert _spec is not None and _spec.loader is not None
        _meta_mod = _ilu.module_from_spec(_spec)
        _sys.modules["meta_bridge_supervisor"] = _meta_mod
        _spec.loader.exec_module(_meta_mod)
    return getattr(_meta_mod, symbol_name)


_CONTROL_PLANE_PREFIX = "reports/control_plane/"
_PACKET_STATUS_SCAN_LIMIT = 40
_EXPLICIT_COMPLETE_PACKET_STATUS_RE = re.compile(
    r"\b(?:COMPLETED|LANDED|CLOSED)\b",
    re.IGNORECASE,
)
_IMPLEMENTED_PACKET_STATUS_RE = re.compile(
    r"\bIMPLEMENTED\b|\bIMPLEMENTATION[-_\s]+COMPLETE\b",
    re.IGNORECASE,
)
_PENDING_PACKET_STATUS_RE = re.compile(
    r"\b(?:PENDING|PENDING_COMMIT|PENDING-COMMIT|PRE_COMMIT|PRE-COMMIT)\b",
    re.IGNORECASE,
)


def _validate_tracked_packet_for_builder(
    tracked_packet: str, repo_root: Path
) -> str | None:
    """Validate tracked_packet for the routing-record builder.

    Returns an error message on rejection, or None on success.
    Four-leg validation (see plan Work Item 1):
      (i)   not absolute
      (ii)  no ``..`` components
      (iii) starts with reports/control_plane/ AND resolved path is inside
            repo_root/reports/control_plane/
      (iv)  file exists on disk

    Deliberately weaker than meta_bridge_supervisor._check_control_plane_path:
    NO git ls-files tracked-file proof, so newly-drafted untracked control-plane
    packets (common on fresh Phase A launches) are admitted.
    """
    if not isinstance(tracked_packet, str) or not tracked_packet.strip():
        return "tracked_packet must be a non-empty string"
    if os.path.isabs(tracked_packet) or ".." in tracked_packet.split("/"):
        return (
            f"tracked_packet must not be absolute or contain '..': {tracked_packet}"
        )
    if not tracked_packet.startswith(_CONTROL_PLANE_PREFIX):
        return (
            f"tracked_packet must start with {_CONTROL_PLANE_PREFIX}: {tracked_packet}"
        )
    full_path = (repo_root / tracked_packet).resolve()
    control_plane_dir = (repo_root / _CONTROL_PLANE_PREFIX).resolve()
    try:
        full_path.relative_to(control_plane_dir)
    except ValueError:
        return (
            f"tracked_packet resolves outside {_CONTROL_PLANE_PREFIX}: "
            f"{tracked_packet} -> {full_path}"
        )
    if not full_path.exists():
        return f"tracked_packet does not exist on disk: {tracked_packet}"
    if not full_path.is_file():
        return f"tracked_packet must be a file, not a directory: {tracked_packet}"
    return None


def packet_status_is_completed(status: str | None) -> bool:
    clean = str(status or "").strip()
    if not clean:
        return False
    if "FINDINGS ROUTED" in clean.upper():
        return True
    if _EXPLICIT_COMPLETE_PACKET_STATUS_RE.search(clean):
        return True
    if _PENDING_PACKET_STATUS_RE.search(clean):
        return False
    return bool(_IMPLEMENTED_PACKET_STATUS_RE.search(clean))


def read_control_plane_packet_status(repo_root: Path, tracked_packet: str) -> str | None:
    packet_err = _validate_tracked_packet_for_builder(tracked_packet, repo_root)
    if packet_err:
        return None
    packet_path = (repo_root / tracked_packet).resolve()
    try:
        lines = packet_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines[:_PACKET_STATUS_SCAN_LIMIT]:
        clean = line.strip()
        if clean.lower().startswith("status:"):
            return clean.partition(":")[2].strip() or None
    return None


def read_control_plane_packet_wave_id(repo_root: Path, tracked_packet: str) -> str | None:
    """Return a packet's explicit Wave ID metadata, normalized when present."""
    packet_err = _validate_tracked_packet_for_builder(tracked_packet, repo_root)
    if packet_err:
        return None
    packet_path = (repo_root / tracked_packet).resolve()
    try:
        lines = packet_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines[:_PACKET_STATUS_SCAN_LIMIT]:
        clean = line.strip()
        lower = clean.lower()
        if lower.startswith("wave id:") or lower.startswith("wave_id:"):
            value = clean.partition(":")[2].strip().strip("`")
            normalized = normalize_wave_id(value) if value else ""
            return normalized if normalized != "wave-unknown" else None
    return None


def _tasks_queue_backtick_value(line: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*`([^`]+)`", line)
    return match.group(1).strip() if match else ""


def _line_is_next_codex_post_redteam_queue_entry(line: str) -> bool:
    return (
        "FOUNDER-ORDERED-REDTEAM-" in line
        or "NEXT-CODEX-POST-REDTEAM" in line
    )


def read_founder_ordered_task_state(
    repo_root: Path,
    *,
    wave_id: str = "",
    tracked_packet: str = "",
) -> str | None:
    """Return the TASKS.md state for a founder-ordered queue entry."""
    wanted_wave = normalize_wave_id(wave_id) if wave_id else ""
    wanted_packet = str(tracked_packet or "").strip()
    if not wanted_wave and not wanted_packet:
        return None

    tasks_path = repo_root / "TASKS.md"
    try:
        lines = tasks_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    state_re = re.compile(
        r"^\s*\d+\.\s+\*\*\[(?P<label>[^\]]+)\]\s*(?P<state>.*?)\*\*"
    )
    for line in lines:
        if not _line_is_next_codex_post_redteam_queue_entry(line):
            continue
        match = state_re.match(line)
        if not match:
            continue
        entry_wave = _tasks_queue_backtick_value(line, "Wave ID")
        entry_packet = _tasks_queue_backtick_value(line, "Packet")
        if wanted_wave and entry_wave and normalize_wave_id(entry_wave) == wanted_wave:
            return match.group("state").strip()
        if wanted_packet and entry_packet == wanted_packet:
            return match.group("state").strip()
    return None


def _completed_tracked_packet_error(tracked_packet: str, repo_root: Path) -> str | None:
    status = read_control_plane_packet_status(repo_root, tracked_packet)
    if not packet_status_is_completed(status):
        return None
    return (
        "tracked_packet is already complete and must not be routed again: "
        f"{tracked_packet} has Status: {status}"
    )


def _tracked_packet_wave_conflict_error(
    wave_name: str,
    tracked_packet: str,
    repo_root: Path,
) -> str | None:
    clean_wave = str(wave_name or "").strip()
    expected_wave = normalize_wave_id(clean_wave) if clean_wave else ""
    packet_wave = read_control_plane_packet_wave_id(repo_root, tracked_packet)
    if expected_wave == "wave-unknown":
        expected_wave = ""
    if not expected_wave or not packet_wave or expected_wave == packet_wave:
        return None
    return (
        "tracked_packet Wave ID does not match routed wave_name: "
        f"{tracked_packet} declares Wave ID {packet_wave}, "
        f"but routing requested {expected_wave}"
    )


def build_post_merge_routing_record(
    *,
    wave_name: str,
    task_id: str,
    tracked_packet: str,
    request_for_claude: str,
    summary: str,
    request_for_agent: str = "",
    decision: str = "ROUTE_PHASE_A",
    merged_pr: int | None = None,
    merge_sha: str | None = None,
    repo_root: Path | None = None,
    allow_completed_tracked_packet: bool = False,
    founder_override: str = "",
    pager_route: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Build a validated post-merge routing record from kwargs.

    Canonical builder for the active bus post-merge routing record (default
    .agent_bus/meta/post_merge_routing.json). Mirrors
    commit_executor.build_commit_handoff's shape: returns (record, errors);
    callers MUST check that ``errors`` is empty before trusting the record.

    Auto-populated fields (require repo_root):
      - state_sha: via lazy-imported compute_repo_state (cycle-break)
      - blocker_report_paths: sorted glob of reports/deferred/blocking/*.md
      - head_sha: git rev-parse HEAD
      - merge_sha: head_sha fallback when merge_sha kwarg omitted
      - timestamp_utc: ISO 8601 UTC now
      - next_candidates: single-entry list built from wave_name + tracked_packet

    Validation:
      - required non-empty strings: wave_name, task_id, tracked_packet,
        request_for_agent (or deprecated request_for_claude compatibility input),
        summary
      - decision in POST_MERGE_AUTHORIZED_DECISIONS (lazy-imported)
      - tracked_packet passes _validate_tracked_packet_for_builder
      - explicit tracked_packet Wave ID, when present, matches wave_name
      - completed tracked packets are rejected unless the caller explicitly
        marks this as a post-push/same-wave recovery reroute

    Optional fields:
      - founder_override: when non-empty, the record carries a ``founder_override``
        key (the bare override id). This makes a wave's declared FOUNDER_OVERRIDE
        durable in the routing record from launch time, so the commit-executor
        growth-cap auto-bump's _extract_founder_override_from_routing_record reads
        a non-empty token instead of stranding 'no_founder_override'. Default
        empty preserves the prior record shape exactly (no key emitted).
      - pager_route: when non-empty, the record carries the launch-owned pager
        route so commit/retry paths can use the wave route without ambient env.
    """
    errors: list[str] = []

    if not isinstance(wave_name, str) or not wave_name.strip():
        errors.append("wave_name is required (non-empty string)")
    if not isinstance(task_id, str) or not task_id.strip():
        errors.append("task_id is required (non-empty string)")
    request_text = ""
    if isinstance(request_for_agent, str) and request_for_agent.strip():
        request_text = request_for_agent.strip()
    elif isinstance(request_for_claude, str) and request_for_claude.strip():
        request_text = request_for_claude.strip()
    if not request_text:
        errors.append(
            "request_for_agent is required (or deprecated request_for_claude compatibility input)"
        )
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary is required (non-empty string)")

    try:
        authorized_decisions = _load_meta_bridge_symbol(
            "POST_MERGE_AUTHORIZED_DECISIONS"
        )
    except Exception as exc:
        errors.append(f"Could not load POST_MERGE_AUTHORIZED_DECISIONS: {exc}")
        return {}, errors
    if decision not in authorized_decisions:
        errors.append(
            f"decision must be one of {sorted(authorized_decisions)}; got: {decision!r}"
        )
    normalized_pager_route = ""
    if pager_route is not None:
        if not isinstance(pager_route, str):
            errors.append("pager_route must be a string when provided")
        else:
            normalized_pager_route = pager_route.strip()
            if (
                normalized_pager_route
                and normalized_pager_route not in ALLOWED_PIPELINE_AGENT_PAGER_ROUTES
            ):
                errors.append(
                    "pager_route must be one of "
                    f"{sorted(ALLOWED_PIPELINE_AGENT_PAGER_ROUTES)}; got: {pager_route!r}"
                )

    effective_repo_root = (
        repo_root if repo_root is not None else Path(__file__).resolve().parents[3]
    )
    if not isinstance(effective_repo_root, Path):
        effective_repo_root = Path(effective_repo_root)

    packet_err = _validate_tracked_packet_for_builder(
        tracked_packet if isinstance(tracked_packet, str) else "",
        effective_repo_root,
    )
    if packet_err:
        errors.append(packet_err)
    else:
        completed_packet_err = _completed_tracked_packet_error(
            tracked_packet if isinstance(tracked_packet, str) else "",
            effective_repo_root,
        )
        if completed_packet_err and not allow_completed_tracked_packet:
            errors.append(completed_packet_err)
        else:
            packet_wave_err = _tracked_packet_wave_conflict_error(
                wave_name if isinstance(wave_name, str) else "",
                tracked_packet if isinstance(tracked_packet, str) else "",
                effective_repo_root,
            )
            if packet_wave_err:
                errors.append(packet_wave_err)

    if errors:
        return {}, errors

    try:
        compute_repo_state = _load_meta_bridge_symbol("compute_repo_state")
    except Exception as exc:
        return {}, [f"Could not load compute_repo_state: {exc}"]

    try:
        repo_state = compute_repo_state(effective_repo_root)
    except Exception as exc:
        return {}, [f"compute_repo_state failed: {exc}"]

    head_sha = repo_state.head_sha
    effective_merge_sha = merge_sha if merge_sha else head_sha

    blocker_dir = effective_repo_root / "reports" / "deferred" / "blocking"
    blocker_report_paths: list[str] = []
    if blocker_dir.is_dir():
        for p in sorted(blocker_dir.glob("*.md")):
            if p.name == "README.md":
                continue
            blocker_report_paths.append(
                p.relative_to(effective_repo_root).as_posix()
            )

    timestamp_utc = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )

    record: dict[str, Any] = {
        "decision": decision,
        "summary": summary,
        "request_for_agent": request_text,
        # Deprecated compatibility output for old parsers. Do not use this as
        # operator-facing truth; request_for_agent is the neutral request field.
        "request_for_claude": request_text,
        "wave_name": wave_name,
        "task_id": task_id,
        "merged_pr": merged_pr,
        "merge_sha": effective_merge_sha,
        "head_sha": head_sha,
        "state_sha": repo_state.state_sha,
        "timestamp_utc": timestamp_utc,
        "blocker_report_paths": blocker_report_paths,
        "next_candidates": [
            {
                "candidate": wave_name,
                "bounded": True,
                "tracked_packet": tracked_packet,
            }
        ],
    }
    if allow_completed_tracked_packet:
        record["allow_completed_tracked_packet"] = True
    if isinstance(founder_override, str) and founder_override.strip():
        record["founder_override"] = founder_override.strip()
    if normalized_pager_route:
        record["pager_route"] = normalized_pager_route
    return record, []


def build_and_write_routing_record(
    *,
    wave_name: str,
    task_id: str,
    tracked_packet: str,
    request_for_claude: str,
    summary: str,
    request_for_agent: str = "",
    decision: str = "ROUTE_PHASE_A",
    merged_pr: int | None = None,
    merge_sha: str | None = None,
    repo_root: Path | None = None,
    output_path: Path | None = None,
    bus_dir: str | Path | None = None,
    allow_completed_tracked_packet: bool = False,
    founder_override: str = "",
    pager_route: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Build + persist a routing record. Returns (record, errors).

    Writes to repo_root/.agent_bus/meta/post_merge_routing.json unless
    output_path is provided. On build errors, returns ({}, errors) WITHOUT
    writing. On success, writes pretty-printed JSON and returns (record, []).
    """
    effective_repo_root = (
        repo_root if repo_root is not None else Path(__file__).resolve().parents[3]
    )
    if not isinstance(effective_repo_root, Path):
        effective_repo_root = Path(effective_repo_root)

    record, errors = build_post_merge_routing_record(
        wave_name=wave_name,
        task_id=task_id,
        tracked_packet=tracked_packet,
        request_for_claude=request_for_claude,
        request_for_agent=request_for_agent,
        summary=summary,
        decision=decision,
        merged_pr=merged_pr,
        merge_sha=merge_sha,
        repo_root=effective_repo_root,
        allow_completed_tracked_packet=allow_completed_tracked_packet,
        founder_override=founder_override,
        pager_route=pager_route,
    )
    if errors:
        return {}, errors

    target_path = (
        output_path
        if output_path is not None
        else routing_record_path(effective_repo_root, bus_dir)
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record, []


def run_bridge_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run a bridge subprocess with proper process-group cleanup on timeout.

    Uses Popen with start_new_session=True so that the bridge process and
    its direct children form a new process group.  On timeout, os.killpg()
    kills the entire group (including adapter grandchildren that haven't
    created their own sessions).  Adapter processes that DID create their
    own sessions (via start_new_session=True in bridge_adapters.py) are
    handled by their own watchdog timers — but SIGTERM is sent to the
    bridge first to give it a chance to clean up before SIGKILL.

    Returns a CompletedProcess with stdout, stderr, and returncode.
    Raises ExecutorCommonError on timeout (after cleanup).
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=proc.returncode,
            stdout=stdout,
            stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        # Graceful: SIGTERM the process group so bridge_supervisor can
        # clean up its adapter children before we force-kill.
        pgid = os.getpgid(proc.pid)
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        # Brief grace period for cleanup, then SIGKILL
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                try:
                    proc.kill()
                except OSError:
                    pass
            proc.wait()
        raise ExecutorCommonError(
            f"Bridge subprocess timed out after {timeout}s"
        )
