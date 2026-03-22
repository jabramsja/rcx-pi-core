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
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


class PhaseAExecutorError(RuntimeError):
    """Raised when Phase A executor cannot proceed."""


def load_routing_record(repo_root: Path) -> dict[str, Any]:
    """Load the post-merge routing record."""
    record_path = repo_root / ".agent_bus" / "meta" / "post_merge_routing.json"
    if not record_path.exists():
        raise PhaseAExecutorError(f"Routing record not found: {record_path}")
    return json.loads(record_path.read_text(encoding="utf-8"))


def extract_plan_scope(routing_record: dict[str, Any]) -> dict[str, str]:
    """Extract planning scope from routing record's request_for_claude."""
    return {
        "request": routing_record.get("request_for_claude", ""),
        "summary": routing_record.get("summary", ""),
        "decision": routing_record.get("decision", ""),
    }


def create_plan_draft(
    repo_root: Path,
    plan_name: str,
    scope: dict[str, str],
) -> Path:
    """Create an initial plan packet draft."""
    plan_dir = repo_root / "reports" / "control_plane"
    plan_dir.mkdir(parents=True, exist_ok=True)

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
    depth: str = "full",
    timeout: int = 600,
) -> dict[str, Any]:
    """Run SDK agent review."""
    cmd = [
        sys.executable, "tools/runners/run_review.py",
        *files, "--depth", depth,
    ]
    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True,
            check=False, timeout=timeout,
            env={**__import__("os").environ, "PYTHONHASHSEED": "0"},
        )
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Agent review timed out"}


def run_bridge_design_review(
    repo_root: Path,
    plan_path: str,
    round_num: int,
    *,
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
    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out"}


def lock_plan(repo_root: Path, plan_path: str) -> None:
    """Set Phase-A-Lock: LOCKED in a plan packet."""
    full_path = repo_root / plan_path
    content = full_path.read_text(encoding="utf-8")
    content = content.replace("Phase-A-Lock: UNLOCKED", "Phase-A-Lock: LOCKED")
    content = content.replace(
        "not yet agent-reviewed or bridge-converged",
        "bridge-converged"
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

    # Load routing record for scope context
    try:
        routing_record = load_routing_record(repo_root)
        scope = extract_plan_scope(routing_record)
    except PhaseAExecutorError:
        scope = {"request": "", "summary": "", "decision": "ROUTE_PHASE_A"}

    # Create or load plan draft
    plan_path = create_plan_draft(repo_root, plan_name, scope)
    rel_plan_path = str(plan_path.relative_to(repo_root))
    result["plan_path"] = rel_plan_path
    log(f"Plan draft: {rel_plan_path}")

    # Run SDK agent review on the plan
    log("Running SDK agent review on plan...")
    agent_result = run_sdk_agents(repo_root, [rel_plan_path])
    result["agent_review_ran"] = True
    result["agent_exit_code"] = agent_result["exit_code"]
    log(f"Agent review exit code: {agent_result['exit_code']}")

    # Bridge convergence loop (design review, --no-diff)
    for round_num in range(1, max_bridge_rounds + 1):
        log(f"Bridge design review round {round_num}/{max_bridge_rounds}...")
        result["bridge_rounds"] = round_num

        bridge_result = run_bridge_design_review(
            repo_root, rel_plan_path, round_num,
        )
        log(f"Bridge exit code: {bridge_result['exit_code']}")

        # Check rendered output for GO
        rendered_dir = repo_root / ".agent_bus" / "rendered"
        if rendered_dir.exists():
            renders = sorted(rendered_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            if renders:
                latest = renders[0].read_text(encoding="utf-8")
                if "Decision: GO" in latest:
                    log("Bridge converged: GO")
                    result["status"] = "converged"
                    break
                elif "Decision: REQUEST_CHANGES" in latest or "Decision: NO_GO" in latest:
                    log("Bridge: REQUEST_CHANGES — continuing loop")
                    continue

        if round_num >= max_bridge_rounds:
            result["status"] = "max_rounds_reached"
            log(f"Max bridge rounds ({max_bridge_rounds}) reached")
            return result

    # Lock the plan
    if result.get("status") == "converged":
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
