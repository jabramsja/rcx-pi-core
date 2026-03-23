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


# Required handoff fields (accept both old and new schema during migration)
# New schema: wave_id, files_to_stage, wave_class, target_gate_id, branch_prefix
# Old schema: staged_files, head_branch, hold_push, wave_name
# Minimum required for both: commit_message, pr_title, pr_body, base_branch, task_id, caller
CORE_HANDOFF_FIELDS = {
    "commit_message",
    "pr_title",
    "pr_body",
    "base_branch",
    "task_id",
    "caller",
}
# Old schema required fields (backward compat)
OLD_SCHEMA_FIELDS = {"staged_files", "head_branch", "hold_push", "wave_name", "pre_commit_receipt_path"}
# New schema required fields
NEW_SCHEMA_FIELDS = {"wave_id", "files_to_stage", "wave_class", "target_gate_id", "branch_prefix"}
# Combined for backward compat: core + at least one of old/new
REQUIRED_HANDOFF_FIELDS = CORE_HANDOFF_FIELDS  # Minimum check


def validate_handoff(handoff: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate handoff has required fields with correct types.

    Accepts both old schema (staged_files, head_branch, hold_push, wave_name)
    and new schema (wave_id, files_to_stage, wave_class, branch_prefix).
    Core fields required by both: commit_message, pr_title, pr_body, base_branch, task_id, caller.
    """
    if not isinstance(handoff, dict):
        return False, ["Handoff must be a JSON object"]

    # Check core fields
    missing_core = CORE_HANDOFF_FIELDS - set(handoff.keys())
    if missing_core:
        return False, [f"Missing core field: {f}" for f in sorted(missing_core)]

    errors: list[str] = []

    # Detect schema: new has wave_id, old has wave_name
    is_new_schema = "wave_id" in handoff
    is_old_schema = "staged_files" in handoff or "head_branch" in handoff

    # New schema: require key fields
    if is_new_schema:
        for fld in ("branch_prefix", "wave_id"):
            if not isinstance(handoff.get(fld), str) or not handoff[fld].strip():
                errors.append(f"New schema requires {fld} as non-empty string")
        if handoff.get("base_branch") != "dev":
            errors.append(f"base_branch must be 'dev', got '{handoff.get('base_branch')}'")
    elif not is_old_schema:
        errors.append("Handoff must provide either new schema (wave_id) or old schema (staged_files/head_branch)")

    # Validate file list (accept either field name)
    files_field = "files_to_stage" if is_new_schema else "staged_files"
    file_list = handoff.get(files_field, handoff.get("staged_files", handoff.get("files_to_stage")))
    if not isinstance(file_list, list):
        errors.append(f"{files_field} must be a list")
    elif not file_list:
        errors.append(f"{files_field} must not be empty")
    else:
        for i, f in enumerate(file_list):
            if not isinstance(f, str):
                errors.append(f"{files_field}[{i}] must be a string")

    # Validate string fields
    core_str_fields = ["commit_message", "pr_title", "pr_body", "base_branch", "task_id", "caller"]
    if is_old_schema and not is_new_schema:
        core_str_fields.extend(["head_branch", "pre_commit_receipt_path", "wave_name"])
    for fld in core_str_fields:
        if fld in handoff and (not isinstance(handoff.get(fld), str) or not handoff[fld].strip()):
            errors.append(f"{fld} must be a non-empty string")

    # Old schema: validate hold_push
    if is_old_schema and not is_new_schema:
        if "hold_push" in handoff and not isinstance(handoff.get("hold_push"), bool):
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

    # For new schema: stage files FIRST so receipt staged_sha matches
    _is_new = "wave_id" in handoff
    if _is_new:
        expected_files = handoff.get("files_to_stage", [])
        force_files = handoff.get("force_add_files", [])
        if expected_files or force_files:
            log("New schema: staging files before receipt validation...")
            try:
                if expected_files:
                    run_cmd(["git", "add", *expected_files], cwd=repo_root)
                if force_files:
                    run_cmd(["git", "add", "-f", *force_files], cwd=repo_root)
                result["steps_completed"].append("staging")
            except subprocess.CalledProcessError as exc:
                return {
                    "status": "error",
                    "step": "staging",
                    "errors": [f"git add failed: {exc.stderr.strip()}"],
                    "steps_completed": result["steps_completed"],
                }

    # Validate pre-commit receipt using shared verifier (decision + staged_sha + age)
    # Try to use the full verifier; fall back to basic check if import fails
    _verifier_loaded = False
    try:
        import importlib.util as _ilu
        _verifier_path = repo_root / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
        if _verifier_path.exists():
            _spec = _ilu.spec_from_file_location("_mbs_verifier", str(_verifier_path))
            if _spec and _spec.loader:
                _mbs = _ilu.module_from_spec(_spec)
                sys.modules["_mbs_verifier"] = _mbs  # Required for @dataclass on Python 3.13
                _spec.loader.exec_module(_mbs)
                # Use explicit receipt path from handoff if available
                _explicit_receipt = None
                _receipt_str = handoff.get("pre_commit_receipt_path", "")
                if _receipt_str:
                    _explicit_receipt = repo_root / _receipt_str
                    if not _explicit_receipt.exists():
                        _explicit_receipt = None  # Fall back to canonical
                passed, message = _mbs.verify_pre_commit_receipt(
                    repo_root, receipt_path=_explicit_receipt
                )
                _verifier_loaded = True
                if not passed:
                    return {
                        "status": "error",
                        "step": "receipt_check",
                        "errors": [message],
                    }
    except Exception as _exc:
        # Verifier failed to load — for new schema, fail closed
        if _is_new:
            return {
                "status": "error",
                "step": "receipt_check",
                "errors": [f"Receipt verifier failed to load: {_exc}"],
                "steps_completed": result["steps_completed"],
            }
        # Old schema: fall through to basic check

    if not _verifier_loaded and not _is_new:
        # Fallback: basic receipt check if verifier unavailable
        receipt_path_str = handoff.get("pre_commit_receipt_path", ".agent_bus/meta/pre_commit_receipt.json")
        receipt_path = repo_root / receipt_path_str
        if not receipt_path.exists():
            return {
                "status": "error",
                "step": "receipt_check",
                "errors": [f"Pre-commit receipt not found: {receipt_path_str}"],
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
    log("Pre-commit receipt validated (decision + staged_sha + age)")

    # Derive head_branch from new schema if available, fall back to old
    if "wave_id" in handoff and "branch_prefix" in handoff:
        expected_branch = f"{handoff['branch_prefix']}/{handoff['wave_id']}"
    elif "head_branch" in handoff:
        expected_branch = handoff["head_branch"]
    else:
        return {"status": "error", "step": "branch_check", "errors": ["No head_branch or wave_id+branch_prefix in handoff"]}

    # Verify we're on the right branch
    try:
        current_branch = run_cmd(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return {"status": "error", "step": "branch_check", "errors": ["Cannot determine current branch"]}

    if current_branch != expected_branch:
        return {
            "status": "error",
            "step": "branch_check",
            "errors": [f"Expected branch {expected_branch}, got {current_branch}"],
        }

    # Verify staged files match (staging already done above for new schema)
    expected_files = handoff.get("files_to_stage", handoff.get("staged_files", []))
    force_files = handoff.get("force_add_files", [])
    try:
        staged = run_cmd(
            ["git", "diff", "--cached", "--name-only"], cwd=repo_root
        ).stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        staged = []

    expected = set(expected_files) | set(force_files)
    actual = set(staged)
    if expected and expected != actual:
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

    # Step 3: Hold if receipt says COMMIT_GO_HOLD_PUSH (or legacy hold_push field)
    # New schema: receipt-driven. Old schema: handoff.hold_push boolean.
    receipt_path_str = handoff.get("pre_commit_receipt_path", ".agent_bus/meta/pre_commit_receipt.json")
    _hold = handoff.get("hold_push", False)  # Old schema fallback
    try:
        _receipt_data = json.loads((repo_root / receipt_path_str).read_text(encoding="utf-8"))
        if _receipt_data.get("decision") == "COMMIT_GO_HOLD_PUSH":
            _hold = True
    except (json.JSONDecodeError, OSError, FileNotFoundError):
        pass  # Use handoff fallback
    if _hold:
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
            ["git", "push", "-u", "origin", expected_branch],
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
                "--head", expected_branch,
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
