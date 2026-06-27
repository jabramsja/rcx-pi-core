"""Unit tests for the Claude quick-ack pager receiver (Wave 1; wired in Wave 2b).

Locks the behaviors of ``mu/tools/session/claude_pager_receiver.py`` with a MOCKED
subprocess boundary -- no real ``claude`` process is ever spawned:

1. atomic-enqueue quick-ack (durable queue file; no subprocess during enqueue;
   enqueue is not blocked by an in-flight delivery);
2. serialized single-flight delivery (at most one child in flight);
3. codex-parity delivery (resolved at delivery time by the pager's
   ``resolve_claude_page_delivery``): ``claude --resume <monitor> -p`` INTO the
   persistent dedicated monitor when it is set + distinct from the live
   orchestrator + resumable; else a fresh, resume-less ``claude -p`` (monitor
   unset / monitor == live orchestrator / resume failure) -- the live orchestrator
   is NEVER resumed and a resume failure falls back to a fresh page (no page lost);
4. ~120s timeout + process-group reap (SIGTERM to the child's group on timeout);
5. delivery env per leg: a FRESH page uses the pager's clobber-safe
   ``_claude_dispatch_env`` (``RCX_PIPELINE_SESSION=1`` set, ``RCX_CLAUDE_MONITOR``
   cleared); a RESUME page uses ``_claude_monitor_resume_env``
   (``RCX_CLAUDE_MONITOR=1`` set) so the resumed monitor re-writes its OWN
   ``claude_monitor_session_id`` and never clobbers ``orchestrator_session_id``;
6. exit-0 -> durable receipt vs non-zero/timeout -> fail-open re-queue;
7. idempotency keyed by ``event_id`` ONLY (PR #1137 P2): distinct events that reuse
   a ``transition_key`` are each delivered, never collapsed;
8. ``ensure_draining`` -- the minimal idempotent start-if-not-running entry the pager
   calls after enqueue: keeps ONE bounded, detached live ``--once`` drain pass per
   repo/bus (no open-ended daemon lifecycle), refreshes stale/dead state, and fails
   closed if the drainer cannot be started.

The subprocess is mocked by patching ``receiver_mod.subprocess.Popen``; the
receiver's public API is exercised directly, so no private-attr access is needed.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time

import pytest

from tests.repo_root import REPO_ROOT
from mu.tests.tools.module_loader import load_module


_tool_path = REPO_ROOT / "tools" / "session" / "claude_pager_receiver.py"
receiver_mod = load_module("claude_pager_receiver", _tool_path)


# --------------------------------------------------------------------------- #
# Mocked subprocess boundary (no real ``claude`` is ever launched)
# --------------------------------------------------------------------------- #


class FakeProc:
    """Stand-in for ``subprocess.Popen`` -- never spawns a real process.

    ``pid`` defaults to the test's own pid so ``os.getpgid(pid)`` resolves in the
    reaper path (``os.killpg`` is patched to a recorder, so nothing is signalled).
    """

    def __init__(self, *, exit_code=0, timeout_first=False, on_wait=None, pid=None):
        import os as _os

        self.pid = pid if pid is not None else _os.getpid()
        self._exit_code = exit_code
        self._timeout_first = timeout_first
        self._on_wait = on_wait
        self._wait_count = 0

    def wait(self, timeout=None):
        self._wait_count += 1
        if self._timeout_first and self._wait_count == 1:
            raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)
        if self._on_wait is not None and self._wait_count == 1:
            self._on_wait()
        return self._exit_code


class PopenRecorder:
    """Captures every ``Popen`` invocation's argv / env / kwargs."""

    def __init__(self, proc_factory):
        self._proc_factory = proc_factory
        self.commands = []
        self.envs = []
        self.cwds = []
        self.start_new_sessions = []
        self.process_identities = {}
        self.lock = threading.Lock()

    def __call__(self, command, **kwargs):
        proc = self._proc_factory()
        with self.lock:
            command = list(command)
            self.commands.append(command)
            self.envs.append(kwargs.get("env"))
            self.cwds.append(kwargs.get("cwd"))
            self.start_new_sessions.append(kwargs.get("start_new_session"))
            self.process_identities[int(proc.pid)] = {
                "pid": int(proc.pid),
                "source": "test",
                "start_token": f"test-start-{int(proc.pid)}",
                "argv": command,
                "command_line": " ".join(command),
            }
        return proc

    @property
    def call_count(self):
        return len(self.commands)


def _install_popen(monkeypatch, proc_factory):
    recorder = PopenRecorder(proc_factory)
    monkeypatch.setattr(receiver_mod.subprocess, "Popen", recorder)
    monkeypatch.setattr(
        receiver_mod,
        "read_process_identity",
        lambda pid: recorder.process_identities.get(int(pid)),
    )
    return recorder


def _receiver(tmp_path, **kwargs):
    kwargs.setdefault("bus_dir", ".agent_bus")
    kwargs.setdefault("timeout_s", 120.0)
    return receiver_mod.ClaudePagerReceiver(tmp_path, **kwargs)


def _drainer_state_path(repo_root, *, bus_dir=".agent_bus"):
    return (
        repo_root
        / bus_dir
        / "observability"
        / "claude_pager_receiver"
        / "active_drainer.json"
    )


