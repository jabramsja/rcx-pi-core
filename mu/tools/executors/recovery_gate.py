#!/usr/bin/env python3
"""Pipeline recovery gate: failure classification and Tier 1 auto-fix.

Design doc: mu/docs/agents/PipelineRecovery.v0.md
Import constraints: only stdlib + executor_common.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import normalize_wave_id
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    normalize_wave_id = _mod.normalize_wave_id

# ---------------------------------------------------------------------------
# Failure classification taxonomy
# ---------------------------------------------------------------------------

class FailureClass(Enum):
    """Pipeline failure categories by recovery tier."""
    # Tier 1 -- deterministic auto-fix (zero tokens)
    STALE_BRIDGE_LOCK = "stale_bridge_lock"
    STALE_GIT_INDEX_LOCK = "stale_git_index_lock"
    STALE_EXECUTOR_STATE = "stale_executor_state"
    STALE_CONTINUATION = "stale_continuation"
    MIXED_STAGING = "mixed_staging"
    # Tier 2 -- auto-retry with adjustment (zero tokens)
    PROCESS_TIMEOUT = "process_timeout"
    TRANSIENT_KILL = "transient_kill"
    AGGREGATION_HANG = "aggregation_hang"
    IMPLEMENTER_STALE = "implementer_stale"
    # Tier 3 -- LLM diagnosis (small focused prompt)
    GIT_STAGING_CONFLICT = "git_staging_conflict"
    TEST_FAILURE = "test_failure"
    AGENT_REVIEW_CRASH = "agent_review_crash"
    UNKNOWN_ERROR = "unknown_error"
    # Tier 4 -- escalate (never recover)
    TERMINAL_POLICY = "terminal_policy"
    UNCLASSIFIED = "unclassified"

_TIER_MAP: dict[FailureClass, int] = {
    FailureClass.STALE_BRIDGE_LOCK: 1, FailureClass.STALE_GIT_INDEX_LOCK: 2,
    FailureClass.STALE_EXECUTOR_STATE: 1, FailureClass.STALE_CONTINUATION: 1,
    FailureClass.MIXED_STAGING: 1,
    FailureClass.PROCESS_TIMEOUT: 2, FailureClass.TRANSIENT_KILL: 2,
    FailureClass.AGGREGATION_HANG: 2, FailureClass.IMPLEMENTER_STALE: 2,
    FailureClass.GIT_STAGING_CONFLICT: 3, FailureClass.TEST_FAILURE: 3,
    FailureClass.AGENT_REVIEW_CRASH: 3, FailureClass.UNKNOWN_ERROR: 3,
    FailureClass.TERMINAL_POLICY: 4, FailureClass.UNCLASSIFIED: 4,
}

_TERMINAL_STATUSES = frozenset({
    "question_for_founder", "max_rounds_reached",
    "supervisor_rejected", "needs_phase_b",
})
_TRANSIENT_KILL_CODES = frozenset({-9, -15, 137})


def tier_for(fc: FailureClass) -> int:
    """Return the recovery tier (1-4) for a failure class."""
    return _TIER_MAP[fc]


# ---------------------------------------------------------------------------
# Classifier -- pure dict inspection, no external calls
# ---------------------------------------------------------------------------

def classify_failure(result: dict[str, Any]) -> FailureClass:
    """Classify an executor failure result into a FailureClass."""
    status = result.get("status", "")
    stderr = result.get("stderr", "")
    exit_code = result.get("exit_code")
    step = result.get("step", "")
    stdout = result.get("stdout", "")

    # Tier 4: terminal policy outcomes (check first, never recover)
    if status in _TERMINAL_STATUSES:
        return FailureClass.TERMINAL_POLICY
    if stdout:
        try:
            data = json.loads(stdout)
            if isinstance(data, dict) and data.get("status") in _TERMINAL_STATUSES:
                return FailureClass.TERMINAL_POLICY
        except (json.JSONDecodeError, ValueError):
            pass

    # Tier 1: deterministic lock/state issues
    if "bridge.lock" in stderr or "bridge.lock" in stdout:
        return FailureClass.STALE_BRIDGE_LOCK
    if "index.lock" in stderr or "index.lock" in stdout:
        return FailureClass.STALE_GIT_INDEX_LOCK
    if "phase_b_state.json" in stderr or "stale_state" in status:
        return FailureClass.STALE_EXECUTOR_STATE
    if "continuation" in stderr.lower() and "stale" in stderr.lower():
        return FailureClass.STALE_CONTINUATION
    if _looks_like_mixed_staging(stderr, stdout, step):
        return FailureClass.MIXED_STAGING

    # Tier 2: transient / timeout issues
    if status == "timeout":
        return FailureClass.PROCESS_TIMEOUT
    if exit_code is not None and exit_code in _TRANSIENT_KILL_CODES:
        return FailureClass.TRANSIENT_KILL
    if "aggregation" in stderr.lower():
        return FailureClass.AGGREGATION_HANG
    if result.get("implementer_status") == "stale":
        return FailureClass.IMPLEMENTER_STALE

    # Tier 3: needs diagnosis
    if step in ("stage_files", "git_commit") and "git add" in stderr.lower():
        return FailureClass.GIT_STAGING_CONFLICT
    if "test" in stderr.lower() and ("fail" in stderr.lower() or "error" in stderr.lower()):
        return FailureClass.TEST_FAILURE
    if "agent" in step.lower() and status in ("error", "failed"):
        return FailureClass.AGENT_REVIEW_CRASH
    if status in ("error", "failed"):
        return FailureClass.UNKNOWN_ERROR

    return FailureClass.UNCLASSIFIED


def _looks_like_mixed_staging(stderr: str, stdout: str, step: str) -> bool:
    """Detect mixed staged/unstaged state from error signals."""
    combined_lower = f"{stderr} {stdout}".lower()
    if "mixed" in combined_lower and "staging" in combined_lower:
        return True
    if step in ("stage_files", "git_commit"):
        for line in f"{stderr}\n{stdout}".splitlines():
            if len(line) >= 3 and line[2] == " ":
                if line[0] in "MADRCU" and line[1] in "MADRCU":
                    return True
    return False


# ---------------------------------------------------------------------------
# Tier 1 auto-fix functions
# ---------------------------------------------------------------------------

def _fix_result(fixed: bool, action: str, detail: str) -> dict[str, Any]:
    return {"fixed": fixed, "action": action, "detail": detail}


def fix_stale_bridge_lock(repo_root: Path) -> dict[str, Any]:
    """Remove .agent_bus/bridge.lock if owning PID is dead."""
    lock_path = repo_root / ".agent_bus" / "bridge.lock"
    if not lock_path.exists():
        return _fix_result(False, "noop", "bridge.lock not found")
    try:
        pid = int(lock_path.read_text(encoding="utf-8").strip().splitlines()[0].strip())
    except (ValueError, IndexError, OSError):
        lock_path.write_text("", encoding="utf-8")
        return _fix_result(True, "truncate_corrupt_lock", "bridge.lock unreadable, truncated")
    try:
        os.kill(pid, 0)
        return _fix_result(False, "noop", f"bridge.lock held by live PID {pid}")
    except ProcessLookupError:
        lock_path.write_text("", encoding="utf-8")
        return _fix_result(True, "truncate_dead_pid_lock",
                           f"bridge.lock held by dead PID {pid}, truncated")
    except PermissionError:
        return _fix_result(False, "noop",
                           f"bridge.lock held by PID {pid}, permission denied on signal")


def fix_stale_git_index_lock(repo_root: Path) -> dict[str, Any]:
    """Placeholder for future Tier 2/3 index.lock recovery.

    Demoted from Tier 1 auto-fix because no sound ownership check exists to
    prove the lock is stale vs held by a live git process. See Codex review
    2026-03-31: pgrep-based PID detection is unreliable (git processes
    launched from repo cwd don't include the repo name in argv).

    When Tier 2 retry or Tier 3 LLM diagnosis is implemented, this function
    can be upgraded with a proper ownership check (e.g., lsof on the lock
    file or /proc/$pid/cwd inspection).
    """
    lock_path = repo_root / ".git" / "index.lock"
    if not lock_path.exists():
        return _fix_result(False, "noop", "index.lock not found")
    return _fix_result(False, "demoted_to_tier2",
                       "index.lock exists but Tier 1 auto-fix disabled — "
                       "no sound ownership check to prove lock is stale")


def fix_stale_executor_state(repo_root: Path, wave_id: str = "") -> dict[str, Any]:
    """Remove phase_b_state.json if wave_id mismatches current routing."""
    state_path = repo_root / ".agent_bus" / "executors" / "phase_b_state.json"
    if not state_path.exists():
        return _fix_result(False, "noop", "phase_b_state.json not found")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        state_path.unlink(missing_ok=True)
        return _fix_result(True, "unlink_corrupt_state", "phase_b_state.json corrupt, removed")
    state_wave = state.get("wave_id", "")
    if wave_id and state_wave == wave_id:
        return _fix_result(False, "noop",
                           f"phase_b_state.json wave_id matches current ({wave_id})")
    if not wave_id:
        # No wave_id to compare — can't determine staleness, don't delete
        return _fix_result(False, "noop",
                           f"no wave_id provided — cannot determine if "
                           f"phase_b_state.json (wave: {state_wave}) is stale")
    state_path.unlink(missing_ok=True)
    return _fix_result(True, "unlink_stale_state",
                       f"removed stale phase_b_state.json (was: {state_wave}, current: {wave_id})")


def fix_mixed_staging(repo_root: Path) -> dict[str, Any]:
    """Reset HEAD for files with mixed staged/unstaged state."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root,
            capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "status_failed", f"git status failed: {exc}")
    if proc.returncode != 0:
        return _fix_result(False, "status_failed", f"git status returned {proc.returncode}")

    mixed_files: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        if line[0] not in (" ", "?") and line[1] not in (" ", "?"):
            mixed_files.append(line[3:])
    if not mixed_files:
        return _fix_result(False, "noop", "no mixed staged/unstaged files found")
    try:
        subprocess.run(
            ["git", "reset", "HEAD", "--"] + mixed_files, cwd=repo_root,
            capture_output=True, text=True, timeout=30, check=True)
        return _fix_result(True, "reset_mixed_files",
                           f"reset {len(mixed_files)} mixed-state file(s): {mixed_files}")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "reset_failed", f"git reset failed: {exc}")


