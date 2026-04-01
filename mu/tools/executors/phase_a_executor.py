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
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# Import implementer for plan refinement during bridge loop
_invoke_implementer = None
try:
    _agents_dir = str(SCRIPT_DIR.parent / "agents")
    if _agents_dir not in sys.path:
        sys.path.insert(0, _agents_dir)
    _impl_dir = str(SCRIPT_DIR)
    if _impl_dir not in sys.path:
        sys.path.insert(0, _impl_dir)
    from phase_b_implementer import invoke_implementer as _invoke_implementer
except ImportError:
    pass

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        load_executor_config,
        load_routing_record,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        artifact_size_mtime_ns,
        process_descendants,
        terminate_process_tree,
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
    artifact_size_mtime_ns = _mod.artifact_size_mtime_ns
    process_descendants = _mod.process_descendants
    terminate_process_tree = _mod.terminate_process_tree


class PhaseAExecutorError(RuntimeError):
    """Raised when Phase A executor cannot proceed."""


PLAN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
ALLOWED_REVIEW_DEPTHS = {"quick", "full", "founder", "all"}
RECOGNIZED_BRIDGE_DECISIONS = {
    "GO",
    "REQUEST_CHANGES",
    "NO_GO",
    "QUESTION",
    "STALE",
    "ERROR",
    "SYNTHETIC",
}
BRIDGE_DECISION_RE = re.compile(
    r"(?m)^\s*(?:-\s*)?Decision:\s*"
    r"(GO|REQUEST_CHANGES|NO_GO|QUESTION|STALE|ERROR|SYNTHETIC)\b"
)
PHASE_A_ALLOWED_REVIEW_EXIT_CODES = {0, 1, 2}
PHASE_A_BRIDGE_POLL_SLEEP = 2.0
PHASE_A_BRIDGE_STALE_TIMEOUT = 120.0
PHASE_A_BRIDGE_AGGREGATION_HANG_TIMEOUT = 60.0


def _trim_stderr(stderr: str, limit: int = 500, *, tail: bool = False) -> str:
    """Return a bounded stderr snippet for fail-closed error surfaces."""
    text = (stderr or "").strip()
    if not tail or len(text) <= limit:
        return text[:limit]
    return text[-limit:]


def _read_agent_status_diagnostic(status_path: Path) -> str:
    """Read the status.json artifact and return a structured diagnostic summary.

    Prioritizes agent-level verdicts and timeout information over raw stderr,
    which can be dominated by irrelevant noise (e.g. Bun AVX warnings).
    """
    if not status_path.exists():
        return ""
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    parts: list[str] = []
    if data.get("phase_label"):
        parts.append(f"phase={data['phase_label']}")
    if data.get("status"):
        parts.append(f"status={data['status']}")
    completed = data.get("completed_agents", {})
    if completed:
        for agent, info in sorted(completed.items()):
            if isinstance(info, dict):
                verdict = info.get("verdict", "unknown")
                detail = info.get("detail", "")
                entry = f"{agent}={verdict}"
                if detail:
                    entry += f"({detail[:80]})"
                parts.append(entry)
            else:
                parts.append(f"{agent}={info}")
    running = data.get("running_agents", [])
    if running:
        parts.append(f"still_running={running}")
    return " ".join(parts)


def resolve_review_depth(config: dict[str, Any], phase_key: str, default: str = "quick") -> str:
    """Resolve review depth from executor config and fail closed on invalid values."""
    depth = config.get("review_depths", {}).get(phase_key, default)
    if depth not in ALLOWED_REVIEW_DEPTHS:
        raise PhaseAExecutorError(
            f"Invalid review depth {depth!r} for {phase_key}; "
            f"expected one of {sorted(ALLOWED_REVIEW_DEPTHS)}"
        )
    return depth


def resolve_bridge_reviewer(config: dict[str, Any], phase_key: str, default: str = "codex") -> str:
    """Resolve bridge reviewer backend from executor config."""
    reviewer = config.get("bridge_reviewers", {}).get(phase_key, default)
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise PhaseAExecutorError(
            f"Invalid bridge reviewer {reviewer!r} for {phase_key}; expected non-empty string"
        )
    return reviewer.strip()


