from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mu.tests.tools.module_loader import load_module

_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
pager_mod = load_module(
    "pipeline_agent_pager",
    _TOOLS_DIR / "observability" / "pipeline_agent_pager.py",
)


@pytest.fixture(autouse=True)
def _isolate_live_codex_thread_id(monkeypatch):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)


def _write_config(
    repo_root: Path,
    *,
    enabled: bool = True,
    route: str = "notify-only",
    timeouts: dict[str, int] | None = None,
) -> None:
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline_agent_pager": {
            "enabled": enabled,
            "route": route,
        },
    }
    if timeouts:
        payload["timeouts"] = timeouts
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _event_kwargs(**overrides):
    base = {
        "event_type": "commit_ready",
        "wave_id": "wave-pager",
        "task_id": "[PIPELINE-AGENT-PAGER]",
        "plan_path": "reports/control_plane/pager.md",
        "phase": "phase_b",
        "state": "commit_ready",
        "transition_key": "receipt-1",
        "summary": "commit ready",
        "reason": "receipt validated",
        "artifact_paths": {"receipt": ".agent_bus/meta/pre_commit_receipts/r.json"},
    }
    base.update(overrides)
    return base


def _load_state(repo_root: Path) -> dict:
    return json.loads((repo_root / pager_mod.STATE_PATH).read_text(encoding="utf-8"))


def _load_log(repo_root: Path) -> list[dict]:
    path = repo_root / pager_mod.EVENT_LOG_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_delivery_log(repo_root: Path) -> list[dict]:
    path = repo_root / pager_mod.DELIVERY_LOG_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_skip_log(repo_root: Path) -> list[dict]:
    path = repo_root / pager_mod.SKIP_LOG_PATH
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ack_codex(repo_root, event, state, *, timeout_s):
    """Fake codex dispatch that acknowledges immediately.

    Used by route=both tests to isolate the REAL claude leg
    (``_dispatch_claude``) while keeping codex delivered through the normal
    delivered/receipt flow. Mirrors ``_dispatch_codex``'s success return so the
    codex delivered/pending/retry semantics and receipts stay exercised.
    """
    return {
        "acknowledged": True,
        "ack": {
            "acknowledged_at": "2026-06-01T00:00:00+00:00",
            "thread_id": "thread-codex-1",
            "turn_id": "turn-codex-1",
            "target": "codex",
        },
        "codex_thread_id": "thread-codex-1",
    }


def _write_autoping_state(
    codex_home: Path,
    repo_root: Path,
    thread_id: str,
    *,
    updated_at: str,
    status: str = "waiting_for_prior_ping",
) -> None:
    state_dir = codex_home / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    safe_thread = "".join(ch if ch.isalnum() or ch in "_.-" else "_" for ch in thread_id)
    (state_dir / f"rcx_autoping_{safe_thread}.json").write_text(
        json.dumps(
            {
                "thread_id": thread_id,
                "status": status,
                "updated_at": updated_at,
                "bridge_state": {"wave_root": str(repo_root.resolve())},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _codex_initialize_response(request_id: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"serverInfo": {"name": "codex"}}}


def _codex_thread_response(request_id: int, thread_id: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": {"thread": {"id": thread_id}}}


def _codex_turn_response(request_id: int, *, thread_id: str, turn_id: str | None = None) -> dict:
    payload = {"thread": {"id": thread_id}}
    if turn_id is not None:
        payload["turn"] = {"id": turn_id}
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _codex_error_response(request_id: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"message": message}}


def test_codex_node_bridge_preserves_explicit_empty_params():
    if shutil.which("node") is None:
        pytest.skip("node is required to exercise the Codex websocket bridge")
    requests = [
        {
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "test", "version": "1.0"}},
        },
        {"id": 2, "method": "thread/start", "params": {}},
        {
            "id": 3,
            "method": "turn/start",
            "params": {
                "threadId": {"$from": "2.result.thread.id"},
                "input": [{"type": "text", "text": "pager wake"}],
            },
        },
    ]
    websocket_stub = r"""
class StubWebSocket {
  constructor() {
    this.listeners = {};
    setImmediate(() => this.listeners.open && this.listeners.open());
  }
  addEventListener(name, callback) {
    this.listeners[name] = callback;
  }
  send(raw) {
    const sent = JSON.parse(raw);
    const result = { echo: sent };
    if (sent.method === "thread/start") {
      result.thread = { id: "thread-1" };
    }
    if (sent.method === "turn/start") {
      result.thread = { id: sent.params.threadId };
      result.turn = { id: "turn-1" };
    }
    setImmediate(() => {
      this.listeners.message({
        data: JSON.stringify({ jsonrpc: "2.0", id: sent.id, result }),
      });
    });
  }
  close() {}
}
global.WebSocket = StubWebSocket;
"""

    proc = subprocess.run(
        [
            "node",
            "-e",
            websocket_stub + pager_mod.CODEX_APP_SERVER_NODE_SCRIPT,
            "ws://127.0.0.1:1",
            json.dumps(requests),
            "1000",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert proc.returncode == 0
    payload = json.loads(proc.stdout)
    thread_start = payload["responses"][1]["result"]["echo"]
    assert thread_start["method"] == "thread/start"
    assert thread_start["params"] == {}


def test_event_id_uses_canonical_identity_tuple_and_log_appends_once(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    first = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="first"))
    second = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="second", reason="different summary"))

    assert first["event_id"] == second["event_id"]
    log_entries = _load_log(repo)
    assert len(log_entries) == 1
    assert log_entries[0]["event_id"] == first["event_id"]
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["delivered_targets"][pager_mod.NOTIFY_ONLY_TARGET]["mode"] == pager_mod.NOTIFY_ONLY_TARGET
    assert entry["pending_targets"] == []


