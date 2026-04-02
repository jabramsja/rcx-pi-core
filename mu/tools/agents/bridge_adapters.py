#!/usr/bin/env python3
"""Helpers for running bridge-configured agent commands."""

from __future__ import annotations

import io
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


class BridgeAdapterError(RuntimeError):
    """Raised when bridge adapter configuration or execution fails."""

    def __init__(
        self,
        message: str,
        *,
        output: str | None = None,
        returncode: int | None = None,
    ) -> None:
        super().__init__(message)
        self.output = output
        self.returncode = returncode


@dataclass(frozen=True)
class AdapterSpec:
    name: str
    cmd: list[str]
    timeout_s: int
    prompt_via_stdin: bool = True
    env: dict[str, str] | None = None
    mode: str = "live"


_AGENT_ENVELOPE_BEGIN = "BEGIN_AGENT_ENVELOPE"
_AGENT_ENVELOPE_END = "END_AGENT_ENVELOPE"
_AGENT_ENVELOPE_RE = re.compile(
    r"BEGIN_AGENT_ENVELOPE\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```\s*)?END_AGENT_ENVELOPE",
    re.DOTALL,
)
_AUTHORIZED_AGENT_DECISIONS = frozenset(
    {"GO", "NO_GO", "REQUEST_CHANGES", "QUESTION", "STALE", "ERROR", "SYNTHETIC"}
)


def _extract_text_from_stream_content(block: Any) -> str:
    """Best-effort text extraction from a Claude stream-json content block."""
    if isinstance(block, dict):
        text = block.get("text")
        if isinstance(text, str):
            return text.strip()
    return ""


def _extract_claude_stream_json_output(stdout_text: str) -> str | None:
    """Normalize Claude CLI --output-format stream-json stdout into plain text."""
    raw_lines = [line for line in stdout_text.splitlines() if line.strip()]
    if not raw_lines:
        return None

    events: list[dict[str, Any]] = []
    for line in raw_lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
            return None
        events.append(payload)

    result_text = ""
    assistant_parts: list[str] = []
    for payload in events:
        event_type = payload.get("type")
        if event_type == "result":
            result = payload.get("result")
            if isinstance(result, str) and result.strip():
                result_text = result.strip()
        elif event_type == "assistant":
            message = payload.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, list):
                for block in content:
                    text = _extract_text_from_stream_content(block)
                    if text:
                        assistant_parts.append(text)
            else:
                text = _extract_text_from_stream_content(content)
                if text:
                    assistant_parts.append(text)

    if result_text:
        return result_text
    if assistant_parts:
        return "\n".join(assistant_parts).strip()
    return None


def _extract_codex_json_output(stdout_text: str) -> str | None:
    """Normalize codex exec --json stdout into assistant plain text."""
    raw_lines = [line for line in stdout_text.splitlines() if line.strip()]
    if not raw_lines:
        return None

    assistant_messages: list[str] = []
    for line in raw_lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        event_type = payload.get("type")
        if not isinstance(event_type, str):
            return None
        if event_type != "item.completed":
            continue
        item = payload.get("item")
        if not isinstance(item, dict):
            continue
        if item.get("type") != "agent_message":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            assistant_messages.append(text.strip())

    if assistant_messages:
        return "\n".join(assistant_messages).strip()
    return None


def _normalize_stdout_for_adapter(
    spec: AdapterSpec,
    cmd: list[str],
    stdout_text: str,
) -> str:
    """Return authoritative plain-text stdout for adapters with wrapped output."""
    if not stdout_text.strip():
        return stdout_text

    uses_claude_stream_json = (
        spec.name == "claude"
        and "--output-format" in cmd
        and "stream-json" in cmd
    )
    if uses_claude_stream_json:
        normalized = _extract_claude_stream_json_output(stdout_text)
        return normalized if normalized is not None else stdout_text

    uses_codex_json = (
        spec.name == "codex"
        and "--json" in cmd
    )
    if uses_codex_json:
        normalized = _extract_codex_json_output(stdout_text)
        return normalized if normalized is not None else stdout_text

    return stdout_text


