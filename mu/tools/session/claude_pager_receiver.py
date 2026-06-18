#!/usr/bin/env python3
"""Dormant Claude quick-ack pager receiver (pager-quickack Wave 1).

DORMANCY CONTRACT (Wave 1): this module is intentionally DORMANT. Nothing in the
tree imports, wires, or starts it. The only cross-module coupling is a READ-ONLY
reuse of ``pipeline_agent_pager._claude_dispatch_env`` for the delivery
subprocess environment. Pager wiring (Wave 2) and preflight/daemon auto-start
(Wave 3) are explicitly OUT of scope here.

What it provides (the seven behaviors locked by
``mu/tests/tools/test_claude_pager_receiver.py``):

1. Per-bus file-queue inbox. The atomic enqueue IS the quick-ack: ``enqueue``
   durably writes the event to the per-bus queue dir (temp-file + ``os.replace``)
   and returns as soon as it is queued. Enqueue takes only a SHORT queue lock, so
   an in-flight (slow) delivery NEVER blocks the quick-ack.

2. Serialized, single-flight delivery. ``deliver_once`` holds a SEPARATE delivery
   lock for the whole call, so at most one ``claude`` child is ever in flight.

3. Fresh ``claude -p`` delivery, run asynchronously, NEVER ``--resume``. The
   delivery argv is always ``[claude_bin, "-p", prompt]`` -- a direct page that
   resumes no session.

4. ~120s per-delivery timeout plus a process-group reaper. The child runs in its
   own session/process-group (``start_new_session=True``); on timeout the whole
   group is killed (``os.killpg``) via ``_terminate_process_group``.

5. Delivery environment via ``pipeline_agent_pager._claude_dispatch_env`` -- marks
   the child a pipeline-owned sub-session and clears ``RCX_CLAUDE_MONITOR`` so the
   transient page never clobbers ``orchestrator_session_id`` /
   ``claude_monitor_session_id``.

6. Exit-0 -> durable receipt; non-zero exit or timeout -> fail-open re-queue (the
   event is re-written to the back of the queue and is never lost).

7. Idempotency keyed by ``event_id`` / ``transition_key``. A duplicate event
   (one whose id-set intersects an already-delivered or already-queued event) is
   not re-queued and not re-delivered.

This is additive, observability-only tooling. It touches no runtime/substrate
surface (``rcx_pi/selfhost/`` or ``mu/host/``) and introduces no host semantics.
"""

from __future__ import annotations

import argparse
import fcntl
import itertools
import json
import os
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


class ClaudePagerReceiverError(RuntimeError):
    """Raised when receiver inbox/delivery handling fails."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


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


_CLAUDE_DISPATCH_ENV = _load_claude_dispatch_env()


def delivery_env() -> dict[str, str]:
    """Environment for the delivery subprocess.

    Thin public wrapper over the pager's ``_claude_dispatch_env`` so the
    session-id-clobber-prevention contract (sets ``RCX_PIPELINE_SESSION=1``,
    clears ``RCX_CLAUDE_MONITOR``) is reused verbatim rather than reimplemented.
    """
    return _CLAUDE_DISPATCH_ENV()


def event_keys(event: dict[str, Any]) -> set[str]:
    """Idempotency key-set for *event*: its non-empty ``event_id`` / ``transition_key``."""
    keys: set[str] = set()
    for field in ("event_id", "transition_key"):
        value = str(event.get(field) or "").strip()
        if value:
            keys.add(value)
    return keys


class ClaudePagerReceiver:
    """File-queue inbox + serialized fresh-``claude -p`` delivery (dormant)."""

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
        # Single-flight (long) vs queue-mutation (short) are DISTINCT locks so a
        # 120s in-flight delivery never blocks the atomic-enqueue quick-ack.
        self._delivery_thread_lock = threading.Lock()
        self._queue_thread_lock = threading.Lock()
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

    def delivery_command(self, event: dict[str, Any]) -> list[str]:
        """Delivery argv: always a fresh ``claude -p`` page -- NEVER ``--resume``."""
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
                "event requires a non-empty event_id or transition_key"
            )
        event_id = str(event.get("event_id") or "").strip()
        primary = event_id or sorted(keys)[0]
        with self._queue_guard():
            if keys & self._delivered_keys():
                return {"status": "duplicate_delivered", "event_id": primary, "queue_path": None}
            if keys & self._queued_keys():
                return {"status": "duplicate_queued", "event_id": primary, "queue_path": None}
            queue_path = self._atomic_write_event(event)
        return {"status": "queued", "event_id": primary, "queue_path": str(queue_path)}

    # -- delivery (single-flight) --------------------------------------------

    def deliver_once(self) -> dict[str, Any]:
        """Deliver the oldest queued event (single-flight), if any.

        Returns a status dict. ``idle`` when the queue is empty. On exit-0 a
        receipt is written and the entry removed (``delivered``); on timeout or
        non-zero exit the entry is re-queued fail-open (``requeued``).
        """
        with self._delivery_guard():
            with self._queue_guard():
                queue_files = self._ordered_queue_files()
                if not queue_files:
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
                    "timed_out": bool(result.get("timed_out")),
                    "error": str(result.get("error") or ""),
                }

    def run_until_empty(self, max_iterations: int = 10_000) -> list[dict[str, Any]]:
        """Drain deliverable events once. Stops when only failing events remain.

        A re-queued (persistently failing) event is attempted at most once per
        call; once every remaining event has been re-queued the drain stops, so a
        poison entry can never spin this into an unbounded loop.
        """
        results: list[dict[str, Any]] = []
        attempted_requeued: set[str] = set()
        for _ in range(max_iterations):
            result = self.deliver_once()
            status = result.get("status")
            if status == "idle":
                break
            results.append(result)
            if status == "requeued":
                event_id = str(result.get("event_id") or "")
                if event_id in attempted_requeued:
                    break
                attempted_requeued.add(event_id)
        return results

    def run_forever(
        self,
        *,
        stop_event: "threading.Event | None" = None,
        max_idle_cycles: int | None = None,
    ) -> None:
        """Poll loop: drain, then sleep when idle. (Not wired in Wave 1.)"""
        idle_cycles = 0
        while True:
            if stop_event is not None and stop_event.is_set():
                return
            results = self.run_until_empty()
            if results:
                idle_cycles = 0
                continue
            idle_cycles += 1
            if max_idle_cycles is not None and idle_cycles >= max_idle_cycles:
                return
            time.sleep(self.poll_interval_s)

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
        keys: set[str] = set()
        for record in self._delivered_records():
            for field in ("event_id", "transition_key"):
                value = str(record.get(field) or "").strip()
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
            "WorkingRCX pipeline quick-ack page (direct, fresh claude -p).",
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

    def _dispatch(self, event: dict[str, Any]) -> dict[str, Any]:
        command = self.delivery_command(event)
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
                    # Reuse the pager's clobber-safe delivery env (no session-id clobber).
                    env=delivery_env(),
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
        return {
            "delivered": True,
            "ack": {
                "acknowledged_at": _utcnow(),
                "exit_code": exit_code,
                "target": "claude",
                # Fresh page resumes nothing -> self-evident ``direct`` mode marker.
                "mode": "direct",
                "pid": proc.pid,
                "log_path": str(log_path),
            },
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Dormant Claude quick-ack pager receiver (Wave 1; not wired into the "
            "pipeline). Drains a per-bus file-queue via fresh `claude -p` pages."
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
        for result in receiver.run_until_empty():
            print(json.dumps(result, sort_keys=True))
        return 0
    receiver.run_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
