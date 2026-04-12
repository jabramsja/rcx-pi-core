#!/usr/bin/env python3
"""Pipeline recovery gate: failure classification and Tier 1–3 recovery.

Design doc: mu/docs/agents/PipelineRecovery.v0.md
Import constraints: only stdlib + executor_common.
"""
from __future__ import annotations

import atexit
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple, Optional

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
    PR_MERGE_CONFLICT = "pr_merge_conflict"
    # Tier 3 -- LLM diagnosis (small focused prompt)
    GIT_STAGING_CONFLICT = "git_staging_conflict"
    TEST_FAILURE = "test_failure"
    AGENT_REVIEW_CRASH = "agent_review_crash"
    UNKNOWN_ERROR = "unknown_error"
    NEEDS_PHASE_B = "needs_phase_b"
    BOT_FINDINGS_PENDING = "bot_findings_pending"
    # Tier 4 -- escalate (never recover)
    TERMINAL_POLICY = "terminal_policy"
    UNCLASSIFIED = "unclassified"

_TIER_MAP: dict[FailureClass, int] = {
    FailureClass.STALE_BRIDGE_LOCK: 1, FailureClass.STALE_GIT_INDEX_LOCK: 2,
    FailureClass.STALE_EXECUTOR_STATE: 1, FailureClass.STALE_CONTINUATION: 1,
    FailureClass.MIXED_STAGING: 1,
    FailureClass.PROCESS_TIMEOUT: 2, FailureClass.TRANSIENT_KILL: 2,
    FailureClass.AGGREGATION_HANG: 2, FailureClass.IMPLEMENTER_STALE: 2,
    FailureClass.PR_MERGE_CONFLICT: 2,
    FailureClass.GIT_STAGING_CONFLICT: 3, FailureClass.TEST_FAILURE: 3,
    FailureClass.AGENT_REVIEW_CRASH: 3, FailureClass.UNKNOWN_ERROR: 3,
    FailureClass.NEEDS_PHASE_B: 3,
    FailureClass.BOT_FINDINGS_PENDING: 3,
    FailureClass.TERMINAL_POLICY: 4, FailureClass.UNCLASSIFIED: 4,
}

