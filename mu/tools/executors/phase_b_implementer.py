#!/usr/bin/env python3
"""Phase B implementer: separate code-writing actor for Phase B execution.

This is NOT main Claude. This is a config-driven subagent that receives
a locked plan and produces code changes. The bridge reviewer remains
read-only. The phase_b_executor orchestrates this actor.

Uses the bridge adapter infrastructure to invoke a Claude/Codex agent
with an implementation prompt derived from the locked plan.

Authority model:
  - post-merge supervisor = read-only router
  - phase_b_executor = deterministic orchestrator
  - phase_b_implementer = mutating code writer (THIS FILE)
  - bridge reviewer = read-only reviewer
  - pre-commit supervisor = commit gate
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


class ImplementerError(RuntimeError):
    """Raised when the implementer cannot proceed."""


def build_implementation_prompt(
    plan_content: str,
    *,
    repo_root: Path,
    wave_id: str,
    scope_hint: str = "",
) -> str:
    """Build a structured implementation prompt from a locked plan.

    The prompt instructs the implementer to:
    1. Read the plan
    2. Implement the specified changes
    3. Run validation commands
    4. Report results as structured JSON
    """
    return f"""You are a code implementation agent. Your job is to implement
the changes described in the locked plan below. You are NOT a reviewer —
you write code.

## Locked Plan

{plan_content}

## Instructions

1. Read the plan carefully.
2. Implement ALL specified changes.
3. Run the validation commands listed in the plan.
4. Report your results.

## Constraints

- Do NOT modify files outside the plan's scope.
- Do NOT create new subsystems not described in the plan.
- Do NOT bypass any gates (--no-verify, etc.).
- If you encounter a blocker, report it — do not work around it.

## Wave Context

- wave_id: {wave_id}
- repo_root: {repo_root}
{f'- scope_hint: {scope_hint}' if scope_hint else ''}

## Required Output

Report your results as:
- List of files changed
- Validation command results
- Any issues encountered
"""


def invoke_implementer(
    repo_root: Path,
    prompt: str,
    *,
    backend: str = "codex",
    model_override: str | None = None,
    timeout: int = 1200,
    verbose: bool = False,
) -> dict[str, Any]:
    """Invoke the implementer agent via bridge adapter infrastructure.

    Returns a dict with:
      - status: "success" | "error" | "timeout"
      - output: raw agent output text
      - exit_code: process exit code
    """
    # Use bridge_supervisor.py review as the invocation surface
    # The implementer prompt is sent as a task file
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    task_path = scratch_dir / "phase_b_implementer_task.md"
    task_path.write_text(prompt, encoding="utf-8")

    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    cmd = [
        sys.executable, str(bridge_script),
        "review",
        "--task-file", str(task_path),
        "--summary", "Phase B implementation",
        "--reviewer", backend,
    ]
    if verbose:
        cmd.append("-v")

    if verbose:
        print(f"[implementer] Invoking {backend} implementer (timeout={timeout}s)")

    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "output": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "output": "",
            "stderr": f"Implementer timed out after {timeout}s",
            "exit_code": -1,
        }


def load_executor_config(repo_root: Path) -> dict[str, Any]:
    """Load executor config for backend/model/timeout settings."""
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    if not config_path.exists():
        return {
            "backends": {"phase_b_executor": "codex"},
            "model_overrides": {},
            "timeouts": {"phase_b_executor": 1200},
        }
    return json.loads(config_path.read_text(encoding="utf-8"))
