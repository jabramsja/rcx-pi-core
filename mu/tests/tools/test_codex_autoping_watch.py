from __future__ import annotations

import sqlite3
from pathlib import Path

from tests.repo_root import REPO_ROOT
from mu.tests.tools.module_loader import load_module


_tool_path = REPO_ROOT / "tools" / "session" / "codex_autoping_watch.py"
watch_mod = load_module("codex_autoping_watch", _tool_path)


def test_extract_worktree_candidates_prefers_bridge_supervisor_and_higher_pid():
    ps_output = "\n".join(
        [
            "85181 /Library/... /private/tmp/workingrcx_alpha/mu/tools/executors/phase_b_executor.py --json",
            "94158 /Library/... /private/tmp/workingrcx_beta/tools/agents/bridge_supervisor.py review --job-id phase-b-r3",
            "90000 /Library/... /private/tmp/workingrcx_gamma/tools/agents/bridge_supervisor.py review --job-id phase-a-r1",
        ]
    )

    candidates = watch_mod._extract_worktree_candidates(ps_output)  # ANTICHEAT_OK: tool unit test

    assert candidates == [
        (2, 85181, Path("/private/tmp/workingrcx_alpha")),
        (3, 94158, Path("/private/tmp/workingrcx_beta")),
        (3, 90000, Path("/private/tmp/workingrcx_gamma")),
    ]


def test_extract_worktree_candidates_accepts_canonical_repo_paths():
    ps_output = (
        "999 /Library/... "
        "/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX"
        "/mu/tools/executors/phase_b_executor.py --json"
    )

    candidates = watch_mod._extract_worktree_candidates(ps_output)  # ANTICHEAT_OK: tool unit test

    assert candidates == [
        (
            2,
            999,
            Path("/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX"),
        )
    ]


def test_extract_worktree_candidates_uses_repo_root_arg_for_relative_commands():
    ps_output = (
        "1001 python3 mu/tools/executors/phase_b_executor.py "
        "--repo-root /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX --json"
    )

    candidates = watch_mod._extract_worktree_candidates(ps_output)  # ANTICHEAT_OK: tool unit test

    assert candidates == [
        (
            2,
            1001,
            Path("/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX"),
        )
    ]


def test_discover_active_wave_root_does_not_scan_global_tmp_when_repo_root_is_supplied(
    tmp_path,
    monkeypatch,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    def fake_run(cmd, *, cwd=None, timeout=30):
        return watch_mod.subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(watch_mod, "_run", fake_run)

    assert watch_mod._discover_active_wave_root(repo_root) is None  # ANTICHEAT_OK: tool unit test


def test_extract_last_agent_summary_strips_contract_prefix_and_summary_prefix(tmp_path):
    log_path = tmp_path / "autoping.jsonl"
    log_path.write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Contract active: founder XML + repo protocol in force.\\n\\nAutoping summary: checked bridge.db and raw artifact; no intervention."}}',
                '{"type":"turn.completed"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = watch_mod._extract_last_agent_summary(log_path)  # ANTICHEAT_OK: tool unit test

    assert summary == "checked bridge.db and raw artifact; no intervention."


def test_extract_last_agent_summary_requires_prefixed_summary_line(tmp_path):
    log_path = tmp_path / "autoping.jsonl"
    log_path.write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"I checked the instruction string Autoping summary: but this is not a prefixed summary line."}}',
                '{"type":"turn.completed"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = watch_mod._extract_last_agent_summary(log_path)  # ANTICHEAT_OK: tool unit test

    assert summary is None


def test_extract_last_agent_summary_ignores_non_autoping_operator_messages(tmp_path):
    log_path = tmp_path / "autoping.jsonl"
    log_path.write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Contract active: founder XML + repo protocol in force.\\n\\nOperator update, not an autoping summary."}}',
                '{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"pytest","status":"completed"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = watch_mod._extract_last_agent_summary(log_path)  # ANTICHEAT_OK: tool unit test

    assert summary is None


def test_extract_last_agent_summary_keeps_autoping_summary_after_later_operator_messages(tmp_path):
    log_path = tmp_path / "autoping.jsonl"
    log_path.write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"Autoping summary: checked bridge state; no intervention."}}',
                '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"Contract active: founder XML + repo protocol in force.\\n\\nOperator update, not an autoping summary."}}',
                '{"type":"item.completed","item":{"id":"item_2","type":"command_execution","command":"sed","status":"completed"}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = watch_mod._extract_last_agent_summary(log_path)  # ANTICHEAT_OK: tool unit test

    assert summary == "checked bridge state; no intervention."


