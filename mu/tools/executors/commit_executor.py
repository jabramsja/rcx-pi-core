#!/usr/bin/env python3
"""Commit executor: mechanical commit → push → PR → CI → merge → sweep pipeline.

No LLM needed. Pure git + gh CLI orchestration.
Invoked by COMMIT_GO or COMMIT_GO_HOLD_PUSH from pre-commit supervisor,
or by UPDATE_TRACKER_ONLY from post-merge dispatcher.

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md Section B.4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent


class CommitExecutorError(RuntimeError):
    """Raised when commit executor cannot proceed."""


# Required handoff fields
REQUIRED_HANDOFF_FIELDS = {
    "staged_files",
    "commit_message",
    "pr_title",
    "pr_body",
    "head_branch",
    "base_branch",
    "hold_push",
    "pre_commit_receipt_path",
    "task_id",
    "wave_name",
    "caller",
}


def validate_handoff(handoff: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate handoff has required fields with correct types."""
    if not isinstance(handoff, dict):
        return False, ["Handoff must be a JSON object"]

    missing = REQUIRED_HANDOFF_FIELDS - set(handoff.keys())
    if missing:
        return False, [f"Missing field: {f}" for f in sorted(missing)]

    errors: list[str] = []

    if not isinstance(handoff.get("staged_files"), list):
        errors.append("staged_files must be a list")
    elif not handoff["staged_files"]:
        errors.append("staged_files must not be empty")
    else:
        for i, f in enumerate(handoff["staged_files"]):
            if not isinstance(f, str):
                errors.append(f"staged_files[{i}] must be a string")

    for fld in ("commit_message", "pr_title", "pr_body", "head_branch", "base_branch", "pre_commit_receipt_path", "task_id", "wave_name", "caller"):
        if not isinstance(handoff.get(fld), str) or not handoff[fld].strip():
            errors.append(f"{fld} must be a non-empty string")

    if not isinstance(handoff.get("hold_push"), bool):
        errors.append("hold_push must be a boolean")

    valid_callers = {"phase_b", "phase_a", "update_tracker_only"}
    caller = handoff.get("caller", "")
    if caller and caller not in valid_callers:
        errors.append(f"caller must be one of {sorted(valid_callers)}, got: {caller}")

    return len(errors) == 0, errors