def _write_drainer_state(repo_root, payload, *, bus_dir=".agent_bus"):
    path = _drainer_state_path(repo_root, bus_dir=bus_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


def _write_session_ids(tmp_path, *, monitor=None, live=None):
    """Plant the session-id files the pager's delivery-time resolver reads.

    The receiver's ``_resolve_delivery_plan`` borrows
    ``pipeline_agent_pager.resolve_claude_page_delivery``, which reads
    ``<repo>/.agent_bus/observability/{claude_monitor_session_id,orchestrator_session_id}``
    against the receiver's repo_root + bus_dir. Writing these is the integration seam
    that drives the resume-vs-fresh decision in the receiver tests (no monkeypatching of
    the resolver -- the real resolver is exercised end-to-end).
    """
    obs = tmp_path / ".agent_bus" / "observability"
    obs.mkdir(parents=True, exist_ok=True)
    if monitor is not None:
        (obs / "claude_monitor_session_id").write_text(monitor + "\n", encoding="utf-8")
    if live is not None:
        (obs / "orchestrator_session_id").write_text(live + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# (1) atomic-enqueue quick-ack
# --------------------------------------------------------------------------- #


def test_enqueue_atomically_durably_queues_and_is_the_quick_ack(tmp_path, monkeypatch):
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)

    result = receiver.enqueue({"event_id": "E1", "transition_key": "T1", "summary": "go"})

    # The durable write IS the ack: a queue file exists with the event payload...
    assert result["status"] == "queued"
    assert result["event_id"] == "E1"
    queue_files = list(receiver.queue_dir.glob("*.json"))
    assert len(queue_files) == 1
    import json

    payload = json.loads(queue_files[0].read_text(encoding="utf-8"))
    assert payload["event_id"] == "E1"
    assert payload["transition_key"] == "T1"
    # ...and enqueue NEVER touches the subprocess boundary (delivery is separate).
    assert recorder.call_count == 0
    assert receiver.queued_event_ids() == ["E1"]


def test_enqueue_requires_an_identity_key(tmp_path, monkeypatch):
    _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)

    with pytest.raises(receiver_mod.ClaudePagerReceiverError):
        receiver.enqueue({"summary": "no identity"})


def test_enqueue_is_not_blocked_by_an_in_flight_delivery(tmp_path, monkeypatch):
    # The quick-ack contract under load: a slow (in-flight) delivery holds only the
    # delivery lock, so a concurrent enqueue still returns promptly.
    inflight = threading.Event()
    release = threading.Event()

    def block_until_released():
        inflight.set()
        assert release.wait(timeout=5.0)

    recorder = _install_popen(
        monkeypatch,
        lambda: FakeProc(exit_code=0, on_wait=block_until_released),
    )
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "INFLIGHT"})

    delivery_thread = threading.Thread(target=receiver.deliver_once)
    delivery_thread.start()
    try:
        assert inflight.wait(timeout=5.0), "delivery never started"

        # Delivery is mid-flight (delivery lock held); enqueue must NOT block on it.
        started = time.monotonic()
        ack = receiver.enqueue({"event_id": "QUICK"})
        elapsed = time.monotonic() - started

        assert ack["status"] == "queued"
        assert elapsed < 2.0, f"enqueue blocked on in-flight delivery ({elapsed:.2f}s)"
        assert "QUICK" in receiver.queued_event_ids()
    finally:
        release.set()
        delivery_thread.join(timeout=5.0)
        assert not delivery_thread.is_alive()

    # The in-flight delivery completed; the quick-acked event remains queued.
    assert "QUICK" in receiver.queued_event_ids()
    assert "INFLIGHT" in receiver.delivered_event_ids()


# --------------------------------------------------------------------------- #
# (2) serialized single-flight delivery
# --------------------------------------------------------------------------- #


def test_delivery_is_serialized_single_flight(tmp_path, monkeypatch):
    state = {"active": 0, "max": 0}
    guard = threading.Lock()

    def record_concurrency():
        with guard:
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
        time.sleep(0.05)
        with guard:
            state["active"] -= 1

    recorder = _install_popen(
        monkeypatch,
        lambda: FakeProc(exit_code=0, on_wait=record_concurrency),
    )
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "A"})
    receiver.enqueue({"event_id": "B"})

    threads = [threading.Thread(target=receiver.deliver_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)
        assert not thread.is_alive()

    # At most one ``claude`` child was ever in flight.
    assert state["max"] == 1
    # Both events were delivered exactly once.
    assert recorder.call_count == 2
    assert receiver.delivered_event_ids() == {"A", "B"}
    assert receiver.queued_event_ids() == []


def test_deliveries_drain_in_fifo_order(tmp_path, monkeypatch):
    delivered_ids = []

    def factory():
        return FakeProc(exit_code=0)

    recorder = _install_popen(monkeypatch, factory)
    receiver = _receiver(tmp_path)
    for event_id in ("E1", "E2", "E3"):
        receiver.enqueue({"event_id": event_id})

    receiver.run_until_empty()

    # Reconstruct delivery order from the captured prompts (FIFO == enqueue order).
    for command in recorder.commands:
        prompt = command[-1]
        for event_id in ("E1", "E2", "E3"):
            if f"event_id: {event_id}\n" in prompt + "\n":
                delivered_ids.append(event_id)
                break
    assert delivered_ids == ["E1", "E2", "E3"]


# --------------------------------------------------------------------------- #
# (3) delivery argv: fresh ``claude -p`` vs resume-the-monitor ``claude --resume``
# --------------------------------------------------------------------------- #


def test_delivery_command_is_fresh_claude_p_when_no_resume_target(tmp_path, monkeypatch):
    # With no resume target the argv is a fresh, resume-less page -- the
    # MONITOR_UNSET / MONITOR_EQUALS_LIVE / resume-failure shape.
    _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path, claude_bin="claude")

    command = receiver.delivery_command({"event_id": "E1", "summary": "s"})

    assert command[0] == "claude"
    assert command[1] == "-p"
    assert "--resume" not in command
    assert "--continue" not in command
    assert "-c" not in command
    assert "-r" not in command


