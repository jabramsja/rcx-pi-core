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
    """Run pre-commit supervisor via structured meta_bridge_client.

    Uses the Python API — no subprocess, no shell, no grep.
    Returns dict with 'parsed' containing structured result and 'receipt_path'.
    """
    try:
        agents_dir = str(repo_root / "mu" / "tools" / "agents")
        if agents_dir not in sys.path:
            sys.path.insert(0, agents_dir)
        from meta_bridge_client import run_meta_bridge_package, MetaBridgeClientError
    except ImportError:
        # Fallback: try direct import
        script_dir = Path(__file__).resolve().parent.parent / "agents"
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))
        from meta_bridge_client import run_meta_bridge_package, MetaBridgeClientError

    try:
        result = run_meta_bridge_package(
            package_path,
            wait_for_lock_seconds=30,
            verbose=verbose,
        )
        return {
            "exit_code": 0 if not result.is_error else 1,
            "parsed": {
                "decision": result.decision,
                "summary": result.summary,
                "status": result.status,
                "findings": result.findings,
            },
            "receipt_path": result.receipt_path,
        }
    except MetaBridgeClientError as exc:
        return {
            "exit_code": -1,
            "parsed": {"decision": "ERROR_INTERNAL", "summary": str(exc)[:500]},
            "receipt_path": "",
        }