def test_lifecycle_event_types_are_accepted_persisted_deduped_and_routed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    lifecycle_event_types = [
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
        "commit_ready",
        "commit_succeeded",
        "commit_failed",
        "commit_held",
        "recovery_started",
        "recovery_state_changed",
        "recovery_escalated",
        "recovery_returned",
        "recovery_succeeded",
        "recovery_failed",
        "pipeline_hard_fail",
        "executor_hard_fail",
    ]

    first_ids = []
    for event_type in lifecycle_event_types:
        first = pager_mod.emit_transition_event(
            repo,
            **_event_kwargs(
                event_type=event_type,
                phase=event_type.split("_", 1)[0],
                state=event_type,
                transition_key=f"{event_type}:transition",
                summary=f"{event_type} summary",
            ),
        )
        second = pager_mod.emit_transition_event(
            repo,
            **_event_kwargs(
                event_type=event_type,
                phase=event_type.split("_", 1)[0],
                state=event_type,
                transition_key=f"{event_type}:transition",
                summary=f"{event_type} duplicate",
            ),
        )
        assert second["event_id"] == first["event_id"]
        first_ids.append(first["event_id"])

    assert len(set(first_ids)) == len(lifecycle_event_types)
    log_entries = _load_log(repo)
    assert len(log_entries) == len(lifecycle_event_types)
    state = _load_state(repo)
    assert set(state["events"]) == set(first_ids)
    for event_id in first_ids:
        entry = state["events"][event_id]
        assert entry["requested_targets"] == [pager_mod.NOTIFY_ONLY_TARGET]
        assert entry["pending_targets"] == []
        assert pager_mod.NOTIFY_ONLY_TARGET in entry["delivered_targets"]


def test_unsupported_lifecycle_event_type_fails_closed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    with pytest.raises(pager_mod.PipelineAgentPagerError, match="unsupported pager event_type"):
        pager_mod.emit_transition_event(
            repo,
            **_event_kwargs(event_type="phase_a_secret_unreviewed_transition"),
        )

    assert _load_log(repo) == []
    assert not (repo / pager_mod.STATE_PATH).exists()


def test_disabled_pager_skips_route_validation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, enabled=False, route="notify-only")

    result = pager_mod.emit_transition_event(repo, route="definitely-invalid", **_event_kwargs())

    assert result == {
        "enabled": False,
        "route": "definitely-invalid",
        "event_id": None,
        "attempted": [],
        "budget_exhausted": False,
    }
    assert not (repo / pager_mod.EVENT_LOG_PATH).exists()
    assert not (repo / pager_mod.STATE_PATH).exists()


def test_truncated_event_log_tail_is_quarantined_and_does_not_brick_dispatch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    log_path = repo / pager_mod.EVENT_LOG_PATH
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text('{"event_id":"truncated"', encoding="utf-8")

    replay = pager_mod.dispatch_pending_events(repo)

    assert replay["enabled"] is True
    assert replay["attempted"] == []
    assert _load_log(repo) == []
    quarantined = sorted(
        (repo / pager_mod.OBSERVABILITY_DIR).glob("pipeline_agent_events.jsonl.corrupt.*")
    )
    assert len(quarantined) == 1
    assert '{"event_id":"truncated"' in quarantined[0].read_text(encoding="utf-8")


