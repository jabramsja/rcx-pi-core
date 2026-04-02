#!/usr/bin/env python3
"""Pipeline recovery gate: failure classification and Tier 1–3 recovery.

Design doc: mu/docs/agents/PipelineRecovery.v0.md
Import constraints: only stdlib + executor_common.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
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
    NEEDS_PHASE_B = "needs_phase_b"
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
    FailureClass.NEEDS_PHASE_B: 3, FailureClass.GIT_STAGING_CONFLICT: 3,
    FailureClass.TEST_FAILURE: 3, FailureClass.AGENT_REVIEW_CRASH: 3,
    FailureClass.UNKNOWN_ERROR: 3,
    FailureClass.TERMINAL_POLICY: 4, FailureClass.UNCLASSIFIED: 4,
}

_TERMINAL_STATUSES = frozenset({
    "question_for_founder", "max_rounds_reached",
    "supervisor_rejected",
})
_TRANSIENT_KILL_CODES = frozenset({-9, -15, 137})
_STATUS_LINE_RE = re.compile(
    r"^\s*\[[^\]]+\]\s+Status:\s*([A-Za-z0-9_ -]+)\s*$"
)


def tier_for(fc: FailureClass) -> int:
    """Return the recovery tier (1-4) for a failure class."""
    return _TIER_MAP[fc]


# ---------------------------------------------------------------------------
# Classifier -- pure dict inspection, no external calls
# ---------------------------------------------------------------------------

def classify_failure(result: dict[str, Any]) -> FailureClass:
    """Classify an executor failure result into a FailureClass."""
    outer_statuses = _normalize_status_values(result.get("status", ""))
    outer_status = outer_statuses[0] if outer_statuses else ""
    status = outer_status
    stderr = result.get("stderr", "")
    exit_code = result.get("exit_code")
    step = result.get("step", "")
    stdout = result.get("stdout", "")
    if not isinstance(stderr, str):
        stderr = ""
    if not isinstance(step, str):
        step = ""
    if not isinstance(stdout, str):
        stdout = ""
    embedded = _extract_embedded_result(stdout)
    embedded_statuses = _extract_embedded_statuses(stdout)
    embedded_status = embedded.get("status")
    if isinstance(embedded_status, str) and embedded_status.strip():
        status = embedded_status.strip()
    embedded_step = embedded.get("step")
    if (not isinstance(step, str) or not step.strip()) and isinstance(embedded_step, str):
        step = embedded_step.strip()
    combined_text = _collect_error_text(result, embedded)
    combined_lower = combined_text.lower()

    # Tier 4: terminal policy outcomes (check first, never recover)
    if outer_status in _TERMINAL_STATUSES:
        return FailureClass.TERMINAL_POLICY
    if set(outer_statuses) & _TERMINAL_STATUSES:
        return FailureClass.TERMINAL_POLICY
    if status in _TERMINAL_STATUSES:
        return FailureClass.TERMINAL_POLICY
    if embedded_statuses & _TERMINAL_STATUSES:
        return FailureClass.TERMINAL_POLICY

    if status == FailureClass.NEEDS_PHASE_B.value:
        return FailureClass.NEEDS_PHASE_B
    if FailureClass.NEEDS_PHASE_B.value in outer_statuses:
        return FailureClass.NEEDS_PHASE_B
    if FailureClass.NEEDS_PHASE_B.value in embedded_statuses:
        return FailureClass.NEEDS_PHASE_B

    # Tier 1: deterministic lock/state issues
    if "bridge.lock" in combined_lower:
        return FailureClass.STALE_BRIDGE_LOCK
    if "index.lock" in combined_lower:
        return FailureClass.STALE_GIT_INDEX_LOCK
    if "phase_b_state.json" in combined_lower or "stale_state" in status:
        return FailureClass.STALE_EXECUTOR_STATE
    if "continuation" in combined_lower and "stale" in combined_lower:
        return FailureClass.STALE_CONTINUATION
    if _looks_like_mixed_staging(stderr, stdout, step):
        return FailureClass.MIXED_STAGING

    # Tier 2: transient / timeout issues
    if status == "timeout":
        return FailureClass.PROCESS_TIMEOUT
    if "timed out" in combined_lower and "agent review" in combined_lower:
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
    if "agent" in step.lower() and status in ("error", "failed"):
        return FailureClass.AGENT_REVIEW_CRASH
    if "agent review" in combined_lower and status in ("error", "failed"):
        return FailureClass.AGENT_REVIEW_CRASH
    if status in ("error", "failed"):
        return FailureClass.UNKNOWN_ERROR

    return FailureClass.UNCLASSIFIED


def _extract_embedded_result(stdout: str) -> dict[str, Any]:
    """Extract an executor result object from stdout when available."""
    if not stdout:
        return {}

    try:
        data = json.loads(stdout)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    return {}


def _normalize_status_values(value: Any) -> list[str]:
    """Return string status values without throwing on malformed executor data."""
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]
    return []


def _extract_embedded_statuses(stdout: str) -> set[str]:
    """Extract executor-reported statuses from stdout JSON or status lines."""
    statuses: set[str] = set()
    if not stdout:
        return statuses

    try:
        data = json.loads(stdout)
        if isinstance(data, dict) and isinstance(data.get("status"), str):
            statuses.add(data["status"])
    except (json.JSONDecodeError, ValueError):
        pass

    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict) and isinstance(data.get("status"), str):
                    statuses.add(data["status"])
            except (json.JSONDecodeError, ValueError):
                pass
        match = _STATUS_LINE_RE.match(stripped)
        if match:
            statuses.add(match.group(1).strip())
    return statuses


def _collect_error_text(result: dict[str, Any], embedded: dict[str, Any]) -> str:
    """Collect outer and embedded error text for failure classification."""
    parts: list[str] = []
    for key in ("message", "stderr", "stdout"):
        value = result.get(key, "")
        if isinstance(value, str) and value:
            parts.append(value)
    embedded_error = embedded.get("error")
    if isinstance(embedded_error, str) and embedded_error:
        parts.append(embedded_error)
    embedded_errors = embedded.get("errors")
    if isinstance(embedded_errors, list):
        parts.extend(item for item in embedded_errors if isinstance(item, str) and item)
    return "\n".join(parts)


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


def _timeout_key_for_result(result: dict[str, Any], timeouts: dict[str, Any]) -> str:
    """Select the timeout knob that corresponds to the observed failure."""
    stdout = result.get("stdout", "")
    embedded = _extract_embedded_result(stdout if isinstance(stdout, str) else "")
    outer_statuses = _normalize_status_values(result.get("status", ""))
    status = outer_statuses[0] if outer_statuses else ""
    embedded_status = embedded.get("status")
    if isinstance(embedded_status, str) and embedded_status.strip():
        status = embedded_status.strip()
    step = result.get("step", "")
    embedded_step = embedded.get("step")
    if (not isinstance(step, str) or not step.strip()) and isinstance(embedded_step, str):
        step = embedded_step.strip()
    combined_lower = _collect_error_text(result, embedded).lower()

    if "agent review" in combined_lower and "agent_review" in timeouts:
        return "agent_review"

    executor = result.get("executor", "")
    if isinstance(executor, str) and executor in timeouts:
        return executor
    if isinstance(step, str) and step in timeouts:
        return step
    if status == "timeout" and "phase_b_executor" in timeouts:
        return "phase_b_executor"
    return next(iter(timeouts), "phase_b_executor")


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
    """
    timeouts = _load_config_timeouts(repo_root)
    # Determine which executor timed out from the result
    result = kw.get("result", {})
    timeout_key = _timeout_key_for_result(result, timeouts)
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
    return _fix_result(True, "increase_timeout",
                       f"timeout for {timeout_key} increased from {current}s "
                       f"to {new_timeout}s (capped at 2x original {baseline}s) "
                       f"via RCX_RECOVERY_TIMEOUT_OVERRIDE")


