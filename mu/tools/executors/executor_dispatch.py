#!/usr/bin/env python3
"""Executor dispatcher: reads post-merge routing record and invokes the correct executor.

This is the entry point for automated workflow execution. The post-merge
supervisor emits a routing decision; this script reads it and dispatches
to the appropriate executor.

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent  # mu/tools/executors -> repo root

# Routing token → executor mapping
ROUTING_DISPATCH = {
    "CONTINUE_DIALECTIC": "dialectic_executor",
    "ROUTE_PHASE_A": "phase_a_executor",
    "ROUTE_PHASE_B": "phase_b_executor",
    "UPDATE_TRACKER_ONLY": "commit_executor",
    # COMMIT_GO / COMMIT_GO_HOLD_PUSH come from pre-commit supervisor, not post-merge
    "COMMIT_GO": "commit_executor",
    "COMMIT_GO_HOLD_PUSH": "commit_executor",
}

# Tokens that stop and require human intervention
STOP_TOKENS = {"STOP_FOR_FOUNDER", "STOP_FOR_TRIAGE_DISCUSSION"}

# Available executor scripts
AVAILABLE_EXECUTORS = {"commit_executor", "phase_b_executor"}

DEFAULT_CONFIG_PATH = SCRIPT_DIR / "executor_config.json"
ROUTING_RECORD_PATH = Path(".agent_bus/meta/post_merge_routing.json")


class DispatchError(RuntimeError):
    """Raised when dispatch cannot proceed."""


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load executor config with defaults."""
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return {
            "backends": {},
            "model_overrides": {},
            "timeouts": {},
            "bridge_loop_limits": {"phase_a": 15, "phase_b": 10, "dialectic": 3},
        }
    return json.loads(path.read_text(encoding="utf-8"))


def load_routing_record(repo_root: Path) -> dict[str, Any]:
    """Load and validate the post-merge routing record."""
    record_path = repo_root / ROUTING_RECORD_PATH
    if not record_path.exists():
        raise DispatchError(f"Routing record not found: {record_path}")

    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DispatchError(f"Routing record is not valid JSON: {exc}") from exc

    required = {"decision", "summary"}
    missing = required - set(record.keys())
    if missing:
        raise DispatchError(f"Routing record missing keys: {sorted(missing)}")

    return record


