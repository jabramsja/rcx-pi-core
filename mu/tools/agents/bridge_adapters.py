#!/usr/bin/env python3
"""Helpers for running bridge-configured agent commands."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BridgeAdapterError(RuntimeError):
    """Raised when bridge adapter configuration or execution fails."""


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


def run_adapter(
    spec: AdapterSpec,
    *,
    prompt_text: str,
    prompt_path: Path,
    repo_root: Path,
    job_id: str,
    turn_id: str,
    agent_role: str,
) -> str:
    context = {
        "prompt_file": str(prompt_path),
        "repo_root": str(repo_root),
        "job_id": job_id,
        "turn_id": turn_id,
        "agent_role": agent_role,
    }
    cmd = [_expand_value(part, context) for part in spec.cmd]
    env = os.environ.copy()
    if spec.env:
        env.update({key: _expand_value(value, context) for key, value in spec.env.items()})

    try:
        result = subprocess.run(
            cmd,
            input=prompt_text if spec.prompt_via_stdin else None,
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
            timeout=spec.timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' timed out after {spec.timeout_s}s"
        ) from exc
    except FileNotFoundError as exc:
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' command not found: {cmd[0]}"
        ) from exc

    output = result.stdout
    if result.stderr:
        output = f"{output}\n[stderr]\n{result.stderr}".strip()
    if result.returncode != 0:
        snippet = output[-1000:]
        raise BridgeAdapterError(
            f"Adapter '{spec.name}' exited {result.returncode}. Output tail:\n{snippet}"
        )
    return output
