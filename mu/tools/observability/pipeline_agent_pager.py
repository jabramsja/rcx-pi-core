#!/usr/bin/env python3
"""Shared repo-local pipeline transition pager.

This module owns deterministic event identity, append-only event logging,
per-target delivery state, and bounded adapter dispatch for Codex / Claude.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import parse as urllib_parse

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import (
        DEFAULT_EXECUTOR_CONFIG,
        agent_bus_path,
        agent_bus_relpath,
        load_executor_config,
        resolve_agent_bus_dir,
    )
except ImportError:
    import importlib.util as _ilu

    _common_path = SCRIPT_DIR.parent / "executors" / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    DEFAULT_EXECUTOR_CONFIG = _mod.DEFAULT_EXECUTOR_CONFIG
    agent_bus_path = _mod.agent_bus_path
    agent_bus_relpath = _mod.agent_bus_relpath
    load_executor_config = _mod.load_executor_config
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir

OBSERVABILITY_DIR = agent_bus_relpath(None, "observability")
EVENT_LOG_PATH = OBSERVABILITY_DIR / "pipeline_agent_events.jsonl"
DELIVERY_LOG_PATH = OBSERVABILITY_DIR / "pipeline_agent_delivery_receipts.jsonl"
# Distinct, append-only log of fail-closed skip receipts. A skip is NEITHER a
# delivery (it is never written here as a delivery receipt) NOR a retryable
# error; this log makes the terminal skip durable so it survives a state rebuild
# (mirror of how delivery receipts rebuild ``delivered_targets``).
SKIP_LOG_PATH = OBSERVABILITY_DIR / "pipeline_agent_skip_receipts.jsonl"
STATE_PATH = OBSERVABILITY_DIR / "pipeline_agent_pager_state.json"
LOCK_PATH = OBSERVABILITY_DIR / "pipeline_agent_pager.lock"
ORCHESTRATOR_MODE_PATH = OBSERVABILITY_DIR / "orchestrator_mode.json"
AUTOPING_STATE_GLOB = "rcx_autoping_*.json"
PAUSED_AUTOPING_STATUSES = frozenset({
    "context_exhausted",
    "context_exhausted_paused",
})
# Single source of truth for the orchestrator-session-id file path.
# The pager is read-only here; the writer lives in
# ``.claude/hooks/session-start.sh``. When the file is absent or stale the
# pager dispatches plain ``claude -p`` rather than ``claude --resume``,
# keeping dispatch deterministic even while other Claude subprocesses run
# concurrently in this repo.
ORCHESTRATOR_SESSION_ID_PATH = OBSERVABILITY_DIR / "orchestrator_session_id"
# Single source of truth for the DEDICATED claude-monitor-session-id file path.
# This is a SIBLING of ``orchestrator_session_id`` but a DISTINCT file holding
# the session id of a dedicated Claude monitor conversation -- never the live
# orchestrator session. The pager is read-only here; the writer (the monitor's
# own session-start, mirror of ``.claude/hooks/session-start.sh``) is out of
# scope for this enabler wave. The claude pager leg resolves its ``--resume``
# target ONLY from this file and never falls back to ``orchestrator_session_id``,
# so ``route=both`` can never resume the live orchestrator conversation. When
# this file is absent/malformed, or its id equals the live orchestrator session
# id, the claude leg issues no ``claude --resume``; it falls back to a DIRECT
# ``claude -p`` page (a fresh subprocess that never resumes the live orchestrator).
CLAUDE_MONITOR_SESSION_ID_PATH = OBSERVABILITY_DIR / "claude_monitor_session_id"
# Distinct skip markers for the fail-closed claude leg. A skip carries one of
# these reasons instead of an ``error`` (a transient error stays pending for
# retry; a skip is terminal and leaves ``pending_targets`` without being marked
# delivered). Codex never emits these markers.
CLAUDE_SKIP_REASON_MONITOR_UNSET = "claude_monitor_session_id_unset_or_malformed"
CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE = "claude_monitor_session_id_equals_live_orchestrator"
STATE_VERSION = 1
NOTIFY_ONLY_TARGET = "notify-only"
ALLOWED_EVENT_TYPES = frozenset({
    "phase_a_entered",
    "phase_a_reviewer_started",
    "phase_a_reviewer_completed",
    "phase_a_implementer_started",
    "phase_a_implementer_completed",
    "phase_a_go",
    "phase_a_no_go",
    "phase_a_question",
    "phase_b_implementer_started",
    "phase_b_implementer_completed",
    "phase_b_reviewer_started",
    "phase_b_bridge_completed",
    "phase_b_final_pytest_started",
    "phase_b_final_pytest_passed",
    "phase_b_final_verdict",
    "pre_commit_supervisor_started",
    "pre_commit_supervisor_completed",
    "commit_started",
    "recovery_started",
    "recovery_state_changed",
    "recovery_escalated",
    "recovery_returned",
    "recovery_succeeded",
    "recovery_failed",
    "pipeline_hard_fail",
    "executor_hard_fail",
    "commit_ready",
    "commit_succeeded",
    "commit_failed",
    "commit_held",
})
ALLOWED_ROUTES = frozenset({"codex", "claude", "both", NOTIFY_ONLY_TARGET})
PAGER_ROUTE_OVERRIDE_ENV = "RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE"

_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.Lock] = {}
_ACTIVE_BUS_DIR: ContextVar[Path | None] = ContextVar("pipeline_agent_pager_bus_dir", default=None)


class PipelineAgentPagerError(RuntimeError):
    """Raised when pager event/state handling fails."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active_bus_dir(bus_dir: str | Path | None = None) -> str | Path | None:
    return bus_dir if bus_dir is not None else _ACTIVE_BUS_DIR.get()


def _observability_path(repo_root: Path, *parts: str, bus_dir: str | Path | None = None) -> Path:
    return agent_bus_path(repo_root, _active_bus_dir(bus_dir), "observability", *parts)


def _observability_relpath(*parts: str, bus_dir: str | Path | None = None) -> Path:
    return agent_bus_relpath(_active_bus_dir(bus_dir), "observability", *parts)


def _parse_timestamp_rank(value: Any) -> float:
    if not isinstance(value, str) or not value.strip():
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _codex_state_dir() -> Path:
    codex_home = (
        os.environ.get("RCX_CODEX_HOME")
        or os.environ.get("CODEX_HOME")
        or str(Path.home() / ".codex")
    )
    return Path(codex_home).expanduser() / "state"


def _read_latest_autoping_thread_id(repo_root: Path) -> str:
    state_dir = _codex_state_dir()
    if not state_dir.is_dir():
        return ""
    repo_resolved = repo_root.resolve()
    best_rank = 0.0
    best_thread_id = ""
    for state_path in state_dir.glob(AUTOPING_STATE_GLOB):
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        thread_id = str(payload.get("thread_id") or "").strip()
        if not thread_id:
            continue
        if str(payload.get("status") or "").strip().lower() in PAUSED_AUTOPING_STATUSES:
            continue
        bridge_state = payload.get("bridge_state")
        wave_root = ""
        if isinstance(bridge_state, dict):
            wave_root = str(bridge_state.get("wave_root") or "").strip()
        if not wave_root:
            wave_root = str(payload.get("wave_root") or "").strip()
        if not wave_root:
            continue
        try:
            if Path(wave_root).expanduser().resolve() != repo_resolved:
                continue
        except OSError:
            continue
        rank = max(
            _parse_timestamp_rank(payload.get("updated_at")),
            _parse_timestamp_rank(payload.get("last_dispatched_at")),
            _parse_timestamp_rank(payload.get("last_completed_at")),
        )
        if rank >= best_rank:
            best_rank = rank
            best_thread_id = thread_id
    return best_thread_id


def _autoping_payload_matches_repo(payload: dict[str, Any], repo_resolved: Path) -> bool:
    wave_root = _autoping_payload_wave_root(payload)
    if not wave_root:
        return False
    try:
        return Path(wave_root).expanduser().resolve() == repo_resolved
    except OSError:
        return False


def _autoping_payload_wave_root(payload: dict[str, Any]) -> str:
    bridge_state = payload.get("bridge_state")
    wave_root = ""
    if isinstance(bridge_state, dict):
        wave_root = str(bridge_state.get("wave_root") or "").strip()
    if not wave_root:
        wave_root = str(payload.get("wave_root") or "").strip()
    return wave_root