_TERMINAL_STATUSES = frozenset({
    "question_for_founder", "max_rounds_reached",
    "supervisor_rejected",
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
    embedded_stdout = _parse_json_object(stdout)
    embedded_stderr = _parse_json_object(stderr)
    embedded_status = (
        embedded_stdout.get("status")
        or embedded_stderr.get("status")
        or ""
    )
    embedded_step = (
        embedded_stdout.get("step")
        or embedded_stdout.get("executor")
        or embedded_stderr.get("step")
        or embedded_stderr.get("executor")
        or ""
    )
    embedded_reason = " ".join(
        part
        for part in (
            _summarize_json_value(embedded_stdout),
            _summarize_json_value(embedded_stderr),
        )
        if part
    )
    combined_text = " ".join(
        part for part in (stderr, stdout, embedded_reason) if isinstance(part, str) and part
    )
    combined_lower = combined_text.lower()
    reason_text = _summarize_result_reason(result)
    reason_lower = reason_text.lower()
    step_lower = " ".join(part for part in (step, embedded_step) if part).lower()
    status_failed = status in ("error", "failed") or embedded_status in ("error", "failed")

    # Tier 4: terminal policy outcomes (check first, never recover)
    if status in _TERMINAL_STATUSES:
        return FailureClass.TERMINAL_POLICY
    if embedded_status in _TERMINAL_STATUSES:
        return FailureClass.TERMINAL_POLICY

    # Tier 3: needs_phase_b is recoverable (retry Phase B)
    if status == "needs_phase_b" or embedded_status == "needs_phase_b":
        return FailureClass.NEEDS_PHASE_B

    # Tier 3: bot_findings_pending with P1 unresolved → re-invoke implementer
    if status == "bot_findings_pending" or embedded_status == "bot_findings_pending":
        return FailureClass.BOT_FINDINGS_PENDING

    if status_failed and "merge_pr.sh failed" in reason_lower and (
        "not mergeable" in reason_lower
        or "cannot be cleanly created" in reason_lower
        or "merge conflict" in reason_lower
    ):
        return FailureClass.PR_MERGE_CONFLICT

    # Tier 1: deterministic lock/state issues
    if "bridge.lock" in reason_text:
        return FailureClass.STALE_BRIDGE_LOCK
    if "index.lock" in reason_text:
        return FailureClass.STALE_GIT_INDEX_LOCK
    if "phase_b_state.json" in reason_text or "stale_state" in status:
        return FailureClass.STALE_EXECUTOR_STATE
    if (
        "stale continuation" in reason_lower
        or "continuation record is stale" in reason_lower
    ):
        return FailureClass.STALE_CONTINUATION
    if _looks_like_mixed_staging(stderr, stdout, step):
        return FailureClass.MIXED_STAGING

    # Tier 2: transient / timeout issues
    if status == "timeout":
        return FailureClass.PROCESS_TIMEOUT
    if exit_code is not None and exit_code in _TRANSIENT_KILL_CODES:
        return FailureClass.TRANSIENT_KILL
    if "aggregation" in combined_lower:
        return FailureClass.AGGREGATION_HANG
    if result.get("implementer_status") == "stale":
        return FailureClass.IMPLEMENTER_STALE

    # Tier 3: needs diagnosis
    if step in ("stage_files", "git_commit") and "git add" in combined_lower:
        return FailureClass.GIT_STAGING_CONFLICT
    if "test" in combined_lower and ("fail" in combined_lower or "error" in combined_lower):
        return FailureClass.TEST_FAILURE
    review_crash_hints = (
        "bridge subprocess failed",
        "produced no stdout",
        "adapter 'codex'",
        'adapter "codex"',
        "--packet-review",
        "reviewer",
    )
    if status_failed and any(hint in combined_lower for hint in review_crash_hints):
        return FailureClass.AGENT_REVIEW_CRASH
    if status_failed and ("agent" in step_lower or "bridge" in step_lower):
        return FailureClass.AGENT_REVIEW_CRASH
    if status_failed:
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
    """Remove .agent_bus/bridge.lock if no live process holds the flock.

    Uses _claim_and_remove_bridge_lock for atomic probe+remove: acquires
    LOCK_EX|LOCK_NB (proving no live holder), verifies inode identity, and
    unlinks — all while holding the exclusive lock.  This replaces the legacy
    PID-only check which false-positived recovery when the PID was dead but
    the flock was still held by a live fd (Bridge R4 Finding).
    """
    lock_path = repo_root / ".agent_bus" / "bridge.lock"
    if not lock_path.exists():
        return _fix_result(False, "noop", "bridge.lock not found")
    if _claim_and_remove_bridge_lock(lock_path):
        return _fix_result(True, "claim_and_remove_stale_lock",
                           "bridge.lock atomically claimed and removed (flock unheld)")
    return _fix_result(False, "noop",
                       "bridge.lock held by a live flock — cannot remove")


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
# Tier 2 auto-retry with adjustment (zero tokens)
# ---------------------------------------------------------------------------

_CONFIG_PATH_REL = Path("mu") / "tools" / "executors" / "executor_config.json"


def _load_config_timeouts(repo_root: Path) -> dict[str, Any]:
    """Load timeouts dict from executor_config.json (read-only)."""
    config_path = repo_root / _CONFIG_PATH_REL
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        return cfg.get("timeouts", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _probe_bridge_lock_unheld(lock_path: Path) -> bool:
    """Probe whether bridge.lock's flock is held by a live process.

    Returns True if the lock file does not exist or exists but no process
    holds the flock (safe to unlink).  Returns False if a live process
    holds the flock.

    **WARNING:** Do NOT use this function in a probe-then-act pattern
    (probe → unlink).  The gap between probe return and unlink is a TOCTOU
    window — another process can acquire the flock after the probe releases
    it, and unlinking a held flock creates a new inode (Bridge R3 Finding).
    Use ``_claim_and_remove_bridge_lock`` instead for atomic probe+remove.

    Probe pattern mirrors bridge_supervisor.py health-check (lines 2196-2199):
    non-blocking LOCK_EX succeeds iff no process holds the flock.
    """
    if not lock_path.exists():
        return True
    try:
        fd = os.open(str(lock_path), os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return True
        except (IOError, OSError):
            # A live process holds the flock — NOT safe to unlink.
            return False
        finally:
            os.close(fd)
    except OSError:
        # File disappeared between exists() and open() — treat as unheld.
        return True


def _claim_and_remove_bridge_lock(lock_path: Path) -> bool:
    """Atomically probe and remove bridge.lock — closes the TOCTOU window.

    Opens the lock file, acquires LOCK_EX|LOCK_NB, and — while still holding
    the exclusive lock — verifies the path still refers to the same inode,
    then unlinks.  This eliminates the race window in the probe-then-unlink
    pattern (Bridge R3 Finding: between probe return and unlink, another
    process can acquire the flock on the same inode, and unlinking then
    creates a new inode that allows parallel bridge acquisition).

    Inode identity check: after acquiring LOCK_EX, ``fstat(fd)`` is compared
    with ``stat(lock_path)``.  If the inodes differ, the path was replaced
    between ``open()`` and ``flock()`` — we must NOT unlink the replacement
    (it may belong to a legitimate bridge supervisor).

    Returns True if the lock file was removed (or did not exist).
    Returns False if a live process holds the flock, or the path was replaced.
    """
    if not lock_path.exists():
        return True
    try:
        fd = os.open(str(lock_path), os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            # We hold the exclusive lock on this inode — no other process
            # can hold LOCK_EX on it concurrently.
            removed = False
            try:
                fd_stat = os.fstat(fd)
                path_stat = os.stat(str(lock_path))
                if (fd_stat.st_ino == path_stat.st_ino
                        and fd_stat.st_dev == path_stat.st_dev):
                    # Path still refers to the inode we locked — safe to unlink.
                    lock_path.unlink(missing_ok=True)
                    removed = True
                # else: path was replaced — do NOT unlink the replacement.
            except OSError:
                # Path disappeared after our open — already removed by someone.
                removed = True
            fcntl.flock(fd, fcntl.LOCK_UN)
            return removed
        except (IOError, OSError):
            # A live process holds the flock — NOT safe to remove.
            return False
        finally:
            os.close(fd)
    except OSError:
        # File disappeared between exists() and open() — treat as removed.
        return True


def fix_process_timeout(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Increase timeout by 50% (capped at 2x original) via env var override.

    Step-aware: reads the executor name from kw['result'] to target the
    correct timeout key (e.g. commit_executor, phase_a_executor).
    Falls back to 'phase_b_executor' if not available.

    The 2x cap is against the *original* baseline (before any recovery
    bumps), not the current config value.  The dispatcher writes each
    override back to executor_config.json between attempts, so reading
    ``current`` from disk on the second recovery would already reflect
    the first bump — compounding past the intended cap.

    Also clears the bridge lock when the bridge-owning executor
    (phase_b_executor) timed out AND the lock can be atomically claimed and
    removed — a timeout during a bridge review round leaves the lock held by
    a dead process, and the re-launched executor would immediately fail on
    the stale lock.  The lock is NOT cleared for other executors (e.g.
    commit_executor) because they do not own the bridge lock, and is NOT
    cleared even for phase_b_executor if a live process holds the flock.

    Bridge R3 fix: the lock is now claimed and removed atomically via
    ``_claim_and_remove_bridge_lock`` (LOCK_EX held across unlink + inode
    identity check).  The prior probe-then-unlink pattern had a TOCTOU
    window where another process could acquire the flock between the probe
    return and the unlink, creating a new inode at the same path and
    breaking mutual exclusion.
    """
    timeouts = _load_config_timeouts(repo_root)
    # Determine which executor timed out from the result
    result = kw.get("result", {})
    executor = result.get("executor", "phase_b_executor")
    timeout_key = executor if executor in timeouts else "phase_b_executor"

    # Clear stale bridge lock ONLY when the bridge-owning executor timed out.
    # phase_b_executor drives bridge review; its timeout leaves bridge.lock
    # held by a dead PID.  Other executors (commit_executor, phase_a_executor)
    # never hold the bridge lock, so clearing it would violate the
    # control-plane mutual-exclusion invariant.
    #
    # Bridge R3 fix: uses _claim_and_remove_bridge_lock for atomic
    # probe+remove (LOCK_EX held across unlink + inode identity check).
    # The prior probe-then-unlink pattern had a TOCTOU window.
    lock_path = repo_root / ".agent_bus" / "bridge.lock"
    lock_cleared = False
    if executor == "phase_b_executor" and lock_path.exists():
        lock_cleared = _claim_and_remove_bridge_lock(lock_path)
    current = timeouts.get(timeout_key, 3600)
    # Track original baseline across sequential recoveries.  On the first
    # call the env var is absent so we seed it from the (still-original)
    # config value.  Subsequent calls read the stored original.
    baseline_env_key = f"RCX_RECOVERY_ORIGINAL_TIMEOUT_{timeout_key}"
    stored_baseline = os.environ.get(baseline_env_key)
    if stored_baseline is not None:
        baseline = int(stored_baseline)
    else:
        baseline = current
        os.environ[baseline_env_key] = str(baseline)
    new_timeout = min(int(current * 1.5), baseline * 2)
    os.environ["RCX_RECOVERY_TIMEOUT_OVERRIDE"] = str(new_timeout)
    os.environ["RCX_RECOVERY_TIMEOUT_KEY"] = timeout_key
    lock_msg = " + bridge.lock cleared" if lock_cleared else ""
    return _fix_result(True, "increase_timeout",
                       f"timeout for {timeout_key} increased from {current}s "
                       f"to {new_timeout}s (capped at 2x original {baseline}s) "
                       f"via RCX_RECOVERY_TIMEOUT_OVERRIDE{lock_msg}")


def fix_transient_kill(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """No-op fix — marks as retryable. Dispatcher already retries."""
    return _fix_result(True, "retryable",
                       "transient kill — safe to retry with same parameters")


def fix_aggregation_hang(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Clear bridge lock (after flock probe) and mark stale bridge DB jobs as failed.

    Does NOT delete bridge.db — it is the shared job/transcript SQLite bus
    used by bridge_supervisor.py. Only the lock file is removed (atomically
    claimed and unlinked while LOCK_EX is held, with inode identity check)
    and in-progress/pending jobs for the CURRENT WAVE are marked as failed.
    Jobs belonging to other waves (identified by scope_hint) are untouched.

    Bridge R3 fix: uses _claim_and_remove_bridge_lock for atomic
    probe+remove.  The prior probe-then-unlink pattern had a TOCTOU window
    where another process could acquire the flock between the probe return
    and the unlink.
    """
    wave_id = kw.get("wave_id", "")
    cleared: list[str] = []
    # Clear bridge.lock — atomic claim+remove (LOCK_EX held across unlink).
    # Bridge R3 fix: closes the TOCTOU window from the prior
    # probe-then-unlink pattern.
    lock_path = repo_root / ".agent_bus" / "bridge.lock"
    if lock_path.exists() and _claim_and_remove_bridge_lock(lock_path):
        cleared.append(str(lock_path.relative_to(repo_root)))
    # Mark stale/stuck jobs in bridge.db as failed (preserve the DB itself).
    # Wave-scoped: only mark jobs whose scope_hint matches this wave EXACTLY.
    # NULL/empty scope_hint rows are left untouched — they may belong to
    # other waves that didn't set scope_hint (Bridge R7 fix: NULL-scoped
    # rows must not be treated as current-wave work).
    bridge_db = repo_root / ".agent_bus" / "bridge.db"
    if bridge_db.exists():
        try:
            conn = sqlite3.connect(str(bridge_db), timeout=5)
            try:
                if wave_id:
                    cursor = conn.execute(
                        "UPDATE jobs SET status = 'failed', "
                        "terminal_decision = 'recovery_aggregation_hang' "
                        "WHERE status IN ('pending', 'in_progress') "
                        "AND scope_hint = ?",
                        (wave_id,))
                else:
                    cursor = conn.execute(
                        "UPDATE jobs SET status = 'failed', "
                        "terminal_decision = 'recovery_aggregation_hang' "
                        "WHERE status IN ('pending', 'in_progress')")
                stale_count = cursor.rowcount
                conn.commit()
            finally:
                conn.close()
            if stale_count > 0:
                cleared.append(
                    f"bridge.db: marked {stale_count} stale job(s) as failed")
        except (sqlite3.Error, OSError):
            pass  # DB inaccessible — still safe to retry
    if not cleared:
        return _fix_result(True, "no_stale_state",
                           "no bridge state files to clear — safe to retry")
    return _fix_result(True, "clear_bridge_state",
                       f"cleared bridge state: {cleared}")


def fix_implementer_stale(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Increase stale timeout by 50% (capped at 2x original) via env var override."""
    timeouts = _load_config_timeouts(repo_root)
    timeout_key = "phase_b_implementer_stale"
    current = timeouts.get(timeout_key, 300)
    # Same original-baseline tracking as fix_process_timeout — prevent
    # compounding when the dispatcher writes bumped values to disk.
    baseline_env_key = f"RCX_RECOVERY_ORIGINAL_TIMEOUT_{timeout_key}"
    stored_baseline = os.environ.get(baseline_env_key)
    if stored_baseline is not None:
        baseline = int(stored_baseline)
    else:
        baseline = current
        os.environ[baseline_env_key] = str(baseline)
    new_timeout = min(int(current * 1.5), baseline * 2)
    os.environ["RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE"] = str(new_timeout)
    return _fix_result(True, "increase_stale_timeout",
                       f"stale timeout increased from {current}s to {new_timeout}s "
                       f"(capped at 2x original {baseline}s) "
                       f"via RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE")


def _extract_result_pr_number(result: dict[str, Any]) -> str:
    for candidate in (
        result,
        _parse_json_object(result.get("stdout", "")),
        _parse_json_object(result.get("stderr", "")),
    ):
        if not isinstance(candidate, dict):
            continue
        pr_number = candidate.get("pr_number")
        if isinstance(pr_number, (str, int)):
            normalized = str(pr_number).strip()
            if normalized:
                return normalized
    return ""


def fix_pr_merge_conflict(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Sync the feature branch with the PR base branch when mergeability drifted."""
    result = kw.get("result", {})
    pr_number = _extract_result_pr_number(result)
    if not pr_number:
        return _fix_result(False, "missing_pr_number", "could not determine PR number")

    try:
        status_proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "status_failed", f"git status failed: {exc}")
    if status_proc.returncode != 0:
        return _fix_result(False, "status_failed", f"git status returned {status_proc.returncode}")
    if status_proc.stdout.strip():
        return _fix_result(False, "dirty_worktree", "worktree is not clean enough for auto-sync")

    try:
        pr_view = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "baseRefName,mergeStateStatus"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "pr_view_failed", f"gh pr view failed: {exc}")
    if pr_view.returncode != 0:
        detail = (pr_view.stderr or pr_view.stdout or "").strip()
        return _fix_result(False, "pr_view_failed", detail or f"gh pr view returned {pr_view.returncode}")

    try:
        pr_payload = json.loads(pr_view.stdout or "{}")
    except json.JSONDecodeError as exc:
        return _fix_result(False, "pr_view_invalid_json", f"gh pr view returned invalid JSON: {exc}")
    if not isinstance(pr_payload, dict):
        return _fix_result(False, "pr_view_invalid_json", "gh pr view payload was not an object")

    base_branch = str(pr_payload.get("baseRefName", "")).strip()
    merge_state = str(pr_payload.get("mergeStateStatus", "")).strip()
    if not base_branch:
        return _fix_result(False, "missing_base_branch", f"PR #{pr_number} has no baseRefName")

    try:
        fetch_proc = subprocess.run(
            ["git", "fetch", "origin", base_branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "fetch_failed", f"git fetch origin {base_branch} failed: {exc}")
    if fetch_proc.returncode != 0:
        detail = (fetch_proc.stderr or fetch_proc.stdout or "").strip()
        return _fix_result(False, "fetch_failed", detail or f"git fetch returned {fetch_proc.returncode}")

    try:
        merge_proc = subprocess.run(
            ["git", "merge", "--no-edit", f"origin/{base_branch}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "merge_failed", f"git merge origin/{base_branch} failed: {exc}")
    if merge_proc.returncode != 0:
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        detail = (merge_proc.stderr or merge_proc.stdout or "").strip()
        return _fix_result(
            False,
            "merge_base_branch_failed",
            detail or f"git merge returned {merge_proc.returncode}",
        )

    try:
        push_proc = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "push_failed", f"git push origin HEAD failed: {exc}")
    if push_proc.returncode != 0:
        detail = (push_proc.stderr or push_proc.stdout or "").strip()
        return _fix_result(False, "push_failed", detail or f"git push returned {push_proc.returncode}")

    merge_detail = f"merged origin/{base_branch} into the feature branch for PR #{pr_number}"
    if merge_state:
        merge_detail += f" (prior GitHub merge state: {merge_state})"
    merge_detail += " and pushed the sync commit"
    return _fix_result(True, "merge_base_branch_and_push", merge_detail)


_TIER2_FIXES: dict[FailureClass, Any] = {
    FailureClass.STALE_GIT_INDEX_LOCK: lambda root, **kw: fix_stale_git_index_lock(root),
    FailureClass.PROCESS_TIMEOUT: fix_process_timeout,
    FailureClass.TRANSIENT_KILL: fix_transient_kill,
    FailureClass.AGGREGATION_HANG: fix_aggregation_hang,
    FailureClass.IMPLEMENTER_STALE: fix_implementer_stale,
    FailureClass.PR_MERGE_CONFLICT: fix_pr_merge_conflict,
}


# ---------------------------------------------------------------------------
# Tier 3 LLM recovery loop (small focused prompt via claude --print)
# ---------------------------------------------------------------------------

_DANGEROUS_COMMANDS = frozenset({
    "rm -rf", "rm -r ", "git push", "git reset --hard",
    "git push --force", "git checkout .", "git restore .",
    "git clean -f", "dd if=", "mkfs.", "chmod 777",
    "> /dev/sd", ":(){ :|:& };:",
})

# Pattern-based denylist: catch subcommand variations that exact strings miss.
# In Tier 3 recovery, git reset/checkout/restore/push/clean are never
# appropriate — even "soft" variants can destabilize the pipeline working tree.
# The global-option group handles flags (e.g. --no-pager, -C <path>,
# -c key=val) that appear between ``git`` and the subcommand.
_GIT_GLOBAL_OPT = r"(?:\s+-[^\s]*(?:\s+[^-\s][^\s]*)?)*"
_DANGEROUS_GIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+reset\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+checkout\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+restore\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+push\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+clean\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+config\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+fetch\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+pull\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+clone\b"),
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+stash\b"),
    # Layer 3b: git -c key=val allows config injection on ANY subcommand
    # (e.g. git -c core.pager=evil diff, git -c credential.helper=!sh status).
    # Block all git -c forms — Tier 3 recovery never needs runtime config.
    # Uses _GIT_GLOBAL_OPT to catch -c after preceding global options
    # (e.g. git --no-pager -c alias.status=!sh status).
    re.compile(rf"\bgit{_GIT_GLOBAL_OPT}\s+-c\b"),
]

# Layer 1: Shell metacharacters that enable command chaining, piping, subshells,
# or redirection. Tier 3 recovery commands must be simple single commands.
_SHELL_METACHAR_PATTERN = re.compile(
    r"[;|&`]"
    r"|>\s*>"
    r"|[<>]"
    r"|\$\("
    r"|\$\{"
    r"|\$[A-Za-z_]"
    r"|\\."
    r"|[\n\r]"
)

# Layer 7: Interpreter code-execution flags — python/node/ruby/perl with -c/-e
# allow arbitrary code that can bypass every other denylist check.
# Match only exact -c/-e/-p flags (not -E, --norc, etc.)
_INTERPRETER_CODE_EXEC_PATTERN = re.compile(
    r"\b(?:python[23]?(?:\.\d+)?|node|ruby|perl|lua)\s+"
    r"(?:-[^\s]*\s+)*"
    r"-[cep](?:\s|$)"
)

# Layer 6: Shell wrapper detection — sh/bash/zsh/dash/ksh with -c allow
# arbitrary command execution that bypasses every other denylist.
# Match only exact -c flag (not --norc, --rcfile, etc.)
_SHELL_WRAPPER_PATTERN = re.compile(
    r"\b(?:sh|bash|zsh|dash|ksh|csh|tcsh)\s+"
    r"(?:-[^\s]*\s+)*"
    r"-c(?:\s|$)"
)

# Layer 4: Network egress commands — recovery should never reach the network.
_DANGEROUS_NETWORK_COMMANDS: frozenset[str] = frozenset({
    "curl", "wget", "nc", "ncat", "nmap", "socat",
    "ssh", "scp", "rsync", "ftp", "sftp", "telnet",
})

# Layer 8: Package-manager commands — direct installer CLIs are network egress +
# supply-chain risk.
_DANGEROUS_PACKAGE_MANAGERS: frozenset[str] = frozenset({
    "pip", "pip3", "npm", "npx", "yarn", "pnpm",
    "gem", "cargo", "composer", "brew", "apt", "apt-get", "yum", "dnf",
    "apk", "pacman", "conda", "mamba", "pipx", "poetry", "uv",
})

# Layer 8b: Python stdlib modules that either reach the network or
# execute arbitrary host code when invoked via ``python -m``.  Bridge R3
# Finding 2: ``python3 -m trace --trace script.py`` and ``python3 -m pdb
# script.py`` executed the target script unchecked because Layer 11's
# ``-m`` short-circuit delegated module safety to this denylist, yet
# ``trace``/``pdb`` and their execution-capable siblings were absent.
# The denylist now covers:
#   - Network modules (http/smtp/ftp/xmlrpc/urllib)
#   - Package managers (pip/ensurepip)
#   - Script-execution stdlib modules: ``trace``, ``pdb``, ``runpy``,
#     ``zipapp``, ``timeit``, ``cProfile``/``profile``, ``py_compile``,
#     ``compileall``, ``venv``.  All of these accept a script/module
#     argument and execute it (``cProfile``/``trace``/``pdb``/``profile``
#     wrap the target in an instrumented runner; ``runpy`` runs a file
#     or module as ``__main__``; ``timeit`` parses a code string;
#     ``zipapp`` can bundle arbitrary sources into an executable archive;
#     ``py_compile``/``compileall`` write bytecode files; ``venv``
#     writes a virtualenv tree with activators).
# Module names are lowercased so entries must match the lowercased form.
_DANGEROUS_PYTHON_MODULES: frozenset[str] = frozenset({
    # Network / package-manager modules
    "http.server", "http.client", "smtplib", "ftplib",
    "urllib", "urllib.request", "xmlrpc.server", "xmlrpc.client",
    "simplehttpserver", "pip", "ensurepip",
    # Script-execution stdlib modules (Bridge R3 Finding 2)
    "trace", "pdb", "runpy", "zipapp",
    "timeit", "cprofile", "profile",
    "py_compile", "compileall", "venv",
})

# ``-m\s*`` (zero-or-more whitespace) catches both the canonical
# ``python3 -m trace`` and the short-flag-glued ``python3 -mtrace``
# form (Python accepts both; the latter would otherwise bypass Layer 8b
# because the prior ``-m\s+`` regex required at least one space).
_PYTHON_MODULE_RUN_PATTERN = re.compile(
    r"\b(?:python[23]?(?:\.\d+)?)\s+"
    r"(?:-[^\s]*\s+)*"
    r"-m\s*(\S+)"
)

# Layer 5: Sensitive host paths that should never be read/written by recovery.
# Uses prefix matching (e.g. /etc/pass) to catch shell globs (/etc/pass*).
# Covers absolute home paths (/root/.ssh, /home/<user>/.ssh) in addition to
# tilde and $HOME references.
_SENSITIVE_PATH_PATTERN = re.compile(
    r"/etc/(?:pass|shad|sudoer|ssh)"
    r"|/proc\b"
    r"|/dev/(?!null|urandom)"
    r"|(?:~|\$HOME|\$\{HOME\}|/root|/home/[^\s/]+)/\.(?:ssh|gnupg|aws)\b"
)

# Command-position prefix commands (sudo, env, nohup, etc.).
#
# Bridge R5 Finding 1 / Finding 2: ``command``, ``exec``, and ``eval`` are
# shell dispatch/re-parse builtins that consume their own flags and then
# run whatever follows as the real command.  They share the same
# semantics as ``sudo``/``env``/``nohup`` from the denylist's point of
# view: the token at position 0 is NOT the executed command, the token
# after the prefix's flags IS.  Prior to this fix the resolver returned
# ``command``/``exec`` as the basename (so ``command curl evil`` / ``exec
# curl evil`` bypassed Layer 4) and did not know ``eval`` at all (so
# ``eval curl evil``, after ``_strip_shell_quotes``, bypassed every
# layer).  Adding them here routes every downstream layer (Layer 4
# network, Layer 10 rm, Layer 11 shell/interpreter, Layer 12 cp/mv/kill,
# Layer 13 sudo -s / env -S) through the token that actually runs.
#
# - ``command [-pvV] COMMAND [args...]`` — bash/POSIX builtin that runs
#   COMMAND while bypassing function/alias lookup.  All three flags
#   (``-p`` default PATH, ``-v``/``-V`` print type) are switches with no
#   argument, so the default prefix-stripping loop correctly skips them
#   before reaching COMMAND.
# - ``exec [-cl] [-a NAME] COMMAND [args...]`` — bash builtin that
#   replaces the current shell with COMMAND.  ``-c`` / ``-l`` are
#   switches; ``-a NAME`` consumes the following argv0 token, so it
#   MUST appear in ``_PREFIX_FLAGS_WITH_ARG[\"exec\"]`` below — otherwise
#   ``exec -a good curl evil`` would resolve to ``good`` (attacker-
#   chosen string) as the command basename and bypass every layer.
#   Redirection-only forms (``exec > file``, ``exec 2>&1``) are caught
#   by Layer 1's metacharacter check.
# - ``eval [arguments]`` — bash/POSIX builtin that concatenates
#   arguments into a string and parses the result as a shell command
#   line.  After ``_strip_shell_quotes`` normalisation, ``eval 'curl
#   evil'`` and ``eval curl evil`` tokenize identically, so treating
#   ``eval`` as a prefix routes the downstream layers through the
#   re-parsed command.  ``eval`` has no standard flags, so no
#   ``_PREFIX_FLAGS_WITH_ARG`` entry is needed.
_COMMAND_PREFIXES: frozenset[str] = frozenset({
    "sudo", "env", "nice", "nohup", "time", "timeout",
    "strace", "ltrace", "ionice",
    # Bridge R5: shell dispatch / re-parse builtins
    "command", "exec", "eval",
})

# Per-prefix flags that consume the *next* token as their argument.
# Used by _get_command_basename to skip both the flag and its value so
# the actual command token is found.  Example: sudo -u root curl →
# -u is matched here, "root" is skipped, "curl" is returned.
# NOTE: All short flags are LOWERCASED because all callers of
# _get_command_basename pass lowercased tokens.
_PREFIX_FLAGS_WITH_ARG: dict[str, frozenset[str]] = {
    "sudo": frozenset({
        "-u", "--user", "-g", "--group", "-c", "--close-from",
        "-d", "--chdir", "-h", "--host", "-p", "--prompt",
        "-r", "--chroot", "-t", "--command-timeout", "--other-user",
    }),
    "env": frozenset({
        "-c", "--chdir", "-u", "--unset",
    }),
    "timeout": frozenset({
        "-s", "--signal", "-k", "--kill-after",
    }),
    "nice": frozenset({"-n", "--adjustment"}),
    "strace": frozenset({
        "-e", "--trace", "-o", "--output", "-p", "--attach",
        "-s", "--string-limit",
    }),
    "ltrace": frozenset({"-e", "-o", "-p", "-s", "-n", "-f"}),
    "ionice": frozenset({
        "-c", "--class", "-n", "--classdata", "-p", "--pid",
    }),
    # Bridge R5 Finding 1: ``exec -a NAME COMMAND`` sets argv[0] for
    # COMMAND.  The resolver must skip both ``-a`` and the NAME token so
    # the basename lookup reaches COMMAND itself — otherwise
    # ``exec -a good curl http://evil.com`` resolves to ``good`` and
    # every downstream layer (Layer 4 network in particular) is
    # bypassed.  ``command`` and ``eval`` have no arg-consuming flags
    # in their POSIX/bash forms so no entries are needed for them.
    "exec": frozenset({"-a"}),
}

# Layer 13: Prefix-native exec-mode flags.  Bridge R3 Finding 1: the
# prefix-stripping resolver assumed every prefix flag was either a bare
# switch or a ``--flag VALUE`` pair whose value was inert (``sudo -u
# root``, ``env -u VAR``).  Several prefix flags actually spawn a shell
# or re-parse a string as a full command line, so the resolver loses
# the real executable instead of reaching it:
#
# - ``sudo -s/--shell`` / ``sudo -i/--login`` — run the target user's
#   shell.  The shell itself IS the executed command; nothing else in
#   argv is needed to reach a PID.
# - ``env -S/--split-string STRING`` — env parses STRING as a shell
#   command line and execs the result.  The command is inside STRING,
#   not at token position, so Layer 4 / Layer 11 never see it.
# - ``env -P/--path PATH`` — BSD env resolves the following utility
#   against a caller-supplied PATH, so basename lookup is meaningless
#   (the PATH may point at a malicious directory).
#
# All four modes execute code that no other layer can inspect.  Tier 3
# recovery has no legitimate need for any of them; block unconditionally.
_DANGEROUS_PREFIX_EXEC_FLAGS: dict[str, frozenset[str]] = {
    "sudo": frozenset({"-s", "--shell", "-i", "--login"}),
    "env":  frozenset({"-s", "--split-string", "-p", "--path"}),
}

# Layer 9: Command-composition utilities that execute subcommands.
# xargs/watch/parallel run arbitrary programs; find -exec/-execdir/-ok/
# -okdir all run arbitrary commands against matched paths.  Bridge R3
# Finding 3: ``-execdir`` and ``-okdir`` (GNU find) were not covered by
# the prior ``-exec``-only regex, so ``find . -execdir curl {} +`` and
# ``find . -okdir curl {} +`` reached the Tier 3 shell executor.  None
# of the four forms have legitimate use in Tier 3 recovery.
_COMMAND_COMPOSITION_PATTERN = re.compile(
    r"\bxargs\b"
    r"|\bwatch\s"
    r"|\bparallel\b"
    r"|\bfind\b.*\s-(?:exec|ok)(?:dir)?\b"
)

# Layer 10: Destructive file-system commands — any rm/rmdir/unlink/shred at
# command position (with or without flags) is blocked.  Tier 3 recovery
# should never delete files.
_DANGEROUS_DESTRUCTIVE_COMMANDS: frozenset[str] = frozenset({
    "rm", "rmdir", "unlink", "shred",
})

# Layer 11: Shell / interpreter execution — the shell wrapper (Layer 6) and
# code-exec flag (Layer 7) rules only block ``-c/-e/-p`` forms.  Script-file
# invocations (``bash poc.sh``, ``python3 poc.py``) and dot-source builtins
# (``. poc.sh``, ``source poc.sh``) execute arbitrary code without those
# flags and previously bypassed the denylist (Bridge R1 Finding 2).
#
# This layer blocks at command position (after prefix stripping):
# - Any shell basename (sh, bash, zsh, dash, ksh, csh, tcsh, ...) with or
#   without arguments.  Tier 3 recovery has no legitimate need to spawn a
#   shell; even bare ``bash`` is suspicious.
# - The dot-source builtin tokens ``.`` and ``source``.
# - Any code interpreter (python/python3, node, ruby, perl, lua, php, ...)
#   invoked with a positional (non-flag) argument.  ``-m <module>`` pairs
#   are allowed at this layer because Layer 8b already enforces the
#   dangerous-module denylist.
_SHELL_INTERPRETER_BASENAMES: frozenset[str] = frozenset({
    "sh", "bash", "zsh", "dash", "ksh", "csh", "tcsh",
    "ash", "mksh", "yash", "fish", "rbash",
})

_CODE_INTERPRETER_BASENAMES: frozenset[str] = frozenset({
    "node", "nodejs", "ruby", "perl", "lua", "php", "tclsh",
    "awk", "gawk", "mawk",
})

# Dot-source builtins match on the raw token (``.`` has no filesystem
# basename form); ``source`` is a bash/zsh alias for the same builtin.
_DOT_BUILTIN_TOKENS: frozenset[str] = frozenset({".", "source"})

# Matches python, python2, python3, python2.7, python3.10, python3.11, etc.
_PYTHON_BASENAME_PATTERN = re.compile(r"^python(?:[23](?:\.\d+)?)?$")

# Layer 12: File-data movement (cp/mv) and process-signalling (kill/pkill/
# killall) commands.  Bridge R2 Finding: the prior denylist let
# ``cp .env /tmp/leak``, ``mv recovery_gate.py /tmp/recovery_gate.py``,
# ``kill 12345``, and ``pkill -f claude`` reach the Tier 3 shell executor
# because Layer 10 only covered destructive filesystem commands
# (rm/rmdir/unlink/shred), not data-exfiltration moves or process kills.
# Tier 3 recovery has no legitimate need to copy or move repo files, nor
# to signal other processes — the pipeline supervisor owns process
# lifecycle and git owns file restoration.  Matching is at command
# position (prefix-aware) so ``sudo cp``, ``env mv``, ``sudo kill`` are
# also blocked.
_DANGEROUS_COPY_MOVE_KILL_COMMANDS: frozenset[str] = frozenset({
    "cp", "mv",
    "kill", "pkill", "killall",
})

MAX_RECOVERY_ITERATIONS = 3
_CLAUDE_TIMEOUT = 180
_SHELL_TIMEOUT = 30
_TRIVIAL_EXCERPTS = frozenset({"{", "}", "[", "]", ",", '"', '",', "{}", "[]"})


def _strip_shell_quotes(text: str) -> str:
    """Remove shell quoting characters so regex patterns can match regardless of quoting."""
    return text.replace('"', "").replace("'", "")


# POSIX shell env-assignment pattern: variable name is
# ``[A-Za-z_][A-Za-z0-9_]*`` followed by ``=``.  POSIX shells allow zero
# or more ``NAME=value`` assignments at the start of a simple command,
# even without an explicit ``env``/``sudo`` prefix.  For example,
# ``FOO=1 curl http://x`` runs ``curl`` with ``FOO=1`` in its
# environment — ``FOO=1`` is NOT the command.  Bridge R4 Finding 1:
# the prefix-stripping resolver only recognised ``KEY=value`` tokens
# inside an active prefix zone, so bare leading assignments resolved
# to the assignment token itself as the command basename and bypassed
# every downstream denylist layer (network, shell, rm, cp, interpreter,
# etc.).  Matching a POSIX-valid identifier (not just any ``=``) avoids
# false positives on literal filenames or arguments that happen to
# contain ``=`` (e.g. ``./a=b``).
_ENV_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _is_env_assignment(token: str) -> bool:
    """Return True if ``token`` is a POSIX ``NAME=value`` env assignment.

    Used by the prefix-stripping state machines (``_resolve_command_start``
    and ``_uses_dangerous_prefix_exec_mode_normalized``) to consume leading
    env assignments — both bare (``FOO=1 curl ...``) and prefix-wrapped
    (``sudo FOO=1 curl ...``, ``env FOO=1 pip ...``) — so the resolver
    reaches the real command instead of stopping at the assignment.
    """
    return bool(_ENV_ASSIGNMENT_PATTERN.match(token))


def _resolve_command_start(tokens: list[str]) -> int:
    """Return the index of the first non-prefix command-position token.

    Encodes the prefix-stripping state machine shared by
    ``_get_command_basename`` and ``_get_command_body_tokens``.  Returns
    ``len(tokens)`` if every token is consumed by prefix handling (e.g.
    bare ``sudo`` with no trailing command).
    """
    i = 0
    current_prefix: str | None = None
    while i < len(tokens):
        token = tokens[i]
        # POSIX shell: leading ``NAME=value`` assignments precede the real
        # command (``FOO=1 curl ...`` runs ``curl``).  This check runs
        # BEFORE the prefix lookup so bare leading assignments (no
        # ``env``/``sudo`` prefix) are consumed the same way the shell
        # would consume them.  It also handles mid-zone sudo-style
        # assignments (``sudo FOO=1 curl ...``) that the prefix-zone
        # fallback previously caught via the broader ``"=" in token``
        # check.  Bridge R4 Finding 1: without this, bare leading
        # assignments resolved to the assignment token itself and every
        # downstream denylist layer (network/shell/rm/cp/interpreter)
        # was bypassed.
        if _is_env_assignment(token):
            i += 1
            continue
        basename = token.rsplit("/", 1)[-1]
        if basename in _COMMAND_PREFIXES:
            current_prefix = basename
            i += 1
            continue
        if current_prefix is not None:
            # Skip flags belonging to the prefix command itself
            if token.startswith("-"):
                if "=" not in token and i + 1 < len(tokens):
                    flags = _PREFIX_FLAGS_WITH_ARG.get(current_prefix, frozenset())
                    if token.startswith("--"):
                        consumes = token in flags
                    else:
                        # Bridge re-entry Finding 1: check EVERY char in a
                        # combined short-flag bundle, not just the last.
                        # A reordered bundle like ``sudo -un root curl``
                        # puts the arg-consuming ``-u`` BEFORE the boolean
                        # ``-n``; checking only the trailing char (``-n``)
                        # treated the bundle as non-consuming, leaving the
                        # next token (the user value ``root``) in place
                        # and routing it to the command position while
                        # ``curl`` silently bypassed the denylist.  The
                        # existing ``-nu`` (u at end) form already matched
                        # because the last-char check caught ``-u``; any-
                        # char iteration makes both orderings symmetric,
                        # aligning with the intent documented in the
                        # ``test_get_command_basename_flag_arguments``
                        # ``-nu`` case (``-n`` standalone then ``-u``
                        # takes arg).  This mirrors the Layer 13
                        # dangerous-flag iterator pattern at line 1316 ff.
                        consumes = len(token) >= 2 and any(
                            f"-{ch}" in flags for ch in token[1:]
                        )
                    if consumes:
                        i += 2  # Skip flag and its argument
                        continue
                i += 1
                continue
            # Skip numeric positional args (e.g., timeout 5, nice -10)
            try:
                float(token)
                i += 1
                continue
            except ValueError:
                pass
            current_prefix = None
        return i
    return len(tokens)


def _get_command_basename(tokens: list[str]) -> str:
    """Return the basename of the first command-position token.

    Skips known prefix commands (sudo, env, nohup, etc.) and their own
    flags (``-i``, ``-n``, etc.), flag arguments (``-u root``,
    ``--user root``), env assignments (``FOO=1``), and numeric positional
    args (``timeout 5``).  Flag-argument skipping uses the per-prefix
    ``_PREFIX_FLAGS_WITH_ARG`` map to avoid heuristic parsing.
    """
    if not tokens:
        return ""
    start = _resolve_command_start(tokens)
    if start >= len(tokens):
        # Prefix-handling exhausted every token (e.g. ``sudo -u root`` with
        # no trailing command).  Fall back to the last token's basename so
        # downstream basename lookups stay bounded.
        return tokens[-1].rsplit("/", 1)[-1]
    return tokens[start].rsplit("/", 1)[-1]


def _get_command_body_tokens(tokens: list[str]) -> list[str]:
    """Return the token slice starting at the resolved command position.

    Parallel to ``_get_command_basename`` but preserves the full remaining
    argv so callers can inspect the command AND its arguments after prefix
    stripping.  ``env bash -c 'foo'`` returns ``['bash', '-c', "'foo'"]``,
    ``sudo -u root python3 poc.py`` returns ``['python3', 'poc.py']``.

    Used by the prefix-aware shell-wrapper / script-file detectors (Bridge
    R1 Findings 1 & 2: prefix commands and script-file invocations must
    not hide shell/interpreter execution from the denylist).
    """
    if not tokens:
        return []
    start = _resolve_command_start(tokens)
    if start >= len(tokens):
        return []
    return tokens[start:]


def _targets_git_internals(text: str) -> bool:
    """Check if text references .git/ internal paths.

    Strips shell quotes first so that ``cat ".git"/config`` is still caught.
    """
    normalized = _strip_shell_quotes(text)
    return ".git/" in normalized or ".git\\" in normalized


def _has_shell_metacharacters(cmd: str) -> bool:
    """Return True if cmd contains shell metacharacters (chaining/redirect)."""
    return bool(_SHELL_METACHAR_PATTERN.search(cmd))


def _uses_network_command_normalized(cmd_lower: str) -> bool:
    """Return True if pre-lowered cmd invokes a network egress tool."""
    tokens = cmd_lower.split()
    if not tokens:
        return False
    basename = _get_command_basename(tokens)
    return basename in _DANGEROUS_NETWORK_COMMANDS


def _uses_shell_wrapper_normalized(cmd_lower: str) -> bool:
    """Return True if the command at command position is a shell with -c.

    Resolves the command position via ``_get_command_body_tokens`` so that
    prefix commands (``env bash -c 'foo'``, ``sudo bash -c 'foo'``,
    ``sudo -u root bash -c 'foo'``) cannot hide the shell wrapper behind
    the prefix.  Without the prefix strip the previous ``match`` at string
    start matched ``bash`` at position 0 only and every prefix-wrapped form
    bypassed the check (Bridge R1 Finding 1).

    The stripped body is re-joined before regex matching so that the
    existing ``_SHELL_WRAPPER_PATTERN`` (which requires ``-c`` after the
    shell name) still works, and so that ``echo "bash -c"`` is still NOT
    matched — ``echo`` has no prefix-strip semantics, its body starts at
    ``echo``, and the shell regex does not match there.
    """
    tokens = cmd_lower.split()
    body = _get_command_body_tokens(tokens)
    if not body:
        return False
    body_str = " ".join(body)
    return bool(_SHELL_WRAPPER_PATTERN.match(body_str))


def _is_python_basename(basename: str) -> bool:
    """Return True if the basename is any python interpreter variant."""
    return bool(_PYTHON_BASENAME_PATTERN.match(basename))


def _uses_shell_or_interpreter_execution_normalized(cmd_lower: str) -> bool:
    """Return True if the command invokes a shell, dot-source builtin, or
    code interpreter at command position (Layer 11, Bridge R1 Finding 2).

    Catches execution paths that Layers 6 and 7 miss:

    - ``bash poc.sh`` / ``sh poc.sh`` — shell with a script-file argument
      (Layer 6 only checks ``-c``).
    - ``. poc.sh`` / ``source poc.sh`` — dot-source builtin that reads a
      script file into the current shell context.
    - ``python3 poc.py`` / ``node index.js`` — interpreter with a script
      file argument (Layer 7 only checks ``-c/-e/-p``).

    Command-position resolution runs through ``_get_command_body_tokens``
    so prefix commands (``env bash poc.sh``, ``sudo python3 poc.py``) are
    covered too.

    Interpreter + ``-m <module>`` is NOT blocked by this layer — the
    dangerous-module denylist in ``_uses_dangerous_python_module_normalized``
    (Layer 8b) enforces the module scope.  Bare flag-only forms like
    ``python3 --version`` remain allowed.
    """
    tokens = cmd_lower.split()
    body = _get_command_body_tokens(tokens)
    if not body:
        return False

    first = body[0]

    # Dot-source builtin — raw-token equality (``.`` has no basename form).
    if first in _DOT_BUILTIN_TOKENS:
        return True

    basename = first.rsplit("/", 1)[-1]

    # Shell basename at command position is always blocked in Tier 3 —
    # bare ``bash``, ``bash poc.sh``, ``bash -c ...``, ``sh script.sh``.
    if basename in _SHELL_INTERPRETER_BASENAMES:
        return True

    # Code interpreter at command position with a non-flag positional
    # argument.  ``-m <module>`` and ``-m<module>`` (glued) forms hand off
    # to module invocation mode (module denylist enforced separately by
    # Layer 8b).  Pure-flag forms (``python3 --version``, ``python3 -h``)
    # and bare ``python3`` are allowed.
    if basename in _CODE_INTERPRETER_BASENAMES or _is_python_basename(basename):
        idx = 1
        while idx < len(body):
            arg = body[idx]
            if arg == "-m" or (arg.startswith("-m") and len(arg) > 2):
                # ``-m <module> [args...]`` or the short-flag-glued
                # ``-m<module> [args...]`` form is module invocation, not
                # a script-file invocation.  Python accepts both spellings
                # (``python3 -mjson.tool data.json`` is equivalent to
                # ``python3 -m json.tool data.json``), and Layer 8b's
                # ``_PYTHON_MODULE_RUN_PATTERN`` already handles both via
                # its ``-m\s*(\S+)`` regex — so dangerous glued forms like
                # ``python3 -mpip install evil`` and ``python3 -mtrace
                # script.py`` remain blocked upstream by the dangerous-
                # module denylist.  Everything after the ``-m`` (or glued
                # module name) is the module's own argv — Layer 11 must
                # not re-parse it as a script positional, otherwise safe
                # invocations like ``python3 -m pytest tests/``,
                # ``python3 -mpytest tests/`` or ``python3 -mjson.tool
                # data.json`` would be blocked.
                return False
            if arg.startswith("-"):
                idx += 1
                continue
            # Non-flag positional argument — script file or similar.
            return True
    return False


def _uses_interpreter_code_exec_normalized(cmd_raw: str) -> bool:
    """Return True if cmd invokes interpreter with lowercase -c/-e/-p.

    Accepts RAW (non-lowered) input so -E (ignore env) is not confused
    with -e (execute). The regex is compiled with re.IGNORECASE for the
    interpreter name but the flag character [cep] is lowercase-only
    since IGNORECASE would also match -C/-E/-P which are NOT code exec.
    """
    # Two-step: find interpreter name case-insensitively, then check
    # if a lowercase -c/-e/-p flag follows
    interp_match = re.search(
        r"\b(?:python[23]?(?:\.\d+)?|node|ruby|perl|lua)\s+",
        cmd_raw, re.IGNORECASE,
    )
    if not interp_match:
        return False
    after_interp = cmd_raw[interp_match.end():]
    # Match optional preceding flags, then exactly -c, -e, or -p (lowercase only)
    return bool(re.match(r"(?:-[^\s]*\s+)*-[cep](?:\s|$)", after_interp))


def _uses_package_manager_normalized(cmd_lower: str) -> bool:
    """Return True if pre-lowered cmd invokes a standalone package manager."""
    tokens = cmd_lower.split()
    if not tokens:
        return False
    basename = _get_command_basename(tokens)
    return basename in _DANGEROUS_PACKAGE_MANAGERS


def _uses_dangerous_python_module_normalized(cmd_lower: str) -> bool:
    """Return True if pre-lowered cmd runs a network-capable Python module via -m."""
    m = _PYTHON_MODULE_RUN_PATTERN.search(cmd_lower)
    if not m:
        return False
    module = m.group(1)
    return module in _DANGEROUS_PYTHON_MODULES or module.rsplit(".", 1)[0] in _DANGEROUS_PYTHON_MODULES


def _targets_sensitive_paths(cmd: str) -> bool:
    """Return True if cmd references sensitive host paths."""
    return bool(_SENSITIVE_PATH_PATTERN.search(cmd))


def _uses_command_composition_normalized(cmd_lower: str) -> bool:
    """Return True if cmd uses xargs/watch/parallel/find-exec composition."""
    return bool(_COMMAND_COMPOSITION_PATTERN.search(cmd_lower))


def _uses_destructive_command_normalized(cmd_lower: str) -> bool:
    """Return True if the command-position basename is a destructive FS command."""
    tokens = cmd_lower.split()
    if not tokens:
        return False
    basename = _get_command_basename(tokens)
    return basename in _DANGEROUS_DESTRUCTIVE_COMMANDS


def _uses_copy_move_kill_normalized(cmd_lower: str) -> bool:
    """Return True if the command-position basename is cp/mv/kill/pkill/killall.

    Layer 12: Tier 3 recovery must not move or copy repo files (exfiltration
    of secrets, relocation of source files) and must not signal other
    processes (supervisor/agent disruption).  Prefix-aware via
    ``_get_command_basename`` so ``sudo cp``, ``env mv``, ``nohup kill``
    are all caught.
    """
    tokens = cmd_lower.split()
    if not tokens:
        return False
    basename = _get_command_basename(tokens)
    return basename in _DANGEROUS_COPY_MOVE_KILL_COMMANDS


def _uses_dangerous_prefix_exec_mode_normalized(cmd_lower: str) -> bool:
    """Return True if a prefix command uses an exec-mode flag (Layer 13).

    Bridge R3 Finding 1: ``sudo -s``, ``sudo -i``, ``env -S STRING`` and
    ``env -P PATH`` all execute code that the command-position basename
    resolver cannot reach — the "command" is either the prefix tool
    itself running a shell (``sudo -s``) or encoded in a flag argument
    that the resolver treats as an inert value (``env -S "curl evil"``).
    Layer 13 scans every token in the prefix zone (before the first
    non-flag, non-argument command-position token) and blocks the
    command outright if any token matches a per-prefix dangerous-flag
    set.

    Handles four token shapes:
      - Long option: ``--shell`` / ``--split-string`` / ``--path``
      - Long option with value: ``--split-string=curl`` / ``--path=/tmp``
      - Short option: ``-s``, ``-i``, ``-p``
      - Combined / glued short option: ``-ns`` (= ``-n -s``), ``-Scurl``
        (= ``-S curl``).  Every letter after the leading dash is checked
        against the dangerous-flag set, so both combination forms are
        caught.

    Prefix-stripping semantics mirror ``_resolve_command_start`` so that
    flag-with-arg pairs (``sudo -u user``, ``env -c /tmp``) are skipped
    correctly and chained prefixes (``sudo env -S ...``) are scanned
    end-to-end.
    """
    tokens = cmd_lower.split()
    if not tokens:
        return False
    i = 0
    current_prefix: str | None = None
    while i < len(tokens):
        token = tokens[i]

        # POSIX shell: leading ``NAME=value`` assignments precede the
        # real command (``FOO=1 sudo -s`` still invokes sudo).  Consume
        # them unconditionally so the state machine reaches the prefix
        # lookup below.  Without this, a bare leading assignment would
        # trigger the ``current_prefix is None`` early return and
        # Layer 13 would miss dangerous exec-mode flags entirely
        # (``FOO=1 sudo -s`` → bypass).  Matches both before the first
        # prefix AND sudo-style mid-zone assignments (``sudo FOO=1 -s``),
        # replacing the later ``if "=" in token`` fallback with a single
        # POSIX-strict identifier check.
        if _is_env_assignment(token):
            i += 1
            continue

        basename = token.rsplit("/", 1)[-1]

        # Enter (or re-enter) the prefix zone when a prefix basename
        # appears — chained prefixes like ``sudo env nohup ...`` all
        # contribute their own dangerous-flag sets.
        if basename in _COMMAND_PREFIXES:
            current_prefix = basename
            i += 1
            continue

        if current_prefix is None:
            return False

        dangerous = _DANGEROUS_PREFIX_EXEC_FLAGS.get(current_prefix, frozenset())

        # Long option: --flag or --flag=value
        if token.startswith("--"):
            bare = token.split("=", 1)[0]
            if bare in dangerous:
                return True
            if "=" not in token and i + 1 < len(tokens):
                flags = _PREFIX_FLAGS_WITH_ARG.get(current_prefix, frozenset())
                if token in flags:
                    i += 2
                    continue
            i += 1
            continue

        # Short option: -s, -si (combined), -Scurl (glued value).
        # Check every character after the leading dash so combined and
        # glued forms both route to the dangerous-flag set.
        if token.startswith("-") and len(token) >= 2:
            for ch in token[1:]:
                if f"-{ch}" in dangerous:
                    return True
            if "=" not in token and i + 1 < len(tokens):
                flags = _PREFIX_FLAGS_WITH_ARG.get(current_prefix, frozenset())
                # Bridge re-entry Finding 1: same any-char-in-bundle
                # check as ``_resolve_command_start``.  A reordered bundle
                # like ``sudo -un root -s`` needed the flag-arg pair
                # ``-u root`` skipped to reach the trailing dangerous
                # ``-s``; with the old ``f"-{token[-1]}" in flags`` check
                # only the last char (``-n``) was inspected, the pair was
                # NOT skipped, and Layer 13 returned False on the
                # intervening ``root`` positional — bypassing the shell-
                # flag block.  Matching any arg-consuming flag in the
                # bundle mirrors the dangerous-flag iterator above and
                # routes Layer 13 through the real exec-mode flag.
                if any(f"-{ch}" in flags for ch in token[1:]):
                    i += 2
                    continue
            i += 1
            continue

        # env KEY=VALUE assignment — stays in the prefix zone.
        if "=" in token:
            i += 1
            continue

        # Numeric positional (``timeout 30``, ``nice -5``) — still in
        # the prefix zone; the next non-numeric token is the command.
        try:
            float(token)
            i += 1
            continue
        except ValueError:
            pass

        # Non-flag, non-numeric, non-assignment token → command position
        # reached.  Layer 13 has nothing more to check; downstream layers
        # (Layer 4, Layer 11, Layer 12) inspect the command itself.
        return False

    return False


def _is_dangerous_command(cmd: str) -> bool:
    """Check if a shell command matches the 13 denylist layers.

    All pattern/token checks run against a quote-stripped normalisation so
    that ``"sh" -c "..."`` or ``"git" push`` cannot bypass word-boundary matching.
    Note: ``_has_shell_metacharacters`` runs on the RAW command because quotes
    don't neutralise metacharacters when ``shell=True``.
    """
    # Layer 1: metacharacter check on raw text
    if _has_shell_metacharacters(cmd):
        return True

    # Quote-stripped text for remaining checks
    normalized_raw = _strip_shell_quotes(cmd).strip()
    normalized_lower = normalized_raw.lower()

    # Layer 2: exact-match denylist
    for denied in _DANGEROUS_COMMANDS:
        if denied in normalized_lower:
            return True
    # Layer 3: git subcommand patterns with global-option awareness
    for pattern in _DANGEROUS_GIT_PATTERNS:
        if pattern.search(normalized_lower):
            return True
    # Layer 13: prefix-native exec-mode flags (sudo -s/-i, env -S/-P).
    # Runs EARLY so prefix-encoded execution modes are caught before the
    # command-basename resolver would have to trust a synthetic target.
    if _uses_dangerous_prefix_exec_mode_normalized(normalized_lower):
        return True
    # Layer 4: network egress commands (command-position only)
    if _uses_network_command_normalized(normalized_lower):
        return True
    # Layer 5: sensitive host paths (case-sensitive for $HOME)
    if _targets_sensitive_paths(normalized_raw):
        return True
    # Layer 6: shell wrappers (sh -c, bash -c)
    if _uses_shell_wrapper_normalized(normalized_lower):
        return True
    # Layer 7: interpreter code execution (python -c, node -e)
    # Use raw (non-lowered) text because -E is NOT code exec, only -c/-e/-p are
    if _uses_interpreter_code_exec_normalized(normalized_raw):
        return True
    # Layer 8: package managers + dangerous Python modules
    if _uses_package_manager_normalized(normalized_lower):
        return True
    if _uses_dangerous_python_module_normalized(normalized_lower):
        return True
    # Layer 9: command-composition utilities (xargs, find -exec, watch, parallel)
    if _uses_command_composition_normalized(normalized_lower):
        return True
    # Layer 10: destructive file-system commands (rm, rmdir, unlink, shred)
    if _uses_destructive_command_normalized(normalized_lower):
        return True
    # Layer 11: shell / interpreter execution paths that bypass Layer 6/7
    # (bash poc.sh, python3 poc.py, . poc.sh, source poc.sh)
    if _uses_shell_or_interpreter_execution_normalized(normalized_lower):
        return True
    # Layer 12: file-data movement (cp/mv) and process-signalling
    # (kill/pkill/killall) — Bridge R2 Finding: these flowed through the
    # Tier 3 shell executor unblocked.
    if _uses_copy_move_kill_normalized(normalized_lower):
        return True
    return False


def _build_diagnosis_prompt(
    result: dict[str, Any], wave_id: str, iteration: int,
    repo_root: Path,
) -> str:
    """Build a ~2K token diagnosis prompt for claude --print."""
    fc = result.get("failure_class", result.get("recovery", {}).get("failure_class", "unknown"))
    tier = result.get("tier", result.get("recovery", {}).get("tier", 3))
    step = result.get("step", "unknown")
    stderr = result.get("stderr", "")
    stdout = result.get("stdout", "")
    # Truncate to keep within token budget
    stderr_lines = stderr.strip().splitlines()[-100:]
    stdout_lines = stdout.strip().splitlines()[-50:]
    # Get git status
    try:
        git_proc = subprocess.run(
            ["git", "status", "--short"], cwd=repo_root,
            capture_output=True, text=True, timeout=10)
        git_status = git_proc.stdout[:500] if git_proc.returncode == 0 else "(unavailable)"
    except (subprocess.TimeoutExpired, OSError):
        git_status = "(unavailable)"

    return f"""You are a pipeline recovery agent. A pipeline step has failed and you must diagnose and fix it.

Failure class: {fc}
Tier: {tier}
Step: {step}
Iteration: {iteration + 1}/{MAX_RECOVERY_ITERATIONS}
Wave: {wave_id}

STDERR (last 100 lines):
{chr(10).join(stderr_lines)}

STDOUT (last 50 lines):
{chr(10).join(stdout_lines)}

Git status:
{git_status}

Do not run tools or shell commands yourself during this diagnosis turn.
Use only the evidence above, decide the smallest honest next action, and
return the JSON plan immediately.

Respond with ONLY a JSON object (no markdown, no explanation outside JSON):
{{"action": "shell"|"edit"|"skip"|"escalate", "commands": ["cmd1", "cmd2"], "explanation": "why"}}

- "shell": run shell commands to fix the issue
- "edit": apply file edits (commands = [{{"file_path": "...", "old_text": "...", "new_text": "..."}}])
- "skip": cannot fix, return failure
- "escalate": need human intervention

Safety: no rm -rf, no git push, no git reset --hard. Max 30s per command."""


def _terminate_process_tree(proc: Any) -> None:
    """Best-effort kill for a timed-out subprocess plus its descendants."""
    if proc is None:
        return
    pid = int(getattr(proc, "pid", 0) or 0)
    killed_group = False
    if pid > 0:
        try:
            os.killpg(pid, signal.SIGKILL)
            killed_group = True
        except OSError:
            killed_group = False
    if not killed_group:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.communicate(timeout=1)
    except TypeError:
        try:
            proc.communicate()
        except Exception:
            pass
    except Exception:
        pass


def _apply_edit(edit: dict[str, Any], repo_root: Path) -> tuple[bool, str]:
    """Apply a single file edit from the LLM response.

    Safety: file_path must resolve to within repo_root (no symlink escape).
    """
    raw_path = edit.get("file_path", "")
    file_path = (repo_root / raw_path).resolve()
    repo_resolved = repo_root.resolve()
    if not str(file_path).startswith(str(repo_resolved) + os.sep) and file_path != repo_resolved:
        return False, f"repo-escape blocked: {raw_path} resolves outside repo root"
    git_dir = repo_resolved / ".git"
    if str(file_path).startswith(str(git_dir) + os.sep) or file_path == git_dir:
        return False, f"sensitive-path blocked: {raw_path} targets .git/ internals"
    old_text = edit.get("old_text", "")
    new_text = edit.get("new_text", "")
    if not file_path.exists():
        return False, f"file not found: {file_path}"
    try:
        content = file_path.read_text(encoding="utf-8")
        if old_text not in content:
            return False, f"old_text not found in {file_path}"
        content = content.replace(old_text, new_text, 1)
        file_path.write_text(content, encoding="utf-8")
        return True, f"edited {file_path}"
    except OSError as exc:
        return False, f"edit failed: {exc}"


def _log_tier3_attempt(
    repo_root: Path, wave_id: str, step: str, failure_class: str,
    iteration: int, action: str, outcome: str, duration_s: float,
    detail: str = "", invocation_id: str = "",
) -> None:
    """Persist a single Tier 3 recovery iteration to recovery_log.json."""
    attempts = _load_recovery_log(repo_root)
    attempt = RecoveryAttempt(
        timestamp=datetime.now(timezone.utc).isoformat(),
        wave_id=wave_id, step=step, failure_class=failure_class, tier=3,
        action=f"tier3_iter{iteration}_{action}", outcome=outcome,
        duration_s=duration_s, tokens_used=0, detail=detail,
        invocation_id=invocation_id,
    )
    attempts.append(asdict(attempt))
    _save_recovery_log(repo_root, attempts)


def run_recovery_loop(
    repo_root: Path, result: dict[str, Any], wave_id: str,
    max_iterations: int = MAX_RECOVERY_ITERATIONS,
    verify_command: list[str] | None = None,
    invocation_id: str = "",
) -> dict[str, Any]:
    """Tier 3 LLM recovery loop: diagnose → fix → verify.

    Returns dict with: recovered, exhausted, iterations, log.
    All iterations are durably logged to recovery_log.json.
    """
    loop_log: list[dict[str, Any]] = []
    fc = result.get("failure_class", result.get("recovery", {}).get("failure_class", "unknown"))
    step = result.get("step") or result.get("executor", "unknown")
    failure_class = (
        FailureClass(fc)
        if fc in FailureClass._value2member_map_
        else FailureClass.UNKNOWN_ERROR
    )
    if not invocation_id:
        invocation_id = _new_invocation_id(wave_id, step, str(fc))
    current_status = _load_recovery_status(repo_root)
    if current_status.get("invocation_id") != invocation_id or not current_status.get("active"):
        attempts = _load_recovery_log(repo_root)
        _begin_recovery_status(
            repo_root,
            attempts=attempts,
            result=result,
            wave_id=wave_id,
            step=step,
            failure_class=failure_class,
            tier=3,
            prior_attempts=0,
            invocation_id=invocation_id,
        )
        _update_recovery_status(repo_root, max_iterations=max_iterations)

    for i in range(max_iterations):
        iteration_t0 = time.monotonic()
        prompt = _build_diagnosis_prompt(result, wave_id, i, repo_root)
        _update_recovery_status(
            repo_root,
            state="tier3_waiting_on_claude",
            current_iteration=i + 1,
            last_action="diagnose",
            child_pid=0,
            child_role="",
            current_command="claude --print",
            detail=_excerpt(_summarize_result_reason(result)),
        )

        # Call claude --print for diagnosis
        claude_proc = None
        try:
            claude_proc = subprocess.Popen(
                ["claude", "--print", "-p", prompt],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=repo_root,
                start_new_session=True,
            )
            _update_recovery_status(
                repo_root,
                child_pid=claude_proc.pid,
                child_role="claude",
            )
            stdout, _stderr = claude_proc.communicate(timeout=_CLAUDE_TIMEOUT)
            raw_response = stdout.strip()
        except subprocess.TimeoutExpired:
            _terminate_process_tree(claude_proc)
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "timeout",
                "detail": "claude --print timed out",
                "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "timeout", "failed", dur, "claude --print timed out",
                               invocation_id=invocation_id)
            _update_recovery_status(
                repo_root,
                state="tier3_timeout",
                child_pid=0,
                child_role="",
                current_command="",
                last_action="timeout",
                detail="claude --print timed out",
            )
            continue
        except OSError as exc:
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "error",
                "detail": f"claude invocation failed: {exc}",
                "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "error", "failed", dur, f"claude invocation failed: {exc}",
                               invocation_id=invocation_id)
            _update_recovery_status(
                repo_root,
                state="tier3_error",
                child_pid=0,
                child_role="",
                current_command="",
                last_action="error",
                detail=_excerpt(f"claude invocation failed: {exc}"),
            )
            continue

        # Parse JSON response
        try:
            # Strip markdown fences if present
            cleaned = raw_response
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                lines = [l for l in lines if not l.startswith("```")]
                cleaned = "\n".join(lines)
            response = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "parse_error",
                "detail": f"could not parse response: {raw_response[:200]}",
                "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "parse_error", "failed", dur,
                               f"could not parse response: {raw_response[:200]}",
                               invocation_id=invocation_id)
            _update_recovery_status(
                repo_root,
                state="tier3_parse_error",
                child_pid=0,
                child_role="",
                current_command="",
                last_action="parse_error",
                detail=_excerpt(raw_response[:200]),
            )
            continue

        action = response.get("action", "skip")
        commands = response.get("commands", [])
        explanation = response.get("explanation", "")
        _update_recovery_status(
            repo_root,
            child_pid=0,
            child_role="",
            current_command="",
            last_action=action,
            explanation=_excerpt(explanation),
            detail=_excerpt(explanation),
        )

        if action == "escalate":
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "escalate",
                "detail": explanation, "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "escalate", "escalated", dur, explanation,
                               invocation_id=invocation_id)
            _finish_recovery_status(
                repo_root,
                recovered=False,
                exhausted=True,
                outcome="escalated",
                action="escalate",
                detail=explanation,
                state="tier3_escalated",
            )
            return {"recovered": False, "exhausted": True,
                    "iterations": i + 1, "log": loop_log}

        if action == "skip":
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "skip",
                "detail": explanation, "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "skip", "skipped", dur, explanation,
                               invocation_id=invocation_id)
            _finish_recovery_status(
                repo_root,
                recovered=False,
                exhausted=False,
                outcome="skipped",
                action="skip",
                detail=explanation,
                state="tier3_skipped",
            )
            return {"recovered": False, "exhausted": False,
                    "iterations": i + 1, "log": loop_log}

        if action == "shell":
            cmd_results = []
            blocked = False
            executed = 0
            all_ok = True
            _update_recovery_status(
                repo_root,
                state="tier3_running_shell",
                current_command=_excerpt(commands[0] if commands else ""),
            )
            for cmd in commands:
                if not isinstance(cmd, str):
                    continue
                if _is_dangerous_command(cmd):
                    cmd_results.append(f"BLOCKED: {cmd}")
                    blocked = True
                    all_ok = False
                    continue
                if _targets_git_internals(cmd):
                    cmd_results.append(f"BLOCKED (sensitive path): {cmd}")
                    blocked = True
                    all_ok = False
                    continue
                try:
                    cmd_proc = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True,
                        timeout=_SHELL_TIMEOUT, cwd=repo_root)
                    executed += 1
                    if cmd_proc.returncode != 0:
                        all_ok = False
                    cmd_results.append(
                        f"exit={cmd_proc.returncode}: {cmd_proc.stdout[:200]}")
                except subprocess.TimeoutExpired:
                    all_ok = False
                    cmd_results.append(f"TIMEOUT: {cmd}")
                except OSError as exc:
                    all_ok = False
                    cmd_results.append(f"ERROR: {exc}")
            loop_log.append({
                "iteration": i + 1, "action": "shell",
                "commands": commands, "results": cmd_results,
                "blocked": blocked, "detail": explanation,
                "duration_s": round(time.monotonic() - iteration_t0, 3)})
            action_applied = executed > 0 and all_ok and not blocked

        elif action == "edit":
            edit_results = []
            edit_successes = 0
            edit_failures = 0
            _update_recovery_status(
                repo_root,
                state="tier3_applying_edit",
            )
            for edit in commands:
                if isinstance(edit, dict):
                    ok, msg = _apply_edit(edit, repo_root)
                    edit_results.append(msg)
                    if ok:
                        edit_successes += 1
                    else:
                        edit_failures += 1
            loop_log.append({
                "iteration": i + 1, "action": "edit",
                "results": edit_results, "detail": explanation,
                "duration_s": round(time.monotonic() - iteration_t0, 3)})
            action_applied = edit_successes > 0 and edit_failures == 0
        else:
            action_applied = False

        # Verify: re-run the failed gate/check if a verify command is provided
        if verify_command:
            try:
                _update_recovery_status(
                    repo_root,
                    state="tier3_verifying",
                    current_command=_excerpt(" ".join(verify_command)),
                )
                verify_proc = subprocess.run(
                    verify_command, capture_output=True, text=True,
                    timeout=_SHELL_TIMEOUT, cwd=repo_root)
                if verify_proc.returncode == 0:
                    dur = round(time.monotonic() - iteration_t0, 3)
                    loop_log.append({
                        "iteration": i + 1, "action": "verify_pass",
                        "detail": "verification passed"})
                    _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                                       action, "success", dur, "verification passed",
                                       invocation_id=invocation_id)
                    _finish_recovery_status(
                        repo_root,
                        recovered=True,
                        exhausted=False,
                        outcome="success",
                        action=action,
                        detail="verification passed",
                        state="tier3_verify_pass",
                    )
                    return {"recovered": True, "exhausted": False,
                            "iterations": i + 1, "log": loop_log}
                # Update result with new error for next iteration
                result = dict(result)
                result["stderr"] = verify_proc.stderr
                result["stdout"] = verify_proc.stdout
                _update_recovery_status(
                    repo_root,
                    state="tier3_verify_failed",
                    detail=_excerpt(_summarize_result_reason(result)),
                )
            except (subprocess.TimeoutExpired, OSError):
                pass
        elif action in {"shell", "edit"} and action_applied:
            dur = round(time.monotonic() - iteration_t0, 3)
            retry_target = _retry_target(result, step)
            detail = explanation or f"{action} applied; retrying {retry_target}"
            _log_tier3_attempt(
                repo_root, wave_id, step, fc, i + 1,
                action, "retry_requested", dur, detail,
                invocation_id=invocation_id,
            )
            _finish_recovery_status(
                repo_root,
                recovered=True,
                exhausted=False,
                outcome="retry_requested",
                action=action,
                detail=detail,
                state="tier3_retry_requested",
            )
            return {
                "recovered": True,
                "exhausted": False,
                "iterations": i + 1,
                "log": loop_log,
            }
        # Log iteration outcome (verify failed or no verify command)
        dur = round(time.monotonic() - iteration_t0, 3)
        _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                           action, "failed", dur, explanation,
                           invocation_id=invocation_id)

    _finish_recovery_status(
        repo_root,
        recovered=False,
        exhausted=True,
        outcome="exhausted",
        action="exhausted",
        detail=f"max {max_iterations} Tier 3 iterations exhausted",
        state="tier3_exhausted",
    )
    return {"recovered": False, "exhausted": True,
            "iterations": max_iterations, "log": loop_log}


