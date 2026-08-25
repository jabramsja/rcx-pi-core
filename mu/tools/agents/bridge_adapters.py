#!/usr/bin/env python3
"""Helpers for running bridge-configured agent commands."""

from __future__ import annotations

import io
import json
import os
import pwd
import re
import signal
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Mapping
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


def _real_home_dir() -> str:
    """Return the account home directory without trusting $HOME overrides."""
    return pwd.getpwuid(os.getuid()).pw_dir


def _real_codex_home() -> Path:
    return Path(_real_home_dir()) / ".codex"


def _codex_home_is_writable(home: Path) -> bool:
    required_paths = (
        home,
        home / "sessions",
        home / "state",
        home / "log",
    )
    for path in required_paths:
        target = path if path.exists() else path.parent
        if not target.exists():
            return False
        if not os.access(target, os.W_OK | os.X_OK):
            return False
    return True


def _seed_codex_runtime_home(runtime_home: Path) -> None:
    """Populate a repo-local Codex runtime home with auth/config surfaces."""
    runtime_home.mkdir(parents=True, exist_ok=True)
    for child in ("sessions", "state", "log", "tmp"):
        (runtime_home / child).mkdir(parents=True, exist_ok=True)

    source_home = _real_codex_home()
    for name in ("auth.json", "config.toml", "config.json", "installation_id"):
        src = source_home / name
        if src.is_file():
            shutil.copy2(src, runtime_home / name)


_AGENT_ENVELOPE_BEGIN = "BEGIN_AGENT_ENVELOPE"
_AGENT_ENVELOPE_END = "END_AGENT_ENVELOPE"
_AGENT_ENVELOPE_BEGIN_RE = re.compile(
    rf"(?<![A-Za-z0-9_]){_AGENT_ENVELOPE_BEGIN}(?![A-Za-z0-9_])"
)
_JSON_WHITESPACE = frozenset(" \t\n\r")
_ASCII_IDENTIFIER_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
)
AGENT_DECISION_PLACEHOLDER = (
    "GO|NO_GO|REQUEST_CHANGES|QUESTION|STALE|ERROR|SYNTHETIC"
)
AGENT_ENVELOPE_REQUIRED_KEYS = frozenset(
    {
        "job_id",
        "turn_id",
        "agent_role",
        "decision",
        "summary",
        "touched_files_claimed",
        "findings",
        "validations_claimed",
        "request_for_next_agent",
    }
)
_AUTHORIZED_AGENT_DECISIONS = frozenset(
    {"GO", "NO_GO", "REQUEST_CHANGES", "QUESTION", "STALE", "ERROR", "SYNTHETIC"}
)
_META_ENVELOPE_RE = re.compile(
    r"BEGIN_META_ENVELOPE\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```\s*)?END_META_ENVELOPE",
    re.DOTALL,
)
_AGENT_BUS_NAMESPACE_RE = re.compile(r"^\.agent_bus-[A-Za-z0-9][A-Za-z0-9_-]*$")
_AUTHORIZED_META_DECISIONS = frozenset(
    {
        "COMMIT_GO",
        "COMMIT_GO_HOLD_PUSH",
        "NO_ACTION",
        "NEEDS_PHASE_A",
        "NEEDS_PHASE_B",
        "STOP_FOR_FOUNDER",
        "STOP_FOR_TRIAGE_DISCUSSION",
        "CONTINUE_DIALECTIC",
        "ROUTE_PHASE_A",
        "ROUTE_PHASE_B",
        "UPDATE_TRACKER_ONLY",
        "ERROR_VALIDATION_FAILED",
        "ERROR_PACKAGE_INVALID",
        "ERROR_CODEX_TIMEOUT",
        "ERROR_CODEX_ABORT",
        "ERROR_REPO_CHANGED",
        "ERROR_MERGE_NOT_FOUND",
        "ERROR_INTERNAL",
        "RETRY_SUGGESTED",
    }
)


@dataclass(frozen=True)
class AgentEnvelopeCandidate:
    """One syntactically complete, raw-decoded agent-envelope candidate."""

    decoded: Any
    source_start: int
    source_end: int
    json_start: int
    json_end: int

    @property
    def source_span(self) -> tuple[int, int]:
        return self.source_start, self.source_end

    @property
    def json_span(self) -> tuple[int, int]:
        return self.json_start, self.json_end


