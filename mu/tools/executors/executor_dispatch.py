#!/usr/bin/env python3
"""Executor dispatcher: reads post-merge routing record and invokes the correct executor.

This is the entry point for automated workflow execution. The post-merge
supervisor emits a routing decision; this script reads it and dispatches
to the appropriate executor.

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent  # mu/tools/executors -> repo root
AGENTS_DIR = SCRIPT_DIR.parent / "agents"
OBSERVABILITY_DIR = SCRIPT_DIR.parent / "observability"
POST_MERGE_PACKAGE_NAME = "post_merge_package.json"

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        DEFAULT_EXECUTOR_CONFIG,
        agent_bus_path,
        agent_bus_relpath,
        load_executor_config as _common_load_executor_config,
        load_routing_record as _common_load_routing_record,
        build_and_write_routing_record as _common_build_and_write_routing_record,
        ROUTING_RECORD_PATH as _COMMON_ROUTING_RECORD_PATH,
        apply_recovery_config_env_overrides,
        merge_executor_config_overrides,
        ensure_git_worktree_clean,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        emit_pipeline_agent_event,
        normalize_wave_id,
        packet_status_is_completed,
        process_descendants,
        read_control_plane_packet_status,
        read_control_plane_packet_wave_id,
        read_founder_ordered_task_state,
        resolve_agent_bus_dir,
        routing_record_path as _common_routing_record_path,
        terminate_process_tree,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    DEFAULT_EXECUTOR_CONFIG = _mod.DEFAULT_EXECUTOR_CONFIG
    agent_bus_path = _mod.agent_bus_path
    agent_bus_relpath = _mod.agent_bus_relpath
    _common_load_executor_config = _mod.load_executor_config
    _common_load_routing_record = _mod.load_routing_record
    _common_build_and_write_routing_record = _mod.build_and_write_routing_record
    _COMMON_ROUTING_RECORD_PATH = _mod.ROUTING_RECORD_PATH
    apply_recovery_config_env_overrides = _mod.apply_recovery_config_env_overrides
    merge_executor_config_overrides = _mod.merge_executor_config_overrides
    ensure_git_worktree_clean = _mod.ensure_git_worktree_clean
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError
    emit_pipeline_agent_event = _mod.emit_pipeline_agent_event
    normalize_wave_id = _mod.normalize_wave_id
    packet_status_is_completed = _mod.packet_status_is_completed
    process_descendants = _mod.process_descendants
    read_control_plane_packet_status = _mod.read_control_plane_packet_status
    read_control_plane_packet_wave_id = _mod.read_control_plane_packet_wave_id
    read_founder_ordered_task_state = _mod.read_founder_ordered_task_state
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir
    _common_routing_record_path = _mod.routing_record_path
    terminate_process_tree = _mod.terminate_process_tree

try:
    from pipeline_monitor_identity import (
        DEFAULT_TMUX_SESSION,
        MonitorIdentityError,
        load_monitor_lanes,
        resolve_monitor_identity,
    )
except ImportError:
    import importlib.util as _ilu
    _identity_path = OBSERVABILITY_DIR / "pipeline_monitor_identity.py"
    _identity_spec = _ilu.spec_from_file_location("pipeline_monitor_identity", str(_identity_path))
    _identity_mod = _ilu.module_from_spec(_identity_spec)
    assert _identity_spec.loader is not None
    sys.modules["pipeline_monitor_identity"] = _identity_mod
    _identity_spec.loader.exec_module(_identity_mod)
    DEFAULT_TMUX_SESSION = _identity_mod.DEFAULT_TMUX_SESSION
    MonitorIdentityError = _identity_mod.MonitorIdentityError
    load_monitor_lanes = _identity_mod.load_monitor_lanes
    resolve_monitor_identity = _identity_mod.resolve_monitor_identity

try:
    from recovery_gate import (
        attempt_recovery,
        clear_stale_recovery_status_on_success,
        _normalize_phase_a_retry_plan_name,
    )
except ImportError:
    import importlib.util as _ilu
    _recovery_path = SCRIPT_DIR / "recovery_gate.py"
    _recovery_spec = _ilu.spec_from_file_location("recovery_gate", str(_recovery_path))
    _recovery_mod = _ilu.module_from_spec(_recovery_spec)
    assert _recovery_spec.loader is not None
    sys.modules["recovery_gate"] = _recovery_mod
    _recovery_spec.loader.exec_module(_recovery_mod)
    attempt_recovery = _recovery_mod.attempt_recovery
    clear_stale_recovery_status_on_success = _recovery_mod.clear_stale_recovery_status_on_success
    _normalize_phase_a_retry_plan_name = _recovery_mod._normalize_phase_a_retry_plan_name

try:
    from meta_bridge_supervisor import compute_repo_state as _compute_repo_state
except ImportError:
    import importlib.util as _ilu
    _meta_path = REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
    _meta_spec = _ilu.spec_from_file_location("meta_bridge_supervisor", str(_meta_path))
    _meta_mod = _ilu.module_from_spec(_meta_spec)
    assert _meta_spec.loader is not None
    sys.modules["meta_bridge_supervisor"] = _meta_mod
    _meta_spec.loader.exec_module(_meta_mod)
    _compute_repo_state = _meta_mod.compute_repo_state

# Routing token → executor mapping
ROUTING_DISPATCH = {
    "CONTINUE_DIALECTIC": "dialectic_executor",
    "ROUTE_PHASE_A": "phase_a_executor",
    "ROUTE_PHASE_B": "phase_b_executor",
    "UPDATE_TRACKER_ONLY": "commit_executor",
    # COMMIT_GO / COMMIT_GO_HOLD_PUSH come from pre-commit supervisor, not post-merge
    "COMMIT_GO": "commit_executor",
    "COMMIT_GO_HOLD_PUSH": "commit_executor",
}

# Tokens that stop and require human intervention
STOP_TOKENS = {"STOP_FOR_FOUNDER", "STOP_FOR_TRIAGE_DISCUSSION"}

# Dispatch-level statuses that are never retryable.
# - success/stopped/error/not_implemented/stale: config or structural outcomes.
# NOTE: "timeout" was removed — it is now routed through the recovery gate
# where Tier 2 fix_process_timeout adjusts the timeout and grants a retry.
_NON_RETRYABLE_DISPATCH_STATUSES = frozenset({
    "success", "held", "stopped", "error", "not_implemented", "stale",
})

# Executor-reported statuses that indicate a terminal outcome requiring
# founder intervention — retrying would just re-produce the same result.
# - question_for_founder: bridge QUESTION requires human input
# - max_rounds_reached: bridge loop exhausted without convergence
# - supervisor_rejected: pre-commit supervisor returned non-COMMIT_GO
#   (e.g. STOP_FOR_FOUNDER) — founder decision required
_TERMINAL_EXECUTOR_STATUSES = frozenset({
    "question_for_founder",
    "max_rounds_reached",
    "supervisor_rejected",
})

# Available executor scripts
AVAILABLE_EXECUTORS = {"commit_executor", "phase_b_executor", "phase_a_executor", "dialectic_executor"}
_JSON_EXECUTORS = frozenset({
    "commit_executor",
    "phase_b_executor",
    "phase_a_executor",
    "dialectic_executor",
})
SURFACE_COMMANDS = {
    "phase-a",
    "phase-b",
    "pre-commit-supervisor",
    "commit",
    "post-merge-supervisor",
}


def _emit_executor_hard_fail_event(
    repo_root: Path,
    result: dict[str, Any],
    wave_id: str,
    record: dict[str, Any] | None = None,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Emit the dispatcher-owned terminal failure event from recovery facts."""
    record = record or {}
    recovery = result.get("recovery")
    recovery = recovery if isinstance(recovery, dict) else {}
    executor_name = str(result.get("executor") or result.get("step") or "dispatcher")
    status = str(result.get("status") or "failed")
    decision = str(result.get("decision") or record.get("decision") or "unknown")
    failure_class = str(recovery.get("failure_class") or result.get("failure_class") or "unknown")
    outcome = str(recovery.get("outcome") or recovery.get("action") or "terminal")
    normalized_wave_id = normalize_wave_id(
        wave_id
        or str(record.get("wave_name") or record.get("wave_id") or "")
        or str(result.get("wave_id") or result.get("wave_name") or "")
    )
    transition_key = ":".join([
        normalized_wave_id,
        executor_name,
        status,
        decision,
        failure_class,
        outcome,
    ])
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=bus_dir,
        event_type="executor_hard_fail",
        wave_id=normalized_wave_id,
        task_id=str(
            result.get("task_id")
            or record.get("task_id")
            or "[PIPELINE-RECOVERY]"
        ).strip(),
        plan_path=str(record.get("tracked_packet") or result.get("plan_path") or ""),
        phase="executor_dispatch",
        state=status,
        transition_key=transition_key,
        summary=f"{executor_name} failed after dispatcher recovery handling",
        reason=str(result.get("message") or result.get("summary") or failure_class),
        artifact_paths={},
    )


def _configured_bridge_loop_limit(config: dict[str, Any], key: str) -> int:
    """Return a positive configured bridge loop limit with default fallback."""
    default_value = DEFAULT_EXECUTOR_CONFIG.get("bridge_loop_limits", {}).get(key, 1)
    value = config.get("bridge_loop_limits", {}).get(key, default_value)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default_value)
    if parsed < 1:
        return int(default_value)
    return parsed


DEFAULT_CONFIG_PATH = SCRIPT_DIR / "executor_config.json"
PHASE_B_RECOVERY_PLAN_ENV = "RCX_RECOVERY_PHASE_B_PLAN_PATH"
PHASE_B_RECOVERY_PLAN_WAVE_ENV = "RCX_RECOVERY_PHASE_B_PLAN_WAVE_ID"


class DispatchError(RuntimeError):
    """Raised when dispatch cannot proceed."""


class ControlSurfaceError(RuntimeError):
    """Raised when a modular surface invocation is malformed."""


def _phase_b_recovery_plan_from_env(record: dict[str, Any]) -> str:
    """Return a recovery-seeded Phase B plan only when it is wave-bound."""
    plan_path = os.environ.get(PHASE_B_RECOVERY_PLAN_ENV, "").strip()
    if not plan_path:
        return ""
    expected_wave_raw = str(record.get("wave_name") or record.get("wave_id") or "").strip()
    env_wave_raw = os.environ.get(PHASE_B_RECOVERY_PLAN_WAVE_ENV, "").strip()
    expected_wave = normalize_wave_id(expected_wave_raw) if expected_wave_raw else ""
    env_wave = normalize_wave_id(env_wave_raw) if env_wave_raw else ""
    if (
        not expected_wave
        or expected_wave == "wave-unknown"
        or not env_wave
        or env_wave == "wave-unknown"
        or env_wave != expected_wave
    ):
        return ""
    return plan_path


def _bind_phase_b_recovery_plan_wave(record: dict[str, Any], repo_root: Path) -> None:
    """Bind a recovery plan hint to record identity using the plan path itself."""
    plan_path = os.environ.get(PHASE_B_RECOVERY_PLAN_ENV, "").strip()
    env_wave_raw = os.environ.get(PHASE_B_RECOVERY_PLAN_WAVE_ENV, "").strip()
    if not plan_path or not env_wave_raw:
        return
    env_wave = normalize_wave_id(env_wave_raw)
    if env_wave == "wave-unknown":
        return
    current_wave_raw = str(record.get("wave_name") or record.get("wave_id") or "").strip()
    current_wave = normalize_wave_id(current_wave_raw) if current_wave_raw else ""
    if current_wave and current_wave != "wave-unknown":
        return
    plan_wave = _phase_b_plan_wave_id(repo_root, plan_path)
    if plan_wave and plan_wave == env_wave:
        record["wave_name"] = env_wave


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load executor config using the canonical shared defaults/merge rules."""
    path = config_path or DEFAULT_CONFIG_PATH
    if path == DEFAULT_CONFIG_PATH:
        return _common_load_executor_config(REPO_ROOT)
    if not path.exists():
        return apply_recovery_config_env_overrides(merge_executor_config_overrides({}))
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return apply_recovery_config_env_overrides(merge_executor_config_overrides(loaded))


def load_routing_record(
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load and validate the post-merge routing record.

    Delegates to executor_common.load_routing_record (canonical implementation).
    Wraps ExecutorCommonError as DispatchError for backward compatibility.
    """
    try:
        return _common_load_routing_record(repo_root, bus_dir=bus_dir)
    except ExecutorCommonError as exc:
        raise DispatchError(str(exc)) from exc


def validate_routing_record_freshness(record: dict[str, Any], repo_root: Path) -> tuple[bool, str]:
    """Check that the routing record's state_sha matches current repo state."""
    record_sha = record.get("state_sha", "")
    if not record_sha:
        return False, "Routing record has no state_sha — cannot verify freshness"

    try:
        current_sha = _compute_repo_state(repo_root).state_sha
    except Exception as exc:
        return False, f"Cannot compute repo state: {exc}"

    if current_sha != record_sha:
        return False, (
            f"Routing record is stale: record state_sha={record_sha[:8]}, "
            f"current={current_sha[:8]}"
        )

    return True, "fresh"


