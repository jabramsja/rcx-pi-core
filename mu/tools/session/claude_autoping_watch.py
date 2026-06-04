#!/usr/bin/env python3
"""WorkingRCX dedicated Claude monitor autoping watcher.

This is the GENERIC autoping core, mirrored for the DEDICATED Claude monitor.
It keeps the dedicated monitor session warm by periodically resuming it with a
diagnostic keepalive subprocess, exactly the way ``codex_autoping_watch.py``
keeps the Codex monitor thread warm -- but stripped of every codex-app-server
specific (bridge.db polling, tmux integration, thread/turn protocol, fresh-exec
context recovery are all OMITTED).

The monitor session id is resolved ONLY from the dedicated
``<bus_dir>/observability/claude_monitor_session_id`` file, reusing the same
fail-closed discipline as
``pipeline_agent_pager._read_claude_monitor_session_id``. It NEVER resumes
``orchestrator_session_id`` -- pinging the live orchestrator is the interference
the dedicated-monitor design exists to prevent. The live orchestrator id is read
SOLELY for the equal-to-live guard (mirror of
``pipeline_agent_pager._dispatch_claude``'s ``MONITOR_EQUALS_LIVE`` skip), never
as a ``--resume`` target. When the monitor id is absent/malformed, OR equals the
live orchestrator id, the watcher PAUSES (it does not crash and never falls back
to the live orchestrator); it resumes automatically once a clean, DISTINCT id
lands.

GAP-1 (mechanical tool-disable): the keepalive ``claude --resume`` argv carries a
mechanical ``--disallowedTools`` flag covering at minimum ``Bash`` -- the tool
that could otherwise spawn ``executor_dispatch.py`` / ``phase_a_executor.py`` /
``phase_b_executor.py`` / ``commit_executor.py`` / ``bridge_supervisor.py``. The
prompt instruction is only a BACKUP guard.

GAP-2 (stream-json): the keepalive argv passes ``--output-format stream-json``
(with ``--verbose``, required by ``claude -p`` for stream-json) so the watcher
can parse the terminal agent_message text for the one-line ``Autoping summary:``.
"""
from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BUS_DIR = ".agent_bus"
BUS_DIR_RE = re.compile(r"^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$")
DEFAULT_INTERVAL_S = 20.0
DEFAULT_INITIAL_DELAY_S = 30.0
DEFAULT_PING_TIMEOUT_S = 120.0
STATE_VERSION = 1
SUMMARY_PREFIX = "Autoping summary:"
MONITOR_SESSION_ID_FILENAME = "claude_monitor_session_id"
# The LIVE orchestrator session-id file (sibling of the dedicated monitor file).
# Read SOLELY for the equal-to-live guard in ``_resolve_keepalive_session_id`` --
# NEVER as a ``claude --resume`` target.
ORCHESTRATOR_SESSION_ID_FILENAME = "orchestrator_session_id"

# Health vocabulary for the state-file ``status`` field. ``paused`` is the single
# unhealthy/paused signal (monitor id absent or malformed); every other value is
# a live, healthy tick. An operator -- and a future health gate -- reads this
# field directly off the repo-matched state file.
STATUS_INITIAL_DELAY = "initial_delay"
STATUS_PAUSED = "paused"
STATUS_PING_DISPATCHED = "ping_dispatched"
STATUS_WAITING = "waiting_for_prior_ping"
STATUS_PRIOR_FINISHED = "prior_ping_finished"
STATUS_PRIOR_TIMED_OUT = "prior_ping_timed_out"

# Pause reason recorded when the dedicated monitor id is not yet resolvable.
PAUSE_REASON_MONITOR_UNSET = (
    "dedicated claude_monitor_session_id is absent or malformed; "
    "pausing keepalive (never resuming the live orchestrator)"
)
# Pause reason recorded when the dedicated monitor id equals the LIVE orchestrator
# session id. Mirror of ``pipeline_agent_pager``'s ``MONITOR_EQUALS_LIVE`` skip:
# the dedicated monitor must be DISTINCT from the live orchestrator before any
# resume, so this case pauses (never resumes the live orchestrator).
PAUSE_REASON_MONITOR_EQUALS_LIVE = (
    "dedicated claude_monitor_session_id equals the live orchestrator session id; "
    "pausing keepalive (never resuming the live orchestrator)"
)