def test_both_route_persists_partial_success_and_retries_only_pending_target(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    calls: list[str] = []
    attempts = {"claude": 0}

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        calls.append(target)
        if target == "codex":
            return {
                "acknowledged": True,
                "ack": {"acknowledged_at": "2026-04-17T00:00:00+00:00", "thread_id": "thread-1", "turn_id": "turn-1"},
                "codex_thread_id": "thread-1",
            }
        attempts["claude"] += 1
        if attempts["claude"] == 1:
            return {"acknowledged": False, "error": "claude exited 1"}
        return {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:01+00:00", "exit_code": 0},
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    assert result["enabled"] is True
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == ["claude"]

    replay = pager_mod.dispatch_pending_events(repo)
    assert replay["enabled"] is True
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex", "claude"}
    assert entry["pending_targets"] == []
    assert calls == ["codex", "claude", "claude"]


def test_re_emitting_same_event_under_broader_route_adds_new_pending_target(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    first = pager_mod.emit_transition_event(repo, **_event_kwargs())
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["requested_targets"] == [pager_mod.NOTIFY_ONLY_TARGET]
    assert entry["pending_targets"] == []

    _write_config(repo, route="codex")
    dispatch_calls: list[str] = []

    def pending_codex(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {"acknowledged": False, "error": "codex unavailable"}

    monkeypatch.setattr(pager_mod, "_dispatch_target", pending_codex)

    second = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="reroute to codex"))
    assert second["event_id"] == first["event_id"]
    assert dispatch_calls == ["codex"]
    log_entries = _load_log(repo)
    assert len(log_entries) == 2
    assert [entry["route"] for entry in log_entries] == [pager_mod.NOTIFY_ONLY_TARGET, "codex"]
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["requested_targets"] == [pager_mod.NOTIFY_ONLY_TARGET, "codex"]
    assert entry["pending_targets"] == ["codex"]


def test_broader_route_replay_rebuilds_pending_targets_from_append_only_log(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    first = pager_mod.emit_transition_event(repo, **_event_kwargs())
    _write_config(repo, route="codex")

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda *args, **kwargs: {"acknowledged": False, "error": "codex unavailable"},
    )
    second = pager_mod.emit_transition_event(repo, **_event_kwargs(summary="reroute to codex"))
    assert second["event_id"] == first["event_id"]
    assert len(_load_log(repo)) == 2

    (repo / pager_mod.STATE_PATH).unlink()

    dispatch_calls: list[str] = []

    def ack_codex(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "target": "codex",
            },
            "codex_thread_id": "thread-1",
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", ack_codex)

    replay = pager_mod.dispatch_pending_events(repo)

    assert replay["enabled"] is True
    assert dispatch_calls == ["codex"]
    state = _load_state(repo)
    entry = state["events"][first["event_id"]]
    assert entry["requested_targets"] == [pager_mod.NOTIFY_ONLY_TARGET, "codex"]
    assert set(entry["delivered_targets"]) == {pager_mod.NOTIFY_ONLY_TARGET, "codex"}
    assert entry["pending_targets"] == []
    assert len(_load_delivery_log(repo)) == 2


def test_trigger_budget_exhaustion_leaves_pending_target_durable_for_replay(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(
        repo,
        route="both",
        timeouts={
            "pipeline_agent_pager_trigger": 1,
            "pipeline_agent_pager_codex_ack": 5,
            "pipeline_agent_pager_claude_ack": 5,
        },
    )
    calls: list[str] = []

    def slow_first_target(repo_root, target, event, state, config, *, timeout_s):
        calls.append(target)
        if target == "codex":
            time.sleep(1.1)
            return {
                "acknowledged": True,
                "ack": {"acknowledged_at": "2026-04-17T00:00:00+00:00", "thread_id": "thread-1", "turn_id": "turn-1"},
                "codex_thread_id": "thread-1",
            }
        return {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:01+00:00", "exit_code": 0},
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", slow_first_target)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    assert result["budget_exhausted"] is True
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == ["claude"]

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda repo_root, target, event, state, config, *, timeout_s: {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:02+00:00", "exit_code": 0},
        },
    )
    pager_mod.dispatch_pending_events(repo)
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex", "claude"}
    assert entry["pending_targets"] == []
    assert calls == ["codex"]


def test_dispatcher_state_persists_last_dispatch_provenance(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="notify-only")

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    state = _load_state(repo)
    last_dispatch = state["dispatcher"]["last_dispatch"]
    assert last_dispatch["event_id"] == result["event_id"]
    assert last_dispatch["event_type"] == "commit_ready"
    assert last_dispatch["phase"] == "phase_b"
    assert last_dispatch["state"] == "commit_ready"
    assert last_dispatch["target"] == pager_mod.NOTIFY_ONLY_TARGET
    assert last_dispatch["acknowledged"] is True
    assert last_dispatch["attempted_at"]
    assert last_dispatch["completed_at"]
    assert last_dispatch["summary"] == "commit ready"


def test_overlapping_emit_calls_do_not_duplicate_delivery(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    dispatch_calls = 0
    first_started = threading.Event()

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        nonlocal dispatch_calls
        dispatch_calls += 1
        first_started.set()
        time.sleep(0.2)
        return {
            "acknowledged": True,
            "ack": {"acknowledged_at": "2026-04-17T00:00:00+00:00", "thread_id": "thread-1", "turn_id": "turn-1"},
            "codex_thread_id": "thread-1",
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)
    results = []

    def worker():
        results.append(pager_mod.emit_transition_event(repo, **_event_kwargs()))

    thread_a = threading.Thread(target=worker)
    thread_b = threading.Thread(target=worker)
    thread_a.start()
    assert first_started.wait(timeout=2)
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert len(results) == 2
    assert dispatch_calls == 1
    assert len(_load_log(repo)) == 1


def test_invalid_codex_listener_port_stays_pending_and_reportable(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    monkeypatch.setenv("RCX_CODEX_APP_SERVER_URL", "ws://127.0.0.1:not-a-port")

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["enabled"] is True
    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "RCX_CODEX_APP_SERVER_URL must include a valid websocket port",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["count"] == 1
    assert entry["attempts"]["codex"]["last_error"] == (
        "RCX_CODEX_APP_SERVER_URL must include a valid websocket port"
    )
    assert state["codex_thread_id"] is None
    assert _load_delivery_log(repo) == []


def test_missing_codex_listener_port_stays_pending_without_exchange(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    monkeypatch.setenv("RCX_CODEX_APP_SERVER_URL", "ws://127.0.0.1")

    def unexpected_exchange(url, requests, timeout_s):
        raise AssertionError(f"unexpected exchange attempt for {url}")

    monkeypatch.setattr(
        pager_mod,
        "_codex_app_server_exchange",
        unexpected_exchange,
    )

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["enabled"] is True
    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "RCX_CODEX_APP_SERVER_URL must include a valid websocket port",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["count"] == 1
    assert entry["attempts"]["codex"]["last_error"] == (
        "RCX_CODEX_APP_SERVER_URL must include a valid websocket port"
    )
    assert state["codex_thread_id"] is None
    assert _load_delivery_log(repo) == []


def test_non_loopback_codex_listener_stays_pending_and_reportable(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state setup
    state["codex_thread_id"] = "thread-existing"
    pager_mod._save_state(repo, state)  # ANTICHEAT_OK: direct pager state setup
    monkeypatch.setenv("RCX_CODEX_APP_SERVER_URL", "ws://192.168.1.50:8765")

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "RCX_CODEX_APP_SERVER_URL must target a loopback websocket listener",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["last_error"] == (
        "RCX_CODEX_APP_SERVER_URL must target a loopback websocket listener"
    )
    assert state["codex_thread_id"] == "thread-existing"
    assert _load_delivery_log(repo) == []


def test_unavailable_codex_listener_fallback_failure_stays_pending_and_reportable(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager state setup
    state["codex_thread_id"] = "thread-existing"
    pager_mod._save_state(repo, state)  # ANTICHEAT_OK: direct pager state setup

    def unavailable_exchange(url, requests, timeout_s):
        raise pager_mod.PipelineAgentPagerError(
            f"{url} unavailable: websocket connection failed"
        )

    monkeypatch.setattr(
        pager_mod,
        "_codex_app_server_exchange",
        unavailable_exchange,
    )
    monkeypatch.setattr(
        pager_mod,
        "_dispatch_codex_exec_resume",
        lambda repo_root, event_record, *, thread_id, timeout_s: {
            "acknowledged": False,
            "error": "codex exec resume exited 1: fallback unavailable",
            "codex_thread_id": thread_id,
        },
    )

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    expected_error = (
        "ws://127.0.0.1:8765 unavailable: websocket connection failed; "
        "codex exec resume exited 1: fallback unavailable"
    )

    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": expected_error,
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert entry["delivered_targets"] == {}
    assert entry["pending_targets"] == ["codex"]
    assert entry["attempts"]["codex"]["count"] == 1
    assert entry["attempts"]["codex"]["last_error"] == expected_error
    assert state["codex_thread_id"] == "thread-existing"
    assert _load_delivery_log(repo) == []


def test_codex_ack_requires_accepted_turn_response_fields(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    request_batches: list[list[dict]] = []

    def missing_turn_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        return [
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-1"),
            _codex_turn_response(3, thread_id="thread-1"),
        ]

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=missing_turn_exchange):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert failed["acknowledged"] is False
    assert "missing" in failed["error"]
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "thread/start",
        "turn/start",
    ]
    assert request_batches[0][0]["params"]["clientInfo"] == {
        "name": "pipeline_agent_pager",
        "version": "1.0",
    }
    expected_prompt = getattr(pager_mod, "_event_prompt")(event)
    assert request_batches[0][2]["params"] == {
        "threadId": {"$from": "2.result.thread.id"},
        "input": [{"type": "text", "text": expected_prompt}],
    }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-1"),
            _codex_turn_response(3, thread_id="thread-1", turn_id="turn-1"),
        ],
    ):
        succeeded = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert succeeded["acknowledged"] is True
    assert succeeded["codex_thread_id"] == "thread-1"
    assert succeeded["ack"]["turn_id"] == "turn-1"

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-1"),
            {"jsonrpc": "2.0", "id": 3, "result": {"turn": {"id": "turn-1"}}},
        ],
    ):
        turn_only = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert turn_only["acknowledged"] is True
    assert turn_only["codex_thread_id"] == "thread-1"
    assert turn_only["ack"]["thread_id"] == "thread-1"
    assert turn_only["ack"]["turn_id"] == "turn-1"


def test_codex_ack_rejects_mismatched_thread_id(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-expected"),
            _codex_turn_response(3, thread_id="thread-other", turn_id="turn-1"),
        ],
    ):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert "did not match requested thread" in failed["error"]
    assert failed["codex_thread_id"] == "thread-expected"


def test_codex_app_server_dispatch_prefers_live_thread_over_stored_thread(tmp_path, monkeypatch):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))
    request_batches: list[list[dict]] = []

    def fake_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        return [
            _codex_initialize_response(1),
            _codex_turn_response(2, thread_id="thread-live", turn_id="turn-1"),
        ]

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=fake_exchange):
        result = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    assert result["codex_thread_id"] == "thread-live"
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "turn/start",
    ]
    assert request_batches[0][1]["params"]["threadId"] == "thread-live"