def _parse_ps_time_seconds(value: str) -> float:
    text = value.strip()
    if not text:
        return 0.0
    days = 0
    if "-" in text:
        day_text, text = text.split("-", 1)
        try:
            days = int(day_text)
        except ValueError:
            return 0.0
    parts = text.split(":")
    try:
        seconds = float(parts[-1])
    except (IndexError, ValueError):
        return 0.0
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return (days * 86400) + (hours * 3600) + (minutes * 60) + seconds


def _process_tree_fingerprint(root_pid: int) -> tuple[tuple[int, float], ...]:
    if root_pid <= 0:
        return ()
    try:
        os.kill(root_pid, 0)
    except (OSError, ProcessLookupError):
        return ()

    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,time="],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return ((root_pid, 0.0),)

    children_by_parent: dict[int, set[int]] = {}
    cpu_by_pid: dict[int, float] = {}
    for raw in proc.stdout.splitlines():
        parts = raw.split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        children_by_parent.setdefault(ppid, set()).add(pid)
        cpu_by_pid[pid] = _parse_ps_time_seconds(parts[2])

    descendants: set[int] = set()
    stack = list(children_by_parent.get(root_pid, set()))
    while stack:
        pid = stack.pop()
        if pid in descendants:
            continue
        descendants.add(pid)
        stack.extend(children_by_parent.get(pid, set()))

    tracked = {root_pid, *descendants}
    return tuple(sorted((pid, cpu_by_pid.get(pid, 0.0)) for pid in tracked))


def _kill_process_group(
    proc: subprocess.Popen[str],
    *,
    wait_for_exit: bool = False,
) -> None:
    tracked_pids = [pid for pid, _cpu in _process_tree_fingerprint(proc.pid)]
    for pid in tracked_pids:
        if pid == proc.pid:
            continue
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            proc.kill()
        except OSError:
            pass
    if wait_for_exit:
        deadline = time.monotonic() + 2.0
        child_pids = [pid for pid in tracked_pids if pid != proc.pid]
        while tracked_pids and time.monotonic() < deadline:
            remaining_children = [
                pid for pid in child_pids if _pid_is_live_non_zombie(pid)
            ]
            root_alive = proc.poll() is None
            if not root_alive:
                try:
                    proc.wait(timeout=0)
                except (subprocess.TimeoutExpired, ValueError):
                    pass
            if not remaining_children and not root_alive:
                break
            child_pids = remaining_children
            tracked_pids = ([proc.pid] if root_alive else []) + child_pids
            time.sleep(0.05)


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def _pid_is_live_non_zombie(pid: int) -> bool:
    if not _pid_exists(pid):
        return False

    try:
        proc = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return True

    stat = proc.stdout.strip()
    if not stat:
        return False
    return not stat.lstrip().startswith("Z")


def _contains_complete_agent_envelope(text: str) -> bool:
    for match in _AGENT_ENVELOPE_RE.finditer(text):
        try:
            envelope = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        decision = envelope.get("decision")
        if isinstance(decision, str) and decision in _AUTHORIZED_AGENT_DECISIONS:
            return True
    return False


def _authoritative_output_so_far(spec: AdapterSpec, cmd: list[str], stdout_text: str) -> str:
    """Scan only authoritative assistant stdout, not raw tool-result payloads."""
    return _normalize_stdout_for_adapter(spec, cmd, stdout_text)