def _canonical_routing_record_path(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
    return _common_routing_record_path(repo_root, bus_dir).resolve()


def _load_routing_record_json(path: Path) -> dict[str, Any] | None:
    """Best-effort JSON object load without imposing freshness validation."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _matches_canonical_routing_record(
    record: dict[str, Any],
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> bool:
    """Return True when the inline record still matches the canonical routing file."""
    canonical_record = _load_routing_record_json(_canonical_routing_record_path(repo_root, bus_dir))
    return canonical_record == record


def resolve_executor(decision: str) -> str | None:
    """Map a routing decision to an executor name."""
    return ROUTING_DISPATCH.get(decision)


def _sanitize_plan_name(candidate_text: str, fallback: str = "plan_unknown") -> str:
    """Convert candidate text into a safe plan slug."""
    raw = (candidate_text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", raw)
    if not tokens:
        tokens = re.findall(r"[a-z0-9]+", fallback.lower())
    slug = "_".join(tokens).strip("_")
    return (slug or "plan_unknown")[:50]


def _load_routing_record_payload(
    *,
    path_value: Path | None,
    json_value: str | None,
) -> str | None:
    if path_value and json_value:
        raise ControlSurfaceError("Provide only one of --routing-record-path or --routing-record-json")
    if path_value:
        try:
            return path_value.read_text(encoding="utf-8")
        except OSError as exc:
            raise ControlSurfaceError(f"Cannot read routing record: {exc}") from exc
    return json_value


def _canonicalize_surface_task_id(task_id: str) -> str:
    """Normalize surface CLI task IDs into bracketed TASKS.md token form."""
    clean = str(task_id or "").strip()
    if not clean:
        return ""
    if clean.startswith("[") and clean.endswith("]"):
        return clean
    return f"[{clean}]"


def _routing_candidate_dicts(record: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = record.get("next_candidates")
    if not isinstance(candidates, list):
        return []
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def _selected_routing_candidate_dicts(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Return candidates eligible for routing, with legacy fallback."""
    candidates = _routing_candidate_dicts(record)
    bounded = [
        candidate for candidate in candidates
        if candidate.get("bounded") is True
    ]
    return bounded or candidates


def _surface_phase_b_plan_from_routing_payload(routing_payload: str | None) -> str | None:
    """Prefer tracked_packet from a Phase B routing payload when no explicit plan is given."""
    if not routing_payload:
        return None
    try:
        record = json.loads(routing_payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    for candidate in _selected_routing_candidate_dicts(record):
        tracked_packet = str(candidate.get("tracked_packet") or "").strip()
        if tracked_packet:
            return tracked_packet
    return None


def _routing_record_tracked_packet(record: dict[str, Any]) -> str:
    for candidate in _selected_routing_candidate_dicts(record):
        tracked_packet = str(candidate.get("tracked_packet") or "").strip()
        if tracked_packet:
            return tracked_packet
    return ""


def _tasks_backtick_value(line: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*`([^`]+)`", line)
    return match.group(1).strip() if match else ""


_TASKS_TRACKER_NOTE_HEADER_RE = re.compile(
    r"^- Tracker sync note \([^,]+,\s*([^)]+)\):\s*\*\*[^*]+\*\*"
)


def _line_is_next_codex_post_redteam_queue_entry(line: str) -> bool:
    return (
        "FOUNDER-ORDERED-REDTEAM-" in line
        or "NEXT-CODEX-POST-REDTEAM" in line
    )


def _tasks_control_plane_packet_value(repo_root: Path, line: str) -> str:
    packet = _tasks_backtick_value(line, "Packet")
    if not packet.startswith("reports/control_plane/"):
        return ""
    candidate = Path(packet)
    if candidate.is_absolute() or ".." in candidate.parts:
        return ""
    full_path = (repo_root / packet).resolve()
    try:
        full_path.relative_to((repo_root / "reports" / "control_plane").resolve())
    except ValueError:
        return ""
    return packet


def _founder_ordered_task_packet_for_wave(repo_root: Path, wave_id: str) -> str:
    normalized_wave = normalize_wave_id(wave_id)
    if not normalized_wave:
        return ""
    try:
        lines = (repo_root / "TASKS.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        if not _line_is_next_codex_post_redteam_queue_entry(line):
            continue
        tracker_match = _TASKS_TRACKER_NOTE_HEADER_RE.match(line)
        entry_wave = normalize_wave_id(_tasks_backtick_value(line, "Wave ID"))
        if (not entry_wave or entry_wave == "wave-unknown") and tracker_match:
            entry_wave = normalize_wave_id(tracker_match.group(1))
        if entry_wave != normalized_wave:
            continue
        packet = _tasks_control_plane_packet_value(repo_root, line)
        if not packet:
            return ""
        if tracker_match:
            return packet
        if (repo_root / packet).is_file():
            return packet
        return ""
    return ""


def _enrich_founder_ordered_tracked_packets(
    repo_root: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    """Fill missing tracked_packet from TASKS.md to avoid date-slug duplicates."""
    candidates = record.get("next_candidates")
    if not isinstance(candidates, list):
        return record
    changed = False
    enriched_candidates: list[Any] = []
    record_wave = str(record.get("wave_name") or record.get("wave_id") or "").strip()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            enriched_candidates.append(candidate)
            continue
        enriched = dict(candidate)
        if not str(enriched.get("tracked_packet") or "").strip():
            wave = str(
                enriched.get("wave_name")
                or enriched.get("wave_id")
                or enriched.get("candidate")
                or record_wave
                or ""
            ).strip()
            packet = _founder_ordered_task_packet_for_wave(repo_root, wave)
            if packet:
                enriched["tracked_packet"] = packet
                changed = True
        enriched_candidates.append(enriched)
    if not changed:
        return record
    enriched_record = dict(record)
    enriched_record["next_candidates"] = enriched_candidates
    return enriched_record


def _completed_routing_candidates(
    repo_root: Path,
    record: dict[str, Any],
) -> list[dict[str, str]]:
    completed: list[dict[str, str]] = []
    allow_completed_reroute = bool(record.get("allow_completed_tracked_packet"))
    for candidate in _selected_routing_candidate_dicts(record):
        tracked_packet = str(candidate.get("tracked_packet") or "").strip()
        if not tracked_packet:
            continue
        status = read_control_plane_packet_status(repo_root, tracked_packet)
        if packet_status_is_completed(status) and not allow_completed_reroute:
            completed.append(
                {
                    "tracked_packet": tracked_packet,
                    "status": str(status or ""),
                    "candidate": str(candidate.get("candidate") or ""),
                }
            )
            continue
        task_wave = str(
            candidate.get("wave_name")
            or candidate.get("wave_id")
            or record.get("wave_name")
            or record.get("wave_id")
            or candidate.get("candidate")
            or ""
        )
        task_state = read_founder_ordered_task_state(
            repo_root,
            wave_id=task_wave,
            tracked_packet=tracked_packet,
        )
        if packet_status_is_completed(task_state) and not allow_completed_reroute:
            completed.append(
                {
                    "tracked_packet": tracked_packet,
                    "status": f"TASKS.md state: {task_state}",
                    "candidate": str(candidate.get("candidate") or ""),
                }
            )
    return completed


def _completed_candidate_stop_result(
    repo_root: Path,
    record: dict[str, Any],
    *,
    decision: str,
    executor_name: str,
) -> dict[str, Any] | None:
    completed = _completed_routing_candidates(repo_root, record)
    if not completed:
        return None
    packets = ", ".join(
        f"{item['tracked_packet']} (Status: {item['status']})"
        for item in completed
    )
    return {
        "status": "stopped",
        "decision": decision,
        "executor": executor_name,
        "summary": "Routing stopped because the selected bounded packet is already complete.",
        "message": (
            "Refusing to dispatch an already-complete bounded candidate. "
            f"Refresh the post-merge routing record to the next open packet. Completed: {packets}"
        ),
        "completed_candidates": completed,
        "request_for_agent": (
            "Refresh post-merge routing from the canonical open queue before "
            "retrying dispatcher; do not rerun completed packets."
        ),
        "request_for_claude": (
            "Refresh post-merge routing from the canonical open queue before "
            "retrying dispatcher; do not rerun completed packets."
        ),
    }


def _routing_candidate_wave_id(
    record: dict[str, Any],
    candidate: dict[str, Any],
) -> str:
    wave = str(
        candidate.get("wave_name")
        or candidate.get("wave_id")
        or record.get("wave_name")
        or record.get("wave_id")
        or candidate.get("candidate")
        or ""
    ).strip()
    normalized = normalize_wave_id(wave) if wave else ""
    return normalized if normalized != "wave-unknown" else ""


def _routing_candidate_explicit_wave_id(candidate: dict[str, Any]) -> str:
    wave = str(candidate.get("wave_name") or candidate.get("wave_id") or "").strip()
    normalized = normalize_wave_id(wave) if wave else ""
    return normalized if normalized != "wave-unknown" else ""


def _routing_record_wave_id(record: dict[str, Any]) -> str:
    wave = str(record.get("wave_name") or record.get("wave_id") or "").strip()
    normalized = normalize_wave_id(wave) if wave else ""
    return normalized if normalized != "wave-unknown" else ""


def _routing_candidate_label_wave_id(candidate: dict[str, Any]) -> str:
    if candidate.get("bounded") is not True:
        return ""
    wave = str(candidate.get("candidate") or "").strip()
    normalized = normalize_wave_id(wave) if wave else ""
    return normalized if normalized != "wave-unknown" else ""


def _tracked_packet_wave_conflict_result(
    repo_root: Path,
    record: dict[str, Any],
    *,
    decision: str,
    executor_name: str,
) -> dict[str, Any] | None:
    conflicts: list[str] = []
    for candidate in _selected_routing_candidate_dicts(record):
        tracked_packet = str(candidate.get("tracked_packet") or "").strip()
        if not tracked_packet:
            continue
        routed_wave = _routing_candidate_wave_id(record, candidate)
        packet_wave = read_control_plane_packet_wave_id(repo_root, tracked_packet)
        if decision == "ROUTE_PHASE_B":
            explicit_candidate_wave = _routing_candidate_explicit_wave_id(candidate)
            if not explicit_candidate_wave:
                continue
            routed_wave = explicit_candidate_wave
        if not routed_wave or not packet_wave or routed_wave == packet_wave:
            continue
        conflicts.append(
            f"{tracked_packet} declares Wave ID {packet_wave}, "
            f"but the routed candidate is {routed_wave}"
        )
    if not conflicts:
        return None
    return {
        "status": "error",
        "decision": decision,
        "executor": executor_name,
        "summary": "Routing stopped because the selected tracked packet has a conflicting Wave ID.",
        "message": (
            "Refusing to dispatch a bounded candidate whose tracked_packet "
            "declares a different Wave ID. " + "; ".join(conflicts)
        ),
        "request_for_agent": (
            "Regenerate routing against the correct same-wave packet, or update "
            "the packet identity through a bounded Phase A packet before dispatch."
        ),
        "request_for_claude": (
            "Regenerate routing against the correct same-wave packet, or update "
            "the packet identity through a bounded Phase A packet before dispatch."
        ),
    }


def _phase_a_normalized_retry_packet_conflict_result(
    repo_root: Path,
    record: dict[str, Any],
    candidate: dict[str, Any],
    *,
    source_packet: str,
    normalized_packet: str,
    decision: str,
    executor_name: str,
) -> dict[str, Any] | None:
    """Fail closed if a normalized Phase A alias already belongs to another wave."""
    expected_wave = _routing_candidate_authority_wave_id(repo_root, record, candidate)
    if not expected_wave:
        source_wave = read_control_plane_packet_wave_id(repo_root, source_packet)
        expected_wave = source_wave or ""
    alias_wave = read_control_plane_packet_wave_id(repo_root, normalized_packet)
    if not expected_wave or not alias_wave or expected_wave == alias_wave:
        return None
    return {
        "status": "error",
        "decision": decision,
        "executor": executor_name,
        "summary": "Routing stopped because the normalized Phase A retry packet has a conflicting Wave ID.",
        "message": (
            "Refusing to normalize Phase A tracked_packet "
            f"{source_packet} to {normalized_packet}: existing normalized "
            f"packet declares Wave ID {alias_wave}, routed/source wave is {expected_wave}."
        ),
        "request_for_agent": (
            "Regenerate routing against the correct same-wave normalized packet, "
            "or remove the stale alias through a bounded control-plane repair."
        ),
        "request_for_claude": (
            "Regenerate routing against the correct same-wave normalized packet, "
            "or remove the stale alias through a bounded control-plane repair."
        ),
    }


def _same_wave_tasks_authority_exists(
    repo_root: Path,
    *,
    wave_id: str,
    tracked_packet: str,
) -> bool:
    packet = _phase_b_plan_routing_packet(repo_root, tracked_packet)
    if not packet:
        return False
    if _founder_ordered_task_packet_for_wave(repo_root, wave_id) == packet:
        return True
    return _tasks_tracker_entry_exists(
        repo_root,
        wave_id=wave_id,
        tracked_packet=packet,
    )


def _phase_a_normalized_retry_has_source_authority(
    repo_root: Path,
    *,
    wave_id: str,
    tracked_packet: str,
    candidate: dict[str, Any],
) -> bool:
    """Allow a Phase A retry packet only when it is a safe normalization of an authorized packet."""
    authority_packet = _phase_a_normalized_retry_authority_packet(
        repo_root,
        tracked_packet=tracked_packet,
        candidate=candidate,
    )
    if not authority_packet:
        return False
    authority_wave = read_control_plane_packet_wave_id(repo_root, authority_packet)
    if authority_wave and normalize_wave_id(authority_wave) != normalize_wave_id(wave_id):
        return False
    return _same_wave_tasks_authority_exists(
        repo_root,
        wave_id=wave_id,
        tracked_packet=authority_packet,
    )


def _phase_a_normalized_retry_authority_packet(
    repo_root: Path,
    *,
    tracked_packet: str,
    candidate: dict[str, Any],
) -> str:
    if str(candidate.get("recovery_authority") or "") != "phase_a_plan_name_normalization":
        return ""
    packet = _phase_b_plan_routing_packet(repo_root, tracked_packet)
    authority_packet = str(candidate.get("authority_tracked_packet") or "").strip()
    authority_packet = _phase_b_plan_routing_packet(repo_root, authority_packet)
    if not packet or not authority_packet or packet == authority_packet:
        return ""
    normalized_stem = _normalize_phase_a_retry_plan_name(Path(authority_packet).stem)
    if not normalized_stem or Path(packet).stem != normalized_stem:
        return ""
    return authority_packet


def _phase_a_normalized_retry_authority_wave_id(
    repo_root: Path,
    *,
    tracked_packet: str,
    candidate: dict[str, Any],
) -> str:
    authority_packet = _phase_a_normalized_retry_authority_packet(
        repo_root,
        tracked_packet=tracked_packet,
        candidate=candidate,
    )
    if not authority_packet:
        return ""
    authority_wave = read_control_plane_packet_wave_id(repo_root, authority_packet)
    normalized = normalize_wave_id(authority_wave) if authority_wave else ""
    return normalized if normalized != "wave-unknown" else ""


def _routing_candidate_authority_wave_id(
    repo_root: Path,
    record: dict[str, Any],
    candidate: dict[str, Any],
) -> str:
    tracked_packet = str(candidate.get("tracked_packet") or "").strip()
    candidate_wave = _routing_candidate_explicit_wave_id(candidate)
    candidate_label_wave = _routing_candidate_label_wave_id(candidate)
    record_wave = _routing_record_wave_id(record)
    routed_wave = candidate_wave or record_wave or candidate_label_wave
    if tracked_packet:
        authority_wave = _phase_a_normalized_retry_authority_wave_id(
            repo_root,
            tracked_packet=tracked_packet,
            candidate=candidate,
        )
        if authority_wave and (not routed_wave or routed_wave == authority_wave):
            return authority_wave
    if candidate_wave:
        return candidate_wave
    if candidate_label_wave:
        return routed_wave
    if tracked_packet:
        packet_wave = read_control_plane_packet_wave_id(repo_root, tracked_packet)
        if packet_wave:
            return packet_wave
    if routed_wave:
        return routed_wave
    return ""


def _phase_b_routing_record_bound_to_plan_wave(
    repo_root: Path,
    record: dict[str, Any],
    *,
    plan_path: str,
    wave_id: str,
) -> dict[str, Any]:
    """Return a Phase B routing record whose identity follows the locked packet."""
    normalized_wave = normalize_wave_id(str(wave_id or ""))
    if normalized_wave == "wave-unknown":
        return record

    plan_packet = _phase_b_plan_routing_packet(repo_root, plan_path)
    rebound = dict(record)
    rebound["wave_name"] = normalized_wave

    candidates = record.get("next_candidates")
    if not isinstance(candidates, list):
        return rebound

    rebound_candidates: list[Any] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            rebound_candidates.append(candidate)
            continue
        updated = dict(candidate)
        tracked_packet = _phase_b_plan_routing_packet(
            repo_root,
            str(updated.get("tracked_packet") or "").strip(),
        )
        if tracked_packet == plan_packet:
            updated["candidate"] = normalized_wave
            updated["wave_name"] = normalized_wave
        rebound_candidates.append(updated)
    rebound["next_candidates"] = rebound_candidates
    return rebound


def _phase_a_normalized_retry_chain_authority_packet(
    repo_root: Path,
    *,
    plan_path: str,
    record: dict[str, Any],
    plan_wave_id: str,
) -> str:
    """Return the source packet that must govern Phase B for a normalized retry."""
    plan_packet = _phase_b_plan_routing_packet(repo_root, plan_path)
    if not plan_packet:
        return ""
    for candidate in _selected_routing_candidate_dicts(record):
        tracked_packet = _phase_b_plan_routing_packet(
            repo_root,
            str(candidate.get("tracked_packet") or "").strip(),
        )
        if tracked_packet != plan_packet:
            continue
        authority_packet = _phase_a_normalized_retry_authority_packet(
            repo_root,
            tracked_packet=tracked_packet,
            candidate=candidate,
        )
        if not authority_packet:
            continue
        authority_wave = read_control_plane_packet_wave_id(repo_root, authority_packet)
        normalized_authority_wave = (
            normalize_wave_id(authority_wave) if authority_wave else ""
        )
        if normalized_authority_wave == "wave-unknown":
            normalized_authority_wave = ""
        routed_wave = _routing_candidate_wave_id(record, candidate)
        if (
            routed_wave
            and normalized_authority_wave
            and routed_wave != normalized_authority_wave
        ):
            continue
        if (
            plan_wave_id
            and normalized_authority_wave
            and plan_wave_id != normalized_authority_wave
        ):
            continue
        return authority_packet
    return ""


def _phase_a_normalized_retry_phase_b_candidates(
    repo_root: Path,
    record: dict[str, Any],
    *,
    plan_path: str,
    authority_packet: str,
    authority_wave_id: str,
) -> list[Any]:
    """Rewrite normalized retry candidates back to their source packet for Phase B."""
    plan_packet = _phase_b_plan_routing_packet(repo_root, plan_path)
    if not plan_packet or not authority_packet:
        return list((record or {}).get("next_candidates", []))
    rewritten_candidates: list[Any] = []
    rewrote = False
    for candidate in list((record or {}).get("next_candidates", [])):
        if not isinstance(candidate, dict):
            rewritten_candidates.append(candidate)
            continue
        rewritten = dict(candidate)
        tracked_packet = _phase_b_plan_routing_packet(
            repo_root,
            str(rewritten.get("tracked_packet") or "").strip(),
        )
        if tracked_packet == plan_packet:
            if authority_wave_id:
                rewritten["candidate"] = authority_wave_id
                rewritten["wave_name"] = authority_wave_id
            rewritten["tracked_packet"] = authority_packet
            rewritten.pop("recovery_authority", None)
            rewritten.pop("authority_tracked_packet", None)
            rewrote = True
        rewritten_candidates.append(rewritten)
    if not rewrote:
        candidate_wave = authority_wave_id or normalize_wave_id(Path(authority_packet).stem)
        return [
            {
                "candidate": candidate_wave,
                "bounded": True,
                "tracked_packet": authority_packet,
            }
        ]
    return rewritten_candidates


def _missing_next_codex_tracker_authority_result(
    repo_root: Path,
    record: dict[str, Any],
    *,
    decision: str,
    executor_name: str,
) -> dict[str, Any] | None:
    task_id = _canonicalize_surface_task_id(str(record.get("task_id") or ""))
    if task_id != "[NEXT-CODEX-POST-REDTEAM]":
        return None
    missing: list[str] = []
    for candidate in _selected_routing_candidate_dicts(record):
        tracked_packet = str(candidate.get("tracked_packet") or "").strip()
        if not tracked_packet:
            continue
        routed_wave = _routing_candidate_authority_wave_id(
            repo_root,
            record,
            candidate,
        )
        if not routed_wave:
            continue
        if _same_wave_tasks_authority_exists(
            repo_root,
            wave_id=routed_wave,
            tracked_packet=tracked_packet,
        ):
            continue
        if _phase_a_normalized_retry_has_source_authority(
            repo_root,
            wave_id=routed_wave,
            tracked_packet=tracked_packet,
            candidate=candidate,
        ):
            continue
        missing.append(f"{routed_wave} -> {tracked_packet}")
    if not missing:
        return None
    return {
        "status": "held",
        "decision": decision,
        "executor": executor_name,
        "summary": (
            "Routing held because NEXT-CODEX-POST-REDTEAM packet authority is "
            "missing from TASKS.md."
        ),
        "message": (
            "Refusing to dispatch a bounded NEXT-CODEX-POST-REDTEAM candidate "
            "without a same-wave TASKS.md queue entry or tracker note for the "
            "exact wave/packet pair: " + "; ".join(missing)
        ),
        "request_for_agent": (
            "Create or repair the same-wave TASKS.md authority for the packet, "
            "or regenerate routing to a packet that already has same-wave "
            "TASKS.md authority; do not run Phase A from an orphan packet path."
        ),
        "request_for_claude": (
            "Create or repair the same-wave TASKS.md authority for the packet, "
            "or regenerate routing to a packet that already has same-wave "
            "TASKS.md authority; do not run Phase A from an orphan packet path."
        ),
    }


def _candidate_has_tracker_update_scope(candidate: dict[str, Any]) -> bool:
    if str(candidate.get("tracked_packet") or "").strip():
        return True
    files = candidate.get("files")
    return isinstance(files, list) and any(str(item).strip() for item in files)


def _tracker_update_has_actionable_scope(record: dict[str, Any]) -> bool:
    tracker_note = record.get("tracker_note_text")
    if isinstance(tracker_note, str) and tracker_note.strip():
        return True
    for field in ("files_to_stage", "force_add_files"):
        files = record.get(field)
        if isinstance(files, list) and any(str(item).strip() for item in files):
            return True
    return any(
        _candidate_has_tracker_update_scope(candidate)
        for candidate in _selected_routing_candidate_dicts(record)
    )


def _empty_tracker_update_hold_result(
    record: dict[str, Any],
    *,
    decision: str,
    executor_name: str,
) -> dict[str, Any] | None:
    if decision != "UPDATE_TRACKER_ONLY":
        return None
    if _tracker_update_has_actionable_scope(record):
        return None
    return {
        "status": "held",
        "decision": decision,
        "executor": executor_name,
        "summary": "No actionable tracker update scope is present.",
        "message": (
            "UPDATE_TRACKER_ONLY was held because the routing record has no "
            "tracker_note_text, files_to_stage, force_add_files, tracked_packet, "
            "or candidate files. Refusing to synthesize a TASKS.md-only handoff."
        ),
        "request_for_agent": (
            "Refresh post-merge routing to an open packet or provide explicit "
            "tracker update scope before dispatching UPDATE_TRACKER_ONLY."
        ),
        "request_for_claude": (
            "Refresh post-merge routing to an open packet or provide explicit "
            "tracker update scope before dispatching UPDATE_TRACKER_ONLY."
        ),
    }


def _phase_b_plan_declared_wave_id(repo_root: Path, plan_path: str) -> str:
    """Read an explicit Wave ID from a Phase B plan, without stem fallback."""
    clean_path = str(plan_path or "").strip()
    if not clean_path:
        return ""
    candidate = Path(clean_path)
    try:
        if candidate.is_absolute():
            full_path = candidate.resolve()
        else:
            if ".." in candidate.parts:
                return ""
            full_path = (repo_root / clean_path).resolve()
        if not full_path.is_relative_to(repo_root.resolve()):
            return ""
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for raw_line in content.splitlines():
        clean = raw_line.strip()
        lower = clean.lower()
        if lower.startswith("wave id:") or lower.startswith("wave_id:"):
            value = clean.split(":", 1)[1].strip()
            if value:
                return normalize_wave_id(value)
    return ""


def _phase_b_plan_wave_id(repo_root: Path, plan_path: str) -> str:
    """Resolve the wave id Phase B will use for an explicit plan path."""
    clean_path = str(plan_path or "").strip()
    if not clean_path:
        return ""
    declared = _phase_b_plan_declared_wave_id(repo_root, clean_path)
    if declared:
        return declared
    fallback = normalize_wave_id(Path(clean_path).stem)
    return fallback


def _phase_b_plan_routing_packet(repo_root: Path, plan_path: str) -> str:
    """Return the repo-relative tracked packet path for chained routing."""
    clean_path = str(plan_path or "").strip()
    if not clean_path:
        return ""
    candidate = Path(clean_path)
    try:
        if candidate.is_absolute():
            full_path = candidate.resolve()
        else:
            if ".." in candidate.parts:
                return clean_path
            full_path = (repo_root / clean_path).resolve()
        repo_resolved = repo_root.resolve()
        if full_path.is_relative_to(repo_resolved):
            return full_path.relative_to(repo_resolved).as_posix()
    except OSError:
        return clean_path
    return clean_path


def _plan_requires_pre_phase_b_tracker_entry(repo_root: Path, plan_path: str) -> bool:
    """Return true when a locked packet explicitly gates Phase B on TASKS sync."""
    clean_path = str(plan_path or "").strip()
    if not clean_path:
        return False
    candidate = Path(clean_path)
    try:
        if candidate.is_absolute():
            full_path = candidate.resolve()
        else:
            if ".." in candidate.parts:
                return False
            full_path = (repo_root / clean_path).resolve()
        if not full_path.is_relative_to(repo_root.resolve()):
            return False
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    lowered = content.lower()
    tracker_precondition = "tasks.md" in lowered and "tracker entr" in lowered
    prerequisite_stop = (
        "no-go prerequisite stop" in lowered
        or "no-go for implementation" in lowered
        or "cannot authorize implementation" in lowered
        or "no implementation, commit automation, or count-reduction claim is authorized" in lowered
    )
    return (
        tracker_precondition
        and (
            "before phase b dispatch" in lowered
            or prerequisite_stop
        )
    )


def _tasks_tracker_entry_exists(
    repo_root: Path,
    *,
    wave_id: str,
    tracked_packet: str,
) -> bool:
    """Check TASKS.md for a canonical same-wave tracker note for a packet."""
    normalized_wave = normalize_wave_id(wave_id)
    packet = _phase_b_plan_routing_packet(repo_root, tracked_packet)
    if not normalized_wave or not packet:
        return False
    note_header = re.compile(
        r"^- Tracker sync note \([^,]+,\s*([^)]+)\):\s*\*\*[^*]+\*\*"
    )
    packet_field = re.compile(
        r"\bPacket:\s*`?" + re.escape(packet) + r"`?(?=\.|\s|$)"
    )
    try:
        lines = (repo_root / "TASKS.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        match = note_header.match(line)
        if not match:
            continue
        if normalize_wave_id(match.group(1)) != normalized_wave:
            continue
        if packet_field.search(line):
            return True
    return False


def _phase_b_tracker_gate_result(
    repo_root: Path,
    *,
    plan_path: str,
    wave_id: str,
    tracked_packet: str,
) -> dict[str, Any] | None:
    """Hold Phase B when the packet's own tracker precondition is unmet."""
    if not _plan_requires_pre_phase_b_tracker_entry(repo_root, plan_path):
        return None
    normalized_wave = normalize_wave_id(wave_id)
    packet = str(tracked_packet or "").strip()
    if _tasks_tracker_entry_exists(
        repo_root,
        wave_id=normalized_wave,
        tracked_packet=packet,
    ):
        return None
    return {
        "status": "held",
        "decision": "ROUTE_PHASE_B",
        "executor": "phase_b_executor",
        "summary": "Phase B held until same-wave TASKS tracker entry exists.",
        "message": (
            "Refusing to dispatch Phase B because the locked packet requires a "
            "TASKS.md tracker entry before Phase B dispatch, but TASKS.md does "
            f"not contain the exact wave/packet pair: wave_id={normalized_wave!r}, "
            f"packet={packet!r}."
        ),
        "request_for_agent": (
            "Add or repair the same-wave TASKS.md tracker entry for the locked "
            "packet, then resume Phase B from that packet. Do not bypass the "
            "packet's tracker precondition."
        ),
        "request_for_claude": (
            "Add or repair the same-wave TASKS.md tracker entry for the locked "
            "packet, then resume Phase B from that packet. Do not bypass the "
            "packet's tracker precondition."
        ),
    }


def _surface_record_for_chain(
    args: argparse.Namespace,
    repo_root: Path,
) -> dict[str, Any]:
    """Build the identity record used for surface retry handoff validation."""
    decision = _surface_decision(args)
    canonical_task_id = _canonicalize_surface_task_id(getattr(args, "task_id", ""))
    record: dict[str, Any] = {
        "decision": decision,
        "wave_name": _surface_wave_id(args, repo_root),
        "task_id": canonical_task_id,
    }
    if args.surface == "phase-a":
        summary = str(getattr(args, "summary", "") or "").strip()
        request = str(
            getattr(args, "request_for_agent", "")
            or getattr(args, "request_for_claude", "")
            or ""
        ).strip()
        if summary:
            record["summary"] = summary
        if request:
            record["request_for_agent"] = request
            record["request_for_claude"] = request
        record["next_candidates"] = [
            {
                "candidate": record["wave_name"],
                "bounded": True,
            }
        ]
        teammate_identity = getattr(args, "_teammate_identity", None)
        if isinstance(teammate_identity, dict):
            record["teammate_lane"] = teammate_identity.get("lane", "")
            record["bus_dir"] = teammate_identity.get("bus_dir", "")
            record["dashboard_port"] = teammate_identity.get("dashboard_port")
            record["tmux_session"] = teammate_identity.get("tmux_session", "")
            record["teammate_worktree"] = str(getattr(args, "_teammate_worktree", ""))
    if args.surface == "commit" and getattr(args, "handoff", None):
        try:
            handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            handoff = None
        if isinstance(handoff, dict):
            wave_id = handoff.get("wave_id")
            if isinstance(wave_id, str) and wave_id.strip():
                record["wave_name"] = normalize_wave_id(wave_id)
            task_id = handoff.get("task_id")
            if isinstance(task_id, str) and task_id.strip():
                record["task_id"] = task_id
            tracked_packet = handoff.get("tracked_packet")
            if isinstance(tracked_packet, str) and tracked_packet.strip():
                record["next_candidates"] = [
                    {
                        "candidate": str(record.get("wave_name") or ""),
                        "bounded": True,
                        "tracked_packet": tracked_packet.strip(),
                    }
                ]
        return record
    if args.surface in {"phase-b", "commit"}:
        routing_payload = _load_routing_record_payload(
            path_value=getattr(args, "routing_record_path", None),
            json_value=getattr(args, "routing_record_json", None),
        )
        if routing_payload:
            try:
                parsed = json.loads(routing_payload)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed = None
            if isinstance(parsed, dict):
                record.update(parsed)
                parsed_decision = str(parsed.get("decision") or "").strip()
                if args.surface == "phase-b":
                    if parsed_decision and parsed_decision != decision:
                        record["source_routing_decision"] = parsed_decision
                    record["decision"] = decision
                else:
                    record["decision"] = str(record.get("decision") or decision)
                if canonical_task_id:
                    record["task_id"] = canonical_task_id
        if args.surface == "commit":
            return record
    if args.surface == "phase-a":
        record = _enrich_founder_ordered_tracked_packets(repo_root, record)
    if args.surface != "phase-b":
        return record

    _bind_phase_b_recovery_plan_wave(record, repo_root)
    plan_path = (
        getattr(args, "plan", None)
        or _surface_phase_b_plan_from_routing_payload(routing_payload)
        or _phase_b_recovery_plan_from_env(record)
    )
    if plan_path:
        if not _routing_record_tracked_packet(record):
            record["next_candidates"] = [{"tracked_packet": plan_path}]
        wave_name = str(record.get("wave_name") or record.get("wave_id") or "").strip()
        if not wave_name or normalize_wave_id(wave_name) == "wave-unknown":
            plan_wave_id = _phase_b_plan_wave_id(repo_root, plan_path)
            if plan_wave_id:
                record["wave_name"] = plan_wave_id
    return record


def _phase_a_surface_record_for_persistence(
    repo_root: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    persisted = dict(record)
    persisted["decision"] = str(persisted.get("decision") or "ROUTE_PHASE_A")
    persisted["summary"] = str(persisted.get("summary") or "")
    request_text = str(
        persisted.get("request_for_agent") or persisted.get("request_for_claude") or ""
    )
    persisted["request_for_agent"] = request_text
    persisted["request_for_claude"] = request_text
    wave_name = str(persisted.get("wave_name") or persisted.get("wave_id") or "").strip()
    if wave_name and not isinstance(persisted.get("next_candidates"), list):
        persisted["next_candidates"] = [{"candidate": wave_name, "bounded": True}]

    try:
        repo_state = _compute_repo_state(repo_root)
    except Exception:
        return persisted
    persisted.setdefault("head_sha", repo_state.head_sha)
    persisted["state_sha"] = repo_state.state_sha
    return persisted


def _persist_phase_a_surface_routing_record(
    repo_root: Path,
    record: dict[str, Any],
    *,
    bus_dir: str | Path | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    persisted = _phase_a_surface_record_for_persistence(repo_root, record)
    target_path = _canonical_routing_record_path(repo_root, bus_dir)
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ControlSurfaceError(
            f"Cannot persist Phase A routing context to {target_path}: {exc}"
        ) from exc
    if verbose:
        print(f"[dispatch] Persisted Phase A routing context: {target_path}")
    return persisted


def build_surface_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Modular control-plane entrypoint for executors and supervisors",
    )
    sub = parser.add_subparsers(dest="surface", required=True)

    phase_a = sub.add_parser("phase-a", help="Run Phase A executor")
    phase_a.add_argument("--plan-name", required=True, help="Plan packet slug")
    phase_a.add_argument(
        "--task-id",
        default="",
        help="TASKS.md task ID (e.g. [PIPELINE-RECOVERY] or PIPELINE-RECOVERY). Propagated to Phase B and commit handoff.",
    )
    phase_a.add_argument(
        "--summary",
        default="",
        help="Short Phase A scope summary. Used to seed the routing context passed to phase_a_executor.",
    )
    phase_a.add_argument(
        "--request-for-agent",
        dest="request_for_agent",
        default="",
        help="Detailed Phase A request. Used to seed the routing context passed to phase_a_executor.",
    )
    # Deprecated compatibility input: parse old scripts without advertising a
    # Claude-named operator surface.
    phase_a.add_argument(
        "--request-for-claude",
        dest="request_for_agent",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    phase_a.add_argument("--max-rounds", type=int, default=15)
    phase_a.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    phase_a.add_argument(
        "--teammate-lane",
        default=None,
        help=(
            "Configured teammate lane to run from a dedicated git worktree with "
            "that lane's namespaced agent bus"
        ),
    )
    phase_a.add_argument("-v", "--verbose", action="store_true")
    phase_a.add_argument("--json", action="store_true")

    phase_b = sub.add_parser("phase-b", help="Run Phase B executor")
    phase_b.add_argument("--plan", default=None, help="Locked plan packet path")
    phase_b.add_argument(
        "--task-id",
        default="",
        help="TASKS.md task ID (e.g. [PIPELINE-RECOVERY] or PIPELINE-RECOVERY). Used in commit handoff.",
    )
    phase_b.add_argument("--routing-record-path", type=Path, help="Path to routing record JSON")
    phase_b.add_argument("--routing-record-json", help="Routing record JSON string")
    phase_b.add_argument("--max-rounds", type=int, default=10)
    phase_b.add_argument("--bootstrap-exception", action="store_true")
    phase_b.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    phase_b.add_argument("-v", "--verbose", action="store_true")
    phase_b.add_argument("--json", action="store_true")

    pre_commit = sub.add_parser("pre-commit-supervisor", help="Run pre-commit supervisor")
    pre_commit.add_argument("--package", type=Path, required=True)
    pre_commit.add_argument("--dry-run", action="store_true")
    pre_commit.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    pre_commit.add_argument("-v", "--verbose", action="store_true")
    pre_commit.add_argument("--json", action="store_true")

    commit = sub.add_parser("commit", help="Run commit executor")
    commit.add_argument("--handoff", type=Path, help="Path to handoff JSON")
    commit.add_argument("--routing-record-path", type=Path, help="Path to routing record JSON")
    commit.add_argument("--routing-record-json", help="Routing record JSON string")
    commit.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    commit.add_argument("-v", "--verbose", action="store_true")
    commit.add_argument("--json", action="store_true")

    post_merge = sub.add_parser("post-merge-supervisor", help="Run post-merge supervisor")
    post_merge.add_argument("--package", type=Path, required=True)
    post_merge.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    post_merge.add_argument("-v", "--verbose", action="store_true")
    post_merge.add_argument("--json", action="store_true")

    return parser


def build_surface_command(
    args: argparse.Namespace,
    *,
    routing_record: dict[str, Any] | None = None,
    script_repo_root: Path | None = None,
) -> list[str]:
    canonical_task_id = _canonicalize_surface_task_id(getattr(args, "task_id", ""))
    executor_script_dir = _script_dir_for_repo(script_repo_root)
    agents_dir = _agents_dir_for_repo(script_repo_root)
    if args.surface == "phase-a":
        cmd = [
            sys.executable,
            str(executor_script_dir / "phase_a_executor.py"),
            "--plan-name",
            args.plan_name,
            "--max-rounds",
            str(args.max_rounds),
        ]
        if routing_record is not None:
            cmd.extend(["--routing-record", json.dumps(routing_record)])
    elif args.surface == "phase-b":
        cmd = [
            sys.executable,
            str(executor_script_dir / "phase_b_executor.py"),
            "--max-rounds",
            str(args.max_rounds),
            "--dispatcher-owned-recovery",
        ]
        routing_payload = (
            json.dumps(routing_record)
            if routing_record is not None
            else _load_routing_record_payload(
                path_value=args.routing_record_path,
                json_value=args.routing_record_json,
            )
        )
        recovery_record: dict[str, Any] = routing_record or {}
        if not recovery_record and routing_payload:
            try:
                parsed_record = json.loads(routing_payload)
            except (json.JSONDecodeError, TypeError, ValueError):
                parsed_record = None
            if isinstance(parsed_record, dict):
                recovery_record = parsed_record
        recovery_plan_path = _phase_b_recovery_plan_from_env(recovery_record)
        plan_path = (
            args.plan
            or _surface_phase_b_plan_from_routing_payload(routing_payload)
            or recovery_plan_path
        )
        if plan_path:
            cmd.extend(["--plan", plan_path])
        if routing_payload:
            cmd.extend(["--routing-record", routing_payload])
        if args.bootstrap_exception:
            cmd.append("--bootstrap-exception")
        if canonical_task_id:
            cmd.extend(["--task-id", canonical_task_id])
    elif args.surface == "pre-commit-supervisor":
        cmd = [
            sys.executable,
            str(agents_dir / "meta_bridge_supervisor.py"),
            "--package",
            str(args.package),
        ]
        if args.dry_run:
            cmd.append("--dry-run")
    elif args.surface == "commit":
        cmd = [
            sys.executable,
            str(executor_script_dir / "commit_executor.py"),
        ]
        routing_payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if args.handoff:
            if routing_payload:
                raise ControlSurfaceError("Provide either --handoff or a routing record, not both")
            cmd.extend(["--handoff", str(args.handoff)])
        elif routing_payload:
            cmd.extend(["--routing-record", routing_payload])
        else:
            raise ControlSurfaceError("commit requires --handoff or a routing record")
    elif args.surface == "post-merge-supervisor":
        cmd = [
            sys.executable,
            str(agents_dir / "meta_bridge_supervisor.py"),
            "--mode",
            "post-merge",
            "--package",
            str(args.package),
        ]
    else:
        raise ControlSurfaceError(f"Unsupported surface: {args.surface}")

    if getattr(args, "bus_dir", None):
        cmd.extend(["--bus-dir", str(args.bus_dir)])
    if getattr(args, "verbose", False):
        cmd.append("--verbose")
    if getattr(args, "json", False):
        cmd.append("--json")
    return cmd


def _surface_forward_timeout(args: argparse.Namespace, config: dict[str, Any]) -> int | float:
    key = str(args.surface).replace("-", "_")
    fallback = DEFAULT_EXECUTOR_CONFIG["timeouts"].get(key, 900)
    value = config.get("timeouts", {}).get(key, fallback)
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    if parsed <= 0:
        return fallback
    return int(parsed) if parsed.is_integer() else parsed


def run_surface_command(
    cmd: list[str],
    *,
    repo_root: Path,
    timeout: int | float | None = None,
) -> int:
    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        if exc.stdout:
            sys.stdout.write(exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode(errors="replace"))
        if exc.stderr:
            sys.stderr.write(exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(errors="replace"))
        print(
            f"[executor-dispatch] Surface command timed out after {timeout}s: {cmd[0]}",
            file=sys.stderr,
        )
        return 124
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def _surface_wave_id(args: argparse.Namespace, repo_root: Path) -> str:
    """Derive a stable wave_id for recoverable surface invocations."""
    if args.surface == "phase-a":
        return normalize_wave_id(args.plan_name)
    if args.surface == "phase-b":
        payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if payload:
            try:
                record = json.loads(payload)
                wave_name = record.get("wave_name") or record.get("wave_id", "")
                if isinstance(wave_name, str) and wave_name.strip():
                    return normalize_wave_id(wave_name)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        if args.plan:
            return _phase_b_plan_wave_id(repo_root, args.plan)
    if args.surface == "commit":
        if args.handoff:
            try:
                handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
                wave_id = handoff.get("wave_id")
                if isinstance(wave_id, str) and wave_id.strip():
                    return normalize_wave_id(wave_id)
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
            return normalize_wave_id(args.handoff.stem)
        payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if payload:
            try:
                record = json.loads(payload)
                wave_name = record.get("wave_name") or record.get("wave_id", "")
                if isinstance(wave_name, str) and wave_name.strip():
                    return normalize_wave_id(wave_name)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return "wave-unknown"


def _surface_decision(args: argparse.Namespace) -> str:
    """Derive the logical dispatcher decision for a modular surface invocation."""
    if args.surface == "phase-a":
        return "ROUTE_PHASE_A"
    if args.surface == "phase-b":
        return "ROUTE_PHASE_B"
    if args.surface == "commit":
        payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if payload:
            try:
                record = json.loads(payload)
                decision = record.get("decision")
                if isinstance(decision, str) and decision.strip():
                    return decision
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return "COMMIT_GO"
    raise ControlSurfaceError(f"Unsupported recoverable surface: {args.surface}")


def _reload_explicit_routing_record(
    path: Path | None,
    *,
    verbose: bool = False,
) -> dict[str, Any] | None:
    """Best-effort reload for caller-owned routing files between retries."""
    if path is None:
        return None
    record = _load_routing_record_json(path)
    if record is None and verbose:
        print(f"[dispatch] Explicit routing reload skipped: could not parse {path}")
    return record


def _emit_surface_stop_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, indent=2))
        return
    print(f"[dispatch] Status: {result.get('status', 'stopped')}")
    print(f"[dispatch] Decision: {result.get('decision', 'unknown')}")
    executor = result.get("executor")
    if executor:
        print(f"[dispatch] Executor: {executor}")
    message = result.get("message") or result.get("summary")
    if message:
        print(f"[dispatch] {message}")


def run_recoverable_surface_command(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    config: dict[str, Any],
) -> int:
    """Run recoverable control surfaces through the dispatcher recovery gate."""
    bus_dir = getattr(args, "bus_dir", None)
    if bus_dir is not None:
        resolve_agent_bus_dir(repo_root, bus_dir)
    script_repo_root = getattr(args, "_teammate_script_repo_root", None)
    executor_name = {
        "phase-a": "phase_a_executor",
        "phase-b": "phase_b_executor",
        "commit": "commit_executor",
    }[args.surface]
    decision = _surface_decision(args)
    surface_record = _surface_record_for_chain(args, repo_root)
    explicit_commit_handoff = args.surface == "commit" and getattr(args, "handoff", None)
    if not explicit_commit_handoff:
        completed_stop = _completed_candidate_stop_result(
            repo_root,
            surface_record,
            decision=decision,
            executor_name=executor_name,
        )
        if completed_stop is not None:
            _emit_surface_stop_result(
                completed_stop,
                json_output=bool(getattr(args, "json", False)),
            )
            return 0
    wave_id = normalize_wave_id(
        str(surface_record.get("wave_name") or surface_record.get("wave_id") or "")
    )
    if not wave_id:
        wave_id = _surface_wave_id(args, repo_root)
    original_timeouts = None
    result: dict[str, Any] | None = None
    surface_retry_record: dict[str, Any] | None = None

    # Auto-spawn the per-lane tmux monitor for a lane bus launch (no-op for the
    # MAIN/default bus).  The wave-end cleanup runs in the finally below so it
    # fires on normal completion, recovery breaks, and the signal/exception
    # paths alike.
    monitor = _LaneMonitor(repo_root, bus_dir, verbose=getattr(args, "verbose", False))
    monitor.spawn()
    # Arm a process-level signal handler so a SIGTERM landing outside an executor
    # subprocess window still runs the wave-end cleanup (see main()).
    _signal_cleanup_token = _install_wave_end_signal_cleanup(monitor)

    try:
        while True:
            if result is not None and _is_chained_commit_failure(result):
                retried = _retry_commit_only(
                    repo_root,
                    config,
                    verbose=getattr(args, "verbose", False),
                    bus_dir=bus_dir,
                    script_repo_root=script_repo_root,
                )
                if retried.get("stdout"):
                    sys.stdout.write(retried["stdout"])
                if retried.get("stderr"):
                    sys.stderr.write(retried["stderr"])
                if retried.get("status") in {"success", "held"}:
                    return 0
                result = retried
            else:
                if surface_retry_record is not None:
                    surface_record = surface_retry_record
                    surface_retry_record = None
                else:
                    surface_record = _surface_record_for_chain(args, repo_root)
                decision = str(surface_record.get("decision") or decision)
                wave_id = normalize_wave_id(
                    str(surface_record.get("wave_name") or surface_record.get("wave_id") or wave_id)
                )
                if args.surface == "phase-a":
                    surface_record = _persist_phase_a_surface_routing_record(
                        repo_root,
                        surface_record,
                        bus_dir=bus_dir,
                        verbose=getattr(args, "verbose", False),
                    )
                cmd = build_surface_command(
                    args,
                    routing_record=surface_record,
                    script_repo_root=script_repo_root,
                )
                _default_timeout = DEFAULT_EXECUTOR_CONFIG["timeouts"].get(executor_name, 600)
                timeout = config.get("timeouts", {}).get(executor_name, _default_timeout)
                try:
                    completed = _run_executor_in_group(cmd, cwd=repo_root, timeout=timeout)
                    _emit_completed_process_output(completed)
                    if executor_name == "commit_executor":
                        if completed.returncode != 0:
                            result = {
                                "status": "failed",
                                "decision": decision,
                                "executor": executor_name,
                                "step": args.surface.replace("-", "_"),
                                "exit_code": completed.returncode,
                                "stdout": completed.stdout,
                                "stderr": completed.stderr,
                            }
                        else:
                            c_status, c_decision = _classify_commit_executor_result(completed)
                            if c_status in {"success", "held"}:
                                return 0
                            result = {
                                "status": c_status,
                                "decision": c_decision,
                                "executor": executor_name,
                                "step": args.surface.replace("-", "_"),
                                "exit_code": completed.returncode,
                                "stdout": completed.stdout,
                                "stderr": completed.stderr,
                            }
                    elif completed.returncode == 0:
                        result = _continue_successful_executor_chain(
                            executor_name,
                            completed,
                            repo_root=repo_root,
                            config=config,
                            record=surface_record,
                            verbose=getattr(args, "verbose", False),
                            emit_output=True,
                            bus_dir=bus_dir,
                            script_repo_root=script_repo_root,
                            max_bridge_rounds=getattr(args, "max_rounds", None),
                        )
                        if result.get("status") in {"success", "held"}:
                            return 0
                    else:
                        result = {
                            "status": "failed",
                            "decision": decision,
                            "executor": executor_name,
                            "step": args.surface.replace("-", "_"),
                            "exit_code": completed.returncode,
                            "stdout": completed.stdout,
                            "stderr": completed.stderr,
                        }
                except subprocess.TimeoutExpired:
                    result = {
                        "status": "timeout",
                        "decision": decision,
                        "executor": executor_name,
                        "step": args.surface.replace("-", "_"),
                        "message": f"Executor {executor_name} timed out after {timeout}s",
                        "stdout": "",
                        "stderr": "",
                    }

            embedded_recovery = result.get("recovery")
            if isinstance(embedded_recovery, dict) and embedded_recovery.get("recovered"):
                if getattr(args, "verbose", False):
                    print(
                        "[dispatch] Surface Phase B recovered in-process — "
                        "retrying before commit chain"
                    )
                _clear_phase_b_state_for_retry(
                    repo_root, result, verbose=getattr(args, "verbose", False), bus_dir=bus_dir
                )
                retry_record = _recovered_retry_record(
                    result,
                    current_record=surface_record,
                    allow_phase_b_to_phase_a=bool(getattr(args, "bootstrap_exception", False)),
                )
                if retry_record is not None:
                    surface_retry_record = retry_record
                continue

            if result.get("status") == "failed" and _is_terminal_executor_outcome(result):
                _emit_executor_hard_fail_event(repo_root, result, wave_id, surface_record, bus_dir=bus_dir)
                break

            recovery = attempt_recovery(repo_root, result, wave_id, bus_dir=bus_dir)
            result["recovery"] = recovery
            if getattr(args, "verbose", False):
                print(
                    f"[dispatch] Surface recovery: class={recovery.get('failure_class')} "
                    f"tier={recovery.get('tier')} recovered={recovery.get('recovered')}"
                )
            if not recovery.get("recovered"):
                _emit_executor_hard_fail_event(repo_root, result, wave_id, surface_record, bus_dir=bus_dir)
                break

            new_orig = _apply_recovery_overrides(
                config, repo_root=repo_root, verbose=getattr(args, "verbose", False))
            original_timeouts = _merge_recovery_original_config(
                original_timeouts,
                new_orig,
            )
            _clear_phase_b_state_for_retry(repo_root, result, verbose=getattr(args, "verbose", False), bus_dir=bus_dir)
            retry_record = _recovered_retry_record(
                result,
                current_record=surface_record,
                allow_phase_b_to_phase_a=bool(getattr(args, "bootstrap_exception", False)),
            )
            if retry_record is not None:
                surface_retry_record = retry_record

        return 1
    finally:
        _remove_wave_end_signal_cleanup(_signal_cleanup_token)
        monitor.cleanup()
        if original_timeouts is not None:
            _restore_config_on_disk(
                repo_root, original_timeouts,
                verbose=getattr(args, "verbose", False),
            )
            config["timeouts"] = _recovery_original_section(original_timeouts, "timeouts")
            config["bridge_turn_timeouts"] = _recovery_original_section(
                original_timeouts, "bridge_turn_timeouts"
            )
        _clear_recovery_override_env()
        for env_key in list(os.environ):
            if env_key.startswith((
                "RCX_RECOVERY_ORIGINAL_TIMEOUT_",
                "RCX_RECOVERY_ORIGINAL_BRIDGE_TURN_TIMEOUT_",
                PHASE_B_RECOVERY_PLAN_ENV,
                PHASE_B_RECOVERY_PLAN_WAVE_ENV,
            )):
                os.environ.pop(env_key, None)


def _validate_phase_b_handoff_identity(handoff_path: Path, record: dict[str, Any]) -> tuple[bool, str]:
    """Fail closed if a stale handoff file does not match the current routing identity."""
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"Phase B handoff is not valid JSON: {exc}"
    if not isinstance(handoff, dict):
        return False, "Phase B handoff must decode to a JSON object"

    wave_name = record.get("wave_name") or record.get("wave_id", "")
    if not isinstance(wave_name, str) or not wave_name.strip():
        return False, "Routing record missing wave_name/wave_id for handoff identity check"
    expected_wave_id = normalize_wave_id(wave_name)
    actual_wave_id = handoff.get("wave_id")
    if actual_wave_id != expected_wave_id:
        return False, (
            f"Phase B handoff wave_id mismatch: expected {expected_wave_id}, got {actual_wave_id}"
        )

    expected_task_id = record.get("task_id")
    actual_task_id = handoff.get("task_id")
    if (expected_task_id or actual_task_id) and actual_task_id != expected_task_id:
        return False, (
            f"Phase B handoff task_id mismatch: expected {expected_task_id}, got {actual_task_id}"
        )

    expected_packet = _routing_record_tracked_packet(record)
    if expected_packet:
        scope_items = handoff.get("scope_items")
        actual_packet = handoff.get("tracked_packet")
        if not actual_packet and isinstance(scope_items, list):
            for item in scope_items:
                if isinstance(item, str) and item.strip() == expected_packet:
                    actual_packet = item.strip()
                    break
        if actual_packet != expected_packet:
            return False, (
                "Phase B handoff tracked_packet mismatch: "
                f"expected {expected_packet}, got {actual_packet}"
            )

    return True, "ok"


def _phase_b_tracked_plan_or_error(
    repo: Path,
    record: dict[str, Any],
    *,
    include_recovery_env: bool = False,
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve a Phase B tracked packet path, optionally from recovery env."""
    for candidate in _selected_routing_candidate_dicts(record):
        tracked_packet = candidate.get("tracked_packet")
        if tracked_packet and isinstance(tracked_packet, str):
            plan_path = tracked_packet
            break
    else:
        plan_path = None

    if not plan_path and include_recovery_env:
        plan_path = _phase_b_recovery_plan_from_env(record) or None
    if not plan_path:
        return None, None

    plan_resolved = (repo / plan_path).resolve()
    if Path(plan_path).is_absolute() or ".." in Path(plan_path).parts:
        return None, {
            "status": "error",
            "decision": record.get("decision", ""),
            "executor": "phase_b_executor",
            "message": f"Path traversal in tracked_packet: {plan_path}",
        }
    if not plan_resolved.is_relative_to(repo.resolve()):
        return None, {
            "status": "error",
            "decision": record.get("decision", ""),
            "executor": "phase_b_executor",
            "message": f"tracked_packet escapes repo root: {plan_path}",
        }
    return plan_path, None


def _is_terminal_executor_outcome(result: dict[str, Any]) -> bool:
    """Check if a failed executor result contains a terminal outcome.

    Terminal outcomes (e.g. bridge NO_GO requiring founder intervention,
    max bridge rounds exhausted) should not be retried — retrying would
    re-invoke the executor with the same inputs and the same result.
    """
    stdout = result.get("stdout", "")
    if not stdout:
        return False
    # Try full JSON parse (executor with --json)
    try:
        data = json.loads(stdout)
        if isinstance(data, dict) and data.get("status") in _TERMINAL_EXECUTOR_STATUSES:
            return True
    except (json.JSONDecodeError, ValueError):
        pass
    # Try line-by-line: Phase B text output is "[phase-b] Status: <status>"
    # and executors may emit per-line JSON objects.
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("[phase-") and "Status:" in stripped:
            status_part = stripped.split("Status:", 1)[1].strip()
            if status_part in _TERMINAL_EXECUTOR_STATUSES:
                return True
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict) and data.get("status") in _TERMINAL_EXECUTOR_STATUSES:
                    return True
            except (json.JSONDecodeError, ValueError):
                pass
    return False


def _is_chained_commit_failure(result: dict[str, Any]) -> bool:
    """Check if a dispatch result is a failed chained commit.

    When Phase A→B→commit or Phase B→commit chains, the commit step may
    fail while earlier phases succeeded.  Retrying should only re-run the
    commit executor, not the full chain.
    """
    if _looks_like_private_attr_test_integrity_failure(result):
        return False
    return (
        result.get("status") == "failed"
        and result.get("executor") == "commit_executor"
        and result.get("chained_from") is not None
    )


def _looks_like_private_attr_test_integrity_failure(result: dict[str, Any]) -> bool:
    """Detect the anti-cheat failure that must return to Phase B/recovery."""
    parts: list[str] = []
    for key in ("stdout", "stderr", "message", "reason", "detail", "step"):
        value = result.get(key)
        if isinstance(value, str):
            parts.append(value)
    errors = result.get("errors")
    if isinstance(errors, list):
        parts.extend(str(item) for item in errors)
    text = "\n".join(parts).lower()
    return (
        "private_attr_gate" in text
        or "private-attr test-integrity gate failed" in text
        or "found private attr access in tests/" in text
    )


def _classify_commit_executor_result(
    commit_result: subprocess.CompletedProcess[str],
) -> tuple[str, str]:
    """Derive (dispatch_status, decision) from a commit executor subprocess result.

    The commit executor exits 0 for both ``success`` and ``held`` (the latter
    when the routing decision was ``COMMIT_GO_HOLD_PUSH``).  Without parsing
    the executor's output, the dispatcher would collapse ``held`` into
    ``success`` and report ``COMMIT_GO`` — making a local-hold stop look like
    a completed wave.

    Returns ``("held", "COMMIT_HELD")`` when the commit was made locally but
    push was intentionally skipped, ``("success", "COMMIT_GO")`` on full
    success, or ``("failed", "COMMIT_GO")`` on non-zero exit.
    """
    if commit_result.returncode != 0:
        return "failed", "COMMIT_GO"
    stdout = commit_result.stdout or ""
    try:
        payload = json.loads(stdout)
        if isinstance(payload, dict):
            status = payload.get("status")
            if status == "held":
                return "held", "COMMIT_HELD"
            if status == "success":
                return "success", "COMMIT_GO"
            if status in {"error", "failed", "timeout"}:
                return "failed", "COMMIT_GO"
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        status = payload.get("status")
        if status == "held":
            return "held", "COMMIT_HELD"
        if status == "success":
            return "success", "COMMIT_GO"
        if status in {"error", "failed", "timeout"}:
            return "failed", "COMMIT_GO"
    if "[commit-executor] Status: held" in stdout:
        return "held", "COMMIT_HELD"
    if "[commit-executor] Status: error" in stdout:
        return "failed", "COMMIT_GO"
    return "success", "COMMIT_GO"


def _extract_structured_stdout_payload(stdout: str) -> dict[str, Any] | None:
    """Best-effort decode of executor stdout JSON."""
    if not stdout:
        return None
    try:
        payload = json.loads(stdout)
        if isinstance(payload, dict):
            return payload
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None

def _parse_worktree_list(output: str) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain` into entry dicts."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                entries.append(current)
                current = {}
            current["worktree"] = value
            continue
        current[key] = value or "true"
    if current:
        entries.append(current)
    return entries


def resolve_repo_root_for_dispatch(*, verbose: bool = False) -> Path:
    """Resolve the active worktree root for dispatcher execution.

    When invoked from the bare/common git dir, fall back to a linked worktree
    for the current branch if and only if exactly one exists.
    """
    try:
        top_level = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
        inside_work_tree = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
        is_bare = subprocess.run(
            ["git", "rev-parse", "--is-bare-repository"],
            capture_output=True, text=True, check=False,
        )
        if (
            inside_work_tree.returncode == 0
            and inside_work_tree.stdout.strip() == "true"
            and not (
                is_bare.returncode == 0
                and is_bare.stdout.strip() == "true"
            )
        ):
            return top_level
    except subprocess.CalledProcessError:
        pass

    branch_proc = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if branch_proc.returncode != 0 or not branch_proc.stdout.strip():
        raise DispatchError(
            "Not in a git worktree, and no current branch is available to resolve a linked worktree"
        )
    branch = branch_proc.stdout.strip()

    worktree_proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=False,
    )
    if worktree_proc.returncode != 0:
        raise DispatchError(
            "Not in a git worktree, and linked worktrees could not be enumerated"
        )

    target_ref = f"refs/heads/{branch}"
    matches = [
        Path(entry["worktree"])
        for entry in _parse_worktree_list(worktree_proc.stdout)
        if entry.get("worktree")
        and entry.get("bare") != "true"
        and entry.get("branch") == target_ref
    ]
    if len(matches) == 1:
        if verbose:
            print(
                f"[dispatch] Resolved linked worktree for branch {branch}: {matches[0]}",
                file=sys.stderr,
            )
        return matches[0]
    if not matches:
        raise DispatchError(
            "Current repository is a bare/common git dir. Run from a linked worktree "
            f"or create one for {branch!r} with `git worktree add <path> {branch}`."
        )
    match_list = ", ".join(str(path) for path in matches)
    raise DispatchError(
        f"Multiple linked worktrees found for branch {branch!r}: {match_list}. "
        "Run the dispatcher from the intended linked worktree."
    )