def test_delivery_command_resumes_monitor_when_resume_session_id_given(tmp_path, monkeypatch):
    # Codex-parity argv: a non-empty resume target pages INTO that session.
    _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path, claude_bin="claude")

    command = receiver.delivery_command(
        {"event_id": "E1", "summary": "s"}, resume_session_id="sess-monitor"
    )

    assert command[0] == "claude"
    assert command[1] == "--resume"
    assert command[2] == "sess-monitor"
    assert command[3] == "-p"
    # The prompt is the shared page body (same as the fresh leg) -- the resume changes
    # only the delivery TARGET and mechanically disables tools, not the prompt.
    prompt_index = command.index("-p") + 1
    assert "event_id: E1\n" in command[prompt_index] + "\n"
    disallowed_index = command.index("--disallowedTools")
    assert disallowed_index > prompt_index
    assert command[disallowed_index + 1 :] == ["Bash", "Edit", "Write", "NotebookEdit"]
    # A blank/whitespace resume id degrades to a fresh page (never ``--resume ''``).
    blank = receiver.delivery_command({"event_id": "E1"}, resume_session_id="   ")
    assert blank[1] == "-p"
    assert "--resume" not in blank
    assert "--disallowedTools" not in blank


def test_dispatched_command_is_fresh_when_no_monitor_configured(tmp_path, monkeypatch):
    # No monitor session-id file in this bus -> the delivery-time resolver elects fresh.
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "E1"})

    receiver.deliver_once()

    assert recorder.call_count == 1
    command = recorder.commands[0]
    assert command[1] == "-p"
    assert "--resume" not in command
    # Child runs in its own session/process-group so a timeout can reap the group.
    assert recorder.start_new_sessions[0] is True


def test_dispatched_command_resumes_monitor_when_configured(tmp_path, monkeypatch):
    # A dedicated monitor id, distinct from the live orchestrator, present in this bus ->
    # the page is delivered INTO that monitor (``claude --resume <monitor> -p``).
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    _write_session_ids(tmp_path, monitor="sess-monitor", live="sess-live")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "E1"})

    result = receiver.deliver_once()

    assert recorder.call_count == 1
    command = recorder.commands[0]
    assert command[:3] == [receiver.claude_bin, "--resume", "sess-monitor"]
    assert command[3] == "-p"
    # The delivery is recorded with the resume mode + the monitor it paged into.
    assert result["status"] == "delivered"
    assert result["ack"]["mode"] == "resume"
    assert result["ack"]["monitor_session_id"] == "sess-monitor"
    assert recorder.start_new_sessions[0] is True


# --------------------------------------------------------------------------- #
# (4) ~120s timeout + process-group reaper
# --------------------------------------------------------------------------- #


def test_timeout_reaps_child_process_group_and_fails_open(tmp_path, monkeypatch):
    killed = []
    monkeypatch.setattr(receiver_mod.os, "killpg", lambda pgid, sig: killed.append((pgid, sig)))

    _install_popen(monkeypatch, lambda: FakeProc(exit_code=0, timeout_first=True))
    receiver = _receiver(tmp_path, timeout_s=120.0)
    receiver.enqueue({"event_id": "SLOW"})

    result = receiver.deliver_once()

    # Timeout -> the whole child process group is signalled (SIGTERM)...
    assert result["status"] == "requeued"
    assert result["timed_out"] is True
    assert len(killed) >= 1
    # FakeProc.pid defaults to this test process' pid, so the reaped group id is
    # the test process' own group -- but os.killpg is patched, so nothing is sent.
    expected_pgid = receiver_mod.os.getpgid(receiver_mod.os.getpid())
    assert killed[0] == (expected_pgid, signal.SIGTERM)
    # ...and the event is failed-open: still queued, no receipt.
    assert "SLOW" in receiver.queued_event_ids()
    assert receiver.delivered_event_ids() == set()


def test_default_delivery_timeout_is_about_120s():
    assert receiver_mod.DEFAULT_DELIVERY_TIMEOUT_S == pytest.approx(120.0)


# --------------------------------------------------------------------------- #
# (5) delivery env via pager._claude_dispatch_env -- no session-id clobber
# --------------------------------------------------------------------------- #


def test_delivery_env_sets_pipeline_session_and_clears_monitor(monkeypatch):
    # Prove the clobber-prevention contract: even with RCX_CLAUDE_MONITOR set in
    # the ambient environment, the delivery env clears it and marks the child a
    # pipeline-owned sub-session (so the SessionStart writer is fully suppressed).
    monkeypatch.setenv("RCX_CLAUDE_MONITOR", "1")
    monkeypatch.setenv("RCX_PIPELINE_SESSION", "")

    env = receiver_mod.delivery_env()

    assert env["RCX_PIPELINE_SESSION"] == "1"
    assert "RCX_CLAUDE_MONITOR" not in env


