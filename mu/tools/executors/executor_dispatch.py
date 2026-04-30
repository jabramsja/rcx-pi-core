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
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent  # mu/tools/executors -> repo root
AGENTS_DIR = SCRIPT_DIR.parent / "agents"
POST_MERGE_PACKAGE_NAME = "post_merge_package.json"

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        DEFAULT_EXECUTOR_CONFIG,
        agent_bus_path,
        agent_bus_relpath,
        load_executor_config as _common_load_executor_config,
        load_routing_record as _common_load_routing_record,
        build_and_write_routing_record as _common_build_and_write_routing_record,
        ROUTING_RECORD_PATH as _COMMON_ROUTING_RECORD_PATH,
        merge_executor_config_overrides,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        emit_pipeline_agent_event,
        normalize_wave_id,
        process_descendants,
        resolve_agent_bus_dir,
        routing_record_path as _common_routing_record_path,
        terminate_process_tree,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    DEFAULT_EXECUTOR_CONFIG = _mod.DEFAULT_EXECUTOR_CONFIG
    agent_bus_path = _mod.agent_bus_path
    agent_bus_relpath = _mod.agent_bus_relpath
    _common_load_executor_config = _mod.load_executor_config
    _common_load_routing_record = _mod.load_routing_record
    _common_build_and_write_routing_record = _mod.build_and_write_routing_record
    _COMMON_ROUTING_RECORD_PATH = _mod.ROUTING_RECORD_PATH
    merge_executor_config_overrides = _mod.merge_executor_config_overrides
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError
    emit_pipeline_agent_event = _mod.emit_pipeline_agent_event
    normalize_wave_id = _mod.normalize_wave_id
    process_descendants = _mod.process_descendants
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir
    _common_routing_record_path = _mod.routing_record_path
    terminate_process_tree = _mod.terminate_process_tree

try:
    from recovery_gate import attempt_recovery, clear_stale_recovery_status_on_success
except ImportError:
    import importlib.util as _ilu
    _recovery_path = SCRIPT_DIR / "recovery_gate.py"
    _recovery_spec = _ilu.spec_from_file_location("recovery_gate", str(_recovery_path))
    _recovery_mod = _ilu.module_from_spec(_recovery_spec)
    assert _recovery_spec.loader is not None
    sys.modules["recovery_gate"] = _recovery_mod
    _recovery_spec.loader.exec_module(_recovery_mod)
    attempt_recovery = _recovery_mod.attempt_recovery
    clear_stale_recovery_status_on_success = _recovery_mod.clear_stale_recovery_status_on_success

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
_TERMINAL_EXECUTOR_STATUSES = frozenset({
    "question_for_founder",
    "max_rounds_reached",
    "supervisor_rejected",
})

# Available executor scripts
AVAILABLE_EXECUTORS = {"commit_executor", "phase_b_executor", "phase_a_executor", "dialectic_executor"}
_JSON_EXECUTORS = frozenset({"commit_executor", "phase_b_executor", "phase_a_executor"})
SURFACE_COMMANDS = {
    "phase-a",
    "phase-b",
    "pre-commit-supervisor",
    "commit",
    "post-merge-supervisor",
}


