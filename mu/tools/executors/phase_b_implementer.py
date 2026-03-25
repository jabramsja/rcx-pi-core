#!/usr/bin/env python3
"""Phase B implementer: separate code-writing actor for Phase B execution.

This is NOT main Claude. This is a config-driven subagent that receives
a locked plan and produces code changes. The bridge reviewer remains
read-only. The phase_b_executor orchestrates this actor.

Uses bridge_adapters.run_adapter() DIRECTLY to invoke the configured backend
as a code-writing actor. Does NOT route through the review command
(which is a review-only surface with a prompt that says "do not edit files").

Authority model:
  - post-merge supervisor = read-only router
  - phase_b_executor = deterministic orchestrator
  - phase_b_implementer = mutating code writer (THIS FILE)
  - bridge reviewer = read-only reviewer (separate from implementer)
  - pre-commit supervisor = commit gate
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

# Import bridge_adapters at module level for testability (patchable).
# Guarded because bridge_adapters may not be on sys.path until runtime.
_bridge_adapters = None
_bridge_import_error = None

try:
    _agents_dir = str(Path(__file__).resolve().parent.parent / "agents")
    if _agents_dir not in sys.path:
        sys.path.insert(0, _agents_dir)
    import bridge_adapters as _bridge_adapters
except ImportError as _exc:
    _bridge_import_error = _exc


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


# Model override support per backend.
# Only backends listed here with a known flag can honor model override.
_MODEL_OVERRIDE_SUPPORT: dict[str, str | None] = {
    "codex": None,   # Codex CLI does not support --model for cross-vendor models
    "claude": "--model",  # Claude Code CLI supports --model <name>
}


def _apply_model_override(
    cmd: list[str],
    backend: str,
    model_override: str,
) -> tuple[list[str], bool]:
    """Apply model override to adapter command if the backend supports it.

    Returns (new_cmd, was_applied).
    """
    flag = _MODEL_OVERRIDE_SUPPORT.get(backend)
    if flag is None:
        return cmd, False

    # Replace existing flag value or append
    new_cmd = list(cmd)
    if flag in new_cmd:
        idx = new_cmd.index(flag)
        if idx + 1 < len(new_cmd):
            new_cmd[idx + 1] = model_override
        else:
            new_cmd.append(model_override)
    else:
        new_cmd.extend([flag, model_override])
    return new_cmd, True


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

    Uses bridge_adapters.run_adapter() directly with an implementation prompt.
    Does NOT route through the review command (which is review-only).

    Returns a dict with:
      - status: "success" | "error" | "timeout"
      - output: raw agent output text
      - exit_code: process exit code
      - job_id: unique job identifier for this invocation
      - model_override_applied: whether model override was actually honored
    """
    # Use module-level bridge_adapters import, with runtime fallback
    global _bridge_adapters, _bridge_import_error
    if _bridge_adapters is None:
        try:
            agents_dir = str(repo_root / "mu" / "tools" / "agents")
            if agents_dir not in sys.path:
                sys.path.insert(0, agents_dir)
            import bridge_adapters as _bridge_adapters
        except ImportError as exc:
            _bridge_import_error = exc

    if _bridge_adapters is None:
        return {
            "status": "error",
            "output": "",
            "stderr": f"Cannot import bridge_adapters: {_bridge_import_error}",
            "exit_code": -1,
            "job_id": "",
            "model_override_applied": False,
        }

    AdapterSpec = _bridge_adapters.AdapterSpec
    BridgeAdapterError = _bridge_adapters.BridgeAdapterError

    # Load bridge config
    config_path = repo_root / ".agent_bus" / "bridge_config.json"
    try:
        config = _bridge_adapters.load_bridge_config(config_path)
        adapter = _bridge_adapters.get_adapter(config, backend)
    except BridgeAdapterError as exc:
        return {
            "status": "error",
            "output": "",
            "stderr": f"Bridge adapter config error: {exc}",
            "exit_code": -1,
            "job_id": "",
            "model_override_applied": False,
        }

    # Apply timeout override from caller
    cmd = list(adapter.cmd)
    adapter_timeout = timeout

    # Apply model override if the backend supports it
    model_applied = False
    if model_override:
        cmd, model_applied = _apply_model_override(cmd, backend, model_override)
        if not model_applied and verbose:
            print(
                f"[implementer] WARNING: model_override={model_override!r} not supported "
                f"by backend={backend!r}. Using backend's default model."
            )

    # Build the final adapter spec with overrides
    final_adapter = _bridge_adapters.AdapterSpec(
        name=adapter.name,
        cmd=cmd,
        timeout_s=adapter_timeout,
        prompt_via_stdin=adapter.prompt_via_stdin,
        env=adapter.env,
        mode=adapter.mode,
    )

    # Generate deterministic job_id for this invocation
    job_id = f"impl-{uuid.uuid4().hex[:8]}"

    # Write prompt to file for adapter (some adapters read from file)
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    prompt_path = scratch_dir / "phase_b_implementer_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")

    # Raw output for debugging
    raw_output_path = scratch_dir / f"phase_b_implementer_output_{job_id}.txt"

    if verbose:
        print(
            f"[implementer] Invoking {backend} (timeout={adapter_timeout}s, "
            f"model_override={model_override!r}, applied={model_applied})"
        )

    try:
        output = _bridge_adapters.run_adapter(
            final_adapter,
            prompt_text=prompt,
            prompt_path=prompt_path,
            repo_root=repo_root,
            job_id=job_id,
            turn_id="impl",
            agent_role="implementer",
            raw_output_path=raw_output_path,
        )
        return {
            "status": "success",
            "output": output,
            "stderr": "",
            "exit_code": 0,
            "job_id": job_id,
            "model_override_applied": model_applied,
        }
    except BridgeAdapterError as exc:
        error_str = str(exc)
        is_timeout = "timed out" in error_str.lower()
        return {
            "status": "timeout" if is_timeout else "error",
            "output": "",
            "stderr": error_str,
            "exit_code": -1 if is_timeout else 1,
            "job_id": job_id,
            "model_override_applied": model_applied,
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