def test_dispatch_passes_clobber_safe_env_to_subprocess(tmp_path, monkeypatch):
    monkeypatch.setenv("RCX_CLAUDE_MONITOR", "1")
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "E1"})

    receiver.deliver_once()

    assert recorder.call_count == 1
    env = recorder.envs[0]
    assert env is not None
    assert env["RCX_PIPELINE_SESSION"] == "1"
    assert "RCX_CLAUDE_MONITOR" not in env


def test_resume_delivery_passes_monitor_env_to_subprocess(tmp_path, monkeypatch):
    # No-clobber on the RESUME leg: the resumed monitor's child gets
    # RCX_CLAUDE_MONITOR=1 (so its SessionStart re-writes claude_monitor_session_id,
    # NOT orchestrator_session_id) AND the pipeline-owned marker.
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    _write_session_ids(tmp_path, monitor="sess-monitor", live="sess-live")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "E1"})

    receiver.deliver_once()

    assert recorder.call_count == 1
    assert recorder.commands[0][:2] == [receiver.claude_bin, "--resume"]
    env = recorder.envs[0]
    assert env is not None
    assert env["RCX_CLAUDE_MONITOR"] == "1"
    assert env["RCX_PIPELINE_SESSION"] == "1"


# --------------------------------------------------------------------------- #
# (6) exit-0 -> receipt  vs  non-zero/timeout -> fail-open re-queue
# --------------------------------------------------------------------------- #


def test_exit_zero_writes_receipt_and_clears_queue(tmp_path, monkeypatch):
    _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "OK", "transition_key": "TK"})

    result = receiver.deliver_once()

    assert result["status"] == "delivered"
    assert result["ack"]["exit_code"] == 0
    assert result["ack"]["mode"] == "direct"
    assert "OK" in receiver.delivered_event_ids()
    assert receiver.queued_event_ids() == []
    # The receipt is durable on disk.
    assert receiver.receipts_path.exists()
    assert "OK" in receiver.receipts_path.read_text(encoding="utf-8")


def test_nonzero_exit_fails_open_requeues_without_receipt(tmp_path, monkeypatch):
    _install_popen(monkeypatch, lambda: FakeProc(exit_code=7))
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "FAIL"})

    result = receiver.deliver_once()

    assert result["status"] == "requeued"
    assert "FAIL" in receiver.queued_event_ids()
    assert receiver.delivered_event_ids() == set()
    assert not receiver.receipts_path.exists()


def test_launch_oserror_fails_open_requeues(tmp_path, monkeypatch):
    def boom(command, **kwargs):
        raise OSError("claude binary not found")

    monkeypatch.setattr(receiver_mod.subprocess, "Popen", boom)
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "NOBIN"})

    result = receiver.deliver_once()

    assert result["status"] == "requeued"
    assert "NOBIN" in receiver.queued_event_ids()
    assert receiver.delivered_event_ids() == set()


# --------------------------------------------------------------------------- #
# (7) idempotency keyed by event_id / transition_key
# --------------------------------------------------------------------------- #


def test_duplicate_enqueue_is_not_requeued(tmp_path, monkeypatch):
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)

    first = receiver.enqueue({"event_id": "DUP", "transition_key": "TK"})
    second = receiver.enqueue({"event_id": "DUP", "transition_key": "TK"})

    assert first["status"] == "queued"
    assert second["status"] == "duplicate_queued"
    assert len(list(receiver.queue_dir.glob("*.json"))) == 1
    assert recorder.call_count == 0


def test_delivered_event_is_not_redelivered(tmp_path, monkeypatch):
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "ONCE"})
    receiver.run_until_empty()
    assert recorder.call_count == 1

    # Re-enqueue the same event after delivery: terminal idempotency, no re-deliver.
    again = receiver.enqueue({"event_id": "ONCE"})
    assert again["status"] == "duplicate_delivered"
    assert receiver.queued_event_ids() == []
    assert receiver.run_until_empty() == []
    assert recorder.call_count == 1


def test_distinct_events_sharing_a_transition_key_are_each_delivered(tmp_path, monkeypatch):
    """PR #1137 P2: idempotency keys on ``event_id`` ONLY, never ``transition_key``.

    Two genuinely-distinct events that reuse a ``transition_key`` (the pager hashes
    event_type/state/phase plus transition_key into a distinct event_id) must NOT collapse.
    Before the fix the second was deduped as a duplicate and silently dropped; now each is
    queued and delivered independently.
    """
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    receiver = _receiver(tmp_path)

    # Deliver an event carrying transition_key TK under event_id X...
    receiver.enqueue({"event_id": "X", "transition_key": "TK"})
    receiver.run_until_empty()
    assert recorder.call_count == 1

    # ...a DIFFERENT event_id Y with the SAME transition_key TK is NOT a duplicate.
    distinct = receiver.enqueue({"event_id": "Y", "transition_key": "TK"})
    assert distinct["status"] == "queued"
    receiver.run_until_empty()
    assert recorder.call_count == 2
    assert receiver.delivered_event_ids() == {"X", "Y"}

    # And the SAME event_id IS still deduped (event-id identity is what dedups).
    same = receiver.enqueue({"event_id": "X", "transition_key": "TK-other"})
    assert same["status"] == "duplicate_delivered"
    assert receiver.run_until_empty() == []
    assert recorder.call_count == 2