def test_codex_app_server_failure_falls_back_to_exec_resume_for_live_thread(tmp_path, monkeypatch):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["repo_root"] = repo_root
        seen["event_id"] = event_record["event_id"]
        seen["thread_id"] = thread_id
        seen["timeout_s"] = timeout_s
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError("ws://127.0.0.1:8765 unavailable: HTTPError"),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=fake_exec_resume,
    ):
        fallback = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert fallback["acknowledged"] is True
    assert fallback["ack"]["mode"] == "exec_resume"
    assert fallback["codex_thread_id"] == "thread-live"
    assert seen["thread_id"] == "thread-live"
    assert seen["event_id"] == event["event_id"]


def test_codex_node_websocket_unavailable_falls_back_to_exec_resume_for_live_thread(
    tmp_path, monkeypatch
):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_node_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout='{"error":"node WebSocket unavailable"}',
            stderr="",
        )

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["thread_id"] = thread_id
        seen["timeout_s"] = timeout_s
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    monkeypatch.setattr(pager_mod.subprocess, "run", fake_node_run)
    monkeypatch.setattr(pager_mod, "_dispatch_codex_exec_resume", fake_exec_resume)

    fallback = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert fallback["acknowledged"] is True
    assert fallback["ack"]["mode"] == "exec_resume"
    assert fallback["codex_thread_id"] == "thread-live"
    assert seen["thread_id"] == "thread-live"
    assert seen["timeout_s"] > 0


def test_codex_app_server_fallback_returns_failure_when_timeout_is_exhausted(
    tmp_path,
    monkeypatch,
):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_exchange(url, requests, timeout_s):
        time.sleep(0.01)
        raise pager_mod.PipelineAgentPagerError(
            "ws://127.0.0.1:8765 unavailable: HTTPError"
        )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=fake_exchange,
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=AssertionError("exhausted timeout must not launch fallback"),
    ):
        result = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=0.001)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert result["codex_thread_id"] == "thread-live"
    assert "unavailable" in result["error"]
    assert "timed out before acknowledgement" in result["error"]


def test_event_prompt_forbids_headless_pipeline_relaunch():
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager prompt contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    prompt = pager_mod._event_prompt(event)  # ANTICHEAT_OK: direct pager prompt contract test

    assert "Do not run shell commands" in prompt
    assert "Do not edit files" in prompt
    assert "Do not launch or relaunch executor_dispatch.py" in prompt
    assert "foreground restart to the operator-visible pipeline surface" in prompt

def test_codex_thread_start_requires_explicit_thread_id_field(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        return_value=[
            _codex_initialize_response(1),
            {"jsonrpc": "2.0", "id": 2, "result": {"id": "not-a-thread-id"}},
            _codex_turn_response(3, thread_id="thread-ignored", turn_id="turn-1"),
        ],
    ):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert failed["error"] == "codex thread create missing thread_id"
    assert failed["codex_thread_id"] is None


def test_codex_stale_thread_reseeds_on_explicit_error(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    request_batches: list[list[dict]] = []

    def fake_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        if len(request_batches) == 1:
            return [
                _codex_initialize_response(1),
                _codex_error_response(2, "thread not found: thread-stale"),
            ]
        return [
            _codex_initialize_response(1),
            _codex_thread_response(2, "thread-fresh"),
            _codex_turn_response(3, thread_id="thread-fresh", turn_id="turn-1"),
        ]

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=fake_exchange):
        succeeded = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert succeeded["acknowledged"] is True
    assert succeeded["codex_thread_id"] == "thread-fresh"
    assert succeeded["ack"]["thread_id"] == "thread-fresh"
    assert succeeded["ack"]["turn_id"] == "turn-1"
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "turn/start",
    ]
    expected_prompt = getattr(pager_mod, "_event_prompt")(event)
    assert request_batches[0][1]["params"] == {
        "threadId": "thread-stale",
        "input": [{"type": "text", "text": expected_prompt}],
    }
    assert [request["method"] for request in request_batches[1]] == [
        "initialize",
        "thread/start",
        "turn/start",
    ]


def test_codex_exec_resume_fallback_prefers_live_thread_over_stored_thread(tmp_path, monkeypatch):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-live")

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["repo_root"] = repo_root
        seen["event_id"] = event_record["event_id"]
        seen["thread_id"] = thread_id
        seen["timeout_s"] = timeout_s
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError("ws://127.0.0.1:8765 unavailable: HTTPError"),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=fake_exec_resume,
    ):
        result = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    assert result["codex_thread_id"] == "thread-live"
    assert result["ack"]["mode"] == "exec_resume"
    assert seen["thread_id"] == "thread-live"