def _autoping_thread_is_foreign_to_repo(repo_root: Path, thread_id: str) -> bool:
    thread_id = str(thread_id or "").strip()
    if not thread_id:
        return False
    state_dir = _codex_state_dir()
    if not state_dir.is_dir():
        return False
    repo_resolved = repo_root.resolve()
    saw_foreign_state = False
    for state_path in state_dir.glob(AUTOPING_STATE_GLOB):
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("thread_id") or "").strip() != thread_id:
            continue
        wave_root = _autoping_payload_wave_root(payload)
        if not wave_root:
            continue
        try:
            if Path(wave_root).expanduser().resolve() == repo_resolved:
                return False
        except OSError:
            continue
        saw_foreign_state = True
    return saw_foreign_state


def _autoping_thread_is_paused(repo_root: Path, thread_id: str) -> bool:
    thread_id = str(thread_id or "").strip()
    if not thread_id:
        return False
    state_dir = _codex_state_dir()
    if not state_dir.is_dir():
        return False
    repo_resolved = repo_root.resolve()
    for state_path in state_dir.glob(AUTOPING_STATE_GLOB):
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        if str(payload.get("thread_id") or "").strip() != thread_id:
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status not in PAUSED_AUTOPING_STATUSES:
            continue
        if _autoping_payload_matches_repo(payload, repo_resolved):
            return True
    return False


def _repo_lock(repo_root: Path) -> threading.Lock:
    key = f"{repo_root.resolve()}::{agent_bus_relpath(_active_bus_dir()).as_posix()}"
    with _PROCESS_LOCKS_GUARD:
        lock = _PROCESS_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _PROCESS_LOCKS[key] = lock
        return lock


class _PagerLock:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._thread_lock = _repo_lock(repo_root)
        self._fp = None

    def __enter__(self) -> "_PagerLock":
        self._thread_lock.acquire()
        lock_path = _observability_path(self._repo_root, "pipeline_agent_pager.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(lock_path, "a+", encoding="utf-8")
        fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._fp is not None
        try:
            fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
        finally:
            self._fp.close()
            self._thread_lock.release()


def _default_dispatch_record() -> dict[str, Any]:
    return {
        "event_id": "",
        "event_type": "",
        "wave_id": "",
        "task_id": "",
        "phase": "",
        "state": "",
        "transition_key": "",
        "summary": "",
        "target": "",
        "attempted_at": "",
        "completed_at": "",
        "acknowledged": None,
        "error": "",
    }


def _default_dispatcher_state() -> dict[str, Any]:
    return {
        "active": False,
        "pid": 0,
        "started_at": "",
        "updated_at": "",
        "last_dispatch": _default_dispatch_record(),
    }


def _default_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "events": {},
        "codex_thread_id": None,
        "dispatcher": _default_dispatcher_state(),
        "updated_at": _utcnow(),
    }


def _coerce_positive_timeout(value: Any, fallback: float) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return float(fallback)
    if timeout <= 0:
        return float(fallback)
    return timeout


def _load_state(repo_root: Path) -> dict[str, Any]:
    state_path = _observability_path(repo_root, "pipeline_agent_pager_state.json")
    if not state_path.exists():
        return _default_state()
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PipelineAgentPagerError(f"pager state unreadable: {exc}") from exc
    if not isinstance(state, dict):
        raise PipelineAgentPagerError("pager state must be a JSON object")
    merged = _default_state()
    merged.update(state)
    if not isinstance(merged.get("events"), dict):
        raise PipelineAgentPagerError("pager state 'events' must be an object")
    dispatcher_state = merged.get("dispatcher")
    if not isinstance(dispatcher_state, dict):
        merged["dispatcher"] = _default_dispatcher_state()
    else:
        normalized_dispatcher = _default_dispatcher_state()
        normalized_dispatcher.update(dispatcher_state)
        last_dispatch = dispatcher_state.get("last_dispatch")
        if isinstance(last_dispatch, dict):
            normalized_last_dispatch = _default_dispatch_record()
            normalized_last_dispatch.update(last_dispatch)
            normalized_dispatcher["last_dispatch"] = normalized_last_dispatch
        else:
            normalized_dispatcher["last_dispatch"] = _default_dispatch_record()
        merged["dispatcher"] = normalized_dispatcher
    return merged


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


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _atomic_write_text(path, rendered)


