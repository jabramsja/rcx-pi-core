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
import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        load_executor_config,
        DEFAULT_EXECUTOR_CONFIG,
        load_routing_record, ExecutorCommonError,
        BLOCKING_KEYWORDS, NON_BLOCKING_KEYWORDS,
        REPEAT_FINDING_CAP,
        MAX_WAVE_ID_LEN, WAVE_ID_RE,
        normalize_wave_id,
        process_descendants,
        artifact_size_mtime_ns,
        terminate_process_tree,
        ensure_not_agent_review_mode,
        run_bridge_subprocess,
    )
except ImportError:
    # Fallback for direct execution
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    load_executor_config = _mod.load_executor_config
    DEFAULT_EXECUTOR_CONFIG = _mod.DEFAULT_EXECUTOR_CONFIG
    load_routing_record = _mod.load_routing_record
    ExecutorCommonError = _mod.ExecutorCommonError
    BLOCKING_KEYWORDS = _mod.BLOCKING_KEYWORDS
    NON_BLOCKING_KEYWORDS = _mod.NON_BLOCKING_KEYWORDS
    REPEAT_FINDING_CAP = _mod.REPEAT_FINDING_CAP
    MAX_WAVE_ID_LEN = _mod.MAX_WAVE_ID_LEN
    WAVE_ID_RE = _mod.WAVE_ID_RE
    normalize_wave_id = _mod.normalize_wave_id
    process_descendants = _mod.process_descendants
    artifact_size_mtime_ns = _mod.artifact_size_mtime_ns
    terminate_process_tree = _mod.terminate_process_tree
    ensure_not_agent_review_mode = _mod.ensure_not_agent_review_mode
    run_bridge_subprocess = _mod.run_bridge_subprocess

try:
    from tracker_sync_note import TrackerSyncNoteFields, render_tracker_sync_note
except ImportError:
    import importlib.util as _ilu
    _tracker_path = SCRIPT_DIR / "tracker_sync_note.py"
    _tracker_spec = _ilu.spec_from_file_location("tracker_sync_note", str(_tracker_path))
    _tracker_mod = _ilu.module_from_spec(_tracker_spec)
    assert _tracker_spec.loader is not None
    sys.modules["tracker_sync_note"] = _tracker_mod
    _tracker_spec.loader.exec_module(_tracker_mod)
    TrackerSyncNoteFields = _tracker_mod.TrackerSyncNoteFields
    render_tracker_sync_note = _tracker_mod.render_tracker_sync_note


class PhaseBExecutorError(RuntimeError):
    """Raised when Phase B executor cannot proceed."""


ALLOWED_FINDING_DISPOSITIONS = {"blocking", "non_blocking"}
BRIDGE_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RECOGNIZED_BRIDGE_DECISIONS = {"GO", "REQUEST_CHANGES", "NO_GO", "QUESTION"}
ALLOWED_REVIEW_DEPTHS = {"quick", "full", "founder", "all"}
BRIDGE_REVIEW_POLL_INTERVAL = 30.0
BRIDGE_REVIEW_POLL_SLEEP = 5.0
BRIDGE_REVIEW_STALE_TIMEOUT = 120.0
BRIDGE_REVIEW_AGGREGATION_HANG_TIMEOUT = 60.0
DEFAULT_PYTEST_GATE_TIMEOUT_S = 300
MAX_PYTEST_GATE_TIMEOUT_S = 900


# ---------------------------------------------------------------------------
# Finding disposition helpers
# ---------------------------------------------------------------------------