def test_distinct_events_are_each_delivered(tmp_path, monkeypatch):
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "A", "transition_key": "TA"})
    receiver.enqueue({"event_id": "B", "transition_key": "TB"})

    receiver.run_until_empty()

    assert recorder.call_count == 2
    assert receiver.delivered_event_ids() == {"A", "B"}


# --------------------------------------------------------------------------- #
# Idempotency / fail-open persists across a fresh receiver (durable on disk)
# --------------------------------------------------------------------------- #


def test_receipts_enforce_idempotency_across_restart(tmp_path, monkeypatch):
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    first = _receiver(tmp_path)
    first.enqueue({"event_id": "PERSIST"})
    first.run_until_empty()
    assert recorder.call_count == 1

    # A brand-new receiver instance over the same bus reloads the durable receipt.
    second = _receiver(tmp_path)
    assert "PERSIST" in second.delivered_event_ids()
    assert second.enqueue({"event_id": "PERSIST"})["status"] == "duplicate_delivered"
    assert second.run_until_empty() == []
    assert recorder.call_count == 1


def test_run_forever_returns_on_idle_when_bounded(tmp_path, monkeypatch):
    _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path, poll_interval_s=0.0)

    # No events queued -> a single idle cycle returns immediately (no hang).
    receiver.run_forever(max_idle_cycles=1)


# --------------------------------------------------------------------------- #
# Persistent failure must NOT tight-loop (bridge round 2 regression)
# --------------------------------------------------------------------------- #


def test_run_until_empty_attempts_each_failing_event_once(tmp_path, monkeypatch):
    # A persistently failing event is attempted EXACTLY once per drain call
    # (honoring the "at most once per call" contract): once the drain head comes
    # back around to it, the pass stops instead of re-delivering.
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=7))
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "POISON", "transition_key": "PTK"})

    results = receiver.run_until_empty()

    assert recorder.call_count == 1, (
        f"failing event attempted {recorder.call_count}x in one drain (expected 1)"
    )
    assert [result["status"] for result in results] == ["requeued"]
    assert "POISON" in receiver.queued_event_ids()
    assert receiver.delivered_event_ids() == set()


def test_deliver_once_skips_attempted_head_and_delivers_later_tail(tmp_path, monkeypatch):
    # PR #1163 bot-review regression: if a live --once drainer has already
    # failed and requeued the head event, a later page enqueued behind that head
    # must still drain in the same pass instead of being hidden by skip_keys.
    outcomes = iter([7, 0])
    recorder = _install_popen(
        monkeypatch,
        lambda: FakeProc(exit_code=next(outcomes)),
    )
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "POISON", "transition_key": "PTK"})

    first = receiver.deliver_once(skip_keys=set())
    attempted = set(first["keys"])
    receiver.enqueue({"event_id": "TAIL", "transition_key": "TTK"})
    second = receiver.deliver_once(skip_keys=attempted)

    assert [first["status"], second["status"]] == ["requeued", "delivered"]
    assert [first["event_id"], second["event_id"]] == ["POISON", "TAIL"]
    assert recorder.call_count == 2
    assert receiver.queued_event_ids() == ["POISON"]
    assert receiver.delivered_event_ids() == {"TAIL"}


def test_run_forever_backs_off_on_persistent_failure_no_tight_loop(tmp_path, monkeypatch):
    # Bridge round 2 regression: a persistently failing event must NOT spin the
    # poll loop. With a large poll interval the daemon attempts the poison once,
    # then PARKS in an interruptible backoff -- it does not rapidly retry on the
    # fail-open re-queue (the pre-fix behavior racked up hundreds of attempts).
    first_attempt = threading.Event()

    def factory():
        first_attempt.set()
        return FakeProc(exit_code=7)

    recorder = _install_popen(monkeypatch, factory)
    receiver = _receiver(tmp_path, poll_interval_s=999.0)
    receiver.enqueue({"event_id": "POISON"})

    stop_event = threading.Event()
    thread = threading.Thread(
        target=receiver.run_forever, kwargs={"stop_event": stop_event}
    )
    thread.start()
    try:
        # The daemon makes its first (failing) attempt, then must enter backoff.
        assert first_attempt.wait(timeout=5.0), "daemon never attempted delivery"
        # Give a tight loop (the pre-fix bug) a generous window to rack up calls;
        # with the fix the daemon is parked in stop_event.wait, so it stays ~1.
        time.sleep(0.3)
        calls_during_backoff = recorder.call_count
    finally:
        stop_event.set()
        thread.join(timeout=5.0)

    # Prompt, clean shutdown: the interruptible backoff woke on stop_event...
    assert not thread.is_alive(), "run_forever did not stop promptly on stop_event"
    # ...and there was NO tight loop: a single persistent failure was retried at
    # most a couple of times across the backoff window (not hundreds).
    assert calls_during_backoff <= 3, (
        f"persistent failure tight-looped the daemon: "
        f"{calls_during_backoff} delivery attempts during backoff"
    )
    # The poison event is failed-open (still queued), never delivered.
    assert "POISON" in receiver.queued_event_ids()
    assert receiver.delivered_event_ids() == set()


# --------------------------------------------------------------------------- #
# (8) ensure_draining -- minimal idempotent start-if-not-running entry (Wave 2b)
# --------------------------------------------------------------------------- #