def test_extract_ping_error_summary_reports_context_exhaustion(tmp_path):
    log_path = tmp_path / "autoping.jsonl"
    log_path.write_text(
        "\n".join(
            [
                '{"type":"thread.started","thread_id":"abc"}',
                '{"type":"turn.started"}',
                '{"type":"error","message":"Codex ran out of room in the model context window. Start a new thread or clear earlier history before retrying."}',
                '{"type":"turn.failed","error":{"message":"Codex ran out of room in the model context window. Start a new thread or clear earlier history before retrying."}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = watch_mod._extract_ping_error_summary(log_path)  # ANTICHEAT_OK: tool unit test

    assert summary is not None
    assert "context window is exhausted" in summary
    assert watch_mod._is_context_exhausted_summary(summary) is True  # ANTICHEAT_OK: tool unit test


def test_context_exhausted_state_matches_current_thread_only():
    assert watch_mod._state_context_exhausted_for_thread(  # ANTICHEAT_OK: tool unit test
        {"thread_id": "thread-live", "status": "context_exhausted"},
        "thread-live",
    ) is True
    assert watch_mod._state_context_exhausted_for_thread(  # ANTICHEAT_OK: tool unit test
        {"thread_id": "thread-live", "status": "context_exhausted_paused"},
        "thread-live",
    ) is True
    assert watch_mod._state_context_exhausted_for_thread(  # ANTICHEAT_OK: tool unit test
        {"thread_id": "thread-live", "status": "context_exhausted"},
        "thread-other",
    ) is False
    assert watch_mod._state_context_exhausted_for_thread(  # ANTICHEAT_OK: tool unit test
        {"thread_id": "thread-live", "status": "waiting_for_prior_ping"},
        "thread-live",
    ) is False


def test_state_requires_fresh_exec_after_primary_thread_context_exhaustion():
    assert watch_mod._state_requires_fresh_exec_for_thread(  # ANTICHEAT_OK: tool unit test
        {
            "thread_id": "thread-live",
            "status": "prior_ping_finished",
            "primary_thread_context_exhausted": True,
        },
        "thread-live",
    ) is True
    assert watch_mod._state_requires_fresh_exec_for_thread(  # ANTICHEAT_OK: tool unit test
        {
            "thread_id": "thread-live",
            "status": "prior_ping_finished",
            "primary_thread_context_exhausted": True,
        },
        "thread-other",
    ) is False


def test_initial_status_recovers_context_exhausted_thread_with_fresh_exec():
    assert watch_mod._initial_status_for_state(  # ANTICHEAT_OK: tool unit test
        {"thread_id": "thread-live", "status": "context_exhausted"},
        "thread-live",
    ) == "context_exhausted_recovering"
    assert watch_mod._initial_status_for_state(  # ANTICHEAT_OK: tool unit test
        {
            "thread_id": "thread-live",
            "status": "prior_ping_finished",
            "primary_thread_context_exhausted": True,
        },
        "thread-live",
    ) == "context_exhausted_recovering"
    assert watch_mod._initial_status_for_state(  # ANTICHEAT_OK: tool unit test
        {"thread_id": "thread-live", "status": "initial_delay"},
        "thread-live",
    ) == "initial_delay"


def test_ping_timed_out_only_after_configured_budget():
    assert watch_mod._ping_timed_out(  # ANTICHEAT_OK: tool unit test
        started_monotonic=10.0,
        timeout_s=120.0,
        now_monotonic=129.9,
    ) is False
    assert watch_mod._ping_timed_out(  # ANTICHEAT_OK: tool unit test
        started_monotonic=10.0,
        timeout_s=120.0,
        now_monotonic=130.0,
    ) is True
    assert watch_mod._ping_timed_out(  # ANTICHEAT_OK: tool unit test
        started_monotonic=10.0,
        timeout_s=0.0,
        now_monotonic=999.0,
    ) is False


def test_bridge_state_signature_is_stable_for_unchanged_visible_state():
    bridge_state = {
        "wave_root": "/private/tmp/workingrcx_alpha",
        "job": {"job_id": "phase-b-r1", "status": "AWAITING_REVIEWER_APPROVAL"},
        "turn": {"turn_id": "turn-1", "status": "FAILED", "decision": "ERROR"},
        "ignored": "not part of signature",
    }

    first = watch_mod._bridge_state_signature(  # ANTICHEAT_OK: tool unit test
        bridge_state,
        ["", "  Last pager wake: hard_fail", ""],
    )
    second = watch_mod._bridge_state_signature(  # ANTICHEAT_OK: tool unit test
        dict(reversed(list(bridge_state.items()))),
        ["  Last pager wake: hard_fail"],
    )

    assert first == second


def test_unchanged_state_suppression_allows_only_first_context_recovery_tick():
    state = {
        "last_bridge_signature": "sig-1",
        "last_summary": "checked bridge state; no intervention.",
        "primary_thread_context_exhausted": True,
        "status": "prior_ping_finished",
    }

    assert watch_mod._should_suppress_unchanged_state(  # ANTICHEAT_OK: tool unit test
        state,
        "sig-1",
        recovering_context_now=False,
    ) is True
    assert watch_mod._should_suppress_unchanged_state(  # ANTICHEAT_OK: tool unit test
        state,
        "sig-1",
        recovering_context_now=True,
    ) is False


def test_attention_required_summary_flags_failed_reviewer_turn():
    summary = watch_mod._attention_required_summary(  # ANTICHEAT_OK: tool unit test
        {
            "job": {"job_id": "phase-b-r2", "status": "AWAITING_REVIEWER_APPROVAL"},
            "turn": {
                "turn_id": "phase-b-r2--reviewer",
                "agent_role": "reviewer",
                "status": "FAILED",
                "decision": "ERROR",
            },
        }
    )

    assert summary is not None
    assert "attention required" in summary
    assert "phase-b-r2" in summary
    assert "FAILED" in summary


def test_attention_required_summary_ignores_running_turn():
    summary = watch_mod._attention_required_summary(  # ANTICHEAT_OK: tool unit test
        {
            "job": {"job_id": "phase-b-r2", "status": "REVIEWER_RUNNING"},
            "turn": {
                "turn_id": "phase-b-r2--reviewer",
                "agent_role": "reviewer",
                "status": "RUNNING",
                "decision": "-",
            },
        }
    )

    assert summary is None


def test_read_bridge_state_degrades_when_bridge_db_tables_are_missing(tmp_path):
    wave_root = tmp_path / "wave"
    bridge_db = wave_root / ".agent_bus" / "bridge.db"
    bridge_db.parent.mkdir(parents=True)
    sqlite3.connect(bridge_db).close()

    state = watch_mod._read_bridge_state(wave_root)  # ANTICHEAT_OK: tool unit test

    assert state["wave_root"] == str(wave_root)
    assert state["bridge_db"] == str(bridge_db)
    assert state["job"] is None
    assert state["turn"] is None
    assert state["bridge_db_degraded"] is True
    assert "OperationalError: no such table" in state["bridge_db_error"]


def test_read_bridge_state_uses_configured_bus_dir(tmp_path):
    wave_root = tmp_path / "wave"
    bridge_db = wave_root / ".agent_bus-alpha" / "bridge.db"
    bridge_db.parent.mkdir(parents=True)
    conn = sqlite3.connect(bridge_db)
    try:
        conn.executescript(
            """
            CREATE TABLE jobs (
              job_id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              terminal_decision TEXT
            );
            CREATE TABLE turns (
              turn_id TEXT PRIMARY KEY,
              job_id TEXT NOT NULL,
              agent_role TEXT NOT NULL,
              status TEXT NOT NULL,
              decision TEXT
            );
            """
        )
        conn.execute("INSERT INTO jobs VALUES (?, ?, ?)", ("job-alpha", "DONE", "GO"))
        conn.execute(
            "INSERT INTO turns VALUES (?, ?, ?, ?, ?)",
            ("turn-alpha", "job-alpha", "reviewer", "DONE", "GO"),
        )
        conn.commit()
    finally:
        conn.close()

    state = watch_mod._read_bridge_state(  # ANTICHEAT_OK: tool unit test
        wave_root,
        bus_dir=".agent_bus-alpha",
    )

    assert state["bridge_db"] == str(bridge_db)
    assert state["bus_dir"] == ".agent_bus-alpha"
    assert state["job"]["job_id"] == "job-alpha"
    assert state["turn"]["turn_id"] == "turn-alpha"


def test_write_state_merges_existing_fields(tmp_path):
    state_path = tmp_path / "autoping_state.json"
    watch_mod._write_state(  # ANTICHEAT_OK: tool unit test
        state_path,
        {
            "watcher_pid": 10,
            "last_completed_at": "2026-04-23T18:40:00+00:00",
            "last_summary": "prior summary",
        },
    )

    watch_mod._write_state(  # ANTICHEAT_OK: tool unit test
        state_path,
        {
            "watcher_pid": 11,
            "status": "waiting_for_prior_ping",
        },
    )

    payload = watch_mod._read_state(state_path)  # ANTICHEAT_OK: tool unit test

    assert payload["watcher_pid"] == 11
    assert payload["status"] == "waiting_for_prior_ping"
    assert payload["last_completed_at"] == "2026-04-23T18:40:00+00:00"
    assert payload["last_summary"] == "prior summary"


def test_resume_env_preserves_live_codex_environment(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/real-home")
    monkeypatch.setenv("CODEX_HOME", "/tmp/real-codex-home")
    monkeypatch.setenv("RCX_CODEX_HOME", "/tmp/rcx-overlay")
    monkeypatch.setenv("KEEP_ME", "yes")

    env = watch_mod._resume_env()  # ANTICHEAT_OK: tool unit test

    assert env["HOME"] == "/tmp/real-home"
    assert env["CODEX_HOME"] == "/tmp/real-codex-home"
    assert env["RCX_CODEX_HOME"] == "/tmp/rcx-overlay"
    assert env["KEEP_ME"] == "yes"


def test_codex_resume_command_uses_read_only_sandbox_without_bypass():
    command = watch_mod._codex_resume_command(  # ANTICHEAT_OK: autoping argv contract test
        "thread-live",
        "watch prompt",
    )

    assert command[:3] == [
        "codex",
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
    assert disabled_features == set(watch_mod.CODEX_NO_TOOLS_DISABLED_FEATURES)
    assert "-c" in command
    assert 'sandbox_mode="read-only"' in command
    assert 'approval_policy="never"' in command
    assert command[-3:] == ["--json", "thread-live", "watch prompt"]
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_codex_fresh_exec_command_starts_new_diagnostic_session():
    command = watch_mod._codex_ping_command(  # ANTICHEAT_OK: autoping argv contract test
        "thread-live",
        "watch prompt",
        fresh_exec=True,
    )

    assert command[:2] == ["codex", "exec"]
    assert command[2] != "resume"
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    disabled_features = {
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--disable"
    }
    assert disabled_features == set(watch_mod.CODEX_NO_TOOLS_DISABLED_FEATURES)
    assert command[-2:] == ["--json", "watch prompt"]
    assert "thread-live" not in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_timeout_context_exhausted_summary_marks_thread_paused():
    summary = "current Codex thread context window is exhausted; start a new thread"

    assert watch_mod._status_for_ping_summary(  # ANTICHEAT_OK: autoping state contract test
        summary,
        timed_out=True,
    ) == "context_exhausted_paused"


def test_render_prompt_forbids_headless_pipeline_relaunches(tmp_path):
    summary_path = tmp_path / "summary.txt"

    prompt = watch_mod._render_prompt(  # ANTICHEAT_OK: tool unit test
        bridge_state={"job": {"job_id": "phase-b-r1", "status": "FAILED"}},
        tmux_tail=["tail line"],
        summary_path=summary_path,
    )

    assert "Do not launch or relaunch executor_dispatch.py" in prompt
    assert "Do not background a new pipeline process" in prompt


def test_render_prompt_keeps_autoping_diagnostic_only(tmp_path):
    summary_path = tmp_path / "summary.txt"

    prompt = watch_mod._render_prompt(  # ANTICHEAT_OK: tool unit test
        bridge_state={"job": {"job_id": "phase-b-r1", "status": "FAILED"}},
        tmux_tail=["tail line"],
        summary_path=summary_path,
    )

    assert "without mutating repo files" in prompt
    assert "Do not run shell commands" in prompt
    assert "Do not edit files" in prompt
    assert "Do not run pytest" in prompt
    assert "broad validation suites" in prompt
    assert "The watcher will persist that final summary" in prompt
    assert "Persist your operator-facing summary" not in prompt
    assert "apply safe repo-local structural fixes" not in prompt


def test_resume_env_keeps_rcx_overlay_for_resumed_turns(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("CODEX_HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("RCX_CODEX_HOME", "/tmp/rcx-codex-runtime-home")
    monkeypatch.setenv("KEEP_ME", "yes")

    env = watch_mod._resume_env()  # ANTICHEAT_OK: tool unit test

    assert env["HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["CODEX_HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["RCX_CODEX_HOME"] == "/tmp/rcx-codex-runtime-home"
    assert env["KEEP_ME"] == "yes"