def resolve_bridge_turn_timeout(config: dict[str, Any], phase_key: str, default: float) -> float:
    """Resolve bridge turn timeout budget from executor config."""
    timeout = config.get("bridge_turn_timeouts", {}).get(phase_key, default)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise PhaseAExecutorError(
            f"Invalid bridge turn timeout {timeout!r} for {phase_key}; expected positive number"
        )
    return float(timeout)


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
    verbose: bool = False,
    timeout: int = 600,
) -> dict[str, Any]:
    """Run SDK agent review with supervised status/report artifacts."""
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _read_status_snapshot(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _status_fingerprint(snapshot: dict[str, Any]) -> tuple[Any, ...]:
        return (
            snapshot.get("status", ""),
            snapshot.get("phase_label", ""),
            tuple(snapshot.get("running_agents", []) or []),
            json.dumps(snapshot.get("completed_agents", {}) or {}, sort_keys=True),
            snapshot.get("last_progress_label", ""),
            snapshot.get("last_progress_timestamp", ""),
        )

    cmd = [
        sys.executable, "tools/runners/run_review.py",
        *files, "--depth", depth,
        "--fail-fast-hard-gate",
        "--no-memory",
    ]
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    stdout_path = scratch_dir / f"phase_a_agent_review_{run_id}.stdout.log"
    stderr_path = scratch_dir / f"phase_a_agent_review_{run_id}.stderr.log"
    status_path = scratch_dir / f"phase_a_agent_review_{run_id}.status.json"
    report_path = scratch_dir / f"phase_a_agent_review_{run_id}.report.md"
    cmd.extend(["--output", str(report_path)])
    findings_path = repo_root / ".agent_memory" / "findings.json"
    poll_interval = 30.0
    stale_timeout = 300.0
    aggregation_hang_timeout = 120.0
    single_tail_timeout = 180

    with stdout_path.open("w", encoding="utf-8") as stdout_handle, \
            stderr_path.open("w", encoding="utf-8") as stderr_handle:
        proc = subprocess.Popen(
            cmd,
            cwd=repo_root,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            env={
                **os.environ,
                "PYTHONHASHSEED": "0",
                "RCX_REVIEW_STATUS_PATH": str(status_path),
                "RCX_REVIEW_HEARTBEAT_INTERVAL": str(int(poll_interval)),
                "RCX_REVIEW_SINGLE_TAIL_TIMEOUT": str(single_tail_timeout),
                "RCX_REVIEW_GROUP_STALE_TIMEOUT": str(int(stale_timeout)),
                "RCX_REVIEW_AGENT_TIMEOUT": str(max(timeout, single_tail_timeout)),
            },
        )

        last_stdout_size, _ = artifact_size_mtime_ns(stdout_path)
        last_stderr_size, _ = artifact_size_mtime_ns(stderr_path)
        last_findings_size, last_findings_mtime = artifact_size_mtime_ns(findings_path)
        last_status_snapshot = _read_status_snapshot(status_path)
        last_status_fingerprint = _status_fingerprint(last_status_snapshot)
        last_children = process_descendants(proc.pid, cwd=repo_root)
        last_progress_ts = _timestamp()
        last_progress_at = time.monotonic()
        start_time = last_progress_at
        last_heartbeat_at = 0.0

        def _read_logs() -> tuple[str, str]:
            stdout_handle.flush()
            stderr_handle.flush()
            return (
                stdout_path.read_text(encoding="utf-8"),
                stderr_path.read_text(encoding="utf-8"),
            )

        while True:
            exit_code = proc.poll()
            child_pids = process_descendants(proc.pid, cwd=repo_root)
            stdout_size, _ = artifact_size_mtime_ns(stdout_path)
            stderr_size, _ = artifact_size_mtime_ns(stderr_path)
            findings_size, findings_mtime = artifact_size_mtime_ns(findings_path)
            status_snapshot = _read_status_snapshot(status_path)
            status_fingerprint = _status_fingerprint(status_snapshot)
            status_changed = status_fingerprint != last_status_fingerprint

            output_growth = (
                stdout_size != last_stdout_size
                or stderr_size != last_stderr_size
                or findings_size != last_findings_size
                or findings_mtime != last_findings_mtime
                or status_changed
            )
            child_state_changed = child_pids != last_children

            if output_growth or child_state_changed:
                last_progress_at = time.monotonic()
                last_progress_ts = _timestamp()

            now = time.monotonic()
            if verbose and (now - last_heartbeat_at >= poll_interval):
                pending_agents = status_snapshot.get("running_agents", [])
                phase_label = status_snapshot.get("phase_label", "")
                print(
                    "[phase-a] SDK heartbeat: "
                    f"step=agent_review pid={proc.pid} child_pids={sorted(child_pids)} "
                    f"stdout_bytes={stdout_size} stderr_bytes={stderr_size} "
                    f"findings_mtime_ns={findings_mtime} status_pending={pending_agents} "
                    f"status_phase={phase_label} last_progress={last_progress_ts}",
                    file=sys.stderr,
                    flush=True,
                )
                last_heartbeat_at = now

            if exit_code is not None:
                break

            idle_for = now - last_progress_at
            if not child_pids and idle_for >= aggregation_hang_timeout:
                terminate_process_tree(proc.pid, cwd=repo_root)
                stdout_text, stderr_text = _read_logs()
                return {
                    "exit_code": -3,
                    "stdout": stdout_text,
                    "stderr": (
                        "aggregation_hang: agent-review children exited but aggregator "
                        f"remained alive for {int(idle_for)}s"
                        + (f"\n{stderr_text[:2000]}" if stderr_text else "")
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                    "status_path": str(status_path.relative_to(repo_root)),
                    "report_path": str(report_path.relative_to(repo_root)),
                    "last_progress_timestamp": last_progress_ts,
                }
            if idle_for >= stale_timeout:
                terminate_process_tree(proc.pid, cwd=repo_root)
                stdout_text, stderr_text = _read_logs()
                status_detail = ""
                if status_snapshot:
                    status_detail = (
                        f"\nstatus_phase={status_snapshot.get('phase_label', '')} "
                        f"running_agents={status_snapshot.get('running_agents', [])} "
                        f"last_progress={status_snapshot.get('last_progress_timestamp', '')}"
                    )
                return {
                    "exit_code": -2,
                    "stdout": stdout_text,
                    "stderr": (
                        "stale_run: no output growth, findings artifact change, or "
                        f"child-state change for {int(idle_for)}s"
                        + status_detail
                        + (f"\n{stderr_text[:2000]}" if stderr_text else "")
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                    "status_path": str(status_path.relative_to(repo_root)),
                    "report_path": str(report_path.relative_to(repo_root)),
                    "last_progress_timestamp": last_progress_ts,
                }
            if now - start_time >= timeout:
                terminate_process_tree(proc.pid, cwd=repo_root)
                stdout_text, stderr_text = _read_logs()
                status_detail = ""
                if status_snapshot:
                    status_detail = (
                        f"\nstatus_phase={status_snapshot.get('phase_label', '')} "
                        f"running_agents={status_snapshot.get('running_agents', [])} "
                        f"last_progress={status_snapshot.get('last_progress_timestamp', '')}"
                    )
                return {
                    "exit_code": -1,
                    "stdout": stdout_text,
                    "stderr": (
                        f"Agent review timed out after {timeout}s "
                        f"(last progress {last_progress_ts})"
                        + status_detail
                        + (f"\n{stderr_text[:2000]}" if stderr_text else "")
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                    "status_path": str(status_path.relative_to(repo_root)),
                    "report_path": str(report_path.relative_to(repo_root)),
                    "last_progress_timestamp": last_progress_ts,
                }

            last_stdout_size = stdout_size
            last_stderr_size = stderr_size
            last_findings_size = findings_size
            last_findings_mtime = findings_mtime
            last_status_snapshot = status_snapshot
            last_status_fingerprint = status_fingerprint
            last_children = child_pids
            time.sleep(poll_interval)

        stdout_text, stderr_text = _read_logs()
        return {
            "exit_code": proc.returncode,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "stdout_path": str(stdout_path.relative_to(repo_root)),
            "stderr_path": str(stderr_path.relative_to(repo_root)),
            "status_path": str(status_path.relative_to(repo_root)),
            "report_path": str(report_path.relative_to(repo_root)),
            "last_progress_timestamp": last_progress_ts,
        }


def run_bridge_design_review(
    repo_root: Path,
    plan_path: str,
    round_num: int,
    *,
    job_id: str | None = None,
    timeout: int = 1200,
    agent_review_context: str = "",
) -> dict[str, Any]:
    """Run bridge design review (--no-diff) on a plan packet."""
    config = load_executor_config(repo_root)
    reviewer = resolve_bridge_reviewer(config, "phase_a")
    bridge_turn_timeout = resolve_bridge_turn_timeout(config, "phase_a", default=300.0)
    stale_timeout = min(timeout, max(PHASE_A_BRIDGE_STALE_TIMEOUT, bridge_turn_timeout))
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    task_path = scratch_dir / f"phase_a_bridge_r{round_num}.md"
    task_content = (
        f"# Phase A Bridge Round {round_num}\n\n"
        f"Review the plan at `{plan_path}` as an adversarial co-lead reviewer.\n\n"
        "## Required Plan Content (BLOCKING if missing)\n\n"
        "A Phase A plan MUST contain ALL of the following to receive GO:\n"
        "1. **Scope**: explicit list of files/directories in scope\n"
        "2. **Work items**: concrete, bounded tasks derived from TASKS.md current phase\n"
        "3. **Constraints**: what is NOT in scope\n"
        "4. **Stop conditions**: when to stop\n"
        "5. **Acceptance criteria**: how to know it's done\n"
        "6. **Grounding**: references to TASKS.md authorization and governing packet\n\n"
        "A plan with only routing metadata, supervisor request echoes, or empty sections\n"
        "is NOT a plan — it is a stub. Reject stubs with REQUEST_CHANGES.\n\n"
        "## Review Protocol\n\n"
        "- Read TASKS.md for the current phase description and authorization\n"
        "- Read the governing tracked packet for sequence and supporting inputs\n"
        "- Verify plan work items are grounded in actual codebase state (run commands)\n"
        "- Use repo-local evidence only. Do not browse the web or query external\n"
        "  network resources for this review.\n\n"
    )
    if agent_review_context:
        task_content += agent_review_context + "\n\n"
    task_content += "Questions? Concerns? Thoughts? -- Think hard\n"
    task_path.write_text(task_content, encoding="utf-8")

    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    cmd = [
        sys.executable, str(bridge_script),
        "review",
        "--task-file", str(task_path),
        "--summary", f"Phase A plan review R{round_num}",
        "--reviewer", reviewer,
        "-v", "--no-diff",
    ]
    if job_id:
        cmd.extend(["--job-id", job_id])

    run_id = job_id or uuid.uuid4().hex[:8]
    stdout_path = scratch_dir / f"phase_a_bridge_{run_id}.stdout.log"
    stderr_path = scratch_dir / f"phase_a_bridge_{run_id}.stderr.log"

    def _read_logs() -> tuple[str, str]:
        return (
            stdout_path.read_text(encoding="utf-8") if stdout_path.exists() else "",
            stderr_path.read_text(encoding="utf-8") if stderr_path.exists() else "",
        )

    def _artifact_fingerprint() -> tuple[Any, ...]:
        rendered_path = repo_root / ".agent_bus" / "rendered" / f"{run_id}.md"
        raw_dir = repo_root / ".agent_bus" / "raw" / run_id
        raw_files: tuple[tuple[str, tuple[int, int | None]], ...] = ()
        if raw_dir.exists():
            raw_files = tuple(
                sorted(
                    (path.name, artifact_size_mtime_ns(path))
                    for path in raw_dir.iterdir()
                    if path.is_file()
                )
            )
        return (
            artifact_size_mtime_ns(stdout_path),
            artifact_size_mtime_ns(stderr_path),
            artifact_size_mtime_ns(rendered_path),
            raw_files,
        )

    with stdout_path.open("w", encoding="utf-8") as stdout_handle, \
            stderr_path.open("w", encoding="utf-8") as stderr_handle:
        proc = subprocess.Popen(
            cmd,
            cwd=repo_root,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            env={
                **os.environ,
                "RCX_BRIDGE_MAX_TURN_WALL_TIME_S": str(min(timeout, bridge_turn_timeout)),
            },
            start_new_session=True,
        )

        last_snapshot = {
            "child_pids": tuple(sorted(process_descendants(proc.pid, cwd=repo_root))),
            "artifact_fingerprint": _artifact_fingerprint(),
        }
        last_progress_at = time.monotonic()
        start_time = last_progress_at

        while True:
            exit_code = proc.poll()
            snapshot = {
                "child_pids": tuple(sorted(process_descendants(proc.pid, cwd=repo_root))),
                "artifact_fingerprint": _artifact_fingerprint(),
            }
            now = time.monotonic()
            if snapshot != last_snapshot:
                last_progress_at = now
            idle_for = now - last_progress_at

            if exit_code is not None:
                stdout, stderr = _read_logs()
                return {
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            if not snapshot["child_pids"] and idle_for >= PHASE_A_BRIDGE_AGGREGATION_HANG_TIMEOUT:
                terminate_process_tree(proc.pid, cwd=repo_root)
                stdout, stderr = _read_logs()
                return {
                    "exit_code": -3,
                    "stdout": stdout,
                    "stderr": (
                        f"Bridge review aggregation hang after {idle_for:.1f}s "
                        f"(job_id={run_id}, stdout_log={stdout_path.name}, stderr_log={stderr_path.name}).\n"
                        f"{stderr}"
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            if idle_for >= stale_timeout:
                terminate_process_tree(proc.pid, cwd=repo_root)
                stdout, stderr = _read_logs()
                return {
                    "exit_code": -2,
                    "stdout": stdout,
                    "stderr": (
                        f"Bridge review stale after {idle_for:.1f}s "
                        f"(job_id={run_id}, child_pids={list(snapshot['child_pids'])}, "
                        f"stale_timeout_s={stale_timeout:.1f}, "
                        f"stdout_log={stdout_path.name}, stderr_log={stderr_path.name}).\n"
                        f"{stderr}"
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            if now - start_time >= timeout:
                terminate_process_tree(proc.pid, cwd=repo_root)
                stdout, stderr = _read_logs()
                return {
                    "exit_code": -1,
                    "stdout": stdout,
                    "stderr": (
                        f"Bridge review timed out after {timeout}s "
                        f"(job_id={run_id}, stdout_log={stdout_path.name}, stderr_log={stderr_path.name}).\n"
                        f"{stderr}"
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            last_snapshot = snapshot
            time.sleep(PHASE_A_BRIDGE_POLL_SLEEP)


def _parse_phase_a_findings(render_content: str) -> list[dict[str, Any]]:
    """Parse findings from bridge rendered output for blocking/non-blocking classification.

    Looks for the structured findings block in the reviewer turn. Each finding
    has severity, title, disposition, and detail.
    """
    findings: list[dict[str, Any]] = []
    # Parse the JSON envelope from the rendered content
    import re as _re
    envelope_match = _re.search(
        r"BEGIN_AGENT_ENVELOPE\s*\n(.*?)\nEND_AGENT_ENVELOPE",
        render_content,
        _re.DOTALL,
    )
    if envelope_match:
        try:
            envelope = json.loads(envelope_match.group(1))
            for f in envelope.get("findings", []):
                findings.append({
                    "severity": f.get("severity", "medium"),
                    "title": f.get("title", ""),
                    "detail": f.get("detail", ""),
                    "disposition": f.get("disposition", ""),
                    "file": f.get("file", ""),
                })
        except (json.JSONDecodeError, TypeError):
            pass
    return findings


def _extract_bridge_decision(render_content: str) -> str:
    """Parse the canonical bridge decision line from rendered output."""
    decisions = [match.group(1) for match in BRIDGE_DECISION_RE.finditer(render_content)]
    if not decisions:
        return ""
    # Bridge renders often start with a synthetic reader turn before the
    # authoritative reviewer turn. Prefer the last non-synthetic decision, but
    # still surface a terminal SYNTHETIC-only render as fail-closed input.
    for decision in reversed(decisions):
        if decision != "SYNTHETIC":
            return decision
    return decisions[-1]


def lock_plan(repo_root: Path, plan_path: str) -> None:
    """Set Phase-A-Lock: LOCKED in a plan packet.

    Idempotent: if the packet is already LOCKED, applies status text cleanup
    and returns without error. Fails closed with a structured error if the
    control line is missing, malformed, or duplicated.
    """
    full_path = repo_root / plan_path
    content = full_path.read_text(encoding="utf-8")
    unlocked_lines = re.findall(r"(?m)^Phase-A-Lock:\s*UNLOCKED\s*$", content)
    locked_lines = re.findall(r"(?m)^Phase-A-Lock:\s*LOCKED\s*$", content)
    total = len(unlocked_lines) + len(locked_lines)
    if total == 0:
        raise PhaseAExecutorError(
            f"No Phase-A-Lock control line found in {plan_path}. "
            "Expected exactly one line matching 'Phase-A-Lock: UNLOCKED' or "
            "'Phase-A-Lock: LOCKED'."
        )
    if total > 1:
        raise PhaseAExecutorError(
            f"Expected exactly one Phase-A-Lock control line in {plan_path}, "
            f"found {len(unlocked_lines)} unlocked and {len(locked_lines)} locked"
        )
    # Exactly one control line exists
    if unlocked_lines:
        content, lock_replacements = re.subn(
            r"(?m)^Phase-A-Lock:\s*UNLOCKED\s*$",
            "Phase-A-Lock: LOCKED",
            content,
            count=1,
        )
        if lock_replacements != 1:
            raise PhaseAExecutorError(
                f"Expected one unlock line in {plan_path}, found {lock_replacements}"
            )
    # Already LOCKED — idempotent, just apply status text cleanup below
    content = re.sub(
        r"not yet agent-reviewed or bridge-converged",
        "bridge-converged",
        content,
        count=1,
    )
    full_path.write_text(content, encoding="utf-8")


def checkpoint_commit_plan(
    repo_root: Path,
    plan_path: str,
    plan_name: str,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Stage and commit a locked plan file as a lightweight checkpoint.

    Returns {"sha": "<commit_sha>"} on success, {"skipped": True} if nothing
    to commit, or {"error": "<message>"} on failure.
    """
    log = (lambda msg: print(f"[phase-a] {msg}", file=sys.stderr)) if verbose else (lambda msg: None)
    try:
        subprocess.run(
            ["git", "add", plan_path],
            cwd=repo_root, check=True, capture_output=True, text=True,
        )
        checkpoint_msg = f"chore: Phase A lock — {plan_name}"
        # Skip receipt check only — plan-only checkpoint has no supervisor receipt.
        # All other pre-commit checks (doc consistency, governance) still run.
        checkpoint_env = {**os.environ, "RCX_SKIP_RECEIPT_CHECK": "1"}
        commit_result = subprocess.run(
            ["git", "commit", plan_path, "-m", checkpoint_msg],
            cwd=repo_root, capture_output=True, text=True,
            env=checkpoint_env,
        )
        if commit_result.returncode != 0:
            if "nothing to commit" in commit_result.stdout:
                log("Plan already committed — skipping checkpoint")
                return {"skipped": True}
            return {"error": f"Checkpoint commit failed: {commit_result.stderr.strip()}"}
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, check=True,
        ).stdout.strip()
        log(f"Checkpoint commit: {sha[:8]} ({checkpoint_msg})")
        return {"sha": sha}
    except subprocess.CalledProcessError as exc:
        return {"error": f"Checkpoint commit failed: {exc}"}


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

    _log_path = repo_root / ".scratch" / "phase_a_executor_live.log"
    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _log_fp = open(_log_path, "w", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[phase-a] {msg}"
        if verbose:
            print(line, flush=True)
        try:
            _log_fp.write(line + "\n")
            _log_fp.flush()
        except (OSError, ValueError):
            pass

    config = load_executor_config(repo_root)

    # Load routing record for scope context
    try:
        routing_record = load_routing_record(repo_root)
        scope = extract_plan_scope(routing_record)
    except (PhaseAExecutorError, ExecutorCommonError):
        scope = {"request": "", "summary": "", "decision": "ROUTE_PHASE_A"}

    # Create or load plan draft
    try:
        plan_path = create_plan_draft(repo_root, plan_name, scope)
    except PhaseAExecutorError as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result
    rel_plan_path = str(plan_path.relative_to(repo_root))
    result["plan_path"] = rel_plan_path
    log(f"Plan draft: {rel_plan_path}")

    # Run SDK agent review on the plan. Exit 2 is warnings / soft gate per
    # run_review.py + AgentRunbook; hard gate / infra exits still fail closed.
    review_depth = resolve_review_depth(config, "phase_a")
    log(f"Running SDK agent review on plan (depth={review_depth})...")
    agent_timeout = config.get("timeouts", {}).get("agent_review", 900)
    agent_result = run_sdk_agents(
        repo_root,
        [rel_plan_path],
        depth=review_depth,
        verbose=verbose,
        timeout=agent_timeout,
    )
    result["agent_review_ran"] = True
    result["agent_exit_code"] = agent_result["exit_code"]
    result["agent_review_report_path"] = agent_result.get("report_path")
    result["agent_review_status_path"] = agent_result.get("status_path")
    result["agent_review_stdout_path"] = agent_result.get("stdout_path")
    log(f"Agent review exit code: {agent_result['exit_code']}")

    if agent_result["exit_code"] not in PHASE_A_ALLOWED_REVIEW_EXIT_CODES:
        # Prefer structured status diagnostic over raw stderr, which can be
        # dominated by irrelevant noise (Bun AVX warnings, SDK chatter).
        status_diag = ""
        if agent_result.get("status_path"):
            status_diag = _read_agent_status_diagnostic(
                repo_root / agent_result["status_path"]
            )
        detail_parts: list[str] = []
        if status_diag:
            detail_parts.append(f"agent_status: {status_diag}")
        detail_parts.append(
            f"stderr_tail: {_trim_stderr(agent_result.get('stderr', ''), 500, tail=True)}"
        )
        if agent_result.get("report_path"):
            detail_parts.append(f"report_path={agent_result['report_path']}")
        if agent_result.get("status_path"):
            detail_parts.append(f"status_path={agent_result['status_path']}")
        if agent_result.get("stdout_path"):
            detail_parts.append(f"stdout_path={agent_result['stdout_path']}")
        result["status"] = "error"
        result["error"] = (
            f"SDK agent review failed (exit={agent_result['exit_code']}). "
            "Hard gate: agents must pass before bridge review. "
            + " | ".join(detail_parts)
        )
        return result
    if agent_result["exit_code"] == 1:
        log(
            "Agent review returned semantic blocker findings (exit=1); "
            "continuing to bridge for contextual blocking/non-blocking classification"
        )
        result["agent_review_warning_only"] = True
    elif agent_result["exit_code"] == 2:
        log("Agent review returned soft warnings (exit=2) — continuing to bridge")
        result["agent_review_warning_only"] = True

    # Build agent review context for bridge (mirrors Phase B's SDK artifact surface)
    agent_review_bridge_ctx = ""
    if result.get("agent_review_report_path"):
        agent_review_bridge_ctx = (
            "## SDK Agent Review Artifacts\n\n"
            f"- exit_code: {result.get('agent_exit_code')}\n"
            f"- report: {result.get('agent_review_report_path')}\n"
            f"- status: {result.get('agent_review_status_path')}\n"
            f"- stdout: {result.get('agent_review_stdout_path')}\n\n"
            "Bridge must treat SDK findings as review inputs for contextual "
            "blocking/non-blocking classification. Semantic SDK negatives are "
            "not automatic current-step blockers by themselves."
        )

    # Bridge convergence loop (design review, --no-diff)
    for round_num in range(1, max_bridge_rounds + 1):
        bridge_job_id = f"phase-a-r{round_num}-{uuid.uuid4().hex[:8]}"
        log(f"Bridge design review round {round_num}/{max_bridge_rounds} (job={bridge_job_id})...")
        result["bridge_rounds"] = round_num

        bridge_result = run_bridge_design_review(
            repo_root, rel_plan_path, round_num,
            job_id=bridge_job_id,
            agent_review_context=agent_review_bridge_ctx,
        )
        log(f"Bridge exit code: {bridge_result['exit_code']}")

        rendered_path = repo_root / ".agent_bus" / "rendered" / f"{bridge_job_id}.md"
        if rendered_path.exists():
            render_content = rendered_path.read_text(encoding="utf-8")
            bridge_decision = _extract_bridge_decision(render_content)
            if bridge_decision == "GO":
                if bridge_result["exit_code"] != 0:
                    log(
                        f"Bridge returned GO with unexpected exit {bridge_result['exit_code']} "
                        "— failing closed"
                    )
                    result["status"] = "error"
                    result["error"] = (
                        f"Bridge subprocess failed in round {round_num} "
                        f"(exit={bridge_result['exit_code']}, decision=GO). "
                        f"stderr: {_trim_stderr(bridge_result.get('stderr', ''), tail=True)}"
                    )
                    result["rendered_path"] = str(rendered_path)
                    return result
                log("Bridge converged: GO")
                result["status"] = "converged"
                break
            elif bridge_decision in {"REQUEST_CHANGES", "NO_GO"}:
                # bridge_supervisor.py review returns exit=1 for non-GO decisions.
                # Treat REQUEST_CHANGES/NO_GO as recoverable review outcomes when
                # the exit code matches that CLI contract; only unexpected codes
                # are infrastructure failures here.
                if bridge_result["exit_code"] not in (0, 1):
                    log(
                        f"Bridge subprocess failed (exit {bridge_result['exit_code']}) "
                        f"with decision {bridge_decision} — failing closed"
                    )
                    result["status"] = "error"
                    result["error"] = (
                        f"Bridge subprocess failed in round {round_num} "
                        f"(exit={bridge_result['exit_code']}, decision={bridge_decision}). "
                        f"stderr: {_trim_stderr(bridge_result.get('stderr', ''), tail=True)}"
                    )
                    result["rendered_path"] = str(rendered_path)
                    return result
                # Classify findings as blocking vs non-blocking.
                # If only non-blockers remain, converge — design advisory
                # findings don't need to block plan convergence.
                # Read raw reviewer output for finding parsing — the JSON
                # envelope (BEGIN_AGENT_ENVELOPE) is in the raw output,
                # not in the rendered markdown.
                raw_dir = repo_root / ".agent_bus" / "raw" / bridge_job_id
                raw_content = ""
                if raw_dir.is_dir():
                    for raw_file in sorted(raw_dir.iterdir()):
                        if "reviewer" in raw_file.name:
                            raw_content = raw_file.read_text(encoding="utf-8")
                            break
                parsed_findings = _parse_phase_a_findings(
                    raw_content if raw_content else render_content)
                blocking = [f for f in parsed_findings if f.get("disposition") == "blocking"
                            or (f.get("disposition") not in ("blocking", "non_blocking")
                                and f.get("severity") in ("critical", "high"))]
                non_blocking = [f for f in parsed_findings if f not in blocking]
                log(f"Bridge: REQUEST_CHANGES — {len(blocking)} blocking, {len(non_blocking)} non-blocking")

                if parsed_findings and not blocking:
                    log(f"Bridge: all {len(non_blocking)} findings are non-blocking — treating as GO")
                    result["status"] = "converged"
                    result["non_blocking_count"] = len(non_blocking)
                    break

                # Invoke Claude implementer to fix blocking findings
                if _invoke_implementer is not None and blocking:
                    plan_content = (repo_root / rel_plan_path).read_text(encoding="utf-8")
                    blocking_text = "\n".join(
                        f"- [{f.get('severity','?')}] {f.get('title','untitled')}: {f.get('detail','')[:200]}"
                        for f in blocking
                    )
                    impl_prompt = (
                        f"You are updating a Phase A plan at `{rel_plan_path}`.\n\n"
                        f"The bridge reviewer returned REQUEST_CHANGES. Fix ONLY the blocking findings:\n\n"
                        f"{blocking_text}\n\n"
                        f"## Current plan content:\n\n{plan_content}\n\n"
                        f"## Required plan sections:\n"
                        "1. Scope: files/directories in scope\n"
                        "2. Work items: concrete bounded tasks from TASKS.md current phase\n"
                        "3. Constraints: what is NOT in scope\n"
                        "4. Stop conditions\n"
                        "5. Acceptance criteria\n"
                        "6. Grounding: TASKS.md authorization + governing packet refs\n\n"
                        f"Read TASKS.md (current phase for [NEXT-CODEX-POST-REDTEAM]) and the "
                        f"governing packet at reports/control_plane/post_redteam_structural_queue_2026-03-20.md. "
                        f"Update the plan file directly. Do NOT create new files."
                    )
                    log("Invoking implementer to fix blocking findings...")
                    impl_result = _invoke_implementer(
                        repo_root, impl_prompt,
                        backend="claude",
                        timeout=900,
                        verbose=verbose,
                    )
                    if impl_result["status"] != "success":
                        log(f"Implementer failed: {impl_result['status']} — continuing with unmodified plan")
                    else:
                        log("Implementer updated plan — continuing to next bridge round")
                elif not _invoke_implementer:
                    log("Bridge: REQUEST_CHANGES — no implementer available, continuing with unmodified plan")
                continue
            elif bridge_decision == "QUESTION":
                if bridge_result["exit_code"] not in (0, 1):
                    log(
                        f"Bridge subprocess failed (exit {bridge_result['exit_code']}) "
                        "with QUESTION decision — failing closed"
                    )
                    result["status"] = "error"
                    result["error"] = (
                        f"Bridge subprocess failed in round {round_num} "
                        f"(exit={bridge_result['exit_code']}, decision=QUESTION). "
                        f"stderr: {_trim_stderr(bridge_result.get('stderr', ''), tail=True)}"
                    )
                    result["rendered_path"] = str(rendered_path)
                    return result
                log("Bridge: QUESTION — fail-closed (unresolved question)")
                result["status"] = "error"
                result["error"] = "Bridge returned QUESTION decision — requires human resolution"
                result["rendered_path"] = str(rendered_path)
                return result
            elif bridge_decision in {"STALE", "ERROR", "SYNTHETIC"}:
                if bridge_result["exit_code"] not in (0, 1):
                    log(
                        f"Bridge subprocess failed (exit {bridge_result['exit_code']}) "
                        f"with {bridge_decision} decision — failing closed"
                    )
                    result["status"] = "error"
                    result["error"] = (
                        f"Bridge subprocess failed in round {round_num} "
                        f"(exit={bridge_result['exit_code']}, decision={bridge_decision}). "
                        f"stderr: {_trim_stderr(bridge_result.get('stderr', ''), tail=True)}"
                    )
                    result["rendered_path"] = str(rendered_path)
                    return result
                log(f"Bridge: {bridge_decision} — fail-closed")
                result["status"] = "error"
                if bridge_decision == "SYNTHETIC":
                    result["error"] = (
                        "Bridge returned SYNTHETIC-only decision (decision=SYNTHETIC) — reviewer turn missing"
                    )
                else:
                    result["error"] = (
                        f"Bridge returned {bridge_decision} decision (decision={bridge_decision}) — cannot proceed"
                    )
                result["rendered_path"] = str(rendered_path)
                return result
            else:
                if bridge_result["exit_code"] != 0:
                    log(
                        f"Bridge failed (exit {bridge_result['exit_code']}) with "
                        f"unrecognized decision {bridge_decision!r} — failing closed"
                    )
                    result["status"] = "error"
                    result["error"] = (
                        f"Bridge subprocess failed in round {round_num} "
                        f"(exit={bridge_result['exit_code']}). "
                        f"stderr: {_trim_stderr(bridge_result.get('stderr', ''), tail=True)}"
                    )
                    result["rendered_path"] = str(rendered_path)
                    return result
                # Unrecognized decision — fail closed, do not burn rounds
                log("Bridge: unrecognized decision — fail-closed")
                result["status"] = "error"
                result["error"] = "Bridge returned unrecognized decision — cannot proceed"
                result["rendered_path"] = str(rendered_path)
                return result
        else:
            if bridge_result["exit_code"] != 0:
                log(f"Bridge failed (exit {bridge_result['exit_code']}) — failing closed")
                result["status"] = "error"
                result["error"] = (
                    f"Bridge subprocess failed in round {round_num} "
                    f"(exit={bridge_result['exit_code']}). "
                    f"stderr: {_trim_stderr(bridge_result.get('stderr', ''), tail=True)}"
                )
                return result
            log("Bridge exited 0 without rendered output — fail-closed")
            result["status"] = "error"
            result["error"] = "Bridge exited 0 but produced no rendered output"
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
    try:
        lock_plan(repo_root, rel_plan_path)
    except PhaseAExecutorError as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        return result
    log(f"Phase-A-Lock: LOCKED in {rel_plan_path}")

    # No checkpoint commit — the locked plan is a working artifact that
    # Phase B consumes directly.  It gets committed as part of the
    # implementation commit after Phase B converges.

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