def run_cmd(args: list[str], *, cwd: Path, check: bool = True, timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a command and return result."""
    return subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, check=check, timeout=timeout,
    )


def run_commit_pipeline(
    handoff: dict[str, Any],
    *,
    repo_root: Path,
    verbose: bool = False,
) -> dict[str, Any]:
    """Execute the commit pipeline.

    Returns a result dict with status and details.
    """
    result: dict[str, Any] = {
        "status": "success",
        "steps_completed": [],
        "pr_number": None,
        "merge_sha": None,
    }

    def log(msg: str) -> None:
        if verbose:
            print(f"[commit-executor] {msg}")

    # Step 1: Validate handoff
    valid, errors = validate_handoff(handoff)
    if not valid:
        return {"status": "error", "step": "validate", "errors": errors}

    # Validate pre-commit receipt exists
    receipt_path = repo_root / handoff.get("pre_commit_receipt_path", "")
    if not receipt_path.exists():
        return {
            "status": "error",
            "step": "receipt_check",
            "errors": [f"Pre-commit receipt not found: {handoff.get('pre_commit_receipt_path')}"],
        }
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("decision") not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            return {
                "status": "error",
                "step": "receipt_check",
                "errors": [f"Receipt decision '{receipt.get('decision')}' does not authorize commit"],
            }
    except (json.JSONDecodeError, OSError) as exc:
        return {"status": "error", "step": "receipt_check", "errors": [f"Receipt unreadable: {exc}"]}

    result["steps_completed"].append("receipt_check")
    log("Pre-commit receipt validated")

    # Verify we're on the right branch
    try:
        current_branch = run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return {"status": "error", "step": "branch_check", "errors": ["Cannot determine current branch"]}

    if current_branch != handoff["head_branch"]:
        return {
            "status": "error",
            "step": "branch_check",
            "errors": [f"Expected branch {handoff['head_branch']}, got {current_branch}"],
        }

    # Verify staged files match
    try:
        staged = run_cmd(
            ["git", "diff", "--cached", "--name-only"], cwd=repo_root
        ).stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        staged = []

    expected = set(handoff["staged_files"])
    actual = set(staged)
    if expected != actual:
        missing = expected - actual
        extra = actual - expected
        errs = []
        if missing:
            errs.append(f"Expected staged but not found: {sorted(missing)}")
        if extra:
            errs.append(f"Staged but not in handoff: {sorted(extra)}")
        return {"status": "error", "step": "staged_check", "errors": errs}

    result["steps_completed"].append("validate")
    log("Handoff validated")

    # Step 2: Commit
    log("Committing...")
    try:
        commit_result = run_cmd(
            ["git", "commit", "-m", handoff["commit_message"]],
            cwd=repo_root, timeout=60,
        )
        result["steps_completed"].append("commit")
        log(f"Committed: {commit_result.stdout.strip()}")
    except subprocess.CalledProcessError as exc:
        return {
            "status": "error",
            "step": "commit",
            "errors": [f"git commit failed: {exc.stderr.strip()}"],
            "steps_completed": result["steps_completed"],
        }

    # Step 3: Hold if COMMIT_GO_HOLD_PUSH
    if handoff.get("hold_push", False):
        try:
            sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        except subprocess.CalledProcessError:
            sha = "unknown"
        result["status"] = "held"
        result["steps_completed"].append("hold")
        result["commit_sha"] = sha
        result["message"] = f"Committed locally (SHA: {sha[:8]}). Hold before push per COMMIT_GO_HOLD_PUSH."
        log(result["message"])
        return result

    # Step 4: Push
    log("Pushing...")
    try:
        run_cmd(
            ["git", "push", "-u", "origin", handoff["head_branch"]],
            cwd=repo_root, timeout=300,
        )
        result["steps_completed"].append("push")
        log("Pushed")
    except subprocess.CalledProcessError as exc:
        return {
            "status": "error",
            "step": "push",
            "errors": [f"git push failed: {exc.stderr.strip()}"],
            "steps_completed": result["steps_completed"],
        }

    # Step 5: Create PR (non-interactive)
    log("Creating PR...")
    try:
        pr_result = run_cmd(
            [
                "gh", "pr", "create",
                "--base", handoff["base_branch"],
                "--head", handoff["head_branch"],
                "--title", handoff["pr_title"],
                "--body", handoff["pr_body"],
            ],
            cwd=repo_root, timeout=30,
        )
        pr_url = pr_result.stdout.strip()
        # Extract PR number from URL
        pr_number = pr_url.rstrip("/").split("/")[-1]
        result["pr_number"] = pr_number
        result["pr_url"] = pr_url
        result["steps_completed"].append("pr_create")
        log(f"PR created: {pr_url}")
    except subprocess.CalledProcessError as exc:
        return {
            "status": "error",
            "step": "pr_create",
            "errors": [f"gh pr create failed: {exc.stderr.strip()}"],
            "steps_completed": result["steps_completed"],
        }

    # Step 6: Wait for CI (watch mode, blocks until complete)
    log(f"Waiting for CI on PR #{pr_number}...")
    try:
        run_cmd(
            ["gh", "pr", "checks", pr_number, "--watch"],
            cwd=repo_root, timeout=600,
        )
        result["steps_completed"].append("ci_wait")
        log("CI passed")
    except subprocess.CalledProcessError as exc:
        return {
            "status": "error",
            "step": "ci_wait",
            "errors": [f"CI checks failed: {exc.stderr.strip()}"],
            "steps_completed": result["steps_completed"],
            "pr_number": pr_number,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "step": "ci_wait",
            "errors": ["CI wait timed out after 600s"],
            "steps_completed": result["steps_completed"],
            "pr_number": pr_number,
        }

    # Step 7+8: Merge via merge_pr.sh --sweep (handles bot threads mechanically)
    log(f"Merging PR #{pr_number} with sweep...")
    merge_script = repo_root / "mu" / "tools" / "hooks" / "merge_pr.sh"
    if not merge_script.exists():
        return {
            "status": "error",
            "step": "merge",
            "errors": [f"merge_pr.sh not found at {merge_script}"],
            "steps_completed": result["steps_completed"],
            "pr_number": pr_number,
        }
    try:
        run_cmd(
            ["bash", str(merge_script), pr_number, "--sweep"],
            cwd=repo_root, timeout=120,
        )
        result["steps_completed"].append("merge")
        log(f"PR #{pr_number} merged")
    except subprocess.CalledProcessError as exc:
        return {
            "status": "error",
            "step": "merge",
            "errors": [f"merge_pr.sh failed: {exc.stderr.strip()}"],
            "steps_completed": result["steps_completed"],
            "pr_number": pr_number,
        }

    # Step 9: Post-merge verify — checkout dev and pull to get merged state
    try:
        # merge_pr.sh already does checkout + pull, but verify we're on dev
        current = run_cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root).stdout.strip()
        if current != handoff["base_branch"]:
            run_cmd(["git", "checkout", handoff["base_branch"]], cwd=repo_root)
            run_cmd(["git", "pull"], cwd=repo_root)

        head_sha = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        status_output = run_cmd(["git", "status", "--short"], cwd=repo_root).stdout.strip()
        result["merge_sha"] = head_sha
        result["steps_completed"].append("verify")
        log(f"Post-merge verify: HEAD={head_sha[:8]}, on {handoff['base_branch']}, clean={not status_output}")
    except subprocess.CalledProcessError as exc:
        result["steps_completed"].append("verify_failed")
        log(f"Post-merge verify failed: {exc}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Commit executor: mechanical commit pipeline",
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        help="Path to handoff JSON file",
    )
    parser.add_argument(
        "--routing-record",
        type=str,
        help="Routing record JSON string (from dispatcher)",
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

    # Load handoff
    if args.handoff:
        try:
            handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[error] Cannot load handoff: {exc}", file=sys.stderr)
            return 1
    elif args.routing_record:
        # When invoked by dispatcher, routing_record is the post-merge record.
        # Commit executor needs a proper handoff, not a routing record.
        # The dispatcher should have prepared the handoff.
        print("[error] commit_executor requires --handoff, not --routing-record. "
              "The dispatcher or caller must prepare the handoff.", file=sys.stderr)
        return 1
    else:
        print("[error] Provide --handoff <path>", file=sys.stderr)
        return 1

    result = run_commit_pipeline(handoff, repo_root=repo_root, verbose=args.verbose)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = result.get("status", "unknown")
        steps = result.get("steps_completed", [])
        print(f"[commit-executor] Status: {status}")
        print(f"[commit-executor] Steps: {', '.join(steps)}")
        if result.get("pr_number"):
            print(f"[commit-executor] PR: #{result['pr_number']}")
        if result.get("merge_sha"):
            print(f"[commit-executor] Merge SHA: {result['merge_sha'][:8]}")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"[commit-executor] Error: {e}")
        if result.get("message"):
            print(f"[commit-executor] {result['message']}")

    return 0 if result.get("status") in ("success", "held") else 1


if __name__ == "__main__":
    sys.exit(main())