# GAP-1: mechanically disabled tools for the keepalive resume. ``Bash`` is the
# load-bearing entry (it is the tool that could launch a pipeline executor); the
# edit/write tools are disabled too so the keepalive monitor stays diagnostic and
# read-only, the same spirit as the Codex watcher's ``sandbox_mode="read-only"``.
CLAUDE_KEEPALIVE_DISALLOWED_TOOLS = ("Bash", "Edit", "Write", "NotebookEdit")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _claude_bin() -> str:
    return os.environ.get("RCX_CLAUDE_AUTOPING_CLAUDE_BIN", "claude")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _validate_bus_dir(value: str | None) -> str:
    raw = (value or DEFAULT_BUS_DIR).strip().rstrip("/")
    if (
        not raw
        or "\\" in raw
        or "/" in raw
        or ".." in raw
        or raw.startswith("/")
        or (raw != DEFAULT_BUS_DIR and BUS_DIR_RE.fullmatch(raw) is None)
    ):
        raise ValueError(f"invalid active bus root: {raw!r}")
    return raw


def _observability_dir(repo_root: Path, bus_dir: str) -> Path:
    return repo_root / bus_dir / "observability"


def _resume_env() -> dict[str, str]:
    # Preserve the live shell environment so the keepalive resume inherits the
    # same auth/session context and any repo-local RCX state overlay in use.
    return os.environ.copy()


def _read_monitor_session_id(repo_root: Path, bus_dir: str) -> str | None:
    """Resolve the DEDICATED claude-monitor session id, fail-closed.

    Mirrors ``pipeline_agent_pager._read_claude_monitor_session_id`` exactly: read
    ONLY the dedicated ``claude_monitor_session_id`` file under the observability
    dir, and treat every absent/malformed case as ``None`` (missing file,
    OSError, non-UTF-8 bytes, empty, whitespace-only, internal whitespace). There
    is NO fallback to ``orchestrator_session_id`` -- the live orchestrator
    conversation is never a ``claude --resume`` target.
    """
    monitor_path = _observability_dir(repo_root, bus_dir) / MONITOR_SESSION_ID_FILENAME
    try:
        raw = monitor_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    except UnicodeDecodeError:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if any(ch.isspace() for ch in candidate):
        return None
    return candidate


def _read_orchestrator_session_id(repo_root: Path, bus_dir: str) -> str | None:
    """Read the LIVE orchestrator session id -- for the equal-to-live guard ONLY.

    Mirrors ``pipeline_agent_pager._read_orchestrator_session_id``'s malformed-
    tolerance discipline (missing file, OSError, non-UTF-8, empty, whitespace-only,
    internal whitespace -> ``None``). This id is read SOLELY so
    ``_resolve_keepalive_session_id`` can refuse to resume a monitor id that equals
    the live orchestrator session -- exactly the ``MONITOR_EQUALS_LIVE`` guard in
    ``pipeline_agent_pager._dispatch_claude``. It is NEVER returned as a
    ``claude --resume`` target: pinging the live orchestrator is the interference
    the dedicated-monitor design exists to prevent.
    """
    live_path = _observability_dir(repo_root, bus_dir) / ORCHESTRATOR_SESSION_ID_FILENAME
    try:
        raw = live_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    except UnicodeDecodeError:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    if any(ch.isspace() for ch in candidate):
        return None
    return candidate


def _resolve_session_id(repo_root: Path, bus_dir: str, explicit: str | None) -> str | None:
    """Resolve the candidate keepalive id: an explicit override wins, else the file.

    The default (no explicit id) reads the dedicated monitor file each tick so a
    pause clears the moment a clean, distinct id lands. NEVER reads the live
    orchestrator id. This is the RAW candidate; the equal-to-live guard lives in
    ``_resolve_keepalive_session_id``, which every dispatch path must use.
    """
    explicit_id = (explicit or "").strip()
    if explicit_id:
        return explicit_id
    return _read_monitor_session_id(repo_root, bus_dir)


