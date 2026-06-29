"""Regression tests for the dedicated Claude monitor autoping watcher.

Bounds GAP-4 (a)-(d) for the claude-monitor-autoping-route-both wave:
  (a) the keepalive targets the dedicated ``claude_monitor_session_id``, NEVER the
      live orchestrator session;
  (b) the keepalive argv carries the mechanical tool-restriction flag (GAP-1) AND
      ``--output-format stream-json`` (GAP-2), and the summary parser extracts the
      one-line ``Autoping summary:`` from a stream-json sample;
  (c) an absent/malformed monitor id pauses (no orchestrator fallback);
  (d) the repo-matched state file carries the full schema + a ``status`` health
      field.

GAP-4 (e) (``_requested_targets('both')`` -> ['codex','claude'] and a page
dispatches to both) lives in the EXISTING mu/tests/tools/test_pipeline_agent_pager.py.
"""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT
from mu.tests.tools.module_loader import load_module


_tool_path = REPO_ROOT / "tools" / "session" / "claude_autoping_watch.py"
watch_mod = load_module("claude_autoping_watch", _tool_path)


def _seed_observability(repo: Path, bus_dir: str = ".agent_bus") -> Path:
    obs = repo / bus_dir / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    return obs


# --- (a) keepalive targets the dedicated monitor, never the orchestrator -------


def test_read_monitor_session_id_resolves_dedicated_monitor_file(tmp_path):
    obs = _seed_observability(tmp_path)
    (obs / "claude_monitor_session_id").write_text("sess-monitor-01\n", encoding="utf-8")

    resolved = watch_mod._read_monitor_session_id(tmp_path, ".agent_bus")  # ANTICHEAT_OK: tool unit test
    assert resolved == "sess-monitor-01"


def test_read_monitor_session_id_never_falls_back_to_orchestrator(tmp_path):
    # The core fail-closed contract: with ONLY the live orchestrator id present and
    # NO dedicated monitor file, resolution returns None -- the watcher pauses and
    # never resumes the live orchestrator conversation.
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_text("sess-live-99\n", encoding="utf-8")

    assert watch_mod._read_monitor_session_id(tmp_path, ".agent_bus") is None  # ANTICHEAT_OK: tool unit test


def test_keepalive_command_targets_monitor_not_orchestrator():
    argv = watch_mod._claude_keepalive_command("sess-monitor-01", "PROMPT")  # ANTICHEAT_OK: argv contract test

    assert argv[:5] == ["claude", "--resume", "sess-monitor-01", "-p", "PROMPT"]
    # Never the live orchestrator id, and no whole-session continue forms.
    assert "sess-live-99" not in argv
    assert "--continue" not in argv
    assert "-c" not in argv


def test_resolve_session_id_reads_only_monitor_file(tmp_path):
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_text("sess-live-99\n", encoding="utf-8")
    (obs / "claude_monitor_session_id").write_text("sess-monitor-01\n", encoding="utf-8")

    resolved = watch_mod._resolve_session_id(tmp_path, ".agent_bus", None)  # ANTICHEAT_OK: tool unit test
    assert resolved == "sess-monitor-01"


# --- (b) GAP-1 tool-restriction + GAP-2 stream-json + summary parse ------------


def test_keepalive_command_restricts_tools_and_streams_json():
    argv = watch_mod._claude_keepalive_command("sess-monitor-01", "PROMPT")  # ANTICHEAT_OK: argv contract test

    # GAP-1: the mechanical tool-restriction flag is present and covers at least
    # Bash (the tool that could spawn a pipeline executor).
    assert "--disallowedTools" in argv
    disallowed_value = argv[argv.index("--disallowedTools") + 1]
    assert "Bash" in disallowed_value
    # GAP-2: stream-json output so the watcher can parse the terminal summary.
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv


