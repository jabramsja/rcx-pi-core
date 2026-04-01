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
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent  # mu/tools/executors -> repo root
AGENTS_DIR = SCRIPT_DIR.parent / "agents"
META_BUS_DIR = ".agent_bus/meta"
POST_MERGE_PACKAGE_NAME = "post_merge_package.json"

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        load_executor_config as _common_load_executor_config,
        load_routing_record as _common_load_routing_record,
        merge_executor_config_overrides,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        normalize_wave_id,
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
    normalize_wave_id = _mod.normalize_wave_id

try:
    from recovery_gate import attempt_recovery
except ImportError:
    import importlib.util as _ilu
    _recovery_path = SCRIPT_DIR / "recovery_gate.py"
    _recovery_spec = _ilu.spec_from_file_location("recovery_gate", str(_recovery_path))
    _recovery_mod = _ilu.module_from_spec(_recovery_spec)
    assert _recovery_spec.loader is not None
    sys.modules["recovery_gate"] = _recovery_mod
    _recovery_spec.loader.exec_module(_recovery_mod)
    attempt_recovery = _recovery_mod.attempt_recovery

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

# Dispatch-level statuses that are never retryable.
# - success/stopped/error/not_implemented/stale: config or structural outcomes.
# NOTE: "timeout" was removed — it is now routed through the recovery gate
# where Tier 2 fix_process_timeout adjusts the timeout and grants a retry.
_NON_RETRYABLE_DISPATCH_STATUSES = frozenset({
    "success", "held", "stopped", "error", "not_implemented", "stale",
})

# Executor-reported statuses that indicate a terminal outcome requiring
# founder intervention — retrying would just re-produce the same result.
# - question_for_founder: bridge QUESTION requires human input
# - max_rounds_reached: bridge loop exhausted without convergence
# - supervisor_rejected: pre-commit supervisor returned non-COMMIT_GO
#   (e.g. STOP_FOR_FOUNDER) — founder decision required
# - needs_phase_b: supervisor returned NEEDS_PHASE_B after reentry
#   convergence — manual intervention required
_TERMINAL_EXECUTOR_STATUSES = frozenset({
    "question_for_founder",
    "max_rounds_reached",
    "supervisor_rejected",
    "needs_phase_b",
})

# Available executor scripts
AVAILABLE_EXECUTORS = {"commit_executor", "phase_b_executor", "phase_a_executor", "dialectic_executor"}
SURFACE_COMMANDS = {
    "phase-a",
    "phase-b",
    "pre-commit-supervisor",
    "commit",
    "post-merge-supervisor",
}

DEFAULT_CONFIG_PATH = SCRIPT_DIR / "executor_config.json"


class DispatchError(RuntimeError):
    """Raised when dispatch cannot proceed."""


class ControlSurfaceError(RuntimeError):
    """Raised when a modular surface invocation is malformed."""


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


def _load_routing_record_payload(
    *,
    path_value: Path | None,
    json_value: str | None,
) -> str | None:
    if path_value and json_value:
        raise ControlSurfaceError("Provide only one of --routing-record-path or --routing-record-json")
    if path_value:
        try:
            return path_value.read_text(encoding="utf-8")
        except OSError as exc:
            raise ControlSurfaceError(f"Cannot read routing record: {exc}") from exc
    return json_value