def _resolve_keepalive_session_id(
    repo_root: Path, bus_dir: str, explicit: str | None
) -> tuple[str | None, str]:
    """Resolve the keepalive target id, enforcing BOTH fail-closed guards.

    Mirrors ``pipeline_agent_pager._dispatch_claude``'s two guards, applied BEFORE
    any ``claude --resume`` argv is built:
      1. monitor id absent/malformed  -> ``(None, PAUSE_REASON_MONITOR_UNSET)``;
      2. monitor id == live orchestrator id
                                       -> ``(None, PAUSE_REASON_MONITOR_EQUALS_LIVE)``.
    The live orchestrator id is read SOLELY for the inequality check in guard 2 and
    is NEVER returned as a resume target. On success returns ``(monitor_id, "")``.
    The watcher pauses (no crash, no orchestrator fallback) on either guard and
    resumes automatically once a clean, DISTINCT monitor id lands. Guard 2 also
    covers an explicit ``--session-id`` override that happens to equal the live id.
    """
    candidate = _resolve_session_id(repo_root, bus_dir, explicit)
    if not candidate:
        return None, PAUSE_REASON_MONITOR_UNSET
    live_session_id = _read_orchestrator_session_id(repo_root, bus_dir)
    if live_session_id is not None and candidate == live_session_id:
        return None, PAUSE_REASON_MONITOR_EQUALS_LIVE
    return candidate, ""


def _claude_keepalive_command(session_id: str, prompt: str) -> list[str]:
    """Build the dedicated-monitor keepalive argv.

    GAP-1: the argv carries a mechanical ``--disallowedTools`` flag (at minimum
    ``Bash``) so the resumed monitor cannot launch a pipeline executor, regardless
    of the prompt. GAP-2: ``--output-format stream-json --verbose`` so the watcher
    can parse the terminal agent_message for the ``Autoping summary:`` line. The
    resume target is the dedicated monitor id -- never the live orchestrator.
    """
    return [
        _claude_bin(),
        "--resume",
        session_id,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        # SEPARATE argv tokens: claude's ``--disallowedTools <tools...>`` is
        # variadic, so each name disables one tool. A single space-joined token
        # would name one nonexistent tool and disable nothing.
        "--disallowedTools",
        *CLAUDE_KEEPALIVE_DISALLOWED_TOOLS,
    ]


def _render_prompt(*, summary_path: Path, bus_dir: str = DEFAULT_BUS_DIR) -> str:
    return (
        "WorkingRCX dedicated Claude monitor keepalive tick.\n"
        "This is an autoping heartbeat that keeps the dedicated monitor session warm; it is NOT a request to act on the pipeline.\n"
        "Do not run shell commands, tests, preflight checks, or other tools from this keepalive wake path.\n"
        "Do not edit files, run git add/commit/push, or apply structural fixes from this keepalive wake path.\n"
        "Do not launch or relaunch executor_dispatch.py, phase_a_executor.py, phase_b_executor.py, commit_executor.py, or bridge_supervisor.py from this keepalive wake path.\n"
        "Do not background a new pipeline process from this keepalive turn.\n"
        "Stay idle and ready; the pager will resume this same session with real work when a pipeline transition occurs.\n"
        f"Always end with one concise final sentence beginning '{SUMMARY_PREFIX}' "
        "that states the monitor is warm and whether anything needed attention. "
        "The watcher persists that final summary; do not write the summary file yourself.\n\n"
        f"Active bus root: {bus_dir}\n"
        f"Watcher summary path: {summary_path}\n"
    )


