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
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import DEFAULT_EXECUTOR_CONFIG, load_executor_config
except ImportError:
    import importlib.util as _ilu

    _common_path = SCRIPT_DIR.parent / "executors" / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    DEFAULT_EXECUTOR_CONFIG = _mod.DEFAULT_EXECUTOR_CONFIG
    load_executor_config = _mod.load_executor_config

OBSERVABILITY_DIR = Path(".agent_bus/observability")
EVENT_LOG_PATH = OBSERVABILITY_DIR / "pipeline_agent_events.jsonl"
DELIVERY_LOG_PATH = OBSERVABILITY_DIR / "pipeline_agent_delivery_receipts.jsonl"
STATE_PATH = OBSERVABILITY_DIR / "pipeline_agent_pager_state.json"
LOCK_PATH = OBSERVABILITY_DIR / "pipeline_agent_pager.lock"
STATE_VERSION = 1
NOTIFY_ONLY_TARGET = "notify-only"
ALLOWED_EVENT_TYPES = frozenset({
    "phase_b_reviewer_started",
    "recovery_started",
    "recovery_state_changed",
    "recovery_failed",
    "pipeline_hard_fail",
    "commit_ready",
})
ALLOWED_ROUTES = frozenset({"codex", "claude", "both", NOTIFY_ONLY_TARGET})

_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.Lock] = {}