def validate_routing_record_freshness(record: dict[str, Any], repo_root: Path) -> tuple[bool, str]:
    """Check that the routing record's state_sha matches current repo state."""
    record_sha = record.get("state_sha", "")
    if not record_sha:
        return False, "Routing record has no state_sha — cannot verify freshness"

    # Compute current state SHA (same algorithm as meta_bridge_supervisor)
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        staged = subprocess.run(
            ["git", "diff", "--cached", "--binary"],
            cwd=repo_root, capture_output=True, check=True,
        ).stdout
        unstaged = subprocess.run(
            ["git", "diff", "--binary"],
            cwd=repo_root, capture_output=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as exc:
        return False, f"Cannot compute repo state: {exc}"

    staged_sha = hashlib.sha256(staged).hexdigest()
    unstaged_sha = hashlib.sha256(unstaged).hexdigest()

    # Compute untracked SHA (must match supervisor's compute_repo_state)
    try:
        untracked_output = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout
        ignore_prefixes = (".agent_bus/", ".git/", ".scratch/", "__pycache__/", ".venv/", "venv/", "node_modules/")
        untracked_hasher = hashlib.sha256()
        for raw in sorted(untracked_output.splitlines()):
            raw = raw.strip()
            if not raw:
                continue
            if any(raw.startswith(p) for p in ignore_prefixes):
                continue
            path = repo_root / raw
            if path.is_file():
                untracked_hasher.update(raw.encode("utf-8"))
                untracked_hasher.update(b"\0")
                untracked_hasher.update(path.read_bytes())
                untracked_hasher.update(b"\0")
        untracked_sha = untracked_hasher.hexdigest()
    except (subprocess.CalledProcessError, OSError):
        untracked_sha = hashlib.sha256(b"").hexdigest()

    current_sha = hashlib.sha256(
        f"{head}|{staged_sha}|{unstaged_sha}|{untracked_sha}".encode("utf-8")
    ).hexdigest()

    if current_sha != record_sha:
        return False, (
            f"Routing record is stale: record state_sha={record_sha[:8]}, "
            f"current={current_sha[:8]}"
        )

    return True, "fresh"


def resolve_executor(decision: str) -> str | None:
    """Map a routing decision to an executor name."""
    return ROUTING_DISPATCH.get(decision)


def dispatch(
    record: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    skip_freshness: bool = False,
    verbose: bool = False,
) -> dict[str, Any]:
    """Dispatch a routing decision to the appropriate executor.

    Returns a result dict with status, executor, and output.
    """
    repo = repo_root or REPO_ROOT
    cfg = config or load_config()
    decision = record.get("decision", "")

    # Stop tokens — require human intervention
    if decision in STOP_TOKENS:
        return {
            "status": "stopped",
            "decision": decision,
            "summary": record.get("summary", ""),
            "request_for_claude": record.get("request_for_claude", ""),
            "message": f"Routing stopped: {decision}. Requires founder/triage intervention.",
        }

    # Resolve executor
    executor_name = resolve_executor(decision)
    if executor_name is None:
        return {
            "status": "error",
            "decision": decision,
            "message": f"Unknown routing decision: {decision}. No executor mapped.",
        }

    # Check if executor is implemented
    if executor_name not in AVAILABLE_EXECUTORS:
        return {
            "status": "not_implemented",
            "decision": decision,
            "executor": executor_name,
            "message": f"Executor {executor_name} is not yet implemented (Slice 3-6). "
                       f"Manual execution required.",
        }

    # Validate freshness
    if not skip_freshness:
        fresh, msg = validate_routing_record_freshness(record, repo)
        if not fresh:
            return {
                "status": "stale",
                "decision": decision,
                "executor": executor_name,
                "message": f"Routing record is stale: {msg}. Re-run post-merge supervisor.",
            }

    if verbose:
        print(f"[dispatch] Decision: {decision} → {executor_name}")

    # Dispatch to executor
    executor_path = SCRIPT_DIR / f"{executor_name}.py"
    if not executor_path.exists():
        return {
            "status": "error",
            "decision": decision,
            "executor": executor_name,
            "message": f"Executor script not found: {executor_path}",
        }

    # Invoke executor with appropriate interface
    # commit_executor requires --handoff (not --routing-record)
    # Other executors use --routing-record
    try:
        timeout = cfg.get("timeouts", {}).get(executor_name, 300)
        if executor_name == "commit_executor":
            # Commit executor needs a handoff file, not a routing record.
            # When invoked from UPDATE_TRACKER_ONLY, the dispatcher must have
            # a handoff prepared by the caller. For now, report that the caller
            # must prepare the handoff.
            return {
                "status": "needs_handoff",
                "decision": decision,
                "executor": executor_name,
                "message": "commit_executor requires a prepared --handoff file. "
                           "The caller (phase_b, phase_a, or update_tracker_only) "
                           "must stage files, run pre-commit supervisor, and prepare "
                           "the handoff before dispatching to commit_executor.",
            }

        result = subprocess.run(
            [sys.executable, str(executor_path), "--routing-record", json.dumps(record)],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "status": "success" if result.returncode == 0 else "failed",
            "decision": decision,
            "executor": executor_name,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "decision": decision,
            "executor": executor_name,
            "message": f"Executor {executor_name} timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "status": "error",
            "decision": decision,
            "executor": executor_name,
            "message": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Executor dispatcher: reads routing record and invokes executor",
    )
    parser.add_argument(
        "--routing-record",
        type=Path,
        help="Path to routing record JSON (default: .agent_bus/meta/post_merge_routing.json)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to executor config JSON",
    )
    parser.add_argument(
        "--skip-freshness",
        action="store_true",
        help="Skip routing record freshness check",
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

    # Load routing record
    if args.routing_record:
        try:
            record = json.loads(args.routing_record.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[error] Cannot load routing record: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            record = load_routing_record(repo_root)
        except DispatchError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1

    # Load config
    config = load_config(args.config) if args.config else load_config()

    # Dispatch
    result = dispatch(
        record,
        config=config,
        repo_root=repo_root,
        skip_freshness=args.skip_freshness,
        verbose=args.verbose,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        status = result.get("status", "unknown")
        decision = result.get("decision", "unknown")
        executor = result.get("executor", "none")
        message = result.get("message", result.get("summary", ""))
        print(f"[dispatch] Status: {status}")
        print(f"[dispatch] Decision: {decision}")
        if executor != "none":
            print(f"[dispatch] Executor: {executor}")
        if message:
            print(f"[dispatch] {message}")
        if result.get("stdout"):
            print(result["stdout"])
        if result.get("stderr"):
            print(result["stderr"], file=sys.stderr)

    return 0 if result.get("status") in ("success", "stopped", "not_implemented") else 1


if __name__ == "__main__":
    sys.exit(main())
