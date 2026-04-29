#!/usr/bin/env python3
"""Pipeline recovery gate: failure classification and Tier 1–3 recovery.

Design doc: mu/docs/agents/PipelineRecovery.v0.md
Import constraints: stdlib + executor_common at module import time.
The hybrid Tier 3 implementer path lazy-loads phase_b_implementer at runtime.
"""
from __future__ import annotations

import atexit
import fcntl
import hashlib
import json
import os
import re
import shutil
import unicodedata
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Callable, NamedTuple, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import (
        emit_pipeline_agent_event,
        load_executor_config,
        load_routing_record,
        normalize_wave_id,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    emit_pipeline_agent_event = _mod.emit_pipeline_agent_event
    load_executor_config = _mod.load_executor_config
    load_routing_record = _mod.load_routing_record
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
    TRACKER_NOTE_CONTRACT = "tracker_note_contract"
    FEATURE_BRANCH_MISMATCH = "feature_branch_mismatch"
    MISSING_BRIDGE_CONFIG = "missing_bridge_config"
    POST_REENTRY_NEEDS_PHASE_B = "post_reentry_needs_phase_b"
    PHASE_B_PLAN_REQUIRED = "phase_b_plan_required"
    MISSING_PHASE_A_LOCK = "missing_phase_a_lock"
    # Tier 2 -- auto-retry with adjustment (zero tokens)
    PROCESS_TIMEOUT = "process_timeout"
    TRANSIENT_KILL = "transient_kill"
    UPSTREAM_CONNECTIVITY = "upstream_connectivity"
    AGGREGATION_HANG = "aggregation_hang"
    IMPLEMENTER_STALE = "implementer_stale"
    PR_MERGE_CONFLICT = "pr_merge_conflict"
    PR_CONFLICTING = "pr_conflicting"
    # Tier 3 -- LLM diagnosis (small focused prompt)
    GIT_STAGING_CONFLICT = "git_staging_conflict"
    TEST_FAILURE = "test_failure"
    AGENT_REVIEW_CRASH = "agent_review_crash"
    UNKNOWN_ERROR = "unknown_error"
    NEEDS_PHASE_B = "needs_phase_b"
    BOT_FINDINGS_PENDING = "bot_findings_pending"
    MAX_TURNS_REACHED = "max_turns_reached"
    PRE_PUSH_FAILED = "pre_push_failed"
    STAGE_FAILED = "stage_failed"
    IMPLEMENTER_ERROR = "implementer_error"
    BRIDGE_ERROR = "bridge_error"
    L4_CONTRACT_VIOLATION = "l4_contract_violation"
    # Tier 4 -- escalate (never recover)
    TERMINAL_POLICY = "terminal_policy"
    UNCLASSIFIED = "unclassified"

_TIER_MAP: dict[FailureClass, int] = {
    FailureClass.STALE_BRIDGE_LOCK: 1, FailureClass.STALE_GIT_INDEX_LOCK: 2,
    FailureClass.STALE_EXECUTOR_STATE: 1, FailureClass.STALE_CONTINUATION: 1,
    FailureClass.MIXED_STAGING: 1, FailureClass.TRACKER_NOTE_CONTRACT: 1,
    FailureClass.FEATURE_BRANCH_MISMATCH: 1,
    FailureClass.MISSING_BRIDGE_CONFIG: 1,
    FailureClass.POST_REENTRY_NEEDS_PHASE_B: 1,
    FailureClass.PHASE_B_PLAN_REQUIRED: 1,
    FailureClass.MISSING_PHASE_A_LOCK: 1,
    FailureClass.PROCESS_TIMEOUT: 2, FailureClass.TRANSIENT_KILL: 2,
    FailureClass.UPSTREAM_CONNECTIVITY: 2,
    FailureClass.AGGREGATION_HANG: 2, FailureClass.IMPLEMENTER_STALE: 2,
    FailureClass.PR_MERGE_CONFLICT: 2,
    FailureClass.PR_CONFLICTING: 2,
    FailureClass.GIT_STAGING_CONFLICT: 3, FailureClass.TEST_FAILURE: 3,
    FailureClass.AGENT_REVIEW_CRASH: 3, FailureClass.UNKNOWN_ERROR: 3,
    FailureClass.NEEDS_PHASE_B: 3,
    FailureClass.BOT_FINDINGS_PENDING: 3,
    FailureClass.MAX_TURNS_REACHED: 3,
    FailureClass.PRE_PUSH_FAILED: 3,
    FailureClass.STAGE_FAILED: 3,
    FailureClass.IMPLEMENTER_ERROR: 3,
    FailureClass.BRIDGE_ERROR: 3,
    FailureClass.L4_CONTRACT_VIOLATION: 3,
    FailureClass.TERMINAL_POLICY: 4, FailureClass.UNCLASSIFIED: 4,
}

_TERMINAL_STATUSES = frozenset({
    "question_for_founder", "max_rounds_reached",
    "supervisor_rejected",
})
_STANDALONE_STATUS_FAILURE_CLASSES: dict[str, FailureClass] = {
    "pre_push_failed": FailureClass.PRE_PUSH_FAILED,
    "stage_failed": FailureClass.STAGE_FAILED,
    "implementer_error": FailureClass.IMPLEMENTER_ERROR,
    "bridge_error": FailureClass.BRIDGE_ERROR,
    "l4_contract_violation": FailureClass.L4_CONTRACT_VIOLATION,
}
_TRANSIENT_KILL_CODES = frozenset({-9, -15, 137})
PHASE_B_RECOVERY_PLAN_ENV = "RCX_RECOVERY_PHASE_B_PLAN_PATH"
STALE_BRIDGE_LOCK_WAIT_TIMEOUT_S = 30.0
STALE_BRIDGE_LOCK_WAIT_POLL_S = 0.5
CONTROL_PLANE_PACKET_PREFIX = "reports/control_plane/"
_FEATURE_BRANCH_RE = re.compile(
    r"On branch (?P<current>[^,\n]+), expected (?P<base>\S+) or (?P<target>\S+)"
)


def tier_for(fc: FailureClass) -> int:
    """Return the recovery tier (1-4) for a failure class."""
    return _TIER_MAP[fc]


def _json_field_equals(value: Any, field_names: frozenset[str], expected: str) -> bool:
    """Return true when a nested JSON-like payload carries field == expected."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in field_names and str(item).strip() == expected:
                return True
            if _json_field_equals(item, field_names, expected):
                return True
    if isinstance(value, list):
        return any(_json_field_equals(item, field_names, expected) for item in value)
    return False


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

    if any(
        _json_field_equals(candidate, frozenset({"error_subtype", "subtype"}), "error_max_turns")
        for candidate in (result, embedded_stdout, embedded_stderr)
    ):
        return FailureClass.MAX_TURNS_REACHED

    status_key = str(status or embedded_status or "").strip().lower()
    if status_key in _STANDALONE_STATUS_FAILURE_CLASSES:
        return _STANDALONE_STATUS_FAILURE_CLASSES[status_key]

    # Tier 1: a post-reentry supervisor NEEDS_PHASE_B veto can deterministically
    # seed the in-branch re-entry checkpoint and retry Phase B without Tier 3.
    if _looks_like_post_reentry_needs_phase_b(result):
        return FailureClass.POST_REENTRY_NEEDS_PHASE_B

    if (
        status_failed
        and ("use --plan" in reason_lower or "use --plan" in combined_lower)
        and ("tracked packet" in reason_lower or "tracked packet" in combined_lower)
        and (
            "derive_planless_context" in step_lower
            or "planless mode" in reason_lower
            or "planless mode" in combined_lower
        )
    ):
        return FailureClass.PHASE_B_PLAN_REQUIRED

    # Tier 3: needs_phase_b is recoverable (retry Phase B)
    # Commit executor currently wraps a supervisor NEEDS_PHASE_B return as a
    # generic error payload whose reason begins with "Supervisor returned
    # NEEDS_PHASE_B". Recognize that structured reason so commit-side re-entry
    # routes back through Phase B instead of falling into stale-state recovery.
    if (
        status == "needs_phase_b"
        or embedded_status == "needs_phase_b"
        or (status_failed and "supervisor returned needs_phase_b" in reason_lower)
        or (status_failed and "supervisor returned needs_phase_b" in combined_lower)
    ):
        return FailureClass.NEEDS_PHASE_B

    # Tier 3: bot_findings_pending with P1 unresolved → re-invoke implementer
    if status == "bot_findings_pending" or embedded_status == "bot_findings_pending":
        return FailureClass.BOT_FINDINGS_PENDING

    stdout_lower = stdout.lower() if isinstance(stdout, str) else ""
    if status_failed and _looks_like_upstream_connectivity_failure(f"{combined_text}\n{reason_text}"):
        return FailureClass.UPSTREAM_CONNECTIVITY
    if (
        result.get("failure_class") == "pr_conflicting"
        or embedded_stdout.get("failure_class") == "pr_conflicting"
        or embedded_stderr.get("failure_class") == "pr_conflicting"
        or "mergeable=conflicting" in reason_lower
        or "mergeable=conflicting" in combined_lower
        or "mergeable=conflicting" in stdout_lower
        or "mergestatestatus=dirty" in reason_lower
        or "mergestatestatus=dirty" in combined_lower
        or "mergestatestatus=dirty" in stdout_lower
    ):
        return FailureClass.PR_CONFLICTING

    if status_failed and "merge_pr.sh failed" in reason_lower and (
        "not mergeable" in reason_lower
        or "cannot be cleanly created" in reason_lower
        or "merge conflict" in reason_lower
    ):
        return FailureClass.PR_MERGE_CONFLICT

    # Tier 1: deterministic lock/state issues
    if _looks_like_git_index_permission_failure(f"{combined_text}\n{reason_text}"):
        return FailureClass.UNCLASSIFIED
    if "bridge config not found" in reason_lower or "bridge config not found" in combined_lower:
        return FailureClass.MISSING_BRIDGE_CONFIG
    if "bridge.lock" in reason_lower or "bridge.lock" in combined_lower:
        return FailureClass.STALE_BRIDGE_LOCK
    if "index.lock" in reason_lower or "index.lock" in combined_lower:
        return FailureClass.STALE_GIT_INDEX_LOCK
    if "phase_b_state.json" in reason_lower or "phase_b_state.json" in combined_lower or "stale_state" in status:
        return FailureClass.STALE_EXECUTOR_STATE
    if (
        "stale continuation" in reason_lower
        or "continuation record is stale" in reason_lower
    ):
        return FailureClass.STALE_CONTINUATION
    if _looks_like_mixed_staging(result):
        return FailureClass.MIXED_STAGING
    if _looks_like_tracker_note_contract_mismatch(result):
        return FailureClass.TRACKER_NOTE_CONTRACT
    if _looks_like_feature_branch_mismatch(result):
        return FailureClass.FEATURE_BRANCH_MISMATCH
    if _looks_like_missing_phase_a_lock(result):
        return FailureClass.MISSING_PHASE_A_LOCK

    # Tier 2: transient / timeout issues
    if (
        status_failed
        and step_lower in ("bridge_subprocess", "reentry_bridge_subprocess")
        and ("timed out after" in reason_lower or "timed out after" in combined_lower)
    ):
        return FailureClass.PROCESS_TIMEOUT
    if status == "timeout":
        return FailureClass.PROCESS_TIMEOUT
    if exit_code is not None and exit_code in _TRANSIENT_KILL_CODES:
        return FailureClass.TRANSIENT_KILL
    if "aggregation" in combined_lower:
        return FailureClass.AGGREGATION_HANG
    if result.get("implementer_status") == "stale":
        return FailureClass.IMPLEMENTER_STALE

    # Tier 3: needs diagnosis
    staging_steps = {
        "stage_files",
        "git_commit",
        "staging",
        "bridge_staging",
        "reentry_bridge_staging",
        "reentry_staging",
    }
    structured_step_names = {
        str(candidate).strip().lower()
        for candidate in (step, embedded_step)
        if str(candidate or "").strip()
    }
    if structured_step_names.intersection(staging_steps) and (
        "git add" in combined_lower
        or "git add" in reason_lower
        or "failed to stage files" in combined_lower
        or "failed to stage files" in reason_lower
    ):
        return FailureClass.GIT_STAGING_CONFLICT
    fatal_codex_launch_hints = (
        "codex cannot access session files",
        "failed to create session",
        "missing bearer or basic authentication in header",
        "401 unauthorized",
    )
    if status_failed and any(
        hint in combined_lower or hint in reason_lower
        for hint in fatal_codex_launch_hints
    ):
        return FailureClass.UNCLASSIFIED
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


def _looks_like_mixed_staging(result: dict[str, Any]) -> bool:
    """Detect mixed staged/unstaged state from error signals.

    Structured non-staging commit failures must win over incidental raw stdout
    chatter. This keeps agent-stream text like "mixed staging state" from
    reclassifying a later `run_pre_push_script` failure as a staging defect.
    """
    stderr = str(result.get("stderr", "") or "")
    stdout = str(result.get("stdout", "") or "")
    step = str(result.get("step", "") or "")
    combined_lower = f"{stderr} {stdout}".lower()
    staging_steps = {
        "ensure_tracker_note",
        "stage_files",
        "collect_and_stage_indicator",
        "git_commit",
    }
    non_staging_commit_steps = {
        "validate_inputs",
        "ensure_feature_branch",
        "build_and_run_supervisor",
        "validate_receipt",
        "run_pre_commit_script",
        "hold_check",
        "run_pre_push_script",
        "git_push",
        "ensure_pr",
        "wait_ci",
        "ensure_review_clear_and_merge",
    }
    structured_steps = {
        str(candidate.get("step", "")).strip()
        for candidate in _extract_result_candidates(result)
        if candidate.get("step")
    }
    if step:
        structured_steps.add(step)
    if (
        structured_steps
        and structured_steps.isdisjoint(staging_steps)
        and not structured_steps.isdisjoint(non_staging_commit_steps)
    ):
        return False
    if "mixed" in combined_lower and "staging" in combined_lower:
        return True
    if step in ("stage_files", "git_commit"):
        for line in f"{stderr}\n{stdout}".splitlines():
            if len(line) >= 3 and line[2] == " ":
                if line[0] in "MADRCU" and line[1] in "MADRCU":
                    return True
    return False


def _extract_validation_errors(result: dict[str, Any]) -> list[str]:
    """Collect structured validation errors from the result and embedded JSON."""
    errors: list[str] = []
    for candidate in (
        result,
        _parse_json_object(result.get("stdout", "")),
        _parse_json_object(result.get("stderr", "")),
    ):
        if not isinstance(candidate, dict):
            continue
        raw_errors = candidate.get("errors")
        if not isinstance(raw_errors, list):
            continue
        for item in raw_errors:
            text = str(item).strip()
            if text:
                errors.append(text)
    return errors


def _looks_like_tracker_note_contract_mismatch(result: dict[str, Any]) -> bool:
    """Detect the commit validate_inputs tracker-note marker mismatch."""
    errors = _extract_validation_errors(result)
    if not errors:
        return False
    missing_markers = [
        text for text in errors
        if text.startswith("tracker_note_text missing required field marker:")
    ]
    if not missing_markers:
        return False
    missing_no_op = any("no_op_proof:" in text for text in missing_markers)
    missing_defer_reason = any("defer_reason_code:" in text for text in missing_markers)
    if not (missing_no_op and missing_defer_reason):
        return False
    steps = {
        str(candidate.get("step", "")).strip()
        for candidate in (
            result,
            _parse_json_object(result.get("stdout", "")),
            _parse_json_object(result.get("stderr", "")),
        )
        if isinstance(candidate, dict) and candidate.get("step")
    }
    return "validate_inputs" in steps or not steps


def _extract_result_candidates(result: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for candidate in (
        result,
        _parse_json_object(result.get("stdout", "")),
        _parse_json_object(result.get("stderr", "")),
    ):
        if isinstance(candidate, dict):
            candidates.append(candidate)
    return candidates


def _merge_result_candidates(result: dict[str, Any]) -> dict[str, Any]:
    """Merge outer executor wrapper state with embedded structured payloads."""
    merged: dict[str, Any] = {}
    for candidate in _extract_result_candidates(result):
        for key, value in candidate.items():
            if value in (None, ""):
                continue
            merged[key] = value
    return merged


def _effective_result_step(result: dict[str, Any]) -> str:
    for candidate in _extract_result_candidates(result):
        step = str(candidate.get("step", "")).strip()
        if step:
            return step
    for candidate in _extract_result_candidates(result):
        executor = str(candidate.get("executor", "")).strip()
        if executor:
            return executor
    return "unknown"


def _extract_feature_branch_expectation(result: dict[str, Any]) -> dict[str, str] | None:
    combined_parts: list[str] = []
    reason_text = _summarize_result_reason(result)
    if reason_text:
        combined_parts.append(reason_text)
    for candidate in _extract_result_candidates(result):
        for key in ("error", "detail", "message", "stderr", "stdout"):
            value = candidate.get(key)
            excerpt = _summarize_json_value(value)
            if excerpt:
                combined_parts.append(excerpt)
        errors = candidate.get("errors")
        if isinstance(errors, list):
            combined_parts.extend(str(item) for item in errors if isinstance(item, str))
    combined_text = "\n".join(combined_parts)
    match = _FEATURE_BRANCH_RE.search(combined_text)
    if not match:
        return None
    return {key: match.group(key).strip() for key in ("current", "base", "target")}


def _looks_like_feature_branch_mismatch(result: dict[str, Any]) -> bool:
    expectation = _extract_feature_branch_expectation(result)
    if expectation is None:
        return False
    steps = {
        str(candidate.get("step", "")).strip()
        for candidate in _extract_result_candidates(result)
        if candidate.get("step")
    }
    return "ensure_feature_branch" in steps or not steps

def _looks_like_post_reentry_needs_phase_b(result: dict[str, Any]) -> bool:
    candidates = _extract_result_candidates(result)
    reason_lower = " ".join(
        part
        for part in (
            _summarize_result_reason(result),
            *(_summarize_json_value(candidate) for candidate in candidates),
        )
        if part
    ).lower()
    candidate_steps = {
        str(candidate.get("step", "") or "").strip().lower()
        for candidate in candidates
        if str(candidate.get("step", "") or "").strip()
    }
    candidate_statuses = {
        str(candidate.get("status", "") or "").strip().lower()
        for candidate in candidates
        if str(candidate.get("status", "") or "").strip()
    }
    if "supervisor returned needs_phase_b" not in reason_lower:
        return (
            "needs_phase_b" in candidate_statuses
            and "post_reentry_supervisor" in candidate_steps
        )
    if "after reentry convergence" in reason_lower:
        return True
    return "post_reentry_supervisor" in candidate_steps


def _looks_like_upstream_connectivity_failure(detail: str) -> bool:
    """Detect transient Codex/OpenAI transport failures, excluding auth/session defects."""
    lowered = str(detail or "").lower()
    if not lowered:
        return False
    terminal_hints = (
        "401 unauthorized",
        "missing bearer or basic authentication",
        "codex cannot access session files",
        "failed to initialize rollout recorder",
    )
    if any(hint in lowered for hint in terminal_hints):
        return False
    upstream_hints = (
        "failed to lookup address information",
        "nodename nor servname provided",
        "temporary failure in name resolution",
    )
    if any(hint in lowered for hint in upstream_hints):
        return True
    if "responses_websocket" in lowered and "failed to connect to websocket" in lowered:
        return True
    if (
        "stream disconnected before completion" in lowered
        and "error sending request for url" in lowered
        and ("backend-api/codex" in lowered or "/v1/responses" in lowered)
    ):
        return True
    return False


def _looks_like_git_index_permission_failure(detail: str) -> bool:
    lowered = str(detail or "").lower()
    if "index.lock" not in lowered:
        return False
    if "operation not permitted" not in lowered and "permission denied" not in lowered:
        return False
    return "unable to create" in lowered or "could not create" in lowered


def _looks_like_missing_phase_a_lock(result: dict[str, Any]) -> bool:
    errors = _extract_validation_errors(result)
    if not errors:
        return False
    missing_lock = any(
        re.fullmatch(
            r"validate_inputs fatal: Plan Phase-A-Lock must be LOCKED "
            r"\(or ROUTING_RECORD_AUTHORITY for planless\), got",
            text,
        )
        for text in errors
    )
    if not missing_lock:
        return False
    steps = {
        str(candidate.get("step", "")).strip()
        for candidate in _extract_result_candidates(result)
        if candidate.get("step")
    }
    return "validate_inputs" in steps or not steps


def _extract_plan_path(result: dict[str, Any]) -> str:
    for candidate in _extract_result_candidates(result):
        plan_path = str(candidate.get("plan_path", "") or "").strip()
        if plan_path:
            return plan_path
    return ""


def _normalize_phase_a_lock_repair_packet_path(plan_path: str) -> str | None:
    candidate = str(plan_path or "").strip().replace("\\", "/")
    if not candidate:
        return None
    while candidate.startswith("./"):
        candidate = candidate[2:]
    if candidate.startswith("/"):
        return None

    parts: list[str] = []
    for part in PurePosixPath(candidate).parts:
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    if not parts:
        return None

    normalized = PurePosixPath(*parts).as_posix()
    path = PurePosixPath(normalized)
    if path.parent.as_posix() != CONTROL_PLANE_PACKET_PREFIX.rstrip("/"):
        return None
    if path.suffix != ".md":
        return None
    return normalized


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
    deadline = time.monotonic() + STALE_BRIDGE_LOCK_WAIT_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(STALE_BRIDGE_LOCK_WAIT_POLL_S)
        if _claim_and_remove_bridge_lock(lock_path):
            return _fix_result(
                True,
                "wait_and_remove_stale_lock",
                "bridge.lock released during bounded wait and was atomically removed",
            )
    return _fix_result(False, "noop",
                       "bridge.lock held by a live flock after bounded wait — cannot remove")


def fix_missing_phase_a_lock(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Repair a missing Phase-A-Lock header on a Phase B control-plane packet.

    This is intentionally narrow: it only repairs packets where the parsed
    Phase-A-Lock is absent. If the packet already declares UNLOCKED or any
    other non-empty value, recovery must not auto-upgrade it.
    """
    result = kw.get("result", {}) or {}
    plan_path = _extract_plan_path(result)
    if not plan_path:
        return _fix_result(
            False,
            "plan_path_missing",
            "missing Phase-A-Lock repair needs plan_path from the executor result",
        )

    repo_root_resolved = repo_root.resolve()
    normalized_plan_path = _normalize_phase_a_lock_repair_packet_path(plan_path)
    if normalized_plan_path is None:
        return _fix_result(
            False,
            "non_packet_plan_path",
            "missing Phase-A-Lock repair only applies to "
            f"{CONTROL_PLANE_PACKET_PREFIX}*.md packets: {plan_path}",
        )
    plan_path = normalized_plan_path

    try:
        plan_file = (repo_root / plan_path).resolve()
        plan_file.relative_to(repo_root_resolved)
        plan_file.relative_to((repo_root / CONTROL_PLANE_PACKET_PREFIX).resolve())
    except ValueError:
        return _fix_result(False, "unsafe_plan_path", f"unsafe plan_path outside repo: {plan_path}")
    if not plan_file.is_file():
        return _fix_result(False, "plan_missing", f"plan packet not found: {plan_path}")

    try:
        phase_a_mod = _load_executor_module_from_repo(repo_root, "phase_a_executor")
        phase_b_mod = _load_executor_module_from_repo(repo_root, "phase_b_executor")
    except Exception as exc:
        return _fix_result(False, "module_load_failed", f"could not load plan helpers: {exc}")

    try:
        plan = phase_b_mod.load_plan_packet(repo_root, plan_path)
    except Exception as exc:
        return _fix_result(False, "plan_parse_failed", f"could not parse plan packet: {exc}")

    phase_a_lock = str(plan.get("phase_a_lock", "") or "").strip()
    if phase_a_lock:
        return _fix_result(
            False,
            "phase_a_lock_present",
            f"{plan_path} already declares Phase-A-Lock: {phase_a_lock}; requires explicit Phase A or packet repair",
        )

    lock_path = repo_root / ".agent_bus" / "bridge.lock"
    lock_detail = ""
    if lock_path.exists():
        if not _claim_and_remove_bridge_lock(lock_path):
            return _fix_result(
                False,
                "bridge_lock_live",
                "bridge.lock is still held by a live flock — cannot safely retry after repairing Phase-A-Lock",
            )
        lock_detail = " + cleared stale bridge.lock"

    try:
        phase_a_mod.lock_plan(repo_root, plan_path)
        repaired = phase_b_mod.load_plan_packet(repo_root, plan_path)
    except Exception as exc:
        return _fix_result(False, "lock_repair_failed", f"could not repair Phase-A-Lock: {exc}")

    if str(repaired.get("phase_a_lock", "") or "").strip() != "LOCKED":
        return _fix_result(
            False,
            "lock_repair_failed",
            f"{plan_path} did not converge to Phase-A-Lock: LOCKED after repair",
        )

    return _fix_result(
        True,
        "repair_missing_phase_a_lock",
        f"inserted and locked missing Phase-A-Lock in {plan_path}{lock_detail}",
    )


def fix_stale_git_index_lock(repo_root: Path) -> dict[str, Any]:
    """Recover only index.lock cases that have already self-cleared.

    Existing lock files still fail closed because no sound ownership check
    proves stale vs. live. If the failure text named index.lock but the lock is
    gone by recovery time, the safest zero-mutation action is to grant a retry.
    """
    lock_path = repo_root / ".git" / "index.lock"
    if not lock_path.exists():
        return _fix_result(
            True,
            "transient_index_lock_released",
            "index.lock not found after index.lock failure; retry without deleting",
        )
    return _fix_result(False, "demoted_to_tier2",
                       "index.lock exists but Tier 1 auto-fix disabled — "
                       "no sound ownership check to prove lock is stale")


def fix_missing_bridge_config(repo_root: Path) -> dict[str, Any]:
    """Self-heal missing .agent_bus/bridge_config.json in a linked worktree.

    Phase B, recovery_gate, and bot_remediation all invoke LLM adapters via
    bridge_adapters.load_bridge_config, which raises if the config file is
    missing. commit_executor step-15 has an auto-heal for the same file, but
    phase_b and recovery_gate don't — leaving a chicken-and-egg where
    recovery can't fix the very infrastructure it needs to run an LLM.

    This Tier 1 fixer is deterministic (no LLM) and mirrors the commit_executor
    auto-heal: locate the main repo via the worktree's .git file pointer and
    copy its bridge_config.json into the worktree's .agent_bus/ directory.

    Returns a noop result if the file already exists, or an error if the main
    repo can't be located / its copy is missing.
    """
    import shutil

    dst = repo_root / ".agent_bus" / "bridge_config.json"
    if dst.exists():
        return _fix_result(False, "noop", f"bridge_config.json already present at {dst}")

    git_pointer = repo_root / ".git"
    if not git_pointer.is_file():
        return _fix_result(
            False, "noop",
            f"{repo_root}/.git is not a worktree pointer file; cannot derive main repo",
        )

    try:
        content = git_pointer.read_text(encoding="utf-8").strip()
        if not content.startswith("gitdir:"):
            return _fix_result(
                False, "error",
                f"unexpected .git file content (no 'gitdir:' prefix): {content[:80]}",
            )
        gitdir_str = content.split("gitdir:", 1)[1].strip()
        if not gitdir_str:
            return _fix_result(
                False, "error",
                "empty gitdir value in .git pointer file",
            )
        gitdir = Path(gitdir_str)
        # Per gitfile(5), gitdir may be absolute or relative; relative paths
        # are resolved against the gitfile's parent (the worktree root), not
        # the process CWD. Normalize before taking parents so any '..'
        # segments collapse into a clean absolute path.
        if not gitdir.is_absolute():
            gitdir = repo_root / gitdir
        gitdir = gitdir.resolve()
        # gitdir = <main_repo>/.git/worktrees/<name>
        # main_repo = gitdir.parent.parent.parent
        main_repo = gitdir.parent.parent.parent
    except Exception as exc:
        return _fix_result(False, "error", f"failed to resolve main repo from .git pointer: {exc}")

    src = main_repo / ".agent_bus" / "bridge_config.json"
    if not src.exists():
        return _fix_result(
            False, "error",
            f"main repo at {main_repo} has no .agent_bus/bridge_config.json to copy",
        )

    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    except Exception as exc:
        return _fix_result(False, "error", f"copy from {src} to {dst} failed: {exc}")

    return _fix_result(
        True, "copy_bridge_config_from_main_repo",
        f"copied bridge_config.json from {src} to {dst}",
    )


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


def _load_executor_module_from_repo(repo_root: Path, module_name: str) -> Any:
    """Load an executor helper module from the current repo on demand."""
    executors_dir = repo_root / "mu" / "tools" / "executors"
    module_path = executors_dir / f"{module_name}.py"
    if not module_path.is_file():
        raise ImportError(f"{module_name} not found at {module_path}")

    import importlib.util as _ilu

    module_key = (
        f"_rcx_recovery_{module_name}_"
        f"{hashlib.sha256(str(module_path.resolve()).encode('utf-8')).hexdigest()[:12]}"
    )
    spec = _ilu.spec_from_file_location(module_key, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load spec for {module_name} from {module_path}")

    old_sys_path = list(sys.path)
    if str(executors_dir) not in sys.path:
        sys.path.insert(0, str(executors_dir))
    module = _ilu.module_from_spec(spec)
    sys.modules[module_key] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = old_sys_path
        sys.modules.pop(module_key, None)
    return module


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item).strip() for item in value if str(item).strip()})