def fix_transient_kill(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """No-op fix — marks as retryable. Dispatcher already retries."""
    return _fix_result(True, "retryable",
                       "transient kill — safe to retry with same parameters")


def fix_aggregation_hang(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Clear bridge lock and mark stale bridge DB jobs as failed.

    Does NOT delete bridge.db — it is the shared job/transcript SQLite bus
    used by bridge_supervisor.py. Only the lock file is removed and
    in-progress/pending jobs for the CURRENT WAVE are marked as failed.
    Jobs belonging to other waves (identified by scope_hint) are untouched.
    """
    wave_id = kw.get("wave_id", "")
    cleared: list[str] = []
    # Clear bridge.lock
    lock_path = repo_root / ".agent_bus" / "bridge.lock"
    if lock_path.exists():
        lock_path.unlink(missing_ok=True)
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


_TIER2_FIXES: dict[FailureClass, Any] = {
    FailureClass.PROCESS_TIMEOUT: fix_process_timeout,
    FailureClass.TRANSIENT_KILL: fix_transient_kill,
    FailureClass.AGGREGATION_HANG: fix_aggregation_hang,
    FailureClass.IMPLEMENTER_STALE: fix_implementer_stale,
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
_DANGEROUS_COMMAND_PATTERNS = (
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgit\s+reset\b"),
    re.compile(r"\bgit\s+checkout\b(?:[^\n]*\s)?--(?:\s|$)"),
    re.compile(
        r"\bgit\s+restore\b"
        r"(?=[^\n]*\s--source(?:=|\s)|[^\n]*\s--staged(?:=|\s|$))"
    ),
    re.compile(r"\|\s*(?:sh|bash)\b"),
    re.compile(r"\bbase64\b"),
    re.compile(r"\beval\b"),
    re.compile(r"\bgit\s+config\b[^\n]*\balias\."),
    re.compile(r"\bgit\s+\$"),
)
_SENSITIVE_RELATIVE_PATHS = (
    ".git/config",
    ".git/hooks",
)

MAX_RECOVERY_ITERATIONS = 3
_CLAUDE_TIMEOUT = 60
_SHELL_TIMEOUT = 30


def _is_dangerous_command(cmd: str) -> bool:
    """Check if a shell command matches the denylist."""
    cmd_lower = cmd.strip().lower()
    for denied in _DANGEROUS_COMMANDS:
        if denied in cmd_lower:
            return True
    if _touches_sensitive_path_text(cmd_lower):
        return True
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(cmd_lower):
            return True
    return False


def _touches_sensitive_path_text(text: str) -> bool:
    """Fail closed on commands that touch repo-internal sensitive paths."""
    lowered = text.strip().lower()
    return (
        ".git/config" in lowered
        or ".git/hooks/" in lowered
        or lowered.endswith(".git/hooks")
    )


def _is_sensitive_repo_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/").strip().lower()
    parts: list[str] = []
    for part in normalized.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    normalized = "/".join(parts)
    return any(
        normalized == denied or normalized.startswith(f"{denied}/")
        for denied in _SENSITIVE_RELATIVE_PATHS
    )


def _trim_prompt_block(text: str, *, max_lines: int, max_chars_per_line: int = 240) -> str:
    """Trim prompt context by line count and per-line width."""
    lines = text.strip().splitlines()
    if not lines:
        return ""
    if len(lines) > max_lines:
        lines = [f"[truncated {len(lines) - max_lines} earlier lines]"] + lines[-max_lines:]
    trimmed_lines: list[str] = []
    for line in lines:
        if len(line) > max_chars_per_line:
            trimmed_lines.append(f"{line[:max_chars_per_line]}...[truncated]")
        else:
            trimmed_lines.append(line)
    return "\n".join(trimmed_lines)


def _build_diagnosis_prompt(
    result: dict[str, Any], wave_id: str, iteration: int,
    repo_root: Path, prior_invalid_response: str = "",
) -> str:
    """Build a ~2K token diagnosis prompt for claude --print."""
    fc = result.get("failure_class", result.get("recovery", {}).get("failure_class", "unknown"))
    tier = result.get("tier", result.get("recovery", {}).get("tier", 3))
    step = result.get("step", "unknown")
    stderr = result.get("stderr", "")
    stdout = result.get("stdout", "")
    stderr_block = _trim_prompt_block(stderr if isinstance(stderr, str) else "", max_lines=40)
    stdout_block = _trim_prompt_block(stdout if isinstance(stdout, str) else "", max_lines=20)
    # Get git status
    try:
        git_proc = subprocess.run(
            ["git", "status", "--short"], cwd=repo_root,
            capture_output=True, text=True, timeout=10)
        git_status = git_proc.stdout[:500] if git_proc.returncode == 0 else "(unavailable)"
    except (subprocess.TimeoutExpired, OSError):
        git_status = "(unavailable)"

    invalid_response_block = ""
    if prior_invalid_response.strip():
        invalid_response_block = f"""

Previous response was invalid because it was not parseable JSON. Reissue the
diagnosis as a SINGLE JSON object matching the schema below and do not add any
prose outside the JSON.

Previous invalid response (truncated):
{prior_invalid_response[:600]}
"""

    return f"""You are a pipeline recovery agent. A pipeline step has failed and you must diagnose and fix it.

Failure class: {fc}
Tier: {tier}
Step: {step}
Iteration: {iteration + 1}/{MAX_RECOVERY_ITERATIONS}
Wave: {wave_id}

STDERR (last 100 lines):
{stderr_block}

STDOUT (last 50 lines):
{stdout_block}

Git status:
{git_status}
{invalid_response_block}

Respond with ONLY a JSON object (no markdown, no explanation outside JSON):
{{"action": "shell"|"edit"|"skip"|"escalate", "commands": ["cmd1", "cmd2"], "explanation": "why"}}

- "shell": run shell commands to fix the issue
- "edit": apply file edits (commands = [{{"file_path": "...", "old_text": "...", "new_text": "..."}}])
- "skip": cannot fix, return failure
- "escalate": need human intervention

If the cause is a caller-supplied env var, CLI flag, or parent-process state
that this recovery loop cannot safely change, use "skip" with explanation.
If human intervention is required, use "escalate" with explanation.

Safety: no rm -rf, no git push, no git reset --hard. Max 30s per command."""


def _extract_first_json_object(text: str) -> str | None:
    """Return the first balanced JSON object embedded in text."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
                continue
            if ch == "{":
                depth += 1
                continue
            if ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:idx + 1]
                if depth < 0:
                    break
        start = text.find("{", start + 1)
    return None


def _parse_recovery_response(raw_response: str) -> dict[str, Any]:
    """Parse a recovery-agent response, tolerating prose-wrapped JSON."""
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        lines = [line for line in lines if not line.startswith("```")]
        cleaned = "\n".join(lines).strip()
    if not cleaned:
        raise ValueError("empty response")

    candidates: list[str] = [cleaned]
    embedded = _extract_first_json_object(cleaned)
    if embedded and embedded != cleaned:
        candidates.append(embedded)

    last_error = "response was not valid JSON"
    for candidate in candidates:
        try:
            response = json.loads(candidate)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = str(exc)
            continue
        if isinstance(response, dict):
            return response
        last_error = "response must decode to a JSON object"
    raise ValueError(last_error)


def _apply_edit(edit: dict[str, Any], repo_root: Path) -> tuple[bool, str]:
    """Apply a single file edit from the LLM response.

    Safety: file_path must resolve to within repo_root (no symlink escape).
    """
    raw_path = edit.get("file_path", "")
    if not isinstance(raw_path, str):
        return False, "file_path must be a string"
    raw_path = raw_path.strip()
    if not raw_path:
        return False, "file_path is required"
    if _is_sensitive_repo_path(raw_path):
        return False, f"sensitive path blocked: {raw_path}"
    file_path = (repo_root / raw_path).resolve()
    repo_resolved = repo_root.resolve()
    if not str(file_path).startswith(str(repo_resolved) + os.sep) and file_path != repo_resolved:
        return False, f"repo-escape blocked: {raw_path} resolves outside repo root"
    repo_relative = file_path.relative_to(repo_resolved).as_posix()
    if _is_sensitive_repo_path(repo_relative):
        return False, f"sensitive path blocked: {raw_path}"
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
    detail: str = "",
) -> None:
    """Persist a single Tier 3 recovery iteration to recovery_log.json."""
    attempts = _load_recovery_log(repo_root)
    attempt = RecoveryAttempt(
        timestamp=datetime.now(timezone.utc).isoformat(),
        wave_id=wave_id, step=step, failure_class=failure_class, tier=3,
        action=f"tier3_iter{iteration}_{action}", outcome=outcome,
        duration_s=duration_s, tokens_used=0, detail=detail,
    )
    attempts.append(asdict(attempt))
    _save_recovery_log(repo_root, attempts)


