#!/usr/bin/env python3
"""Shared utilities for executor scripts.

Canonical implementations of functions previously duplicated across
executor_dispatch.py, phase_a_executor.py, phase_b_executor.py, and
dialectic_executor.py.
"""

from __future__ import annotations

import copy
import json
import os
import re
import signal
import shutil
import stat
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
            "display_name": "Claude Opus 4.8 max",
            "model": "claude-opus-4-8",
            "effort": "max",
        },
        "codex": {
            "display_name": "Codex 5.5 xhigh",
            "model": "gpt-5.5",
            "reasoning_effort": "xhigh",
        },
    },
    "backends": {
        "post_merge_supervisor": "codex",
        "dialectic_executor": "codex",
        "phase_a_executor": "claude",
        "phase_b_executor": "claude",
        "bot_remediation": "claude",
        "commit_executor": None,
    },
    "bridge_reviewers": {
        "phase_a": "codex",
        "phase_b": "codex",
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
        "route": "notify-only",
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
    """
    if not isinstance(overrides, dict):
        raise ExecutorCommonError("executor config overrides must be a JSON object")
    merged = _deep_merge(DEFAULT_EXECUTOR_CONFIG, overrides)
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
        raw_overrides: dict[str, Any] = {}
        config = copy.deepcopy(DEFAULT_EXECUTOR_CONFIG)
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


def process_descendants(root_pid: int, *, cwd: Path | None = None) -> set[int]:
    """Return descendant PIDs for a process tree.

    Collects the PPID tree from ALL processes (``ps -axo pid=,ppid=``)
    and walks from *root_pid* down.  The root does NOT need to be alive —
    descendants that were spawned before the root died still show the
    original PPID in the snapshot (reparenting to PID 1 happens
    asynchronously and may not have occurred yet).  This is critical for
    the timeout-kill path: the dispatcher kills the Phase A process group
    first (``os.killpg``), then calls this function to sweep up children
    in separate sessions (``start_new_session=True`` adapters).
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