def _raw_file_size(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _stdout_progress_seen(event: threading.Event) -> bool:
    return event.is_set()


def _progress_fingerprint(proc: subprocess.Popen[str], raw_output_path: Path | None) -> tuple[Any, ...]:
    return (_raw_file_size(raw_output_path), _process_tree_fingerprint(proc.pid))


def _start_stale_watchdog(
    proc: subprocess.Popen[str],
    raw_output_path: Path | None,
    stale_timeout_s: float | None,
    stale_timed_out: threading.Event,
) -> tuple[threading.Event, threading.Thread | None]:
    stop_event = threading.Event()
    if stale_timeout_s is None:
        return stop_event, None

    def _watch_progress() -> None:
        last_progress = time.monotonic()
        last_fingerprint = _progress_fingerprint(proc, raw_output_path)
        poll_interval = min(max(stale_timeout_s / 5.0, 0.2), 5.0)
        while not stop_event.wait(poll_interval):
            if proc.poll() is not None:
                return
            fingerprint = _progress_fingerprint(proc, raw_output_path)
            if fingerprint != last_fingerprint:
                last_fingerprint = fingerprint
                last_progress = time.monotonic()
                continue
            if time.monotonic() - last_progress >= stale_timeout_s:
                stale_timed_out.set()
                _kill_process_group(proc, wait_for_exit=True)
                return

    thread = threading.Thread(target=_watch_progress, daemon=True)
    thread.start()
    return stop_event, thread


def _expand_value(value: str, context: dict[str, str]) -> str:
    expanded = os.path.expandvars(value)
    try:
        return expanded.format(**context)
    except KeyError as exc:
        missing = exc.args[0]
        raise BridgeAdapterError(f"Missing bridge command placeholder: {missing}") from exc


def load_bridge_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise BridgeAdapterError(
            f"Bridge config not found at '{config_path}'. Copy tools/agents/bridge_config.example.json "
            "to .agent_bus/bridge_config.json and fill in your local CLI commands."
        )
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BridgeAdapterError(f"Bridge config is not valid JSON: {exc}") from exc


def get_adapter(config: dict[str, Any], adapter_name: str) -> AdapterSpec:
    agents = config.get("agents")
    if not isinstance(agents, dict):
        raise BridgeAdapterError("Bridge config missing top-level 'agents' object")
    raw = agents.get(adapter_name)
    if not isinstance(raw, dict):
        raise BridgeAdapterError(f"Bridge config missing adapter '{adapter_name}'")
    cmd = raw.get("cmd")
    if not isinstance(cmd, list) or not cmd or not all(isinstance(part, str) for part in cmd):
        raise BridgeAdapterError(f"Adapter '{adapter_name}' must define non-empty string list 'cmd'")
    timeout_s = raw.get("timeout_s", 1800)
    if not isinstance(timeout_s, int) or timeout_s <= 0:
        raise BridgeAdapterError(f"Adapter '{adapter_name}' timeout_s must be a positive integer")
    prompt_via_stdin = raw.get("prompt_via_stdin", True)
    if not isinstance(prompt_via_stdin, bool):
        raise BridgeAdapterError(f"Adapter '{adapter_name}' prompt_via_stdin must be boolean")
    env = raw.get("env")
    if env is not None and (not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items())):
        raise BridgeAdapterError(f"Adapter '{adapter_name}' env must be a string:string object if present")
    mode = raw.get("mode", "live")
    if mode != "live":
        raise BridgeAdapterError(
            f"Adapter '{adapter_name}' mode '{mode}' is not supported in bridge v1. "
            "Use live mode for now."
        )
    return AdapterSpec(
        name=adapter_name,
        cmd=cmd,
        timeout_s=timeout_s,
        prompt_via_stdin=prompt_via_stdin,
        env=env,
        mode=mode,
    )


