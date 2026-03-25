#!/usr/bin/env python3
"""Phase B executor: implements a locked plan through bridge convergence loop.

Invoked by ROUTE_PHASE_B routing token from the post-merge supervisor.
Replaces Claude-as-workflow-engine for Phase B implementation waves.

Control flow:
1. Read locked plan packet + routing record
2. Invoke implementer agent (separate code-writing actor via bridge adapter)
3. Run SDK agent review ONCE — nonzero exit is fatal
4. Bridge convergence loop (implementer-fix → bridge-review per round):
   - GO: converged, proceed
   - REQUEST_CHANGES/NO_GO: re-invoke implementer with findings, then next round
   - QUESTION: fail closed (requires founder input)
5. Stage the final file set BEFORE supervisor (receipt binds to staged state)
6. Run pre-commit supervisor (receipt minted against staged state)
7. On COMMIT_GO: prepare handoff with exact per-invocation receipt path
8. On NEEDS_PHASE_B: re-invoke implementer with findings, then bridge review loop
9. On other decisions: report and stop

All terminal exits (max_rounds, question, supervisor_rejected) clear persisted
state to prevent stale resume on next invocation.

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md Section B.3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        load_routing_record, ExecutorCommonError,
        BLOCKING_KEYWORDS, NON_BLOCKING_KEYWORDS,
        HARDENING_INDICATORS, DEFECT_INDICATORS,
        REPEAT_FINDING_CAP,
        run_bridge_subprocess,
    )
except ImportError:
    # Fallback for direct execution
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    load_routing_record = _mod.load_routing_record
    ExecutorCommonError = _mod.ExecutorCommonError
    BLOCKING_KEYWORDS = _mod.BLOCKING_KEYWORDS
    NON_BLOCKING_KEYWORDS = _mod.NON_BLOCKING_KEYWORDS
    HARDENING_INDICATORS = _mod.HARDENING_INDICATORS
    DEFECT_INDICATORS = _mod.DEFECT_INDICATORS
    REPEAT_FINDING_CAP = _mod.REPEAT_FINDING_CAP
    run_bridge_subprocess = _mod.run_bridge_subprocess


class PhaseBExecutorError(RuntimeError):
    """Raised when Phase B executor cannot proceed."""


# ---------------------------------------------------------------------------
# Finding disposition helpers
# ---------------------------------------------------------------------------

def _disposition_for_finding(finding: dict[str, Any]) -> tuple[str, str]:
    """Derive effective disposition for a single finding.

    Returns (disposition, reason) tuple for logging/auditability.

    Priority:
    1. Explicit 'disposition' field — use as-is.
    2. Severity 'critical' — always blocking.
    3. High severity — blocking UNLESS explicit non-blocking keyword match.
    4. Medium/low severity — non-blocking UNLESS blocking keyword match.
    5. No severity — keyword match, then fail-closed blocking.
    """
    disposition = finding.get("disposition")
    if disposition is not None:
        return disposition, "explicit disposition field"

    severity = (finding.get("severity") or "").lower()
    # Build searchable text from title + summary
    text = " ".join(filter(None, [
        finding.get("title", ""),
        finding.get("summary", ""),
    ])).lower()

    # Critical severity is always blocking regardless of content
    if severity == "critical":
        return "blocking", "critical severity (always blocking)"

    # Check for keyword matches
    blocking_match = next((kw for kw in BLOCKING_KEYWORDS if kw in text), None)
    non_blocking_match = next((kw for kw in NON_BLOCKING_KEYWORDS if kw in text), None)

    # High severity: blocking unless an explicit non-blocking keyword match
    # or detail-text analysis reveals hardening vs defect signals.
    if severity == "high":
        if blocking_match:
            return "blocking", f"high severity + blocking keyword: '{blocking_match}'"
        if non_blocking_match:
            return "non_blocking", f"high severity but non-blocking keyword: '{non_blocking_match}'"

        # No primary keyword match — inspect detail text for hardening vs defect signals
        detail = " ".join(filter(None, [
            finding.get("title", ""),
            finding.get("summary", ""),
            finding.get("detail", ""),
            finding.get("description", ""),
        ])).lower()

        hardening_hit = next((kw for kw in HARDENING_INDICATORS if kw in detail), None)
        defect_hit = next((kw for kw in DEFECT_INDICATORS if kw in detail), None)

        # Defect signal overrides hardening signal (fail-closed on conflict)
        if defect_hit and not hardening_hit:
            return "blocking", f"high severity + defect indicator: '{defect_hit}'"
        if hardening_hit and not defect_hit:
            return "non_blocking", f"high severity + hardening indicator: '{hardening_hit}'"
        if defect_hit and hardening_hit:
            return "blocking", f"high severity + conflicting indicators (defect: '{defect_hit}', hardening: '{hardening_hit}') — fail-closed"

        # No signals at all: fail-closed
        return "blocking", "high severity, no keyword match (fail-closed)"

    # Medium/low severity: non-blocking unless a blocking keyword match
    if severity in ("medium", "low"):
        if blocking_match:
            return "blocking", f"{severity} severity + blocking keyword: '{blocking_match}'"
        if non_blocking_match:
            return "non_blocking", f"{severity} severity + non-blocking keyword: '{non_blocking_match}'"
        return "non_blocking", f"{severity} severity, no keyword match"

    # No severity or unrecognized: check keywords, then fail-closed
    if blocking_match:
        return "blocking", f"blocking keyword match: '{blocking_match}'"
    if non_blocking_match:
        return "non_blocking", f"non-blocking keyword match: '{non_blocking_match}'"

    # Fail-closed default: anything unrecognized is blocking
    return "blocking", "fail-closed default (no disposition, no severity, no keyword match)"


def _finding_key(finding: dict[str, Any]) -> str:
    """Return a stable identity key for a finding (title + file).

    Used to track repeat appearances across bridge rounds.
    """
    title = (finding.get("title") or "").strip().lower()
    file = (finding.get("file") or "").strip()
    return f"{title}||{file}"


def _classify_findings(
    findings: list[dict[str, Any]],
    finding_history: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate findings into blocking and non-blocking lists.

    Uses _disposition_for_finding to resolve each finding's effective
    disposition (explicit field → keyword heuristic → fail-closed blocking).
    Logs the classification decision with reason for each finding.

    If *finding_history* is provided, it maps finding keys to the number of
    consecutive rounds they have appeared as blocking.  The dict is updated
    in-place.  Blocking findings are NEVER auto-downgraded — they stay blocking.
    The caller uses the repeat count for loop termination (hard failure).
    """
    blocking: list[dict[str, Any]] = []
    non_blocking: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for f in findings:
        disposition, reason = _disposition_for_finding(f)
        title = f.get("title", "<untitled>")
        key = _finding_key(f)
        seen_keys.add(key)

        # Track repeat counts for blocking findings (used for loop termination,
        # NOT for auto-downgrade — blocking findings stay blocking).
        if disposition == "blocking" and finding_history is not None:
            count = finding_history.get(key, 0) + 1
            finding_history[key] = count
        elif disposition != "blocking" and finding_history is not None:
            # Non-blocking findings reset the counter (resolved or already deferred)
            finding_history.pop(key, None)

        print(f"  [classify] '{title}' → {disposition} ({reason})", file=__import__('sys').stderr)
        if disposition == "non_blocking":
            non_blocking.append(f)
        else:
            blocking.append(f)

    # Prune stale keys from history (findings that disappeared this round)
    if finding_history is not None:
        stale = [k for k in finding_history if k not in seen_keys]
        for k in stale:
            del finding_history[k]

    return blocking, non_blocking