def test_codex_exec_resume_fallback_uses_autoping_thread_when_env_missing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    codex_home = tmp_path / "codex-home"
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-live",
        updated_at="2026-04-24T18:48:05+00:00",
    )
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    seen: dict[str, object] = {}

    def fake_exec_resume(repo_root, event_record, *, thread_id, timeout_s):
        seen["thread_id"] = thread_id
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": thread_id,
                "target": "codex",
                "mode": "exec_resume",
                "pid": 12345,
            },
            "codex_thread_id": thread_id,
        }

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError("ws://127.0.0.1:8765 unavailable: HTTPError"),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=fake_exec_resume,
    ):
        result = pager_mod._dispatch_codex(repo, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    assert result["codex_thread_id"] == "thread-live"
    assert seen["thread_id"] == "thread-live"


def test_codex_exec_resume_fallback_skips_paused_context_exhausted_autoping_thread(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    codex_home = tmp_path / "codex-home"
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-exhausted",
        updated_at="2026-04-24T18:48:05+00:00",
        status="context_exhausted_paused",
    )
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError(
            "ws://127.0.0.1:8765 unavailable: HTTPError"
        ),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=AssertionError("exhausted autoping thread must not be resumed"),
    ):
        result = pager_mod._dispatch_codex(repo, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert "unavailable" in result["error"]


def test_codex_exec_resume_fallback_skips_paused_context_exhausted_env_thread(
    tmp_path,
    monkeypatch,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    codex_home = tmp_path / "codex-home"
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-exhausted")
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-exhausted",
        updated_at="2026-04-24T18:48:05+00:00",
        status="context_exhausted_paused",
    )
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-exhausted"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_codex_app_server_exchange",
        side_effect=pager_mod.PipelineAgentPagerError(
            "ws://127.0.0.1:8765 unavailable: HTTPError"
        ),
    ), patch.object(
        pager_mod,
        "_dispatch_codex_exec_resume",
        side_effect=AssertionError("exhausted ambient thread must not be resumed"),
    ):
        result = pager_mod._dispatch_codex(repo, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert "unavailable" in result["error"]


def test_replay_prefers_autoping_thread_over_stale_delivery_receipt(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    codex_home = tmp_path / "codex-home"
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("RCX_CODEX_HOME", str(codex_home))
    _write_autoping_state(
        codex_home,
        repo,
        "thread-live",
        updated_at="2026-04-24T18:48:05+00:00",
    )
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager state reconciliation test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    event_log_path = repo / pager_mod.EVENT_LOG_PATH
    event_log_path.parent.mkdir(parents=True, exist_ok=True)
    event_log_path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    delivery_path = repo / pager_mod.DELIVERY_LOG_PATH
    delivery_path.write_text(
        json.dumps(
            {
                "event_id": event["event_id"],
                "target": "codex",
                "ack": {
                    "acknowledged_at": "2026-04-24T18:47:07+00:00",
                    "target": "codex",
                    "thread_id": "thread-stale",
                },
                "codex_thread_id": "thread-stale",
                "recorded_at": "2026-04-24T18:47:07+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    replay = pager_mod.dispatch_pending_events(repo)

    assert replay["attempted"] == []
    state = _load_state(repo)
    assert state["codex_thread_id"] == "thread-live"
    entry = state["events"][event["event_id"]]
    assert entry["pending_targets"] == []


def test_codex_exec_resume_env_preserves_live_codex_environment(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("CODEX_HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("RCX_CODEX_HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("KEEP_ME", "yes")

    env = pager_mod._codex_exec_resume_env()  # ANTICHEAT_OK: direct pager adapter contract test

    assert env["HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["CODEX_HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["RCX_CODEX_HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["KEEP_ME"] == "yes"


def test_codex_exec_resume_command_uses_read_only_sandbox_without_bypass():
    command = pager_mod._codex_exec_resume_command(  # ANTICHEAT_OK: pager argv contract test
        "codex-bin",
        "thread-live",
        "wake prompt",
    )

    assert command[:3] == [
        "codex-bin",
        "exec",
        "resume",
    ]
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    disabled_features = {
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--disable"
    }
    assert disabled_features == set(pager_mod.CODEX_NO_TOOLS_DISABLED_FEATURES)
    assert 'sandbox_mode="read-only"' in command
    assert 'approval_policy="never"' in command
    assert command[-2:] == ["thread-live", "wake prompt"]
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_codex_exec_resume_requires_success_before_acknowledgement(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    terminated: list[int] = []

    class RunningPopen:
        pid = 4242

        def __init__(self, *args, **kwargs):
            pass

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(["codex"], timeout)

    monkeypatch.setattr(pager_mod.subprocess, "Popen", RunningPopen)
    monkeypatch.setattr(
        pager_mod,
        "_terminate_process_group",
        lambda proc: terminated.append(proc.pid),
    )

    result = pager_mod._dispatch_codex_exec_resume(  # ANTICHEAT_OK: direct pager adapter contract test
        repo,
        event,
        thread_id="thread-live",
        timeout_s=0.01,
    )

    assert result["acknowledged"] is False
    assert result["codex_thread_id"] == "thread-live"
    assert "timed out" in result["error"]
    assert terminated == [4242]


def test_codex_exec_resume_acknowledges_only_zero_exit(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    class SuccessfulPopen:
        pid = 4243

        def __init__(self, *args, **kwargs):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(pager_mod.subprocess, "Popen", SuccessfulPopen)

    result = pager_mod._dispatch_codex_exec_resume(  # ANTICHEAT_OK: direct pager adapter contract test
        repo,
        event,
        thread_id="thread-live",
        timeout_s=0.01,
    )

    assert result["acknowledged"] is True
    assert result["ack"]["mode"] == "exec_resume"
    assert result["ack"]["thread_id"] == "thread-live"
    assert result["ack"]["pid"] == 4243


def test_replay_uses_delivery_receipt_log_after_state_persist_crash(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")

    dispatch_calls: list[str] = []

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "target": "codex",
            },
            "codex_thread_id": "thread-1",
        }

    original_save_state = pager_mod._save_state  # ANTICHEAT_OK: crash-window regression harness
    save_calls = {"count": 0}

    def crashing_save_state(repo_root, state):
        save_calls["count"] += 1
        if save_calls["count"] >= 3:
            raise RuntimeError("simulated crash during pager state persist")
        return original_save_state(repo_root, state)

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)
    monkeypatch.setattr(pager_mod, "_save_state", crashing_save_state)

    try:
        pager_mod.emit_transition_event(repo, **_event_kwargs())
    except RuntimeError as exc:
        assert "simulated crash" in str(exc)
    else:
        raise AssertionError("emit_transition_event should fail during simulated crash")

    state = _load_state(repo)
    event_id = next(iter(state["events"]))
    assert set(state["events"][event_id]["delivered_targets"]) == {"codex"}
    assert state["events"][event_id]["pending_targets"] == []
    receipts = _load_delivery_log(repo)
    assert len(receipts) == 1
    assert receipts[0]["event_id"] == event_id
    assert receipts[0]["target"] == "codex"

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("codex should not be redelivered")),
    )
    monkeypatch.setattr(pager_mod, "_save_state", original_save_state)

    replay = pager_mod.dispatch_pending_events(repo)
    assert replay["attempted"] == []
    state = _load_state(repo)
    entry = state["events"][event_id]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []
    assert state["codex_thread_id"] == "thread-1"
    assert dispatch_calls == ["codex"]


def test_receipt_log_failure_after_ack_does_not_redeliver_same_event(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")

    dispatch_calls: list[str] = []

    def fake_dispatch(repo_root, target, event, state, config, *, timeout_s):
        dispatch_calls.append(target)
        return {
            "acknowledged": True,
            "ack": {
                "acknowledged_at": "2026-04-17T00:00:00+00:00",
                "thread_id": "thread-1",
                "turn_id": "turn-1",
                "target": "codex",
            },
            "codex_thread_id": "thread-1",
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", fake_dispatch)
    monkeypatch.setattr(
        pager_mod,
        "_append_delivery_receipt",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("simulated crash after target ACK but before durable receipt append")
        ),
    )

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    assert result["attempted"][0]["acknowledged"] is True
    assert "simulated crash" in result["attempted"][0]["receipt_log_warning"]

    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []
    assert _load_delivery_log(repo) == []

    monkeypatch.setattr(
        pager_mod,
        "_dispatch_target",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("codex should not be redelivered")
        ),
    )

    replay = pager_mod.dispatch_pending_events(repo)
    assert replay["attempted"] == []
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []
    assert dispatch_calls == ["codex"]


def test_codex_ack_budget_is_shared_across_stale_thread_reseed(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    state["codex_thread_id"] = "thread-stale"
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    calls: list[float] = []
    request_batches: list[list[dict]] = []

    def fake_exchange(url, requests, timeout_s):
        request_batches.append(requests)
        calls.append(timeout_s)
        if len(calls) == 1:
            time.sleep(0.12)
            return [
                _codex_initialize_response(1),
                _codex_error_response(2, "no rollout found for thread id thread-stale"),
            ]
        raise pager_mod.PipelineAgentPagerError(
            f"second codex exchange exceeded remaining budget ({timeout_s:.3f}s)"
        )

    with patch.object(pager_mod, "_codex_app_server_exchange", side_effect=fake_exchange):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=0.2)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert "remaining budget" in failed["error"]
    assert len(calls) == 2
    assert calls[0] <= 0.2
    assert calls[1] < calls[0]
    assert [request["method"] for request in request_batches[0]] == [
        "initialize",
        "turn/start",
    ]
    assert [request["method"] for request in request_batches[1]] == [
        "initialize",
        "thread/start",
        "turn/start",
    ]


def test_emit_transition_event_clears_stale_codex_thread_id_when_dispatch_requests_it(
    tmp_path, monkeypatch
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="codex")
    state = pager_mod._default_state()  # ANTICHEAT_OK: state persistence regression
    state["codex_thread_id"] = "thread-dead"
    pager_mod._save_state(repo, state)  # ANTICHEAT_OK: direct pager state setup

    def stale_thread_failure(repo_root, target, event, state, config, *, timeout_s):
        assert state["codex_thread_id"] == "thread-dead"
        return {
            "acknowledged": False,
            "error": "thread not found: thread-dead",
            "codex_thread_id": None,
            "clear_codex_thread_id": True,
        }

    monkeypatch.setattr(pager_mod, "_dispatch_target", stale_thread_failure)

    result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["attempted"] == [
        {
            "event_id": result["event_id"],
            "target": "codex",
            "acknowledged": False,
            "error": "thread not found: thread-dead",
            "receipt_log_warning": "",
        }
    ]
    state = _load_state(repo)
    assert state["codex_thread_id"] is None
    entry = state["events"][result["event_id"]]
    assert entry["pending_targets"] == ["codex"]


def test_claude_ack_requires_zero_exit(tmp_path):
    # The dedicated monitor session id must be present (and != live) for the
    # subprocess leg to run at all; a valid monitor exercises exit-code handling.
    repo = tmp_path / "repo"
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-monitor-ack", encoding="utf-8")
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )
    config: dict = {}

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude", "--resume"], 1, "", "no auth"),
    ):
        failed = pager_mod._dispatch_claude(repo, event, config, timeout_s=5)  # ANTICHEAT_OK
    assert failed["acknowledged"] is False
    assert "exited 1" in failed["error"]
    assert not failed.get("skipped")

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude", "--resume"], 0, "ok", ""),
    ):
        succeeded = pager_mod._dispatch_claude(repo, event, config, timeout_s=5)  # ANTICHEAT_OK
    assert succeeded["acknowledged"] is True
    assert succeeded["ack"]["target"] == "claude"
    assert succeeded["ack"]["session_id"] == "sess-monitor-ack"


def test_dispatch_claude_resumes_dedicated_monitor_distinct_from_live(tmp_path):
    repo = tmp_path / "repo"
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-monitor-01", encoding="utf-8")
    # Live orchestrator id present AND DISTINCT: the resume target must be the
    # dedicated monitor, never the live orchestrator session.
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.write_text("sess-live-99", encoding="utf-8")

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude"], 0, "ok", ""),
    ) as run_mock:
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    argv = run_mock.call_args.args[0]
    expected_prompt = pager_mod._event_prompt(event)  # ANTICHEAT_OK: argv expectation
    assert argv == [
        "claude",
        "--resume",
        "sess-monitor-01",
        "-p",
        expected_prompt,
    ]
    # Never resumes the live orchestrator session.
    assert "sess-live-99" not in argv
    assert "-c" not in argv
    assert "--continue" not in argv


def test_dispatch_claude_argv_strips_trailing_newline_on_monitor_session_id(tmp_path):
    repo = tmp_path / "repo"
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-trailing-nl\n", encoding="utf-8")

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude"], 0, "ok", ""),
    ) as run_mock:
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is True
    argv = run_mock.call_args.args[0]
    expected_prompt = pager_mod._event_prompt(event)  # ANTICHEAT_OK: argv expectation
    assert argv == [
        "claude",
        "--resume",
        "sess-trailing-nl",
        "-p",
        expected_prompt,
    ]


def test_dispatch_claude_fails_closed_when_monitor_absent_even_if_live_present(tmp_path):
    # THE core regression: with the live orchestrator id present but no dedicated
    # monitor file, the pre-fix code resumed the LIVE session. The locked design
    # MUST fail closed -- issue no subprocess and never target the live session.
    repo = tmp_path / "repo"
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.parent.mkdir(parents=True, exist_ok=True)
    live_path.write_text("sess-live-only", encoding="utf-8")

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(pager_mod.subprocess, "run") as run_mock:
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert result["skipped"] is True
    assert result["skip_reason"] == pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET
    assert "error" not in result
    run_mock.assert_not_called()


@pytest.mark.parametrize(
    "monitor_bytes",
    [
        b"",            # empty
        b"  \n\t \n",   # whitespace-only
        b"sess abc\n",  # internal whitespace
        b"\xff\xfe",    # non-UTF-8 bytes (UnicodeDecodeError, not OSError)
    ],
)
def test_dispatch_claude_fails_closed_when_monitor_malformed(tmp_path, monitor_bytes):
    repo = tmp_path / "repo"
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_bytes(monitor_bytes)
    # A live id is also present to prove malformed-monitor never resumes live.
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.write_text("sess-live-present", encoding="utf-8")

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(pager_mod.subprocess, "run") as run_mock:
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert result["skipped"] is True
    assert result["skip_reason"] == pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET
    run_mock.assert_not_called()


def test_dispatch_claude_fails_closed_when_monitor_equals_live(tmp_path):
    repo = tmp_path / "repo"
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-collision", encoding="utf-8")
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.write_text("sess-collision", encoding="utf-8")

    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(pager_mod.subprocess, "run") as run_mock:
        result = pager_mod._dispatch_claude(repo, event, {}, timeout_s=5)  # ANTICHEAT_OK

    assert result["acknowledged"] is False
    assert result["skipped"] is True
    assert result["skip_reason"] == pager_mod.CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE
    # Never pages the live conversation.
    run_mock.assert_not_called()


def test_emit_transition_event_routes_claude_through_real_dispatch_target(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="claude")

    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-monitor-claude-01", encoding="utf-8")
    # Distinct live orchestrator id present to prove the resume targets the
    # dedicated monitor, never the live session.
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.write_text("sess-live-claude-99", encoding="utf-8")

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude"], 0, "ok", ""),
    ) as run_mock:
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["enabled"] is True
    assert result["route"] == "claude"
    assert len(result["attempted"]) == 1
    assert result["attempted"][0]["target"] == "claude"
    assert result["attempted"][0]["acknowledged"] is True

    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    assert "claude" in entry["delivered_targets"]
    assert entry["delivered_targets"]["claude"]["target"] == "claude"
    assert entry["delivered_targets"]["claude"]["session_id"] == "sess-monitor-claude-01"
    assert entry["pending_targets"] == []
    assert entry.get("skipped_targets", {}) == {}

    log_events = _load_log(repo)
    assert len(log_events) == 1
    expected_prompt = pager_mod._event_prompt(log_events[0])  # ANTICHEAT_OK: argv expectation
    argv = run_mock.call_args.args[0]
    assert argv == [
        "claude",
        "--resume",
        "sess-monitor-claude-01",
        "-p",
        expected_prompt,
    ]
    assert "sess-live-claude-99" not in argv


def test_both_route_happy_path_delivers_claude_to_dedicated_monitor(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))

    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    monitor_path.parent.mkdir(parents=True, exist_ok=True)
    monitor_path.write_text("sess-monitor-both", encoding="utf-8")
    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.write_text("sess-live-both", encoding="utf-8")

    # Fake codex so it acks through the normal delivered/receipt flow; run the
    # REAL claude leg (_dispatch_claude) against the dedicated monitor.
    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude"], 0, "ok", ""),
    ) as run_mock:
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())

    assert result["enabled"] is True
    state = _load_state(repo)
    entry = state["events"][result["event_id"]]
    # (a) route=both reaches a claude target whose id != the live orchestrator id.
    assert set(entry["delivered_targets"]) == {"codex", "claude"}
    assert entry["delivered_targets"]["claude"]["session_id"] == "sess-monitor-both"
    assert entry["pending_targets"] == []
    assert entry.get("skipped_targets", {}) == {}

    delivery = _load_delivery_log(repo)
    assert len([r for r in delivery if r["target"] == "claude"]) == 1
    assert _load_skip_log(repo) == []

    argv = run_mock.call_args.args[0]
    assert argv[:3] == ["claude", "--resume", "sess-monitor-both"]
    assert "sess-live-both" not in argv


