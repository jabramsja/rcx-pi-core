#!/usr/bin/env python3
"""Helpers for running bridge-configured agent commands."""

from __future__ import annotations

import io
import json
import os
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass
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


def _tee_stream(source: io.TextIOWrapper, sink: io.StringIO, tty: Any, raw_file: Any = None) -> None:
    """Read from source, write to sink (capture), tty (live display), and raw_file (incremental persist)."""
    for line in source:
        sink.write(line)
        if tty is not None:
            tty.write(line)
            tty.flush()
        if raw_file is not None:
            raw_file.write(line)
            raw_file.flush()


def _run_adapter_buffered(
    spec: AdapterSpec,
    cmd: list[str],
    env: dict[str, str],
    prompt_text: str,
    repo_root: Path,
    raw_output_path: Path | None = None,
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

    def _kill_after_timeout() -> None:
        timed_out.set()
        try:
            # Kill entire process group to clean up children
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            try:
                proc.kill()
            except OSError:
                pass

    watchdog = threading.Timer(spec.timeout_s, _kill_after_timeout)
    watchdog.daemon = True
    watchdog.start()

    try:
        if spec.prompt_via_stdin and proc.stdin is not None:
            try:
                proc.stdin.write(prompt_text)
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Process exited early; continue to read remaining output
        for line in proc.stdout:
            stdout_lines.append(line)
            if raw_fh is not None:
                raw_fh.write(line)
                raw_fh.flush()
        proc.wait(timeout=spec.timeout_s)
        watchdog.cancel()
    except subprocess.TimeoutExpired as exc:
        watchdog.cancel()
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            proc.kill()
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
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                proc.kill()
            proc.wait()
        stderr_thread.join(timeout=5)
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' timed out after {spec.timeout_s}s"
        )

    stderr_thread.join(timeout=5)

    output = "".join(stdout_lines)
    stderr_text = stderr_buf.getvalue()
    if stderr_text:
        output = f"{output}\n[stderr]\n{stderr_text}".strip()
        if raw_fh is not None:
            raw_fh.write(f"\n[stderr]\n{stderr_text}")
            raw_fh.flush()
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

    stdout_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stdout, stdout_buf, sys.stdout, raw_fh),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_tee_stream,
        args=(proc.stderr, stderr_buf, sys.stderr),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()

    try:
        if spec.prompt_via_stdin and proc.stdin is not None:
            try:
                proc.stdin.write(prompt_text)
                proc.stdin.close()
            except BrokenPipeError:
                pass  # Process exited early; continue to wait for remaining output
        proc.wait(timeout=spec.timeout_s)
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            proc.kill()
        proc.wait()
        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)
        if raw_fh is not None:
            raw_fh.close()
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' timed out after {spec.timeout_s}s"
        ) from exc

    stdout_thread.join(timeout=5)
    stderr_thread.join(timeout=5)

    output = stdout_buf.getvalue()
    stderr_text = stderr_buf.getvalue()
    if stderr_text:
        output = f"{output}\n[stderr]\n{stderr_text}".strip()
        if raw_fh is not None:
            raw_fh.write(f"\n[stderr]\n{stderr_text}")
            raw_fh.flush()
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
) -> str:
    context = {
        "prompt_file": str(prompt_path),
        "repo_root": str(repo_root),
        "job_id": job_id,
        "turn_id": turn_id,
        "agent_role": agent_role,
    }
    cmd, env = _prepare_adapter_env(spec, context)

    if stream:
        return _run_adapter_streaming(spec, cmd, env, prompt_text, repo_root, raw_output_path)
    return _run_adapter_buffered(spec, cmd, env, prompt_text, repo_root, raw_output_path)