def _clip_summary(text: str, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _extract_summary_line(text: str) -> str | None:
    cleaned = text.replace("\r", "\n")
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line.startswith(SUMMARY_PREFIX):
            continue
        summary = line[len(SUMMARY_PREFIX):].strip()
        if summary:
            return summary
    return None


def _extract_text_from_stream_content(block: Any) -> str:
    """Best-effort text extraction from a Claude stream-json content block."""
    if isinstance(block, dict):
        text = block.get("text")
        if isinstance(text, str):
            return text.strip()
    return ""


def _stream_json_event_text(payload: dict[str, Any]) -> str:
    """Plain text from a single Claude stream-json event.

    Mirrors ``bridge_adapters._extract_claude_stream_json_output``: the terminal
    ``result`` event carries the final agent text; ``assistant`` events carry
    message content blocks. ``agent_message``/``message`` are accepted defensively.
    """
    event_type = payload.get("type")
    if event_type == "result":
        result = payload.get("result")
        return result.strip() if isinstance(result, str) else ""
    if event_type == "assistant":
        message = payload.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        parts: list[str] = []
        if isinstance(content, list):
            for block in content:
                text = _extract_text_from_stream_content(block)
                if text:
                    parts.append(text)
        else:
            text = _extract_text_from_stream_content(content)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if event_type in {"agent_message", "message"}:
        text = payload.get("text")
        return text.strip() if isinstance(text, str) else ""
    return ""


def _extract_last_agent_summary(log_path: Path) -> str | None:
    """Return the last ``Autoping summary:`` line from a stream-json keepalive log.

    The log captures stdout+stderr, so non-JSON lines are tolerated (skipped)
    rather than aborting the parse the way the strict adapter normalizer would.
    """
    if not log_path.exists():
        return None

    last_summary: str | None = None
    for raw_line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        text = _stream_json_event_text(payload)
        if not text:
            continue
        summary = _extract_summary_line(text)
        if summary:
            last_summary = summary

    if not last_summary:
        return None
    return _clip_summary(last_summary)


def _ping_timed_out(
    *,
    started_monotonic: float | None,
    timeout_s: float,
    now_monotonic: float | None = None,
) -> bool:
    if started_monotonic is None or timeout_s <= 0:
        return False
    now = time.monotonic() if now_monotonic is None else now_monotonic
    return now - started_monotonic >= timeout_s


def _status_for_ping_summary(summary: str | None, *, timed_out: bool = False) -> str:
    return STATUS_PRIOR_TIMED_OUT if timed_out else STATUS_PRIOR_FINISHED


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


# --- active keepalive child tracking + termination handling -------------------
# The keepalive resume runs in its OWN session (``start_new_session=True``), so it
# is NOT in the watcher's process group; ``kill <watcher-pid>`` alone would orphan
# it -- exactly the stale ``claude --resume`` keepalive the launcher's
# force-restart could otherwise leave behind. The watcher records its in-flight
# child and reaps that child's process group on SIGTERM/SIGINT and on any
# interpreter exit (including an unhandled exception), so terminating the watcher
# deterministically tears the keepalive down too. The launcher adds a matching
# orphan sweep for the SIGKILL/hard-crash case this cannot catch.
_ACTIVE_CHILD: subprocess.Popen[str] | None = None


def _track_active_child(proc: subprocess.Popen[str] | None) -> subprocess.Popen[str] | None:
    """Record (or clear) the in-flight keepalive child for the termination path."""
    global _ACTIVE_CHILD
    _ACTIVE_CHILD = proc
    return proc


def _reap_active_child() -> None:
    """Terminate the tracked keepalive child's process group, if one is running."""
    proc = _ACTIVE_CHILD
    if proc is not None and proc.poll() is None:
        _terminate_process_group(proc)


def _install_termination_handlers() -> None:
    """Reap the active keepalive child whenever the watcher is asked to stop.

    Registers an ``atexit`` reaper (covers normal exit, ``SystemExit``, and
    unhandled exceptions) plus SIGTERM/SIGINT handlers that reap then exit. The
    launcher's force-restart sends a plain ``kill <watcher-pid>`` (SIGTERM) and the
    watcher-orphan sweep sends SIGTERM to the watcher's process group; both now
    reap the detached ``claude --resume`` child instead of orphaning it. SIGKILL
    cannot be caught here; the launcher's keepalive-orphan sweep covers that.
    """
    atexit.register(_reap_active_child)

    def _handle(signum: int, _frame: Any) -> None:
        _reap_active_child()
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)


