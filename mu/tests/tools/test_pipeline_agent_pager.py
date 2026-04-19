from __future__ import annotations

import json
import subprocess
import threading
import time
from pathlib import Path
from unittest.mock import patch

from mu.tests.tools.module_loader import load_module

_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
pager_mod = load_module(
    "pipeline_agent_pager",
    _TOOLS_DIR / "observability" / "pipeline_agent_pager.py",
)


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


def test_codex_ack_requires_accepted_turn_response_fields(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_http_json_post",
        side_effect=[
            {"thread_id": "thread-1"},
            {"thread_id": "thread-1"},
        ],
    ):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert failed["acknowledged"] is False
    assert "missing" in failed["error"]

    with patch.object(
        pager_mod,
        "_http_json_post",
        side_effect=[
            {"thread_id": "thread-1"},
            {"thread_id": "thread-1", "turn_id": "turn-1"},
        ],
    ):
        succeeded = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK
    assert succeeded["acknowledged"] is True
    assert succeeded["codex_thread_id"] == "thread-1"
    assert succeeded["ack"]["turn_id"] == "turn-1"


def test_codex_ack_rejects_mismatched_thread_id(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )

    with patch.object(
        pager_mod,
        "_http_json_post",
        side_effect=[
            {"thread_id": "thread-expected"},
            {"thread_id": "thread-other", "turn_id": "turn-1"},
        ],
    ):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=5)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert "did not match requested thread" in failed["error"]
    assert failed["codex_thread_id"] == "thread-expected"


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


def test_codex_ack_budget_is_shared_across_thread_create_and_turn_submit(tmp_path):
    state = pager_mod._default_state()  # ANTICHEAT_OK: direct pager adapter contract test
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="codex",
        metadata=None,
        **_event_kwargs(),
    )
    calls: list[float] = []

    def fake_post(url, payload, timeout_s):
        calls.append(timeout_s)
        if len(calls) == 1:
            time.sleep(0.12)
            return {"thread_id": "thread-1"}
        raise pager_mod.PipelineAgentPagerError(
            f"second codex call exceeded remaining budget ({timeout_s:.3f}s)"
        )

    with patch.object(pager_mod, "_http_json_post", side_effect=fake_post):
        failed = pager_mod._dispatch_codex(tmp_path, event, state, timeout_s=0.2)  # ANTICHEAT_OK

    assert failed["acknowledged"] is False
    assert "remaining budget" in failed["error"]
    assert len(calls) == 2
    assert calls[0] <= 0.2
    assert calls[1] < calls[0]


def test_claude_ack_requires_zero_exit(tmp_path):
    event = pager_mod._build_event_record(  # ANTICHEAT_OK: direct pager adapter contract test
        route="claude",
        metadata=None,
        **_event_kwargs(),
    )
    config: dict = {}

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude", "-p"], 1, "", "no auth"),
    ):
        failed = pager_mod._dispatch_claude(tmp_path, event, config, timeout_s=5)  # ANTICHEAT_OK
    assert failed["acknowledged"] is False
    assert "exited 1" in failed["error"]

    with patch.object(
        pager_mod.subprocess,
        "run",
        return_value=subprocess.CompletedProcess(["claude", "-p"], 0, "ok", ""),
    ):
        succeeded = pager_mod._dispatch_claude(tmp_path, event, config, timeout_s=5)  # ANTICHEAT_OK
    assert succeeded["acknowledged"] is True
    assert succeeded["ack"]["target"] == "claude"


def test_dispatch_claude_argv_uses_resume_when_session_id_present(tmp_path):
    repo = tmp_path / "repo"
    session_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("sess-deterministic-01", encoding="utf-8")

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
        "sess-deterministic-01",
        "-p",
        expected_prompt,
    ]
    assert "-c" not in argv
    assert "--continue" not in argv


def test_dispatch_claude_argv_is_plain_p_when_session_id_absent(tmp_path):
    repo = tmp_path / "repo"
    # Deliberately do not create the session-id file — current repo state.
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
    # Pins PR #794 bot P1 remediation: argv is deterministic plain `-p`, no -c / --continue / --resume.
    assert argv == ["claude", "-p", expected_prompt]
    assert "-c" not in argv
    assert "--continue" not in argv
    assert "--resume" not in argv


def test_dispatch_claude_argv_falls_back_when_session_id_empty(tmp_path):
    repo = tmp_path / "repo"
    session_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("", encoding="utf-8")

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
    assert argv == ["claude", "-p", expected_prompt]
    assert "--resume" not in argv
    assert "-c" not in argv
    assert "--continue" not in argv


def test_dispatch_claude_argv_falls_back_when_session_id_whitespace_only(tmp_path):
    repo = tmp_path / "repo"
    session_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("  \n\t \n", encoding="utf-8")

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
    assert argv == ["claude", "-p", expected_prompt]
    assert "--resume" not in argv


def test_dispatch_claude_argv_falls_back_when_session_id_has_internal_whitespace(tmp_path):
    repo = tmp_path / "repo"
    session_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("sess abc\n", encoding="utf-8")

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
    assert argv == ["claude", "-p", expected_prompt]
    assert "--resume" not in argv


def test_dispatch_claude_argv_strips_trailing_newline_on_session_id(tmp_path):
    repo = tmp_path / "repo"
    session_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("sess-trailing-nl\n", encoding="utf-8")

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


def test_dispatch_claude_argv_falls_back_when_session_id_file_is_not_utf8(tmp_path):
    repo = tmp_path / "repo"
    session_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    # Non-UTF-8 bytes: Path.read_text(encoding='utf-8') raises UnicodeDecodeError,
    # which is NOT an OSError subclass. Pins bridge-round-1 BLOCKING finding.
    session_path.write_bytes(b"\xff\xfe")

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
    assert argv == ["claude", "-p", expected_prompt]
    assert "--resume" not in argv
    assert "-c" not in argv
    assert "--continue" not in argv


def test_emit_transition_event_routes_claude_through_real_dispatch_target(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(repo, route="claude")

    session_path = repo / pager_mod.ORCHESTRATOR_SESSION_ID_PATH
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text("sess-integration-claude-01", encoding="utf-8")

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
    assert entry["pending_targets"] == []

    log_events = _load_log(repo)
    assert len(log_events) == 1
    expected_prompt = pager_mod._event_prompt(log_events[0])  # ANTICHEAT_OK: argv expectation
    argv = run_mock.call_args.args[0]
    assert argv == [
        "claude",
        "--resume",
        "sess-integration-claude-01",
        "-p",
        expected_prompt,
    ]