def _bridge_scope_fingerprint_for_files(repo_root: Path, files: list[str]) -> str:
    digest = hashlib.sha256()
    for rel_path in sorted(files):
        digest.update(b"\0path\0")
        digest.update(rel_path.encode("utf-8", errors="surrogatepass"))
        full_path = repo_root / rel_path
        if not full_path.exists():
            digest.update(b"\0missing")
            continue
        digest.update(b"\0present\0")
        digest.update(full_path.read_bytes())
    return digest.hexdigest()


def _post_reentry_scope_files(repo_root: Path, result: dict[str, Any], plan_path: str) -> list[str]:
    explicit_files = _coerce_string_list(result.get("changed_files"))
    if explicit_files:
        return explicit_files
    try:
        phase_b_mod = _load_executor_module_from_repo(repo_root, "phase_b_executor")
        plan_declared_files = _coerce_string_list(result.get("plan_declared_files"))
        if not plan_declared_files and plan_path:
            try:
                plan_file = (repo_root / plan_path).resolve()
                plan_file.relative_to(repo_root.resolve())
                if plan_file.is_file() and hasattr(phase_b_mod, "_parse_plan_declared_files"):
                    plan_declared_files = _coerce_string_list(
                        phase_b_mod._parse_plan_declared_files(  # ANTICHEAT_OK: recovery mirrors Phase B scope parsing
                            plan_file.read_text(encoding="utf-8")
                        )
                    )
            except (OSError, ValueError):
                plan_declared_files = []
        return phase_b_mod._collect_wave_owned_files(  # ANTICHEAT_OK: recovery seeds the exact Phase B resume scope
            repo_root,
            plan_path,
            plan_declared_files or None,
            set(_coerce_string_list(result.get("implementer_changed"))) or None,
            set(_coerce_string_list(result.get("executor_created"))) or None,
            set(_coerce_string_list(result.get("baseline_wave_files"))) or None,
        )
    except Exception:
        return []


