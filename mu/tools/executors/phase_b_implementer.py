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
import re
import sys
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from executor_common import (
        ensure_bridge_config_path,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        load_executor_config,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    assert _spec.loader is not None
    _spec.loader.exec_module(_mod)
    ensure_bridge_config_path = _mod.ensure_bridge_config_path
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError
    load_executor_config = _mod.load_executor_config

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


_OUTER_PIPELINE_COMMAND_TARGET_RE = (
    r"(?:[A-Z0-9_]+=\S+\s+)*"
    r"(?:(?:python3|python)\s+)?"
    r"(?:\./)?"
    r"(?:"
    r"(?:mu/)?tools/executors/(?:executor_dispatch|phase_a_executor|phase_b_executor|commit_executor)\.py"
    r"|tools/session/founder_session_guard\.sh"
    r"|tools/session/founder_session_attest\.sh"
    r"|codex-rcx-preflight"
    r")\b"
)
_OUTER_PIPELINE_COMMAND_LINE_RE = re.compile(
    r"^\s*"
    r"(?:(?:>\s*)|(?:[-*+]\s+(?:\[[ xX]\]\s+)?)|(?:\d+[.)]\s+))*"
    r"`*"
    r"\s*"
    r"(?:[$#]\s+)?"
    + _OUTER_PIPELINE_COMMAND_TARGET_RE
)
_OUTER_PIPELINE_COMMAND_CODE_SPAN_RE = re.compile(
    r"`+\s*"
    r"(?:[$#]\s+)?"
    + _OUTER_PIPELINE_COMMAND_TARGET_RE
)
_OUTER_PIPELINE_COMMAND_PLACEHOLDER = (
    "[outer-pipeline command omitted from Phase B implementer prompt]"
)


def _contains_outer_pipeline_command(line: str) -> bool:
    """Return True for runnable outer-pipeline commands in locked-plan text."""
    return bool(
        _OUTER_PIPELINE_COMMAND_LINE_RE.search(line)
        or _OUTER_PIPELINE_COMMAND_CODE_SPAN_RE.search(line)
    )


def _render_locked_plan_for_implementer(plan_content: str) -> str:
    """Render locked plan text while making outer-pipeline commands inert."""
    rendered: list[str] = []
    for line in plan_content.splitlines():
        if _contains_outer_pipeline_command(line):
            rendered.append(_OUTER_PIPELINE_COMMAND_PLACEHOLDER)
        else:
            rendered.append(line)
    return "\n".join(rendered)


def _extract_adapter_result_envelope(output: Any) -> dict[str, Any]:
    """Extract the final adapter result event from JSON or JSONL output."""
    if not isinstance(output, str):
        return {}
    text = output.strip()
    if not text:
        return {}
    payloads: list[dict[str, Any]] = []
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        parsed = None
    if isinstance(parsed, dict):
        payloads.append(parsed)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            parsed_line = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(parsed_line, dict):
            payloads.append(parsed_line)
    for payload in reversed(payloads):
        if payload.get("type") == "result":
            return payload
    return {}


def _adapter_result_diagnostics(output: Any) -> dict[str, Any]:
    envelope = _extract_adapter_result_envelope(output)
    subtype = str(envelope.get("subtype") or "").strip()
    if not subtype or subtype == "success":
        return {}
    diagnostics: dict[str, Any] = {
        "error_subtype": subtype,
        "adapter_result": envelope,
    }
    stop_reason = envelope.get("stop_reason")
    if stop_reason not in (None, ""):
        diagnostics["stop_reason"] = stop_reason
    num_turns = envelope.get("num_turns")
    if num_turns not in (None, ""):
        diagnostics["num_turns"] = num_turns
    return diagnostics


def _read_adapter_raw_output(raw_output_path: Path) -> str:
    try:
        return raw_output_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _adapter_result_diagnostics_from_outputs(*outputs: Any) -> dict[str, Any]:
    for output in outputs:
        diagnostics = _adapter_result_diagnostics(output)
        if diagnostics:
            return diagnostics
    return {}


def build_implementation_prompt(
    plan_content: str,
    *,
    repo_root: Path,
    wave_id: str,
    scope_hint: str = "",
    scope_contract: str = "",
    learning_context: str = "",
) -> str:
    """Build a structured implementation prompt from a locked plan.

    The prompt instructs the implementer to:
    1. Read the plan
    2. Implement the specified changes
    3. Run only the Phase B-local validation commands
    4. Report results as structured JSON

    Args:
        learning_context: Pre-computed, sanitized learning store output from
            load_relevant_learnings(). Injected as-is when non-empty.
    """
    rendered_plan = _render_locked_plan_for_implementer(plan_content)
    learning_section = f"\n{learning_context}\n" if learning_context else ""
    scope_contract_section = (
        f"\n## Scope Contract\n\n{scope_contract}\n"
        if scope_contract else ""
    )
    return f"""You are a code implementation agent. Your job is to implement
the changes described in the locked plan below. You are NOT a reviewer —
you write code.

## Phase B Execution Boundary

This prompt is already running inside Phase B under the outer dispatcher. Treat
any locked-plan pipeline launch, startup/preflight, attestation, commit, push,
PR, merge, or closeout command as non-executable context. Do NOT run dispatcher
or executor launch commands from inside this implementer, including
`executor_dispatch.py`, `phase_a_executor.py`, `phase_b_executor.py`, or
`commit_executor.py`.

## Locked Plan

{rendered_plan}
{learning_section}
{scope_contract_section}
## Instructions

1. Read the plan carefully.
2. Implement ALL specified changes.
3. Run only the Phase B-local validation commands listed in the plan.
4. Report your results.

## Constraints

- Do NOT modify files outside the plan's scope.
- Do NOT create new subsystems not described in the plan.
- Do NOT bypass any gates (--no-verify, etc.).
- Do NOT run commit/push governance commands from inside this Phase B implementer.
  Specifically: do NOT run `./tools/pre-push-fast`, `./tools/audit_fast.sh`,
  `./dev.sh`, `git push`, `gh pr`, or merge scripts as part of Phase B-local
  validation. Those belong to commit/pre-push execution, not the implementer.
- If the plan includes broader governance or closeout commands, treat them as
  executor/closeout-owned surfaces unless the plan explicitly says they are
  required as Phase B-local validation.
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
DEFAULT_IMPLEMENTER_STALE_TIMEOUT_S = 300.0


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
    bus_dir: str | Path | None = None,
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
    try:
        ensure_not_agent_review_mode("phase_b_implementer.invoke_implementer")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "output": "",
            "stderr": str(exc),
            "exit_code": -1,
            "job_id": "",
            "model_override_applied": False,
        }

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

    config = load_executor_config(repo_root)
    raw_stale_timeout = config.get("timeouts", {}).get(
        "phase_b_implementer_stale",
        DEFAULT_IMPLEMENTER_STALE_TIMEOUT_S,
    )
    try:
        stale_timeout_s = float(raw_stale_timeout)
    except (TypeError, ValueError):
        stale_timeout_s = DEFAULT_IMPLEMENTER_STALE_TIMEOUT_S
    if stale_timeout_s <= 0:
        stale_timeout_s = DEFAULT_IMPLEMENTER_STALE_TIMEOUT_S
    stale_timeout_s = min(float(timeout), stale_timeout_s)
    # Do NOT use zero_output_timeout for the implementer path.
    # claude --print defers all stdout until after the model's final text
    # response — intermediate tool calls (Read, Edit, Bash, etc.) produce
    # no stdout.  A complex implementer session can run 35+ tool calls
    # over 300+ seconds with zero stdout, triggering a false-positive kill.
    # The stale_timeout already guards against true subprocess hangs by
    # monitoring process-level activity, and the adapter's main timeout_s
    # watchdog enforces the wall-clock budget.
    # Evidence: session 34ffd8cf (2026-04-13) made 35 tool calls across
    # 113 events but was killed at 300s for "no stdout" while actively
    # working (last event: mid-Bash-tool-call).
    zero_output_timeout_s = None

    AdapterSpec = _bridge_adapters.AdapterSpec
    BridgeAdapterError = _bridge_adapters.BridgeAdapterError

    # Load bridge config from the active invocation bus.
    try:
        config_path = ensure_bridge_config_path(repo_root, bus_dir)
        config = _bridge_adapters.load_bridge_config(config_path)
        adapter = _bridge_adapters.get_adapter(config, backend)
    except (BridgeAdapterError, ExecutorCommonError) as exc:
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
            f"stale_timeout={stale_timeout_s}s, "
            f"zero_output_timeout={zero_output_timeout_s}s, "
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
            bus_dir=bus_dir,
            raw_output_path=raw_output_path,
            zero_output_timeout_s=zero_output_timeout_s,
            stale_timeout_s=stale_timeout_s,
        )
        diagnostics = _adapter_result_diagnostics_from_outputs(
            _read_adapter_raw_output(raw_output_path),
            output,
        )
        if diagnostics:
            return {
                "status": "error",
                "output": output,
                "stderr": (
                    "Adapter result subtype: "
                    f"{diagnostics.get('error_subtype')}"
                ),
                "exit_code": 1,
                "job_id": job_id,
                "model_override_applied": model_applied,
                **diagnostics,
            }
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
        adapter_output = str(getattr(exc, "output", "") or "")
        diagnostics = _adapter_result_diagnostics_from_outputs(
            _read_adapter_raw_output(raw_output_path),
            adapter_output,
        )
        lowered = error_str.lower()
        is_timeout = "timed out" in lowered
        is_stale = "stalled after" in lowered
        return {
            "status": "timeout" if is_timeout else ("stale" if is_stale else "error"),
            "output": adapter_output,
            "stderr": error_str,
            "exit_code": (
                getattr(exc, "returncode", None)
                if getattr(exc, "returncode", None) is not None
                else (-1 if is_timeout else (-2 if is_stale else 1))
            ),
            "job_id": job_id,
            "model_override_applied": model_applied,
            **diagnostics,
        }