def test_extract_last_agent_summary_parses_stream_json_result_event(tmp_path):
    log = tmp_path / "keepalive.jsonl"
    log.write_text(
        "\n".join(
            [
                '{"type":"system","subtype":"init","session_id":"sess-monitor-01"}',
                '{"type":"result","subtype":"success","result":"Autoping summary: monitor warm; no action needed."}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = watch_mod._extract_last_agent_summary(log)  # ANTICHEAT_OK: tool unit test
    assert summary == "monitor warm; no action needed."


def test_extract_last_agent_summary_parses_stream_json_assistant_blocks(tmp_path):
    log = tmp_path / "keepalive.jsonl"
    log.write_text(
        "\n".join(
            [
                '{"type":"system","subtype":"init"}',
                '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"checking..."}]}}',
                '{"type":"assistant","message":{"role":"assistant","content":[{"type":"text","text":"Autoping summary: monitor warm; nothing to do."}]}}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = watch_mod._extract_last_agent_summary(log)  # ANTICHEAT_OK: tool unit test
    assert summary == "monitor warm; nothing to do."


def test_extract_last_agent_summary_requires_prefixed_line(tmp_path):
    log = tmp_path / "keepalive.jsonl"
    log.write_text(
        '{"type":"result","subtype":"success","result":"I mention Autoping summary: but not as a prefixed line."}\n',
        encoding="utf-8",
    )

    assert watch_mod._extract_last_agent_summary(log) is None  # ANTICHEAT_OK: tool unit test


def test_extract_last_agent_summary_tolerates_non_json_stderr_lines(tmp_path):
    # The keepalive log captures stdout+stderr; interleaved non-JSON stderr lines
    # must be skipped, not abort the parse.
    log = tmp_path / "keepalive.jsonl"
    log.write_text(
        "\n".join(
            [
                "some stderr warning that is not json",
                '{"type":"result","subtype":"success","result":"Autoping summary: warm."}',
                "another trailing stderr line",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert watch_mod._extract_last_agent_summary(log) == "warm."  # ANTICHEAT_OK: tool unit test


# --- (c) absent/malformed monitor id -> paused, no orchestrator fallback -------


@pytest.mark.parametrize(
    "monitor_bytes",
    [
        None,            # missing file entirely
        b"",             # empty
        b"  \n\t \n",    # whitespace-only
        b"sess abc\n",   # internal whitespace
        b"\xff\xfe",     # non-UTF-8 bytes
    ],
)
def test_read_monitor_session_id_fails_closed_on_malformed(tmp_path, monitor_bytes):
    obs = _seed_observability(tmp_path)
    # A live id is also present to prove malformed-monitor never resumes live.
    (obs / "orchestrator_session_id").write_text("sess-live-present\n", encoding="utf-8")
    if monitor_bytes is not None:
        (obs / "claude_monitor_session_id").write_bytes(monitor_bytes)

    assert watch_mod._read_monitor_session_id(tmp_path, ".agent_bus") is None  # ANTICHEAT_OK: tool unit test


def test_resolve_session_id_prefers_explicit_override(tmp_path):
    # An explicit operator-pinned id wins; the file is not consulted.
    obs = _seed_observability(tmp_path)
    (obs / "claude_monitor_session_id").write_text("sess-from-file\n", encoding="utf-8")

    resolved = watch_mod._resolve_session_id(tmp_path, ".agent_bus", "sess-explicit")  # ANTICHEAT_OK: tool unit test
    assert resolved == "sess-explicit"


def test_absent_monitor_id_maps_to_paused_state(tmp_path):
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_text("sess-live-only\n", encoding="utf-8")

    # Resolution yields nothing (no fallback to the live id) ...
    assert watch_mod._resolve_session_id(tmp_path, ".agent_bus", None) is None  # ANTICHEAT_OK: tool unit test
    # ... and the watcher's pause update marks the monitor unhealthy with a reason.
    update = watch_mod._paused_state_update(4321)  # ANTICHEAT_OK: tool unit test
    assert update["status"] == watch_mod.STATUS_PAUSED == "paused"
    assert update["active_pid"] is None
    assert "orchestrator" in update["pause_reason"].lower()


# --- (d) state-file schema + status health field ------------------------------


def test_state_skeleton_has_full_schema_and_status_health(tmp_path):
    skeleton = watch_mod._state_skeleton(  # ANTICHEAT_OK: tool unit test
        repo_root=tmp_path,
        bus_dir=".agent_bus",
        session_id="sess-monitor-01",
        summary_path=tmp_path / "summary.txt",
        watcher_pid=999,
    )

    required = {
        "version",
        "updated_at",
        "watcher_pid",
        "session_id",
        "status",
        "active_pid",
        "active_log",
        "last_exit_code",
        "last_completed_at",
        "last_summary",
        "repo_root",
        "bus_dir",
        "summary_path",
        "pause_reason",
    }
    assert required <= set(skeleton)
    assert skeleton["version"] == watch_mod.STATE_VERSION == 1
    assert skeleton["session_id"] == "sess-monitor-01"
    assert skeleton["bus_dir"] == ".agent_bus"
    # Health field is a live (non-paused) status by default.
    assert skeleton["status"] == watch_mod.STATUS_INITIAL_DELAY
    assert skeleton["status"] != watch_mod.STATUS_PAUSED


def test_paused_state_update_marks_paused_with_reason():
    update = watch_mod._paused_state_update(123)  # ANTICHEAT_OK: tool unit test
    assert update["status"] == "paused"
    assert update["watcher_pid"] == 123
    assert update["pause_reason"]


def test_write_state_merges_existing_fields(tmp_path):
    state_path = tmp_path / "claude_autoping_sess.json"
    watch_mod._write_state(  # ANTICHEAT_OK: tool unit test
        state_path,
        {
            "watcher_pid": 10,
            "last_completed_at": "2026-06-04T00:00:00+00:00",
            "last_summary": "prior summary",
            "status": "ping_dispatched",
        },
    )
    watch_mod._write_state(  # ANTICHEAT_OK: tool unit test
        state_path,
        {"watcher_pid": 11, "status": "waiting_for_prior_ping"},
    )

    payload = watch_mod._read_state(state_path)  # ANTICHEAT_OK: tool unit test
    assert payload["watcher_pid"] == 11
    assert payload["status"] == "waiting_for_prior_ping"
    assert payload["last_completed_at"] == "2026-06-04T00:00:00+00:00"
    assert payload["last_summary"] == "prior summary"


# --- core helpers (prompt backup guard, timeout, process-group kill, etc.) -----


def test_keepalive_prompt_forbids_executor_relaunch_and_requests_summary(tmp_path):
    prompt = watch_mod._render_prompt(  # ANTICHEAT_OK: tool unit test
        summary_path=tmp_path / "summary.txt",
        bus_dir=".agent_bus",
    )
    # GAP-1 BACKUP guard (the argv flag is the PRIMARY guard).
    assert "Do not launch or relaunch executor_dispatch.py" in prompt
    assert "Do not run shell commands" in prompt
    assert "Do not edit files" in prompt
    # The watcher relies on this trailing instruction to harvest the summary.
    assert "Autoping summary:" in prompt


def test_ping_timed_out_only_after_configured_budget():
    assert watch_mod._ping_timed_out(  # ANTICHEAT_OK: tool unit test
        started_monotonic=10.0, timeout_s=120.0, now_monotonic=129.9
    ) is False
    assert watch_mod._ping_timed_out(  # ANTICHEAT_OK: tool unit test
        started_monotonic=10.0, timeout_s=120.0, now_monotonic=130.0
    ) is True
    assert watch_mod._ping_timed_out(  # ANTICHEAT_OK: tool unit test
        started_monotonic=10.0, timeout_s=0.0, now_monotonic=999.0
    ) is False


def test_status_for_ping_summary_reports_timeout_vs_finished():
    assert watch_mod._status_for_ping_summary("warm.") == "prior_ping_finished"  # ANTICHEAT_OK: tool unit test
    assert (
        watch_mod._status_for_ping_summary("warm.", timed_out=True)  # ANTICHEAT_OK: tool unit test
        == "prior_ping_timed_out"
    )


def test_terminate_process_group_escalates_to_sigkill():
    # A child that IGNORES SIGTERM forces the SIGKILL escalation path (mirror of
    # the codex watcher's _terminate_process_group on a stale keepalive).
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    try:
        watch_mod._terminate_process_group(proc, grace_s=1.0)  # ANTICHEAT_OK: tool unit test
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


# --- finding-3: terminating the watcher reaps the detached keepalive child ------
# The keepalive runs in its own session (start_new_session=True), so it is NOT in
# the watcher's process group; ``kill <watcher-pid>`` (what the launcher's
# force-restart sends) would orphan it. The watcher installs SIGTERM/SIGINT +
# atexit reapers so stopping the watcher reaps the tracked child instead.


def test_autoping_install_termination_handlers_registers_signal_and_atexit_reaper(monkeypatch):
    # Capture the atexit registration instead of polluting the real interpreter.
    registered: list = []
    monkeypatch.setattr(
        watch_mod.atexit, "register", lambda fn, *a, **k: (registered.append(fn) or fn)
    )

    # Seed a tracked, running child so the registered atexit handler can be proven a
    # working reaper *by behavior* -- invoking it must tear the keepalive child's
    # process group down -- rather than by comparing a private function identity.
    # ``monkeypatch.setattr`` is pytest's public patching seam and auto-restores the
    # tracked-child global after the test.
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    monkeypatch.setattr(watch_mod, "_ACTIVE_CHILD", proc)

    original_term = signal.getsignal(signal.SIGTERM)
    original_int = signal.getsignal(signal.SIGINT)
    try:
        watch_mod._install_termination_handlers()  # ANTICHEAT_OK: tool unit test
        # The atexit reaper is the catch-all (normal exit / unhandled exception):
        # install registered a handler, and invoking the registered handler(s) reaps
        # the tracked keepalive child's process group.
        assert registered, "install must register an atexit reaper"
        for handler in registered:
            handler()
        assert proc.poll() is not None
        # SIGTERM/SIGINT now route to a real handler, not the default disposition.
        term_handler = signal.getsignal(signal.SIGTERM)
        int_handler = signal.getsignal(signal.SIGINT)
        assert callable(term_handler)
        assert term_handler not in (signal.SIG_DFL, signal.SIG_IGN)
        assert callable(int_handler)
        assert int_handler not in (signal.SIG_DFL, signal.SIG_IGN)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
        signal.signal(signal.SIGTERM, original_term)
        signal.signal(signal.SIGINT, original_int)


def test_autoping_reap_active_child_terminates_tracked_process_group():
    # A tracked, running child's process group is terminated when the watcher is
    # reaped -- proving ``kill <watcher-pid>`` no longer orphans the keepalive.
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    try:
        watch_mod._track_active_child(proc)  # ANTICHEAT_OK: tool unit test
        watch_mod._reap_active_child()  # ANTICHEAT_OK: tool unit test
        assert proc.poll() is not None
    finally:
        watch_mod._track_active_child(None)  # ANTICHEAT_OK: tool unit test
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_autoping_reap_active_child_is_noop_without_live_child():
    # No tracked child (or an already-finished one) must not raise.
    watch_mod._track_active_child(None)  # ANTICHEAT_OK: tool unit test
    watch_mod._reap_active_child()  # ANTICHEAT_OK: tool unit test

    finished = subprocess.Popen(
        [sys.executable, "-c", "raise SystemExit(0)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        text=True,
    )
    finished.wait(timeout=5)
    try:
        watch_mod._track_active_child(finished)  # ANTICHEAT_OK: tool unit test
        watch_mod._reap_active_child()  # ANTICHEAT_OK: tool unit test (poll() guard => no-op)
    finally:
        watch_mod._track_active_child(None)  # ANTICHEAT_OK: tool unit test


def test_validate_bus_dir_accepts_default_and_namespaced_rejects_traversal():
    assert watch_mod._validate_bus_dir(".agent_bus") == ".agent_bus"  # ANTICHEAT_OK: tool unit test
    assert watch_mod._validate_bus_dir(".agent_bus-lane1") == ".agent_bus-lane1"  # ANTICHEAT_OK: tool unit test
    # Empty/None collapse to the default bus (mirror of the codex watcher), so they
    # are valid; only traversal / absolute / non-namespaced values are rejected.
    assert watch_mod._validate_bus_dir("") == ".agent_bus"  # ANTICHEAT_OK: tool unit test
    assert watch_mod._validate_bus_dir(None) == ".agent_bus"  # ANTICHEAT_OK: tool unit test
    for bad in ["..", "/abs", ".agent_bus/../x", "a/b", ".secret"]:
        with pytest.raises(ValueError):
            watch_mod._validate_bus_dir(bad)  # ANTICHEAT_OK: tool unit test


def test_resume_env_preserves_live_environment(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/real-home")
    monkeypatch.setenv("KEEP_ME", "yes")
    env = watch_mod._resume_env()  # ANTICHEAT_OK: tool unit test
    assert env["HOME"] == "/tmp/real-home"
    assert env["KEEP_ME"] == "yes"


def test_resume_env_sets_claude_monitor_marker(monkeypatch):
    # Regression for the recurring CLAUDE autoping WATCHER self-collision pause
    # (2026-06-21 / 2026-06-28): the keepalive resume MUST carry RCX_CLAUDE_MONITOR=1
    # so the resumed monitor session's session-start hook writes ONLY
    # claude_monitor_session_id and never clobbers orchestrator_session_id. Deleting
    # the var first proves _resume_env() SETS it (not merely passes it through), so
    # this fails against the bare os.environ.copy() it replaces.
    monkeypatch.delenv("RCX_CLAUDE_MONITOR", raising=False)
    monkeypatch.setenv("KEEP_ME", "yes")
    env = watch_mod._resume_env()  # ANTICHEAT_OK: tool unit test
    assert env["RCX_CLAUDE_MONITOR"] == "1"
    # Additive: the marker does not displace any inherited environment key.
    assert env["KEEP_ME"] == "yes"


# --- bridge round-2 finding 1: equal-to-live guard before resume ---------------
# The dedicated monitor id MUST be DISTINCT from the live orchestrator session
# before the watcher builds a ``claude --resume`` argv -- mirror of the pager's
# MONITOR_EQUALS_LIVE skip. The live id is read for the inequality check ONLY,
# never as a resume target, and the watcher pauses (no orchestrator fallback) when
# they are equal.


def test_autoping_read_orchestrator_session_id_reads_live_file(tmp_path):
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_text("sess-live-99\n", encoding="utf-8")
    assert (
        watch_mod._read_orchestrator_session_id(tmp_path, ".agent_bus")  # ANTICHEAT_OK: tool unit test
        == "sess-live-99"
    )


def test_autoping_read_orchestrator_session_id_fails_closed_on_malformed(tmp_path):
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_bytes(b"sess live\n")  # internal whitespace
    assert watch_mod._read_orchestrator_session_id(tmp_path, ".agent_bus") is None  # ANTICHEAT_OK: tool unit test


def test_autoping_resolve_keepalive_pauses_when_monitor_equals_live(tmp_path):
    obs = _seed_observability(tmp_path)
    # The dedicated monitor file mistakenly holds the SAME id as the live orchestrator.
    (obs / "orchestrator_session_id").write_text("same-session\n", encoding="utf-8")
    (obs / "claude_monitor_session_id").write_text("same-session\n", encoding="utf-8")

    session_id, reason = watch_mod._resolve_keepalive_session_id(  # ANTICHEAT_OK: tool unit test
        tmp_path, ".agent_bus", None
    )
    # Paused: NO resume target returned, and the reason is the equal-to-live guard.
    assert session_id is None
    assert reason == watch_mod.PAUSE_REASON_MONITOR_EQUALS_LIVE
    assert "orchestrator" in reason.lower()


def test_autoping_resolve_keepalive_pauses_when_explicit_override_equals_live(tmp_path):
    # The guard also covers an explicit --session-id override that equals the live id;
    # an operator-pinned id is never allowed to resume the live orchestrator.
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_text("live-and-explicit\n", encoding="utf-8")

    session_id, reason = watch_mod._resolve_keepalive_session_id(  # ANTICHEAT_OK: tool unit test
        tmp_path, ".agent_bus", "live-and-explicit"
    )
    assert session_id is None
    assert reason == watch_mod.PAUSE_REASON_MONITOR_EQUALS_LIVE


def test_autoping_resolve_keepalive_returns_monitor_id_when_distinct_from_live(tmp_path):
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_text("sess-live-99\n", encoding="utf-8")
    (obs / "claude_monitor_session_id").write_text("sess-monitor-01\n", encoding="utf-8")

    session_id, reason = watch_mod._resolve_keepalive_session_id(  # ANTICHEAT_OK: tool unit test
        tmp_path, ".agent_bus", None
    )
    assert session_id == "sess-monitor-01"
    assert reason == ""


def test_autoping_resolve_keepalive_pauses_unset_when_monitor_absent(tmp_path):
    # Only the live orchestrator file exists -> still UNSET (no fallback to the live id).
    obs = _seed_observability(tmp_path)
    (obs / "orchestrator_session_id").write_text("sess-live-only\n", encoding="utf-8")

    session_id, reason = watch_mod._resolve_keepalive_session_id(  # ANTICHEAT_OK: tool unit test
        tmp_path, ".agent_bus", None
    )
    assert session_id is None
    assert reason == watch_mod.PAUSE_REASON_MONITOR_UNSET


def test_autoping_resolve_keepalive_resumes_when_only_monitor_present(tmp_path):
    # No live orchestrator file at all -> distinct by construction -> resume target.
    obs = _seed_observability(tmp_path)
    (obs / "claude_monitor_session_id").write_text("sess-monitor-01\n", encoding="utf-8")

    session_id, reason = watch_mod._resolve_keepalive_session_id(  # ANTICHEAT_OK: tool unit test
        tmp_path, ".agent_bus", None
    )
    assert session_id == "sess-monitor-01"
    assert reason == ""


# --- bridge round-2 finding 2: watcher self-isolates its process group ----------
# The launcher's orphan sweep terminates a stale watcher with
# killpg(getpgid(<watcher-pid>)). The watcher MUST be its own session/process-group
# leader so killpg signals only the watcher, never the launcher's inherited process
# group. macOS has no setsid(1), so the watcher self-isolates via os.setsid().


def test_autoping_isolate_process_group_swallows_already_leader_error(monkeypatch):
    # If the watcher is ALREADY a process-group leader, os.setsid() raises
    # PermissionError; the guard must swallow it (already isolated) and not raise.
    def _raise_already_leader():
        raise PermissionError("already a process group leader")

    monkeypatch.setattr(watch_mod.os, "setsid", _raise_already_leader)
    watch_mod._isolate_process_group()  # ANTICHEAT_OK: tool unit test (must not raise)


def test_autoping_isolate_process_group_promotes_to_own_session_leader():
    # Verified in a SUBPROCESS that starts as a NON-leader (shares the pytest process
    # group): _isolate_process_group() must promote it to its own group leader so
    # getpgid(0) == getpid(). Calling setsid in the pytest process itself would
    # detach the test runner, so this is asserted strictly out-of-process.
    code = (
        "import importlib.util, os\n"
        f"spec = importlib.util.spec_from_file_location('caw', {str(_tool_path)!r})\n"
        "mod = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(mod)\n"
        "mod._isolate_process_group()\n"
        "print('leader', os.getpgid(0) == os.getpid())\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        # No start_new_session: the child starts as a NON-leader so setsid must
        # actually promote it (proving the isolation is effective, not pre-existing).
    )
    assert proc.returncode == 0, proc.stderr
    # The watcher ended up as its own session/process-group leader.
    assert "leader True" in proc.stdout