@pytest.mark.parametrize(
    "setup, expected_reason",
    [
        ("missing", pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET),
        ("empty", pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET),
        ("internal_ws", pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET),
        ("non_utf8", pager_mod.CLAUDE_SKIP_REASON_MONITOR_UNSET),
        ("equals_live", pager_mod.CLAUDE_SKIP_REASON_MONITOR_EQUALS_LIVE),
    ],
)
def test_both_route_fail_closed_records_distinct_skip_and_does_not_retry(
    tmp_path, monkeypatch, setup, expected_reason
):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))

    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.parent.mkdir(parents=True, exist_ok=True)
    live_path.write_text("sess-live-x", encoding="utf-8")
    monitor_path = repo / pager_mod.CLAUDE_MONITOR_SESSION_ID_PATH
    if setup == "missing":
        pass  # no monitor file
    elif setup == "empty":
        monitor_path.write_text("", encoding="utf-8")
    elif setup == "internal_ws":
        monitor_path.write_text("sess monitor x\n", encoding="utf-8")
    elif setup == "non_utf8":
        monitor_path.write_bytes(b"\xff\xfe")
    elif setup == "equals_live":
        monitor_path.write_text("sess-live-x", encoding="utf-8")

    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    with patch.object(pager_mod.subprocess, "run") as run_mock:
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    # No claude --resume issued (codex is faked above subprocess; claude fails closed).
    run_mock.assert_not_called()
    event_id = result["event_id"]

    state = _load_state(repo)
    entry = state["events"][event_id]
    # codex delivered normally; claude parked as a DISTINCT skip.
    assert set(entry["delivered_targets"]) == {"codex"}
    assert "claude" not in entry["delivered_targets"]
    assert "claude" in entry["skipped_targets"]
    assert entry["skipped_targets"]["claude"]["skip_reason"] == expected_reason
    assert entry["pending_targets"] == []
    assert entry["attempts"]["claude"]["last_skip_reason"] == expected_reason

    # No claude delivery receipt; a distinct skip receipt instead.
    delivery = _load_delivery_log(repo)
    assert [r for r in delivery if r["target"] == "claude"] == []
    skip_receipts = _load_skip_log(repo)
    assert len(skip_receipts) == 1
    assert skip_receipts[0]["target"] == "claude"
    assert skip_receipts[0]["event_id"] == event_id
    assert skip_receipts[0]["skip_reason"] == expected_reason

    # (e) codex unchanged: codex delivered with a normal delivery receipt.
    assert len([r for r in delivery if r["target"] == "codex"]) == 1

    # A SECOND dispatch must NOT re-attempt the claude leg (terminal skip) and
    # must not re-attempt codex either -- neither falsely delivered nor retried.
    with patch.object(pager_mod.subprocess, "run") as run_mock2:
        replay = pager_mod.dispatch_pending_events(repo)
    run_mock2.assert_not_called()
    assert replay["attempted"] == []

    state2 = _load_state(repo)
    entry2 = state2["events"][event_id]
    assert "claude" not in entry2["delivered_targets"]
    assert "claude" in entry2["skipped_targets"]
    assert entry2["pending_targets"] == []
    # Receipts not duplicated on replay.
    assert len(_load_skip_log(repo)) == 1
    assert len([r for r in _load_delivery_log(repo) if r["target"] == "claude"]) == 0


