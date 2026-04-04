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
import subprocess
import time
from pathlib import Path
from typing import Any

ROUTING_RECORD_PATH = Path(".agent_bus/meta/post_merge_routing.json")
MAX_WAVE_ID_LEN = 80
WAVE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
REVIEW_MODE_ENV_VARS = ("RCX_AGENT_REVIEW_MODE", "RCX_REVIEW_MODE")

DEFAULT_EXECUTOR_CONFIG: dict[str, Any] = {
    "backends": {
        "post_merge_supervisor": "codex",
        "dialectic_executor": "codex",
        "phase_a_executor": "codex",
        "phase_b_executor": "claude",
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
    "review_depths": {
        "phase_a": "quick",
        "phase_b": "quick",
    },
    "timeouts": {
        "dialectic_executor": 600,
        "phase_a_executor": 3600,
        "phase_b_executor": 3600,
        "phase_b_implementer_stale": 300,
        "commit_executor": 3600,
        "agent_review": 900,
    },
    "bridge_loop_limits": {
        "phase_a": 15,
        "phase_b": 10,
        "dialectic": 3,
    },
}

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


def load_executor_config(repo_root: Path) -> dict[str, Any]:
    """Load executor config, preserving default nested keys when partially set."""
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    if not config_path.exists():
        return copy.deepcopy(DEFAULT_EXECUTOR_CONFIG)
    loaded = json.loads(config_path.read_text(encoding="utf-8"))
    return merge_executor_config_overrides(loaded)


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
    """Return descendant PIDs for a live root process."""
    if root_pid <= 0:
        return set()
    try:
        os.kill(root_pid, 0)
    except (ProcessLookupError, PermissionError):
        return set()

    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,ppid="],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
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


def load_routing_record(repo_root: Path) -> dict[str, Any]:
    """Load and validate the post-merge routing record.

    This is the canonical implementation. All executors should import
    this instead of maintaining their own copy.

    Returns the parsed JSON record.
    Raises ExecutorCommonError if the file is missing, invalid JSON,
    or missing required keys.
    """
    record_path = repo_root / ROUTING_RECORD_PATH
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