def build_surface_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Modular control-plane entrypoint for executors and supervisors",
    )
    sub = parser.add_subparsers(dest="surface", required=True)

    phase_a = sub.add_parser("phase-a", help="Run Phase A executor")
    phase_a.add_argument("--plan-name", required=True, help="Plan packet slug")
    phase_a.add_argument("--max-rounds", type=int, default=15)
    phase_a.add_argument("-v", "--verbose", action="store_true")
    phase_a.add_argument("--json", action="store_true")

    phase_b = sub.add_parser("phase-b", help="Run Phase B executor")
    phase_b.add_argument("--plan", default=None, help="Locked plan packet path")
    phase_b.add_argument("--routing-record-path", type=Path, help="Path to routing record JSON")
    phase_b.add_argument("--routing-record-json", help="Routing record JSON string")
    phase_b.add_argument("--max-rounds", type=int, default=10)
    phase_b.add_argument("--bootstrap-exception", action="store_true")
    phase_b.add_argument("-v", "--verbose", action="store_true")
    phase_b.add_argument("--json", action="store_true")

    pre_commit = sub.add_parser("pre-commit-supervisor", help="Run pre-commit supervisor")
    pre_commit.add_argument("--package", type=Path, required=True)
    pre_commit.add_argument("--dry-run", action="store_true")
    pre_commit.add_argument("-v", "--verbose", action="store_true")
    pre_commit.add_argument("--json", action="store_true")

    commit = sub.add_parser("commit", help="Run commit executor")
    commit.add_argument("--handoff", type=Path, help="Path to handoff JSON")
    commit.add_argument("--routing-record-path", type=Path, help="Path to routing record JSON")
    commit.add_argument("--routing-record-json", help="Routing record JSON string")
    commit.add_argument("-v", "--verbose", action="store_true")
    commit.add_argument("--json", action="store_true")

    post_merge = sub.add_parser("post-merge-supervisor", help="Run post-merge supervisor")
    post_merge.add_argument("--package", type=Path, required=True)
    post_merge.add_argument("-v", "--verbose", action="store_true")
    post_merge.add_argument("--json", action="store_true")

    return parser


def build_surface_command(args: argparse.Namespace) -> list[str]:
    if args.surface == "phase-a":
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "phase_a_executor.py"),
            "--plan-name",
            args.plan_name,
            "--max-rounds",
            str(args.max_rounds),
        ]
    elif args.surface == "phase-b":
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "phase_b_executor.py"),
            "--max-rounds",
            str(args.max_rounds),
        ]
        if args.plan:
            cmd.extend(["--plan", args.plan])
        routing_payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if routing_payload:
            cmd.extend(["--routing-record", routing_payload])
        if args.bootstrap_exception:
            cmd.append("--bootstrap-exception")
    elif args.surface == "pre-commit-supervisor":
        cmd = [
            sys.executable,
            str(AGENTS_DIR / "meta_bridge_supervisor.py"),
            "--package",
            str(args.package),
        ]
        if args.dry_run:
            cmd.append("--dry-run")
    elif args.surface == "commit":
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "commit_executor.py"),
        ]
        routing_payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if args.handoff:
            if routing_payload:
                raise ControlSurfaceError("Provide either --handoff or a routing record, not both")
            cmd.extend(["--handoff", str(args.handoff)])
        elif routing_payload:
            cmd.extend(["--routing-record", routing_payload])
        else:
            raise ControlSurfaceError("commit requires --handoff or a routing record")
    elif args.surface == "post-merge-supervisor":
        cmd = [
            sys.executable,
            str(AGENTS_DIR / "meta_bridge_supervisor.py"),
            "--mode",
            "post-merge",
            "--package",
            str(args.package),
        ]
    else:
        raise ControlSurfaceError(f"Unsupported surface: {args.surface}")

    if getattr(args, "verbose", False):
        cmd.append("--verbose")
    if getattr(args, "json", False):
        cmd.append("--json")
    return cmd


def run_surface_command(cmd: list[str], *, repo_root: Path) -> int:
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


def _validate_phase_b_handoff_identity(handoff_path: Path, record: dict[str, Any]) -> tuple[bool, str]:
    """Fail closed if a stale handoff file does not match the current routing identity."""
    try:
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, f"Phase B handoff is not valid JSON: {exc}"
    if not isinstance(handoff, dict):
        return False, "Phase B handoff must decode to a JSON object"

    wave_name = record.get("wave_name") or record.get("wave_id", "")
    if not isinstance(wave_name, str) or not wave_name.strip():
        return False, "Routing record missing wave_name/wave_id for handoff identity check"
    expected_wave_id = normalize_wave_id(wave_name)
    actual_wave_id = handoff.get("wave_id")
    if actual_wave_id != expected_wave_id:
        return False, (
            f"Phase B handoff wave_id mismatch: expected {expected_wave_id}, got {actual_wave_id}"
        )

    expected_task_id = record.get("task_id")
    actual_task_id = handoff.get("task_id")
    if (expected_task_id or actual_task_id) and actual_task_id != expected_task_id:
        return False, (
            f"Phase B handoff task_id mismatch: expected {expected_task_id}, got {actual_task_id}"
        )

    return True, "ok"