def test_ensure_draining_spawns_detached_bounded_once_drainer(tmp_path, monkeypatch):
    """ensure_draining starts ONE bounded, detached drain pass (no open-ended daemon).

    The pager calls this right after enqueue to GUARANTEE the queued event drains
    (PR #1137 P1). It must spawn a SINGLE bounded pass: ``<python> claude_pager_receiver.py
    --once`` (run_until_empty then exit) -- NEVER an owner-loop / poll-forever -- in its own
    session/process-group so it outlives the short-lived pager invocation.
    """
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)

    result = receiver.ensure_draining()

    assert result["started"] is True
    assert result["mode"] == "detached_once"
    assert recorder.call_count == 1
    command = recorder.commands[0]
    # Bounded single pass: --once -> run_until_empty -> exit (NOT run-forever).
    assert "--once" in command
    # The drainer is a python process running the receiver CLI itself (it then spawns claude).
    assert command[0] == receiver_mod.sys.executable
    # ``command[1]`` is the receiver script. Assert it against the module file the test
    # loaded (``_tool_path``, resolved) -- the same value the module derives into its
    # self-path constant -- rather than reaching into that private constant, so the suite
    # stays on a public seam (the private-attr test-integrity gate).
    assert str(_tool_path.resolve()) in command
    # Bound to the SAME repo/bus the pager enqueued into.
    assert "--repo-root" in command and str(receiver.repo_root) in command
    assert "--bus-dir" in command and receiver.bus_dir in command
    # Detached: its own session/process-group so a timeout reaper can kill the whole group.
    assert recorder.start_new_sessions[0] is True


def test_ensure_draining_is_idempotent_and_repeatable(tmp_path, monkeypatch):
    """Calling ensure_draining repeatedly is safe (idempotent start-if-not-running).

    Back-to-back enqueues each call ensure_draining. While a matching detached drainer
    remains live for this repo/bus, the second ensure is accepted as already draining and
    MUST NOT spawn another ``--once`` receiver behind the delivery lock.
    """
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)

    first = receiver.ensure_draining()
    second = receiver.ensure_draining()

    assert first["started"] is True
    assert first["accepted"] is True
    assert second["started"] is False
    assert second["already_draining"] is True
    assert second["accepted"] is True
    assert second["pid"] == first["pid"]
    assert recorder.call_count == 1


def test_ensure_draining_duplicate_under_failure_keeps_event_queued(tmp_path, monkeypatch):
    """Duplicate drain ensures do not hide or mark queued events delivered.

    This is the stale-herd regression shape: a live drainer may be stuck behind a failing
    delivery/credential state, but repeated enqueue attempts must reuse the active drainer
    instead of spawning hundreds more. Skipping the duplicate spawn must not mutate the
    durable queue or write a delivery receipt.
    """
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "PERSISTENT-FAIL"})

    first = receiver.ensure_draining()
    second = receiver.ensure_draining()
    third = receiver.ensure_draining()

    assert first["started"] is True
    assert second["already_draining"] is True
    assert third["already_draining"] is True
    assert recorder.call_count == 1
    assert receiver.queued_event_ids() == ["PERSISTENT-FAIL"]
    assert receiver.delivered_event_ids() == set()


def test_once_drainer_clears_live_state_when_idle_allows_future_spawn(tmp_path, monkeypatch):
    """A one-shot drainer that reaches idle clears active state before future ensures.

    Without this, an enqueue racing with a just-finished but not-yet-exited ``--once``
    child could observe a live pid, skip the spawn, and leave the new event waiting for
    a future unrelated enqueue.
    """
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)

    first = receiver.ensure_draining()
    assert first["started"] is True
    assert _drainer_state_path(tmp_path).exists()

    assert receiver.run_until_empty() == []

    assert not _drainer_state_path(tmp_path).exists()
    second = receiver.ensure_draining()
    assert second["started"] is True
    assert recorder.call_count == 2


def test_ensure_draining_refreshes_dead_drainer_state(tmp_path, monkeypatch):
    """A recorded but dead drainer pid is refreshable and starts a fresh pass."""
    dead_pid = 999_999_999
    recorder = _install_popen(
        monkeypatch,
        lambda: FakeProc(pid=dead_pid),
    )
    receiver = _receiver(tmp_path)

    first = receiver.ensure_draining()
    second = receiver.ensure_draining()

    assert first["started"] is True
    assert second["started"] is True
    assert recorder.call_count == 2


def test_ensure_draining_refreshes_malformed_drainer_state(tmp_path, monkeypatch):
    """Unreadable drainer state is stale and must not suppress a fresh spawn."""
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)
    state_path = _drainer_state_path(tmp_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text("{not-json\n", encoding="utf-8")

    result = receiver.ensure_draining()

    assert result["started"] is True
    assert recorder.call_count == 1


def test_ensure_draining_refreshes_command_mismatched_live_state(tmp_path, monkeypatch):
    """A live pid with the wrong command is not accepted as this repo/bus drainer."""
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)
    _write_drainer_state(
        tmp_path,
        {
            "pid": os.getpid(),
            "mode": "detached_once",
            "command": ["python3", "wrong_receiver.py", "--once"],
            "repo_root": str(receiver.repo_root),
            "bus_dir": receiver.bus_dir,
        },
    )

    result = receiver.ensure_draining()

    assert result["started"] is True
    assert recorder.call_count == 1
    state = json.loads(_drainer_state_path(tmp_path).read_text(encoding="utf-8"))
    assert "--once" in state["command"]
    assert "wrong_receiver.py" not in state["command"]