def _prepare_adapter_env(spec: AdapterSpec, context: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    """Build command list and environment for an adapter invocation."""
    cmd = [_expand_value(part, context) for part in spec.cmd]
    env = os.environ.copy()
    # Strip nesting-detection vars so Claude Code subprocess doesn't refuse to start
    for nest_var in ("CLAUDECODE", "CLAUDE_CODE_SESSION", "CLAUDE_CODE"):
        env.pop(nest_var, None)
    if spec.env:
        env.update({key: _expand_value(value, context) for key, value in spec.env.items()})
    return cmd, env


def _tee_stream(
    source: io.TextIOWrapper,
    sink: io.StringIO,
    tty: Any,
    raw_file: Any = None,
    on_line: Any = None,
) -> None:
    """Read from source, write to sink (capture), tty (live display), and raw_file (incremental persist)."""
    for line in source:
        sink.write(line)
        if raw_file is not None:
            raw_file.write(line)
            raw_file.flush()
        if on_line is not None:
            on_line(line, sink)
        if tty is not None:
            tty.write(line)
            tty.flush()


def _run_adapter_buffered(
    spec: AdapterSpec,
    cmd: list[str],
    env: dict[str, str],
    prompt_text: str,
    repo_root: Path,
    raw_output_path: Path | None = None,
    zero_output_timeout_s: float | None = None,
    stale_timeout_s: float | None = None,
    stop_after_envelope: bool = False,
) -> str:
    """Run adapter with full capture (no streaming), optionally writing to raw file incrementally."""
    raw_fh = None
    if raw_output_path is not None:
        raw_fh = open(raw_output_path, "w", encoding="utf-8")

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if spec.prompt_via_stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=repo_root,
            env=env,
            start_new_session=True,  # Own process group for clean child cleanup
        )
    except FileNotFoundError as exc:
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' command not found: {cmd[0]}"
        ) from exc
    except PermissionError as exc:
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' command not executable: {cmd[0]}"
        ) from exc

    stdout_lines: list[str] = []
    stderr_buf = io.StringIO()
    stdout_progress = threading.Event()

    # Drain stderr concurrently to prevent pipe deadlock when child writes
    # heavily to stderr while we block reading stdout line-by-line.
    stderr_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stderr, stderr_buf, None),
        daemon=True,
    )
    stderr_thread.start()

    # Watchdog timer: kill the ENTIRE process group if it exceeds timeout_s.
    # This prevents orphaned children (e.g., codex exec spawning sub-processes).
    timed_out = threading.Event()
    zero_output_timed_out = threading.Event()
    stale_timed_out = threading.Event()
    envelope_terminated = threading.Event()
    stale_watchdog_stop, stale_watchdog = _start_stale_watchdog(
        proc,
        raw_output_path,
        stale_timeout_s,
        stale_timed_out,
    )

    def _kill_after_timeout() -> None:
        timed_out.set()
        _kill_process_group(proc, wait_for_exit=True)

    def _kill_after_zero_output_timeout() -> None:
        if _stdout_progress_seen(stdout_progress) or proc.poll() is not None:
            return
        zero_output_timed_out.set()
        _kill_process_group(proc, wait_for_exit=True)

    watchdog = threading.Timer(spec.timeout_s, _kill_after_timeout)
    watchdog.daemon = True
    watchdog.start()
    zero_output_watchdog = None
    if zero_output_timeout_s is not None and raw_output_path is not None:
        zero_output_watchdog = threading.Timer(
            zero_output_timeout_s,
            _kill_after_zero_output_timeout,
        )
        zero_output_watchdog.daemon = True
        zero_output_watchdog.start()

    try:
        if spec.prompt_via_stdin and proc.stdin is not None:
            try:
                proc.stdin.write(prompt_text)
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Process exited early; continue to read remaining output
        for line in proc.stdout:
            stdout_lines.append(line)
            stdout_progress.set()
            if raw_fh is not None:
                raw_fh.write(line)
                raw_fh.flush()
            if (
                stop_after_envelope
                and not envelope_terminated.is_set()
                and _contains_complete_agent_envelope(
                    _authoritative_output_so_far(spec, cmd, "".join(stdout_lines))
                )
            ):
                envelope_terminated.set()
                _kill_process_group(proc, wait_for_exit=True)
        proc.wait(timeout=spec.timeout_s)
        watchdog.cancel()
        if zero_output_watchdog is not None:
            zero_output_watchdog.cancel()
        stale_watchdog_stop.set()
        if stale_watchdog is not None:
            stale_watchdog.join(timeout=5)
    except subprocess.TimeoutExpired as exc:
        watchdog.cancel()
        if zero_output_watchdog is not None:
            zero_output_watchdog.cancel()
        stale_watchdog_stop.set()
        if stale_watchdog is not None:
            stale_watchdog.join(timeout=5)
        _kill_process_group(proc, wait_for_exit=True)
        proc.wait()
        stderr_thread.join(timeout=5)
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' timed out after {spec.timeout_s}s"
        ) from exc

    if timed_out.is_set():
        # Timer fired — genuine timeout regardless of returncode
        # (SIGKILL sets returncode to -9, not None)
        if proc.returncode is None:
            _kill_process_group(proc, wait_for_exit=True)
            proc.wait()
        stderr_thread.join(timeout=5)
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' timed out after {spec.timeout_s}s"
        )

    stderr_thread.join(timeout=5)

    output = _normalize_stdout_for_adapter(spec, cmd, "".join(stdout_lines))
    stderr_text = stderr_buf.getvalue()
    if stderr_text:
        output = f"{output}\n[stderr]\n{stderr_text}".strip()
        if raw_fh is not None:
            raw_fh.write(f"\n[stderr]\n{stderr_text}")
            raw_fh.flush()
    if zero_output_timed_out.is_set():
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' produced no stdout after {zero_output_timeout_s}s",
            output=output,
            returncode=proc.returncode,
        )
    if stale_timed_out.is_set():
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' stalled after {stale_timeout_s}s without output growth or process-tree activity",
            output=output,
            returncode=proc.returncode,
        )
    if envelope_terminated.is_set():
        if raw_fh is not None:
            raw_fh.close()
        return output
    if raw_fh is not None:
        raw_fh.close()
    if proc.returncode != 0:
        snippet = output[-1000:]
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' exited {proc.returncode}. Output tail:\n{snippet}",
            output=output,
            returncode=proc.returncode,
        )
    return output