def _script_dir_for_repo(script_repo_root: Path | None) -> Path:
    if script_repo_root is None:
        return SCRIPT_DIR
    return Path(script_repo_root) / "mu" / "tools" / "executors"


def _agents_dir_for_repo(script_repo_root: Path | None) -> Path:
    if script_repo_root is None:
        return AGENTS_DIR
    return Path(script_repo_root) / "mu" / "tools" / "agents"


def _worktree_entries(repo_root: Path) -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DispatchError(f"Cannot enumerate git worktrees for teammate lane: {exc}") from exc
    return _parse_worktree_list(result.stdout)


def _primary_worktree_root(repo_root: Path, entries: list[dict[str, str]]) -> Path:
    for entry in entries:
        raw_path = entry.get("worktree", "").strip()
        if raw_path and entry.get("bare") != "true":
            return Path(raw_path)
    return Path(repo_root)


def _teammate_worktree_path(repo_root: Path, lane: str, entries: list[dict[str, str]]) -> Path:
    anchor = _primary_worktree_root(repo_root, entries)
    return anchor.parent / f"{anchor.name}-{lane}"


def _matching_worktree_entry(
    entries: list[dict[str, str]],
    target_path: Path,
) -> dict[str, str] | None:
    target_key = target_path.resolve(strict=False)
    for entry in entries:
        raw_path = entry.get("worktree", "").strip()
        if not raw_path or entry.get("bare") == "true":
            continue
        if Path(raw_path).resolve(strict=False) == target_key:
            return entry
    return None