def _isolate_process_group() -> None:
    """Detach the watcher into its OWN session/process group at startup.

    The launcher's orphan sweep (``cleanup_orphaned_autoping_watchers`` in
    ``ensure_claude_autoping.sh``) terminates a stale watcher with
    ``os.killpg(os.getpgid(<watcher-pid>), SIGTERM)``. ``setsid(1)`` is NOT
    available on macOS, and the launcher backgrounds the watcher with a plain
    ``nohup ... &`` -- which, in a non-interactive shell (the pipeline/hook context
    the bridge flagged), leaves the watcher in the launcher's INHERITED process
    group. Without this call a sweep ``killpg`` on that inherited group would signal
    unrelated processes. Calling ``os.setsid()`` here makes the watcher a brand-new
    session+group leader (``os.getpgid(pid) == pid``), so the sweep's ``killpg`` is
    scoped to this watcher alone. (The sweep also re-checks group leadership before
    ``killpg`` as defense-in-depth.) The detached ``claude --resume`` keepalive
    children are isolated separately via ``start_new_session=True``, so they are
    unaffected.

    ``os.setsid()`` raises ``PermissionError`` only when the caller is ALREADY a
    process-group leader -- in which case the watcher already owns an isolated
    group, so the guard is a harmless no-op.
    """
    try:
        os.setsid()
    except (PermissionError, OSError):
        # Already a session/group leader (or setsid unsupported here): the process
        # already owns an isolated group, so the sweep's killpg stays safe.
        pass


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    merged = _read_state(path)
    merged.update(payload)
    _write_text(path, json.dumps(merged, indent=2, sort_keys=True) + "\n")


def _state_skeleton(
    *,
    repo_root: Path,
    bus_dir: str,
    session_id: str | None,
    summary_path: Path,
    watcher_pid: int,
    status: str = STATUS_INITIAL_DELAY,
    pause_reason: str = "",
) -> dict[str, Any]:
    """Full state-file schema (version 1 + the generic codex fields).

    Every field is seeded so the repo-matched state file always carries the
    complete schema; per-tick updates merge over this skeleton. ``status`` is the
    health signal (``paused`` vs any live status); ``pause_reason`` explains a
    pause.
    """
    return {
        "version": STATE_VERSION,
        "updated_at": _now(),
        "watcher_pid": watcher_pid,
        "session_id": session_id or "",
        "status": status,
        "active_pid": None,
        "active_log": None,
        "last_exit_code": None,
        "last_completed_at": None,
        "last_summary": "",
        "repo_root": str(repo_root),
        "bus_dir": bus_dir,
        "summary_path": str(summary_path),
        "pause_reason": pause_reason,
    }


def _paused_state_update(watcher_pid: int, *, reason: str = PAUSE_REASON_MONITOR_UNSET) -> dict[str, Any]:
    """State merge that marks the monitor PAUSED (unhealthy) with a reason."""
    return {
        "updated_at": _now(),
        "watcher_pid": watcher_pid,
        "status": STATUS_PAUSED,
        "active_pid": None,
        "active_log": None,
        "last_exit_code": None,
        "pause_reason": reason,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WorkingRCX dedicated Claude monitor autoping watcher")
    parser.add_argument("--repo-root", default=str(_repo_root()))
    parser.add_argument("--session-id", default="")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S)
    parser.add_argument("--initial-delay", type=float, default=DEFAULT_INITIAL_DELAY_S)
    parser.add_argument("--ping-timeout", type=float, default=DEFAULT_PING_TIMEOUT_S)
    parser.add_argument("--bus-dir", default=os.environ.get("RCX_AGENT_BUS_DIR", DEFAULT_BUS_DIR))
    return parser.parse_args()