# ---------------------------------------------------------------------------
# Recovery log
# ---------------------------------------------------------------------------

RECOVERY_LOG_DIR = Path(".agent_bus") / "recovery"
RECOVERY_LOG_FILE = RECOVERY_LOG_DIR / "recovery_log.json"
RECOVERY_STATUS_FILE = RECOVERY_LOG_DIR / "recovery_status.json"
MAX_LOG_ENTRIES = 500

# ---------------------------------------------------------------------------
# Learning store -- persistent pattern promotion/demotion (Tier B)
# Design doc: mu/docs/agents/PipelineRecovery.v0.md lines 156-251
# ---------------------------------------------------------------------------

LEARNED_PATTERNS_FILE = ".agent_bus/recovery/learned_patterns.json"
# Durable dead-letter directory for deferred syncs that could not acquire
# the main-repo lock within the finite flush timeout.  Each pending store
# snapshot is written as a uniquely-named JSON file so the write does NOT
# require the main-repo lock (per-file atomicity only).  The next successful
# _sync_to_main_repo drains these files under the lock, folding them into
# the merged output before the atomic rename, then deletes them.  This is
# the mechanism that satisfies the Tier B persistence contract (design doc
# line 172) when the in-memory _pending_main_repo_syncs list would otherwise
# die with the process — Bridge R9 re-entry Finding 1.
LEARNED_PATTERNS_INBOX_DIR = ".agent_bus/recovery/learned_patterns.inbox"
PROMOTION_THRESHOLD = 3        # success count required for promotion
PROMOTION_WAVE_THRESHOLD = 2   # distinct wave_ids required for promotion
DEMOTION_LOCK_THRESHOLD = 3    # permanent Tier 3 lock after this many demotions
EXPIRY_DAYS = 30               # pattern expiry (days since last success)
CLEANUP_DAYS = 90              # pattern cleanup (days since last update)
LOCK_TIMEOUT_S = 5             # max wait for main-repo file lock
FLUSH_LOCK_TIMEOUT_S = 30      # max wait for lock at process exit (atexit flush)
MIN_FINGERPRINT_LENGTH = 16    # minimum normalized fingerprint length for promotion