class PipelineAgentPagerError(RuntimeError):
    """Raised when pager event/state handling fails."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_lock(repo_root: Path) -> threading.Lock:
    key = str(repo_root.resolve())
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
        lock_path = self._repo_root / LOCK_PATH
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


def _default_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "events": {},
        "codex_thread_id": None,
        "dispatcher": {
            "active": False,
            "pid": 0,
            "started_at": "",
            "updated_at": "",
        },
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
    state_path = repo_root / STATE_PATH
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
    if not isinstance(merged.get("dispatcher"), dict):
        merged["dispatcher"] = _default_state()["dispatcher"]
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
    _atomic_write_json(repo_root / STATE_PATH, state)


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
    return _load_jsonl_records(repo_root / EVENT_LOG_PATH, label="pager event log")


def _load_delivery_receipts(repo_root: Path) -> list[dict[str, Any]]:
    return _load_jsonl_records(repo_root / DELIVERY_LOG_PATH, label="pager delivery log")


def _append_jsonl_record(path: Path, payload: dict[str, Any], *, label: str) -> None:
    records = _load_jsonl_records(path, label=label)
    records.append(payload)
    _atomic_write_text(path, _serialize_jsonl_records(records))


def _append_event_record(repo_root: Path, event: dict[str, Any]) -> None:
    _append_jsonl_record(repo_root / EVENT_LOG_PATH, event, label="pager event log")


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
        repo_root / DELIVERY_LOG_PATH,
        receipt,
        label="pager delivery log",
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


def _resolve_route(config: dict[str, Any], explicit_route: str | None) -> str:
    route = explicit_route or config.get("pipeline_agent_pager", {}).get("route", NOTIFY_ONLY_TARGET)
    route_text = str(route or "").strip()
    if route_text not in ALLOWED_ROUTES:
        raise PipelineAgentPagerError(f"unsupported pager route: {route_text!r}")
    return route_text


def _configured_route_text(config: dict[str, Any], explicit_route: str | None) -> str:
    route = explicit_route if explicit_route is not None else config.get(
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
        entry.setdefault("attempts", {})
    _refresh_pending_targets(entry)
    return entry


def _refresh_pending_targets(entry: dict[str, Any]) -> None:
    requested = list(entry.get("requested_targets", []))
    delivered = entry.get("delivered_targets", {})
    entry["pending_targets"] = [
        target for target in requested
        if target not in delivered
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


def _set_dispatcher(state: dict[str, Any], *, active: bool) -> None:
    dispatcher = state.setdefault("dispatcher", {})
    dispatcher["active"] = active
    dispatcher["pid"] = os.getpid()
    if active and not dispatcher.get("started_at"):
        dispatcher["started_at"] = _utcnow()
    if not active:
        dispatcher["started_at"] = ""
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
    return "\n".join(lines)


def _excerpt(value: str, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _http_json_post(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8")
            status = getattr(response, "status", 200)
    except (urllib_error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise PipelineAgentPagerError(f"{url} unavailable: {type(exc).__name__}") from exc
    if status < 200 or status >= 300:
        raise PipelineAgentPagerError(f"{url} returned HTTP {status}")
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise PipelineAgentPagerError(f"{url} returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise PipelineAgentPagerError(f"{url} returned non-object JSON")
    return parsed


def _remaining_timeout(deadline: float, *, label: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise PipelineAgentPagerError(f"{label} timed out before acknowledgement")
    return remaining


def _dispatch_codex(
    repo_root: Path,
    event: dict[str, Any],
    state: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    base_url = os.environ.get("RCX_CODEX_APP_SERVER_URL", "http://127.0.0.1:8765").rstrip("/")
    threads_path = os.environ.get("RCX_CODEX_APP_SERVER_THREADS_PATH", "/api/threads")
    turns_template = os.environ.get(
        "RCX_CODEX_APP_SERVER_TURNS_PATH_TEMPLATE",
        "/api/threads/{thread_id}/turns",
    )
    thread_id = str(state.get("codex_thread_id") or "").strip()
    deadline = time.monotonic() + max(timeout_s, 0.001)

    def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = _http_json_post(
            url,
            payload,
            _remaining_timeout(deadline, label="codex pager acknowledgement"),
        )
        _remaining_timeout(deadline, label="codex pager acknowledgement")
        return response

    try:
        if not thread_id:
            created = post_json(
                f"{base_url}{threads_path}",
                {
                    "title": "RCX Pipeline Pager",
                    "source": "pipeline_agent_pager",
                },
            )
            thread_id = str(created.get("thread_id") or created.get("id") or "").strip()
            if not thread_id:
                return {
                    "acknowledged": False,
                    "error": "codex thread create missing thread_id",
                }
        turn_response = post_json(
            f"{base_url}{turns_template.format(thread_id=thread_id)}",
            {
                "prompt": _event_prompt(event),
                "event": event,
                "source": "pipeline_agent_pager",
            },
        )
    except PipelineAgentPagerError as exc:
        return {
            "acknowledged": False,
            "error": str(exc),
            "codex_thread_id": thread_id or None,
        }
    response_thread_id = str(turn_response.get("thread_id") or "").strip()
    turn_id = str(
        turn_response.get("turn_id")
        or turn_response.get("turn_handle")
        or turn_response.get("id")
        or ""
    ).strip()
    if response_thread_id and response_thread_id != thread_id:
        return {
            "acknowledged": False,
            "error": (
                "codex accepted-turn response thread_id "
                f"{response_thread_id!r} did not match requested thread {thread_id!r}"
            ),
            "codex_thread_id": thread_id or None,
        }
    ack_thread_id = response_thread_id or thread_id
    if not ack_thread_id or not turn_id:
        return {
            "acknowledged": False,
            "error": "codex accepted-turn response missing thread_id or turn_id",
            "codex_thread_id": thread_id or None,
        }
    return {
        "acknowledged": True,
        "ack": {
            "acknowledged_at": _utcnow(),
            "thread_id": ack_thread_id,
            "turn_id": turn_id,
            "target": "codex",
        },
        "codex_thread_id": ack_thread_id,
    }


def _dispatch_claude(
    repo_root: Path,
    event: dict[str, Any],
    config: dict[str, Any],
    *,
    timeout_s: float,
) -> dict[str, Any]:
    claude_bin = os.environ.get("RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN", "claude")
    continue_flag = bool(config.get("pipeline_agent_pager", {}).get("claude_continue", False))
    command = [claude_bin]
    if continue_flag:
        command.append("-c")
    command.extend(["-p", _event_prompt(event)])
    try:
        proc = subprocess.run(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
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
    return {
        "acknowledged": True,
        "ack": {
            "acknowledged_at": _utcnow(),
            "exit_code": proc.returncode,
            "target": "claude",
        },
    }


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
            if error_text:
                attempt_record["last_error"] = error_text
            else:
                attempt_record.pop("last_error", None)
            attempt_record.pop("last_receipt_log_warning", None)
            attempts[target] = attempt_record
            if dispatch_result.get("codex_thread_id"):
                state["codex_thread_id"] = dispatch_result["codex_thread_id"]
            receipt_log_warning = ""
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


def dispatch_pending_events(repo_root: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
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


def emit_transition_event(
    repo_root: Path,
    *,
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
    config = load_executor_config(repo_root)
    if not _pager_enabled(config):
        return {
            "enabled": False,
            "route": _configured_route_text(config, route),
            "event_id": None,
            "attempted": [],
            "budget_exhausted": False,
        }
    resolved_route = _resolve_route(config, route)
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
    args = parser.parse_args(argv)
    if not args.dispatch_pending:
        parser.error("specify --dispatch-pending")
    result = dispatch_pending_events(args.repo_root)
    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
