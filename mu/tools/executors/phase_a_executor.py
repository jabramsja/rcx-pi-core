#!/usr/bin/env python3
"""Phase A executor: creates plan packets through design + bridge convergence.

Invoked by ROUTE_PHASE_A routing token from the post-merge supervisor.
Creates or refines a plan packet, runs agents, loops bridge until converged,
then commits the plan via the branch/merge discipline.

Control flow:
1. Read routing record and rollout context
2. Create a plan packet draft in reports/control_plane/
3. Run SDK agent review on the plan
4. Send plan + agent findings to bridge (--no-diff, design review)
5. Fix blockers, defer non-blockers
6. Loop bridge until only non-blockers remain
7. Set Phase-A-Lock: LOCKED
8. Commit plan via branch/merge discipline (feature branch -> PR -> merge)
9. Trigger post-merge supervisor on dev

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md Section B.2
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        load_executor_config,
        load_routing_record,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        run_bridge_subprocess,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    load_executor_config = _mod.load_executor_config
    load_routing_record = _mod.load_routing_record
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError
    run_bridge_subprocess = _mod.run_bridge_subprocess


class PhaseAExecutorError(RuntimeError):
    """Raised when Phase A executor cannot proceed."""


PLAN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
ALLOWED_REVIEW_DEPTHS = {"quick", "full", "founder", "all"}


def resolve_review_depth(config: dict[str, Any], phase_key: str, default: str = "quick") -> str:
    """Resolve review depth from executor config and fail closed on invalid values."""
    depth = config.get("review_depths", {}).get(phase_key, default)
    if depth not in ALLOWED_REVIEW_DEPTHS:
        raise PhaseAExecutorError(
            f"Invalid review depth {depth!r} for {phase_key}; "
            f"expected one of {sorted(ALLOWED_REVIEW_DEPTHS)}"
        )
    return depth


def extract_plan_scope(routing_record: dict[str, Any]) -> dict[str, str]:
    """Extract planning scope from routing record's request_for_claude."""
    return {
        "request": routing_record.get("request_for_claude", ""),
        "summary": routing_record.get("summary", ""),
        "decision": routing_record.get("decision", ""),
    }


def _find_tracked_packet(plan_dir: Path, plan_name: str) -> Path | None:
    """Find an existing tracked/canonical packet matching plan_name.

    Searches for files matching `{plan_name}_*.md` in the plan directory,
    sorted by name (most recent date last). Returns the best match, or
    None if no tracked packet exists.

    A tracked packet is one that is already LOCKED or has meaningful content
    beyond a placeholder stub.
    """
    if not plan_dir.exists():
        return None

    candidates = sorted(plan_dir.glob(f"{plan_name}_*.md"))
    if not candidates:
        return None

    # Prefer locked packets over unlocked ones
    for c in reversed(candidates):
        content = c.read_text(encoding="utf-8")
        if "Phase-A-Lock: LOCKED" in content:
            return c

    # Fall back to the most recent (by filename date) existing packet
    # but only if it has real content (not just a stub header)
    for c in reversed(candidates):
        content = c.read_text(encoding="utf-8")
        # A packet with more than just the header template has real content
        if len(content.strip().splitlines()) > 10:
            return c

    # Return the most recent candidate even if it's a stub —
    # still better than creating a new dated duplicate
    return candidates[-1]


def create_plan_draft(
    repo_root: Path,
    plan_name: str,
    scope: dict[str, str],
) -> Path:
    """Create an initial plan packet draft, or reuse an existing tracked packet.

    If a tracked/canonical packet already exists for this plan_name, reuse it
    instead of creating a new dated placeholder. New dated drafts are only
    created when no matching tracked packet exists.
    """
    if not isinstance(plan_name, str) or not PLAN_NAME_RE.fullmatch(plan_name):
        raise PhaseAExecutorError(f"Unsafe plan_name: {plan_name!r}")
    if Path(plan_name).name != plan_name or "/" in plan_name or "\\" in plan_name:
        raise PhaseAExecutorError(f"Path traversal in plan_name: {plan_name!r}")

    plan_dir = repo_root / "reports" / "control_plane"
    plan_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing tracked packet first
    existing = _find_tracked_packet(plan_dir, plan_name)
    if existing is not None:
        return existing

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plan_path = plan_dir / f"{plan_name}_{date_str}.md"

    if plan_path.exists():
        return plan_path  # Don't overwrite existing draft

    content = f"""# {plan_name.replace('_', ' ').title()}

Date: {date_str}
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED
Purpose: {scope.get('request', 'planning required')}

## Scope

{scope.get('summary', '(to be filled in during Phase A)')}

## Request from Post-Merge Supervisor

{scope.get('request', '(none)')}
"""
    plan_path.write_text(content, encoding="utf-8")
    return plan_path