# Module-level state for deferred main-repo syncs (lock-timeout fallback).
# Best-effort in-memory retry between recovery events.  For at-exit
# durability (when the process cannot wait for the main-repo lock), see
# LEARNED_PATTERNS_INBOX_DIR and _inbox_write_snapshot().
_pending_main_repo_syncs: list[tuple[Path, dict]] = []


class LearnedMatch(NamedTuple):
    """Result from check_learned_patterns when a promoted pattern matches."""
    failure_class: FailureClass
    tier: int
    pattern_id: str
    action: str


def _normalize_fingerprint(raw: str) -> str:
    """Strip whitespace and collapse consecutive whitespace to single spaces.

    Applied at both observation (storage/hashing) and lookup (matching) time
    to ensure consistent fingerprint comparison.
    """
    return " ".join(raw.split())


def _extract_classifier_signal(result: dict[str, Any]) -> str:
    """Replicate classify_failure's signal extraction without classification.

    Extracts stderr, stdout, parses embedded JSON via _parse_json_object,
    extracts embedded_reason via _summarize_json_value, and returns combined
    text. This is the same processed signal that classify_failure() inspects
    at its combined_text variable (lines 122-124).
    """
    try:
        stderr = result.get("stderr", "")
        stdout = result.get("stdout", "")
        embedded_stdout = _parse_json_object(stdout)
        embedded_stderr = _parse_json_object(stderr)
        embedded_reason = " ".join(
            part
            for part in (
                _summarize_json_value(embedded_stdout),
                _summarize_json_value(embedded_stderr),
            )
            if part
        )
        combined_text = " ".join(
            part for part in (stderr, stdout, embedded_reason)
            if isinstance(part, str) and part
        )
        return combined_text
    except Exception:
        return result.get("stderr", "")