def _save_state(repo_root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _utcnow()
    _atomic_write_json(_observability_path(repo_root, "pipeline_agent_pager_state.json"), state)


def _serialize_jsonl_records(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )


def _quarantine_corrupt_jsonl(path: Path, raw_text: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    quarantine_path = path.with_name(f"{path.name}.corrupt.{stamp}")
    _atomic_write_text(quarantine_path, raw_text)


def _load_jsonl_records(path: Path, *, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PipelineAgentPagerError(f"{label} unreadable: {exc}") from exc
    records: list[dict[str, Any]] = []
    nonempty_lines = [
        raw_line.strip()
        for raw_line in raw_text.splitlines()
        if raw_line.strip()
    ]
    for index, line in enumerate(nonempty_lines):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            if index != len(nonempty_lines) - 1:
                raise PipelineAgentPagerError(f"{label} unreadable: {exc}") from exc
            _quarantine_corrupt_jsonl(path, raw_text)
            _atomic_write_text(path, _serialize_jsonl_records(records))
            return records
        if not isinstance(record, dict):
            raise PipelineAgentPagerError(f"{label} line must be a JSON object")
        records.append(record)
    return records


def _load_events_from_log(repo_root: Path) -> list[dict[str, Any]]:
    return _load_jsonl_records(
        _observability_path(repo_root, "pipeline_agent_events.jsonl"),
        label="pager event log",
    )


def _load_delivery_receipts(repo_root: Path) -> list[dict[str, Any]]:
    return _load_jsonl_records(
        _observability_path(repo_root, "pipeline_agent_delivery_receipts.jsonl"),
        label="pager delivery log",
    )


def _append_jsonl_record(path: Path, payload: dict[str, Any], *, label: str) -> None:
    records = _load_jsonl_records(path, label=label)
    records.append(payload)
    _atomic_write_text(path, _serialize_jsonl_records(records))


def _append_event_record(repo_root: Path, event: dict[str, Any]) -> None:
    _append_jsonl_record(
        _observability_path(repo_root, "pipeline_agent_events.jsonl"),
        event,
        label="pager event log",
    )


def _append_delivery_receipt(
    repo_root: Path,
    *,
    event_id: str,
    target: str,
    ack: dict[str, Any],
    codex_thread_id: str | None = None,
) -> None:
    receipt = {
        "event_id": event_id,
        "target": target,
        "ack": ack,
        "recorded_at": _utcnow(),
    }
    thread_id = str(codex_thread_id or "").strip()
    if thread_id:
        receipt["codex_thread_id"] = thread_id
    _append_jsonl_record(
        _observability_path(repo_root, "pipeline_agent_delivery_receipts.jsonl"),
        receipt,
        label="pager delivery log",
    )


def _load_skip_receipts(repo_root: Path) -> list[dict[str, Any]]:
    return _load_jsonl_records(
        _observability_path(repo_root, "pipeline_agent_skip_receipts.jsonl"),
        label="pager skip log",
    )


def _append_skip_receipt(
    repo_root: Path,
    *,
    event_id: str,
    target: str,
    skip_reason: str,
) -> None:
    """Append a DISTINCT skip receipt (never a delivery receipt).

    A fail-closed leg is terminal: this durable, append-only record lets
    ``_reconcile_delivery_state`` rebuild ``skipped_targets`` after a state
    rebuild, exactly as delivery receipts rebuild ``delivered_targets``. It is
    deliberately written to a SEPARATE log so it can never be mistaken for a
    delivery (which would falsely mark the target delivered).
    """
    receipt = {
        "event_id": event_id,
        "target": target,
        "skip_reason": skip_reason,
        "recorded_at": _utcnow(),
    }
    _append_jsonl_record(
        _observability_path(repo_root, "pipeline_agent_skip_receipts.jsonl"),
        receipt,
        label="pager skip log",
    )


def _canonical_identity_tuple(
    *,
    task_id: str,
    wave_id: str,
    event_type: str,
    plan_path: str | None,
    phase: str,
    state: str,
    transition_key: str,
) -> dict[str, Any]:
    identity: dict[str, Any] = {
        "task_id": task_id,
        "wave_id": wave_id,
        "event_type": event_type,
        "phase": phase,
        "state": state,
        "transition_key": transition_key,
    }
    if plan_path:
        identity["plan_path"] = plan_path
    return identity


def _compute_event_id(identity: dict[str, Any]) -> str:
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _requested_targets(route: str) -> list[str]:
    if route == "both":
        return ["codex", "claude"]
    if route in {"codex", "claude", NOTIFY_ONLY_TARGET}:
        return [route]
    raise PipelineAgentPagerError(f"unsupported pager route: {route}")


def _pipeline_route_override() -> str | None:
    value = os.environ.get(PAGER_ROUTE_OVERRIDE_ENV)
    if value is None:
        return None
    route_text = str(value or "").strip()
    return route_text or None


def _orchestrator_mode_route(repo_root: Path) -> str | None:
    state_path = _observability_path(repo_root, "orchestrator_mode.json")
    if not state_path.exists():
        return None
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PipelineAgentPagerError(f"orchestrator mode state unreadable: {exc}") from exc
    if not isinstance(payload, dict):
        raise PipelineAgentPagerError("orchestrator mode state must be a JSON object")
    mode = str(payload.get("mode") or "").strip()
    if not mode:
        return None
    if mode not in {"codex", "claude"}:
        raise PipelineAgentPagerError(f"unsupported orchestrator mode route: {mode!r}")
    return mode


def _normalize_artifact_paths(artifact_paths: dict[str, Any] | None) -> dict[str, str]:
    normalized: dict[str, str] = {}
    if not artifact_paths:
        return normalized
    for key, value in artifact_paths.items():
        label = str(key or "").strip()
        path = str(value or "").strip()
        if not label or not path:
            continue
        normalized[label] = path
    return normalized


def _resolve_route(repo_root: Path, config: dict[str, Any], explicit_route: str | None) -> str:
    route = (
        explicit_route
        or _pipeline_route_override()
        or _orchestrator_mode_route(repo_root)
        or config.get("pipeline_agent_pager", {}).get("route", NOTIFY_ONLY_TARGET)
    )
    route_text = str(route or "").strip()
    if route_text not in ALLOWED_ROUTES:
        raise PipelineAgentPagerError(f"unsupported pager route: {route_text!r}")
    return route_text


def _configured_route_text(repo_root: Path, config: dict[str, Any], explicit_route: str | None) -> str:
    if explicit_route is not None:
        route = explicit_route
    else:
        route = _pipeline_route_override() or _orchestrator_mode_route(repo_root) or config.get(
            "pipeline_agent_pager",
            {},
        ).get("route", NOTIFY_ONLY_TARGET)
    route_text = str(route or "").strip()
    return route_text or NOTIFY_ONLY_TARGET


def _pager_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("pipeline_agent_pager", {}).get("enabled", False))


def _build_event_record(
    *,
    event_type: str,
    wave_id: str,
    task_id: str,
    plan_path: str | None,
    phase: str,
    state: str,
    transition_key: str,
    summary: str,
    reason: str,
    artifact_paths: dict[str, str],
    route: str,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise PipelineAgentPagerError(f"unsupported pager event_type: {event_type!r}")
    if not task_id.strip():
        raise PipelineAgentPagerError("task_id is required for pager events")
    if not wave_id.strip():
        raise PipelineAgentPagerError("wave_id is required for pager events")
    if not phase.strip():
        raise PipelineAgentPagerError("phase is required for pager events")
    if not state.strip():
        raise PipelineAgentPagerError("state is required for pager events")
    if not transition_key.strip():
        raise PipelineAgentPagerError("transition_key is required for pager events")
    identity = _canonical_identity_tuple(
        task_id=task_id.strip(),
        wave_id=wave_id.strip(),
        event_type=event_type,
        plan_path=plan_path.strip() if isinstance(plan_path, str) and plan_path.strip() else None,
        phase=phase.strip(),
        state=state.strip(),
        transition_key=transition_key.strip(),
    )
    event_id = _compute_event_id(identity)
    event: dict[str, Any] = {
        **identity,
        "event_id": event_id,
        "summary": summary.strip() or reason.strip() or event_type,
        "reason": reason.strip() or summary.strip() or event_type,
        "artifact_paths": artifact_paths,
        "timestamp": _utcnow(),
        "route": route,
        "requested_targets": _requested_targets(route),
    }
    if metadata:
        event["metadata"] = metadata
    return event


def _ensure_event_state(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    events = state.setdefault("events", {})
    entry = events.get(event["event_id"])
    if not isinstance(entry, dict):
        entry = {
            "event_id": event["event_id"],
            "route": event["route"],
            "requested_targets": list(event["requested_targets"]),
            "delivered_targets": {},
            "skipped_targets": {},
            "attempts": {},
            "pending_targets": list(event["requested_targets"]),
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
        }
        events[event["event_id"]] = entry
    else:
        merged_targets = _merge_requested_targets(
            entry.get("requested_targets", []),
            event.get("requested_targets", []),
        )
        entry["route"] = event["route"]
        entry["requested_targets"] = merged_targets
        entry.setdefault("delivered_targets", {})
        entry.setdefault("skipped_targets", {})
        entry.setdefault("attempts", {})
    _refresh_pending_targets(entry)
    return entry


def _refresh_pending_targets(entry: dict[str, Any]) -> None:
    requested = list(entry.get("requested_targets", []))
    delivered = entry.get("delivered_targets", {})
    skipped = entry.get("skipped_targets", {})
    # A target leaves pending if it was delivered OR fail-closed skipped. The
    # skip subtraction is what keeps a fail-closed claude leg from being retried
    # indefinitely while never marking it delivered.
    entry["pending_targets"] = [
        target for target in requested
        if target not in delivered and target not in skipped
    ]
    entry["updated_at"] = _utcnow()


def _merge_requested_targets(*sources: Any) -> list[str]:
    merged_targets: list[str] = []
    for source in sources:
        if not isinstance(source, list):
            continue
        for target in source:
            target_text = str(target or "").strip()
            if not target_text or target_text in merged_targets:
                continue
            merged_targets.append(target_text)
    return merged_targets


def _coalesced_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered_event_ids: list[str] = []
    coalesced_by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        prior = coalesced_by_id.get(event_id)
        if prior is None:
            merged = dict(event)
            merged["requested_targets"] = _merge_requested_targets(event.get("requested_targets", []))
            coalesced_by_id[event_id] = merged
            ordered_event_ids.append(event_id)
            continue
        merged = dict(prior)
        merged.update(event)
        merged["requested_targets"] = _merge_requested_targets(
            prior.get("requested_targets", []),
            event.get("requested_targets", []),
        )
        coalesced_by_id[event_id] = merged
    return [coalesced_by_id[event_id] for event_id in ordered_event_ids]


def _drop_transient_monitor_skips(entry: dict[str, Any]) -> None:
    """Scrub a PERSISTED transient monitor-state skip from a rebuilt entry.

    The two monitor-state skip reasons (``CLAUDE_SKIP_REASON_MONITOR_UNSET`` /
    ``CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE``) are NEVER terminal: both mean the
    dedicated monitor is not yet up with a DISTINCT id, and both clear the moment
    the monitor's session-start lands a clean, distinct id. The live dispatch path
    no longer parks either reason, but an older build -- or the prior terminal
    EQUALS_LIVE branch -- may have PERSISTED one directly into the state file's
    ``skipped_targets``, which ``_load_state`` reloads and ``_ensure_event_state``
    preserves via ``setdefault``. The skip-receipt guard only stops a REBUILD from
    a durable receipt; it cannot undo an already-loaded state entry. Drop any such
    stale entry so ``_refresh_pending_targets`` returns the target to
    ``pending_targets`` -- retryable once a distinct monitor id exists. Terminal
    skips (every other reason) are left untouched.
    """
    skipped = entry.get("skipped_targets")
    if not isinstance(skipped, dict) or not skipped:
        return
    transient_targets: list[str] = []
    for target, info in skipped.items():
        if isinstance(info, dict):
            reason = str(info.get("skip_reason") or "").strip()
        else:
            reason = str(info or "").strip()
        if reason in {
            CLAUDE_SKIP_REASON_MONITOR_UNSET,
            CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE,
        }:
            transient_targets.append(target)
    if not transient_targets:
        return
    for target in transient_targets:
        del skipped[target]
    _refresh_pending_targets(entry)


def _reconcile_delivery_state(
    repo_root: Path,
    state: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    event_map: dict[str, dict[str, Any]] = {}
    for event in _coalesced_events(events):
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        event_map[event_id] = event
        _ensure_event_state(state, event)

    for receipt in _load_delivery_receipts(repo_root):
        event_id = str(receipt.get("event_id") or "").strip()
        target = str(receipt.get("target") or "").strip()
        ack = receipt.get("ack")
        if not event_id or not target or not isinstance(ack, dict):
            raise PipelineAgentPagerError("pager delivery receipt missing event_id, target, or ack")
        event = event_map.get(event_id)
        if event is None:
            raise PipelineAgentPagerError(
                f"pager delivery receipt references unknown event_id: {event_id}"
            )
        entry = _ensure_event_state(state, event)
        delivered = entry.setdefault("delivered_targets", {})
        delivered[target] = ack
        thread_id = str(receipt.get("codex_thread_id") or "").strip()
        if target == "codex" and thread_id:
            state["codex_thread_id"] = thread_id
        _refresh_pending_targets(entry)

    for receipt in _load_skip_receipts(repo_root):
        event_id = str(receipt.get("event_id") or "").strip()
        target = str(receipt.get("target") or "").strip()
        skip_reason = str(receipt.get("skip_reason") or "").strip()
        if not event_id or not target or not skip_reason:
            raise PipelineAgentPagerError(
                "pager skip receipt missing event_id, target, or skip_reason"
            )
        event = event_map.get(event_id)
        if event is None:
            raise PipelineAgentPagerError(
                f"pager skip receipt references unknown event_id: {event_id}"
            )
        if skip_reason in {
            CLAUDE_SKIP_REASON_MONITOR_UNSET,
            CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE,
        }:
            # Authoritative replay-safety guard: a transient monitor-state skip is
            # NEVER terminal. Both reasons mean the dedicated monitor is not yet up
            # with a DISTINCT id -- the id is unset/malformed, or it transiently
            # equals the live orchestrator id -- and both clear the moment the
            # monitor's session-start lands a clean, distinct id. The live dispatch
            # path no longer writes either receipt (both are retryable in
            # _dispatch_pending_locked), but an older build -- or the prior
            # terminal EQUALS_LIVE branch -- may have left one on disk; do NOT
            # rebuild a skipped_targets entry from it. Leaving the target out of
            # skipped_targets keeps it in pending_targets so it retries once a
            # distinct monitor id exists. This closes the re-terminalize-on-rebuild
            # hole; every other skip reason rebuilds terminally below, unchanged.
            continue
        entry = _ensure_event_state(state, event)
        skipped = entry.setdefault("skipped_targets", {})
        skipped[target] = {
            "skip_reason": skip_reason,
            "recorded_at": str(receipt.get("recorded_at") or "").strip(),
        }
        _refresh_pending_targets(entry)
    # State-side mirror of the skip-receipt guard above. The receipt guard stops a
    # monitor-state skip from being REBUILT from a durable receipt, but an older
    # build -- or the prior terminal EQUALS_LIVE branch -- may have PERSISTED the
    # skip directly into the state file's skipped_targets (which _load_state
    # reloads and _ensure_event_state preserves). Scrub any such stale monitor-
    # state skip from every rebuilt entry so the claude leg returns to
    # pending_targets, retryable once a distinct monitor id exists. Without this, a
    # restart/replay re-terminalizes a page the monitor simply was not ready for
    # (bridge round-2 NO_GO). Terminal skips (every other reason) are untouched.
    for entry in state.get("events", {}).values():
        if isinstance(entry, dict):
            _drop_transient_monitor_skips(entry)
    autoping_thread_id = _read_latest_autoping_thread_id(repo_root)
    if autoping_thread_id:
        state["codex_thread_id"] = autoping_thread_id


def _set_dispatcher(state: dict[str, Any], *, active: bool) -> None:
    dispatcher = state.setdefault("dispatcher", _default_dispatcher_state())
    dispatcher["active"] = active
    dispatcher["pid"] = os.getpid()
    if active and not dispatcher.get("started_at"):
        dispatcher["started_at"] = _utcnow()
    if not active:
        dispatcher["started_at"] = ""
    dispatcher["updated_at"] = _utcnow()


def _begin_dispatch_record(state: dict[str, Any], event: dict[str, Any], *, target: str) -> None:
    dispatcher = state.setdefault("dispatcher", _default_dispatcher_state())
    dispatcher["last_dispatch"] = {
        "event_id": str(event.get("event_id") or "").strip(),
        "event_type": str(event.get("event_type") or "").strip(),
        "wave_id": str(event.get("wave_id") or "").strip(),
        "task_id": str(event.get("task_id") or "").strip(),
        "phase": str(event.get("phase") or "").strip(),
        "state": str(event.get("state") or "").strip(),
        "transition_key": str(event.get("transition_key") or "").strip(),
        "summary": str(event.get("summary") or "").strip(),
        "target": str(target or "").strip(),
        "attempted_at": _utcnow(),
        "completed_at": "",
        "acknowledged": None,
        "error": "",
    }
    dispatcher["updated_at"] = _utcnow()


def _finish_dispatch_record(state: dict[str, Any], *, acknowledged: bool, error: str = "") -> None:
    dispatcher = state.setdefault("dispatcher", _default_dispatcher_state())
    last_dispatch = dispatcher.get("last_dispatch")
    if not isinstance(last_dispatch, dict):
        last_dispatch = _default_dispatch_record()
        dispatcher["last_dispatch"] = last_dispatch
    last_dispatch["completed_at"] = _utcnow()
    last_dispatch["acknowledged"] = bool(acknowledged)
    last_dispatch["error"] = str(error or "").strip()
    dispatcher["updated_at"] = _utcnow()


def _event_prompt(event: dict[str, Any]) -> str:
    lines = [
        "WorkingRCX pipeline pager wakeup.",
        f"event_id: {event['event_id']}",
        f"event_type: {event['event_type']}",
        f"wave_id: {event['wave_id']}",
        f"task_id: {event['task_id']}",
        f"phase: {event['phase']}",
        f"state: {event['state']}",
        f"transition_key: {event['transition_key']}",
        f"summary: {event.get('summary', '')}",
    ]
    plan_path = event.get("plan_path")
    if isinstance(plan_path, str) and plan_path.strip():
        lines.append(f"plan_path: {plan_path}")
    artifact_paths = event.get("artifact_paths", {})
    if isinstance(artifact_paths, dict) and artifact_paths:
        lines.append("authoritative_artifacts:")
        for label, path in sorted(artifact_paths.items()):
            lines.append(f"- {label}: {path}")
    lines.append("Use these authoritative facts directly; do not re-scrape the repo just to rediscover the transition.")
    lines.append(
        "Do not run shell commands, tests, preflight checks, docs consistency, "
        "or tools from this headless pager wake path."
    )
    lines.append(
        "Do not edit files, run git add/commit/push, or apply structural fixes "
        "from this headless pager wake path."
    )
    lines.append(
        "Do not launch or relaunch executor_dispatch.py, phase_a_executor.py, "
        "phase_b_executor.py, commit_executor.py, or bridge_supervisor.py from "
        "this pager wake path."
    )
    lines.append(
        "If the pipeline is dead, report the diagnosed root cause and leave "
        "foreground restart to the operator-visible pipeline surface."
    )
    return "\n".join(lines)


def _excerpt(value: str, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


CODEX_APP_SERVER_NODE_SCRIPT = r"""
const [url, requestsJson, timeoutMsText] = process.argv.slice(1);
const requests = JSON.parse(requestsJson);
const timeoutMs = Math.max(1, Number(timeoutMsText));
let finished = false;
let activeRequest = null;
const responses = [];
const responsesById = new Map();

function finish(code, payload) {
  if (finished) {
    return;
  }
  finished = true;
  clearTimeout(timer);
  try {
    socket.close();
  } catch {}
  process.stdout.write(JSON.stringify(payload));
  process.exit(code);
}

function lookupPath(value, path) {
  if (!path) {
    return value;
  }
  let current = value;
  for (const part of path.split(".")) {
    if (current == null || typeof current !== "object" || !(part in current)) {
      return undefined;
    }
    current = current[part];
  }
  return current;
}

function resolveRefs(value) {
  if (Array.isArray(value)) {
    return value.map((item) => resolveRefs(item));
  }
  if (value && typeof value === "object") {
    if (Object.keys(value).length === 1 && typeof value.$from === "string") {
      const [idText, ...pathParts] = value.$from.split(".");
      const response = responsesById.get(Number(idText));
      return lookupPath(response, pathParts.join("."));
    }
    const resolved = {};
    for (const [key, inner] of Object.entries(value)) {
      resolved[key] = resolveRefs(inner);
    }
    return resolved;
  }
  return value;
}

function sendNext() {
  if (!requests.length) {
    finish(0, { responses });
    return;
  }
  activeRequest = requests.shift();
  const payload = {
    jsonrpc: "2.0",
    id: activeRequest.id,
    method: activeRequest.method,
  };
  if (Object.prototype.hasOwnProperty.call(activeRequest, "params")) {
    payload.params = resolveRefs(activeRequest.params);
  }
  socket.send(JSON.stringify(payload));
}

if (typeof WebSocket !== "function") {
  process.stdout.write(JSON.stringify({ error: "node WebSocket unavailable" }));
  process.exit(1);
}

const socket = new WebSocket(url);
const timer = setTimeout(() => {
  finish(1, { error: "timed out before acknowledgement", responses });
}, timeoutMs);

socket.addEventListener("open", () => {
  sendNext();
});

socket.addEventListener("message", (event) => {
  let message;
  try {
    message = JSON.parse(String(event.data));
  } catch {
    return;
  }
  if (
    !activeRequest ||
    !message ||
    typeof message !== "object" ||
    !Object.prototype.hasOwnProperty.call(message, "id") ||
    message.id !== activeRequest.id
  ) {
    return;
  }
  responses.push(message);
  responsesById.set(activeRequest.id, message);
  activeRequest = null;
  sendNext();
});

socket.addEventListener("error", () => {
  finish(1, { error: "websocket connection failed", responses });
});

socket.addEventListener("close", () => {
  if (!finished) {
    finish(1, { error: "websocket closed before completing exchange", responses });
  }
});
"""


def _codex_app_server_url() -> str:
    raw = str(
        os.environ.get("RCX_CODEX_APP_SERVER_URL", "ws://127.0.0.1:8765")
    ).strip()
    parts = urllib_parse.urlparse(raw)
    try:
        port = parts.port
    except ValueError as exc:
        raise PipelineAgentPagerError(
            "RCX_CODEX_APP_SERVER_URL must include a valid websocket port"
        ) from exc
    if port is None:
        raise PipelineAgentPagerError(
            "RCX_CODEX_APP_SERVER_URL must include a valid websocket port"
        )
    host = (parts.hostname or "").strip().lower()
    if parts.scheme != "ws":
        raise PipelineAgentPagerError(
            "RCX_CODEX_APP_SERVER_URL must be a ws:// loopback listener URL"
        )
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise PipelineAgentPagerError(
            "RCX_CODEX_APP_SERVER_URL must target a loopback websocket listener"
        )
    return raw


def _codex_app_server_exchange(
    url: str,
    requests: list[dict[str, Any]],
    timeout_s: float,
) -> list[dict[str, Any]]:
    if timeout_s <= 0:
        raise PipelineAgentPagerError("codex pager acknowledgement timed out before acknowledgement")
    try:
        proc = subprocess.run(
            [
                "node",
                "-e",
                CODEX_APP_SERVER_NODE_SCRIPT,
                url,
                json.dumps(requests),
                str(max(1, int(timeout_s * 1000))),
            ],
            capture_output=True,
            text=True,
            timeout=max(timeout_s, 0.001) + 0.25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PipelineAgentPagerError(f"{url} unavailable: {type(exc).__name__}") from exc
    try:
        parsed = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise PipelineAgentPagerError(f"{url} returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise PipelineAgentPagerError(f"{url} returned non-object JSON")
    if proc.returncode != 0:
        error = str(parsed.get("error") or _excerpt(proc.stderr) or "websocket exchange failed").strip()
        raise PipelineAgentPagerError(f"{url} unavailable: {error}")
    responses = parsed.get("responses")
    if not isinstance(responses, list):
        raise PipelineAgentPagerError(f"{url} returned invalid response list")
    return responses


def _remaining_timeout(deadline: float, *, label: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PipelineAgentPagerError(f"{label} timed out before acknowledgement")
    return remaining


def _is_codex_transport_unavailable(error_text: str) -> bool:
    lowered = str(error_text or "").lower()
    return "unavailable" in lowered or "returned http" in lowered


def _codex_exec_resume_env() -> dict[str, str]:
    # Preserve the live shell environment so resume inherits the same auth/session
    # context while still allowing a repo-local RCX overlay when present.
    return os.environ.copy()


CODEX_NO_TOOLS_DISABLED_FEATURES = (
    "apps",
    "apply_patch_freeform",
    "apply_patch_streaming_events",
    "artifact",
    "browser_use",
    "code_mode",
    "code_mode_only",
    "codex_git_commit",
    "computer_use",
    "image_generation",
    "js_repl",
    "js_repl_tools_only",
    "multi_agent",
    "multi_agent_v2",
    "plugins",
    "request_permissions_tool",
    "shell_snapshot",
    "shell_tool",
    "skill_mcp_dependency_install",
    "tool_call_mcp_elicitation",
    "tool_search",
    "tool_suggest",
    "unified_exec",
    "workspace_dependencies",
)
CODEX_NO_TOOLS_RESUME_ARGS = tuple(
    part
    for feature_name in CODEX_NO_TOOLS_DISABLED_FEATURES
    for part in ("--disable", feature_name)
)
CODEX_PAGER_RESUME_CONFIG = (
    "--ignore-user-config",
    "--ignore-rules",
    *CODEX_NO_TOOLS_RESUME_ARGS,
    "-c",
    'sandbox_mode="read-only"',
    "-c",
    'approval_policy="never"',
)


def _codex_exec_resume_command(codex_bin: str, thread_id: str, prompt: str) -> list[str]:
    return [
        codex_bin,
        "exec",
        "resume",
        *CODEX_PAGER_RESUME_CONFIG,
        "--json",
        thread_id,
        prompt,
    ]


def _terminate_process_group(proc: subprocess.Popen[str], *, grace_s: float = 5.0) -> None:
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        return


def _dispatch_codex_exec_resume(
    repo_root: Path,
    event: dict[str, Any],
    *,
    thread_id: str,
    timeout_s: float,
) -> dict[str, Any]:
    codex_bin = os.environ.get("RCX_PIPELINE_AGENT_PAGER_CODEX_BIN", "codex")
    log_dir = _observability_path(repo_root, "codex_pager_dispatch")
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = log_dir / f"codex_pager_{stamp}_{event['event_id'][:8]}.jsonl"
    command = _codex_exec_resume_command(codex_bin, thread_id, _event_prompt(event))
    try:
        with log_path.open("w", encoding="utf-8") as sink:
            proc = subprocess.Popen(
                command,
                cwd=repo_root,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
                env=_codex_exec_resume_env(),
            )
    except OSError as exc:
        return {
            "acknowledged": False,
            "error": f"codex exec resume launch failed: {exc}",
            "codex_thread_id": thread_id,
        }

    try:
        exit_code = proc.wait(timeout=max(timeout_s, 0.001))
    except subprocess.TimeoutExpired:
        _terminate_process_group(proc)
        try:
            detail = _excerpt(log_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            detail = ""
        return {
            "acknowledged": False,
            "error": (
                f"codex exec resume timed out after {timeout_s:.3g}s"
                + (f": {detail}" if detail else "")
            ),
            "codex_thread_id": thread_id,
        }
    if exit_code != 0:
        try:
            detail = _excerpt(log_path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            detail = ""
        return {
            "acknowledged": False,
            "error": (
                f"codex exec resume exited {exit_code}"
                + (f": {detail}" if detail else "")
            ),
            "codex_thread_id": thread_id,
        }
    return {
        "acknowledged": True,
        "ack": {
            "acknowledged_at": _utcnow(),
            "thread_id": thread_id,
            "target": "codex",
            "mode": "exec_resume",
            "pid": proc.pid,
            "log_path": str(log_path),
        },
        "codex_thread_id": thread_id,
    }
def _response_nested_value(response: dict[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        current: Any = response
        for part in path:
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current not in (None, ""):
            return current
    return None


def _codex_response_error(response: dict[str, Any]) -> str:
    message = _response_nested_value(response, ("error", "message"))
    if message not in (None, ""):
        return str(message).strip()
    error = response.get("error")
    if error not in (None, ""):
        return _excerpt(error)
    return ""


def _codex_thread_id_from_response(response: dict[str, Any]) -> str:
    value = _response_nested_value(
        response,
        ("result", "thread", "id"),
        ("thread", "id"),
    )
    return str(value or "").strip()


def _codex_turn_id_from_response(response: dict[str, Any]) -> str:
    value = _response_nested_value(
        response,
        ("result", "turn", "id"),
        ("turn", "id"),
    )
    return str(value or "").strip()


def _codex_is_stale_thread_error(message: str) -> bool:
    lower = str(message or "").strip().lower()
    return "thread not found" in lower or "no rollout found" in lower


def _dispatch_codex(
    repo_root: Path,
    event: dict[str, Any],
    state: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    autoping_thread_id = _read_latest_autoping_thread_id(repo_root)
    env_thread_id = str(os.environ.get("CODEX_THREAD_ID") or "").strip()
    if env_thread_id and (
        _autoping_thread_is_paused(repo_root, env_thread_id)
        or _autoping_thread_is_foreign_to_repo(repo_root, env_thread_id)
    ):
        env_thread_id = ""
    live_thread_id = env_thread_id or autoping_thread_id
    state_thread_id = str(state.get("codex_thread_id") or "").strip()
    if state_thread_id and (
        _autoping_thread_is_paused(repo_root, state_thread_id)
        or _autoping_thread_is_foreign_to_repo(repo_root, state_thread_id)
    ):
        state_thread_id = ""
    thread_id = live_thread_id or state_thread_id
    base_url = ""
    deadline = time.monotonic() + max(timeout_s, 0.001)

    def exchange(requests: list[dict[str, Any]]) -> list[dict[str, Any]]:
        responses = _codex_app_server_exchange(
            base_url,
            requests,
            _remaining_timeout(deadline, label="codex pager acknowledgement"),
        )
        _remaining_timeout(deadline, label="codex pager acknowledgement")
        return responses

    def initialize_request(request_id: int) -> dict[str, Any]:
        return {
            "id": request_id,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "pipeline_agent_pager",
                    "version": "1.0",
                }
            },
        }

    def thread_start_request(request_id: int) -> dict[str, Any]:
        return {"id": request_id, "method": "thread/start", "params": {}}

    def turn_start_request(request_id: int, target_thread: Any) -> dict[str, Any]:
        return {
            "id": request_id,
            "method": "turn/start",
            "params": {
                "threadId": target_thread,
                "input": [{"type": "text", "text": _event_prompt(event)}],
            },
        }

    clear_thread_id = False
    try:
        base_url = _codex_app_server_url()
        if thread_id:
            existing_responses = exchange(
                [initialize_request(1), turn_start_request(2, thread_id)]
            )
            turn_response = existing_responses[-1] if existing_responses else {}
            turn_error = _codex_response_error(turn_response)
            if turn_error and _codex_is_stale_thread_error(turn_error):
                clear_thread_id = True
                thread_id = ""
            elif turn_error:
                return {
                    "acknowledged": False,
                    "error": turn_error,
                    "codex_thread_id": state.get("codex_thread_id") or None,
                }
        if not thread_id:
            new_thread_responses = exchange(
                [
                    initialize_request(1),
                    thread_start_request(2),
                    turn_start_request(3, {"$from": "2.result.thread.id"}),
                ]
            )
            thread_response = new_thread_responses[1] if len(new_thread_responses) > 1 else {}
            thread_error = _codex_response_error(thread_response)
            if thread_error:
                return {
                    "acknowledged": False,
                    "error": thread_error,
                    "codex_thread_id": None,
                    "clear_codex_thread_id": clear_thread_id,
                }
            thread_id = _codex_thread_id_from_response(thread_response)
            if not thread_id:
                return {
                    "acknowledged": False,
                    "error": "codex thread create missing thread_id",
                    "codex_thread_id": None,
                    "clear_codex_thread_id": clear_thread_id,
                }
            turn_response = new_thread_responses[-1] if new_thread_responses else {}
    except PipelineAgentPagerError as exc:
        fallback_thread_id = live_thread_id or thread_id
        if fallback_thread_id and _is_codex_transport_unavailable(str(exc)):
            fallback_timeout_s = deadline - time.monotonic()
            if fallback_timeout_s <= 0:
                return {
                    "acknowledged": False,
                    "error": (
                        f"{exc}; codex exec resume fallback skipped because "
                        "codex pager acknowledgement timed out before acknowledgement"
                    ),
                    "codex_thread_id": fallback_thread_id,
                }
            fallback = _dispatch_codex_exec_resume(
                repo_root,
                event,
                thread_id=fallback_thread_id,
                timeout_s=fallback_timeout_s,
            )
            if not fallback.get("acknowledged"):
                error_text = str(fallback.get("error") or "").strip()
                fallback["error"] = (
                    f"{exc}; {error_text}" if error_text else str(exc)
                )
            return fallback
        return {
            "acknowledged": False,
            "error": str(exc),
            "codex_thread_id": thread_id or None,
            "clear_codex_thread_id": clear_thread_id and not thread_id,
        }
    response_error = _codex_response_error(turn_response)
    if response_error:
        return {
            "acknowledged": False,
            "error": response_error,
            "codex_thread_id": thread_id or None,
            "clear_codex_thread_id": clear_thread_id and not thread_id,
        }
    response_thread_id = _codex_thread_id_from_response(turn_response)
    effective_thread_id = response_thread_id or thread_id
    turn_id = _codex_turn_id_from_response(turn_response)
    if response_thread_id and response_thread_id != thread_id:
        return {
            "acknowledged": False,
            "error": (
                "codex accepted-turn response thread_id "
                f"{response_thread_id!r} did not match requested thread {thread_id!r}"
            ),
            "codex_thread_id": thread_id or None,
        }
    if not turn_id:
        return {
            "acknowledged": False,
            "error": "codex accepted-turn response missing turn_id",
            "codex_thread_id": thread_id or None,
        }
    return {
        "acknowledged": True,
        "ack": {
            "acknowledged_at": _utcnow(),
            "thread_id": effective_thread_id,
            "turn_id": turn_id,
            "target": "codex",
        },
        "codex_thread_id": effective_thread_id,
    }


def _read_orchestrator_session_id(repo_root: Path) -> str | None:
    """Return the orchestrator session id for pager ``--resume`` dispatch.

    The orchestrator-session-id file is authored by the
    SessionStart hook writer in ``.claude/hooks/session-start.sh``. The
    pager is read-only here and tolerates every absent/malformed case so
    that a missing, stale, or corrupt file never crashes the orchestrator:
    missing file, empty file, whitespace-only file, and a single trailing
    newline all yield ``None``. A session id containing internal whitespace
    or newlines — or a file whose bytes are not valid UTF-8 — is treated as
    malformed: a single fallback note is emitted to stderr and ``None`` is
    returned so the caller falls back to plain ``claude -p`` dispatch.
    """
    session_path = _observability_path(repo_root, "orchestrator_session_id")
    try:
        raw = session_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    except UnicodeDecodeError:
        print(
            f"[pipeline_agent_pager] orchestrator_session_id at {session_path} "
            "is not valid UTF-8; falling back to plain -p dispatch",
            file=sys.stderr,
            flush=True,
        )
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if any(ch.isspace() for ch in candidate):
        print(
            f"[pipeline_agent_pager] orchestrator_session_id at {session_path} "
            "contains internal whitespace; falling back to plain -p dispatch",
            file=sys.stderr,
            flush=True,
        )
        return None
    return candidate


def _read_claude_monitor_session_id(repo_root: Path) -> str | None:
    """Return the DEDICATED claude-monitor session id for pager ``--resume``.

    Mirrors ``_read_orchestrator_session_id``'s malformed-tolerance discipline
    exactly, but reads ONLY the dedicated monitor-session-id file (a sibling of
    ``orchestrator_session_id`` under the observability dir). The monitor file
    is authored by the claude monitor's own session-start writer. When no distinct
    monitor id is available this resolver returns ``None`` and ``_dispatch_claude``
    falls back to a DIRECT ``claude -p`` page. There is NO fallback to the live
    ``orchestrator_session_id`` file: the live orchestrator conversation is never
    a ``claude --resume`` target (a direct page resumes nothing). Every
    absent/malformed case yields ``None``: missing file, OSError, non-UTF-8 bytes,
    empty, whitespace-only, and a session id containing internal whitespace or
    newlines.
    """
    monitor_path = _observability_path(repo_root, "claude_monitor_session_id")
    try:
        raw = monitor_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    except UnicodeDecodeError:
        print(
            f"[pipeline_agent_pager] claude_monitor_session_id at {monitor_path} "
            "is not valid UTF-8; failing closed (no claude --resume)",
            file=sys.stderr,
            flush=True,
        )
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if any(ch.isspace() for ch in candidate):
        print(
            f"[pipeline_agent_pager] claude_monitor_session_id at {monitor_path} "
            "contains internal whitespace; failing closed (no claude --resume)",
            file=sys.stderr,
            flush=True,
        )
        return None
    return candidate


def _claude_dispatch_env() -> dict[str, str]:
    """Environment for the pager's own ``claude`` page-delivery subprocess.

    The pager's ``claude`` child -- whether it ``--resume``s the dedicated
    monitor or pages DIRECTLY with a fresh ``claude -p`` -- is a TRANSIENT
    page-delivery process. It is neither the live orchestrator nor a dedicated
    monitor, so its session id must never be registered anywhere. But a fresh
    ``claude`` child runs the repo SessionStart hook
    (``.claude/hooks/session-start.sh``), which by default writes the child's
    session id into ``orchestrator_session_id`` (or, under
    ``RCX_CLAUDE_MONITOR=1``, into the sibling ``claude_monitor_session_id``).

    When the pager runs from a process that does NOT already export
    ``RCX_PIPELINE_SESSION=1`` (a normal pipeline process), that hook would
    clobber the live ``orchestrator_session_id`` with the throwaway child id.
    On the ``--resume`` leg it is worse: the hook writes the monitor id INTO
    ``orchestrator_session_id``, so the next dispatch sees ``monitor == live``
    (the inequality check in ``_dispatch_claude``) and falls through to a direct
    page forever, permanently defeating the dedicated-monitor resume.

    Mark the child as a pipeline-owned sub-session (``RCX_PIPELINE_SESSION=1``)
    AND clear any inherited ``RCX_CLAUDE_MONITOR`` so the child hits the hook's
    full-suppression guard (``RCX_PIPELINE_SESSION=1`` AND
    ``RCX_CLAUDE_MONITOR != 1`` -> ``exit 0``, writes nothing). This reuses the
    SAME suppression contract ``bridge_adapters.py`` already relies on for its
    adapter sub-sessions; it adds no host-only semantics. The rest of the live
    environment is inherited so the page keeps the same auth/session context.
    """
    env = os.environ.copy()
    env["RCX_PIPELINE_SESSION"] = "1"
    env.pop("RCX_CLAUDE_MONITOR", None)
    return env


def _dispatch_claude(
    repo_root: Path,
    event: dict[str, Any],
    config: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    claude_bin = os.environ.get("RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN", "claude")
    monitor_session_id = _read_claude_monitor_session_id(repo_root)
    resume_target: str | None = None
    if monitor_session_id:
        live_session_id = _read_orchestrator_session_id(repo_root)
        if live_session_id is None or monitor_session_id != live_session_id:
            # A DISTINCT dedicated monitor session is registered (present,
            # well-formed, and != the live orchestrator id): resume it. The live
            # orchestrator id is read for this inequality check ONLY, never as a
            # ``--resume`` target.
            resume_target = monitor_session_id
        # else: the dedicated monitor id transiently equals the live orchestrator
        # id -> fall through to a DIRECT page (never resume the live orchestrator).
    # No DISTINCT dedicated monitor available (id absent / malformed, or equal to
    # the live orchestrator id): page Claude DIRECTLY with a fresh ``claude -p``
    # subprocess. A direct page passes NO ``--resume``, so it can never resume the
    # live orchestrator session; it restores the pre-refactor direct pipeline page
    # the dedicated-monitor refactor had turned into a fail-closed skip. The page
    # is a normal acknowledged delivery (or a retryable error) -- never a skip.
    if resume_target is not None:
        command = [claude_bin, "--resume", resume_target, "-p", _event_prompt(event)]
    else:
        command = [claude_bin, "-p", _event_prompt(event)]
    try:
        proc = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
            # Suppress the child's SessionStart orchestrator/monitor writer so a
            # transient page-delivery ``claude`` never clobbers the live
            # ``orchestrator_session_id`` (or ``claude_monitor_session_id``).
            env=_claude_dispatch_env(),
        )
    except subprocess.TimeoutExpired:
        return {
            "acknowledged": False,
            "error": f"claude pager submission timed out after {timeout_s:.3g}s",
        }
    except OSError as exc:
        return {
            "acknowledged": False,
            "error": f"claude pager submission failed: {exc}",
        }
    if proc.returncode != 0:
        return {
            "acknowledged": False,
            "error": (
                f"claude pager submission exited {proc.returncode}: "
                f"{_excerpt(proc.stderr or proc.stdout)}"
            ),
        }
    ack: dict[str, Any] = {
        "acknowledged_at": _utcnow(),
        "exit_code": proc.returncode,
        "target": "claude",
    }
    if resume_target is not None:
        # Resume of a distinct dedicated monitor: record the resumed session id
        # (this path is unchanged from before the direct-fallback wave).
        ack["session_id"] = resume_target
    else:
        # Direct ``claude -p`` page: no session was resumed. The ``direct`` mode
        # marker makes the fallback delivery self-evident in ``delivered_targets``.
        ack["mode"] = "direct"
    return {"acknowledged": True, "ack": ack}


def _dispatch_notify_only(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "acknowledged": True,
        "ack": {
            "acknowledged_at": _utcnow(),
            "event_id": event["event_id"],
            "target": NOTIFY_ONLY_TARGET,
            "mode": NOTIFY_ONLY_TARGET,
        },
    }


def _dispatch_target(
    repo_root: Path,
    target: str,
    event: dict[str, Any],
    state: dict[str, Any],
    config: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    if target == "codex":
        return _dispatch_codex(repo_root, event, state, timeout_s=timeout_s)
    if target == "claude":
        return _dispatch_claude(repo_root, event, config, timeout_s=timeout_s)
    if target == NOTIFY_ONLY_TARGET:
        return _dispatch_notify_only(event)
    raise PipelineAgentPagerError(f"unsupported pager target: {target}")


def _target_timeout(config: dict[str, Any], target: str, remaining_s: float) -> float:
    timeouts = config.get("timeouts", {})
    if target == "codex":
        configured = timeouts.get(
            "pipeline_agent_pager_codex_ack",
            DEFAULT_EXECUTOR_CONFIG["timeouts"]["pipeline_agent_pager_codex_ack"],
        )
    elif target == "claude":
        configured = timeouts.get(
            "pipeline_agent_pager_claude_ack",
            DEFAULT_EXECUTOR_CONFIG["timeouts"]["pipeline_agent_pager_claude_ack"],
        )
    else:
        configured = 1.0
    bounded = _coerce_positive_timeout(configured, 1)
    remaining = max(remaining_s, 0.001)
    return min(bounded, remaining)


def _should_append_event_record(state: dict[str, Any], event: dict[str, Any]) -> bool:
    entry = state.get("events", {}).get(event["event_id"])
    if not isinstance(entry, dict):
        return True
    existing_targets = _merge_requested_targets(entry.get("requested_targets", []))
    next_targets = _merge_requested_targets(existing_targets, event.get("requested_targets", []))
    return next_targets != existing_targets


def _dispatch_pending_locked(
    repo_root: Path,
    state: dict[str, Any],
    events: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    trigger_timeout = _coerce_positive_timeout(
        config.get("timeouts", {}).get(
            "pipeline_agent_pager_trigger",
            DEFAULT_EXECUTOR_CONFIG["timeouts"]["pipeline_agent_pager_trigger"],
        ),
        DEFAULT_EXECUTOR_CONFIG["timeouts"]["pipeline_agent_pager_trigger"],
    )
    deadline = time.monotonic() + trigger_timeout
    report: dict[str, Any] = {
        "attempted": [],
        "budget_exhausted": False,
    }
    for event in _coalesced_events(events):
        entry = _ensure_event_state(state, event)
        pending_targets = list(entry.get("pending_targets", []))
        if not pending_targets:
            continue
        for target in pending_targets:
            remaining_s = deadline - time.monotonic()
            if remaining_s <= 0:
                report["budget_exhausted"] = True
                _refresh_pending_targets(entry)
                _save_state(repo_root, state)
                return report
            timeout_s = _target_timeout(config, target, remaining_s)
            _begin_dispatch_record(state, event, target=target)
            dispatch_result = _dispatch_target(
                repo_root,
                target,
                event,
                state,
                config,
                timeout_s=timeout_s,
            )
            attempts = entry.setdefault("attempts", {})
            prior_attempt = attempts.get(target, {})
            attempt_record = {
                "count": int(prior_attempt.get("count", 0)) + 1,
                "last_attempt_at": _utcnow(),
            }
            error_text = str(dispatch_result.get("error") or "").strip()
            skipped = bool(dispatch_result.get("skipped"))
            skip_reason = str(dispatch_result.get("skip_reason") or "").strip()
            _finish_dispatch_record(
                state,
                acknowledged=bool(dispatch_result.get("acknowledged")),
                error=error_text,
            )
            if error_text:
                attempt_record["last_error"] = error_text
            else:
                attempt_record.pop("last_error", None)
            if skipped and skip_reason:
                attempt_record["last_skip_reason"] = skip_reason
            else:
                attempt_record.pop("last_skip_reason", None)
            attempt_record.pop("last_receipt_log_warning", None)
            attempt_record.pop("last_skip_log_warning", None)
            attempts[target] = attempt_record
            if dispatch_result.get("clear_codex_thread_id"):
                state["codex_thread_id"] = None
            elif dispatch_result.get("codex_thread_id"):
                state["codex_thread_id"] = dispatch_result["codex_thread_id"]
            receipt_log_warning = ""
            skip_log_warning = ""
            state_saved = False
            if dispatch_result.get("acknowledged"):
                delivered = entry.setdefault("delivered_targets", {})
                delivered[target] = dispatch_result["ack"]
                _refresh_pending_targets(entry)
                _save_state(repo_root, state)
                state_saved = True
                try:
                    _append_delivery_receipt(
                        repo_root,
                        event_id=event["event_id"],
                        target=target,
                        ack=dispatch_result["ack"],
                        codex_thread_id=dispatch_result.get("codex_thread_id"),
                    )
                except Exception as exc:
                    receipt_log_warning = str(exc)
                    attempt_record["last_receipt_log_warning"] = receipt_log_warning
                    attempts[target] = attempt_record
                    state_saved = False
            elif skipped and skip_reason in {
                CLAUDE_SKIP_REASON_MONITOR_UNSET,
                CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE,
            }:
                # TRANSIENT, replay-safe monitor-state skip (NOT terminal). Both
                # reasons mean the dedicated monitor is not yet up with a DISTINCT
                # id: MONITOR_UNSET is the whole unset-or-malformed family
                # collapsed by _read_claude_monitor_session_id into one reason;
                # MONITOR_EQUALS_LIVE means the monitor id transiently equals the
                # live orchestrator id. The monitor's session-start writer
                # (.claude/hooks/session-start.sh under RCX_CLAUDE_MONITOR=1)
                # clears BOTH the moment it atomically lands a clean, distinct id,
                # so either skip is genuinely transient. Do NOT park the target in
                # skipped_targets: _refresh_pending_targets then leaves it in
                # pending_targets, retryable on a later dispatch once a distinct
                # monitor id exists. Do NOT append a durable skip receipt either --
                # writing no terminal trace is what keeps a restart/replay from
                # re-terminalizing the page (the matching guard in
                # _reconcile_delivery_state ignores a pre-existing receipt for
                # EITHER reason). A page to Claude is therefore never silently or
                # terminally dropped because the monitor was not yet up with a
                # distinct id. Codex never emits a skip marker, so this branch is
                # claude-only. Every OTHER skip reason stays terminal below.
                _refresh_pending_targets(entry)
                _save_state(repo_root, state)
                state_saved = True
            elif skipped:
                # Genuinely terminal fail-closed claude leg: any future/other skip
                # reason that is NOT one of the two transient monitor-state reasons
                # handled retryably above. A DISTINCT skip -- never a delivery and
                # never a retryable error. Park the target in skipped_targets so
                # _refresh_pending_targets drops it from pending_targets (it is
                # neither marked delivered nor left pending for retry), and append
                # a distinct skip receipt (never a delivery receipt) so the skip
                # survives a state rebuild. Codex never emits the skip marker, so
                # this branch is claude-only and leaves the codex delivered /
                # pending / retry semantics and receipts untouched.
                skipped_targets = entry.setdefault("skipped_targets", {})
                skipped_targets[target] = {
                    "skip_reason": skip_reason,
                    "skipped_at": _utcnow(),
                }
                _refresh_pending_targets(entry)
                _save_state(repo_root, state)
                state_saved = True
                try:
                    _append_skip_receipt(
                        repo_root,
                        event_id=event["event_id"],
                        target=target,
                        skip_reason=skip_reason,
                    )
                except Exception as exc:
                    skip_log_warning = str(exc)
                    attempt_record["last_skip_log_warning"] = skip_log_warning
                    attempts[target] = attempt_record
                    state_saved = False
            _refresh_pending_targets(entry)
            if not state_saved:
                _save_state(repo_root, state)
            report["attempted"].append({
                "event_id": event["event_id"],
                "target": target,
                "acknowledged": bool(dispatch_result.get("acknowledged")),
                "error": error_text,
                "receipt_log_warning": receipt_log_warning,
            })
    return report


def dispatch_pending_events(
    repo_root: Path,
    *,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    resolve_agent_bus_dir(repo_root, bus_dir)
    token = _ACTIVE_BUS_DIR.set(agent_bus_relpath(bus_dir))
    try:
        config = load_executor_config(repo_root)
        if not _pager_enabled(config):
            return {
                "enabled": False,
                "attempted": [],
                "budget_exhausted": False,
            }
        with _PagerLock(repo_root):
            state = _load_state(repo_root)
            events = _load_events_from_log(repo_root)
            _reconcile_delivery_state(repo_root, state, events)
            _set_dispatcher(state, active=True)
            _save_state(repo_root, state)
            try:
                report = _dispatch_pending_locked(repo_root, state, events, config)
            finally:
                _set_dispatcher(state, active=False)
                _save_state(repo_root, state)
            return {
                "enabled": True,
                **report,
            }
    finally:
        _ACTIVE_BUS_DIR.reset(token)


def emit_transition_event(
    repo_root: Path,
    *,
    bus_dir: str | Path | None = None,
    event_type: str,
    wave_id: str,
    task_id: str,
    plan_path: str | None = None,
    phase: str,
    state: str,
    transition_key: str,
    summary: str = "",
    reason: str = "",
    artifact_paths: dict[str, Any] | None = None,
    route: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    resolve_agent_bus_dir(repo_root, bus_dir)
    token = _ACTIVE_BUS_DIR.set(agent_bus_relpath(bus_dir))
    try:
        config = load_executor_config(repo_root)
        if not _pager_enabled(config):
            return {
                "enabled": False,
                "route": _configured_route_text(repo_root, config, route),
                "event_id": None,
                "attempted": [],
                "budget_exhausted": False,
            }
        resolved_route = _resolve_route(repo_root, config, route)
        event = _build_event_record(
            event_type=event_type,
            wave_id=wave_id,
            task_id=task_id,
            plan_path=plan_path,
            phase=phase,
            state=state,
            transition_key=transition_key,
            summary=summary,
            reason=reason,
            artifact_paths=_normalize_artifact_paths(artifact_paths),
            route=resolved_route,
            metadata=metadata,
        )
        with _PagerLock(repo_root):
            state = _load_state(repo_root)
            events = _load_events_from_log(repo_root)
            _reconcile_delivery_state(repo_root, state, events)
            if _should_append_event_record(state, event):
                _append_event_record(repo_root, event)
                events.append(event)
            _ensure_event_state(state, event)
            _set_dispatcher(state, active=True)
            _save_state(repo_root, state)
            try:
                report = _dispatch_pending_locked(repo_root, state, events, config)
            finally:
                _set_dispatcher(state, active=False)
                _save_state(repo_root, state)
            return {
                "enabled": True,
                "event_id": event["event_id"],
                "route": resolved_route,
                **report,
            }
    finally:
        _ACTIVE_BUS_DIR.reset(token)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dispatch pending pipeline-agent pager events.")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root for the pager state/log files.",
    )
    parser.add_argument(
        "--dispatch-pending",
        action="store_true",
        help="Dispatch pending pager targets from the append-only event log.",
    )
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
    )
    args = parser.parse_args(argv)
    if not args.dispatch_pending:
        parser.error("specify --dispatch-pending")
    result = dispatch_pending_events(args.repo_root, bus_dir=args.bus_dir)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