def run_recovery_loop(
    repo_root: Path, result: dict[str, Any], wave_id: str,
    max_iterations: int = MAX_RECOVERY_ITERATIONS,
    verify_command: list[str] | None = None,
) -> dict[str, Any]:
    """Tier 3 LLM recovery loop: diagnose → fix → verify.

    Returns dict with: recovered, exhausted, iterations, log.
    All iterations are durably logged to recovery_log.json.
    """
    loop_log: list[dict[str, Any]] = []
    fc = result.get("failure_class", result.get("recovery", {}).get("failure_class", "unknown"))
    step = result.get("step") or result.get("executor", "unknown")
    prior_invalid_response = ""

    for i in range(max_iterations):
        iteration_t0 = time.monotonic()
        prompt = _build_diagnosis_prompt(
            result, wave_id, i, repo_root, prior_invalid_response=prior_invalid_response)
        action_succeeded = False

        # Call claude --print for diagnosis
        try:
            claude_proc = subprocess.run(
                ["claude", "--print", "-p", prompt],
                capture_output=True, text=True, timeout=_CLAUDE_TIMEOUT,
                cwd=repo_root)
            raw_response = claude_proc.stdout.strip()
        except subprocess.TimeoutExpired:
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "timeout",
                "detail": "claude --print timed out",
                "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "timeout", "failed", dur, "claude --print timed out")
            continue
        except OSError as exc:
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "error",
                "detail": f"claude invocation failed: {exc}",
                "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "error", "failed", dur, f"claude invocation failed: {exc}")
            continue

        # Parse JSON response
        try:
            response = _parse_recovery_response(raw_response)
            prior_invalid_response = ""
        except ValueError as exc:
            prior_invalid_response = raw_response[:1000]
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "parse_error",
                "detail": f"could not parse response ({exc}): {raw_response[:200]}",
                "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "parse_error", "failed", dur,
                               f"could not parse response ({exc}): {raw_response[:200]}")
            continue

        action = response.get("action", "skip")
        commands = response.get("commands", [])
        explanation = response.get("explanation", "")

        if action == "escalate":
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "escalate",
                "detail": explanation, "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "escalate", "escalated", dur, explanation)
            return {"recovered": False, "exhausted": True,
                    "iterations": i + 1, "log": loop_log}

        if action == "skip":
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1, "action": "skip",
                "detail": explanation, "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "skip", "skipped", dur, explanation)
            return {"recovered": False, "exhausted": False,
                    "iterations": i + 1, "log": loop_log}

        if action == "shell":
            cmd_results = []
            blocked = False
            executed_any = False
            shell_success = True
            for cmd in commands:
                if not isinstance(cmd, str):
                    shell_success = False
                    continue
                executed_any = True
                if _is_dangerous_command(cmd):
                    cmd_results.append(f"BLOCKED: {cmd}")
                    blocked = True
                    shell_success = False
                    continue
                try:
                    cmd_proc = subprocess.run(
                        cmd, shell=True, capture_output=True, text=True,
                        timeout=_SHELL_TIMEOUT, cwd=repo_root)
                    cmd_results.append(
                        f"exit={cmd_proc.returncode}: {cmd_proc.stdout[:200]}")
                    if cmd_proc.returncode != 0:
                        shell_success = False
                except subprocess.TimeoutExpired:
                    cmd_results.append(f"TIMEOUT: {cmd}")
                    shell_success = False
                except OSError as exc:
                    cmd_results.append(f"ERROR: {exc}")
                    shell_success = False
            loop_log.append({
                "iteration": i + 1, "action": "shell",
                "commands": commands, "results": cmd_results,
                "blocked": blocked, "detail": explanation,
                "duration_s": round(time.monotonic() - iteration_t0, 3)})
            action_succeeded = executed_any and shell_success

        elif action == "edit":
            edit_results = []
            edit_count = 0
            edit_success = True
            for edit in commands:
                if isinstance(edit, dict):
                    edit_count += 1
                    ok, msg = _apply_edit(edit, repo_root)
                    edit_results.append(msg)
                    if not ok:
                        edit_success = False
            loop_log.append({
                "iteration": i + 1, "action": "edit",
                "results": edit_results, "detail": explanation,
                "duration_s": round(time.monotonic() - iteration_t0, 3)})
            action_succeeded = edit_count > 0 and edit_success

        if not verify_command:
            dur = round(time.monotonic() - iteration_t0, 3)
            if action_succeeded:
                _log_tier3_attempt(
                    repo_root, wave_id, step, fc, i + 1,
                    action, "success", dur,
                    "no explicit verify command; action completed cleanly")
                loop_log.append({
                    "iteration": i + 1, "action": "verify_pass",
                    "detail": "no explicit verify command; action completed cleanly",
                })
                return {"recovered": True, "exhausted": False,
                        "iterations": i + 1, "log": loop_log}
            _log_tier3_attempt(
                repo_root, wave_id, step, fc, i + 1,
                action, "failed", dur, explanation or "action did not complete cleanly")
            continue

        # Verify: re-run the failed gate/check if a verify command is provided
        if verify_command:
            try:
                verify_proc = subprocess.run(
                    verify_command, capture_output=True, text=True,
                    timeout=_SHELL_TIMEOUT, cwd=repo_root)
                if verify_proc.returncode == 0:
                    dur = round(time.monotonic() - iteration_t0, 3)
                    loop_log.append({
                        "iteration": i + 1, "action": "verify_pass",
                        "detail": "verification passed"})
                    _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                                       action, "success", dur, "verification passed")
                    return {"recovered": True, "exhausted": False,
                            "iterations": i + 1, "log": loop_log}
                # Update result with new error for next iteration
                result = dict(result)
                result["stderr"] = verify_proc.stderr
                result["stdout"] = verify_proc.stdout
            except (subprocess.TimeoutExpired, OSError):
                pass
        # Log iteration outcome (verify failed or no verify command)
        dur = round(time.monotonic() - iteration_t0, 3)
        _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                           action, "failed", dur, explanation)

    return {"recovered": False, "exhausted": True,
            "iterations": max_iterations, "log": loop_log}


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
    # Use executor name as fallback when step is missing — prevents
    # distinct timeout sites (e.g. phase_b_executor vs commit_executor)
    # from collapsing into the same (wave_id, "unknown", class) bucket
    # (Bridge R6 Finding 1 fix).
    step = result.get("step") or result.get("executor", "unknown")

    attempts = _load_recovery_log(repo_root)
    prior = _count_prior_attempts(attempts, wave_id, step, fc.value)

    if prior >= MAX_ATTEMPTS_PER_TUPLE:
        return _make_result(False, "exhausted", tier, fc,
                            f"max {MAX_ATTEMPTS_PER_TUPLE} attempts reached for "
                            f"({wave_id}, {step}, {fc.value})", True)
    if tier == 4:
        return _make_result(False, "escalate", 4, fc,
                            f"tier 4 failure ({fc.value}) requires escalation", False)
    if tier == 3:
        loop_result = run_recovery_loop(
            repo_root,
            {
                **result,
                "failure_class": fc.value,
                "tier": tier,
            },
            wave_id,
        )
        detail = f"tier 3 recovery loop ran {loop_result.get('iterations', 0)} iteration(s)"
        if loop_result.get("log"):
            last_entry = loop_result["log"][-1]
            if last_entry.get("detail"):
                detail = f"{detail}; {last_entry['detail']}"
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
                detail=fix_result.get("detail", ""))
            attempts.append(asdict(attempt_rec))
            _save_recovery_log(repo_root, attempts)
            return _make_result(fix_result.get("fixed", False),
                                fix_result.get("action", "unknown"), tier, fc,
                                fix_result.get("detail", ""), False)
        return _make_result(False, "no_fix_registered", tier, fc,
                            f"no tier 2 fix registered for {fc.value}", False)

    fix_fn = _TIER1_FIXES.get(fc)
    if fix_fn is None:
        return _make_result(False, "no_fix_registered", tier, fc,
                            f"no tier 1 fix registered for {fc.value}", False)

    fix_result = fix_fn(repo_root, wave_id=wave_id, result=result)
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