def _is_terminal_executor_outcome(result: dict[str, Any]) -> bool:
    """Check if a failed executor result contains a terminal outcome.

    Terminal outcomes (e.g. bridge NO_GO requiring founder intervention,
    max bridge rounds exhausted) should not be retried — retrying would
    re-invoke the executor with the same inputs and the same result.
    """
    stdout = result.get("stdout", "")
    if not stdout:
        return False
    # Try full JSON parse (executor with --json)
    try:
        data = json.loads(stdout)
        if isinstance(data, dict) and data.get("status") in _TERMINAL_EXECUTOR_STATUSES:
            return True
    except (json.JSONDecodeError, ValueError):
        pass
    # Try line-by-line: Phase B text output is "[phase-b] Status: <status>"
    # and executors may emit per-line JSON objects.
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("[phase-") and "Status:" in stripped:
            status_part = stripped.split("Status:", 1)[1].strip()
            if status_part in _TERMINAL_EXECUTOR_STATUSES:
                return True
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                if isinstance(data, dict) and data.get("status") in _TERMINAL_EXECUTOR_STATUSES:
                    return True
            except (json.JSONDecodeError, ValueError):
                pass
    return False


def _is_chained_commit_failure(result: dict[str, Any]) -> bool:
    """Check if a dispatch result is a failed chained commit.

    When Phase A→B→commit or Phase B→commit chains, the commit step may
    fail while earlier phases succeeded.  Retrying should only re-run the
    commit executor, not the full chain.
    """
    return (
        result.get("status") == "failed"
        and result.get("executor") == "commit_executor"
        and result.get("chained_from") is not None
    )


def _classify_commit_executor_result(
    commit_result: subprocess.CompletedProcess[str],
) -> tuple[str, str]:
    """Derive (dispatch_status, decision) from a commit executor subprocess result.

    The commit executor exits 0 for both ``success`` and ``held`` (the latter
    when the routing decision was ``COMMIT_GO_HOLD_PUSH``).  Without parsing
    the executor's output, the dispatcher would collapse ``held`` into
    ``success`` and report ``COMMIT_GO`` — making a local-hold stop look like
    a completed wave.

    Returns ``("held", "COMMIT_HELD")`` when the commit was made locally but
    push was intentionally skipped, ``("success", "COMMIT_GO")`` on full
    success, or ``("failed", "COMMIT_GO")`` on non-zero exit.
    """
    if commit_result.returncode != 0:
        return "failed", "COMMIT_GO"
    stdout = commit_result.stdout or ""
    if "[commit-executor] Status: held" in stdout:
        return "held", "COMMIT_HELD"
    return "success", "COMMIT_GO"