def test_ensure_draining_accepts_resolved_python_interpreter_identity(tmp_path, monkeypatch):
    """The drainer identity is the receiver argv tail, not the Python symlink spelling."""
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)

    first = receiver.ensure_draining()
    pid = int(first["pid"])
    state_path = _drainer_state_path(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    resolved_argv = list(state["command"])
    resolved_argv[0] = "/resolved/Python.app/Contents/MacOS/Python"
    state["process_identity"]["argv"] = resolved_argv
    state["process_identity"]["command_line"] = " ".join(resolved_argv)
    recorder.process_identities[pid]["argv"] = list(resolved_argv)
    recorder.process_identities[pid]["command_line"] = " ".join(resolved_argv)
    _write_drainer_state(tmp_path, state)

    second = receiver.ensure_draining()

    assert second["started"] is False
    assert second["already_draining"] is True
    assert second["pid"] == first["pid"]
    assert recorder.call_count == 1


def test_ensure_draining_refreshes_live_pid_state_without_process_identity(tmp_path, monkeypatch):
    """A live pid plus matching metadata is stale unless it proves the drainer identity."""
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "LIVE-PID-NO-IDENTITY"})

    first = receiver.ensure_draining()
    state_path = _drainer_state_path(tmp_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["pid"] = os.getpid()
    state.pop("process_identity", None)
    _write_drainer_state(tmp_path, state)

    second = receiver.ensure_draining()

    assert first["started"] is True
    assert second["started"] is True
    assert recorder.call_count == 2
    assert receiver.queued_event_ids() == ["LIVE-PID-NO-IDENTITY"]
    assert receiver.delivered_event_ids() == set()


def test_ensure_draining_refreshes_reused_live_pid_state(tmp_path, monkeypatch):
    """PID reuse is stale when the live process start token or argv no longer matches."""
    recorder = _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "PID-REUSE"})

    first = receiver.ensure_draining()
    reused_pid = int(first["pid"])
    recorder.process_identities[reused_pid] = {
        "pid": reused_pid,
        "source": "test",
        "start_token": f"test-reused-{reused_pid}",
        "argv": ["python3", "not-the-drainer.py"],
        "command_line": "python3 not-the-drainer.py",
    }

    second = receiver.ensure_draining()

    assert first["started"] is True
    assert second["started"] is True
    assert recorder.call_count == 2
    assert receiver.queued_event_ids() == ["PID-REUSE"]
    assert receiver.delivered_event_ids() == set()


def test_ensure_draining_fails_closed_when_spawn_raises(tmp_path, monkeypatch):
    """If the drainer cannot be started, ensure_draining RAISES (so the pager fails open).

    A spawn OSError must surface as ClaudePagerReceiverError, not be swallowed -- the pager's
    _dispatch_claude relies on this to leave the claude target pending (never accept a queue
    that may not drain).
    """
    def _boom(command, **kwargs):
        raise OSError("cannot spawn drainer")

    monkeypatch.setattr(receiver_mod.subprocess, "Popen", _boom)
    receiver = _receiver(tmp_path)

    with pytest.raises(receiver_mod.ClaudePagerReceiverError):
        receiver.ensure_draining()


# --------------------------------------------------------------------------- #
# (9) codex-parity: deliver INTO the persistent warm monitor (claude --resume)
# --------------------------------------------------------------------------- #


def test_resume_delivery_into_monitor_when_set_distinct_resumable(tmp_path, monkeypatch):
    """A set + distinct + resumable monitor -> the page is a turn IN that monitor.

    Codex-parity: just as the codex leg issues each pager turn into the shared autoping
    thread, the claude leg delivers ``claude --resume <claude_monitor_session_id> -p`` --
    INTO the persistent warm monitor -- and records a durable exit-0 receipt with the
    resume mode. The whole flow reuses the existing async drain + receipt machinery.
    """
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    _write_session_ids(tmp_path, monitor="sess-monitor", live="sess-live-distinct")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "RESUMED", "transition_key": "TK"})

    result = receiver.run_until_empty()

    assert recorder.call_count == 1
    command = recorder.commands[0]
    assert command[:3] == [receiver.claude_bin, "--resume", "sess-monitor"]
    assert command[3] == "-p"
    disallowed_index = command.index("--disallowedTools")
    assert disallowed_index > command.index("-p")
    assert command[disallowed_index + 1 :] == ["Bash", "Edit", "Write", "NotebookEdit"]
    assert [r["status"] for r in result] == ["delivered"]
    assert "RESUMED" in receiver.delivered_event_ids()
    assert receiver.queued_event_ids() == []
    # The durable receipt carries the resume provenance.
    receipt_text = receiver.receipts_path.read_text(encoding="utf-8")
    assert "RESUMED" in receipt_text
    assert "resume" in receipt_text
    assert "sess-monitor" in receipt_text


def test_fresh_fallback_when_monitor_unset(tmp_path, monkeypatch):
    # No monitor file -> MONITOR_UNSET -> fresh, resume-less page (mode ``direct``).
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "UNSET"})

    result = receiver.deliver_once()

    assert "--resume" not in recorder.commands[0]
    assert result["ack"]["mode"] == "direct"
    assert "monitor_session_id" not in result["ack"]