def run_sdk_agents(
    repo_root: Path,
    files: list[str],
    *,
    depth: str = "quick",
    timeout: int = 600,
) -> dict[str, Any]:
    """Run SDK agent review."""
    cmd = [
        sys.executable, "tools/runners/run_review.py",
        *files, "--depth", depth,
        "--no-memory",
    ]
    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True,
            check=False, timeout=timeout,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Agent review timed out"}


def run_bridge_design_review(
    repo_root: Path,
    plan_path: str,
    round_num: int,
    *,
    job_id: str | None = None,
    timeout: int = 1200,
) -> dict[str, Any]:
    """Run bridge design review (--no-diff) on a plan packet."""
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    task_path = scratch_dir / f"phase_a_bridge_r{round_num}.md"
    task_path.write_text(
        f"# Phase A Bridge Round {round_num}\n\n"
        f"Review the plan at `{plan_path}` for decision completeness.\n\n"
        f"Questions? Concerns? Thoughts? -- Think hard\n",
        encoding="utf-8",
    )

    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    cmd = [
        sys.executable, str(bridge_script),
        "review",
        "--task-file", str(task_path),
        "--summary", f"Phase A plan review R{round_num}",
        "--reviewer", "codex",
        "-v", "--no-diff",
    ]
    if job_id:
        cmd.extend(["--job-id", job_id])
    try:
        result = run_bridge_subprocess(cmd, cwd=repo_root, timeout=timeout)
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except ExecutorCommonError:
        return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out"}


def lock_plan(repo_root: Path, plan_path: str) -> None:
    """Set Phase-A-Lock: LOCKED in a plan packet."""
    full_path = repo_root / plan_path
    content = full_path.read_text(encoding="utf-8")
    content, lock_replacements = re.subn(
        r"(?m)^Phase-A-Lock:\s*UNLOCKED\s*$",
        "Phase-A-Lock: LOCKED",
        content,
        count=1,
    )
    if lock_replacements != 1:
        raise PhaseAExecutorError(f"Expected one unlock line in {plan_path}, found {lock_replacements}")
    content = re.sub(
        r"not yet agent-reviewed or bridge-converged",
        "bridge-converged",
        content,
        count=1,
    )
    full_path.write_text(content, encoding="utf-8")


