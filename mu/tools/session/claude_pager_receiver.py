#!/usr/bin/env python3
"""Claude quick-ack pager receiver (pager-quickack Wave 1; wired in Wave 2b).

WIRING (Wave 2b): the pager's ``_dispatch_claude`` now drives this receiver -- it
ENQUEUES each page and calls ``ensure_draining`` to GUARANTEE the queued event is
drained (PR #1137 P1). Cross-module coupling is still a READ-ONLY reuse of
``pipeline_agent_pager._claude_dispatch_env`` for the delivery subprocess
environment; this module never imports the pager's mutable state. There is no
open-ended daemon lifecycle: ``ensure_draining`` lazily starts a SINGLE bounded
drain pass (``--once`` -> ``run_until_empty``) that exits when the queue is drained.

What it provides (the behaviors locked by
``mu/tests/tools/test_claude_pager_receiver.py``):

1. Per-bus file-queue inbox. The atomic enqueue IS the quick-ack: ``enqueue``
   durably writes the event to the per-bus queue dir (temp-file + ``os.replace``)
   and returns as soon as it is queued. Enqueue takes only a SHORT queue lock, so
   an in-flight (slow) delivery NEVER blocks the quick-ack.

2. Serialized, single-flight delivery. ``deliver_once`` holds a SEPARATE delivery
   lock for the whole call, so at most one ``claude`` child is ever in flight.

3. Codex-parity delivery (resolved at delivery time by the pager's
   ``resolve_claude_page_delivery``). When a DEDICATED monitor session id is set,
   DISTINCT from the live orchestrator, and resumable, the page is delivered INTO
   that persistent warm monitor with ``--disallowedTools`` on the argv -- the same
   warm monitor the autoping watcher keeps, mirroring how the codex leg issues each
   turn into the shared autoping thread. Otherwise (monitor unset/malformed, monitor
   == live orchestrator, or a resume FAILURE) the page is a fresh, resume-less
   ``[claude_bin, "-p", prompt]`` -- the live orchestrator is NEVER resumed, and a
   resume failure falls back to a fresh page so no page is lost.

4. ~120s per-delivery timeout plus a process-group reaper. The child runs in its
   own session/process-group (``start_new_session=True``); on timeout the whole
   group is killed (``os.killpg``) via ``_terminate_process_group``.

5. Delivery environment per leg. A FRESH page uses
   ``pipeline_agent_pager._claude_dispatch_env`` -- marks the child a pipeline-owned
   sub-session and CLEARS ``RCX_CLAUDE_MONITOR`` so the transient page never clobbers
   ``orchestrator_session_id`` / ``claude_monitor_session_id``. A RESUME page uses
   ``pipeline_agent_pager._claude_monitor_resume_env`` -- SETS ``RCX_CLAUDE_MONITOR=1``
   so the resumed monitor's SessionStart re-writes its OWN
   ``claude_monitor_session_id`` (idempotent) and never clobbers
   ``orchestrator_session_id``. Both envs are borrowed from the pager (returned in the
   delivery plan), not reimplemented here.

6. Exit-0 -> durable receipt; non-zero exit or timeout -> fail-open re-queue (the
   event is re-written to the back of the queue and is never lost).

7. Idempotency keyed by ``event_id`` ONLY (PR #1137 P2). A duplicate event (one
   whose ``event_id`` matches an already-delivered or already-queued event) is not
   re-queued and not re-delivered. ``transition_key`` is deliberately EXCLUDED from
   the dedup identity: the pager hashes ``event_type`` / ``state`` / ``phase`` plus
   ``transition_key`` into a distinct ``event_id``, so two genuinely-distinct pager
   events can legitimately share a ``transition_key`` -- deduping on it would
   collapse them and silently drop the second.

8. ``ensure_draining`` -- the minimal idempotent start-if-not-running entry the
   pager calls right after enqueue. It keeps one live bounded, detached drain pass
   per repo/bus (``--once`` -> ``run_until_empty``, then exit); no owner-loop /
   poll-forever / session-rebuild / restart-supervision. The just-enqueued event
   (queued BEFORE the ensure) is guaranteed to be observed by a live or freshly
   started pass.

This is additive, observability-only tooling. It touches no runtime/substrate
surface (``rcx_pi/selfhost/`` or ``mu/host/``) and introduces no host semantics.
"""

from __future__ import annotations

import argparse
import fcntl
import itertools
import json
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_BUS_DIR = ".agent_bus"
# Mirrors the pager's claude-ack budget intent: a generous single-delivery
# ceiling. The whole child process group is reaped on expiry.
DEFAULT_DELIVERY_TIMEOUT_S = 120.0
DEFAULT_POLL_INTERVAL_S = 5.0
CLAUDE_BIN_ENV = "RCX_PIPELINE_AGENT_PAGER_CLAUDE_BIN"
PROCESS_GROUP_GRACE_S = 5.0
# Mirrors claude_autoping_watch.py: resumed monitor pages are diagnostic/wakeup
# deliveries, so tools must be mechanically absent from the model context.
CLAUDE_RESUME_DISALLOWED_TOOLS = ("Bash", "Edit", "Write", "NotebookEdit")
# This module's own path, used by ``ensure_draining`` to spawn a bounded drain
# pass (``<python> claude_pager_receiver.py --once ...``). Resolved once at import.
_RECEIVER_SCRIPT = str(Path(__file__).resolve())