def test_fresh_fallback_when_monitor_equals_live_never_resumes_orchestrator(tmp_path, monkeypatch):
    """MONITOR_EQUALS_LIVE: the monitor id equals the live orchestrator id.

    The live orchestrator must NEVER be a ``claude --resume`` target (pager != autoping).
    When the dedicated monitor id transiently equals the live orchestrator id the leg pages
    fresh -- it never resumes that shared id.
    """
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    _write_session_ids(tmp_path, monitor="sess-same", live="sess-same")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "EQ"})

    result = receiver.deliver_once()

    command = recorder.commands[0]
    assert "--resume" not in command
    assert "sess-same" not in command  # the shared live id is never on the argv
    assert result["ack"]["mode"] == "direct"


def test_resume_failure_falls_back_to_fresh_page_same_delivery(tmp_path, monkeypatch):
    """Resume failure (stale/dead monitor) -> fresh ``claude -p`` fallback, same delivery.

    Mirrors the codex leg starting a NEW thread on a stale-thread error: a failed resume
    (here a non-zero ``claude --resume`` exit) must not drop the page -- the receiver falls
    back to a fresh, resume-less page within the SAME delivery so the page is still
    delivered (and the live orchestrator is never touched). Two children run, serialized
    under the single delivery lock.
    """
    exit_codes = iter([7, 0])  # resume fails, fresh fallback succeeds
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=next(exit_codes)))
    _write_session_ids(tmp_path, monitor="sess-stale", live="sess-live")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "STALE"})

    result = receiver.deliver_once()

    assert recorder.call_count == 2
    assert recorder.commands[0][:2] == [receiver.claude_bin, "--resume"]
    assert "--disallowedTools" in recorder.commands[0]
    assert "--resume" not in recorder.commands[1]
    assert "--disallowedTools" not in recorder.commands[1]
    # The fresh fallback uses the clobber-safe fresh env (RCX_CLAUDE_MONITOR cleared).
    assert "RCX_CLAUDE_MONITOR" not in recorder.envs[1]
    assert result["status"] == "delivered"
    assert result["ack"]["mode"] == "direct"
    assert result["ack"]["resume_fallback_from"] == "sess-stale"
    assert "STALE" in receiver.delivered_event_ids()


def test_resume_and_fresh_fallback_both_fail_requeues_fail_open(tmp_path, monkeypatch):
    # Resume fails AND the fresh fallback fails -> fail-open re-queue (no page lost), with a
    # combined error naming both failures. Nothing is marked delivered.
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=7))
    _write_session_ids(tmp_path, monitor="sess-stale", live="sess-live")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "LOST?"})

    result = receiver.deliver_once()

    assert recorder.call_count == 2  # resume attempt + fresh fallback attempt
    assert result["status"] == "requeued"
    assert "--resume sess-stale failed" in result["error"]
    assert "fresh page fallback also failed" in result["error"]
    assert "LOST?" in receiver.queued_event_ids()
    assert receiver.delivered_event_ids() == set()


def test_resume_delivery_preserves_event_id_dedup(tmp_path, monkeypatch):
    # event_id-only idempotency is unchanged by the resume leg: a delivered resume page is
    # not re-delivered when its event is re-enqueued (terminal duplicate).
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    _write_session_ids(tmp_path, monitor="sess-monitor", live="sess-live")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "ONCE"})
    receiver.run_until_empty()
    assert recorder.call_count == 1

    again = receiver.enqueue({"event_id": "ONCE"})
    assert again["status"] == "duplicate_delivered"
    assert receiver.run_until_empty() == []
    assert recorder.call_count == 1


def test_serialized_single_flight_holds_with_monitor_resume(tmp_path, monkeypatch):
    # Single-flight is preserved on the resume leg: at most one claude child in flight.
    state = {"active": 0, "max": 0}
    guard = threading.Lock()

    def record_concurrency():
        with guard:
            state["active"] += 1
            state["max"] = max(state["max"], state["active"])
        time.sleep(0.05)
        with guard:
            state["active"] -= 1

    recorder = _install_popen(
        monkeypatch,
        lambda: FakeProc(exit_code=0, on_wait=record_concurrency),
    )
    _write_session_ids(tmp_path, monitor="sess-monitor", live="sess-live")
    receiver = _receiver(tmp_path)
    receiver.enqueue({"event_id": "A"})
    receiver.enqueue({"event_id": "B"})

    threads = [threading.Thread(target=receiver.deliver_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5.0)
        assert not thread.is_alive()

    assert state["max"] == 1  # never two claude children at once, resume leg included
    assert receiver.delivered_event_ids() == {"A", "B"}


def test_ensure_draining_spawn_is_monitor_independent(tmp_path, monkeypatch):
    """Resolution is at DELIVERY time, not spawn time: the drain-spawn argv carries no
    monitor/resume args even when a monitor is configured.

    ``ensure_draining`` only starts the bounded ``--once`` drainer; the drainer itself
    resolves resume-vs-fresh per page. So the spawn command must stay the plain
    ``<python> claude_pager_receiver.py --repo-root ... --bus-dir ... --once`` regardless of
    the monitor id, keeping the ack-budget-critical enqueue+spawn path free of session
    resolution.
    """
    recorder = _install_popen(monkeypatch, FakeProc)
    _write_session_ids(tmp_path, monitor="sess-monitor", live="sess-live")
    receiver = _receiver(tmp_path)

    receiver.ensure_draining()

    command = recorder.commands[0]
    assert "--once" in command
    assert "--resume" not in command
    assert "sess-monitor" not in command
