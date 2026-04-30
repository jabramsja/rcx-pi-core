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
import subprocess
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
IMPLEMENTER_BACKEND_KEYS = frozenset(
    {
        "phase_a_executor",
        "phase_b_executor",
        "bot_remediation",
    }
)
REVIEWER_BRIDGE_KEYS = frozenset({"phase_a", "phase_b"})
DEFAULT_AGENT_DISPLAY_NAMES = {
    "claude": "Claude Opus 4.7 max",
    "codex": "Codex 5.5 xhigh",
}

DEFAULT_EXECUTOR_CONFIG: dict[str, Any] = {
    "role_agents": {
        "implementer": "codex",
        "reviewer": "codex",
    },
    "bridge_agent_defaults": {
        "claude": {
            "display_name": "Claude Opus 4.7 max",
            "model": "claude-opus-4-7",
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
        "phase_a_executor": "codex",
        "phase_b_executor": "codex",
        "bot_remediation": "codex",
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
        "enabled": False,
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
        "pre_push_fast": 900,
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
    """Apply config overrides on top of the canonical executor defaults."""
    if not isinstance(overrides, dict):
        raise ExecutorCommonError("executor config overrides must be a JSON object")
    return _deep_merge(DEFAULT_EXECUTOR_CONFIG, overrides)


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


def _materialize_role_agents(
    config: dict[str, Any],
    *,
    raw_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    implementer_agent = resolve_role_agent(
        config,
        "implementer",
        raw_overrides=raw_overrides,
    )
    reviewer_agent = resolve_role_agent(
        config,
        "reviewer",
        raw_overrides=raw_overrides,
    )

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
        agent = resolve_role_agent(config, role)
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
    return _materialize_role_agents(config, raw_overrides=raw_overrides)


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

        pager_path = (
            Path(__file__).resolve().parent.parent / "observability" / "pipeline_agent_pager.py"
        )
        spec = _ilu.spec_from_file_location("pipeline_agent_pager", str(pager_path))
        module = _ilu.module_from_spec(spec)
        assert spec.loader is not None
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


def build_post_merge_routing_record(
    *,
    wave_name: str,
    task_id: str,
    tracked_packet: str,
    request_for_claude: str,
    summary: str,
    decision: str = "ROUTE_PHASE_A",
    merged_pr: int | None = None,
    merge_sha: str | None = None,
    repo_root: Path | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build a validated post-merge routing record from kwargs.

    Canonical builder for .agent_bus/meta/post_merge_routing.json. Mirrors
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
        request_for_claude, summary
      - decision in POST_MERGE_AUTHORIZED_DECISIONS (lazy-imported)
      - tracked_packet passes _validate_tracked_packet_for_builder
    """
    errors: list[str] = []

    if not isinstance(wave_name, str) or not wave_name.strip():
        errors.append("wave_name is required (non-empty string)")
    if not isinstance(task_id, str) or not task_id.strip():
        errors.append("task_id is required (non-empty string)")
    if not isinstance(request_for_claude, str) or not request_for_claude.strip():
        errors.append("request_for_claude is required (non-empty string)")
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
        "request_for_claude": request_for_claude,
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
    return record, []


def build_and_write_routing_record(
    *,
    wave_name: str,
    task_id: str,
    tracked_packet: str,
    request_for_claude: str,
    summary: str,
    decision: str = "ROUTE_PHASE_A",
    merged_pr: int | None = None,
    merge_sha: str | None = None,
    repo_root: Path | None = None,
    output_path: Path | None = None,
    bus_dir: str | Path | None = None,
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
        summary=summary,
        decision=decision,
        merged_pr=merged_pr,
        merge_sha=merge_sha,
        repo_root=effective_repo_root,
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