_TIER1_FIXES: dict[FailureClass, Any] = {
    FailureClass.STALE_BRIDGE_LOCK: lambda root, **kw: fix_stale_bridge_lock(root),
    # STALE_GIT_INDEX_LOCK demoted to Tier 2: no sound ownership check exists
    # to prove the lock is stale vs held by a live git process. See Codex
    # review 2026-03-31 for the pgrep-evasion proof.
    FailureClass.STALE_EXECUTOR_STATE: lambda root, **kw: fix_stale_executor_state(
        root, wave_id=kw.get("wave_id", "")),
    FailureClass.STALE_CONTINUATION: lambda root, **kw: fix_stale_executor_state(
        root, wave_id=kw.get("wave_id", "")),
    FailureClass.MIXED_STAGING: lambda root, **kw: fix_mixed_staging(root),
}

# ---------------------------------------------------------------------------
# Recovery log
# ---------------------------------------------------------------------------

RECOVERY_LOG_DIR = Path(".agent_bus") / "recovery"
RECOVERY_LOG_FILE = RECOVERY_LOG_DIR / "recovery_log.json"
MAX_LOG_ENTRIES = 500


@dataclass
class RecoveryAttempt:
    """Single recovery attempt record."""
    timestamp: str
    wave_id: str
    step: str
    failure_class: str
    tier: int
    action: str
    outcome: str
    duration_s: float
    tokens_used: int = 0
    detail: str = ""