def _write_deferred_packet(
    repo_root: Path,
    wave_id: str,
    non_blocking_findings: list[dict[str, Any]],
) -> Path:
    """Write or update a deferred non-blocking findings packet.

    Returns the path to the written packet.
    """
    deferred_dir = repo_root / "reports" / "deferred" / "non_blocking"
    deferred_dir.mkdir(parents=True, exist_ok=True)
    safe_wave = wave_id.replace("/", "_").replace(" ", "_")
    packet_path = deferred_dir / f"{safe_wave}_bridge_nonblockers.md"

    lines = [
        f"# Deferred Non-Blocking Findings: {wave_id}",
        "",
        f"Generated by Phase B executor. {len(non_blocking_findings)} finding(s).",
        "",
    ]
    for i, f in enumerate(non_blocking_findings, 1):
        lines.append(f"## {i}. {f.get('title', 'Untitled')}")
        lines.append(f"- **Class:** {f.get('class', 'unknown')}")
        lines.append(f"- **Severity:** {f.get('severity', 'unknown')}")
        lines.append(f"- **File:** {f.get('file', 'unknown')}")
        lines.append(f"- **Disposition:** non_blocking")
        if f.get("evidence_cmd"):
            lines.append(f"- **Evidence:** `{f['evidence_cmd']}`")
        lines.append("")

    packet_path.write_text("\n".join(lines), encoding="utf-8")
    return packet_path


def _parse_findings_from_render(render_text: str) -> list[dict[str, Any]]:
    """Extract structured findings from bridge render text.

    Tries two strategies in order:
    1. JSON envelope between BEGIN_AGENT_ENVELOPE / END_AGENT_ENVELOPE markers.
    2. Numbered markdown findings like:
         1. **DEFECT** (critical): Title text
            - File: path/to/file.py
            - Evidence: description of evidence
    """
    import re

    # Strategy 1: JSON envelope
    pattern = r"BEGIN_AGENT_ENVELOPE\s*(?:```(?:json)?\s*)?(\{.*?\})\s*(?:```\s*)?END_AGENT_ENVELOPE"
    match = re.search(pattern, render_text, re.DOTALL)
    if match:
        try:
            envelope = json.loads(match.group(1))
            return envelope.get("findings", [])
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 2: numbered markdown findings
    # Pattern: "  N. **TYPE** (severity): title"  with optional indented detail lines
    finding_re = re.compile(
        r"^\s*\d+\.\s+\*\*(\w+)\*\*\s*\(([^)]+)\)\s*:\s*(.+)",
        re.MULTILINE,
    )
    findings: list[dict[str, Any]] = []
    lines = render_text.split("\n")
    i = 0
    while i < len(lines):
        m = finding_re.match(lines[i])
        if m:
            finding: dict[str, Any] = {
                "title": m.group(3).strip(),
                "severity": m.group(2).strip(),
                "type": m.group(1).strip(),
            }
            # Collect indented detail lines (  - Key: value)
            i += 1
            detail_re = re.compile(r"^\s+-\s+(\w[\w\s]*):\s*(.*)")
            while i < len(lines):
                dm = detail_re.match(lines[i])
                if dm:
                    key = dm.group(1).strip().lower()
                    value = dm.group(2).strip()
                    finding[key] = value
                    i += 1
                elif lines[i].strip() == "":
                    i += 1  # skip blank lines between details
                else:
                    break
            findings.append(finding)
        else:
            i += 1
    return findings


