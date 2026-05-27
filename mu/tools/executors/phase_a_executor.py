#!/usr/bin/env python3
"""Phase A executor: creates plan packets through design + bridge convergence.

Invoked by ROUTE_PHASE_A routing token from the post-merge supervisor.
Creates or refines a plan packet, runs agents, loops bridge until converged,
then commits the plan via the branch/merge discipline.

Control flow:
1. Read routing record and rollout context
2. Create a plan packet draft in reports/control_plane/
3. Run SDK agent review on the plan
4. Send plan + agent findings to bridge (--no-diff review)
5. Fix blockers, defer non-blockers
6. Loop bridge until only non-blockers remain
7. Set Phase-A-Lock: LOCKED
8. Commit plan via branch/merge discipline (feature branch -> PR -> merge)
9. Trigger post-merge supervisor on dev

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md Section B.2
"""

from __future__ import annotations

import argparse
import hashlib
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
        agent_bus_path,
        load_executor_config,
        load_routing_record,
        ensure_not_agent_review_mode,
        ExecutorCommonError,
        emit_pipeline_agent_event,
        normalize_wave_id,
        artifact_size_mtime_ns,
        process_descendants,
        resolve_agent_bus_dir,
        terminate_process_tree,
    )
except ImportError:
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    agent_bus_path = _mod.agent_bus_path
    load_executor_config = _mod.load_executor_config
    load_routing_record = _mod.load_routing_record
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    ExecutorCommonError = _mod.ExecutorCommonError
    emit_pipeline_agent_event = _mod.emit_pipeline_agent_event
    normalize_wave_id = _mod.normalize_wave_id
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir
    artifact_size_mtime_ns = _mod.artifact_size_mtime_ns
    process_descendants = _mod.process_descendants
    terminate_process_tree = _mod.terminate_process_tree


class PhaseAExecutorError(RuntimeError):
    """Raised when Phase A executor cannot proceed."""