def _has_avx_support() -> bool:
    """Check if the CPU supports AVX instructions.

    Returns True on non-x86 platforms (AVX is x86-specific).
    """
    import platform
    machine = platform.machine().lower()
    if machine not in ("x86_64", "amd64", "i386", "i686"):
        return True  # non-x86, AVX not applicable
    if sys.platform == "linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
            return "avx" in cpuinfo.lower()
        except OSError:
            return True  # can't check, assume present
    if sys.platform == "darwin":
        try:
            proc = subprocess.run(
                ["sysctl", "-n", "hw.optional.avx1_0"],
                capture_output=True, text=True, timeout=5)
            return proc.stdout.strip() == "1"
        except (subprocess.TimeoutExpired, OSError):
            return True  # can't check, assume present
    return True  # unknown platform, assume present


def _environment_tags() -> list[str]:
    """Capture the current machine's environment context.

    Returns a sorted list of tags: [sys.platform] plus optional capability
    tags ("no-avx", "no-claude-cli") per design doc lines 288-294.
    """
    try:
        tags = [sys.platform]
        if not _has_avx_support():
            tags.append("no-avx")
        if shutil.which("claude") is None:
            tags.append("no-claude-cli")
        return sorted(tags)
    except Exception:
        return [sys.platform]


def _environment_matches(pattern_tags: list[str] | None) -> bool:
    """Check if the current environment matches a pattern's recorded tags.

    Returns True if pattern_tags is empty/None (backwards compatibility).
    Returns True on exact set equality with current _environment_tags().
    Fail-closed: returns False on any exception.
    """
    try:
        if not pattern_tags:
            return True  # backwards compat: pre-environment patterns are universal
        current = _environment_tags()
        return sorted(pattern_tags) == sorted(current)
    except Exception:
        return False