def _git_head_sha(root: Path, *, context: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DispatchError(
            f"stale bridge retries after state changes: cannot determine {context} HEAD: {exc}"
        ) from exc
    return result.stdout.strip()


def _ensure_teammate_worktree_head_matches_caller(
    *,
    caller_root: Path,
    target_root: Path,
    lane: str,
) -> None:
    caller_head = _git_head_sha(caller_root, context="caller worktree")
    target_head = _git_head_sha(target_root, context=f"teammate lane {lane!r}")
    if target_head != caller_head:
        raise DispatchError(
            f"stale bridge retries after state changes: teammate lane {lane!r} "
            f"worktree HEAD {target_head[:12]} does not match caller HEAD "
            f"{caller_head[:12]}; remove or rebind {target_root} before dispatch"
        )


def _is_default_agent_bus_dir(bus_dir: str | Path) -> bool:
    return str(bus_dir).strip().rstrip("/") == ".agent_bus"


def _reject_shared_teammate_bus(
    *,
    caller_root: Path,
    target_root: Path,
    bus_dir: str,
    lane: str,
) -> None:
    if _is_default_agent_bus_dir(bus_dir):
        raise DispatchError(
            f"stale bridge retries from shared state: teammate lane {lane!r} "
            "must use a namespaced bus, not the default .agent_bus"
        )
    target_bus = resolve_agent_bus_dir(target_root, bus_dir)
    caller_default = (Path(caller_root) / ".agent_bus").resolve(strict=False)
    target_resolved = target_bus.resolve(strict=False)
    if target_resolved == caller_default:
        raise DispatchError(
            f"shared lock contention: teammate lane {lane!r} would share agent bus "
            f"root {target_bus} with the caller worktree"
        )
    for rel_lock in ("meta/meta_bridge.lock", "bridge.lock"):
        lock_path = target_bus / rel_lock
        try:
            if lock_path.exists() and lock_path.stat().st_size > 0:
                raise DispatchError(
                    f"shared lock contention: teammate lane {lane!r} has an "
                    f"active bridge lock at {lock_path}"
                )
        except OSError as exc:
            raise DispatchError(
                f"shared lock contention: cannot inspect teammate bridge lock "
                f"{lock_path}: {exc}"
            ) from exc


def _create_or_select_teammate_worktree(
    repo_root: Path,
    *,
    lane: str,
    bus_dir: str,
    verbose: bool = False,
) -> Path:
    if _is_default_agent_bus_dir(bus_dir):
        raise DispatchError(
            f"stale bridge retries from shared state: teammate lane {lane!r} "
            "must use a namespaced bus, not the default .agent_bus"
        )

    entries = _worktree_entries(repo_root)
    target_path = _teammate_worktree_path(repo_root, lane, entries)
    current_root = Path(repo_root).resolve(strict=False)
    target_key = target_path.resolve(strict=False)
    matching = _matching_worktree_entry(entries, target_path)

    if current_root == target_key:
        try:
            ensure_git_worktree_clean(repo_root, context=f"teammate lane {lane!r}")
        except ExecutorCommonError as exc:
            raise DispatchError(str(exc)) from exc
        _reject_shared_teammate_bus(
            caller_root=repo_root,
            target_root=repo_root,
            bus_dir=bus_dir,
            lane=lane,
        )
        return Path(repo_root)

    try:
        ensure_git_worktree_clean(repo_root, context="caller worktree")
    except ExecutorCommonError as exc:
        raise DispatchError(str(exc)) from exc

    if matching is not None:
        target_root = Path(matching["worktree"])
        try:
            ensure_git_worktree_clean(target_root, context=f"teammate lane {lane!r}")
        except ExecutorCommonError as exc:
            raise DispatchError(str(exc)) from exc
        _reject_shared_teammate_bus(
            caller_root=repo_root,
            target_root=target_root,
            bus_dir=bus_dir,
            lane=lane,
        )
        _ensure_teammate_worktree_head_matches_caller(
            caller_root=repo_root,
            target_root=target_root,
            lane=lane,
        )
        if verbose:
            print(f"[dispatch] Selected teammate lane {lane}: {target_root}", file=sys.stderr)
        return target_root

    if target_path.exists():
        raise DispatchError(
            f"shared lock contention: teammate lane {lane!r} target {target_path} "
            "exists but is not a registered git worktree"
        )

    try:
        result = subprocess.run(
            ["git", "worktree", "add", "--detach", str(target_path), "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DispatchError(f"Cannot create teammate worktree {target_path}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise DispatchError(
            f"Cannot create teammate worktree {target_path}: {detail or result.returncode}"
        )

    _reject_shared_teammate_bus(
        caller_root=repo_root,
        target_root=target_path,
        bus_dir=bus_dir,
        lane=lane,
    )
    resolve_agent_bus_dir(target_path, bus_dir).mkdir(parents=True, exist_ok=True)
    if verbose:
        print(f"[dispatch] Created teammate lane {lane}: {target_path}", file=sys.stderr)
    return target_path


def prepare_phase_a_teammate_lane(
    args: argparse.Namespace,
    repo_root: Path,
) -> Path:
    """Bind a phase-a teammate lane to a deterministic worktree and bus."""
    raw_lane = str(getattr(args, "teammate_lane", "") or "").strip()
    if not raw_lane:
        return repo_root
    if _is_default_agent_bus_dir(getattr(args, "bus_dir", "") or ""):
        raise DispatchError(
            f"stale bridge retries from shared state: teammate lane {raw_lane!r} "
            "must not use the default .agent_bus"
        )
    try:
        identity = resolve_monitor_identity(
            repo_root,
            lane=raw_lane,
            bus_dir=getattr(args, "bus_dir", None),
            require_configured_named=True,
        )
    except MonitorIdentityError as exc:
        raise DispatchError(f"teammate lane identity rejected: {exc}") from exc
    args.bus_dir = identity.bus_dir
    setattr(args, "_teammate_identity", identity.as_dict())
    target_root = _create_or_select_teammate_worktree(
        repo_root,
        lane=identity.lane,
        bus_dir=identity.bus_dir,
        verbose=getattr(args, "verbose", False),
    )
    setattr(args, "_teammate_worktree", str(target_root))
    setattr(args, "_teammate_script_repo_root", target_root)
    return target_root


def _emit_completed_process_output(
    completed: subprocess.CompletedProcess[str],
) -> None:
    """Mirror a completed subprocess's captured output to the caller."""
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)


def _carry_forward_founder_override(record: dict[str, Any] | None) -> dict[str, str]:
    """Founder-override fields to carry across an A->B routing-record rebuild.

    launch_wave persists the wave's declared ``founder_override`` into the routing
    record at launch time. When the dispatcher rebuilds the routing dict for the
    chained Phase B leg it constructs a fresh dict from a few fields, so the
    override must be copied forward explicitly. Without this, the rebuilt record
    drops the launch-persisted token on the normal chained path and the
    commit-executor Step-5e growth-cap auto-bump reads an empty token via
    ``_extract_founder_override_from_routing_record`` -> a gate-authoring wave
    strands ``no_founder_override``. Both field forms the extractor recognises
    (``founder_override_token`` then ``founder_override``) are preserved when
    present and non-empty; absent fields yield an empty dict, so records without a
    declared override (e.g. the surface-retry path) are unchanged.
    """
    carried: dict[str, str] = {}
    for key in ("founder_override_token", "founder_override"):
        value = (record or {}).get(key)
        if isinstance(value, str) and value.strip():
            carried[key] = value.strip()
    return carried


def _continue_successful_executor_chain(
    executor_name: str,
    completed: subprocess.CompletedProcess[str],
    *,
    repo_root: Path,
    config: dict[str, Any],
    record: dict[str, Any] | None = None,
    verbose: bool = False,
    emit_output: bool = False,
    chain_origin: str | None = None,
    bus_dir: str | Path | None = None,
    script_repo_root: Path | None = None,
    max_bridge_rounds: int | None = None,
) -> dict[str, Any]:
    """Continue the A→B→commit chain after a successful executor leg."""
    executor_script_dir = _script_dir_for_repo(script_repo_root)
    if executor_name == "phase_a_executor":
        plan_path = _extract_plan_path(completed.stdout, repo_root)
        if plan_path is None:
            return {
                "status": "failed",
                "decision": "ROUTE_PHASE_A",
                "executor": executor_name,
                "exit_code": 0,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "message": "Phase A converged but no plan_path found in output",
            }

        if verbose:
            print(f"[dispatch] Phase A converged → chaining to Phase B with plan: {plan_path}")

        phase_b_wave_name = (record or {}).get("wave_name", "")
        plan_wave_id = _phase_b_plan_declared_wave_id(repo_root, plan_path)
        routed_wave_candidates: list[str] = []
        for candidate in _selected_routing_candidate_dicts(record or {}):
            if not (
                candidate.get("wave_name")
                or candidate.get("wave_id")
                or candidate.get("tracked_packet")
            ):
                continue
            candidate_wave = _routing_candidate_authority_wave_id(
                repo_root,
                record or {},
                candidate,
            )
            if candidate_wave:
                routed_wave_candidates.append(candidate_wave)
        routed_wave_candidates = [wave for wave in routed_wave_candidates if wave]
        expected_wave = (
            routed_wave_candidates[0]
            if len(set(routed_wave_candidates)) == 1
            else ""
        )
        if plan_wave_id and expected_wave and plan_wave_id != expected_wave:
            return {
                "status": "error",
                "decision": "ROUTE_PHASE_B",
                "executor": "phase_b_executor",
                "message": (
                    "Phase A produced a tracked packet whose Wave ID conflicts "
                    f"with the routed candidate: {plan_path} declares "
                    f"{plan_wave_id}, routed candidate is {expected_wave}. "
                    "Refusing to chain Phase B."
                ),
                "chained_from": "phase_a_executor",
            }
        authority_plan_path = _phase_a_normalized_retry_chain_authority_packet(
            repo_root,
            plan_path=plan_path,
            record=record or {},
            plan_wave_id=plan_wave_id,
        )
        phase_b_plan_path = authority_plan_path or plan_path
        if authority_plan_path:
            authority_wave_id = _phase_b_plan_declared_wave_id(repo_root, authority_plan_path)
            if authority_wave_id:
                plan_wave_id = authority_wave_id
        if plan_wave_id:
            # The surface plan name can omit the dated wave suffix; commit
            # identity must follow the converged locked packet Phase B uses.
            phase_b_wave_name = plan_wave_id
        if authority_plan_path:
            phase_b_candidates = _phase_a_normalized_retry_phase_b_candidates(
                repo_root,
                record or {},
                plan_path=plan_path,
                authority_packet=authority_plan_path,
                authority_wave_id=plan_wave_id,
            )
        else:
            phase_b_candidates = list((record or {}).get("next_candidates", []))
        phase_b_tracked_packet = _phase_b_plan_routing_packet(repo_root, phase_b_plan_path)
        if plan_wave_id and not _routing_record_tracked_packet(
            {"next_candidates": phase_b_candidates}
        ):
            phase_b_candidates = [
                {
                    "candidate": plan_wave_id,
                    "bounded": True,
                    "tracked_packet": phase_b_tracked_packet,
                }
            ]
        else:
            phase_b_tracked_packet = (
                _routing_record_tracked_packet({"next_candidates": phase_b_candidates})
                or phase_b_tracked_packet
            )
        tracker_gate = _phase_b_tracker_gate_result(
            repo_root,
            plan_path=phase_b_plan_path,
            wave_id=phase_b_wave_name,
            tracked_packet=phase_b_tracked_packet,
        )
        if tracker_gate is not None:
            tracker_gate["chained_from"] = "phase_a_executor"
            return tracker_gate

        phase_b_timeout = config.get("timeouts", {}).get("phase_b_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["phase_b_executor"])
        phase_b_routing = {
            "decision": "ROUTE_PHASE_B",
            "wave_name": phase_b_wave_name,
            "task_id": (record or {}).get("task_id", ""),
            "summary": "Chained from Phase A convergence",
            "next_candidates": phase_b_candidates,
            # Carry the wave's declared FOUNDER_OVERRIDE across the A->B rebuild so
            # the commit-executor Step-5e growth-cap auto-bump reads a non-empty
            # token (see _carry_forward_founder_override). Without this, the rebuilt
            # dict dropped the launch-persisted override on the normal chained path
            # and a gate-authoring wave stranded 'no_founder_override'.
            **_carry_forward_founder_override(record),
        }
        phase_b_args = [
            sys.executable,
            str(executor_script_dir / "phase_b_executor.py"),
            "--plan", phase_b_plan_path,
            "--routing-record", json.dumps(phase_b_routing),
            "--max-rounds",
            str(max_bridge_rounds or _configured_bridge_loop_limit(config, "phase_b")),
            "--dispatcher-owned-recovery",
            "--json",
        ]
        if bus_dir is not None:
            phase_b_args.extend(["--bus-dir", str(bus_dir)])
        try:
            phase_b_result = _run_executor_in_group(
                phase_b_args, cwd=repo_root, timeout=phase_b_timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "decision": "ROUTE_PHASE_B",
                "executor": "phase_b_executor",
                "message": f"Phase B executor timed out after {phase_b_timeout}s",
                "chained_from": "phase_a_executor",
            }
        if emit_output:
            _emit_completed_process_output(phase_b_result)
        if phase_b_result.returncode != 0:
            return {
                "status": "failed",
                "decision": "ROUTE_PHASE_B",
                "executor": "phase_b_executor",
                "exit_code": phase_b_result.returncode,
                "stdout": phase_b_result.stdout,
                "stderr": phase_b_result.stderr,
                "chained_from": "phase_a_executor",
            }
        return _continue_successful_executor_chain(
            "phase_b_executor",
            phase_b_result,
            repo_root=repo_root,
            config=config,
            record=phase_b_routing,
            verbose=verbose,
            emit_output=emit_output,
            chain_origin="phase_a_executor",
            bus_dir=bus_dir,
            script_repo_root=script_repo_root,
        )

    if executor_name == "phase_b_executor":
        handoff_path = agent_bus_path(repo_root, bus_dir, "executors", "phase_b_handoff.json")
        if not handoff_path.exists():
            origin = chain_origin or "phase_b_executor"
            payload = _extract_structured_stdout_payload(completed.stdout or "")
            if isinstance(payload, dict):
                recovery = payload.get("recovery")
                status = payload.get("status")
                if (
                    isinstance(recovery, dict)
                    and recovery.get("recovered")
                    and status not in {"success", "ready", "commit_ready"}
                ):
                    return {
                        "status": "failed",
                        "decision": "ROUTE_PHASE_B",
                        "executor": executor_name,
                        "exit_code": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                        "message": (
                            "Phase B recovered in-process and must be retried "
                            "before chaining commit"
                        ),
                        "recovery": recovery,
                        "retry_record": dict(record or {}),
                        "chained_from": (
                            "phase_a_executor" if origin == "phase_a_executor" else None
                        ),
                    }
                if status not in {None, "success", "ready", "commit_ready"}:
                    return {
                        "status": "failed",
                        "decision": "ROUTE_PHASE_B",
                        "executor": executor_name,
                        "exit_code": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                        "message": (
                            f"Phase B exited 0 with status {status} but produced no handoff"
                        ),
                        "chained_from": (
                            "phase_a_executor" if origin == "phase_a_executor" else None
                        ),
                    }
            return {
                "status": "failed",
                "decision": "ROUTE_PHASE_B",
                "executor": executor_name,
                "exit_code": 0,
                "message": "Phase B converged but no handoff file found",
                "chained_from": (
                    "phase_a_executor" if origin == "phase_a_executor" else None
                ),
            }

        if record and (
            record.get("wave_name")
            or record.get("wave_id")
            or record.get("task_id")
            or _routing_record_tracked_packet(record)
        ):
            valid_handoff, handoff_msg = _validate_phase_b_handoff_identity(
                handoff_path, record
            )
            if not valid_handoff:
                origin = chain_origin or "phase_b_executor"
                return {
                    "status": "error",
                    "decision": "COMMIT_GO",
                    "executor": "commit_executor",
                    "message": f"Phase B handoff validation failed: {handoff_msg}",
                    "chained_from": (
                        "phase_a_executor → phase_b_executor"
                        if origin == "phase_a_executor"
                        else "phase_b_executor"
                    ),
                }

        if verbose:
            print("[dispatch] Phase B converged → chaining to commit executor")

        commit_timeout = config.get("timeouts", {}).get("commit_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_executor"])
        commit_args = [
            sys.executable,
            str(executor_script_dir / "commit_executor.py"),
            "--handoff", str(handoff_path),
            "--json",
        ]
        if bus_dir is not None:
            commit_args.extend(["--bus-dir", str(bus_dir)])
        try:
            commit_result = _run_executor_in_group(
                commit_args, cwd=repo_root, timeout=commit_timeout,
            )
        except subprocess.TimeoutExpired:
            origin = chain_origin or "phase_b_executor"
            return {
                "status": "timeout",
                "decision": "COMMIT_GO",
                "executor": "commit_executor",
                "message": f"Commit executor timed out after {commit_timeout}s",
                "chained_from": (
                    "phase_a_executor → phase_b_executor"
                    if origin == "phase_a_executor"
                    else "phase_b_executor"
                ),
            }
        if emit_output:
            _emit_completed_process_output(commit_result)
        c_status, c_decision = _classify_commit_executor_result(commit_result)
        origin = chain_origin or "phase_b_executor"
        return {
            "status": c_status,
            "decision": c_decision,
            "executor": "commit_executor",
            "exit_code": commit_result.returncode,
            "stdout": commit_result.stdout,
            "stderr": commit_result.stderr,
            "chained_from": (
                "phase_a_executor → phase_b_executor"
                if origin == "phase_a_executor"
                else "phase_b_executor"
            ),
        }

    nc_status, nc_decision = ("success", record.get("decision", "") if record else "")
    if executor_name == "commit_executor":
        nc_status, nc_decision = _classify_commit_executor_result(completed)
    return {
        "status": nc_status,
        "decision": nc_decision,
        "executor": executor_name,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_executor_in_group(
    args: list[str],
    cwd: Path,
    timeout: int | float,
) -> subprocess.CompletedProcess[str]:
    """Run an executor subprocess in its own process group.

    On timeout, kills the entire process group (including grandchildren)
    before raising TimeoutExpired.  This prevents orphaned worker
    subprocesses from persisting across retry attempts.
    """
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    previous_handlers = {
        signum: signal.getsignal(signum)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }

    def _cleanup_for_signal(signum: int, _frame: Any) -> None:
        try:
            terminate_process_tree(proc.pid, cwd=cwd)
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass
        if signum == signal.SIGINT:
            raise KeyboardInterrupt()
        raise SystemExit(128 + signum)

    for signum in previous_handlers:
        signal.signal(signum, _cleanup_for_signal)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Collect the full descendant tree BEFORE killing the process group.
        # Children spawned with start_new_session=True (e.g. claude --print
        # via bridge_adapters.py:576) live in separate sessions and survive
        # os.killpg.  After killpg they get reparented to PID 1 and become
        # unreachable via PPID-tree walking.  Snapshot them first.
        try:
            pre_kill_descendants = process_descendants(proc.pid, cwd=cwd)
        except Exception:
            pre_kill_descendants = set()
        # Kill the process group (catches same-session children)
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
        # Kill descendants from the pre-kill snapshot (catches cross-session children)
        for pid in sorted(pre_kill_descendants, reverse=True):
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            terminate_process_tree(proc.pid, cwd=cwd)
        except Exception:
            pass
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()
        raise
    except BaseException:
        try:
            terminate_process_tree(proc.pid, cwd=cwd)
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass
        raise
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)


def _retry_commit_only(
    repo: Path,
    config: dict[str, Any],
    *,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
    script_repo_root: Path | None = None,
) -> dict[str, Any]:
    """Retry only the commit executor using the existing Phase B handoff.

    Used when a chained commit fails — avoids re-running Phase A/B.
    """
    handoff_path = agent_bus_path(repo, bus_dir, "executors", "phase_b_handoff.json")
    if not handoff_path.exists():
        return {
            "status": "error",
            "decision": "COMMIT_GO",
            "executor": "commit_executor",
            "message": f"Cannot retry commit: handoff file missing at {handoff_path}",
        }

    if verbose:
        print("[dispatch] Retrying commit executor only (Phase A/B already succeeded)")

    commit_timeout = config.get("timeouts", {}).get("commit_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_executor"])
    executor_script_dir = _script_dir_for_repo(script_repo_root)
    commit_args = [
        sys.executable,
        str(executor_script_dir / "commit_executor.py"),
        "--json",
        "--handoff", str(handoff_path),
    ]
    if bus_dir is not None:
        commit_args.extend(["--bus-dir", str(bus_dir)])
    try:
        commit_result = _run_executor_in_group(
            commit_args, cwd=repo, timeout=commit_timeout,
        )
        c_status, c_decision = _classify_commit_executor_result(commit_result)
        return {
            "status": c_status,
            "decision": c_decision,
            "executor": "commit_executor",
            "exit_code": commit_result.returncode,
            "stdout": commit_result.stdout,
            "stderr": commit_result.stderr,
            "chained_from": "retry_commit_only",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "decision": "COMMIT_GO",
            "executor": "commit_executor",
            "message": f"Commit executor timed out after {commit_timeout}s",
        }


def _post_commit_continuation_ready_for_record(
    repo: Path,
    record: dict[str, Any],
    *,
    bus_dir: str | Path | None = None,
) -> tuple[bool, str]:
    wave_id = normalize_wave_id(str(record.get("wave_name") or record.get("wave_id") or ""))
    if not wave_id or wave_id == "wave-unknown":
        return False, "routing record has no normalized wave id"

    handoff_path = agent_bus_path(repo, bus_dir, "executors", "phase_b_handoff.json")
    if not handoff_path.exists():
        return False, f"Phase B handoff missing at {handoff_path}"
    valid_handoff, handoff_msg = _validate_phase_b_handoff_identity(handoff_path, record)
    if not valid_handoff:
        return False, f"Phase B handoff does not match stale routing record: {handoff_msg}"

    continuation_path = agent_bus_path(repo, bus_dir, "executors", f"commit_executor_{wave_id}.json")
    if not continuation_path.exists():
        return False, f"commit continuation missing at {continuation_path}"
    try:
        payload = json.loads(continuation_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"commit continuation unreadable at {continuation_path}: {exc}"
    if not isinstance(payload, dict):
        return False, "commit continuation is not a JSON object"
    if payload.get("version") != 1:
        return False, "commit continuation version is not 1"
    if str(payload.get("status") or "").strip() != "post_commit_pending":
        return False, "commit continuation is not post_commit_pending"
    if str(payload.get("receipt_decision") or "").strip() not in {"COMMIT_GO", "COMMIT_GO_HOLD_PUSH"}:
        return False, "commit continuation has no commit-capable receipt decision"

    steps_completed = payload.get("steps_completed")
    if not isinstance(steps_completed, list) or "git_commit" not in steps_completed:
        return False, "commit continuation has not completed git_commit"
    target_branch = str(payload.get("target_branch") or "").strip()
    commit_sha = str(payload.get("commit_sha") or "").strip()
    if not target_branch or not commit_sha:
        return False, "commit continuation missing target_branch or commit_sha"

    try:
        current_branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout.strip()
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit_sha}^{{commit}}"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit_sha, "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        return False, f"commit continuation git proof failed: {exc}"
    if current_branch != target_branch:
        return False, f"current branch {current_branch} does not match continuation target_branch {target_branch}"
    if ancestor.returncode != 0:
        return False, f"commit continuation commit {commit_sha} is not an ancestor of HEAD"

    return True, f"post-commit continuation ready for {wave_id}"


_RECOVERY_OVERRIDE_ENV_KEYS = (
    "RCX_RECOVERY_TIMEOUT_OVERRIDE",
    "RCX_RECOVERY_TIMEOUT_KEY",
    "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE",
    "RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY",
    "RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE",
)


def _clear_recovery_override_env() -> None:
    """Clear one-shot recovery override env vars after retry scope exits."""
    for env_key in _RECOVERY_OVERRIDE_ENV_KEYS:
        os.environ.pop(env_key, None)


def _apply_recovery_overrides(
    config: dict[str, Any],
    repo_root: Path | None = None,
    verbose: bool = False,
) -> dict[str, Any] | None:
    """Apply Tier 2 recovery env var overrides to in-memory config for retry.

    fix_process_timeout sets RCX_RECOVERY_TIMEOUT_OVERRIDE (and
    RCX_RECOVERY_TIMEOUT_KEY to target the correct executor timeout).
    fix_implementer_stale sets RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE.

    These are applied to the in-memory config dict. Child executors that reload
    config materialize the same inherited env vars through executor_common.
    The tracked executor_config.json must remain read-only during recovery.

    Returns original in-memory timeout sections if any override was applied so
    loop callers can restore the live config between waves.
    """
    original_config: dict[str, Any] = {
        "timeouts": dict(config.get("timeouts", {})),
        "bridge_turn_timeouts": dict(config.get("bridge_turn_timeouts", {})),
        "_restore_disk": False,
    }
    config_modified = False

    timeout_override = os.environ.get("RCX_RECOVERY_TIMEOUT_OVERRIDE")
    if timeout_override:
        try:
            val = int(timeout_override)
            timeout_key = os.environ.get(
                "RCX_RECOVERY_TIMEOUT_KEY", "phase_b_executor")
            config.setdefault("timeouts", {})[timeout_key] = val
            config_modified = True
            if verbose:
                print(f"[dispatch] Applied timeout override: {timeout_key}={val}s")
        except ValueError:
            pass

    bridge_turn_timeout_override = os.environ.get("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE")
    if bridge_turn_timeout_override:
        try:
            val = int(bridge_turn_timeout_override)
            phase_key = os.environ.get("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY", "phase_b")
            config.setdefault("bridge_turn_timeouts", {})[phase_key] = val
            config_modified = True
            if verbose:
                print(
                    "[dispatch] Applied bridge turn timeout override: "
                    f"{phase_key}={val}s"
                )
        except ValueError:
            pass

    stale_override = os.environ.get("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE")
    if stale_override:
        try:
            val = int(stale_override)
            config.setdefault("timeouts", {})["phase_b_implementer_stale"] = val
            config_modified = True
            if verbose:
                print(f"[dispatch] Applied stale timeout override: "
                      f"phase_b_implementer_stale={val}s")
        except ValueError:
            pass

    return original_config if config_modified else None


def _merge_recovery_original_config(
    original_config: dict[str, Any] | None,
    new_config: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Keep the first in-memory baseline and later disk restore data."""
    if new_config is None:
        return original_config
    if original_config is None:
        return new_config
    if new_config.get("_restore_disk") and not original_config.get("_restore_disk"):
        original_config["_restore_disk"] = True
        for key in ("_disk_timeouts", "_disk_bridge_turn_timeouts"):
            if key in new_config:
                original_config[key] = new_config[key]
    return original_config


def _recovery_original_section(
    original_config: dict[str, Any],
    section: str,
) -> dict[str, Any]:
    """Return a timeout section from either current nested or legacy flat baselines."""
    if not isinstance(original_config, dict):
        return {}
    value = original_config.get(section)
    if isinstance(value, dict):
        return dict(value)
    if section == "timeouts":
        nested_section_keys = {"timeouts", "bridge_turn_timeouts"}
        if not any(isinstance(original_config.get(key), dict) for key in nested_section_keys):
            return dict(original_config)
    return {}


def _restore_config_on_disk(
    repo_root: Path,
    original_config: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Restore original timeout sections to executor_config.json after recovery retry."""
    if original_config.get("_restore_disk") is False:
        return

    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    try:
        disk_config = json.loads(config_path.read_text(encoding="utf-8"))
        disk_timeouts = original_config.get("_disk_timeouts")
        disk_bridge_turn_timeouts = original_config.get("_disk_bridge_turn_timeouts")
        disk_config["timeouts"] = (
            dict(disk_timeouts)
            if isinstance(disk_timeouts, dict)
            else _recovery_original_section(original_config, "timeouts")
        )
        disk_config["bridge_turn_timeouts"] = (
            dict(disk_bridge_turn_timeouts)
            if isinstance(disk_bridge_turn_timeouts, dict)
            else _recovery_original_section(original_config, "bridge_turn_timeouts")
        )
        config_path.write_text(
            json.dumps(disk_config, indent=2) + "\n", encoding="utf-8")
        if verbose:
            print("[dispatch] Restored original executor_config.json timeout sections")
    except (json.JSONDecodeError, OSError):
        pass


def _clear_phase_b_state_for_retry(
    repo_root: Path,
    result: dict[str, Any],
    *,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
) -> None:
    """Clear Phase B persisted state before a dispatcher retry.

    When Phase B fails during the bridge-fix cycle (e.g. implementer_bridge_fix
    or pytest_fix step), it returns without clearing its persisted state.  The
    stale checkpoint (typically completed_step="agent_review") would cause the
    next Phase B invocation to skip the implementer re-entry, bypassing the
    required bridge-fix cycle.  Clearing the state forces a fresh start.
    """
    if result.get("executor") != "phase_b_executor":
        return
    recovery = result.get("recovery")
    if (
        isinstance(recovery, dict)
        and recovery.get("recovered")
        and recovery.get("failure_class") == "post_reentry_needs_phase_b"
        and recovery.get("action") == "resume_phase_b_reentry"
    ):
        if verbose:
            print("[dispatch] Preserved recovery-seeded Phase B re-entry state before retry")
        return
    state_path = agent_bus_path(repo_root, bus_dir, "executors", "phase_b_state.json")
    if state_path.exists():
        state_path.unlink()
        if verbose:
            print("[dispatch] Cleared stale Phase B state before retry")


_PHASE_B_RECOVERY_STEPS = frozenset({
    "phase_b",
    "phase_b_executor",
    "post_reentry_supervisor",
})


def _phase_b_result_context(result: dict[str, Any]) -> bool:
    """Return true when a recovered result genuinely belongs to Phase B."""
    executor = str(result.get("executor") or "").strip().lower().replace("-", "_")
    step = str(result.get("step") or "").strip().lower().replace("-", "_")
    return executor == "phase_b_executor" or step in _PHASE_B_RECOVERY_STEPS


def _retry_record_wave_matches_current(
    retry_record: dict[str, Any],
    current_record: dict[str, Any] | None,
) -> bool:
    """Keep recovered retry routing bound to the current wave when both are known."""
    if not current_record:
        return True
    retry_wave = _routing_record_wave_id(retry_record)
    current_wave = _routing_record_wave_id(current_record)
    return not (retry_wave and current_wave and retry_wave != current_wave)


def _retry_record_adds_routing_authority(
    retry_record: dict[str, Any],
    current_record: dict[str, Any] | None,
) -> bool:
    """Return true when a recovered record should override normal routing reload."""
    if not current_record:
        return True
    retry_decision = str(retry_record.get("decision") or "").strip()
    current_decision = str(current_record.get("decision") or "").strip()
    if retry_decision and retry_decision != current_decision:
        return True
    if str(retry_record.get("plan_path") or retry_record.get("tracked_packet") or "").strip():
        return True
    if _routing_record_tracked_packet(retry_record):
        return True
    return False


def _recovered_retry_record(
    result: dict[str, Any],
    *,
    current_record: dict[str, Any] | None = None,
    allow_phase_b_to_phase_a: bool = False,
) -> dict[str, Any] | None:
    """Return a recovered executor's explicit retry record when it is valid."""
    retry_record = result.get("retry_record")
    if not isinstance(retry_record, dict):
        return None
    decision = str(retry_record.get("decision") or "").strip()
    if decision not in ROUTING_DISPATCH:
        return None
    phase_b_context = _phase_b_result_context(result)
    if decision == "ROUTE_PHASE_B":
        if not phase_b_context:
            return None
        if not _retry_record_wave_matches_current(retry_record, current_record):
            return None
        if not _retry_record_adds_routing_authority(retry_record, current_record):
            return None
    if decision == "ROUTE_PHASE_A" and phase_b_context:
        if not _retry_record_wave_matches_current(retry_record, current_record):
            return None
        bootstrap_exception = bool(result.get("bootstrap_exception"))
        if not bootstrap_exception and not allow_phase_b_to_phase_a:
            return None
    try:
        return json.loads(json.dumps(retry_record))
    except (TypeError, ValueError):
        return dict(retry_record)


def _auto_refresh_routing(
    repo_root: Path,
    *,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
    script_repo_root: Path | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Re-run the post-merge supervisor to refresh a stale routing record.

    Looks for the canonical post-merge package at .agent_bus/meta/post_merge_package.json.
    Returns (success, refreshed_record) — record is None on failure.
    """
    package_path = agent_bus_path(repo_root, bus_dir, "meta", POST_MERGE_PACKAGE_NAME)
    if not package_path.exists():
        if verbose:
            print(f"[dispatch] No post-merge package at {package_path} — cannot auto-refresh")
        return False, None
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if verbose:
            print(f"[dispatch] Cannot read post-merge package at {package_path}: {exc}")
        return False, None
    package_merge_sha = package.get("merge_sha")
    current_head = _compute_repo_state(repo_root).head_sha
    if not isinstance(package_merge_sha, str) or not package_merge_sha.strip():
        if verbose:
            print("[dispatch] Post-merge package has no merge_sha — cannot auto-refresh")
        return False, None
    package_merge_sha = package_merge_sha.strip()
    # This is stricter than the manual post-merge supervisor gate: dispatcher
    # auto-refresh implicitly reuses the canonical on-disk package, so an
    # ancestor merge_sha can replay an obsolete bounded next candidate.
    if package_merge_sha != current_head:
        repaired = _refresh_stale_post_merge_package_after_manual_merge(
            repo_root,
            package,
            current_head=current_head,
            verbose=verbose,
            bus_dir=bus_dir,
        )
        if not repaired:
            if verbose:
                print(
                    "[dispatch] Post-merge package is stale: "
                    f"merge_sha={package_merge_sha[:8]}, current HEAD={current_head[:8]}"
                )
            return False, None
        try:
            package = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            if verbose:
                print(f"[dispatch] Cannot re-read refreshed post-merge package: {exc}")
            return False, None
        package_merge_sha = package.get("merge_sha")
        if not isinstance(package_merge_sha, str) or package_merge_sha.strip() != current_head:
            if verbose:
                print("[dispatch] Repaired post-merge package did not bind current HEAD")
            return False, None

    supervisor_script = _agents_dir_for_repo(script_repo_root) / "meta_bridge_supervisor.py"
    if not supervisor_script.exists():
        if verbose:
            print(f"[dispatch] Supervisor script not found: {supervisor_script}")
        return False, None

    cmd = [
        sys.executable,
        str(supervisor_script),
        "--mode", "post-merge",
        "--package", str(package_path),
        "--json",
    ]
    if bus_dir is not None:
        cmd.extend(["--bus-dir", str(bus_dir)])
    if verbose:
        cmd.append("--verbose")
        print(f"[dispatch] Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        if verbose:
            print("[dispatch] Post-merge supervisor timed out during auto-refresh")
        return False, None

    if result.returncode != 0:
        if verbose:
            print(f"[dispatch] Post-merge supervisor exited {result.returncode}")
            if result.stderr:
                print(f"[dispatch] stderr: {result.stderr[:500]}")
        return False, None

    # Reload the routing record
    try:
        refreshed = _common_load_routing_record(repo_root, bus_dir=bus_dir)
    except ExecutorCommonError as exc:
        if verbose:
            print(f"[dispatch] Failed to reload routing record after refresh: {exc}")
        return False, None

    # Verify freshness of the refreshed record
    fresh, msg = validate_routing_record_freshness(refreshed, repo_root)
    if not fresh:
        if verbose:
            print(f"[dispatch] Refreshed record still stale: {msg}")
        return False, None

    if verbose:
        print(f"[dispatch] Auto-refresh succeeded: decision={refreshed.get('decision')}")
    return True, refreshed


def _refresh_stale_post_merge_package_after_manual_merge(
    repo_root: Path,
    package: dict[str, Any],
    *,
    current_head: str,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
) -> bool:
    """Repair the package refresh step missed by a bounded manual PR merge."""
    stale_merge_sha = package.get("merge_sha")
    if not isinstance(stale_merge_sha, str) or not stale_merge_sha.strip():
        return False
    stale_merge_sha = stale_merge_sha.strip()
    if not _git_is_ancestor(repo_root, stale_merge_sha, current_head):
        if verbose:
            print(
                "[dispatch] Refusing stale package repair: "
                f"merge_sha={stale_merge_sha[:8]} is not an ancestor of HEAD"
            )
        return False
    pr_number = _github_merge_commit_pr_number(repo_root, current_head)
    if pr_number is None:
        if verbose:
            print(
                "[dispatch] Refusing stale package repair: current HEAD is not "
                "a GitHub pull-request merge commit"
            )
        return False
    try:
        commit_executor_mod = _load_commit_executor_module()
    except Exception as exc:  # pragma: no cover - defensive import diagnostics
        if verbose:
            print(f"[dispatch] Cannot load commit executor package refresher: {exc}")
        return False
    refresh = getattr(commit_executor_mod, "_refresh_post_merge_package_for_next_open_queue", None)
    if refresh is None:
        if verbose:
            print("[dispatch] Commit executor has no post-merge package refresher")
        return False

    active_bus_dir = getattr(commit_executor_mod, "_ACTIVE_BUS_DIR", None)
    token = None
    if active_bus_dir is not None and bus_dir is not None:
        token = active_bus_dir.set(Path(bus_dir))

    def log(message: str) -> None:
        if verbose:
            print(f"[dispatch] {message}")

    try:
        refresh(
            repo_root=repo_root,
            handoff={"task_id": package.get("task_id") or "[NEXT-CODEX-POST-REDTEAM]"},
            result={"pr_number": str(pr_number)},
            merge_sha=current_head,
            log=log,
        )
    except Exception as exc:  # pragma: no cover - defensive runtime diagnostics
        if verbose:
            print(f"[dispatch] Failed stale package repair: {exc}")
        return False
    finally:
        if token is not None:
            active_bus_dir.reset(token)
    return True


def _git_is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def _github_merge_commit_pr_number(repo_root: Path, commit_sha: str) -> int | None:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%P%x00%s", commit_sha],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    parents, sep, subject = result.stdout.partition("\0")
    if not sep or len(parents.split()) < 2:
        return None
    match = re.search(r"\bMerge pull request #(?P<pr>\d+)\b", subject)
    if not match:
        return None
    return int(match.group("pr"))


def _load_commit_executor_module() -> Any:
    try:
        import commit_executor as commit_executor_mod

        return commit_executor_mod
    except ImportError:
        import importlib.util as _ilu

        commit_path = SCRIPT_DIR / "commit_executor.py"
        spec = _ilu.spec_from_file_location("commit_executor", str(commit_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load commit executor from {commit_path}")
        commit_executor_mod = _ilu.module_from_spec(spec)
        sys.modules["commit_executor"] = commit_executor_mod
        spec.loader.exec_module(commit_executor_mod)
        return commit_executor_mod


def _refresh_canonical_routing_record_state(
    repo_root: Path,
    record: dict[str, Any],
    *,
    output_path: Path | None = None,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Rebind the canonical packet-owned routing record to the current repo state."""
    tracked_packet = _routing_record_tracked_packet(record)
    if not tracked_packet:
        if verbose:
            print("[dispatch] Canonical routing rebind failed: no tracked_packet")
        return False, None

    # Carry the wave's declared FOUNDER_OVERRIDE across the canonical rebind so the
    # commit-executor Step-5e growth-cap auto-bump still reads a non-empty token via
    # _extract_founder_override_from_routing_record. Without this, resuming a launched
    # wave on a stale canonical post_merge_routing.json rebuilt the record through the
    # builder WITHOUT the override -- dropping the launch-persisted token and stranding
    # a gate-authoring wave on 'no_founder_override'. The builder emits a single
    # ``founder_override`` key; both routing-record consumers read
    # ``founder_override_token`` then ``founder_override`` with fallback, so collapsing
    # the carried token-first value into that one param preserves the override. Mirrors
    # the chained A->B path (see _carry_forward_founder_override).
    carried_founder_override = _carry_forward_founder_override(record)
    founder_override_value = (
        carried_founder_override.get("founder_override_token")
        or carried_founder_override.get("founder_override")
        or ""
    )
    refreshed, errors = _common_build_and_write_routing_record(
        wave_name=str(record.get("wave_name") or record.get("wave_id") or ""),
        task_id=str(record.get("task_id") or ""),
        tracked_packet=tracked_packet,
        request_for_claude=str(record.get("request_for_claude") or ""),
        request_for_agent=str(record.get("request_for_agent") or ""),
        summary=str(record.get("summary") or ""),
        decision=str(record.get("decision") or ""),
        merged_pr=record.get("merged_pr") if isinstance(record.get("merged_pr"), int) else None,
        merge_sha=record.get("merge_sha") if isinstance(record.get("merge_sha"), str) else None,
        repo_root=repo_root,
        output_path=output_path or _canonical_routing_record_path(repo_root, bus_dir),
        bus_dir=bus_dir,
        allow_completed_tracked_packet=bool(record.get("allow_completed_tracked_packet")),
        founder_override=founder_override_value,
    )
    if errors:
        if verbose:
            print("[dispatch] Canonical routing rebind failed: " + "; ".join(errors[:3]))
        return False, None

    fresh, msg = validate_routing_record_freshness(refreshed, repo_root)
    if not fresh:
        if verbose:
            print(f"[dispatch] Canonical routing rebind still stale: {msg}")
        return False, None

    if verbose:
        print(f"[dispatch] Canonical routing rebind succeeded: decision={refreshed.get('decision')}")
    return True, refreshed


def _extract_plan_path(phase_a_stdout: str, repo_root: Path) -> str | None:
    """Parse plan_path from Phase A executor output (JSON or text)."""
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        start = phase_a_stdout.find("{", cursor)
        if start == -1:
            break
        try:
            data, end = decoder.raw_decode(phase_a_stdout[start:])
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        pp = data.get("plan_path") if isinstance(data, dict) else None
        if isinstance(pp, str) and pp:
            return pp
        cursor = start + max(end, 1)
    # Try full output as JSON
    try:
        data = json.loads(phase_a_stdout)
        pp = data.get("plan_path")
        if isinstance(pp, str) and pp:
            return pp
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: parse "[phase-a] Plan: <path>" text output
    for line in phase_a_stdout.splitlines():
        if line.strip().startswith("[phase-a] Plan:"):
            pp = line.split("Plan:", 1)[1].strip()
            if pp:
                return pp
    return None


def dispatch(
    record: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    routing_record_path: Path | None = None,
    skip_freshness: bool = False,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Dispatch a routing decision to the appropriate executor.

    Returns a result dict with status, executor, and output.
    """
    try:
        ensure_not_agent_review_mode("executor_dispatch.dispatch")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "decision": record.get("decision", ""),
            "message": str(exc),
        }

    repo = repo_root or REPO_ROOT
    try:
        resolve_agent_bus_dir(repo, bus_dir)
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "decision": record.get("decision", ""),
            "message": str(exc),
        }
    cfg = config or load_config()
    # Preserve caller/canonical identity before TASKS.md tracked_packet backfill.
    identity_record = record
    record = _enrich_founder_ordered_tracked_packets(repo, record)
    decision = record.get("decision", "")

    # Stop tokens — require human intervention
    if decision in STOP_TOKENS:
        return {
            "status": "stopped",
            "decision": decision,
            "summary": record.get("summary", ""),
            "request_for_agent": record.get("request_for_agent") or record.get("request_for_claude", ""),
            "request_for_claude": record.get("request_for_agent") or record.get("request_for_claude", ""),
            "message": f"Routing stopped: {decision}. Requires founder/triage intervention.",
        }

    # Resolve executor
    executor_name = resolve_executor(decision)
    if executor_name is None:
        return {
            "status": "error",
            "decision": decision,
            "message": f"Unknown routing decision: {decision}. No executor mapped.",
        }

    # Check if executor is implemented
    if executor_name not in AVAILABLE_EXECUTORS:
        return {
            "status": "not_implemented",
            "decision": decision,
            "executor": executor_name,
            "message": f"Executor {executor_name} is not yet implemented (Slice 3-6). "
                       f"Manual execution required.",
        }

    # Validate freshness — auto-refresh via post-merge supervisor if stale
    if not skip_freshness:
        fresh, msg = validate_routing_record_freshness(record, repo)
        if not fresh:
            is_inline_caller_owned = (
                routing_record_path is None
                and not _matches_canonical_routing_record(identity_record, repo, bus_dir)
            )
            is_noncanonical_explicit = (
                routing_record_path is not None
                and routing_record_path.resolve() != _canonical_routing_record_path(repo, bus_dir)
            )
            is_canonical_explicit = (
                routing_record_path is not None
                and routing_record_path.resolve() == _canonical_routing_record_path(repo, bus_dir)
            )
            if not is_noncanonical_explicit and not is_inline_caller_owned:
                continuation_ready, continuation_detail = _post_commit_continuation_ready_for_record(
                    repo,
                    record,
                    bus_dir=bus_dir,
                )
                if continuation_ready:
                    if verbose:
                        print(
                            "[dispatch] Stale completed routing has an active "
                            f"post-commit continuation before refresh: {continuation_detail}"
                        )
                    return _retry_commit_only(
                        repo,
                        cfg,
                        verbose=verbose,
                        bus_dir=bus_dir,
                    )
                if verbose:
                    print(f"[dispatch] No pre-refresh post-commit continuation resume: {continuation_detail}")
            if verbose:
                print(f"[dispatch] Routing record stale: {msg}")
                if is_noncanonical_explicit:
                    print(
                        "[dispatch] Explicit noncanonical routing record is caller-owned; "
                        "refusing in-place refresh."
                    )
                elif is_inline_caller_owned:
                    print(
                        "[dispatch] Inline routing record does not match the canonical "
                        "routing file; refusing implicit rebind."
                    )
                elif is_canonical_explicit:
                    print("[dispatch] Rebinding canonical routing record via builder...")
                else:
                    print("[dispatch] Auto-refreshing via post-merge supervisor...")
            if is_noncanonical_explicit:
                return {
                    "status": "stale",
                    "decision": decision,
                    "executor": executor_name,
                    "message": (
                        f"Routing record is stale: {msg}. Explicit noncanonical routing records are "
                        "caller-owned and must be regenerated from authoritative routing instead of "
                        f"being rewritten in place: {routing_record_path}"
                    ),
                }
            if is_inline_caller_owned:
                return {
                    "status": "stale",
                    "decision": decision,
                    "executor": executor_name,
                    "message": (
                        f"Routing record is stale: {msg}. Inline routing records that do not match "
                        "the canonical routing file are caller-owned and must be regenerated from "
                        "authoritative routing instead of being rebound implicitly."
                    ),
                }
            elif is_canonical_explicit:
                refreshed, refresh_record = _refresh_canonical_routing_record_state(
                    repo,
                    record,
                    output_path=routing_record_path,
                    verbose=verbose,
                    bus_dir=bus_dir,
                )
                if not refreshed or refresh_record is None:
                    if verbose:
                        print(
                            "[dispatch] Canonical routing rebind failed; "
                            "falling back to post-merge package refresh..."
                        )
                    refreshed, refresh_record = _auto_refresh_routing(
                        repo,
                        verbose=verbose,
                        bus_dir=bus_dir,
                    )
            else:
                refreshed, refresh_record = _auto_refresh_routing(repo, verbose=verbose, bus_dir=bus_dir)
            if not refreshed or refresh_record is None:
                continuation_ready, continuation_detail = _post_commit_continuation_ready_for_record(
                    repo,
                    record,
                    bus_dir=bus_dir,
                )
                if continuation_ready:
                    if verbose:
                        print(
                            "[dispatch] Stale completed routing has an active "
                            f"post-commit continuation: {continuation_detail}"
                        )
                    return _retry_commit_only(
                        repo,
                        cfg,
                        verbose=verbose,
                        bus_dir=bus_dir,
                    )
                if verbose:
                    print(f"[dispatch] No post-commit continuation resume: {continuation_detail}")
                refresh_message = (
                    "Explicit routing record rebind failed — refresh the packet-owned routing file."
                    if is_noncanonical_explicit
                    else "Auto-refresh failed — re-run post-merge supervisor manually."
                )
                return {
                    "status": "stale",
                    "decision": decision,
                    "executor": executor_name,
                    "message": f"Routing record is stale: {msg}. {refresh_message}",
                }
            # Use the refreshed record for the rest of dispatch
            record = refresh_record
            record = _enrich_founder_ordered_tracked_packets(repo, record)
            decision = record.get("decision", "")
            # Re-check stop tokens after refresh
            if decision in STOP_TOKENS:
                request_text = record.get("request_for_agent") or record.get("request_for_claude", "")
                return {
                    "status": "stopped",
                    "decision": decision,
                    "summary": record.get("summary", ""),
                    "request_for_agent": request_text,
                    "request_for_claude": request_text,
                    "message": f"Routing stopped after refresh: {decision}. "
                               f"Requires founder/triage intervention.",
                }
            executor_name = resolve_executor(decision)
            if executor_name is None:
                return {
                    "status": "error",
                    "decision": decision,
                    "message": f"Refreshed routing decision unknown: {decision}.",
                }
            completed_stop = _completed_candidate_stop_result(
                repo,
                record,
                decision=decision,
                executor_name=executor_name,
            )
            if completed_stop is not None:
                return completed_stop
            packet_wave_conflict = _tracked_packet_wave_conflict_result(
                repo,
                record,
                decision=decision,
                executor_name=executor_name,
            )
            if packet_wave_conflict is not None:
                return packet_wave_conflict
            missing_tracker_authority = _missing_next_codex_tracker_authority_result(
                repo,
                record,
                decision=decision,
                executor_name=executor_name,
            )
            if missing_tracker_authority is not None:
                return missing_tracker_authority
            empty_tracker_update = _empty_tracker_update_hold_result(
                record,
                decision=decision,
                executor_name=executor_name,
            )
            if empty_tracker_update is not None:
                return empty_tracker_update
            if verbose:
                print(f"[dispatch] Refreshed: decision={decision}, executor={executor_name}")

    completed_stop = _completed_candidate_stop_result(
        repo,
        record,
        decision=decision,
        executor_name=executor_name,
    )
    if completed_stop is not None:
        return completed_stop
    packet_wave_conflict = _tracked_packet_wave_conflict_result(
        repo,
        record,
        decision=decision,
        executor_name=executor_name,
    )
    if packet_wave_conflict is not None:
        return packet_wave_conflict
    missing_tracker_authority = _missing_next_codex_tracker_authority_result(
        repo,
        record,
        decision=decision,
        executor_name=executor_name,
    )
    if missing_tracker_authority is not None:
        return missing_tracker_authority

    empty_tracker_update = _empty_tracker_update_hold_result(
        record,
        decision=decision,
        executor_name=executor_name,
    )
    if empty_tracker_update is not None:
        return empty_tracker_update

    if verbose:
        print(f"[dispatch] Decision: {decision} → {executor_name}")

    # Dispatch to executor
    executor_path = SCRIPT_DIR / f"{executor_name}.py"
    if not executor_path.exists():
        return {
            "status": "error",
            "decision": decision,
            "executor": executor_name,
            "message": f"Executor script not found: {executor_path}",
        }

    # Invoke executor with appropriate interface
    try:
        timeout = cfg.get("timeouts", {}).get(executor_name, DEFAULT_EXECUTOR_CONFIG["timeouts"].get(executor_name, 300))

        # Build executor-specific CLI args
        executor_args = [sys.executable, str(executor_path)]
        if executor_name == "commit_executor":
            # Only use a pre-prepared handoff for decisions that come from
            # Phase B/A (COMMIT_GO, COMMIT_GO_HOLD_PUSH).  UPDATE_TRACKER_ONLY
            # must always go through --routing-record so the commit executor
            # builds a tracker-only handoff from the live routing decision
            # instead of replaying a stale Phase B handoff file.
            handoff_path = agent_bus_path(repo, bus_dir, "executors", "phase_b_handoff.json")
            if decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
                # COMMIT_GO/COMMIT_GO_HOLD_PUSH require a pre-prepared Phase B
                # handoff.  Without one, the commit executor would synthesize a
                # handoff that points at the canonical hook receipt instead of
                # the exact per-invocation Phase B receipt — breaking the
                # authority chain.  Fail closed.
                if not handoff_path.exists():
                    return {
                        "status": "error",
                        "decision": decision,
                        "executor": executor_name,
                        "message": (
                            f"No Phase B handoff file at {handoff_path} for "
                            f"{decision}. Cannot commit without a verified "
                            f"Phase B receipt chain."
                        ),
                    }
                valid_handoff, handoff_msg = _validate_phase_b_handoff_identity(handoff_path, record)
                if not valid_handoff:
                    return {
                        "status": "error",
                        "decision": decision,
                        "executor": executor_name,
                        "message": f"Phase B handoff validation failed: {handoff_msg}",
                    }
                executor_args.extend(["--handoff", str(handoff_path)])
            else:
                # UPDATE_TRACKER_ONLY: pass routing record so commit_executor
                # can prepare a tracker-only handoff internally.
                executor_args.extend(["--routing-record", json.dumps(record)])
        elif executor_name == "phase_a_executor":
            # Phase A needs --plan-name. When a candidate already declares a
            # tracked packet, prefer that canonical packet stem so Phase A
            # reuses the tracked file instead of minting a date-slug duplicate.
            candidates = _selected_routing_candidate_dicts(record)
            plan_name = None
            for c in candidates:
                tp = c.get("tracked_packet")
                if tp and isinstance(tp, str):
                    tp_resolved = (repo / tp).resolve()
                    if ".." in Path(tp).parts:
                        return {
                            "status": "error",
                            "decision": decision,
                            "executor": executor_name,
                            "message": f"Path traversal in tracked_packet: {tp}",
                        }
                    if not tp_resolved.is_relative_to(repo.resolve()):
                        return {
                            "status": "error",
                            "decision": decision,
                            "executor": executor_name,
                            "message": f"tracked_packet escapes repo root: {tp}",
                        }
                    source_plan_name = Path(tp).stem
                    normalized_plan_name = _normalize_phase_a_retry_plan_name(
                        source_plan_name,
                    )
                    if normalized_plan_name and normalized_plan_name != source_plan_name:
                        normalized_packet = (
                            f"reports/control_plane/{normalized_plan_name}.md"
                        )
                        normalized_conflict = _phase_a_normalized_retry_packet_conflict_result(
                            repo,
                            record,
                            c,
                            source_packet=tp,
                            normalized_packet=normalized_packet,
                            decision=decision,
                            executor_name=executor_name,
                        )
                        if normalized_conflict is not None:
                            return normalized_conflict
                        c["candidate"] = normalized_plan_name
                        c["tracked_packet"] = normalized_packet
                        c["recovery_authority"] = "phase_a_plan_name_normalization"
                        c["authority_tracked_packet"] = tp
                        record["tracked_packet"] = normalized_packet
                        record["recovery_authority"] = "phase_a_plan_name_normalization"
                        record["authority_tracked_packet"] = tp
                        plan_name = normalized_plan_name
                    else:
                        plan_name = source_plan_name
                    break
                candidate_text = c.get("candidate", "")
                if candidate_text:
                    plan_name = _sanitize_plan_name(candidate_text)
                    break
            if not plan_name:
                plan_name = _sanitize_plan_name(
                    f"plan_{record.get('wave_name', 'unknown')}",
                )
            executor_args.extend(["--plan-name", plan_name])
            # Phase A must receive the dispatcher-selected record. Without this
            # override, phase_a_executor falls back to the canonical routing file
            # and can plan against a stale completed packet.
            executor_args.extend(["--routing-record", json.dumps(record)])
        elif executor_name == "phase_b_executor":
            # Phase B: prefer --plan from next_candidates tracked_packet,
            # then recovery-seeded --plan, then planless routing authority.
            executor_args.append("--dispatcher-owned-recovery")
            plan_path, plan_error = _phase_b_tracked_plan_or_error(
                repo,
                record,
                include_recovery_env=True,
            )
            if plan_error:
                return plan_error
            if plan_path:
                declared_plan_wave = _phase_b_plan_declared_wave_id(repo, plan_path)
                phase_b_wave = (
                    declared_plan_wave
                    or str(record.get("wave_name") or record.get("wave_id") or "")
                )
                if phase_b_wave:
                    record = _phase_b_routing_record_bound_to_plan_wave(
                        repo,
                        record,
                        plan_path=plan_path,
                        wave_id=phase_b_wave,
                    )
                tracker_gate = _phase_b_tracker_gate_result(
                    repo,
                    plan_path=plan_path,
                    wave_id=phase_b_wave,
                    tracked_packet=plan_path,
                )
                if tracker_gate is not None:
                    return tracker_gate
                executor_args.extend(["--plan", plan_path])
                executor_args.extend(["--routing-record", json.dumps(record)])
            else:
                # Planless mode: Phase B derives scope from routing record.
                # The routing record must have wave_name, summary, and
                # next_candidates for this to succeed (fail-closed in Phase B).
                executor_args.extend(["--routing-record", json.dumps(record)])
        elif executor_name == "dialectic_executor":
            executor_args.extend(["--routing-record", json.dumps(record)])
            executor_args.extend([
                "--max-rounds",
                str(_configured_bridge_loop_limit(cfg, "dialectic")),
            ])
        else:
            executor_args.extend(["--routing-record", json.dumps(record)])
        if executor_name in _JSON_EXECUTORS:
            executor_args.append("--json")
        if bus_dir is not None:
            executor_args.extend(["--bus-dir", str(bus_dir)])

        result = _run_executor_in_group(
            executor_args, cwd=repo, timeout=timeout,
        )
        if result.returncode != 0:
            return {
                "status": "failed",
                "decision": decision,
                "executor": executor_name,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        return _continue_successful_executor_chain(
            executor_name,
            result,
            repo_root=repo,
            config=cfg,
            record=record,
            verbose=verbose,
            bus_dir=bus_dir,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "decision": decision,
            "executor": executor_name,
            "message": f"Executor {executor_name} timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "status": "error",
            "decision": decision,
            "executor": executor_name,
            "message": str(exc),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Per-lane tmux monitor lifecycle
#
# When a wave launches on a namespaced lane bus (.agent_bus-<laneN>), the
# dispatcher auto-spawns that lane's 4-pane tmux monitor once at launch and
# auto-cleans the self-healing owner-loop + tmux session at wave-end on every
# exit path.  The default .agent_bus (MAIN) bus is never a lane and is left
# untouched.  tools/observability/pipeline_monitor.sh is INVOKED and
# process-matched here, never modified.
# ─────────────────────────────────────────────────────────────────────────────

_LANE_BUS_PREFIX = ".agent_bus-"
_OWNER_LOOP_TOKEN = "__owner-loop"
# Bounded liveness wait between SIGTERM and SIGKILL for a surviving owner-loop.
_OWNER_TERM_WAIT_SECONDS = 2.0
_OWNER_TERM_POLL_SECONDS = 0.1
# Bounded wait for an in-flight `start --detach` spawn to finish before cleanup.
_SPAWN_REAP_TIMEOUT_SECONDS = 10.0


def _lane_name_from_bus_dir(bus_dir: str | Path | None) -> str | None:
    """Return the lane suffix for a lane bus, or None for the MAIN/default bus.

    ``.agent_bus-<laneN>`` -> ``"laneN"``.  The default ``.agent_bus`` (or any
    non-namespaced value) is MAIN, not a lane, and yields ``None`` so no monitor
    is ever spawned or cleaned for it.
    """
    raw = str(bus_dir or "").strip().rstrip("/")
    if not raw:
        return None
    # Only the bus directory name matters; callers pass repo-relative buses like
    # ".agent_bus-lane1".  Taking the name keeps an absolute bus path from ever
    # smuggling the MAIN bus past the lane check.
    name = Path(raw).name
    if name == ".agent_bus" or not name.startswith(_LANE_BUS_PREFIX):
        return None
    suffix = name[len(_LANE_BUS_PREFIX):]
    return suffix or None


def _lane_monitor_script(repo_root: Path) -> Path:
    """Resolve the pipeline_monitor.sh path to invoke for a lane monitor."""
    primary = repo_root / "mu" / "tools" / "observability" / "pipeline_monitor.sh"
    if primary.exists():
        return primary
    return repo_root / "tools" / "observability" / "pipeline_monitor.sh"


def _resolve_lane_tmux_session(
    repo_root: Path | None,
    bus_dir: str | Path | None,
    lane: str,
) -> str:
    """Resolve the configured tmux session name for a lane bus.

    Matches the lane config by bus_dir using the SAME loader the monitor reads
    (``load_monitor_lanes`` / ``pipeline_monitor.lanes.*.tmux_session``).  Falls
    back to ``rcx-pipeline-<laneN>`` only when repo_root is unknown, the bus has
    no configured identity, or the config cannot be read.  NEVER returns the bare
    ``rcx-pipeline`` MAIN session: a configured value that collapses to it is
    treated as unconfigured so the namespaced fallback wins (hard-safety).
    """
    fallback = f"{DEFAULT_TMUX_SESSION}-{lane}"
    if repo_root is None:
        return fallback
    bus_name = Path(str(bus_dir or "").strip().rstrip("/")).name
    try:
        lanes = load_monitor_lanes(Path(repo_root))
    except Exception:
        # NEVER raise on a config error — a real lane must stay cleanable.
        return fallback
    for config in lanes.values():
        if str(config.get("bus_dir") or "") != bus_name:
            continue
        session = str(config.get("tmux_session") or "").strip()
        if session and session != DEFAULT_TMUX_SESSION:
            return session
        return fallback
    return fallback


def _tmux_has_session(session: str) -> bool:
    """Return True iff a tmux session with the EXACT name exists.

    Uses the ``=`` exact-match target form so a lane probe never matches a
    different session by prefix (``rcx-pipeline`` must not match
    ``rcx-pipeline-lane1``).
    """
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", f"={session}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return False
    return result.returncode == 0


def _tmux_kill_session(session: str) -> None:
    """Best-effort kill of the EXACT tmux session (never prefix-capable)."""
    try:
        subprocess.run(
            ["tmux", "kill-session", "-t", f"={session}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        pass


def _ps_command_lines() -> list[tuple[int, str]]:
    """Return (pid, command-line) for every visible process, best-effort."""
    try:
        result = subprocess.run(
            ["ps", "-A", "-ww", "-o", "pid=,command="],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return []
    processes: list[tuple[int, str]] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        command = command.strip()
        if command:
            processes.append((pid, command))
    return processes


def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _tokens_have_adjacent_pair(tokens: list[str], flag: str, value: str) -> bool:
    """True iff ``flag`` appears immediately followed by exactly ``value``.

    Whole-token matching: ``--lane lane1`` must NOT be considered present in
    ``--lane lane10`` (a substring scan would false-match the prefix).
    """
    for index, token in enumerate(tokens):
        if token == flag and index + 1 < len(tokens) and tokens[index + 1] == value:
            return True
    return False


def _lane_owner_loop_command_kind(
    command: str,
    *,
    repo_root: Path,
    bus_dir: str,
    lane: str,
) -> str:
    """Classify ``command`` as THIS repo+lane's monitor owner-loop.

    Requires ALL of (whole-token / identity-bound):

      * the ``__owner-loop`` token,
      * ``--lane <laneN>`` as adjacent whole tokens (so ``--lane lane1`` never
        matches ``--lane lane10``),
      * ``--bus-dir <bus_dir>`` as adjacent whole tokens,
      * a ``pipeline_monitor.sh`` script-path token consistent with THIS repo.

    Returns ``"absolute"`` when the command carries an absolute
    ``pipeline_monitor.sh`` path under repo_root (definitively ours — no further
    check needed), ``"relative"`` when it carries only a relative monitor path
    (a candidate whose repo binding must be confirmed by the live process CWD),
    or ``""`` when it is not this repo+lane's owner-loop.

    This mirrors pipeline_monitor.sh ``owner_process_matches_root``: the monitor
    spawns its owner-loop via ``bash "$0"``, so ``$0`` is whatever path the
    monitor was launched with.  An absolute path under ANOTHER repo is a
    definitive cross-repo signal and never matches (two repos can each run a
    laneN owner-loop; the other repo's must NOT be killed).  A relative path
    carries no repo in the command string, so it stays a candidate and the
    repo binding is confirmed later against the process CWD.  The MAIN
    owner-loop carries no ``--lane`` token and therefore never matches
    (hard-safety).
    """
    tokens = _command_tokens(command)
    if _OWNER_LOOP_TOKEN not in tokens:
        return ""
    if not _tokens_have_adjacent_pair(tokens, "--lane", lane):
        return ""
    if not _tokens_have_adjacent_pair(tokens, "--bus-dir", bus_dir):
        return ""
    repo_prefix = str(repo_root).rstrip("/") + os.sep
    saw_relative = False
    saw_absolute_foreign = False
    for token in tokens:
        if not token.endswith("pipeline_monitor.sh"):
            continue
        if os.path.isabs(token):
            if token.startswith(repo_prefix):
                return "absolute"  # absolute path under THIS repo — ours
            saw_absolute_foreign = True  # absolute path to ANOTHER repo
        else:
            saw_relative = True
    # No absolute-under-repo match.  A relative monitor path is a candidate only
    # when there is no competing absolute path to a foreign repo.
    if saw_relative and not saw_absolute_foreign:
        return "relative"
    return ""


def _command_matches_lane_owner_loop(
    command: str,
    *,
    repo_root: Path,
    bus_dir: str,
    lane: str,
) -> bool:
    """Return True iff ``command`` is a candidate owner-loop for THIS repo+lane.

    Thin bool view of :func:`_lane_owner_loop_command_kind`.  A relative-path
    owner-loop (``bash "$0"`` with a relative ``$0``) is a candidate here; its
    repo binding is confirmed against the live process CWD in
    :func:`_lane_owner_loop_pids`.  An absolute path under another repo is never
    a candidate (cross-repo hard-safety).
    """
    return bool(
        _lane_owner_loop_command_kind(
            command, repo_root=repo_root, bus_dir=bus_dir, lane=lane
        )
    )


def _pid_cwd(pid: int) -> Path | None:
    """Best-effort resolved working directory of ``pid`` (``/proc`` then
    ``lsof``), or None when it cannot be determined.

    Mirrors pipeline_monitor.sh ``process_cwd`` / commit_executor ``_process_cwd``
    so the dispatcher binds a relative-path owner-loop to this repo the same way
    the monitor does.
    """
    proc_cwd = Path("/proc") / str(pid) / "cwd"
    if proc_cwd.exists():
        try:
            return proc_cwd.resolve(strict=True)
        except (OSError, RuntimeError):
            return None
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 and not result.stdout:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n") and len(line) > 1:
            try:
                return Path(line[1:]).resolve(strict=False)
            except (OSError, RuntimeError):
                return None
    return None


def _cwd_under_repo(cwd: Path | None, repo_root: Path) -> bool:
    """True iff ``cwd`` is repo_root or a path nested under it."""
    if cwd is None:
        return False
    try:
        root = repo_root.resolve(strict=False)
    except (OSError, RuntimeError):
        root = repo_root
    if cwd == root:
        return True
    try:
        cwd.relative_to(root)
        return True
    except ValueError:
        return False


def _lane_owner_loop_pids(
    processes: list[tuple[int, str]],
    *,
    repo_root: Path,
    bus_dir: str,
    lane: str,
) -> list[int]:
    """Select owner-loop pids bound to THIS repo_root + bus_dir + lane.

    An owner-loop whose command carries an absolute monitor path under repo_root
    is selected directly.  One launched via a RELATIVE monitor path (``bash
    "$0"`` with a relative ``$0`` — e.g. a monitor started from repo-relative
    ``tools/observability/pipeline_monitor.sh``) is selected only when the live
    process CWD confirms the repo binding; a cross-repo relative owner-loop is
    left alone (hard-safety).  When the CWD cannot be read the owner-loop is NOT
    selected: never killing a possibly-foreign process outranks best-effort
    zombie reaping, matching pipeline_monitor.sh ``owner_process_matches_root``.
    """
    pids: list[int] = []
    for pid, command in processes:
        kind = _lane_owner_loop_command_kind(
            command, repo_root=repo_root, bus_dir=bus_dir, lane=lane
        )
        if kind == "absolute":
            pids.append(pid)
        elif kind == "relative" and _cwd_under_repo(_pid_cwd(pid), repo_root):
            pids.append(pid)
    return pids


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _signal_pid(pid: int, sig: int) -> None:
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def _terminate_owner_loops(pids: list[int]) -> None:
    """SIGTERM -> bounded liveness wait -> SIGKILL the survivors.

    The owner-loop's TERM trap runs cleanup but does NOT exit, so SIGTERM alone
    leaves it alive; the SIGKILL fallback is required to actually reap it.
    """
    if not pids:
        return
    for pid in pids:
        _signal_pid(pid, signal.SIGTERM)
    survivors = list(pids)
    waited = 0.0
    while waited < _OWNER_TERM_WAIT_SECONDS:
        survivors = [pid for pid in survivors if _pid_alive(pid)]
        if not survivors:
            return
        time.sleep(_OWNER_TERM_POLL_SECONDS)
        waited += _OWNER_TERM_POLL_SECONDS
    for pid in (pid for pid in survivors if _pid_alive(pid)):
        _signal_pid(pid, signal.SIGKILL)


class _LaneMonitor:
    """Auto-spawn + auto-clean lifecycle for a wave's per-lane tmux monitor.

    A no-op for the MAIN/default bus (``.agent_bus``): only namespaced lane
    buses (``.agent_bus-<laneN>``) get a monitor.  Spawn is idempotent (skipped
    when the exact configured session already exists) and best-effort (a spawn
    error is logged, never raised).  Cleanup runs once on every wave-end exit
    path and never raises.
    """

    def __init__(
        self,
        repo_root: Path | None,
        bus_dir: str | Path | None,
        *,
        verbose: bool = False,
    ) -> None:
        self.repo_root = Path(repo_root) if repo_root is not None else None
        # Canonicalize to the bare bus NAME (strip whitespace + any trailing
        # slash and drop directory components) BEFORE it drives the monitor
        # lifecycle.  resolve_agent_bus_dir() accepts a trailing slash (e.g.
        # ".agent_bus-lane1/") and lets the dispatcher proceed, but the raw value
        # would break both ends of the lifecycle: pipeline_monitor.sh rejects any
        # "/" in --bus-dir (spawn would fail) and the owner-loop cleanup matches
        # the --bus-dir token WHOLE (a trailing slash would never match the real
        # owner-loop, stranding it).  Mirrors the same .name reduction already
        # used by _lane_name_from_bus_dir / _resolve_lane_tmux_session.
        self.bus_dir = Path(str(bus_dir).strip().rstrip("/")).name if bus_dir else ""
        self.verbose = verbose
        self.lane = _lane_name_from_bus_dir(self.bus_dir)
        self.session = (
            _resolve_lane_tmux_session(self.repo_root, self.bus_dir, self.lane)
            if self.lane
            else ""
        )
        self._spawn_proc: subprocess.Popen | None = None
        self._cleaned = False

    @property
    def is_lane(self) -> bool:
        """True only for a namespaced lane bus with a known repo identity."""
        return bool(self.lane) and self.repo_root is not None

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"[dispatch] {message}")

    def spawn(self) -> None:
        """Spawn the lane monitor once, idempotently, best-effort."""
        if not self.is_lane:
            return
        try:
            if _tmux_has_session(self.session):
                self._log(
                    f"Lane monitor session already running: {self.session} "
                    f"(lane={self.lane}); skipping spawn"
                )
                return
            cmd = [
                str(_lane_monitor_script(self.repo_root)),
                "--bus-dir",
                self.bus_dir,
                "--lane",
                self.lane,
                "start",
                "--detach",
            ]
            self._spawn_proc = subprocess.Popen(
                cmd,
                cwd=str(self.repo_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            self._log(
                f"Spawned lane monitor: lane={self.lane} bus={self.bus_dir} "
                f"session={self.session}"
            )
        except Exception as exc:  # best-effort: never block/fail the launch
            self._log(f"Lane monitor spawn failed (continuing): {exc}")

    def _reap_in_flight_spawn(self) -> None:
        """Close the async-start race so an in-flight ``start --detach`` spawn
        cannot create the owner-loop/session AFTER cleanup has run."""
        proc = self._spawn_proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                try:
                    proc.wait(timeout=_SPAWN_REAP_TIMEOUT_SECONDS)
                except subprocess.TimeoutExpired:
                    try:
                        terminate_process_tree(proc.pid, cwd=self.repo_root)
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=1)
                    except Exception:
                        pass
        except Exception:
            pass
        finally:
            self._spawn_proc = None

    def cleanup(self) -> None:
        """Idempotently tear down this lane's owner-loop(s) + tmux session."""
        if not self.is_lane or self._cleaned:
            return
        self._cleaned = True
        try:
            # 1) Close the async-start race before killing anything, so a
            #    session/owner-loop created by an in-flight spawn is still caught.
            self._reap_in_flight_spawn()
            # 2) Kill the self-healing owner-loop(s) FIRST so they cannot
            #    resurrect the session after it is killed.
            pids = _lane_owner_loop_pids(
                _ps_command_lines(),
                repo_root=self.repo_root,
                bus_dir=self.bus_dir,
                lane=self.lane,
            )
            _terminate_owner_loops(pids)
            # 3) Kill the EXACT tmux session (best-effort).  Hard-safety: never
            #    target the bare MAIN session even if resolution misbehaved.
            if self.session and self.session != DEFAULT_TMUX_SESSION:
                _tmux_kill_session(self.session)
            self._log(
                f"Cleaned lane monitor: lane={self.lane} session={self.session} "
                f"owner_loops={pids}"
            )
        except Exception as exc:  # cleanup must never raise
            self._log(f"Lane monitor cleanup error (ignored): {exc}")


def _install_wave_end_signal_cleanup(monitor: "_LaneMonitor") -> dict | None:
    """Arm a process-level SIGTERM/SIGINT/SIGHUP handler that runs the lane
    monitor cleanup even when the signal lands OUTSIDE an executor subprocess
    window (routing/recovery/post-merge gaps).

    Python's default SIGTERM disposition terminates the process WITHOUT running
    ``finally``, so a signal in those gaps would bypass ``monitor.cleanup()`` and
    strand the self-healing owner-loop + tmux session.  The only other signal
    handler — ``_run_executor_in_group._cleanup_for_signal`` — is scoped to the
    executor subprocess and restores the prior disposition on exit; the two
    compose because that helper saves and restores whatever handler is installed
    here.  Returns a token (saved prior dispositions) for
    :func:`_remove_wave_end_signal_cleanup`, or None when nothing was armed (the
    MAIN/default bus, or not running on the main thread).
    """
    if not monitor.is_lane:
        return None
    signums = [signal.SIGINT, signal.SIGTERM]
    hup = getattr(signal, "SIGHUP", None)
    if hup is not None:
        signums.append(hup)
    try:
        previous = {sig: signal.getsignal(sig) for sig in signums}
    except (OSError, ValueError):
        return None

    def _handler(signum: int, _frame: Any) -> None:
        # Restore prior dispositions first so a second signal during cleanup
        # follows normal semantics, then clean up once and re-raise so the
        # wave-end exit code mirrors the in-window _cleanup_for_signal path.
        for sig, prev in previous.items():
            try:
                signal.signal(sig, prev)
            except (OSError, ValueError):
                pass
        try:
            monitor.cleanup()
        finally:
            if signum == signal.SIGINT:
                raise KeyboardInterrupt()
            raise SystemExit(128 + signum)

    installed: dict = {}
    for sig in signums:
        try:
            signal.signal(sig, _handler)
            installed[sig] = previous[sig]
        except (OSError, ValueError):
            # Not the main thread / unsupported — best-effort; the outer finally
            # still covers normal completion and exception exits.
            pass
    return installed or None


def _remove_wave_end_signal_cleanup(token: dict | None) -> None:
    """Restore the dispositions saved by :func:`_install_wave_end_signal_cleanup`."""
    if not token:
        return
    for sig, prev in token.items():
        try:
            signal.signal(sig, prev)
        except (OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in SURFACE_COMMANDS:
        parser = build_surface_parser()
        args = parser.parse_args(argv)
        try:
            repo_root = resolve_repo_root_for_dispatch(verbose=getattr(args, "verbose", False))
        except DispatchError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        try:
            if args.surface == "phase-a":
                repo_root = prepare_phase_a_teammate_lane(args, repo_root)
            if args.surface in {"phase-a", "phase-b", "commit"}:
                config = load_config()
                return run_recoverable_surface_command(
                    args,
                    repo_root=repo_root,
                    config=config,
                )
            cmd = build_surface_command(args)
            config = load_config()
            timeout = _surface_forward_timeout(args, config)
        except (ControlSurfaceError, DispatchError) as exc:
            print(f"[executor-dispatch] Error: {exc}", file=sys.stderr)
            return 1
        return run_surface_command(cmd, repo_root=repo_root, timeout=timeout)

    parser = argparse.ArgumentParser(
        description="Executor dispatcher: reads routing record and invokes executor",
    )
    parser.add_argument(
        "--routing-record",
        type=Path,
        help=(
            "Path to routing record JSON "
            "(default: active bus meta/post_merge_routing.json)"
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to executor config JSON",
    )
    parser.add_argument(
        "--skip-freshness",
        action="store_true",
        help="Skip routing record freshness check",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="After merge, run post-merge supervisor and loop (full pipeline cycle)",
    )
    parser.add_argument(
        "--max-waves",
        type=int,
        default=3,
        help="Maximum waves per --loop invocation (default: 3)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Retry failed executor up to N times before giving up (default: 0)",
    )
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("[error] Not in a git repository", file=sys.stderr)
        return 1
    try:
        resolve_agent_bus_dir(repo_root, args.bus_dir)
    except ExecutorCommonError as exc:
        print(f"[error] Invalid --bus-dir: {exc}", file=sys.stderr)
        return 1

    # Enforce linked-worktree execution: the dispatcher must NOT run in the
    # primary worktree when it has dirty files.  Dirty files from interactive
    # work cause scope drift, stale state SHA, and supervisor rejections.
    # Create a fresh linked worktree from dev instead.
    # Skip in test environments (RCX_SKIP_WORKTREE_CHECK=1).
    skip_worktree_check = (
        os.environ.get("RCX_SKIP_WORKTREE_CHECK") == "1"
        or args.routing_record is not None  # explicit routing = caller owns scope
    )
    if not skip_worktree_check and not getattr(args, "surface", None):
        try:
            git_dir = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip()
            git_common = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip()
            is_primary = (Path(git_dir).resolve() == Path(git_common).resolve())
            if is_primary:
                dirty = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=repo_root, capture_output=True, text=True, check=True,
                ).stdout.strip()
                if dirty:
                    dirty_count = len(dirty.splitlines())
                    print(
                        f"[error] Dispatcher refused: primary worktree has {dirty_count} dirty file(s).\n"
                        f"  Pipeline must run in a clean linked worktree to avoid scope drift.\n"
                        f"\n"
                        f"  Create one with:\n"
                        f"    WT=\"/private/tmp/workingrcx_$(date +%s)\"\n"
                        f"    git worktree add \"$WT\" origin/dev --detach\n"
                        f"    cd \"$WT\" && git checkout -b jabramsja/<wave-name>\n"
                        f"    # Then run dispatcher from $WT\n",
                        file=sys.stderr,
                    )
                    return 1
        except subprocess.CalledProcessError:
            pass  # Can't detect worktree type — proceed anyway

    config = load_config(args.config) if args.config else load_config()
    wave_count = 0

    monitor = _LaneMonitor(repo_root, args.bus_dir, verbose=args.verbose)
    monitor.spawn()
    # Arm a process-level signal handler so a SIGTERM landing in a
    # routing/recovery/post-merge gap (outside any executor subprocess window)
    # still runs the wave-end cleanup instead of bypassing the finally below.
    _signal_cleanup_token = _install_wave_end_signal_cleanup(monitor)
    try:
        while True:
            wave_count += 1
            if args.verbose:
                print(f"\n[dispatch] === Wave {wave_count}/{args.max_waves if args.loop else 1} ===")

            # Load routing record
            if args.routing_record:
                try:
                    record = json.loads(args.routing_record.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError) as exc:
                    print(f"[error] Cannot load routing record: {exc}", file=sys.stderr)
                    return 1
            else:
                try:
                    record = load_routing_record(repo_root, bus_dir=args.bus_dir)
                except DispatchError:
                    # No routing record — try to create one via post-merge supervisor
                    if args.verbose:
                        print("[dispatch] No routing record — running post-merge supervisor...")
                    refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
                    if not refreshed or refresh_record is None:
                        print("[error] No routing record and auto-refresh failed", file=sys.stderr)
                        return 1
                    record = refresh_record

            # Dispatch with retries (while-based so recovery can grant extra attempts)
            max_attempts = 1 + max(0, args.retries)
            result = None
            attempt = 1
            _recovery_original_timeouts = None
            while attempt <= max_attempts:
                # If previous attempt was a chained commit failure (Phase A/B
                # succeeded but commit failed), retry only the commit executor
                # instead of re-running the full Phase A→B→commit chain.
                if result is not None and _is_chained_commit_failure(result):
                    result = _retry_commit_only(
                        repo_root, config,
                        verbose=args.verbose,
                        bus_dir=args.bus_dir,
                    )
                else:
                    result = dispatch(
                        record,
                        config=config,
                        repo_root=repo_root,
                        routing_record_path=args.routing_record if args.routing_record else None,
                        skip_freshness=args.skip_freshness,
                        verbose=args.verbose,
                        bus_dir=args.bus_dir,
                    )
                embedded_recovery = result.get("recovery")
                if isinstance(embedded_recovery, dict) and embedded_recovery.get("recovered"):
                    if args.verbose:
                        print(
                            "[dispatch] Phase B recovered in-process — retrying "
                            "before commit chain"
                        )
                    _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose, bus_dir=args.bus_dir)
                    retry_record = _recovered_retry_record(result, current_record=record)
                    if retry_record is not None:
                        record = retry_record
                    elif not _is_chained_commit_failure(result):
                        if args.routing_record:
                            explicit_record = _reload_explicit_routing_record(
                                args.routing_record,
                                verbose=args.verbose,
                            )
                            if explicit_record is not None:
                                record = explicit_record
                        else:
                            refreshed, refresh_record = _auto_refresh_routing(
                                repo_root, verbose=args.verbose, bus_dir=args.bus_dir
                            )
                            if refreshed and refresh_record is not None:
                                record = refresh_record
                    continue
                # Non-retryable dispatch statuses — break immediately
                if result.get("status") in _NON_RETRYABLE_DISPATCH_STATUSES:
                    break
                # Terminal executor outcomes (founder-required, max bridge rounds
                # exhausted) — retrying would re-produce the same result
                if result.get("status") == "failed" and _is_terminal_executor_outcome(result):
                    if args.verbose:
                        print("[dispatch] Executor returned terminal outcome — not retrying")
                    _emit_executor_hard_fail_event(
                        repo_root,
                        result,
                        str(record.get("wave_name") or record.get("wave_id") or ""),
                        record,
                        bus_dir=args.bus_dir,
                    )
                    break
                # Recovery gate: classify failure and attempt Tier 1/2 auto-fix
                # "timeout" is included so PROCESS_TIMEOUT reaches Tier 2 recovery
                # "bot_findings_pending" is deliberately excluded — classify_failure
                # returns UNCLASSIFIED (tier 4) for it, which hits the tier>=3
                # fail-closed break.  Letting it fall through preserves normal
                # --retries behavior so the executor can re-poll bot review state.
                if result.get("status") in ("failed", "timeout"):
                    _wave_id = normalize_wave_id(
                        record.get("wave_name") or record.get("wave_id", ""))
                    recovery = attempt_recovery(repo_root, result, _wave_id, bus_dir=args.bus_dir)
                    result["recovery"] = recovery
                    if args.verbose:
                        tier = recovery.get('tier')
                        action = recovery.get('action', '')
                        print(f"[dispatch] Recovery: class={recovery.get('failure_class')} "
                              f"tier={tier} recovered={recovery.get('recovered')}")
                        if recovery.get("recovered") and tier == 2:
                            print(f"[dispatch] Tier 2 recovery: {action} "
                                  f"— retrying with adjusted parameters")
                    if recovery.get("recovered"):
                        # Apply Tier 2 env var overrides to config + disk before retry.
                        # Keep the first in-memory baseline so sequential
                        # recoveries cannot overwrite the true pre-recovery
                        # config; merge disk metadata only when a later override
                        # actually touches executor_config.json.
                        new_orig = _apply_recovery_overrides(
                            config, repo_root=repo_root, verbose=args.verbose)
                        _recovery_original_timeouts = _merge_recovery_original_config(
                            _recovery_original_timeouts,
                            new_orig,
                        )
                        # Recovery succeeded — grant one extra attempt (don't increment counter)
                        _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose, bus_dir=args.bus_dir)
                        retry_record = _recovered_retry_record(result, current_record=record)
                        if retry_record is not None:
                            record = retry_record
                        elif not _is_chained_commit_failure(result):
                            if args.routing_record:
                                explicit_record = _reload_explicit_routing_record(
                                    args.routing_record,
                                    verbose=args.verbose,
                                )
                                if explicit_record is not None:
                                    record = explicit_record
                            else:
                                refreshed, refresh_record = _auto_refresh_routing(
                                    repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
                                if refreshed and refresh_record is not None:
                                    record = refresh_record
                        continue  # retry dispatch without counting against budget
                    elif recovery.get("exhausted"):
                        if args.verbose:
                            print("[dispatch] Recovery exhausted — not retrying")
                        _emit_executor_hard_fail_event(repo_root, result, _wave_id, record, bus_dir=args.bus_dir)
                        break
                    else:
                        # Tier 3/4 non-recovery: fail closed instead of falling
                        # through to the normal retry loop (Bridge R6 Finding 2).
                        _rec_tier = recovery.get("tier", 0)
                        if _rec_tier >= 3:
                            if args.verbose:
                                print(f"[dispatch] Tier {_rec_tier} recovery not "
                                      f"available — failing closed")
                            _emit_executor_hard_fail_event(repo_root, result, _wave_id, record, bus_dir=args.bus_dir)
                            break
                if attempt >= max_attempts:
                    if result.get("status") in ("failed", "timeout"):
                        _emit_executor_hard_fail_event(
                            repo_root,
                            result,
                            str(record.get("wave_name") or record.get("wave_id") or ""),
                            record,
                            bus_dir=args.bus_dir,
                        )
                    break
                if args.verbose:
                    print(f"[dispatch] Attempt {attempt}/{max_attempts} failed — retrying...")
                # Clear Phase B persisted state before retry to prevent stale
                # resume from skipping required implementer re-entry after a
                # bridge-fix cycle failure.
                _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose, bus_dir=args.bus_dir)
                # Only refresh routing if no explicit --routing-record was provided
                # and this was NOT a chained commit retry (routing is irrelevant
                # when retrying only the commit step).
                # Do NOT unlink the existing routing record before refresh — if
                # refresh fails, the canonical record would be permanently lost.
                # The supervisor overwrites the file in place on success.
                if not _is_chained_commit_failure(result):
                    if args.routing_record:
                        explicit_record = _reload_explicit_routing_record(
                            args.routing_record,
                            verbose=args.verbose,
                        )
                        if explicit_record is not None:
                            record = explicit_record
                    else:
                        refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
                        if refreshed and refresh_record is not None:
                            record = refresh_record
                attempt += 1

            # Restore in-memory config after recovery overrides. Disk restore is
            # metadata-gated; normal recovery keeps executor_config.json read-only.
            if _recovery_original_timeouts is not None:
                _restore_config_on_disk(
                    repo_root, _recovery_original_timeouts,
                    verbose=args.verbose)
                config["timeouts"] = _recovery_original_section(
                    _recovery_original_timeouts, "timeouts"
                )
                config["bridge_turn_timeouts"] = _recovery_original_section(
                    _recovery_original_timeouts, "bridge_turn_timeouts"
                )
            # Clean up original-baseline env vars set by fix_process_timeout /
            # fix_implementer_stale to prevent leakage to --loop waves.
            for _env_key in list(os.environ):
                if _env_key.startswith((
                    "RCX_RECOVERY_ORIGINAL_TIMEOUT_",
                    "RCX_RECOVERY_ORIGINAL_BRIDGE_TURN_TIMEOUT_",
                    PHASE_B_RECOVERY_PLAN_ENV,
                    PHASE_B_RECOVERY_PLAN_WAVE_ENV,
                )):
                    os.environ.pop(_env_key, None)
            _clear_recovery_override_env()

            if result.get("status") in ("success", "held"):
                _wave_id = normalize_wave_id(
                    record.get("wave_name") or record.get("wave_id", "")
                )
                clear_stale_recovery_status_on_success(
                    repo_root,
                    wave_id=_wave_id,
                    success_target=result.get("executor") or result.get("step", ""),
                    bus_dir=args.bus_dir,
                )

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                status = result.get("status", "unknown")
                decision = result.get("decision", "unknown")
                executor = result.get("executor", "none")
                message = result.get("message", result.get("summary", ""))
                print(f"[dispatch] Status: {status}")
                print(f"[dispatch] Decision: {decision}")
                if executor != "none":
                    print(f"[dispatch] Executor: {executor}")
                if message:
                    print(f"[dispatch] {message}")
                if result.get("stdout"):
                    print(result["stdout"])
                if result.get("stderr"):
                    print(result["stderr"], file=sys.stderr)

            # If not looping, or if the wave failed/stopped, exit
            if not args.loop:
                break
            if result.get("status") != "success":
                if args.verbose:
                    print(f"[dispatch] Wave {wave_count} did not succeed ({result.get('status')}), stopping loop")
                break
            if wave_count >= args.max_waves:
                if args.verbose:
                    print(f"[dispatch] Max waves ({args.max_waves}) reached, stopping loop")
                break

            # Post-merge: refresh routing for next wave
            if args.verbose:
                print("[dispatch] Wave succeeded — running post-merge supervisor for next wave...")
            package_path = agent_bus_path(repo_root, args.bus_dir, "meta", POST_MERGE_PACKAGE_NAME)
            if not package_path.exists():
                if args.verbose:
                    print("[dispatch] No post-merge package — cannot loop to next wave")
                break
            refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
            if not refreshed or refresh_record is None:
                if args.verbose:
                    print("[dispatch] Post-merge supervisor failed — stopping loop")
                break
            # Clear the explicit routing record arg so next iteration loads fresh
            args.routing_record = None

        return 0 if result.get("status") in ("success", "held", "stopped", "not_implemented") else 1
    finally:
        _remove_wave_end_signal_cleanup(_signal_cleanup_token)
        monitor.cleanup()


if __name__ == "__main__":
    sys.exit(main())