def _run_adapter_streaming(
    spec: AdapterSpec,
    cmd: list[str],
    env: dict[str, str],
    prompt_text: str,
    repo_root: Path,
    raw_output_path: Path | None = None,
    zero_output_timeout_s: float | None = None,
    stale_timeout_s: float | None = None,
    stop_after_envelope: bool = False,
) -> str:
    """Run adapter with live tee to terminal + full capture for raw output file."""
    raw_fh = None
    if raw_output_path is not None:
        raw_fh = open(raw_output_path, "w", encoding="utf-8")

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE if spec.prompt_via_stdin else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=repo_root,
            env=env,
            start_new_session=True,  # Own process group for clean child cleanup
        )
    except FileNotFoundError as exc:
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' command not found: {cmd[0]}"
        ) from exc
    except PermissionError as exc:
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' command not executable: {cmd[0]}"
        ) from exc

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    envelope_terminated = threading.Event()
    stdout_progress = threading.Event()

    def _stop_after_envelope(line: str, sink: io.StringIO) -> None:
        if (
            not stop_after_envelope
            or envelope_terminated.is_set()
        ):
            return
        if _contains_complete_agent_envelope(
            _authoritative_output_so_far(spec, cmd, sink.getvalue())
        ):
            envelope_terminated.set()
            # Give the adapter a brief grace period to flush any immediate trailing bytes
            # before we terminate lingering background work in the same process group.
            time.sleep(0.05)
            _kill_process_group(proc, wait_for_exit=True)

    def _record_stdout_progress(line: str, sink: io.StringIO) -> None:
        stdout_progress.set()
        _stop_after_envelope(line, sink)

    stdout_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stdout, stdout_buf, sys.stdout, raw_fh, _record_stdout_progress),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stderr, stderr_buf, sys.stderr),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    zero_output_timed_out = threading.Event()
    stale_timed_out = threading.Event()
    stale_watchdog_stop, stale_watchdog = _start_stale_watchdog(
        proc,
        raw_output_path,
        stale_timeout_s,
        stale_timed_out,
    )

    def _kill_after_zero_output_timeout() -> None:
        if _stdout_progress_seen(stdout_progress) or proc.poll() is not None:
            return
        zero_output_timed_out.set()
        _kill_process_group(proc, wait_for_exit=True)

    zero_output_watchdog = None
    if zero_output_timeout_s is not None and raw_output_path is not None:
        zero_output_watchdog = threading.Timer(
            zero_output_timeout_s,
            _kill_after_zero_output_timeout,
        )
        zero_output_watchdog.daemon = True
        zero_output_watchdog.start()

    try:
        if spec.prompt_via_stdin and proc.stdin is not None:
            try:
                proc.stdin.write(prompt_text)
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Process exited early; continue to wait for remaining output
        proc.wait(timeout=spec.timeout_s)
        if zero_output_watchdog is not None:
            zero_output_watchdog.cancel()
        stale_watchdog_stop.set()
        if stale_watchdog is not None:
            stale_watchdog.join(timeout=5)
    except subprocess.TimeoutExpired as exc:
        if zero_output_watchdog is not None:
            zero_output_watchdog.cancel()
        stale_watchdog_stop.set()
        if stale_watchdog is not None:
            stale_watchdog.join(timeout=5)
        _kill_process_group(proc, wait_for_exit=True)
        proc.wait()
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' timed out after {spec.timeout_s}s"
        ) from exc

    join_timeout = 0.2 if envelope_terminated.is_set() else 5
    stdout_thread.join(timeout=join_timeout)
    stderr_thread.join(timeout=join_timeout)

    output = _normalize_stdout_for_adapter(spec, cmd, stdout_buf.getvalue())
    stderr_text = stderr_buf.getvalue()
    if stderr_text:
        output = f"{output}\n[stderr]\n{stderr_text}".strip()
        if raw_fh is not None:
            raw_fh.write(f"\n[stderr]\n{stderr_text}")
            raw_fh.flush()
    if zero_output_timed_out.is_set():
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' produced no stdout after {zero_output_timeout_s}s",
            output=output,
            returncode=proc.returncode,
        )
    if stale_timed_out.is_set():
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' stalled after {stale_timeout_s}s without output growth or process-tree activity",
            output=output,
            returncode=proc.returncode,
        )
    if envelope_terminated.is_set():
        if raw_fh is not None:
            raw_fh.close()
        return output
    if raw_fh is not None:
        raw_fh.close()
    if proc.returncode != 0:
        snippet = output[-1000:]
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' exited {proc.returncode}. Output tail:\n{snippet}",
            output=output,
            returncode=proc.returncode,
        )
    return output