def _run_pytest_on_files(
    repo_root: Path,
    test_files: list[str],
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run pytest on specific test files. Returns exit_code and output."""
    if not test_files:
        return {"exit_code": 0, "stdout": "", "stderr": "", "passed": True}
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "--tb=short", *test_files],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "pytest timed out", "passed": False}


# ---------------------------------------------------------------------------
# State persistence for resume
# ---------------------------------------------------------------------------

STATE_DIR_NAME = ".agent_bus/executors"
STATE_FILE_NAME = "phase_b_state.json"


def _state_file_path(repo_root: Path) -> Path:
    return repo_root / STATE_DIR_NAME / STATE_FILE_NAME


def _save_state(repo_root: Path, state: dict[str, Any]) -> Path:
    """Persist executor state to disk for resume capability."""
    state_path = _state_file_path(repo_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state_path


def _load_state(repo_root: Path) -> dict[str, Any] | None:
    """Load persisted executor state, or None if not found."""
    state_path = _state_file_path(repo_root)
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _clear_state(repo_root: Path) -> None:
    """Remove persisted state file after successful completion."""
    state_path = _state_file_path(repo_root)
    if state_path.exists():
        state_path.unlink()


def load_plan_packet(repo_root: Path, plan_path: str) -> dict[str, str]:
    """Load and parse key fields from a plan packet."""
    full_path = (repo_root / plan_path).resolve()
    if not full_path.is_relative_to(repo_root.resolve()):
        raise PhaseBExecutorError(f"Path traversal blocked: {plan_path}")
    if not full_path.exists():
        raise PhaseBExecutorError(f"Plan packet not found: {plan_path}")

    content = full_path.read_text(encoding="utf-8")
    result = {"path": plan_path, "content": content}

    for line in content.splitlines()[:20]:
        # Handle both plain and markdown-bold formats
        clean = line.replace("**", "").strip()
        if clean.startswith("Phase-A-Lock:"):
            result["phase_a_lock"] = clean.split(":", 1)[1].strip()
        if clean.startswith("Status:"):
            result["status"] = clean.split(":", 1)[1].strip()

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
    job_id: str | None = None,
    verbose: bool = False,
    timeout: int = 1200,
) -> dict[str, Any]:
    """Run bridge_supervisor.py review and return the result.

    If job_id is provided, it's passed to bridge_supervisor so the rendered
    output is written to a deterministic path (.agent_bus/rendered/{job_id}.md).
    The decision is parsed from stdout (bridge_supervisor prints it).
    """
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
    if job_id:
        cmd.extend(["--job-id", job_id])
    if verbose:
        cmd.append("-v")

    try:
        result = run_bridge_subprocess(cmd, cwd=repo_root, timeout=timeout)
        # Parse decision from stdout (bridge_supervisor.py review prints it)
        stdout_stripped = result.stdout.strip()
        decision = ""
        if stdout_stripped:
            # Decision is the last non-empty line of stdout
            for line in reversed(stdout_stripped.splitlines()):
                line = line.strip()
                if line in ("GO", "REQUEST_CHANGES", "NO_GO", "QUESTION"):
                    decision = line
                    break
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "decision": decision,
            "job_id": job_id or "",
        }
    except ExecutorCommonError:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Bridge review timed out after {timeout}s",
            "decision": "",
            "job_id": job_id or "",
        }


def _read_bridge_render(repo_root: Path, job_id: str) -> str:
    """Read the rendered bridge output for a specific job_id.

    Returns the rendered content, or empty string if not found.
    The rendered file is at .agent_bus/rendered/{job_id}.md.
    """
    rendered_path = repo_root / ".agent_bus" / "rendered" / f"{job_id}.md"
    if rendered_path.exists():
        return rendered_path.read_text(encoding="utf-8")
    return ""


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


def _collect_changed_files(repo_root: Path) -> list[str]:
    """Collect all changed files (staged + unstaged + untracked) from git."""
    changed: list[str] = []
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
        changed = sorted(set(f for f in staged + unstaged + untracked if f))
    except subprocess.CalledProcessError:
        pass
    return changed


# Prefixes that are valid wave-owned output paths for Phase B handoff staging.
_WAVE_OWNED_PREFIXES = (
    "mu/tools/",
    "mu/tests/",
    "mu/docs/",
    "tools/",
    "reports/",
    ".agent_bus/",
    ".scratch/",
    "TASKS.md",
    "STATUS.md",
    "CHANGELOG.md",
    "CLAUDE.md",
)


def _collect_wave_owned_files(
    repo_root: Path,
    plan_path: str,
    plan_declared_files: list[str] | None = None,
    implementer_changed_files: set[str] | None = None,
    executor_created_files: set[str] | None = None,
) -> list[str]:
    """Collect changed files scoped to plan-declared + implementer-tracked set only.

    Only stages files that are BOTH dirty in git AND either:
      1. Declared in the plan (plan_declared_files), OR
      2. Actually changed by the implementer (implementer_changed_files), OR
      3. Created by the executor itself (executor_created_files — e.g. deferred packets), OR
      4. Under the plan's directory prefix.

    When neither plan_declared_files nor implementer_changed_files are provided
    (both are None), falls back to prefix-based filtering as a degraded path.
    An empty list/set means "tracking is active but nothing matched" — which
    still allows plan-prefix files through.
    """
    all_changed = _collect_changed_files(repo_root)
    plan_prefix = plan_path.rsplit("/", 1)[0] + "/" if "/" in plan_path else ""

    # If we have explicit tracking, use it strictly — no prefix glob
    if plan_declared_files is not None or implementer_changed_files is not None:
        allowed = set(plan_declared_files or [])
        allowed |= (implementer_changed_files or set())
        allowed |= (executor_created_files or set())
        # The plan file itself is always wave-owned
        allowed.add(plan_path)
        scoped = []
        for f in all_changed:
            if f in allowed:
                scoped.append(f)
        return sorted(scoped)

    # Degraded fallback: prefix-based filtering (no explicit tracking available)
    scoped = []
    for f in all_changed:
        if any(f.startswith(p) or f == p for p in _WAVE_OWNED_PREFIXES):
            scoped.append(f)
        elif plan_prefix and f.startswith(plan_prefix):
            scoped.append(f)
    return scoped


def _stage_files(repo_root: Path, files: list[str]) -> bool:
    """Stage files for commit. Returns True on success."""
    if not files:
        return False
    try:
        subprocess.run(
            ["git", "add", "--", *files],
            cwd=repo_root, capture_output=True, text=True, check=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


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
    tracker_note_text: str = "",
    fixes_implemented: list[str] | None = None,
    files_to_stage: list[str] | None = None,
    force_add_files: list[str] | None = None,
    commit_message: str = "",
    pr_title: str = "",
    pr_body: str = "",
    pre_commit_receipt_path: str = ".agent_bus/meta/pre_commit_receipt.json",
) -> Path:
    """Prepare a commit executor handoff file (new schema).

    Produces the 15-field handoff required by the commit executor state machine.
    """
    handoff: dict[str, Any] = {
        "wave_id": wave_id,
        "task_id": task_id,
        "wave_class": wave_class,
        "target_gate_id": target_gate_id,
        "caller": caller,
        "branch_prefix": branch_prefix,
        "tracker_note_text": tracker_note_text,
        "fixes_implemented": fixes_implemented or [],
        "files_to_stage": files_to_stage or [],
        "force_add_files": force_add_files or [],
        "commit_message": commit_message,
        "pr_title": pr_title,
        "pr_body": pr_body,
        "base_branch": "dev",
        "pre_commit_receipt_path": pre_commit_receipt_path,
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
    force: bool = False,
) -> dict[str, Any]:
    """Execute the Phase B loop.

    This is the main entry point. It orchestrates:
    1. Plan loading + validation
    2. Invoke implementer agent (separate code-writing actor via bridge adapter)
    3. SDK agent review (once) — FAIL CLOSED on nonzero exit
    4. Bridge convergence loop — bound to exact job_id, not newest file
    5. Stage the final file set BEFORE supervisor
    6. Run pre-commit supervisor (receipt minted against actual staged state)
    7. On COMMIT_GO: prepare handoff with explicit receipt path
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
        "deferred_packet_path": None,
    }

    def log(msg: str) -> None:
        if verbose:
            print(f"[phase-b] {msg}")

    # Check for resumable state
    saved_state = _load_state(repo_root)
    resume_after: str = ""
    if saved_state and saved_state.get("plan_path") == plan_path:
        completed_step = saved_state.get("completed_step", "")
        log(f"Resuming from saved state (completed_step={completed_step})")
        result["resumed_from"] = completed_step
        resume_after = completed_step
        # Restore key fields from saved state
        if saved_state.get("bridge_rounds"):
            result["bridge_rounds"] = saved_state["bridge_rounds"]
        if saved_state.get("deferred_packet_path"):
            result["deferred_packet_path"] = saved_state["deferred_packet_path"]

    # Step 1: Load and validate
    # Routing validation is FATAL: wrong routing token → error (not silent rewrite).
    # Only --bootstrap-exception (force=True) bypasses this gate.
    try:
        routing_record = load_routing_record(repo_root)
        if routing_record.get("decision") != "ROUTE_PHASE_B":
            if force:
                log(f"BOOTSTRAP_PHASE_B_EXCEPTION: Routing says {routing_record.get('decision')}, "
                    f"overriding to ROUTE_PHASE_B for bootstrap exception invocation")
                routing_record["decision"] = "ROUTE_PHASE_B"
                result["bootstrap_exception"] = True
            else:
                return {"status": "error", "step": "validate_inputs",
                        "errors": [f"Routing decision is {routing_record.get('decision')}, expected ROUTE_PHASE_B. "
                                   f"Use --bootstrap-exception to override."]}
    except (PhaseBExecutorError, ExecutorCommonError) as exc:
        if force:
            log(f"BOOTSTRAP_PHASE_B_EXCEPTION: Routing record load failed: {exc}")
            log("Using synthetic ROUTE_PHASE_B — this is the narrow bootstrap exception "
                "for waves that modify executor/implementer surfaces themselves.")
            routing_record = {"decision": "ROUTE_PHASE_B", "summary": "BOOTSTRAP_PHASE_B_EXCEPTION invocation"}
            result["bootstrap_exception"] = True
        else:
            return {"status": "error", "step": "load_routing_record",
                    "errors": [f"Routing record load failed: {exc}. Use --bootstrap-exception to override."]}

    try:
        plan = load_plan_packet(repo_root, plan_path)
    except PhaseBExecutorError as exc:
        return {"status": "error", "step": "load_plan", "errors": [str(exc)]}

    log(f"Plan loaded: {plan_path}")
    log(f"Phase-A-Lock: {plan.get('phase_a_lock', 'unknown')}")

    valid, errors = validate_inputs(routing_record, plan)
    if not valid:
        if force:
            log(f"BOOTSTRAP_PHASE_B_EXCEPTION: Validation errors overridden: {errors}")
            result["bootstrap_exception"] = True
        else:
            return {"status": "error", "step": "validate_inputs", "errors": errors}

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

    # Parse plan-declared files from plan content (lines starting with "- " that look like paths)
    plan_declared_files: list[str] | None = None
    _parsed: list[str] = []
    for line in plan.get("content", "").splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and ("/" in stripped or stripped.endswith(".py") or stripped.endswith(".json")):
            candidate = stripped[2:].strip().split()[0].rstrip(",;:")
            if "/" in candidate or candidate.endswith((".py", ".json", ".md", ".txt")):
                _parsed.append(candidate)
    # Only activate strict tracking when the plan actually declares files.
    # An empty parse means "plan has no file list" → use prefix fallback.
    if _parsed:
        plan_declared_files = _parsed

    # Track implementer-changed files: snapshot before, diff after
    implementer_changed: set[str] = set()
    # Track files created by the executor itself (e.g. deferred packets)
    executor_created: set[str] = set()
    # Track accumulated non-blocking findings across rounds (for deferred packet freshness)
    all_non_blocking: list[dict[str, Any]] = []
    # Track repeat-finding counts across bridge rounds (key → consecutive blocking count)
    finding_history: dict[str, int] = {}

    # Restore wave-owned file tracking from persisted state (R7-1: crash-resume)
    if saved_state and resume_after:
        if saved_state.get("implementer_changed"):
            implementer_changed = set(saved_state["implementer_changed"])
        if saved_state.get("executor_created"):
            executor_created = set(saved_state["executor_created"])
        if saved_state.get("all_non_blocking"):
            all_non_blocking = list(saved_state["all_non_blocking"])
        if saved_state.get("finding_history"):
            finding_history = dict(saved_state["finding_history"])

    # Determine which steps to skip based on resume state
    _RESUME_ORDER = ["implementer", "bridge_converged", "needs_phase_b_reentry"]
    _skip_to_reentry = resume_after == "needs_phase_b_reentry"
    _skip_through_bridge = (
        resume_after.startswith("bridge_round_") or resume_after == "bridge_converged"
        or _skip_to_reentry
    )
    _skip_through_implementer = resume_after == "implementer" or _skip_through_bridge

    # Step 3: Invoke implementer agent
    wave_id = plan_path.replace("reports/control_plane/", "").replace(".md", "")
    if _skip_through_implementer:
        log(f"Step 3: SKIPPED (resume_after={resume_after})")
        result["implementer_invoked"] = True
        changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)
    else:
        # Snapshot dirty files before implementer runs
        pre_impl_files = set(_collect_changed_files(repo_root))
        log(f"Invoking implementer (backend={backend}, model_override={model}, timeout={timeout}s)...")
        impl_prompt = build_implementation_prompt(
            plan.get("content", ""),
            repo_root=repo_root,
            wave_id=wave_id,
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
        result["model_override_applied"] = impl_result.get("model_override_applied", False)
        log(f"Implementer: {impl_result['status']} (exit={impl_result['exit_code']})")

        # FAIL CLOSED: any implementer failure is fatal, not just timeout
        if impl_result["status"] != "success":
            return {
                "status": "error",
                "step": "implementer",
                "errors": [
                    f"Implementer failed: {impl_result['status']} "
                    f"(exit={impl_result['exit_code']}): {impl_result.get('stderr', '')[:500]}"
                ],
                "implementer_invoked": True,
                "implementer_status": impl_result["status"],
            }

        # Collect changed files after implementer ran — track what implementer actually changed
        post_impl_files = set(_collect_changed_files(repo_root))
        implementer_changed = post_impl_files - pre_impl_files
        changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)
        log(f"Changed files after implementer: {len(changed_files)} (implementer touched {len(implementer_changed)})")

        # Persist state after implementer
        _save_state(repo_root, {
            "plan_path": plan_path,
            "completed_step": "implementer",
            "wave_id": wave_id,
            "bridge_rounds": 0,
            "implementer_changed": sorted(implementer_changed),
            "executor_created": sorted(executor_created),
            "all_non_blocking": all_non_blocking,
            "finding_history": finding_history,
        })

    # Step 4: Run SDK agents ONCE on live worktree changed files
    # FAIL CLOSED on nonzero exit (hard gate agents must pass)
    if _skip_through_bridge:
        log(f"Step 4: SKIPPED (resume_after={resume_after})")
        result["agent_review_ran"] = True
    else:
        log("Running SDK agent review on changed files...")
        agent_files = changed_files if changed_files else ["--pr"]
        agent_timeout = config.get("timeouts", {}).get("agent_review", 900)
        agent_result = run_sdk_agents(repo_root, agent_files, verbose=verbose, timeout=agent_timeout)
        result["agent_review_ran"] = True
        result["agent_exit_code"] = agent_result["exit_code"]
        log(f"Agent review exit code: {agent_result['exit_code']}")

        if agent_result["exit_code"] != 0:
            return {
                "status": "error",
                "step": "agent_review",
                "errors": [
                    f"SDK agent review failed (exit={agent_result['exit_code']}). "
                    "Hard gate agents must pass before bridge review. "
                    f"stderr: {agent_result.get('stderr', '')[:500]}"
                ],
                "agent_review_ran": True,
                "agent_exit_code": agent_result["exit_code"],
            }

    # Step 5: Bridge convergence loop (implementer-fix → bridge-review)
    # Each round: bridge reviews → if not GO, re-invoke implementer with findings → next round.
    # Decision parsed from stdout. Render read by exact job_id.
    # Enhanced: classify findings by disposition, defer non-blockers, run pytest after fixes.
    bridge_converged = _skip_through_bridge and resume_after in ("bridge_converged", "needs_phase_b_reentry")
    deferred_packet_path: str | None = result.get("deferred_packet_path")

    # Resume from saved bridge round instead of restarting from 1
    _resume_bridge_round = 0
    if _skip_through_bridge and resume_after.startswith("bridge_round_"):
        _resume_bridge_round = saved_state.get("current_bridge_round", 0) if saved_state else 0
        log(f"Resuming bridge loop from round {_resume_bridge_round + 1}")

    for round_num in range(1, max_bridge_rounds + 1):
        if bridge_converged:
            break  # Already converged (e.g. needs_phase_b_reentry resume) — skip initial loop
        if round_num <= _resume_bridge_round:
            continue  # Skip already-completed rounds on resume
        bridge_job_id = f"phase-b-r{round_num}-{uuid.uuid4().hex[:8]}"
        log(f"Bridge review round {round_num}/{max_bridge_rounds} (job={bridge_job_id})...")
        result["bridge_rounds"] = round_num

        # Build task summary — include deferred packet path if we have one
        task_summary = f"Phase B implementation review R{round_num} for {plan_path}"
        if deferred_packet_path:
            task_summary += f"\n\nAcknowledged deferred non-blocking findings: {deferred_packet_path}"

        bridge_result = run_bridge_review(
            repo_root,
            task_summary,
            job_id=bridge_job_id,
            verbose=verbose,
            timeout=timeout,
        )

        # Parse decision from bridge result
        bridge_decision = bridge_result.get("decision", "")
        log(f"Bridge decision: {bridge_decision!r} (exit={bridge_result['exit_code']})")

        # Timeout is a hard error — do not silently retry
        if bridge_result["exit_code"] == -1:
            result["status"] = "error"
            result["errors"] = [
                f"Bridge review timed out in round {round_num} "
                f"(timeout={timeout}s). {bridge_result.get('stderr', '')}"
            ]
            _clear_state(repo_root)
            return result

        if bridge_result["exit_code"] == 0 and bridge_decision == "GO":
            log("Bridge converged: GO")
            bridge_converged = True
            break

        if bridge_decision == "QUESTION":
            # QUESTION requires founder input, not code changes — fail closed
            render = _read_bridge_render(repo_root, bridge_job_id)
            result["status"] = "question_for_founder"
            result["errors"] = [
                f"Bridge returned QUESTION (round {round_num}). "
                "Founder input required — cannot resolve mechanically.",
            ]
            if render:
                result["bridge_render"] = render[:2000]
            _clear_state(repo_root)
            return result

        if bridge_decision in ("REQUEST_CHANGES", "NO_GO"):
            # Read findings from the exact bridge render for this job
            render = _read_bridge_render(repo_root, bridge_job_id)
            findings_text = render if render else bridge_result.get("stdout", "")

            # Parse and classify findings by disposition
            parsed_findings = _parse_findings_from_render(render) if render else []
            blocking_findings, non_blocking_findings = _classify_findings(parsed_findings, finding_history)

            # Fail-closed: if any blocking finding has hit the repeat cap,
            # the implementer cannot resolve it — terminate as hard failure.
            if blocking_findings and finding_history:
                unresolvable = [
                    _finding_key(f) for f in blocking_findings
                    if finding_history.get(_finding_key(f), 0) >= REPEAT_FINDING_CAP
                ]
                if unresolvable:
                    log(f"HARD FAILURE: {len(unresolvable)} blocking finding(s) hit repeat cap "
                        f"({REPEAT_FINDING_CAP} rounds) — implementer cannot resolve")
                    result["status"] = "error"
                    result["step"] = "bridge_convergence"
                    result["errors"] = [
                        f"Blocking finding(s) unresolvable after {REPEAT_FINDING_CAP} rounds: "
                        + ", ".join(unresolvable[:5])
                    ]
                    result["unresolvable_findings"] = blocking_findings
                    _clear_state(repo_root)
                    return result

            # Auto-file non-blocking findings to deferred packet
            if non_blocking_findings:
                all_non_blocking.extend(non_blocking_findings)
                packet_path = _write_deferred_packet(repo_root, wave_id, all_non_blocking)
                deferred_packet_path = str(packet_path.relative_to(repo_root))
                executor_created.add(deferred_packet_path)
                result["deferred_packet_path"] = deferred_packet_path
                log(f"Filed {len(non_blocking_findings)} non-blocking finding(s) to {deferred_packet_path}")

            # If ALL findings are non-blocking, treat as converged
            if parsed_findings and not blocking_findings:
                log(f"All {len(non_blocking_findings)} findings are non-blocking — treating as GO")
                bridge_converged = True
                break

            # Only blocking findings (or raw text if unparseable) go to implementer
            if blocking_findings:
                blocking_text = json.dumps(blocking_findings, indent=2)
                findings_for_impl = (
                    f"## BLOCKING findings only (non-blocking deferred to {deferred_packet_path or 'N/A'})\n\n"
                    + blocking_text
                )
            else:
                # Couldn't parse structured findings — send raw text
                findings_for_impl = findings_text[:4000]

            log(f"Bridge: {bridge_decision} — {len(blocking_findings)} blocking, "
                f"{len(non_blocking_findings)} non-blocking — re-invoking implementer")

            # Snapshot before fix, track after
            pre_fix_files = set(_collect_changed_files(repo_root))
            # Re-invoke implementer to fix what bridge flagged
            fix_prompt = build_implementation_prompt(
                plan.get("content", "")
                + f"\n\n## Bridge Round {round_num} Findings ({bridge_decision})\n\n"
                + findings_for_impl,
                repo_root=repo_root,
                wave_id=wave_id,
                scope_hint=f"Fix {bridge_decision} findings from bridge round {round_num}",
            )
            fix_result = invoke_implementer(
                repo_root, fix_prompt,
                backend=backend, model_override=model,
                timeout=timeout, verbose=verbose,
            )
            log(f"Implementer fix result: {fix_result['status']}")

            # FAIL CLOSED on implementer failure during bridge loop
            if fix_result["status"] != "success":
                return {
                    "status": "error",
                    "step": "implementer_bridge_fix",
                    "errors": [
                        f"Implementer failed during bridge fix round {round_num}: "
                        f"{fix_result['status']} (exit={fix_result['exit_code']})"
                    ],
                }

            # Track what the fix round changed
            post_fix_files = set(_collect_changed_files(repo_root))
            implementer_changed |= (post_fix_files - pre_fix_files)
            # Recollect changed files after implementer fix (scoped to wave outputs)
            changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)
            log(f"Changed files after bridge fix: {len(changed_files)}")

            # Run pytest on changed test files mechanically
            test_files = [f for f in changed_files if f.startswith("mu/tests/") or "/test_" in f or f.endswith("_test.py")]
            if test_files:
                log(f"Running pytest on {len(test_files)} test file(s)...")
                pytest_result = _run_pytest_on_files(repo_root, test_files)
                if not pytest_result["passed"]:
                    log(f"pytest FAILED (exit={pytest_result['exit_code']}) — feeding back to implementer as blocking")
                    # Feed pytest failure back as a blocking finding for next round
                    pytest_prompt = build_implementation_prompt(
                        plan.get("content", "")
                        + f"\n\n## pytest FAILURE after bridge round {round_num}\n\n"
                        + f"Exit code: {pytest_result['exit_code']}\n"
                        + f"stdout:\n{pytest_result['stdout'][:3000]}\n"
                        + f"stderr:\n{pytest_result['stderr'][:1000]}",
                        repo_root=repo_root,
                        wave_id=wave_id,
                        scope_hint=f"Fix pytest failures from bridge round {round_num}",
                    )
                    pre_pytest_fix_files = set(_collect_changed_files(repo_root))
                    pytest_fix = invoke_implementer(
                        repo_root, pytest_prompt,
                        backend=backend, model_override=model,
                        timeout=timeout, verbose=verbose,
                    )
                    if pytest_fix["status"] != "success":
                        return {
                            "status": "error",
                            "step": "pytest_fix",
                            "errors": [f"Implementer failed fixing pytest failures: {pytest_fix['status']}"],
                        }
                    # Track what the pytest-fix pass changed
                    post_pytest_fix_files = set(_collect_changed_files(repo_root))
                    implementer_changed |= (post_pytest_fix_files - pre_pytest_fix_files)
                    changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)

            # Persist state after each bridge round
            _save_state(repo_root, {
                "plan_path": plan_path,
                "completed_step": f"bridge_round_{round_num}",
                "wave_id": wave_id,
                "bridge_rounds": round_num,
                "current_bridge_round": round_num,
                "deferred_packet_path": deferred_packet_path,
                "implementer_changed": sorted(implementer_changed),
                "executor_created": sorted(executor_created),
                "all_non_blocking": all_non_blocking,
                "finding_history": finding_history,
            })
            continue

        if bridge_result["exit_code"] != 0:
            log(f"Bridge invocation failed (exit={bridge_result['exit_code']}), failing closed")
            result["status"] = "error"
            result["step"] = "bridge_subprocess"
            result["errors"] = [
                f"Bridge subprocess failed in round {round_num} "
                f"(exit={bridge_result['exit_code']}). "
                f"stderr: {bridge_result.get('stderr', '')[:500]}"
            ]
            _clear_state(repo_root)
            return result

    if not bridge_converged:
        result["status"] = "max_rounds_reached"
        result["errors"] = [
            f"Bridge did not converge after {max_bridge_rounds} rounds. "
            f"Last bridge decision: {bridge_decision!r}."
        ]
        if all_non_blocking:
            result["deferred_non_blocking_count"] = len(all_non_blocking)
        log(f"Max bridge rounds ({max_bridge_rounds}) reached without convergence")
        # Clear state to prevent stale resume — next invocation must start fresh
        _clear_state(repo_root)
        return result

    # Persist state after bridge convergence
    _save_state(repo_root, {
        "plan_path": plan_path,
        "completed_step": "bridge_converged",
        "wave_id": wave_id,
        "bridge_rounds": result["bridge_rounds"],
        "deferred_packet_path": deferred_packet_path,
        "implementer_changed": sorted(implementer_changed),
        "executor_created": sorted(executor_created),
        "all_non_blocking": all_non_blocking,
        "finding_history": finding_history,
    })

    # Resume from NEEDS_PHASE_B re-entry: skip pytest gate + staging + supervisor,
    # jump directly into the re-entry loop below.
    if _skip_to_reentry:
        log("Resuming into NEEDS_PHASE_B re-entry (skipping supervisor)")
        findings_for_impl = (saved_state or {}).get("reentry_findings", "Fix required (resumed)")
        decision = "NEEDS_PHASE_B"
        # Provide stubs for variables used in re-entry block
        changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)
        deferred_packet_path = result.get("deferred_packet_path")
        supervisor_result = {"parsed": {"summary": findings_for_impl}}
        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        package_path = scratch_dir / "phase_b_supervisor_package.json"
        # Build a COMPLETE supervisor package — not an empty dict.
        # The re-entry path at line ~1489 updates changed_files and bridge_status,
        # but validate_package_schema() requires all 11 fields present.
        blocker_paths: list[str] = []
        blocking_dir = repo_root / "reports" / "deferred" / "blocking"
        if blocking_dir.is_dir():
            blocker_paths = sorted(
                str(p.relative_to(repo_root))
                for p in blocking_dir.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "README.md"
            )
        supervisor_package = {
            "task_id": routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            "wave_name": wave_id,
            "lane": "hooks/agents/bridge control-surface",
            "changed_files": changed_files,
            "scope_items": [plan_path],
            "fixes_implemented": ["Phase B implementation per locked plan (resumed from NEEDS_PHASE_B)"],
            "deferred_items": [deferred_packet_path] if deferred_packet_path else [],
            "bridge_status": {"rounds": result.get("bridge_rounds", 0), "reentry": True},
            "evidence_handles": {},
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
        }
        receipt_path = ""
    else:
        decision = None  # will be set by supervisor below

    if not _skip_to_reentry:
        # Step 5b: Final pytest gate — failed tests MUST block commit_ready
        changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)
        final_test_files = [f for f in changed_files if f.startswith("mu/tests/") or "/test_" in f or f.endswith("_test.py")]
        if final_test_files:
            log(f"Final pytest gate: running {len(final_test_files)} test file(s)...")
            final_pytest = _run_pytest_on_files(repo_root, final_test_files)
            if not final_pytest["passed"]:
                return {
                    "status": "error",
                    "step": "final_pytest_gate",
                    "errors": [
                        f"Final pytest gate FAILED (exit={final_pytest['exit_code']}). "
                        "Tests must pass before commit. "
                        f"stdout: {final_pytest['stdout'][:1000]}"
                    ],
                }
            log("Final pytest gate: PASSED")

        # Step 6: Stage files BEFORE running supervisor
        # This ensures the receipt staged_sha matches what commit_executor will use.
        # Scope to wave-owned files only — do not sweep unrelated dirty worktree files.
        if changed_files:
            log(f"Staging {len(changed_files)} wave-owned files before supervisor...")
            if not _stage_files(repo_root, changed_files):
                return {
                    "status": "error",
                    "step": "staging",
                    "errors": ["Failed to stage files before supervisor"],
                }

        # Step 7: Build and run pre-commit supervisor via structured client
        log("Building supervisor package...")
        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        package_path = scratch_dir / "phase_b_supervisor_package.json"

        # Discover active blocking packets for honest acknowledgment
        blocker_paths: list[str] = []
        blocking_dir = repo_root / "reports" / "deferred" / "blocking"
        if blocking_dir.is_dir():
            blocker_paths = sorted(
                str(p.relative_to(repo_root))
                for p in blocking_dir.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "README.md"
            )
        if blocker_paths:
            log(f"Acknowledging {len(blocker_paths)} active blocking packet(s)")

        supervisor_package = {
            "task_id": routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            "wave_name": wave_id,
            "lane": "hooks/agents/bridge control-surface",
            "changed_files": changed_files,
            "scope_items": [plan_path],
            "fixes_implemented": ["Phase B implementation per locked plan"],
            "deferred_items": [deferred_packet_path] if deferred_packet_path else [],
            "bridge_status": {"rounds": result.get("bridge_rounds", 0)},
            "evidence_handles": {},
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
        }
        package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        log("Running pre-commit supervisor...")
        supervisor_result = run_pre_commit_supervisor(
            repo_root, package_path, verbose=verbose,
        )
        result["pre_commit_decision"] = supervisor_result.get("parsed", {}).get("decision")
        receipt_path = supervisor_result.get("receipt_path", "")
        log(f"Supervisor decision: {result['pre_commit_decision']}, receipt: {receipt_path}")

        decision = result["pre_commit_decision"]
    if decision == "NEEDS_PHASE_B":
        # Re-entry: implementer fixes → bridge reviews → loop
        log("NEEDS_PHASE_B — re-invoking implementer then bridge loop")
        reentry_converged = False
        # Initial findings come from supervisor; subsequent rounds use bridge findings
        findings_for_impl = supervisor_result.get("parsed", {}).get("summary", "Fix required")

        # Persist needs_phase_b_reentry state so crash-resume re-enters here
        _save_state(repo_root, {
            "plan_path": plan_path,
            "completed_step": "needs_phase_b_reentry",
            "wave_id": wave_id,
            "bridge_rounds": result["bridge_rounds"],
            "deferred_packet_path": deferred_packet_path,
            "implementer_changed": sorted(implementer_changed),
            "executor_created": sorted(executor_created),
            "all_non_blocking": all_non_blocking,
            "finding_history": finding_history,
            "reentry_findings": findings_for_impl,
        })

        for reentry_round in range(result["bridge_rounds"] + 1, max_bridge_rounds + 1):
            log(f"Re-entry round {reentry_round}/{max_bridge_rounds}...")
            result["bridge_rounds"] = reentry_round

            log("Re-invoking implementer for fixes...")
            # R7-2: pre/post git diff tracking for re-entry implementer
            pre_reentry_files = set(_collect_changed_files(repo_root))
            reentry_prompt = build_implementation_prompt(
                plan.get("content", "") + "\n\n## Re-entry Findings\n\n"
                + findings_for_impl,
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

            # FAIL CLOSED on re-entry implementer failure
            if impl_result["status"] != "success":
                return {
                    "status": "error",
                    "step": "implementer_reentry",
                    "errors": [f"Implementer re-entry failed: {impl_result['status']}"],
                }

            # R7-2: recompute implementer_changed after re-entry
            post_reentry_files = set(_collect_changed_files(repo_root))
            implementer_changed |= (post_reentry_files - pre_reentry_files)
            changed_files = _collect_wave_owned_files(
                repo_root, plan_path, plan_declared_files,
                implementer_changed or None, executor_created or None,
            )
            log(f"Re-entry changed files: {len(changed_files)} (implementer touched {len(post_reentry_files - pre_reentry_files)})")

            # Bridge reviews the fix (bound to exact job_id)
            bridge_job_id = f"phase-b-reentry-r{reentry_round}-{uuid.uuid4().hex[:8]}"
            bridge_result = run_bridge_review(
                repo_root,
                f"Phase B re-entry R{reentry_round} after NEEDS_PHASE_B for {plan_path}",
                job_id=bridge_job_id,
                verbose=verbose,
                timeout=timeout,
            )
            bridge_decision = bridge_result.get("decision", "")
            log(f"Reentry bridge decision: {bridge_decision!r}")

            # Timeout is a hard error in re-entry too — do not silently retry
            if bridge_result["exit_code"] == -1:
                result["status"] = "error"
                result["errors"] = [
                    f"Bridge review timed out during re-entry round {reentry_round} "
                    f"(timeout={timeout}s). {bridge_result.get('stderr', '')}"
                ]
                _clear_state(repo_root)
                return result

            if bridge_result["exit_code"] == 0 and bridge_decision == "GO":
                log("Bridge re-entry converged: GO")
                reentry_converged = True
                break

            if bridge_decision == "QUESTION":
                # QUESTION in re-entry = fail closed, same as initial loop
                render = _read_bridge_render(repo_root, bridge_job_id)
                result["status"] = "question_for_founder"
                result["errors"] = [
                    f"Bridge returned QUESTION during re-entry (round {reentry_round}). "
                    "Founder input required.",
                ]
                if render:
                    result["bridge_render"] = render[:2000]
                _clear_state(repo_root)
                return result

            if bridge_decision in ("REQUEST_CHANGES", "NO_GO"):
                # Mirror initial loop: classify findings, defer non-blockers
                render = _read_bridge_render(repo_root, bridge_job_id)
                findings_text = render if render else bridge_result.get("stdout", "")

                parsed_findings = _parse_findings_from_render(render) if render else []
                blocking_findings, non_blocking_findings = _classify_findings(parsed_findings, finding_history)

                if non_blocking_findings:
                    all_non_blocking.extend(non_blocking_findings)
                    packet_path = _write_deferred_packet(repo_root, wave_id, all_non_blocking)
                    deferred_packet_path = str(packet_path.relative_to(repo_root))
                    executor_created.add(deferred_packet_path)
                    result["deferred_packet_path"] = deferred_packet_path
                    log(f"Re-entry: filed {len(non_blocking_findings)} non-blocking finding(s)")

                if parsed_findings and not blocking_findings:
                    log(f"Re-entry: all {len(non_blocking_findings)} findings non-blocking — treating as GO")
                    reentry_converged = True
                    break

                if blocking_findings:
                    blocking_text = json.dumps(blocking_findings, indent=2)
                    findings_for_impl = (
                        f"## BLOCKING findings only (non-blocking deferred to {deferred_packet_path or 'N/A'})\n\n"
                        + blocking_text
                    )
                else:
                    findings_for_impl = findings_text[:4000]

                log(f"Reentry bridge: {bridge_decision} — {len(blocking_findings)} blocking, "
                    f"{len(non_blocking_findings)} non-blocking — will re-invoke implementer")
                changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)

                # Checkpoint re-entry state so crash-resume picks up new findings and round
                _save_state(repo_root, {
                    "plan_path": plan_path,
                    "completed_step": "needs_phase_b_reentry",
                    "wave_id": wave_id,
                    "bridge_rounds": reentry_round,
                    "deferred_packet_path": deferred_packet_path,
                    "implementer_changed": sorted(implementer_changed),
                    "executor_created": sorted(executor_created),
                    "all_non_blocking": all_non_blocking,
                    "finding_history": finding_history,
                    "reentry_findings": findings_for_impl,
                })
                continue

            # Fail closed: nonzero exit with unrecognized/empty decision
            if bridge_result["exit_code"] != 0:
                log(f"Re-entry bridge subprocess failed (exit={bridge_result['exit_code']}), failing closed")
                result["status"] = "error"
                result["step"] = "reentry_bridge_subprocess"
                result["errors"] = [
                    f"Bridge subprocess failed during re-entry round {reentry_round} "
                    f"(exit={bridge_result['exit_code']}). "
                    f"stderr: {bridge_result.get('stderr', '')[:500]}"
                ]
                _clear_state(repo_root)
                return result

        if not reentry_converged:
            result["status"] = "max_rounds_reached"
            result["errors"] = [
                f"Bridge did not converge after {max_bridge_rounds} rounds (re-entry path). "
                f"Last bridge decision: {bridge_decision!r}."
            ]
            if all_non_blocking:
                result["deferred_non_blocking_count"] = len(all_non_blocking)
            # Clear state to prevent stale resume — next invocation must start fresh
            _clear_state(repo_root)
            return result

        # R7-3: mechanical pytest gate for re-entry path (mirrors initial path)
        changed_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)
        reentry_test_files = [f for f in changed_files if f.startswith("mu/tests/") or "/test_" in f or f.endswith("_test.py")]
        if reentry_test_files:
            log(f"Re-entry pytest gate: running {len(reentry_test_files)} test file(s)...")
            reentry_pytest = _run_pytest_on_files(repo_root, reentry_test_files)
            if not reentry_pytest["passed"]:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_pytest_gate",
                    "errors": [
                        f"Re-entry pytest gate FAILED (exit={reentry_pytest['exit_code']}). "
                        "Tests must pass before commit. "
                        f"stdout: {reentry_pytest['stdout'][:1000]}"
                    ],
                }
            log("Re-entry pytest gate: PASSED")

        # Re-stage and re-run supervisor after re-entry convergence
        # FAIL CLOSED if restaging fails — do not run supervisor on stale state
        # Scope to wave-owned files only — do not sweep unrelated dirty worktree files.
        if changed_files:
            if not _stage_files(repo_root, changed_files):
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_staging",
                    "errors": ["Failed to stage files after re-entry convergence"],
                }

        # Refresh ALL supervisor package truth for re-entry
        supervisor_package["changed_files"] = changed_files
        supervisor_package["bridge_status"] = {"rounds": result.get("bridge_rounds", 0), "reentry": True}
        # Refresh blocker acknowledgment (may have changed during re-entry)
        blocking_dir = repo_root / "reports" / "deferred" / "blocking"
        if blocking_dir.is_dir():
            supervisor_package["blocker_report_paths"] = sorted(
                str(p.relative_to(repo_root))
                for p in blocking_dir.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "README.md"
            )
        package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        log("Re-running supervisor after bridge re-entry...")
        supervisor_result = run_pre_commit_supervisor(
            repo_root, package_path, verbose=verbose,
        )
        decision = supervisor_result.get("parsed", {}).get("decision")
        receipt_path = supervisor_result.get("receipt_path", "")
        result["pre_commit_decision"] = decision
        log(f"Post-reentry supervisor decision: {decision}")

        if decision == "NEEDS_PHASE_B":
            result["status"] = "needs_phase_b"
            result["errors"] = ["Supervisor returned NEEDS_PHASE_B after reentry convergence. "
                                "Manual intervention required."]
            _clear_state(repo_root)
            return result
        elif decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            result["status"] = "supervisor_rejected"
            result["errors"] = [f"Post-reentry supervisor returned {decision}"]
            _clear_state(repo_root)
            return result

    elif decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        result["status"] = "supervisor_rejected"
        result["errors"] = [f"Supervisor returned {decision}, not COMMIT_GO"]
        _clear_state(repo_root)
        return result

    # Step 8: Prepare commit handoff with explicit receipt path
    # FAIL CLOSED if receipt_path is empty — supervisor must provide a valid path
    if not receipt_path or not receipt_path.strip():
        return {
            "status": "error",
            "step": "commit_handoff",
            "errors": ["Supervisor returned empty receipt_path — cannot produce commit_ready handoff. Fail closed."],
        }

    # Scope to wave-owned files only — do not sweep all dirty files
    wave_owned_files = _collect_wave_owned_files(repo_root, plan_path, plan_declared_files, implementer_changed or None, executor_created or None)
    if not wave_owned_files:
        return {
            "status": "error",
            "step": "commit_handoff",
            "errors": ["files_to_stage is empty — cannot produce a commit_ready handoff with no files"],
        }
    log(f"Preparing commit handoff ({len(wave_owned_files)} wave-owned files)...")
    handoff_path = prepare_commit_handoff(
        repo_root,
        wave_id=wave_id,
        task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
        wave_class="L4_ENABLER",
        target_gate_id="G8",
        tracker_note_text=f"- Tracker sync note (Phase B, {wave_id}): Phase B implementation per locked plan.",
        fixes_implemented=["Phase B implementation per locked plan"],
        files_to_stage=wave_owned_files,
        pre_commit_receipt_path=receipt_path,
        commit_message=f"feat: Phase B implementation for {wave_id}\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>",
        pr_title=f"feat: Phase B - {wave_id}",
        pr_body=f"## Summary\nPhase B implementation per locked plan at {plan_path}",
    )
    result["status"] = "commit_ready"
    result["handoff_path"] = str(handoff_path)
    result["pre_commit_decision"] = decision
    result["receipt_path"] = receipt_path
    # Clear state file on successful completion
    _clear_state(repo_root)
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
    parser.add_argument(
        "--bootstrap-exception",
        action="store_true",
        dest="bootstrap_exception",
        help="BOOTSTRAP_PHASE_B_EXCEPTION: override routing/validation when "
             "the wave modifies executor/implementer surfaces themselves. "
             "Not a generic bypass — see CLAUDE.md.",
    )
    # Keep --force as hidden alias for backward compatibility in tests
    parser.add_argument(
        "--force",
        action="store_true",
        dest="bootstrap_exception",
        help=argparse.SUPPRESS,
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
        force=args.bootstrap_exception,
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