PLAN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
TRACKED_PACKET_DATE_SUFFIX_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}(?:_\d{4}-\d{2}-\d{2})*$"
)
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
BRIDGE_TURN_HEADING_RE = re.compile(r"^###\s+(?P<turn_id>\S+)\s+—\s+(?P<role>\S+)\s*$")
BRIDGE_TURN_RAW_OUTPUT_RE = re.compile(r"^-\s*Raw output:\s*(?P<path>.+?)\s*$")
BRIDGE_TURN_JOB_PREFIX_RE = re.compile(r"^(?P<job_id>.+)--r\d+-")
BRIDGE_TURN_ROUND_RE = re.compile(r"--r(?P<round_no>\d+)-")
AGENT_ENVELOPE_RE = re.compile(
    r"BEGIN_AGENT_ENVELOPE\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```\s*)?END_AGENT_ENVELOPE",
    re.DOTALL,
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


def _first_bounded_next_candidate(routing_record: dict[str, Any]) -> dict[str, Any]:
    """Return the first bounded next-candidate object, if one exists."""
    candidates = routing_record.get("next_candidates", [])
    if not isinstance(candidates, list):
        return {}
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate.get("bounded") is True:
            return candidate
    return {}


def _append_distinct_context(base: str, label: str, extra: str) -> str:
    base = str(base or "").strip()
    extra = str(extra or "").strip()
    if not extra:
        return base
    if not base:
        return extra
    if extra in base:
        return base
    return f"{base}\n\n{label}:\n{extra}"


def extract_plan_scope(routing_record: dict[str, Any]) -> dict[str, str]:
    """Extract planning scope from the routing record and bounded candidate."""
    candidate = _first_bounded_next_candidate(routing_record)
    candidate_request = str(
        candidate.get("request_for_claude")
        or candidate.get("request")
        or ""
    )
    candidate_summary = str(candidate.get("summary") or "")
    candidate_name = str(candidate.get("candidate") or "").strip()

    request = _append_distinct_context(
        str(routing_record.get("request_for_claude", "") or ""),
        "Routed next-candidate request",
        candidate_request,
    )
    if candidate_name:
        request = _append_distinct_context(
            request,
            "Routed next-candidate",
            candidate_name,
        )

    summary = _append_distinct_context(
        str(routing_record.get("summary", "") or ""),
        "Routed next-candidate summary",
        candidate_summary,
    )

    return {
        "request": request,
        "summary": summary,
        "decision": routing_record.get("decision", ""),
        "task_id": routing_record.get("task_id", ""),
        "wave_name": routing_record.get("wave_name", ""),
        "tracked_packet": str(
            candidate.get("tracked_packet")
            or routing_record.get("tracked_packet")
            or ""
        ).strip(),
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

    exact = plan_dir / f"{plan_name}.md"
    if exact.exists():
        return exact

    candidates = sorted(plan_dir.glob(f"{plan_name}_*.md"))
    if not candidates:
        return None

    # Prefer locked packets over unlocked ones
    for c in reversed(candidates):
        content = c.read_text(encoding="utf-8")
        if _phase_a_header_lock_value(content) == "LOCKED":
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


def _tracked_plan_path_from_scope(
    repo_root: Path,
    plan_name: str,
    scope: dict[str, str],
) -> Path | None:
    tracked_packet = str(scope.get("tracked_packet") or "").strip()
    if not tracked_packet:
        return None

    candidate = Path(tracked_packet)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PhaseAExecutorError(f"Unsafe tracked_packet: {tracked_packet!r}")
    if candidate.suffix != ".md":
        raise PhaseAExecutorError(f"tracked_packet must be a Markdown packet: {tracked_packet!r}")
    stem = candidate.stem
    date_suffixed_match = bool(
        stem.startswith(f"{plan_name}_")
        and TRACKED_PACKET_DATE_SUFFIX_RE.fullmatch(stem[len(plan_name) + 1 :])
    )
    if stem != plan_name and not date_suffixed_match:
        raise PhaseAExecutorError(
            f"tracked_packet stem {stem!r} does not match plan_name {plan_name!r}"
        )

    control_dir = (repo_root / "reports" / "control_plane").resolve()
    full_path = (repo_root / candidate).resolve()
    try:
        full_path.relative_to(control_dir)
    except ValueError as exc:
        raise PhaseAExecutorError(
            f"tracked_packet must be under reports/control_plane/: {tracked_packet!r}"
        ) from exc
    return full_path


def _render_plan_draft_content(
    plan_name: str,
    scope: dict[str, str],
    *,
    date_str: str,
) -> str:
    """Render the initial Phase A packet draft for a new or stale stub packet."""
    request = str(scope.get("request", "") or "")
    purpose = next((line.strip() for line in request.splitlines() if line.strip()), "")
    if not purpose:
        purpose = "planning required"
    purpose = re.sub(r"\s+", " ", purpose)

    task_id = str(scope.get("task_id", "") or "").strip()
    wave_id = str(scope.get("wave_name", "") or scope.get("wave_id", "") or "").strip()
    identity_lines = []
    if task_id:
        identity_lines.append(f"Task: {task_id}")
    if wave_id:
        identity_lines.append(f"Wave ID: {wave_id}")
    identity_block = "\n".join(identity_lines)
    if identity_block:
        identity_block += "\n"

    return f"""# {plan_name.replace('_', ' ').title()}

Date: {date_str}
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
{identity_block}\
Phase-A-Lock: UNLOCKED
Purpose: {purpose}

## Scope

{scope.get('summary', '(to be filled in during Phase A)')}

## Request from Post-Merge Supervisor

{scope.get('request', '(none)')}
"""


def create_plan_draft(
    repo_root: Path,
    plan_name: str,
    scope: dict[str, str],
) -> Path:
    """Create an initial plan packet draft, or reuse an existing tracked packet.

    If a tracked/canonical packet already exists for this plan_name, reuse it
    instead of creating a new dated placeholder. New dated drafts are only
    created when no matching tracked packet exists. Unlocked placeholder stubs
    are refreshed with the current request so failed Phase A bootstrap can
    resume mechanically without preserving stale request text.
    """
    if not isinstance(plan_name, str) or not PLAN_NAME_RE.fullmatch(plan_name):
        raise PhaseAExecutorError(f"Unsafe plan_name: {plan_name!r}")
    if Path(plan_name).name != plan_name or "/" in plan_name or "\\" in plan_name:
        raise PhaseAExecutorError(f"Path traversal in plan_name: {plan_name!r}")

    plan_dir = repo_root / "reports" / "control_plane"
    plan_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    content = _render_plan_draft_content(plan_name, scope, date_str=date_str)

    tracked_path = _tracked_plan_path_from_scope(repo_root, plan_name, scope)
    if tracked_path is not None:
        tracked_path.parent.mkdir(parents=True, exist_ok=True)
        if tracked_path.exists():
            tracked_content = tracked_path.read_text(encoding="utf-8")
            if (
                _phase_a_header_allows_placeholder_refresh(tracked_content)
                and _plan_is_placeholder_stub(tracked_content)
            ):
                tracked_path.write_text(content, encoding="utf-8")
            return tracked_path
        tracked_path.write_text(content, encoding="utf-8")
        return tracked_path

    # Check for existing tracked packet first.
    existing = _find_tracked_packet(plan_dir, plan_name)
    if existing is not None:
        existing_content = existing.read_text(encoding="utf-8")
        if (
            _phase_a_header_allows_placeholder_refresh(existing_content)
            and _plan_is_placeholder_stub(existing_content)
        ):
            existing.write_text(content, encoding="utf-8")
        return existing

    plan_path = plan_dir / f"{plan_name}_{date_str}.md"

    if plan_path.exists():
        plan_content = plan_path.read_text(encoding="utf-8")
        if (
            _phase_a_header_allows_placeholder_refresh(plan_content)
            and _plan_is_placeholder_stub(plan_content)
        ):
            plan_path.write_text(content, encoding="utf-8")
        return plan_path

    plan_path.write_text(content, encoding="utf-8")
    return plan_path


_REQUIRED_PHASE_A_SECTION_TITLES = frozenset({
    "scope",
    "work items",
    "constraints",
    "stop conditions",
    "acceptance criteria",
    "grounding",
})

_PHASE_A_SECTION_TITLE_ALIASES = {
    "authorization": "grounding",
}

_PHASE_A_PLACEHOLDER_SECTION_TITLES = frozenset({
    "scope",
    "request from post-merge supervisor",
})

_PHASE_A_LOCK_CANONICAL_RE = re.compile(r"^Phase-A-Lock:\s*(UNLOCKED|LOCKED)[ \t]*$")
_PHASE_A_LOCK_DECORATED_RE = re.compile(
    r"^Phase-A-Lock:\s*(UNLOCKED|LOCKED)[ \t]+\([^()\n]+\)[ \t]*$"
)
_PHASE_A_LOCK_REVIEW_RE = re.compile(r"^Phase-A-Lock:\s*LOCKED_FOR_REVIEW[ \t]*$")
_PHASE_A_LOCK_PENDING_REVIEW_RE = re.compile(
    r"^Phase-A-Lock:\s*UNLOCKED[ \t]+pending bridge re-review[ \t]*$"
)
_PHASE_A_H2_RE = re.compile(r"^##(?!#)(?:[ \t]+|$)")
_BRIDGE_RENDERED_SECTION_RE = re.compile(r"^##(?!#)[ \t]+(.+?)[ \t]*$")
_STRICT_STAGED_L4_COMMAND_RE = re.compile(
    r"(?:python3[ \t]+)?tools/checks/enforce_l4_execution_contract\.py"
)
_STRICT_STAGED_L4_COMMAND_WINDOW_CHARS = 800
_STRICT_STAGED_L4_WAVE_RE = re.compile(
    r"--wave-id(?:=|[ \t]+)"
    r"(?:"
    r'"(?P<double>[A-Za-z0-9][A-Za-z0-9_-]*)"'
    r"|"
    r"'(?P<single>[A-Za-z0-9][A-Za-z0-9_-]*)'"
    r"|"
    r"(?P<bare>[A-Za-z0-9][A-Za-z0-9_-]*)"
    r")"
)
_TASKS_TRACKER_NOTE_HEADER_RE = re.compile(
    r"^- Tracker sync note \([^,]+,\s*([^)]+)\):\s*\*\*[^*]+\*\*"
)


def _canonical_phase_a_section_title(stripped_line: str) -> str:
    title = stripped_line.lstrip("#").strip().lower()
    title = re.sub(r"^[0-9]+(?:\.[0-9]+)*\.\s*", "", title)
    title = re.sub(r"\s+", " ", title).rstrip(":").strip()
    canonical = title
    for required in _REQUIRED_PHASE_A_SECTION_TITLES:
        if (
            title == required
            or title.startswith(f"{required} ")
            or title.startswith(f"{required}(")
            or title.startswith(f"{required}:")
        ):
            canonical = required
            break
    if canonical == title:
        for alias, target in _PHASE_A_SECTION_TITLE_ALIASES.items():
            if (
                title == alias
                or title.startswith(f"{alias} ")
                or title.startswith(f"{alias}(")
                or title.startswith(f"{alias}:")
            ):
                canonical = target
                break
    return canonical


def _extract_phase_a_sections(
    content: str,
    *,
    suppress_request_body_headings: bool = False,
) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_title: str | None = None
    current_body: list[str] = []
    seen_generated_scope = False
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if _PHASE_A_H2_RE.match(stripped):
            canonical_title = _canonical_phase_a_section_title(stripped)
            if suppress_request_body_headings and not seen_generated_scope:
                if canonical_title != "scope":
                    continue
                seen_generated_scope = True
            if (
                current_title == "request from post-merge supervisor"
                and suppress_request_body_headings
                and canonical_title not in _REQUIRED_PHASE_A_SECTION_TITLES
            ):
                current_body.append(line)
                continue
            if current_title is not None:
                sections.setdefault(current_title, []).append(
                    "\n".join(current_body).strip()
                )
            current_title = canonical_title
            current_body = []
            continue
        if current_title is not None:
            current_body.append(line)
    if current_title is not None:
        sections.setdefault(current_title, []).append("\n".join(current_body).strip())
    return sections


def _extract_phase_a_section_titles(content: str) -> set[str]:
    return set(_extract_phase_a_sections(content))


def _phase_a_header_value(content: str, key: str) -> str | None:
    header, _body = _split_plan_header(content)
    prefix = f"{key}:"
    values = [
        line.split(":", 1)[1].strip()
        for line in header.splitlines()
        if line.startswith(prefix)
    ]
    if len(values) != 1:
        return None
    return values[0]


def _first_request_body_line(content: str) -> str | None:
    in_request = False
    for line in content.splitlines():
        stripped = line.strip()
        if _PHASE_A_H2_RE.match(stripped):
            canonical_title = _canonical_phase_a_section_title(stripped)
            if canonical_title == "request from post-merge supervisor":
                in_request = True
                continue
            if in_request and stripped:
                return stripped
        elif in_request and stripped:
            return stripped
    return None


def _looks_like_generated_phase_a_stub(content: str) -> bool:
    """Return True for executor-rendered stubs whose request may contain H2s."""
    if _phase_a_header_lock_value(content) != "UNLOCKED":
        return False
    status = _phase_a_header_value(content, "Status")
    if status != "Phase A (design -- not yet agent-reviewed or bridge-converged)":
        return False
    purpose = _phase_a_header_value(content, "Purpose")
    if not purpose:
        return False
    first_request_line = _first_request_body_line(content)
    return first_request_line == purpose


def _plan_is_placeholder_stub(content: str) -> bool:
    """Return True when a Phase A packet is still a bridge/implementer stub."""
    suppress_request_body_headings = _looks_like_generated_phase_a_stub(content)
    sections = _extract_phase_a_sections(
        content,
        suppress_request_body_headings=suppress_request_body_headings,
    )
    section_titles = set(sections)
    if not section_titles:
        return True
    for title, bodies in sections.items():
        if title in _PHASE_A_PLACEHOLDER_SECTION_TITLES:
            continue
        if title not in _REQUIRED_PHASE_A_SECTION_TITLES:
            return False
        if any(body.strip() for body in bodies):
            return False
    return True


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
            terminal_status = status_snapshot.get("status")

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

            if exit_code is None and not child_pids and terminal_status in {"completed", "hard_gate_failed"}:
                stdout_text, stderr_text = _read_logs()
                return {
                    "exit_code": 0 if terminal_status == "completed" else 1,
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                    "status_path": str(status_path.relative_to(repo_root)),
                    "report_path": str(report_path.relative_to(repo_root)),
                    "last_progress_timestamp": last_progress_ts,
                }

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
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run bridge packet review (--no-diff, non-design) on a plan packet."""
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
        "6. **Grounding / Authorization**: references to TASKS.md authorization "
        "and governing packet. For control-surface L4_ENABLER packets, require "
        "either a wave-bound `FOUNDER_OVERRIDE:<wave_id>` or an explicit "
        "`Authorization: standing pipeline-bug-fix authorization ...` line so "
        "commit automation can derive the same-wave override mechanically.\n\n"
        "A plan with only routing metadata, supervisor request echoes, or empty sections\n"
        "is NOT a plan — it is a stub. Reject stubs with REQUEST_CHANGES.\n\n"
        "## Review Protocol\n\n"
        "- Read only the exact TASKS.md block needed to confirm current-task authorization\n"
        "- Read the governing tracked packet only if the plan is not an obvious stub and "
        "you need sequence/supporting input to verify a concrete plan claim\n"
        "- Treat this as a plan-packet review, not a broad repo red-team pass\n"
        "- If the packet is obviously a stub, reject it immediately from the packet "
        "and TASKS.md evidence; do not spend review budget on unrelated repo sweeps\n"
        "- For an obvious stub, do NOT open governing packets, prior replay notes, "
        "or downstream implementation files before issuing REQUEST_CHANGES\n"
        "- Verify plan work items are grounded in actual codebase state using only "
        "the plan, TASKS.md, and files explicitly referenced by the plan or task\n"
        "- Use repo-local evidence only. Do not browse the web or query external\n"
        "  network resources for this review.\n\n"
    )
    if agent_review_context:
        task_content += (
            "## Decision Discipline After SDK Review\n\n"
            "- Treat completed SDK review artifacts as already-run review input.\n"
            "- Do NOT rerun the same checks unless you have concrete repo-local evidence "
            "that the SDK report is wrong or incomplete.\n"
            "- If the packet is a docs/test-only maintenance or truth-sync packet with "
            "no runtime/substrate delta, keep the review tightly bounded to packet truth, "
            "the cited TASKS.md lines, and the cited local artifacts.\n"
            "- Once you have enough evidence for GO, REQUEST_CHANGES, or QUESTION, emit "
            "the JSON envelope immediately. Do not keep gathering extra evidence after "
            "you have reached a supportable decision.\n\n"
        )
        task_content += agent_review_context + "\n\n"
    task_content += "Questions? Concerns? Thoughts? -- Think hard\n"
    task_path.write_text(task_content, encoding="utf-8")

    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    cmd = [
        sys.executable, str(bridge_script),
    ]
    if bus_dir is not None:
        cmd.extend(["--bus-dir", str(bus_dir)])
    cmd.extend([
        "review",
        "--task-file", str(task_path),
        "--summary", f"Phase A plan review R{round_num}",
        "--reviewer", reviewer,
        "-v", "--no-diff",
    ])
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
        rendered_path = agent_bus_path(repo_root, bus_dir, "rendered", f"{run_id}.md")
        raw_dir = agent_bus_path(repo_root, bus_dir, "raw", run_id)
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


def _extract_phase_a_agent_envelope(text: str) -> dict[str, Any] | None:
    def _extract_direct_envelope(candidate: str) -> dict[str, Any] | None:
        chosen: dict[str, Any] | None = None
        for envelope_match in AGENT_ENVELOPE_RE.finditer(candidate):
            try:
                payload = json.loads(envelope_match.group(1))
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(payload, dict):
                continue
            decision = payload.get("decision")
            if isinstance(decision, str) and "|" in decision:
                continue
            chosen = payload
        return chosen

    envelope = _extract_direct_envelope(text)
    if envelope is not None:
        return envelope

    # Adapter raw output may wrap the envelope inside JSON structures.
    agent_messages: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        # Codex JSONL: {"type":"item.completed","item":{"type":"agent_message","text":"..."}}
        if payload.get("type") == "item.completed":
            item = payload.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                message_text = item.get("text")
                if isinstance(message_text, str) and message_text.strip():
                    agent_messages.append(message_text)
        # Claude stream-json: {"type":"assistant","message":{"content":[{"type":"text","text":"..."}]}}
        elif payload.get("type") == "assistant":
            message = payload.get("message")
            if isinstance(message, dict):
                for block in message.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        message_text = block.get("text")
                        if isinstance(message_text, str) and message_text.strip():
                            agent_messages.append(message_text)
        # Stream result payloads can carry the final envelope as a string.
        result_text = payload.get("result")
        if isinstance(result_text, str) and result_text.strip():
            agent_messages.append(result_text)

    if not agent_messages:
        return None
    return _extract_direct_envelope("\n".join(agent_messages))


def _parse_phase_a_findings(render_content: str) -> list[dict[str, Any]]:
    """Parse findings from bridge rendered output for blocking/non-blocking classification.

    Looks for the structured findings block in the reviewer turn. Each finding
    keeps the reviewer evidence needed for packet rewrites.
    """
    findings: list[dict[str, Any]] = []

    def _envelope_findings(payload: dict[str, Any]) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        for finding in payload.get("findings", []):
            if not isinstance(finding, dict):
                continue
            parsed.append({
                "class": finding.get("class", ""),
                "severity": finding.get("severity", "medium"),
                "title": finding.get("title", ""),
                "detail": finding.get("detail", ""),
                "disposition": finding.get("disposition", ""),
                "file": finding.get("file", ""),
                "line_start": finding.get("line_start"),
                "line_end": finding.get("line_end"),
                "evidence_cmd": finding.get("evidence_cmd", ""),
                "evidence_result": finding.get("evidence_result", ""),
                "status": finding.get("status", ""),
            })
        return parsed

    envelope = _extract_phase_a_agent_envelope(render_content)
    if envelope is not None:
        return _envelope_findings(envelope)

    return findings


def _format_phase_a_blocking_findings(findings: list[dict[str, Any]]) -> str:
    """Format reviewer findings for the Phase A implementer prompt."""
    formatted: list[str] = []
    for idx, finding in enumerate(findings, 1):
        severity = finding.get("severity", "?")
        title = finding.get("title", "untitled")
        detail = (finding.get("detail") or "").strip()
        finding_class = (finding.get("class") or "").strip()
        file_ref = (finding.get("file") or "").strip()
        line_start = finding.get("line_start")
        line_end = finding.get("line_end")
        evidence_cmd = (finding.get("evidence_cmd") or "").strip()
        evidence_result = (finding.get("evidence_result") or "").strip()

        location = file_ref
        if file_ref and isinstance(line_start, int):
            location = f"{file_ref}:{line_start}"
            if isinstance(line_end, int) and line_end != line_start:
                location += f"-{line_end}"

        lines = [f"{idx}. [{severity}] {title}"]
        if finding_class:
            lines.append(f"   Class: {finding_class}")
        if location:
            lines.append(f"   Reference: {location}")
        if detail:
            lines.append(f"   Reviewer detail: {detail[:500]}")
        if evidence_result:
            lines.append(f"   Evidence result: {evidence_result[:700]}")
        if evidence_cmd:
            lines.append(f"   Reproduce with: {evidence_cmd[:500]}")
        formatted.append("\n".join(lines))
    return "\n\n".join(formatted)


def _extract_bridge_decision(
    render_content: str,
    *,
    rendered_path: Path | None = None,
) -> str:
    """Parse the canonical bridge decision line from rendered output.

    Structured ``## Turns`` output is parsed by turn status: completed
    reviewer turns outrank stale turns only when their raw-output artifact is
    verifiable.  Stale-only output remains fail-closed.  Summary text is
    ignored as untrusted rendered content so quoted headings cannot synthesize
    a fake completed turn.

    Unstructured fallback output keeps first-wins semantics: the first
    non-SYNTHETIC ``Decision:`` token is authoritative.  A later appended
    ``Decision: GO`` cannot override an earlier ``Decision: REQUEST_CHANGES``.
    """
    rendered_turns: list[dict[str, Any]] = []
    current_turn: dict[str, Any] | None = None
    in_turns_section = False
    saw_turns_section = False
    for raw_line in render_content.splitlines():
        line = raw_line.strip()
        if not in_turns_section:
            section_match = _BRIDGE_RENDERED_SECTION_RE.match(line)
            if section_match and section_match.group(1).strip().lower() == "turns":
                in_turns_section = True
                saw_turns_section = True
            continue
        section_match = _BRIDGE_RENDERED_SECTION_RE.match(line)
        if section_match:
            if current_turn is not None and current_turn.get("_turn_complete"):
                rendered_turns.append(current_turn)
                current_turn = None
            break
        turn_heading_match = BRIDGE_TURN_HEADING_RE.match(line)
        if turn_heading_match:
            if current_turn is not None:
                if not current_turn.get("_turn_complete"):
                    continue
                if not current_turn.get("_saw_post_raw_blank"):
                    continue
                if not _bridge_turn_heading_can_follow(
                    current_turn,
                    turn_heading_match.group("turn_id"),
                ):
                    continue
                rendered_turns.append(current_turn)
            current_turn = {
                "turn_id": turn_heading_match.group("turn_id"),
                "role": turn_heading_match.group("role").lower(),
                "status": "",
                "decision": "",
                "_in_summary": False,
                "_claimed_after_summary": False,
                "_turn_complete": False,
                "_saw_post_raw_blank": False,
            }
            continue
        if current_turn is None:
            continue
        if current_turn.get("_turn_complete"):
            # The turn's own raw-output line terminates trusted rendered
            # metadata. A canonical next turn is separated by the renderer's
            # blank line; same-turn injected headings before that delimiter
            # stay inside untrusted output.
            if not line:
                current_turn["_saw_post_raw_blank"] = True
            continue
        if current_turn.get("_in_summary"):
            if line.startswith("- Claimed files:"):
                current_turn["_claimed_after_summary"] = True
                continue
            raw_output_path = _bridge_turn_raw_output_for_turn(current_turn, line)
            if current_turn.get("_claimed_after_summary") and raw_output_path:
                current_turn["_raw_output_path"] = raw_output_path
                current_turn["_turn_complete"] = True
                current_turn["_in_summary"] = False
            continue
        if line.startswith("- Summary:"):
            current_turn["_in_summary"] = True
            continue
        if line.startswith("- Status:"):
            current_turn["status"] = line.split(":", 1)[1].strip().split()[0].lower()
        elif line.startswith("- Decision:"):
            match = BRIDGE_DECISION_RE.search(line)
            if match:
                current_turn["decision"] = match.group(1)
        else:
            raw_output_path = _bridge_turn_raw_output_for_turn(current_turn, line)
            if not raw_output_path:
                continue
            current_turn["_raw_output_path"] = raw_output_path
            current_turn["_turn_complete"] = True
    if current_turn is not None and current_turn.get("_turn_complete"):
        rendered_turns.append(current_turn)
    if rendered_turns:
        completed_reviewer_decisions: list[str] = []
        completed_decisions: list[str] = []
        stale_fallback = ""
        saw_stale_turn = False
        saw_completed_turn = False
        for turn in rendered_turns:
            decision = turn.get("decision", "")
            status = turn.get("status", "")
            role = turn.get("role", "")
            if not status or not decision or decision == "SYNTHETIC":
                continue
            if status == "completed":
                if (
                    (saw_stale_turn or saw_completed_turn)
                    and not _bridge_turn_raw_output_artifact_verified(
                        turn,
                        rendered_path,
                    )
                ):
                    continue
                saw_completed_turn = True
                if role == "reviewer":
                    completed_reviewer_decisions.append(decision)
                else:
                    completed_decisions.append(decision)
                continue
            if status == "stale":
                stale_fallback = stale_fallback or decision
                saw_stale_turn = True
        if completed_reviewer_decisions:
            return completed_reviewer_decisions[-1]
        if completed_decisions:
            return completed_decisions[-1]
        if stale_fallback:
            return stale_fallback
    if saw_turns_section:
        return ""

    decisions = [match.group(1) for match in BRIDGE_DECISION_RE.finditer(render_content)]
    if not decisions:
        return ""
    # First-wins: the first non-SYNTHETIC decision is authoritative.
    # This prevents an appended later Decision: token from silently
    # flipping the bridge outcome (bridge R3 finding).
    for decision in decisions:
        if decision != "SYNTHETIC":
            return decision
    return decisions[-1]


def _bridge_turn_raw_output_for_turn(turn: dict[str, Any], line: str) -> str:
    match = BRIDGE_TURN_RAW_OUTPUT_RE.match(line)
    if not match:
        return ""
    turn_id = str(turn.get("turn_id", "") or "").strip()
    if not turn_id:
        return ""
    raw_output_path = match.group("path").strip()
    if Path(raw_output_path).name != f"{turn_id}.txt":
        return ""
    return raw_output_path


def _bridge_turn_raw_output_artifact_verified(
    turn: dict[str, Any],
    rendered_path: Path | None,
) -> bool:
    raw_output_path = str(turn.get("_raw_output_path", "") or "").strip()
    if not raw_output_path or rendered_path is None:
        return False
    raw_path = Path(raw_output_path)
    if raw_path.is_absolute():
        return _bridge_turn_raw_output_matches_turn(turn, raw_path)
    rendered = Path(rendered_path)
    bus_dir = rendered.parent.parent
    repo_root = bus_dir.parent
    candidates = [repo_root / raw_path, bus_dir / raw_path]
    return any(_bridge_turn_raw_output_matches_turn(turn, candidate) for candidate in candidates)


def _bridge_turn_raw_output_matches_turn(turn: dict[str, Any], raw_path: Path) -> bool:
    if not raw_path.is_file():
        return False
    try:
        raw_text = raw_path.read_text(encoding="utf-8")
    except OSError:
        return False
    envelope = _extract_phase_a_agent_envelope(raw_text)
    if not envelope:
        return False

    turn_id = str(turn.get("turn_id", "") or "").strip()
    role = str(turn.get("role", "") or "").strip().lower()
    decision = str(turn.get("decision", "") or "").strip()
    if not turn_id or not role or not decision:
        return False
    envelope_turn_id = str(envelope.get("turn_id", "") or "").strip()
    if envelope_turn_id != turn_id and not _bridge_turn_id_matches_round_alias(
        turn_id,
        envelope_turn_id,
    ):
        return False
    if str(envelope.get("agent_role", "") or "").strip().lower() != role:
        return False

    job_id = _bridge_turn_job_prefix(turn_id)
    if job_id and str(envelope.get("job_id", "") or "").strip() != job_id:
        return False

    envelope_decision = str(envelope.get("decision", "") or "").strip()
    if envelope_decision and envelope_decision != decision:
        return False
    return True


def _bridge_turn_job_prefix(turn_id: str) -> str:
    match = BRIDGE_TURN_JOB_PREFIX_RE.match(turn_id)
    if not match:
        return ""
    return match.group("job_id")


def _bridge_turn_id_matches_round_alias(turn_id: str, envelope_turn_id: str) -> bool:
    """Accept bridge agent envelopes that report the round alias for the turn."""
    if not turn_id or not envelope_turn_id:
        return False
    match = BRIDGE_TURN_ROUND_RE.search(turn_id)
    if not match:
        return False
    return envelope_turn_id == f"round-{match.group('round_no')}"


def _bridge_turn_heading_can_follow(turn: dict[str, Any], next_turn_id: str) -> bool:
    current_turn_id = str(turn.get("turn_id", "") or "").strip()
    next_turn_id = str(next_turn_id or "").strip()
    if current_turn_id and current_turn_id == next_turn_id:
        return False
    current_prefix = _bridge_turn_job_prefix(current_turn_id)
    next_prefix = _bridge_turn_job_prefix(next_turn_id)
    if current_prefix and next_prefix and current_prefix != next_prefix:
        return False
    return True


def _split_plan_header(content: str) -> tuple[str, str]:
    """Split plan packet into header and body at the first ``## `` heading.

    The header contains metadata lines (Date, Status, Phase-A-Lock, Task,
    Wave ID) that precede any markdown H2 section heading.  Body occurrences
    of control-line patterns (e.g. ``Phase-A-Lock: UNLOCKED`` quoted inside
    a code fence or documentation) must never be counted as control lines.

    Returns ``(header, body)`` where ``header + body == content``.
    If no ``## `` heading exists, the entire content is treated as header.
    """
    lines = content.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("## "):
            return "".join(lines[:i]), "".join(lines[i:])
    return content, ""


def _phase_a_header_lock_value(content: str) -> str | None:
    """Return the canonical header lock value, or None when absent/malformed."""
    header, _body = _split_plan_header(content)
    lock_lines = [
        line
        for line in header.splitlines()
        if line.lstrip().startswith("Phase-A-Lock:")
    ]
    if len(lock_lines) != 1:
        return None
    line = lock_lines[0]
    if line != line.lstrip():
        return None
    canonical_match = _PHASE_A_LOCK_CANONICAL_RE.match(line)
    if canonical_match:
        return canonical_match.group(1)
    decorated_match = _PHASE_A_LOCK_DECORATED_RE.match(line)
    if decorated_match:
        return decorated_match.group(1)
    return None


def _phase_a_header_allows_placeholder_refresh(content: str) -> bool:
    """Return True when header metadata proves a stub may be refreshed in place."""
    header, _body = _split_plan_header(content)
    lock_lines = [
        line
        for line in header.splitlines()
        if line.lstrip().startswith("Phase-A-Lock:")
    ]
    if not lock_lines:
        return True
    return len(lock_lines) == 1 and _phase_a_header_lock_value(content) == "UNLOCKED"


def _ensure_phase_a_identity_header(
    content: str,
    routing_record: dict[str, Any] | None,
) -> str:
    """Insert missing authoritative Task/Wave headers from routing context."""
    if not routing_record:
        return content
    task_id = str(routing_record.get("task_id", "") or "").strip()
    wave_id = str(
        routing_record.get("wave_name", "")
        or routing_record.get("wave_id", "")
        or ""
    ).strip()
    if not task_id and not wave_id:
        return content

    header, body = _split_plan_header(content)
    hdr_lines = header.splitlines()
    has_task = False
    blank_task_line: int | None = None
    for i, line in enumerate(hdr_lines):
        stripped = line.strip()
        if not stripped.startswith("Task:"):
            continue
        if stripped.split(":", 1)[1].strip():
            has_task = True
            break
        if blank_task_line is None:
            blank_task_line = i
    has_wave = any(
        line.strip().startswith(("Wave ID:", "wave_id:"))
        for line in hdr_lines
    )
    insertions: list[str] = []
    header_changed = False
    if task_id and not has_task and blank_task_line is not None:
        hdr_lines[blank_task_line] = f"Task: {task_id}"
        header_changed = True
    elif task_id and not has_task:
        insertions.append(f"Task: {task_id}")
    if wave_id and not has_wave:
        insertions.append(f"Wave ID: {wave_id}")
    if not insertions and not header_changed:
        return content

    insert_after = 0
    for i, line in enumerate(hdr_lines):
        stripped = line.strip()
        if stripped.startswith(("#", "Date:", "Status:")):
            insert_after = i + 1
        if stripped.startswith("Phase-A-Lock:"):
            break
    hdr_lines[insert_after:insert_after] = insertions
    header = "\n".join(hdr_lines)
    if not header.endswith("\n"):
        header += "\n"
    return header + body


def _extract_strict_staged_l4_wave_ids(content: str) -> list[str]:
    """Return unique --wave-id values from strict staged L4 commands."""
    wave_ids: list[str] = []
    seen: set[str] = set()
    for command_match in _STRICT_STAGED_L4_COMMAND_RE.finditer(content):
        command = content[
            command_match.start():
            command_match.start() + _STRICT_STAGED_L4_COMMAND_WINDOW_CHARS
        ]
        for boundary in ("`", "\n## "):
            boundary_at = command.find(boundary)
            if boundary_at != -1:
                command = command[:boundary_at]
        command = re.sub(r"\\\r?\n", " ", command)
        command = re.sub(r"\s+", " ", command)
        if "--staged" not in command:
            continue
        for wave_match in _STRICT_STAGED_L4_WAVE_RE.finditer(command):
            raw_wave_id = (
                wave_match.group("double")
                or wave_match.group("single")
                or wave_match.group("bare")
                or ""
            )
            wave_id = normalize_wave_id(raw_wave_id)
            if not wave_id or wave_id in seen:
                continue
            seen.add(wave_id)
            wave_ids.append(wave_id)
    return wave_ids


def _phase_a_scope_mentions_tasks(content: str) -> bool:
    """Return true when the Phase A Scope section explicitly includes TASKS.md."""
    sections = _extract_phase_a_sections(content)
    return any("TASKS.md" in body for body in sections.get("scope", []))


def _phase_a_same_wave_authorization_exists(content: str, wave_id: str) -> bool:
    """Return true when the packet carries wave-bound implementation authority."""
    normalized_wave = normalize_wave_id(wave_id)
    if not normalized_wave or normalized_wave == "wave-unknown":
        return False
    expected = f"FOUNDER_OVERRIDE:{normalized_wave}"
    sections = _extract_phase_a_sections(content)
    for body in sections.get("grounding", []):
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if expected not in line:
                continue
            candidate = re.sub(r"^(?:[-*]|\d+\.)\s*", "", line).strip()
            candidate = candidate.strip("` ")
            candidate = candidate.rstrip(".,;").strip("` ")
            if candidate == expected:
                return True
            lower_candidate = candidate.lower()
            for prefix in (
                "same-wave authorization:",
                "same wave authorization:",
                "authorization:",
                "founder override:",
            ):
                if not lower_candidate.startswith(prefix):
                    continue
                value = candidate[len(prefix):].strip().strip("` ")
                value = value.rstrip(".,;").strip("` ")
                if value == expected:
                    return True
    return False


def _tasks_tracker_note_wave_exists(repo_root: Path, wave_id: str) -> bool:
    """Return true when TASKS.md has a detector-visible tracker note wave id."""
    normalized_wave = normalize_wave_id(wave_id)
    if not normalized_wave:
        return False
    try:
        lines = (repo_root / "TASKS.md").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        match = _TASKS_TRACKER_NOTE_HEADER_RE.match(line)
        if not match:
            continue
        if normalize_wave_id(match.group(1)) != normalized_wave:
            continue
        if "Class:" in line or "FOUNDER_OVERRIDE:" in line:
            return True
    return False


def _phase_a_strict_staged_l4_guard_errors(
    repo_root: Path,
    *,
    plan_path: str,
    content: str,
    routing_record: dict[str, Any] | None,
) -> list[str]:
    """Fail closed before Phase A lock for ungrounded strict staged L4 commands."""
    strict_wave_ids = _extract_strict_staged_l4_wave_ids(content)
    if not strict_wave_ids:
        return []

    errors: list[str] = []
    if not _phase_a_scope_mentions_tasks(content):
        errors.append(
            "packet requires strict staged L4 --wave-id validation but Scope does "
            "not include TASKS.md tracker-sync authority"
        )

    packet_wave_id = _phase_a_wave_id(
        routing_record or {},
        plan_name=Path(plan_path).stem,
        rel_plan_path=plan_path,
        plan_content=content,
    )
    if not _phase_a_same_wave_authorization_exists(content, packet_wave_id):
        errors.append(
            "packet requires strict staged L4 --wave-id validation but lacks "
            f"same-wave authorization FOUNDER_OVERRIDE:{packet_wave_id}"
        )

    missing_tracker = [
        wave_id
        for wave_id in strict_wave_ids
        if not _tasks_tracker_note_wave_exists(repo_root, wave_id)
    ]
    if missing_tracker:
        errors.append(
            "TASKS.md lacks detector-visible tracker sync note(s) for strict "
            "staged L4 wave id(s): " + ", ".join(missing_tracker)
        )
    return errors


def _is_strict_staged_l4_guard_error(message: str) -> bool:
    """Return true when Phase A failed at the strict L4 missing-tracker guard."""
    return (
        message.startswith("Phase A strict staged L4 guard failed before lock:")
        and "TASKS.md lacks detector-visible tracker sync note(s)" in message
    )


def _normalize_phase_a_relpath(path: str | Path) -> str:
    return Path(str(path)).as_posix().lstrip("./")


def _is_phase_a_generated_runtime_path(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    if not parts:
        return False
    first = parts[0]
    return first in {".git", ".scratch", ".pytest_cache", "__pycache__"} or (
        first == ".agent_bus" or first.startswith(".agent_bus-")
    )


def _parse_git_porcelain_z_paths(output: bytes) -> set[str]:
    paths: set[str] = set()
    entries = output.split(b"\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry or len(entry) < 4:
            continue
        status = entry[:2].decode("ascii", errors="replace")
        path = entry[3:].decode("utf-8", errors="surrogateescape")
        if path:
            paths.add(path)
        if ("R" in status or "C" in status) and i < len(entries):
            old_path = entries[i].decode("utf-8", errors="surrogateescape")
            i += 1
            if old_path:
                paths.add(old_path)
    return paths


def _git_dirty_paths(repo_root: Path) -> set[str] | None:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return _parse_git_porcelain_z_paths(proc.stdout)


def _iter_phase_a_recovery_repo_files(repo_root: Path) -> set[str]:
    paths: set[str] = set()
    for root, dirnames, filenames in os.walk(repo_root):
        root_path = Path(root)
        rel_root = "." if root_path == repo_root else root_path.relative_to(repo_root).as_posix()
        kept_dirnames = []
        for dirname in dirnames:
            rel_dir = dirname if rel_root == "." else f"{rel_root}/{dirname}"
            if not _is_phase_a_generated_runtime_path(rel_dir):
                kept_dirnames.append(dirname)
        dirnames[:] = kept_dirnames
        for filename in filenames:
            rel_file = filename if rel_root == "." else f"{rel_root}/{filename}"
            if not _is_phase_a_generated_runtime_path(rel_file):
                paths.add(rel_file)
    return paths


def _phase_a_file_fingerprint(path: Path) -> str:
    if not path.exists():
        return "missing"
    if not path.is_file():
        return "non-file"
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        return f"unreadable:{exc.__class__.__name__}"
    return digest.hexdigest()


def _strict_l4_recovery_scope_snapshot(
    repo_root: Path,
    allowed_relpaths: set[str],
) -> dict[str, str]:
    dirty_paths = _git_dirty_paths(repo_root)
    if dirty_paths is None:
        snapshot_paths = _iter_phase_a_recovery_repo_files(repo_root)
    else:
        snapshot_paths = set(dirty_paths)
    snapshot_paths.update(allowed_relpaths)
    return {
        path: _phase_a_file_fingerprint(repo_root / path)
        for path in sorted(snapshot_paths)
        if not _is_phase_a_generated_runtime_path(path)
    }


def _changed_paths_between_snapshots(
    before: dict[str, str],
    after: dict[str, str],
) -> list[str]:
    return sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )


def _strict_staged_l4_guard_recovery_prompt(
    *,
    rel_plan_path: str,
    current_plan_content: str,
    guard_error: str,
) -> str:
    """Build a bounded implementer prompt for Phase A strict L4 tracker recovery."""
    return (
        "You are repairing a Phase A strict staged L4 pre-lock guard failure.\n\n"
        f"IMPORTANT: Write changes ONLY to `{rel_plan_path}` and `TASKS.md`. "
        "Do NOT create new files. Do NOT write to any other path.\n\n"
        "The bridge already returned GO, but Phase A refused to lock the packet "
        "because strict staged L4 validation requires detector-visible same-wave "
        "tracker authority before implementation can proceed.\n\n"
        f"Guard failure:\n{guard_error}\n\n"
        "Required recovery:\n"
        "- Add or repair detector-visible TASKS.md tracker sync note(s) for every "
        "missing wave id named in the guard failure.\n"
        "- Keep the tracker note wave id, Class, Packet, evidence command, "
        "evidence delta, progress proofs, FOUNDER_OVERRIDE, indicator artifact, "
        "and invariant metadata parseable by `tools/checks/enforce_l4_execution_contract.py`.\n"
        "- Ensure the Phase A packet Scope includes `TASKS.md` when strict staged "
        "L4 validation is part of acceptance.\n"
        "- Ensure the Phase A packet Grounding / Authorization carries exact "
        "same-wave authorization, for example `FOUNDER_OVERRIDE:<wave_id>`.\n"
        "- Preserve the existing packet scope and stop conditions. Do not broaden "
        "into implementation, runtime, workflow, branch-protection, or unrelated "
        "documentation changes.\n\n"
        "This is a guard recovery task, not a broad repo investigation. Use only "
        "the current packet and the exact TASKS.md tracker area needed for the "
        "missing wave id.\n\n"
        f"## Current plan content:\n\n{current_plan_content}\n\n"
        "Questions? Concerns? Thoughts? -- Think hard\n"
    )


def lock_plan(
    repo_root: Path,
    plan_path: str,
    *,
    routing_record: dict[str, Any] | None = None,
) -> None:
    """Set Phase-A-Lock: LOCKED in a plan packet.

    Idempotent: if the packet is already LOCKED, applies status text cleanup
    and returns without error. Fails closed with a structured error if the
    control line is missing, malformed, or duplicated.

    Only the header section (before the first ``## `` heading) is inspected
    for Phase-A-Lock control lines.  Body occurrences (code fences, docs)
    are ignored so they cannot inflate the control-line count.
    """
    full_path = repo_root / plan_path
    content = full_path.read_text(encoding="utf-8")
    content_with_identity = _ensure_phase_a_identity_header(content, routing_record)
    if content_with_identity != content:
        content = content_with_identity
        full_path.write_text(content, encoding="utf-8")

    # Split at first ## heading — control lines live in the header only.
    header, body = _split_plan_header(content)

    # Use [ \t]* (not \s*) before $ to avoid greedily eating newlines
    # that separate the header from the body.  \s includes \n which,
    # combined with multiline $, can consume blank lines between the
    # control line and the first ## heading — causing header+body
    # concatenation without a newline separator (bridge R2 finding).
    phase_a_lock_header_lines = [
        line
        for line in header.splitlines()
        if line.lstrip().startswith("Phase-A-Lock:")
    ]
    decorated_lock_values: list[str] = []
    review_lock_lines: list[str] = []
    malformed_lock_lines: list[str] = []
    for line in phase_a_lock_header_lines:
        if line != line.lstrip():
            malformed_lock_lines.append(line)
            continue
        canonical_match = _PHASE_A_LOCK_CANONICAL_RE.match(line)
        if canonical_match:
            continue
        decorated_match = _PHASE_A_LOCK_DECORATED_RE.match(line)
        if decorated_match:
            decorated_lock_values.append(decorated_match.group(1))
            continue
        if (
            _PHASE_A_LOCK_REVIEW_RE.match(line)
            or _PHASE_A_LOCK_PENDING_REVIEW_RE.match(line)
        ):
            review_lock_lines.append(line)
            continue
        malformed_lock_lines.append(line)
    if len(phase_a_lock_header_lines) > 1:
        raise PhaseAExecutorError(
            f"Expected exactly one Phase-A-Lock control line in {plan_path}; "
            "mixed or duplicate canonical Phase-A-Lock metadata is not allowed, "
            f"found {len(phase_a_lock_header_lines)} header lines"
        )
    if malformed_lock_lines:
        raise PhaseAExecutorError(
            f"Expected Phase-A-Lock to be exactly UNLOCKED or LOCKED in {plan_path}, "
            f"found malformed header lines: {', '.join(malformed_lock_lines)}"
        )
    if decorated_lock_values:
        canonical_lock_line = f"Phase-A-Lock: {decorated_lock_values[0]}"
        hdr_lines = header.splitlines(keepends=True)
        for i, line in enumerate(hdr_lines):
            if line.rstrip("\r\n") == phase_a_lock_header_lines[0]:
                line_ending = "\n" if line.endswith("\n") else ""
                hdr_lines[i] = f"{canonical_lock_line}{line_ending}"
                break
        else:
            raise PhaseAExecutorError(
                f"Expected exactly one Phase-A-Lock header line in {plan_path}, "
                f"found no rewritable decorated line"
            )
        header = "".join(hdr_lines)
        content = header + body
        full_path.write_text(content, encoding="utf-8")
        header, body = _split_plan_header(content)
    if review_lock_lines:
        # Bridge implementers sometimes use this transient sentinel while the
        # packet is under review.  After bridge GO, lock_plan owns the canonical
        # transition.  Normalize directly to the final LOCKED state in memory so
        # an interrupted process cannot persist a dispatchable UNLOCKED packet.
        canonical_lock_line = "Phase-A-Lock: LOCKED"
        hdr_lines = header.splitlines(keepends=True)
        for i, line in enumerate(hdr_lines):
            if line.rstrip("\r\n") == phase_a_lock_header_lines[0]:
                line_ending = "\n" if line.endswith("\n") else ""
                hdr_lines[i] = f"{canonical_lock_line}{line_ending}"
                break
        else:
            raise PhaseAExecutorError(
                f"Expected exactly one Phase-A-Lock header line in {plan_path}, "
                f"found no rewritable review sentinel"
            )
        header = "".join(hdr_lines)
        content = header + body
        header, body = _split_plan_header(content)
    unlocked_lines = re.findall(r"(?m)^Phase-A-Lock:\s*UNLOCKED[ \t]*$", header)
    locked_lines = re.findall(r"(?m)^Phase-A-Lock:\s*LOCKED[ \t]*$", header)
    total = len(unlocked_lines) + len(locked_lines)
    if total == 0:
        # No lock line exists — insert one after the header block.
        # The implementer may have rewritten the stub without including
        # the Phase-A-Lock line. Insert it after Status: or Date: lines.
        hdr_lines = header.splitlines()
        insert_after = 0
        for i, line in enumerate(hdr_lines):
            stripped = line.strip()
            if stripped.startswith(("Status:", "Date:", "Task:", "Wave ID:")):
                insert_after = i + 1
        hdr_lines.insert(insert_after, "Phase-A-Lock: UNLOCKED")
        header = "\n".join(hdr_lines)
        if not header.endswith("\n"):
            header += "\n"
        content = header + body
        full_path.write_text(content, encoding="utf-8")
        # Recompute after insert (header only)
        header, body = _split_plan_header(content)
        unlocked_lines = re.findall(r"(?m)^Phase-A-Lock:\s*UNLOCKED[ \t]*$", header)
        locked_lines = re.findall(r"(?m)^Phase-A-Lock:\s*LOCKED[ \t]*$", header)
        total = len(unlocked_lines) + len(locked_lines)
    if total > 1:
        raise PhaseAExecutorError(
            f"Expected exactly one Phase-A-Lock control line in {plan_path}, "
            f"found {len(unlocked_lines)} unlocked and {len(locked_lines)} locked"
        )
    # Exactly one control line exists — operate on header, then rejoin.
    if unlocked_lines:
        strict_l4_errors = _phase_a_strict_staged_l4_guard_errors(
            repo_root,
            plan_path=plan_path,
            content=content,
            routing_record=routing_record,
        )
        if strict_l4_errors:
            raise PhaseAExecutorError(
                "Phase A strict staged L4 guard failed before lock: "
                + "; ".join(strict_l4_errors)
            )
        header, lock_replacements = re.subn(
            r"(?m)^Phase-A-Lock:\s*UNLOCKED[ \t]*$",
            "Phase-A-Lock: LOCKED",
            header,
            count=1,
        )
        if lock_replacements != 1:
            raise PhaseAExecutorError(
                f"Expected one unlock line in {plan_path}, found {lock_replacements}"
            )
    # Already LOCKED — idempotent, just apply status text cleanup below.
    # Update the Status field in the HEADER only (P2 finding PR #749:
    # body Status: lines must not be rewritten).
    header, status_replacements = re.subn(
        r"(?m)^Status:\s*.*$",
        "Status: Phase B (locked, implementing)",
        header,
        count=1,
    )
    if status_replacements == 0:
        print(
            f"[phase-a] WARNING: lock_plan found no Status: line in {plan_path}; "
            "Phase B status not set",
            file=sys.stderr,
        )
    content = header + body
    full_path.write_text(content, encoding="utf-8")


def _phase_a_task_id(routing_record: dict[str, Any], plan_content: str) -> str:
    task_id = str(routing_record.get("task_id") or "").strip()
    if task_id:
        return task_id
    for line in plan_content.splitlines():
        if line.strip().startswith("Task:"):
            value = line.split("Task:", 1)[1].strip()
            if value:
                return value
    return "[PIPELINE-AGENT-PAGER]"


def _phase_a_wave_id(
    routing_record: dict[str, Any],
    *,
    plan_name: str,
    rel_plan_path: str,
    plan_content: str,
) -> str:
    for line in plan_content.splitlines():
        if line.strip().lower().startswith("wave id:"):
            value = line.split(":", 1)[1].strip().strip("`")
            if value:
                return normalize_wave_id(value)
    candidate = (
        str(routing_record.get("wave_name") or routing_record.get("wave_id") or "").strip()
        or Path(rel_plan_path).stem
        or plan_name
    )
    return normalize_wave_id(candidate)


def _emit_phase_a_event(
    repo_root: Path,
    *,
    routing_record: dict[str, Any],
    plan_name: str,
    rel_plan_path: str,
    event_type: str,
    state: str,
    transition_key: str,
    summary: str,
    artifact_paths: dict[str, str] | None = None,
    bus_dir: str | Path | None = None,
) -> dict[str, Any]:
    plan_content = ""
    try:
        plan_content = (repo_root / rel_plan_path).read_text(encoding="utf-8")
    except OSError:
        pass
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=bus_dir,
        event_type=event_type,
        wave_id=_phase_a_wave_id(
            routing_record,
            plan_name=plan_name,
            rel_plan_path=rel_plan_path,
            plan_content=plan_content,
        ),
        task_id=_phase_a_task_id(routing_record, plan_content),
        plan_path=rel_plan_path,
        phase="phase_a",
        state=state,
        transition_key=transition_key,
        summary=summary,
        reason=summary,
        artifact_paths=artifact_paths,
    )


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
    bus_dir: str | Path | None = None,
    routing_record_override: dict[str, Any] | None = None,
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

    try:
        resolve_agent_bus_dir(repo_root, bus_dir)
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
    implementer_backend = config.get("backends", {}).get("phase_a_executor", "codex")
    if not isinstance(implementer_backend, str) or not implementer_backend.strip():
        raise PhaseAExecutorError(
            "Invalid implementer backend "
            f"{implementer_backend!r} for phase_a_executor; expected non-empty string"
        )
    implementer_backend = implementer_backend.strip()

    # Load routing record for scope context
    try:
        if routing_record_override is not None:
            routing_record = dict(routing_record_override)
        else:
            routing_record = load_routing_record(repo_root, bus_dir=bus_dir)
        scope = extract_plan_scope(routing_record)
    except (PhaseAExecutorError, ExecutorCommonError):
        routing_record = {}
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
    try:
        _emit_phase_a_event(
            repo_root,
            routing_record=routing_record,
            plan_name=plan_name,
            rel_plan_path=rel_plan_path,
            event_type="phase_a_entered",
            state="entered",
            transition_key=f"{rel_plan_path}:entered",
            summary=f"Phase A entered for {rel_plan_path}",
            artifact_paths={"plan": rel_plan_path},
            bus_dir=bus_dir,
        )
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"Phase A pager emission failed on entry: {exc}"
        return result
    review_depth = resolve_review_depth(config, "phase_a")
    agent_timeout = config.get("timeouts", {}).get("agent_review", 900)
    plan_content = plan_path.read_text(encoding="utf-8")
    defer_agent_review = _plan_is_placeholder_stub(plan_content)

    def _run_phase_a_agent_review(log_label: str) -> tuple[bool, str]:
        log(log_label)
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
            return False, ""

        if agent_result["exit_code"] == 1:
            log(
                "Agent review returned semantic blocker findings (exit=1); "
                "continuing to bridge for contextual blocking/non-blocking classification"
            )
            result["agent_review_warning_only"] = True
        elif agent_result["exit_code"] == 2:
            log("Agent review returned soft warnings (exit=2) — continuing to bridge")
            result["agent_review_warning_only"] = True

        if result.get("agent_review_report_path"):
            status_summary = ""
            if result.get("agent_review_status_path"):
                status_summary = _read_agent_status_diagnostic(
                    repo_root / result["agent_review_status_path"]
                )
            agent_review_context = "## SDK Agent Review Artifacts\n\n"
            agent_review_context += f"- exit_code: {result.get('agent_exit_code')}\n"
            if status_summary:
                agent_review_context += f"- status_summary: {status_summary}\n"
            agent_review_context += f"- report: {result.get('agent_review_report_path')}\n"
            agent_review_context += f"- status: {result.get('agent_review_status_path')}\n"
            agent_review_context += f"- stdout: {result.get('agent_review_stdout_path')}\n\n"
            agent_review_context += (
                "Bridge must treat SDK findings as review inputs for contextual "
                "blocking/non-blocking classification. Semantic SDK negatives are "
                "not automatic current-step blockers by themselves."
            )
            return True, agent_review_context
        return True, ""

    def _run_bridge_convergence(*, start_round: int, agent_review_context: str) -> bool:
        for round_num in range(start_round, max_bridge_rounds + 1):
            bridge_job_id = f"phase-a-r{round_num}-{uuid.uuid4().hex[:8]}"
            log(f"Bridge design review round {round_num}/{max_bridge_rounds} (job={bridge_job_id})...")
            result["bridge_rounds"] = round_num
            try:
                _emit_phase_a_event(
                    repo_root,
                    routing_record=routing_record,
                    plan_name=plan_name,
                    rel_plan_path=rel_plan_path,
                    event_type="phase_a_reviewer_started",
                    state="reviewer_started",
                    transition_key=f"{bridge_job_id}:reviewer_started",
                    summary=f"Phase A reviewer started for round {round_num}",
                    artifact_paths={"plan": rel_plan_path},
                    bus_dir=bus_dir,
                )
            except Exception as exc:
                result["status"] = "error"
                result["error"] = f"Phase A pager emission failed before bridge review: {exc}"
                return False

            bridge_result = run_bridge_design_review(
                repo_root, rel_plan_path, round_num,
                job_id=bridge_job_id,
                agent_review_context=agent_review_context,
                bus_dir=bus_dir,
            )
            log(f"Bridge exit code: {bridge_result['exit_code']}")

            rendered_path = agent_bus_path(repo_root, bus_dir, "rendered", f"{bridge_job_id}.md")
            if rendered_path.exists():
                render_content = rendered_path.read_text(encoding="utf-8")
                bridge_decision = _extract_bridge_decision(
                    render_content,
                    rendered_path=rendered_path,
                )
                try:
                    _emit_phase_a_event(
                        repo_root,
                        routing_record=routing_record,
                        plan_name=plan_name,
                        rel_plan_path=rel_plan_path,
                        event_type="phase_a_reviewer_completed",
                        state=bridge_decision.lower() if bridge_decision else "reviewer_completed",
                        transition_key=f"{bridge_job_id}:reviewer_completed:{bridge_decision or 'unknown'}",
                        summary=f"Phase A reviewer completed round {round_num} with {bridge_decision or 'unknown'}",
                        artifact_paths={"rendered": str(rendered_path.relative_to(repo_root))},
                        bus_dir=bus_dir,
                    )
                except Exception as exc:
                    result["status"] = "error"
                    result["error"] = f"Phase A pager emission failed after bridge review: {exc}"
                    return False
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
                        return False
                    log("Bridge converged: GO")
                    result["status"] = "converged"
                    try:
                        _emit_phase_a_event(
                            repo_root,
                            routing_record=routing_record,
                            plan_name=plan_name,
                            rel_plan_path=rel_plan_path,
                            event_type="phase_a_go",
                            state="go",
                            transition_key=f"{bridge_job_id}:go",
                            summary=f"Phase A bridge GO for round {round_num}",
                            artifact_paths={"rendered": str(rendered_path.relative_to(repo_root))},
                            bus_dir=bus_dir,
                        )
                    except Exception as exc:
                        result["status"] = "error"
                        result["error"] = f"Phase A pager emission failed on GO: {exc}"
                        return False
                    return True
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
                        return False
                    # Classify findings as blocking vs non-blocking.
                    # If only non-blockers remain, converge — design advisory
                    # findings don't need to block plan convergence.
                    # Read raw reviewer output for finding parsing — the JSON
                    # envelope (BEGIN_AGENT_ENVELOPE) is in the raw output,
                    # not in the rendered markdown.
                    raw_dir = agent_bus_path(repo_root, bus_dir, "raw", bridge_job_id)
                    raw_content = ""
                    if raw_dir.is_dir():
                        for raw_file in sorted(raw_dir.iterdir()):
                            if "reviewer" in raw_file.name:
                                raw_content = raw_file.read_text(encoding="utf-8")
                                break
                    parsed_findings = _parse_phase_a_findings(
                        raw_content if raw_content else render_content
                    )
                    # Critical severity = always blocking regardless of
                    # reviewer-declared disposition (bridge R3 finding:
                    # a non_blocking disposition must not suppress critical).
                    # High severity = blocking only when disposition is
                    # absent/unknown (reviewer can explicitly mark high as
                    # non_blocking).
                    blocking = [
                        f
                        for f in parsed_findings
                        if f.get("disposition") == "blocking"
                        or f.get("severity") == "critical"
                        or (
                            f.get("disposition") not in ("blocking", "non_blocking")
                            and f.get("severity") == "high"
                        )
                    ]
                    non_blocking = [f for f in parsed_findings if f not in blocking]
                    if parsed_findings:
                        log(
                            f"Bridge: REQUEST_CHANGES — {len(blocking)} blocking, "
                            f"{len(non_blocking)} non-blocking"
                        )
                    else:
                        log(
                            f"Bridge: {bridge_decision} without structured findings — "
                            "continuing review loop"
                        )

                    if parsed_findings and not blocking:
                        log(
                            f"Bridge: all {len(non_blocking)} findings are non-blocking — "
                            "treating as GO"
                        )
                        result["status"] = "converged"
                        result["non_blocking_count"] = len(non_blocking)
                        try:
                            _emit_phase_a_event(
                                repo_root,
                                routing_record=routing_record,
                                plan_name=plan_name,
                                rel_plan_path=rel_plan_path,
                                event_type="phase_a_go",
                                state="go",
                                transition_key=f"{bridge_job_id}:non_blocking_go",
                                summary=(
                                    "Phase A treated non-blocking-only "
                                    f"{bridge_decision} as GO for round {round_num}"
                                ),
                                artifact_paths={"rendered": str(rendered_path.relative_to(repo_root))},
                                bus_dir=bus_dir,
                            )
                        except Exception as exc:
                            result["status"] = "error"
                            result["error"] = f"Phase A pager emission failed on non-blocking GO: {exc}"
                            return False
                        return True

                    if _invoke_implementer is not None and blocking:
                        current_plan_content = (repo_root / rel_plan_path).read_text(encoding="utf-8")
                        plan_hash_before = hash(current_plan_content)
                        blocking_text = _format_phase_a_blocking_findings(blocking)
                        stub_rewrite = _plan_is_placeholder_stub(current_plan_content)
                        _task_id = scope.get("task_id", "")
                        if not _task_id:
                            for line in current_plan_content.splitlines():
                                if line.strip().startswith("Task:"):
                                    _task_id = line.split("Task:", 1)[1].strip()
                                    break
                        stub_rewrite_guidance = ""
                        if stub_rewrite:
                            stub_rewrite_guidance = (
                                "Because the current packet is still a stub, do NOT inspect downstream "
                                "implementation files just to decide whether work items are already "
                                "landed. Use the cited TASKS.md lines, governing packet, and "
                                "blocking-finding evidence to draft the first real plan. Stop after "
                                "rewriting the packet with the required Phase A sections; do NOT try "
                                "to solve the underlying implementation in this turn.\n\n"
                            )
                        impl_prompt = (
                            f"You are updating a Phase A plan at `{rel_plan_path}`.\n\n"
                            f"IMPORTANT: Write ALL changes to `{rel_plan_path}` ONLY. "
                            f"Do NOT create new files. Do NOT write to any other path.\n\n"
                            "The bridge reviewer returned REQUEST_CHANGES. "
                            "Fix ONLY the blocking findings below.\n"
                            "Treat the reviewer evidence below as authoritative for this rewrite.\n\n"
                            f"{blocking_text}\n\n"
                            "This is a packet rewrite task, not a broad repo investigation.\n"
                            "Use ONLY the minimum repo-local evidence needed to rewrite the packet:\n"
                            f"- `{rel_plan_path}`\n"
                            f"- exact TASKS.md lines for `{_task_id or 'the current task'}`\n"
                            "- files, lines, and docs explicitly cited in the blocking findings above\n\n"
                            "TASKS.md authorizes the wave, but it does NOT prove every listed item "
                            "is still unlanded. If a blocking finding proves a work item is already "
                            "implemented in current code, remove it from pending work items and "
                            "acceptance criteria instead of re-listing it as unresolved.\n"
                            "Prefer current code truth over stale packet wording when they conflict.\n\n"
                            f"{stub_rewrite_guidance}"
                            "Do NOT inspect unrelated dirty files, `git diff`, `git status`, "
                            "or unrelated executor/test changes. Do NOT widen scope beyond the "
                            "blocking findings. Search TASKS.md for the exact task id instead of "
                            "reading the entire file when targeted lookup is enough.\n\n"
                            f"## Current plan content:\n\n{current_plan_content}\n\n"
                            f"## Required plan sections:\n"
                            "1. Scope: files/directories in scope\n"
                            "2. Work items: concrete bounded tasks from TASKS.md current phase\n"
                            "3. Constraints: what is NOT in scope\n"
                            "4. Stop conditions\n"
                            "5. Acceptance criteria\n"
                            "6. Grounding / Authorization: TASKS.md authorization "
                            "+ governing packet refs. For control-surface L4_ENABLER "
                            "packets, include either a wave-bound `FOUNDER_OVERRIDE:<wave_id>` "
                            "or an explicit `Authorization: standing pipeline-bug-fix "
                            "authorization ...` line so commit automation can derive the "
                            "same-wave override mechanically.\n\n"
                            f"Read TASKS.md for the current task ({_task_id or 'see NEXT section'}) "
                            f"and use the plan file at `{rel_plan_path}` as the governing packet. "
                            f"Update ONLY `{rel_plan_path}`. Do NOT create new files. "
                            "Replace the stub with the real plan directly in that file."
                        )
                        log("Invoking implementer to fix blocking findings...")
                        try:
                            _emit_phase_a_event(
                                repo_root,
                                routing_record=routing_record,
                                plan_name=plan_name,
                                rel_plan_path=rel_plan_path,
                                event_type="phase_a_implementer_started",
                                state="implementer_started",
                                transition_key=f"{bridge_job_id}:implementer_started",
                                summary=f"Phase A implementer started after {bridge_decision} round {round_num}",
                                artifact_paths={"rendered": str(rendered_path.relative_to(repo_root))},
                                bus_dir=bus_dir,
                            )
                        except Exception as exc:
                            result["status"] = "error"
                            result["error"] = f"Phase A pager emission failed before implementer: {exc}"
                            return False
                        impl_result = _invoke_implementer(
                            repo_root, impl_prompt,
                            backend=implementer_backend,
                            timeout=900,
                            verbose=verbose,
                            bus_dir=bus_dir,
                        )
                        try:
                            _emit_phase_a_event(
                                repo_root,
                                routing_record=routing_record,
                                plan_name=plan_name,
                                rel_plan_path=rel_plan_path,
                                event_type="phase_a_implementer_completed",
                                state=str(impl_result.get("status") or "implementer_completed"),
                                transition_key=f"{bridge_job_id}:implementer_completed",
                                summary=(
                                    "Phase A implementer completed with "
                                    f"{impl_result.get('status', 'unknown')} after round {round_num}"
                                ),
                                artifact_paths={"rendered": str(rendered_path.relative_to(repo_root))},
                                bus_dir=bus_dir,
                            )
                        except Exception as exc:
                            result["status"] = "error"
                            result["error"] = f"Phase A pager emission failed after implementer: {exc}"
                            return False
                        # Always check if the plan file was modified, even on
                        # adapter-level failure.  The implementer may have
                        # successfully edited the file via Edit tool calls
                        # before claude --print exited non-zero (e.g. session
                        # ended mid-tool-call without a final text response,
                        # causing the adapter to report error despite edits
                        # having been applied).
                        plan_file = repo_root / rel_plan_path
                        try:
                            new_content = plan_file.read_text(encoding="utf-8")
                        except (OSError, FileNotFoundError):
                            # Plan file missing/unreadable after implementer run.
                            # Treat as unmodified — the bridge will detect the
                            # missing file on its next round.
                            new_content = current_plan_content
                        plan_actually_changed = hash(new_content) != plan_hash_before
                        if impl_result["status"] != "success":
                            if plan_actually_changed:
                                log(
                                    f"Implementer reported {impl_result['status']} but plan "
                                    f"WAS modified ({len(new_content.splitlines())} lines) "
                                    f"— treating as successful edit"
                                )
                            else:
                                log(
                                    f"Implementer failed: {impl_result['status']} — continuing "
                                    "with unmodified plan"
                                )
                        else:
                            if not plan_actually_changed:
                                log(f"WARNING: Implementer returned success but {rel_plan_path} "
                                    f"was NOT modified. Plan may have been written elsewhere. "
                                    f"Failing closed to prevent infinite stub loop.")
                                result["status"] = "error"
                                result["error"] = (
                                    f"Implementer did not modify {rel_plan_path}. "
                                    f"Check if plan was written to a different file."
                                )
                                return False
                            log(f"Implementer updated plan ({len(new_content.splitlines())} lines) "
                                f"— continuing to next bridge round")
                    elif not _invoke_implementer and blocking:
                        log(
                            "Bridge: REQUEST_CHANGES — no implementer available, "
                            "continuing with unmodified plan"
                        )
                    if bridge_decision == "NO_GO":
                        try:
                            _emit_phase_a_event(
                                repo_root,
                                routing_record=routing_record,
                                plan_name=plan_name,
                                rel_plan_path=rel_plan_path,
                                event_type="phase_a_no_go",
                                state="no_go",
                                transition_key=f"{bridge_job_id}:no_go",
                                summary=f"Phase A bridge NO_GO for round {round_num}",
                                artifact_paths={"rendered": str(rendered_path.relative_to(repo_root))},
                                bus_dir=bus_dir,
                            )
                        except Exception as exc:
                            result["status"] = "error"
                            result["error"] = f"Phase A pager emission failed on NO_GO: {exc}"
                            return False
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
                        return False
                    log("Bridge: QUESTION — fail-closed (unresolved question)")
                    result["status"] = "error"
                    result["error"] = "Bridge returned QUESTION decision — requires human resolution"
                    result["rendered_path"] = str(rendered_path)
                    try:
                        _emit_phase_a_event(
                            repo_root,
                            routing_record=routing_record,
                            plan_name=plan_name,
                            rel_plan_path=rel_plan_path,
                            event_type="phase_a_question",
                            state="question",
                            transition_key=f"{bridge_job_id}:question",
                            summary="Phase A bridge QUESTION requires human resolution",
                            artifact_paths={"rendered": str(rendered_path.relative_to(repo_root))},
                            bus_dir=bus_dir,
                        )
                    except Exception as exc:
                        result["error"] = f"Phase A pager emission failed on QUESTION: {exc}"
                    return False
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
                        return False
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
                    return False
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
                        return False
                    log("Bridge: unrecognized decision — fail-closed")
                    result["status"] = "error"
                    result["error"] = "Bridge returned unrecognized decision — cannot proceed"
                    result["rendered_path"] = str(rendered_path)
                    return False
            else:
                if bridge_result["exit_code"] != 0:
                    log(f"Bridge failed (exit {bridge_result['exit_code']}) — failing closed")
                    result["status"] = "error"
                    result["error"] = (
                        f"Bridge subprocess failed in round {round_num} "
                        f"(exit={bridge_result['exit_code']}). "
                        f"stderr: {_trim_stderr(bridge_result.get('stderr', ''), tail=True)}"
                    )
                    return False
                log("Bridge exited 0 without rendered output — fail-closed")
                result["status"] = "error"
                result["error"] = "Bridge exited 0 but produced no rendered output"
                return False

            if round_num >= max_bridge_rounds:
                result["status"] = "max_rounds_reached"
                log(f"Max bridge rounds ({max_bridge_rounds}) reached")
                return False

        result["status"] = "max_rounds_reached"
        result["error"] = (
            f"Bridge did not converge after {max_bridge_rounds} rounds. "
            "Plan was never locked."
        )
        log(f"Max bridge rounds ({max_bridge_rounds}) reached without convergence")
        return False

    agent_review_bridge_ctx = ""
    if defer_agent_review:
        log(
            "Plan draft is still a placeholder stub — deferring SDK agent review "
            "until bridge/implementer produces a real plan"
        )
    elif not config.get("agent_review_enabled", True):
        log("SDK agent review DISABLED via executor_config.json (agent_review_enabled=false)")
        result["agent_exit_code"] = 0
        result["agent_review_ran"] = False
    else:
        review_ok, agent_review_bridge_ctx = _run_phase_a_agent_review(
            f"Running SDK agent review on plan (depth={review_depth})..."
        )
        if not review_ok:
            return result

    if not _run_bridge_convergence(start_round=1, agent_review_context=agent_review_bridge_ctx):
        return result

    if defer_agent_review and not result["agent_review_ran"]:
        refined_plan_content = (repo_root / rel_plan_path).read_text(encoding="utf-8")
        if _plan_is_placeholder_stub(refined_plan_content):
            result["status"] = "error"
            result["error"] = (
                "Bridge converged but the plan is still a placeholder stub. "
                "Phase A requires stub rejection and same-file rewrite before "
                "deferred SDK review can run."
            )
            return result
        if config.get("agent_review_enabled", True):
            review_ok, agent_review_bridge_ctx = _run_phase_a_agent_review(
                f"Running deferred SDK agent review on refined plan (depth={review_depth})..."
            )
            if not review_ok:
                return result
            if result.get("agent_review_warning_only"):
                if not _run_bridge_convergence(
                    start_round=result["bridge_rounds"] + 1,
                    agent_review_context=agent_review_bridge_ctx,
                ):
                    return result

    # Lock the plan. If bridge GO missed detector-visible TASKS.md authority for
    # strict staged L4 validation, run one bounded recovery pass that may edit
    # only the packet and TASKS.md, then require bridge review again before lock.
    strict_l4_recovery_attempted = False
    while True:
        try:
            lock_plan(repo_root, rel_plan_path, routing_record=routing_record)
            break
        except PhaseAExecutorError as exc:
            error_text = str(exc)
            if (
                _is_strict_staged_l4_guard_error(error_text)
                and _invoke_implementer is not None
                and not strict_l4_recovery_attempted
            ):
                strict_l4_recovery_attempted = True
                current_plan_content = (repo_root / rel_plan_path).read_text(encoding="utf-8")
                allowed_recovery_paths = {_normalize_phase_a_relpath(rel_plan_path), "TASKS.md"}
                pre_recovery_snapshot = _strict_l4_recovery_scope_snapshot(
                    repo_root,
                    allowed_recovery_paths,
                )
                impl_prompt = _strict_staged_l4_guard_recovery_prompt(
                    rel_plan_path=rel_plan_path,
                    current_plan_content=current_plan_content,
                    guard_error=error_text,
                )
                log("Strict staged L4 guard failed before lock — invoking bounded tracker recovery...")
                impl_result = _invoke_implementer(
                    repo_root,
                    impl_prompt,
                    backend=implementer_backend,
                    timeout=900,
                    verbose=verbose,
                    bus_dir=bus_dir,
                )
                post_recovery_snapshot = _strict_l4_recovery_scope_snapshot(
                    repo_root,
                    allowed_recovery_paths,
                )
                changed_paths = _changed_paths_between_snapshots(
                    pre_recovery_snapshot,
                    post_recovery_snapshot,
                )
                out_of_scope_paths = [
                    path for path in changed_paths if path not in allowed_recovery_paths
                ]
                if out_of_scope_paths:
                    result["status"] = "error"
                    result["error"] = (
                        "Strict staged L4 guard recovery edited out-of-scope path(s): "
                        f"{', '.join(out_of_scope_paths)}; allowed paths: "
                        f"{', '.join(sorted(allowed_recovery_paths))}"
                    )
                    return result
                recovery_changed_paths = [
                    path for path in changed_paths if path in allowed_recovery_paths
                ]
                recovery_changed = bool(recovery_changed_paths)
                impl_status = str(impl_result.get("status") or "unknown")
                if impl_status != "success" and not recovery_changed:
                    result["status"] = "error"
                    result["error"] = (
                        "Strict staged L4 guard recovery implementer failed without edits: "
                        f"{impl_status}; original guard error: {error_text}"
                    )
                    return result
                if not recovery_changed:
                    result["status"] = "error"
                    result["error"] = (
                        "Strict staged L4 guard recovery made no packet or TASKS.md edits; "
                        f"original guard error: {error_text}"
                    )
                    return result
                result["strict_l4_guard_recovery_ran"] = True
                result["strict_l4_guard_recovery_changed_files"] = recovery_changed_paths
                log(
                    "Strict staged L4 guard recovery edited "
                    f"{', '.join(recovery_changed_paths)}; "
                    "rerunning bridge review before lock"
                )
                if not _run_bridge_convergence(
                    start_round=result["bridge_rounds"] + 1,
                    agent_review_context=agent_review_bridge_ctx,
                ):
                    return result
                continue
            result["status"] = "error"
            result["error"] = error_text
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
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
    )
    args = parser.parse_args()

    routing_record_override: dict[str, Any] | None = None
    if args.routing_record:
        try:
            parsed_record = json.loads(args.routing_record)
        except json.JSONDecodeError as exc:
            print(f"[error] --routing-record is not valid JSON: {exc}", file=sys.stderr)
            return 1
        if not isinstance(parsed_record, dict):
            print("[error] --routing-record must decode to a JSON object", file=sys.stderr)
            return 1
        routing_record_override = parsed_record

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
        bus_dir=args.bus_dir,
        routing_record_override=routing_record_override,
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