def _disposition_for_finding(finding: dict[str, Any]) -> tuple[str, str]:
    """Derive effective disposition for a single finding.

    Returns (disposition, reason) tuple for logging/auditability.

    Priority:
    1. Severity 'critical'/'high' — always blocking unless an explicit valid
       disposition is present.
    2. Explicit 'disposition' field — use only if valid.
    3. Medium/low severity — non-blocking UNLESS blocking keyword match.
    4. No severity — keyword match, then fail-closed blocking.
    """
    severity = (finding.get("severity") or "").lower()
    disposition = finding.get("disposition")
    finding_class = str(finding.get("class") or "").upper()

    # Governance/doc-only findings: DOC_ACCURACY or POLICY_BOUND on governance
    # paths are editorial, not runtime risks. Downgrade to non-blocking regardless
    # of severity. Critical DEFECT findings on code still block.
    _GOV_CLASSES = {"POLICY_BOUND", "DOC_ACCURACY"}
    _GOV_PATH_PREFIXES = ("reports/", "TASKS.md", ".claude/", "CHANGELOG.md", "STATUS.md")
    finding_file = str(finding.get("file") or "")
    is_gov_path = any(finding_file.startswith(p) for p in _GOV_PATH_PREFIXES)
    is_governance = finding_class in _GOV_CLASSES and is_gov_path
    if is_governance:
        return "non_blocking", (
            f"{severity} {finding_class} on governance/doc path — "
            f"downgraded to non-blocking (file: {finding_file})"
        )

    # Critical/high findings on non-governance paths stay blocking even if an
    # explicit disposition tries to soften them. Fail-closed severity floor.
    if severity == "critical":
        if disposition == "non_blocking":
            return "blocking", "critical severity overrides explicit non_blocking disposition"
        return "blocking", "critical severity (always blocking)"

    if severity == "high":
        if disposition == "non_blocking":
            return "blocking", "high severity overrides explicit non_blocking disposition"
        return "blocking", "high severity (always blocking)"

    if disposition is not None:
        if disposition in ALLOWED_FINDING_DISPOSITIONS:
            return disposition, "explicit disposition field"
        return "blocking", f"invalid disposition {disposition!r} (fail-closed)"

    # Build searchable text from title + summary
    text = " ".join(filter(None, [
        finding.get("title", ""),
        finding.get("summary", ""),
    ])).lower()

    # Check for keyword matches
    blocking_match = next((kw for kw in BLOCKING_KEYWORDS if kw in text), None)
    non_blocking_match = next((kw for kw in NON_BLOCKING_KEYWORDS if kw in text), None)

    # Low/medium doc-accuracy findings are documentation/editorial residue, not
    # behavioral blockers. Keep them non-blocking even if their title quotes a
    # blocking keyword while describing prior behavior (for example "crash").
    if severity in ("medium", "low") and finding_class == "DOC_ACCURACY":
        if non_blocking_match:
            return "non_blocking", f"{severity} DOC_ACCURACY + non-blocking keyword: '{non_blocking_match}'"
        if blocking_match:
            return "non_blocking", (
                f"{severity} DOC_ACCURACY remains non-blocking despite keyword: '{blocking_match}'"
            )
        return "non_blocking", f"{severity} DOC_ACCURACY finding"

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

        print(f"  [classify] '{title}' → {disposition} ({reason})", file=sys.stderr)
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
    *,
    wave_class: str = "",
    target_gate_id: str = "",
) -> Path:
    """Write or update a deferred non-blocking findings packet.

    Returns the path to the written packet.
    """
    deferred_dir = repo_root / "reports" / "deferred" / "non_blocking"
    deferred_dir.mkdir(parents=True, exist_ok=True)
    safe_wave = normalize_wave_id(wave_id)
    packet_path = deferred_dir / f"{safe_wave}_bridge_nonblockers.md"

    lines = [
        f"# Deferred Non-Blocking Findings: {wave_id}",
        "",
        f"Wave: {wave_id}",
        f"Class: {wave_class}" if wave_class else "Class: unknown",
        f"Target Gate: {target_gate_id}" if target_gate_id else "Target Gate: unknown",
        "Status: DEFERRED_NON_BLOCKING",
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


def _resolve_bridge_reviewer(config: dict[str, Any], phase_key: str, default: str = "codex") -> str:
    """Resolve bridge reviewer backend from executor config."""
    reviewer = config.get("bridge_reviewers", {}).get(phase_key, default)
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise PhaseBExecutorError(
            f"Invalid bridge reviewer {reviewer!r} for {phase_key}; expected non-empty string"
        )
    return reviewer.strip()


def _resolve_bridge_turn_timeout(config: dict[str, Any], phase_key: str, default: float) -> float:
    """Resolve bridge turn timeout budget from executor config."""
    timeout = config.get("bridge_turn_timeouts", {}).get(phase_key, default)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise PhaseBExecutorError(
            f"Invalid bridge turn timeout {timeout!r} for {phase_key}; expected positive number"
        )
    return float(timeout)


def _record_non_blocking_findings(
    repo_root: Path,
    wave_id: str,
    existing_findings: list[dict[str, Any]],
    new_findings: list[dict[str, Any]],
    *,
    wave_class: str = "",
    target_gate_id: str = "",
) -> tuple[list[dict[str, Any]], Path | None]:
    """Merge non-blocking findings by stable key and refresh the deferred packet."""
    if not new_findings:
        return existing_findings, None
    merged: dict[str, dict[str, Any]] = {
        _finding_key(finding): finding
        for finding in existing_findings
    }
    for finding in new_findings:
        merged[_finding_key(finding)] = finding
    merged_findings = list(merged.values())
    return merged_findings, _write_deferred_packet(
        repo_root, wave_id, merged_findings,
        wave_class=wave_class, target_gate_id=target_gate_id,
    )


def _supervisor_reason_text(parsed: dict[str, Any]) -> str:
    """Return the actionable supervisor reason instead of only the decision token."""
    parts: list[str] = []
    summary = str(parsed.get("summary", "") or "").strip()
    if summary:
        parts.append(summary)
    error_detail = str(parsed.get("error_detail", "") or "").strip()
    if error_detail and error_detail != summary:
        parts.append(f"detail: {error_detail}")
    request_for_claude = str(parsed.get("request_for_claude", "") or "").strip()
    if request_for_claude and request_for_claude not in parts:
        parts.append(f"next: {request_for_claude}")
    return " | ".join(parts)


def _collect_supervisor_deferred_items(
    changed_files: list[str],
    deferred_packet_path: str | None,
) -> list[str]:
    """Surface active wave-owned deferred non-blocking packets in supervisor packages."""
    deferred_items = {
        rel_path
        for rel_path in changed_files
        if rel_path.startswith("reports/deferred/non_blocking/")
        and rel_path.endswith(".md")
        and not rel_path.endswith("/README.md")
    }
    if deferred_packet_path:
        deferred_items.add(deferred_packet_path)
    return sorted(deferred_items)


def _extract_agent_envelope_payloads(render_text: str) -> tuple[list[str], bool, bool]:
    """Return payloads, whether markers were present, and whether nesting was seen."""
    payloads: list[str] = []
    current: list[str] = []
    inside = False
    saw_markers = False
    saw_nested_markers = False

    for line in render_text.splitlines():
        stripped = line.strip()
        if stripped == "BEGIN_AGENT_ENVELOPE":
            saw_markers = True
            if inside:
                saw_nested_markers = True
            inside = True
            current = []
            continue
        if stripped == "END_AGENT_ENVELOPE":
            saw_markers = True
            if inside:
                payloads.append("\n".join(current))
                current = []
                inside = False
            continue
        if inside:
            current.append(line)
    if inside:
        saw_markers = True
    return payloads, saw_markers, saw_nested_markers


def _normalize_agent_envelope_payload(payload: str) -> str:
    """Strip optional fenced-code wrapper around an AGENT_ENVELOPE payload."""
    stripped = payload.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _iter_agent_message_texts(text: str) -> list[str]:
    """Extract agent_message payloads from a JSONL bridge raw transcript."""
    texts: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "agent_message":
            continue
        message_text = item.get("text")
        if isinstance(message_text, str) and message_text.strip():
            texts.append(message_text)
    return texts


def _iter_bridge_raw_texts_from_render(render_text: str) -> list[str]:
    """Load raw bridge turn outputs referenced by a rendered transcript.

    The rendered markdown summary omits machine fields like `disposition`, so
    Phase B must prefer the raw reviewer transcript when it is available.
    """
    raw_output_re = re.compile(r"^\s*-\s+Raw output:\s+(.+)$", re.MULTILINE)
    texts: list[str] = []
    seen: set[str] = set()
    for match in reversed(list(raw_output_re.finditer(render_text))):
        raw_ref = match.group(1).strip()
        path = Path(raw_ref)
        if not path.is_absolute():
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue
    return texts


def _iter_bridge_raw_texts(
    repo_root: Path,
    job_id: str,
    render_text: str = "",
) -> list[str]:
    """Load raw bridge reviewer outputs for a job id, falling back to render refs.

    The rendered markdown can lag the raw reviewer transcript briefly after the
    bridge subprocess exits. Prefer direct raw reviewer files by job id so Phase B
    can still classify the authoritative findings when the render is stale.
    """
    texts: list[str] = []
    seen_paths: set[str] = set()

    if BRIDGE_JOB_ID_RE.fullmatch(job_id or ""):
        raw_dir = repo_root / ".agent_bus" / "raw" / job_id
        if raw_dir.is_dir():
            reviewer_files = sorted(
                (
                    path for path in raw_dir.iterdir()
                    if path.is_file() and "reviewer" in path.name
                ),
                reverse=True,
            )
            other_files = sorted(
                (
                    path for path in raw_dir.iterdir()
                    if path.is_file() and path not in reviewer_files
                ),
                reverse=True,
            )
            for path in reviewer_files + other_files:
                key = str(path.resolve())
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                try:
                    texts.append(path.read_text(encoding="utf-8"))
                except OSError:
                    continue

    raw_output_re = re.compile(r"^\s*-\s+Raw output:\s+(.+)$", re.MULTILINE)
    for match in reversed(list(raw_output_re.finditer(render_text))):
        raw_ref = match.group(1).strip()
        path = Path(raw_ref)
        if not path.is_absolute():
            continue
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        try:
            texts.append(path.read_text(encoding="utf-8"))
        except OSError:
            continue

    return texts


def _has_parse_ready_bridge_raw_text(raw_text: str) -> bool:
    """Return True when a raw reviewer transcript is ready for findings parsing."""
    return (
        ("BEGIN_AGENT_ENVELOPE" in raw_text and "END_AGENT_ENVELOPE" in raw_text)
        or bool(re.search(r"^\s*\d+\.\s+\*\*(\w+)\*\*\s*\(([^)]+)\)\s*:\s*(.+)", raw_text, re.MULTILINE))
    )


def _read_bridge_review_material(
    repo_root: Path,
    job_id: str,
    *,
    settle_timeout: float = 2.0,
    poll_sleep: float = 0.05,
) -> tuple[str, list[str]]:
    """Read rendered + raw bridge artifacts, allowing a brief post-exit settle window.

    Bridge subprocess exit can race the final render/raw artifact flush. Poll
    briefly so Phase B reads the completed reviewer envelope instead of treating a
    stale partial view as malformed.
    """
    deadline = time.monotonic() + max(settle_timeout, 0.0)
    best_render = ""
    best_raw_texts: list[str] = []

    while True:
        render_text = _read_bridge_render(repo_root, job_id)
        raw_texts = _iter_bridge_raw_texts(repo_root, job_id, render_text)
        if render_text:
            best_render = render_text
        if raw_texts:
            best_raw_texts = raw_texts
        if any(_has_parse_ready_bridge_raw_text(text) for text in raw_texts):
            return render_text or best_render, raw_texts
        if time.monotonic() >= deadline:
            return render_text or best_render, raw_texts or best_raw_texts
        time.sleep(poll_sleep)


def _parse_findings_from_text(text: str) -> list[dict[str, Any]]:
    """Extract structured findings from raw bridge text or rendered markdown.

    Tries two strategies in order:
    1. JSON envelope between BEGIN_AGENT_ENVELOPE / END_AGENT_ENVELOPE markers.
    2. Numbered markdown findings like:
         1. **DEFECT** (critical): Title text
            - File: path/to/file.py
            - Evidence: description of evidence
    """
    agent_messages = _iter_agent_message_texts(text)
    if agent_messages:
        for message_text in reversed(agent_messages):
            findings = _parse_findings_from_text(message_text)
            if findings:
                return findings
        return []

    # Strategy 1: JSON envelope
    # Parse envelope blocks structurally so malformed markers cannot swallow
    # later payloads, and fail closed if multiple conflicting valid envelopes
    # appear in a single render.
    envelope_payloads, saw_envelope_markers, saw_nested_markers = _extract_agent_envelope_payloads(text)
    if saw_nested_markers:
        return [{
            "title": "Nested AGENT_ENVELOPE markers blocked structured bridge findings parsing",
            "severity": "critical",
            "type": "DEFECT",
            "disposition": "blocking",
            "detail": "Bridge render contained nested AGENT_ENVELOPE markers.",
        }]
    # Use the LAST valid envelope with non-empty findings — same strategy as
    # bridge_supervisor.parse_envelope().  Codex emits draft envelopes during
    # reasoning; only the final one is authoritative.
    any_valid = False
    for payload in reversed(envelope_payloads):
        try:
            envelope = json.loads(_normalize_agent_envelope_payload(payload))
        except (json.JSONDecodeError, TypeError):
            continue
        any_valid = True
        findings = envelope.get("findings")
        if isinstance(findings, list) and findings:
            return findings
    # Envelope markers were present but no valid JSON could be parsed —
    # fail closed so malformed reviewer output doesn't silently pass.
    if saw_envelope_markers and not any_valid and envelope_payloads:
        return [{
            "title": "All AGENT_ENVELOPE payloads in bridge render are malformed JSON",
            "severity": "critical",
            "type": "DEFECT",
            "disposition": "blocking",
            "detail": "Bridge render contained envelope markers but no parseable JSON payload.",
        }]

    # Strategy 2: numbered markdown findings
    # Pattern: "  N. **TYPE** (severity): title"  with optional indented detail lines
    finding_re = re.compile(
        r"^\s*\d+\.\s+\*\*(\w+)\*\*\s*\(([^)]+)\)\s*:\s*(.+)",
        re.MULTILINE,
    )
    findings: list[dict[str, Any]] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = finding_re.match(lines[i])
        if m:
            finding_class = m.group(1).strip()
            finding: dict[str, Any] = {
                "title": m.group(3).strip(),
                "severity": m.group(2).strip(),
                "type": finding_class,
                "class": finding_class,
                # Markdown render summaries do not preserve reviewer disposition.
                # Fail closed when envelope data is unavailable.
                "disposition": "blocking",
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
    if findings:
        return findings

    if saw_envelope_markers and not any_valid:
        return [{
            "title": "Malformed AGENT_ENVELOPE blocked structured bridge findings parsing",
            "severity": "critical",
            "type": "DEFECT",
            "disposition": "blocking",
            "detail": "Bridge render contained AGENT_ENVELOPE markers but no valid JSON findings payload.",
        }]
    return findings


def _parse_findings_from_render(
    render_text: str,
    raw_texts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Extract structured findings from bridge render text.

    Prefer raw reviewer transcripts referenced by the render so explicit bridge
    metadata like `disposition` survives classification. Fall back to rendered
    markdown parsing only when raw outputs are unavailable.
    """
    preferred_raw_texts = raw_texts if raw_texts is not None else _iter_bridge_raw_texts_from_render(render_text)
    for raw_text in preferred_raw_texts:
        findings = _parse_findings_from_text(raw_text)
        if findings:
            return findings
    return _parse_findings_from_text(render_text)


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
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "passed": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "pytest timed out", "passed": False}


def _resolve_pytest_gate_timeout(raw_timeout: Any) -> int:
    """Bound local pytest gates to a sane floor/cap inside Phase B."""
    try:
        timeout_s = int(float(raw_timeout))
    except (TypeError, ValueError):
        return DEFAULT_PYTEST_GATE_TIMEOUT_S
    if timeout_s <= 0:
        return DEFAULT_PYTEST_GATE_TIMEOUT_S
    return max(DEFAULT_PYTEST_GATE_TIMEOUT_S, min(timeout_s, MAX_PYTEST_GATE_TIMEOUT_S))


def _summarize_pytest_failure(result: dict[str, Any], *, stdout_limit: int = 1000, stderr_limit: int = 1000) -> str:
    """Build a bounded pytest failure summary without dropping stderr-only failures."""
    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()
    parts: list[str] = []
    if stdout:
        parts.append(f"stdout: {stdout[:stdout_limit]}")
    if stderr:
        parts.append(f"stderr: {stderr[:stderr_limit]}")
    return " ".join(parts) if parts else "no stdout/stderr captured"


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


def update_plan_packet_status(repo_root: Path, plan_path: str, new_status: str) -> None:
    """Update the Status: field in a tracked plan packet.

    Called after bridge convergence to advance the packet from
    'Phase A' to 'Phase B (implementation-complete, bridge-converged)'.
    This prevents the pre-commit supervisor from flagging a stale
    Phase A status on a commit-ready wave (Bug 1, 2026-04-06).
    """
    full_path = (repo_root / plan_path).resolve()
    if not full_path.exists():
        return
    content = full_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated = False
    for i, line in enumerate(lines):
        clean = line.replace("**", "").strip()
        if clean.startswith("Status:"):
            lines[i] = f"Status: {new_status}"
            updated = True
            break
    if updated:
        full_path.write_text("\n".join(lines), encoding="utf-8")


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
) -> None:
    """Validate inputs before proceeding with Phase B.

    Raises PhaseBExecutorError on invalid routing token or unlocked plan.
    Callers holding BOOTSTRAP_PHASE_B_EXCEPTION may catch and override.
    """
    errors: list[str] = []

    # Routing decision must be ROUTE_PHASE_B
    decision = routing_record.get("decision", "")
    if decision != "ROUTE_PHASE_B":
        errors.append(f"Expected ROUTE_PHASE_B, got {decision}")

    # Plan must be locked (or ROUTING_RECORD_AUTHORITY for planless mode)
    lock = plan.get("phase_a_lock", "")
    if lock not in ("LOCKED", "ROUTING_RECORD_AUTHORITY"):
        errors.append(f"Plan Phase-A-Lock must be LOCKED (or ROUTING_RECORD_AUTHORITY for planless), got {lock}")

    if errors:
        raise PhaseBExecutorError(
            f"validate_inputs fatal: {'; '.join(errors)}"
        )


def _parse_ps_time_seconds(value: str) -> float:
    """Parse `ps` TIME output into seconds."""
    text = value.strip()
    if not text:
        return 0.0
    days = 0
    if "-" in text:
        day_text, text = text.split("-", 1)
        try:
            days = int(day_text)
        except ValueError:
            return 0.0
    parts = text.split(":")
    try:
        seconds = float(parts[-1])
    except (IndexError, ValueError):
        return 0.0
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return (days * 86400) + (hours * 3600) + (minutes * 60) + seconds


def _bridge_process_snapshot(root_pid: int, repo_root: Path) -> tuple[tuple[int, ...], tuple[tuple[int, float], ...]]:
    """Return descendant PID list and CPU-time fingerprint for a bridge subprocess tree."""
    if root_pid <= 0:
        return (), ()
    try:
        os.kill(root_pid, 0)
    except (ProcessLookupError, PermissionError):
        return (), ()

    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,ppid=,time="],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return (), ()

    children_by_parent: dict[int, set[int]] = {}
    cpu_by_pid: dict[int, float] = {}
    for raw in proc.stdout.splitlines():
        parts = raw.split(None, 2)
        if len(parts) != 3:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        children_by_parent.setdefault(ppid, set()).add(pid)
        cpu_by_pid[pid] = _parse_ps_time_seconds(parts[2])

    descendants: set[int] = set()
    stack = list(children_by_parent.get(root_pid, set()))
    while stack:
        pid = stack.pop()
        if pid in descendants:
            continue
        descendants.add(pid)
        stack.extend(children_by_parent.get(pid, set()))

    tracked = {root_pid, *descendants}
    cpu_fingerprint = tuple(
        sorted((pid, cpu_by_pid.get(pid, 0.0)) for pid in tracked)
    )
    return tuple(sorted(descendants)), cpu_fingerprint


def _bridge_file_fingerprint(path: Path) -> tuple[bool, int, int | None]:
    if not path.exists():
        return (False, 0, None)
    stat = path.stat()
    return (True, stat.st_size, stat.st_mtime_ns)


def _bridge_artifact_fingerprint(
    repo_root: Path,
    job_id: str,
    stdout_path: Path,
    stderr_path: Path,
) -> tuple[Any, ...]:
    rendered_path = repo_root / ".agent_bus" / "rendered" / f"{job_id}.md"
    raw_dir = repo_root / ".agent_bus" / "raw" / job_id
    raw_files: tuple[tuple[str, tuple[bool, int, int | None]], ...] = ()
    if raw_dir.exists():
        raw_files = tuple(
            sorted(
                (path.name, _bridge_file_fingerprint(path))
                for path in raw_dir.iterdir()
                if path.is_file()
            )
        )
    return (
        _bridge_file_fingerprint(stdout_path),
        _bridge_file_fingerprint(stderr_path),
        _bridge_file_fingerprint(rendered_path),
        raw_files,
    )


def _bridge_progress_snapshot(
    repo_root: Path,
    job_id: str,
    root_pid: int,
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    child_pids, cpu_fingerprint = _bridge_process_snapshot(root_pid, repo_root)
    return {
        "child_pids": child_pids,
        "cpu_fingerprint": cpu_fingerprint,
        "artifact_fingerprint": _bridge_artifact_fingerprint(
            repo_root, job_id, stdout_path, stderr_path
        ),
    }


def _terminate_bridge_subprocess(proc: subprocess.Popen[str]) -> None:
    """Terminate a bridge subprocess and its process group."""
    try:
        pgid = os.getpgid(proc.pid)
    except (OSError, ProcessLookupError):
        pgid = None

    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.terminate()
    except (OSError, ProcessLookupError):
        pass

    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.1)

    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGKILL)
        else:
            proc.kill()
    except (OSError, ProcessLookupError):
        pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _run_bridge_review_subprocess(
    repo_root: Path,
    cmd: list[str],
    *,
    job_id: str,
    timeout: int,
    verbose: bool,
    env: dict[str, str] | None = None,
    poll_interval: float = BRIDGE_REVIEW_POLL_INTERVAL,
    stale_timeout: float = BRIDGE_REVIEW_STALE_TIMEOUT,
    aggregation_hang_timeout: float = BRIDGE_REVIEW_AGGREGATION_HANG_TIMEOUT,
) -> dict[str, Any]:
    """Run bridge review with active stale/aggregation monitoring."""
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    run_id = job_id or uuid.uuid4().hex[:8]
    stdout_path = scratch_dir / f"phase_b_bridge_{run_id}.stdout.log"
    stderr_path = scratch_dir / f"phase_b_bridge_{run_id}.stderr.log"
    poll_sleep = min(BRIDGE_REVIEW_POLL_SLEEP, poll_interval)

    with stdout_path.open("w", encoding="utf-8") as stdout_handle, \
            stderr_path.open("w", encoding="utf-8") as stderr_handle:
        proc = subprocess.Popen(
            cmd,
            cwd=repo_root,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            env=env,
            start_new_session=True,
        )

        def _read_logs() -> tuple[str, str]:
            stdout_handle.flush()
            stderr_handle.flush()
            return (
                stdout_path.read_text(encoding="utf-8"),
                stderr_path.read_text(encoding="utf-8"),
            )

        last_snapshot = _bridge_progress_snapshot(
            repo_root, job_id, proc.pid, stdout_path, stderr_path
        )
        last_progress_at = time.monotonic()
        start_time = last_progress_at
        last_heartbeat_at = 0.0

        while True:
            exit_code = proc.poll()
            snapshot = _bridge_progress_snapshot(
                repo_root, job_id, proc.pid, stdout_path, stderr_path
            )
            now = time.monotonic()
            if snapshot != last_snapshot:
                last_progress_at = now
            idle_for = now - last_progress_at

            if verbose and (now - last_heartbeat_at >= poll_interval):
                stderr_bytes = snapshot["artifact_fingerprint"][1][1]
                print(
                    "[phase-b] Bridge heartbeat: "
                    f"job={job_id} pid={proc.pid} child_pids={list(snapshot['child_pids'])} "
                    f"idle_seconds={idle_for:.1f} stderr_bytes={stderr_bytes}",
                    file=sys.stderr,
                    flush=True,
                )
                last_heartbeat_at = now

            if exit_code is not None:
                stdout, stderr = _read_logs()
                return {
                    "exit_code": exit_code,
                    "stdout": stdout,
                    "stderr": stderr,
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            if not snapshot["child_pids"] and idle_for >= aggregation_hang_timeout:
                _terminate_bridge_subprocess(proc)
                stdout, stderr = _read_logs()
                return {
                    "exit_code": -3,
                    "stdout": stdout,
                    "stderr": (
                        f"Bridge review aggregation hang after {idle_for:.1f}s "
                        f"(job_id={job_id}, stdout_log={stdout_path.name}, stderr_log={stderr_path.name}).\n"
                        f"{stderr}"
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            if idle_for >= stale_timeout:
                _terminate_bridge_subprocess(proc)
                stdout, stderr = _read_logs()
                return {
                    "exit_code": -2,
                    "stdout": stdout,
                    "stderr": (
                        f"Bridge review stale after {idle_for:.1f}s "
                        f"(job_id={job_id}, child_pids={list(snapshot['child_pids'])}, "
                        f"stdout_log={stdout_path.name}, stderr_log={stderr_path.name}).\n"
                        f"{stderr}"
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            if now - start_time >= timeout:
                _terminate_bridge_subprocess(proc)
                stdout, stderr = _read_logs()
                return {
                    "exit_code": -1,
                    "stdout": stdout,
                    "stderr": (
                        f"Bridge review timed out after {timeout}s "
                        f"(job_id={job_id}, stdout_log={stdout_path.name}, stderr_log={stderr_path.name}).\n"
                        f"{stderr}"
                    ).strip(),
                    "stdout_path": str(stdout_path.relative_to(repo_root)),
                    "stderr_path": str(stderr_path.relative_to(repo_root)),
                }

            last_snapshot = snapshot
            time.sleep(poll_sleep)


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
    config = load_executor_config(repo_root)
    reviewer = _resolve_bridge_reviewer(config, "phase_b")
    bridge_turn_timeout = _resolve_bridge_turn_timeout(config, "phase_b", default=300.0)

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
        "--reviewer", reviewer,
    ]
    if job_id:
        cmd.extend(["--job-id", job_id])
    if verbose:
        cmd.append("-v")

    result = _run_bridge_review_subprocess(
        repo_root,
        cmd,
        job_id=job_id or "",
        timeout=timeout,
        verbose=verbose,
        stale_timeout=max(BRIDGE_REVIEW_STALE_TIMEOUT, bridge_turn_timeout),
        env={
            **os.environ,
            "RCX_BRIDGE_MAX_TURN_WALL_TIME_S": str(min(timeout, bridge_turn_timeout)),
        },
    )
    stdout_stripped = result["stdout"].strip()
    decision = ""
    if stdout_stripped:
        for line in reversed(stdout_stripped.splitlines()):
            line = line.strip()
            if line in RECOGNIZED_BRIDGE_DECISIONS:
                decision = line
                break
    result["decision"] = decision
    result["job_id"] = job_id or ""
    return result


def _read_bridge_render(repo_root: Path, job_id: str) -> str:
    """Read the rendered bridge output for a specific job_id.

    Returns the rendered content, or empty string if not found.
    The rendered file is at .agent_bus/rendered/{job_id}.md.
    """
    if not BRIDGE_JOB_ID_RE.fullmatch(job_id or ""):
        return ""
    rendered_path = repo_root / ".agent_bus" / "rendered" / f"{job_id}.md"
    if rendered_path.exists():
        return rendered_path.read_text(encoding="utf-8")
    return ""


def run_sdk_agents(
    repo_root: Path,
    files: list[str],
    *,
    depth: str = "quick",
    verbose: bool = False,
    timeout: int = 600,
) -> dict[str, Any]:
    """Run SDK agent review on implementation files."""
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
        """Ignore pure heartbeat rewrites; track only semantic status changes."""
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
        *files,
        "--depth", depth,
        "--fail-fast-hard-gate",
        "--no-memory",
    ]
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    stdout_path = scratch_dir / f"phase_b_agent_review_{run_id}.stdout.log"
    stderr_path = scratch_dir / f"phase_b_agent_review_{run_id}.stderr.log"
    status_path = scratch_dir / f"phase_b_agent_review_{run_id}.status.json"
    report_path = scratch_dir / f"phase_b_agent_review_{run_id}.report.md"
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
                    "[phase-b] SDK heartbeat: "
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
                status_detail = ""
                if status_snapshot:
                    status_detail = (
                        f"\nstatus_phase={status_snapshot.get('phase_label', '')} "
                        f"running_agents={status_snapshot.get('running_agents', [])} "
                        f"last_progress={status_snapshot.get('last_progress_timestamp', '')}"
                    )
                return {
                    "exit_code": -3,
                    "stdout": stdout_text,
                    "stderr": (
                        "aggregation_hang: reviewer children exited but aggregator "
                        f"remained alive for {int(idle_for)}s"
                        + status_detail
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


def _select_sdk_review_files(files: list[str]) -> list[str]:
    """Prefer tool/runtime implementation files for the one-time SDK gate.

    Test files stay mechanically validated in the wave, but they should not
    consume the limited one-time SDK hard-gate budget unless no tool/runtime
    surfaces remain.
    """
    implementation = [
        f for f in files
        if f.startswith(("mu/tools/", "tools/"))
        or f in {"CLAUDE.md", "TASKS.md", "STATUS.md", "CHANGELOG.md"}
    ]
    return implementation


def _total_bridge_rounds(repo_root: Path) -> int:
    """Count total completed Phase B bridge rounds from bridge.db."""
    db_path = repo_root / ".agent_bus" / "bridge.db"
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(str(db_path), timeout=5)
        row = conn.execute(
            "SELECT COUNT(*) FROM jobs WHERE job_id LIKE 'phase-b-%' AND status = 'DONE'"
        ).fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception:
        return 0


def _collect_changed_files(
    repo_root: Path,
    allowed_files: set[str] | None = None,
) -> list[str]:
    """Collect changed files (staged + unstaged + untracked) from git.

    When *allowed_files* is provided, only files in that set are returned.
    This prevents sweeping unrelated dirty-worktree files into the wave.
    """
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
    if allowed_files is not None:
        changed = [f for f in changed if f in allowed_files]
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


_DECLARED_PATH_EXTENSIONS = (".py", ".json", ".md", ".txt", ".sh")
_DECLARED_ROOT_FILES = {"CLAUDE.md", "TASKS.md", "STATUS.md", "CHANGELOG.md"}
_LINE_REF_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::(?P<col>\d+))?$")
_INLINE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+|(?:CLAUDE|TASKS|STATUS|CHANGELOG)\.md)(?![A-Za-z0-9_./-])")


def _normalize_declared_path_token(token: str) -> str | None:
    """Normalize markdown-ish path tokens from plan packets into repo-relative paths."""
    candidate = token.strip().strip("`'\"*()[]{}<>")
    candidate = candidate.rstrip(",;:.")
    if not candidate:
        return None
    if candidate.startswith("./"):
        candidate = candidate.removeprefix("./")
    line_ref = _LINE_REF_RE.match(candidate)
    if line_ref:
        candidate = line_ref.group("path")
    if not candidate or any(part == ".." for part in Path(candidate).parts):
        return None
    if candidate.startswith("/"):
        return None
    if candidate in _DECLARED_ROOT_FILES:
        return candidate
    if "/" not in candidate:
        return candidate if candidate.endswith(_DECLARED_PATH_EXTENSIONS) else None
    if candidate.endswith(_DECLARED_PATH_EXTENSIONS):
        return candidate
    return None


def _parse_plan_declared_files(plan_content: str) -> list[str]:
    """Extract repo-relative file paths from a locked plan packet."""
    seen: set[str] = set()
    parsed: list[str] = []

    def _add(token: str) -> None:
        normalized = _normalize_declared_path_token(token)
        if normalized and normalized not in seen:
            seen.add(normalized)
            parsed.append(normalized)

    for line in plan_content.splitlines():
        for token in re.findall(r"`([^`\n]+)`", line):
            _add(token)
        stripped = line.strip()
        if stripped.startswith("- "):
            bullet_body = stripped[2:].strip()
            if bullet_body:
                _add(bullet_body.split()[0])
        for token in _INLINE_PATH_RE.findall(line):
            _add(token)

    return parsed


def _parse_fenced_out_files(plan_content: str) -> list[str]:
    """Extract repo-relative files explicitly marked as fenced out in the packet."""
    seen: set[str] = set()
    parsed: list[str] = []

    for line in plan_content.splitlines():
        if "fenced out" not in line.lower():
            continue
        for token in re.findall(r"`([^`\n]+)`", line):
            normalized = _normalize_declared_path_token(token)
            if normalized and normalized not in seen:
                seen.add(normalized)
                parsed.append(normalized)

    return parsed


def _collect_baseline_wave_files(repo_root: Path, plan_path: str) -> list[str]:
    """Capture the preserved dirty-wave baseline before implementer deltas are applied.

    This preserves the caller-approved dirty wave on runs that intentionally start
    from an already-dirty control-plane lane. Later implementer/executor deltas
    are unioned on top of this baseline.
    """
    all_changed = _collect_changed_files(repo_root)
    plan_prefix = plan_path.rsplit("/", 1)[0] + "/" if "/" in plan_path else ""
    baseline: list[str] = []
    for f in all_changed:
        if any(f.startswith(p) or f == p for p in _WAVE_OWNED_PREFIXES):
            baseline.append(f)
        elif plan_prefix and f.startswith(plan_prefix):
            baseline.append(f)
    return sorted(set(baseline))


def _collect_wave_owned_files(
    repo_root: Path,
    plan_path: str,
    plan_declared_files: list[str] | None = None,
    implementer_changed_files: set[str] | None = None,
    executor_created_files: set[str] | None = None,
    baseline_wave_files: set[str] | None = None,
) -> list[str]:
    """Collect changed files scoped to plan-declared + implementer-tracked set only.

    Only stages files that are BOTH dirty in git AND either:
      1. Declared in the plan (plan_declared_files), OR
      2. Actually changed by the implementer (implementer_changed_files), OR
      3. Created by the executor itself (executor_created_files — e.g. deferred packets), OR
      4. Part of the preserved dirty-wave baseline (baseline_wave_files), OR
      5. Under the plan's directory prefix.

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
        allowed |= (baseline_wave_files or set())
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
        elif baseline_wave_files and f in baseline_wave_files:
            scoped.append(f)
    return sorted(scoped)


def _resolve_review_depth(config: dict[str, Any], phase_key: str, default: str = "quick") -> str:
    """Resolve review depth from executor config and fail closed on invalid values."""
    depth = config.get("review_depths", {}).get(phase_key, default)
    if depth not in ALLOWED_REVIEW_DEPTHS:
        raise PhaseBExecutorError(
            f"Invalid review depth {depth!r} for {phase_key}; "
            f"expected one of {sorted(ALLOWED_REVIEW_DEPTHS)}"
        )
    return depth


def _stage_files(repo_root: Path, files: list[str]) -> bool:
    """Stage files for commit. Returns True on success.

    Files under .claude/ are staged individually to avoid the git multi-path
    pathspec resolver false-positive: batch ``git add`` with .claude/ paths
    alongside other top-level paths triggers "ignored by .gitignore" on the
    .claude parent directory even for tracked files under negation-rule
    subdirectories (.claude/hooks/).  Single-path adds work correctly.
    See .claude/rules/learning.md 2026-04-11 entry (git add multi-path).
    """
    if not files:
        return False
    claude_files = [f for f in files if f.startswith(".claude/") or f.startswith(".claude\\")]
    other_files = [f for f in files if f not in claude_files]
    try:
        if other_files:
            subprocess.run(
                ["git", "add", "--", *other_files],
                cwd=repo_root, capture_output=True, text=True, check=True,
            )
        for cf in claude_files:
            subprocess.run(
                ["git", "add", "--", cf],
                cwd=repo_root, capture_output=True, text=True, check=True,
            )
        return True
    except subprocess.CalledProcessError:
        # Fail closed. Phase B must not bypass ignore rules by force-adding
        # files the repo has explicitly excluded from normal staging.
        return False


def _agent_review_scope_fingerprint(repo_root: Path, files: list[str], *, depth: str) -> str:
    """Fingerprint the exact SDK review scope for safe resume."""
    digest = hashlib.sha256()
    digest.update(depth.encode("utf-8"))
    for rel_path in sorted(files):
        digest.update(b"\0path\0")
        digest.update(rel_path.encode("utf-8", errors="surrogatepass"))
        full_path = repo_root / rel_path
        if not full_path.exists():
            digest.update(b"\0missing")
            continue
        digest.update(b"\0present\0")
        digest.update(full_path.read_bytes())
    return digest.hexdigest()


def _bridge_scope_fingerprint(repo_root: Path, files: list[str]) -> str:
    """Fingerprint the exact bridge-reviewed scope for safe resume."""
    digest = hashlib.sha256()
    for rel_path in sorted(files):
        digest.update(b"\0path\0")
        digest.update(rel_path.encode("utf-8", errors="surrogatepass"))
        full_path = repo_root / rel_path
        if not full_path.exists():
            digest.update(b"\0missing")
            continue
        digest.update(b"\0present\0")
        digest.update(full_path.read_bytes())
    return digest.hexdigest()


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
                "request_for_claude": result.request_for_claude,
                "error_code": result.error_code,
                "error_detail": result.error_detail,
            },
            "receipt_path": result.receipt_path,
        }
    except MetaBridgeClientError as exc:
        return {
            "exit_code": -1,
            "parsed": {
                "decision": "ERROR_INTERNAL",
                "status": "error",
                "summary": "Pre-commit supervisor client error",
                "findings": [],
                "error_detail": str(exc)[:2000],
            },
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
    supervisor_lane: str | None = None,
    deferred_items: list[str] | None = None,
    bridge_status: dict[str, Any] | None = None,
    scope_items: list[str] | None = None,
    evidence_handles: dict[str, str] | None = None,
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
    if supervisor_lane is not None:
        handoff["supervisor_lane"] = supervisor_lane
    if deferred_items is not None:
        handoff["deferred_items"] = deferred_items
    if bridge_status is not None:
        handoff["bridge_status"] = bridge_status
    if scope_items is not None:
        handoff["scope_items"] = scope_items
    if evidence_handles is not None:
        handoff["evidence_handles"] = evidence_handles

    handoff_dir = repo_root / ".agent_bus" / "executors"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    handoff_path = handoff_dir / "phase_b_handoff.json"
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return handoff_path


def _build_phase_b_tracker_note(
    *,
    wave_id: str,
    task_id: str,
    wave_class: str = "L4_ENABLER",
    target_gate_id: str,
    plan_path: str,
    changed_files: list[str],
    test_files: list[str],
    receipt_path: str,
    bridge_rounds: int,
    reentry: bool,
) -> str:
    """Render an L4-compliant tracker note for a Phase B commit handoff."""
    # Phase B produces implementation work — MAINTENANCE requires no_op_proof/defer_reason_code
    # which are not available here. Guard to L4_ENABLER if routing says MAINTENANCE.
    if wave_class == "MAINTENANCE":
        wave_class = "L4_ENABLER"
    display_task = (task_id or "").strip() or wave_id
    if display_task.startswith("[") and display_task.endswith("]"):
        display_task = display_task[1:-1]
    if not display_task:
        display_task = wave_id

    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    if test_files:
        evidence_command = "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short " + " ".join(test_files)
        evidence_delta = (
            f"(1) Phase B converged on the locked plan at {plan_path}. "
            f"(2) Final pytest gate covered {len(test_files)} test file(s) from the wave-owned diff. "
            f"(3) Commit handoff carries explicit receipt authority at {receipt_path}."
        )
    else:
        evidence_command = (
            f"python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
            f"--output {indicator_path}"
        )
        evidence_delta = (
            f"(1) Phase B converged on the locked plan at {plan_path}. "
            f"(2) Commit handoff carries {len(changed_files)} wave-owned file(s) with explicit receipt "
            f"authority at {receipt_path}. "
            "(3) No test files were present in the wave-owned diff, so indicator collection is the "
            "mechanical evidence surface."
        )

    progress_before = (
        "Phase B had not yet emitted a commit-ready handoff with a canonical tracker note, "
        "so downstream governance could not bind the wave cleanly to its indicator artifact."
    )
    progress_after = (
        f"Phase B emitted a commit-ready handoff for {wave_id} with {len(changed_files)} wave-owned "
        f"file(s), bridge rounds={bridge_rounds}"
    )
    if reentry:
        progress_after += ", reentry=true"
    progress_after += ", explicit receipt authority, and an L4-compliant tracker note."

    fields = TrackerSyncNoteFields(
        wave_id=wave_id,
        title=f"{display_task} — commit-ready Phase B handoff",
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        evidence_command=evidence_command,
        evidence_delta=evidence_delta,
        progress_proof_before=progress_before,
        progress_proof_after=progress_after,
        primary_blocker_class="INTEGRATION",
        primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
        indicator_artifact_ref=indicator_path,
        indicator_collection_command=(
            f"python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
            f"--output {indicator_path}"
        ),
    )
    return render_tracker_sync_note(fields)


def _derive_planless_context(
    routing_record: dict[str, Any],
    repo_root: Path,
) -> dict[str, str]:
    """Derive a bounded implementation context from a routing record.

    Used when Phase B is invoked without --plan. The routing record must
    contain enough information to bound the scope:
    - wave_name or wave_id (task identity)
    - summary (what to implement)
    - next_candidates with at least one candidate (bounded scope)

    Returns a synthetic plan dict compatible with the plan loading path.
    Raises PhaseBExecutorError if the routing record is under-specified.
    """
    wave_id = routing_record.get("wave_name") or routing_record.get("wave_id", "")
    summary = routing_record.get("summary", "")
    request = routing_record.get("request_for_claude", "")
    candidates = routing_record.get("next_candidates", [])

    errors: list[str] = []
    if not wave_id:
        errors.append("Routing record missing wave_name/wave_id — cannot derive task identity")
    if not summary:
        errors.append("Routing record missing summary — cannot derive implementation scope")
    if not candidates:
        errors.append("Routing record missing next_candidates — scope is unbounded")

    if errors:
        raise PhaseBExecutorError(
            f"Cannot derive planless Phase B context: {'; '.join(errors)}. "
            f"Either provide --plan or enrich the routing record."
        )

    # Check for a tracked_packet in candidates — if one exists, the caller
    # should have used --plan instead.
    for c in candidates:
        tp = c.get("tracked_packet")
        if tp and (repo_root / tp).exists():
            raise PhaseBExecutorError(
                f"Routing record references tracked packet '{tp}' which exists. "
                f"Use --plan {tp} instead of planless mode."
            )

    # Build a synthetic plan content from routing record scope
    candidate_text = "\n".join(
        f"- {c.get('candidate', 'unknown')}" for c in candidates
    )
    content = (
        f"# Planless Phase B: {wave_id}\n\n"
        f"Date: derived-from-routing-record\n"
        f"Status: Phase B (planless — authority from routing record)\n"
        f"Phase-A-Lock: ROUTING_RECORD_AUTHORITY\n\n"
        f"## Summary\n\n{summary}\n\n"
        f"## Request\n\n{request or '(none)'}\n\n"
        f"## Candidates\n\n{candidate_text}\n"
    )

    return {
        "path": f"<planless:{wave_id}>",
        "content": content,
        "phase_a_lock": "ROUTING_RECORD_AUTHORITY",
        "status": "Phase B (planless)",
        "planless": "true",
        "wave_id": wave_id,
    }


def run_phase_b(
    repo_root: Path,
    plan_path: str | None = None,
    *,
    max_bridge_rounds: int = 10,
    verbose: bool = False,
    force: bool = False,
    routing_record_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute the Phase B loop.

    This is the main entry point. It orchestrates:
    1. Plan loading + validation (or planless derivation from routing record)
    2. Invoke implementer agent (separate code-writing actor via bridge adapter)
    3. SDK agent review (once) — FAIL CLOSED on nonzero exit
    4. Bridge convergence loop — bound to exact job_id, not newest file
    5. Stage the final file set BEFORE supervisor
    6. Run pre-commit supervisor (receipt minted against actual staged state)
    7. On COMMIT_GO: prepare handoff with explicit receipt path
    8. On NEEDS_PHASE_B: re-enter bridge loop (not agents)

    If plan_path is None, derives bounded context from routing record.
    Fails closed on ambiguous or under-specified routing records.

    Returns a result dict with status and details.
    """
    try:
        ensure_not_agent_review_mode("phase_b_executor.run_phase_b")
    except ExecutorCommonError as exc:
        return {
            "status": "error",
            "step": "review_mode_guard",
            "errors": [str(exc)],
        }

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
    if saved_state:
        saved_plan = saved_state.get("plan_path")
        # For planless invocations (plan_path is None on entry), the saved
        # state stores the derived "<planless:wave_id>" path.  Match if the
        # saved path is a planless marker — the actual plan_path will be set
        # after _derive_planless_context runs, so we match on the marker
        # prefix here instead of requiring an exact None == None comparison.
        plan_matches = (
            saved_plan == plan_path  # explicit --plan case
            or (plan_path is None and isinstance(saved_plan, str)
                and saved_plan.startswith("<planless:"))
        )
        if plan_matches:
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
        # _merge_task_id sentinel: load normal routing record, then merge task_id
        merge_task_id = None
        if isinstance(routing_record_override, dict) and "_merge_task_id" in routing_record_override:
            merge_task_id = routing_record_override.pop("_merge_task_id")
            routing_record_override = None  # don't replace, just merge
        if routing_record_override is not None:
            if not isinstance(routing_record_override, dict):
                raise PhaseBExecutorError("routing_record_override must be a JSON object")
            routing_record = routing_record_override
        else:
            routing_record = load_routing_record(repo_root)
        if merge_task_id:
            routing_record["task_id"] = merge_task_id
        if routing_record.get("decision") != "ROUTE_PHASE_B":
            if force:
                log(f"BOOTSTRAP_PHASE_B_EXCEPTION: Routing says {routing_record.get('decision')}, "
                    f"overriding to ROUTE_PHASE_B for bootstrap exception invocation")
                routing_record["decision"] = "ROUTE_PHASE_B"
                # Inject task_id from override if routing record lacks it
                if routing_record_override and routing_record_override.get("task_id") and not routing_record.get("task_id"):
                    routing_record["task_id"] = routing_record_override["task_id"]
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
            # Preserve task_id from override if provided (e.g., via --task-id CLI)
            if routing_record_override and routing_record_override.get("task_id"):
                routing_record["task_id"] = routing_record_override["task_id"]
            result["bootstrap_exception"] = True
        else:
            return {"status": "error", "step": "load_routing_record",
                    "errors": [f"Routing record load failed: {exc}. Use --bootstrap-exception to override."]}

    # Plan loading: either from --plan path or derived from routing record
    if plan_path:
        try:
            plan = load_plan_packet(repo_root, plan_path)
        except PhaseBExecutorError as exc:
            return {"status": "error", "step": "load_plan", "errors": [str(exc)]}
        log(f"Plan loaded: {plan_path}")
    else:
        # Planless mode: derive bounded context from routing record
        try:
            plan = _derive_planless_context(routing_record, repo_root)
            plan_path = plan["path"]
            result["plan_path"] = plan_path
            result["planless"] = True
            log(f"Planless mode: derived context from routing record (wave={plan.get('wave_id', '?')})")
        except PhaseBExecutorError as exc:
            return {"status": "error", "step": "derive_planless_context", "errors": [str(exc)]}

    log(f"Phase-A-Lock: {plan.get('phase_a_lock', 'unknown')}")

    try:
        validate_inputs(routing_record, plan)
    except PhaseBExecutorError as exc:
        if force:
            log(f"BOOTSTRAP_PHASE_B_EXCEPTION: Validation errors overridden: {exc}")
            result["bootstrap_exception"] = True
        else:
            return {"status": "error", "step": "validate_inputs", "errors": [str(exc)]}

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
    backend = config.get("backends", {}).get(
        "phase_b_executor",
        DEFAULT_EXECUTOR_CONFIG["backends"]["phase_b_executor"],
    )
    model = config.get("model_overrides", {}).get("phase_b_executor")
    timeout = config.get("timeouts", {}).get("phase_b_executor", 1200)
    pytest_gate_timeout = _resolve_pytest_gate_timeout(timeout)

    # Extract wave governance fields from routing record (not hardcoded)
    wave_class = routing_record.get("wave_class", "L4_ENABLER")
    target_gate_id = routing_record.get("target_gate_id", "G8")

    # Parse plan-declared files from markdown/body content.
    fenced_out_files = set(_parse_fenced_out_files(plan.get("content", "")))
    plan_declared_files: list[str] | None = None
    _parsed = [
        path for path in _parse_plan_declared_files(plan.get("content", ""))
        if path not in fenced_out_files
    ]
    # Only activate strict tracking when the plan actually declares files.
    # An empty parse means "plan has no file list" → use prefix fallback.
    if _parsed:
        plan_declared_files = _parsed
    if fenced_out_files:
        log(
            f"Checkout-state fence excludes {len(fenced_out_files)} file(s) "
            "from this wave-owned scope"
        )

    # Track implementer-changed files: snapshot before, diff after
    implementer_changed: set[str] = set()
    # Track files created by the executor itself (e.g. deferred packets)
    executor_created: set[str] = set()
    # Preserve the dirty-wave baseline so resumed packaging does not collapse to
    # only the latest implementer delta.
    baseline_wave_files: set[str] = set()
    # Track accumulated non-blocking findings across rounds (for deferred packet freshness)
    all_non_blocking: list[dict[str, Any]] = []
    # Track repeat-finding counts across bridge rounds (key → consecutive blocking count)
    finding_history: dict[str, int] = {}

    # Restore wave-owned file tracking from persisted state (R7-1: crash-resume)
    if saved_state and resume_after:
        if saved_state.get("implementer_changed"):
            implementer_changed = set(saved_state["implementer_changed"]) - fenced_out_files
        if saved_state.get("executor_created"):
            executor_created = set(saved_state["executor_created"]) - fenced_out_files
        if saved_state.get("baseline_wave_files"):
            baseline_wave_files = set(saved_state["baseline_wave_files"]) - fenced_out_files
        if saved_state.get("all_non_blocking"):
            all_non_blocking = list(saved_state["all_non_blocking"])
        if saved_state.get("finding_history"):
            finding_history = dict(saved_state["finding_history"])
    # Merge persisted dirty-wave scope with the current repo dirty baseline so
    # late follow-up fixes made after a saved checkpoint are not silently dropped
    # from supervisor packaging on resume.
    baseline_wave_files |= (set(_collect_baseline_wave_files(repo_root, plan_path)) - fenced_out_files)

    # Determine which steps to skip based on resume state
    _RESUME_ORDER = ["implementer", "agent_review", "bridge_converged", "needs_phase_b_reentry"]
    _skip_to_reentry = resume_after == "needs_phase_b_reentry"
    _skip_through_bridge = (
        resume_after.startswith("bridge_round_") or resume_after == "bridge_converged"
        or _skip_to_reentry
    )
    _skip_through_implementer = resume_after in {"implementer", "agent_review"} or _skip_through_bridge

    # Step 2.5: Ensure we're on the feature branch (not dev)
    raw_wave_id = plan.get("wave_id") or plan_path.replace("reports/control_plane/", "").replace(".md", "")
    wave_id = normalize_wave_id(raw_wave_id)
    _branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=str(repo_root), capture_output=True, text=True,
    )
    if _branch_result.returncode == 0:
        current_branch = _branch_result.stdout.strip()
        feature_branch = f"jabramsja/{wave_id}"
        if current_branch in ("dev", "main", "master") and current_branch != feature_branch:
            # Check if feature branch already exists
            branch_exists = subprocess.run(
                ["git", "rev-parse", "--verify", f"refs/heads/{feature_branch}"],
                cwd=str(repo_root), capture_output=True, text=True,
            ).returncode == 0
            try:
                # Stash any dirty working-tree files (e.g. reviewer config swaps)
                # so branch checkout doesn't fail on conflicts. Pop after checkout.
                stash_result = subprocess.run(
                    ["git", "stash", "--include-untracked"],
                    cwd=str(repo_root), capture_output=True, text=True,
                )
                stashed = stash_result.returncode == 0 and "No local changes" not in stash_result.stdout
                if branch_exists:
                    log(f"Step 2.5: Checking out existing feature branch {feature_branch}")
                    subprocess.run(
                        ["git", "checkout", feature_branch],
                        cwd=str(repo_root), check=True, capture_output=True,
                    )
                else:
                    log(f"Step 2.5: Creating feature branch {feature_branch}")
                    subprocess.run(
                        ["git", "checkout", "-b", feature_branch],
                        cwd=str(repo_root), check=True, capture_output=True,
                    )
                result["feature_branch"] = feature_branch
                if stashed:
                    subprocess.run(
                        ["git", "stash", "pop"],
                        cwd=str(repo_root), capture_output=True,
                    )
            except subprocess.CalledProcessError as exc:
                # Restore stash on failure
                if stashed:
                    subprocess.run(
                        ["git", "stash", "pop"],
                        cwd=str(repo_root), capture_output=True,
                    )
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"Branch checkout failed (fail-closed): {exc}. "
                                   f"Cannot invoke implementer on protected branch '{current_branch}'."]}
        else:
            log(f"Step 2.5: Already on {current_branch} (OK)")
    else:
        log("Step 2.5: Not a git repo — skipping branch checkout")

    # Step 3: Invoke implementer agent
    if _skip_through_implementer:
        log(f"Step 3: SKIPPED (resume_after={resume_after})")
        result["implementer_invoked"] = True
        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
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
            result.update({
                "status": "error",
                "step": "implementer",
                "errors": [
                    f"Implementer failed: {impl_result['status']} "
                    f"(exit={impl_result['exit_code']}): {impl_result.get('stderr', '')[:500]}"
                ],
                "implementer_invoked": True,
                "implementer_status": impl_result["status"],
            })
            return result

        # Collect changed files after implementer ran — track what implementer actually changed
        post_impl_files = set(_collect_changed_files(repo_root))
        implementer_changed = (post_impl_files - pre_impl_files) - fenced_out_files
        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
        log(f"Changed files after implementer: {len(changed_files)} (implementer touched {len(implementer_changed)})")

        # Persist state after implementer
        _save_state(repo_root, {
            "plan_path": plan_path,
            "completed_step": "implementer",
            "wave_id": wave_id,
            "bridge_rounds": 0,
            "implementer_changed": sorted(implementer_changed),
            "executor_created": sorted(executor_created),
            "baseline_wave_files": sorted(baseline_wave_files),
            "all_non_blocking": all_non_blocking,
            "finding_history": finding_history,
        })

    bridge_scope_fingerprint = _bridge_scope_fingerprint(repo_root, changed_files)
    if (
        saved_state is not None
        and not _skip_to_reentry
        and (
            resume_after == "bridge_converged"
            or resume_after.startswith("bridge_round_")
        )
    ):
        saved_bridge_scope_fingerprint = saved_state.get("bridge_scope_fingerprint")
        if saved_bridge_scope_fingerprint != bridge_scope_fingerprint:
            log(
                "Saved bridge checkpoint drifted or lacked scope fingerprint; "
                "re-running SDK review and bridge"
            )
            _skip_through_bridge = False
        else:
            log(
                f"Bridge checkpoint scope fingerprint matched "
                f"(resume_after={resume_after})"
            )

    # Step 4: Run SDK agents ONCE on live worktree changed files
    # FAIL CLOSED on nonzero exit (hard gate agents must pass)
    if _skip_through_bridge:
        log(f"Step 4: SKIPPED (resume_after={resume_after})")
        result["agent_review_ran"] = True
    elif not config.get("agent_review_enabled", True):
        log("Step 4: SDK agent review DISABLED via executor_config.json (agent_review_enabled=false)")
        result["agent_exit_code"] = 0
        result["agent_review_ran"] = False
        result["agent_review_warning_only"] = False
    else:
        review_depth = _resolve_review_depth(config, "phase_b")
        log(f"Running SDK agent review on changed files (depth={review_depth})...")
        agent_files = _select_sdk_review_files(changed_files) if changed_files else ["--pr"]
        if changed_files and not agent_files:
            log(
                "Skipping SDK agent review: no implementation files remain in the wave-owned "
                "changed set; report/doc residue will proceed to bridge without a second hard gate",
            )
            result["agent_review_skipped_reason"] = "no_implementation_files"
            result["agent_review_scope"] = []
        else:
            agent_scope_fingerprint = _agent_review_scope_fingerprint(
                repo_root,
                agent_files,
                depth=review_depth,
            )
            can_resume_agent_review = (
                resume_after == "agent_review"
                and saved_state is not None
                and saved_state.get("agent_review_scope_fingerprint") == agent_scope_fingerprint
                and saved_state.get("agent_exit_code", -1) >= 0
                and bool(saved_state.get("agent_review_report_path"))
                and bool(saved_state.get("agent_review_status_path"))
            )
            if changed_files and agent_files != changed_files:
                log(
                    f"SDK review scope narrowed to {len(agent_files)} implementation file(s) "
                    f"(excluded {len(changed_files) - len(agent_files)} report artifact(s))",
                )
            result["agent_review_ran"] = True
            result["agent_review_scope"] = agent_files
            if can_resume_agent_review:
                result["agent_exit_code"] = int(saved_state["agent_exit_code"])
                result["agent_review_report_path"] = saved_state.get("agent_review_report_path")
                result["agent_review_status_path"] = saved_state.get("agent_review_status_path")
                result["agent_review_stdout_path"] = saved_state.get("agent_review_stdout_path")
                log("Step 4: SKIPPED (resume_after=agent_review, scope fingerprint matched)")
                log(f"Agent review exit code: {result['agent_exit_code']} (resumed)")
            else:
                if resume_after == "agent_review":
                    log(
                        "Saved agent review checkpoint drifted or was incomplete; "
                        "re-running SDK agent review"
                    )
                agent_timeout = config.get("timeouts", {}).get("agent_review", 1500)
                agent_result = run_sdk_agents(
                    repo_root,
                    agent_files,
                    depth=review_depth,
                    verbose=verbose,
                    timeout=agent_timeout,
                )
                result["agent_exit_code"] = agent_result["exit_code"]
                result["agent_review_report_path"] = agent_result.get("report_path")
                result["agent_review_status_path"] = agent_result.get("status_path")
                result["agent_review_stdout_path"] = agent_result.get("stdout_path")
                log(f"Agent review exit code: {agent_result['exit_code']}")

                if agent_result["exit_code"] < 0:
                    # Negative exits (-1 timeout, -2 stale, -3 aggregation-hang)
                    # mean the agent review NEVER COMPLETED — no findings to forward.
                    # Fail closed: re-running is safer than proceeding blind.
                    return {
                        "status": "error",
                        "step": "agent_review",
                        "errors": [
                            f"SDK agent review infrastructure failure (exit={agent_result['exit_code']}). "
                            "Review did not complete. "
                            f"stderr: {agent_result.get('stderr', '')[:500]}"
                        ],
                        "agent_review_ran": True,
                        "agent_exit_code": agent_result["exit_code"],
                    }
                if agent_result["exit_code"] not in (0, 1, 2):
                    # exit=3 (hard gate) means agents RAN and produced findings.
                    # Treat as WARNING — findings forwarded to bridge/implementer
                    # loop for contextual triage.  Agents run once; the bridge
                    # review is the real convergence gate.
                    log(
                        f"Agent review exit={agent_result['exit_code']}; "
                        "treating as warning (findings forwarded to bridge review)"
                    )

                _save_state(repo_root, {
                    "plan_path": plan_path,
                    "completed_step": "agent_review",
                    "wave_id": wave_id,
                    "bridge_rounds": 0,
                    "implementer_changed": sorted(implementer_changed),
                    "executor_created": sorted(executor_created),
                    "baseline_wave_files": sorted(baseline_wave_files),
                    "all_non_blocking": all_non_blocking,
                    "finding_history": finding_history,
                    "agent_review_scope": agent_files,
                    "agent_review_scope_fingerprint": agent_scope_fingerprint,
                    "agent_exit_code": agent_result["exit_code"],
                    "agent_review_report_path": agent_result.get("report_path"),
                    "agent_review_status_path": agent_result.get("status_path"),
                    "agent_review_stdout_path": agent_result.get("stdout_path"),
                })

            if result["agent_exit_code"] != 0:
                if result["agent_exit_code"] == 1:
                    log(
                        "Agent review returned semantic blocker findings exit=1; "
                        "continuing to bridge for contextual blocking/non-blocking classification"
                    )
                elif result["agent_exit_code"] == 2:
                    log("Agent review returned warnings-only exit=2; continuing to bridge review")
                else:
                    log(
                        f"Agent review exit={result['agent_exit_code']}; "
                        "findings forwarded as warnings to bridge review"
                    )
                result["agent_review_warning_only"] = True

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

        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
        if changed_files:
            log(f"Staging {len(changed_files)} wave-owned files before bridge review...")
            if not _stage_files(repo_root, changed_files):
                result["status"] = "error"
                result["step"] = "bridge_staging"
                result["errors"] = ["Failed to stage files before bridge review"]
                _clear_state(repo_root)
                return result

        # Build task summary — include deferred packet path if we have one
        task_summary = f"Phase B implementation review R{round_num} for {plan_path}"
        if deferred_packet_path:
            task_summary += f"\n\nAcknowledged deferred non-blocking findings: {deferred_packet_path}"
        if result.get("agent_review_report_path"):
            task_summary += (
                "\n\nOne-time Phase B SDK review artifacts:"
                f"\n- exit_code: {result.get('agent_exit_code')}"
                f"\n- report: {result.get('agent_review_report_path')}"
                f"\n- status: {result.get('agent_review_status_path')}"
                f"\n- stdout: {result.get('agent_review_stdout_path')}"
                "\nBridge must treat SDK findings as review inputs for contextual "
                "blocking/non-blocking classification. Semantic SDK negatives are "
                "not automatic current-step blockers by themselves."
            )

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

        # Bridge supervision failures are hard errors — do not silently retry
        if bridge_result["exit_code"] in (-1, -2, -3):
            failure_label = {
                -1: "timed out",
                -2: "stale",
                -3: "aggregation hang",
            }[bridge_result["exit_code"]]
            result["status"] = "error"
            result["errors"] = [
                f"Bridge review {failure_label} in round {round_num}. "
                f"{bridge_result.get('stderr', '')}"
            ]
            _clear_state(repo_root)
            return result

        if bridge_result["exit_code"] == 0 and bridge_decision == "GO":
            render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
            parsed_findings = _parse_findings_from_render(render, raw_texts) if (render or raw_texts) else []
            blocking_findings, non_blocking_findings = _classify_findings(parsed_findings, finding_history)
            if blocking_findings:
                result["status"] = "error"
                result["step"] = "bridge_decision"
                result["errors"] = [
                    f"Bridge returned GO in round {round_num} but rendered transcript still contains "
                    f"{len(blocking_findings)} blocking finding(s). Fail closed."
                ]
                _clear_state(repo_root)
                return result
            if non_blocking_findings:
                all_non_blocking, packet_path = _record_non_blocking_findings(
                    repo_root, wave_id, all_non_blocking, non_blocking_findings,
                    wave_class=wave_class, target_gate_id=target_gate_id,
                )
                if packet_path is not None:
                    deferred_packet_path = str(packet_path.relative_to(repo_root))
                    executor_created.add(deferred_packet_path)
                    result["deferred_packet_path"] = deferred_packet_path
                    log(f"Filed {len(non_blocking_findings)} non-blocking finding(s) from GO to {deferred_packet_path}")
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

        if bridge_result["exit_code"] == 0 and bridge_decision not in RECOGNIZED_BRIDGE_DECISIONS:
            result["status"] = "error"
            result["step"] = "bridge_decision"
            result["errors"] = [
                f"Bridge returned unrecognized success decision in round {round_num}: "
                f"{bridge_decision!r}. Fail closed."
            ]
            _clear_state(repo_root)
            return result

        if bridge_decision in ("REQUEST_CHANGES", "NO_GO"):
            # bridge_supervisor.py review returns exit=1 for non-GO decisions.
            # Treat REQUEST_CHANGES/NO_GO as recoverable review outcomes when
            # the exit code matches that CLI contract; only unexpected codes
            # are infrastructure failures here.
            if bridge_result["exit_code"] not in (0, 1):
                log(f"Bridge subprocess failed (exit={bridge_result['exit_code']}) "
                    f"with decision {bridge_decision!r} — fail closed (not recoverable)")
                result["status"] = "error"
                result["step"] = "bridge_subprocess"
                result["errors"] = [
                    f"Bridge subprocess failed in round {round_num} "
                    f"(exit={bridge_result['exit_code']}, decision={bridge_decision}). "
                    f"Unexpected exit with {bridge_decision} is not recoverable. "
                    f"stderr: {bridge_result.get('stderr', '')[:500]}"
                ]
                _clear_state(repo_root)
                return result

            # Read findings from the exact bridge render for this job
            render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
            findings_text = render if render else bridge_result.get("stdout", "")

            # Parse and classify findings by disposition
            parsed_findings = _parse_findings_from_render(render, raw_texts) if (render or raw_texts) else []
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
                all_non_blocking, packet_path = _record_non_blocking_findings(
                    repo_root, wave_id, all_non_blocking, non_blocking_findings,
                    wave_class=wave_class, target_gate_id=target_gate_id,
                )
                if packet_path is not None:
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

            # Track what the fix round changed. The local pytest pass should only
            # exercise tests introduced or edited by this fix round, not every
            # pre-existing test file already present in the broader replay scope.
            post_fix_files = set(_collect_changed_files(repo_root))
            current_fix_changed = sorted(post_fix_files - pre_fix_files)
            implementer_changed |= set(current_fix_changed)
            # Recollect changed files after implementer fix (scoped to wave outputs)
            changed_files = _collect_wave_owned_files(
                repo_root,
                plan_path,
                plan_declared_files,
                implementer_changed or None,
                executor_created or None,
                baseline_wave_files or None,
            )
            log(
                f"Changed files after bridge fix: {len(changed_files)} "
                f"(current fix touched {len(current_fix_changed)})"
            )

            # Run pytest only on test files changed by this bridge-fix pass.
            test_files = [
                f for f in current_fix_changed
                if f.startswith("mu/tests/") or "/test_" in f or f.endswith("_test.py")
            ]
            if test_files:
                log(f"Running pytest on {len(test_files)} newly changed test file(s)...")
                pytest_result = _run_pytest_on_files(repo_root, test_files, timeout=pytest_gate_timeout)
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
                    changed_files = _collect_wave_owned_files(
                        repo_root,
                        plan_path,
                        plan_declared_files,
                        implementer_changed or None,
                        executor_created or None,
                        baseline_wave_files or None,
                    )

            # Persist state after each bridge round
            _save_state(repo_root, {
                "plan_path": plan_path,
                "completed_step": f"bridge_round_{round_num}",
                "wave_id": wave_id,
                "bridge_rounds": round_num,
                "current_bridge_round": round_num,
                "bridge_scope_fingerprint": _bridge_scope_fingerprint(repo_root, changed_files),
                "deferred_packet_path": deferred_packet_path,
                "implementer_changed": sorted(implementer_changed),
                "executor_created": sorted(executor_created),
                "baseline_wave_files": sorted(baseline_wave_files),
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
        "bridge_scope_fingerprint": _bridge_scope_fingerprint(repo_root, changed_files),
        "deferred_packet_path": deferred_packet_path,
        "implementer_changed": sorted(implementer_changed),
        "executor_created": sorted(executor_created),
        "baseline_wave_files": sorted(baseline_wave_files),
        "all_non_blocking": all_non_blocking,
        "finding_history": finding_history,
    })

    # Resume from NEEDS_PHASE_B re-entry: skip pytest gate + staging + supervisor,
    # jump directly into the re-entry loop below.
    supervisor_parsed: dict[str, Any] = {}
    refresh_reentry_findings = False
    if _skip_to_reentry:
        log("Resuming into NEEDS_PHASE_B re-entry (skipping supervisor)")
        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
        current_scope_fingerprint = _bridge_scope_fingerprint(repo_root, changed_files)
        saved_scope_fingerprint = (saved_state or {}).get("bridge_scope_fingerprint")
        refresh_reentry_findings = saved_scope_fingerprint != current_scope_fingerprint
        if refresh_reentry_findings:
            findings_for_impl = "Refresh bridge findings from the current worktree before re-invoking the implementer."
            log("NEEDS_PHASE_B resume checkpoint drifted or lacked scope fingerprint; refreshing bridge findings first")
        else:
            findings_for_impl = (saved_state or {}).get("reentry_findings", "Fix required (resumed)")
        result["pre_commit_summary"] = findings_for_impl
        decision = "NEEDS_PHASE_B"
        # Provide stubs for variables used in re-entry block
        deferred_packet_path = result.get("deferred_packet_path")
        supervisor_result = {"parsed": {"summary": findings_for_impl}}
        supervisor_parsed = supervisor_result["parsed"]
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
        deferred_items = _collect_supervisor_deferred_items(changed_files, deferred_packet_path)
        all_dirty_reentry = _collect_changed_files(repo_root)
        fenced_reentry = [f for f in all_dirty_reentry if f not in set(changed_files)]

        supervisor_package = {
            "task_id": routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            "wave_name": wave_id,
            "lane": "hooks/agents/bridge control-surface",
            "changed_files": changed_files,
            "fenced_files": fenced_reentry,
            "scope_items": [plan_path],
            "fixes_implemented": ["Phase B implementation per locked plan (resumed from NEEDS_PHASE_B)"],
            "deferred_items": deferred_items,
            "bridge_status": {"rounds": result.get("bridge_rounds", 0), "total_rounds": _total_bridge_rounds(repo_root), "reentry": True},
            "evidence_handles": {},
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
        }
        receipt_path = ""
    else:
        decision = None  # will be set by supervisor below

    if not _skip_to_reentry:
        # Step 5b: Final pytest gate — failed tests MUST block commit_ready
        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
        final_test_files = [f for f in changed_files if f.startswith("mu/tests/") or "/test_" in f or f.endswith("_test.py")]
        if final_test_files:
            log(f"Final pytest gate: running {len(final_test_files)} test file(s)...")
            final_pytest = _run_pytest_on_files(repo_root, final_test_files, timeout=pytest_gate_timeout)
            if not final_pytest["passed"]:
                return {
                    "status": "error",
                    "step": "final_pytest_gate",
                    "errors": [
                        f"Final pytest gate FAILED (exit={final_pytest['exit_code']}). "
                        "Tests must pass before commit. "
                        + _summarize_pytest_failure(final_pytest)
                    ],
                }
            log("Final pytest gate: PASSED")

        # Step 5b: Update tracked packet status before staging.
        # Advances from "Phase A" to "Phase B (bridge-converged)" so the
        # supervisor sees consistent state (Bug 1 fix, 2026-04-06).
        # Deferred to "Phase B" (not "COMPLETED") until supervisor confirms
        # COMMIT_GO — premature COMPLETED is incorrect if supervisor rejects
        # (P2 bot finding, 2026-04-06).
        # Guard: skip for planless mode where plan_path is a synthetic token
        # (P1 bot finding, 2026-04-06).
        if not plan_path.startswith("<"):
            update_plan_packet_status(
                repo_root, plan_path,
                "Phase B (implementation-complete, bridge-converged)",
            )
            if plan_path not in changed_files:
                changed_files.append(plan_path)

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
        deferred_items = _collect_supervisor_deferred_items(changed_files, deferred_packet_path)

        # Fenced files: dirty in git but not wave-owned (from other waves)
        all_dirty = _collect_changed_files(repo_root)
        fenced = [f for f in all_dirty if f not in set(changed_files)]

        supervisor_package = {
            "task_id": routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            "wave_name": wave_id,
            "lane": "hooks/agents/bridge control-surface",
            "changed_files": changed_files,
            "fenced_files": fenced,
            "scope_items": [plan_path],
            "fixes_implemented": ["Phase B implementation per locked plan"],
            "deferred_items": deferred_items,
            "bridge_status": {"rounds": result.get("bridge_rounds", 0), "total_rounds": _total_bridge_rounds(repo_root)},
            "evidence_handles": {"indicator": f"reports/l4_wave_indicators/{wave_id}.json"},
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
        }
        package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        log("Running pre-commit supervisor...")
        supervisor_result = run_pre_commit_supervisor(
            repo_root, package_path, verbose=verbose,
        )
        supervisor_parsed = supervisor_result.get("parsed", {})
        result["pre_commit_decision"] = supervisor_parsed.get("decision")
        result["pre_commit_summary"] = _supervisor_reason_text(supervisor_parsed)
        receipt_path = supervisor_result.get("receipt_path", "")
        log(f"Supervisor decision: {result['pre_commit_decision']}, receipt: {receipt_path}")
        if result.get("pre_commit_summary"):
            log(f"Supervisor summary: {result['pre_commit_summary']}")

        decision = result["pre_commit_decision"]
    if decision == "NEEDS_PHASE_B":
        # Re-entry: implementer fixes → bridge reviews → loop
        log("NEEDS_PHASE_B — re-invoking implementer then bridge loop")
        reentry_converged = False
        # Initial findings come from supervisor; subsequent rounds use bridge findings
        findings_for_impl = result.get("pre_commit_summary") or supervisor_parsed.get("summary", "Fix required")

        # Persist needs_phase_b_reentry state so crash-resume re-enters here
        _save_state(repo_root, {
            "plan_path": plan_path,
            "completed_step": "needs_phase_b_reentry",
            "wave_id": wave_id,
            "bridge_rounds": result["bridge_rounds"],
            "bridge_scope_fingerprint": _bridge_scope_fingerprint(repo_root, changed_files),
            "deferred_packet_path": deferred_packet_path,
            "implementer_changed": sorted(implementer_changed),
            "executor_created": sorted(executor_created),
            "baseline_wave_files": sorted(baseline_wave_files),
            "all_non_blocking": all_non_blocking,
            "finding_history": finding_history,
            "reentry_findings": findings_for_impl,
        })

        for reentry_round in range(result["bridge_rounds"] + 1, max_bridge_rounds + 1):
            log(f"Re-entry round {reentry_round}/{max_bridge_rounds}...")
            result["bridge_rounds"] = reentry_round

            if refresh_reentry_findings:
                refresh_reentry_findings = False
                changed_files = _collect_wave_owned_files(
                    repo_root, plan_path, plan_declared_files,
                    implementer_changed or None, executor_created or None,
                    baseline_wave_files or None,
                )
                log("Re-entry: checkpoint drift detected; refreshing bridge findings before re-invoking implementer")
            else:
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
                    _clear_state(repo_root)
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
                    baseline_wave_files or None,
                )
                log(
                    f"Re-entry changed files: {len(changed_files)} "
                    f"(implementer touched {len(post_reentry_files - pre_reentry_files)})"
                )

            if changed_files:
                log(f"Re-entry: staging {len(changed_files)} wave-owned files before bridge review...")
                if not _stage_files(repo_root, changed_files):
                    _clear_state(repo_root)
                    return {
                        "status": "error",
                        "step": "reentry_bridge_staging",
                        "errors": ["Failed to stage files before bridge review during re-entry"],
                    }

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

            # Bridge supervision failures are hard errors in re-entry too
            if bridge_result["exit_code"] in (-1, -2, -3):
                failure_label = {
                    -1: "timed out",
                    -2: "stale",
                    -3: "aggregation hang",
                }[bridge_result["exit_code"]]
                result["status"] = "error"
                result["errors"] = [
                    f"Bridge review {failure_label} during re-entry round {reentry_round}. "
                    f"{bridge_result.get('stderr', '')}"
                ]
                _clear_state(repo_root)
                return result

            if bridge_result["exit_code"] == 0 and bridge_decision == "GO":
                render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
                parsed_findings = _parse_findings_from_render(render, raw_texts) if (render or raw_texts) else []
                blocking_findings, non_blocking_findings = _classify_findings(parsed_findings)
                if blocking_findings:
                    result["status"] = "error"
                    result["step"] = "reentry_bridge_decision"
                    result["errors"] = [
                        f"Bridge returned GO during re-entry round {reentry_round} but rendered transcript still "
                        f"contains {len(blocking_findings)} blocking finding(s). Fail closed."
                    ]
                    _clear_state(repo_root)
                    return result
                if non_blocking_findings:
                    all_non_blocking, packet_path = _record_non_blocking_findings(
                        repo_root, wave_id, all_non_blocking, non_blocking_findings
                    )
                    if packet_path is not None:
                        deferred_packet_path = str(packet_path.relative_to(repo_root))
                        executor_created.add(deferred_packet_path)
                        result["deferred_packet_path"] = deferred_packet_path
                        log(f"Re-entry GO: filed {len(non_blocking_findings)} non-blocking finding(s)")
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

            if bridge_result["exit_code"] == 0 and bridge_decision not in RECOGNIZED_BRIDGE_DECISIONS:
                result["status"] = "error"
                result["step"] = "reentry_bridge_decision"
                result["errors"] = [
                    f"Bridge returned unrecognized success decision during re-entry round {reentry_round}: "
                    f"{bridge_decision!r}. Fail closed."
                ]
                _clear_state(repo_root)
                return result

            if bridge_decision in ("REQUEST_CHANGES", "NO_GO"):
                # bridge_supervisor.py review returns exit=1 for non-GO decisions.
                # Treat REQUEST_CHANGES/NO_GO as recoverable review outcomes when
                # the exit code matches that CLI contract; only unexpected codes
                # are infrastructure failures here.
                if bridge_result["exit_code"] not in (0, 1):
                    log(f"Re-entry bridge subprocess failed (exit={bridge_result['exit_code']}) "
                        f"with decision {bridge_decision!r} — fail closed (not recoverable)")
                    result["status"] = "error"
                    result["step"] = "reentry_bridge_subprocess"
                    result["errors"] = [
                        f"Re-entry bridge subprocess failed in round {reentry_round} "
                        f"(exit={bridge_result['exit_code']}, decision={bridge_decision}). "
                        f"Unexpected exit with {bridge_decision} is not recoverable. "
                        f"stderr: {bridge_result.get('stderr', '')[:500]}"
                    ]
                    _clear_state(repo_root)
                    return result

                # Mirror initial loop: classify findings, defer non-blockers
                render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
                findings_text = render if render else bridge_result.get("stdout", "")

                parsed_findings = _parse_findings_from_render(render, raw_texts) if (render or raw_texts) else []
                blocking_findings, non_blocking_findings = _classify_findings(parsed_findings, finding_history)

                if blocking_findings and finding_history:
                    unresolvable = [
                        _finding_key(f) for f in blocking_findings
                        if finding_history.get(_finding_key(f), 0) >= REPEAT_FINDING_CAP
                    ]
                    if unresolvable:
                        log(f"HARD FAILURE: re-entry blocking finding(s) hit repeat cap "
                            f"({REPEAT_FINDING_CAP} rounds) — implementer cannot resolve")
                        result["status"] = "error"
                        result["step"] = "reentry_bridge_convergence"
                        result["errors"] = [
                            f"Re-entry blocking finding(s) unresolvable after {REPEAT_FINDING_CAP} rounds: "
                            + ", ".join(unresolvable[:5])
                        ]
                        result["unresolvable_findings"] = blocking_findings
                        _clear_state(repo_root)
                        return result

                if non_blocking_findings:
                    all_non_blocking, packet_path = _record_non_blocking_findings(
                        repo_root, wave_id, all_non_blocking, non_blocking_findings
                    )
                    if packet_path is not None:
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
                changed_files = _collect_wave_owned_files(
                    repo_root,
                    plan_path,
                    plan_declared_files,
                    implementer_changed or None,
                    executor_created or None,
                    baseline_wave_files or None,
                )

                # Checkpoint re-entry state so crash-resume picks up new findings and round
                _save_state(repo_root, {
                    "plan_path": plan_path,
                    "completed_step": "needs_phase_b_reentry",
                    "wave_id": wave_id,
                    "bridge_rounds": reentry_round,
                    "bridge_scope_fingerprint": _bridge_scope_fingerprint(repo_root, changed_files),
                    "deferred_packet_path": deferred_packet_path,
                    "implementer_changed": sorted(implementer_changed),
                    "executor_created": sorted(executor_created),
                    "baseline_wave_files": sorted(baseline_wave_files),
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
        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
        reentry_test_files = [f for f in changed_files if f.startswith("mu/tests/") or "/test_" in f or f.endswith("_test.py")]
        if reentry_test_files:
            log(f"Re-entry pytest gate: running {len(reentry_test_files)} test file(s)...")
            reentry_pytest = _run_pytest_on_files(repo_root, reentry_test_files, timeout=pytest_gate_timeout)
            if not reentry_pytest["passed"]:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_pytest_gate",
                    "errors": [
                        f"Re-entry pytest gate FAILED (exit={reentry_pytest['exit_code']}). "
                        "Tests must pass before commit. "
                        + _summarize_pytest_failure(reentry_pytest)
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
        all_dirty_reentry2 = _collect_changed_files(repo_root)
        supervisor_package["fenced_files"] = [f for f in all_dirty_reentry2 if f not in set(changed_files)]
        supervisor_package["bridge_status"] = {"rounds": result.get("bridge_rounds", 0), "total_rounds": _total_bridge_rounds(repo_root), "reentry": True}
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
        supervisor_parsed = supervisor_result.get("parsed", {})
        decision = supervisor_parsed.get("decision")
        receipt_path = supervisor_result.get("receipt_path", "")
        result["pre_commit_decision"] = decision
        result["pre_commit_summary"] = _supervisor_reason_text(supervisor_parsed)
        log(f"Post-reentry supervisor decision: {decision}")
        if result.get("pre_commit_summary"):
            log(f"Post-reentry supervisor summary: {result['pre_commit_summary']}")

        if decision == "NEEDS_PHASE_B":
            result["status"] = "needs_phase_b"
            detail = result.get("pre_commit_summary", "")
            message = "Supervisor returned NEEDS_PHASE_B after reentry convergence. Manual intervention required."
            if detail:
                message += f" {detail}"
            result["errors"] = [message]
            _clear_state(repo_root)
            return result
        elif decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            result["status"] = "supervisor_rejected"
            result["step"] = "post_reentry_supervisor"
            detail = result.get("pre_commit_summary", "")
            message = f"Post-reentry supervisor returned {decision}"
            if detail:
                message += f". {detail}"
            result["errors"] = [message]
            _clear_state(repo_root)
            return result

    elif decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
        result["status"] = "supervisor_rejected"
        result["step"] = "pre_commit_supervisor"
        detail = result.get("pre_commit_summary", "")
        message = f"Supervisor returned {decision}, not COMMIT_GO"
        if detail:
            message += f". {detail}"
        result["errors"] = [message]
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
    wave_owned_files = _collect_wave_owned_files(
        repo_root,
        plan_path,
        plan_declared_files,
        implementer_changed or None,
        executor_created or None,
        baseline_wave_files or None,
    )
    if not wave_owned_files:
        return {
            "status": "error",
            "step": "commit_handoff",
            "errors": ["files_to_stage is empty — cannot produce a commit_ready handoff with no files"],
        }
    handoff_deferred_items = _collect_supervisor_deferred_items(
        wave_owned_files, deferred_packet_path,
    )
    handoff_bridge_status: dict[str, Any] = {
        "rounds": result.get("bridge_rounds", 0),
        "total_rounds": _total_bridge_rounds(repo_root),
    }
    if "reentry_converged" in locals() and locals()["reentry_converged"]:
        handoff_bridge_status["reentry"] = True
    handoff_test_files = locals().get("reentry_test_files") or locals().get("final_test_files") or []
    tracker_note_text = _build_phase_b_tracker_note(
        wave_id=wave_id,
        task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        plan_path=plan_path,
        changed_files=wave_owned_files,
        test_files=handoff_test_files,
        receipt_path=receipt_path,
        bridge_rounds=result.get("bridge_rounds", 0),
        reentry=bool("reentry_converged" in locals() and locals()["reentry_converged"]),
    )
    log(f"Preparing commit handoff ({len(wave_owned_files)} wave-owned files)...")
    handoff_path = prepare_commit_handoff(
        repo_root,
        wave_id=wave_id,
        task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        tracker_note_text=tracker_note_text,
        fixes_implemented=["Phase B implementation per locked plan"],
        files_to_stage=wave_owned_files,
        pre_commit_receipt_path=receipt_path,
        commit_message=f"feat: Phase B implementation for {wave_id}\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>",
        pr_title=f"feat: Phase B - {wave_id}",
        pr_body=f"## Summary\nPhase B implementation per locked plan at {plan_path}",
        supervisor_lane="hooks/agents/bridge control-surface",
        deferred_items=handoff_deferred_items,
        bridge_status=handoff_bridge_status,
        scope_items=[plan_path],
        evidence_handles={"indicator": f"reports/l4_wave_indicators/{wave_id}.json"},
    )
    result["status"] = "commit_ready"
    result["handoff_path"] = str(handoff_path)
    result["pre_commit_decision"] = decision
    result["receipt_path"] = receipt_path
    # Now that COMMIT_GO is confirmed, advance packet to COMPLETED
    # (deferred from Step 5b to avoid premature COMPLETED on rejection)
    if not plan_path.startswith("<"):
        update_plan_packet_status(
            repo_root, plan_path, "COMPLETED (commit-ready, supervisor COMMIT_GO)",
        )
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
        default=None,
        help="Path to locked plan packet (relative to repo root). "
             "If omitted, derives bounded context from routing record.",
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
        "--task-id",
        type=str,
        default=None,
        help="TASKS.md task ID (e.g., '[NEXT-CODEX-POST-REDTEAM]'). "
             "Overrides routing record task_id. Required for --bootstrap-exception "
             "when routing record has no task_id.",
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

    routing_record_override = None
    if args.routing_record:
        try:
            routing_record_override = json.loads(args.routing_record)
        except json.JSONDecodeError as exc:
            print(json.dumps({
                "status": "error",
                "step": "parse_routing_record",
                "errors": [f"--routing-record is not valid JSON: {exc}"],
            }, indent=2) if args.json else f"[phase-b] Error: --routing-record is not valid JSON: {exc}")
            return 1
        if not isinstance(routing_record_override, dict):
            print(json.dumps({
                "status": "error",
                "step": "parse_routing_record",
                "errors": ["--routing-record must decode to a JSON object"],
            }, indent=2) if args.json else "[phase-b] Error: --routing-record must decode to a JSON object")
            return 1

    # Inject task_id into routing record override if provided via CLI.
    # Merge into existing override (if any) rather than replacing it,
    # so --task-id works both with and without --routing-record.
    if args.task_id:
        if routing_record_override is not None:
            routing_record_override["task_id"] = args.task_id
        else:
            # No full override — pass task_id for post-load merge in run_phase_b
            routing_record_override = {"_merge_task_id": args.task_id}

    result = run_phase_b(
        repo_root, args.plan,
        max_bridge_rounds=args.max_rounds,
        verbose=args.verbose,
        force=args.bootstrap_exception,
        routing_record_override=routing_record_override,
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