def test_claude_skip_is_terminal_after_state_rebuild_from_logs(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="both")
    monkeypatch.setenv("RCX_CODEX_HOME", str(tmp_path / "codex-home"))

    live_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    live_path.parent.mkdir(parents=True, exist_ok=True)
    live_path.write_text("sess-live-term", encoding="utf-8")
    # Dedicated monitor deliberately absent -> claude fails closed.

    monkeypatch.setattr(pager_mod, "_dispatch_codex", _ack_codex)

    with patch.object(pager_mod.subprocess, "run") as run_mock:
        result = pager_mod.emit_transition_event(repo, **_event_kwargs())
    run_mock.assert_not_called()
    event_id = result["event_id"]

    # Drop the durable state json; force a rebuild purely from append-only logs.
    (repo / pager_mod.STATE_PATH).unlink()

    with patch.object(pager_mod.subprocess, "run") as run_mock2:
        replay = pager_mod.dispatch_pending_events(repo)
    run_mock2.assert_not_called()
    assert replay["attempted"] == []

    state = _load_state(repo)
    entry = state["events"][event_id]
    # The skip receipt rebuilds skipped_targets; the codex receipt rebuilds delivered.
    assert "claude" in entry["skipped_targets"]
    assert "claude" not in entry["delivered_targets"]
    assert set(entry["delivered_targets"]) == {"codex"}
    assert entry["pending_targets"] == []


