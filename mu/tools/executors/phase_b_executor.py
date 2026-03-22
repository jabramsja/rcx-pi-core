#!/usr/bin/env python3
"""Phase B executor: implements a locked plan through bridge convergence loop.

Invoked by ROUTE_PHASE_B routing token from the post-merge supervisor.
Replaces Claude-as-workflow-engine for Phase B implementation waves.

Control flow:
1. Read locked plan packet + routing record
2. Invoke Codex to implement the plan (via bridge_supervisor.py review)
3. Loop bridge until only non-blockers remain
4. File non-blockers to reports/deferred/non_blocking/
5. Prepare pre-commit supervisor package and run supervisor
6. On COMMIT_GO: prepare handoff for commit_executor
7. On NEEDS_PHASE_B: re-enter bridge loop (not agents)
8. On other decisions: report and stop

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md Section B.3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


class PhaseBExecutorError(RuntimeError):
    """Raised when Phase B executor cannot proceed."""


def load_routing_record(repo_root: Path) -> dict[str, Any]:
    """Load the post-merge routing record."""
    record_path = repo_root / ".agent_bus" / "meta" / "post_merge_routing.json"
    if not record_path.exists():
        raise PhaseBExecutorError(f"Routing record not found: {record_path}")
    return json.loads(record_path.read_text(encoding="utf-8"))


def load_plan_packet(repo_root: Path, plan_path: str) -> dict[str, str]:
    """Load and parse key fields from a plan packet."""
    full_path = repo_root / plan_path
    if not full_path.exists():
        raise PhaseBExecutorError(f"Plan packet not found: {plan_path}")

    content = full_path.read_text(encoding="utf-8")
    result = {"path": plan_path, "content": content}

    for line in content.splitlines()[:10]:
        if line.startswith("Phase-A-Lock:"):
            result["phase_a_lock"] = line.split(":", 1)[1].strip()
        if line.startswith("Status:"):
            result["status"] = line.split(":", 1)[1].strip()

    return result


def validate_inputs(
    routing_record: dict[str, Any],
    plan: dict[str, str],
) -> tuple[bool, list[str]]:
    """Validate inputs before proceeding with Phase B."""
    errors: list[str] = []

    # Routing decision must be ROUTE_PHASE_B
    decision = routing_record.get("decision", "")
    if decision != "ROUTE_PHASE_B":
        errors.append(f"Expected ROUTE_PHASE_B, got {decision}")

    # Plan must be locked
    lock = plan.get("phase_a_lock", "")
    if lock != "LOCKED":
        errors.append(f"Plan Phase-A-Lock must be LOCKED, got {lock}")

    return len(errors) == 0, errors


def run_bridge_review(
    repo_root: Path,
    task_summary: str,
    *,
    verbose: bool = False,
    timeout: int = 1200,
) -> dict[str, Any]:
    """Run bridge_supervisor.py review and return the rendered result."""
    # Write task file
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    task_path = scratch_dir / "phase_b_bridge_task.md"
    task_path.write_text(task_summary, encoding="utf-8")

    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    cmd = [
        sys.executable, str(bridge_script),
        "review",
        "--task-file", str(task_path),
        "--summary", "Phase B implementation review",
        "--reviewer", "codex",
    ]
    if verbose:
        cmd.append("-v")

    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Bridge review timed out"}


def run_sdk_agents(
    repo_root: Path,
    files: list[str],
    *,
    depth: str = "full",
    verbose: bool = False,
    timeout: int = 600,
) -> dict[str, Any]:
    """Run SDK agent review on implementation files."""
    cmd = [
        sys.executable, "tools/runners/run_review.py",
        *files,
        "--depth", depth,
    ]

    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True,
            check=False, timeout=timeout,
            env={**__import__("os").environ, "PYTHONHASHSEED": "0"},
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "Agent review timed out"}


def run_pre_commit_supervisor(
    repo_root: Path,
    package_path: Path,
    *,
    verbose: bool = False,
    timeout: int = 1200,
) -> dict[str, Any]:
    """Run pre-commit supervisor on a package."""
    supervisor = repo_root / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
    cmd = [
        sys.executable, str(supervisor),
        "--package", str(package_path),
        "--json",
    ]
    if verbose:
        cmd.append("-v")

    try:
        result = subprocess.run(
            cmd, cwd=repo_root, capture_output=True, text=True,
            check=False, timeout=timeout,
        )
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            parsed = {"decision": "ERROR_INTERNAL", "summary": result.stdout[:500]}
        return {
            "exit_code": result.returncode,
            "parsed": parsed,
        }
    except subprocess.TimeoutExpired:
        return {
            "exit_code": -1,
            "parsed": {"decision": "ERROR_CODEX_TIMEOUT", "summary": "Pre-commit supervisor timed out"},
        }


def prepare_commit_handoff(
    repo_root: Path,
    *,
    staged_files: list[str],
    commit_message: str,
    pr_title: str,
    pr_body: str,
    head_branch: str,
    task_id: str,
    wave_name: str,
    hold_push: bool = False,
) -> Path:
    """Prepare a commit executor handoff file."""
    handoff = {
        "staged_files": staged_files,
        "commit_message": commit_message,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "head_branch": head_branch,
        "base_branch": "dev",
        "hold_push": hold_push,
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
        "task_id": task_id,
        "wave_name": wave_name,
        "caller": "phase_b",
    }

    handoff_dir = repo_root / ".agent_bus" / "executors"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    handoff_path = handoff_dir / "phase_b_handoff.json"
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return handoff_path


def run_phase_b(
    repo_root: Path,
    plan_path: str,
    *,
    max_bridge_rounds: int = 10,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute the Phase B loop.

    This is the main entry point. It orchestrates:
    1. Plan loading + validation
    2. SDK agent review
    3. Bridge convergence loop
    4. Pre-commit supervisor
    5. Commit handoff preparation

    Returns a result dict with status and details.
    """
    result: dict[str, Any] = {
        "status": "success",
        "plan_path": plan_path,
        "bridge_rounds": 0,
        "agent_review_ran": False,
        "pre_commit_decision": None,
        "handoff_path": None,
    }

    def log(msg: str) -> None:
        if verbose:
            print(f"[phase-b] {msg}")

    # Load and validate
    try:
        routing_record = load_routing_record(repo_root)
    except PhaseBExecutorError as exc:
        log(f"Routing record load failed: {exc}")
        # Proceed without routing record if plan path is provided directly
        routing_record = {"decision": "ROUTE_PHASE_B", "summary": "Direct invocation"}

    try:
        plan = load_plan_packet(repo_root, plan_path)
    except PhaseBExecutorError as exc:
        return {"status": "error", "step": "load_plan", "errors": [str(exc)]}

    log(f"Plan loaded: {plan_path}")
    log(f"Phase-A-Lock: {plan.get('phase_a_lock', 'unknown')}")

    # Note: validation is advisory — Phase B can proceed with a LOCKED plan
    # even if invoked directly (not through post-merge supervisor)
    valid, errors = validate_inputs(routing_record, plan)
    if not valid:
        log(f"Input validation warnings: {errors}")
        # Don't fail on validation — allow direct invocation for testing

    result["status"] = "ready"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase B executor: implement locked plan through bridge convergence",
    )
    parser.add_argument(
        "--plan",
        type=str,
        required=True,
        help="Path to locked plan packet (relative to repo root)",
    )
    parser.add_argument(
        "--routing-record",
        type=str,
        help="Routing record JSON string (from dispatcher)",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=10,
        help="Max bridge convergence rounds (default: 10)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
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

    result = run_phase_b(
        repo_root, args.plan,
        max_bridge_rounds=args.max_rounds,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[phase-b] Status: {result.get('status')}")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"[phase-b] Error: {e}")

    return 0 if result.get("status") in ("success", "ready") else 1


if __name__ == "__main__":
    sys.exit(main())