# A drain cycle made "progress" only if at least one event left the queue durably
# this cycle (delivered, or dropped as a duplicate / unreadable). A cycle that
# only re-queued persistently-failing events is NOT progress -- ``run_forever``
# backs off for the poll interval instead of retrying immediately, so a poison
# event can never tight-loop the daemon.
_DRAIN_PROGRESS_STATUSES = frozenset(
    {"delivered", "duplicate_delivered", "dropped_unreadable"}
)


class ClaudePagerReceiverError(RuntimeError):
    """Raised when receiver inbox/delivery handling fails."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _coerce_pid(pid: Any) -> int | None:
    try:
        value = int(pid)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def _split_command_line(command_line: str) -> list[str]:
    try:
        return shlex.split(command_line)
    except ValueError:
        return command_line.split()


def _read_proc_process_identity(pid: int) -> dict[str, Any] | None:
    proc_dir = Path("/proc") / str(pid)
    if not proc_dir.exists():
        return None
    try:
        raw_cmdline = (proc_dir / "cmdline").read_bytes()
        stat_text = (proc_dir / "stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    argv = [
        part.decode("utf-8", errors="surrogateescape")
        for part in raw_cmdline.split(b"\0")
        if part
    ]
    if not argv:
        return None
    stat_end = stat_text.rfind(")")
    if stat_end < 0:
        return None
    stat_fields = stat_text[stat_end + 2 :].split()
    if len(stat_fields) < 20:
        return None
    if stat_fields[0].upper().startswith("Z"):
        return None
    return {
        "pid": pid,
        "source": "proc",
        "start_token": f"proc:{stat_fields[19]}",
        "argv": argv,
        "command_line": " ".join(shlex.quote(arg) for arg in argv),
    }


def _ps_field(pid: int, field: str) -> str | None:
    try:
        result = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", f"{field}="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _read_ps_process_identity(pid: int) -> dict[str, Any] | None:
    stat = _ps_field(pid, "stat")
    if stat and stat.lstrip().upper().startswith("Z"):
        return None
    started = _ps_field(pid, "lstart")
    command_line = _ps_field(pid, "command") or _ps_field(pid, "args")
    if not started or not command_line:
        return None
    argv = _split_command_line(command_line)
    if not argv:
        return None
    return {
        "pid": pid,
        "source": "ps",
        "start_token": f"ps:{started}",
        "argv": argv,
        "command_line": command_line,
    }


def read_process_identity(pid: Any) -> dict[str, Any] | None:
    """Return live process identity strong enough to reject stale PID reuse."""
    value = _coerce_pid(pid)
    if value is None:
        return None
    proc_identity = _read_proc_process_identity(value)
    if proc_identity is not None:
        return proc_identity
    return _read_ps_process_identity(value)


def _identity_pid(identity: dict[str, Any]) -> int | None:
    return _coerce_pid(identity.get("pid"))


def _identity_start_token(identity: dict[str, Any]) -> str:
    return str(identity.get("start_token") or "").strip()


def _identity_argv(identity: dict[str, Any]) -> list[str]:
    argv = identity.get("argv")
    if isinstance(argv, list) and all(isinstance(part, str) for part in argv):
        return list(argv)
    command_line = str(identity.get("command_line") or "").strip()
    if not command_line:
        return []
    return _split_command_line(command_line)


def _identity_matches_drainer_command(
    identity: dict[str, Any],
    command: list[str],
) -> bool:
    argv = _identity_argv(identity)
    if len(argv) != len(command):
        return False
    if not argv or not str(argv[0]).strip():
        return False
    # macOS may report the resolved Python.app executable even when Popen was
    # invoked through sys.executable's Homebrew symlink. The stable drainer
    # identity is the receiver script plus repo/bus/timeout/--once arguments;
    # PID + start-token still provide the anti-PID-reuse proof.
    return argv[1:] == command[1:]


def _atomic_write_text(path: Path, text: str) -> None:
    """Durably write *text* to *path* via temp-file + ``os.replace``.

    The replace is atomic on POSIX, so a reader never observes a half-written
    queue entry -- this is what makes the enqueue itself the quick-ack.
    """
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


def _excerpt(value: str, limit: int = 240) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _terminate_process_group(proc: "subprocess.Popen[str]", *, grace_s: float = PROCESS_GROUP_GRACE_S) -> None:
    """Kill the child's whole process group (SIGTERM, then SIGKILL on grace).

    Mirrors ``pipeline_agent_pager._terminate_process_group``: the child is
    launched with ``start_new_session=True`` so it is its own group leader, and
    a delivery timeout reaps the entire group rather than orphaning grandchildren.
    """
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return
    try:
        proc.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        return
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        return


def _load_claude_dispatch_env():
    """Resolve ``pipeline_agent_pager._claude_dispatch_env`` (READ-ONLY reuse).

    Tries a normal import first, then falls back to a by-path load of the sibling
    observability module -- the same import discipline the pager itself uses for
    ``executor_common``. The pager module is loaded only to borrow this one pure
    helper; nothing in it is mutated and no daemon is started.
    """
    try:
        from pipeline_agent_pager import _claude_dispatch_env as fn  # type: ignore
        return fn
    except Exception:
        pass
    import importlib.util as _ilu

    pager_path = SCRIPT_DIR.parent / "observability" / "pipeline_agent_pager.py"
    spec = _ilu.spec_from_file_location("pipeline_agent_pager", str(pager_path))
    if spec is None or spec.loader is None:
        raise ClaudePagerReceiverError(f"cannot load pipeline_agent_pager from {pager_path}")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._claude_dispatch_env


def _load_resolve_claude_page_delivery():
    """Resolve ``pipeline_agent_pager.resolve_claude_page_delivery`` (READ-ONLY reuse).

    Same import discipline as ``_load_claude_dispatch_env``: a normal import first,
    then a by-path load of the sibling observability module. The pager owns the
    resume-vs-fresh decision and the never-resume-the-live-orchestrator guard
    (codex-parity); the receiver borrows this PURE resolver and calls it at delivery
    time with its own ``repo_root`` + ``bus_dir``. Nothing in the pager module is
    mutated and no daemon is started.
    """
    try:
        from pipeline_agent_pager import resolve_claude_page_delivery as fn  # type: ignore
        return fn
    except Exception:
        pass
    import importlib.util as _ilu

    pager_path = SCRIPT_DIR.parent / "observability" / "pipeline_agent_pager.py"
    spec = _ilu.spec_from_file_location("pipeline_agent_pager", str(pager_path))
    if spec is None or spec.loader is None:
        raise ClaudePagerReceiverError(f"cannot load pipeline_agent_pager from {pager_path}")
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resolve_claude_page_delivery


_CLAUDE_DISPATCH_ENV = _load_claude_dispatch_env()
_RESOLVE_CLAUDE_PAGE_DELIVERY = _load_resolve_claude_page_delivery()


def delivery_env() -> dict[str, str]:
    """Environment for a FRESH (resume-less) delivery subprocess.

    Thin public wrapper over the pager's ``_claude_dispatch_env`` so the
    session-id-clobber-prevention contract (sets ``RCX_PIPELINE_SESSION=1``,
    clears ``RCX_CLAUDE_MONITOR``) is reused verbatim rather than reimplemented.
    The resume-the-monitor leg uses the pager's ``_claude_monitor_resume_env``
    (``RCX_CLAUDE_MONITOR=1``) instead, returned inside the delivery plan from
    ``resolve_claude_page_delivery``.
    """
    return _CLAUDE_DISPATCH_ENV()


def event_keys(event: dict[str, Any]) -> set[str]:
    """Idempotency key-set for *event*: its non-empty ``event_id`` ONLY (PR #1137 P2).

    ``transition_key`` is deliberately EXCLUDED. It is not a unique event identity:
    the pager hashes ``event_type`` / ``state`` / ``phase`` plus ``transition_key``
    into a distinct ``event_id``, so two genuinely-distinct pager events can share a
    ``transition_key``. Including it in the dedup key collapsed those distinct events
    -- the second enqueue returned a duplicate and was silently dropped while the
    receipt-bridge (which promotes by ``event_id``) left it pending forever. Keying on
    ``event_id`` only keeps distinct same-``transition_key`` events distinct.

    Returns a 0-or-1 element set so the existing ``keys & delivered``/``keys & queued``
    intersection logic is unchanged; an event with no ``event_id`` yields the empty
    set (``enqueue`` rejects it).
    """
    event_id = str(event.get("event_id") or "").strip()
    return {event_id} if event_id else set()


class ClaudePagerReceiver:
    """File-queue inbox + serialized single-flight delivery.

    Delivery is codex-parity: a page is delivered INTO the persistent dedicated
    monitor (``claude --resume <monitor>``) when one is configured + distinct from
    the live orchestrator + resumable, else a fresh, resume-less ``claude -p`` (the
    resume-vs-fresh decision is the pager's ``resolve_claude_page_delivery``, applied
    at delivery time; the live orchestrator is never resumed).
    """

    def __init__(
        self,
        repo_root: str | Path,
        *,
        bus_dir: str = DEFAULT_BUS_DIR,
        claude_bin: str | None = None,
        timeout_s: float = DEFAULT_DELIVERY_TIMEOUT_S,
        poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.bus_dir = bus_dir
        self.claude_bin = claude_bin or os.environ.get(CLAUDE_BIN_ENV, "claude")
        self.timeout_s = float(timeout_s)
        self.poll_interval_s = float(poll_interval_s)
        self._base = self.repo_root / bus_dir / "observability" / "claude_pager_receiver"
        self._queue_dir = self._base / "queue"
        self._log_dir = self._base / "delivery_logs"
        self._receipts_path = self._base / "delivered.jsonl"
        self._delivery_lock_path = self._base / "delivery.lock"
        self._queue_lock_path = self._base / "queue.lock"
        self._drainer_lock_path = self._base / "drainer.lock"
        self._drainer_state_path = self._base / "active_drainer.json"
        # Single-flight (long) vs queue-mutation (short) are DISTINCT locks so a
        # 120s in-flight delivery never blocks the atomic-enqueue quick-ack.
        # Spawn decisions use a third lock: delivery.lock serializes actual Claude
        # children, but it cannot prevent many detached --once drainers from piling
        # up behind that delivery lock.
        self._delivery_thread_lock = threading.Lock()
        self._queue_thread_lock = threading.Lock()
        self._drainer_thread_lock = threading.Lock()
        self._seq = itertools.count()

    # -- public read surface --------------------------------------------------

    @property
    def queue_dir(self) -> Path:
        return self._queue_dir

    @property
    def receipts_path(self) -> Path:
        return self._receipts_path

    def queued_event_ids(self) -> list[str]:
        """Event ids currently queued, in FIFO (filename) order."""
        ids: list[str] = []
        for path in self._ordered_queue_files():
            event = self._read_queue_file(path)
            if event is not None:
                ids.append(str(event.get("event_id") or "").strip())
        return ids

    def delivered_event_ids(self) -> set[str]:
        """Event ids that have a durable delivery receipt."""
        return {
            str(record.get("event_id") or "").strip()
            for record in self._delivered_records()
            if str(record.get("event_id") or "").strip()
        }

    def delivery_command(
        self, event: dict[str, Any], *, resume_session_id: str | None = None
    ) -> list[str]:
        """Delivery argv.

        When ``resume_session_id`` is a non-empty id, the page is delivered INTO that
        persistent session with tools mechanically denied:
        ``claude --resume <id> -p <prompt> --disallowedTools ...`` (codex-parity --
        the page becomes a turn in the warm dedicated monitor). Otherwise it is a
        fresh, resume-less ``claude -p`` page. The resume target is resolved by the
        pager's ``resolve_claude_page_delivery`` at delivery time (NEVER the live
        orchestrator); this method only builds the argv from the resolved decision.
        """
        resume_id = str(resume_session_id or "").strip()
        if resume_id:
            return [
                self.claude_bin,
                "--resume",
                resume_id,
                "-p",
                self._event_prompt(event),
                "--disallowedTools",
                *CLAUDE_RESUME_DISALLOWED_TOOLS,
            ]
        return [self.claude_bin, "-p", self._event_prompt(event)]

    # -- enqueue (the quick-ack) ---------------------------------------------

    def enqueue(self, event: dict[str, Any]) -> dict[str, Any]:
        """Atomically queue *event*; the durable write IS the quick-ack.

        Idempotent: an event whose key-set intersects an already-delivered or
        already-queued event is not re-queued. Holds only the SHORT queue lock so
        it returns immediately even while a delivery is in flight.
        """
        keys = event_keys(event)
        if not keys:
            raise ClaudePagerReceiverError(
                "event requires a non-empty event_id"
            )
        primary = str(event.get("event_id") or "").strip()
        with self._queue_guard():
            if keys & self._delivered_keys():
                return {"status": "duplicate_delivered", "event_id": primary, "queue_path": None}
            if keys & self._queued_keys():
                return {"status": "duplicate_queued", "event_id": primary, "queue_path": None}
            queue_path = self._atomic_write_event(event)
        return {"status": "queued", "event_id": primary, "queue_path": str(queue_path)}

    # -- ensure-draining (the start-if-not-running entry) ---------------------

    def ensure_draining(self) -> dict[str, Any]:
        """Start a bounded, detached drain pass so a queued event is GUARANTEED to drain.

        This is the minimal idempotent "start-if-not-running" entry the pager calls
        right after it enqueues a page (PR #1137 P1): a durably-queued event always has
        a drain pass started after it, so there is NO never-drained-queue window.

        Mechanism (deliberately minimal -- NO open-ended daemon lifecycle): under a
        per-repo/bus spawn lock, reuse a matching live DETACHED child or spawn one fresh.
        That child runs a SINGLE bounded drain pass (``--once`` -> ``run_until_empty``)
        and then EXITS. There is no owner-loop, no poll-forever, no session-rebuild, and
        no restart-supervision; each ``claude`` page the child makes reuses the existing
        per-delivery timeout + ``_terminate_process_group`` reaper. The child is its own
        session/process-group (``start_new_session=True``) so it outlives this short-lived
        pager invocation.

        Idempotent and safe under concurrency WITH spawn suppression: ``delivery.lock``
        still serializes actual ``claude`` children, while ``drainer.lock`` prevents
        repeated enqueue attempts from spawning an unbounded herd of detached receivers
        waiting behind that delivery lock. Missing, dead, malformed, or command-mismatched
        drainer state is refreshable. A matching live state is accepted as already
        draining. Because the caller enqueues the event BEFORE calling this, a fresh spawn
        observes that event; a live drainer clears its state before reporting idle or
        exhausted, so an enqueue racing with drainer exit starts the next pass instead of
        being hidden behind stale live-pid state.

        Returns ``{"started": True, "pid": ..., "mode": "detached_once"}`` when a new
        drainer starts, or ``{"started": False, "already_draining": True, ...}`` when a
        matching live drainer is already responsible for the repo/bus queue.
        Raises ``ClaudePagerReceiverError`` if the drainer cannot be started, so the pager
        can FAIL-OPEN (leave the target pending rather than accept an undrainable queue).
        """
        self._base.mkdir(parents=True, exist_ok=True)
        spawn_log = self._base / "drain_spawn.log"
        command = self._drain_command()
        with self._drainer_guard():
            active = self._matching_live_drainer_state(command)
            if active is not None:
                return {
                    "started": False,
                    "already_draining": True,
                    "accepted": True,
                    "pid": active["pid"],
                    "mode": "detached_once",
                    "status": "already_draining",
                    "state_path": str(self._drainer_state_path),
                }
            try:
                with spawn_log.open("a", encoding="utf-8") as sink:
                    proc = subprocess.Popen(
                        command,
                        cwd=str(self.repo_root),
                        stdin=subprocess.DEVNULL,
                        stdout=sink,
                        stderr=subprocess.STDOUT,
                        text=True,
                        # Own session/process-group: outlives the pager invocation and lets
                        # each delivery's timeout reaper kill the whole claude child group.
                        start_new_session=True,
                        env=os.environ.copy(),
                    )
            except OSError as exc:
                raise ClaudePagerReceiverError(
                    f"claude pager drain spawn failed: {exc}"
                ) from exc
            self._write_drainer_state(command=command, pid=proc.pid)
        return {
            "started": True,
            "accepted": True,
            "pid": proc.pid,
            "mode": "detached_once",
            "status": "started",
            "state_path": str(self._drainer_state_path),
        }

    # -- delivery (single-flight) --------------------------------------------

    def deliver_once(self, *, skip_keys: "set[str] | None" = None) -> dict[str, Any]:
        """Deliver the oldest queued event (single-flight), if any.

        Returns a status dict. ``idle`` when the queue is empty. On exit-0 a
        receipt is written and the entry removed (``delivered``); on timeout or
        non-zero exit the entry is re-queued fail-open (``requeued``).

        ``skip_keys`` lets a single drain pass (``run_until_empty``) avoid
        re-attempting an event it has already tried this pass: if the oldest
        queued event's idempotency keys intersect ``skip_keys`` the call returns
        ``exhausted`` WITHOUT spawning a delivery, so a persistently-failing
        event is attempted at most once per drain.
        """
        with self._delivery_guard():
            with self._queue_guard():
                queue_files = self._ordered_queue_files()
                if not queue_files:
                    self._clear_current_drainer_state()
                    return {"status": "idle"}
                queue_path = queue_files[0]
                event = self._read_queue_file(queue_path)
                if event is None:
                    queue_path.unlink(missing_ok=True)
                    return {"status": "dropped_unreadable", "queue_path": str(queue_path)}
                event_id = str(event.get("event_id") or "").strip()
                if self._already_delivered(event):
                    # Terminal idempotency: a duplicate is dropped, never re-delivered.
                    queue_path.unlink(missing_ok=True)
                    return {"status": "duplicate_delivered", "event_id": event_id}
                if skip_keys and (event_keys(event) & skip_keys):
                    # The oldest queued event was already attempted (and re-queued)
                    # this drain pass -> only persistently-failing events remain.
                    # Report ``exhausted`` so ``run_until_empty`` stops WITHOUT a
                    # second delivery (honors "attempted at most once per call").
                    self._clear_current_drainer_state()
                    return {"status": "exhausted", "event_id": event_id}
            # Dispatch OUTSIDE the queue lock (but still single-flight) so a slow
            # delivery never blocks concurrent enqueues' quick-ack.
            result = self._dispatch(event)
            with self._queue_guard():
                if result.get("delivered"):
                    self._write_receipt(event, result.get("ack", {}))
                    queue_path.unlink(missing_ok=True)
                    return {
                        "status": "delivered",
                        "event_id": event_id,
                        "ack": result.get("ack", {}),
                    }
                # Fail-open: re-queue (write-before-delete so it is never lost).
                self._requeue(event, queue_path, error=str(result.get("error") or ""))
                return {
                    "status": "requeued",
                    "event_id": event_id,
                    # Full idempotency key-set so a single drain pass can dedup and
                    # avoid re-attempting this event (see ``run_until_empty``).
                    "keys": sorted(event_keys(event)),
                    "timed_out": bool(result.get("timed_out")),
                    "error": str(result.get("error") or ""),
                }

    def run_until_empty(self, max_iterations: int = 10_000) -> list[dict[str, Any]]:
        """Drain deliverable events once. Stops when only failing events remain.

        Each queued event is attempted AT MOST ONCE per call: a re-queued
        (persistently failing) event is recorded by its idempotency key-set, and
        when the drain head comes back around to an already-attempted event the
        pass stops (``deliver_once`` reports ``exhausted``). A poison entry can
        therefore never spin this into an unbounded -- or even repeated -- loop
        within a single call.
        """
        results: list[dict[str, Any]] = []
        attempted: set[str] = set()
        for _ in range(max_iterations):
            result = self.deliver_once(skip_keys=attempted)
            status = result.get("status")
            if status in ("idle", "exhausted"):
                break
            results.append(result)
            if status == "requeued":
                keys = result.get("keys") or []
                if not keys:
                    # No resolvable idempotency key -> cannot dedup this event;
                    # stop rather than risk re-attempting it in a tight loop.
                    break
                attempted.update(keys)
        return results

    def run_forever(
        self,
        *,
        stop_event: "threading.Event | None" = None,
        max_idle_cycles: int | None = None,
        poll_interval_s: float | None = None,
    ) -> None:
        """Poll loop: drain, then back off when a cycle makes no durable progress.

        "Progress" means at least one event left the queue durably this cycle
        (delivered / duplicate-dropped / unreadable-dropped). A cycle that only
        re-queued persistently-failing events is NOT progress: the loop backs off
        for the poll interval instead of immediately retrying, so a poison event
        can never tight-loop the daemon. The backoff is interruptible by
        ``stop_event`` so shutdown stays prompt even with a long poll interval.
        ``poll_interval_s`` optionally overrides the receiver's configured cadence
        for this run. (Not wired in Wave 1.)
        """
        interval = self.poll_interval_s if poll_interval_s is None else float(poll_interval_s)
        no_progress_cycles = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            results = self.run_until_empty()
            if any(result.get("status") in _DRAIN_PROGRESS_STATUSES for result in results):
                # The queue advanced this cycle -> keep draining immediately.
                no_progress_cycles = 0
                continue
            # Idle, or only persistently-failing requeues this cycle: back off so
            # a poison event retries at the poll cadence, never in a tight loop.
            no_progress_cycles += 1
            if max_idle_cycles is not None and no_progress_cycles >= max_idle_cycles:
                return
            if stop_event is not None:
                if stop_event.wait(interval):
                    return
            else:
                time.sleep(interval)

    # -- internals ------------------------------------------------------------

    @contextmanager
    def _guarded(self, thread_lock: threading.Lock, lock_path: Path) -> Iterator[None]:
        thread_lock.acquire()
        self._base.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
                thread_lock.release()

    def _delivery_guard(self) -> "Iterator[None]":
        return self._guarded(self._delivery_thread_lock, self._delivery_lock_path)

    def _queue_guard(self) -> "Iterator[None]":
        return self._guarded(self._queue_thread_lock, self._queue_lock_path)

    def _drainer_guard(self) -> "Iterator[None]":
        return self._guarded(self._drainer_thread_lock, self._drainer_lock_path)

    def _drain_command(self) -> list[str]:
        return [
            sys.executable,
            _RECEIVER_SCRIPT,
            "--repo-root", str(self.repo_root),
            "--bus-dir", self.bus_dir,
            "--timeout-s", str(self.timeout_s),
            "--once",
        ]

    def _read_drainer_state(self) -> dict[str, Any] | None:
        try:
            payload = json.loads(self._drainer_state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return payload if isinstance(payload, dict) else None

    def _pid_is_live(self, pid: Any) -> bool:
        value = _coerce_pid(pid)
        if value is None:
            return False
        try:
            os.kill(value, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except (OSError, OverflowError):
            return False
        return True

    def _drainer_process_identity_matches(
        self,
        *,
        state: dict[str, Any],
        pid: int,
        command: list[str],
    ) -> bool:
        recorded = state.get("process_identity")
        if not isinstance(recorded, dict):
            return False
        live = read_process_identity(pid)
        if live is None:
            return False
        if _identity_pid(recorded) != pid or _identity_pid(live) != pid:
            return False
        if not _identity_start_token(recorded):
            return False
        if _identity_start_token(recorded) != _identity_start_token(live):
            return False
        if not _identity_matches_drainer_command(recorded, command):
            return False
        if not _identity_matches_drainer_command(live, command):
            return False
        return True

    def _matching_live_drainer_state(self, command: list[str]) -> dict[str, Any] | None:
        state = self._read_drainer_state()
        if state is None:
            return None
        pid = state.get("pid")
        if list(state.get("command") or []) != command:
            return None
        if str(state.get("repo_root") or "") != str(self.repo_root):
            return None
        if str(state.get("bus_dir") or "") != str(self.bus_dir):
            return None
        if str(state.get("mode") or "") != "detached_once":
            return None
        if not self._pid_is_live(pid):
            return None
        try:
            live_pid = int(pid)
        except (TypeError, ValueError):
            return None
        if not self._drainer_process_identity_matches(
            state=state,
            pid=live_pid,
            command=command,
        ):
            return None
        return {"pid": live_pid, "state": state}

    def _write_drainer_state(self, *, command: list[str], pid: int) -> None:
        state = {
            "pid": int(pid),
            "mode": "detached_once",
            "command": list(command),
            "repo_root": str(self.repo_root),
            "bus_dir": str(self.bus_dir),
            "timeout_s": self.timeout_s,
            "started_at": _utcnow(),
        }
        process_identity = read_process_identity(pid)
        if process_identity is not None:
            state["process_identity"] = process_identity
        _atomic_write_text(
            self._drainer_state_path,
            json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n",
        )

    def _clear_current_drainer_state(self) -> None:
        command = self._drain_command()
        pid = os.getpid()
        with self._drainer_guard():
            state = self._read_drainer_state()
            if state is None:
                return
            try:
                state_pid = int(state.get("pid", -1) or -1)
            except (TypeError, ValueError):
                return
            if state_pid != pid:
                return
            if list(state.get("command") or []) != command:
                return
            self._drainer_state_path.unlink(missing_ok=True)

    def _ordered_queue_files(self) -> list[Path]:
        if not self._queue_dir.is_dir():
            return []
        return sorted(path for path in self._queue_dir.glob("*.json") if path.is_file())

    def _read_queue_file(self, path: Path) -> dict[str, Any] | None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            return None
        return event if isinstance(event, dict) else None

    def _atomic_write_event(self, event: dict[str, Any]) -> Path:
        self._queue_dir.mkdir(parents=True, exist_ok=True)
        keyfrag = (
            str(event.get("event_id") or "").strip()
            or str(event.get("transition_key") or "").strip()
            or "event"
        )
        safe = "".join(ch if (ch.isalnum() or ch in "-_") else "-" for ch in keyfrag)[:32]
        # ``time.time_ns()`` gives a monotone FIFO prefix; the per-receiver counter
        # breaks any same-nanosecond ties so ordering stays deterministic.
        name = f"{time.time_ns():020d}-{next(self._seq):06d}-{safe}.json"
        queue_path = self._queue_dir / name
        _atomic_write_text(
            queue_path,
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n",
        )
        return queue_path

    def _queued_keys(self) -> set[str]:
        keys: set[str] = set()
        for path in self._ordered_queue_files():
            event = self._read_queue_file(path)
            if event is not None:
                keys |= event_keys(event)
        return keys

    def _delivered_records(self) -> list[dict[str, Any]]:
        if not self._receipts_path.exists():
            return []
        try:
            text = self._receipts_path.read_text(encoding="utf-8")
        except OSError:
            return []
        records: list[dict[str, Any]] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records

    def _delivered_keys(self) -> set[str]:
        # Event_id ONLY (PR #1137 P2), mirroring ``event_keys``: a receipt's
        # ``transition_key`` is informational and must not dedup a distinct event
        # that merely reuses it.
        keys: set[str] = set()
        for record in self._delivered_records():
            value = str(record.get("event_id") or "").strip()
            if value:
                keys.add(value)
        return keys

    def _already_delivered(self, event: dict[str, Any]) -> bool:
        return bool(event_keys(event) & self._delivered_keys())

    def _write_receipt(self, event: dict[str, Any], ack: dict[str, Any]) -> None:
        self._base.mkdir(parents=True, exist_ok=True)
        receipt = {
            "event_id": str(event.get("event_id") or "").strip(),
            "transition_key": str(event.get("transition_key") or "").strip(),
            "ack": ack,
            "recorded_at": _utcnow(),
        }
        with self._receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")

    def _requeue(self, event: dict[str, Any], queue_path: Path, *, error: str) -> None:
        requeued = dict(event)
        attempts = int(requeued.get("_delivery_attempts", 0) or 0) + 1
        requeued["_delivery_attempts"] = attempts
        requeued["_last_delivery_error"] = _excerpt(error)
        # Write the new (back-of-queue) entry BEFORE removing the old one so the
        # event is never momentarily absent from the durable queue.
        self._atomic_write_event(requeued)
        queue_path.unlink(missing_ok=True)

    def _delivery_log_path(self, event: dict[str, Any]) -> Path:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        event_id = (str(event.get("event_id") or "").strip() or "event")[:16]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        return self._log_dir / f"claude_pager_{stamp}_{event_id}.log"

    def _event_prompt(self, event: dict[str, Any]) -> str:
        lines = [
            "WorkingRCX pipeline quick-ack page.",
            f"event_id: {str(event.get('event_id') or '').strip()}",
            f"transition_key: {str(event.get('transition_key') or '').strip()}",
            f"event_type: {str(event.get('event_type') or '').strip()}",
            f"wave_id: {str(event.get('wave_id') or '').strip()}",
            f"task_id: {str(event.get('task_id') or '').strip()}",
            f"phase: {str(event.get('phase') or '').strip()}",
            f"state: {str(event.get('state') or '').strip()}",
            f"summary: {str(event.get('summary') or '').strip()}",
            "Use these authoritative facts directly; do not re-scrape the repo.",
            "Do not run shell commands, tests, preflight, docs checks, or tools "
            "from this headless page path.",
            "Do not launch or relaunch executor_dispatch.py, phase_a_executor.py, "
            "phase_b_executor.py, commit_executor.py, or bridge_supervisor.py.",
        ]
        return "\n".join(lines)

    def _resolve_delivery_plan(self) -> dict[str, Any]:
        """Resolve the delivery target (resume-the-monitor vs fresh) at DELIVERY time.

        Borrows the pager's ``resolve_claude_page_delivery`` so the resume-vs-fresh
        decision AND the never-resume-the-live-orchestrator guard are computed from the
        SAME session-id files and logic the pager owns, evaluated against THIS receiver's
        ``repo_root`` + ``bus_dir`` at the moment of delivery (the detached drain
        subprocess has no ContextVar bus set, so the explicit ``bus_dir`` is required).

        Returns ``{"mode": "resume", "monitor_session_id": <id>, "env": <resume env>}``
        ONLY when the resolver clearly elects a resume with a well-formed monitor id and
        a delivery env; EVERYTHING else (unset / equals-live / malformed / any resolution
        error) degrades to ``{"mode": "fresh", "monitor_session_id": None, "env":
        delivery_env()}``. Fail-open and never-resume-live by construction: a fresh page
        is the safe default, so a flaky resolver can never resume the wrong session or
        lose a page.
        """
        try:
            plan = _RESOLVE_CLAUDE_PAGE_DELIVERY(self.repo_root, bus_dir=self.bus_dir)
            if (
                isinstance(plan, dict)
                and plan.get("mode") == "resume"
                and str(plan.get("monitor_session_id") or "").strip()
                and isinstance(plan.get("env"), dict)
            ):
                return {
                    "mode": "resume",
                    "monitor_session_id": str(plan["monitor_session_id"]).strip(),
                    "env": plan["env"],
                }
        except Exception:
            # Fail-open: any resolver error -> fresh, resume-less page.
            pass
        return {"mode": "fresh", "monitor_session_id": None, "env": delivery_env()}

    def _run_delivery(
        self,
        event: dict[str, Any],
        *,
        command: list[str],
        env: dict[str, str],
        mode: str,
        monitor_session_id: str | None = None,
    ) -> dict[str, Any]:
        """Launch ONE ``claude`` page child and reap it (shared by the resume + fresh legs).

        Single source of the subprocess + ~120s timeout + process-group reaper behavior:
        the child runs in its own session/process-group (``start_new_session=True``) so a
        timeout reaps the whole group via ``_terminate_process_group``. Returns the
        ``{delivered, ack|error, timed_out}`` shape ``deliver_once`` already consumes. On
        exit-0 the ack carries ``mode`` (``"resume"`` or ``"direct"``) and, for a resume,
        the ``monitor_session_id`` it paged into.
        """
        log_path = self._delivery_log_path(event)
        try:
            with log_path.open("w", encoding="utf-8") as sink:
                proc = subprocess.Popen(
                    command,
                    cwd=str(self.repo_root),
                    stdin=subprocess.DEVNULL,
                    stdout=sink,
                    stderr=subprocess.STDOUT,
                    text=True,
                    # Own session/process-group so a timeout reaps the whole group.
                    start_new_session=True,
                    env=env,
                )
        except OSError as exc:
            return {"delivered": False, "error": f"claude pager delivery launch failed: {exc}"}

        try:
            exit_code = proc.wait(timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            _terminate_process_group(proc)
            return {
                "delivered": False,
                "timed_out": True,
                "error": f"claude pager delivery timed out after {self.timeout_s:.3g}s",
            }
        if exit_code != 0:
            detail = ""
            try:
                detail = _excerpt(log_path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                detail = ""
            return {
                "delivered": False,
                "error": (
                    f"claude pager delivery exited {exit_code}"
                    + (f": {detail}" if detail else "")
                ),
            }
        ack = {
            "acknowledged_at": _utcnow(),
            "exit_code": exit_code,
            "target": "claude",
            "mode": mode,
            "pid": proc.pid,
            "log_path": str(log_path),
        }
        resume_id = str(monitor_session_id or "").strip()
        if resume_id:
            ack["monitor_session_id"] = resume_id
        return {"delivered": True, "ack": ack}

    def _dispatch(self, event: dict[str, Any]) -> dict[str, Any]:
        """Deliver one page: resume the warm monitor when configured, else a fresh page.

        Codex-parity: page INTO the persistent dedicated monitor
        (``claude --resume <claude_monitor_session_id>``) when the resolver elects a
        resume (monitor set + distinct from the live orchestrator + resumable), mirroring
        how the codex leg issues each turn into the shared autoping thread. On a resume
        FAILURE (stale/dead monitor -- the claude mirror of codex's stale-thread case)
        FALL BACK to a fresh, resume-less ``claude -p`` page in the SAME delivery, so no
        page is lost and the live orchestrator is never resumed. When the resolver elects
        fresh (MONITOR_UNSET / MONITOR_EQUALS_LIVE / resolution error) a single fresh page
        is delivered. Every leg reuses ``_run_delivery`` (same timeout + reaper), and the
        whole call stays under ``deliver_once``'s single delivery lock, so at most one
        ``claude`` child is ever in flight.
        """
        plan = self._resolve_delivery_plan()
        if plan["mode"] == "resume":
            monitor_id = plan["monitor_session_id"]
            result = self._run_delivery(
                event,
                command=self.delivery_command(event, resume_session_id=monitor_id),
                env=plan["env"],
                mode="resume",
                monitor_session_id=monitor_id,
            )
            if result.get("delivered"):
                return result
            # Resume failed (stale/dead monitor): fall back to a fresh page so the page is
            # still delivered. Mirrors codex starting a NEW thread on a stale-thread error
            # -- the page is never dropped because the dedicated monitor was unusable.
            fresh = self._run_delivery(
                event,
                command=self.delivery_command(event),
                env=delivery_env(),
                mode="direct",
            )
            if fresh.get("delivered"):
                fresh["ack"]["resume_fallback_from"] = monitor_id
            else:
                fresh["error"] = (
                    f"claude --resume {monitor_id} failed "
                    f"({_excerpt(str(result.get('error') or ''))}); "
                    f"fresh page fallback also failed "
                    f"({_excerpt(str(fresh.get('error') or ''))})"
                )
                if result.get("timed_out") or fresh.get("timed_out"):
                    fresh["timed_out"] = True
            return fresh
        # Fresh leg (MONITOR_UNSET / MONITOR_EQUALS_LIVE / resolution error).
        return self._run_delivery(
            event,
            command=self.delivery_command(event),
            env=plan["env"],
            mode="direct",
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Claude quick-ack pager receiver. Drains a per-bus file-queue, "
            "delivering each page INTO the persistent dedicated monitor "
            "(`claude --resume <monitor>`) when one is configured + distinct from "
            "the live orchestrator, else a fresh `claude -p` page."
        )
    )
    parser.add_argument("--repo-root", default=".", help="Repo root (default: cwd).")
    parser.add_argument("--bus-dir", default=DEFAULT_BUS_DIR, help="Agent bus dir.")
    parser.add_argument(
        "--timeout-s", type=float, default=DEFAULT_DELIVERY_TIMEOUT_S,
        help="Per-delivery timeout in seconds.",
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Drain the queue once and exit (no poll loop).",
    )
    args = parser.parse_args(argv)
    receiver = ClaudePagerReceiver(
        Path(args.repo_root),
        bus_dir=args.bus_dir,
        timeout_s=args.timeout_s,
    )
    if args.once:
        try:
            for result in receiver.run_until_empty():
                print(json.dumps(result, sort_keys=True))
        finally:
            receiver._clear_current_drainer_state()
        return 0
    receiver.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