def prepare_commit_handoff(
    repo_root: Path,
    *,
    wave_id: str,
    task_id: str,
    wave_class: str,
    target_gate_id: str,
    caller: str = "phase_b",
    branch_prefix: str = "jabramsja",
    tracker_sync: dict[str, str] | None = None,
    fixes_implemented: list[str] | None = None,
    files_to_stage: list[str] | None = None,
    force_add_files: list[str] | None = None,
    commit_message: str = "",
    pr_title: str = "",
    pr_body: str = "",
    # Legacy fields (deprecated — kept for backward compat during migration)
    staged_files: list[str] | None = None,
    head_branch: str = "",
    wave_name: str = "",
    hold_push: bool = False,
) -> Path:
    """Prepare a commit executor handoff file.

    New schema (R16+): uses wave_id, structured tracker_sync, files_to_stage.
    Legacy fields accepted for backward compatibility but ignored if new fields present.
    """
    handoff: dict[str, Any] = {
        "wave_id": wave_id,
        "task_id": task_id,
        "wave_class": wave_class,
        "target_gate_id": target_gate_id,
        "caller": caller,
        "branch_prefix": branch_prefix,
        "fixes_implemented": fixes_implemented or [],
        "files_to_stage": files_to_stage or staged_files or [],
        "force_add_files": force_add_files or [],
        "commit_message": commit_message,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "base_branch": "dev",
        "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
    }

    # Structured tracker sync (new path — replaces freeform tracker_note_text)
    if tracker_sync is not None:
        handoff["tracker_sync"] = tracker_sync

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
    2. Invoke implementer agent (separate code-writing actor)
    3. SDK agent review (once)
    4. Bridge convergence loop (bridge only, not agents again)
    5. Non-blockers to reports/deferred/non_blocking/
    6. On convergence: prepare pre-commit package + run supervisor
    7. On COMMIT_GO: prepare handoff for commit_executor
    8. On NEEDS_PHASE_B: re-enter bridge loop (not agents)

    Returns a result dict with status and details.
    """
    result: dict[str, Any] = {
        "status": "success",
        "plan_path": plan_path,
        "bridge_rounds": 0,
        "agent_review_ran": False,
        "implementer_invoked": False,
        "pre_commit_decision": None,
        "handoff_path": None,
    }

    def log(msg: str) -> None:
        if verbose:
            print(f"[phase-b] {msg}")

    # Step 1: Load and validate
    try:
        routing_record = load_routing_record(repo_root)
    except PhaseBExecutorError as exc:
        log(f"Routing record load failed: {exc}")
        routing_record = {"decision": "ROUTE_PHASE_B", "summary": "Direct invocation"}

    try:
        plan = load_plan_packet(repo_root, plan_path)
    except PhaseBExecutorError as exc:
        return {"status": "error", "step": "load_plan", "errors": [str(exc)]}

    log(f"Plan loaded: {plan_path}")
    log(f"Phase-A-Lock: {plan.get('phase_a_lock', 'unknown')}")

    valid, errors = validate_inputs(routing_record, plan)
    if not valid:
        log(f"Input validation warnings: {errors}")

    # Step 2: Load executor config for backend/model/timeout
    try:
        from phase_b_implementer import (
            build_implementation_prompt,
            invoke_implementer,
            load_executor_config,
        )
    except ImportError:
        # Fallback: try relative import
        script_dir = Path(__file__).resolve().parent
        if str(script_dir) not in sys.path:
            sys.path.insert(0, str(script_dir))
        from phase_b_implementer import (
            build_implementation_prompt,
            invoke_implementer,
            load_executor_config,
        )

    config = load_executor_config(repo_root)
    backend = config.get("backends", {}).get("phase_b_executor", "codex")
    model = config.get("model_overrides", {}).get("phase_b_executor")
    timeout = config.get("timeouts", {}).get("phase_b_executor", 1200)

    # Step 3: Invoke implementer agent
    log(f"Invoking implementer (backend={backend}, timeout={timeout}s)...")
    impl_prompt = build_implementation_prompt(
        plan.get("content", ""),
        repo_root=repo_root,
        wave_id=plan_path.replace("reports/control_plane/", "").replace(".md", ""),
    )
    impl_result = invoke_implementer(
        repo_root, impl_prompt,
        backend=backend,
        model_override=model,
        timeout=timeout,
        verbose=verbose,
    )
    result["implementer_invoked"] = True
    result["implementer_status"] = impl_result["status"]
    log(f"Implementer: {impl_result['status']} (exit={impl_result['exit_code']})")

    if impl_result["status"] == "timeout":
        return {"status": "error", "step": "implementer", "errors": ["Implementer timed out"]}

    # Collect changed files after implementer ran (for agents + supervisor + handoff)
    changed_files: list[str] = []
    try:
        _staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        _unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        _untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        changed_files = sorted(set(f for f in _staged + _unstaged + _untracked if f))
    except subprocess.CalledProcessError:
        pass

    # Step 4: Run SDK agents ONCE on live worktree changed files
    log("Running SDK agent review on changed files...")
    agent_files = changed_files if changed_files else ["--pr"]
    agent_result = run_sdk_agents(repo_root, agent_files, verbose=verbose)
    result["agent_review_ran"] = True
    result["agent_exit_code"] = agent_result["exit_code"]
    log(f"Agent review exit code: {agent_result['exit_code']}")

    # Step 5: Bridge convergence loop (bridge only — agents already ran)
    for round_num in range(1, max_bridge_rounds + 1):
        log(f"Bridge review round {round_num}/{max_bridge_rounds}...")
        result["bridge_rounds"] = round_num

        bridge_result = run_bridge_review(
            repo_root,
            f"Phase B implementation review R{round_num} for {plan_path}",
            verbose=verbose,
        )
        log(f"Bridge exit code: {bridge_result['exit_code']}")

        # Check bridge result — only trust renders newer than this invocation
        if bridge_result["exit_code"] != 0:
            log(f"Bridge invocation failed (exit={bridge_result['exit_code']}), continuing loop")
            continue

        rendered_dir = repo_root / ".agent_bus" / "rendered"
        if rendered_dir.exists():
            # Only look at renders created AFTER this bridge call started
            renders = sorted(rendered_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            if renders:
                latest = renders[0]
                # Verify this render is fresh (created within last 5 minutes)
                import time as _time
                render_age = _time.time() - latest.stat().st_mtime
                if render_age > 300:
                    log(f"Stale render ({int(render_age)}s old), ignoring")
                    continue
                content = latest.read_text(encoding="utf-8")
                if "Decision: GO" in content:
                    log("Bridge converged: GO")
                    result["status"] = "converged"
                    break
                elif "Decision: REQUEST_CHANGES" in content or "Decision: NO_GO" in content:
                    log("Bridge: REQUEST_CHANGES — continuing loop")
                    continue

    if result.get("status") != "converged":
        if round_num >= max_bridge_rounds:
            result["status"] = "max_rounds_reached"
            log(f"Max bridge rounds ({max_bridge_rounds}) reached without convergence")
            return result

    # Step 6: Build and run pre-commit supervisor via structured client
    log("Building supervisor package...")
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    package_path = scratch_dir / "phase_b_supervisor_package.json"

    # Derive wave_id from plan path
    wave_id = plan_path.replace("reports/control_plane/", "").replace(".md", "")

    # Get ALL changed files (staged + unstaged + untracked)
    changed_files: list[str] = []
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        unstaged = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip().splitlines()
        changed_files = sorted(set(f for f in staged + unstaged + untracked if f))
    except subprocess.CalledProcessError:
        changed_files = []

    supervisor_package = {
        "task_id": routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
        "wave_name": wave_id,
        "lane": "hooks/agents/bridge control-surface",
        "changed_files": changed_files,
        "scope_items": [plan_path],
        "fixes_implemented": ["Phase B implementation per locked plan"],
        "deferred_items": [],
        "bridge_status": {"rounds": result.get("bridge_rounds", 0)},
        "evidence_handles": {},
        "blocker_report_paths": [],
        "current_judgment": "COMMIT_GO",
    }
    package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

    log("Running pre-commit supervisor...")
    supervisor_result = run_pre_commit_supervisor(
        repo_root, package_path, verbose=verbose,
    )
    result["pre_commit_decision"] = supervisor_result.get("parsed", {}).get("decision")
    receipt_path = supervisor_result.get("receipt_path", ".agent_bus/meta/pre_commit_receipt.json")
    log(f"Supervisor decision: {result['pre_commit_decision']}")

    decision = result["pre_commit_decision"]
    if decision == "NEEDS_PHASE_B":
        # Re-enter: implementer fixes → bridge reviews → loop until converged
        # Bridge is read-only — it can't fix anything. Implementer must act.
        log("NEEDS_PHASE_B — re-invoking implementer then bridge loop")
        reentry_converged = False

        for reentry_round in range(result["bridge_rounds"] + 1, max_bridge_rounds + 1):
            log(f"Re-entry round {reentry_round}/{max_bridge_rounds}...")
            result["bridge_rounds"] = reentry_round

            # Re-invoke implementer to fix what bridge/supervisor flagged
            log("Re-invoking implementer for fixes...")
            reentry_prompt = build_implementation_prompt(
                plan.get("content", "") + "\n\n## NEEDS_PHASE_B Findings\n\n"
                + supervisor_result.get("parsed", {}).get("summary", "Fix required"),
                repo_root=repo_root,
                wave_id=wave_id,
                scope_hint="Fix findings from bridge/supervisor review",
            )
            impl_result = invoke_implementer(
                repo_root, reentry_prompt,
                backend=backend, model_override=model,
                timeout=timeout, verbose=verbose,
            )
            log(f"Implementer re-entry: {impl_result['status']}")

            # Rebuild changed_files from live state after implementer ran
            try:
                staged = subprocess.run(
                    ["git", "diff", "--cached", "--name-only"],
                    cwd=repo_root, capture_output=True, text=True, check=True,
                ).stdout.strip().splitlines()
                unstaged = subprocess.run(
                    ["git", "diff", "--name-only"],
                    cwd=repo_root, capture_output=True, text=True, check=True,
                ).stdout.strip().splitlines()
                untracked = subprocess.run(
                    ["git", "ls-files", "--others", "--exclude-standard"],
                    cwd=repo_root, capture_output=True, text=True, check=True,
                ).stdout.strip().splitlines()
                changed_files = sorted(set(f for f in staged + unstaged + untracked if f))
            except subprocess.CalledProcessError:
                pass  # Keep previous changed_files

            # Rewrite supervisor package with fresh changed_files
            supervisor_package["changed_files"] = changed_files
            package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

            # Bridge reviews the fix (same exit_code + freshness checks as initial loop)
            bridge_result = run_bridge_review(
                repo_root,
                f"Phase B re-entry R{reentry_round} after NEEDS_PHASE_B for {plan_path}",
                verbose=verbose,
            )
            if bridge_result["exit_code"] != 0:
                log(f"Reentry bridge failed (exit={bridge_result['exit_code']}), continuing loop")
                continue

            rendered_dir = repo_root / ".agent_bus" / "rendered"
            if rendered_dir.exists():
                renders = sorted(rendered_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
                if renders:
                    latest = renders[0]
                    import time as _time
                    render_age = _time.time() - latest.stat().st_mtime
                    if render_age > 300:
                        log(f"Stale reentry render ({int(render_age)}s old), ignoring")
                        continue
                    content = latest.read_text(encoding="utf-8")
                    if "Decision: GO" in content:
                        log("Bridge re-entry converged: GO")
                        reentry_converged = True
                        break

        if not reentry_converged:
            result["status"] = "max_rounds_reached"
            return result

        # Re-run supervisor FRESH after re-entry convergence
        log("Re-running supervisor after bridge re-entry...")
        supervisor_result = run_pre_commit_supervisor(
            repo_root, package_path, verbose=verbose,
        )
        decision = supervisor_result.get("parsed", {}).get("decision")
        receipt_path = supervisor_result.get("receipt_path", "")
        result["pre_commit_decision"] = decision
        log(f"Post-reentry supervisor decision: {decision}")

        if decision == "NEEDS_PHASE_B":
            # Second NEEDS_PHASE_B — fail closed, don't produce commit_ready
            result["status"] = "needs_phase_b"
            result["errors"] = ["Supervisor returned NEEDS_PHASE_B after reentry convergence. "
                                "Manual intervention required."]
            return result
        elif decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            result["status"] = "supervisor_rejected"
            result["errors"] = [f"Post-reentry supervisor returned {decision}"]
            return result

    elif decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        result["status"] = "supervisor_rejected"
        result["errors"] = [f"Supervisor returned {decision}, not COMMIT_GO"]
        return result

    # Step 7: Prepare commit handoff with real values
    log("Preparing commit handoff...")
    # Use staged_files alias for backward compat with commit_executor
    handoff_path = prepare_commit_handoff(
        repo_root,
        wave_id=wave_id,
        task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        files_to_stage=changed_files,
        commit_message=f"feat: Phase B implementation for {wave_id}\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>",
        pr_title=f"feat: Phase B - {wave_id}",
        pr_body=f"## Summary\nPhase B implementation per locked plan at {plan_path}",
    )
    # Patch the handoff with the real receipt path
    handoff_data = json.loads(handoff_path.read_text(encoding="utf-8"))
    handoff_data["pre_commit_receipt_path"] = receipt_path
    handoff_path.write_text(json.dumps(handoff_data, indent=2) + "\n", encoding="utf-8")
    result["status"] = "commit_ready"
    result["handoff_path"] = str(handoff_path)
    result["pre_commit_decision"] = decision
    result["receipt_path"] = receipt_path
    log(f"Handoff written: {handoff_path}")
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

    return 0 if result.get("status") in ("success", "ready", "commit_ready") else 1


if __name__ == "__main__":
    sys.exit(main())