def _emit_executor_hard_fail_event(
    repo_root: Path,
    result: dict[str, Any],
    wave_id: str,
    record: dict[str, Any] | None = None,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Emit the dispatcher-owned terminal failure event from recovery facts."""
    record = record or {}
    recovery = result.get("recovery")
    recovery = recovery if isinstance(recovery, dict) else {}
    executor_name = str(result.get("executor") or result.get("step") or "dispatcher")
    status = str(result.get("status") or "failed")
    decision = str(result.get("decision") or record.get("decision") or "unknown")
    failure_class = str(recovery.get("failure_class") or result.get("failure_class") or "unknown")
    outcome = str(recovery.get("outcome") or recovery.get("action") or "terminal")
    normalized_wave_id = normalize_wave_id(
        wave_id
        or str(record.get("wave_name") or record.get("wave_id") or "")
        or str(result.get("wave_id") or result.get("wave_name") or "")
    )
    transition_key = ":".join([
        normalized_wave_id,
        executor_name,
        status,
        decision,
        failure_class,
        outcome,
    ])
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=bus_dir,
        event_type="executor_hard_fail",
        wave_id=normalized_wave_id,
        task_id=str(
            result.get("task_id")
            or record.get("task_id")
            or "[PIPELINE-RECOVERY]"
        ).strip(),
        plan_path=str(record.get("tracked_packet") or result.get("plan_path") or ""),
        phase="executor_dispatch",
        state=status,
        transition_key=transition_key,
        summary=f"{executor_name} failed after dispatcher recovery handling",
        reason=str(result.get("message") or result.get("summary") or failure_class),
        artifact_paths={},
    )

DEFAULT_CONFIG_PATH = SCRIPT_DIR / "executor_config.json"
PHASE_B_RECOVERY_PLAN_ENV = "RCX_RECOVERY_PHASE_B_PLAN_PATH"


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


def load_routing_record(
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load and validate the post-merge routing record.

    Delegates to executor_common.load_routing_record (canonical implementation).
    Wraps ExecutorCommonError as DispatchError for backward compatibility.
    """
    try:
        return _common_load_routing_record(repo_root, bus_dir=bus_dir)
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


def _canonical_routing_record_path(repo_root: Path, bus_dir: str | Path | None = None) -> Path:
    return _common_routing_record_path(repo_root, bus_dir).resolve()


def _load_routing_record_json(path: Path) -> dict[str, Any] | None:
    """Best-effort JSON object load without imposing freshness validation."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _matches_canonical_routing_record(
    record: dict[str, Any],
    repo_root: Path,
    bus_dir: str | Path | None = None,
) -> bool:
    """Return True when the inline record still matches the canonical routing file."""
    canonical_record = _load_routing_record_json(_canonical_routing_record_path(repo_root, bus_dir))
    return canonical_record == record


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


def _canonicalize_surface_task_id(task_id: str) -> str:
    """Normalize surface CLI task IDs into bracketed TASKS.md token form."""
    clean = str(task_id or "").strip()
    if not clean:
        return ""
    if clean.startswith("[") and clean.endswith("]"):
        return clean
    return f"[{clean}]"


def _surface_phase_b_plan_from_routing_payload(routing_payload: str | None) -> str | None:
    """Prefer tracked_packet from a Phase B routing payload when no explicit plan is given."""
    if not routing_payload:
        return None
    try:
        record = json.loads(routing_payload)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(record, dict):
        return None
    candidates = record.get("next_candidates")
    if not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        tracked_packet = str(candidate.get("tracked_packet") or "").strip()
        if tracked_packet:
            return tracked_packet
    return None


def _routing_record_tracked_packet(record: dict[str, Any]) -> str:
    candidates = record.get("next_candidates")
    if not isinstance(candidates, list):
        return ""
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        tracked_packet = str(candidate.get("tracked_packet") or "").strip()
        if tracked_packet:
            return tracked_packet
    return ""


def _phase_b_plan_declared_wave_id(repo_root: Path, plan_path: str) -> str:
    """Read an explicit Wave ID from a Phase B plan, without stem fallback."""
    clean_path = str(plan_path or "").strip()
    if not clean_path:
        return ""
    candidate = Path(clean_path)
    try:
        if candidate.is_absolute():
            full_path = candidate.resolve()
        else:
            if ".." in candidate.parts:
                return ""
            full_path = (repo_root / clean_path).resolve()
        if not full_path.is_relative_to(repo_root.resolve()):
            return ""
        content = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for raw_line in content.splitlines():
        clean = raw_line.strip()
        lower = clean.lower()
        if lower.startswith("wave id:") or lower.startswith("wave_id:"):
            value = clean.split(":", 1)[1].strip()
            if value:
                return normalize_wave_id(value)
    return ""


def _phase_b_plan_wave_id(repo_root: Path, plan_path: str) -> str:
    """Resolve the wave id Phase B will use for an explicit plan path."""
    clean_path = str(plan_path or "").strip()
    if not clean_path:
        return ""
    declared = _phase_b_plan_declared_wave_id(repo_root, clean_path)
    if declared:
        return declared
    fallback = normalize_wave_id(Path(clean_path).stem)
    return fallback


def _phase_b_plan_routing_packet(repo_root: Path, plan_path: str) -> str:
    """Return the repo-relative tracked packet path for chained routing."""
    clean_path = str(plan_path or "").strip()
    if not clean_path:
        return ""
    candidate = Path(clean_path)
    try:
        if candidate.is_absolute():
            full_path = candidate.resolve()
        else:
            if ".." in candidate.parts:
                return clean_path
            full_path = (repo_root / clean_path).resolve()
        repo_resolved = repo_root.resolve()
        if full_path.is_relative_to(repo_resolved):
            return full_path.relative_to(repo_resolved).as_posix()
    except OSError:
        return clean_path
    return clean_path


def _surface_record_for_chain(
    args: argparse.Namespace,
    repo_root: Path,
) -> dict[str, Any]:
    """Build the identity record used for surface retry handoff validation."""
    decision = _surface_decision(args)
    canonical_task_id = _canonicalize_surface_task_id(getattr(args, "task_id", ""))
    record: dict[str, Any] = {
        "decision": decision,
        "wave_name": _surface_wave_id(args, repo_root),
        "task_id": canonical_task_id,
    }
    if args.surface == "phase-a":
        summary = str(getattr(args, "summary", "") or "").strip()
        request = str(getattr(args, "request_for_claude", "") or "").strip()
        if summary:
            record["summary"] = summary
        if request:
            record["request_for_claude"] = request
        record["next_candidates"] = [
            {
                "candidate": record["wave_name"],
                "bounded": True,
            }
        ]
    if args.surface != "phase-b":
        return record

    routing_payload = _load_routing_record_payload(
        path_value=args.routing_record_path,
        json_value=args.routing_record_json,
    )
    if routing_payload:
        try:
            parsed = json.loads(routing_payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            parsed = None
        if isinstance(parsed, dict):
            record.update(parsed)
            record["decision"] = str(record.get("decision") or decision)
            if canonical_task_id:
                record["task_id"] = canonical_task_id

    plan_path = (
        getattr(args, "plan", None)
        or _surface_phase_b_plan_from_routing_payload(routing_payload)
        or os.environ.get(PHASE_B_RECOVERY_PLAN_ENV, "").strip()
    )
    if plan_path:
        if not _routing_record_tracked_packet(record):
            record["next_candidates"] = [{"tracked_packet": plan_path}]
        wave_name = str(record.get("wave_name") or record.get("wave_id") or "").strip()
        if not wave_name or normalize_wave_id(wave_name) == "wave-unknown":
            plan_wave_id = _phase_b_plan_wave_id(repo_root, plan_path)
            if plan_wave_id:
                record["wave_name"] = plan_wave_id
    return record


def _phase_a_surface_record_for_persistence(
    repo_root: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    persisted = dict(record)
    persisted["decision"] = str(persisted.get("decision") or "ROUTE_PHASE_A")
    persisted["summary"] = str(persisted.get("summary") or "")
    persisted["request_for_claude"] = str(persisted.get("request_for_claude") or "")
    wave_name = str(persisted.get("wave_name") or persisted.get("wave_id") or "").strip()
    if wave_name and not isinstance(persisted.get("next_candidates"), list):
        persisted["next_candidates"] = [{"candidate": wave_name, "bounded": True}]

    try:
        repo_state = _compute_repo_state(repo_root)
    except Exception:
        return persisted
    persisted.setdefault("head_sha", repo_state.head_sha)
    persisted["state_sha"] = repo_state.state_sha
    return persisted


def _persist_phase_a_surface_routing_record(
    repo_root: Path,
    record: dict[str, Any],
    *,
    bus_dir: str | Path | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    persisted = _phase_a_surface_record_for_persistence(repo_root, record)
    target_path = _canonical_routing_record_path(repo_root, bus_dir)
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ControlSurfaceError(
            f"Cannot persist Phase A routing context to {target_path}: {exc}"
        ) from exc
    if verbose:
        print(f"[dispatch] Persisted Phase A routing context: {target_path}")
    return persisted


def build_surface_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Modular control-plane entrypoint for executors and supervisors",
    )
    sub = parser.add_subparsers(dest="surface", required=True)

    phase_a = sub.add_parser("phase-a", help="Run Phase A executor")
    phase_a.add_argument("--plan-name", required=True, help="Plan packet slug")
    phase_a.add_argument(
        "--task-id",
        default="",
        help="TASKS.md task ID (e.g. [PIPELINE-RECOVERY] or PIPELINE-RECOVERY). Propagated to Phase B and commit handoff.",
    )
    phase_a.add_argument(
        "--summary",
        default="",
        help="Short Phase A scope summary. Used to seed the routing context passed to phase_a_executor.",
    )
    phase_a.add_argument(
        "--request-for-claude",
        default="",
        help="Detailed Phase A request. Used to seed the routing context passed to phase_a_executor.",
    )
    phase_a.add_argument("--max-rounds", type=int, default=15)
    phase_a.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    phase_a.add_argument("-v", "--verbose", action="store_true")
    phase_a.add_argument("--json", action="store_true")

    phase_b = sub.add_parser("phase-b", help="Run Phase B executor")
    phase_b.add_argument("--plan", default=None, help="Locked plan packet path")
    phase_b.add_argument(
        "--task-id",
        default="",
        help="TASKS.md task ID (e.g. [PIPELINE-RECOVERY] or PIPELINE-RECOVERY). Used in commit handoff.",
    )
    phase_b.add_argument("--routing-record-path", type=Path, help="Path to routing record JSON")
    phase_b.add_argument("--routing-record-json", help="Routing record JSON string")
    phase_b.add_argument("--max-rounds", type=int, default=10)
    phase_b.add_argument("--bootstrap-exception", action="store_true")
    phase_b.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    phase_b.add_argument("-v", "--verbose", action="store_true")
    phase_b.add_argument("--json", action="store_true")

    pre_commit = sub.add_parser("pre-commit-supervisor", help="Run pre-commit supervisor")
    pre_commit.add_argument("--package", type=Path, required=True)
    pre_commit.add_argument("--dry-run", action="store_true")
    pre_commit.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    pre_commit.add_argument("-v", "--verbose", action="store_true")
    pre_commit.add_argument("--json", action="store_true")

    commit = sub.add_parser("commit", help="Run commit executor")
    commit.add_argument("--handoff", type=Path, help="Path to handoff JSON")
    commit.add_argument("--routing-record-path", type=Path, help="Path to routing record JSON")
    commit.add_argument("--routing-record-json", help="Routing record JSON string")
    commit.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    commit.add_argument("-v", "--verbose", action="store_true")
    commit.add_argument("--json", action="store_true")

    post_merge = sub.add_parser("post-merge-supervisor", help="Run post-merge supervisor")
    post_merge.add_argument("--package", type=Path, required=True)
    post_merge.add_argument("--bus-dir", default=None, help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)")
    post_merge.add_argument("-v", "--verbose", action="store_true")
    post_merge.add_argument("--json", action="store_true")

    return parser


def build_surface_command(
    args: argparse.Namespace,
    *,
    routing_record: dict[str, Any] | None = None,
) -> list[str]:
    canonical_task_id = _canonicalize_surface_task_id(getattr(args, "task_id", ""))
    if args.surface == "phase-a":
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "phase_a_executor.py"),
            "--plan-name",
            args.plan_name,
            "--max-rounds",
            str(args.max_rounds),
        ]
        if routing_record is not None:
            cmd.extend(["--routing-record", json.dumps(routing_record)])
    elif args.surface == "phase-b":
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "phase_b_executor.py"),
            "--max-rounds",
            str(args.max_rounds),
            "--dispatcher-owned-recovery",
        ]
        routing_payload = (
            json.dumps(routing_record)
            if routing_record is not None
            else _load_routing_record_payload(
                path_value=args.routing_record_path,
                json_value=args.routing_record_json,
            )
        )
        recovery_plan_path = os.environ.get(PHASE_B_RECOVERY_PLAN_ENV, "").strip()
        plan_path = (
            args.plan
            or _surface_phase_b_plan_from_routing_payload(routing_payload)
            or recovery_plan_path
        )
        if plan_path:
            cmd.extend(["--plan", plan_path])
        if routing_payload:
            cmd.extend(["--routing-record", routing_payload])
        if args.bootstrap_exception:
            cmd.append("--bootstrap-exception")
        if canonical_task_id:
            cmd.extend(["--task-id", canonical_task_id])
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

    if getattr(args, "bus_dir", None):
        cmd.extend(["--bus-dir", str(args.bus_dir)])
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


def _surface_wave_id(args: argparse.Namespace, repo_root: Path) -> str:
    """Derive a stable wave_id for recoverable surface invocations."""
    if args.surface == "phase-a":
        return normalize_wave_id(args.plan_name)
    if args.surface == "phase-b":
        payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if payload:
            try:
                record = json.loads(payload)
                wave_name = record.get("wave_name") or record.get("wave_id", "")
                if isinstance(wave_name, str) and wave_name.strip():
                    return normalize_wave_id(wave_name)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        if args.plan:
            return _phase_b_plan_wave_id(repo_root, args.plan)
    if args.surface == "commit":
        if args.handoff:
            try:
                handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
                wave_id = handoff.get("wave_id")
                if isinstance(wave_id, str) and wave_id.strip():
                    return normalize_wave_id(wave_id)
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
            return normalize_wave_id(args.handoff.stem)
        payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if payload:
            try:
                record = json.loads(payload)
                wave_name = record.get("wave_name") or record.get("wave_id", "")
                if isinstance(wave_name, str) and wave_name.strip():
                    return normalize_wave_id(wave_name)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return "wave-unknown"


def _surface_decision(args: argparse.Namespace) -> str:
    """Derive the logical dispatcher decision for a modular surface invocation."""
    if args.surface == "phase-a":
        return "ROUTE_PHASE_A"
    if args.surface == "phase-b":
        return "ROUTE_PHASE_B"
    if args.surface == "commit":
        payload = _load_routing_record_payload(
            path_value=args.routing_record_path,
            json_value=args.routing_record_json,
        )
        if payload:
            try:
                record = json.loads(payload)
                decision = record.get("decision")
                if isinstance(decision, str) and decision.strip():
                    return decision
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return "COMMIT_GO"
    raise ControlSurfaceError(f"Unsupported recoverable surface: {args.surface}")


def _reload_explicit_routing_record(
    path: Path | None,
    *,
    verbose: bool = False,
) -> dict[str, Any] | None:
    """Best-effort reload for caller-owned routing files between retries."""
    if path is None:
        return None
    record = _load_routing_record_json(path)
    if record is None and verbose:
        print(f"[dispatch] Explicit routing reload skipped: could not parse {path}")
    return record


def run_recoverable_surface_command(
    args: argparse.Namespace,
    *,
    repo_root: Path,
    config: dict[str, Any],
) -> int:
    """Run recoverable control surfaces through the dispatcher recovery gate."""
    bus_dir = getattr(args, "bus_dir", None)
    if bus_dir is not None:
        resolve_agent_bus_dir(repo_root, bus_dir)
    executor_name = {
        "phase-a": "phase_a_executor",
        "phase-b": "phase_b_executor",
        "commit": "commit_executor",
    }[args.surface]
    decision = _surface_decision(args)
    surface_record = _surface_record_for_chain(args, repo_root)
    wave_id = normalize_wave_id(
        str(surface_record.get("wave_name") or surface_record.get("wave_id") or "")
    )
    if not wave_id:
        wave_id = _surface_wave_id(args, repo_root)
    original_timeouts = None
    result: dict[str, Any] | None = None

    try:
        while True:
            if result is not None and _is_chained_commit_failure(result):
                retried = _retry_commit_only(
                    repo_root,
                    config,
                    verbose=getattr(args, "verbose", False),
                    bus_dir=bus_dir,
                )
                if retried.get("stdout"):
                    sys.stdout.write(retried["stdout"])
                if retried.get("stderr"):
                    sys.stderr.write(retried["stderr"])
                if retried.get("status") in {"success", "held"}:
                    return 0
                result = retried
            else:
                surface_record = _surface_record_for_chain(args, repo_root)
                decision = str(surface_record.get("decision") or decision)
                wave_id = normalize_wave_id(
                    str(surface_record.get("wave_name") or surface_record.get("wave_id") or wave_id)
                )
                if args.surface == "phase-a":
                    surface_record = _persist_phase_a_surface_routing_record(
                        repo_root,
                        surface_record,
                        bus_dir=bus_dir,
                        verbose=getattr(args, "verbose", False),
                    )
                cmd = build_surface_command(args, routing_record=surface_record)
                _default_timeout = DEFAULT_EXECUTOR_CONFIG["timeouts"].get(executor_name, 600)
                timeout = config.get("timeouts", {}).get(executor_name, _default_timeout)
                try:
                    completed = _run_executor_in_group(cmd, cwd=repo_root, timeout=timeout)
                    _emit_completed_process_output(completed)
                    if executor_name == "commit_executor":
                        if completed.returncode != 0:
                            result = {
                                "status": "failed",
                                "decision": decision,
                                "executor": executor_name,
                                "step": args.surface.replace("-", "_"),
                                "exit_code": completed.returncode,
                                "stdout": completed.stdout,
                                "stderr": completed.stderr,
                            }
                        else:
                            c_status, c_decision = _classify_commit_executor_result(completed)
                            if c_status in {"success", "held"}:
                                return 0
                            result = {
                                "status": c_status,
                                "decision": c_decision,
                                "executor": executor_name,
                                "step": args.surface.replace("-", "_"),
                                "exit_code": completed.returncode,
                                "stdout": completed.stdout,
                                "stderr": completed.stderr,
                            }
                    elif completed.returncode == 0:
                        result = _continue_successful_executor_chain(
                            executor_name,
                            completed,
                            repo_root=repo_root,
                            config=config,
                            record=surface_record,
                            verbose=getattr(args, "verbose", False),
                            emit_output=True,
                            bus_dir=bus_dir,
                        )
                        if result.get("status") in {"success", "held"}:
                            return 0
                    else:
                        result = {
                            "status": "failed",
                            "decision": decision,
                            "executor": executor_name,
                            "step": args.surface.replace("-", "_"),
                            "exit_code": completed.returncode,
                            "stdout": completed.stdout,
                            "stderr": completed.stderr,
                        }
                except subprocess.TimeoutExpired:
                    result = {
                        "status": "timeout",
                        "decision": decision,
                        "executor": executor_name,
                        "step": args.surface.replace("-", "_"),
                        "message": f"Executor {executor_name} timed out after {timeout}s",
                        "stdout": "",
                        "stderr": "",
                    }

            embedded_recovery = result.get("recovery")
            if isinstance(embedded_recovery, dict) and embedded_recovery.get("recovered"):
                if getattr(args, "verbose", False):
                    print(
                        "[dispatch] Surface Phase B recovered in-process — "
                        "retrying before commit chain"
                    )
                _clear_phase_b_state_for_retry(
                    repo_root, result, verbose=getattr(args, "verbose", False), bus_dir=bus_dir
                )
                continue

            if result.get("status") == "failed" and _is_terminal_executor_outcome(result):
                _emit_executor_hard_fail_event(repo_root, result, wave_id, surface_record, bus_dir=bus_dir)
                break

            recovery = attempt_recovery(repo_root, result, wave_id, bus_dir=bus_dir)
            result["recovery"] = recovery
            if getattr(args, "verbose", False):
                print(
                    f"[dispatch] Surface recovery: class={recovery.get('failure_class')} "
                    f"tier={recovery.get('tier')} recovered={recovery.get('recovered')}"
                )
            if not recovery.get("recovered"):
                _emit_executor_hard_fail_event(repo_root, result, wave_id, surface_record, bus_dir=bus_dir)
                break

            new_orig = _apply_recovery_overrides(
                config, repo_root=repo_root, verbose=getattr(args, "verbose", False))
            if original_timeouts is None:
                original_timeouts = new_orig
            _clear_phase_b_state_for_retry(repo_root, result, verbose=getattr(args, "verbose", False), bus_dir=bus_dir)

        return 1
    finally:
        if original_timeouts is not None:
            _restore_config_on_disk(
                repo_root, original_timeouts,
                verbose=getattr(args, "verbose", False),
            )
            config["timeouts"] = _recovery_original_section(original_timeouts, "timeouts")
            config["bridge_turn_timeouts"] = _recovery_original_section(
                original_timeouts, "bridge_turn_timeouts"
            )
        for env_key in list(os.environ):
            if env_key.startswith((
                "RCX_RECOVERY_ORIGINAL_TIMEOUT_",
                "RCX_RECOVERY_ORIGINAL_BRIDGE_TURN_TIMEOUT_",
                PHASE_B_RECOVERY_PLAN_ENV,
            )):
                os.environ.pop(env_key, None)


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

    expected_packet = _routing_record_tracked_packet(record)
    if expected_packet:
        scope_items = handoff.get("scope_items")
        actual_packet = handoff.get("tracked_packet")
        if not actual_packet and isinstance(scope_items, list):
            for item in scope_items:
                if isinstance(item, str) and item.strip() == expected_packet:
                    actual_packet = item.strip()
                    break
        if actual_packet != expected_packet:
            return False, (
                "Phase B handoff tracked_packet mismatch: "
                f"expected {expected_packet}, got {actual_packet}"
            )

    return True, "ok"


def _phase_b_tracked_plan_or_error(
    repo: Path,
    record: dict[str, Any],
    *,
    include_recovery_env: bool = False,
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve a Phase B tracked packet path, optionally from recovery env."""
    for candidate in record.get("next_candidates", []):
        if not isinstance(candidate, dict):
            continue
        tracked_packet = candidate.get("tracked_packet")
        if tracked_packet and isinstance(tracked_packet, str):
            plan_path = tracked_packet
            break
    else:
        plan_path = None

    if not plan_path and include_recovery_env:
        plan_path = os.environ.get(PHASE_B_RECOVERY_PLAN_ENV, "").strip() or None
    if not plan_path:
        return None, None

    plan_resolved = (repo / plan_path).resolve()
    if Path(plan_path).is_absolute() or ".." in Path(plan_path).parts:
        return None, {
            "status": "error",
            "decision": record.get("decision", ""),
            "executor": "phase_b_executor",
            "message": f"Path traversal in tracked_packet: {plan_path}",
        }
    if not plan_resolved.is_relative_to(repo.resolve()):
        return None, {
            "status": "error",
            "decision": record.get("decision", ""),
            "executor": "phase_b_executor",
            "message": f"tracked_packet escapes repo root: {plan_path}",
        }
    return plan_path, None


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
    try:
        payload = json.loads(stdout)
        if isinstance(payload, dict):
            status = payload.get("status")
            if status == "held":
                return "held", "COMMIT_HELD"
            if status == "success":
                return "success", "COMMIT_GO"
            if status in {"error", "failed", "timeout"}:
                return "failed", "COMMIT_GO"
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if not isinstance(payload, dict):
            continue
        status = payload.get("status")
        if status == "held":
            return "held", "COMMIT_HELD"
        if status == "success":
            return "success", "COMMIT_GO"
        if status in {"error", "failed", "timeout"}:
            return "failed", "COMMIT_GO"
    if "[commit-executor] Status: held" in stdout:
        return "held", "COMMIT_HELD"
    if "[commit-executor] Status: error" in stdout:
        return "failed", "COMMIT_GO"
    return "success", "COMMIT_GO"


def _extract_structured_stdout_payload(stdout: str) -> dict[str, Any] | None:
    """Best-effort decode of executor stdout JSON."""
    if not stdout:
        return None
    try:
        payload = json.loads(stdout)
        if isinstance(payload, dict):
            return payload
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None

def _parse_worktree_list(output: str) -> list[dict[str, str]]:
    """Parse `git worktree list --porcelain` into entry dicts."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            if current:
                entries.append(current)
                current = {}
            current["worktree"] = value
            continue
        current[key] = value or "true"
    if current:
        entries.append(current)
    return entries


def resolve_repo_root_for_dispatch(*, verbose: bool = False) -> Path:
    """Resolve the active worktree root for dispatcher execution.

    When invoked from the bare/common git dir, fall back to a linked worktree
    for the current branch if and only if exactly one exists.
    """
    try:
        top_level = Path(subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip())
        inside_work_tree = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, check=False,
        )
        is_bare = subprocess.run(
            ["git", "rev-parse", "--is-bare-repository"],
            capture_output=True, text=True, check=False,
        )
        if (
            inside_work_tree.returncode == 0
            and inside_work_tree.stdout.strip() == "true"
            and not (
                is_bare.returncode == 0
                and is_bare.stdout.strip() == "true"
            )
        ):
            return top_level
    except subprocess.CalledProcessError:
        pass

    branch_proc = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    if branch_proc.returncode != 0 or not branch_proc.stdout.strip():
        raise DispatchError(
            "Not in a git worktree, and no current branch is available to resolve a linked worktree"
        )
    branch = branch_proc.stdout.strip()

    worktree_proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True, text=True, check=False,
    )
    if worktree_proc.returncode != 0:
        raise DispatchError(
            "Not in a git worktree, and linked worktrees could not be enumerated"
        )

    target_ref = f"refs/heads/{branch}"
    matches = [
        Path(entry["worktree"])
        for entry in _parse_worktree_list(worktree_proc.stdout)
        if entry.get("worktree")
        and entry.get("bare") != "true"
        and entry.get("branch") == target_ref
    ]
    if len(matches) == 1:
        if verbose:
            print(
                f"[dispatch] Resolved linked worktree for branch {branch}: {matches[0]}",
                file=sys.stderr,
            )
        return matches[0]
    if not matches:
        raise DispatchError(
            "Current repository is a bare/common git dir. Run from a linked worktree "
            f"or create one for {branch!r} with `git worktree add <path> {branch}`."
        )
    match_list = ", ".join(str(path) for path in matches)
    raise DispatchError(
        f"Multiple linked worktrees found for branch {branch!r}: {match_list}. "
        "Run the dispatcher from the intended linked worktree."
    )
def _emit_completed_process_output(
    completed: subprocess.CompletedProcess[str],
) -> None:
    """Mirror a completed subprocess's captured output to the caller."""
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)