def run_adapter(
    spec: AdapterSpec,
    *,
    prompt_text: str,
    prompt_path: Path,
    repo_root: Path,
    job_id: str,
    turn_id: str,
    agent_role: str,
    stream: bool = False,
    raw_output_path: Path | None = None,
    timeout_override_s: float | None = None,
    zero_output_timeout_s: float | None = None,
    stale_timeout_s: float | None = None,
    stop_after_envelope: bool = False,
) -> str:
    if timeout_override_s is not None:
        if timeout_override_s <= 0:
            raise BridgeAdapterError("timeout_override_s must be positive")
        spec = replace(spec, timeout_s=timeout_override_s)
    if stale_timeout_s is not None and stale_timeout_s <= 0:
        raise BridgeAdapterError("stale_timeout_s must be positive")

    context = {
        "prompt_file": str(prompt_path),
        "repo_root": str(repo_root),
        "job_id": job_id,
        "turn_id": turn_id,
        "agent_role": agent_role,
    }
    cmd, env = _prepare_adapter_env(spec, context)

    if stream:
        return _run_adapter_streaming(
            spec,
            cmd,
            env,
            prompt_text,
            repo_root,
            raw_output_path,
            zero_output_timeout_s,
            stale_timeout_s,
            stop_after_envelope,
        )
    return _run_adapter_buffered(
        spec,
        cmd,
        env,
        prompt_text,
        repo_root,
        raw_output_path,
        zero_output_timeout_s,
        stale_timeout_s,
        stop_after_envelope,
    )