def _skip_json_whitespace(text: str, start: int) -> int:
    cursor = start
    while cursor < len(text) and text[cursor] in _JSON_WHITESPACE:
        cursor += 1
    return cursor


def _has_exact_token_at(text: str, start: int, token: str) -> bool:
    if not text.startswith(token, start):
        return False
    before = text[start - 1] if start else ""
    after_index = start + len(token)
    after = text[after_index] if after_index < len(text) else ""
    return (
        before not in _ASCII_IDENTIFIER_CHARS
        and after not in _ASCII_IDENTIFIER_CHARS
    )


def is_agent_decision_placeholder(decision: object) -> bool:
    """Return whether *decision* is exactly the shared schema placeholder."""

    return isinstance(decision, str) and decision == AGENT_DECISION_PLACEHOLDER


def extract_agent_envelope_candidates(text: str) -> list[AgentEnvelopeCandidate]:
    """Extract marker-safe, syntactically complete agent-envelope candidates.

    Framing is intentionally independent of envelope semantics. Each returned
    value is decoded exactly once with ``JSONDecoder.raw_decode`` and carries
    both the full framed source span and the decoded JSON extent.
    """

    decoder = json.JSONDecoder()
    candidates: list[AgentEnvelopeCandidate] = []
    search_from = 0

    while begin_match := _AGENT_ENVELOPE_BEGIN_RE.search(text, search_from):
        cursor = _skip_json_whitespace(text, begin_match.end())
        fenced = False
        if text.startswith("```json", cursor):
            fenced = True
            cursor += len("```json")
            cursor = _skip_json_whitespace(text, cursor)
        elif text.startswith("```", cursor):
            fenced = True
            cursor += len("```")
            cursor = _skip_json_whitespace(text, cursor)

        json_start = cursor
        try:
            decoded, json_end = decoder.raw_decode(text, json_start)
        except (json.JSONDecodeError, ValueError):
            search_from = begin_match.end()
            continue

        cursor = _skip_json_whitespace(text, json_end)
        if fenced:
            if not text.startswith("```", cursor):
                # The JSON value decoded successfully, so marker text inside
                # its source extent remains payload even though framing failed.
                search_from = json_end
                continue
            cursor += len("```")
            cursor = _skip_json_whitespace(text, cursor)

        if not _has_exact_token_at(text, cursor, _AGENT_ENVELOPE_END):
            # Resume after the decoded extent so a marker-like substring in a
            # valid JSON string cannot become an independent candidate.
            search_from = json_end
            continue

        source_end = cursor + len(_AGENT_ENVELOPE_END)
        candidates.append(
            AgentEnvelopeCandidate(
                decoded=decoded,
                source_start=begin_match.start(),
                source_end=source_end,
                json_start=json_start,
                json_end=json_end,
            )
        )
        # Successfully decoded marker text is payload data, not another opener.
        search_from = source_end

    return candidates