def _continue_successful_executor_chain(
    executor_name: str,
    completed: subprocess.CompletedProcess[str],
    *,
    repo_root: Path,
    config: dict[str, Any],
    record: dict[str, Any] | None = None,
    verbose: bool = False,
    emit_output: bool = False,
    chain_origin: str | None = None,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Continue the A→B→commit chain after a successful executor leg."""
    if executor_name == "phase_a_executor":
        plan_path = _extract_plan_path(completed.stdout, repo_root)
        if plan_path is None:
            return {
                "status": "failed",
                "decision": "ROUTE_PHASE_A",
                "executor": executor_name,
                "exit_code": 0,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "message": "Phase A converged but no plan_path found in output",
            }

        if verbose:
            print(f"[dispatch] Phase A converged → chaining to Phase B with plan: {plan_path}")

        phase_b_wave_name = (record or {}).get("wave_name", "")
        plan_wave_id = _phase_b_plan_declared_wave_id(repo_root, plan_path)
        if plan_wave_id:
            # The surface plan name can omit the dated wave suffix; commit
            # identity must follow the converged locked packet Phase B uses.
            phase_b_wave_name = plan_wave_id
        phase_b_candidates = list((record or {}).get("next_candidates", []))
        if plan_wave_id and not _routing_record_tracked_packet(
            {"next_candidates": phase_b_candidates}
        ):
            phase_b_candidates = [
                {"tracked_packet": _phase_b_plan_routing_packet(repo_root, plan_path)}
            ]

        phase_b_timeout = config.get("timeouts", {}).get("phase_b_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["phase_b_executor"])
        phase_b_routing = {
            "decision": "ROUTE_PHASE_B",
            "wave_name": phase_b_wave_name,
            "task_id": (record or {}).get("task_id", ""),
            "summary": "Chained from Phase A convergence",
            "next_candidates": phase_b_candidates,
        }
        phase_b_args = [
            sys.executable,
            str(SCRIPT_DIR / "phase_b_executor.py"),
            "--plan", plan_path,
            "--routing-record", json.dumps(phase_b_routing),
            "--dispatcher-owned-recovery",
            "--json",
        ]
        if bus_dir is not None:
            phase_b_args.extend(["--bus-dir", str(bus_dir)])
        try:
            phase_b_result = _run_executor_in_group(
                phase_b_args, cwd=repo_root, timeout=phase_b_timeout,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "decision": "ROUTE_PHASE_B",
                "executor": "phase_b_executor",
                "message": f"Phase B executor timed out after {phase_b_timeout}s",
                "chained_from": "phase_a_executor",
            }
        if emit_output:
            _emit_completed_process_output(phase_b_result)
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
        return _continue_successful_executor_chain(
            "phase_b_executor",
            phase_b_result,
            repo_root=repo_root,
            config=config,
            record=phase_b_routing,
            verbose=verbose,
            emit_output=emit_output,
            chain_origin="phase_a_executor",
            bus_dir=bus_dir,
        )

    if executor_name == "phase_b_executor":
        handoff_path = agent_bus_path(repo_root, bus_dir, "executors", "phase_b_handoff.json")
        if not handoff_path.exists():
            origin = chain_origin or "phase_b_executor"
            payload = _extract_structured_stdout_payload(completed.stdout or "")
            if isinstance(payload, dict):
                recovery = payload.get("recovery")
                status = payload.get("status")
                if (
                    isinstance(recovery, dict)
                    and recovery.get("recovered")
                    and status not in {"success", "ready", "commit_ready"}
                ):
                    return {
                        "status": "failed",
                        "decision": "ROUTE_PHASE_B",
                        "executor": executor_name,
                        "exit_code": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                        "message": (
                            "Phase B recovered in-process and must be retried "
                            "before chaining commit"
                        ),
                        "recovery": recovery,
                        "chained_from": (
                            "phase_a_executor" if origin == "phase_a_executor" else None
                        ),
                    }
                if status not in {None, "success", "ready", "commit_ready"}:
                    return {
                        "status": "failed",
                        "decision": "ROUTE_PHASE_B",
                        "executor": executor_name,
                        "exit_code": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                        "message": (
                            f"Phase B exited 0 with status {status} but produced no handoff"
                        ),
                        "chained_from": (
                            "phase_a_executor" if origin == "phase_a_executor" else None
                        ),
                    }
            return {
                "status": "failed",
                "decision": "ROUTE_PHASE_B",
                "executor": executor_name,
                "exit_code": 0,
                "message": "Phase B converged but no handoff file found",
                "chained_from": (
                    "phase_a_executor" if origin == "phase_a_executor" else None
                ),
            }

        if record and (
            record.get("wave_name")
            or record.get("wave_id")
            or record.get("task_id")
            or _routing_record_tracked_packet(record)
        ):
            valid_handoff, handoff_msg = _validate_phase_b_handoff_identity(
                handoff_path, record
            )
            if not valid_handoff:
                origin = chain_origin or "phase_b_executor"
                return {
                    "status": "error",
                    "decision": "COMMIT_GO",
                    "executor": "commit_executor",
                    "message": f"Phase B handoff validation failed: {handoff_msg}",
                    "chained_from": (
                        "phase_a_executor → phase_b_executor"
                        if origin == "phase_a_executor"
                        else "phase_b_executor"
                    ),
                }

        if verbose:
            print("[dispatch] Phase B converged → chaining to commit executor")

        commit_timeout = config.get("timeouts", {}).get("commit_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_executor"])
        commit_args = [
            sys.executable,
            str(SCRIPT_DIR / "commit_executor.py"),
            "--handoff", str(handoff_path),
            "--json",
        ]
        if bus_dir is not None:
            commit_args.extend(["--bus-dir", str(bus_dir)])
        try:
            commit_result = _run_executor_in_group(
                commit_args, cwd=repo_root, timeout=commit_timeout,
            )
        except subprocess.TimeoutExpired:
            origin = chain_origin or "phase_b_executor"
            return {
                "status": "timeout",
                "decision": "COMMIT_GO",
                "executor": "commit_executor",
                "message": f"Commit executor timed out after {commit_timeout}s",
                "chained_from": (
                    "phase_a_executor → phase_b_executor"
                    if origin == "phase_a_executor"
                    else "phase_b_executor"
                ),
            }
        if emit_output:
            _emit_completed_process_output(commit_result)
        c_status, c_decision = _classify_commit_executor_result(commit_result)
        origin = chain_origin or "phase_b_executor"
        return {
            "status": c_status,
            "decision": c_decision,
            "executor": "commit_executor",
            "exit_code": commit_result.returncode,
            "stdout": commit_result.stdout,
            "stderr": commit_result.stderr,
            "chained_from": (
                "phase_a_executor → phase_b_executor"
                if origin == "phase_a_executor"
                else "phase_b_executor"
            ),
        }

    nc_status, nc_decision = ("success", record.get("decision", "") if record else "")
    if executor_name == "commit_executor":
        nc_status, nc_decision = _classify_commit_executor_result(completed)
    return {
        "status": nc_status,
        "decision": nc_decision,
        "executor": executor_name,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _run_executor_in_group(
    args: list[str],
    cwd: Path,
    timeout: int | float,
) -> subprocess.CompletedProcess[str]:
    """Run an executor subprocess in its own process group.

    On timeout, kills the entire process group (including grandchildren)
    before raising TimeoutExpired.  This prevents orphaned worker
    subprocesses from persisting across retry attempts.
    """
    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    previous_handlers = {
        signum: signal.getsignal(signum)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }

    def _cleanup_for_signal(signum: int, _frame: Any) -> None:
        try:
            terminate_process_tree(proc.pid, cwd=cwd)
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass
        if signum == signal.SIGINT:
            raise KeyboardInterrupt()
        raise SystemExit(128 + signum)

    for signum in previous_handlers:
        signal.signal(signum, _cleanup_for_signal)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Collect the full descendant tree BEFORE killing the process group.
        # Children spawned with start_new_session=True (e.g. claude --print
        # via bridge_adapters.py:576) live in separate sessions and survive
        # os.killpg.  After killpg they get reparented to PID 1 and become
        # unreachable via PPID-tree walking.  Snapshot them first.
        try:
            pre_kill_descendants = process_descendants(proc.pid, cwd=cwd)
        except Exception:
            pre_kill_descendants = set()
        # Kill the process group (catches same-session children)
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except OSError:
            pass
        # Kill descendants from the pre-kill snapshot (catches cross-session children)
        for pid in sorted(pre_kill_descendants, reverse=True):
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        try:
            terminate_process_tree(proc.pid, cwd=cwd)
        except Exception:
            pass
        try:
            proc.kill()
        except OSError:
            pass
        proc.wait()
        raise
    except BaseException:
        try:
            terminate_process_tree(proc.pid, cwd=cwd)
        except Exception:
            pass
        try:
            proc.wait(timeout=1)
        except Exception:
            pass
        raise
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return subprocess.CompletedProcess(args, proc.returncode, stdout, stderr)


def _retry_commit_only(
    repo: Path,
    config: dict[str, Any],
    *,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Retry only the commit executor using the existing Phase B handoff.

    Used when a chained commit fails — avoids re-running Phase A/B.
    """
    handoff_path = agent_bus_path(repo, bus_dir, "executors", "phase_b_handoff.json")
    if not handoff_path.exists():
        return {
            "status": "error",
            "decision": "COMMIT_GO",
            "executor": "commit_executor",
            "message": f"Cannot retry commit: handoff file missing at {handoff_path}",
        }

    if verbose:
        print("[dispatch] Retrying commit executor only (Phase A/B already succeeded)")

    commit_timeout = config.get("timeouts", {}).get("commit_executor", DEFAULT_EXECUTOR_CONFIG["timeouts"]["commit_executor"])
    commit_args = [
        sys.executable,
        str(SCRIPT_DIR / "commit_executor.py"),
        "--handoff", str(handoff_path),
    ]
    if bus_dir is not None:
        commit_args.extend(["--bus-dir", str(bus_dir)])
    try:
        commit_result = _run_executor_in_group(
            commit_args, cwd=repo, timeout=commit_timeout,
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


def _apply_recovery_overrides(
    config: dict[str, Any],
    repo_root: Path | None = None,
    verbose: bool = False,
) -> dict[str, dict[str, Any]] | None:
    """Apply Tier 2 recovery env var overrides to config for retry.

    fix_process_timeout sets RCX_RECOVERY_TIMEOUT_OVERRIDE (and
    RCX_RECOVERY_TIMEOUT_KEY to target the correct executor timeout).
    fix_implementer_stale sets RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE.

    These are applied to the in-memory config dict AND written to
    executor_config.json on disk (when repo_root is provided) so that
    subprocesses which reload config from disk (e.g. phase_b_implementer)
    pick up the adjusted values.

    Returns original disk timeout sections if disk was modified (caller
    should pass to _restore_config_on_disk after retry), or None.
    """
    disk_config = None
    original_config = None
    config_path = None
    disk_modified = False

    if repo_root is not None:
        config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
        try:
            disk_config = json.loads(config_path.read_text(encoding="utf-8"))
            original_config = {
                "timeouts": dict(disk_config.get("timeouts", {})),
                "bridge_turn_timeouts": dict(disk_config.get("bridge_turn_timeouts", {})),
            }
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

    bridge_turn_timeout_override = os.environ.get("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE")
    if bridge_turn_timeout_override:
        try:
            val = int(bridge_turn_timeout_override)
            phase_key = os.environ.get("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY", "phase_b")
            config.setdefault("bridge_turn_timeouts", {})[phase_key] = val
            if disk_config is not None:
                disk_config.setdefault("bridge_turn_timeouts", {})[phase_key] = val
                disk_modified = True
            if verbose:
                print(
                    "[dispatch] Applied bridge turn timeout override: "
                    f"{phase_key}={val}s"
                )
        except ValueError:
            pass
        os.environ.pop("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE", None)
        os.environ.pop("RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY", None)

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

    return original_config if disk_modified else None


def _recovery_original_section(
    original_config: dict[str, Any],
    section: str,
) -> dict[str, Any]:
    """Return a timeout section from either current nested or legacy flat baselines."""
    if not isinstance(original_config, dict):
        return {}
    value = original_config.get(section)
    if isinstance(value, dict):
        return dict(value)
    if section == "timeouts":
        nested_section_keys = {"timeouts", "bridge_turn_timeouts"}
        if not any(isinstance(original_config.get(key), dict) for key in nested_section_keys):
            return dict(original_config)
    return {}


def _restore_config_on_disk(
    repo_root: Path,
    original_config: dict[str, dict[str, Any]],
    verbose: bool = False,
) -> None:
    """Restore original timeout sections to executor_config.json after recovery retry."""
    config_path = repo_root / "mu" / "tools" / "executors" / "executor_config.json"
    try:
        disk_config = json.loads(config_path.read_text(encoding="utf-8"))
        disk_config["timeouts"] = _recovery_original_section(original_config, "timeouts")
        disk_config["bridge_turn_timeouts"] = _recovery_original_section(
            original_config, "bridge_turn_timeouts"
        )
        config_path.write_text(
            json.dumps(disk_config, indent=2) + "\n", encoding="utf-8")
        if verbose:
            print("[dispatch] Restored original executor_config.json timeout sections")
    except (json.JSONDecodeError, OSError):
        pass


def _clear_phase_b_state_for_retry(
    repo_root: Path,
    result: dict[str, Any],
    *,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
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
    recovery = result.get("recovery")
    if (
        isinstance(recovery, dict)
        and recovery.get("recovered")
        and recovery.get("failure_class") == "post_reentry_needs_phase_b"
        and recovery.get("action") == "resume_phase_b_reentry"
    ):
        if verbose:
            print("[dispatch] Preserved recovery-seeded Phase B re-entry state before retry")
        return
    state_path = agent_bus_path(repo_root, bus_dir, "executors", "phase_b_state.json")
    if state_path.exists():
        state_path.unlink()
        if verbose:
            print("[dispatch] Cleared stale Phase B state before retry")


def _auto_refresh_routing(
    repo_root: Path,
    *,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Re-run the post-merge supervisor to refresh a stale routing record.

    Looks for the canonical post-merge package at .agent_bus/meta/post_merge_package.json.
    Returns (success, refreshed_record) — record is None on failure.
    """
    package_path = agent_bus_path(repo_root, bus_dir, "meta", POST_MERGE_PACKAGE_NAME)
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
    if bus_dir is not None:
        cmd.extend(["--bus-dir", str(bus_dir)])
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
        refreshed = _common_load_routing_record(repo_root, bus_dir=bus_dir)
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


def _refresh_canonical_routing_record_state(
    repo_root: Path,
    record: dict[str, Any],
    *,
    output_path: Path | None = None,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """Rebind the canonical packet-owned routing record to the current repo state."""
    tracked_packet = _routing_record_tracked_packet(record)
    if not tracked_packet:
        if verbose:
            print("[dispatch] Canonical routing rebind failed: no tracked_packet")
        return False, None

    refreshed, errors = _common_build_and_write_routing_record(
        wave_name=str(record.get("wave_name") or record.get("wave_id") or ""),
        task_id=str(record.get("task_id") or ""),
        tracked_packet=tracked_packet,
        request_for_claude=str(record.get("request_for_claude") or ""),
        summary=str(record.get("summary") or ""),
        decision=str(record.get("decision") or ""),
        merged_pr=record.get("merged_pr") if isinstance(record.get("merged_pr"), int) else None,
        merge_sha=record.get("merge_sha") if isinstance(record.get("merge_sha"), str) else None,
        repo_root=repo_root,
        output_path=output_path or _canonical_routing_record_path(repo_root, bus_dir),
        bus_dir=bus_dir,
    )
    if errors:
        if verbose:
            print("[dispatch] Canonical routing rebind failed: " + "; ".join(errors[:3]))
        return False, None

    fresh, msg = validate_routing_record_freshness(refreshed, repo_root)
    if not fresh:
        if verbose:
            print(f"[dispatch] Canonical routing rebind still stale: {msg}")
        return False, None

    if verbose:
        print(f"[dispatch] Canonical routing rebind succeeded: decision={refreshed.get('decision')}")
    return True, refreshed


def _extract_plan_path(phase_a_stdout: str, repo_root: Path) -> str | None:
    """Parse plan_path from Phase A executor output (JSON or text)."""
    decoder = json.JSONDecoder()
    cursor = 0
    while True:
        start = phase_a_stdout.find("{", cursor)
        if start == -1:
            break
        try:
            data, end = decoder.raw_decode(phase_a_stdout[start:])
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        pp = data.get("plan_path") if isinstance(data, dict) else None
        if isinstance(pp, str) and pp:
            return pp
        cursor = start + max(end, 1)
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
    routing_record_path: Path | None = None,
    skip_freshness: bool = False,
    verbose: bool = False,
    bus_dir: str | Path | None = None,
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
    try:
        resolve_agent_bus_dir(repo, bus_dir)
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "decision": record.get("decision", ""),
            "message": str(exc),
        }
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
            is_inline_caller_owned = (
                routing_record_path is None
                and not _matches_canonical_routing_record(record, repo, bus_dir)
            )
            is_noncanonical_explicit = (
                routing_record_path is not None
                and routing_record_path.resolve() != _canonical_routing_record_path(repo, bus_dir)
            )
            is_canonical_explicit = (
                routing_record_path is not None
                and routing_record_path.resolve() == _canonical_routing_record_path(repo, bus_dir)
            )
            if verbose:
                print(f"[dispatch] Routing record stale: {msg}")
                if is_noncanonical_explicit:
                    print(
                        "[dispatch] Explicit noncanonical routing record is caller-owned; "
                        "refusing in-place refresh."
                    )
                elif is_inline_caller_owned:
                    print(
                        "[dispatch] Inline routing record does not match the canonical "
                        "routing file; refusing implicit rebind."
                    )
                elif is_canonical_explicit:
                    print("[dispatch] Rebinding canonical routing record via builder...")
                else:
                    print("[dispatch] Auto-refreshing via post-merge supervisor...")
            if is_noncanonical_explicit:
                return {
                    "status": "stale",
                    "decision": decision,
                    "executor": executor_name,
                    "message": (
                        f"Routing record is stale: {msg}. Explicit noncanonical routing records are "
                        "caller-owned and must be regenerated from authoritative routing instead of "
                        f"being rewritten in place: {routing_record_path}"
                    ),
                }
            if is_inline_caller_owned:
                return {
                    "status": "stale",
                    "decision": decision,
                    "executor": executor_name,
                    "message": (
                        f"Routing record is stale: {msg}. Inline routing records that do not match "
                        "the canonical routing file are caller-owned and must be regenerated from "
                        "authoritative routing instead of being rebound implicitly."
                    ),
                }
            elif is_canonical_explicit:
                refreshed, refresh_record = _refresh_canonical_routing_record_state(
                    repo,
                    record,
                    output_path=routing_record_path,
                    verbose=verbose,
                    bus_dir=bus_dir,
                )
            else:
                refreshed, refresh_record = _auto_refresh_routing(repo, verbose=verbose, bus_dir=bus_dir)
            if not refreshed or refresh_record is None:
                refresh_message = (
                    "Explicit routing record rebind failed — refresh the packet-owned routing file."
                    if is_noncanonical_explicit
                    else "Auto-refresh failed — re-run post-merge supervisor manually."
                )
                return {
                    "status": "stale",
                    "decision": decision,
                    "executor": executor_name,
                    "message": f"Routing record is stale: {msg}. {refresh_message}",
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
        timeout = cfg.get("timeouts", {}).get(executor_name, DEFAULT_EXECUTOR_CONFIG["timeouts"].get(executor_name, 300))

        # Build executor-specific CLI args
        executor_args = [sys.executable, str(executor_path)]
        if executor_name == "commit_executor":
            # Only use a pre-prepared handoff for decisions that come from
            # Phase B/A (COMMIT_GO, COMMIT_GO_HOLD_PUSH).  UPDATE_TRACKER_ONLY
            # must always go through --routing-record so the commit executor
            # builds a tracker-only handoff from the live routing decision
            # instead of replaying a stale Phase B handoff file.
            handoff_path = agent_bus_path(repo, bus_dir, "executors", "phase_b_handoff.json")
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
            # Phase A needs --plan-name. When a candidate already declares a
            # tracked packet, prefer that canonical packet stem so Phase A
            # reuses the tracked file instead of minting a date-slug duplicate.
            candidates = record.get("next_candidates", [])
            plan_name = None
            for c in candidates:
                tp = c.get("tracked_packet")
                if tp and isinstance(tp, str):
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
                    plan_name = Path(tp).stem
                    break
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
            # then recovery-seeded --plan, then planless routing authority.
            executor_args.append("--dispatcher-owned-recovery")
            plan_path, plan_error = _phase_b_tracked_plan_or_error(
                repo,
                record,
                include_recovery_env=True,
            )
            if plan_error:
                return plan_error
            if plan_path:
                executor_args.extend(["--plan", plan_path])
                executor_args.extend(["--routing-record", json.dumps(record)])
            else:
                # Planless mode: Phase B derives scope from routing record.
                # The routing record must have wave_name, summary, and
                # next_candidates for this to succeed (fail-closed in Phase B).
                executor_args.extend(["--routing-record", json.dumps(record)])
        else:
            executor_args.extend(["--routing-record", json.dumps(record)])
        if executor_name in _JSON_EXECUTORS:
            executor_args.append("--json")
        if bus_dir is not None:
            executor_args.extend(["--bus-dir", str(bus_dir)])

        result = _run_executor_in_group(
            executor_args, cwd=repo, timeout=timeout,
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
        return _continue_successful_executor_chain(
            executor_name,
            result,
            repo_root=repo,
            config=cfg,
            record=record,
            verbose=verbose,
            bus_dir=bus_dir,
        )
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
            repo_root = resolve_repo_root_for_dispatch(verbose=getattr(args, "verbose", False))
        except DispatchError as exc:
            print(f"[error] {exc}", file=sys.stderr)
            return 1
        try:
            if args.surface in {"phase-a", "phase-b", "commit"}:
                config = load_config()
                return run_recoverable_surface_command(
                    args,
                    repo_root=repo_root,
                    config=config,
                )
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
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
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
    try:
        resolve_agent_bus_dir(repo_root, args.bus_dir)
    except ExecutorCommonError as exc:
        print(f"[error] Invalid --bus-dir: {exc}", file=sys.stderr)
        return 1

    # Enforce linked-worktree execution: the dispatcher must NOT run in the
    # primary worktree when it has dirty files.  Dirty files from interactive
    # work cause scope drift, stale state SHA, and supervisor rejections.
    # Create a fresh linked worktree from dev instead.
    # Skip in test environments (RCX_SKIP_WORKTREE_CHECK=1).
    skip_worktree_check = (
        os.environ.get("RCX_SKIP_WORKTREE_CHECK") == "1"
        or args.routing_record is not None  # explicit routing = caller owns scope
    )
    if not skip_worktree_check and not getattr(args, "surface", None):
        try:
            git_dir = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip()
            git_common = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=repo_root, capture_output=True, text=True, check=True,
            ).stdout.strip()
            is_primary = (Path(git_dir).resolve() == Path(git_common).resolve())
            if is_primary:
                dirty = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=repo_root, capture_output=True, text=True, check=True,
                ).stdout.strip()
                if dirty:
                    dirty_count = len(dirty.splitlines())
                    print(
                        f"[error] Dispatcher refused: primary worktree has {dirty_count} dirty file(s).\n"
                        f"  Pipeline must run in a clean linked worktree to avoid scope drift.\n"
                        f"\n"
                        f"  Create one with:\n"
                        f"    WT=\"/private/tmp/workingrcx_$(date +%s)\"\n"
                        f"    git worktree add \"$WT\" origin/dev --detach\n"
                        f"    cd \"$WT\" && git checkout -b jabramsja/<wave-name>\n"
                        f"    # Then run dispatcher from $WT\n",
                        file=sys.stderr,
                    )
                    return 1
        except subprocess.CalledProcessError:
            pass  # Can't detect worktree type — proceed anyway

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
                record = load_routing_record(repo_root, bus_dir=args.bus_dir)
            except DispatchError:
                # No routing record — try to create one via post-merge supervisor
                if args.verbose:
                    print("[dispatch] No routing record — running post-merge supervisor...")
                refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
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
                    bus_dir=args.bus_dir,
                )
            else:
                result = dispatch(
                    record,
                    config=config,
                    repo_root=repo_root,
                    routing_record_path=args.routing_record if args.routing_record else None,
                    skip_freshness=args.skip_freshness,
                    verbose=args.verbose,
                    bus_dir=args.bus_dir,
                )
            embedded_recovery = result.get("recovery")
            if isinstance(embedded_recovery, dict) and embedded_recovery.get("recovered"):
                if args.verbose:
                    print(
                        "[dispatch] Phase B recovered in-process — retrying "
                        "before commit chain"
                    )
                _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose, bus_dir=args.bus_dir)
                if not _is_chained_commit_failure(result):
                    if args.routing_record:
                        explicit_record = _reload_explicit_routing_record(
                            args.routing_record,
                            verbose=args.verbose,
                        )
                        if explicit_record is not None:
                            record = explicit_record
                    else:
                        refreshed, refresh_record = _auto_refresh_routing(
                            repo_root, verbose=args.verbose, bus_dir=args.bus_dir
                        )
                        if refreshed and refresh_record is not None:
                            record = refresh_record
                continue
            # Non-retryable dispatch statuses — break immediately
            if result.get("status") in _NON_RETRYABLE_DISPATCH_STATUSES:
                break
            # Terminal executor outcomes (founder-required, max bridge rounds
            # exhausted) — retrying would re-produce the same result
            if result.get("status") == "failed" and _is_terminal_executor_outcome(result):
                if args.verbose:
                    print("[dispatch] Executor returned terminal outcome — not retrying")
                _emit_executor_hard_fail_event(
                    repo_root,
                    result,
                    str(record.get("wave_name") or record.get("wave_id") or ""),
                    record,
                    bus_dir=args.bus_dir,
                )
                break
            # Recovery gate: classify failure and attempt Tier 1/2 auto-fix
            # "timeout" is included so PROCESS_TIMEOUT reaches Tier 2 recovery
            # "bot_findings_pending" is deliberately excluded — classify_failure
            # returns UNCLASSIFIED (tier 4) for it, which hits the tier>=3
            # fail-closed break.  Letting it fall through preserves normal
            # --retries behavior so the executor can re-poll bot review state.
            if result.get("status") in ("failed", "timeout"):
                _wave_id = normalize_wave_id(
                    record.get("wave_name") or record.get("wave_id", ""))
                recovery = attempt_recovery(repo_root, result, _wave_id, bus_dir=args.bus_dir)
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
                    _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose, bus_dir=args.bus_dir)
                    if not _is_chained_commit_failure(result):
                        if args.routing_record:
                            explicit_record = _reload_explicit_routing_record(
                                args.routing_record,
                                verbose=args.verbose,
                            )
                            if explicit_record is not None:
                                record = explicit_record
                        else:
                            refreshed, refresh_record = _auto_refresh_routing(
                                repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
                            if refreshed and refresh_record is not None:
                                record = refresh_record
                    continue  # retry dispatch without counting against budget
                elif recovery.get("exhausted"):
                    if args.verbose:
                        print("[dispatch] Recovery exhausted — not retrying")
                    _emit_executor_hard_fail_event(repo_root, result, _wave_id, record, bus_dir=args.bus_dir)
                    break
                else:
                    # Tier 3/4 non-recovery: fail closed instead of falling
                    # through to the normal retry loop (Bridge R6 Finding 2).
                    _rec_tier = recovery.get("tier", 0)
                    if _rec_tier >= 3:
                        if args.verbose:
                            print(f"[dispatch] Tier {_rec_tier} recovery not "
                                  f"available — failing closed")
                        _emit_executor_hard_fail_event(repo_root, result, _wave_id, record, bus_dir=args.bus_dir)
                        break
            if attempt >= max_attempts:
                if result.get("status") in ("failed", "timeout"):
                    _emit_executor_hard_fail_event(
                        repo_root,
                        result,
                        str(record.get("wave_name") or record.get("wave_id") or ""),
                        record,
                        bus_dir=args.bus_dir,
                    )
                break
            if args.verbose:
                print(f"[dispatch] Attempt {attempt}/{max_attempts} failed — retrying...")
            # Clear Phase B persisted state before retry to prevent stale
            # resume from skipping required implementer re-entry after a
            # bridge-fix cycle failure.
            _clear_phase_b_state_for_retry(repo_root, result, verbose=args.verbose, bus_dir=args.bus_dir)
            # Only refresh routing if no explicit --routing-record was provided
            # and this was NOT a chained commit retry (routing is irrelevant
            # when retrying only the commit step).
            # Do NOT unlink the existing routing record before refresh — if
            # refresh fails, the canonical record would be permanently lost.
            # The supervisor overwrites the file in place on success.
            if not _is_chained_commit_failure(result):
                if args.routing_record:
                    explicit_record = _reload_explicit_routing_record(
                        args.routing_record,
                        verbose=args.verbose,
                    )
                    if explicit_record is not None:
                        record = explicit_record
                else:
                    refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
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
            config["timeouts"] = _recovery_original_section(
                _recovery_original_timeouts, "timeouts"
            )
            config["bridge_turn_timeouts"] = _recovery_original_section(
                _recovery_original_timeouts, "bridge_turn_timeouts"
            )
        # Clean up original-baseline env vars set by fix_process_timeout /
        # fix_implementer_stale to prevent leakage to --loop waves.
        for _env_key in list(os.environ):
            if _env_key.startswith((
                "RCX_RECOVERY_ORIGINAL_TIMEOUT_",
                "RCX_RECOVERY_ORIGINAL_BRIDGE_TURN_TIMEOUT_",
                PHASE_B_RECOVERY_PLAN_ENV,
            )):
                os.environ.pop(_env_key, None)

        if result.get("status") in ("success", "held"):
            _wave_id = normalize_wave_id(
                record.get("wave_name") or record.get("wave_id", "")
            )
            clear_stale_recovery_status_on_success(
                repo_root,
                wave_id=_wave_id,
                success_target=result.get("executor") or result.get("step", ""),
                bus_dir=args.bus_dir,
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
        package_path = agent_bus_path(repo_root, args.bus_dir, "meta", POST_MERGE_PACKAGE_NAME)
        if not package_path.exists():
            if args.verbose:
                print("[dispatch] No post-merge package — cannot loop to next wave")
            break
        refreshed, refresh_record = _auto_refresh_routing(repo_root, verbose=args.verbose, bus_dir=args.bus_dir)
        if not refreshed or refresh_record is None:
            if args.verbose:
                print("[dispatch] Post-merge supervisor failed — stopping loop")
            break
        # Clear the explicit routing record arg so next iteration loads fresh
        args.routing_record = None

    return 0 if result.get("status") in ("success", "held", "stopped", "not_implemented") else 1


if __name__ == "__main__":
    sys.exit(main())