def _retry_commit_only(
    repo: Path,
    config: dict[str, Any],
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Retry only the commit executor using the existing Phase B handoff.

    Used when a chained commit fails — avoids re-running Phase A/B.
    """
    handoff_path = repo / ".agent_bus" / "executors" / "phase_b_handoff.json"
    if not handoff_path.exists():
        return {
            "status": "error",
            "decision": "COMMIT_GO",
            "executor": "commit_executor",
            "message": f"Cannot retry commit: handoff file missing at {handoff_path}",
        }

    if verbose:
        print("[dispatch] Retrying commit executor only (Phase A/B already succeeded)")

    commit_timeout = config.get("timeouts", {}).get("commit_executor", 300)
    commit_args = [
        sys.executable,
        str(SCRIPT_DIR / "commit_executor.py"),
        "--handoff", str(handoff_path),
    ]
    try:
        commit_result = subprocess.run(
            commit_args,
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
            timeout=commit_timeout,
        )
        c_status, c_decision = _classify_commit_executor_result(commit_result)
        return {
            "status": c_status,
            "decision": c_decision,
            "executor": "commit_executor",
            "exit_code": commit_result.returncode,
            "stdout": commit_result.stdout,
            "stderr": commit_result.stderr,
            "chained_from": "retry_commit_only",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "decision": "COMMIT_GO",
            "executor": "commit_executor",
            "message": f"Commit executor timed out after {commit_timeout}s",
        }


# Phase B state file path — must match phase_b_executor.py constants.
_PHASE_B_STATE_PATH = Path(".agent_bus") / "executors" / "phase_b_state.json"


def _apply_recovery_overrides(
    config: dict[str, Any],
    repo_root: Path | None = None,
    verbose: bool = False,
) -> dict[str, Any] | None:
    """Apply Tier 2 recovery env var overrides to config for retry.

    fix_process_timeout sets RCX_RECOVERY_TIMEOUT_OVERRIDE (and
    RCX_RECOVERY_TIMEOUT_KEY to target the correct executor timeout).
    fix_implementer_stale sets RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE.

    These are applied to the in-memory config dict AND written to
    executor_config.json on disk (when repo_root is provided) so that
    subprocesses which reload config from disk (e.g. phase_b_implementer)
    pick up the adjusted values.

    Returns original disk timeouts dict if disk was modified (caller
    should pass to _restore_config_on_disk after retry), or None.
    """
    disk_config = None
    original_timeouts = None
    config_path = None
    disk_modified = False

    if repo_root is not None:
        config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
        try:
            disk_config = json.loads(config_path.read_text(encoding="utf-8"))
            original_timeouts = dict(disk_config.get("timeouts", {}))
        except (json.JSONDecodeError, OSError):
            disk_config = None

    timeout_override = os.environ.get("RCX_RECOVERY_TIMEOUT_OVERRIDE")
    if timeout_override:
        try:
            val = int(timeout_override)
            timeout_key = os.environ.get(
                "RCX_RECOVERY_TIMEOUT_KEY", "phase_b_executor")
            config.setdefault("timeouts", {})[timeout_key] = val
            if disk_config is not None:
                disk_config.setdefault("timeouts", {})[timeout_key] = val
                disk_modified = True
            if verbose:
                print(f"[dispatch] Applied timeout override: {timeout_key}={val}s")
        except ValueError:
            pass
        # Clear env vars after consumption to prevent leakage to later
        # retries or --loop waves (Bridge R4 Finding fix).
        os.environ.pop("RCX_RECOVERY_TIMEOUT_OVERRIDE", None)
        os.environ.pop("RCX_RECOVERY_TIMEOUT_KEY", None)

    stale_override = os.environ.get("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE")
    if stale_override:
        try:
            val = int(stale_override)
            config.setdefault("timeouts", {})["phase_b_implementer_stale"] = val
            if disk_config is not None:
                disk_config.setdefault("timeouts", {})["phase_b_implementer_stale"] = val
                disk_modified = True
            if verbose:
                print(f"[dispatch] Applied stale timeout override: "
                      f"phase_b_implementer_stale={val}s")
        except ValueError:
            pass
        # Clear env var after consumption (Bridge R4 Finding fix).
        os.environ.pop("RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE", None)

    if disk_modified and config_path is not None and disk_config is not None:
        try:
            config_path.write_text(
                json.dumps(disk_config, indent=2) + "\n", encoding="utf-8")
            if verbose:
                print("[dispatch] Recovery overrides written to executor_config.json")
        except OSError:
            pass

    return original_timeouts if disk_modified else None


def _restore_config_on_disk(
    repo_root: Path,
    original_timeouts: dict[str, Any],
    verbose: bool = False,
) -> None:
    """Restore original timeouts to executor_config.json after recovery retry."""
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    try:
        disk_config = json.loads(config_path.read_text(encoding="utf-8"))
        disk_config["timeouts"] = original_timeouts
        config_path.write_text(
            json.dumps(disk_config, indent=2) + "\n", encoding="utf-8")
        if verbose:
            print("[dispatch] Restored original executor_config.json timeouts")
    except (json.JSONDecodeError, OSError):
        pass


def _clear_phase_b_state_for_retry(
    repo_root: Path,
    result: dict[str, Any],
    *,
    verbose: bool = False,
) -> None:
    """Clear Phase B persisted state before a dispatcher retry.

    When Phase B fails during the bridge-fix cycle (e.g. implementer_bridge_fix
    or pytest_fix step), it returns without clearing its persisted state.  The
    stale checkpoint (typically completed_step="agent_review") would cause the
    next Phase B invocation to skip the implementer re-entry, bypassing the
    required bridge-fix cycle.  Clearing the state forces a fresh start.
    """
    if result.get("executor") != "phase_b_executor":
        return
    state_path = repo_root / _PHASE_B_STATE_PATH
    if state_path.exists():
        state_path.unlink()
        if verbose:
            print("[dispatch] Cleared stale Phase B state before retry")


def _auto_refresh_routing(
    repo_root: Path,
    *,
    verbose: bool = False,
) -> tuple[bool, dict[str, Any] | None]:
    """Re-run the post-merge supervisor to refresh a stale routing record.

    Looks for the canonical post-merge package at .agent_bus/meta/post_merge_package.json.
    Returns (success, refreshed_record) — record is None on failure.
    """
    package_path = repo_root / META_BUS_DIR / POST_MERGE_PACKAGE_NAME
    if not package_path.exists():
        if verbose:
            print(f"[dispatch] No post-merge package at {package_path} — cannot auto-refresh")
        return False, None

    supervisor_script = AGENTS_DIR / "meta_bridge_supervisor.py"
    if not supervisor_script.exists():
        if verbose:
            print(f"[dispatch] Supervisor script not found: {supervisor_script}")
        return False, None

    cmd = [
        sys.executable,
        str(supervisor_script),
        "--mode", "post-merge",
        "--package", str(package_path),
        "--json",
    ]
    if verbose:
        cmd.append("--verbose")
        print(f"[dispatch] Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        if verbose:
            print("[dispatch] Post-merge supervisor timed out during auto-refresh")
        return False, None

    if result.returncode != 0:
        if verbose:
            print(f"[dispatch] Post-merge supervisor exited {result.returncode}")
            if result.stderr:
                print(f"[dispatch] stderr: {result.stderr[:500]}")
        return False, None

    # Reload the routing record
    try:
        refreshed = _common_load_routing_record(repo_root)
    except ExecutorCommonError as exc:
        if verbose:
            print(f"[dispatch] Failed to reload routing record after refresh: {exc}")
        return False, None

    # Verify freshness of the refreshed record
    fresh, msg = validate_routing_record_freshness(refreshed, repo_root)
    if not fresh:
        if verbose:
            print(f"[dispatch] Refreshed record still stale: {msg}")
        return False, None

    if verbose:
        print(f"[dispatch] Auto-refresh succeeded: decision={refreshed.get('decision')}")
    return True, refreshed


def _extract_plan_path(phase_a_stdout: str, repo_root: Path) -> str | None:
    """Parse plan_path from Phase A executor output (JSON or text)."""
    # Try JSON first
    for line in phase_a_stdout.strip().splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                data = json.loads(line)
                pp = data.get("plan_path")
                if isinstance(pp, str) and pp:
                    return pp
            except json.JSONDecodeError:
                pass
    # Try full output as JSON
    try:
        data = json.loads(phase_a_stdout)
        pp = data.get("plan_path")
        if isinstance(pp, str) and pp:
            return pp
    except (json.JSONDecodeError, ValueError):
        pass
    # Fallback: parse "[phase-a] Plan: <path>" text output
    for line in phase_a_stdout.splitlines():
        if line.strip().startswith("[phase-a] Plan:"):
            pp = line.split("Plan:", 1)[1].strip()
            if pp:
                return pp
    return None


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

    # Validate freshness — auto-refresh via post-merge supervisor if stale
    if not skip_freshness:
        fresh, msg = validate_routing_record_freshness(record, repo)
        if not fresh:
            if verbose:
                print(f"[dispatch] Routing record stale: {msg}")
                print("[dispatch] Auto-refreshing via post-merge supervisor...")
            refreshed, refresh_record = _auto_refresh_routing(repo, verbose=verbose)
            if not refreshed or refresh_record is None:
                return {
                    "status": "stale",
                    "decision": decision,
                    "executor": executor_name,
                    "message": f"Routing record is stale: {msg}. "
                               f"Auto-refresh failed — re-run post-merge supervisor manually.",
                }
            # Use the refreshed record for the rest of dispatch
            record = refresh_record
            decision = record.get("decision", "")
            # Re-check stop tokens after refresh
            if decision in STOP_TOKENS:
                return {
                    "status": "stopped",
                    "decision": decision,
                    "summary": record.get("summary", ""),
                    "request_for_claude": record.get("request_for_claude", ""),
                    "message": f"Routing stopped after refresh: {decision}. "
                               f"Requires founder/triage intervention.",
                }
            executor_name = resolve_executor(decision)
            if executor_name is None:
                return {
                    "status": "error",
                    "decision": decision,
                    "message": f"Refreshed routing decision unknown: {decision}.",
                }
            if verbose:
                print(f"[dispatch] Refreshed: decision={decision}, executor={executor_name}")

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
                valid_handoff, handoff_msg = _validate_phase_b_handoff_identity(handoff_path, record)
                if not valid_handoff:
                    return {
                        "status": "error",
                        "decision": decision,
                        "executor": executor_name,
                        "message": f"Phase B handoff validation failed: {handoff_msg}",
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
        if result.returncode != 0:
            return {
                "status": "failed",
                "decision": decision,
                "executor": executor_name,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        # ── Phase chain: A → B → commit ─────────────────────────
        # After Phase A converges, immediately invoke Phase B with the
        # locked plan.  After Phase B produces a commit handoff, invoke
        # the commit executor.  This is the full pipeline cycle without
        # requiring separate dispatch invocations between phases.

        if executor_name == "phase_a_executor":
            # Parse plan_path from Phase A JSON output
            plan_path = _extract_plan_path(result.stdout, repo)
            if plan_path is None:
                return {
                    "status": "failed",
                    "decision": decision,
                    "executor": executor_name,
                    "exit_code": 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "message": "Phase A converged but no plan_path found in output",
                }

            if verbose:
                print(f"[dispatch] Phase A converged → chaining to Phase B with plan: {plan_path}")

            phase_b_timeout = cfg.get("timeouts", {}).get("phase_b_executor", 3600)
            # Synthesize a ROUTE_PHASE_B routing record so Phase B's
            # routing validation passes.
            phase_b_routing = json.dumps({
                "decision": "ROUTE_PHASE_B",
                "wave_name": record.get("wave_name", ""),
                "task_id": record.get("task_id", ""),
                "summary": "Chained from Phase A convergence",
                "next_candidates": record.get("next_candidates", []),
            })
            phase_b_args = [
                sys.executable,
                str(SCRIPT_DIR / "phase_b_executor.py"),
                "--plan", plan_path,
                "--routing-record", phase_b_routing,
            ]
            try:
                phase_b_result = subprocess.run(
                    phase_b_args,
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=phase_b_timeout,
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "timeout",
                    "decision": "ROUTE_PHASE_B",
                    "executor": "phase_b_executor",
                    "message": f"Phase B executor timed out after {phase_b_timeout}s",
                    "chained_from": "phase_a_executor",
                }
            if phase_b_result.returncode != 0:
                return {
                    "status": "failed",
                    "decision": "ROUTE_PHASE_B",
                    "executor": "phase_b_executor",
                    "exit_code": phase_b_result.returncode,
                    "stdout": phase_b_result.stdout,
                    "stderr": phase_b_result.stderr,
                    "chained_from": "phase_a_executor",
                }

            if verbose:
                print("[dispatch] Phase B converged → chaining to commit executor")

            # Phase B writes handoff to canonical location
            handoff_path = repo / ".agent_bus" / "executors" / "phase_b_handoff.json"
            if not handoff_path.exists():
                return {
                    "status": "failed",
                    "decision": "ROUTE_PHASE_B",
                    "executor": "phase_b_executor",
                    "exit_code": 0,
                    "message": "Phase B converged but no handoff file found",
                    "chained_from": "phase_a_executor",
                }

            commit_timeout = cfg.get("timeouts", {}).get("commit_executor", 300)
            commit_args = [
                sys.executable,
                str(SCRIPT_DIR / "commit_executor.py"),
                "--handoff", str(handoff_path),
            ]
            try:
                commit_result = subprocess.run(
                    commit_args,
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=commit_timeout,
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "timeout",
                    "decision": "COMMIT_GO",
                    "executor": "commit_executor",
                    "message": f"Commit executor timed out after {commit_timeout}s",
                    "chained_from": "phase_a_executor → phase_b_executor",
                }
            c_status, c_decision = _classify_commit_executor_result(commit_result)
            return {
                "status": c_status,
                "decision": c_decision,
                "executor": "commit_executor",
                "exit_code": commit_result.returncode,
                "stdout": commit_result.stdout,
                "stderr": commit_result.stderr,
                "chained_from": "phase_a_executor → phase_b_executor",
            }

        elif executor_name == "phase_b_executor":
            # Phase B succeeded — chain to commit executor
            handoff_path = repo / ".agent_bus" / "executors" / "phase_b_handoff.json"
            if not handoff_path.exists():
                return {
                    "status": "failed",
                    "decision": decision,
                    "executor": executor_name,
                    "exit_code": 0,
                    "message": "Phase B converged but no handoff file found",
                }

            if verbose:
                print("[dispatch] Phase B converged → chaining to commit executor")

            commit_timeout = cfg.get("timeouts", {}).get("commit_executor", 300)
            commit_args = [
                sys.executable,
                str(SCRIPT_DIR / "commit_executor.py"),
                "--handoff", str(handoff_path),
            ]
            try:
                commit_result = subprocess.run(
                    commit_args,
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=commit_timeout,
                )
            except subprocess.TimeoutExpired:
                return {
                    "status": "timeout",
                    "decision": "COMMIT_GO",
                    "executor": "commit_executor",
                    "message": f"Commit executor timed out after {commit_timeout}s",
                    "chained_from": "phase_b_executor",
                }
            c_status, c_decision = _classify_commit_executor_result(commit_result)
            return {
                "status": c_status,
                "decision": c_decision,
                "executor": "commit_executor",
                "exit_code": commit_result.returncode,
                "stdout": commit_result.stdout,
                "stderr": commit_result.stderr,
                "chained_from": "phase_b_executor",
            }

        # Non-chained executor (commit, dialectic, etc.)
        nc_status, nc_decision = ("success", decision)
        if executor_name == "commit_executor":
            nc_status, nc_decision = _classify_commit_executor_result(result)
        return {
            "status": nc_status,
            "decision": nc_decision,
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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in SURFACE_COMMANDS:
        parser = build_surface_parser()
        args = parser.parse_args(argv)
        try:
            repo_root = Path(subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            ).stdout.strip())
        except subprocess.CalledProcessError:
            print("[error] Not in a git repository", file=sys.stderr)
            return 1
        try:
            cmd = build_surface_command(args)
        except ControlSurfaceError as exc:
            print(f"[executor-dispatch] Error: {exc}", file=sys.stderr)
            return 1
        return run_surface_command(cmd, repo_root=repo_root)

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
    parser.add_argument(
        "--loop",
        action="store_true",
        help="After merge, run post-merge supervisor and loop (full pipeline cycle)",
    )
    parser.add_argument(
        "--max-waves",
        type=int,
        default=3,
        help="Maximum waves per --loop invocation (default: 3)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Retry failed executor up to N times before giving up (default: 0)",
    )
    args = parser.parse_args(argv)

    try:
        repo_root = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
    except subprocess.CalledProcessError:
        print("[error] Not in a git repository", file=sys.stderr)
        return 1

    config = load_config(args.config) if args.config else load_config()
    wave_count = 0

    while True:
        wave_count += 1
        if args.verbose:
            print(f"\n[dispatch] === Wave {wave_count}/{args.max_waves if args.loop else 1} ===")

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
            except DispatchError:
                # No routing record — try to create one via post-merge supervisor
                if args.verbose:
                    print("[dispatch] No routing record — running post-merge supervisor...")
                refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose)
                if not refreshed or refresh_record is None:
                    print("[error] No routing record and auto-refresh failed", file=sys.stderr)
                    return 1
                record = refresh_record

        # Dispatch with retries (while-based so recovery can grant extra attempts)
        max_attempts = 1 + max(0, args.retries)
        result = None
        attempt = 1
        _recovery_original_timeouts = None
        while attempt <= max_attempts:
            # If previous attempt was a chained commit failure (Phase A/B
            # succeeded but commit failed), retry only the commit executor
            # instead of re-running the full Phase A→B→commit chain.
            if result is not None and _is_chained_commit_failure(result):
                result = _retry_commit_only(
                    repo_root, config,
                    verbose=args.verbose,
                )
            else:
                result = dispatch(
                    record,
                    config=config,
                    repo_root=repo_root,
                    skip_freshness=args.skip_freshness,
                    verbose=args.verbose,
                )
            # Non-retryable dispatch statuses — break immediately
            if result.get("status") in _NON_RETRYABLE_DISPATCH_STATUSES:
                break
            # Terminal executor outcomes (founder-required, max bridge rounds
            # exhausted) — retrying would re-produce the same result
            if result.get("status") == "failed" and _is_terminal_executor_outcome(result):
                if args.verbose:
                    print("[dispatch] Executor returned terminal outcome — not retrying")
                break
            # Recovery gate: classify failure and attempt Tier 1/2 auto-fix
            # "timeout" is included so PROCESS_TIMEOUT reaches Tier 2 recovery
            if result.get("status") in ("failed", "timeout"):
                _wave_id = normalize_wave_id(
                    record.get("wave_name") or record.get("wave_id", ""))
                recovery = attempt_recovery(repo_root, result, _wave_id)
                result["recovery"] = recovery
                if args.verbose:
                    tier = recovery.get('tier')
                    action = recovery.get('action', '')
                    print(f"[dispatch] Recovery: class={recovery.get('failure_class')} "
                          f"tier={tier} recovered={recovery.get('recovered')}")
                    if recovery.get("recovered") and tier == 2:
                        print(f"[dispatch] Tier 2 recovery: {action} "
                              f"— retrying with adjusted parameters")
                if recovery.get("recovered"):
                    # Apply Tier 2 env var overrides to config + disk before retry.
                    # Only capture original_timeouts on the FIRST recovery to
                    # prevent sequential recoveries from overwriting the true
                    # pre-recovery baseline (Finding 2 fix).
                    new_orig = _apply_recovery_overrides(
                        config, repo_root=repo_root, verbose=args.verbose)
                    if _recovery_original_timeouts is None:
                        _recovery_original_timeouts = new_orig
                    # Recovery succeeded — grant one extra attempt (don't increment counter)
                    _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose)
                    if not args.routing_record and not _is_chained_commit_failure(result):
                        refreshed, refresh_record = _auto_refresh_routing(
                            repo_root, verbose=args.verbose)
                        if refreshed and refresh_record is not None:
                            record = refresh_record
                    continue  # retry dispatch without counting against budget
                elif recovery.get("exhausted"):
                    if args.verbose:
                        print("[dispatch] Recovery exhausted — not retrying")
                    break
                else:
                    # Tier 3/4 non-recovery: fail closed instead of falling
                    # through to the normal retry loop (Bridge R6 Finding 2).
                    _rec_tier = recovery.get("tier", 0)
                    if _rec_tier >= 3:
                        if args.verbose:
                            print(f"[dispatch] Tier {_rec_tier} recovery not "
                                  f"available — failing closed")
                        break
            if attempt >= max_attempts:
                break
            if args.verbose:
                print(f"[dispatch] Attempt {attempt}/{max_attempts} failed — retrying...")
            # Clear Phase B persisted state before retry to prevent stale
            # resume from skipping required implementer re-entry after a
            # bridge-fix cycle failure.
            _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose)
            # Only refresh routing if no explicit --routing-record was provided
            # and this was NOT a chained commit retry (routing is irrelevant
            # when retrying only the commit step).
            # Do NOT unlink the existing routing record before refresh — if
            # refresh fails, the canonical record would be permanently lost.
            # The supervisor overwrites the file in place on success.
            if not args.routing_record and not _is_chained_commit_failure(result):
                refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose)
                if refreshed and refresh_record is not None:
                    record = refresh_record
            attempt += 1

        # Restore disk AND in-memory config if recovery overrides were written.
        # Both must be restored to prevent leakage to --loop waves
        # (Bridge R4 Finding fix).
        if _recovery_original_timeouts is not None:
            _restore_config_on_disk(
                repo_root, _recovery_original_timeouts,
                verbose=args.verbose)
            config["timeouts"] = dict(_recovery_original_timeouts)

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

        # If not looping, or if the wave failed/stopped, exit
        if not args.loop:
            break
        if result.get("status") != "success":
            if args.verbose:
                print(f"[dispatch] Wave {wave_count} did not succeed ({result.get('status')}), stopping loop")
            break
        if wave_count >= args.max_waves:
            if args.verbose:
                print(f"[dispatch] Max waves ({args.max_waves}) reached, stopping loop")
            break

        # Post-merge: refresh routing for next wave
        if args.verbose:
            print("[dispatch] Wave succeeded — running post-merge supervisor for next wave...")
        package_path = repo_root / META_BUS_DIR / POST_MERGE_PACKAGE_NAME
        if not package_path.exists():
            if args.verbose:
                print("[dispatch] No post-merge package — cannot loop to next wave")
            break
        refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose)
        if not refreshed or refresh_record is None:
            if args.verbose:
                print("[dispatch] Post-merge supervisor failed — stopping loop")
            break
        # Clear the explicit routing record arg so next iteration loads fresh
        args.routing_record = None

    return 0 if result.get("status") in ("success", "held", "stopped", "not_implemented") else 1


if __name__ == "__main__":
    sys.exit(main())