def test_session_start_hook_writes_orchestrator_session_id_for_pager_read(tmp_path):
    """K-2 pager-session-id-autowrite regression: the new
    .claude/hooks/session-start.sh SessionStart hook writes the active
    session id to <repo_root>/.agent_bus/observability/orchestrator_session_id
    so the pager's reader at pipeline_agent_pager.py:656 resolves it for
    `claude --resume <id>` dispatch. This integration test exercises the
    hook AND the pager's reader end-to-end (no mocks).
    """
    repo_root = Path(__file__).resolve().parents[3]
    hook_path = repo_root / ".claude" / "hooks" / "session-start.sh"
    assert hook_path.exists(), f"hook script missing at {hook_path}"

    session_id = "1e9c6188-11d3-4cbb-87eb-399699e72bcc"
    payload = json.dumps({
        "session_id": session_id,
        "hook_event_name": "SessionStart",
        "source": "startup",
    })

    env = {
        "PATH": "/usr/bin:/bin:/usr/local/bin",
        "HOME": str(tmp_path),
        "CLAUDE_PROJECT_DIR": str(tmp_path),
    }
    result = subprocess.run(
        ["bash", str(hook_path)],
        input=payload,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"hook exit={result.returncode} stderr={result.stderr!r}"
    )

    target = tmp_path / ".agent_bus" / "observability" / "orchestrator_session_id"
    assert target.exists(), f"hook did not write {target}"
    assert target.read_text().strip() == session_id

    resolved = pager_mod._read_orchestrator_session_id(tmp_path)  # ANTICHEAT_OK: integration read
    assert resolved == session_id

    malformed_cases = [
        '{"not_session_id":"x"}',
        '{"session_id":""}',
        '{"session_id":"has space"}',
        'not valid json',
    ]
    for payload_bad in malformed_cases:
        clean_root = tmp_path / f"clean_{abs(hash(payload_bad))}"
        clean_root.mkdir(parents=True, exist_ok=True)
        env_clean = {**env, "CLAUDE_PROJECT_DIR": str(clean_root)}
        r = subprocess.run(
            ["bash", str(hook_path)],
            input=payload_bad,
            env=env_clean,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        assert r.returncode == 0, f"hook should fail-open on {payload_bad!r}, got exit={r.returncode}"
        bad_target = clean_root / ".agent_bus" / "observability" / "orchestrator_session_id"
        assert not bad_target.exists(), (
            f"hook wrote file for malformed payload {payload_bad!r}: "
            f"{bad_target.read_text() if bad_target.exists() else '<missing>'}"
        )


def test_codex_exec_resume_env_preserves_rcx_overlay_when_present(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/real-home")
    monkeypatch.setenv("CODEX_HOME", "/tmp/real-codex-home")
    monkeypatch.setenv("RCX_CODEX_HOME", "/tmp/rcx-overlay")

    env = pager_mod._codex_exec_resume_env()  # ANTICHEAT_OK: tool unit test

    assert env["HOME"] == "/tmp/real-home"
    assert env["CODEX_HOME"] == "/tmp/real-codex-home"
    assert env["RCX_CODEX_HOME"] == "/tmp/rcx-overlay"
