#!/usr/bin/env python3
"""Executor dispatcher: reads post-merge routing record and invokes the correct executor.

This is the entry point for automated workflow execution. The post-merge
supervisor emits a routing decision; this script reads it and dispatches
to the appropriate executor.

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent  # mu/tools/executors -> repo root

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        load_executor_config as _common_load_executor_config,
        load_routing_record as _common_load_routing_record,
        merge_executor_config_overrides,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _common_load_executor_config = _mod.load_executor_config
    _common_load_routing_record = _mod.load_routing_record
    merge_executor_config_overrides = _mod.merge_executor_config_overrides
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError

try:
    from meta_bridge_supervisor import compute_repo_state as _compute_repo_state
except ImportError:
    import importlib.util as _ilu
    _meta_path = REPO_ROOT / "mu" / "tools" / "agents" / "meta_bridge_supervisor.py"
    _meta_spec = _ilu.spec_from_file_location("meta_bridge_supervisor", str(_meta_path))
    _meta_mod = _ilu.module_from_spec(_meta_spec)
    assert _meta_spec.loader is not None
    sys.modules["meta_bridge_supervisor"] = _meta_mod
    _meta_spec.loader.exec_module(_meta_mod)
    _compute_repo_state = _meta_mod.compute_repo_state

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
AVAILABLE_EXECUTORS = {"commit_executor", "phase_b_executor", "phase_a_executor", "dialectic_executor"}

DEFAULT_CONFIG_PATH = SCRIPT_DIR / "executor_config.json"


class DispatchError(RuntimeError):
    """Raised when dispatch cannot proceed."""


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load executor config using the canonical shared defaults/merge rules."""
    path = config_path or DEFAULT_CONFIG_PATH
    if path == DEFAULT_CONFIG_PATH:
        return _common_load_executor_config(REPO_ROOT)
    if not path.exists():
        return merge_executor_config_overrides({})
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return merge_executor_config_overrides(loaded)


def load_routing_record(repo_root: Path) -> dict[str, Any]:
    """Load and validate the post-merge routing record.

    Delegates to executor_common.load_routing_record (canonical implementation).
    Wraps ExecutorCommonError as DispatchError for backward compatibility.
    """
    try:
        return _common_load_routing_record(repo_root)
    except ExecutorCommonError as exc:
        raise DispatchError(str(exc)) from exc


def validate_routing_record_freshness(record: dict[str, Any], repo_root: Path) -> tuple[bool, str]:
    """Check that the routing record's state_sha matches current repo state."""
    record_sha = record.get("state_sha", "")
    if not record_sha:
        return False, "Routing record has no state_sha — cannot verify freshness"

    try:
        current_sha = _compute_repo_state(repo_root).state_sha
    except Exception as exc:
        return False, f"Cannot compute repo state: {exc}"

    if current_sha != record_sha:
        return False, (
            f"Routing record is stale: record state_sha={record_sha[:8]}, "
            f"current={current_sha[:8]}"
        )

    return True, "fresh"


def resolve_executor(decision: str) -> str | None:
    """Map a routing decision to an executor name."""
    return ROUTING_DISPATCH.get(decision)


def _sanitize_plan_name(candidate_text: str, fallback: str = "plan_unknown") -> str:
    """Convert candidate text into a safe plan slug."""
    raw = (candidate_text or "").lower()
    tokens = re.findall(r"[a-z0-9]+", raw)
    if not tokens:
        tokens = re.findall(r"[a-z0-9]+", fallback.lower())
    slug = "_".join(tokens).strip("_")
    return (slug or "plan_unknown")[:50]


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
    try:
        ensure_not_agent_review_mode("executor_dispatch.dispatch")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "decision": record.get("decision", ""),
            "message": str(exc),
        }

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
    try:
        timeout = cfg.get("timeouts", {}).get(executor_name, 300)

        # Build executor-specific CLI args
        executor_args = [sys.executable, str(executor_path)]
        if executor_name == "commit_executor":
            # Only use a pre-prepared handoff for decisions that come from
            # Phase B/A (COMMIT_GO, COMMIT_GO_HOLD_PUSH).  UPDATE_TRACKER_ONLY
            # must always go through --routing-record so the commit executor
            # builds a tracker-only handoff from the live routing decision
            # instead of replaying a stale Phase B handoff file.
            handoff_path = repo / ".agent_bus" / "executors" / "phase_b_handoff.json"
            if decision in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
                # COMMIT_GO/COMMIT_GO_HOLD_PUSH require a pre-prepared Phase B
                # handoff.  Without one, the commit executor would synthesize a
                # handoff that points at the canonical hook receipt instead of
                # the exact per-invocation Phase B receipt — breaking the
                # authority chain.  Fail closed.
                if not handoff_path.exists():
                    return {
                        "status": "error",
                        "decision": decision,
                        "executor": executor_name,
                        "message": (
                            f"No Phase B handoff file at {handoff_path} for "
                            f"{decision}. Cannot commit without a verified "
                            f"Phase B receipt chain."
                        ),
                    }
                executor_args.extend(["--handoff", str(handoff_path)])
            else:
                # UPDATE_TRACKER_ONLY: pass routing record so commit_executor
                # can prepare a tracker-only handoff internally.
                executor_args.extend(["--routing-record", json.dumps(record)])
        elif executor_name == "phase_a_executor":
            # Phase A needs --plan-name
            candidates = record.get("next_candidates", [])
            plan_name = None
            for c in candidates:
                candidate_text = c.get("candidate", "")
                if candidate_text:
                    plan_name = _sanitize_plan_name(candidate_text)
                    break
            if not plan_name:
                plan_name = _sanitize_plan_name(
                    f"plan_{record.get('wave_name', 'unknown')}",
                )
            executor_args.extend(["--plan-name", plan_name])
        elif executor_name == "phase_b_executor":
            # Phase B: prefer --plan from next_candidates tracked_packet,
            # fall back to planless mode (routing record as authority source)
            candidates = record.get("next_candidates", [])
            plan_path = None
            for c in candidates:
                tp = c.get("tracked_packet")
                if tp and isinstance(tp, str):
                    # Validate: no path traversal, must be relative, must
                    # resolve inside repo root.
                    tp_resolved = (repo / tp).resolve()
                    if ".." in Path(tp).parts:
                        return {
                            "status": "error",
                            "decision": decision,
                            "executor": executor_name,
                            "message": f"Path traversal in tracked_packet: {tp}",
                        }
                    if not tp_resolved.is_relative_to(repo.resolve()):
                        return {
                            "status": "error",
                            "decision": decision,
                            "executor": executor_name,
                            "message": f"tracked_packet escapes repo root: {tp}",
                        }
                    plan_path = tp
                    break
            if plan_path:
                executor_args.extend(["--plan", plan_path])
            else:
                # Planless mode: Phase B derives scope from routing record.
                # The routing record must have wave_name, summary, and
                # next_candidates for this to succeed (fail-closed in Phase B).
                executor_args.extend(["--routing-record", json.dumps(record)])
        else:
            executor_args.extend(["--routing-record", json.dumps(record)])

        result = subprocess.run(
            executor_args,
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