def run_phase_a(
    repo_root: Path,
    plan_name: str,
    *,
    max_bridge_rounds: int = 15,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute the Phase A planning loop.

    Returns a result dict with status and plan path.
    """
    try:
        ensure_not_agent_review_mode("phase_a_executor.run_phase_a")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "plan_name": plan_name,
            "plan_path": None,
            "bridge_rounds": 0,
            "agent_review_ran": False,
            "error": str(exc),
        }

    result: dict[str, Any] = {
        "status": "success",
        "plan_name": plan_name,
        "plan_path": None,
        "bridge_rounds": 0,
        "agent_review_ran": False,
    }

    def log(msg: str) -> None:
        if verbose:
            print(f"[phase-a] {msg}")

    config = load_executor_config(repo_root)

    # Load routing record for scope context
    try:
        routing_record = load_routing_record(repo_root)
        scope = extract_plan_scope(routing_record)
    except (PhaseAExecutorError, ExecutorCommonError):
        scope = {"request": "", "summary": "", "decision": "ROUTE_PHASE_A"}

    # Create or load plan draft
    plan_path = create_plan_draft(repo_root, plan_name, scope)
    rel_plan_path = str(plan_path.relative_to(repo_root))
    result["plan_path"] = rel_plan_path
    log(f"Plan draft: {rel_plan_path}")

    # Run SDK agent review on the plan — FAIL CLOSED on nonzero exit
    review_depth = resolve_review_depth(config, "phase_a")
    log(f"Running SDK agent review on plan (depth={review_depth})...")
    agent_result = run_sdk_agents(repo_root, [rel_plan_path], depth=review_depth)
    result["agent_review_ran"] = True
    result["agent_exit_code"] = agent_result["exit_code"]
    log(f"Agent review exit code: {agent_result['exit_code']}")

    if agent_result["exit_code"] != 0:
        result["status"] = "error"
        result["error"] = (
            f"SDK agent review failed (exit={agent_result['exit_code']}). "
            "Hard gate: agents must pass before bridge review. "
            f"stderr: {agent_result.get('stderr', '')[:500]}"
        )
        return result

    # Bridge convergence loop (design review, --no-diff)
    for round_num in range(1, max_bridge_rounds + 1):
        bridge_job_id = f"phase-a-r{round_num}-{uuid.uuid4().hex[:8]}"
        log(f"Bridge design review round {round_num}/{max_bridge_rounds} (job={bridge_job_id})...")
        result["bridge_rounds"] = round_num

        bridge_result = run_bridge_design_review(
            repo_root, rel_plan_path, round_num,
            job_id=bridge_job_id,
        )
        log(f"Bridge exit code: {bridge_result['exit_code']}")

        # Check rendered output for GO — bound to exact job_id
        rendered_path = repo_root / ".agent_bus" / "rendered" / f"{bridge_job_id}.md"
        if rendered_path.exists():
            render_content = rendered_path.read_text(encoding="utf-8")
            if "Decision: GO" in render_content:
                log("Bridge converged: GO")
                result["status"] = "converged"
                break
            elif "Decision: REQUEST_CHANGES" in render_content or "Decision: NO_GO" in render_content:
                log("Bridge: REQUEST_CHANGES — continuing loop")
                continue
            elif "Decision: QUESTION" in render_content:
                log("Bridge: QUESTION — fail-closed (unresolved question)")
                result["status"] = "error"
                result["error"] = "Bridge returned QUESTION decision — requires human resolution"
                result["rendered_path"] = str(rendered_path)
                return result
            else:
                # Unrecognized decision — fail closed, do not burn rounds
                log("Bridge: unrecognized decision — fail-closed")
                result["status"] = "error"
                result["error"] = "Bridge returned unrecognized decision — cannot proceed"
                result["rendered_path"] = str(rendered_path)
                return result
        else:
            # No rendered output — fail closed (bridge did not produce output)
            if bridge_result["exit_code"] != 0:
                log(f"Bridge failed (exit {bridge_result['exit_code']}) with no rendered output")
                result["status"] = "error"
                result["error"] = f"Bridge subprocess failed with exit code {bridge_result['exit_code']}"
                return result

        if round_num >= max_bridge_rounds:
            result["status"] = "max_rounds_reached"
            log(f"Max bridge rounds ({max_bridge_rounds}) reached")
            return result

    # If the bridge loop exhausted without converging (e.g. all rounds were
    # REQUEST_CHANGES which `continue` past the max-rounds guard), the status
    # is still the initial "success" — which is a false positive.  Fail closed.
    if result.get("status") != "converged":
        result["status"] = "max_rounds_reached"
        result["error"] = (
            f"Bridge did not converge after {max_bridge_rounds} rounds. "
            "Plan was never locked."
        )
        log(f"Max bridge rounds ({max_bridge_rounds}) reached without convergence")
        return result

    # Lock the plan
    lock_plan(repo_root, rel_plan_path)
    log(f"Phase-A-Lock: LOCKED in {rel_plan_path}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase A executor: create plan through bridge convergence",
    )
    parser.add_argument(
        "--plan-name",
        type=str,
        required=True,
        help="Name for the plan packet (e.g., 'executor_surfaces_plan')",
    )
    parser.add_argument(
        "--routing-record",
        type=str,
        help="Routing record JSON string (from dispatcher)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=15,
        help="Max bridge convergence rounds (default: 15)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        action="store_true",
    )
    args = parser.parse_args()

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("[error] Not in a git repository", file=sys.stderr)
        return 1

    result = run_phase_a(
        repo_root, args.plan_name,
        max_bridge_rounds=args.max_rounds,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[phase-a] Status: {result.get('status')}")
        if result.get("plan_path"):
            print(f"[phase-a] Plan: {result['plan_path']}")

    return 0 if result.get("status") in ("success", "converged") else 1


if __name__ == "__main__":
    sys.exit(main())