def fix_tracker_note_contract(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Regenerate a canonical MAINTENANCE tracker note for a Phase B handoff."""
    handoff_path = repo_root / ".agent_bus" / "executors" / "phase_b_handoff.json"
    if not handoff_path.exists():
        return _fix_result(False, "handoff_missing", f"handoff file missing at {handoff_path}")

    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _fix_result(False, "handoff_invalid", f"could not read handoff JSON: {exc}")
    if not isinstance(handoff, dict):
        return _fix_result(False, "handoff_invalid", "handoff payload was not a JSON object")
    if str(handoff.get("caller", "")).strip() != "phase_b":
        return _fix_result(False, "unsupported_caller", "tracker-note repair only supports Phase B handoffs")
    if str(handoff.get("wave_class", "")).strip() != "MAINTENANCE":
        return _fix_result(False, "unsupported_wave_class", "tracker-note repair only supports MAINTENANCE handoffs")

    try:
        phase_b_mod = _load_executor_module_from_repo(repo_root, "phase_b_executor")
        commit_mod = _load_executor_module_from_repo(repo_root, "commit_executor")
    except Exception as exc:
        return _fix_result(False, "module_load_failed", f"could not load executor helpers: {exc}")

    files_to_stage = [
        str(path).strip()
        for path in handoff.get("files_to_stage", [])
        if str(path).strip()
    ]
    test_files = [
        path for path in files_to_stage
        if path.startswith("mu/tests/") or "/test_" in path or path.endswith("_test.py")
    ]
    scope_items = handoff.get("scope_items", [])
    plan_path = next(
        (str(item).strip() for item in scope_items if str(item).strip()),
        "<phase-b-plan-unavailable>",
    )
    plan_content = ""
    if plan_path != "<phase-b-plan-unavailable>":
        try:
            plan_file = (repo_root / plan_path).resolve()
            plan_file.relative_to(repo_root.resolve())
            if plan_file.is_file():
                plan_content = plan_file.read_text(encoding="utf-8")
        except (OSError, ValueError):
            plan_content = ""
    bridge_status = handoff.get("bridge_status", {})
    if not isinstance(bridge_status, dict):
        bridge_status = {}
    try:
        tracker_note_text = phase_b_mod._build_phase_b_tracker_note(  # ANTICHEAT_OK: recovery reuses the Phase B tracker-note generator
            wave_id=str(handoff.get("wave_id", "")).strip(),
            task_id=str(handoff.get("task_id", "")).strip() or "[PIPELINE-RECOVERY]",
            wave_class="MAINTENANCE",
            target_gate_id=str(handoff.get("target_gate_id", "G8")).strip() or "G8",
            plan_path=plan_path,
            plan_content=plan_content,
            changed_files=files_to_stage,
            test_files=test_files,
            receipt_path=str(handoff.get("pre_commit_receipt_path", "")).strip(),
            bridge_rounds=int(bridge_status.get("rounds", 0) or 0),
            reentry=bool(bridge_status.get("reentry")),
        )
    except Exception as exc:
        return _fix_result(False, "note_rebuild_failed", f"could not rebuild tracker note: {exc}")

    repaired_handoff = dict(handoff)
    repaired_handoff["tracker_note_text"] = tracker_note_text
    valid, errors = commit_mod.validate_handoff(repaired_handoff)
    if not valid:
        return _fix_result(
            False,
            "repaired_handoff_invalid",
            "rebuilt tracker note still failed validation: " + "; ".join(errors[:5]),
        )

    try:
        handoff_path.write_text(json.dumps(repaired_handoff, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return _fix_result(False, "handoff_write_failed", f"could not rewrite handoff JSON: {exc}")

    return _fix_result(
        True,
        "rebuild_phase_b_handoff_tracker_note",
        f"rewrote tracker_note_text in {handoff_path} using the Phase B MAINTENANCE tracker-note generator",
    )


def fix_feature_branch_mismatch(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Move the worktree onto the canonical target branch for the active handoff."""
    result = kw.get("result", {})
    expectation = _extract_feature_branch_expectation(result)
    handoff_path = repo_root / ".agent_bus" / "executors" / "phase_b_handoff.json"
    if not handoff_path.exists():
        return _fix_result(False, "handoff_missing", f"handoff file missing at {handoff_path}")
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return _fix_result(False, "handoff_invalid", f"could not read handoff JSON: {exc}")
    if not isinstance(handoff, dict):
        return _fix_result(False, "handoff_invalid", "handoff payload was not a JSON object")

    wave_id = str(handoff.get("wave_id", "")).strip()
    branch_prefix = str(handoff.get("branch_prefix", "")).strip()
    base_branch = str(handoff.get("base_branch", "")).strip()
    if not wave_id or not branch_prefix or not base_branch:
        return _fix_result(
            False,
            "handoff_missing_branch_fields",
            "handoff missing wave_id, branch_prefix, or base_branch",
        )
    explicit_target_branch = str(handoff.get("target_branch", "")).strip()
    target_branch = explicit_target_branch or f"{branch_prefix}/{wave_id}"

    if expectation is not None:
        if expectation["base"] != base_branch or expectation["target"] != target_branch:
            return _fix_result(
                False,
                "branch_contract_mismatch",
                f"handoff expects {base_branch} or {target_branch}, but failure text expected "
                f"{expectation['base']} or {expectation['target']}",
            )

    try:
        current_proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "current_branch_failed", f"git rev-parse HEAD failed: {exc}")
    if current_proc.returncode != 0:
        detail = (current_proc.stderr or current_proc.stdout or "").strip()
        return _fix_result(False, "current_branch_failed", detail or "git rev-parse HEAD failed")
    current_branch = current_proc.stdout.strip()

    if current_branch == target_branch:
        return _fix_result(True, "already_on_target_branch", f"already on {target_branch}")

    try:
        local_check = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{target_branch}"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "target_branch_probe_failed", f"git rev-parse target branch failed: {exc}")
    local_target_exists = local_check.returncode == 0

    try:
        remote_check = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", target_branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "target_branch_probe_failed", f"git ls-remote target branch failed: {exc}")
    remote_target_exists = bool(remote_check.stdout.strip())

    if local_target_exists or remote_target_exists:
        collisions: list[str] = []
        if local_target_exists:
            collisions.append(f"local branch {target_branch}")
        if remote_target_exists:
            collisions.append(f"remote branch origin/{target_branch}")
        collision_text = " and ".join(collisions)
        return _fix_result(
            False,
            "target_branch_collision",
            f"refusing to switch from {current_branch} to {target_branch}: {collision_text} already exists; "
            "feature-branch recovery must fail closed on branch collisions",
        )

    checkout_cmd = ["git", "checkout", "-b", target_branch, base_branch]

    try:
        checkout_proc = subprocess.run(
            checkout_cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return _fix_result(False, "branch_switch_failed", f"{' '.join(checkout_cmd)} failed: {exc}")
    if checkout_proc.returncode != 0:
        detail = (checkout_proc.stderr or checkout_proc.stdout or "").strip()
        return _fix_result(
            False,
            "branch_switch_failed",
            detail or f"{' '.join(checkout_cmd)} returned {checkout_proc.returncode}",
        )

    detail = f"created canonical target branch {target_branch} from {base_branch} and preserved the worktree"
    return _fix_result(True, "create_expected_feature_branch", detail)


def fix_post_reentry_needs_phase_b(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Resume the deterministic Phase B re-entry path after a post-reentry veto."""
    result = kw.get("result", {})
    result_payload = _merge_result_candidates(result)
    plan_path = _extract_plan_path(result_payload)
    if not plan_path:
        return _fix_result(
            False,
            "missing_plan_path",
            "post-reentry NEEDS_PHASE_B result missing plan_path",
        )

    wave_hint = str(result_payload.get("wave_id") or Path(plan_path).stem or "wave-unknown").strip()
    bridge_rounds_raw = result_payload.get("bridge_rounds", 0)
    try:
        bridge_rounds = int(bridge_rounds_raw or 0)
    except (TypeError, ValueError):
        bridge_rounds = 0

    findings = str(
        result_payload.get("pre_commit_summary")
        or _summarize_result_reason(result_payload)
        or _summarize_result_reason(result)
        or "Fix required"
    ).strip()

    resume_state: dict[str, Any] = {
        "plan_path": plan_path,
        "completed_step": "needs_phase_b_reentry",
        "wave_id": normalize_wave_id(wave_hint),
        "bridge_rounds": bridge_rounds,
        "reentry_findings": findings,
    }
    scope_files = _post_reentry_scope_files(repo_root, result_payload, plan_path)
    scope_fingerprint = str(result_payload.get("bridge_scope_fingerprint") or "").strip()
    if not scope_fingerprint:
        scope_fingerprint = _bridge_scope_fingerprint_for_files(repo_root, scope_files)
    resume_state["bridge_scope_fingerprint"] = scope_fingerprint
    if scope_files:
        resume_state["changed_files"] = scope_files

    for list_key in ("implementer_changed", "executor_created", "baseline_wave_files"):
        list_value = _coerce_string_list(result_payload.get(list_key))
        if list_value:
            resume_state[list_key] = list_value
    if scope_files and not resume_state.get("baseline_wave_files"):
        resume_state["baseline_wave_files"] = scope_files
    all_non_blocking = result_payload.get("all_non_blocking")
    if isinstance(all_non_blocking, list):
        resume_state["all_non_blocking"] = all_non_blocking
    finding_history = result_payload.get("finding_history")
    if isinstance(finding_history, dict):
        resume_state["finding_history"] = finding_history

    deferred_packet_path = str(result_payload.get("deferred_packet_path") or "").strip()
    if deferred_packet_path:
        resume_state["deferred_packet_path"] = deferred_packet_path

    state_path = repo_root / ".agent_bus" / "executors" / "phase_b_state.json"
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(resume_state, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        return _fix_result(
            False,
            "phase_b_state_write_failed",
            f"could not seed {state_path}: {exc}",
        )

    return _fix_result(
        True,
        "resume_phase_b_reentry",
        f"seeded {state_path} so dispatcher retry resumes NEEDS_PHASE_B re-entry for {plan_path}",
    )


def _phase_b_plan_required_path(result: dict[str, Any]) -> str:
    plan_path = str(result.get("plan_path") or "").strip()
    if plan_path:
        return plan_path

    candidates = [
        _summarize_result_reason(result),
        str(result.get("stdout") or ""),
        str(result.get("stderr") or ""),
        _summarize_json_value(_parse_json_object(result.get("stdout", ""))),
        _summarize_json_value(_parse_json_object(result.get("stderr", ""))),
    ]
    for text in candidates:
        match = re.search(r"\bUse\s+--plan\s+([^\s]+)", text or "", flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".,;:")
    return ""


def fix_phase_b_plan_required(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Let dispatcher retry Phase B with --plan after a planless tracked-packet stop."""
    result = kw.get("result", {})
    plan_path = _phase_b_plan_required_path(result)
    if not plan_path:
        try:
            plan_path = _routing_plan_path(load_routing_record(repo_root))
        except Exception:
            plan_path = ""
    if not plan_path:
        return _fix_result(
            False,
            "missing_plan_path",
            "phase_b plan-required recovery could not resolve a tracked packet path",
        )
    resolved = repo_root / plan_path
    if not resolved.exists():
        return _fix_result(
            False,
            "missing_plan_file",
            f"tracked packet {plan_path} does not exist for dispatcher retry",
        )
    os.environ[PHASE_B_RECOVERY_PLAN_ENV] = plan_path
    return _fix_result(
        True,
        "retry_phase_b_with_plan",
        f"dispatcher retry will relaunch Phase B with --plan {plan_path}",
    )


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
    FailureClass.TRACKER_NOTE_CONTRACT: fix_tracker_note_contract,
    FailureClass.FEATURE_BRANCH_MISMATCH: fix_feature_branch_mismatch,
    FailureClass.MISSING_BRIDGE_CONFIG: lambda root, **kw: fix_missing_bridge_config(root),
    FailureClass.POST_REENTRY_NEEDS_PHASE_B: fix_post_reentry_needs_phase_b,
    FailureClass.PHASE_B_PLAN_REQUIRED: fix_phase_b_plan_required,
    FailureClass.MISSING_PHASE_A_LOCK: fix_missing_phase_a_lock,
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


def _load_config_bridge_turn_timeouts(repo_root: Path) -> dict[str, Any]:
    """Load bridge_turn_timeouts dict from executor_config.json (read-only)."""
    config_path = repo_root / _CONFIG_PATH_REL
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        return cfg.get("bridge_turn_timeouts", {})
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
    bridge_turn_timeouts = _load_config_bridge_turn_timeouts(repo_root)
    # Determine which executor timed out from the result
    result = kw.get("result", {})
    executor = result.get("executor", "phase_b_executor")
    timeout_key = executor if executor in timeouts else "phase_b_executor"
    step = _effective_result_step(result).lower()
    bridge_turn_key = "phase_b" if step in ("bridge_subprocess", "reentry_bridge_subprocess") else ""

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
    if bridge_turn_key:
        current = int(bridge_turn_timeouts.get(bridge_turn_key, 300))
        baseline_env_key = (
            f"RCX_RECOVERY_ORIGINAL_BRIDGE_TURN_TIMEOUT_{bridge_turn_key}"
        )
        stored_baseline = os.environ.get(baseline_env_key)
        if stored_baseline is not None:
            baseline = int(stored_baseline)
        else:
            baseline = current
            os.environ[baseline_env_key] = str(baseline)
        new_timeout = min(int(current * 1.5), baseline * 2)
        os.environ["RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE"] = str(new_timeout)
        os.environ["RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY"] = bridge_turn_key
        target_label = f"bridge_turn_timeouts.{bridge_turn_key}"
        override_label = "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE"
    else:
        current = int(timeouts.get(timeout_key, 3600))
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
        target_label = timeout_key
        override_label = "RCX_RECOVERY_TIMEOUT_OVERRIDE"
    lock_msg = " + bridge.lock cleared" if lock_cleared else ""
    return _fix_result(True, "increase_timeout",
                       f"timeout for {target_label} increased from {current}s "
                       f"to {new_timeout}s (capped at 2x original {baseline}s) "
                       f"via {override_label}{lock_msg}")


def fix_transient_kill(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """No-op fix — marks as retryable. Dispatcher already retries."""
    return _fix_result(True, "retryable",
                       "transient kill — safe to retry with same parameters")


def fix_upstream_connectivity(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Mark external Codex/network failures as retryable without Tier 3."""
    os.environ["RCX_RECOVERY_UPSTREAM_CONNECTIVITY_RETRY"] = "1"
    return _fix_result(
        True,
        "retry_upstream_connectivity",
        "upstream Codex connectivity failed — retrying the failed pipeline step without invoking Tier 3 recovery",
    )


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


def _extract_branch_context_field(result: dict[str, Any], field: str) -> str:
    for candidate in (
        result,
        _parse_json_object(result.get("stdout", "")),
        _parse_json_object(result.get("stderr", "")),
    ):
        if not isinstance(candidate, dict):
            continue
        value = candidate.get(field)
        if isinstance(value, str):
            stripped = value.strip()
            if stripped:
                return stripped
    return ""


def fix_pr_conflicting(repo_root: Path, **kw: Any) -> dict[str, Any]:
    """Delegate to commit_executor._try_auto_resolve_pr_conflict on CONFLICTING/DIRTY PRs.

    Widens the Step 14 auto-resolve recipe beyond its original call site so
    any recovery-gate path can reach it. Preconditions (clean worktree +
    resolved branch context) fail-close before the mutating helper runs.
    """
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
    except (subprocess.SubprocessError, OSError) as exc:
        return _fix_result(False, "status_failed", f"git status failed: {exc}")
    if status_proc.returncode != 0:
        return _fix_result(False, "status_failed", f"git status returned {status_proc.returncode}")
    if status_proc.stdout.strip():
        return _fix_result(
            False, "dirty_worktree", "worktree is not clean enough for auto-resolve"
        )

    base_branch = _extract_branch_context_field(result, "base_branch")
    branch_name = _extract_branch_context_field(result, "branch_name")
    if not (base_branch and branch_name):
        try:
            pr_view = subprocess.run(
                ["gh", "pr", "view", pr_number, "--json", "baseRefName,headRefName"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            return _fix_result(False, "pr_view_failed", f"gh pr view failed: {exc}")
        if pr_view.returncode != 0:
            detail = (pr_view.stderr or pr_view.stdout or "").strip()
            return _fix_result(
                False, "pr_view_failed",
                detail or f"gh pr view returned {pr_view.returncode}",
            )
        try:
            pr_payload = json.loads(pr_view.stdout or "{}")
        except json.JSONDecodeError as exc:
            return _fix_result(False, "pr_view_failed", f"gh pr view returned invalid JSON: {exc}")
        if not isinstance(pr_payload, dict):
            return _fix_result(False, "pr_view_failed", "gh pr view payload was not an object")
        if not base_branch:
            base_branch = str(pr_payload.get("baseRefName", "")).strip()
        if not branch_name:
            branch_name = str(pr_payload.get("headRefName", "")).strip()

    if not (base_branch and branch_name):
        return _fix_result(
            False, "missing_branch_context",
            f"PR #{pr_number} missing baseRefName or headRefName",
        )

    # HEAD-matches-branch_name guard. The helper at
    # commit_executor._try_auto_resolve_pr_conflict merges origin/<base_branch>
    # into implicit HEAD, then pushes `branch_name` explicitly. If HEAD is on a
    # different branch, the merge commit lands on the wrong branch while the
    # push reports success on the unchanged branch_name — a wrong-branch
    # mutation with success-reporting. The Step 14 call site is safe because
    # the pipeline has just pushed the feature branch, so HEAD is implicitly
    # aligned. Any widened recovery entrypoint must prove HEAD == branch_name
    # before delegating.
    try:
        head_proc = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        return _fix_result(
            False, "current_branch_failed", f"git rev-parse HEAD failed: {exc}"
        )
    if head_proc.returncode != 0:
        detail = (head_proc.stderr or head_proc.stdout or "").strip()
        return _fix_result(
            False, "current_branch_failed",
            detail or f"git rev-parse HEAD returned {head_proc.returncode}",
        )
    current_branch = head_proc.stdout.strip()
    if current_branch != branch_name:
        return _fix_result(
            False, "branch_mismatch",
            f"HEAD on {current_branch!r}, expected PR head {branch_name!r}; "
            "refusing to auto-resolve on the wrong branch",
        )

    try:
        commit_mod = _load_executor_module_from_repo(repo_root, "commit_executor")
    except Exception as exc:
        return _fix_result(False, "module_load_failed", f"could not load commit_executor: {exc}")

    helper = commit_mod._try_auto_resolve_pr_conflict(
        repo_root,
        pr_number=pr_number,
        base_branch=base_branch,
        branch_name=branch_name,
        log=None,
    )
    return _fix_result(
        fixed=bool(helper.get("resolved")),
        action=str(helper.get("action", "unknown")),
        detail=str(helper.get("detail", "")),
    )


_TIER2_FIXES: dict[FailureClass, Any] = {
    FailureClass.STALE_GIT_INDEX_LOCK: lambda root, **kw: fix_stale_git_index_lock(root),
    FailureClass.PROCESS_TIMEOUT: fix_process_timeout,
    FailureClass.TRANSIENT_KILL: fix_transient_kill,
    FailureClass.UPSTREAM_CONNECTIVITY: fix_upstream_connectivity,
    FailureClass.AGGREGATION_HANG: fix_aggregation_hang,
    FailureClass.IMPLEMENTER_STALE: fix_implementer_stale,
    FailureClass.PR_MERGE_CONFLICT: fix_pr_merge_conflict,
    FailureClass.PR_CONFLICTING: fix_pr_conflicting,
}


# ---------------------------------------------------------------------------
# Tier 3 LLM recovery loop (small focused prompt via configured recovery agent)
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
_SHELL_TIMEOUT = 30
_TRIVIAL_EXCERPTS = frozenset({"{", "}", "[", "]", ",", '"', '",', "{}", "[]"})
_HYBRID_SCOPE_PATTERNS: tuple[str, ...] = (
    "mu/tools/executors/**/*.py",
    "mu/tests/tools/test_*.py",
    "reports/deferred/**/*.md",
    "reports/control_plane/**/*.md",
)
_HYBRID_HARD_DENY_PREFIXES: tuple[str, ...] = (
    "mu/host/",
    "rcx_pi/",
    ".git/",
    ".agent_bus/",
    ".claude/",
    "archive/",
)
_HYBRID_BOOTSTRAP_SURFACES: frozenset[str] = frozenset({
    "mu/tools/executors/phase_b_implementer.py",
    ".agent_bus/bridge_config.json",
})
_HYBRID_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "action",
    "commands",
    "explanation",
})
_HYBRID_COMMAND_KEYS: frozenset[str] = frozenset({
    "summary",
    "files_in_scope",
    "validation_spec",
    "why_not_shell_edit",
})
_HYBRID_VALIDATION_KEYS: frozenset[str] = frozenset({
    "validator",
    "targets",
})


def _is_hybrid_test_tool_path(rel_path: str) -> bool:
    prefix = "mu/tests/tools/"
    if not rel_path.startswith(prefix):
        return False
    leaf = rel_path[len(prefix):]
    return "/" not in leaf and leaf.startswith("test_") and leaf.endswith(".py")


def _is_hybrid_allowed_scope_path(rel_path: str) -> bool:
    return (
        (rel_path.startswith("mu/tools/executors/") and rel_path.endswith(".py"))
        or _is_hybrid_test_tool_path(rel_path)
        or (rel_path.startswith("reports/deferred/") and rel_path.endswith(".md"))
        or (rel_path.startswith("reports/control_plane/") and rel_path.endswith(".md"))
    )


def _is_hybrid_validator_target(rel_path: str) -> bool:
    return _is_hybrid_test_tool_path(rel_path)


def _strip_shell_quotes(text: str) -> str:
    """Remove shell quoting characters so regex patterns can match regardless of quoting."""
    return text.replace('"', "").replace("'", "")


def _load_bridge_adapters_module(repo_root: Path) -> Any:
    """Load bridge_adapters lazily so recovery stays repo-config driven."""
    agents_dir = repo_root / "mu" / "tools" / "agents"
    if str(agents_dir) not in sys.path:
        sys.path.insert(0, str(agents_dir))
    try:
        import importlib
        return importlib.import_module("bridge_adapters")
    except ImportError:
        import importlib.util as _ilu
        module_path = agents_dir / "bridge_adapters.py"
        spec = _ilu.spec_from_file_location("bridge_adapters", str(module_path))
        module = _ilu.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module


def _resolve_recovery_agent_invocation(
    repo_root: Path,
    *,
    wave_id: str,
    step: str,
    iteration: int,
    prompt: str,
) -> dict[str, Any]:
    """Resolve the configured recovery agent command through bridge config."""
    config = load_executor_config(repo_root)
    backend = str(
        config.get("backends", {}).get("recovery_gate")
        or config.get("backends", {}).get("phase_b_executor")
        or "codex"
    ).strip() or "codex"

    bridge_adapters = _load_bridge_adapters_module(repo_root)
    bridge_config_path = repo_root / ".agent_bus" / "bridge_config.json"
    bridge_config = bridge_adapters.load_bridge_config(bridge_config_path)
    spec = bridge_adapters.get_adapter(bridge_config, backend)

    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    prompt_token = normalize_wave_id(f"{wave_id}-{step}-{iteration + 1}")
    prompt_path = scratch_dir / f"recovery_agent_{prompt_token}.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    cmd, env = bridge_adapters._prepare_adapter_env(  # ANTICHEAT_OK: recovery must reuse bridge-config command expansion
        spec,
        {
            "prompt_file": str(prompt_path),
            "repo_root": str(repo_root),
            "job_id": f"recovery-{prompt_token}",
            "turn_id": f"tier3-{iteration + 1}",
            "agent_role": "recovery",
        },
    )
    command_label = " ".join(str(part) for part in cmd)
    return {
        "bridge_adapters": bridge_adapters,
        "spec": spec,
        "cmd": cmd,
        "env": env,
        "command_label": command_label,
        "prompt_input": prompt if spec.prompt_via_stdin else None,
        "prompt_path": prompt_path,
    }


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
    """Build a ~2K token diagnosis prompt for the configured recovery agent."""
    fc = result.get("failure_class", result.get("recovery", {}).get("failure_class", "unknown"))
    tier = result.get("tier", result.get("recovery", {}).get("tier", 3))
    step = _effective_result_step(result)
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
{{"action": "shell"|"edit"|"delegate_implementer"|"skip"|"escalate", "commands": [...], "explanation": "why"}}

- "shell": run shell commands to fix the issue
- "edit": apply file edits (commands = [{{"file_path": "...", "old_text": "...", "new_text": "..."}}])
- "delegate_implementer": request the existing phase_b_implementer code-writing actor for a bounded control-surface repair
- "skip": cannot fix, return failure
- "escalate": need human intervention

For "delegate_implementer", "commands" must contain exactly one object:
{{
  "summary": "...",
  "files_in_scope": ["mu/tools/executors/recovery_gate.py"],
  "validation_spec": [
    {{
      "validator": "pytest_targeted",
      "targets": ["mu/tests/tools/test_recovery_gate.py"]
    }}
  ],
  "why_not_shell_edit": "requires coordinated code change"
}}

delegate_implementer rules:
- files_in_scope may include ONLY these bounded control-surface patterns:
  - mu/tools/executors/**/*.py
  - mu/tests/tools/test_*.py
  - reports/deferred/**/*.md
  - reports/control_plane/**/*.md
- files_in_scope must still avoid host/runtime/bootstrap/config surfaces.
- Do NOT target bridge / adapter / implementer bootstrap surfaces.
- Do NOT return raw validation shell, validation_commands, args, or unsupported fields.
- validation_spec may use ONLY pytest_targeted with targets matching:
  - mu/tests/tools/test_*.py

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


def _normalize_hybrid_repo_relative(raw_path: Any) -> str | None:
    """Normalize a repo-relative path token for the hybrid recovery contract."""
    if not isinstance(raw_path, str):
        return None
    candidate = raw_path.strip().replace("\\", "/")
    if not candidate:
        return None
    if candidate.startswith("./"):
        candidate = candidate[2:]
    if candidate.startswith("/"):
        return None
    parts = []
    for part in PurePosixPath(candidate).parts:
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    if not parts:
        return None
    return PurePosixPath(*parts).as_posix()


def _normalize_recovery_prompt_exception_path(raw_path: Any) -> str | None:
    """Normalize the active recovery-agent prompt path for hybrid checkpoints."""
    normalized = _normalize_hybrid_repo_relative(raw_path)
    if normalized is None:
        return None
    path = PurePosixPath(normalized)
    if path.parent.as_posix() != ".scratch":
        return None
    if not path.name.startswith("recovery_agent_") or not path.name.endswith(".txt"):
        return None
    return normalized


def _recovery_prompt_lineage_token(raw_path: Any) -> str | None:
    normalized = _normalize_recovery_prompt_exception_path(raw_path)
    if normalized is None:
        return None
    token = PurePosixPath(normalized).stem[len("recovery_agent_"):]
    prefix, sep, suffix = token.rpartition("-")
    if sep and suffix.isdigit():
        return prefix
    return token


def _allowed_recovery_prompt_lineages(
    exception_paths: frozenset[str],
) -> frozenset[str]:
    prefixes = {
        prefix
        for item in exception_paths
        for prefix in [_recovery_prompt_lineage_token(item)]
        if prefix
    }
    return frozenset(prefixes)


def _is_allowed_hybrid_exception_path(
    rel_path: str,
    *,
    exception_paths: frozenset[str],
) -> bool:
    if rel_path in exception_paths:
        return True
    lineage = _recovery_prompt_lineage_token(rel_path)
    if lineage is None:
        return False
    return lineage in _allowed_recovery_prompt_lineages(exception_paths)


def _hybrid_exception_paths(
    job_id: str | None = None,
    *,
    recovery_prompt_relpath: str | None = None,
    result_exception_paths: list[str] | tuple[str, ...] | None = None,
) -> frozenset[str]:
    """Return the exact admitted .scratch nodes for the hybrid branch."""
    paths = {
        ".scratch",
        ".scratch/phase_b_implementer_prompt.md",
    }
    recovery_prompt = _normalize_recovery_prompt_exception_path(
        recovery_prompt_relpath
    )
    if recovery_prompt:
        paths.add(recovery_prompt)
    if job_id:
        paths.add(f".scratch/phase_b_implementer_output_{job_id}.txt")
    if result_exception_paths:
        for rel_path in result_exception_paths:
            normalized = _normalize_hybrid_repo_relative(rel_path)
            if normalized and normalized.startswith(".scratch/"):
                paths.add(normalized)
    return frozenset(paths)


def _result_scratch_exception_paths(result: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for key in (
        "agent_review_stdout_path",
        "agent_review_stderr_path",
        "bridge_stdout_path",
        "bridge_stderr_path",
        "stdout_path",
        "stderr_path",
    ):
        value = str(result.get(key) or "").strip()
        if value:
            paths.append(value)
    return paths


def _hybrid_scope_contract(files_in_scope: list[str], validation_spec: list[dict[str, Any]]) -> str:
    """Render the advisory scope contract passed to the implementer prompt."""
    validation_lines = [
        f"- {item['validator']}: {', '.join(item['targets'])}"
        for item in validation_spec
    ]
    return "\n".join([
        "This is the bounded hybrid Tier 3 recovery branch.",
        "Prompt-level scope is advisory only; recovery will audit surviving drift and local git-control state after the run.",
        "Allowed product writes:",
        *[f"- {path}" for path in files_in_scope],
        "Allowed transient executor byproducts:",
        "- .scratch/",
        "- .scratch/recovery_agent_<token>.txt",
        "- .scratch/phase_b_implementer_prompt.md",
        "- .scratch/phase_b_implementer_output_<job>.txt",
        "Do not modify validator modules unless they are explicitly listed in the allowed product writes above.",
        "Do not modify executor config, bridge config, implementer bootstrap files, .git state, or any other path.",
        "Validators recovery will run after your change:",
        *validation_lines,
    ])


def _fingerprint_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fingerprint_file(path: Path) -> str | None:
    try:
        return _fingerprint_bytes(path.read_bytes())
    except OSError:
        return None


def _absolute_path_snapshot(path: Path) -> dict[str, Any]:
    """Capture existence, type, link target, realpath, and content fingerprint."""
    snapshot: dict[str, Any] = {
        "exists": False,
        "type": "missing",
        "realpath": str(path.resolve(strict=False)),
        "readlink": None,
        "fingerprint": None,
    }
    try:
        st = path.lstat()
    except FileNotFoundError:
        return snapshot
    snapshot["exists"] = True
    mode = st.st_mode
    if stat.S_ISLNK(mode):
        snapshot["type"] = "symlink"
        snapshot["readlink"] = os.readlink(path)
    elif stat.S_ISDIR(mode):
        snapshot["type"] = "directory"
    elif stat.S_ISREG(mode):
        snapshot["type"] = "file"
        snapshot["fingerprint"] = _fingerprint_file(path)
    else:
        snapshot["type"] = "other"
    try:
        snapshot["realpath"] = str(path.resolve(strict=True))
    except FileNotFoundError:
        snapshot["realpath"] = str(path.resolve(strict=False))
    return snapshot


def _collect_hybrid_inventory(repo_root: Path) -> dict[str, dict[str, Any]]:
    """Inventory every path in the worktree except .git, descending into .scratch."""
    inventory: dict[str, dict[str, Any]] = {}

    def walk(directory: Path, rel_prefix: str = "") -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except FileNotFoundError:
            return
        for entry in entries:
            rel_path = f"{rel_prefix}/{entry.name}" if rel_prefix else entry.name
            if rel_path == ".git" or rel_path.startswith(".git/"):
                continue
            path = Path(entry.path)
            snapshot = _absolute_path_snapshot(path)
            inventory[rel_path] = {
                "exists": snapshot["exists"],
                "type": snapshot["type"],
                "readlink": snapshot["readlink"],
            }
            if snapshot["type"] == "directory":
                walk(path, rel_path)

    walk(repo_root)
    return inventory


def _collect_hybrid_manifest(
    repo_root: Path,
    *,
    exception_paths: frozenset[str],
) -> dict[str, dict[str, Any]]:
    """Capture every pre-existing non-directory path outside .git and exact exceptions."""
    manifest: dict[str, dict[str, Any]] = {}
    inventory = _collect_hybrid_inventory(repo_root)
    for rel_path, meta in inventory.items():
        if _is_allowed_hybrid_exception_path(
            rel_path,
            exception_paths=exception_paths,
        ):
            continue
        if meta["type"] == "directory":
            continue
        path = repo_root / rel_path
        snapshot = _absolute_path_snapshot(path)
        if not snapshot["exists"]:
            continue
        manifest[rel_path] = snapshot
    return manifest


def _validate_hybrid_scope_file(repo_root: Path, rel_path: str) -> tuple[bool, str]:
    path = repo_root / rel_path
    snapshot = _absolute_path_snapshot(path)
    expected_realpath = str((repo_root / rel_path).resolve(strict=False))
    if not snapshot["exists"]:
        return False, f"declared scope path missing: {rel_path}"
    if snapshot["type"] != "file":
        return False, f"declared scope path must stay a regular file: {rel_path}"
    if snapshot["realpath"] != expected_realpath:
        return False, f"declared scope path escaped stable realpath: {rel_path}"
    return True, ""


def _validate_hybrid_scratch_state(
    repo_root: Path,
    *,
    exception_paths: frozenset[str],
) -> tuple[bool, str]:
    scratch_path = repo_root / ".scratch"
    scratch_snapshot = _absolute_path_snapshot(scratch_path)
    expected_scratch_realpath = str(scratch_path.resolve(strict=False))
    if scratch_snapshot["exists"]:
        if scratch_snapshot["type"] != "directory":
            return False, ".scratch must remain a directory at repo root"
        if scratch_snapshot["realpath"] != expected_scratch_realpath:
            return False, ".scratch escaped its stable repo-root realpath"
    for rel_path in sorted(exception_paths):
        if rel_path == ".scratch":
            continue
        path = repo_root / rel_path
        snapshot = _absolute_path_snapshot(path)
        expected_realpath = str(path.resolve(strict=False))
        if not snapshot["exists"]:
            continue
        if snapshot["type"] != "file":
            return False, f"hybrid .scratch exception must remain a regular file: {rel_path}"
        if snapshot["realpath"] != expected_realpath:
            return False, f"hybrid .scratch exception escaped its stable realpath: {rel_path}"
    return True, ""


def _ensure_hybrid_scratch_inventory_allowed(
    repo_root: Path,
    inventory: dict[str, dict[str, Any]],
    *,
    exception_paths: frozenset[str],
) -> tuple[bool, str]:
    for rel_path in sorted(inventory):
        if not rel_path.startswith(".scratch/"):
            continue
        if not _is_allowed_hybrid_exception_path(
            rel_path,
            exception_paths=exception_paths,
        ):
            continue
        path = repo_root / rel_path
        snapshot = _absolute_path_snapshot(path)
        expected_realpath = str(path.resolve(strict=False))
        if snapshot["exists"] and snapshot["type"] != "file":
            return False, f"hybrid .scratch exception must remain a regular file: {rel_path}"
        if snapshot["exists"] and snapshot["realpath"] != expected_realpath:
            return False, f"hybrid .scratch exception escaped its stable realpath: {rel_path}"
    extra_paths = sorted(
        path for path in inventory
        if path.startswith(".scratch/")
        and not _is_allowed_hybrid_exception_path(
            path,
            exception_paths=exception_paths,
        )
    )
    if extra_paths:
        return False, f"unexpected .scratch descendant outside exact exception set: {extra_paths[0]}"
    return True, ""


def _capture_hybrid_git_control_tuple(repo_root: Path) -> dict[str, Any]:
    """Capture repo-local git-control state for fail-closed equality checks."""
    def git_output(args: list[str], *, allow_nonzero: bool = False) -> tuple[int, str, str]:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0 and not allow_nonzero:
            raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

    def git_path(name: str) -> Path:
        _, stdout, _ = git_output(["rev-parse", "--git-path", name])
        path = Path(stdout)
        if not path.is_absolute():
            path = repo_root / path
        return path

    head_code, head_oid, head_err = git_output(["rev-parse", "HEAD"], allow_nonzero=True)
    symref_code, symref, symref_err = git_output(["symbolic-ref", "-q", "HEAD"], allow_nonzero=True)
    _, refs_stdout, _ = git_output(
        ["for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)"],
        allow_nonzero=True,
    )
    _, remote_stdout, _ = git_output(
        ["config", "--get-regexp", "^remote\\."],
        allow_nonzero=True,
    )
    index_snapshot = _absolute_path_snapshot(git_path("index"))
    head_snapshot = _absolute_path_snapshot(git_path("HEAD"))
    config_snapshot = _absolute_path_snapshot(git_path("config"))
    refs_lines = refs_stdout.splitlines()
    remote_fingerprint = _fingerprint_bytes(remote_stdout.encode("utf-8"))
    return {
        "head": {
            "oid": head_oid,
            "oid_returncode": head_code,
            "oid_stderr": head_err,
            "symref": symref,
            "symref_returncode": symref_code,
            "symref_stderr": symref_err,
            "path_snapshot": head_snapshot,
        },
        "index": index_snapshot,
        "refs": {
            "lines": refs_lines,
            "fingerprint": _fingerprint_bytes("\n".join(refs_lines).encode("utf-8")),
        },
        "remote_config": {
            "lines": remote_stdout.splitlines(),
            "fingerprint": remote_fingerprint,
            "path_snapshot": config_snapshot,
        },
    }


def _diff_hybrid_manifest(
    baseline: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for rel_path, before in baseline.items():
        after = current.get(rel_path, {"exists": False, "type": "missing", "realpath": before["realpath"], "readlink": None, "fingerprint": None})
        for field in ("exists", "type", "realpath", "readlink", "fingerprint"):
            if before.get(field) != after.get(field):
                reasons[rel_path] = f"manifest_{field}_changed"
                break
    return reasons


def _diff_hybrid_inventory(
    baseline: dict[str, dict[str, Any]],
    current: dict[str, dict[str, Any]],
    *,
    exception_paths: frozenset[str],
) -> dict[str, str]:
    reasons: dict[str, str] = {}
    for rel_path in sorted(set(baseline) | set(current)):
        before = baseline.get(rel_path)
        after = current.get(rel_path)
        # Same-lineage recovery prompt siblings are tolerated only when they
        # were already present at checkpoint time. Newly created siblings must
        # still fail closed unless they are an exact admitted exception path.
        if rel_path in exception_paths:
            continue
        if before is not None and _is_allowed_hybrid_exception_path(
            rel_path,
            exception_paths=exception_paths,
        ):
            continue
        if before is None:
            reasons[rel_path] = "inventory_created"
            continue
        if after is None:
            reasons[rel_path] = "inventory_deleted"
            continue
        if before.get("type") != after.get("type"):
            reasons[rel_path] = "inventory_type_changed"
            continue
        if before.get("readlink") != after.get("readlink"):
            reasons[rel_path] = "inventory_readlink_changed"
    return reasons


def _capture_hybrid_checkpoint(
    repo_root: Path,
    *,
    files_in_scope: list[str],
    exception_paths: frozenset[str],
) -> tuple[bool, dict[str, Any]]:
    for rel_path in files_in_scope:
        ok, detail = _validate_hybrid_scope_file(repo_root, rel_path)
        if not ok:
            return False, {"detail": detail}
    ok, detail = _validate_hybrid_scratch_state(
        repo_root,
        exception_paths=exception_paths,
    )
    if not ok:
        return False, {"detail": detail}
    inventory = _collect_hybrid_inventory(repo_root)
    ok, detail = _ensure_hybrid_scratch_inventory_allowed(
        repo_root,
        inventory,
        exception_paths=exception_paths,
    )
    if not ok:
        return False, {"detail": detail}
    try:
        git_control = _capture_hybrid_git_control_tuple(repo_root)
    except Exception as exc:
        return False, {"detail": f"hybrid git-control baseline failed: {exc}"}
    manifest = _collect_hybrid_manifest(
        repo_root,
        exception_paths=exception_paths,
    )
    return True, {
        "manifest": manifest,
        "inventory": inventory,
        "git_control": git_control,
        "exception_paths": exception_paths,
    }


def _audit_hybrid_checkpoint(
    repo_root: Path,
    *,
    baseline: dict[str, Any],
    files_in_scope: list[str],
    exception_paths: frozenset[str],
) -> tuple[bool, dict[str, Any]]:
    ok, current = _capture_hybrid_checkpoint(
        repo_root,
        files_in_scope=files_in_scope,
        exception_paths=exception_paths,
    )
    if not ok:
        return False, current
    if current["git_control"] != baseline["git_control"]:
        return False, {"detail": "hybrid git-control tuple drifted from baseline"}
    manifest_reasons = _diff_hybrid_manifest(baseline["manifest"], current["manifest"])
    inventory_reasons = _diff_hybrid_inventory(
        baseline["inventory"],
        current["inventory"],
        exception_paths=exception_paths,
    )
    observed_drift = sorted(set(manifest_reasons) | set(inventory_reasons))
    out_of_scope = sorted(path for path in observed_drift if path not in files_in_scope)
    if out_of_scope:
        return False, {
            "detail": f"hybrid observed drift escaped declared scope: {out_of_scope[0]}",
            "observed_drift": observed_drift,
            "manifest_reasons": manifest_reasons,
            "inventory_reasons": inventory_reasons,
        }
    return True, {
        "observed_drift": observed_drift,
        "manifest_reasons": manifest_reasons,
        "inventory_reasons": inventory_reasons,
        "git_control": current["git_control"],
    }


def _load_phase_b_implementer_module(repo_root: Path) -> Any:
    executors_dir = repo_root / "mu" / "tools" / "executors"
    if str(executors_dir) not in sys.path:
        sys.path.insert(0, str(executors_dir))
    # Keep the lazy import outside the observed-drift contract by suppressing
    # repo-local .pyc writes during module load.
    prior_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        try:
            import importlib
            return importlib.import_module("phase_b_implementer")
        except ImportError:
            import importlib.util as _ilu
            module_path = executors_dir / "phase_b_implementer.py"
            spec = _ilu.spec_from_file_location("phase_b_implementer", str(module_path))
            module = _ilu.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)
            return module
    finally:
        sys.dont_write_bytecode = prior_dont_write_bytecode


def _hybrid_bootstrap_fault_detected(
    result: dict[str, Any],
    files_in_scope: list[str],
) -> tuple[bool, str]:
    for rel_path in files_in_scope:
        if rel_path in _HYBRID_BOOTSTRAP_SURFACES:
            return True, f"hybrid delegation may not target bootstrap surface: {rel_path}"
    haystack = " ".join(
        str(result.get(key, "") or "")
        for key in ("step", "stderr", "stdout", "executor")
    ).lower()
    blocked_fragments = (
        "mu/tools/executors/phase_b_implementer.py",
        ".agent_bus/bridge_config.json",
        "bridge adapter config error",
        "cannot import bridge_adapters",
        "adapter invocation/bootstrap",
        "adapter selection",
    )
    for fragment in blocked_fragments:
        if fragment in haystack:
            return True, f"hybrid delegation blocked for bootstrap/adapter fault: {fragment}"
    return False, ""


def _validate_hybrid_validation_spec(spec: Any) -> tuple[bool, list[dict[str, Any]] | None, str]:
    if not isinstance(spec, list) or not spec:
        return False, None, "delegate_implementer validation_spec must be a non-empty list"
    validated: list[dict[str, Any]] = []
    for item in spec:
        if not isinstance(item, dict):
            return False, None, "delegate_implementer validation_spec items must be objects"
        extra = sorted(set(item) - _HYBRID_VALIDATION_KEYS)
        if extra:
            return False, None, f"delegate_implementer validation_spec has unsupported fields: {extra}"
        if item.get("validator") != "pytest_targeted":
            return False, None, f"unsupported hybrid validator: {item.get('validator')!r}"
        targets = item.get("targets")
        if not isinstance(targets, list) or not targets:
            return False, None, "pytest_targeted requires a non-empty targets list"
        normalized_targets: list[str] = []
        for raw_target in targets:
            normalized = _normalize_hybrid_repo_relative(raw_target)
            if normalized is None:
                return False, None, f"invalid validator target: {raw_target!r}"
            if not _is_hybrid_validator_target(normalized):
                return False, None, f"validator target outside hybrid allowlist: {normalized}"
            normalized_targets.append(normalized)
        if len(set(normalized_targets)) != len(normalized_targets):
            return False, None, "pytest_targeted targets must be unique"
        validated.append({
            "validator": "pytest_targeted",
            "targets": normalized_targets,
        })
    return True, validated, ""


def _validate_delegate_implementer_payload(
    response: dict[str, Any],
) -> tuple[bool, dict[str, Any] | None, str]:
    extra_top_level = sorted(set(response) - _HYBRID_TOP_LEVEL_KEYS)
    if extra_top_level:
        return False, None, f"delegate_implementer response has unsupported top-level fields: {extra_top_level}"
    if "validation_commands" in response:
        return False, None, "delegate_implementer rejects raw validation_commands"
    commands = response.get("commands")
    if not isinstance(commands, list):
        return False, None, "delegate_implementer commands must be a singleton list"
    if len(commands) != 1:
        return False, None, "delegate_implementer commands must contain exactly one object"
    command = commands[0]
    if not isinstance(command, dict):
        return False, None, "delegate_implementer command entry must be an object"
    extra_command_fields = sorted(set(command) - _HYBRID_COMMAND_KEYS)
    if extra_command_fields:
        return False, None, f"delegate_implementer command has unsupported fields: {extra_command_fields}"
    if "args" in command:
        return False, None, "delegate_implementer rejects args"
    files_in_scope_raw = command.get("files_in_scope")
    if not isinstance(files_in_scope_raw, list) or not files_in_scope_raw:
        return False, None, "delegate_implementer files_in_scope must be a non-empty list"
    files_in_scope: list[str] = []
    for raw_path in files_in_scope_raw:
        normalized = _normalize_hybrid_repo_relative(raw_path)
        if normalized is None:
            return False, None, f"invalid files_in_scope entry: {raw_path!r}"
        if any(normalized.startswith(prefix) for prefix in _HYBRID_HARD_DENY_PREFIXES):
            return False, None, f"hybrid files_in_scope targets denied prefix: {normalized}"
        if normalized in _HYBRID_BOOTSTRAP_SURFACES:
            return False, None, f"hybrid files_in_scope targets bootstrap surface: {normalized}"
        if not _is_hybrid_allowed_scope_path(normalized):
            return False, None, f"hybrid files_in_scope is outside the bounded control-surface allowlist: {normalized}"
        files_in_scope.append(normalized)
    if len(set(files_in_scope)) != len(files_in_scope):
        return False, None, "delegate_implementer files_in_scope entries must be unique"
    ok, validation_spec, detail = _validate_hybrid_validation_spec(command.get("validation_spec"))
    if not ok:
        return False, None, detail
    return True, {
        "summary": str(command.get("summary", "") or "").strip(),
        "why_not_shell_edit": str(command.get("why_not_shell_edit", "") or "").strip(),
        "files_in_scope": files_in_scope,
        "validation_spec": validation_spec,
    }, ""


def _run_pytest_targeted_validator(
    repo_root: Path,
    *,
    targets: list[str],
    timeout: int,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-x",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        *targets,
    ]
    with tempfile.TemporaryDirectory(prefix="rcx-recovery-tmp-") as tmp_root, tempfile.TemporaryDirectory(prefix="rcx-recovery-cache-") as cache_root:
        env = {
            **os.environ,
            "PYTHONHASHSEED": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TMPDIR": tmp_root,
            "TMP": tmp_root,
            "TEMP": tmp_root,
            "XDG_CACHE_HOME": cache_root,
        }
        proc = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            check=False,
        )
    return {
        "validator": "pytest_targeted",
        "command": command,
        "targets": list(targets),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
    }


def _run_hybrid_validation_spec(
    repo_root: Path,
    *,
    validation_spec: list[dict[str, Any]],
    timeout: int,
) -> dict[str, Any]:
    last_result: dict[str, Any] | None = None
    for item in validation_spec:
        last_result = _run_pytest_targeted_validator(
            repo_root,
            targets=item["targets"],
            timeout=timeout,
        )
        if not last_result["passed"]:
            return last_result
    return last_result or {
        "validator": "",
        "command": [],
        "targets": [],
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "passed": True,
    }


def _build_delegate_implementer_prompt(
    repo_root: Path,
    *,
    wave_id: str,
    step: str,
    explanation: str,
    delegate_payload: dict[str, Any],
    module: Any,
) -> str:
    files_in_scope = delegate_payload["files_in_scope"]
    validation_spec = delegate_payload["validation_spec"]
    learning_context = load_relevant_learnings(
        "implementer",
        files_in_scope,
        repo_root,
    )
    locked_plan = "\n".join([
        "# Hybrid Recovery Repair",
        "",
        f"- Failure step: {step}",
        f"- Recovery explanation: {explanation or '(none provided)'}",
        f"- Delegate summary: {delegate_payload.get('summary') or '(none provided)'}",
        f"- Why not shell/edit: {delegate_payload.get('why_not_shell_edit') or '(not provided)'}",
        "",
        "## Writable Scope",
        *[f"- {path}" for path in files_in_scope],
        "",
        "## Recovery-Owned Verification",
        *[
            f"- {item['validator']}: {', '.join(item['targets'])}"
            for item in validation_spec
        ],
        "",
        "Do not modify any file outside the writable scope above.",
        "Do not modify validator modules unless explicitly listed in writable scope.",
        "Do not modify executor config, bridge config, implementer bootstrap files, or .git state.",
        "Recovery will audit surviving drift and local git-control immutability after your run.",
    ])
    return module.build_implementation_prompt(
        locked_plan,
        repo_root=repo_root,
        wave_id=wave_id,
        scope_hint=f"Hybrid recovery delegate for {step}",
        scope_contract=_hybrid_scope_contract(files_in_scope, validation_spec),
        learning_context=learning_context,
    )


def _run_delegate_implementer_action(
    repo_root: Path,
    *,
    result: dict[str, Any],
    wave_id: str,
    step: str,
    response: dict[str, Any],
    explanation: str,
    recovery_prompt_path: Any = None,
    verbose: bool = False,
) -> dict[str, Any]:
    config = load_executor_config(repo_root)
    if not bool(config.get("hybrid_recovery_enabled", False)):
        return {
            "ok": False,
            "detail": "hybrid_recovery_enabled is false; delegate_implementer is disabled",
            "result_update": None,
        }
    ok, delegate_payload, detail = _validate_delegate_implementer_payload(response)
    if not ok or delegate_payload is None:
        return {"ok": False, "detail": detail, "result_update": None}
    blocked, blocked_detail = _hybrid_bootstrap_fault_detected(result, delegate_payload["files_in_scope"])
    if blocked:
        return {"ok": False, "detail": blocked_detail, "result_update": None}
    _update_recovery_status(
        repo_root,
        state="tier3_delegate_scope_validation",
        current_command="delegate_implementer scope validation",
        detail=_excerpt(explanation),
    )
    recovery_prompt_relpath = None
    if recovery_prompt_path is not None:
        prompt_path = Path(recovery_prompt_path)
        if prompt_path.is_absolute():
            try:
                prompt_path = prompt_path.relative_to(repo_root)
            except ValueError:
                prompt_path = Path()
        recovery_prompt_relpath = _normalize_hybrid_repo_relative(
            prompt_path.as_posix()
        )
    baseline_ok, baseline = _capture_hybrid_checkpoint(
        repo_root,
        files_in_scope=delegate_payload["files_in_scope"],
        exception_paths=_hybrid_exception_paths(
            recovery_prompt_relpath=recovery_prompt_relpath,
            result_exception_paths=_result_scratch_exception_paths(result),
        ),
    )
    if not baseline_ok:
        return {"ok": False, "detail": baseline["detail"], "result_update": None}
    try:
        module = _load_phase_b_implementer_module(repo_root)
    except Exception as exc:
        return {
            "ok": False,
            "detail": f"could not load phase_b_implementer for hybrid recovery: {exc}",
            "result_update": None,
        }
    prompt = _build_delegate_implementer_prompt(
        repo_root,
        wave_id=wave_id,
        step=step,
        explanation=explanation,
        delegate_payload=delegate_payload,
        module=module,
    )
    implementer_timeout = int(
        config.get("timeouts", {}).get("recovery_implementer")
        or config.get("timeouts", {}).get("phase_b_executor", 1200)
    )
    implementer_result = module.invoke_implementer(
        repo_root,
        prompt,
        backend=str(
            config.get("backends", {}).get("phase_b_executor") or "codex"
        ),
        model_override=config.get("model_overrides", {}).get("phase_b_executor"),
        timeout=implementer_timeout,
        verbose=verbose,
    )
    exception_paths = _hybrid_exception_paths(
        implementer_result.get("job_id") or None,
        recovery_prompt_relpath=recovery_prompt_relpath,
        result_exception_paths=_result_scratch_exception_paths(result),
    )
    pre_validation_ok, pre_validation_audit = _audit_hybrid_checkpoint(
        repo_root,
        baseline=baseline,
        files_in_scope=delegate_payload["files_in_scope"],
        exception_paths=exception_paths,
    )
    if not pre_validation_ok:
        return {
            "ok": False,
            "detail": pre_validation_audit["detail"],
            "result_update": None,
            "implementer_result": implementer_result,
        }
    if implementer_result.get("status") != "success":
        return {
            "ok": False,
            "detail": (
                "delegate_implementer returned "
                f"{implementer_result.get('status')} (exit={implementer_result.get('exit_code')})"
            ),
            "result_update": {
                "stdout": implementer_result.get("output", ""),
                "stderr": implementer_result.get("stderr", ""),
            },
            "implementer_result": implementer_result,
            "pre_validation_audit": pre_validation_audit,
        }
    validator_timeout = min(max(60, implementer_timeout), 300)
    validator_targets = [
        target
        for item in delegate_payload["validation_spec"]
        for target in item["targets"]
    ]
    try:
        validator_result = _run_hybrid_validation_spec(
            repo_root,
            validation_spec=delegate_payload["validation_spec"],
            timeout=validator_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        command = exc.cmd if isinstance(exc.cmd, list) else [str(exc.cmd)]
        validator_result = {
            "validator": "pytest_targeted",
            "command": command,
            "targets": validator_targets,
            "stdout": "",
            "stderr": f"hybrid validator timed out after {validator_timeout}s",
            "exit_code": 124,
            "passed": False,
            "timed_out": True,
        }
    final_ok, final_audit = _audit_hybrid_checkpoint(
        repo_root,
        baseline=baseline,
        files_in_scope=delegate_payload["files_in_scope"],
        exception_paths=exception_paths,
    )
    if not final_ok:
        return {
            "ok": False,
            "detail": final_audit["detail"],
            "result_update": None,
            "implementer_result": implementer_result,
            "validator_result": validator_result,
            "pre_validation_audit": pre_validation_audit,
        }
    if not validator_result["passed"]:
        return {
            "ok": False,
            "detail": "hybrid validator failed",
            "result_update": {
                "stdout": validator_result["stdout"],
                "stderr": validator_result["stderr"],
            },
            "implementer_result": implementer_result,
            "validator_result": validator_result,
            "pre_validation_audit": pre_validation_audit,
            "final_audit": final_audit,
        }
    return {
        "ok": True,
        "detail": explanation or f"delegate_implementer applied; retrying {_retry_target(result, step)}",
        "implementer_result": implementer_result,
        "validator_result": validator_result,
        "pre_validation_audit": pre_validation_audit,
        "final_audit": final_audit,
    }


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


def _is_nonretryable_recovery_agent_failure(detail: str) -> bool:
    lowered = str(detail or "").lower()
    if not lowered:
        return False
    if "401 unauthorized" in lowered:
        return True
    if (
        "fatal error: codex cannot access session files" in lowered
        or ("thread/start failed" in lowered and "session files" in lowered)
        or ("thread/resume failed" in lowered and "session files" in lowered)
    ):
        return True
    if "failed to initialize rollout recorder" in lowered and "operation not permitted" in lowered:
        return True
    return False


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
    step = _effective_result_step(result)
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
        try:
            agent_invocation = _resolve_recovery_agent_invocation(
                repo_root,
                wave_id=wave_id,
                step=step,
                iteration=i,
                prompt=prompt,
            )
        except Exception as exc:
            dur = round(time.monotonic() - iteration_t0, 3)
            detail = f"recovery agent setup failed: {exc}"
            loop_log.append({
                "iteration": i + 1,
                "action": "error",
                "detail": detail,
                "duration_s": dur,
            })
            _log_tier3_attempt(
                repo_root, wave_id, step, fc, i + 1,
                "error", "failed", dur, detail,
                invocation_id=invocation_id,
            )
            _update_recovery_status(
                repo_root,
                state="tier3_error",
                current_iteration=i + 1,
                child_pid=0,
                child_role="",
                current_command="",
                last_action="error",
                detail=_excerpt(detail),
            )
            continue

        command_label = _excerpt(agent_invocation["command_label"])
        _update_recovery_status(
            repo_root,
            state="tier3_waiting_on_agent",
            current_iteration=i + 1,
            last_action="diagnose",
            child_pid=0,
            child_role="",
            current_command=command_label,
            detail=_excerpt(_summarize_result_reason(result)),
        )

        # Call the configured recovery agent through the same bridge-config path
        # used by the rest of the pipeline surfaces.
        recovery_proc = None
        spec = agent_invocation["spec"]
        bridge_adapters = agent_invocation["bridge_adapters"]
        try:
            recovery_proc = subprocess.Popen(
                agent_invocation["cmd"],
                stdin=subprocess.PIPE if spec.prompt_via_stdin else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=repo_root,
                env=agent_invocation["env"],
                start_new_session=True,
            )
            _update_recovery_status(
                repo_root,
                child_pid=recovery_proc.pid,
                child_role=spec.name,
            )
            prompt_input = agent_invocation["prompt_input"] if spec.prompt_via_stdin else None
            stdout, stderr = recovery_proc.communicate(
                input=prompt_input,
                timeout=spec.timeout_s,
            )
            raw_response = bridge_adapters._normalize_stdout_for_adapter(  # ANTICHEAT_OK: recovery must parse the configured adapter's wrapped stdout
                spec,
                agent_invocation["cmd"],
                stdout,
            ).strip()
            stderr_response = bridge_adapters._normalize_stdout_for_adapter(  # ANTICHEAT_OK: codex may place authoritative output on stderr
                spec,
                agent_invocation["cmd"],
                stderr,
            ).strip()
            if stderr_response:
                if not raw_response:
                    raw_response = stderr_response
                else:
                    raw_response = f"{raw_response}\n[stderr]\n{stderr_response}".strip()
            if recovery_proc.returncode != 0:
                tail = _excerpt(raw_response or stderr_response or stderr or stdout)
                raise RuntimeError(
                    f"recovery agent '{spec.name}' exited {recovery_proc.returncode}: {tail}"
                )
        except subprocess.TimeoutExpired:
            _terminate_process_tree(recovery_proc)
            dur = round(time.monotonic() - iteration_t0, 3)
            detail = f"recovery agent '{spec.name}' timed out after {spec.timeout_s}s"
            loop_log.append({
                "iteration": i + 1, "action": "timeout",
                "detail": detail,
                "duration_s": dur})
            _log_tier3_attempt(repo_root, wave_id, step, fc, i + 1,
                               "timeout", "failed", dur, detail,
                               invocation_id=invocation_id)
            _update_recovery_status(
                repo_root,
                state="tier3_timeout",
                child_pid=0,
                child_role="",
                current_command="",
                last_action="timeout",
                detail=_excerpt(detail),
            )
            continue
        except Exception as exc:
            dur = round(time.monotonic() - iteration_t0, 3)
            detail = f"recovery agent invocation failed: {exc}"
            loop_log.append({
                "iteration": i + 1, "action": "error",
                "detail": detail,
                "duration_s": dur})
            _log_tier3_attempt(
                repo_root, wave_id, step, fc, i + 1,
                "error", "failed", dur, detail,
                invocation_id=invocation_id,
            )
            if _looks_like_upstream_connectivity_failure(detail):
                _finish_recovery_status(
                    repo_root,
                    recovered=True,
                    exhausted=False,
                    outcome="success",
                    action="retryable_upstream_connectivity",
                    detail=detail,
                    state="tier3_upstream_connectivity_retryable",
                )
                return {
                    "recovered": True,
                    "exhausted": False,
                    "iterations": i + 1,
                    "log": loop_log,
                }
            if _is_nonretryable_recovery_agent_failure(detail):
                _finish_recovery_status(
                    repo_root,
                    recovered=False,
                    exhausted=True,
                    outcome="exhausted",
                    action="exhausted",
                    detail=detail,
                    state="tier3_exhausted",
                )
                return {
                    "recovered": False,
                    "exhausted": True,
                    "iterations": i + 1,
                    "log": loop_log,
                }
            _update_recovery_status(
                repo_root,
                state="tier3_error",
                child_pid=0,
                child_role="",
                current_command="",
                last_action="error",
                detail=_excerpt(detail),
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
        if not isinstance(response, dict):
            dur = round(time.monotonic() - iteration_t0, 3)
            detail = "recovery agent response must be a JSON object"
            loop_log.append({
                "iteration": i + 1,
                "action": "parse_error",
                "detail": detail,
                "duration_s": dur,
            })
            _log_tier3_attempt(
                repo_root, wave_id, step, fc, i + 1,
                "parse_error", "failed", dur, detail,
                invocation_id=invocation_id,
            )
            _update_recovery_status(
                repo_root,
                state="tier3_parse_error",
                child_pid=0,
                child_role="",
                current_command="",
                last_action="parse_error",
                detail=detail,
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

        # Tier-3 short-circuit: if the recovery agent explicitly returns a
        # non-actionable action (skip/escalate) while more iterations remain,
        # subsequent iterations would burn equivalent codex invocations for the
        # same conclusion. Collapse to a single terminal record instead.
        #
        # Bot P1 fix (2026-04-17, PR #791 follow-up): exhausted must stay
        # False on deliberate non-actionable skip. `_finish_recovery_status`
        # emits `pipeline_hard_fail` pager events when exhausted=True, which
        # is INCORRECT operational severity for a deliberate agent skip.
        # Match the semantics of the existing non-short-circuit `skip` path
        # (line ~3510 in this file) which is explicitly non-exhausted.
        # An `escalate` action implies human-intervention-needed (matches
        # the existing `escalate` return path below which also keeps
        # exhausted=False). Setting exhausted=True here would trigger false
        # hard_fail alerts for cases the agent intentionally chose not to
        # auto-remediate.
        if action in {"skip", "escalate"} and i < max_iterations - 1:
            dur = round(time.monotonic() - iteration_t0, 3)
            detail = (
                f"tier-3 iter {i + 1} returned non-actionable action={action}; "
                f"short-circuiting remaining iterations"
            )
            loop_log.append({
                "iteration": i + 1,
                "action": action,
                "detail": detail,
                "explanation": explanation,
                "duration_s": dur,
                "short_circuited": True,
            })
            _log_tier3_attempt(
                repo_root, wave_id, step, fc, i + 1,
                action, "short_circuited", dur, detail,
                invocation_id=invocation_id,
            )
            # Bot P1 fix (PR #792 2nd-round finding): differentiate skip vs
            # escalate severity on short-circuit.
            #   - action="skip"     → agent can't fix but issue isn't
            #                         critical. NOT exhausted. No hard_fail
            #                         pager event.
            #   - action="escalate" → agent believes human intervention is
            #                         required. Genuine exhausted terminal
            #                         state. pipeline_hard_fail pager event
            #                         is the CORRECT severity.
            # Collapsing both into exhausted=False (Wave G initial fix)
            # hid legitimate escalate-hard-fail signal. Restore it.
            is_skip = (action == "skip")
            exhausted_flag = not is_skip  # False for skip, True for escalate
            _finish_recovery_status(
                repo_root,
                recovered=False,
                exhausted=exhausted_flag,
                outcome="short_circuited_non_actionable",
                action=action,
                detail=detail,
                state="tier3_short_circuited",
            )
            return {
                "recovered": False,
                "exhausted": exhausted_flag,
                "iterations": i + 1,
                "log": loop_log,
            }

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

        if action == "delegate_implementer":
            delegate_result = _run_delegate_implementer_action(
                repo_root,
                result=result,
                wave_id=wave_id,
                step=step,
                response=response,
                explanation=explanation,
                recovery_prompt_path=agent_invocation.get("prompt_path"),
            )
            dur = round(time.monotonic() - iteration_t0, 3)
            loop_log.append({
                "iteration": i + 1,
                "action": "delegate_implementer",
                "detail": delegate_result["detail"],
                "duration_s": dur,
                "implementer_status": (
                    delegate_result.get("implementer_result", {}) or {}
                ).get("status"),
                "pre_validation_drift": (
                    delegate_result.get("pre_validation_audit", {}) or {}
                ).get("observed_drift", []),
                "final_drift": (
                    delegate_result.get("final_audit", {}) or {}
                ).get("observed_drift", []),
            })
            if delegate_result.get("ok"):
                retry_target = _retry_target(result, step)
                detail = delegate_result["detail"] or f"delegate_implementer applied; retrying {retry_target}"
                _log_tier3_attempt(
                    repo_root, wave_id, step, fc, i + 1,
                    "delegate_implementer", "retry_requested", dur, detail,
                    invocation_id=invocation_id,
                )
                _finish_recovery_status(
                    repo_root,
                    recovered=True,
                    exhausted=False,
                    outcome="retry_requested",
                    action="delegate_implementer",
                    detail=detail,
                    state="tier3_retry_requested",
                )
                return {
                    "recovered": True,
                    "exhausted": False,
                    "iterations": i + 1,
                    "log": loop_log,
                }
            result_update = delegate_result.get("result_update")
            if isinstance(result_update, dict):
                result = dict(result)
                if "stderr" in result_update:
                    result["stderr"] = result_update["stderr"]
                if "stdout" in result_update:
                    result["stdout"] = result_update["stdout"]
                _update_recovery_status(
                    repo_root,
                    state="tier3_verify_failed",
                    detail=_excerpt(_summarize_result_reason(result)),
                )
            else:
                _update_recovery_status(
                    repo_root,
                    state="tier3_delegate_failed",
                    detail=_excerpt(delegate_result["detail"]),
                )
            _log_tier3_attempt(
                repo_root, wave_id, step, fc, i + 1,
                "delegate_implementer", "failed", dur, delegate_result["detail"],
                invocation_id=invocation_id,
            )
            continue

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
        reason_text = _summarize_result_reason(result)
        step = _effective_result_step(result)
        if reason_text:
            prefix = f"{step}: {reason_text}" if step else reason_text
            if combined_text:
                normalized_prefix = _normalize_fingerprint(prefix)
                normalized_combined = _normalize_fingerprint(combined_text)
                if normalized_prefix in normalized_combined:
                    return combined_text
                return f"{prefix} {combined_text}"
            return prefix
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
    # Only unescape the two sequences produced by _escape_backtick_field:
    #   \` → `   and   \\ → \
    # Other backslash sequences (e.g. \t, \n, path\to\file) are preserved
    # so manually authored fingerprints with literal backslashes are not corrupted.
    return re.sub(r"\\([`\\])", r"\1", s)


# Regex supports backslash-escaped backticks within the delimited fields:
#   (?:[^`\\]|\\.)+ = one or more of: (non-backtick-non-backslash) | (backslash + any char)
_FIXED_ENTRY_RE = re.compile(
    r"^-\s*\[.*?\]\s*FIXED\s*\|\s*fingerprint:\s*`((?:[^`\\]|\\.)+)`\s*\|\s*action:\s*`((?:[^`\\]|\\.)+)`",
)

# Regex for ALL learning.md entries (not just FIXED).
# Format: - [DATE] CATEGORY | fingerprint: `text` | ...
# Captures: date, category, fingerprint.  Description is the multi-line
# body that follows (handled by _load_learning_md_entries below).
_LEARNING_MD_ENTRY_RE = re.compile(
    r"^-\s*\[(\d{4}-\d{2}-\d{2})\]\s*([A-Z]+)\s*\|\s*fingerprint:\s*`((?:[^`\\]|\\.)+)`"
)

# Map agent names to relevant learning.md categories.
# None = unfiltered (receives all categories).
# Agents that work on pipeline infrastructure see PIPELINE/HOOK/WORKTREE/DISPATCH.
# Agents that review code quality see broader categories.
_AGENT_CATEGORY_MAP: dict[str, list[str] | None] = {
    "implementer": ["PIPELINE", "HOOK", "WORKTREE", "DISPATCH", "BRIDGE"],
    "grounding": ["PIPELINE", "HOOK", "DEBUG"],
    "fuzzer": ["PIPELINE", "DEBUG"],
    "verifier": None,       # unfiltered — sees all
    "adversary": None,      # unfiltered — sees all
    "expert": None,         # unfiltered — sees all
    "structural-proof": None,
    "translator": None,
    "visualizer": None,
    "advisor": None,
}


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


def _load_learning_md_entries(repo_root: Path) -> list[dict]:
    """Parse ALL learning.md entries into structured dicts.

    Reads every entry matching ``- [DATE] CATEGORY | fingerprint: `text` ...``
    and extracts the multi-line description body that follows (indented lines
    until the next top-level entry or EOF).

    Returns list of dicts with keys: date, category, fingerprint, body.
    Skips entries marked SUPERSEDED.  Returns empty list on any error.
    """
    try:
        md_path = repo_root / LEARNING_MD_REL
        if not md_path.exists():
            return []
        lines = md_path.read_text(encoding="utf-8").splitlines()
        entries: list[dict] = []
        current: dict | None = None
        body_lines: list[str] = []

        for line in lines:
            m = _LEARNING_MD_ENTRY_RE.match(line.strip())
            if m:
                # Save previous entry
                if current is not None:
                    current["body"] = " ".join(body_lines).strip()[:500]
                    entries.append(current)
                # Check for SUPERSEDED
                if "SUPERSEDED BY:" in line:
                    current = None
                    body_lines = []
                    continue
                current = {
                    "date": m.group(1),
                    "category": m.group(2),
                    "fingerprint": _unescape_backtick_field(m.group(3)),
                }
                body_lines = []
            elif current is not None and line.startswith("  "):
                body_lines.append(line.strip())
        # Final entry
        if current is not None:
            current["body"] = " ".join(body_lines).strip()[:500]
            entries.append(current)
        return entries
    except (OSError, TypeError, ValueError) as exc:
        import logging
        logging.getLogger(__name__).warning(
            "_load_learning_md_entries failed (non-fatal): %s", exc)
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
        result_step = _effective_result_step(result)
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
    decoder = json.JSONDecoder()
    brace_positions = [idx for idx, ch in enumerate(text) if ch == "{"]
    for start in reversed(brace_positions):
        try:
            parsed, end = decoder.raw_decode(text[start:])
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if text[start + end:].strip():
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


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _save_recovery_status(repo_root: Path, status: dict[str, Any]) -> None:
    status_path = repo_root / RECOVERY_STATUS_FILE
    _atomic_write_text(status_path, json.dumps(status, indent=2) + "\n")


def _snapshot_recovery_status(repo_root: Path) -> tuple[bool, str]:
    status_path = repo_root / RECOVERY_STATUS_FILE
    if not status_path.exists():
        return False, ""
    return True, status_path.read_text(encoding="utf-8")


def _restore_recovery_status(repo_root: Path, *, existed: bool, raw_text: str) -> None:
    status_path = repo_root / RECOVERY_STATUS_FILE
    if existed:
        _atomic_write_text(status_path, raw_text)
        return
    try:
        status_path.unlink()
    except FileNotFoundError:
        return


def _commit_recovery_status(
    repo_root: Path,
    status: dict[str, Any],
    *,
    event_actions: list[Callable[[], Any]] | None = None,
) -> dict[str, Any]:
    existed, raw_text = _snapshot_recovery_status(repo_root)
    _save_recovery_status(repo_root, status)
    try:
        for action in event_actions or []:
            action()
    except Exception:
        _restore_recovery_status(repo_root, existed=existed, raw_text=raw_text)
        raise
    return status


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


def _routing_plan_path(record: dict[str, Any]) -> str:
    plan_path = str(record.get("plan_path") or "").strip()
    if plan_path:
        return plan_path
    scope_items = record.get("scope_items")
    if isinstance(scope_items, list):
        for item in scope_items:
            text = str(item or "").strip()
            if text.endswith(".md"):
                return text
    return ""


def _recovery_event_context(
    repo_root: Path,
    *,
    result: dict[str, Any] | None = None,
    status: dict[str, Any] | None = None,
) -> tuple[str, str | None]:
    result = result or {}
    status = status or {}
    task_id = str(
        result.get("task_id")
        or status.get("task_id")
        or ""
    ).strip()
    plan_path = str(
        result.get("plan_path")
        or status.get("plan_path")
        or ""
    ).strip()
    if not task_id or not plan_path:
        try:
            routing_record = load_routing_record(repo_root)
        except Exception:
            routing_record = {}
        if not task_id:
            task_id = str(routing_record.get("task_id") or "").strip()
        if not plan_path:
            plan_path = _routing_plan_path(routing_record)
    return task_id or "[PIPELINE-RECOVERY]", plan_path or None


def _emit_recovery_event(
    repo_root: Path,
    *,
    status: dict[str, Any],
    event_type: str,
    state: str,
    transition_key: str,
    summary: str,
    reason: str,
    artifact_paths: dict[str, str] | None = None,
) -> None:
    task_id, plan_path = _recovery_event_context(repo_root, status=status)
    emit_pipeline_agent_event(
        repo_root,
        event_type=event_type,
        wave_id=str(status.get("wave_id") or "").strip(),
        task_id=task_id,
        plan_path=plan_path,
        phase="recovery_gate",
        state=state,
        transition_key=transition_key,
        summary=summary,
        reason=reason,
        artifact_paths=artifact_paths,
    )


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
    task_id, plan_path = _recovery_event_context(repo_root, result=result)
    status = {
        "active": True,
        "invocation_id": invocation_id,
        "wave_id": wave_id,
        "task_id": task_id,
        "plan_path": plan_path or "",
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
    return _commit_recovery_status(
        repo_root,
        status,
        event_actions=[
            lambda status=status, invocation_id=invocation_id, wave_id=wave_id: _emit_recovery_event(
                repo_root,
                status=status,
                event_type="recovery_started",
                state=str(status.get("state") or "recovery_started"),
                transition_key=f"{invocation_id}:recovery_started",
                summary=f"Recovery started for {wave_id}",
                reason=str(status.get("reason") or "recovery started"),
                artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
            )
        ],
    )


def _update_recovery_status(repo_root: Path, **updates: Any) -> dict[str, Any]:
    status = _load_recovery_status(repo_root)
    if (
        status
        and not bool(status.get("active", False))
        and "active" not in updates
        and "invocation_id" not in updates
        and "started_at" not in updates
    ):
        return status
    prior_state = str(status.get("state") or "")
    status.update(updates)
    status["updated_at"] = _now_iso()
    new_state = str(status.get("state") or "")
    event_actions: list[Callable[[], Any]] = []
    if new_state and new_state != prior_state:
        transition_key = (
            f"{status.get('invocation_id', 'recovery')}:"
            f"{new_state}:{status.get('current_iteration', 0)}"
        )
        event_actions.append(
            lambda status=status, new_state=new_state, transition_key=transition_key: _emit_recovery_event(
                repo_root,
                status=status,
                event_type="recovery_state_changed",
                state=new_state,
                transition_key=transition_key,
                summary=f"Recovery state changed to {new_state}",
                reason=str(status.get("detail") or status.get("reason") or new_state),
                artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
            )
        )
        if new_state == "resolved_by_later_success":
            event_actions.append(
                lambda status=status, new_state=new_state, transition_key=transition_key: _emit_recovery_event(
                    repo_root,
                    status=status,
                    event_type="recovery_returned",
                    state=new_state,
                    transition_key=(
                        f"{status.get('invocation_id', 'recovery')}:"
                        "recovery_returned"
                    ),
                    summary="Recovery returned to normal pipeline execution",
                    reason=str(status.get("detail") or status.get("reason") or new_state),
                    artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
                )
            )
    return _commit_recovery_status(repo_root, status, event_actions=event_actions)


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
    status = _load_recovery_status(repo_root)
    prior_state = str(status.get("state") or "")
    status.update(
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
    status["updated_at"] = _now_iso()
    new_state = str(status.get("state") or "")
    event_actions: list[Callable[[], Any]] = []
    if new_state and new_state != prior_state:
        transition_key = (
            f"{status.get('invocation_id', 'recovery')}:"
            f"{new_state}:{status.get('current_iteration', 0)}"
        )
        event_actions.append(
            lambda status=status, new_state=new_state, transition_key=transition_key: _emit_recovery_event(
                repo_root,
                status=status,
                event_type="recovery_state_changed",
                state=new_state,
                transition_key=transition_key,
                summary=f"Recovery state changed to {new_state}",
                reason=str(status.get("detail") or status.get("reason") or new_state),
                artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
            )
        )
    if not recovered:
        transition_key = (
            f"{status.get('invocation_id', 'recovery')}:"
            f"recovery_failed:{outcome or state}"
        )
        event_actions.append(
            lambda status=status, state=state, outcome=outcome, detail=detail, transition_key=transition_key: _emit_recovery_event(
                repo_root,
                status=status,
                event_type="recovery_failed",
                state=str(status.get("state") or state),
                transition_key=transition_key,
                summary=f"Recovery failed with outcome {outcome or state}",
                reason=_excerpt(detail),
                artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
                )
            )
        if outcome == "escalated" or "escalated" in state:
            event_actions.append(
                lambda status=status, state=state, outcome=outcome, detail=detail: _emit_recovery_event(
                    repo_root,
                    status=status,
                    event_type="recovery_escalated",
                    state=str(status.get("state") or state),
                    transition_key=(
                        f"{status.get('invocation_id', 'recovery')}:"
                        f"recovery_escalated:{outcome or state}"
                    ),
                    summary=f"Recovery escalated with outcome {outcome or state}",
                    reason=_excerpt(detail),
                    artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
                )
            )
        if exhausted:
            event_actions.append(
                lambda status=status, state=state, outcome=outcome, detail=detail: _emit_recovery_event(
                    repo_root,
                    status=status,
                    event_type="pipeline_hard_fail",
                    state="hard_fail",
                    transition_key=(
                        f"{status.get('invocation_id', 'recovery')}:"
                        f"pipeline_hard_fail:{outcome or state}"
                    ),
                    summary=f"Pipeline hard-failed after recovery {outcome or state}",
                    reason=_excerpt(detail),
                    artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
                )
            )
    else:
        transition_key = (
            f"{status.get('invocation_id', 'recovery')}:"
            f"recovery_succeeded:{outcome or state}"
        )
        event_actions.append(
            lambda status=status, state=state, outcome=outcome, detail=detail, transition_key=transition_key: _emit_recovery_event(
                repo_root,
                status=status,
                event_type="recovery_succeeded",
                state=str(status.get("state") or state),
                transition_key=transition_key,
                summary=f"Recovery succeeded with outcome {outcome or state}",
                reason=_excerpt(detail),
                artifact_paths={"recovery_status": str(RECOVERY_STATUS_FILE)},
            )
        )
    return _commit_recovery_status(repo_root, status, event_actions=event_actions)


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
MAX_UPSTREAM_CONNECTIVITY_ATTEMPTS_PER_TUPLE = 6


def _max_attempts_for_failure(fc: FailureClass) -> int:
    if fc == FailureClass.UPSTREAM_CONNECTIVITY:
        return MAX_UPSTREAM_CONNECTIVITY_ATTEMPTS_PER_TUPLE
    return MAX_ATTEMPTS_PER_TUPLE


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
                _step = _effective_result_step(result)
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
    step = _effective_result_step(result)

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

    max_attempts = _max_attempts_for_failure(fc)
    if prior >= max_attempts:
        detail = (
            f"max {max_attempts} attempts reached for "
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


# ---------------------------------------------------------------------------
# Subagent warming: learning store → prompt injection
# ---------------------------------------------------------------------------

# Static mapping of agent names to relevant FailureClass values for filtering.
# None = unfiltered (all entries).  List = include only matching failure_class.
# SCOPE-DOWN: taxonomy has no domain-level categories (security, complexity, etc.)
# for non-pipeline agents; those receive unfiltered.  Deferred pending FailureClass
# taxonomy extension per PipelineRecovery.v0.md:280.
_AGENT_FAILURE_CLASS_MAP: dict[str, list[str] | None] = {
    # Implementation agents — pipeline-subset: only failure classes
    # that produce actionable learnings for build/test execution
    "implementer":      ["test_failure", "git_staging_conflict", "process_timeout",
                         "implementer_stale", "needs_phase_b", "mixed_staging",
                         "max_turns_reached", "pre_push_failed", "stage_failed",
                         "implementer_error", "bridge_error",
                         "l4_contract_violation"],
    # Depth agents — pipeline-subset: test/edge-case execution focus
    "grounding":        ["test_failure", "needs_phase_b", "unknown_error"],
    "fuzzer":           ["test_failure", "unknown_error", "process_timeout"],
    # All other agents — unfiltered (SCOPE-DOWN)
    "verifier":         None,
    "adversary":        None,
    "expert":           None,
    "structural-proof": None,
    "translator":       None,
    "visualizer":       None,
    "advisor":          None,
}

# Confusable-character translation table for prompt-safety sanitization.
# Greek/Cyrillic visual lookalikes mapped to Latin equivalents.
# Same table as shared_agent_utils._KEYWORD_CONFUSABLE_TRANSLATION.
_LEARNING_CONFUSABLE_TRANSLATION = str.maketrans({
    "Α": "A", "А": "A",
    "Β": "B", "В": "B",
    "С": "C",
    "Ε": "E", "Е": "E",
    "Η": "H",
    "І": "I", "Ι": "I",
    "Κ": "K",
    "М": "M",
    "Ν": "N",
    "Ο": "O", "О": "O",
    "Ρ": "P", "Р": "P",
    "Ѕ": "S",
    "Τ": "T", "Т": "T",
    "Υ": "Y",
    "Χ": "X",
    "а": "a",
    "е": "e",
    "і": "i",
    "ј": "j",
    "ο": "o", "о": "o",
    "р": "p",
    "ѕ": "s",
    "с": "c",
    "х": "x",
    "у": "y",
})

_LEARNING_ZERO_WIDTH_RE = re.compile(
    r'[\u000b\u000c\u0085\u200b\u200c\u200d\u2028\u2029\u2060\ufeff]'
)


def _sanitize_learning_output(text: str, max_len: int = 4000) -> str:
    """Sanitize learning store output before prompt injection.

    Replicates the complete security-relevant measure set from
    shared_agent_utils.sanitize_for_prompt using only stdlib (re, unicodedata).
    This avoids importing tools.runners.shared_agent_utils into executor-side
    code (that module has import-time side effects: env clearing, SDK monkey-patching).

    Steps:
    1. NFKC Unicode normalization
    2. Confusable-character translation (Greek/Cyrillic → Latin)
    3. Zero-width/line-separator control character stripping
    4. Triple-backtick escaping
    5. Newline/CR replacement with space
    6. Instruction-like pattern redaction (word-bounded)
    7. Verdict-marker redaction (case-insensitive)
    8. Truncation to max_len AFTER sanitization
    """
    if not text:
        return ""

    # 1. NFKC normalization
    text = unicodedata.normalize('NFKC', text)

    # 2. Confusable-character translation
    text = text.translate(_LEARNING_CONFUSABLE_TRANSLATION)

    # 3. Strip zero-width characters
    text = _LEARNING_ZERO_WIDTH_RE.sub('', text)

    # 4. Escape triple backticks
    text = text.replace('```', '` ` `')

    # 5. Replace newlines/carriage returns
    text = text.replace('\n', ' ').replace('\r', ' ')

    # 6. Instruction-like pattern redaction (word-bounded)
    word_patterns = [
        r'ignore\s+previous',
        r'disregard',
        r'new\s+instructions',
        r'system\s+prompt',
        r'forget\s+everything',
        r'you\s+are\s+now',
        r'override\s+instructions',
    ]
    for pattern in word_patterns:
        text = re.sub(r'\b' + pattern + r'\b', '[REDACTED]', text, flags=re.IGNORECASE)

    # 7. Verdict-marker redaction
    verdict_patterns = [
        r'VERDICT\s*:',
        r'OVERALL_VERDICT\s*:',
    ]
    for pattern in verdict_patterns:
        text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)

    # 8. Truncate AFTER sanitization, at entry boundary (never mid-entry).
    # After step 5, newlines are spaces; entries are delimited by " - [".
    if len(text) > max_len:
        truncated = text[:max_len]
        # Find the last entry boundary so we don't split mid-record.
        last_boundary = truncated.rfind(' - [')
        if last_boundary > 0:
            text = truncated[:last_boundary]
        else:
            text = truncated

    return text


def load_relevant_learnings(
    agent_name: str,
    files: list[str],
    repo_root: Path,
) -> str:
    """Load learning store patterns relevant to an agent, sanitized for prompt injection.

    Reads three data sources (priority order):
    1. learned_patterns.json via _load_learning_store() — promoted patterns with
       full metadata (failure_class, action, fingerprint, success_count, etc.)
    2. FIXED entries from .claude/rules/learning.md via _load_session_fixed_entries()
       — session-captured fixes with fingerprint + action only.
    3. ALL learning.md entries via _load_learning_md_entries() — curated diagnostic
       knowledge with fingerprints, root causes, and structural fixes.  This is the
       richest source (46+ entries) and the primary channel for warming subagents with
       pipeline knowledge they cannot see from .claude/rules/ (separate sessions).

    Filters: JSON entries by failure_class (_AGENT_FAILURE_CLASS_MAP).
    Learning.md entries by category (_AGENT_CATEGORY_MAP).
    FIXED entries are included unfiltered (no metadata to filter on).

    Budget: 4000 characters total.  Store entries first (most validated),
    then learning.md entries (most numerous/rich), then FIXED entries.
    Truncates at entry boundaries.

    Returns sanitized formatted string, or empty string on no content/error.
    """
    try:
        store = _load_learning_store(repo_root)
        fixed_entries = _load_session_fixed_entries(repo_root)
        md_entries = _load_learning_md_entries(repo_root)
    except Exception:
        return ""

    # Collect JSON pattern entries (Tier 1: promoted, validated)
    patterns = store.get("patterns", {})
    allowed_classes = _AGENT_FAILURE_CLASS_MAP.get(agent_name)  # None = unfiltered

    json_entries: list[dict] = []
    for _pid, record in patterns.items():
        if not isinstance(record, dict):
            continue
        fc = record.get("failure_class", "")
        if allowed_classes is not None and fc not in allowed_classes:
            continue
        json_entries.append(record)

    json_entries.sort(key=lambda r: r.get("updated_at", ""), reverse=True)

    # Filter learning.md entries by category for this agent (Tier 2: curated)
    allowed_categories = _AGENT_CATEGORY_MAP.get(agent_name)  # None = unfiltered
    filtered_md: list[dict] = []
    for entry in md_entries:
        cat = entry.get("category", "")
        if allowed_categories is not None and cat not in allowed_categories:
            continue
        filtered_md.append(entry)
    # Sort by date descending — curated entries at the top of learning.md
    # are newest-first, but _export_to_learning_md() appends promoted entries
    # at EOF which would otherwise be consumed last under the budget cap.
    filtered_md.sort(key=lambda e: e.get("date", ""), reverse=True)

    # Format entries within budget
    MAX_LEN = 4000
    header = "## Learning Context\n\nKnown pipeline patterns and fixes:\n"
    parts: list[str] = []
    current_len = len(header)

    # JSON store entries first (most validated)
    for rec in json_entries:
        fp = rec.get("fingerprint", "")
        action = rec.get("action", "")
        fc = rec.get("failure_class", "")
        sc = rec.get("success_count", 0)
        entry = f"- [{fc}] {fp} → {action} (success:{sc})"
        entry_len = len(entry) + 1
        if current_len + entry_len > MAX_LEN:
            break
        parts.append(entry)
        current_len += entry_len

    # Learning.md entries second (curated diagnostic knowledge)
    for md_rec in filtered_md:
        fp = md_rec.get("fingerprint", "")
        cat = md_rec.get("category", "")
        body = md_rec.get("body", "")
        # Truncate body to first sentence or 120 chars for budget
        short_body = body[:120].split(". ")[0] if body else ""
        entry = f"- [{cat}] {fp}"
        if short_body:
            entry += f" — {short_body}"
        entry_len = len(entry) + 1
        if current_len + entry_len > MAX_LEN:
            break
        parts.append(entry)
        current_len += entry_len

    # FIXED entries last (session-captured, least metadata)
    for fix in reversed(fixed_entries):
        fp = fix.get("fingerprint", "")
        action = fix.get("action", "")
        entry = f"- [session-fix] {fp} → {action}"
        entry_len = len(entry) + 1
        if current_len + entry_len > MAX_LEN:
            break
        parts.append(entry)
        current_len += entry_len

    if not parts:
        return ""

    body = "\n".join(parts)
    raw_output = header + body

    return _sanitize_learning_output(raw_output, max_len=MAX_LEN)