def _resolve_main_repo_root(repo_root: Path) -> Path:
    """Return the main repo root for merge-on-sync persistence.

    Uses git rev-parse --git-common-dir to find the common git dir.
    If repo_root is already the main repo, returns repo_root unchanged.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse",
             "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return repo_root
        common_dir = Path(proc.stdout.strip())
        # The main repo working tree is the parent of .git
        main_root = common_dir.parent
        if main_root == repo_root:
            return repo_root  # already main repo
        if main_root.is_dir():
            return main_root
        return repo_root
    except (subprocess.TimeoutExpired, OSError):
        return repo_root


def _merge_stores(base: dict, incoming: dict) -> dict:
    """Pure-function union merge per design doc line 251.

    All pattern_ids from both inputs are unioned. Same-id conflicts use
    per-field merge:

    - When both records share the same ``environment_tags`` (or either is
      empty for backwards compatibility), higher ``success_count`` wins
      and ties are broken by more recent ``updated_at``.  This is the
      same-environment cross-worktree case — pooling evidence is safe.

    - When the two records have DIFFERENT non-empty ``environment_tags``,
      the more recent ``updated_at`` wins regardless of ``success_count``.
      Environment change is a counter-reset event (design doc lifecycle
      diagram lines 210–214: "different machine" / "env change" → "Reset
      counter"), so the latest observation represents the pattern's
      current era.  Using ``success_count`` as the tiebreaker would
      resurrect the stale old-environment snapshot with its (higher)
      pre-reset counter and silently drop the reset that
      ``observe_outcome`` just performed (Bridge R1 Finding 3).

    ``distinct_wave_ids`` is set-unioned only when both records share the
    same environment_tags; when environments differ, it is taken from the
    winning record only (no cross-environment union).
    """
    base_patterns = base.get("patterns", {})
    incoming_patterns = incoming.get("patterns", {})
    merged_patterns: dict[str, dict] = {}

    all_ids = set(base_patterns.keys()) | set(incoming_patterns.keys())
    for pid in all_ids:
        b_rec = base_patterns.get(pid)
        i_rec = incoming_patterns.get(pid)
        if b_rec is None:
            merged_patterns[pid] = dict(i_rec)
            continue
        if i_rec is None:
            merged_patterns[pid] = dict(b_rec)
            continue
        # Both exist — per-field merge.
        b_sc = b_rec.get("success_count", 0)
        i_sc = i_rec.get("success_count", 0)
        b_env = b_rec.get("environment_tags", []) or []
        i_env = i_rec.get("environment_tags", []) or []
        # "Environments match" covers exact equality plus the backwards
        # compat case where either side predates environment tagging.
        envs_match_or_empty = (
            sorted(b_env) == sorted(i_env) or not b_env or not i_env
        )
        if not envs_match_or_empty:
            # Cross-environment conflict — updated_at is the authoritative
            # "era" marker.  Deterministic tiebreak on equal timestamps:
            # incoming wins (treat incoming as the newer-arriving writer).
            b_ts = b_rec.get("updated_at", "")
            i_ts = i_rec.get("updated_at", "")
            if i_ts > b_ts:
                winner, loser = i_rec, b_rec
            elif b_ts > i_ts:
                winner, loser = b_rec, i_rec
            else:
                winner, loser = i_rec, b_rec
        elif b_sc > i_sc:
            winner, loser = b_rec, i_rec
        elif i_sc > b_sc:
            winner, loser = i_rec, b_rec
        else:
            # Same-environment tie: break by more recent updated_at.
            b_ts = b_rec.get("updated_at", "")
            i_ts = i_rec.get("updated_at", "")
            if i_ts > b_ts:
                winner, loser = i_rec, b_rec
            else:
                winner, loser = b_rec, i_rec
        merged_rec = dict(winner)
        # Safety ratchet fields: always take the strictest value from
        # BOTH records to prevent a stale high-success snapshot from
        # resurrecting a demoted or permanently-locked pattern.
        merged_demotion = max(
            winner.get("demotion_count", 0),
            loser.get("demotion_count", 0),
        )
        merged_locked = (
            winner.get("permanently_locked", False)
            or loser.get("permanently_locked", False)
        )
        merged_rec["demotion_count"] = merged_demotion
        merged_rec["permanently_locked"] = merged_locked
        if merged_locked:
            merged_rec["promoted_tier"] = 3
        elif merged_demotion > 0:
            # Demotion ratchet: when either record has demotion history,
            # take the worst (highest-numbered / most-demoted) tier to
            # prevent a stale high-success snapshot from resurrecting a
            # demoted pattern back to a lower tier number.
            w_tier = winner.get("promoted_tier")
            l_tier = loser.get("promoted_tier")
            # Treat None as "not promoted" (no tier to ratchet)
            if w_tier is not None and l_tier is not None:
                merged_rec["promoted_tier"] = max(w_tier, l_tier)
            elif l_tier is not None:
                merged_rec["promoted_tier"] = l_tier
            # else: winner's tier stands (loser has no tier)
        # distinct_wave_ids merge is environment-aware
        w_env = winner.get("environment_tags", [])
        l_env = loser.get("environment_tags", [])
        w_waves = winner.get("distinct_wave_ids", [])
        l_waves = loser.get("distinct_wave_ids", [])
        if sorted(w_env) == sorted(l_env) or not w_env or not l_env:
            # Same environment (or backwards-compat empty): set-union
            merged_rec["distinct_wave_ids"] = sorted(
                set(w_waves) | set(l_waves)
            )
        else:
            # Different environments: take winner's only
            merged_rec["distinct_wave_ids"] = list(w_waves)
        merged_patterns[pid] = merged_rec

    # Metadata: use more recent last_modified
    base_meta = base.get("metadata", {})
    incoming_meta = incoming.get("metadata", {})
    if incoming_meta.get("last_modified", "") > base_meta.get("last_modified", ""):
        merged_meta = dict(incoming_meta)
    else:
        merged_meta = dict(base_meta)

    return {"patterns": merged_patterns, "metadata": merged_meta}


def _overlay_ratchet_record(base: dict, incoming: dict) -> dict:
    """Overlay ``incoming`` record on top of ``base`` with a safety ratchet.

    Same-repo overlay semantics: the incoming (caller's authoritative)
    snapshot wins for normal scalar fields such as ``action``,
    ``success_count``, ``failure_count``, ``last_success``, and
    ``updated_at``.  However, the monotonically-growing safety triad —
    ``demotion_count``, ``permanently_locked``, and (conditionally)
    ``promoted_tier`` — must survive stale concurrent writers.

    Field-level rules:

    - ``demotion_count``: always ``max(base, incoming)``.  ``dc`` is
      append-only in the live code (``observe_outcome`` only
      increments it); any decrease in the incoming view is stale.

    - ``permanently_locked``: always ``base OR incoming``.  Once a
      pattern is permanently locked, no stale writer may unlock it.

    - ``promoted_tier``: tricky.  Unlike ``dc`` and ``locked``, tier is
      NOT monotonic — ``observe_outcome`` legitimately re-promotes a
      demoted pattern back to tier 1 after enough fresh successes, and
      legitimately demotes it back later.  Unconditional ``max`` would
      freeze the tier at the worst value ever seen and block every
      re-promotion, which breaks the live failure-recovery loop.

      We only pin the tier when the caller's view is provably stale on
      demotion state — i.e. when ``incoming.dc < base.dc``.  Because
      ``dc`` is append-only, this inequality uniquely identifies a
      writer that failed to observe a demotion already on disk.  For
      ``incoming.dc == base.dc`` (same demotion view, legitimate
      re-promotion or concurrent writer that agrees) and for
      ``incoming.dc > base.dc`` (caller is demoting further, strictly
      ahead of disk), the caller's tier is authoritative.

      When the merged record ends up ``permanently_locked``, the tier
      is forced to 3 regardless of staleness — a locked pattern must
      not be addressable.

    Reason: repairs Bridge R5 Finding 12 / R9 re-entry Finding 1 (same
    ``pattern_id`` stale concurrent overlay erasing a recorded
    demotion) without regressing ``observe_outcome``'s single-writer
    re-promotion loop, which the earlier unconditional-``max`` ratchet
    broke (see ``test_permanent_lock_after_3_demotions``).  The
    cross-worktree ``_merge_stores`` path uses a different policy (it
    has environment tags and an updated_at tie-break and is re-entered
    only on linked-worktree sync) — do not conflate the two.
    """
    merged = dict(incoming)
    base_dc = base.get("demotion_count", 0)
    incoming_dc = incoming.get("demotion_count", 0)
    merged_dem = max(base_dc, incoming_dc)
    merged_locked = (
        base.get("permanently_locked", False)
        or incoming.get("permanently_locked", False)
    )
    merged["demotion_count"] = merged_dem
    merged["permanently_locked"] = merged_locked
    # distinct_wave_ids: environment-aware merge, mirroring
    # ``_merge_stores`` semantics exactly.
    #
    # - Same environment (or either side empty for backwards compat):
    #   set-union, so concurrent same-pattern writers with different
    #   wave attributions each contribute to the cumulative set.
    #   Without this union, the later overlay save drops the prior
    #   writer's wave evidence (Bridge R8 Finding 2: same-repo
    #   overlay merge drops same-ID success and wave evidence under
    #   stale concurrent writers).
    #
    # - Different non-empty environments: take ``incoming`` only
    #   (already set by ``merged = dict(incoming)`` above).  This is
    #   the counter-reset path — ``observe_outcome`` resets the
    #   pattern when the environment changes (see
    #   ``test_environment_change_resets_counters``), so the base
    #   record on disk is from a prior "era" whose wave attributions
    #   do NOT carry forward.  Unconditional union would resurrect
    #   the stale old-environment wave list and silently invert the
    #   reset.
    base_env = base.get("environment_tags", []) or []
    incoming_env = incoming.get("environment_tags", []) or []
    envs_match_or_empty = (
        sorted(base_env) == sorted(incoming_env) or not base_env or not incoming_env
    )
    if envs_match_or_empty:
        base_waves = base.get("distinct_wave_ids", []) or []
        incoming_waves = incoming.get("distinct_wave_ids", []) or []
        merged["distinct_wave_ids"] = sorted(set(base_waves) | set(incoming_waves))
    # else: merged["distinct_wave_ids"] already holds incoming's list
    # from the ``merged = dict(incoming)`` at the top of the function.
    if merged_locked:
        # Locked pattern: force lowest (strictest) tier so it never
        # exits the permanently_locked state via a stale caller.
        merged["promoted_tier"] = 3
    elif incoming_dc < base_dc:
        # Stale-writer detection: caller observed a dc lower than disk,
        # which is only possible if they missed a demotion already
        # recorded.  Treat their tier as untrusted and keep the
        # on-disk tier to prevent resurrection.  Treat None as "no
        # tier to ratchet".
        b_tier = base.get("promoted_tier")
        if b_tier is not None:
            merged["promoted_tier"] = b_tier
        # else: base has no tier — incoming's tier (already in merged)
        # stands; there's nothing to ratchet against.
    # else: incoming_dc >= base_dc — caller saw at least as many
    # demotions as disk, so their tier change (either demoting further
    # or re-promoting after enough successes) is authoritative and the
    # incoming tier (already in merged) stands unchanged.
    return merged


def _validate_pattern_record(record: dict) -> bool:
    """Check that a pattern record has required fields."""
    if not isinstance(record, dict):
        return False
    if not isinstance(record.get("pattern_id"), str):
        return False
    if not isinstance(record.get("fingerprint"), str):
        return False
    if not isinstance(record.get("failure_class"), str):
        return False
    return True


def _empty_store() -> dict:
    """Return an empty learning store with metadata."""
    return {
        "patterns": {},
        "metadata": {"last_modified": datetime.now(timezone.utc).isoformat()},
    }


def _load_learning_store(repo_root: Path) -> dict:
    """Load learned_patterns.json with merge-on-sync from main repo.

    Reads worktree copy, and if in a linked worktree also reads the main
    repo copy, merging via _merge_stores(). Returns empty store on any error.
    """
    def _read_store(path: Path) -> dict | None:
        try:
            if not path.exists():
                return None
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            if not isinstance(data.get("patterns"), dict):
                return None
            # Validate and filter individual records
            valid_patterns = {}
            for pid, rec in data["patterns"].items():
                if not _validate_pattern_record(rec):
                    continue
                # Defaults for backwards compatibility
                if "environment_tags" not in rec:
                    rec["environment_tags"] = []
                if "distinct_wave_ids" not in rec:
                    rec["distinct_wave_ids"] = []
                valid_patterns[pid] = rec
            data["patterns"] = valid_patterns
            if "metadata" not in data:
                data["metadata"] = {"last_modified": ""}
            return data
        except (json.JSONDecodeError, ValueError, KeyError, OSError) as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to read learning store at %s: %s", path, exc)
            return None

    worktree_path = repo_root / LEARNED_PATTERNS_FILE
    worktree_store = _read_store(worktree_path)

    main_root = _resolve_main_repo_root(repo_root)
    main_store = None
    if main_root != repo_root:
        main_path = main_root / LEARNED_PATTERNS_FILE
        main_store = _read_store(main_path)

    if worktree_store is None and main_store is None:
        return _empty_store()
    if worktree_store is None:
        return main_store  # type: ignore[return-value]
    if main_store is None:
        return worktree_store
    return _merge_stores(worktree_store, main_store)


def _save_learning_store(repo_root: Path, store: dict) -> None:
    """Write learned_patterns.json with merge-on-sync to main repo.

    Uses atomic temp-file-plus-os.rename(). Main repo write is serialized
    via fcntl.flock(). On lock timeout, defers sync to _pending_main_repo_syncs.

    Durability contract (Bridge Round 1 Finding — same-repo lock-timeout
    in-memory-only loss window).  When the caller is operating directly
    on the main repo (``main_root == repo_root``) there is no separate
    worktree copy to serve as a durable fallback, so a failed
    ``_sync_to_main_repo`` (lock-open failure, lock acquisition timeout,
    or mid-critical-section OSError) would leave the snapshot only in
    the in-memory ``_pending_main_repo_syncs`` list.  That list dies
    with the process on crash/SIGKILL before the ``atexit`` flush
    runs, silently losing the learned pattern and violating the
    Tier B persistence contract (design doc line 172: "synced to main
    repo before worktree teardown").

    Fix: on the same-repo path, whenever the normal sync fails, write
    a durable dead-letter inbox snapshot via ``_inbox_write_snapshot``.
    The inbox file is a uniquely-named JSON blob under
    ``LEARNED_PATTERNS_INBOX_DIR`` and requires NO main-repo lock (each
    file is independent, collision-free via ``uuid4()``), so the
    fallback cannot itself deadlock on the lock-timeout path.  The
    next successful ``_sync_to_main_repo`` from any process drains the
    inbox under the lock, folds every snapshot into the merged output
    via ``_overlay_ratchet_record`` (which is idempotent when the
    inbox snapshot and the caller store contain the same record), and
    deletes the drained files after the atomic rename.  A process
    crash between the inbox write and the next sync leaves the
    snapshot durably on disk for the following process to recover.

    The linked-worktree branch (``main_root != repo_root``) already
    writes the worktree copy atomically BEFORE calling
    ``_sync_to_main_repo``, so that worktree copy is the durable
    fallback — no inbox pre-write is required on that branch.  Adding
    one would be redundant because the worktree path is a
    per-worktree single-writer file that cannot race and is already
    recoverable via the next load/sync cycle.
    """
    global _pending_main_repo_syncs
    store.setdefault("metadata", {})["last_modified"] = datetime.now(timezone.utc).isoformat()

    def _atomic_write(path: Path, data: dict) -> None:
        os.makedirs(path.parent, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.rename(str(tmp_path), str(path))

    # Determine main repo root before any writes — needed to decide
    # whether the worktree path IS the shared main path.
    main_root = _resolve_main_repo_root(repo_root)

    if main_root != repo_root:
        # Linked worktree: write local copy (single-writer safe), then
        # sync to main repo with lock-serialized read-merge-write.
        try:
            worktree_path = repo_root / LEARNED_PATTERNS_FILE
            _atomic_write(worktree_path, store)
        except OSError as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to write learning store (worktree): %s", exc)
            return

    # Sync to main repo (or same repo) with lock-serialized write.
    # For linked worktrees: full _merge_stores so cross-worktree patterns are
    # preserved with conflict resolution (higher success_count wins).
    # For same-repo: overlay merge — incoming patterns overwrite same-ID
    # existing patterns (the caller's modifications are authoritative), but
    # patterns only in existing (from concurrent writers) are preserved.
    # Full _merge_stores would be wrong here: it picks the record with higher
    # success_count, which undoes intentional resets (e.g., env-change counter
    # reset in observe_outcome where success_count drops from 2 to 1).
    overlay = (main_root == repo_root)
    synced = _sync_to_main_repo(
        main_root, store, blocking=False, overlay=overlay,
    )

    # Same-repo durability fallback: the normal sync deferred (lock
    # timeout / open failure / mid-critical-section OSError) and there
    # is no worktree-side copy on this branch, so the only remaining
    # copy would be ``_pending_main_repo_syncs`` — which is in-memory
    # only.  Write a durable dead-letter inbox snapshot now so a crash
    # before the next sync or the ``atexit`` flush cannot lose the
    # observation.  The inbox write is best-effort: if it also fails
    # (e.g., directory unwriteable) the learning store gracefully
    # degrades to best-effort in-memory retry — recovery is
    # non-load-bearing and must never crash the pipeline.
    if not synced and main_root == repo_root:
        _inbox_write_snapshot(main_root, store)


# ---------------------------------------------------------------------------
# Durable dead-letter inbox (Bridge R9 re-entry Finding 1)
# ---------------------------------------------------------------------------
# Problem: ``_flush_pending_syncs`` is the at-process-exit last-resort sync.
# If the main-repo lock is held past ``FLUSH_LOCK_TIMEOUT_S``, the previous
# design re-enqueued the pending store to the in-memory
# ``_pending_main_repo_syncs`` list and returned.  The process then exited
# with the list still populated, so the Tier B learned patterns were never
# persisted to disk — the data died with the process despite having a
# perfectly good worktree copy in scope at flush time.  This broke the
# Tier B persistence contract (design doc line 172: "synced to main repo
# before worktree teardown").
#
# Fix: a durable on-disk dead-letter inbox.  When the flush-path lock
# attempt fails, each pending store snapshot is written as a uniquely-named
# JSON file in ``{main_root}/.agent_bus/recovery/learned_patterns.inbox/``.
# Writing a uniquely-named file does NOT require the main-repo lock (each
# file is independent), so the inbox write cannot deadlock and is atomic
# via temp-file-plus-``os.rename()``.  The next successful
# ``_sync_to_main_repo`` call — from any process in any worktree — drains
# the inbox under the lock, folds every snapshot into the merged output
# before the atomic rename, then deletes the drained inbox files.  Data is
# durably on disk between flush and the next sync, so a process exit after
# flush-timeout does not lose learned patterns.

def _inbox_dir(main_root: Path) -> Path:
    """Return the dead-letter inbox directory under ``main_root``."""
    return main_root / LEARNED_PATTERNS_INBOX_DIR


def _inbox_write_snapshot(main_root: Path, store: dict) -> bool:
    """Atomically write ``store`` as a uniquely-named inbox snapshot file.

    No lock required: each call produces a unique filename via ``uuid4()``,
    so concurrent writers cannot collide.  The write is atomic (temp-file
    plus ``os.rename()``) so a crash mid-write cannot leave a truncated
    snapshot for the drain path to choke on.

    Returns True on success, False on OSError.  Caller should treat failure
    as a best-effort degradation — the learning store cannot crash the
    recovery path.
    """
    try:
        inbox = _inbox_dir(main_root)
        os.makedirs(str(inbox), exist_ok=True)
        # Monotonic-ish prefix for drain ordering + uuid4 for uniqueness.
        # Use perf_counter_ns for tight ordering across multiple deferrals
        # in the same process; uuid4 keeps cross-process collisions away.
        name = f"{time.time_ns():020d}-{uuid.uuid4().hex}.json"
        final_path = inbox / name
        tmp_path = inbox / f".{name}.tmp"
        tmp_path.write_text(
            json.dumps(store, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.rename(str(tmp_path), str(final_path))
        return True
    except (OSError, TypeError, ValueError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to write learning-store inbox snapshot at %s: %s",
            main_root, exc)
        return False


def _inbox_read_snapshots(main_root: Path) -> list[tuple[Path, dict]]:
    """Read all inbox snapshot files for ``main_root``.

    Returns a list of ``(path, store)`` tuples.  Files that are corrupt,
    truncated, partially-written, or have unexpected schema are skipped —
    the drain path must never crash the sync.  Caller is responsible for
    deleting the files after the merged output has been successfully
    written.

    Ordered by filename (which embeds ``time.time_ns()``) so older
    snapshots are merged first — the per-field merge in ``_merge_stores``
    is associative, but ordering gives deterministic behavior on equal
    timestamps.
    """
    inbox = _inbox_dir(main_root)
    try:
        if not inbox.is_dir():
            return []
        entries = sorted(inbox.iterdir(), key=lambda p: p.name)
    except OSError:
        return []

    snapshots: list[tuple[Path, dict]] = []
    for path in entries:
        # Skip the in-flight temp files from atomic writes.
        name = path.name
        if name.startswith(".") or not name.endswith(".json"):
            continue
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError, ValueError):
            # Truncated or not-yet-complete write — skip this cycle;
            # the next drain will retry.  Do NOT delete: the file may
            # still be in the middle of an atomic rename from another
            # process.
            continue
        if not isinstance(data, dict) or not isinstance(
            data.get("patterns"), dict
        ):
            # Malformed — the file is valid JSON but not a store shape.
            # Delete so it doesn't re-poison every subsequent drain.
            try:
                path.unlink()
            except OSError:
                pass
            continue
        snapshots.append((path, data))
    return snapshots


def _inbox_delete_snapshots(paths: list[Path]) -> None:
    """Delete a batch of inbox snapshot files after successful drain.

    Tolerates concurrent deletion (another drain may have already removed
    the file) and other per-file errors — the goal is best-effort cleanup.
    Orphaned inbox files are harmless: they will be re-merged on the next
    drain and eventually cleaned up then.
    """
    for path in paths:
        try:
            path.unlink()
        except OSError:
            pass


def _sync_to_main_repo(
    main_root: Path, store: dict, *, blocking: bool = False,
    overlay: bool = False,
) -> bool:
    """Sync learning store to main repo with file-lock serialization.

    When overlay=False (default, for cross-worktree sync), uses full
    _merge_stores with conflict resolution.  When overlay=True (for
    same-repo sync), incoming patterns overwrite same-ID existing patterns
    while preserving patterns only in the existing store.

    Returns True on success, False on failure/timeout.
    """
    global _pending_main_repo_syncs
    main_path = main_root / LEARNED_PATTERNS_FILE
    lock_path = Path(str(main_path) + ".lock")

    try:
        os.makedirs(main_path.parent, exist_ok=True)
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to open lockfile %s: %s", lock_path, exc)
        _pending_main_repo_syncs.append((main_root, dict(store)))
        return False

    acquired = False
    try:
        if blocking:
            # Use a finite timeout even for "blocking" calls to prevent
            # indefinite hangs at process exit (Bridge R3 Finding 3).
            deadline = time.monotonic() + FLUSH_LOCK_TIMEOUT_S
            while time.monotonic() < deadline:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (IOError, OSError):
                    time.sleep(0.1)
        else:
            # Non-blocking retry loop with timeout
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            while time.monotonic() < deadline:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (IOError, OSError):
                    time.sleep(0.1)

        if not acquired:
            import logging
            timeout_used = FLUSH_LOCK_TIMEOUT_S if blocking else LOCK_TIMEOUT_S
            logging.getLogger(__name__).warning(
                "Lock timeout (%ds) for main-repo sync at %s; deferring",
                timeout_used, main_path)
            _pending_main_repo_syncs.append((main_root, dict(store)))
            return False

        # Read current main repo copy, merge, write
        existing = None
        try:
            if main_path.exists():
                raw = main_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, dict) and isinstance(data.get("patterns"), dict):
                    existing = data
        except (json.JSONDecodeError, ValueError, OSError):
            existing = None

        # Drain pending snapshots for this main_root BEFORE computing the
        # merged output.  Bridge R4 Finding 2: previously the pending list
        # was filtered post-write without being applied, so a same-repo
        # save that timed out and appended a snapshot to
        # ``_pending_main_repo_syncs`` would have that snapshot silently
        # dropped on the next successful save — any patterns unique to
        # the deferred snapshot (not present in the caller's later
        # ``store``) were permanently lost.  Folding the pending
        # snapshots in here ensures the post-write filter is honest: it
        # only removes entries that are actually represented in the
        # merged output that just went to disk.
        pending_for_root = [
            (r, s) for r, s in _pending_main_repo_syncs
            if r == main_root
        ]

        # Drain the durable dead-letter inbox for this main_root.  Any
        # snapshots that a previous flush-path lock timeout pushed to
        # disk (Bridge R9 re-entry Finding 1) are folded into the merged
        # output alongside the in-memory pending entries.  We read them
        # BEFORE the merge and delete them AFTER the atomic rename — if
        # the write fails, the files stay on disk and the next drain
        # retries.  Ordered by filename (monotonic ns prefix) so
        # deterministic on equal-timestamp conflicts.
        inbox_snapshots = _inbox_read_snapshots(main_root)

        if overlay:
            # Same-repo overlay order (oldest → newest): inbox snapshots
            # (durable carry-over from previous flush timeouts) are the
            # oldest, then in-memory pending snapshots (deferred from
            # earlier saves in THIS process), then any on-disk state
            # from concurrent/prior successful writes, and finally the
            # caller's current ``store`` — the authoritative latest
            # snapshot, which wins on pattern_id conflicts for scalar
            # fields (action, counters, timestamps).
            #
            # Safety ratchet (Bridge R5 Finding 12 / R9 re-entry
            # Finding 1): for every same-ID conflict we pass the pair
            # through ``_overlay_ratchet_record`` so that
            # ``demotion_count``, ``permanently_locked``, and
            # ``promoted_tier`` take the strictest value across both
            # sides.  Without this ratchet, a stale writer running
            # after an earlier demotion or permanent lock would
            # overwrite those fields via ``dict.update`` and resurrect
            # the pattern to a higher-trust tier — exactly the defect
            # reproduced by the Phase B R9 re-entry repro script.
            merged_patterns: dict[str, Any] = {}
            sources: list[dict[str, Any]] = []
            for _ipath, inbox_store in inbox_snapshots:
                sources.append(inbox_store.get("patterns", {}))
            for _r, pending_store in pending_for_root:
                sources.append(pending_store.get("patterns", {}))
            if existing is not None:
                sources.append(existing.get("patterns", {}))
            sources.append(store.get("patterns", {}))
            for source in sources:
                for pid, rec in source.items():
                    if pid in merged_patterns:
                        merged_patterns[pid] = _overlay_ratchet_record(
                            merged_patterns[pid], rec,
                        )
                    else:
                        merged_patterns[pid] = dict(rec)
            fallback_meta = (
                existing.get("metadata", {}) if existing is not None else {}
            )
            merged = {
                "patterns": merged_patterns,
                "metadata": store.get("metadata", fallback_meta),
            }
        else:
            # Cross-worktree: full field-level union via _merge_stores.
            # Associative, so fold-left over (existing, store, *pending,
            # *inbox) produces a deterministic merged result regardless
            # of insertion order.
            if existing is not None:
                merged = _merge_stores(existing, store)
            else:
                merged = dict(store)
            for _r, pending_store in pending_for_root:
                merged = _merge_stores(merged, pending_store)
            for _ipath, inbox_store in inbox_snapshots:
                merged = _merge_stores(merged, inbox_store)

        merged.setdefault("metadata", {})["last_modified"] = (
            datetime.now(timezone.utc).isoformat()
        )

        # Atomic write
        tmp_path = main_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(merged, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.rename(str(tmp_path), str(main_path))

        # Atomic rename succeeded — NOW it is safe to delete the inbox
        # files we folded in.  If deletion fails for some entries, they
        # will be re-merged harmlessly on the next drain.
        _inbox_delete_snapshots([p for p, _s in inbox_snapshots])

        # Successful sync — remove the pending entries we just absorbed
        # into the merged output.  Safe now because ``pending_for_root``
        # was folded into ``merged`` above; post-write filter no longer
        # silently discards data.
        _pending_main_repo_syncs = [
            (r, s) for r, s in _pending_main_repo_syncs
            if r != main_root
        ]
        return True

    except OSError as exc:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to sync learning store to main repo: %s", exc)
        if not blocking:
            _pending_main_repo_syncs.append((main_root, dict(store)))
        return False
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            os.close(lock_fd)
        except OSError:
            pass


def _flush_pending_syncs() -> None:
    """Drain _pending_main_repo_syncs at process exit (atexit handler).

    Pre-merges all deferred stores for the same main_root before syncing
    once per root. This prevents earlier entries from being dropped when
    _sync_to_main_repo removes all matching entries on success.

    Uses a bounded blocking lock (``FLUSH_LOCK_TIMEOUT_S``) to prevent
    indefinite hangs at process exit (Bridge R3 Finding 3).  When the
    lock cannot be acquired within that bound, the deferred store is
    written to the durable dead-letter inbox
    (``LEARNED_PATTERNS_INBOX_DIR``) via ``_inbox_write_snapshot`` — the
    next successful ``_sync_to_main_repo`` call from any process drains
    the inbox under the lock and folds every snapshot into the merged
    output before the atomic rename.  This is what satisfies the Tier B
    persistence contract (design doc line 172) when the in-memory
    ``_pending_main_repo_syncs`` list would otherwise die with the
    process — Bridge R9 re-entry Finding 1.
    """
    global _pending_main_repo_syncs
    try:
        # Group and pre-merge all pending stores by main_root so a single
        # sync per root contains all deferred patterns.
        grouped: dict[str, tuple[Path, dict]] = {}
        for main_root, store in _pending_main_repo_syncs:
            key = str(main_root)
            if key in grouped:
                _, existing = grouped[key]
                grouped[key] = (main_root, _merge_stores(existing, store))
            else:
                grouped[key] = (main_root, dict(store))

        # Clear the pending list before syncing — _sync_to_main_repo will
        # not find (or remove) stale entries.
        _pending_main_repo_syncs = []

        for _key, (main_root, merged_store) in grouped.items():
            if _sync_to_main_repo(
                main_root, merged_store, blocking=True,
            ):
                continue
            # Sync failed (lock timeout or OSError).  ``_sync_to_main_repo``
            # may have re-appended this main_root's store to
            # ``_pending_main_repo_syncs`` on the lock-timeout path — that
            # re-enqueue is an in-memory best-effort that dies with the
            # process and does NOT satisfy the Tier B persistence
            # contract.  Durably persist to the dead-letter inbox so the
            # next successful ``_sync_to_main_repo`` (from any process in
            # any worktree) merges the snapshot into the main repo store.
            if _inbox_write_snapshot(main_root, merged_store):
                # The on-disk copy is the durable source of truth now.
                # Remove any in-memory re-enqueue ``_sync_to_main_repo``
                # just added for this root — keeping both would double-
                # merge the same data on the next sync (harmless but
                # wasteful) and would also cause the subsequent re-flush
                # to re-write an already-persisted snapshot.
                _pending_main_repo_syncs = [
                    (r, s) for r, s in _pending_main_repo_syncs
                    if r != main_root
                ]
            else:
                # Inbox write also failed — best-effort degradation, keep
                # the in-memory re-enqueue (if any) so a later in-process
                # event can retry.  Do NOT raise: the learning store is
                # a best-effort optimization layer, not a load-bearing
                # dependency.  If the re-enqueue was not performed by
                # ``_sync_to_main_repo`` (OSError path with
                # ``blocking=True``), re-append here ourselves so the
                # flush-side guarantee "nothing silently vanishes"
                # still holds.
                already_enqueued = any(
                    r == main_root for r, _s in _pending_main_repo_syncs
                )
                if not already_enqueued:
                    _pending_main_repo_syncs.append(
                        (main_root, merged_store),
                    )
    except Exception:
        pass  # Never mask other exit behavior


atexit.register(_flush_pending_syncs)


# ---------------------------------------------------------------------------
# Cross-pollination: learning.md ↔ learning store
# ---------------------------------------------------------------------------

LEARNING_MD_REL = Path(".claude") / "rules" / "learning.md"


def _escape_backtick_field(s: str) -> str:
    """Escape backticks and backslashes for backtick-delimited wire format.

    Used by _export_to_learning_md (write path) and should be used when
    authoring FIXED entries with backtick-bearing fingerprints or actions.
    Order matters: escape backslashes first, then backticks.
    """
    return s.replace("\\", "\\\\").replace("`", "\\`")


def _unescape_backtick_field(s: str) -> str:
    r"""Unescape a backtick-delimited wire format field.

    Reverses _escape_backtick_field: \` → `, \\ → \.
    Uses regex to process escape sequences left-to-right without overlap.
    """
    return re.sub(r"\\(.)", r"\1", s)


# Regex supports backslash-escaped backticks within the delimited fields:
#   (?:[^`\\]|\\.)+ = one or more of: (non-backtick-non-backslash) | (backslash + any char)
_FIXED_ENTRY_RE = re.compile(
    r"^-\s*\[.*?\]\s*FIXED\s*\|\s*fingerprint:\s*`((?:[^`\\]|\\.)+)`\s*\|\s*action:\s*`((?:[^`\\]|\\.)+)`",
)


def _export_to_learning_md(record: dict, repo_root: Path) -> None:
    """Append a promoted pattern to .claude/rules/learning.md.

    Append-only: opens file in "a" mode — never reads or rewrites existing
    content.  Uses fcntl advisory lock for concurrent safety (same pattern
    as _save_learning_store).  Gracefully no-ops on any error.
    """
    try:
        md_path = repo_root / LEARNING_MD_REL
        os.makedirs(md_path.parent, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        fingerprint = _escape_backtick_field(record.get("fingerprint", ""))
        success_count = record.get("success_count", 0)
        entry = (
            f"- [{date_str}] PIPELINE | fingerprint: `{fingerprint}` "
            f"| refs: {success_count}\n"
        )
        lock_path = Path(str(md_path) + ".lock")
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
        try:
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            acquired = False
            while time.monotonic() < deadline:
                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (IOError, OSError):
                    time.sleep(0.1)
            if not acquired:
                return  # graceful no-op on lock timeout
            with open(md_path, "a", encoding="utf-8") as f:
                f.write(entry)
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except (IOError, OSError):
                pass
            os.close(lock_fd)
    except (OSError, TypeError, ValueError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "_export_to_learning_md failed (non-fatal): %s", exc)


def _load_session_fixed_entries(repo_root: Path) -> list[dict]:
    """Parse FIXED entries from .claude/rules/learning.md.

    FIXED entry grammar:
        - [DATE] FIXED | fingerprint: `<text>` | action: `<fix description>`

    Returns list of dicts with keys: fingerprint, action.
    Returns empty list if file absent or on any error.
    """
    try:
        md_path = repo_root / LEARNING_MD_REL
        if not md_path.exists():
            return []
        entries: list[dict] = []
        for line in md_path.read_text(encoding="utf-8").splitlines():
            m = _FIXED_ENTRY_RE.match(line.strip())
            if m:
                entries.append({
                    "fingerprint": _unescape_backtick_field(m.group(1)),
                    "action": _unescape_backtick_field(m.group(2)),
                })
        return entries
    except (OSError, TypeError, ValueError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "_load_session_fixed_entries failed (non-fatal): %s", exc)
        return []


def check_learned_patterns(
    repo_root: Path, result: dict[str, Any],
) -> Optional[LearnedMatch]:
    """Pre-classification override from the learning store.

    Matches promoted patterns against the first 80 chars of the classifier's
    extracted signal (not raw stderr). Requires step match + fingerprint
    substring match + environment match. Returns None on no match or error
    (fail-closed to static classifier).
    """
    try:
        store = _load_learning_store(repo_root)
        lookup_signal = _normalize_fingerprint(
            _extract_classifier_signal(result)[:80]
        )
        # Use executor name as fallback when step is missing — prevents
        # distinct executor surfaces from collapsing into the same scope.
        # Final fallback must match ``attempt_recovery`` at line 3519 (and
        # the parallel sites at :1590 and :3505) which all use ``"unknown"``
        # for the no-step/no-executor case; any other literal here silently
        # breaks the learned-override lookup because recorded patterns are
        # keyed off ``step="unknown"`` but would be looked up with ``""``.
        # (Bot review PR #751 Comment 2 — P2: align missing-step fallback
        # with attempt_recovery scope key.)
        result_step = result.get("step") or result.get("executor", "unknown")
        now = datetime.now(timezone.utc)

        # Collect all matching patterns, then select the strongest match
        # (longest fingerprint = most specific, then highest success_count).
        best_match: Optional[LearnedMatch] = None
        best_fp_len = -1
        best_success = -1

        for pid, pattern in store.get("patterns", {}).items():
            # Skip non-promoted patterns (tier > 1 means not promoted to Tier 1)
            promoted_tier = pattern.get("promoted_tier")
            if promoted_tier is None or promoted_tier > 2:
                continue
            # Skip permanently locked patterns
            if pattern.get("permanently_locked", False):
                continue
            # Check expiry
            last_success = pattern.get("last_success", "")
            if last_success:
                try:
                    ls_dt = datetime.fromisoformat(last_success)
                    if ls_dt.tzinfo is None:
                        ls_dt = ls_dt.replace(tzinfo=timezone.utc)
                    if (now - ls_dt).days > EXPIRY_DAYS:
                        continue
                except (ValueError, TypeError):
                    continue
            # Condition 1: step match
            if pattern.get("step", "") != result_step:
                continue
            # Condition 2: fingerprint substring match
            stored_fp = _normalize_fingerprint(pattern.get("fingerprint", ""))
            if not stored_fp or stored_fp not in lookup_signal:
                continue
            # Condition 3: environment match
            if not _environment_matches(pattern.get("environment_tags")):
                continue

            # All conditions met — candidate match
            try:
                fc = FailureClass(pattern["failure_class"])
            except (ValueError, KeyError):
                continue

            fp_len = len(stored_fp)
            success_count = pattern.get("success_count", 0)
            if (fp_len > best_fp_len) or (
                fp_len == best_fp_len and success_count > best_success
            ):
                best_match = LearnedMatch(
                    failure_class=fc,
                    tier=promoted_tier,
                    pattern_id=pid,
                    action=pattern.get("action", ""),
                )
                best_fp_len = fp_len
                best_success = success_count

        return best_match
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "check_learned_patterns failed (fail-closed to static): %s", exc)
        return None


def observe_outcome(
    repo_root: Path,
    failure_class: FailureClass,
    action: str,
    fingerprint: str,
    outcome: str,
    wave_id: str,
    step: str,
    result: dict[str, Any],
) -> None:
    """Record recovery outcome with environment tags, check promotion/demotion.

    Fingerprint is derived from _extract_classifier_signal(result)[:80] by the
    caller. Environment tags are captured at observation time.
    """
    try:
        store = _load_learning_store(repo_root)
        normalized_fp = _normalize_fingerprint(fingerprint[:80])
        pattern_id = hashlib.sha256(
            f"{failure_class.value}:{action}:{step}:{normalized_fp}".encode()
        ).hexdigest()[:12]

        now_iso = datetime.now(timezone.utc).isoformat()
        current_env = _environment_tags()

        patterns = store.get("patterns", {})
        record = patterns.get(pattern_id)

        if record is None:
            record = {
                "pattern_id": pattern_id,
                "fingerprint": normalized_fp,
                "failure_class": failure_class.value,
                "action": action,
                "step": step,
                "environment_tags": current_env,
                "success_count": 0,
                "failure_count": 0,
                "demotion_count": 0,
                "promoted_tier": None,
                "permanently_locked": False,
                "distinct_wave_ids": [],
                "last_success": None,
                "updated_at": now_iso,
                "created_at": now_iso,
            }
        else:
            # Environment-change counter reset (design doc lines 210-214)
            stored_env = record.get("environment_tags", [])
            if stored_env and sorted(stored_env) != sorted(current_env):
                record["success_count"] = 0
                record["distinct_wave_ids"] = []
                # Clear promoted_tier so the pattern must re-earn promotion
                # on the new environment (an already-promoted pattern must not
                # be auto-applied on an environment where it hasn't proven itself)
                record["promoted_tier"] = None
            record["environment_tags"] = current_env

        record["updated_at"] = now_iso

        if outcome == "success":
            record["success_count"] = record.get("success_count", 0) + 1
            record["last_success"] = now_iso
            # Append wave_id (deduplicated)
            wave_ids = record.get("distinct_wave_ids", [])
            if wave_id not in wave_ids:
                wave_ids.append(wave_id)
            record["distinct_wave_ids"] = wave_ids

            # Promotion gate
            prev_tier = record.get("promoted_tier")
            sc = record["success_count"]
            n_waves = len(record["distinct_wave_ids"])
            fp_len = len(normalized_fp)
            if (
                sc >= PROMOTION_THRESHOLD
                and n_waves >= PROMOTION_WAVE_THRESHOLD
                and fp_len >= MIN_FINGERPRINT_LENGTH
                and not record.get("permanently_locked", False)
            ):
                record["promoted_tier"] = 1
                # Export on first promotion transition only
                if prev_tier != 1:
                    _export_to_learning_md(record, repo_root)
        else:
            record["failure_count"] = record.get("failure_count", 0) + 1
            # Demotion: if currently promoted, demote one tier
            current_tier = record.get("promoted_tier")
            if current_tier is not None and current_tier <= 2:
                if current_tier == 1:
                    record["promoted_tier"] = 2
                elif current_tier == 2:
                    record["promoted_tier"] = 3
                record["demotion_count"] = record.get("demotion_count", 0) + 1
                record["failure_count"] = 0  # reset on demotion
                # Permanent lock check
                if record["demotion_count"] >= DEMOTION_LOCK_THRESHOLD:
                    record["promoted_tier"] = 3
                    record["permanently_locked"] = True

        patterns[pattern_id] = record
        store["patterns"] = patterns
        _save_learning_store(repo_root, store)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(
            "observe_outcome failed (non-fatal): %s", exc)


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
    invocation_id: str = ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _excerpt(value: Any, limit: int = 160) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", "\n").strip()
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    excerpt = ""
    for candidate in reversed(lines):
        if candidate not in _TRIVIAL_EXCERPTS:
            excerpt = candidate
            break
    if not excerpt:
        excerpt = lines[-1] if lines else text
    if len(excerpt) <= limit:
        return excerpt
    return excerpt[: limit - 3].rstrip() + "..."


def _parse_json_object(value: Any) -> dict[str, Any]:
    if not isinstance(value, str):
        return {}
    text = value.strip()
    if not text:
        return {}
    candidates: list[str] = []
    if text.startswith("{"):
        candidates.append(text)
    json_start = text.find("{")
    json_end = text.rfind("}")
    if json_start != -1 and json_end > json_start:
        candidates.append(text[json_start:json_end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _summarize_json_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("error", "errors", "message", "detail", "reason", "stderr", "stdout"):
            excerpt = _summarize_json_value(value.get(key))
            if excerpt:
                return excerpt
        for nested in value.values():
            excerpt = _summarize_json_value(nested)
            if excerpt:
                return excerpt
        return ""
    if isinstance(value, list):
        for item in value:
            excerpt = _summarize_json_value(item)
            if excerpt:
                return excerpt
        return ""
    excerpt = _excerpt(value)
    return excerpt if excerpt not in _TRIVIAL_EXCERPTS else ""


def _summarize_result_reason(result: dict[str, Any]) -> str:
    def _usable_excerpt(value: Any) -> str:
        if isinstance(value, (list, dict)):
            excerpt = _summarize_json_value(value)
            if excerpt:
                return excerpt
        excerpt = _excerpt(value)
        if not excerpt:
            return ""
        if re.fullmatch(r"[\d,\s]+", excerpt):
            return ""
        return excerpt

    for key in ("error", "errors", "stderr", "detail", "message"):
        excerpt = _usable_excerpt(result.get(key, ""))
        if excerpt:
            return excerpt
    for key in ("stdout", "stderr"):
        excerpt = _summarize_json_value(_parse_json_object(result.get(key, "")))
        if excerpt:
            return excerpt
    excerpt = _usable_excerpt(result.get("stdout", ""))
    if excerpt:
        return excerpt
    status = _excerpt(result.get("status", ""))
    step = _excerpt(result.get("step") or result.get("executor", ""))
    if status and step:
        return f"{step}: {status}"
    return status or step or "recovery invoked"


def _load_recovery_status(repo_root: Path) -> dict[str, Any]:
    status_path = repo_root / RECOVERY_STATUS_FILE
    if not status_path.exists():
        return {}
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_recovery_status(repo_root: Path, status: dict[str, Any]) -> None:
    status_path = repo_root / RECOVERY_STATUS_FILE
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


def _count_wave_invocations(attempts: list[dict[str, Any]], wave_id: str) -> int:
    invocation_ids: set[str] = set()
    fallback = 0
    for entry in attempts:
        if entry.get("wave_id") != wave_id:
            continue
        invocation_id = entry.get("invocation_id", "")
        if invocation_id:
            invocation_ids.add(invocation_id)
        else:
            fallback += 1
    return len(invocation_ids) + fallback


def _new_invocation_id(wave_id: str, step: str, failure_class: str) -> str:
    base = normalize_wave_id(wave_id or "wave")[:40]
    step_part = normalize_wave_id(step or "step")[:20]
    class_part = normalize_wave_id(failure_class or "failure")[:24]
    return f"{base}-{step_part}-{class_part}-{uuid.uuid4().hex[:8]}"


def _retry_target(result: dict[str, Any], step: str) -> str:
    target = result.get("executor") or step or result.get("step", "")
    return str(target).strip()


def _begin_recovery_status(
    repo_root: Path,
    *,
    attempts: list[dict[str, Any]],
    result: dict[str, Any],
    wave_id: str,
    step: str,
    failure_class: FailureClass,
    tier: int,
    prior_attempts: int,
    invocation_id: str,
) -> dict[str, Any]:
    now = _now_iso()
    status = {
        "active": True,
        "invocation_id": invocation_id,
        "wave_id": wave_id,
        "step": step,
        "failure_class": failure_class.value,
        "tier": tier,
        "tuple_attempt_index": prior_attempts + 1,
        "wave_invocation_count": _count_wave_invocations(attempts, wave_id) + 1,
        "started_at": now,
        "updated_at": now,
        "finished_at": "",
        "owner_pid": os.getpid(),
        "child_pid": 0,
        "child_role": "",
        "state": f"tier{tier}_starting",
        "reason": _summarize_result_reason(result),
        "retry_target": _retry_target(result, step),
        "current_iteration": 0,
        "max_iterations": MAX_RECOVERY_ITERATIONS if tier == 3 else 0,
        "last_action": "",
        "current_command": "",
        "explanation": "",
        "detail": "",
        "recovered": False,
        "exhausted": False,
        "outcome": "",
    }
    _save_recovery_status(repo_root, status)
    return status


def _update_recovery_status(repo_root: Path, **updates: Any) -> dict[str, Any]:
    status = _load_recovery_status(repo_root)
    status.update(updates)
    status["updated_at"] = _now_iso()
    _save_recovery_status(repo_root, status)
    return status


def _finish_recovery_status(
    repo_root: Path,
    *,
    recovered: bool,
    exhausted: bool,
    outcome: str,
    action: str,
    detail: str,
    state: str,
) -> dict[str, Any]:
    return _update_recovery_status(
        repo_root,
        active=False,
        recovered=recovered,
        exhausted=exhausted,
        outcome=outcome,
        state=state,
        last_action=action,
        detail=_excerpt(detail),
        child_pid=0,
        child_role="",
        current_command="",
        finished_at=_now_iso(),
    )


def _human_recovery_target_label(target: str) -> str:
    cleaned = str(target or "").strip()
    mapping = {
        "phase_a_executor": "Phase A",
        "phase_a": "Phase A",
        "phase_b_executor": "Phase B",
        "phase_b": "Phase B",
        "commit_executor": "Commit",
        "commit": "Commit",
        "executor_dispatch": "Dispatch",
    }
    if cleaned in mapping:
        return mapping[cleaned]
    normalized = cleaned.replace("_executor", "").replace("_", " ").strip()
    return normalized or "pipeline step"


def clear_stale_recovery_status_on_success(
    repo_root: Path,
    *,
    wave_id: str = "",
    success_target: str = "",
) -> dict[str, Any]:
    """Mark an old inactive recovery record as cleared by a later success.

    This keeps the pane honest after a retry eventually works. Without this,
    observability keeps showing the last exhausted recovery tuple even though
    the pipeline has already moved on and succeeded.
    """
    status = _load_recovery_status(repo_root)
    if not status or bool(status.get("active")):
        return status

    status_wave = str(status.get("wave_id", "")).strip()
    if wave_id and status_wave and status_wave != wave_id:
        return status

    step = str(status.get("step", "")).strip()
    retry_target = str(status.get("retry_target", "")).strip()
    normalized_target = str(success_target or "").strip()
    if normalized_target and normalized_target not in {step, retry_target}:
        return status

    if (
        bool(status.get("recovered"))
        and str(status.get("outcome", "")).strip().lower() == "cleared"
        and str(status.get("state", "")).strip() == "resolved_by_later_success"
    ):
        return status

    target_label = _human_recovery_target_label(normalized_target or retry_target or step)
    detail = (
        f"{target_label} later succeeded, so this older recovery record is "
        "historical only."
    )
    return _update_recovery_status(
        repo_root,
        active=False,
        recovered=True,
        exhausted=False,
        outcome="cleared",
        state="resolved_by_later_success",
        last_action="later_success",
        detail=_excerpt(detail),
        child_pid=0,
        child_role="",
        current_command="",
        finished_at=_now_iso(),
    )


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
    count = 0
    seen_invocations: set[str] = set()
    for entry in attempts:
        if entry.get("wave_id") != wave_id:
            continue
        if entry.get("step") != step:
            continue
        if entry.get("failure_class") != failure_class:
            continue
        invocation_id = entry.get("invocation_id", "")
        if invocation_id:
            if invocation_id in seen_invocations:
                continue
            seen_invocations.add(invocation_id)
        count += 1
    return count


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
    # Learning store pre-classification override (before static classifier)
    learned = check_learned_patterns(repo_root, result)
    if learned is not None:
        # Terminal-policy outcomes must NEVER be overridden by learned patterns.
        # classify_failure() is a pure dict-inspection function — safe to call.
        static_fc = classify_failure(result)
        static_tier = tier_for(static_fc)
        if static_tier >= 4:
            # Hard escalation — ignore learned override entirely.
            fc, tier = static_fc, static_tier
        else:
            fc, tier = learned.failure_class, learned.tier
            # Validate the promoted tier has a handler for this failure class.
            # Tier 3 always has a handler (recovery_loop). Tier 4 is escalation.
            # Tier 1/2 require registered fix functions — without one the pattern
            # strands at "no_fix_registered" and never demotes (Bridge R3 Finding 2).
            _has_handler = (
                tier >= 3
                or (tier == 1 and fc in _TIER1_FIXES)
                or (tier == 2 and fc in _TIER2_FIXES)
            )
            if not _has_handler:
                # Observe as failed to trigger demotion, then fall through.
                _step = result.get("step") or result.get("executor", "unknown")
                observe_outcome(
                    repo_root, fc, learned.action,
                    _extract_classifier_signal(result)[:80],
                    "failed", wave_id, _step, result,
                )
                fc, tier = static_fc, static_tier
    else:
        fc = classify_failure(result)
        tier = tier_for(fc)
        # FIXED-entry fallback: consult .claude/rules/learning.md for
        # manually curated Tier 1 candidates when no auto-observed match.
        # Auto-observed patterns take priority (richer matching semantics).
        if tier < 4:
            _fixed_entries = _load_session_fixed_entries(repo_root)
            if _fixed_entries:
                _lookup = _normalize_fingerprint(
                    _extract_classifier_signal(result)[:80]
                )
                for _fe in _fixed_entries:
                    _fe_fp = _normalize_fingerprint(_fe["fingerprint"])
                    if _fe_fp and _fe_fp in _lookup:
                        # Validate Tier 1 has a handler for this failure class
                        # before accepting the FIXED match.  Without this guard
                        # a FIXED entry for a Tier 2 failure (e.g. PROCESS_TIMEOUT)
                        # would force tier=1 where no handler exists, producing
                        # "no_fix_registered" and suppressing the working Tier 2
                        # recovery (Bridge R1 Finding 3).
                        if fc not in _TIER1_FIXES:
                            continue
                        learned = LearnedMatch(
                            failure_class=fc,
                            tier=1,
                            pattern_id="fixed_entry",
                            action=_fe["action"],
                        )
                        tier = 1
                        break
    # Use executor name as fallback when step is missing — prevents
    # distinct timeout sites (e.g. phase_b_executor vs commit_executor)
    # from collapsing into the same (wave_id, "unknown", class) bucket
    # (Bridge R6 Finding 1 fix).
    step = result.get("step") or result.get("executor", "unknown")

    attempts = _load_recovery_log(repo_root)
    prior = _count_prior_attempts(attempts, wave_id, step, fc.value)
    invocation_id = _new_invocation_id(wave_id, step, fc.value)
    _begin_recovery_status(
        repo_root,
        attempts=attempts,
        result=result,
        wave_id=wave_id,
        step=step,
        failure_class=fc,
        tier=tier,
        prior_attempts=prior,
        invocation_id=invocation_id,
    )

    if prior >= MAX_ATTEMPTS_PER_TUPLE:
        detail = (
            f"max {MAX_ATTEMPTS_PER_TUPLE} attempts reached for "
            f"({wave_id}, {step}, {fc.value})"
        )
        _finish_recovery_status(
            repo_root,
            recovered=False,
            exhausted=True,
            outcome="exhausted",
            action="exhausted",
            detail=detail,
            state=f"tier{tier}_exhausted",
        )
        return _make_result(False, "exhausted", tier, fc, detail, True)
    if tier == 4:
        detail = f"tier 4 failure ({fc.value}) requires escalation"
        _finish_recovery_status(
            repo_root,
            recovered=False,
            exhausted=False,
            outcome="escalated",
            action="escalate",
            detail=detail,
            state="tier4_escalated",
        )
        return _make_result(False, "escalate", 4, fc, detail, False)
    if tier == 3:
        loop_result = run_recovery_loop(
            repo_root,
            {
                **result,
                "failure_class": fc.value,
            },
            wave_id,
            invocation_id=invocation_id,
        )
        detail = ""
        if loop_result.get("log"):
            detail = str(loop_result["log"][-1].get("detail", "")).strip()
        if not detail:
            detail = _load_recovery_status(repo_root).get("detail", "")
        # Observe outcome for learning store (Tier 3 exit)
        t3_outcome = "success" if loop_result.get("recovered") else "failed"
        observe_outcome(
            repo_root, fc, "recovery_loop",
            _extract_classifier_signal(result)[:80],
            t3_outcome, wave_id,
            step, result,
        )
        return _make_result(
            loop_result.get("recovered", False),
            "recovery_loop",
            tier,
            fc,
            detail,
            loop_result.get("exhausted", False),
        )

    # Tier 2: check _TIER2_FIXES before falling through
    if tier == 2:
        _update_recovery_status(repo_root, state="tier2_fixing")
        fix_fn = _TIER2_FIXES.get(fc)
        if fix_fn is not None:
            fix_result = fix_fn(repo_root, wave_id=wave_id, result=result)
            duration = time.monotonic() - t0
            attempt_rec = RecoveryAttempt(
                timestamp=datetime.now(timezone.utc).isoformat(),
                wave_id=wave_id, step=step, failure_class=fc.value, tier=tier,
                action=fix_result.get("action", "unknown"),
                outcome="success" if fix_result.get("fixed") else "failed",
                duration_s=round(duration, 3), tokens_used=0,
                detail=fix_result.get("detail", ""),
                invocation_id=invocation_id)
            attempts.append(asdict(attempt_rec))
            _save_recovery_log(repo_root, attempts)
            # Observe outcome for learning store (Tier 2 exit)
            t2_outcome = "success" if fix_result.get("fixed") else "failed"
            observe_outcome(
                repo_root, fc, fix_result.get("action", "unknown"),
                _extract_classifier_signal(result)[:80],
                t2_outcome, wave_id,
                step, result,
            )
            _finish_recovery_status(
                repo_root,
                recovered=fix_result.get("fixed", False),
                exhausted=False,
                outcome="success" if fix_result.get("fixed") else "failed",
                action=fix_result.get("action", "unknown"),
                detail=fix_result.get("detail", ""),
                state="tier2_fixed" if fix_result.get("fixed") else "tier2_failed",
            )
            return _make_result(fix_result.get("fixed", False),
                                fix_result.get("action", "unknown"), tier, fc,
                                fix_result.get("detail", ""), False)
        detail = f"no tier 2 fix registered for {fc.value}"
        _finish_recovery_status(
            repo_root,
            recovered=False,
            exhausted=False,
            outcome="failed",
            action="no_fix_registered",
            detail=detail,
            state="tier2_unhandled",
        )
        return _make_result(False, "no_fix_registered", tier, fc, detail, False)

    fix_fn = _TIER1_FIXES.get(fc)
    if fix_fn is None:
        detail = f"no tier 1 fix registered for {fc.value}"
        _finish_recovery_status(
            repo_root,
            recovered=False,
            exhausted=False,
            outcome="failed",
            action="no_fix_registered",
            detail=detail,
            state="tier1_unhandled",
        )
        return _make_result(False, "no_fix_registered", tier, fc, detail, False)

    _update_recovery_status(repo_root, state="tier1_fixing")
    fix_result = fix_fn(repo_root, wave_id=wave_id, result=result)
    duration = time.monotonic() - t0

    attempt = RecoveryAttempt(
        timestamp=datetime.now(timezone.utc).isoformat(),
        wave_id=wave_id, step=step, failure_class=fc.value, tier=tier,
        action=fix_result.get("action", "unknown"),
        outcome="success" if fix_result.get("fixed") else "failed",
        duration_s=round(duration, 3), tokens_used=0,
        detail=fix_result.get("detail", ""),
        invocation_id=invocation_id)
    attempts.append(asdict(attempt))
    _save_recovery_log(repo_root, attempts)
    # Observe outcome for learning store (Tier 1 exit)
    t1_outcome = "success" if fix_result.get("fixed") else "failed"
    observe_outcome(
        repo_root, fc, fix_result.get("action", "unknown"),
        _extract_classifier_signal(result)[:80],
        t1_outcome, wave_id,
        step, result,
    )
    _finish_recovery_status(
        repo_root,
        recovered=fix_result.get("fixed", False),
        exhausted=False,
        outcome="success" if fix_result.get("fixed") else "failed",
        action=fix_result.get("action", "unknown"),
        detail=fix_result.get("detail", ""),
        state="tier1_fixed" if fix_result.get("fixed") else "tier1_failed",
    )

    return _make_result(fix_result.get("fixed", False),
                        fix_result.get("action", "unknown"), tier, fc,
                        fix_result.get("detail", ""), False)