def main() -> int:
    # Finding-2: detach into our OWN session/process group BEFORE anything else, so
    # the launcher's orphan sweep ``killpg(getpgid(<watcher-pid>))`` only ever
    # signals this watcher -- never the launcher's inherited process group.
    _isolate_process_group()
    args = _parse_args()
    try:
        bus_dir = _validate_bus_dir(args.bus_dir)
    except ValueError as exc:
        print(f"[claude-autoping] {exc}", flush=True)
        return 2

    repo_root = Path(args.repo_root).resolve()
    explicit_session_id = (args.session_id or "").strip()
    obs_dir = _observability_dir(repo_root, bus_dir)
    log_dir = obs_dir / "claude_autoping_dispatch"
    obs_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    startup_candidate = _resolve_session_id(repo_root, bus_dir, explicit_session_id)
    startup_session_id, startup_pause_reason = _resolve_keepalive_session_id(
        repo_root, bus_dir, explicit_session_id
    )
    # Slug from the RAW candidate so the state-file path stays stable and matches the
    # launcher's slug (derived from the resolved monitor id) even when the
    # equal-to-live guard pauses dispatch.
    name_slug = _slug(startup_candidate or explicit_session_id or "pending")
    state_path = obs_dir / f"claude_autoping_{name_slug}.json"
    summary_path = obs_dir / f"claude_autoping_{name_slug}_summary.txt"

    print(
        f"[claude-autoping] initial_delay_s={args.initial_delay} "
        f"session_id={startup_session_id or '<unset>'} repo_root={repo_root} bus_dir={bus_dir}",
        flush=True,
    )
    _write_state(
        state_path,
        _state_skeleton(
            repo_root=repo_root,
            bus_dir=bus_dir,
            session_id=startup_session_id,
            summary_path=summary_path,
            watcher_pid=os.getpid(),
            status=(STATUS_INITIAL_DELAY if startup_session_id else STATUS_PAUSED),
            pause_reason=("" if startup_session_id else startup_pause_reason),
        ),
    )
    # Reap the detached keepalive child if the watcher is stopped (force-restart /
    # orphan sweep send SIGTERM) -- installed before the initial delay so a stop
    # during startup is handled too.
    _install_termination_handlers()
    time.sleep(args.initial_delay)

    active_proc: subprocess.Popen[str] | None = _track_active_child(None)
    active_log: Path | None = None
    active_started_monotonic: float | None = None

    while True:
        if active_proc is not None:
            exit_code = active_proc.poll()
            if exit_code is None:
                elapsed_s = (
                    time.monotonic() - active_started_monotonic
                    if active_started_monotonic is not None
                    else 0.0
                )
                summary = _extract_last_agent_summary(active_log) if active_log else None
                if summary:
                    completed_pid = active_proc.pid
                    _terminate_process_group(active_proc)
                    _write_text(summary_path, summary + "\n")
                    _write_state(
                        state_path,
                        {
                            "updated_at": _now(),
                            "watcher_pid": os.getpid(),
                            "status": STATUS_PRIOR_FINISHED,
                            "active_pid": None,
                            "active_log": None,
                            "last_exit_code": 0,
                            "last_completed_at": _now(),
                            "last_summary": summary,
                            "pause_reason": "",
                            "summary_path": str(summary_path),
                        },
                    )
                    print(
                        "[claude-autoping] prior_ping_summary_received "
                        f"pid={completed_pid} elapsed_s={elapsed_s:.1f} active_log={active_log}",
                        flush=True,
                    )
                    active_proc = None
                    active_log = None
                    active_started_monotonic = None
                    time.sleep(args.interval)
                    continue

                if _ping_timed_out(
                    started_monotonic=active_started_monotonic,
                    timeout_s=args.ping_timeout,
                ):
                    timed_out_pid = active_proc.pid
                    _terminate_process_group(active_proc)
                    exit_code = active_proc.returncode
                    summary = _extract_last_agent_summary(active_log) if active_log else None
                    if summary is None:
                        summary = (
                            "autoping keepalive timed out after "
                            f"{int(elapsed_s)}s without an Autoping summary; "
                            f"terminated stale resume pid={timed_out_pid}"
                        )
                    _write_text(summary_path, summary + "\n")
                    _write_state(
                        state_path,
                        {
                            "updated_at": _now(),
                            "watcher_pid": os.getpid(),
                            "status": STATUS_PRIOR_TIMED_OUT,
                            "active_pid": None,
                            "active_log": None,
                            "last_exit_code": exit_code if exit_code is not None else 124,
                            "last_completed_at": _now(),
                            "last_summary": summary,
                            "pause_reason": "",
                            "summary_path": str(summary_path),
                        },
                    )
                    print(
                        f"[claude-autoping] {STATUS_PRIOR_TIMED_OUT} "
                        f"pid={timed_out_pid} elapsed_s={elapsed_s:.1f} active_log={active_log}",
                        flush=True,
                    )
                    active_proc = None
                    active_log = None
                    active_started_monotonic = None
                    time.sleep(args.interval)
                    continue

                _write_state(
                    state_path,
                    {
                        "updated_at": _now(),
                        "watcher_pid": os.getpid(),
                        "status": STATUS_WAITING,
                        "active_pid": active_proc.pid,
                        "active_log": str(active_log or ""),
                        "last_exit_code": None,
                        "pause_reason": "",
                        "summary_path": str(summary_path),
                    },
                )
                print(
                    f"[claude-autoping] waiting active_pid={active_proc.pid} active_log={active_log}",
                    flush=True,
                )
                time.sleep(args.interval)
                continue

            # Process exited on its own before we observed a summary.
            summary = _extract_last_agent_summary(active_log) if active_log else None
            if summary:
                _write_text(summary_path, summary + "\n")
                print(f"[claude-autoping][summary] {summary}", flush=True)
            _write_state(
                state_path,
                {
                    "updated_at": _now(),
                    "watcher_pid": os.getpid(),
                    "status": STATUS_PRIOR_FINISHED,
                    "active_pid": None,
                    "active_log": None,
                    "last_exit_code": exit_code,
                    "last_completed_at": _now(),
                    "last_summary": summary or "",
                    "pause_reason": "",
                    "summary_path": str(summary_path),
                },
            )
            print(
                f"[claude-autoping] prior_ping_finished pid={active_proc.pid} exit_code={exit_code}",
                flush=True,
            )
            active_proc = None
            active_log = None
            active_started_monotonic = None

        session_id, pause_reason = _resolve_keepalive_session_id(
            repo_root, bus_dir, explicit_session_id
        )
        if not session_id:
            # PAUSE: the dedicated monitor id is absent/malformed, OR it equals the
            # live orchestrator id (the equal-to-live guard). Do NOT crash and NEVER
            # fall back to / resume the live orchestrator. Resumes automatically once
            # a clean, DISTINCT monitor id lands.
            _write_state(state_path, _paused_state_update(os.getpid(), reason=pause_reason))
            print(
                f"[claude-autoping] paused ({pause_reason})",
                flush=True,
            )
            time.sleep(args.interval)
            continue

        prompt = _render_prompt(summary_path=summary_path, bus_dir=bus_dir)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        active_log = log_dir / f"claude_autoping_{stamp}.jsonl"
        with active_log.open("w", encoding="utf-8") as sink:
            active_proc = _track_active_child(
                subprocess.Popen(
                    _claude_keepalive_command(session_id, prompt),
                    cwd=str(repo_root),
                    stdin=subprocess.DEVNULL,
                    stdout=sink,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                    env=_resume_env(),
                )
            )
        active_started_monotonic = time.monotonic()
        _write_state(
            state_path,
            {
                "updated_at": _now(),
                "watcher_pid": os.getpid(),
                "session_id": session_id,
                "status": STATUS_PING_DISPATCHED,
                "active_pid": active_proc.pid,
                "active_log": str(active_log),
                "last_exit_code": None,
                "pause_reason": "",
                "summary_path": str(summary_path),
            },
        )
        print(
            "[claude-autoping] dispatched "
            f"pid={active_proc.pid} session_id={session_id} log={active_log} summary={summary_path}",
            flush=True,
        )
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