def _load_recovery_log(repo_root: Path) -> list[dict[str, Any]]:
    """Load recovery log, returning empty list on missing/corrupt file."""
    log_path = repo_root / RECOVERY_LOG_FILE
    if not log_path.exists():
        return []
    try:
        data = json.loads(log_path.read_text(encoding="utf-8"))
        return data.get("attempts", []) if isinstance(data, dict) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_recovery_log(repo_root: Path, attempts: list[dict[str, Any]]) -> None:
    """Save recovery log, capped at MAX_LOG_ENTRIES."""
    log_path = repo_root / RECOVERY_LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if len(attempts) > MAX_LOG_ENTRIES:
        attempts = attempts[-MAX_LOG_ENTRIES:]
    log_path.write_text(
        json.dumps({"attempts": attempts}, indent=2) + "\n", encoding="utf-8")


def _count_prior_attempts(
    attempts: list[dict[str, Any]], wave_id: str, step: str, failure_class: str,
) -> int:
    """Count prior recovery attempts for the same (wave_id, step, class) tuple."""
    return sum(1 for e in attempts
               if e.get("wave_id") == wave_id
               and e.get("step") == step
               and e.get("failure_class") == failure_class)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

MAX_ATTEMPTS_PER_TUPLE = 2


def _make_result(recovered: bool, action: str, tier: int,
                 fc: FailureClass, detail: str, exhausted: bool) -> dict[str, Any]:
    return {"recovered": recovered, "action": action, "tier": tier,
            "failure_class": fc.value, "detail": detail, "exhausted": exhausted}