def _validated_bus_dir_name(raw_bus_dir: str | Path | None) -> str:
    raw = str(raw_bus_dir or ".agent_bus").strip().rstrip("/")
    if not raw:
        raw = ".agent_bus"
    if (
        raw.startswith("/")
        or "/" in raw
        or "\\" in raw
        or raw in {".", ".."}
        or ".." in raw
    ):
        raise BridgeAdapterError(
            f"Invalid adapter bus_dir {raw!r}: expected .agent_bus or .agent_bus-<id>"
        )
    if raw == ".agent_bus" or _AGENT_BUS_NAMESPACE_RE.fullmatch(raw):
        return raw
    raise BridgeAdapterError(
        f"Invalid adapter bus_dir {raw!r}: expected .agent_bus or .agent_bus-<id>"
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

    # Codex JSONL: extract agent_message text fields.
    # Only applies to the codex adapter — other adapters pass through.
    if spec.name != "codex":
        return stdout_text

    # Codex exec outputs JSONL where the envelope lives inside
    # {"type":"item.completed","item":{"type":"agent_message","text":"..."}}
    # The text field has escaped newlines that parse_envelope can't match.
    #
    # Check if envelope markers are at the top level by testing whether the
    # line that contains the marker is NOT valid JSON (i.e., it's plain text
    # from a non-JSONL output). A simple `in` check with "\n" is unreliable
    # because the marker can appear at a JSONL line boundary and false-match.
    if _AGENT_ENVELOPE_BEGIN in stdout_text:
        marker_in_plain_text = False
        for raw_line in stdout_text.splitlines():
            if _AGENT_ENVELOPE_BEGIN in raw_line:
                try:
                    json.loads(raw_line.strip())
                except (json.JSONDecodeError, ValueError):
                    # Not JSON — marker is at top level (plain text)
                    marker_in_plain_text = True
                    break
        if marker_in_plain_text:
            return stdout_text

    # Try extracting from JSONL agent_message entries
    agent_texts: list[str] = []
    for line in stdout_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            entry = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            continue
        if entry.get("type") != "item.completed":
            continue
        item = entry.get("item")
        if not isinstance(item, dict) or item.get("type") != "agent_message":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            agent_texts.append(text)
    if agent_texts:
        return "\n".join(agent_texts)

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
    except (PermissionError, OSError, subprocess.CalledProcessError):
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


def _line_is_terminal_result_event(line: str) -> bool:
    """True if a stdout line is the claude stream-json terminal result event.

    The implementer adapter (claude --print --output-format stream-json) emits a
    single final ``{"type": "result", ...}`` event after the model's last turn.
    Observing it lets a caller bound the post-completion teardown window (Stop
    hooks, MCP server shutdown) so an alive-but-finished subprocess cannot hang
    past the model's actual completion.  Matches the top-level ``type`` only, so a
    nested ``tool_result`` payload that merely contains the substring is not a
    false positive (consistent with
    phase_b_implementer._extract_adapter_result_envelope).
    """
    stripped = line.strip()
    if '"result"' not in stripped:
        return False
    try:
        payload = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return False
    return isinstance(payload, dict) and payload.get("type") == "result"


def _contains_complete_adapter_envelope(text: str) -> bool:
    for candidate in extract_agent_envelope_candidates(text):
        envelope = candidate.decoded
        if not isinstance(envelope, Mapping):
            continue
        if AGENT_ENVELOPE_REQUIRED_KEYS.difference(envelope):
            continue
        decision = envelope["decision"]
        if is_agent_decision_placeholder(decision):
            continue
        if not isinstance(decision, str) or decision not in _AUTHORIZED_AGENT_DECISIONS:
            # Poison only agent-envelope arbitration. The independent legacy
            # meta-envelope branch must still retain its stop authority.
            break
        return True

    # Meta-envelope framing and decision policy are intentionally unchanged.
    for match in _META_ENVELOPE_RE.finditer(text):
        try:
            envelope = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        decision = envelope.get("decision")
        if isinstance(decision, str) and decision in _AUTHORIZED_META_DECISIONS:
            return True
    return False


def _raw_transcript_contains_complete_adapter_envelope(raw_output_path: Path | None) -> bool:
    if raw_output_path is None:
        return False
    try:
        return _contains_complete_adapter_envelope(raw_output_path.read_text(encoding="utf-8"))
    except OSError:
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
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BridgeAdapterError(f"Bridge config is not valid JSON: {exc}") from exc
    if not isinstance(config, dict):
        raise BridgeAdapterError("Bridge config must be a JSON object")
    return config


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
    # Mark this as a pipeline session so hooks (check-reasoning-depth.sh,
    # artifact-edit-gate.sh, etc.) bypass interactive-discipline checks.
    # Env var is simpler and more reliable than process-ancestry walking,
    # which fails when the parent executor is killed by a timeout.
    env["RCX_PIPELINE_SESSION"] = "1"
    if spec.env:
        env.update({key: _expand_value(value, context) for key, value in spec.env.items()})
    if spec.name == "codex":
        explicit_env = spec.env or {}
        if (
            "HOME" not in explicit_env
            and "CODEX_HOME" not in explicit_env
            and "RCX_CODEX_HOME" not in explicit_env
        ):
            real_codex_home = _real_codex_home()
            if _codex_home_is_writable(real_codex_home):
                env["HOME"] = _real_home_dir()
                env.pop("CODEX_HOME", None)
                env.pop("RCX_CODEX_HOME", None)
            else:
                repo_root_text = str(context.get("repo_root") or "").strip()
                if repo_root_text:
                    bus_dir_name = _validated_bus_dir_name(context.get("bus_dir"))
                    runtime_home = Path(repo_root_text) / bus_dir_name / "codex_runtime_home"
                    _seed_codex_runtime_home(runtime_home)
                    env["HOME"] = str(runtime_home)
                    env["CODEX_HOME"] = str(runtime_home)
                    env["RCX_CODEX_HOME"] = str(runtime_home)
                else:
                    env["HOME"] = _real_home_dir()
                    env.pop("CODEX_HOME", None)
                    env.pop("RCX_CODEX_HOME", None)
    return cmd, env


def _tee_stream(
    source: io.TextIOWrapper,
    sink: io.StringIO,
    tty: Any,
    raw_writer: Any = None,
    on_line: Any = None,
) -> None:
    """Read from source, write to sink, tty, and optional raw transcript writer."""
    for line in source:
        sink.write(line)
        if raw_writer is not None:
            raw_writer(line)
        if on_line is not None:
            on_line(line, sink)
        if tty is not None:
            tty.write(line)
            tty.flush()


def _build_raw_transcript_writers(raw_file: Any) -> tuple[Any, Any, Any]:
    """Create locked stdout/stderr raw transcript writers for a shared file handle."""
    lock = threading.Lock()
    state = {
        "has_output": False,
        "stderr_written": False,
    }

    def _write(text: str) -> None:
        if raw_file is None or not text:
            return
        raw_file.write(text)
        raw_file.flush()

    def write_stdout(text: str) -> None:
        if raw_file is None or not text:
            return
        with lock:
            _write(text)
            state["has_output"] = True

    def write_stderr(text: str) -> None:
        if raw_file is None or not text:
            return
        with lock:
            if not state["stderr_written"]:
                header = "\n[stderr]\n" if state["has_output"] else "[stderr]\n"
                _write(header)
                state["stderr_written"] = True
                state["has_output"] = True
            _write(text)

    def stderr_written() -> bool:
        return bool(state["stderr_written"])

    return write_stdout, write_stderr, stderr_written


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
    post_result_exit_timeout_s: float | None = None,
) -> str:
    """Run adapter with full capture (no streaming), optionally writing to raw file incrementally."""
    raw_fh = None
    if raw_output_path is not None:
        raw_fh = open(raw_output_path, "w", encoding="utf-8")
    write_stdout_raw, write_stderr_raw, stderr_written_raw = _build_raw_transcript_writers(raw_fh)

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
    stdout_progress = threading.Event()
    envelope_terminated = threading.Event()
    post_result_killed = threading.Event()
    result_terminal_seen_at: list[float | None] = [None]

    def _stop_after_envelope(line: str, sink: io.StringIO) -> None:
        if (
            not stop_after_envelope
            or envelope_terminated.is_set()
        ):
            return
        if (
            _contains_complete_adapter_envelope(
                _authoritative_output_so_far(spec, cmd, sink.getvalue())
            )
            or _raw_transcript_contains_complete_adapter_envelope(raw_output_path)
        ):
            envelope_terminated.set()
            # Give the adapter a moment to flush trailing bytes before
            # terminating any lingering subprocess tree.
            time.sleep(0.05)
            _kill_process_group(proc, wait_for_exit=True)

    def _record_stdout_progress(line: str, sink: io.StringIO) -> None:
        stdout_progress.set()
        _stop_after_envelope(line, sink)
        if (
            post_result_exit_timeout_s is not None
            and result_terminal_seen_at[0] is None
            and _line_is_terminal_result_event(line)
        ):
            result_terminal_seen_at[0] = time.monotonic()

    stdout_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stdout, stdout_buf, None, write_stdout_raw, _record_stdout_progress),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stderr, stderr_buf, None, write_stderr_raw),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    # Watchdog timer: kill the ENTIRE process group if it exceeds timeout_s.
    # This prevents orphaned children (e.g., codex exec spawning sub-processes).
    timed_out = threading.Event()
    zero_output_timed_out = threading.Event()
    stale_timed_out = threading.Event()
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

    try:
        if spec.prompt_via_stdin and proc.stdin is not None:
            try:
                proc.stdin.write(prompt_text)
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Process exited early; continue to read remaining output
        if zero_output_timeout_s is not None and raw_output_path is not None:
            zero_output_watchdog = threading.Timer(
                zero_output_timeout_s,
                _kill_after_zero_output_timeout,
            )
            zero_output_watchdog.daemon = True
            zero_output_watchdog.start()
        deadline = time.monotonic() + spec.timeout_s
        poll_for_post_result = post_result_exit_timeout_s is not None
        wait_slice = (
            0.2 if (stop_after_envelope or poll_for_post_result) else spec.timeout_s
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(cmd, spec.timeout_s)
            try:
                proc.wait(timeout=min(wait_slice, remaining))
                break
            except subprocess.TimeoutExpired:
                if stop_after_envelope and (
                    envelope_terminated.is_set()
                    or _contains_complete_adapter_envelope(
                        _authoritative_output_so_far(spec, cmd, stdout_buf.getvalue())
                    )
                    or _raw_transcript_contains_complete_adapter_envelope(raw_output_path)
                ):
                    envelope_terminated.set()
                    _kill_process_group(proc, wait_for_exit=True)
                    continue
                if (
                    poll_for_post_result
                    and result_terminal_seen_at[0] is not None
                    and time.monotonic() - result_terminal_seen_at[0]
                    >= post_result_exit_timeout_s
                ):
                    post_result_killed.set()
                    _kill_process_group(proc, wait_for_exit=True)
                    continue
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
        stdout_thread.join(timeout=5)
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
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' timed out after {spec.timeout_s}s"
        )

    join_timeout = (
        0.2 if (envelope_terminated.is_set() or post_result_killed.is_set()) else 5
    )
    stdout_thread.join(timeout=join_timeout)
    stderr_thread.join(timeout=join_timeout)

    output = _normalize_stdout_for_adapter(spec, cmd, stdout_buf.getvalue())
    stderr_text = stderr_buf.getvalue()
    if stderr_text:
        if not output.strip() and _contains_complete_adapter_envelope(stderr_text):
            # CLI wrote all output including envelope to stderr (e.g. codex exec).
            # Promote stderr as authoritative output so parse_envelope accepts it.
            output = stderr_text
        else:
            output = f"{output}\n[stderr]\n{stderr_text}".strip()
        if raw_fh is not None and not stderr_written_raw():
            write_stderr_raw(stderr_text)
    if post_result_killed.is_set():
        # The adapter emitted its terminal result event but the process lingered
        # past post_result_exit_timeout_s (e.g. a hung Stop hook or MCP-server
        # teardown).  The completed work is already captured, so return it rather
        # than discarding it as a timeout/stall failure.
        if raw_fh is not None:
            raw_fh.close()
        return output
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
    if proc.returncode != 0 and result_terminal_seen_at[0] is not None:
        # The adapter emitted its terminal result event and then the process
        # exited non-zero during post-completion teardown (e.g. a .claude Stop
        # hook that errors/hangs after the implementer's result envelope). The
        # completed work is already captured, so return it -- the downstream
        # result-subtype check classifies success vs error -- instead of
        # discarding it as an "exited N" failure that forces a wasted implementer
        # re-invoke (#43). result_terminal_seen_at is only armed when
        # post_result_exit_timeout_s is set (implementer), so reviewer/meta
        # adapters keep the original raise-on-nonzero-exit behavior.
        return output
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
    post_result_exit_timeout_s: float | None = None,
) -> str:
    """Run adapter with live tee to terminal + full capture for raw output file."""
    raw_fh = None
    if raw_output_path is not None:
        raw_fh = open(raw_output_path, "w", encoding="utf-8")
    write_stdout_raw, write_stderr_raw, stderr_written_raw = _build_raw_transcript_writers(raw_fh)

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
    post_result_killed = threading.Event()
    result_terminal_seen_at: list[float | None] = [None]

    def _stop_after_envelope(line: str, sink: io.StringIO) -> None:
        if (
            not stop_after_envelope
            or envelope_terminated.is_set()
        ):
            return
        if (
            _contains_complete_adapter_envelope(
                _authoritative_output_so_far(spec, cmd, sink.getvalue())
            )
            or _raw_transcript_contains_complete_adapter_envelope(raw_output_path)
        ):
            envelope_terminated.set()
            # Give the adapter a brief grace period to flush any immediate trailing bytes
            # before we terminate lingering background work in the same process group.
            time.sleep(0.05)
            _kill_process_group(proc, wait_for_exit=True)

    def _record_stdout_progress(line: str, sink: io.StringIO) -> None:
        stdout_progress.set()
        _stop_after_envelope(line, sink)
        if (
            post_result_exit_timeout_s is not None
            and result_terminal_seen_at[0] is None
            and _line_is_terminal_result_event(line)
        ):
            result_terminal_seen_at[0] = time.monotonic()

    stdout_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stdout, stdout_buf, sys.stdout, write_stdout_raw, _record_stdout_progress),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stderr, stderr_buf, sys.stderr, write_stderr_raw),
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

    try:
        if spec.prompt_via_stdin and proc.stdin is not None:
            try:
                proc.stdin.write(prompt_text)
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Process exited early; continue to wait for remaining output
        if zero_output_timeout_s is not None and raw_output_path is not None:
            zero_output_watchdog = threading.Timer(
                zero_output_timeout_s,
                _kill_after_zero_output_timeout,
            )
            zero_output_watchdog.daemon = True
            zero_output_watchdog.start()
        deadline = time.monotonic() + spec.timeout_s
        poll_for_post_result = post_result_exit_timeout_s is not None
        wait_slice = (
            0.2 if (stop_after_envelope or poll_for_post_result) else spec.timeout_s
        )
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(cmd, spec.timeout_s)
            try:
                proc.wait(timeout=min(wait_slice, remaining))
                break
            except subprocess.TimeoutExpired:
                if stop_after_envelope and (
                    envelope_terminated.is_set()
                    or _contains_complete_adapter_envelope(
                        _authoritative_output_so_far(spec, cmd, stdout_buf.getvalue())
                    )
                    or _raw_transcript_contains_complete_adapter_envelope(raw_output_path)
                ):
                    envelope_terminated.set()
                    _kill_process_group(proc, wait_for_exit=True)
                    continue
                if (
                    poll_for_post_result
                    and result_terminal_seen_at[0] is not None
                    and time.monotonic() - result_terminal_seen_at[0]
                    >= post_result_exit_timeout_s
                ):
                    post_result_killed.set()
                    _kill_process_group(proc, wait_for_exit=True)
                    continue
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

    join_timeout = (
        0.2 if (envelope_terminated.is_set() or post_result_killed.is_set()) else 5
    )
    stdout_thread.join(timeout=join_timeout)
    stderr_thread.join(timeout=join_timeout)

    output = _normalize_stdout_for_adapter(spec, cmd, stdout_buf.getvalue())
    stderr_text = stderr_buf.getvalue()
    if stderr_text:
        if not output.strip() and _contains_complete_adapter_envelope(stderr_text):
            # CLI wrote all output including envelope to stderr (e.g. codex exec).
            # Promote stderr as authoritative output so parse_envelope accepts it.
            output = stderr_text
        else:
            output = f"{output}\n[stderr]\n{stderr_text}".strip()
        if raw_fh is not None and not stderr_written_raw():
            write_stderr_raw(stderr_text)
    if post_result_killed.is_set():
        # The adapter emitted its terminal result event but the process lingered
        # past post_result_exit_timeout_s (e.g. a hung Stop hook or MCP-server
        # teardown).  The completed work is already captured, so return it rather
        # than discarding it as a timeout/stall failure.
        if raw_fh is not None:
            raw_fh.close()
        return output
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
    if proc.returncode != 0 and result_terminal_seen_at[0] is not None:
        # The adapter emitted its terminal result event and then the process
        # exited non-zero during post-completion teardown (e.g. a .claude Stop
        # hook that errors/hangs after the implementer's result envelope). The
        # completed work is already captured, so return it -- the downstream
        # result-subtype check classifies success vs error -- instead of
        # discarding it as an "exited N" failure that forces a wasted implementer
        # re-invoke (#43). result_terminal_seen_at is only armed when
        # post_result_exit_timeout_s is set (implementer), so reviewer/meta
        # adapters keep the original raise-on-nonzero-exit behavior.
        return output
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
    post_result_exit_timeout_s: float | None = None,
    bus_dir: str | Path | None = None,
) -> str:
    if timeout_override_s is not None:
        if timeout_override_s <= 0:
            raise BridgeAdapterError("timeout_override_s must be positive")
        spec = replace(spec, timeout_s=timeout_override_s)
    if stale_timeout_s is not None and stale_timeout_s <= 0:
        raise BridgeAdapterError("stale_timeout_s must be positive")
    if post_result_exit_timeout_s is not None and post_result_exit_timeout_s <= 0:
        raise BridgeAdapterError("post_result_exit_timeout_s must be positive")

    context = {
        "prompt_file": str(prompt_path),
        "repo_root": str(repo_root),
        "job_id": job_id,
        "turn_id": turn_id,
        "agent_role": agent_role,
        "bus_dir": _validated_bus_dir_name(bus_dir),
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
            post_result_exit_timeout_s,
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
        post_result_exit_timeout_s,
    )
