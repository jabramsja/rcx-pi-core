"""Unit tests for the dormant Claude quick-ack pager receiver (Wave 1).

Locks the seven behaviors of ``mu/tools/session/claude_pager_receiver.py`` with a
MOCKED subprocess boundary -- no real ``claude`` process is ever spawned:

1. atomic-enqueue quick-ack (durable queue file; no subprocess during enqueue;
   enqueue is not blocked by an in-flight delivery);
2. serialized single-flight delivery (at most one child in flight);
3. fresh ``claude -p`` delivery, NEVER ``--resume``;
4. ~120s timeout + process-group reap (SIGTERM to the child's group on timeout);
5. delivery env via the pager's clobber-safe ``_claude_dispatch_env``
   (``RCX_PIPELINE_SESSION=1`` set, ``RCX_CLAUDE_MONITOR`` cleared);
6. exit-0 -> durable receipt vs non-zero/timeout -> fail-open re-queue;
7. idempotency keyed by ``event_id`` / ``transition_key``.

The subprocess is mocked by patching ``receiver_mod.subprocess.Popen``; the
receiver's public API is exercised directly, so no private-attr access is needed.
"""

from __future__ import annotations

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
        self.lock = threading.Lock()

    def __call__(self, command, **kwargs):
        with self.lock:
            self.commands.append(list(command))
            self.envs.append(kwargs.get("env"))
            self.cwds.append(kwargs.get("cwd"))
            self.start_new_sessions.append(kwargs.get("start_new_session"))
        return self._proc_factory()

    @property
    def call_count(self):
        return len(self.commands)


def _install_popen(monkeypatch, proc_factory):
    recorder = PopenRecorder(proc_factory)
    monkeypatch.setattr(receiver_mod.subprocess, "Popen", recorder)
    return recorder


def _receiver(tmp_path, **kwargs):
    kwargs.setdefault("bus_dir", ".agent_bus")
    kwargs.setdefault("timeout_s", 120.0)
    return receiver_mod.ClaudePagerReceiver(tmp_path, **kwargs)


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
# (3) fresh ``claude -p`` -- never ``--resume``
# --------------------------------------------------------------------------- #


def test_delivery_command_is_fresh_claude_p_never_resume(tmp_path, monkeypatch):
    _install_popen(monkeypatch, FakeProc)
    receiver = _receiver(tmp_path, claude_bin="claude")

    command = receiver.delivery_command({"event_id": "E1", "summary": "s"})

    assert command[0] == "claude"
    assert command[1] == "-p"
    assert "--resume" not in command
    assert "--continue" not in command
    assert "-c" not in command
    assert "-r" not in command


def test_dispatched_command_never_carries_resume(tmp_path, monkeypatch):
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


def test_idempotency_keys_on_transition_key_independent_of_event_id(tmp_path, monkeypatch):
    recorder = _install_popen(monkeypatch, lambda: FakeProc(exit_code=0))
    receiver = _receiver(tmp_path)
    # Deliver an event carrying transition_key TK under event_id X...
    receiver.enqueue({"event_id": "X", "transition_key": "TK"})
    receiver.run_until_empty()
    assert recorder.call_count == 1

    # ...a DIFFERENT event_id Y but the SAME transition_key TK is still a duplicate.
    duplicate = receiver.enqueue({"event_id": "Y", "transition_key": "TK"})
    assert duplicate["status"] == "duplicate_delivered"
    assert receiver.run_until_empty() == []
    assert recorder.call_count == 1


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