def attempt_recovery(
    repo_root: Path, result: dict[str, Any], wave_id: str,
) -> dict[str, Any]:
    """Attempt recovery for a failed executor result.

    Returns dict with: recovered, action, tier, failure_class, detail, exhausted.
    """
    t0 = time.monotonic()
    fc = classify_failure(result)
    tier = tier_for(fc)
    step = result.get("step", "unknown")

    attempts = _load_recovery_log(repo_root)
    prior = _count_prior_attempts(attempts, wave_id, step, fc.value)

    if prior >= MAX_ATTEMPTS_PER_TUPLE:
        return _make_result(False, "exhausted", tier, fc,
                            f"max {MAX_ATTEMPTS_PER_TUPLE} attempts reached for "
                            f"({wave_id}, {step}, {fc.value})", True)
    if tier == 4:
        return _make_result(False, "escalate", 4, fc,
                            f"tier 4 failure ({fc.value}) requires escalation", False)
    if tier in (2, 3):
        return _make_result(False, "not_implemented", tier, fc,
                            f"tier {tier} recovery not yet implemented", False)

    fix_fn = _TIER1_FIXES.get(fc)
    if fix_fn is None:
        return _make_result(False, "no_fix_registered", tier, fc,
                            f"no tier 1 fix registered for {fc.value}", False)

    fix_result = fix_fn(repo_root, wave_id=wave_id)
    duration = time.monotonic() - t0

    attempt = RecoveryAttempt(
        timestamp=datetime.now(timezone.utc).isoformat(),
        wave_id=wave_id, step=step, failure_class=fc.value, tier=tier,
        action=fix_result.get("action", "unknown"),
        outcome="success" if fix_result.get("fixed") else "failed",
        duration_s=round(duration, 3), tokens_used=0,
        detail=fix_result.get("detail", ""))
    attempts.append(asdict(attempt))
    _save_recovery_log(repo_root, attempts)

    return _make_result(fix_result.get("fixed", False),
                        fix_result.get("action", "unknown"), tier, fc,
                        fix_result.get("detail", ""), False)
