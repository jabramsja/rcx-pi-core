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

Most terminal exits clear persisted state to prevent stale resume on next
invocation. Founder-wait QUESTION verdicts that must block routine redispatch
are journaled as explicit terminal checkpoints.

See: reports/control_plane/executor_surfaces_plan_2026-03-22.md Section B.3
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

SCRIPT_DIR = Path(__file__).resolve().parent

# Import canonical load_routing_record from shared module
try:
    from executor_common import (
        agent_bus_path,
        agent_bus_relpath,
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
        resolve_agent_bus_dir,
        emit_pipeline_agent_event,
    )
except ImportError:
    # Fallback for direct execution
    import importlib.util as _ilu
    _common_path = SCRIPT_DIR / "executor_common.py"
    _spec = _ilu.spec_from_file_location("executor_common", str(_common_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    agent_bus_path = _mod.agent_bus_path
    agent_bus_relpath = _mod.agent_bus_relpath
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
    resolve_agent_bus_dir = _mod.resolve_agent_bus_dir
    emit_pipeline_agent_event = _mod.emit_pipeline_agent_event

_ACTIVE_BUS_DIR: ContextVar[Path | None] = ContextVar("phase_b_executor_bus_dir", default=None)


def _active_bus_dir() -> Path | None:
    return _ACTIVE_BUS_DIR.get()

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

try:
    import candidate_authority as _candidate_authority
except ImportError:
    import importlib.util as _ilu
    _candidate_authority_path = SCRIPT_DIR / "candidate_authority.py"
    _candidate_authority_spec = _ilu.spec_from_file_location(
        "candidate_authority",
        str(_candidate_authority_path),
    )
    _candidate_authority = _ilu.module_from_spec(_candidate_authority_spec)
    assert _candidate_authority_spec.loader is not None
    sys.modules["candidate_authority"] = _candidate_authority
    _candidate_authority_spec.loader.exec_module(_candidate_authority)


class PhaseBExecutorError(RuntimeError):
    """Raised when Phase B executor cannot proceed."""


ALLOWED_FINDING_DISPOSITIONS = {"blocking", "non_blocking"}
BRIDGE_JOB_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
RECOGNIZED_BRIDGE_DECISIONS = {"GO", "REQUEST_CHANGES", "NO_GO", "QUESTION"}
BRIDGE_CORRECTION_CONTEXT_LIMIT = 4000
PHASE_B_BRIDGE_AUTHORITY_ROUND = "bridge_pre_review"
ALLOWED_REVIEW_DEPTHS = {"quick", "full", "founder", "all"}
BRIDGE_REVIEW_POLL_INTERVAL = 30.0
BRIDGE_REVIEW_POLL_SLEEP = 5.0
BRIDGE_REVIEW_STALE_TIMEOUT = 120.0
BRIDGE_REVIEW_AGGREGATION_HANG_TIMEOUT = 60.0
DEFAULT_PYTEST_GATE_TIMEOUT_S = 300
# Structural/L4 gates can legitimately exceed 40 minutes under the Phase B
# final sweep. Keep a bounded cap while allowing the configured executor budget
# to cover a full evidence-sized pytest run.
MAX_PYTEST_GATE_TIMEOUT_S = 7200
_MAINTENANCE_FORBIDDEN_PREFIXES = (
    "mu/host/",
    "mu/substrate/",
    "mu/closures/",
    "mu/bridge/",
    "mu/programs/",
    "rcx_pi/selfhost/",
    "mu/tools/compilers/",
    "tools/compilers/",
)
_CONTROL_PLANE_TOOLING_PREFIXES = (
    ".github/workflows/",
    "tools/checks/",
    "mu/tools/agents/",
    "mu/tools/executors/",
    "mu/tools/checks/",
    "mu/tools/hooks/",
    "mu/tools/observability/",
    "mu/tools/recovery/",
)
_SUPERVISOR_OVERRIDE_WAVE_CLASSES = {"L4_ENABLER", "MAINTENANCE"}
PHASE_B_PRE_SUPERVISOR_PENDING_STATUS = (
    "Phase B (pre-supervisor pending, bridge-converged)"
)
PHASE_B_INDICATOR_SCOPE_REFRESH_START = "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->"
PHASE_B_INDICATOR_SCOPE_REFRESH_END = "<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->"
PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER = (
    "<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->"
)


# ---------------------------------------------------------------------------
# Finding disposition helpers
# ---------------------------------------------------------------------------


def _is_go_bridge_decision(bridge_decision: str) -> bool:
    """Return whether a bridge decision authorizes deferral and convergence."""
    return bridge_decision == "GO"


def _shared_deferrable_on_go(finding: dict[str, Any]) -> bool:
    """Return recovery_gate's deferrability verdict for *finding* on a GO round.

    phase_b does NOT define its own deferrability predicate. It delegates to the
    single shared rule ``recovery_gate._finding_is_deferrable_on_go`` so the two
    executors can never diverge (the prior attempt was NO_GO'd for adding a
    second, divergent definition). The import is function-local to match the
    established executor idiom; recovery_gate imports phase_b_executor only inside
    a function, so this stays cycle-safe. The shared rule fail-closes (returns
    False / not deferrable) on a non-dict finding.
    """
    try:
        from recovery_gate import _finding_is_deferrable_on_go
    except ImportError:
        _rg_path = SCRIPT_DIR / "recovery_gate.py"
        _rg_spec = importlib.util.spec_from_file_location("recovery_gate", str(_rg_path))
        _rg_mod = importlib.util.module_from_spec(_rg_spec)
        assert _rg_spec.loader is not None
        sys.modules[_rg_spec.name] = _rg_mod
        _rg_spec.loader.exec_module(_rg_mod)
        _finding_is_deferrable_on_go = _rg_mod._finding_is_deferrable_on_go
    return _finding_is_deferrable_on_go(finding)


def _shared_mandatory_blocking_evidence(finding: dict[str, Any]) -> bool:
    """Return recovery_gate's exact mandatory-evidence promotion verdict."""
    try:
        from recovery_gate import _finding_has_mandatory_blocking_evidence
    except ImportError:
        _rg_path = SCRIPT_DIR / "recovery_gate.py"
        _rg_spec = importlib.util.spec_from_file_location("recovery_gate", str(_rg_path))
        _rg_mod = importlib.util.module_from_spec(_rg_spec)
        assert _rg_spec.loader is not None
        sys.modules[_rg_spec.name] = _rg_mod
        _rg_spec.loader.exec_module(_rg_mod)
        _finding_has_mandatory_blocking_evidence = (
            _rg_mod._finding_has_mandatory_blocking_evidence
        )
    return _finding_has_mandatory_blocking_evidence(finding)


def _disposition_for_finding(finding: dict[str, Any]) -> tuple[str, str]:
    """Derive effective disposition for a single finding.

    Returns (disposition, reason) tuple for logging/auditability.

    Priority:
    1. Exact mandatory evidence_result conjunction — promotion to blocking.
    2. Present 'disposition' field — canonical values are authoritative at
       every severity; invalid or ambiguous values fail closed.
    3. With disposition absent, severity 'critical'/'high' — blocking.
    4. Medium/low governance/doc-only findings — non-blocking by default.
    5. Medium/low severity — non-blocking UNLESS blocking keyword match.
    6. No severity — keyword match, then fail-closed blocking.
    """
    severity = str(finding.get("severity") or "").strip().lower()
    disposition = finding.get("disposition")
    finding_class = str(finding.get("class") or "").upper()

    # Exact mandatory impact is an independent promotion. It runs before every
    # structured/fallback branch so disposition=non_blocking cannot bypass it.
    if _shared_mandatory_blocking_evidence(finding):
        return "blocking", (
            "mandatory evidence_result promotion: declared hard-invariant "
            "violation with merge disposition blocking"
        )

    if "disposition" in finding:
        if (
            isinstance(disposition, str)
            and disposition in ALLOWED_FINDING_DISPOSITIONS
        ):
            # Delegate the structured decision to recovery_gate's one shared
            # authority. Canonical dispositions control at every severity once
            # exact mandatory-evidence promotion has been ruled out.
            if _shared_deferrable_on_go(finding):
                return "non_blocking", "explicit disposition field"
            return "blocking", "explicit disposition field"
        return "blocking", f"invalid disposition {disposition!r} (fail-closed)"

    # The existing severity floor applies only when the reviewer omitted the
    # structured disposition. This preserves fail-closed handling for absent
    # high/critical dispositions without relabeling explicit current impact.
    if severity == "critical":
        return "blocking", "critical severity with absent disposition"

    if severity == "high":
        return "blocking", "high severity with absent disposition"

    # Governance/doc-only findings: DOC_ACCURACY or POLICY_BOUND on governance
    # paths are editorial, not runtime risks. Downgrade to non-blocking for
    # medium/low severity only when the reviewer did not give an explicit
    # disposition — critical/high and explicit blocking are handled above.
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
    disposition (mandatory promotion → explicit field → absent-disposition
    severity floor/fallback heuristics → fail-closed blocking). Logs the
    decision with reason for each finding.

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


def _blocking_findings_in_deferred_convergence(
    findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return accumulated deferred findings whose effective disposition blocks.

    This intentionally reuses the normal Phase B finding disposition logic at
    the bridge-converged boundary so a stale or malformed saved state cannot
    resume into final pytest/supervisor with a blocker hidden in
    ``all_non_blocking``.
    """
    blocking: list[dict[str, Any]] = []
    for index, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            blocking.append({
                "title": f"Malformed deferred finding at index {index}",
                "severity": "critical",
                "disposition": "blocking",
                "detail": "all_non_blocking contained a non-object finding payload",
            })
            continue
        disposition, reason = _disposition_for_finding(finding)
        if disposition == "blocking":
            annotated = dict(finding)
            annotated["effective_disposition"] = disposition
            annotated["effective_disposition_reason"] = reason
            blocking.append(annotated)
    return blocking


def _control_packet_line_ref_checker_path(repo_root: Path) -> Path:
    """Return the existing control-packet line-ref checker path."""
    repo_candidate = repo_root / "tools" / "checks" / "check_control_packet_line_refs.py"
    if repo_candidate.exists():
        return repo_candidate
    source_candidate = SCRIPT_DIR.parents[2] / "tools" / "checks" / "check_control_packet_line_refs.py"
    return source_candidate


def _load_control_packet_line_ref_checker(repo_root: Path) -> Any:
    """Load tools/checks/check_control_packet_line_refs.py for callable reuse."""
    checker_path = _control_packet_line_ref_checker_path(repo_root)
    if not checker_path.exists():
        raise PhaseBExecutorError(
            f"control-packet line-ref checker not found: {checker_path}"
        )
    spec = importlib.util.spec_from_file_location(
        "phase_b_control_packet_line_ref_checker",
        str(checker_path),
    )
    if spec is None or spec.loader is None:
        raise PhaseBExecutorError(
            f"control-packet line-ref checker cannot be loaded: {checker_path}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _control_packet_paths(plan_path: str, changed_files: list[str]) -> list[str]:
    """Return sorted relative control-packet paths among ``plan_path`` + ``changed_files``.

    A control packet is a ``reports/control_plane/*.md`` file. Shared by the
    pre-finalization line-ref normalizer and the line-ref lint so both operate
    on exactly the same packet set by construction -- the normalizer cannot
    drift out of lockstep with what the lint inspects.
    """
    packet_paths: set[str] = set()
    for raw_path in [plan_path, *changed_files]:
        rel_path = str(raw_path or "").strip()
        if (
            rel_path
            and not rel_path.startswith("<")
            and rel_path.startswith("reports/control_plane/")
            and rel_path.endswith(".md")
        ):
            packet_paths.add(rel_path)
    return sorted(packet_paths)


def _normalize_control_packet_line_refs(
    repo_root: Path,
    *,
    plan_path: str,
    changed_files: list[str],
) -> None:
    """Strip extension-colon-digit line refs from changed control packets in place.

    phase_b is the PRODUCING executor of its own control packet, so rewriting the
    packet on disk here is not an external artifact edit. Every
    ``<name>.<ext>:<line>`` reference -- including the ``:<line>:<col>``,
    ``:<line>-<line>`` (range), and ``:<line>,<line>`` (list) tails -- is
    reduced to the compliant name-only ``<name>.<ext>`` form *before* the
    fail-closed line-ref lint runs, so an implementer-added line citation
    self-heals instead of stranding the wave (tier-3 recovery cannot remove it
    because control-plane artifacts are edit-gated). The extension set is taken
    from the checker's ``CODE_EXTENSIONS`` so the normalizer stays in lockstep
    with what the lint flags.

    Best-effort by design: the lint remains the post-normalization guard. If the
    checker cannot load, or a packet cannot be read or written, this returns
    without raising and the lint fails closed on the still-offending packet --
    normalization can only remove strands, never introduce a fail-open.
    """
    packet_paths = _control_packet_paths(plan_path, changed_files)
    if not packet_paths:
        return

    try:
        checker = _load_control_packet_line_ref_checker(repo_root)
    except PhaseBExecutorError:
        return

    extensions = getattr(checker, "CODE_EXTENSIONS", ())
    if not extensions:
        return
    # Longest-first alternation mirrors the checker so a prefix extension
    # (``js`` inside ``json``) cannot shadow the longer match. Capture the
    # ``.<ext>`` head, then consume the FULL numeric citation tail: a mandatory
    # ``:<digits>`` (the same anchor the lint flags) followed by any number of
    # ``[:,-]<digits>`` groups. That single greedy tail collapses every common
    # citation shape -- ``file:line``, ``file:line:col``, ``file:line-line``
    # (range), and ``file:line,line`` (list) -- to the bare name-only head in
    # one pass. Consuming only ``:<digits>`` groups (the earlier form) stripped
    # the ``:line`` of a range but left the ``-line`` behind as malformed
    # ``file.py-line`` residue; the lint then PASSED on it (no longer
    # ``.<ext>:<digit>``) and silently shipped a broken ref. Requiring a leading
    # ``:<digits>`` keeps host:port, clock times, and extension-less numeric
    # ranges untouched, exactly as the lint leaves them.
    ext_alternation = "|".join(sorted(extensions, key=len, reverse=True))
    normalize_re = re.compile(
        r"(\.(?:" + ext_alternation + r")):\d+(?:[:,-]\d+)*"
    )

    for rel_path in packet_paths:
        packet = repo_root / rel_path
        try:
            text = packet.read_text(encoding="utf-8")
        except OSError:
            continue
        normalized = normalize_re.sub(r"\1", text)
        if normalized != text:
            try:
                packet.write_text(normalized, encoding="utf-8")
            except OSError:
                continue


def _control_packet_line_ref_lint_error(
    repo_root: Path,
    *,
    plan_path: str,
    changed_files: list[str],
) -> str | None:
    """Return an error string when changed control packets cite code by line."""
    packet_paths = _control_packet_paths(plan_path, changed_files)
    if not packet_paths:
        return None

    try:
        checker = _load_control_packet_line_ref_checker(repo_root)
    except PhaseBExecutorError as exc:
        return str(exc)

    reports: list[str] = []
    for rel_path in packet_paths:
        packet = repo_root / rel_path
        try:
            offenses = checker.scan_path(packet)
        except OSError as exc:
            return f"{rel_path}: cannot read for control-packet line-ref lint: {exc}"
        if offenses:
            reports.append(checker.format_offenses(rel_path, offenses))
    if not reports:
        return None
    remediation = getattr(
        checker,
        "REMEDIATION",
        "Cite code by function name instead of file:line.",
    )
    return (
        "pre-finalization control-packet line-ref lint failed:\n"
        + "\n".join(reports)
        + f"\n\n{remediation}"
    )


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


def _canonical_deferred_packet_relpath(wave_id: str) -> str:
    return (
        "reports/deferred/non_blocking/"
        f"{normalize_wave_id(wave_id)}_bridge_nonblockers.md"
    )


def _same_wave_closed_deferred_archive_path(repo_root: Path, wave_id: str) -> Path | None:
    safe_wave = normalize_wave_id(wave_id)
    if not safe_wave:
        return None
    archive_dir = repo_root / "reports" / "archive" / "deferred"
    if not archive_dir.is_dir():
        return None
    candidates = sorted(
        p for p in archive_dir.glob(f"{safe_wave}_bridge_nonblockers*.md")
        if "_closed-by-" in p.name
    )
    return candidates[0] if candidates else None


def _render_post_closure_non_blocking_block(
    wave_id: str,
    non_blocking_findings: list[dict[str, Any]],
) -> str:
    lines = [
        "<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:start -->",
        "## Post-Closure Non-Blocking Review Notes",
        "",
        f"Wave: {wave_id}",
        "Status: RETAINED_OUTSIDE_ACTIVE_DEFERRED_LANE",
        f"Generated by Phase B executor. {len(non_blocking_findings)} finding(s).",
        "",
        "The same-wave generated bridge packet has already been archived closed, so",
        "these later non-blocking review notes are retained here instead of",
        "reopening `reports/deferred/non_blocking/` for the same wave.",
        "",
    ]
    for i, f in enumerate(non_blocking_findings, 1):
        lines.append(f"## Post-Closure {i}. {f.get('title', 'Untitled')}")
        lines.append(f"- **Class:** {f.get('class', 'unknown')}")
        lines.append(f"- **Severity:** {f.get('severity', 'unknown')}")
        lines.append(f"- **File:** {f.get('file', 'unknown')}")
        lines.append("- **Disposition:** non_blocking")
        if f.get("evidence_cmd"):
            lines.append(f"- **Evidence:** `{f['evidence_cmd']}`")
        lines.append("")
    lines.append("<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:end -->")
    return "\n".join(lines)


def _replace_post_closure_non_blocking_block(packet_text: str, block: str) -> str:
    start_marker = "<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:start -->"
    end_marker = "<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:end -->"
    start = packet_text.find(start_marker)
    end = packet_text.find(end_marker)
    if start != -1 and end != -1 and end > start:
        end += len(end_marker)
        return (
            packet_text[:start].rstrip()
            + "\n\n"
            + block.rstrip()
            + "\n"
            + packet_text[end:].lstrip("\n")
        )
    if start != -1 or end != -1:
        raise PhaseBExecutorError("post-closure deferred block markers are unbalanced")
    return packet_text.rstrip() + "\n\n" + block.rstrip() + "\n"


def _remove_post_closure_non_blocking_block(packet_text: str) -> tuple[str, bool]:
    start_marker = "<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:start -->"
    end_marker = "<!-- PHASE_B_POST_CLOSURE_NONBLOCKING:end -->"
    start = packet_text.find(start_marker)
    end = packet_text.find(end_marker)
    if start != -1 and end != -1 and end > start:
        end += len(end_marker)
        prefix = packet_text[:start].rstrip()
        suffix = packet_text[end:].lstrip("\n")
        if prefix and suffix:
            return prefix + "\n\n" + suffix, True
        if prefix:
            return prefix + "\n", True
        return suffix, True
    if start != -1 or end != -1:
        raise PhaseBExecutorError("post-closure deferred block markers are unbalanced")
    return packet_text, False


def _retain_non_blocking_findings_in_closed_archive(
    repo_root: Path,
    wave_id: str,
    archive_path: Path,
    non_blocking_findings: list[dict[str, Any]],
) -> None:
    packet_text = archive_path.read_text(encoding="utf-8")
    block = _render_post_closure_non_blocking_block(wave_id, non_blocking_findings)
    archive_path.write_text(
        _replace_post_closure_non_blocking_block(packet_text, block),
        encoding="utf-8",
    )


def _clear_non_blocking_findings_from_closed_archive(archive_path: Path) -> bool:
    packet_text = archive_path.read_text(encoding="utf-8")
    updated_text, changed = _remove_post_closure_non_blocking_block(packet_text)
    if changed:
        archive_path.write_text(updated_text, encoding="utf-8")
    return changed


def _clear_deferred_packet(repo_root: Path, wave_id: str) -> None:
    """Remove the canonical deferred packet for a wave when no findings remain."""
    packet_path = (
        repo_root
        / "reports"
        / "deferred"
        / "non_blocking"
        / f"{normalize_wave_id(wave_id)}_bridge_nonblockers.md"
    )
    try:
        packet_path.unlink()
    except FileNotFoundError:
        return


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
    """Replace non-blocking findings with the latest bridge truth."""
    if not new_findings:
        _clear_deferred_packet(repo_root, wave_id)
        return [], None
    merged: dict[str, dict[str, Any]] = {}
    for finding in new_findings:
        merged[_finding_key(finding)] = finding
    merged_findings = list(merged.values())
    return merged_findings, _write_deferred_packet(
        repo_root, wave_id, merged_findings,
        wave_class=wave_class, target_gate_id=target_gate_id,
    )


def _sync_deferred_non_blocking_state(
    repo_root: Path,
    wave_id: str,
    existing_findings: list[dict[str, Any]],
    new_findings: list[dict[str, Any]],
    *,
    previous_packet_path: str | None,
    executor_created: set[str],
    wave_class: str = "",
    target_gate_id: str = "",
) -> tuple[list[dict[str, Any]], str | None]:
    """Refresh deferred packet state from the latest bridge findings."""
    closed_archive_path = _same_wave_closed_deferred_archive_path(repo_root, wave_id)
    if closed_archive_path is not None:
        current_findings = list(new_findings)
        archive_rel_path = str(closed_archive_path.relative_to(repo_root))
        if current_findings:
            _retain_non_blocking_findings_in_closed_archive(
                repo_root,
                wave_id,
                closed_archive_path,
                current_findings,
            )
            executor_created.add(archive_rel_path)
        elif _clear_non_blocking_findings_from_closed_archive(closed_archive_path):
            executor_created.add(archive_rel_path)
        active_rel_path = _canonical_deferred_packet_relpath(wave_id)
        _clear_deferred_packet(repo_root, wave_id)
        executor_created.add(active_rel_path)
        return current_findings, None

    current_findings, packet_path = _record_non_blocking_findings(
        repo_root,
        wave_id,
        existing_findings,
        new_findings,
        wave_class=wave_class,
        target_gate_id=target_gate_id,
    )
    if packet_path is None:
        if previous_packet_path:
            # Keep the cleared packet in executor-owned scope until the next
            # scoped staging pass reconciles a possible staged-add/worktree-delete
            # state. Dropping it here can leave an AD packet outside the handoff.
            executor_created.add(previous_packet_path)
        return current_findings, None
    rel_path = str(packet_path.relative_to(repo_root))
    executor_created.add(rel_path)
    return current_findings, rel_path


def _checkpoint_bridge_fix_pending(
    repo_root: Path,
    *,
    plan_path: str,
    wave_id: str,
    round_num: int,
    bridge_decision: str,
    bridge_fix_findings: str,
    changed_files: list[str],
    deferred_packet_path: str | None,
    implementer_changed: set[str],
    executor_created: set[str],
    baseline_wave_files: set[str],
    all_non_blocking: list[dict[str, Any]],
    finding_history: dict[str, int],
) -> None:
    """Persist the exact pre-fix bridge state so crash-resume can continue honestly."""
    _save_state(repo_root, {
        "plan_path": plan_path,
        "completed_step": "bridge_fix_pending",
        "wave_id": wave_id,
        "bridge_rounds": round_num,
        "current_bridge_round": round_num,
        "bridge_decision": bridge_decision,
        "bridge_fix_findings": bridge_fix_findings,
        "bridge_scope_fingerprint": _bridge_scope_fingerprint(repo_root, changed_files),
        "deferred_packet_path": deferred_packet_path,
        "implementer_changed": sorted(implementer_changed),
        "executor_created": sorted(executor_created),
        "baseline_wave_files": sorted(baseline_wave_files),
        "all_non_blocking": all_non_blocking,
        "finding_history": finding_history,
    })


def _supervisor_reason_text(parsed: dict[str, Any]) -> str:
    """Return the actionable supervisor reason instead of only the decision token."""
    parts: list[str] = []
    summary = str(parsed.get("summary", "") or "").strip()
    if summary:
        parts.append(summary)
    error_detail = str(parsed.get("error_detail", "") or "").strip()
    if error_detail and error_detail != summary:
        parts.append(f"detail: {error_detail}")
    request_for_agent = str(parsed.get("request_for_agent") or parsed.get("request_for_claude", "") or "").strip()
    if request_for_agent and request_for_agent not in parts:
        parts.append(f"next: {request_for_agent}")
    return " | ".join(parts)


def _is_staged_deletion(repo_root: Path, rel_path: str) -> bool:
    """Return whether rel_path is staged as a deletion in the git index."""
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "--", rel_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    except subprocess.CalledProcessError:
        return False
    for line in staged:
        status, _, path = line.partition("\t")
        if path == rel_path and status == "D":
            return True
    return False


def _has_closed_archive_for_deferred_source(rel_path: str, wave_owned_files: list[str]) -> bool:
    """Return whether a deferred source deletion has a tracked closed archive mate."""
    if not (
        rel_path.startswith("reports/deferred/non_blocking/")
        and rel_path.endswith(".md")
    ):
        return False
    source_stem = Path(rel_path).name[:-3]
    for candidate in wave_owned_files:
        if not candidate.startswith("reports/archive/deferred/"):
            continue
        candidate_name = Path(candidate).name
        if (
            candidate_name.startswith(source_stem)
            and "_closed-by-" in candidate_name
            and candidate_name.endswith(".md")
        ):
            return True
    return False


def _collect_supervisor_deferred_items(
    changed_files: list[str],
    deferred_packet_path: str | None,
    *,
    repo_root: Path | None = None,
) -> list[str]:
    """Surface active wave-owned deferred non-blocking packets in supervisor packages."""
    def is_active_deferred_item(rel_path: str) -> bool:
        if repo_root is not None and _is_staged_deletion(repo_root, rel_path):
            return False
        return True

    changed_file_set = set(changed_files)
    deferred_items = {
        rel_path
        for rel_path in changed_file_set
        if rel_path.startswith("reports/deferred/non_blocking/")
        and rel_path.endswith(".md")
        and not rel_path.endswith("/README.md")
        and is_active_deferred_item(rel_path)
    }
    if (
        deferred_packet_path
        and deferred_packet_path in changed_file_set
        and is_active_deferred_item(deferred_packet_path)
    ):
        deferred_items.add(deferred_packet_path)
    return sorted(deferred_items)


def _split_commit_handoff_stage_files(
    repo_root: Path,
    wave_id: str,
    wave_owned_files: list[str],
) -> tuple[list[str], list[str]]:
    """Separate add-able handoff paths from staged-deleted active deferred packets."""
    stage_files: list[str] = []
    staged_deletions: list[str] = []
    for rel_path in wave_owned_files:
        if (
            _has_closed_archive_for_deferred_source(rel_path, wave_owned_files)
            and _is_staged_deletion(repo_root, rel_path)
        ):
            staged_deletions.append(rel_path)
            continue
        stage_files.append(rel_path)
    return stage_files, staged_deletions


def _collect_supervisor_evidence_handles(repo_root: Path, wave_id: str) -> dict[str, str]:
    """Return only package evidence handles that already exist in repo truth."""
    indicator_rel = f"reports/l4_wave_indicators/{wave_id}.json"
    if (repo_root / indicator_rel).exists():
        return {"indicator": indicator_rel}
    return {}


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
        raw_dir = agent_bus_path(repo_root, _active_bus_dir(), "raw", job_id)
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


def _bounded_bridge_correction_context(text: str) -> str:
    """Bound correction context without dropping all late reviewer content."""
    content = text.strip()
    if len(content) <= BRIDGE_CORRECTION_CONTEXT_LIMIT:
        return content

    omission = "\n\n...[middle omitted from bounded bridge correction context]...\n\n"
    available = BRIDGE_CORRECTION_CONTEXT_LIMIT - len(omission)
    head_limit = available // 2
    tail_limit = available - head_limit
    return content[:head_limit] + omission + content[-tail_limit:]


def _bridge_correction_context(
    parsed_findings: list[dict[str, Any]],
    render_text: str,
    raw_texts: list[str],
    bridge_stdout: str,
) -> str:
    """Select bounded reviewer context for a non-GO implementer correction.

    Structured findings are the narrowest authoritative correction input. If
    the review was not structurally parseable, prefer the final reviewer agent
    message over surrounding command-event noise, then retain the prior raw /
    render / stdout fallback.
    """
    if parsed_findings:
        context = json.dumps(parsed_findings, indent=2)
    else:
        agent_message = ""
        for raw_text in raw_texts:
            agent_messages = _iter_agent_message_texts(raw_text)
            if agent_messages:
                agent_message = agent_messages[-1]
                break
        if not agent_message:
            render_messages = _iter_agent_message_texts(render_text)
            if render_messages:
                agent_message = render_messages[-1]
        if not agent_message:
            stdout_messages = _iter_agent_message_texts(bridge_stdout)
            if stdout_messages:
                agent_message = stdout_messages[-1]
        context = (
            agent_message
            if agent_message
            else "\n\n".join(raw_texts) or render_text or bridge_stdout
        )
    return _bounded_bridge_correction_context(context)


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


def resolve_pytest_gate_timeout(raw_timeout: Any) -> int:
    """Public seam for tests and commit-packet refresh code."""
    return _resolve_pytest_gate_timeout(raw_timeout)


def _is_pytest_gate_file(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    return path.startswith("mu/tests/") or "/test_" in path or path.endswith("_test.py")


_RUNTIME_TARGETED_TESTS = {
    "mu/host/js/core/bootstrap_core.js": (
        "tests/l4_gates/test_bootstrap_core_carveout_gate.py",
    ),
    "mu/tools/executors/phase_b_executor.py": (
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff",
        "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors",
    ),
}

_PYTEST_DIFF_SELECTOR_HINTS = {
    "mu/tests/parity/test_js_parity_automated.py": (
        (
            ("_MAX_STEPS_GUARDED_ACTIONS", "_GUARDED_ACTION_BASE_ARGS"),
            (
                "maxEngineIterations",
                "Engine actions use one outer iteration",
                "API cap validation",
                "deeper engine convergence",
                "parity coverage with small structural budgets below",
                "Base args for each guarded action",
                "API guard acceptance/rejection",
                "full engine convergence behavior",
            ),
            ("mu/tests/parity/test_js_parity_automated.py::TestAPIMaxStepsGuard",),
        ),
    ),
    "mu/tests/tools/test_phase_b_executor.py": (
        (
            (
                "test_phase_b_pytest_gate_timeout_",
                "test_pytest_selector_hints_",
                "test_select_pytest_gate_files_uses",
            ),
            (),
            (
                "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_allows_pre_push_budget",
                "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_phase_b_pytest_gate_timeout_keeps_floor_for_invalid_values",
                "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_guard_matrix_diff",
                "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_max_steps_mixed_diff_falls_back_to_file_gate",
                "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_selector_hints_executor_test_context_only_marker_falls_back_to_file",
                "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_pytest_gate_diff_text_includes_staged_and_unstaged_diff",
                "mu/tests/tools/test_phase_b_executor.py::TestSdkReviewDepthContract::test_select_pytest_gate_files_uses_targeted_executor_timeout_selectors",
            ),
        ),
    ),
}


def _pytest_gate_diff_text(repo_root: Path, path: str) -> str:
    diff_parts: list[str] = []
    for args in (
        ("git", "diff", "--cached", "--", path),
        ("git", "diff", "--", path),
    ):
        result = subprocess.run(
            args,
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            diff_parts.append(result.stdout)
    return "\n".join(diff_parts)


def pytest_gate_diff_text(repo_root: Path, path: str) -> str:
    """Return staged and unstaged diff text for pytest gate selector narrowing."""
    return _pytest_gate_diff_text(repo_root, path)


def _changed_diff_hunks(diff_text: str) -> list[str]:
    hunks: list[str] = []
    current_hunk: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("@@ "):
            if current_hunk:
                hunks.append("\n".join(current_hunk))
            current_hunk = [line]
        elif current_hunk:
            current_hunk.append(line)
    if current_hunk:
        hunks.append("\n".join(current_hunk))
    return [
        hunk
        for hunk in hunks
        if any(
            (line.startswith("+") and not line.startswith("+++"))
            or (line.startswith("-") and not line.startswith("---"))
            for line in hunk.splitlines()
        )
    ]


def _changed_diff_lines(hunk: str) -> list[str]:
    return [
        line[1:].strip()
        for line in hunk.splitlines()
        if (
            (line.startswith("+") and not line.startswith("+++"))
            or (line.startswith("-") and not line.startswith("---"))
        )
    ]


def _diff_hunks_match_only_markers(
    diff_text: str,
    hunk_markers: tuple[str, ...],
    changed_line_markers: tuple[str, ...],
) -> bool:
    changed_hunks = _changed_diff_hunks(diff_text)
    if not changed_hunks:
        return False
    if not all(any(marker in hunk for marker in hunk_markers) for hunk in changed_hunks):
        return False
    effective_changed_line_markers = changed_line_markers or hunk_markers
    return all(
        any(marker in changed_line for marker in effective_changed_line_markers)
        for hunk in changed_hunks
        for changed_line in _changed_diff_lines(hunk)
    )


def _pytest_selector_hints_for_diff(path: str, diff_text: str) -> list[str]:
    selectors: list[str] = []
    for hunk_markers, changed_line_markers, hinted_selectors in _PYTEST_DIFF_SELECTOR_HINTS.get(path, ()):
        if _diff_hunks_match_only_markers(diff_text, hunk_markers, changed_line_markers):
            selectors.extend(hinted_selectors)
    return selectors


def pytest_selector_hints_for_diff(path: str, diff_text: str) -> list[str]:
    """Return public pytest selectors when a diff is known to be narrow."""
    return _pytest_selector_hints_for_diff(path, diff_text)


def _pytest_selector_path(selector: str) -> str:
    return selector.split("::", 1)[0]


def _runtime_targeted_tests_for_path(
    path: str,
    repo_root: Path | None,
) -> tuple[str, ...]:
    candidates = _RUNTIME_TARGETED_TESTS.get(path, ())
    if repo_root is None:
        return candidates
    return tuple(
        selector
        for selector in candidates
        if (repo_root / _pytest_selector_path(selector)).exists()
    )


def _select_pytest_gate_files(changed_files: list[str], repo_root: Path | None = None) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for path in changed_files:
        normalized = path.replace("\\", "/")
        candidates = []
        if _is_pytest_gate_file(normalized):
            selector_hints: list[str] = []
            if repo_root is not None:
                selector_hints = pytest_selector_hints_for_diff(
                    normalized,
                    pytest_gate_diff_text(repo_root, normalized),
                )
            candidates.extend(selector_hints or [normalized])
        candidates.extend(_runtime_targeted_tests_for_path(normalized, repo_root))
        for candidate in candidates:
            if candidate not in seen:
                selected.append(candidate)
                seen.add(candidate)
    return selected


def select_pytest_gate_files(changed_files: list[str], repo_root: Path | None = None) -> list[str]:
    """Public selector seam used by tests and commit-packet refresh paths."""
    return _select_pytest_gate_files(changed_files, repo_root)


def select_private_attr_gate_files(changed_files: list[str]) -> list[str]:
    """Return wave-owned Python test files that should trigger anti-cheat."""
    return sorted({
        path.replace("\\", "/")
        for path in changed_files
        if _is_pytest_gate_file(path.replace("\\", "/"))
    })


def _resolve_private_attr_checker(repo_root: Path) -> Path | None:
    """Resolve the tracked private-attr checker from repo or executor paths."""
    candidates = [
        repo_root / "mu" / "tools" / "checks" / "linters" / "check_private_attr_access.py",
        repo_root / "tools" / "checks" / "linters" / "check_private_attr_access.py",
        SCRIPT_DIR.parents[1] / "tools" / "checks" / "linters" / "check_private_attr_access.py",
        SCRIPT_DIR.parents[2] / "tools" / "checks" / "linters" / "check_private_attr_access.py",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def run_private_attr_gate(
    repo_root: Path,
    changed_files: list[str],
    *,
    timeout: int = 120,
) -> dict[str, Any]:
    """Run the existing private-attr checker for wave-owned Python tests."""
    gate_files = select_private_attr_gate_files(changed_files)
    if not gate_files:
        return {
            "passed": True,
            "skipped": True,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "test_files": [],
        }
    checker = _resolve_private_attr_checker(repo_root)
    if checker is None:
        return {
            "passed": False,
            "skipped": False,
            "exit_code": 127,
            "stdout": "",
            "stderr": "private-attr checker not found",
            "test_files": gate_files,
        }
    try:
        completed = subprocess.run(
            [sys.executable, str(checker), str(repo_root), *gate_files],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
        return {
            "passed": completed.returncode == 0,
            "skipped": False,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "test_files": gate_files,
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "skipped": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"private-attr checker timed out after {timeout}s",
            "test_files": gate_files,
        }


def private_attr_gate_summary(gate_result: dict[str, Any], *, reentry: bool) -> str:
    output = "\n".join(
        part
        for part in (
            str(gate_result.get("stdout") or ""),
            str(gate_result.get("stderr") or ""),
        )
        if part
    ).strip()
    if len(output) > 2500:
        output = output[-2500:]
    test_files = gate_result.get("test_files") or []
    file_summary = ", ".join(str(path) for path in test_files[:8])
    if len(test_files) > 8:
        file_summary += f", ... (+{len(test_files) - 8} more)"
    prefix = "Re-entry " if reentry else ""
    message = (
        f"{prefix}private-attr test-integrity gate FAILED "
        f"(exit={gate_result.get('exit_code')}). "
        "Python test files in the wave-owned diff must not access single-underscore helpers. "
        "Use public seams or public commit-packet refresh paths instead."
    )
    if file_summary:
        message += f" Triggering test file(s): {file_summary}."
    if output:
        message += f"\n\nChecker output:\n{output}"
    return message


_NON_GATE_TEST_DOMAINS = (
    "tests/engine/", "tests/parity/", "tests/structural/", "tests/tools/", "tests/docs/",
    "mu/tests/engine/", "mu/tests/parity/", "mu/tests/structural/", "mu/tests/tools/", "mu/tests/docs/",
)

_STRUCTURAL_ARTIFACT_PREFIXES = (
    "mu/host/",
    "mu/programs/",
    "mu/substrate/",
    "mu/closures/",
    "mu/tests/l4_gates/",
    "tests/l4_gates/",
)

_EXPLICIT_WORKLOAD_TARGET_RE = re.compile(
    r"^\s*workload_target:\s*`?([A-Za-z0-9_.-]+)`?",
    re.MULTILINE,
)


def _select_non_gate_test_files(paths: list[str]) -> list[str]:
    return [
        path for path in paths
        if _is_pytest_gate_file(path) and path.startswith(_NON_GATE_TEST_DOMAINS)
    ]


def _infer_structural_workload_target(changed_files: list[str], plan_content: str) -> str:
    """Infer the least-surprising L4 structural workload target from wave scope."""
    explicit_target = _EXPLICIT_WORKLOAD_TARGET_RE.search(plan_content or "")
    if explicit_target:
        return explicit_target.group(1).strip("` .")
    scope_text = "\n".join(changed_files) + "\n" + (plan_content or "")
    if (
        "attempt_trace" in scope_text
        or "stage0_vm" in scope_text
        or "step_mu.py" in scope_text
    ):
        return "host_debt_reduction"
    if "rcx_engine" in scope_text or "engine_pipeline" in scope_text:
        return "host_debt_reduction"
    if "recurrence" in scope_text or "exhaustion" in scope_text:
        return "recurrence_exhaustion"
    if "seed_auto_execution" in scope_text:
        return "seed_auto_execution"
    if "execution_layer_truth" in scope_text:
        return "execution_layer_truth"
    if "coverage" in scope_text:
        return "host_debt_reduction"
    return "ontology_promotion"


def _summarize_structural_artifacts(changed_files: list[str], *, limit: int = 8) -> str:
    artifacts = [
        path for path in changed_files
        if path.startswith(_STRUCTURAL_ARTIFACT_PREFIXES)
    ]
    if not artifacts:
        artifacts = list(changed_files)
    visible = artifacts[:limit]
    suffix = ""
    if len(artifacts) > limit:
        suffix = f"; +{len(artifacts) - limit} more structural artifact(s)"
    return "; ".join(visible) + suffix


def _build_structural_post_gate_sweep(test_files: list[str], changed_files: list[str]) -> str:
    non_gate_tests = _select_non_gate_test_files(test_files) or _select_non_gate_test_files(changed_files)
    if non_gate_tests:
        return "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short " + " ".join(non_gate_tests)
    return "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/structural/ mu/tests/parity/"


def _phase_b_scope_has_runtime_substrate_file(changed_files: list[str]) -> bool:
    return any(path.startswith(_MAINTENANCE_FORBIDDEN_PREFIXES) for path in changed_files)


def _phase_b_scope_has_control_plane_tooling_file(changed_files: list[str]) -> bool:
    return any(path.startswith(_CONTROL_PLANE_TOOLING_PREFIXES) for path in changed_files)


def _phase_b_scope_is_tracker_or_packet_only(changed_files: list[str]) -> bool:
    scoped = [path for path in changed_files if path]
    if not scoped:
        return False
    packet_prefixes = (
        "reports/control_plane/",
        "reports/l4_wave_indicators/",
        "reports/deferred/",
    )
    return all(path == "TASKS.md" or path.startswith(packet_prefixes) for path in scoped)


def _plan_declares_classless_comment_only_runtime_override(plan_content: str) -> bool:
    text = (plan_content or "").lower().replace("`", "")
    return (
        "classless founder_override comment-only runtime override" in text
        or "classless founder_override comment/docstring-only runtime override" in text
    )


def _plan_declares_l4_enabler_runtime_text_override(plan_content: str) -> bool:
    """Return true for locked enabler packets that scope runtime edits to text."""
    text = (plan_content or "").lower().replace("`", "")
    if "class: l4_enabler" not in text:
        return False
    text_scope = any(
        phrase in text
        for phrase in (
            "comment, source-lock, and marker wording",
            "comment/source-lock",
            "comment-only",
            "docstring-only",
            "wording/proof-class alignment",
            "source-lock or marker-truth test expectations",
        )
    )
    no_behavior = any(
        phrase in text
        for phrase in (
            "behavior is not in scope",
            "not runtime behavior change",
            "zero executable runtime",
            "no runtime behavior",
            "without runtime behavior",
        )
    )
    return text_scope and no_behavior


def _plan_declares_routing_boundary(plan_content: str) -> bool:
    text = (plan_content or "").lower()
    return (
        "not an implementation packet" in text
        or "phase a routing boundary" in text
        or "control-plane phase a only" in text
        or "control plane phase a only" in text
        or "phase a rewrite may change only this packet" in text
        or "locked later phase b plan" in text
        or "cannot authorize implementation" in text
        or "does not authorize implementation" in text
        or "no phase b implementation write set is authorized" in text
        or "no phase b runtime" in text
        or "implementation is not authorized" in text
        or "does not authorize editing tasks.md or implementation files" in text
        or "do not solve the implementation" in text
        or "phase b is not authorized" in text
        or "stop before phase b implementation" in text
        or "no implementation, commit automation, or count-reduction claim is authorized" in text
        or "no-go package" in text
        or "no-go before commit readiness" in text
        or "no-go for implementation" in text
        or "no-go prerequisite stop" in text
        or "stopped before commit readiness" in text
        or "no accepted executable runtime delta" in text
    )


def _plan_declares_smaller_prerequisite_only(plan_content: str) -> bool:
    text = (plan_content or "").lower()
    return "needs a smaller prerequisite before implementation" in text


def _phase_b_declares_structural_runtime_intent(
    plan_content: str,
    routing_record: dict[str, Any] | None = None,
) -> bool:
    text_parts = [plan_content or ""]
    if routing_record:
        text_parts.extend(
            str(routing_record.get(key) or "")
            for key in ("summary", "request_for_agent", "request_for_claude", "wave_class")
        )
    text = " ".join(text_parts).lower().replace("`", "")
    return (
        "l4_structural implementation wave" in text
        or "l4_structural runtime wave" in text
    )


def _reentry_findings_indicate_runtime_pre_push_failure(findings: Any) -> bool:
    if isinstance(findings, (dict, list, tuple)):
        try:
            findings_text = json.dumps(findings, sort_keys=True)
        except TypeError:
            findings_text = str(findings)
    else:
        findings_text = str(findings or "")
    text = findings_text.lower()
    commit_gate_signal = (
        "run_pre_push_script" in text
        or "pre-push-fast failed" in text
        or "pre-push failed" in text
    )
    runtime_failure_signal = any(
        token in text
        for token in (
            "tests/structural/",
            "tests/parity/",
            "mu/tests/structural/",
            "mu/tests/parity/",
            "mu/host/",
            "eval_step.js",
        )
    )
    return commit_gate_signal and runtime_failure_signal


def _effective_phase_b_tracker_wave_class(
    wave_class: str,
    *,
    plan_content: str,
    changed_files: list[str],
) -> str:
    """Classify final package scope from the actual diff before packet prose.

    L4_STRUCTURAL is reserved for executable runtime/substrate deltas plus L4 gate
    evidence. A control-plane packet that only selects a later structural route is
    an enabler, even when the selected future route is structural.
    """
    if _phase_b_scope_has_runtime_substrate_file(changed_files):
        if _plan_declares_l4_enabler_runtime_text_override(plan_content):
            return "L4_ENABLER"
        if _plan_declares_classless_comment_only_runtime_override(plan_content):
            if _phase_b_scope_has_control_plane_tooling_file(changed_files):
                return "L4_ENABLER"
            return ""
        return "L4_STRUCTURAL"
    if wave_class != "L4_STRUCTURAL":
        return wave_class
    if _plan_declares_routing_boundary(plan_content):
        return "L4_ENABLER"
    if _plan_declares_smaller_prerequisite_only(plan_content):
        return wave_class
    if _phase_b_scope_is_tracker_or_packet_only(changed_files):
        return "L4_ENABLER"
    return wave_class


def build_phase_b_tracker_note(
    *,
    wave_id: str,
    task_id: str,
    wave_class: str = "L4_ENABLER",
    target_gate_id: str,
    plan_path: str,
    plan_content: str = "",
    changed_files: list[str],
    test_files: list[str],
    receipt_path: str,
    bridge_rounds: int,
    reentry: bool,
    post_gate_contract_sweep: str = "",
    founder_override: str = "",
    unblocks_wave_id: str = "",
    unblocks_runtime_blocker: str = "",
    pre_supervisor: bool = False,
) -> str:
    """Render a Phase B tracker note through the public package-class seam."""
    effective_wave_class = _effective_phase_b_tracker_wave_class(
        wave_class,
        plan_content=plan_content,
        changed_files=changed_files,
    )
    return _build_phase_b_tracker_note(
        wave_id=wave_id,
        task_id=task_id,
        wave_class=effective_wave_class,
        target_gate_id=target_gate_id,
        plan_path=plan_path,
        plan_content=plan_content,
        changed_files=changed_files,
        test_files=test_files,
        receipt_path=receipt_path,
        bridge_rounds=bridge_rounds,
        reentry=reentry,
        post_gate_contract_sweep=post_gate_contract_sweep,
        founder_override=founder_override,
        unblocks_wave_id=unblocks_wave_id,
        unblocks_runtime_blocker=unblocks_runtime_blocker,
        pre_supervisor=pre_supervisor,
    )


def _summarize_bounded_output(label: str, text: str, *, limit: int) -> list[str]:
    content = text.strip()
    if not content:
        return []
    if limit <= 0:
        return [f"{label}: <{len(content)} char(s) captured; display limit is 0>"]
    if len(content) <= limit:
        return [f"{label}: {content}"]

    head_limit = max(1, limit // 2)
    tail_limit = max(1, limit - head_limit)
    omitted = len(content) - head_limit - tail_limit
    return [
        f"{label}_head: {content[:head_limit]}",
        f"{label}_omitted: {omitted} char(s)",
        f"{label}_tail: {content[-tail_limit:]}",
    ]


def _summarize_pytest_failure(result: dict[str, Any], *, stdout_limit: int = 1000, stderr_limit: int = 1000) -> str:
    """Build a bounded pytest failure summary without dropping tail assertions."""
    stdout = result.get("stdout") or ""
    stderr = result.get("stderr") or ""
    parts: list[str] = []
    parts.extend(_summarize_bounded_output("stdout", stdout, limit=stdout_limit))
    parts.extend(_summarize_bounded_output("stderr", stderr, limit=stderr_limit))
    return " ".join(parts) if parts else "no stdout/stderr captured"


# ---------------------------------------------------------------------------
# State persistence for resume
# ---------------------------------------------------------------------------

STATE_FILE_NAME = "phase_b_state.json"
BRANCH_STASH_STATE_FILE_NAME = "phase_b_branch_stash.json"
STATE_LOAD_ERROR_KEY = "__phase_b_state_load_error__"
PRIVATE_ATTR_QUESTION_STEPS = {
    "private_attr_remediation_question_for_founder",
    "reentry_private_attr_remediation_question_for_founder",
}
RESUMABLE_STATE_STEPS = {
    "implementer",
    "agent_review",
    "bridge_fix_pending",
    "bridge_converged",
    "private_attr_remediation_pending_review",
    "needs_phase_b_reentry",
    "reentry_private_attr_remediation_pending_review",
    *PRIVATE_ATTR_QUESTION_STEPS,
}


def _state_file_path(repo_root: Path) -> Path:
    return agent_bus_path(repo_root, _active_bus_dir(), "executors", STATE_FILE_NAME)


def _branch_stash_state_file_path(repo_root: Path) -> Path:
    return agent_bus_path(repo_root, _active_bus_dir(), "executors", BRANCH_STASH_STATE_FILE_NAME)


def _atomic_write_text(path: Path, content: str, *, default_mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = default_mode
    if path.exists():
        try:
            mode = stat.S_IMODE(os.stat(path).st_mode)
        except OSError:
            mode = default_mode

    tmp_path: Path | None = None
    fd: int | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            fd = None
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
        tmp_path = None
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _write_branch_stash_state(repo_root: Path, state: dict[str, Any]) -> Path:
    state_path = _branch_stash_state_file_path(repo_root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return state_path


def _load_branch_stash_state(repo_root: Path) -> dict[str, Any] | None:
    state_path = _branch_stash_state_file_path(repo_root)
    try:
        raw = state_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "status": "invalid",
            "state_path": agent_bus_relpath(_active_bus_dir(), "executors", BRANCH_STASH_STATE_FILE_NAME),
            "output": "branch-switch stash recovery state is not valid JSON",
        }
    if not isinstance(state, dict):
        return {
            "status": "invalid",
            "state_path": agent_bus_relpath(_active_bus_dir(), "executors", BRANCH_STASH_STATE_FILE_NAME),
            "output": "branch-switch stash recovery state must be a JSON object",
        }
    return state


def _clear_branch_stash_state(repo_root: Path) -> None:
    try:
        _branch_stash_state_file_path(repo_root).unlink()
    except FileNotFoundError:
        return


def _git_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())


def _git_binary_output(repo_root: Path, args: list[str]) -> bytes | None:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _git_revision_exists(repo_root: Path, revision: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", revision],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _reverse_stash_patch_applies(
    repo_root: Path,
    left_revision: str,
    right_revision: str,
    *,
    cached: bool,
) -> bool:
    patch = _git_binary_output(
        repo_root,
        ["diff", "--binary", left_revision, right_revision],
    )
    if patch is None:
        return False
    if not patch:
        return True
    apply_cmd = ["git", "apply", "--reverse", "--check"]
    if cached:
        apply_cmd.insert(2, "--cached")
    apply_result = subprocess.run(
        apply_cmd,
        cwd=str(repo_root),
        input=patch,
        capture_output=True,
    )
    return apply_result.returncode == 0


def _branch_switch_stash_appears_applied(
    repo_root: Path,
    stash_record: dict[str, str],
) -> bool:
    """Prove a restore_started stash already reached the worktree/index."""
    stash_ref = stash_record["stash_ref"]
    base_revision = f"{stash_ref}^1"
    index_revision = f"{stash_ref}^2"
    untracked_revision = f"{stash_ref}^3"
    empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"

    if not _git_revision_exists(repo_root, base_revision):
        return False
    if not _git_revision_exists(repo_root, index_revision):
        return False
    if not _reverse_stash_patch_applies(
        repo_root,
        base_revision,
        index_revision,
        cached=True,
    ):
        return False
    if not _reverse_stash_patch_applies(
        repo_root,
        index_revision,
        stash_ref,
        cached=False,
    ):
        return False
    if _git_revision_exists(repo_root, untracked_revision):
        return _reverse_stash_patch_applies(
            repo_root,
            empty_tree,
            untracked_revision,
            cached=False,
        )
    return True


def _find_stash_record_for_marker(repo_root: Path, marker: str) -> dict[str, str] | None:
    list_result = subprocess.run(
        ["git", "stash", "list", "--format=%gd%x00%H%x00%s"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if list_result.returncode != 0:
        return None
    for line in list_result.stdout.splitlines():
        parts = line.split("\x00", 2)
        if len(parts) != 3:
            continue
        stash_ref, stash_oid, subject = parts
        if stash_ref and stash_oid and marker in subject:
            return {
                "stash_ref": stash_ref,
                "stash_oid": stash_oid,
                "stash_subject": subject,
            }
    return None


def _resolve_branch_switch_stash_record(
    repo_root: Path,
    stash_state: dict[str, Any],
) -> tuple[dict[str, str] | None, str | None]:
    marker = str(stash_state.get("marker") or "").strip()
    if not marker:
        return None, "branch-switch stash recovery state is missing marker"

    stash_record = _find_stash_record_for_marker(repo_root, marker)
    if not stash_record:
        return None, f"branch-switch stash recovery marker was not found in git stash list: {marker}"

    expected_oid = str(stash_state.get("stash_oid") or "").strip()
    if expected_oid and stash_record["stash_oid"] != expected_oid:
        detail = (
            "branch-switch stash recovery object id mismatch for marker "
            f"{marker}: expected {expected_oid}, found {stash_record['stash_oid']}"
        )
        stash_state.update({
            "status": "stash_oid_mismatch",
            "output": detail,
        })
        _write_branch_stash_state(repo_root, stash_state)
        return None, detail

    prior_status = str(stash_state.get("status") or "").strip()
    resolved_status = prior_status if prior_status in {
        "restore_started",
        "restore_applied",
        "drop_failed",
    } else "stashed"
    stash_state.update({
        "status": resolved_status,
        "stash_ref": stash_record["stash_ref"],
        "stash_oid": stash_record["stash_oid"],
        "stash_subject": stash_record["stash_subject"],
    })
    _write_branch_stash_state(repo_root, stash_state)
    return stash_record, None


def _pop_branch_switch_stash_record(
    repo_root: Path,
    stash_state: dict[str, Any],
    stash_record: dict[str, str],
) -> str | None:
    stash_ref = stash_record["stash_ref"]
    apply_cmd = ["git", "stash", "apply", "--index", stash_ref]
    stash_state.update({
        "status": "restore_started",
        "stash_ref": stash_ref,
        "stash_oid": stash_record["stash_oid"],
        "stash_subject": stash_record["stash_subject"],
        "restore_started_at": datetime.now(timezone.utc).isoformat(),
    })
    _write_branch_stash_state(repo_root, stash_state)

    apply_result = subprocess.run(
        apply_cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if apply_result.returncode != 0:
        stash_state.update({
            "status": "pop_failed",
            "returncode": apply_result.returncode,
            "stash_ref": stash_ref,
            "stash_oid": stash_record["stash_oid"],
            "stash_subject": stash_record["stash_subject"],
            "output": _git_output(apply_result),
        })
        _write_branch_stash_state(repo_root, stash_state)
        return (
            f"{' '.join(apply_cmd)} failed; recovery state preserved at "
            f"{agent_bus_relpath(_active_bus_dir(), 'executors', BRANCH_STASH_STATE_FILE_NAME)}: "
            f"{_git_output(apply_result) or apply_result.returncode}"
        )
    stash_state.update({
        "status": "restore_applied",
        "returncode": apply_result.returncode,
        "stash_ref": stash_ref,
        "stash_oid": stash_record["stash_oid"],
        "stash_subject": stash_record["stash_subject"],
        "apply_output": _git_output(apply_result),
        "restore_applied_at": datetime.now(timezone.utc).isoformat(),
    })
    _write_branch_stash_state(repo_root, stash_state)

    drop_error = _drop_branch_switch_stash_record(repo_root, stash_state)
    if drop_error:
        return drop_error
    _clear_branch_stash_state(repo_root)
    return None


def _complete_already_applied_branch_switch_stash(
    repo_root: Path,
    stash_state: dict[str, Any],
    stash_record: dict[str, str],
) -> tuple[bool, str | None]:
    if not _branch_switch_stash_appears_applied(repo_root, stash_record):
        return False, None

    stash_state.update({
        "status": "restore_applied",
        "stash_ref": stash_record["stash_ref"],
        "stash_oid": stash_record["stash_oid"],
        "stash_subject": stash_record["stash_subject"],
        "apply_output": (
            "branch-switch stash restore was already present in the "
            "worktree/index; reverse patch checks proved restart idempotence"
        ),
        "restore_applied_at": datetime.now(timezone.utc).isoformat(),
    })
    _write_branch_stash_state(repo_root, stash_state)

    drop_error = _drop_branch_switch_stash_record(repo_root, stash_state)
    if drop_error:
        return True, drop_error
    _clear_branch_stash_state(repo_root)
    return True, None


def _drop_branch_switch_stash_record(repo_root: Path, stash_state: dict[str, Any]) -> str | None:
    marker = str(stash_state.get("marker") or "").strip()
    stash_record = _find_stash_record_for_marker(repo_root, marker) if marker else None
    if not stash_record:
        stash_state.update({
            "status": "restore_dropped",
            "drop_output": "branch-switch stash marker is already absent from git stash list",
            "restore_dropped_at": datetime.now(timezone.utc).isoformat(),
        })
        _write_branch_stash_state(repo_root, stash_state)
        return None

    stash_ref = stash_record["stash_ref"]
    drop_cmd = ["git", "stash", "drop", stash_ref]
    drop_result = subprocess.run(
        drop_cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if drop_result.returncode != 0:
        if marker and _find_stash_record_for_marker(repo_root, marker) is None:
            stash_state.update({
                "status": "restore_dropped",
                "drop_output": _git_output(drop_result),
                "restore_dropped_at": datetime.now(timezone.utc).isoformat(),
            })
            _write_branch_stash_state(repo_root, stash_state)
            return None
        stash_state.update({
            "status": "drop_failed",
            "returncode": drop_result.returncode,
            "stash_ref": stash_ref,
            "stash_oid": stash_record["stash_oid"],
            "stash_subject": stash_record["stash_subject"],
            "output": _git_output(drop_result),
        })
        _write_branch_stash_state(repo_root, stash_state)
        return (
            f"{' '.join(drop_cmd)} failed after branch-switch stash restore; "
            "recovery state preserved at "
            f"{agent_bus_relpath(_active_bus_dir(), 'executors', BRANCH_STASH_STATE_FILE_NAME)}: "
            f"{_git_output(drop_result) or drop_result.returncode}"
        )

    stash_state.update({
        "status": "restore_dropped",
        "returncode": drop_result.returncode,
        "stash_ref": stash_ref,
        "stash_oid": stash_record["stash_oid"],
        "stash_subject": stash_record["stash_subject"],
        "drop_output": _git_output(drop_result),
        "restore_dropped_at": datetime.now(timezone.utc).isoformat(),
    })
    _write_branch_stash_state(repo_root, stash_state)
    return None


def _stash_dirty_worktree_for_branch_switch(
    repo_root: Path,
    *,
    current_branch: str,
    feature_branch: str,
) -> tuple[dict[str, Any] | None, str | None]:
    marker = f"phase_b:{feature_branch}:{uuid.uuid4().hex}"
    state = {
        "status": "pending",
        "marker": marker,
        "current_branch": current_branch,
        "feature_branch": feature_branch,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_branch_stash_state(repo_root, state)
    stash_result = subprocess.run(
        ["git", "stash", "push", "--include-untracked", "-m", marker],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    combined_output = _git_output(stash_result)
    if stash_result.returncode != 0:
        state.update({
            "status": "stash_failed",
            "returncode": stash_result.returncode,
            "output": combined_output,
        })
        _write_branch_stash_state(repo_root, state)
        return None, f"git stash push failed before branch checkout: {combined_output or stash_result.returncode}"
    if "No local changes" in combined_output:
        _clear_branch_stash_state(repo_root)
        return None, None

    stash_record = _find_stash_record_for_marker(repo_root, marker)
    if not stash_record:
        state.update({
            "status": "stash_ref_missing",
            "output": combined_output,
        })
        _write_branch_stash_state(repo_root, state)
        return None, (
            "git stash push reported saved changes, but the created stash ref could not be found; "
            f"recovery marker: {marker}"
        )
    state.update({
        "status": "stashed",
        "stash_ref": stash_record["stash_ref"],
        "stash_oid": stash_record["stash_oid"],
        "stash_subject": stash_record["stash_subject"],
        "output": combined_output,
    })
    _write_branch_stash_state(repo_root, state)
    return state, None


def _restore_branch_switch_stash(repo_root: Path, stash_state: dict[str, Any]) -> str | None:
    stash_record, resolve_error = _resolve_branch_switch_stash_record(repo_root, stash_state)
    if resolve_error:
        return resolve_error
    if stash_record is None:
        return "branch-switch stash recovery record resolution failed"
    if str(stash_state.get("status") or "").strip() == "restore_started":
        completed, completion_error = _complete_already_applied_branch_switch_stash(
            repo_root,
            stash_state,
            stash_record,
        )
        if completed:
            return completion_error
    return _pop_branch_switch_stash_record(repo_root, stash_state, stash_record)


def _restore_pending_branch_switch_stash(repo_root: Path) -> str | None:
    stash_state = _load_branch_stash_state(repo_root)
    if stash_state is None:
        return None

    status = str(stash_state.get("status") or "").strip()
    if status == "restore_dropped":
        _clear_branch_stash_state(repo_root)
        return None
    if status in {"restore_applied", "drop_failed"}:
        drop_error = _drop_branch_switch_stash_record(repo_root, stash_state)
        if drop_error:
            return drop_error
        _clear_branch_stash_state(repo_root)
        return None
    if status == "pop_failed":
        return (
            "branch-switch stash recovery previously failed; resolve the worktree conflict "
            f"or restore the stash recorded in "
            f"{agent_bus_relpath(_active_bus_dir(), 'executors', BRANCH_STASH_STATE_FILE_NAME)}"
        )
    if status in {"invalid", "stash_failed", "stash_oid_mismatch"}:
        detail = str(stash_state.get("output") or status)
        return (
            "branch-switch stash recovery is blocked by persisted state at "
            f"{agent_bus_relpath(_active_bus_dir(), 'executors', BRANCH_STASH_STATE_FILE_NAME)}: "
            f"{detail}"
        )

    marker = str(stash_state.get("marker") or "").strip()
    if status == "pending" and marker:
        stash_record, resolve_error = _resolve_branch_switch_stash_record(repo_root, stash_state)
        if stash_record:
            return _pop_branch_switch_stash_record(repo_root, stash_state, stash_record)
        if resolve_error and "was not found in git stash list" not in resolve_error:
            return resolve_error
        _clear_branch_stash_state(repo_root)
        return None

    if marker:
        return _restore_branch_switch_stash(repo_root, stash_state)

    if str(stash_state.get("stash_ref") or "").strip():
        return "branch-switch stash recovery state has stash_ref but no marker; refusing to pop mutable stash ref"

    return (
        "branch-switch stash recovery state has no recoverable stash_ref or marker at "
        f"{agent_bus_relpath(_active_bus_dir(), 'executors', BRANCH_STASH_STATE_FILE_NAME)}"
    )


def _checkout_feature_branch_from_protected_branch(
    repo_root: Path,
    *,
    current_branch: str,
    feature_branch: str,
    branch_exists: bool,
    log: Callable[[str], None],
) -> str | None:
    stash_state, stash_error = _stash_dirty_worktree_for_branch_switch(
        repo_root,
        current_branch=current_branch,
        feature_branch=feature_branch,
    )
    if stash_error:
        return stash_error

    if branch_exists:
        log(f"Step 2.5: Checking out existing feature branch {feature_branch}")
        checkout_cmd = ["git", "checkout", feature_branch]
    else:
        log(f"Step 2.5: Creating feature branch {feature_branch}")
        checkout_cmd = ["git", "checkout", "-b", feature_branch]
    checkout_result = subprocess.run(
        checkout_cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    if checkout_result.returncode != 0:
        restore_error = _restore_branch_switch_stash(repo_root, stash_state) if stash_state else None
        checkout_error = _git_output(checkout_result) or str(checkout_result.returncode)
        if restore_error:
            return f"Branch checkout failed: {checkout_error}; additionally, {restore_error}"
        return f"Branch checkout failed: {checkout_error}"

    if stash_state:
        restore_error = _restore_branch_switch_stash(repo_root, stash_state)
        if restore_error:
            return f"Branch checkout succeeded, but dirty worktree restore failed: {restore_error}"
    return None


def _save_state(repo_root: Path, state: dict[str, Any]) -> Path:
    """Persist executor state to disk for resume capability."""
    state_path = _state_file_path(repo_root)
    try:
        _atomic_write_text(state_path, json.dumps(state, indent=2) + "\n")
    except OSError as exc:
        raise PhaseBExecutorError(
            f"atomic Phase B state replacement failed for "
            f"{agent_bus_relpath(_active_bus_dir(), 'executors', STATE_FILE_NAME)}: {exc}"
        ) from exc
    return state_path


def _state_load_error(error_type: str, detail: str) -> dict[str, Any]:
    return {
        STATE_LOAD_ERROR_KEY: True,
        "status": "error",
        "step": "load_state",
        "state_error": error_type,
        "state_path": agent_bus_relpath(_active_bus_dir(), "executors", STATE_FILE_NAME),
        "errors": [detail],
    }


def _is_state_load_error(state: Any) -> bool:
    return isinstance(state, dict) and bool(state.get(STATE_LOAD_ERROR_KEY))


def _state_missing_fields_error(
    state_path: Path,
    *,
    fields: list[str],
    completed_step: str | None = None,
) -> dict[str, Any]:
    fields_text = ", ".join(fields)
    step_text = f" for completed_step={completed_step!r}" if completed_step else ""
    return _state_load_error(
        "incomplete",
        "Phase B checkpoint is incomplete"
        f"{step_text}; missing or invalid field(s): {fields_text}. "
        f"Refusing mutable replay from {state_path}.",
    )


def _valid_state_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_state_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_loaded_state_container(state_path: Path, state: dict[str, Any]) -> dict[str, Any] | None:
    missing: list[str] = []
    if not _valid_state_string(state.get("plan_path")):
        missing.append("plan_path")
    if missing:
        return _state_missing_fields_error(state_path, fields=missing)
    return None


def _validate_resumable_state_shape(state_path: Path, state: dict[str, Any]) -> dict[str, Any] | None:
    missing: list[str] = []
    completed_step = state.get("completed_step")
    if not _valid_state_string(completed_step):
        missing.append("completed_step")
    if not _valid_state_string(state.get("wave_id")):
        missing.append("wave_id")
    if not _valid_state_int(state.get("bridge_rounds")):
        missing.append("bridge_rounds")
    if missing:
        return _state_missing_fields_error(state_path, fields=missing)

    completed_step = str(completed_step).strip()
    bridge_round_step = completed_step.startswith("bridge_round_")
    if completed_step not in RESUMABLE_STATE_STEPS and not bridge_round_step:
        return _state_load_error(
            "unknown_step",
            "Phase B checkpoint has unrecognized completed_step "
            f"{completed_step!r}; refusing mutable replay from {state_path}.",
        )
    if bridge_round_step:
        try:
            round_num = int(completed_step.removeprefix("bridge_round_"))
        except ValueError:
            round_num = 0
        if round_num <= 0:
            return _state_load_error(
                "unknown_step",
                "Phase B checkpoint has invalid bridge_round completed_step "
                f"{completed_step!r}; refusing mutable replay from {state_path}.",
            )
    if completed_step == "bridge_fix_pending":
        step_missing: list[str] = []
        if not _valid_state_int(state.get("current_bridge_round")) or state.get("current_bridge_round", 0) <= 0:
            step_missing.append("current_bridge_round")
        if not _valid_state_string(state.get("bridge_fix_findings")):
            step_missing.append("bridge_fix_findings")
        if step_missing:
            return _state_missing_fields_error(
                state_path,
                fields=step_missing,
                completed_step=completed_step,
            )
    if completed_step in PRIVATE_ATTR_QUESTION_STEPS:
        terminal_result = state.get("terminal_result")
        if not isinstance(terminal_result, dict) or terminal_result.get("status") != "question_for_founder":
            return _state_missing_fields_error(
                state_path,
                fields=["terminal_result"],
                completed_step=completed_step,
            )
    return None


def _state_load_error_result(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "error",
        "step": "load_state",
        "state_error": state.get("state_error", "invalid"),
        "state_path": state.get(
            "state_path",
            agent_bus_relpath(_active_bus_dir(), "executors", STATE_FILE_NAME),
        ),
        "errors": list(state.get("errors") or ["Phase B checkpoint is invalid"]),
    }


def _saved_state_matches_invocation(saved_plan: Any, plan_path: str | None) -> bool:
    return saved_plan == plan_path


def _state_plan_mismatch_result(saved_state: dict[str, Any], plan_path: str | None) -> dict[str, Any]:
    saved_plan = saved_state.get("plan_path")
    return {
        "status": "error",
        "step": "load_state",
        "state_error": "plan_mismatch",
        "state_path": agent_bus_relpath(_active_bus_dir(), "executors", STATE_FILE_NAME),
        "errors": [
            "Phase B checkpoint plan_path does not match this invocation; "
            "refusing mutable replay from a mismatched checkpoint "
            f"(saved={saved_plan!r}, requested={plan_path!r})."
        ],
    }


def _private_attr_question_result_from_state(saved_state: dict[str, Any]) -> dict[str, Any]:
    terminal_result = saved_state.get("terminal_result")
    if isinstance(terminal_result, dict):
        result = dict(terminal_result)
    else:
        result = {
            "status": "question_for_founder",
            "step": saved_state.get("question_step", "private_attr_bridge_review"),
            "errors": list(saved_state.get("errors") or [
                "Bridge returned QUESTION after private-attr remediation. Founder input required."
            ]),
        }
    result["resumed_from"] = saved_state.get("completed_step")
    result["terminal_checkpoint"] = agent_bus_relpath(
        _active_bus_dir(),
        "executors",
        STATE_FILE_NAME,
    )
    return result


def _load_state(repo_root: Path) -> dict[str, Any] | None:
    """Load persisted executor state, or None if not found."""
    state_path = _state_file_path(repo_root)
    try:
        raw = state_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        return _state_load_error(
            "unreadable",
            f"Phase B checkpoint is unreadable; refusing mutable replay: {state_path}: {exc}",
        )
    try:
        state = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _state_load_error(
            "malformed_json",
            f"Phase B checkpoint is malformed or torn; refusing mutable replay: {state_path}: {exc}",
        )
    if not isinstance(state, dict):
        return _state_load_error(
            "non_object",
            f"Phase B checkpoint must be a JSON object; refusing mutable replay: {state_path}",
        )
    shape_error = _validate_loaded_state_container(state_path, state)
    if shape_error is not None:
        return shape_error
    return state


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


def _normalize_plan_metadata_line(line: str) -> str:
    """Normalize plan metadata lines by stripping common Markdown wrappers."""
    clean = line.replace("**", "").strip()
    if clean.startswith(("- ", "* ")):
        clean = clean[2:].strip()
    elif re.match(r"^\d+\.\s+", clean):
        clean = re.sub(r"^\d+\.\s+", "", clean, count=1).strip()
    if clean.startswith("`") and clean.endswith("`") and len(clean) >= 2:
        clean = clean[1:-1].strip()
    return clean


def _extract_plan_metadata_value(
    line: str,
    prefixes: tuple[str, ...],
) -> tuple[str | None, str | None]:
    """Return canonical and narrative metadata values for one plan line.

    Canonical Task/Wave identity must come from a real top-level packet header.
    Indented prose is treated as narrative only so body text cannot authorize
    the same-wave task_id exception.
    """
    if line.startswith(prefixes):
        value = line.split(":", 1)[1].strip()
        if value.startswith("`") and value.endswith("`") and len(value) >= 2:
            value = value[1:-1].strip()
        return value, None
    clean = _normalize_plan_metadata_line(line)
    if clean.startswith(prefixes):
        return None, clean.split(":", 1)[1].strip()
    return None, None


def _iter_authoritative_plan_header_lines(plan_content: str) -> Iterator[str]:
    """Yield only the packet header lines that can prove canonical identity.

    For the same-wave task_id exception, authoritative Task/Wave identity must
    come from the real top-level packet header: lines before the first section
    heading and outside fenced code blocks. Body prose and fenced examples are
    informational only and must not authorize routing leniency. The only
    heading allowed inside the authoritative window is an optional top-of-file
    document title; any later ATX or setext heading closes the header scan.
    """
    in_fence = False
    saw_document_title = False
    seen_nonblank_header_content = False
    lines = plan_content.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            index += 1
            continue
        if in_fence:
            index += 1
            continue
        next_stripped = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if re.match(r"^#{1,6}\s", stripped):
            if saw_document_title or seen_nonblank_header_content:
                break
            saw_document_title = True
            seen_nonblank_header_content = True
            yield line
            index += 1
            continue
        if stripped and re.match(r"^(=+|-+)$", next_stripped):
            if saw_document_title or seen_nonblank_header_content:
                break
            saw_document_title = True
            seen_nonblank_header_content = True
            yield line
            yield lines[index + 1]
            index += 2
            continue
        yield line
        if stripped:
            seen_nonblank_header_content = True
        index += 1


def _extract_unique_canonical_plan_identity(plan_content: str) -> tuple[str, str] | None:
    """Return the packet's sole canonical Task/Wave pair, or fail closed."""
    if not plan_content:
        return None

    canonical_task_values: list[str] = []
    canonical_wave_values: list[str] = []
    for line in _iter_authoritative_plan_header_lines(plan_content):
        task_value, _ = _extract_plan_metadata_value(line, ("Task:",))
        if task_value is not None:
            canonical_task_values.append(task_value)
        wave_value, _ = _extract_plan_metadata_value(line, ("Wave ID:", "wave_id:"))
        if wave_value is not None:
            canonical_wave_values.append(wave_value)

    if len(canonical_task_values) != 1 or len(canonical_wave_values) != 1:
        return None
    task_id = canonical_task_values[0]
    wave_id = canonical_wave_values[0]
    if not task_id or not wave_id:
        return None
    return task_id, wave_id


def _extract_authoritative_plan_header_metadata(
    plan_content: str,
) -> tuple[list[str], list[str]]:
    """Return authoritative Task/Wave headers from the packet header only."""
    canonical_task_values: list[str] = []
    canonical_wave_values: list[str] = []
    for line in _iter_authoritative_plan_header_lines(plan_content):
        task_value, _ = _extract_plan_metadata_value(line, ("Task:",))
        if task_value is not None:
            canonical_task_values.append(task_value)
        wave_value, _ = _extract_plan_metadata_value(line, ("Wave ID:", "wave_id:"))
        if wave_value is not None:
            canonical_wave_values.append(wave_value)
    return canonical_task_values, canonical_wave_values


def _extract_authoritative_routed_retained_candidates(plan_content: str) -> list[str]:
    """Return top-level routed retained candidate identities from the packet header."""
    routed_candidates: list[str] = []
    for line in _iter_authoritative_plan_header_lines(plan_content):
        candidate_value, _ = _extract_plan_metadata_value(
            line,
            ("Routed retained candidate:", "routed_retained_candidate:"),
        )
        if candidate_value is not None:
            routed_candidates.append(candidate_value)
    return routed_candidates


def load_plan_packet(repo_root: Path, plan_path: str) -> dict[str, str]:
    """Load and parse key fields from a plan packet."""
    full_path = (repo_root / plan_path).resolve()
    if not full_path.is_relative_to(repo_root.resolve()):
        raise PhaseBExecutorError(f"Path traversal blocked: {plan_path}")
    if not full_path.exists():
        raise PhaseBExecutorError(f"Plan packet not found: {plan_path}")

    content = full_path.read_text(encoding="utf-8")
    result = {"path": plan_path, "content": content}

    # Phase-A-Lock resolution: packets may contain both a malformed stub
    # (e.g. "Phase-A-Lock: PLACEHOLDER" on line 1) and an implementer-added
    # canonical line (e.g. "Phase-A-Lock: LOCKED" on line 6). A naive
    # first-match reader returns PLACEHOLDER, breaking validate_inputs.
    #
    # To resolve safely, we distinguish CANONICAL lock lines (literal
    # "Phase-A-Lock:" at column 0 after optional whitespace trim) from
    # NARRATIVE lock lines (bullet/backtick/numbered forms that
    # _normalize_plan_metadata_line rewrites into canonical-looking text).
    # Narrative forms like "- `Phase-A-Lock: LOCKED`" or "1. `Phase-A-Lock:
    # LOCKED`" MUST NOT upgrade a canonical-UNLOCKED header to LOCKED, or
    # the Phase-B lock gate is weakened — any prose mentioning LOCKED in
    # the body would falsely satisfy validate_inputs.
    #
    # Rule: prefer-LOCKED applies only within canonical values. Narrative
    # values are used only as a fallback when no canonical value exists
    # (preserving the legacy markdown-bypass path tested by
    # test_markdown_bypass_lines_parse / test_late_markdown_bypass_lines_parse).
    canonical_lock_values: list[str] = []
    narrative_lock_values: list[str] = []
    canonical_task_values, canonical_wave_values = _extract_authoritative_plan_header_metadata(
        content
    )

    for line in content.splitlines():
        clean = _normalize_plan_metadata_line(line)
        stripped = line.strip()
        if stripped.startswith("Phase-A-Lock:"):
            canonical_lock_values.append(stripped.split(":", 1)[1].strip())
        elif clean.startswith("Phase-A-Lock:"):
            narrative_lock_values.append(clean.split(":", 1)[1].strip())
        if clean.startswith("Status:") and "status" not in result:
            result["status"] = clean.split(":", 1)[1].strip()
        if "founder_override" not in result:
            founder_override = _extract_founder_override_from_metadata_line(line)
            if founder_override:
                result["founder_override"] = founder_override
        if (
            clean.startswith("Unblocks wave id:") or clean.startswith("unblocks_wave_id:")
        ) and "unblocks_wave_id" not in result:
            result["unblocks_wave_id"] = clean.split(":", 1)[1].strip()
        if (
            clean.startswith("Unblocks runtime blocker:") or clean.startswith("unblocks_runtime_blocker:")
        ) and "unblocks_runtime_blocker" not in result:
            result["unblocks_runtime_blocker"] = clean.split(":", 1)[1].strip()

    # Resolve phase_a_lock: prefer canonical values over narrative values.
    # Within the chosen set, prefer LOCKED then ROUTING_RECORD_AUTHORITY,
    # falling back to first-match when neither is present.
    chosen_values = canonical_lock_values if canonical_lock_values else narrative_lock_values
    if chosen_values:
        if "LOCKED" in chosen_values:
            result["phase_a_lock"] = "LOCKED"
        elif "ROUTING_RECORD_AUTHORITY" in chosen_values:
            result["phase_a_lock"] = "ROUTING_RECORD_AUTHORITY"
        else:
            result["phase_a_lock"] = chosen_values[0]

    # Task/Wave identity is authoritative only when it appears in the real
    # packet header, before the first section heading and outside fenced code.
    # Later prose examples, grounding sections, or markdown bullets must not
    # silently become the packet's routing identity.
    if canonical_task_values:
        result["task_id"] = canonical_task_values[0]

    if canonical_wave_values:
        result["wave_id"] = canonical_wave_values[0]

    return result


def _matches_explicit_same_wave_task_id_exception(
    routing_record: dict[str, Any],
    plan: dict[str, str],
) -> bool:
    """Allow one explicit same-wave mismatch class for the recovery follow-up.

    This remains fail-closed: the only admitted mismatch is the current
    [PIPELINE-RECOVERY] routing anchor paired with a same-wave plan whose
    `Task:` field mirrors that packet's explicit `Wave ID:` and whose path is
    the tracked packet named in the routing record.
    """
    routing_task_id = str(routing_record.get("task_id", "")).strip()
    if routing_task_id != "[PIPELINE-RECOVERY]":
        return False

    canonical_identity = _extract_unique_canonical_plan_identity(
        str(plan.get("content", ""))
    )
    if canonical_identity is None:
        return False
    plan_task_id, plan_wave_id = canonical_identity
    plan_path = str(plan.get("path", "")).strip()
    routing_wave_id = str(
        routing_record.get("wave_name") or routing_record.get("wave_id") or ""
    ).strip()
    if not (plan_task_id and plan_wave_id and plan_path and routing_wave_id):
        return False
    if plan_task_id != plan_wave_id:
        return False
    if normalize_wave_id(plan_wave_id) != normalize_wave_id(routing_wave_id):
        return False

    candidates = routing_record.get("next_candidates")
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if candidate.get("bounded") is not True:
            continue
        tracked_packet = str(candidate.get("tracked_packet", "")).strip()
        candidate_wave_id = str(candidate.get("candidate", "")).strip()
        if tracked_packet != plan_path:
            continue
        if candidate_wave_id and (
            normalize_wave_id(candidate_wave_id) != normalize_wave_id(plan_wave_id)
        ):
            return False
        return True
    return False


def _is_tracked_pipeline_recovery_packet(
    routing_record: dict[str, Any],
    plan: dict[str, str],
) -> bool:
    """Return True when the plan is the tracked [PIPELINE-RECOVERY] packet."""
    routing_task_id = str(routing_record.get("task_id", "")).strip()
    if routing_task_id != "[PIPELINE-RECOVERY]":
        return False

    plan_path = str(plan.get("path", "")).strip()
    if not plan_path:
        return False

    candidates = routing_record.get("next_candidates")
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        tracked_packet = str(candidate.get("tracked_packet", "")).strip()
        if tracked_packet == plan_path:
            return True
    return False


def _phase_b_task_id(routing_record: dict[str, Any], plan: dict[str, Any]) -> str:
    return str(
        routing_record.get("task_id")
        or plan.get("task_id")
        or "[PIPELINE-AGENT-PAGER]"
    ).strip()


def _phase_b_pager_route(routing_record: dict[str, Any]) -> str | None:
    route = str(routing_record.get("pager_route") or "").strip()
    return route or None


def _emit_phase_b_event(
    repo_root: Path,
    *,
    routing_record: dict[str, Any],
    plan: dict[str, Any],
    plan_path: str,
    event_type: str,
    state: str,
    transition_key: str,
    summary: str,
    artifact_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    # Derive wave_id with a 3-tier fallback so a missing routing_record
    # (e.g. BOOTSTRAP_PHASE_B_EXCEPTION synthetic routing) or a packet
    # without an explicit `wave_id:` field does not crash phase_b's pager
    # emit at pipeline_agent_pager.py:347. Priority: plan.wave_id →
    # routing_record.wave_name → plan filename stem → "phase_b_unknown_wave".
    # The pager still requires a non-empty wave_id, so the final fallback
    # guarantees emit never raises on missing identity.
    # Bot P2 fix (2026-04-17, PR #791 follow-up): coerce each fallback
    # source to str() BEFORE calling .strip(). plan.get("wave_id") and
    # routing_record.get("wave_name") come from untyped JSON and may be
    # int / float / bool / None. Calling .strip() on a non-str raises
    # AttributeError and crashes phase_b's pager emit, defeating the
    # entire purpose of this fallback chain.
    derived_wave_id = (
        str(plan.get("wave_id") or "").strip()
        or str(routing_record.get("wave_name") or "").strip()
    )
    if not derived_wave_id and plan_path:
        derived_wave_id = Path(str(plan_path)).stem.strip()
    if not derived_wave_id:
        derived_wave_id = "phase_b_unknown_wave"
    return emit_pipeline_agent_event(
        repo_root,
        bus_dir=_active_bus_dir(),
        event_type=event_type,
        wave_id=derived_wave_id,
        task_id=_phase_b_task_id(routing_record, plan),
        plan_path=plan_path,
        phase="phase_b",
        state=state,
        transition_key=transition_key,
        summary=summary,
        reason=summary,
        artifact_paths=artifact_paths,
        route=_phase_b_pager_route(routing_record),
    )


def _phase_b_review_transition_key(round_num: int, bridge_job_id: str) -> str:
    return str(bridge_job_id or "").strip() or f"phase-b-r{round_num}"


def _phase_b_transition_key(bridge_job_id: str, state: str) -> str:
    bridge_job_text = str(bridge_job_id or "").strip() or "phase-b"
    return f"{bridge_job_text}:{state}"


def _phase_b_reentry_implementer_transition_key(
    reentry_round: int,
    *,
    source_key: str,
    state: str,
) -> str:
    source_text = str(source_key or "").strip() or "supervisor"
    return _phase_b_transition_key(
        f"reentry-round-{reentry_round}:{source_text}",
        state,
    )


def _phase_b_hard_fail_transition_key(
    repo_root: Path,
    *,
    state: str,
    changed_files: list[str],
    reentry: bool = False,
) -> str:
    scope_fingerprint = _bridge_scope_fingerprint(repo_root, changed_files)
    prefix = "phase-b-reentry" if reentry else "phase-b"
    return f"{prefix}:{state}:{scope_fingerprint}"


def _emit_phase_b_hard_fail(
    repo_root: Path,
    *,
    routing_record: dict[str, Any],
    plan: dict[str, Any],
    plan_path: str,
    state: str,
    changed_files: list[str],
    summary: str,
    reentry: bool = False,
) -> dict[str, Any]:
    return _emit_phase_b_event(
        repo_root,
        routing_record=routing_record,
        plan=plan,
        plan_path=plan_path,
        event_type="pipeline_hard_fail",
        state=state,
        transition_key=_phase_b_hard_fail_transition_key(
            repo_root,
            state=state,
            changed_files=changed_files,
            reentry=reentry,
        ),
        summary=summary,
    )


def _emit_phase_b_pytest_failure(
    repo_root: Path,
    *,
    routing_record: dict[str, Any],
    plan: dict[str, Any],
    plan_path: str,
    state: str,
    source_key: str,
    changed_files: list[str],
    test_files: list[str],
    summary: str,
    reentry: bool = False,
) -> None:
    artifact_paths = {"test_files": ",".join(test_files)}
    _emit_phase_b_event(
        repo_root,
        routing_record=routing_record,
        plan=plan,
        plan_path=plan_path,
        event_type="phase_b_final_verdict",
        state=state,
        transition_key=_phase_b_transition_key(source_key, state),
        summary=summary,
        artifact_paths=artifact_paths,
    )
    _emit_phase_b_hard_fail(
        repo_root,
        routing_record=routing_record,
        plan=plan,
        plan_path=plan_path,
        state=state,
        changed_files=changed_files,
        summary=summary,
        reentry=reentry,
    )


_FOUNDER_OVERRIDE_TOKEN_RE = re.compile(r"FOUNDER_OVERRIDE:\s*(\S+)")
_FOUNDER_OVERRIDE_METADATA_PREFIXES = (
    "founder override:",
    "founder_override:",
    "founder override token:",
    "founder_override_token:",
    "wave-bound authorization:",
)


def _extract_founder_override_from_metadata_line(line: str) -> str:
    clean = _normalize_plan_metadata_line(line)
    lowered = clean.lower()
    if clean.startswith("FOUNDER_OVERRIDE:"):
        token = clean.split(":", 1)[1].strip()
    elif clean.startswith("`FOUNDER_OVERRIDE:"):
        token = clean.split(":", 1)[1].strip()
    elif lowered.startswith(_FOUNDER_OVERRIDE_METADATA_PREFIXES):
        match = _FOUNDER_OVERRIDE_TOKEN_RE.search(clean)
        if not match:
            return ""
        token = match.group(1).strip()
    else:
        return ""
    return token.split()[0].strip().strip("`").rstrip("`.,;)")


def _extract_founder_override(plan_content: str) -> str:
    """Read an optional canonical founder override token from the plan text."""
    if not plan_content:
        return ""
    for line in plan_content.splitlines():
        founder_override = _extract_founder_override_from_metadata_line(line)
        if founder_override:
            return founder_override
    return ""


def _extract_founder_override_candidates(plan_content: str) -> list[str]:
    """Return founder override tokens in packet order, stripped to bare IDs."""
    candidates: list[str] = []
    if not plan_content:
        return candidates
    for line in plan_content.splitlines():
        founder_override = _extract_founder_override_from_metadata_line(line)
        if founder_override:
            candidates.append(founder_override)
    return candidates


def _bare_founder_override_token(raw_token: str) -> str:
    token = str(raw_token or "").strip()
    if token.startswith("FOUNDER_OVERRIDE:"):
        token = token.split(":", 1)[1].strip()
    if not token:
        return ""
    return token.split()[0].strip().strip("`").rstrip("`.,;)")


def _derive_phase_b_founder_override(
    *,
    plan_content: str,
    wave_id: str,
    wave_class: str,
    explicit_founder_override: str = "",
) -> str:
    """Prefer the same-wave override when the locked packet authorizes one."""
    normalized_wave_id = normalize_wave_id(wave_id)
    candidates = [
        token
        for token in [
            _bare_founder_override_token(explicit_founder_override),
            *_extract_founder_override_candidates(plan_content),
        ]
        if token
    ]
    for token in candidates:
        if normalize_wave_id(token) == normalized_wave_id:
            return token

    authorized = _extract_authorized_control_surface_founder_override(
        plan_content,
        wave_id=wave_id,
        wave_class=wave_class,
    )
    if authorized:
        return authorized
    return candidates[0] if candidates else ""


def _extract_founder_override_from_tracker_note(tracker_note_text: str) -> str:
    """Return a prefixed founder override token from rendered tracker text."""
    if not tracker_note_text:
        return ""
    match = re.search(r"FOUNDER_OVERRIDE:\s*(\S+)", tracker_note_text)
    if not match:
        return ""
    bare_token = match.group(1).strip().rstrip("`.,;")
    return f"FOUNDER_OVERRIDE:{bare_token}" if bare_token else ""


def _supervisor_package_founder_override_token(raw_token: str, *, wave_class: str) -> str:
    """Return an override token only for wave classes allowed by supervisor schema."""
    token = str(raw_token or "").strip()
    if not token:
        return ""
    if str(wave_class or "").strip() not in _SUPERVISOR_OVERRIDE_WAVE_CLASSES:
        return ""
    if not token.startswith("FOUNDER_OVERRIDE:"):
        token = f"FOUNDER_OVERRIDE:{token}"
    return token


_CONTROL_SURFACE_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])control-surface(?![A-Za-z0-9_-])"
)
_NEGATED_CONTROL_SURFACE_RE = re.compile(
    r"(?i)\b(?:anti|no|non|not|without)[-\s]+control-surface\b"
)
_AUTHORIZED_CONTROL_SURFACE_L4_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])authorized\s+control-surface\s+l4[_ -]?enabler"
    r"(?![A-Za-z0-9_-])"
)
_STANDING_PIPELINE_BUG_FIX_AUTHORIZATION_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9_-])standing pipeline-bug-fix authorization(?![A-Za-z0-9_-])"
)
_NEGATED_AUTHORIZATION_RE = re.compile(
    r"(?i)\b(?:authorization\s+(?:is\s+)?(?:denied|not|rejected|revoked)|"
    r"denied|not\s+(?:authorized|approved|granted)|no\s+(?:standing\s+pipeline-bug-fix\s+)?"
    r"authorization|rejected|revoked|without\s+authorization)\b"
)


def _extract_authorized_control_surface_founder_override(
    plan_content: str,
    *,
    wave_id: str,
    wave_class: str,
) -> str:
    """Derive same-wave override only from explicit control-surface authority."""
    if str(wave_class or "").strip() not in _SUPERVISOR_OVERRIDE_WAVE_CLASSES:
        return ""
    normalized_wave_id = normalize_wave_id(wave_id)
    if not plan_content or not normalized_wave_id:
        return ""

    has_control_surface_lane = False
    has_authorization = False
    for raw_line in _iter_authoritative_plan_header_lines(plan_content):
        clean = raw_line.strip()
        if _NEGATED_AUTHORIZATION_RE.search(clean):
            return ""
        if clean.lower().startswith("lane:"):
            lane = clean.split(":", 1)[1]
            if (
                _CONTROL_SURFACE_TOKEN_RE.search(lane)
                and not _NEGATED_CONTROL_SURFACE_RE.search(lane)
            ):
                has_control_surface_lane = True
        if clean.lower().startswith(("authorization:", "founder authorization:", "authority:")):
            auth = clean.split(":", 1)[1]
            if (
                _STANDING_PIPELINE_BUG_FIX_AUTHORIZATION_RE.search(auth)
                or _AUTHORIZED_CONTROL_SURFACE_L4_RE.search(auth)
            ):
                has_authorization = True

    if has_control_surface_lane and has_authorization:
        return normalized_wave_id
    return ""


def _extract_maintenance_bypass_fields(plan_content: str) -> tuple[str, str]:
    """Read optional consecutive-maintenance bypass fields from the plan text."""
    if not plan_content:
        return "", ""
    unblocks_wave_id = ""
    unblocks_runtime_blocker = ""
    for line in plan_content.splitlines():
        clean = _normalize_plan_metadata_line(line)
        if (
            clean.startswith("Unblocks wave id:") or clean.startswith("unblocks_wave_id:")
        ) and not unblocks_wave_id:
            unblocks_wave_id = clean.split(":", 1)[1].strip().strip("`")
        if (
            clean.startswith("Unblocks runtime blocker:")
            or clean.startswith("unblocks_runtime_blocker:")
        ) and not unblocks_runtime_blocker:
            unblocks_runtime_blocker = clean.split(":", 1)[1].strip().strip("`")
        if unblocks_wave_id and unblocks_runtime_blocker:
            return unblocks_wave_id, unblocks_runtime_blocker
    return "", ""


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

    plan_task_id = str(plan.get("task_id", "")).strip()
    routing_task_id = str(routing_record.get("task_id", "")).strip()
    same_wave_exception = _matches_explicit_same_wave_task_id_exception(
        routing_record, plan
    )
    canonical_task_values, canonical_wave_values = _extract_authoritative_plan_header_metadata(
        str(plan.get("content", ""))
    )
    duplicate_authoritative_identity_fields: list[str] = []
    if len(canonical_task_values) > 1:
        duplicate_authoritative_identity_fields.append("Task")
    if len(canonical_wave_values) > 1:
        duplicate_authoritative_identity_fields.append("Wave ID")
    tracked_pipeline_recovery_packet = _is_tracked_pipeline_recovery_packet(
        routing_record, plan
    )
    tracked_pipeline_recovery_identity_error = ""
    tracked_pipeline_recovery_identity_message = (
        "Tracked [PIPELINE-RECOVERY] packet is missing authoritative "
        "Task/Wave header identity required to prove any same-wave "
        f"task_id exception against routing task_id {routing_task_id}"
    )
    duplicate_authoritative_identity_error = ""
    if duplicate_authoritative_identity_fields:
        duplicate_authoritative_identity_error = (
            "Plan contains duplicate authoritative identity headers: "
            f"{', '.join(duplicate_authoritative_identity_fields)}"
        )
    if tracked_pipeline_recovery_packet:
        if duplicate_authoritative_identity_fields:
            tracked_pipeline_recovery_identity_error = (
                tracked_pipeline_recovery_identity_message
            )
    elif duplicate_authoritative_identity_error:
        errors.append(duplicate_authoritative_identity_error)
    if (
        routing_task_id
        and lock != "ROUTING_RECORD_AUTHORITY"
        and not plan_task_id
        and not same_wave_exception
    ):
        if tracked_pipeline_recovery_packet:
            tracked_pipeline_recovery_identity_error = (
                tracked_pipeline_recovery_identity_error
                or tracked_pipeline_recovery_identity_message
            )
        else:
            errors.append(
                "Plan is missing authoritative Task header required to match "
                f"routing task_id {routing_task_id}"
            )
    if tracked_pipeline_recovery_identity_error:
        errors.append(tracked_pipeline_recovery_identity_error)
    if (
        plan_task_id
        and routing_task_id
        and plan_task_id != routing_task_id
        and not same_wave_exception
    ):
        errors.append(
            f"Plan task_id {plan_task_id} does not match routing task_id {routing_task_id}"
        )
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
    except (PermissionError, OSError, subprocess.CalledProcessError):
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
    rendered_path = agent_bus_path(repo_root, _active_bus_dir(), "rendered", f"{job_id}.md")
    raw_dir = agent_bus_path(repo_root, _active_bus_dir(), "raw", job_id)
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


def _signal_process_group_or_pid(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
        return
    except (OSError, ProcessLookupError):
        pass
    try:
        os.kill(pid, sig)
    except (OSError, ProcessLookupError):
        pass


def _pid_is_live(pid: int) -> bool:
    if pid <= 0:
        return False
    # ``kill(pid, 0)`` also succeeds for zombies.  Detached bridge children can
    # be reparented to a PID 1 that does not reap promptly, so treat Linux's
    # terminal process states as exited instead of waiting out cleanup timeouts.
    try:
        proc_stat = (Path("/proc") / str(pid) / "stat").read_bytes()
    except OSError:
        # /proc is not portable and may be hidden; retain the kill(0) fallback.
        pass
    else:
        stat_tail = proc_stat.rpartition(b")")[2]
        stat_fields = stat_tail.split()
        if stat_fields and stat_fields[0] in {b"Z", b"X", b"x"}:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _reap_pid_if_child(pid: int) -> None:
    if pid <= 0:
        return
    try:
        while True:
            reaped_pid, _status = os.waitpid(pid, os.WNOHANG)
            if reaped_pid == 0:
                return
            if reaped_pid == pid:
                return
    except ChildProcessError:
        return
    except OSError:
        return


def _live_recorded_bridge_children(child_pids: tuple[int, ...]) -> tuple[int, ...]:
    live: list[int] = []
    for child_pid in child_pids:
        _reap_pid_if_child(child_pid)
        if _pid_is_live(child_pid):
            live.append(child_pid)
    return tuple(live)


def _wait_for_bridge_subprocess_exit(
    proc: subprocess.Popen[str],
    child_pids: tuple[int, ...],
    *,
    deadline: float,
) -> bool:
    while time.monotonic() < deadline:
        proc_done = proc.poll() is not None
        live_children = _live_recorded_bridge_children(child_pids)
        if proc_done and not live_children:
            return True
        time.sleep(0.1)
    return proc.poll() is not None and not _live_recorded_bridge_children(child_pids)


def _terminate_bridge_subprocess(
    proc: subprocess.Popen[str],
    *,
    child_pids: tuple[int, ...] = (),
) -> None:
    """Terminate a bridge subprocess, including detached adapter children."""
    try:
        pgid = os.getpgid(proc.pid)
    except (OSError, ProcessLookupError):
        pgid = None

    detached_child_pids = tuple(
        sorted({pid for pid in child_pids if pid > 0 and pid != proc.pid})
    )
    for child_pid in detached_child_pids:
        _signal_process_group_or_pid(child_pid, signal.SIGTERM)

    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.terminate()
    except (OSError, ProcessLookupError):
        pass

    if _wait_for_bridge_subprocess_exit(
        proc,
        detached_child_pids,
        deadline=time.monotonic() + 2.0,
    ):
        return

    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGKILL)
        else:
            proc.kill()
    except (OSError, ProcessLookupError):
        pass
    for child_pid in _live_recorded_bridge_children(detached_child_pids):
        _signal_process_group_or_pid(child_pid, signal.SIGKILL)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass
    _wait_for_bridge_subprocess_exit(
        proc,
        detached_child_pids,
        deadline=time.monotonic() + 5.0,
    )


def _run_bridge_review_subprocess(
    repo_root: Path,
    cmd: list[str],
    *,
    job_id: str,
    timeout: int,
    verbose: bool,
    env: dict[str, str] | None = None,
    on_started: Callable[[], None] | None = None,
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
        last_child_pids: tuple[int, ...] = ()
        try:
            if on_started is not None:
                on_started()

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
            last_child_pids = tuple(last_snapshot.get("child_pids") or ())
            last_progress_at = time.monotonic()
            start_time = last_progress_at
            last_heartbeat_at = 0.0

            while True:
                snapshot = _bridge_progress_snapshot(
                    repo_root, job_id, proc.pid, stdout_path, stderr_path
                )
                current_child_pids = tuple(snapshot.get("child_pids") or ())
                # Only a root known live after this snapshot may advance PID authority.
                exit_code = proc.poll()
                if exit_code is None:
                    last_child_pids = current_child_pids
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
                    stdout_size, _ = artifact_size_mtime_ns(stdout_path)
                    stderr_size, _ = artifact_size_mtime_ns(stderr_path)
                    _terminate_bridge_subprocess(
                        proc,
                        child_pids=tuple(
                            sorted(set(last_child_pids).union(current_child_pids))
                        ),
                    )
                    os.truncate(stdout_path, stdout_size)
                    os.truncate(stderr_path, stderr_size)
                    stdout, stderr = _read_logs()
                    return {
                        "exit_code": exit_code,
                        "stdout": stdout,
                        "stderr": stderr,
                        "stdout_path": str(stdout_path.relative_to(repo_root)),
                        "stderr_path": str(stderr_path.relative_to(repo_root)),
                    }

                if not snapshot["child_pids"] and idle_for >= aggregation_hang_timeout:
                    _terminate_bridge_subprocess(proc, child_pids=snapshot["child_pids"])
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
                    _terminate_bridge_subprocess(proc, child_pids=snapshot["child_pids"])
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
                    _terminate_bridge_subprocess(proc, child_pids=snapshot["child_pids"])
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
        except BaseException:
            cleanup_child_pids = set(last_child_pids)
            try:
                cleanup_snapshot = _bridge_progress_snapshot(
                    repo_root,
                    job_id,
                    proc.pid,
                    stdout_path,
                    stderr_path,
                )
                cleanup_child_pids.update(cleanup_snapshot.get("child_pids") or ())
            except BaseException:
                pass
            _terminate_bridge_subprocess(
                proc,
                child_pids=tuple(sorted(pid for pid in cleanup_child_pids if pid)),
            )
            raise


def run_bridge_review(
    repo_root: Path,
    task_summary: str,
    *,
    job_id: str | None = None,
    reader_agent: str | None = None,
    verbose: bool = False,
    timeout: int = 1200,
    on_started: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Run bridge_supervisor.py review and return the result.

    If job_id is provided, it's passed to bridge_supervisor so the rendered
    output is written to a deterministic path under the active bus rendered
    directory.
    The decision is parsed from stdout (bridge_supervisor prints it).
    """
    config = load_executor_config(repo_root)
    reader = (
        reader_agent
        if reader_agent is not None
        else config.get("backends", {}).get(
            "phase_b_executor",
            DEFAULT_EXECUTOR_CONFIG["backends"]["phase_b_executor"],
        )
    )
    if not isinstance(reader, str) or not reader.strip():
        raise PhaseBExecutorError(
            f"Invalid bridge reader {reader!r} for phase_b; expected non-empty string"
        )
    reader = reader.strip()
    reviewer = _resolve_bridge_reviewer(config, "phase_b")
    bridge_turn_timeout = _resolve_bridge_turn_timeout(config, "phase_b", default=300.0)

    # Write task file
    scratch_dir = repo_root / ".scratch"
    scratch_dir.mkdir(exist_ok=True)
    task_path = scratch_dir / "phase_b_bridge_task.md"
    task_path.write_text(task_summary, encoding="utf-8")

    bridge_script = repo_root / "tools" / "agents" / "bridge_supervisor.py"
    active_bus_dir = _active_bus_dir()
    cmd = [sys.executable, str(bridge_script)]
    if active_bus_dir is not None:
        cmd.extend(["--bus-dir", str(active_bus_dir)])
    cmd.extend([
        "review",
        "--task-file", str(task_path),
        "--summary", "Phase B implementation review",
        "--reader", reader,
        "--reviewer", reviewer,
    ])
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
        on_started=on_started,
        stale_timeout=max(BRIDGE_REVIEW_STALE_TIMEOUT, bridge_turn_timeout),
        env={
            **os.environ,
            # The outer bridge wrapper already enforces the authoritative total
            # review budget. Keep the inner adapter aligned with that outer
            # subprocess timeout so an in-progress reviewer does not get killed
            # early by the narrower config stale window.
            "RCX_BRIDGE_MAX_TURN_WALL_TIME_S": str(float(timeout)),
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
    The rendered file is under the active agent bus rendered directory.
    """
    if not BRIDGE_JOB_ID_RE.fullmatch(job_id or ""):
        return ""
    rendered_path = agent_bus_path(repo_root, _active_bus_dir(), "rendered", f"{job_id}.md")
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


def _build_bridge_status(rounds: Any, *, reentry: bool = False) -> dict[str, Any]:
    """Render a normalized bridge-status block from an explicit round count."""
    try:
        normalized_rounds = max(int(rounds or 0), 0)
    except (TypeError, ValueError):
        normalized_rounds = 0
    bridge_status: dict[str, Any] = {
        "rounds": normalized_rounds,
        "total_rounds": normalized_rounds,
    }
    if reentry:
        bridge_status["reentry"] = True
    return bridge_status


_BRIDGE_ROUND_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}
_BRIDGE_ROUND_WORD_PATTERN = "|".join(
    sorted((re.escape(word) for word in _BRIDGE_ROUND_WORDS), key=len, reverse=True)
)
_BRIDGE_ROUND_ILLUSTRATIVE_PREFIX_RE = re.compile(
    r"\b(?:"
    r"such\s+as|for\s+example|e\.g\.|"
    r"examples?\s+include|examples?\s*:|sample\s*:"
    r")\s*(?:[,:-]\s*)?",
    flags=re.IGNORECASE,
)
_BRIDGE_ROUND_ILLUSTRATIVE_CLAUSE_BREAK_RE = re.compile(r"[.;!?,:]")


def _documented_bridge_round_value(raw_value: str) -> int:
    normalized = raw_value.strip().lower()
    if normalized.isdigit():
        return int(normalized)
    return _BRIDGE_ROUND_WORDS.get(normalized, 0)


def _bridge_round_match_is_illustrative(text: str, match_start: int) -> bool:
    line_start = text.rfind("\n", 0, match_start) + 1
    prefix = text[line_start:match_start]
    for marker in _BRIDGE_ROUND_ILLUSTRATIVE_PREFIX_RE.finditer(prefix):
        if not _BRIDGE_ROUND_ILLUSTRATIVE_CLAUSE_BREAK_RE.search(prefix[marker.end():]):
            return True
    return False


def _documented_bridge_round_floor_from_text(text: str) -> int:
    round_floor = 0
    for match in re.finditer(
        r"\bBridge\s+Round\s+(\d+)\s+Remediation\b",
        text,
        flags=re.IGNORECASE,
    ):
        if _bridge_round_match_is_illustrative(text, match.start()):
            continue
        round_floor = max(round_floor, int(match.group(1)))
    for match in re.finditer(
        rf"\b(\d+|{_BRIDGE_ROUND_WORD_PATTERN})\s+"
        r"(?:Phase\s+[AB]\s+)?bridge\s+rounds?\b",
        text,
        flags=re.IGNORECASE,
    ):
        if _bridge_round_match_is_illustrative(text, match.start()):
            continue
        round_floor = max(round_floor, _documented_bridge_round_value(match.group(1)))
    return round_floor


def _documented_bridge_round_floor(repo_root: Path, wave_id: str, plan_path: str) -> int:
    """Return the highest same-wave bridge remediation round recorded in repo truth."""
    round_floor = 0
    if plan_path and not plan_path.startswith("<"):
        packet_path = repo_root / plan_path
        try:
            packet_text = packet_path.read_text(encoding="utf-8")
        except OSError:
            packet_text = ""
        round_floor = max(round_floor, _documented_bridge_round_floor_from_text(packet_text))

    wave_date_match = re.search(r"(\d{4}-\d{2}-\d{2})$", str(wave_id or ""))
    if wave_date_match:
        wave_date = wave_date_match.group(1)
        try:
            tasks_text = (repo_root / "TASKS.md").read_text(encoding="utf-8")
        except OSError:
            tasks_text = ""
        wave_index = tasks_text.find(str(wave_id or ""))
        if wave_index != -1:
            entry_start = tasks_text.rfind("\n  - Tracker sync note", 0, wave_index)
            if entry_start == -1:
                entry_start = tasks_text.rfind("\n- **[", 0, wave_index)
            entry_start = 0 if entry_start == -1 else entry_start + 1
            entry_end_candidates = [
                pos for marker in ("\n  - Tracker sync note", "\n- **[", "\n## ")
                if (pos := tasks_text.find(marker, wave_index + len(str(wave_id or "")))) != -1
            ]
            entry_end = min(entry_end_candidates) if entry_end_candidates else len(tasks_text)
            tasks_window = tasks_text[entry_start:entry_end]
            for match in re.finditer(
                rf"\b{re.escape(wave_date)}\s+bridge\s+round\s+(\d+)\s+remediation\b",
                tasks_window,
                flags=re.IGNORECASE,
            ):
                round_floor = max(round_floor, int(match.group(1)))
    return round_floor


def _build_effective_bridge_status(
    repo_root: Path,
    wave_id: str,
    plan_path: str,
    rounds: Any,
    *,
    reentry: bool = False,
) -> dict[str, Any]:
    """Render bridge status without underreporting same-wave documented rounds."""
    try:
        executor_rounds = max(int(rounds or 0), 0)
    except (TypeError, ValueError):
        executor_rounds = 0
    documented_rounds = _documented_bridge_round_floor(repo_root, wave_id, plan_path)
    return _build_bridge_status(max(executor_rounds, documented_rounds), reentry=reentry)


def _bridge_rounds_for_tracker_note(bridge_status: dict[str, Any]) -> int:
    """Use the package bridge-status floor when rendering tracker prose."""
    round_candidates: list[int] = []
    for key in ("rounds", "total_rounds"):
        try:
            round_candidates.append(max(int(bridge_status.get(key) or 0), 0))
        except (TypeError, ValueError):
            round_candidates.append(0)
    return max(round_candidates or [0])


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


def _collect_staged_files(repo_root: Path) -> list[str]:
    """Collect files already staged in git."""
    try:
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip().splitlines()
    except subprocess.CalledProcessError:
        return []
    return sorted(set(f for f in staged if f))


def _reconcile_bridge_fix_scope(
    repo_root: Path,
    implementer_changed_files: set[str],
    current_fix_changed_files: set[str],
) -> set[str]:
    """Honor a bridge-fix agent's intentional staging boundary.

    Bridge fixes sometimes resolve package-composition findings by unstaging
    pre-existing files from a broader implementation scope. Accumulated
    ``implementer_changed`` state must not blindly re-stage those files for the
    next review round, but files newly changed by this fix round still need to
    remain tracked even when the agent did not stage them itself.
    """
    staged_after_fix = set(_collect_staged_files(repo_root))
    if not staged_after_fix:
        return set(implementer_changed_files)

    current_fix_changed = set(current_fix_changed_files)
    preexisting_tracked = set(implementer_changed_files) - current_fix_changed
    return (preexisting_tracked & staged_after_fix) | current_fix_changed


def _collect_commit_bound_files(
    repo_root: Path,
    changed_files: list[str],
    *,
    allowed_files: set[str] | None = None,
) -> list[str]:
    """Return the supervisor/commit package truth for files bound to this commit.

    Phase B stages wave-owned files before the pre-commit supervisor so the
    receipt hash matches the later commit path. Once a file is staged, it is
    commit-bound git truth; packaging it as fenced dirty work creates a false
    package contradiction.
    """
    commit_bound = set(changed_files) | set(_collect_staged_files(repo_root))
    if allowed_files is not None:
        commit_bound &= set(allowed_files)
    return sorted(commit_bound)


def _collect_fenced_dirty_files(repo_root: Path, commit_bound_files: list[str]) -> list[str]:
    """Collect dirty files that are not currently commit-bound."""
    commit_bound = set(commit_bound_files)
    return [f for f in _collect_changed_files(repo_root) if f not in commit_bound]


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
    ".gitignore",
)


_DECLARED_PATH_EXTENSIONS = (".py", ".json", ".md", ".txt", ".sh")
_DECLARED_ROOT_FILES = {".gitignore", "CLAUDE.md", "TASKS.md", "STATUS.md", "CHANGELOG.md"}
_LINE_REF_RE = re.compile(r"^(?P<path>.+?):(?P<line>\d+)(?::(?P<col>\d+))?$")
_INLINE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+|(?:CLAUDE|TASKS|STATUS|CHANGELOG)\.md|\.gitignore)(?![A-Za-z0-9_./-])")
_PLAN_WAVE_CLASS_RE = re.compile(
    r"^\s*(?:[-*]\s*)?`?(?:wave[_ -]?class|class)\s*[:=]\s*`?(?P<value>[A-Za-z0-9_-]+)",
    flags=re.IGNORECASE,
)
_PLAN_TARGET_GATE_RE = re.compile(
    r"^\s*(?:[-*]\s*)?`?(?:target[_ -]?gate(?:[_ -]?id)?)\s*[:=]\s*`?(?P<value>G[1-8])\b",
    flags=re.IGNORECASE,
)
_PLAN_GATE_ID_TOKEN_RE = re.compile(r"^(?P<gate>G[1-8])\b", flags=re.IGNORECASE)


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
    lines = plan_content.splitlines()
    broad_refresh_lines = _phase_b_broad_refresh_line_indices(lines)
    seen: set[str] = set()
    parsed: list[str] = []

    def _add(token: str) -> None:
        normalized = _normalize_declared_path_token(token)
        if normalized and normalized not in seen:
            seen.add(normalized)
            parsed.append(normalized)

    for index, line in enumerate(lines):
        if index in broad_refresh_lines:
            continue
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


def _phase_b_broad_refresh_line_indices(lines: list[str]) -> set[int]:
    """Return line indices belonging to explicitly non-authoritative refresh blocks."""
    broad_refresh_lines: set[int] = set()
    refresh_start: int | None = None
    for index, line in enumerate(lines):
        if PHASE_B_INDICATOR_SCOPE_REFRESH_START in line:
            refresh_start = index
        if (
            refresh_start is not None
            and PHASE_B_INDICATOR_SCOPE_REFRESH_END in line
        ):
            block_lines = lines[refresh_start:index + 1]
            if any(
                PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER in block_line
                for block_line in block_lines
            ):
                broad_refresh_lines.update(range(refresh_start, index + 1))
            refresh_start = None
    if refresh_start is not None and any(
        PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER in block_line
        for block_line in lines[refresh_start:]
    ):
        broad_refresh_lines.update(range(refresh_start, len(lines)))
    return broad_refresh_lines


def _parse_exact_stage_scope_files(plan_content: str) -> list[str]:
    """Extract a packet section that explicitly declares the exact staged scope."""
    lines = plan_content.splitlines()
    broad_refresh_lines = _phase_b_broad_refresh_line_indices(lines)

    def _section_text(header: str) -> str:
        section_start: int | None = None
        for index, line in enumerate(lines):
            if line.strip().lower() == header:
                section_start = index + 1
                break
        if section_start is None:
            return ""
        section_end = len(lines)
        for index in range(section_start, len(lines)):
            if lines[index].strip().startswith("## "):
                section_end = index
                break
        return "\n".join(lines[section_start:section_end])

    acceptance_text = " ".join(
        _section_text("## acceptance criteria").lower().split()
    )
    launcher_exact_final_set = (
        "final staged set contains exactly" in acceptance_text
    )
    marker_index: int | None = None
    launcher_scope = False
    for index, line in enumerate(lines):
        if index in broad_refresh_lines:
            continue
        stripped = line.strip()
        lower = stripped.lower()
        bullet_body = lower[2:].strip() if lower.startswith("- ") else lower
        is_launcher_scope_header = (
            launcher_exact_final_set
            and lower == "files and surfaces in scope:"
        )
        is_exact_stage_header = (
            "`" not in stripped
            and (
                lower == "allowed write scope:"
                or ("may stage exactly" in lower and "file" in lower and lower.endswith(":"))
                or bullet_body in {"authorized staged files:", "current staged files:"}
                or is_launcher_scope_header
            )
        )
        if is_exact_stage_header:
            marker_index = index
            launcher_scope = is_launcher_scope_header
            break
    if marker_index is None:
        return []

    seen: set[str] = set()
    parsed: list[str] = []
    started = False
    for line in lines[marker_index + 1:]:
        stripped = line.strip()
        if not stripped:
            if started:
                break
            continue
        if stripped.startswith("#"):
            break
        if not stripped.startswith("- "):
            if started:
                break
            continue
        normalized = _normalize_declared_path_token(stripped[2:].strip().split()[0])
        if normalized and normalized not in seen:
            seen.add(normalized)
            parsed.append(normalized)
            started = True
    if launcher_scope:
        optional_reviewer_nonblocker = bool(
            "final staged set contains exactly" in acceptance_text
            and re.search(
                r"\bplus only the standard generated reviewer[ -]nonblocker "
                r"report if one is required\b",
                acceptance_text,
            )
        )
        if optional_reviewer_nonblocker:
            _tasks, waves = _extract_authoritative_plan_header_metadata(plan_content)
            if len(waves) == 1:
                deferred_path = _canonical_deferred_packet_relpath(waves[0])
                if deferred_path not in seen:
                    parsed.append(deferred_path)
    return parsed


def parse_exact_stage_scope_files(plan_content: str) -> list[str]:
    """Public selector seam for exact staged-scope control-packet tests."""
    return _parse_exact_stage_scope_files(plan_content)


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


def _parse_plan_wave_class(plan_content: str) -> str:
    """Extract the locked packet's declared header wave class."""
    for line in _iter_authoritative_plan_header_lines(plan_content):
        match = _PLAN_WAVE_CLASS_RE.match(line.strip())
        if match:
            return match.group("value").strip().strip("`.,;")
    return ""


def _resolve_phase_b_wave_class(
    routing_record: dict[str, Any],
    plan_content: str,
) -> str:
    """Resolve package class from the locked packet before stale routing metadata."""
    plan_wave_class = _parse_plan_wave_class(plan_content)
    if plan_wave_class:
        return plan_wave_class
    if _phase_b_declares_structural_runtime_intent(plan_content, routing_record):
        return "L4_STRUCTURAL"
    return str(routing_record.get("wave_class") or "").strip() or "L4_ENABLER"


def _refresh_phase_b_package_governance(
    repo_root: Path,
    plan: dict[str, Any],
    plan_path: str,
    routing_record: dict[str, Any],
) -> tuple[str, str]:
    """Refresh package governance from the live packet before supervisor packaging."""
    plan_content = str(plan.get("content", "") or "")
    if plan_path and not plan_path.startswith("<"):
        try:
            plan_content = (repo_root / plan_path).read_text(encoding="utf-8")
            plan["content"] = plan_content
        except OSError:
            pass
    wave_class = _resolve_phase_b_wave_class(routing_record, plan_content)
    target_gate_id = (
        _normalize_plan_target_gate_id(routing_record.get("target_gate_id"))
        or _parse_plan_target_gate_id(plan_content)
        or "G8"
    )
    return wave_class, target_gate_id


def _parse_plan_target_gate_id(plan_content: str) -> str:
    """Extract the locked packet's target gate id when routing omits it."""
    for line in plan_content.splitlines():
        match = _PLAN_TARGET_GATE_RE.match(line.strip())
        if match:
            return _normalize_plan_target_gate_id(match.group("value"))
    return ""


def _normalize_plan_target_gate_id(value: Any) -> str:
    """Return a concrete target gate, or empty for packet NO-GO placeholders."""
    gate = str(value or "").strip().split(" #", 1)[0].strip().strip("`.,;")
    normalized = " ".join(gate.lower().split())
    if normalized in {
        "",
        "-",
        "n/a",
        "na",
        "none",
        "none selected",
        "none-selected",
        "not applicable",
        "not selected",
        "not-selected",
    }:
        return ""
    match = _PLAN_GATE_ID_TOKEN_RE.match(gate)
    return match.group("gate").upper() if match else gate


def _is_phase_b_indicator_scope_refresh_temp_path(
    candidate_path: str,
    plan_path: str,
) -> bool:
    """Identify only same-packet temporary files created by atomic scope refresh."""
    normalized_plan = str(plan_path or "").strip().replace("\\", "/")
    normalized_candidate = str(candidate_path or "").strip().replace("\\", "/")
    if (
        not normalized_plan
        or normalized_plan.startswith("<")
        or not normalized_candidate
    ):
        return False
    packet = Path(normalized_plan)
    candidate = Path(normalized_candidate)
    if candidate.parent != packet.parent:
        return False
    prefix = f".{packet.name}."
    suffix = ".tmp"
    if not candidate.name.startswith(prefix) or not candidate.name.endswith(suffix):
        return False
    nonce = candidate.name[len(prefix):-len(suffix)]
    return bool(nonce)


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
        if _is_phase_b_indicator_scope_refresh_temp_path(f, plan_path):
            continue
        if any(f.startswith(p) or f == p for p in _WAVE_OWNED_PREFIXES):
            baseline.append(f)
        elif plan_prefix and f.startswith(plan_prefix):
            baseline.append(f)
    return sorted(set(baseline))


def _restrict_baseline_to_exact_scope(
    baseline_wave_files: set[str],
    exact_stage_scope_files: set[str] | None,
) -> set[str]:
    """Prevent dirty-worktree baseline capture from widening an exact package."""
    if not exact_stage_scope_files:
        return baseline_wave_files
    return set(baseline_wave_files) & set(exact_stage_scope_files)


def _expand_exact_stage_scope_files_for_git(
    repo_root: Path,
    exact_stage_scope_files: set[str],
) -> set[str]:
    """Include git-tracked equivalents for exact-scope paths behind symlinks."""
    if not exact_stage_scope_files:
        return set()
    expanded = set(exact_stage_scope_files)
    try:
        root_resolved = repo_root.resolve()
    except OSError:
        return expanded
    for rel_path in list(exact_stage_scope_files):
        candidate = repo_root / rel_path
        try:
            resolved = candidate.resolve(strict=False)
            git_rel = resolved.relative_to(root_resolved).as_posix()
        except (OSError, ValueError):
            continue
        if git_rel and git_rel != rel_path and not git_rel.startswith("../"):
            expanded.add(git_rel)
    return expanded


def expand_exact_stage_scope_files_for_git(
    repo_root: Path,
    exact_stage_scope_files: set[str],
) -> set[str]:
    """Public seam for resolving exact staged-scope paths to git paths."""
    return _expand_exact_stage_scope_files_for_git(repo_root, exact_stage_scope_files)


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
    all_changed = [
        path for path in _collect_changed_files(repo_root)
        if not _is_phase_b_indicator_scope_refresh_temp_path(path, plan_path)
    ]
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


def _stage_files_with_diagnostics(repo_root: Path, files: list[str]) -> tuple[bool, str]:
    """Stage files for commit and return a failure detail when git rejects them.

    Files under .claude/ are staged individually to avoid the git multi-path
    pathspec resolver false-positive: batch ``git add`` with .claude/ paths
    alongside other top-level paths triggers "ignored by .gitignore" on the
    .claude parent directory even for tracked files under negation-rule
    subdirectories (.claude/hooks/).  Single-path adds work correctly.
    See .claude/rules/learning.md 2026-04-11 entry (git add multi-path).
    """
    if not files:
        return False, "no files supplied"
    try:
        staged_files = set(_collect_staged_files(repo_root))
    except subprocess.CalledProcessError as exc:
        detail_parts = [
            f"git add failed with exit={exc.returncode}",
            (exc.stderr or "").strip(),
            (exc.stdout or "").strip(),
        ]
        return False, " | ".join(part for part in detail_parts if part)
    stageable_files: list[str] = []
    for f in files:
        if (repo_root / f).exists():
            stageable_files.append(f)
            continue
        try:
            in_index = subprocess.run(
                ["git", "ls-files", "--error-unmatch", "--", f],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except subprocess.CalledProcessError as exc:
            detail_parts = [
                f"git add failed with exit={exc.returncode}",
                (exc.stderr or "").strip(),
                (exc.stdout or "").strip(),
            ]
            return False, " | ".join(part for part in detail_parts if part)
        if in_index.returncode == 0:
            stageable_files.append(f)
            continue
        if f in staged_files:
            # Already-staged deletions/renames have no index path left; re-adding
            # that missing source path fails with "pathspec did not match".
            continue
        stageable_files.append(f)
    if not stageable_files:
        return True, ""
    claude_files = [f for f in stageable_files if f.startswith(".claude/") or f.startswith(".claude\\")]
    other_files = [f for f in stageable_files if f not in claude_files]
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
        return True, ""
    except subprocess.CalledProcessError as exc:
        # Fail closed. Phase B must not bypass ignore rules by force-adding
        # files the repo has explicitly excluded from normal staging.
        detail_parts = [
            f"git add failed with exit={exc.returncode}",
            (exc.stderr or "").strip(),
            (exc.stdout or "").strip(),
        ]
        return False, " | ".join(part for part in detail_parts if part)


_LAST_STAGE_FILES_DETAIL = ""


def _stage_files(repo_root: Path, files: list[str]) -> bool:
    """Stage files for commit. Returns True on success."""
    global _LAST_STAGE_FILES_DETAIL
    ok, detail = _stage_files_with_diagnostics(repo_root, files)
    _LAST_STAGE_FILES_DETAIL = detail
    return ok


def _stage_files_for_pipeline(repo_root: Path, files: list[str]) -> tuple[bool, str]:
    """Stage through the existing seam while preserving git diagnostics."""
    global _LAST_STAGE_FILES_DETAIL
    _LAST_STAGE_FILES_DETAIL = ""
    ok = _stage_files(repo_root, files)
    detail = _LAST_STAGE_FILES_DETAIL
    if not ok and not detail:
        detail = "git add failed without diagnostic detail"
    return ok, detail


def _unstage_out_of_exact_scope(
    repo_root: Path,
    allowed_files: set[str],
) -> tuple[bool, str]:
    """Keep an exact-scope package from inheriting stale staged wave files."""
    stale_staged = sorted(
        path for path in _collect_staged_files(repo_root)
        if path not in allowed_files
    )
    if not stale_staged:
        return True, ""
    try:
        subprocess.run(
            ["git", "restore", "--staged", "--", *stale_staged],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return True, ""
    except subprocess.CalledProcessError as exc:
        detail_parts = [
            f"git restore --staged failed with exit={exc.returncode}",
            (exc.stderr or "").strip(),
            (exc.stdout or "").strip(),
        ]
        return False, " | ".join(part for part in detail_parts if part)


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
    bus_dir: str | Path | None = None,
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
            bus_dir=bus_dir,
        )
        return {
            "exit_code": 0 if not result.is_error else 1,
            "parsed": {
                "decision": result.decision,
                "summary": result.summary,
                "status": result.status,
                "findings": result.findings,
                "request_for_agent": result.request_for_claude,
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
    target_branch: str | None = None,
    tracker_note_text: str = "",
    fixes_implemented: list[str] | None = None,
    files_to_stage: list[str] | None = None,
    force_add_files: list[str] | None = None,
    commit_message: str = "",
    pr_title: str = "",
    pr_body: str = "",
    pre_commit_receipt_path: str | None = None,
    tracked_packet: str | None = None,
    supervisor_lane: str | None = None,
    deferred_items: list[str] | None = None,
    bridge_status: dict[str, Any] | None = None,
    scope_items: list[str] | None = None,
    evidence_handles: dict[str, str] | None = None,
    pager_route: str | None = None,
    bus_dir: str | Path | None = None,
) -> Path:
    """Prepare a commit executor handoff file (new schema).

    Produces the 15-field handoff required by the commit executor state machine.
    """
    try:
        from commit_executor import build_commit_handoff
    except ImportError:
        import importlib.util as _ilu
        _commit_path = SCRIPT_DIR / "commit_executor.py"
        _commit_spec = _ilu.spec_from_file_location("commit_executor", str(_commit_path))
        _commit_mod = _ilu.module_from_spec(_commit_spec)
        assert _commit_spec.loader is not None
        _commit_spec.loader.exec_module(_commit_mod)
        build_commit_handoff = _commit_mod.build_commit_handoff

    if pre_commit_receipt_path is None:
        pre_commit_receipt_path = str(
            agent_bus_relpath(bus_dir, "meta", "pre_commit_receipt.json")
        )
    handoff, errors = build_commit_handoff(
        wave_id=wave_id,
        task_id=task_id,
        files_to_stage=list(files_to_stage or []),
        commit_message=commit_message,
        fixes_implemented=list(fixes_implemented or []),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        caller=caller,
        base_branch="dev",
        branch_prefix=branch_prefix,
        target_branch=target_branch,
        force_add_files=list(force_add_files or []),
        pr_title=pr_title,
        pr_body=pr_body,
        tracker_note_text=tracker_note_text or None,
        tracked_packet=tracked_packet,
        supervisor_lane=supervisor_lane,
        deferred_items=deferred_items,
        bridge_status=bridge_status,
        scope_items=scope_items,
        evidence_handles=evidence_handles,
        pre_commit_receipt_path=pre_commit_receipt_path,
        pager_route=pager_route,
        repo_root=repo_root,
    )
    if errors:
        raise PhaseBExecutorError(
            "Cannot prepare commit handoff via build_commit_handoff: "
            + "; ".join(errors)
        )

    handoff_dir = agent_bus_path(repo_root, bus_dir, "executors")
    handoff_dir.mkdir(parents=True, exist_ok=True)
    handoff_path = handoff_dir / "phase_b_handoff.json"
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    return handoff_path


def _dispatcher_handoff_plan_path(routing_record: dict[str, Any]) -> str:
    for candidate in (
        routing_record.get("plan_path"),
        routing_record.get("tracked_packet"),
    ):
        path = str(candidate or "").strip()
        if path:
            return path
    next_candidates = routing_record.get("next_candidates")
    if isinstance(next_candidates, list):
        for item in next_candidates:
            if isinstance(item, dict):
                path = str(item.get("tracked_packet") or "").strip()
                if path:
                    return path
    return ""


def _dispatcher_handoff_explicit_files(routing_record: dict[str, Any]) -> list[str]:
    paths: list[str] = []

    def add_many(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                text = str(item or "").strip()
                if text:
                    paths.append(text)

    add_many(routing_record.get("files_to_stage"))
    add_many(routing_record.get("force_add_files"))
    next_candidates = routing_record.get("next_candidates")
    if isinstance(next_candidates, list):
        for item in next_candidates:
            if isinstance(item, dict):
                add_many(item.get("files"))
    return _dedupe_phase_b_repo_paths(paths)


def _validate_dispatcher_handoff_receipt(
    repo_root: Path,
    receipt_rel: str,
    receipt_file: Path,
    *,
    bus_dir: str | Path | None = None,
) -> list[str]:
    errors: list[str] = []
    expected_prefix = str(
        agent_bus_relpath(bus_dir, "meta", "pre_commit_receipts")
    ).rstrip("/") + "/"
    if not receipt_rel.startswith(expected_prefix):
        errors.append(
            "receipt_path must point to a pre-commit supervisor receipt under "
            f"{expected_prefix}: {receipt_rel}"
        )
    if Path(receipt_rel).suffix != ".json":
        errors.append(f"receipt_path must be a JSON receipt file: {receipt_rel}")
    try:
        receipt_data = json.loads(receipt_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        errors.append(f"receipt_path is not a readable JSON receipt: {receipt_rel}: {exc}")
        return errors
    if not isinstance(receipt_data, dict):
        errors.append(f"receipt_path must decode to a JSON object: {receipt_rel}")
        return errors
    receipt_decision = str(receipt_data.get("decision") or "").strip()
    if receipt_decision not in {"COMMIT_GO", "COMMIT_GO_HOLD_PUSH"}:
        errors.append(
            "receipt_path decision must be COMMIT_GO or COMMIT_GO_HOLD_PUSH, "
            f"got {receipt_decision or '<missing>'}: {receipt_rel}"
        )
    for field in ("staged_sha", "timestamp_utc", "package_digest", "package_path"):
        value = receipt_data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(
                "receipt_path missing required supervisor receipt field "
                f"{field}: {receipt_rel}"
            )
    timestamp_utc = str(receipt_data.get("timestamp_utc") or "").strip()
    if timestamp_utc:
        try:
            datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        except ValueError:
            errors.append(
                f"receipt_path timestamp_utc is unparseable: {receipt_rel}"
            )
    return errors


def prepare_dispatcher_commit_handoff_from_routing_record(
    repo_root: Path,
    routing_record: dict[str, Any],
    *,
    receipt_path: str,
    plan_path: str | None = None,
    bus_dir: str | Path | None = None,
) -> tuple[Path | None, list[str]]:
    """Rebuild the dispatcher-visible Phase B handoff through Phase B builders.

    This is for recovery after Phase B already has receipt evidence but the
    durable handoff is missing, stale, or mismatched. It does not run the
    pre-commit supervisor and refuses to synthesize receipt authority.
    """
    errors: list[str] = []
    if not isinstance(routing_record, dict):
        return None, ["routing_record must be a JSON object"]

    receipt_rel = str(receipt_path or "").strip()
    if not receipt_rel:
        errors.append("receipt_path is required for dispatcher Phase B handoff rebuild")
    elif os.path.isabs(receipt_rel) or any(part == ".." for part in Path(receipt_rel).parts):
        errors.append(f"unsafe receipt_path for dispatcher Phase B handoff rebuild: {receipt_rel}")
    else:
        receipt_file = (repo_root / receipt_rel).resolve()
        try:
            receipt_file.relative_to(repo_root.resolve())
        except ValueError:
            errors.append(f"receipt_path escapes repo root: {receipt_rel}")
        if not receipt_file.exists():
            errors.append(f"receipt_path does not exist: {receipt_rel}")
        else:
            errors.extend(
                _validate_dispatcher_handoff_receipt(
                    repo_root,
                    receipt_rel,
                    receipt_file,
                    bus_dir=bus_dir,
                )
            )

    routing_plan_path = _dispatcher_handoff_plan_path(routing_record)
    resolved_plan_path = str(plan_path or "").strip() or routing_plan_path
    if not resolved_plan_path:
        errors.append("routing record missing plan_path/tracked_packet for dispatcher Phase B handoff rebuild")
    if resolved_plan_path.startswith("<"):
        errors.append(f"dispatcher Phase B handoff rebuild requires a real plan packet, got {resolved_plan_path}")
    if (
        routing_plan_path
        and not routing_plan_path.startswith("<")
        and resolved_plan_path
        and resolved_plan_path != routing_plan_path
    ):
        errors.append(
            "dispatcher Phase B handoff rebuild plan_path "
            f"{resolved_plan_path} does not match routing tracked_packet {routing_plan_path}"
        )
    if errors:
        return None, errors

    try:
        plan = load_plan_packet(repo_root, resolved_plan_path)
    except PhaseBExecutorError as exc:
        return None, [str(exc)]
    plan_content = str(plan.get("content") or "")
    plan_wave_id = normalize_wave_id(str(plan.get("wave_id") or ""))
    routing_wave_id = normalize_wave_id(
        str(routing_record.get("wave_name") or routing_record.get("wave_id") or "")
    )
    if plan_wave_id and routing_wave_id and plan_wave_id != routing_wave_id:
        return None, [
            "plan Wave ID "
            f"{plan_wave_id} does not match routing wave {routing_wave_id} "
            "for dispatcher Phase B handoff rebuild"
        ]
    wave_id = plan_wave_id or routing_wave_id
    if not wave_id:
        return None, ["cannot resolve wave_id for dispatcher Phase B handoff rebuild"]

    wave_class, target_gate_id = _refresh_phase_b_package_governance(
        repo_root,
        plan,
        resolved_plan_path,
        routing_record,
    )
    fenced_out_files = set(_parse_fenced_out_files(plan_content))
    exact_stage_scope_files = _expand_exact_stage_scope_files_for_git(
        repo_root,
        set(_parse_exact_stage_scope_files(plan_content)),
    )
    if exact_stage_scope_files:
        plan_declared_files = sorted(
            path for path in exact_stage_scope_files
            if path not in fenced_out_files
        )
    else:
        plan_declared_files = [
            path for path in _parse_plan_declared_files(plan_content)
            if path not in fenced_out_files
        ]
    explicit_files = set(_dispatcher_handoff_explicit_files(routing_record)) - fenced_out_files
    if exact_stage_scope_files:
        explicit_files &= exact_stage_scope_files
    baseline_files = (
        set(_collect_baseline_wave_files(repo_root, resolved_plan_path))
        - fenced_out_files
    )
    baseline_files = _restrict_baseline_to_exact_scope(
        baseline_files,
        exact_stage_scope_files or None,
    )
    wave_owned_files = _collect_wave_owned_files(
        repo_root,
        resolved_plan_path,
        plan_declared_files or None,
        explicit_files or None,
        set(),
        baseline_files,
    )
    wave_owned_files = _collect_commit_bound_files(
        repo_root,
        wave_owned_files,
        allowed_files=set(wave_owned_files),
    )
    wave_owned_files = [
        path for path in wave_owned_files
        if path != receipt_rel
        and not path.startswith(".agent_bus/meta/pre_commit_receipts/")
        and path != ".agent_bus/executors/phase_b_handoff.json"
    ]
    if not wave_owned_files:
        return None, ["no wave-owned files available for dispatcher Phase B handoff rebuild"]

    handoff_files_to_stage, handoff_staged_deletions = _split_commit_handoff_stage_files(
        repo_root,
        wave_id,
        wave_owned_files,
    )
    if not handoff_files_to_stage:
        return None, ["no add-able files available for dispatcher Phase B handoff rebuild"]

    bridge_status = _build_effective_bridge_status(repo_root, wave_id, resolved_plan_path, 0)
    test_files = _select_pytest_gate_files(wave_owned_files, repo_root=repo_root)
    tracker_note_text = build_phase_b_tracker_note(
        wave_id=wave_id,
        task_id=str(routing_record.get("task_id") or plan.get("task_id") or f"[{wave_id}]"),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        plan_path=resolved_plan_path,
        plan_content=plan_content,
        changed_files=wave_owned_files,
        test_files=test_files,
        receipt_path=receipt_rel,
        bridge_rounds=_bridge_rounds_for_tracker_note(bridge_status),
        reentry=False,
        founder_override=str(plan.get("founder_override") or ""),
        unblocks_wave_id=str(plan.get("unblocks_wave_id") or ""),
        unblocks_runtime_blocker=str(plan.get("unblocks_runtime_blocker") or ""),
    )
    handoff_scope_items = list(dict.fromkeys([resolved_plan_path, *handoff_staged_deletions]))
    handoff_path = prepare_commit_handoff(
        repo_root,
        wave_id=wave_id,
        task_id=str(routing_record.get("task_id") or plan.get("task_id") or f"[{wave_id}]"),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        tracker_note_text=tracker_note_text,
        fixes_implemented=["Phase B handoff rebuilt by dispatcher recovery via Phase B builder"],
        files_to_stage=handoff_files_to_stage,
        pre_commit_receipt_path=receipt_rel,
        commit_message=f"feat: Phase B implementation for {wave_id}\n\nCo-Authored-By: Codex GPT-5.5 xhigh <noreply@openai.com>",
        pr_title=f"feat: Phase B - {wave_id}",
        pr_body=f"## Summary\nPhase B implementation per locked plan at {resolved_plan_path}",
        tracked_packet=resolved_plan_path,
        supervisor_lane="hooks/agents/bridge control-surface",
        deferred_items=_collect_supervisor_deferred_items(
            wave_owned_files,
            _canonical_deferred_packet_relpath(wave_id),
            repo_root=repo_root,
        ),
        bridge_status=bridge_status,
        scope_items=handoff_scope_items,
        evidence_handles={"indicator": f"reports/l4_wave_indicators/{wave_id}.json"},
        pager_route=str(routing_record.get("pager_route") or "").strip() or None,
        bus_dir=bus_dir,
    )
    return handoff_path, []


def _wave_bound_target_branch(
    observed_branch: str,
    *,
    wave_id: str,
    branch_prefix: str = "jabramsja",
) -> str:
    """Return only a canonical wave branch or a restart branch for that wave."""
    if not observed_branch or not wave_id or not branch_prefix:
        return ""
    canonical_branch = f"{branch_prefix}/{wave_id}"
    if observed_branch == canonical_branch:
        return observed_branch
    if observed_branch == f"{canonical_branch}-restart":
        return observed_branch
    if observed_branch.startswith(f"{canonical_branch}-restart-"):
        return observed_branch
    return ""


def _phase_b_target_branch_for_current_worktree(
    observed_branch: str,
    *,
    wave_id: str,
    wave_class: str,
    plan_content: str,
    branch_prefix: str = "jabramsja",
) -> str:
    """Return the commit target branch Phase B may preserve from the worktree."""
    wave_bound = _wave_bound_target_branch(
        observed_branch,
        wave_id=wave_id,
        branch_prefix=branch_prefix,
    )
    if wave_bound:
        return wave_bound
    if str(wave_class or "").strip() != "L4_ENABLER":
        return ""
    if "existing PR branch" not in plan_content:
        return ""
    if f"FOUNDER_OVERRIDE:{wave_id}" not in plan_content:
        return ""
    if observed_branch in ("dev", "main", "master", "HEAD"):
        return ""
    prefix = f"{branch_prefix}/"
    if not observed_branch.startswith(prefix):
        return ""
    if ".." in observed_branch or observed_branch.endswith("/"):
        return ""
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", observed_branch):
        return ""
    return observed_branch


def _launch_target_branch_authority_from_routing_record(
    routing_record: dict[str, Any],
    *,
    wave_id: str,
) -> tuple[str, str, str | None]:
    metadata = _candidate_authority_metadata_from_routing_record(routing_record)
    authority = (
        metadata.get("target_branch_authority")
        if isinstance(metadata, dict)
        else None
    )
    if authority is None:
        return "", "", None
    if not isinstance(authority, dict):
        return "", "", "launch target-branch authority must be a JSON object"
    target_branch = str(authority.get("target_branch") or "").strip()
    branch_prefix = str(authority.get("branch_prefix") or "").strip()
    if not target_branch or not branch_prefix:
        return "", "", "launch target-branch authority is missing target_branch or branch_prefix"
    if _wave_bound_target_branch(
        target_branch,
        wave_id=wave_id,
        branch_prefix=branch_prefix,
    ) != target_branch:
        return "", "", (
            "launch target-branch authority is not wave-bound: "
            f"{target_branch!r}"
        )
    return branch_prefix, target_branch, None


def _phase_b_tracker_scope_refs(changed_files: list[str], indicator_path: str, *, limit: int = 32) -> str:
    refs: list[str] = []
    for raw_path in [*changed_files, indicator_path]:
        path = str(raw_path or "").strip().replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        if not path or path in refs:
            continue
        refs.append(path)
    if not refs:
        return ""
    visible = refs[:limit]
    suffix = ""
    if len(refs) > limit:
        suffix = f", +{len(refs) - limit} more"
    return "scope_refs: " + ", ".join(f"`{path}`" for path in visible) + suffix + "."


def _phase_b_tracker_non_scope_note(plan_content: str, changed_files: list[str]) -> str:
    """Project explicit packet non-scope constraints into the tracker note."""
    if _phase_b_scope_has_runtime_substrate_file(changed_files):
        return ""
    normalized = " ".join(str(plan_content or "").split()).lower()
    if "optimization" not in normalized or "runtime/substrate" not in normalized:
        return ""
    if "seed" not in normalized or "parity" not in normalized:
        return ""
    return (
        "Optimization and production runtime/substrate/seed/parity edits remain out of scope. "
        "Optimization is LAST."
    )


def _build_phase_b_tracker_note(
    *,
    wave_id: str,
    task_id: str,
    wave_class: str = "L4_ENABLER",
    target_gate_id: str,
    plan_path: str,
    plan_content: str = "",
    changed_files: list[str],
    test_files: list[str],
    receipt_path: str,
    bridge_rounds: int,
    reentry: bool,
    post_gate_contract_sweep: str = "",
    founder_override: str = "",
    unblocks_wave_id: str = "",
    unblocks_runtime_blocker: str = "",
    pre_supervisor: bool = False,
) -> str:
    """Render an L4-compliant tracker note for a Phase B commit handoff."""
    display_task = (task_id or "").strip() or wave_id
    if display_task.startswith("[") and display_task.endswith("]"):
        display_task = display_task[1:-1]
    if not display_task:
        display_task = wave_id

    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"

    def _pytest_coverage_label(selectors: list[str]) -> str:
        test_paths: list[str] = []
        for selector in selectors:
            path = _pytest_selector_path(str(selector or "").strip())
            if path and path not in test_paths:
                test_paths.append(path)
        if len(selectors) == len(test_paths):
            return f"{len(test_paths)} test file(s)"
        return f"{len(selectors)} pytest selector(s) across {len(test_paths)} test file(s)"

    def _append_l4_files_contract(command: str) -> str:
        if wave_class != "L4_STRUCTURAL":
            return command
        contract_files: list[str] = []
        for path in [*changed_files, indicator_path]:
            normalized = str(path or "").strip()
            if normalized and normalized not in contract_files:
                contract_files.append(normalized)
        files_arg = " ".join(contract_files)
        return (
            f"{command} && python3 tools/checks/enforce_l4_execution_contract.py "
            f"--files {files_arg} --wave-id {wave_id} --wave-class {wave_class}"
        )

    effective_test_files = list(test_files)
    if not effective_test_files and wave_class == "L4_STRUCTURAL":
        effective_test_files = _select_pytest_gate_files(changed_files)
    if effective_test_files:
        pytest_coverage_label = _pytest_coverage_label(effective_test_files)
        evidence_command = _append_l4_files_contract(
            "PYTHONHASHSEED=0 python3 -m pytest -x --tb=short "
            + " ".join(effective_test_files)
        )
        if pre_supervisor:
            evidence_delta = (
                f"(1) Phase B converged on the locked plan at {plan_path}. "
                f"(2) Final pytest gate covered {pytest_coverage_label} from the wave-owned diff. "
                f"(3) Pre-commit supervisor package is staged at {receipt_path}; "
                "commit handoff receipt remains pending the supervisor decision."
            )
        else:
            evidence_delta = (
                f"(1) Phase B converged on the locked plan at {plan_path}. "
                f"(2) Final pytest gate covered {pytest_coverage_label} from the wave-owned diff. "
                f"(3) Commit handoff carries explicit receipt authority at {receipt_path}."
            )
    else:
        evidence_command = _append_l4_files_contract(
            f"python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
            f"--output {indicator_path}"
        )
        if pre_supervisor:
            evidence_delta = (
                f"(1) Phase B converged on the locked plan at {plan_path}. "
                f"(2) Pre-commit supervisor package is staged at {receipt_path} with "
                f"{len(changed_files)} wave-owned file(s). "
                "(3) No test files were present in the wave-owned diff, so indicator collection is the "
                "mechanical evidence surface."
            )
        else:
            evidence_delta = (
                f"(1) Phase B converged on the locked plan at {plan_path}. "
                f"(2) Commit handoff carries {len(changed_files)} wave-owned file(s) with explicit receipt "
                f"authority at {receipt_path}. "
                "(3) No test files were present in the wave-owned diff, so indicator collection is the "
                "mechanical evidence surface."
            )

    scope_refs = _phase_b_tracker_scope_refs(changed_files, indicator_path)
    non_scope_note = _phase_b_tracker_non_scope_note(plan_content, changed_files)
    if scope_refs:
        evidence_delta = f"{evidence_delta} {scope_refs}"
    if non_scope_note:
        evidence_delta = f"{evidence_delta} {non_scope_note}"

    if pre_supervisor:
        progress_before = (
            "Phase B could reach pre-commit supervisor review before TASKS.md contained a "
            "canonical tracker note for the wave, so Gate 2 and Gate 8 could not bind "
            "the package to trusted L4 authority."
        )
        progress_after = (
            f"Phase B staged a canonical tracker note for {wave_id} before pre-commit "
            f"supervisor validation with {len(changed_files)} wave-owned file(s), "
            f"bridge rounds={bridge_rounds}"
        )
        if reentry:
            progress_after += ", reentry=true"
        progress_after += ", and package-bound L4 authority."
    else:
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
    founder_override = _derive_phase_b_founder_override(
        plan_content=plan_content,
        wave_id=wave_id,
        wave_class=wave_class,
        explicit_founder_override=founder_override,
    )

    tracker_kwargs: dict[str, str] = {
        "evidence_command": evidence_command,
        "evidence_delta": evidence_delta,
        "progress_proof_before": progress_before,
        "progress_proof_after": progress_after,
    }
    runtime_comment_override = (
        (
            _plan_declares_classless_comment_only_runtime_override(plan_content)
            or _plan_declares_l4_enabler_runtime_text_override(plan_content)
        )
        and _phase_b_scope_has_runtime_substrate_file(changed_files)
    )
    if not wave_class or (wave_class == "L4_ENABLER" and runtime_comment_override):
        tracker_kwargs["no_op_proof"] = (
            "wave-owned runtime/substrate edits are comment-only debt-map text "
            "with zero executable runtime delta, bound to the same-wave "
            "FOUNDER_OVERRIDE and revalidated from the staged diff"
        )
    if wave_class == "L4_STRUCTURAL":
        tracker_kwargs.update({
            "workload_target": _infer_structural_workload_target(changed_files, plan_content),
            "host_semantics_delta_before": (
                "host semantics ratchet baseline and authority inventory baseline before this wave; "
                "runtime or substrate scope is allowed only as a parity-preserving structural reduction "
                "without new host authority sites"
            ),
            "host_semantics_delta_after": (
                "host semantics ratchet remains unchanged after this wave; indicator net_host_semantic_delta=0 "
                "and authority inventory must remain at baseline for commit"
            ),
            "structural_artifact_ref": _summarize_structural_artifacts(changed_files),
            "post_gate_contract_sweep": (
                post_gate_contract_sweep
                or _build_structural_post_gate_sweep(effective_test_files, changed_files)
            ),
        })
    if wave_class == "MAINTENANCE":
        runtime_like = [
            path for path in changed_files
            if path.startswith(_MAINTENANCE_FORBIDDEN_PREFIXES)
        ]
        if runtime_like:
            offenders = ", ".join(runtime_like[:3])
            if len(runtime_like) > 3:
                offenders += f" (+{len(runtime_like) - 3} more)"
            raise PhaseBExecutorError(
                "MAINTENANCE Phase B handoff cannot claim no-op proof while wave-owned files include "
                f"runtime/substrate paths: {offenders}"
            )
        tracker_kwargs.update({
            "no_op_proof": (
                "wave-owned scope is limited to control-surface/tooling/test/doc files; "
                f"no host/runtime/substrate paths are present in this handoff ({len(changed_files)} file(s))"
            ),
            "defer_reason_code": "PIPELINE_HARDENING",
        })
        if not (unblocks_wave_id and unblocks_runtime_blocker):
            extracted_wave_id, extracted_runtime_blocker = _extract_maintenance_bypass_fields(
                plan_content,
            )
            if extracted_wave_id and extracted_runtime_blocker:
                unblocks_wave_id = unblocks_wave_id or extracted_wave_id
                unblocks_runtime_blocker = unblocks_runtime_blocker or extracted_runtime_blocker
        if unblocks_wave_id:
            tracker_kwargs["unblocks_wave_id"] = unblocks_wave_id
        if unblocks_runtime_blocker:
            tracker_kwargs["unblocks_runtime_blocker"] = unblocks_runtime_blocker

    fields = TrackerSyncNoteFields(
        wave_id=wave_id,
        title=(
            f"{display_task} — Phase B pre-commit supervisor package"
            if pre_supervisor
            else f"{display_task} — commit-ready Phase B handoff"
        ),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        packet_ref=plan_path if plan_path and not plan_path.startswith("<") else "",
        primary_blocker_class="INTEGRATION",
        primary_invariant_id="INV_STRUCTURAL_FORWARD_MOTION",
        indicator_artifact_ref=indicator_path,
        indicator_collection_command=(
            f"python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id {wave_id} "
            f"--output {indicator_path}"
        ),
        founder_override=founder_override,
        **tracker_kwargs,
    )
    return render_tracker_sync_note(fields)


def _load_commit_executor_for_tracker_sync() -> Any:
    try:
        import commit_executor
        return commit_executor
    except ImportError:
        import importlib.util as _ilu

        _commit_path = SCRIPT_DIR / "commit_executor.py"
        _commit_spec = _ilu.spec_from_file_location("commit_executor", str(_commit_path))
        _commit_mod = _ilu.module_from_spec(_commit_spec)
        assert _commit_spec.loader is not None
        _commit_spec.loader.exec_module(_commit_mod)
        return _commit_mod


def _strip_tracker_inline_code(value: str) -> str:
    text = str(value or "").strip()
    if text.startswith("`") and text.endswith("`."):
        return text[1:-2].strip()
    if text.startswith("`") and text.endswith("`"):
        return text[1:-1].strip()
    return text


def _tracker_evidence_command_value(tracker_note_text: str) -> str:
    commit_mod = _load_commit_executor_for_tracker_sync()
    return _strip_tracker_inline_code(
        commit_mod._tracker_marker_value(tracker_note_text, "evidence_command")
    )


def _sync_phase_b_tasks_tracker_note(
    repo_root: Path,
    *,
    wave_id: str,
    tracker_note_text: str,
) -> tuple[str | None, bool]:
    """Insert or refresh the canonical Phase B tracker note before supervisor review."""
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return None, False

    commit_mod = _load_commit_executor_for_tracker_sync()
    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    ra_idx, ra_end_idx = commit_mod._find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return None, False

    global_matcher = getattr(commit_mod, "_matching_tracker_note_indices", None)
    if callable(global_matcher):
        matching_tracker_indices = global_matcher(lines, wave_id)
    else:
        matching_tracker_indices = commit_mod._matching_tracker_note_indices_in_range(
            lines,
            wave_id,
            start_idx=0,
            end_idx=len(lines),
        )

    note_line = tracker_note_text if tracker_note_text.endswith("\n") else tracker_note_text + "\n"
    existing_idx = (
        matching_tracker_indices[0] if len(matching_tracker_indices) == 1 else None
    )
    last_tracker_idx = None
    for idx in range(ra_idx + 1, ra_end_idx):
        if lines[idx].strip().startswith("- Tracker sync note"):
            last_tracker_idx = idx
    if existing_idx is not None and lines[existing_idx] == note_line and existing_idx == last_tracker_idx:
        return None, False
    for idx in sorted(matching_tracker_indices, reverse=True):
        lines.pop(idx)

    ra_idx, ra_end_idx = commit_mod._find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return None, False

    last_tracker_idx = None
    for idx in range(ra_idx + 1, ra_end_idx):
        if lines[idx].strip().startswith("- Tracker sync note"):
            last_tracker_idx = idx
    insert_idx = last_tracker_idx + 1 if last_tracker_idx is not None else ra_idx + 1
    lines.insert(insert_idx, note_line)

    tasks_path.write_text("".join(lines), encoding="utf-8")
    return None, True


def _collect_and_stage_l4_indicator_artifact(
    repo_root: Path,
    *,
    wave_id: str,
) -> tuple[str | None, str | None]:
    """Collect and stage the L4 indicator artifact required by tracker notes."""
    if not normalize_wave_id(wave_id):
        return None, "cannot collect L4 indicator artifact without a canonical wave_id"
    indicator_script = repo_root / "mu" / "tools" / "metrics" / "collect_l4_wave_indicators.py"
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    if not indicator_script.exists():
        return None, f"Indicator collector script not found: {indicator_script}"
    try:
        collect_result = subprocess.run(
            [
                sys.executable,
                str(indicator_script),
                "--wave-id",
                wave_id,
                "--output",
                indicator_path,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return None, "Indicator collection timed out after 120s"
    if collect_result.returncode != 0:
        detail = (collect_result.stderr or collect_result.stdout or "").strip()
        if len(detail) > 500:
            detail = detail[:500] + "..."
        return None, (
            f"Indicator collection failed with exit={collect_result.returncode}: "
            f"{detail or '(no output)'}"
        )
    if not (repo_root / indicator_path).exists():
        return None, f"Indicator artifact not created: {indicator_path}"
    try:
        subprocess.run(
            ["git", "add", "-f", "--", indicator_path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        return None, f"git add -f failed for {indicator_path}: {detail or '(no output)'}"
    return indicator_path, None


def _dedupe_phase_b_repo_paths(paths: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        relpath = str(path or "").strip().replace("\\", "/")
        while relpath.startswith("./"):
            relpath = relpath[2:]
        if not relpath or relpath in seen:
            continue
        seen.add(relpath)
        deduped.append(relpath)
    return deduped


def _render_phase_b_indicator_scope_refresh_block(
    *,
    wave_id: str,
    plan_path: str,
    indicator_path: str,
    changed_files: list[str],
    broad_package_snapshot: bool = False,
) -> str:
    if broad_package_snapshot:
        staged_paths = sorted(
            _dedupe_phase_b_repo_paths([*changed_files, indicator_path, plan_path])
        )
    else:
        staged_paths = _dedupe_phase_b_repo_paths(changed_files)
    lines = [
        PHASE_B_INDICATOR_SCOPE_REFRESH_START,
        "## Phase B Indicator Scope Reconciliation",
        "",
    ]
    if broad_package_snapshot:
        lines.extend([
            PHASE_B_INDICATOR_SCOPE_BROAD_SNAPSHOT_MARKER,
            "",
        ])
    lines.extend([
        f"- Refresh wave: `{wave_id}`",
        f"- Active packet: `{plan_path}`",
        f"- Indicator artifact: `{indicator_path}`",
        "- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator "
        "before review so the tracker note, Gate 8 package, and "
        "governing packet describe one staged scope.",
        "- Scope binding: no indicator file other than the artifact above is in scope for this wave.",
        "- Authorized staged files:",
    ])
    for path in staged_paths:
        lines.append(f"  - `{path}`")
    lines.append(PHASE_B_INDICATOR_SCOPE_REFRESH_END)
    return "\n".join(lines) + "\n"


def _replace_phase_b_indicator_scope_refresh_block(packet_text: str, block: str) -> str:
    start = packet_text.find(PHASE_B_INDICATOR_SCOPE_REFRESH_START)
    end = packet_text.find(PHASE_B_INDICATOR_SCOPE_REFRESH_END)
    if start != -1 and end != -1 and end > start:
        end += len(PHASE_B_INDICATOR_SCOPE_REFRESH_END)
        trailing_newline = "\n" if end < len(packet_text) and packet_text[end:end + 1] != "\n" else ""
        return packet_text[:start].rstrip() + "\n\n" + block.rstrip() + trailing_newline + packet_text[end:]
    if start != -1 or end != -1:
        raise ValueError("existing Phase B indicator scope refresh markers are unbalanced")
    return packet_text.rstrip() + "\n\n" + block


def _reconcile_phase_b_indicator_scope_text(packet_text: str, *, indicator_path: str) -> str:
    exact_scope = (
        "Indicator scope is limited to the exact same-wave artifact "
        f"`{indicator_path}`, mechanically collected and staged by Phase B before "
        "pre-commit supervisor review. No other indicator file is in scope."
    )
    refreshed = re.sub(
        r"(?m)^No indicator file is in scope[^\n]*(?:\n|$)",
        exact_scope + "\n",
        packet_text,
    )
    refreshed = re.sub(
        r"(?m)^(\d+\.\s+After implementation is locked and validated, update only .*?)"
        r"\s+Do not update indicator files unless [^\n]*$",
        rf"\1 Update only `{indicator_path}` when Phase B or commit automation "
        "mechanically collects the same-wave L4 indicator artifact.",
        refreshed,
    )
    refreshed = re.sub(
        r"(?m)^- Do not touch indicator files without [^\n]*$",
        f"- Do not touch indicator files other than `{indicator_path}`; it is the exact "
        "same-wave L4 artifact authorized by this Phase B indicator scope reconciliation.",
        refreshed,
    )
    refreshed = re.sub(
        r"(?m)^- Aside from the same-wave `TASKS\.md` tracker entry required to bind "
        r"this packet, this packet does not authorize creation of a new report, indicator,"
        r"([^\n]*)$",
        f"- Aside from the same-wave `TASKS.md` tracker entry and exact same-wave "
        f"indicator artifact `{indicator_path}` required for commit packaging, this packet "
        r"does not authorize creation of a new report,\1",
        refreshed,
    )
    refreshed = re.sub(
        r"(?m)^- Closeout updates, if any, are limited to directly required "
        r"`TASKS\.md` lines and this governing packet unless [^\n]*$",
        f"- Closeout updates may include directly required `TASKS.md` lines, this governing "
        f"packet, and exact same-wave indicator artifact `{indicator_path}`; all closeout "
        "text must cite the validation that proved the implementation.",
        refreshed,
    )
    refreshed = re.sub(
        r"No Phase B runtime, marker, ratchet-baseline, indicator, or successor packet\n"
        r"write set is authorized by this decision\.",
        "No Phase B runtime, marker, ratchet-baseline, or successor packet\n"
        "write set is authorized by this decision. The exact same-wave indicator\n"
        f"artifact `{indicator_path}` is authorized only for mechanical commit packaging.",
        refreshed,
    )
    return refreshed.replace(
        "No indicator file was touched.",
        f"Indicator artifact `{indicator_path}` was collected and staged mechanically before "
        "pre-commit supervisor review.",
    )


def _refresh_phase_b_indicator_packet_scope(
    repo_root: Path,
    *,
    plan_path: str,
    wave_id: str,
    indicator_path: str,
    changed_files: list[str],
) -> tuple[bool, str | None]:
    """Refresh the active packet when Phase B adds a same-wave L4 indicator."""
    packet_rel = str(plan_path or "").strip()
    indicator_rel = str(indicator_path or "").strip()
    normalized_wave = normalize_wave_id(str(wave_id or ""))
    if not packet_rel or packet_rel.startswith("<"):
        return False, None
    if not normalized_wave:
        return False, "cannot refresh Phase B indicator packet scope without a canonical wave_id"
    if not indicator_rel:
        return False, "cannot refresh Phase B indicator packet scope without an indicator path"
    if indicator_rel != f"reports/l4_wave_indicators/{normalized_wave}.json":
        return False, (
            "indicator path does not match same-wave L4 indicator artifact: "
            f"{indicator_rel} (wave_id={normalized_wave})"
        )

    packet_full = (repo_root / packet_rel).resolve()
    repo_resolved = repo_root.resolve()
    if not packet_full.is_relative_to(repo_resolved):
        return False, f"active packet escapes repo root: {packet_rel}"
    if not packet_full.exists():
        return False, f"active packet not found for Phase B indicator scope refresh: {packet_rel}"

    try:
        packet_text = packet_full.read_text(encoding="utf-8")
        packet_mode = stat.S_IMODE(os.stat(packet_full).st_mode)
    except OSError as exc:
        return False, (
            "cannot read active packet for Phase B indicator scope refresh: "
            f"{packet_rel}: {exc}"
        )
    original_exact_scope = _parse_exact_stage_scope_files(packet_text)
    _tasks, waves = _extract_authoritative_plan_header_metadata(packet_text)
    routed_candidates = _extract_authoritative_routed_retained_candidates(packet_text)
    identity_matches_wave = waves == [normalized_wave]
    identity_matches_routed_candidate = (
        len(waves) == 1
        and routed_candidates == [normalized_wave]
    )
    if not identity_matches_wave and not identity_matches_routed_candidate:
        return False, (
            "active packet missing unique matching Wave ID or routed retained candidate "
            "for Phase B indicator scope refresh: "
            f"{packet_rel} (wave_id={normalized_wave})"
        )

    refreshed = _reconcile_phase_b_indicator_scope_text(
        packet_text,
        indicator_path=indicator_rel,
    )
    block = _render_phase_b_indicator_scope_refresh_block(
        wave_id=normalized_wave,
        plan_path=packet_rel,
        indicator_path=indicator_rel,
        changed_files=original_exact_scope or changed_files,
        broad_package_snapshot=not bool(original_exact_scope),
    )
    try:
        refreshed = _replace_phase_b_indicator_scope_refresh_block(refreshed, block)
    except ValueError as exc:
        return False, str(exc)
    if refreshed == packet_text:
        return False, None

    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            dir=str(packet_full.parent),
            prefix=f".{packet_full.name}.",
            suffix=".tmp",
        )
        tmp_path = Path(tmp_name)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(refreshed)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, packet_mode)
        os.replace(tmp_path, packet_full)
    except BaseException as exc:
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return False, (
            "atomic Phase B indicator packet scope refresh failed for "
            f"{packet_rel}: {exc}"
        )
    ok, detail = _stage_files_for_pipeline(repo_root, [packet_rel])
    if not ok:
        return False, f"git add failed for refreshed packet {packet_rel}: {detail}"
    return True, None


def _tasks_has_canonical_wave_tracker_note(repo_root: Path, *, wave_id: str) -> bool:
    """Return True when TASKS.md carries trusted same-wave tracker authority."""
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return False

    commit_mod = _load_commit_executor_for_tracker_sync()
    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    ra_idx, ra_end_idx = commit_mod._find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return False

    matching_tracker_indices = commit_mod._matching_tracker_note_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical_tracker_indices = [
        idx
        for idx in matching_tracker_indices
        if commit_mod._is_canonical_tracker_note_line(
            lines[idx].rstrip("\n"),
            wave_id,
        )
    ]
    return (
        len(matching_tracker_indices) == 1
        and len(canonical_tracker_indices) == 1
    )


def _should_collect_l4_indicator_artifact(
    repo_root: Path,
    *,
    wave_id: str,
    wave_class: str,
    tracker_note_modified: bool,
    founder_override_token: str,
    changed_files: list[str],
) -> bool:
    if wave_class not in {"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"} or not wave_id:
        return False
    if not (repo_root / "TASKS.md").exists():
        return False
    indicator_path = f"reports/l4_wave_indicators/{wave_id}.json"
    return (
        tracker_note_modified
        or bool(founder_override_token)
        or indicator_path not in changed_files
        or not (repo_root / indicator_path).exists()
    )


def _phase_b_same_wave_indicator_path(wave_id: str) -> str:
    return f"reports/l4_wave_indicators/{wave_id}.json"


def _candidate_authority_spec_path(repo_root: Path, *, wave_id: str) -> Path:
    return agent_bus_path(
        repo_root,
        _active_bus_dir(),
        "meta",
        "candidate_authority",
        f"{wave_id}.spec.json",
    )


def _candidate_authority_required_from_routing_record(
    routing_record: dict[str, Any],
) -> bool:
    metadata = routing_record.get("candidate_authority")
    if isinstance(metadata, dict) and isinstance(metadata.get("required"), bool):
        return metadata["required"]
    required = routing_record.get("candidate_authority_required")
    return required if isinstance(required, bool) else False


def _candidate_authority_metadata_from_routing_record(
    routing_record: dict[str, Any],
) -> dict[str, Any] | None:
    metadata = routing_record.get("candidate_authority")
    return metadata if isinstance(metadata, dict) else None


def _prepare_candidate_authority_if_configured(
    repo_root: Path,
    *,
    wave_id: str,
    phase: str,
    review_round: str,
    context: str,
    required: bool = True,
    trusted_metadata: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """Run launch-owned candidate authority before reviewer entry."""
    spec_path = _candidate_authority_spec_path(repo_root, wave_id=wave_id)
    if trusted_metadata is not None:
        trusted_spec_path = str(trusted_metadata.get("spec_path") or "").strip()
        if trusted_spec_path:
            spec_path = Path(trusted_spec_path)
            if not spec_path.is_absolute():
                spec_path = repo_root / spec_path
        elif required:
            return None, (
                f"Candidate authority launch metadata is required before {context}: "
                "missing spec_path"
            )
    if not spec_path.exists():
        if not required:
            return None, None
        return None, (
            f"Candidate authority spec is required before {context}: "
            f"missing {spec_path}"
        )
    try:
        base_spec = _candidate_authority.load_authority_spec(spec_path)
        trusted_identity = (
            trusted_metadata.get("spec_identity")
            if isinstance(trusted_metadata, dict)
            else None
        )
        if trusted_identity is None:
            if required:
                return None, (
                    "Candidate authority launch-bound spec identity is required "
                    f"before {context}"
                )
        else:
            _candidate_authority.verify_authority_spec_identity(
                repo_root,
                base_spec,
                trusted_identity,
            )
        spec = _candidate_authority.CandidateAuthoritySpec.from_mapping(
            {
                **base_spec.to_dict(),
                "phase": phase,
                "review_round": review_round,
            }
        )
        receipt = _candidate_authority.prepare_candidate_authority(
            repo_root,
            spec,
            bus_dir=_active_bus_dir(),
        )
    except _candidate_authority.CandidateAuthorityError as exc:
        return None, (
            f"Candidate authority failed before {context}: {exc}"
        )
    receipt_path = str(receipt.get("receipt_path") or "")
    try:
        _candidate_authority.verify_current_receipt(
            repo_root,
            Path(receipt_path),
            trusted_spec=spec,
            phase=phase,
            review_round=review_round,
        )
    except _candidate_authority.CandidateAuthorityError as exc:
        return None, (
            f"Candidate authority receipt verification failed before {context}: {exc}"
        )
    return receipt_path, None


def prepare_candidate_authority_if_configured(
    repo_root: Path,
    *,
    wave_id: str,
    phase: str,
    review_round: str,
    context: str,
    required: bool = True,
    trusted_metadata: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """Public review-entry seam for candidate authority refresh."""
    return _prepare_candidate_authority_if_configured(
        repo_root,
        wave_id=wave_id,
        phase=phase,
        review_round=review_round,
        context=context,
        required=required,
        trusted_metadata=trusted_metadata,
    )


def _guard_candidate_authority_scope_if_configured(
    repo_root: Path,
    *,
    wave_id: str,
    context: str,
    required: bool,
    trusted_metadata: dict[str, Any] | None,
) -> str | None:
    spec_path = _candidate_authority_spec_path(repo_root, wave_id=wave_id)
    if trusted_metadata is not None:
        trusted_spec_path = str(trusted_metadata.get("spec_path") or "").strip()
        if trusted_spec_path:
            spec_path = Path(trusted_spec_path)
            if not spec_path.is_absolute():
                spec_path = repo_root / spec_path
        elif required:
            return (
                f"Candidate authority launch metadata is required before {context}: "
                "missing spec_path"
            )
    if not spec_path.exists():
        if not required:
            return None
        return f"Candidate authority spec is required before {context}: missing {spec_path}"
    try:
        base_spec = _candidate_authority.load_authority_spec(spec_path)
        trusted_identity = (
            trusted_metadata.get("spec_identity")
            if isinstance(trusted_metadata, dict)
            else None
        )
        if trusted_identity is None:
            if required:
                return (
                    "Candidate authority launch-bound spec identity is required "
                    f"before {context}"
                )
        else:
            _candidate_authority.verify_authority_spec_identity(
                repo_root,
                base_spec,
                trusted_identity,
            )
        _candidate_authority.guard_candidate_scope_before_mutation(repo_root, base_spec)
    except _candidate_authority.CandidateAuthorityError as exc:
        return f"Candidate authority scope guard failed before {context}: {exc}"
    return None


def _prepare_phase_b_pre_review_package(
    repo_root: Path,
    *,
    candidate_files: list[str],
    exact_stage_scope_files: set[str],
    plan_path: str,
    wave_id: str,
    wave_class: str,
    step_prefix: str,
    context: str,
    candidate_authority_required: bool = False,
    candidate_authority_metadata: dict[str, Any] | None = None,
) -> tuple[list[str], dict[str, Any] | None]:
    """Prepare one complete, staged Phase B package before bridge review."""
    prepared_files = [
        path for path in _dedupe_phase_b_repo_paths(candidate_files)
        if not _is_phase_b_indicator_scope_refresh_temp_path(path, plan_path)
    ]
    if plan_path and not plan_path.startswith("<") and plan_path not in prepared_files:
        prepared_files.append(plan_path)

    def _failure(
        suffix: str,
        message: str,
        *,
        detail: str = "",
    ) -> tuple[list[str], dict[str, Any]]:
        errors = [message]
        if detail and detail != message:
            errors.append(detail)
        error: dict[str, Any] = {
            "status": "error",
            "step": f"{step_prefix}_{suffix}",
            "errors": errors,
        }
        if detail:
            error["stderr"] = detail
        return prepared_files, error

    normalized_wave = ""
    if not plan_path.startswith("<planless:") and wave_class in {
        "L4_STRUCTURAL",
        "L4_ENABLER",
        "MAINTENANCE",
    }:
        normalized_wave = normalize_wave_id(str(wave_id or ""))
        if not normalized_wave:
            return _failure(
                "tracker_authority",
                f"Canonical same-wave TASKS authority is unavailable before {context}: "
                "wave_id is missing or invalid",
            )
        authority_guard_error = _guard_candidate_authority_scope_if_configured(
            repo_root,
            wave_id=normalized_wave,
            context=f"{context} collector",
            required=candidate_authority_required,
            trusted_metadata=candidate_authority_metadata,
        )
        if authority_guard_error is not None:
            return _failure(
                "candidate_authority_scope",
                f"Candidate authority scope is required before {context}",
                detail=authority_guard_error,
            )

    staged_files = set(_collect_staged_files(repo_root))
    staged_refresh_temps = {
        path
        for path in staged_files
        if _is_phase_b_indicator_scope_refresh_temp_path(path, plan_path)
    }
    if staged_refresh_temps:
        reconciled_ok, reconciled_detail = _unstage_out_of_exact_scope(
            repo_root,
            staged_files - staged_refresh_temps,
        )
        if not reconciled_ok:
            return _failure(
                "scope_reconcile",
                f"Failed to exclude stale packet-refresh temporary files before {context}",
                detail=reconciled_detail,
            )

    exact_scope = set(exact_stage_scope_files)
    if exact_scope:
        reconciled_ok, reconciled_detail = _unstage_out_of_exact_scope(
            repo_root,
            exact_scope,
        )
        if not reconciled_ok:
            return _failure(
                "scope_reconcile",
                f"Failed to reconcile exact staged scope before {context}",
                detail=reconciled_detail,
            )
        out_of_scope = sorted(path for path in prepared_files if path not in exact_scope)
        if out_of_scope:
            return _failure(
                "scope_reconcile",
                f"Current Phase B candidate exceeds exact staged scope before {context}",
                detail=", ".join(out_of_scope),
            )

    if prepared_files:
        staged_ok, stage_detail = _stage_files_for_pipeline(
            repo_root,
            prepared_files,
        )
        if not staged_ok:
            return _failure(
                "staging",
                f"Failed to stage current Phase B candidate before {context}",
                detail=stage_detail,
            )

    if plan_path.startswith("<planless:"):
        return prepared_files, None

    if wave_class not in {"L4_STRUCTURAL", "L4_ENABLER", "MAINTENANCE"}:
        return prepared_files, None

    try:
        tracker_authorized = _tasks_has_canonical_wave_tracker_note(
            repo_root,
            wave_id=normalized_wave,
        )
    except Exception as exc:
        return _failure(
            "tracker_authority",
            f"Canonical same-wave TASKS authority check failed before {context}",
            detail=str(exc),
        )
    if not tracker_authorized:
        return _failure(
            "tracker_authority",
            f"Canonical same-wave TASKS authority is required before {context}: "
            f"{normalized_wave}",
        )

    indicator_path = _phase_b_same_wave_indicator_path(normalized_wave)
    if exact_scope and indicator_path not in exact_scope:
        return _failure(
            "scope_reconcile",
            f"Canonical same-wave indicator is outside exact staged scope before {context}",
            detail=indicator_path,
        )
    try:
        collected_path, indicator_error = _collect_and_stage_l4_indicator_artifact(
            repo_root,
            wave_id=normalized_wave,
        )
    except Exception as exc:
        return _failure(
            "l4_indicator",
            f"Canonical same-wave indicator collection failed before {context}",
            detail=str(exc),
        )
    if indicator_error is not None:
        return _failure(
            "l4_indicator",
            f"Canonical same-wave indicator preparation failed before {context}",
            detail=indicator_error,
        )
    if collected_path != indicator_path:
        return _failure(
            "l4_indicator",
            f"Canonical collector returned the wrong same-wave indicator before {context}",
            detail=f"expected {indicator_path}, got {collected_path or '(none)'}",
        )
    if indicator_path not in prepared_files:
        prepared_files.append(indicator_path)

    try:
        _packet_modified, packet_error = _refresh_phase_b_indicator_packet_scope(
            repo_root,
            plan_path=plan_path,
            wave_id=normalized_wave,
            indicator_path=indicator_path,
            changed_files=prepared_files,
        )
    except Exception as exc:
        return _failure(
            "indicator_scope",
            f"Governing packet scope refresh failed before {context}",
            detail=str(exc),
        )
    if packet_error is not None:
        return _failure(
            "indicator_scope",
            f"Governing packet scope refresh failed before {context}",
            detail=packet_error,
        )
    _receipt_path, authority_error = prepare_candidate_authority_if_configured(
        repo_root,
        wave_id=normalized_wave,
        phase="phase_b",
        review_round=PHASE_B_BRIDGE_AUTHORITY_ROUND,
        context=context,
        required=candidate_authority_required,
        trusted_metadata=candidate_authority_metadata,
    )
    if authority_error is not None:
        return _failure(
            "candidate_authority",
            f"Candidate authority is required before {context}",
            detail=authority_error,
        )
    return prepared_files, None


def _phase_b_pre_supervisor_note_scope(changed_files: list[str]) -> list[str]:
    return sorted({*changed_files, "TASKS.md"})


def _verify_phase_b_pre_supervisor_tracker_note(
    repo_root: Path,
    *,
    wave_id: str,
    expected_note_text: str,
    changed_files: list[str],
) -> str | None:
    """Fail closed when the final package scope and latest tracker note diverge."""
    tasks_path = repo_root / "TASKS.md"
    if not tasks_path.exists():
        return None

    expected_indicator = _phase_b_same_wave_indicator_path(wave_id)
    if expected_indicator not in changed_files:
        return (
            "pre-supervisor tracker note verification failed: same-wave "
            f"indicator '{expected_indicator}' is not in the final supervisor scope"
        )

    commit_mod = _load_commit_executor_for_tracker_sync()
    lines = tasks_path.read_text(encoding="utf-8").splitlines(keepends=True)
    ra_idx, ra_end_idx = commit_mod._find_ra_section_range(lines)
    if ra_idx is None or ra_end_idx is None:
        return "pre-supervisor tracker note verification failed: TASKS.md has no Ra tracker section"

    tracker_indices = [
        idx
        for idx in range(ra_idx + 1, ra_end_idx)
        if lines[idx].strip().startswith("- Tracker sync note")
    ]
    if not tracker_indices:
        return "pre-supervisor tracker note verification failed: TASKS.md has no tracker notes"

    top_idx = tracker_indices[-1]
    matching_indices = commit_mod._matching_tracker_note_indices_in_range(
        lines,
        wave_id,
        start_idx=ra_idx,
        end_idx=ra_end_idx,
    )
    canonical_indices = [
        idx
        for idx in matching_indices
        if commit_mod._is_canonical_tracker_note_line(lines[idx].rstrip("\n"), wave_id)
    ]
    if canonical_indices != [top_idx]:
        return (
            "pre-supervisor tracker note verification failed: latest tracker "
            f"note is not the canonical note for wave_id '{wave_id}'"
        )

    expected_line = expected_note_text.rstrip("\n")
    observed_line = lines[top_idx].rstrip("\n")
    if observed_line != expected_line:
        return (
            "pre-supervisor tracker note verification failed: latest tracker "
            "note does not match the final supervisor scope"
        )

    checker = repo_root / "tools" / "checks" / "enforce_l4_execution_contract.py"
    if checker.exists():
        check = subprocess.run(
            [
                "python3",
                "tools/checks/enforce_l4_execution_contract.py",
                "--staged",
                "--wave-id",
                wave_id,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if check.returncode != 0:
            detail = (check.stdout + "\n" + check.stderr).strip()
            return (
                "pre-supervisor tracker note verification failed: L4 execution "
                f"contract rejected final staged scope (exit={check.returncode}): "
                f"{detail[:1200]}"
            )

    return None


def _finalize_phase_b_pre_supervisor_tracker_note(
    repo_root: Path,
    *,
    wave_id: str,
    task_id: str,
    wave_class: str,
    target_gate_id: str,
    plan_path: str,
    plan_content: str,
    changed_files: list[str],
    test_files: list[str],
    receipt_path: str,
    bridge_status: dict[str, Any],
    reentry: bool,
    founder_override: str = "",
    unblocks_wave_id: str = "",
    unblocks_runtime_blocker: str = "",
    allowed_files: set[str] | None = None,
) -> tuple[str, str, str, bool, list[str], str | None]:
    """Render/stage the final pre-supervisor tracker note after scope refresh."""
    final_scope = _phase_b_pre_supervisor_note_scope(changed_files)
    modified_any = False
    tracker_note = ""
    raw_founder_override = ""
    package_founder_override = ""

    for _attempt in range(2):
        note_wave_class = _effective_phase_b_tracker_wave_class(
            wave_class,
            plan_content=plan_content,
            changed_files=final_scope,
        )
        tracker_note = build_phase_b_tracker_note(
            wave_id=wave_id,
            task_id=task_id,
            wave_class=note_wave_class,
            target_gate_id=target_gate_id,
            plan_path=plan_path,
            plan_content=plan_content,
            changed_files=final_scope,
            test_files=test_files,
            receipt_path=receipt_path,
            bridge_rounds=_bridge_rounds_for_tracker_note(bridge_status),
            reentry=reentry,
            founder_override=founder_override,
            unblocks_wave_id=unblocks_wave_id,
            unblocks_runtime_blocker=unblocks_runtime_blocker,
            pre_supervisor=True,
        )
        raw_founder_override = _extract_founder_override_from_tracker_note(tracker_note)
        package_founder_override = _supervisor_package_founder_override_token(
            raw_founder_override,
            wave_class=note_wave_class,
        )
        tracker_sync_error, tracker_note_modified = _sync_phase_b_tasks_tracker_note(
            repo_root,
            wave_id=wave_id,
            tracker_note_text=tracker_note,
        )
        if tracker_sync_error is not None:
            return tracker_note, raw_founder_override, package_founder_override, modified_any, final_scope, tracker_sync_error
        if tracker_note_modified:
            modified_any = True
            ok, detail = _stage_files_for_pipeline(repo_root, ["TASKS.md"])
            if not ok:
                return (
                    tracker_note,
                    raw_founder_override,
                    package_founder_override,
                    modified_any,
                    final_scope,
                    f"git add failed for final Phase B tracker note: {detail}",
                )

        refreshed_scope = _phase_b_pre_supervisor_note_scope(
            _collect_commit_bound_files(
                repo_root,
                final_scope,
                allowed_files=allowed_files,
            )
        )
        if refreshed_scope == final_scope:
            verify_error = _verify_phase_b_pre_supervisor_tracker_note(
                repo_root,
                wave_id=wave_id,
                expected_note_text=tracker_note,
                changed_files=final_scope,
            )
            return (
                tracker_note,
                raw_founder_override,
                package_founder_override,
                modified_any,
                final_scope,
                verify_error,
            )
        final_scope = refreshed_scope

    verify_error = _verify_phase_b_pre_supervisor_tracker_note(
        repo_root,
        wave_id=wave_id,
        expected_note_text=tracker_note,
        changed_files=final_scope,
    )
    return (
        tracker_note,
        raw_founder_override,
        package_founder_override,
        modified_any,
        final_scope,
        verify_error,
    )


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
    request = routing_record.get("request_for_agent") or routing_record.get("request_for_claude", "")
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


_IMPLEMENTER_DIAGNOSTIC_FIELDS = ("error_subtype", "stop_reason", "num_turns")


def _copy_implementer_diagnostics(
    target: dict[str, Any],
    impl_result: dict[str, Any],
) -> None:
    for field in _IMPLEMENTER_DIAGNOSTIC_FIELDS:
        if field in impl_result and impl_result[field] not in (None, ""):
            target[field] = impl_result[field]


def _implementer_failure_result(
    *,
    step: str,
    message: str,
    impl_result: dict[str, Any],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "error",
        "step": step,
        "errors": [message],
        "implementer_status": impl_result.get("status"),
    }
    _copy_implementer_diagnostics(result, impl_result)
    return result


def run_phase_b(
    repo_root: Path,
    plan_path: str | None = None,
    *,
    max_bridge_rounds: int = 10,
    verbose: bool = False,
    force: bool = False,
    routing_record_override: dict[str, Any] | None = None,
    bus_dir: str | Path | None = None,
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
    if bus_dir is not None:
        try:
            resolve_agent_bus_dir(repo_root, bus_dir)
        except ExecutorCommonError as exc:
            return {"status": "error", "step": "bus_dir", "errors": [str(exc)]}
        token = _ACTIVE_BUS_DIR.set(agent_bus_relpath(bus_dir))
        try:
            return run_phase_b(
                repo_root,
                plan_path,
                max_bridge_rounds=max_bridge_rounds,
                verbose=verbose,
                force=force,
                routing_record_override=routing_record_override,
            )
        finally:
            _ACTIVE_BUS_DIR.reset(token)
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

    def _activate_matching_saved_state(saved: dict[str, Any]) -> str | dict[str, Any]:
        shape_error = _validate_resumable_state_shape(_state_file_path(repo_root), saved)
        if shape_error is not None:
            return _state_load_error_result(shape_error)
        completed_step = saved.get("completed_step", "")
        if completed_step in PRIVATE_ATTR_QUESTION_STEPS:
            return _private_attr_question_result_from_state(saved)
        log(f"Resuming from saved state (completed_step={completed_step})")
        result["resumed_from"] = completed_step
        if saved.get("bridge_rounds"):
            result["bridge_rounds"] = saved["bridge_rounds"]
        if saved.get("deferred_packet_path"):
            result["deferred_packet_path"] = saved["deferred_packet_path"]
        return str(completed_step)

    # Check for resumable state
    saved_state = _load_state(repo_root)
    if _is_state_load_error(saved_state):
        return _state_load_error_result(saved_state)
    resume_after: str = ""
    if saved_state and plan_path is not None:
        saved_plan = saved_state.get("plan_path")
        if _saved_state_matches_invocation(saved_plan, plan_path):
            activated_state = _activate_matching_saved_state(saved_state)
            if isinstance(activated_state, dict):
                return activated_state
            resume_after = activated_state
        else:
            return _state_plan_mismatch_result(saved_state, plan_path)

    branch_stash_error = _restore_pending_branch_switch_stash(repo_root)
    if branch_stash_error:
        return {
            "status": "error",
            "step": "restore_branch_switch_stash",
            "errors": [branch_stash_error],
        }

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
            routing_record = load_routing_record(repo_root, bus_dir=_active_bus_dir())
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
            # ALSO preserve task_id from _merge_task_id sentinel (CLI --task-id
            # path when there is no full override). merge_task_id is popped at
            # line 2371 before load_routing_record runs; if load raises, the
            # exception path lands here with routing_record_override=None but
            # merge_task_id still holds the user-supplied task_id. Without this
            # block the synthetic routing_record gets no task_id, and the
            # downstream default at _phase_b_task_id / handoff construction
            # falls back to the hardcoded "[EXECUTOR-SURFACES]" — which the
            # supervisor then rejects because that task is CLOSED in TASKS.md.
            # Observed 2026-04-17 on tier3-short-circuit-2026-04-17 wave.
            if merge_task_id:
                routing_record["task_id"] = merge_task_id
            result["bootstrap_exception"] = True
        else:
            return {"status": "error", "step": "load_routing_record",
                    "errors": [f"Routing record load failed: {exc}. Use --bootstrap-exception to override."]}

    # Plan loading: either from --plan path or derived from routing record
    if plan_path:
        try:
            plan = load_plan_packet(repo_root, plan_path)
        except PhaseBExecutorError as exc:
            return {
                "status": "error",
                "step": "load_plan",
                "plan_path": plan_path,
                "errors": [str(exc)],
            }
        result["plan_path"] = plan_path
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

    if saved_state and not resume_after:
        if not _saved_state_matches_invocation(saved_state.get("plan_path"), plan_path):
            return _state_plan_mismatch_result(saved_state, plan_path)
        activated_state = _activate_matching_saved_state(saved_state)
        if isinstance(activated_state, dict):
            return activated_state
        resume_after = activated_state

    plan_task_id = str(plan.get("task_id", "")).strip()
    if plan_task_id and not str(routing_record.get("task_id", "")).strip():
        routing_record["task_id"] = plan_task_id

    log(f"Phase-A-Lock: {plan.get('phase_a_lock', 'unknown')}")

    try:
        validate_inputs(routing_record, plan)
    except PhaseBExecutorError as exc:
        if force:
            log(f"BOOTSTRAP_PHASE_B_EXCEPTION: Validation errors overridden: {exc}")
            result["bootstrap_exception"] = True
        else:
            return {
                "status": "error",
                "step": "validate_inputs",
                "plan_path": plan_path,
                "errors": [str(exc)],
            }

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

    # Import load_relevant_learnings for subagent warming
    try:
        from recovery_gate import load_relevant_learnings
    except ImportError:
        _rg_path = SCRIPT_DIR / "recovery_gate.py"
        import importlib.util as _rg_ilu
        _rg_spec = _rg_ilu.spec_from_file_location("recovery_gate", str(_rg_path))
        _rg_mod = _rg_ilu.module_from_spec(_rg_spec)
        assert _rg_spec.loader is not None
        _rg_spec.loader.exec_module(_rg_mod)
        load_relevant_learnings = _rg_mod.load_relevant_learnings

    config = load_executor_config(repo_root)
    backend = config.get("backends", {}).get(
        "phase_b_executor",
        DEFAULT_EXECUTOR_CONFIG["backends"]["phase_b_executor"],
    )
    model = config.get("model_overrides", {}).get("phase_b_executor")
    timeout = config.get("timeouts", {}).get("phase_b_executor", 1200)
    pytest_gate_timeout = _resolve_pytest_gate_timeout(timeout)
    candidate_authority_required = _candidate_authority_required_from_routing_record(
        routing_record
    )
    candidate_authority_metadata = _candidate_authority_metadata_from_routing_record(
        routing_record
    )
    candidate_authority_package_kwargs: dict[str, Any] = {
        "candidate_authority_required": candidate_authority_required,
    }
    if candidate_authority_metadata is not None:
        candidate_authority_package_kwargs["candidate_authority_metadata"] = (
            candidate_authority_metadata
        )

    plan_content = plan.get("content", "")

    # The locked packet is the package-truth authority when it declares class.
    wave_class, target_gate_id = _refresh_phase_b_package_governance(
        repo_root,
        plan,
        plan_path,
        routing_record,
    )

    # Parse plan-declared files from markdown/body content.
    fenced_out_files = set(_parse_fenced_out_files(plan_content))
    exact_stage_scope_files = _expand_exact_stage_scope_files_for_git(
        repo_root,
        set(_parse_exact_stage_scope_files(plan_content)),
    )
    plan_declared_files: list[str] | None = None
    if exact_stage_scope_files:
        _parsed = sorted(path for path in exact_stage_scope_files if path not in fenced_out_files)
    else:
        _parsed = [
            path for path in _parse_plan_declared_files(plan_content)
            if path not in fenced_out_files
        ]
    # Only activate strict tracking when the plan actually declares files.
    # An empty parse means "plan has no file list" → use prefix fallback.
    if _parsed:
        plan_declared_files = _parsed
    if exact_stage_scope_files:
        log(f"Exact staged scope declares {len(exact_stage_scope_files)} file(s)")
    if fenced_out_files:
        log(
            f"Checkout-state fence excludes {len(fenced_out_files)} file(s) "
            "from this wave-owned scope"
        )

    # Compute learning context once for all implementer invocations
    learning_context = load_relevant_learnings(
        "implementer", plan_declared_files or [], repo_root,
    )
    if learning_context:
        log(f"Learning context loaded ({len(learning_context)} chars)")

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
    changed_files: list[str] = []

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
    baseline_wave_files = _restrict_baseline_to_exact_scope(
        baseline_wave_files,
        exact_stage_scope_files or None,
    )
    if exact_stage_scope_files:
        implementer_changed &= exact_stage_scope_files
        executor_created &= exact_stage_scope_files

    def _build_bridge_fix_prompt(round_num: int, bridge_decision: str, findings_for_impl: str) -> str:
        """Build the implementer prompt for a bridge-fix round."""
        return build_implementation_prompt(
            plan.get("content", "")
            + f"\n\n## Bridge Round {round_num} Findings ({bridge_decision})\n\n"
            + findings_for_impl,
            repo_root=repo_root,
            wave_id=wave_id,
            scope_hint=f"Fix {bridge_decision} findings from bridge round {round_num}",
            learning_context=learning_context,
        )

    def _build_reentry_fix_prompt(bridge_decision: str, findings_for_impl: str) -> str:
        """Build a re-entry prompt with authoritative non-GO decision context."""
        decision_suffix = (
            f" ({bridge_decision})"
            if bridge_decision in ("REQUEST_CHANGES", "NO_GO")
            else ""
        )
        return build_implementation_prompt(
            plan.get("content", "")
            + f"\n\n## Re-entry Findings{decision_suffix}\n\n"
            + findings_for_impl,
            repo_root=repo_root,
            wave_id=wave_id,
            scope_hint="Fix findings from bridge/supervisor review",
            learning_context=learning_context,
        )

    def _complete_bridge_fix(
        round_num: int,
        fix_result: dict[str, Any],
        pre_fix_files: set[str],
        *,
        bridge_decision: str = "",
    ) -> dict[str, Any] | None:
        """Finalize a bridge-fix implementer run and persist the completed round."""
        nonlocal implementer_changed, changed_files

        log(f"Implementer fix result: {fix_result['status']}")

        if fix_result["status"] != "success":
            return _implementer_failure_result(
                step="implementer_bridge_fix",
                message=(
                    f"Implementer failed during bridge fix round {round_num}: "
                    f"{fix_result['status']} (exit={fix_result['exit_code']})"
                ),
                impl_result=fix_result,
            )

        # Track what the fix round changed. The local pytest pass should only
        # exercise tests introduced or edited by this fix round, not every
        # pre-existing test file already present in the broader replay scope.
        post_fix_files = set(_collect_changed_files(repo_root))
        current_fix_changed = sorted(post_fix_files - pre_fix_files)
        implementer_changed |= set(current_fix_changed)
        if exact_stage_scope_files:
            current_fix_changed = sorted(set(current_fix_changed) & exact_stage_scope_files)
            implementer_changed &= exact_stage_scope_files
        reconciled_implementer_changed = _reconcile_bridge_fix_scope(
            repo_root,
            implementer_changed,
            set(current_fix_changed),
        )
        if reconciled_implementer_changed != implementer_changed:
            log(
                "Bridge fix reconciled implementer scope from "
                f"{len(implementer_changed)} to {len(reconciled_implementer_changed)} file(s)"
            )
            implementer_changed = reconciled_implementer_changed
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

        test_files = _select_pytest_gate_files(current_fix_changed, repo_root)
        if test_files:
            log(f"Running pytest on {len(test_files)} newly changed test file(s)...")
            pytest_result = _run_pytest_on_files(repo_root, test_files, timeout=pytest_gate_timeout)
            if not pytest_result["passed"]:
                log(f"pytest FAILED (exit={pytest_result['exit_code']}) — feeding back to implementer as blocking")
                pytest_prompt = build_implementation_prompt(
                    plan.get("content", "")
                    + f"\n\n## pytest FAILURE after bridge round {round_num}\n\n"
                    + f"Exit code: {pytest_result['exit_code']}\n"
                    + f"stdout:\n{pytest_result['stdout'][:3000]}\n"
                    + f"stderr:\n{pytest_result['stderr'][:1000]}",
                    repo_root=repo_root,
                    wave_id=wave_id,
                    scope_hint=f"Fix pytest failures from bridge round {round_num}",
                    learning_context=learning_context,
                )
                pre_pytest_fix_files = set(_collect_changed_files(repo_root))
                pytest_fix_transition = f"round-{round_num}:pytest_fix"
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_implementer_started",
                        state="pytest_fix_started",
                        transition_key=_phase_b_transition_key(
                            pytest_fix_transition,
                            "pytest_fix_started",
                        ),
                        summary=(
                            "Phase B implementer started pytest fix after "
                            f"bridge round {round_num}"
                        ),
                        artifact_paths={"plan": plan_path},
                    )
                except Exception as exc:
                    return {
                        "status": "error",
                        "step": "phase_b_pager",
                        "errors": [
                            "Phase B pager emission failed before pytest-fix "
                            f"implementer: {exc}"
                        ],
                    }
                pytest_fix = invoke_implementer(
                    repo_root, pytest_prompt,
                    backend=backend, model_override=model,
                    timeout=timeout, verbose=verbose,
                    bus_dir=_active_bus_dir(),
                )
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_implementer_completed",
                        state=f"pytest_fix_{pytest_fix.get('status', 'completed')}",
                        transition_key=_phase_b_transition_key(
                            pytest_fix_transition,
                            "pytest_fix_completed",
                        ),
                        summary=(
                            "Phase B implementer completed pytest fix after "
                            f"bridge round {round_num} with "
                            f"{pytest_fix.get('status', 'unknown')}"
                        ),
                        artifact_paths={"plan": plan_path},
                    )
                except Exception as exc:
                    return {
                        "status": "error",
                        "step": "phase_b_pager",
                        "errors": [
                            "Phase B pager emission failed after pytest-fix "
                            f"implementer: {exc}"
                        ],
                    }
                if pytest_fix["status"] != "success":
                    return _implementer_failure_result(
                        step="pytest_fix",
                        message=(
                            "Implementer failed fixing pytest failures: "
                            f"{pytest_fix['status']}"
                        ),
                        impl_result=pytest_fix,
                    )
                post_pytest_fix_files = set(_collect_changed_files(repo_root))
                implementer_changed |= (post_pytest_fix_files - pre_pytest_fix_files)
                if exact_stage_scope_files:
                    implementer_changed &= exact_stage_scope_files
                changed_files = _collect_wave_owned_files(
                    repo_root,
                    plan_path,
                    plan_declared_files,
                    implementer_changed or None,
                    executor_created or None,
                    baseline_wave_files or None,
                )

        _save_state(repo_root, {
            "plan_path": plan_path,
            "completed_step": f"bridge_round_{round_num}",
            "wave_id": wave_id,
            "bridge_rounds": round_num,
            "current_bridge_round": round_num,
            "last_bridge_decision": bridge_decision,
            "bridge_scope_fingerprint": _bridge_scope_fingerprint(repo_root, changed_files),
            "deferred_packet_path": deferred_packet_path,
            "implementer_changed": sorted(implementer_changed),
            "executor_created": sorted(executor_created),
            "baseline_wave_files": sorted(baseline_wave_files),
            "all_non_blocking": all_non_blocking,
            "finding_history": finding_history,
        })
        return None

    def _apply_bridge_fix(round_num: int, bridge_decision: str, findings_for_impl: str) -> dict[str, Any] | None:
        """Run the post-bridge implementer fix and persist the completed round."""
        pre_fix_files = set(_collect_changed_files(repo_root))
        fix_prompt = _build_bridge_fix_prompt(round_num, bridge_decision, findings_for_impl)
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="phase_b_implementer_started",
                state="bridge_fix_started",
                transition_key=_phase_b_transition_key(f"round-{round_num}", "bridge_fix_started"),
                summary=f"Phase B implementer started bridge fix for round {round_num}",
                artifact_paths={"plan": plan_path},
            )
        except Exception as exc:
            return {
                "status": "error",
                "step": "phase_b_pager",
                "errors": [f"Phase B pager emission failed before bridge-fix implementer: {exc}"],
            }
        fix_result = invoke_implementer(
            repo_root, fix_prompt,
            backend=backend, model_override=model,
            timeout=timeout, verbose=verbose,
            bus_dir=_active_bus_dir(),
        )
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="phase_b_implementer_completed",
                state=f"bridge_fix_{fix_result.get('status', 'completed')}",
                transition_key=_phase_b_transition_key(f"round-{round_num}", "bridge_fix_completed"),
                summary=(
                    "Phase B implementer completed bridge fix round "
                    f"{round_num} with {fix_result.get('status', 'unknown')}"
                ),
                artifact_paths={"plan": plan_path},
            )
        except Exception as exc:
            return {
                "status": "error",
                "step": "phase_b_pager",
                "errors": [f"Phase B pager emission failed after bridge-fix implementer: {exc}"],
            }
        return _complete_bridge_fix(
            round_num,
            fix_result,
            pre_fix_files,
            bridge_decision=bridge_decision,
        )

    def _complete_reentry_fix(
        impl_result: dict[str, Any],
        pre_reentry_files: set[str],
        reentry_findings: str,
        pending_bridge_round: int,
    ) -> dict[str, Any] | None:
        """Record a re-entry implementer pass before the next bridge review."""
        nonlocal implementer_changed, changed_files

        log(f"Implementer re-entry: {impl_result['status']}")
        if impl_result["status"] != "success":
            _clear_state(repo_root)
            return _implementer_failure_result(
                step="implementer_reentry",
                message=f"Implementer re-entry failed: {impl_result['status']}",
                impl_result=impl_result,
            )

        post_reentry_files = set(_collect_changed_files(repo_root))
        implementer_changed |= (post_reentry_files - pre_reentry_files)
        if exact_stage_scope_files:
            implementer_changed &= exact_stage_scope_files
        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
        changed_files = _bridge_review_scope_files(changed_files)
        log(
            f"Re-entry changed files: {len(changed_files)} "
            f"(implementer touched {len(post_reentry_files - pre_reentry_files)})"
        )
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
            "reentry_findings": reentry_findings,
            "runtime_pre_push_failure_reentry": reentry_runtime_pre_push_failure,
            "skip_reentry_implementer_once": True,
            "pending_reentry_bridge_round": pending_bridge_round,
        })
        log("Re-entry: checkpointed implemented fixes before bridge review")
        return None

    def _bridge_review_scope_files(candidate_files: list[str]) -> list[str]:
        """Include the governing packet in bridge-reviewed/staged scope."""
        scoped = list(candidate_files)
        if plan_path and not plan_path.startswith("<") and plan_path not in scoped:
            scoped.append(plan_path)
        if exact_stage_scope_files:
            scoped = [path for path in scoped if path in exact_stage_scope_files]
        return scoped

    def _private_attr_pending_review_step(*, reentry: bool) -> str:
        return (
            "reentry_private_attr_remediation_pending_review"
            if reentry
            else "private_attr_remediation_pending_review"
        )

    def _private_attr_question_step(*, reentry: bool) -> str:
        return (
            "reentry_private_attr_remediation_question_for_founder"
            if reentry
            else "private_attr_remediation_question_for_founder"
        )

    def _save_private_attr_pending_review_state(
        candidate_files: list[str],
        *,
        reentry: bool,
    ) -> list[str]:
        """Checkpoint private-attr remediation before the required fresh review."""
        scoped_files = _bridge_review_scope_files(candidate_files)
        _save_state(repo_root, {
            "plan_path": plan_path,
            "completed_step": _private_attr_pending_review_step(reentry=reentry),
            "wave_id": wave_id,
            "bridge_rounds": result["bridge_rounds"],
            "bridge_scope_fingerprint": _bridge_scope_fingerprint(repo_root, scoped_files),
            "deferred_packet_path": deferred_packet_path,
            "implementer_changed": sorted(implementer_changed),
            "executor_created": sorted(executor_created),
            "baseline_wave_files": sorted(baseline_wave_files),
            "all_non_blocking": all_non_blocking,
            "finding_history": finding_history,
            "private_attr_gate_test_files": result.get("private_attr_gate_test_files", []),
        })
        return scoped_files

    def _run_private_attr_gate_with_remediation(
        candidate_files: list[str],
        *,
        reentry: bool = False,
    ) -> tuple[list[str], dict[str, Any] | None, bool]:
        """Run anti-cheat and feed failures through the implementer loop."""
        nonlocal implementer_changed, changed_files

        current_files = list(candidate_files)
        max_gate_rounds = max(1, max_bridge_rounds)
        step_name = "reentry_private_attr_gate" if reentry else "private_attr_gate"
        remediated = False
        for gate_round in range(1, max_gate_rounds + 1):
            gate_result = run_private_attr_gate(
                repo_root,
                current_files,
                timeout=pytest_gate_timeout,
            )
            if gate_result.get("skipped"):
                return current_files, None, remediated
            result["private_attr_gate_test_files"] = gate_result.get("test_files", [])
            if gate_result.get("passed"):
                log(
                    ("Re-entry " if reentry else "")
                    + "private-attr gate: PASSED for "
                    f"{len(gate_result.get('test_files') or [])} test file(s)"
                )
                return current_files, None, remediated

            failure_summary = private_attr_gate_summary(gate_result, reentry=reentry)
            if gate_round >= max_gate_rounds:
                return current_files, {
                    "status": "error",
                    "step": step_name,
                    "errors": [failure_summary],
                    "private_attr_gate": gate_result,
                }, remediated

            log(
                ("Re-entry " if reentry else "")
                + "private-attr gate failed; re-invoking implementer "
                f"(round {gate_round}/{max_gate_rounds})"
            )
            pre_gate_fix_files = set(_collect_changed_files(repo_root))
            fix_prompt = build_implementation_prompt(
                plan_content
                + "\n\n## Private Attribute Test Integrity Gate Failure\n\n"
                + failure_summary
                + "\n\nDo not weaken `tools/checks/linters/check_private_attr_access.py`, "
                "do not add allowlist entries, do not add `ANTICHEAT_OK`, and do not "
                "bypass `tools/hooks/pre-push-fast`. Fix the tests through a public seam "
                "or existing public commit-packet refresh path.",
                repo_root=repo_root,
                wave_id=wave_id,
                scope_hint="Fix private-attribute access in wave-owned Python tests",
                learning_context=learning_context,
            )
            fix_result = invoke_implementer(
                repo_root,
                fix_prompt,
                backend=backend,
                model_override=model,
                timeout=timeout,
                verbose=verbose,
                bus_dir=_active_bus_dir(),
            )
            if fix_result["status"] != "success":
                return current_files, _implementer_failure_result(
                    step=step_name,
                    message=(
                        "Implementer failed while fixing private-attr test-integrity "
                        f"gate: {fix_result['status']} (exit={fix_result['exit_code']})"
                    ),
                    impl_result=fix_result,
                ), remediated

            post_gate_fix_files = set(_collect_changed_files(repo_root))
            implementer_changed |= (post_gate_fix_files - pre_gate_fix_files) - fenced_out_files
            if exact_stage_scope_files:
                implementer_changed &= exact_stage_scope_files
            current_files = _collect_wave_owned_files(
                repo_root,
                plan_path,
                plan_declared_files,
                implementer_changed or None,
                executor_created or None,
                baseline_wave_files or None,
            )
            current_files = _save_private_attr_pending_review_state(
                current_files,
                reentry=reentry,
            )
            changed_files = current_files
            remediated = True

        return current_files, {
            "status": "error",
            "step": step_name,
            "errors": ["private-attr gate did not converge before commit handoff"],
        }, remediated

    def _run_private_attr_remediation_bridge_review(
        candidate_files: list[str],
        *,
        reentry: bool = False,
    ) -> tuple[list[str], dict[str, Any] | None]:
        """Freshly review implementer changes made by the private-attr gate."""
        nonlocal all_non_blocking, deferred_packet_path, changed_files

        current_files = _bridge_review_scope_files(candidate_files)
        next_round = int(result.get("bridge_rounds") or 0) + 1
        private_attr_review_budget = max(1, max_bridge_rounds)
        private_attr_review_limit = max_bridge_rounds + private_attr_review_budget
        step_name = (
            "reentry_private_attr_bridge_review"
            if reentry
            else "private_attr_bridge_review"
        )
        if next_round > private_attr_review_limit:
            return current_files, {
                "status": "error",
                "step": step_name,
                "errors": [
                    "Private-attr remediation changed files after the bridge review "
                    "budget was exhausted and did not converge within the additional "
                    f"{private_attr_review_budget} private-attr review round(s); cannot "
                    "proceed to commit without fresh review."
                ],
            }
        log(
            ("Re-entry " if reentry else "")
            + "private-attr remediation: preparing "
            f"{len(current_files)} wave-owned files before fresh bridge review..."
        )
        current_files, preparation_error = _prepare_phase_b_pre_review_package(
            repo_root,
            candidate_files=current_files,
            exact_stage_scope_files=exact_stage_scope_files,
            plan_path=plan_path,
            wave_id=wave_id,
            wave_class=wave_class,
            step_prefix=step_name,
            context="private-attr remediation bridge review",
            **candidate_authority_package_kwargs,
        )
        if preparation_error is not None:
            return current_files, preparation_error
        indicator_path = _phase_b_same_wave_indicator_path(wave_id)
        if indicator_path in current_files:
            executor_created.add(indicator_path)
        changed_files = current_files

        bridge_job_id = (
            f"phase-b-reentry-private-attr-r{next_round}-{uuid.uuid4().hex[:8]}"
            if reentry
            else f"phase-b-private-attr-r{next_round}-{uuid.uuid4().hex[:8]}"
        )
        transition_key = _phase_b_review_transition_key(next_round, bridge_job_id)
        log(
            ("Re-entry " if reentry else "")
            + "private-attr remediation: fresh bridge review "
            f"{next_round}/{private_attr_review_limit} "
            f"(bridge budget={max_bridge_rounds}, "
            f"private-attr extra={private_attr_review_budget}, job={bridge_job_id})..."
        )
        try:
            bridge_result = run_bridge_review(
                repo_root,
                (
                    ("Phase B re-entry" if reentry else "Phase B")
                    + f" private-attr remediation review R{next_round} for {plan_path}"
                ),
                job_id=bridge_job_id,
                reader_agent=backend,
                verbose=verbose,
                timeout=timeout,
                on_started=lambda: _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_reviewer_started",
                    state="reviewer_started",
                    transition_key=transition_key,
                    summary=(
                        "Phase B reviewer started after private-attr "
                        f"remediation for round {next_round}"
                    ),
                    artifact_paths={
                        "agent_review_report": str(result.get("agent_review_report_path") or ""),
                        "agent_review_status": str(result.get("agent_review_status_path") or ""),
                    },
                ),
            )
        except Exception as exc:
            return current_files, {
                "status": "error",
                "step": "phase_b_pager",
                "errors": [
                    "Phase B pager emission failed after private-attr "
                    f"remediation reviewer launch: {exc}"
                ],
            }

        result["bridge_rounds"] = next_round
        result["bridge_job_id"] = bridge_job_id
        result["bridge_stdout_path"] = bridge_result.get("stdout_path")
        result["bridge_stderr_path"] = bridge_result.get("stderr_path")
        bridge_decision = bridge_result.get("decision", "")
        log(
            ("Re-entry " if reentry else "")
            + f"private-attr remediation bridge decision: {bridge_decision!r} "
            f"(exit={bridge_result['exit_code']})"
        )

        if bridge_result["exit_code"] in (-1, -2, -3):
            failure_label = {
                -1: "timed out",
                -2: "stale",
                -3: "aggregation hang",
            }[bridge_result["exit_code"]]
            return current_files, {
                "status": "error",
                "step": step_name,
                "errors": [
                    f"Bridge review {failure_label} after private-attr remediation. "
                    f"{bridge_result.get('stderr', '')}"
                ],
            }

        if (
            bridge_result["exit_code"] == 0
            and _is_go_bridge_decision(bridge_decision)
        ):
            render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
            parsed_findings = _parse_findings_from_render(render, raw_texts) if (render or raw_texts) else []
            blocking_findings, non_blocking_findings = _classify_findings(parsed_findings, finding_history)
            if blocking_findings:
                return current_files, {
                    "status": "error",
                    "step": step_name,
                    "errors": [
                        "Bridge returned GO after private-attr remediation but rendered "
                        f"transcript still contains {len(blocking_findings)} blocking finding(s). "
                        "Fail closed."
                    ],
                }
            if render or raw_texts:
                prior_deferred_packet_path = deferred_packet_path
                all_non_blocking, deferred_packet_path = _sync_deferred_non_blocking_state(
                    repo_root,
                    wave_id,
                    all_non_blocking,
                    non_blocking_findings,
                    previous_packet_path=prior_deferred_packet_path,
                    executor_created=executor_created,
                    wave_class=wave_class,
                    target_gate_id=target_gate_id,
                )
                if deferred_packet_path is not None:
                    result["deferred_packet_path"] = deferred_packet_path
                else:
                    result.pop("deferred_packet_path", None)
            try:
                _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_bridge_completed",
                    state="reentry_private_attr_bridge_go" if reentry else "private_attr_bridge_go",
                    transition_key=_phase_b_transition_key(bridge_job_id, "private_attr_bridge_go"),
                    summary=(
                        "Phase B bridge GO after private-attr remediation "
                        f"for round {next_round}"
                    ),
                    artifact_paths={
                        "bridge_stdout": str(bridge_result.get("stdout_path") or ""),
                        "bridge_stderr": str(bridge_result.get("stderr_path") or ""),
                        "deferred_packet": str(deferred_packet_path or ""),
                    },
                )
            except Exception as exc:
                return current_files, {
                    "status": "error",
                    "step": "phase_b_pager",
                    "errors": [
                        "Phase B pager emission failed after private-attr "
                        f"remediation bridge GO: {exc}"
                    ],
                }
            changed_files = current_files
            return current_files, None

        if bridge_decision == "QUESTION":
            question_result: dict[str, Any] = {
                "status": "question_for_founder",
                "step": step_name,
                "bridge_rounds": next_round,
                "bridge_job_id": bridge_job_id,
                "bridge_stdout_path": bridge_result.get("stdout_path"),
                "bridge_stderr_path": bridge_result.get("stderr_path"),
                "errors": [
                    "Bridge returned QUESTION after private-attr remediation. "
                    "Founder input required."
                ],
            }
            render = _read_bridge_render(repo_root, bridge_job_id)
            if render:
                question_result["bridge_render"] = render[:2000]
            _save_state(repo_root, {
                "plan_path": plan_path,
                "completed_step": _private_attr_question_step(reentry=reentry),
                "wave_id": wave_id,
                "bridge_rounds": next_round,
                "bridge_job_id": bridge_job_id,
                "bridge_decision": bridge_decision,
                "bridge_stdout_path": bridge_result.get("stdout_path"),
                "bridge_stderr_path": bridge_result.get("stderr_path"),
                "bridge_render": question_result.get("bridge_render", ""),
                "question_step": step_name,
                "errors": list(question_result["errors"]),
                "terminal_result": question_result,
                "deferred_packet_path": deferred_packet_path,
                "implementer_changed": sorted(implementer_changed),
                "executor_created": sorted(executor_created),
                "baseline_wave_files": sorted(baseline_wave_files),
                "all_non_blocking": all_non_blocking,
                "finding_history": finding_history,
                "private_attr_gate_test_files": result.get("private_attr_gate_test_files", []),
            })
            return current_files, question_result

        if bridge_result["exit_code"] == 0 and bridge_decision not in RECOGNIZED_BRIDGE_DECISIONS:
            return current_files, {
                "status": "error",
                "step": step_name,
                "errors": [
                    "Bridge returned unrecognized success decision after private-attr "
                    f"remediation: {bridge_decision!r}. Fail closed."
                ],
            }

        if bridge_decision in ("REQUEST_CHANGES", "NO_GO"):
            if bridge_result["exit_code"] not in (0, 1):
                return current_files, {
                    "status": "error",
                    "step": f"{step_name}_subprocess",
                    "errors": [
                        "Bridge subprocess failed after private-attr remediation "
                        f"(exit={bridge_result['exit_code']}, decision={bridge_decision}). "
                        "Unexpected exit with a recoverable review decision is not recoverable. "
                        f"stderr: {bridge_result.get('stderr', '')[:500]}"
                    ],
                }

            render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
            parsed_findings = _parse_findings_from_render(render, raw_texts) if (render or raw_texts) else []
            blocking_findings, non_blocking_findings = _classify_findings(parsed_findings, finding_history)

            if blocking_findings and finding_history:
                unresolvable = [
                    _finding_key(f) for f in blocking_findings
                    if finding_history.get(_finding_key(f), 0) >= REPEAT_FINDING_CAP
                ]
                if unresolvable:
                    return current_files, {
                        "status": "error",
                        "step": step_name,
                        "errors": [
                            "Blocking finding(s) after private-attr remediation were "
                            f"unresolvable after {REPEAT_FINDING_CAP} rounds: "
                            + ", ".join(unresolvable[:5])
                        ],
                        "unresolvable_findings": blocking_findings,
                    }

            # A non-GO decision requires correction even when every parsed
            # finding is explicitly nonblocking. Preserve the review context;
            # none of this round's findings have been deferred.
            findings_for_impl = _bridge_correction_context(
                parsed_findings,
                render,
                raw_texts,
                bridge_result.get("stdout", ""),
            )

            _checkpoint_bridge_fix_pending(
                repo_root,
                plan_path=plan_path,
                wave_id=wave_id,
                round_num=next_round,
                bridge_decision=bridge_decision,
                bridge_fix_findings=findings_for_impl,
                changed_files=current_files,
                deferred_packet_path=deferred_packet_path,
                implementer_changed=implementer_changed,
                executor_created=executor_created,
                baseline_wave_files=baseline_wave_files,
                all_non_blocking=all_non_blocking,
                finding_history=finding_history,
            )
            log(
                ("Re-entry " if reentry else "")
                + "private-attr remediation bridge returned "
                f"{bridge_decision} — {len(blocking_findings)} blocking, "
                f"{len(non_blocking_findings)} non-blocking — re-invoking implementer"
            )
            bridge_fix_error = _apply_bridge_fix(next_round, bridge_decision, findings_for_impl)
            if bridge_fix_error is not None:
                return current_files, bridge_fix_error

            current_files = _collect_wave_owned_files(
                repo_root,
                plan_path,
                plan_declared_files,
                implementer_changed or None,
                executor_created or None,
                baseline_wave_files or None,
            )
            current_files = _bridge_review_scope_files(current_files)
            changed_files = current_files
            current_files, gate_error, _gate_remediated = _run_private_attr_gate_with_remediation(
                current_files,
                reentry=reentry,
            )
            if gate_error is not None:
                return current_files, gate_error
            changed_files = current_files
            return _run_private_attr_remediation_bridge_review(
                current_files,
                reentry=reentry,
            )

        return current_files, {
            "status": "error",
            "step": step_name,
            "errors": [
                "Bridge did not approve the post-private-attr-remediation diff "
                f"(decision={bridge_decision!r}, exit={bridge_result['exit_code']})."
            ],
        }

    # Determine which steps to skip based on resume state
    _RESUME_ORDER = [
        "implementer",
        "agent_review",
        "bridge_fix_pending",
        "bridge_converged",
        "private_attr_remediation_pending_review",
        "needs_phase_b_reentry",
        "reentry_private_attr_remediation_pending_review",
    ]
    _resume_private_attr_review = resume_after == "private_attr_remediation_pending_review"
    _resume_reentry_private_attr_review = (
        resume_after == "reentry_private_attr_remediation_pending_review"
    )
    _skip_to_reentry = resume_after == "needs_phase_b_reentry" or _resume_reentry_private_attr_review
    reentry_runtime_pre_push_failure = bool(
        (saved_state or {}).get("runtime_pre_push_failure_reentry")
    ) or _reentry_findings_indicate_runtime_pre_push_failure(
        (saved_state or {}).get("reentry_findings") if saved_state else ""
    )
    _resume_bridge_fix_pending = resume_after == "bridge_fix_pending"
    _skip_through_bridge = (
        resume_after.startswith("bridge_round_")
        or resume_after in {
            "bridge_fix_pending",
            "bridge_converged",
            "private_attr_remediation_pending_review",
            "reentry_private_attr_remediation_pending_review",
        }
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
            branch_error = _checkout_feature_branch_from_protected_branch(
                repo_root,
                current_branch=current_branch,
                feature_branch=feature_branch,
                branch_exists=branch_exists,
                log=log,
            )
            if branch_error:
                return {"status": "error", "step": "ensure_feature_branch",
                        "errors": [f"{branch_error}. "
                                   f"Cannot invoke implementer on protected branch '{current_branch}'."]}
            result["feature_branch"] = feature_branch
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
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="phase_b_implementer_started",
                state="implementer_started",
                transition_key=_phase_b_transition_key(wave_id, "implementer_started"),
                summary="Phase B implementer started",
                artifact_paths={"plan": plan_path},
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [f"Phase B pager emission failed before implementer: {exc}"]
            return result
        impl_prompt = build_implementation_prompt(
            plan.get("content", ""),
            repo_root=repo_root,
            wave_id=wave_id,
            learning_context=learning_context,
        )
        impl_result = invoke_implementer(
            repo_root, impl_prompt,
            backend=backend,
            model_override=model,
            timeout=timeout,
            verbose=verbose,
            bus_dir=_active_bus_dir(),
        )
        result["implementer_invoked"] = True
        result["implementer_status"] = impl_result["status"]
        result["model_override_applied"] = impl_result.get("model_override_applied", False)
        log(f"Implementer: {impl_result['status']} (exit={impl_result['exit_code']})")
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="phase_b_implementer_completed",
                state=str(impl_result.get("status") or "implementer_completed"),
                transition_key=_phase_b_transition_key(wave_id, "implementer_completed"),
                summary=f"Phase B implementer completed with {impl_result.get('status', 'unknown')}",
                artifact_paths={"plan": plan_path},
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [f"Phase B pager emission failed after implementer: {exc}"]
            return result

        # FAIL CLOSED: any implementer failure is fatal, not just timeout
        if impl_result["status"] != "success":
            result.update(_implementer_failure_result(
                step="implementer",
                message=(
                    f"Implementer failed: {impl_result['status']} "
                    f"(exit={impl_result['exit_code']}): {impl_result.get('stderr', '')[:500]}"
                ),
                impl_result=impl_result,
            ))
            result["implementer_invoked"] = True
            result["implementer_status"] = impl_result["status"]
            return result

        # Collect changed files after implementer ran — track what implementer actually changed
        post_impl_files = set(_collect_changed_files(repo_root))
        implementer_changed = (post_impl_files - pre_impl_files) - fenced_out_files
        if exact_stage_scope_files:
            implementer_changed &= exact_stage_scope_files
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
                result["agent_review_stderr_path"] = saved_state.get("agent_review_stderr_path")
                log("Step 4: SKIPPED (resume_after=agent_review, scope fingerprint matched)")
                log(f"Agent review exit code: {result['agent_exit_code']} (resumed)")
            else:
                if resume_after == "agent_review":
                    log(
                        "Saved agent review checkpoint drifted or was incomplete; "
                        "re-running SDK agent review"
                    )
                _receipt_path, authority_error = prepare_candidate_authority_if_configured(
                    repo_root,
                    wave_id=wave_id,
                    phase="phase_b",
                    review_round="sdk_agent_review",
                    context="SDK agent review",
                    required=candidate_authority_required,
                    trusted_metadata=candidate_authority_metadata,
                )
                if authority_error is not None:
                    _clear_state(repo_root)
                    return {
                        "status": "error",
                        "step": "sdk_candidate_authority",
                        "errors": [authority_error],
                    }
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
                result["agent_review_stderr_path"] = agent_result.get("stderr_path")
                log(f"Agent review exit code: {agent_result['exit_code']}")

                if agent_result["exit_code"] < 0 or agent_result["exit_code"] == 4:
                    # Negative exits (-1 timeout, -2 stale, -3 aggregation-hang)
                    # and exit=4 (INFRA_FAILURE_EXIT_CODE in run_review.py:351)
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
                    "agent_review_stderr_path": agent_result.get("stderr_path"),
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
    # Classify findings by disposition; only GO may defer non-blockers, while
    # non-GO rounds retain the complete review context for bounded correction.
    bridge_converged = _skip_through_bridge and resume_after in (
        "bridge_converged",
        "needs_phase_b_reentry",
        "private_attr_remediation_pending_review",
        "reentry_private_attr_remediation_pending_review",
    )
    deferred_packet_path: str | None = result.get("deferred_packet_path")

    # Resume from saved bridge round instead of restarting from 1
    _resume_bridge_round = 0
    if _skip_through_bridge and resume_after.startswith("bridge_round_"):
        _resume_bridge_round = saved_state.get("current_bridge_round", 0) if saved_state else 0
        log(f"Resuming bridge loop from round {_resume_bridge_round + 1}")
    if _resume_bridge_fix_pending:
        pending_round = saved_state.get("current_bridge_round", 0) if saved_state else 0
        pending_decision = str(saved_state.get("bridge_decision", "") or "") if saved_state else ""
        pending_findings = str(saved_state.get("bridge_fix_findings", "") or "") if saved_state else ""
        if pending_round <= 0 or not pending_findings:
            result["status"] = "error"
            result["step"] = "bridge_fix_resume"
            result["errors"] = [
                "Saved bridge-fix checkpoint was incomplete; missing round number or findings payload."
            ]
            _clear_state(repo_root)
            return result
        log(f"Resuming pending bridge fix from round {pending_round} ({pending_decision or 'REQUEST_CHANGES'})")
        result["bridge_rounds"] = pending_round
        bridge_fix_error = _apply_bridge_fix(
            pending_round,
            pending_decision or "REQUEST_CHANGES",
            pending_findings,
        )
        if bridge_fix_error is not None:
            return bridge_fix_error
        _resume_bridge_round = pending_round

    bridge_decision = str(
        (saved_state or {}).get("last_bridge_decision")
        or (saved_state or {}).get("bridge_decision")
        or "unknown"
    )
    for round_num in range(1, max_bridge_rounds + 1):
        if bridge_converged:
            break  # Already converged (e.g. needs_phase_b_reentry resume) — skip initial loop
        if round_num <= _resume_bridge_round:
            continue  # Skip already-completed rounds on resume
        bridge_job_id = f"phase-b-r{round_num}-{uuid.uuid4().hex[:8]}"
        transition_key = _phase_b_review_transition_key(round_num, bridge_job_id)
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
        changed_files = _bridge_review_scope_files(changed_files)
        log(
            f"Preparing {len(changed_files)} wave-owned files before bridge review..."
        )
        changed_files, preparation_error = _prepare_phase_b_pre_review_package(
            repo_root,
            candidate_files=changed_files,
            exact_stage_scope_files=exact_stage_scope_files,
            plan_path=plan_path,
            wave_id=wave_id,
            wave_class=wave_class,
            step_prefix="bridge_pre_review",
            context=f"bridge review round {round_num}",
            **candidate_authority_package_kwargs,
        )
        if preparation_error is not None:
            _clear_state(repo_root)
            return preparation_error
        indicator_path = _phase_b_same_wave_indicator_path(wave_id)
        if indicator_path in changed_files:
            executor_created.add(indicator_path)

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

        try:
            bridge_result = run_bridge_review(
                repo_root,
                task_summary,
                job_id=bridge_job_id,
                reader_agent=backend,
                verbose=verbose,
                timeout=timeout,
                on_started=lambda: _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_reviewer_started",
                    state="reviewer_started",
                    transition_key=transition_key,
                    summary=f"Phase B reviewer started for round {round_num}",
                    artifact_paths={
                        "agent_review_report": str(result.get("agent_review_report_path") or ""),
                        "agent_review_status": str(result.get("agent_review_status_path") or ""),
                    },
                ),
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [f"Phase B pager emission failed after reviewer launch: {exc}"]
            _clear_state(repo_root)
            return result

        # Parse decision from bridge result
        result["bridge_job_id"] = bridge_job_id
        result["bridge_stdout_path"] = bridge_result.get("stdout_path")
        result["bridge_stderr_path"] = bridge_result.get("stderr_path")
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

        if (
            bridge_result["exit_code"] == 0
            and _is_go_bridge_decision(bridge_decision)
        ):
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
            if render or raw_texts:
                prior_deferred_packet_path = deferred_packet_path
                all_non_blocking, deferred_packet_path = _sync_deferred_non_blocking_state(
                    repo_root,
                    wave_id,
                    all_non_blocking,
                    non_blocking_findings,
                    previous_packet_path=prior_deferred_packet_path,
                    executor_created=executor_created,
                    wave_class=wave_class,
                    target_gate_id=target_gate_id,
                )
                if deferred_packet_path is not None:
                    result["deferred_packet_path"] = deferred_packet_path
                    log(f"Filed {len(non_blocking_findings)} non-blocking finding(s) from GO to {deferred_packet_path}")
                else:
                    result.pop("deferred_packet_path", None)
                    if prior_deferred_packet_path:
                        log("Cleared stale deferred non-blocking packet after GO")
            log("Bridge converged: GO")
            try:
                _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_bridge_completed",
                    state="bridge_go",
                    transition_key=_phase_b_transition_key(bridge_job_id, "bridge_go"),
                    summary=f"Phase B bridge GO for round {round_num}",
                    artifact_paths={
                        "bridge_stdout": str(bridge_result.get("stdout_path") or ""),
                        "bridge_stderr": str(bridge_result.get("stderr_path") or ""),
                        "deferred_packet": str(deferred_packet_path or ""),
                    },
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"] = [f"Phase B pager emission failed after bridge GO: {exc}"]
                _clear_state(repo_root)
                return result
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
            try:
                _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_final_verdict",
                    state="question_for_founder",
                    transition_key=_phase_b_transition_key(bridge_job_id, "question_for_founder"),
                    summary=result["errors"][0],
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"].append(f"Phase B pager emission failed on QUESTION verdict: {exc}")
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

            # Read findings from the exact bridge material for this job.
            render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
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

            # REQUEST_CHANGES/NO_GO is authoritative over disposition. Keep the
            # complete review context in the bounded correction path; none of
            # this round's findings are eligible for deferred state.
            findings_for_impl = _bridge_correction_context(
                parsed_findings,
                render,
                raw_texts,
                bridge_result.get("stdout", ""),
            )

            if round_num >= max_bridge_rounds:
                log(
                    f"Bridge: {bridge_decision} on final allowed round "
                    f"{round_num}/{max_bridge_rounds}; not re-invoking implementer"
                )
                break

            _checkpoint_bridge_fix_pending(
                repo_root,
                plan_path=plan_path,
                wave_id=wave_id,
                round_num=round_num,
                bridge_decision=bridge_decision,
                bridge_fix_findings=findings_for_impl,
                changed_files=changed_files,
                deferred_packet_path=deferred_packet_path,
                implementer_changed=implementer_changed,
                executor_created=executor_created,
                baseline_wave_files=baseline_wave_files,
                all_non_blocking=all_non_blocking,
                finding_history=finding_history,
            )
            log(f"Bridge: {bridge_decision} — {len(blocking_findings)} blocking, "
                f"{len(non_blocking_findings)} non-blocking — re-invoking implementer")
            bridge_fix_error = _apply_bridge_fix(round_num, bridge_decision, findings_for_impl)
            if bridge_fix_error is not None:
                return bridge_fix_error
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
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="phase_b_final_verdict",
                state="max_rounds_reached",
                transition_key=_phase_b_transition_key("phase-b", "max_rounds_reached"),
                summary=result["errors"][0],
            )
            _emit_phase_b_hard_fail(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                state="max_rounds_reached",
                changed_files=changed_files,
                summary=result["errors"][0],
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"].append(
                f"Phase B pager emission failed on max_rounds_reached: {exc}"
            )
            _clear_state(repo_root)
            return result
        # Clear state to prevent stale resume — next invocation must start fresh
        _clear_state(repo_root)
        return result

    blocking_deferred_findings = _blocking_findings_in_deferred_convergence(all_non_blocking)
    if blocking_deferred_findings:
        result["status"] = "error"
        result["step"] = "blocking_finding_convergence"
        result["errors"] = [
            "Bridge convergence state contains effective blocking finding(s) "
            "inside deferred/non-blocking findings; refusing to proceed to "
            "final pytest, supervisor, or commit handoff."
        ]
        result["blocking_findings"] = blocking_deferred_findings
        _clear_state(repo_root)
        return result

    _normalize_control_packet_line_refs(
        repo_root,
        plan_path=plan_path,
        changed_files=changed_files,
    )
    line_ref_error = _control_packet_line_ref_lint_error(
        repo_root,
        plan_path=plan_path,
        changed_files=changed_files,
    )
    if line_ref_error is not None:
        result["status"] = "error"
        result["step"] = "control_packet_line_ref_lint"
        result["errors"] = [line_ref_error]
        _clear_state(repo_root)
        return result

    # Persist state after bridge convergence unless a stricter private-attr
    # remediation checkpoint is already the active resume authority.
    if not (
        _resume_private_attr_review
        or _resume_reentry_private_attr_review
        or _skip_to_reentry
    ):
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
    skip_reentry_implementer_once = False
    pending_reentry_bridge_round = 0
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
        refresh_reentry_findings = bool(
            (saved_state or {}).get("refresh_reentry_findings")
        ) or saved_scope_fingerprint != current_scope_fingerprint
        if refresh_reentry_findings:
            findings_for_impl = "Refresh bridge findings from the current worktree before re-invoking the implementer."
            log("NEEDS_PHASE_B resume checkpoint drifted or lacked scope fingerprint; refreshing bridge findings first")
        else:
            findings_for_impl = (saved_state or {}).get("reentry_findings", "Fix required (resumed)")
            skip_reentry_implementer_once = bool(
                (saved_state or {}).get("skip_reentry_implementer_once")
            )
            try:
                pending_reentry_bridge_round = int(
                    (saved_state or {}).get("pending_reentry_bridge_round") or 0
                )
            except (TypeError, ValueError):
                pending_reentry_bridge_round = 0
        result["pre_commit_summary"] = findings_for_impl
        decision = "NEEDS_PHASE_B"
        # Provide stubs for variables used in re-entry block
        deferred_packet_path = result.get("deferred_packet_path")
        supervisor_result = {"parsed": {"summary": findings_for_impl}}
        supervisor_parsed = supervisor_result["parsed"]
        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        package_path = scratch_dir / "phase_b_supervisor_package.json"
        wave_class, target_gate_id = _refresh_phase_b_package_governance(
            repo_root,
            plan,
            plan_path,
            routing_record,
        )
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
        deferred_items = _collect_supervisor_deferred_items(
            changed_files,
            deferred_packet_path,
            repo_root=repo_root,
        )
        all_dirty_reentry = _collect_changed_files(repo_root)
        fenced_reentry = [f for f in all_dirty_reentry if f not in set(changed_files)]

        supervisor_package = {
            "task_id": routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            "wave_name": wave_id,
            "wave_class": wave_class,
            "lane": "hooks/agents/bridge control-surface",
            "changed_files": changed_files,
            "fenced_files": fenced_reentry,
            "scope_items": [plan_path],
            "fixes_implemented": ["Phase B implementation per locked plan (resumed from NEEDS_PHASE_B)"],
            "deferred_items": deferred_items,
            "bridge_status": _build_effective_bridge_status(
                repo_root,
                wave_id,
                plan_path,
                result.get("bridge_rounds", 0),
                reentry=True,
            ),
            "evidence_handles": _collect_supervisor_evidence_handles(repo_root, wave_id),
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
            # Stubs for the early skip-to-reentry NEEDS_PHASE_B package: pre_supervisor_tracker_note
            # is finalized only on the normal Step-7 path (line ~7759), which this path skips, so it
            # is not yet bound here. The re-entry refresh later sets the real tracker_note_text +
            # evidence_command from reentry_pre_supervisor_tracker_note before the supervisor runs.
            "tracker_note_text": "",
            "evidence_command": "",
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
        _normalize_control_packet_line_refs(
            repo_root,
            plan_path=plan_path,
            changed_files=changed_files,
        )
        line_ref_error = _control_packet_line_ref_lint_error(
            repo_root,
            plan_path=plan_path,
            changed_files=changed_files,
        )
        if line_ref_error is not None:
            result["status"] = "error"
            result["step"] = "control_packet_line_ref_lint"
            result["errors"] = [line_ref_error]
            _clear_state(repo_root)
            return result
        changed_files, private_attr_error, private_attr_remediated = _run_private_attr_gate_with_remediation(
            changed_files,
            reentry=False,
        )
        if private_attr_error is not None:
            return private_attr_error
        if private_attr_remediated or _resume_private_attr_review:
            changed_files, private_attr_bridge_error = _run_private_attr_remediation_bridge_review(
                changed_files,
                reentry=False,
            )
            if private_attr_bridge_error is not None:
                return private_attr_bridge_error
            _normalize_control_packet_line_refs(
                repo_root,
                plan_path=plan_path,
                changed_files=changed_files,
            )
            line_ref_error = _control_packet_line_ref_lint_error(
                repo_root,
                plan_path=plan_path,
                changed_files=changed_files,
            )
            if line_ref_error is not None:
                result["status"] = "error"
                result["step"] = "control_packet_line_ref_lint"
                result["errors"] = [line_ref_error]
                _clear_state(repo_root)
                return result
        final_test_files = _select_pytest_gate_files(changed_files, repo_root)
        if final_test_files:
            log(f"Final pytest gate: running {len(final_test_files)} test file(s)...")
            bridge_job_for_pytest = str(result.get("bridge_job_id") or "").strip()
            try:
                _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_final_pytest_started",
                    state="final_pytest_started",
                    transition_key=_phase_b_transition_key(bridge_job_for_pytest, "final_pytest_started"),
                    summary=f"Phase B final pytest started for {len(final_test_files)} test file(s)",
                    artifact_paths={"test_files": ",".join(final_test_files)},
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"] = [f"Phase B pager emission failed before final pytest: {exc}"]
                _clear_state(repo_root)
                return result
            final_pytest = _run_pytest_on_files(repo_root, final_test_files, timeout=pytest_gate_timeout)
            if not final_pytest["passed"]:
                failure_summary = (
                    f"Final pytest gate FAILED (exit={final_pytest['exit_code']}). "
                    "Tests must pass before commit. "
                    + _summarize_pytest_failure(final_pytest)
                )
                try:
                    _emit_phase_b_pytest_failure(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        state="final_pytest_failed",
                        source_key=bridge_job_for_pytest,
                        changed_files=changed_files,
                        test_files=final_test_files,
                        summary=failure_summary,
                    )
                except Exception as exc:
                    result["status"] = "error"
                    result["step"] = "phase_b_pager"
                    result["errors"] = [
                        f"Phase B pager emission failed after final pytest failure: {exc}"
                    ]
                    _clear_state(repo_root)
                    return result
                return {
                    "status": "error",
                    "step": "final_pytest_gate",
                    "errors": [failure_summary],
                }
            log("Final pytest gate: PASSED")
            try:
                _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_final_pytest_passed",
                    state="final_pytest_passed",
                    transition_key=_phase_b_transition_key(bridge_job_for_pytest, "final_pytest_passed"),
                    summary=f"Phase B final pytest passed for {len(final_test_files)} test file(s)",
                    artifact_paths={"test_files": ",".join(final_test_files)},
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"] = [f"Phase B pager emission failed after final pytest: {exc}"]
                _clear_state(repo_root)
                return result

        scratch_dir = repo_root / ".scratch"
        scratch_dir.mkdir(exist_ok=True)
        package_path = scratch_dir / "phase_b_supervisor_package.json"
        package_relpath = str(package_path.relative_to(repo_root))

        # Step 5b: Update tracked packet status before staging.
        # Advances from "Phase A" to a non-completed bridge-converged pending
        # state so the supervisor sees consistent state without making failed
        # pre-supervisor packages look completed to dispatcher reroute guards.
        # Guard: skip for planless mode where plan_path is a synthetic token
        # (P1 bot finding, 2026-04-06).
        if not plan_path.startswith("<"):
            update_plan_packet_status(
                repo_root,
                plan_path,
                PHASE_B_PRE_SUPERVISOR_PENDING_STATUS,
            )
            if plan_path not in changed_files:
                changed_files.append(plan_path)

        wave_class, target_gate_id = _refresh_phase_b_package_governance(
            repo_root,
            plan,
            plan_path,
            routing_record,
        )
        pre_supervisor_bridge_status = _build_effective_bridge_status(
            repo_root,
            wave_id,
            plan_path,
            result.get("bridge_rounds", 0),
        )
        pre_supervisor_raw_founder_override_token = _derive_phase_b_founder_override(
            plan_content=plan.get("content", ""),
            wave_id=wave_id,
            wave_class=wave_class,
            explicit_founder_override=plan.get("founder_override", ""),
        )
        pre_supervisor_founder_override_token = _supervisor_package_founder_override_token(
            pre_supervisor_raw_founder_override_token,
            wave_class=wave_class,
        )
        tracker_note_modified = False

        # Step 6: Stage files BEFORE running supervisor
        # This ensures the receipt staged_sha matches what commit_executor will use.
        # Scope to wave-owned files only — do not sweep unrelated dirty worktree files.
        if changed_files:
            if exact_stage_scope_files:
                reconciled_ok, reconciled_detail = _unstage_out_of_exact_scope(
                    repo_root,
                    exact_stage_scope_files,
                )
                if not reconciled_ok:
                    return {
                        "status": "error",
                        "step": "pre_supervisor_staging_scope_reconcile",
                        "stderr": reconciled_detail,
                        "errors": [
                            "Failed to reconcile exact staged scope before supervisor",
                            reconciled_detail,
                        ],
                    }
            log(f"Staging {len(changed_files)} wave-owned files before supervisor...")
            staged_ok, stage_detail = _stage_files_for_pipeline(repo_root, changed_files)
            if not staged_ok:
                return {
                    "status": "error",
                    "step": "staging",
                    "stderr": stage_detail,
                    "errors": [
                        "Failed to stage files before supervisor",
                        stage_detail,
                    ],
                }
            refreshed_changed_files = _collect_wave_owned_files(
                repo_root,
                plan_path,
                plan_declared_files,
                implementer_changed or None,
                executor_created or None,
                baseline_wave_files or None,
            )
            if refreshed_changed_files != changed_files:
                log(
                    "Post-stage package scope refreshed from "
                    f"{len(changed_files)} to {len(refreshed_changed_files)} file(s)"
                )
                changed_files = refreshed_changed_files
        indicator_path = ""
        should_collect_l4_indicator = _should_collect_l4_indicator_artifact(
            repo_root,
            wave_id=wave_id,
            wave_class=wave_class,
            tracker_note_modified=tracker_note_modified,
            founder_override_token=pre_supervisor_raw_founder_override_token,
            changed_files=changed_files,
        )
        if should_collect_l4_indicator:
            authority_guard_error = _guard_candidate_authority_scope_if_configured(
                repo_root,
                wave_id=wave_id,
                context="pre-supervisor L4 indicator collector",
                required=candidate_authority_required,
                trusted_metadata=candidate_authority_metadata,
            )
            if authority_guard_error is not None:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "pre_supervisor_candidate_authority_scope",
                    "errors": [authority_guard_error],
                }
            indicator_path, indicator_error = _collect_and_stage_l4_indicator_artifact(
                repo_root,
                wave_id=wave_id,
            )
            if indicator_error is not None:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "pre_supervisor_l4_indicator",
                    "errors": [indicator_error],
                }
            if indicator_path and indicator_path not in changed_files:
                changed_files.append(indicator_path)
                changed_files = sorted(set(changed_files))
            if indicator_path:
                packet_scope_modified, packet_scope_error = _refresh_phase_b_indicator_packet_scope(
                    repo_root,
                    plan_path=plan_path,
                    wave_id=wave_id,
                    indicator_path=indicator_path,
                    changed_files=changed_files,
                )
                if packet_scope_error is not None:
                    _clear_state(repo_root)
                    return {
                        "status": "error",
                        "step": "pre_supervisor_l4_indicator_scope",
                        "errors": [packet_scope_error],
                    }
                if packet_scope_modified and plan_path not in changed_files:
                    changed_files.append(plan_path)
                    changed_files = sorted(set(changed_files))
        package_changed_files = _collect_commit_bound_files(
            repo_root,
            changed_files,
            allowed_files=exact_stage_scope_files or None,
        )
        if package_changed_files != changed_files:
            log(
                "Supervisor package scope expanded to include "
                f"{len(package_changed_files) - len(changed_files)} staged commit-bound file(s)"
            )
            changed_files = package_changed_files
        if indicator_path:
            packet_scope_modified, packet_scope_error = _refresh_phase_b_indicator_packet_scope(
                repo_root,
                plan_path=plan_path,
                wave_id=wave_id,
                indicator_path=indicator_path,
                changed_files=changed_files,
            )
            if packet_scope_error is not None:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "pre_supervisor_l4_indicator_scope",
                    "errors": [packet_scope_error],
                }
            if packet_scope_modified and plan_path not in changed_files:
                changed_files.append(plan_path)
                changed_files = sorted(set(changed_files))
        effective_wave_class = _effective_phase_b_tracker_wave_class(
            wave_class,
            plan_content=plan.get("content", ""),
            changed_files=changed_files,
        )
        if effective_wave_class != wave_class:
            log(
                "Phase B packaging class adjusted from "
                f"{wave_class} to {effective_wave_class} for package scope"
            )
            wave_class = effective_wave_class
        (
            pre_supervisor_tracker_note,
            pre_supervisor_raw_founder_override_token,
            pre_supervisor_founder_override_token,
            tracker_note_modified,
            changed_files,
            tracker_sync_error,
        ) = _finalize_phase_b_pre_supervisor_tracker_note(
            repo_root,
            wave_id=wave_id,
            task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            wave_class=wave_class,
            target_gate_id=target_gate_id,
            plan_path=plan_path,
            plan_content=plan.get("content", ""),
            changed_files=changed_files,
            test_files=final_test_files,
            receipt_path=package_relpath,
            bridge_status=pre_supervisor_bridge_status,
            reentry=False,
            founder_override=pre_supervisor_raw_founder_override_token,
            unblocks_wave_id=plan.get("unblocks_wave_id", ""),
            unblocks_runtime_blocker=plan.get("unblocks_runtime_blocker", ""),
            allowed_files=exact_stage_scope_files or None,
        )
        if tracker_sync_error is not None:
            _clear_state(repo_root)
            return {
                "status": "error",
                "step": "pre_supervisor_tracker_note",
                "errors": [tracker_sync_error],
            }

        # Step 7: Build and run pre-commit supervisor via structured client
        log("Building supervisor package...")

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
        deferred_items = _collect_supervisor_deferred_items(
            changed_files,
            deferred_packet_path,
            repo_root=repo_root,
        )

        # Fenced files: dirty in git but not commit-bound (from other waves)
        fenced = _collect_fenced_dirty_files(repo_root, changed_files)

        scope_items = [plan_path]
        for path in changed_files:
            if path.startswith("reports/l4_wave_indicators/") and path not in scope_items:
                scope_items.append(path)

        supervisor_package = {
            "task_id": routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            "wave_name": wave_id,
            "wave_class": wave_class,
            "lane": "hooks/agents/bridge control-surface",
            "changed_files": changed_files,
            "fenced_files": fenced,
            "scope_items": scope_items,
            "fixes_implemented": ["Phase B implementation per locked plan"],
            "deferred_items": deferred_items,
            "bridge_status": pre_supervisor_bridge_status,
            "evidence_handles": _collect_supervisor_evidence_handles(repo_root, wave_id),
            "blocker_report_paths": blocker_paths,
            "current_judgment": "COMMIT_GO",
            "tracker_note_text": pre_supervisor_tracker_note,
            "evidence_command": _tracker_evidence_command_value(pre_supervisor_tracker_note),
        }
        if pre_supervisor_founder_override_token:
            supervisor_package["founder_override_token"] = pre_supervisor_founder_override_token
        package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        log("Running pre-commit supervisor...")
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="pre_commit_supervisor_started",
                state="started",
                transition_key=_phase_b_transition_key(str(package_path.relative_to(repo_root)), "supervisor_started"),
                summary="Pre-commit supervisor started from Phase B",
                artifact_paths={"supervisor_package": str(package_path.relative_to(repo_root))},
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [f"Phase B pager emission failed before pre-commit supervisor: {exc}"]
            _clear_state(repo_root)
            return result
        supervisor_result = run_pre_commit_supervisor(
            repo_root, package_path, verbose=verbose, bus_dir=_active_bus_dir(),
        )
        supervisor_parsed = supervisor_result.get("parsed", {})
        result["pre_commit_decision"] = supervisor_parsed.get("decision")
        result["pre_commit_summary"] = _supervisor_reason_text(supervisor_parsed)
        receipt_path = supervisor_result.get("receipt_path", "")
        log(f"Supervisor decision: {result['pre_commit_decision']}, receipt: {receipt_path}")
        if result.get("pre_commit_summary"):
            log(f"Supervisor summary: {result['pre_commit_summary']}")

        decision = result["pre_commit_decision"]
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="pre_commit_supervisor_completed",
                state=str(decision or "unknown"),
                transition_key=_phase_b_transition_key(
                    str(receipt_path or package_path.relative_to(repo_root)),
                    f"supervisor_completed:{decision or 'unknown'}",
                ),
                summary=f"Pre-commit supervisor completed with {decision or 'unknown'}",
                artifact_paths={
                    "supervisor_package": str(package_path.relative_to(repo_root)),
                    "supervisor_receipt": str(receipt_path or ""),
                },
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [f"Phase B pager emission failed after pre-commit supervisor: {exc}"]
            _clear_state(repo_root)
            return result
    if decision == "NEEDS_PHASE_B":
        # Re-entry: implementer fixes → bridge reviews → loop
        log("NEEDS_PHASE_B — re-invoking implementer then bridge loop")
        reentry_converged = _resume_reentry_private_attr_review
        bridge_decision = (
            ""
            if refresh_reentry_findings
            else str((saved_state or {}).get("last_reentry_bridge_decision") or "")
        )
        # Initial findings come from supervisor; subsequent rounds use bridge findings
        findings_for_impl = result.get("pre_commit_summary") or supervisor_parsed.get("summary", "Fix required")

        # Persist needs_phase_b_reentry state so crash-resume re-enters here.
        # Do not overwrite pending-review checkpoints; those stricter states
        # must survive until the fresh review runs.
        if not (
            _resume_reentry_private_attr_review
            or (_skip_to_reentry and skip_reentry_implementer_once)
        ):
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
                "last_reentry_bridge_decision": bridge_decision,
                "refresh_reentry_findings": refresh_reentry_findings,
                "runtime_pre_push_failure_reentry": reentry_runtime_pre_push_failure,
            })

        reentry_start_round = result["bridge_rounds"] + 1
        if skip_reentry_implementer_once:
            # A post-implementer checkpoint means fixes are already in the
            # worktree and the next durable action is bridge review. Older
            # checkpoints did not record the pending round, so fall back to the
            # saved bridge_rounds value to review the same round rather than
            # skipping past the max-round boundary.
            reentry_start_round = pending_reentry_bridge_round or max(1, result["bridge_rounds"])

        for reentry_round in range(reentry_start_round, max_bridge_rounds + 1):
            if reentry_converged:
                break
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
            elif skip_reentry_implementer_once:
                skip_reentry_implementer_once = False
                log("Re-entry: implementer already ran for the prior bridge findings; proceeding to review")
            else:
                log("Re-invoking implementer for fixes...")
                pre_reentry_files = set(_collect_changed_files(repo_root))
                reentry_prompt = _build_reentry_fix_prompt(
                    bridge_decision,
                    findings_for_impl,
                )
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_implementer_started",
                        state="reentry_started",
                        transition_key=_phase_b_reentry_implementer_transition_key(
                            reentry_round,
                            source_key="supervisor",
                            state="implementer_started",
                        ),
                        summary=f"Phase B re-entry implementer started for round {reentry_round}",
                        artifact_paths={"plan": plan_path},
                    )
                except Exception as exc:
                    return {
                        "status": "error",
                        "step": "phase_b_pager",
                        "errors": [f"Phase B pager emission failed before re-entry implementer: {exc}"],
                    }
                impl_result = invoke_implementer(
                    repo_root, reentry_prompt,
                    backend=backend, model_override=model,
                    timeout=timeout, verbose=verbose,
                    bus_dir=_active_bus_dir(),
                )
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_implementer_completed",
                        state=f"reentry_{impl_result.get('status', 'completed')}",
                        transition_key=_phase_b_reentry_implementer_transition_key(
                            reentry_round,
                            source_key="supervisor",
                            state="implementer_completed",
                        ),
                        summary=(
                            "Phase B re-entry implementer completed round "
                            f"{reentry_round} with {impl_result.get('status', 'unknown')}"
                        ),
                        artifact_paths={"plan": plan_path},
                    )
                except Exception as exc:
                    return {
                        "status": "error",
                        "step": "phase_b_pager",
                        "errors": [f"Phase B pager emission failed after re-entry implementer: {exc}"],
                    }
                reentry_fix_error = _complete_reentry_fix(
                    impl_result,
                    pre_reentry_files,
                    findings_for_impl,
                    reentry_round,
                )
                if reentry_fix_error is not None:
                    return reentry_fix_error

            changed_files = _bridge_review_scope_files(changed_files)
            log(
                "Re-entry: preparing "
                f"{len(changed_files)} wave-owned files before bridge review..."
            )
            changed_files, preparation_error = _prepare_phase_b_pre_review_package(
                repo_root,
                candidate_files=changed_files,
                exact_stage_scope_files=exact_stage_scope_files,
                plan_path=plan_path,
                wave_id=wave_id,
                wave_class=wave_class,
                step_prefix="reentry_bridge_pre_review",
                context="re-entry bridge review",
                **candidate_authority_package_kwargs,
            )
            if preparation_error is not None:
                _clear_state(repo_root)
                return preparation_error
            indicator_path = _phase_b_same_wave_indicator_path(wave_id)
            if indicator_path in changed_files:
                executor_created.add(indicator_path)

            # Bridge reviews the fix (bound to exact job_id)
            bridge_job_id = f"phase-b-reentry-r{reentry_round}-{uuid.uuid4().hex[:8]}"
            transition_key = _phase_b_review_transition_key(reentry_round, bridge_job_id)
            try:
                bridge_result = run_bridge_review(
                    repo_root,
                    f"Phase B re-entry R{reentry_round} after NEEDS_PHASE_B for {plan_path}",
                    job_id=bridge_job_id,
                    reader_agent=backend,
                    verbose=verbose,
                    timeout=timeout,
                    on_started=lambda: _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_reviewer_started",
                        state="reviewer_started",
                        transition_key=transition_key,
                        summary=f"Phase B reviewer started for round {reentry_round}",
                        artifact_paths={
                            "agent_review_report": str(result.get("agent_review_report_path") or ""),
                            "agent_review_status": str(result.get("agent_review_status_path") or ""),
                        },
                    ),
                )
            except Exception as exc:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "phase_b_pager",
                    "errors": [f"Phase B pager emission failed after re-entry reviewer launch: {exc}"],
                }
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

            if (
                bridge_result["exit_code"] == 0
                and _is_go_bridge_decision(bridge_decision)
            ):
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
                if render or raw_texts:
                    prior_deferred_packet_path = deferred_packet_path
                    all_non_blocking, deferred_packet_path = _sync_deferred_non_blocking_state(
                        repo_root,
                        wave_id,
                        all_non_blocking,
                        non_blocking_findings,
                        previous_packet_path=prior_deferred_packet_path,
                        executor_created=executor_created,
                        wave_class=wave_class,
                        target_gate_id=target_gate_id,
                    )
                    if deferred_packet_path is not None:
                        result["deferred_packet_path"] = deferred_packet_path
                        log(f"Re-entry GO: filed {len(non_blocking_findings)} non-blocking finding(s)")
                    else:
                        result.pop("deferred_packet_path", None)
                        if prior_deferred_packet_path:
                            log("Re-entry GO cleared stale deferred non-blocking packet")
                log("Bridge re-entry converged: GO")
                result["bridge_job_id"] = bridge_job_id
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_bridge_completed",
                        state="reentry_bridge_go",
                        transition_key=_phase_b_transition_key(bridge_job_id, "reentry_bridge_go"),
                        summary=f"Phase B re-entry bridge GO for round {reentry_round}",
                        artifact_paths={
                            "bridge_stdout": str(bridge_result.get("stdout_path") or ""),
                            "bridge_stderr": str(bridge_result.get("stderr_path") or ""),
                            "deferred_packet": str(deferred_packet_path or ""),
                        },
                    )
                except Exception as exc:
                    result["status"] = "error"
                    result["step"] = "phase_b_pager"
                    result["errors"] = [f"Phase B pager emission failed after re-entry bridge GO: {exc}"]
                    _clear_state(repo_root)
                    return result
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
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_final_verdict",
                        state="reentry_question_for_founder",
                        transition_key=_phase_b_transition_key(
                            bridge_job_id,
                            "reentry_question_for_founder",
                        ),
                        summary=result["errors"][0],
                    )
                except Exception as exc:
                    result["status"] = "error"
                    result["step"] = "phase_b_pager"
                    result["errors"].append(
                        f"Phase B pager emission failed on re-entry QUESTION verdict: {exc}"
                    )
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

                # Mirror the initial loop's parsing and repeat-cap checks.
                render, raw_texts = _read_bridge_review_material(repo_root, bridge_job_id)
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

                # A non-GO re-entry round remains nonconverged regardless of
                # finding dispositions. Preserve every finding for correction;
                # none of this round's findings have been deferred.
                findings_for_impl = _bridge_correction_context(
                    parsed_findings,
                    render,
                    raw_texts,
                    bridge_result.get("stdout", ""),
                )

                if reentry_round >= max_bridge_rounds:
                    log(
                        f"Reentry bridge: {bridge_decision} on final allowed round "
                        f"{reentry_round}/{max_bridge_rounds}; not re-invoking implementer"
                    )
                    break

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
                changed_files = _bridge_review_scope_files(changed_files)

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
                    "last_reentry_bridge_decision": bridge_decision,
                    "runtime_pre_push_failure_reentry": reentry_runtime_pre_push_failure,
                })
                log("Re-entry: checkpointed bridge findings; re-invoking implementer in-branch")
                pre_reentry_files = set(_collect_changed_files(repo_root))
                reentry_prompt = _build_reentry_fix_prompt(
                    bridge_decision,
                    findings_for_impl,
                )
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_implementer_started",
                        state="reentry_started",
                        transition_key=_phase_b_reentry_implementer_transition_key(
                            reentry_round,
                            source_key=bridge_job_id,
                            state="implementer_started",
                        ),
                        summary=f"Phase B re-entry implementer started for round {reentry_round}",
                        artifact_paths={"plan": plan_path},
                    )
                except Exception as exc:
                    return {
                        "status": "error",
                        "step": "phase_b_pager",
                        "errors": [f"Phase B pager emission failed before re-entry implementer: {exc}"],
                    }
                impl_result = invoke_implementer(
                    repo_root, reentry_prompt,
                    backend=backend, model_override=model,
                    timeout=timeout, verbose=verbose,
                    bus_dir=_active_bus_dir(),
                )
                try:
                    _emit_phase_b_event(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        event_type="phase_b_implementer_completed",
                        state=f"reentry_{impl_result.get('status', 'completed')}",
                        transition_key=_phase_b_reentry_implementer_transition_key(
                            reentry_round,
                            source_key=bridge_job_id,
                            state="implementer_completed",
                        ),
                        summary=(
                            "Phase B re-entry implementer completed round "
                            f"{reentry_round} with {impl_result.get('status', 'unknown')}"
                        ),
                        artifact_paths={"plan": plan_path},
                    )
                except Exception as exc:
                    return {
                        "status": "error",
                        "step": "phase_b_pager",
                        "errors": [f"Phase B pager emission failed after re-entry implementer: {exc}"],
                    }
                reentry_fix_error = _complete_reentry_fix(
                    impl_result,
                    pre_reentry_files,
                    findings_for_impl,
                    reentry_round + 1,
                )
                if reentry_fix_error is not None:
                    return reentry_fix_error
                skip_reentry_implementer_once = True
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
            try:
                _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_final_verdict",
                    state="reentry_max_rounds_reached",
                    transition_key=_phase_b_transition_key(
                        "phase-b-reentry",
                        "max_rounds_reached",
                    ),
                    summary=result["errors"][0],
                )
                _emit_phase_b_hard_fail(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    state="max_rounds_reached",
                    changed_files=changed_files,
                    summary=result["errors"][0],
                    reentry=True,
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"].append(
                    f"Phase B pager emission failed on re-entry max_rounds_reached: {exc}"
                )
                _clear_state(repo_root)
                return result
            # Clear state to prevent stale resume — next invocation must start fresh
            _clear_state(repo_root)
            return result

        blocking_deferred_findings = _blocking_findings_in_deferred_convergence(all_non_blocking)
        if blocking_deferred_findings:
            result["status"] = "error"
            result["step"] = "blocking_finding_convergence"
            result["errors"] = [
                "Re-entry bridge convergence state contains effective blocking "
                "finding(s) inside deferred/non-blocking findings; refusing to "
                "proceed to final pytest, supervisor, or commit handoff."
            ]
            result["blocking_findings"] = blocking_deferred_findings
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
        _normalize_control_packet_line_refs(
            repo_root,
            plan_path=plan_path,
            changed_files=changed_files,
        )
        line_ref_error = _control_packet_line_ref_lint_error(
            repo_root,
            plan_path=plan_path,
            changed_files=changed_files,
        )
        if line_ref_error is not None:
            result["status"] = "error"
            result["step"] = "control_packet_line_ref_lint"
            result["errors"] = [line_ref_error]
            _clear_state(repo_root)
            return result
        changed_files, private_attr_error, private_attr_remediated = _run_private_attr_gate_with_remediation(
            changed_files,
            reentry=True,
        )
        if private_attr_error is not None:
            _clear_state(repo_root)
            return private_attr_error
        if private_attr_remediated or _resume_reentry_private_attr_review:
            changed_files, private_attr_bridge_error = _run_private_attr_remediation_bridge_review(
                changed_files,
                reentry=True,
            )
            if private_attr_bridge_error is not None:
                if private_attr_bridge_error.get("status") != "question_for_founder":
                    _clear_state(repo_root)
                return private_attr_bridge_error
            _normalize_control_packet_line_refs(
                repo_root,
                plan_path=plan_path,
                changed_files=changed_files,
            )
            line_ref_error = _control_packet_line_ref_lint_error(
                repo_root,
                plan_path=plan_path,
                changed_files=changed_files,
            )
            if line_ref_error is not None:
                result["status"] = "error"
                result["step"] = "control_packet_line_ref_lint"
                result["errors"] = [line_ref_error]
                _clear_state(repo_root)
                return result
        reentry_test_files = _select_pytest_gate_files(changed_files, repo_root)
        if reentry_test_files:
            log(f"Re-entry pytest gate: running {len(reentry_test_files)} test file(s)...")
            reentry_pytest = _run_pytest_on_files(repo_root, reentry_test_files, timeout=pytest_gate_timeout)
            if not reentry_pytest["passed"]:
                failure_summary = (
                    f"Re-entry pytest gate FAILED (exit={reentry_pytest['exit_code']}). "
                    "Tests must pass before commit. "
                    + _summarize_pytest_failure(reentry_pytest)
                )
                try:
                    _emit_phase_b_pytest_failure(
                        repo_root,
                        routing_record=routing_record,
                        plan=plan,
                        plan_path=plan_path,
                        state="reentry_pytest_failed",
                        source_key=str(result.get("bridge_job_id") or "phase-b-reentry"),
                        changed_files=changed_files,
                        test_files=reentry_test_files,
                        summary=failure_summary,
                        reentry=True,
                    )
                except Exception as exc:
                    result["status"] = "error"
                    result["step"] = "phase_b_pager"
                    result["errors"] = [
                        f"Phase B pager emission failed after re-entry pytest failure: {exc}"
                    ]
                    _clear_state(repo_root)
                    return result
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_pytest_gate",
                    "errors": [failure_summary],
                }
            log("Re-entry pytest gate: PASSED")

        wave_class, target_gate_id = _refresh_phase_b_package_governance(
            repo_root,
            plan,
            plan_path,
            routing_record,
        )
        reentry_pre_supervisor_bridge_status = _build_effective_bridge_status(
            repo_root,
            wave_id,
            plan_path,
            result.get("bridge_rounds", 0),
            reentry=True,
        )
        reentry_pre_supervisor_raw_founder_override_token = _derive_phase_b_founder_override(
            plan_content=plan.get("content", ""),
            wave_id=wave_id,
            wave_class=wave_class,
            explicit_founder_override=plan.get("founder_override", ""),
        )
        reentry_pre_supervisor_founder_override_token = _supervisor_package_founder_override_token(
            reentry_pre_supervisor_raw_founder_override_token,
            wave_class=wave_class,
        )
        reentry_tracker_note_modified = False

        # Re-stage and re-run supervisor after re-entry convergence
        # FAIL CLOSED if restaging fails — do not run supervisor on stale state
        # Scope to wave-owned files only — do not sweep unrelated dirty worktree files.
        if changed_files:
            if exact_stage_scope_files:
                reconciled_ok, reconciled_detail = _unstage_out_of_exact_scope(
                    repo_root,
                    exact_stage_scope_files,
                )
                if not reconciled_ok:
                    _clear_state(repo_root)
                    return {
                        "status": "error",
                        "step": "reentry_staging_scope_reconcile",
                        "stderr": reconciled_detail,
                        "errors": [
                            "Failed to reconcile exact staged scope before re-entry supervisor",
                            reconciled_detail,
                        ],
                    }
            staged_ok, stage_detail = _stage_files_for_pipeline(repo_root, changed_files)
            if not staged_ok:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_staging",
                    "stderr": stage_detail,
                    "errors": [
                        "Failed to stage files after re-entry convergence",
                        stage_detail,
                    ],
                }
            refreshed_changed_files = _collect_wave_owned_files(
                repo_root,
                plan_path,
                plan_declared_files,
                implementer_changed or None,
                executor_created or None,
                baseline_wave_files or None,
            )
            if refreshed_changed_files != changed_files:
                log(
                    "Re-entry: post-stage package scope refreshed from "
                    f"{len(changed_files)} to {len(refreshed_changed_files)} file(s)"
                )
                changed_files = refreshed_changed_files
        indicator_path = ""
        reentry_should_collect_l4_indicator = _should_collect_l4_indicator_artifact(
            repo_root,
            wave_id=wave_id,
            wave_class=wave_class,
            tracker_note_modified=reentry_tracker_note_modified,
            founder_override_token=reentry_pre_supervisor_raw_founder_override_token,
            changed_files=changed_files,
        )
        if reentry_should_collect_l4_indicator:
            authority_guard_error = _guard_candidate_authority_scope_if_configured(
                repo_root,
                wave_id=wave_id,
                context="re-entry pre-supervisor L4 indicator collector",
                required=candidate_authority_required,
                trusted_metadata=candidate_authority_metadata,
            )
            if authority_guard_error is not None:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_pre_supervisor_candidate_authority_scope",
                    "errors": [authority_guard_error],
                }
            indicator_path, indicator_error = _collect_and_stage_l4_indicator_artifact(
                repo_root,
                wave_id=wave_id,
            )
            if indicator_error is not None:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_pre_supervisor_l4_indicator",
                    "errors": [indicator_error],
                }
            if indicator_path and indicator_path not in changed_files:
                changed_files.append(indicator_path)
                changed_files = sorted(set(changed_files))
            if indicator_path:
                packet_scope_modified, packet_scope_error = _refresh_phase_b_indicator_packet_scope(
                    repo_root,
                    plan_path=plan_path,
                    wave_id=wave_id,
                    indicator_path=indicator_path,
                    changed_files=changed_files,
                )
                if packet_scope_error is not None:
                    _clear_state(repo_root)
                    return {
                        "status": "error",
                        "step": "reentry_pre_supervisor_l4_indicator_scope",
                        "errors": [packet_scope_error],
                    }
                if packet_scope_modified and plan_path not in changed_files:
                    changed_files.append(plan_path)
                    changed_files = sorted(set(changed_files))
        reentry_package_changed_files = _collect_commit_bound_files(
            repo_root,
            changed_files,
            allowed_files=exact_stage_scope_files or None,
        )
        if reentry_package_changed_files != changed_files:
            log(
                "Re-entry supervisor package scope expanded to include "
                f"{len(reentry_package_changed_files) - len(changed_files)} staged commit-bound file(s)"
            )
            changed_files = reentry_package_changed_files
        if indicator_path:
            packet_scope_modified, packet_scope_error = _refresh_phase_b_indicator_packet_scope(
                repo_root,
                plan_path=plan_path,
                wave_id=wave_id,
                indicator_path=indicator_path,
                changed_files=changed_files,
            )
            if packet_scope_error is not None:
                _clear_state(repo_root)
                return {
                    "status": "error",
                    "step": "reentry_pre_supervisor_l4_indicator_scope",
                    "errors": [packet_scope_error],
                }
            if packet_scope_modified and plan_path not in changed_files:
                changed_files.append(plan_path)
                changed_files = sorted(set(changed_files))
        if (
            reentry_runtime_pre_push_failure
            and _phase_b_declares_structural_runtime_intent(plan.get("content", ""), routing_record)
            and not _phase_b_scope_has_runtime_substrate_file(changed_files)
        ):
            result["status"] = "error"
            result["step"] = "reentry_runtime_pre_push_scope"
            result["errors"] = [
                "Refusing to convert a runtime pre-push failure re-entry for an "
                "L4_STRUCTURAL implementation wave into a control-only commit-ready package. "
                "Resume Phase B with a runtime/test structural fix or preserve the failure as a blocker."
            ]
            return result
        effective_wave_class = _effective_phase_b_tracker_wave_class(
            wave_class,
            plan_content=plan.get("content", ""),
            changed_files=changed_files,
        )
        if effective_wave_class != wave_class:
            log(
                "Re-entry Phase B packaging class adjusted from "
                f"{wave_class} to {effective_wave_class} for planning-only scope"
            )
            wave_class = effective_wave_class
        (
            reentry_pre_supervisor_tracker_note,
            reentry_pre_supervisor_raw_founder_override_token,
            reentry_pre_supervisor_founder_override_token,
            reentry_tracker_note_modified,
            changed_files,
            reentry_tracker_sync_error,
        ) = _finalize_phase_b_pre_supervisor_tracker_note(
            repo_root,
            wave_id=wave_id,
            task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
            wave_class=wave_class,
            target_gate_id=target_gate_id,
            plan_path=plan_path,
            plan_content=plan.get("content", ""),
            changed_files=changed_files,
            test_files=reentry_test_files,
            receipt_path=str(package_path.relative_to(repo_root)),
            bridge_status=reentry_pre_supervisor_bridge_status,
            reentry=True,
            founder_override=reentry_pre_supervisor_raw_founder_override_token,
            unblocks_wave_id=plan.get("unblocks_wave_id", ""),
            unblocks_runtime_blocker=plan.get("unblocks_runtime_blocker", ""),
            allowed_files=exact_stage_scope_files or None,
        )
        if reentry_tracker_sync_error is not None:
            _clear_state(repo_root)
            return {
                "status": "error",
                "step": "reentry_pre_supervisor_tracker_note",
                "errors": [reentry_tracker_sync_error],
            }

        # Refresh ALL supervisor package truth for re-entry
        supervisor_package["wave_class"] = wave_class
        supervisor_package["changed_files"] = changed_files
        supervisor_package["fenced_files"] = _collect_fenced_dirty_files(repo_root, changed_files)
        supervisor_package["deferred_items"] = _collect_supervisor_deferred_items(
            changed_files,
            deferred_packet_path,
            repo_root=repo_root,
        )
        scope_items = [plan_path]
        for path in changed_files:
            if path.startswith("reports/l4_wave_indicators/") and path not in scope_items:
                scope_items.append(path)
        supervisor_package["scope_items"] = scope_items
        supervisor_package["bridge_status"] = reentry_pre_supervisor_bridge_status
        supervisor_package["evidence_handles"] = _collect_supervisor_evidence_handles(
            repo_root,
            wave_id,
        )
        supervisor_package["tracker_note_text"] = reentry_pre_supervisor_tracker_note
        supervisor_package["evidence_command"] = _tracker_evidence_command_value(
            reentry_pre_supervisor_tracker_note
        )
        # Refresh blocker acknowledgment (may have changed during re-entry)
        blocking_dir = repo_root / "reports" / "deferred" / "blocking"
        if blocking_dir.is_dir():
            supervisor_package["blocker_report_paths"] = sorted(
                str(p.relative_to(repo_root))
                for p in blocking_dir.iterdir()
                if p.is_file() and p.suffix == ".md" and p.name != "README.md"
            )
        if reentry_pre_supervisor_founder_override_token:
            supervisor_package["founder_override_token"] = reentry_pre_supervisor_founder_override_token
        else:
            supervisor_package.pop("founder_override_token", None)
        package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        log("Re-running supervisor after bridge re-entry...")
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="pre_commit_supervisor_started",
                state="reentry_started",
                transition_key=_phase_b_transition_key(
                    str(package_path.relative_to(repo_root)),
                    "reentry_supervisor_started",
                ),
                summary="Pre-commit supervisor re-started after Phase B re-entry",
                artifact_paths={"supervisor_package": str(package_path.relative_to(repo_root))},
            )
        except Exception as exc:
            _clear_state(repo_root)
            return {
                "status": "error",
                "step": "phase_b_pager",
                "errors": [f"Phase B pager emission failed before re-entry supervisor: {exc}"],
            }
        supervisor_result = run_pre_commit_supervisor(
            repo_root, package_path, verbose=verbose, bus_dir=_active_bus_dir(),
        )
        supervisor_parsed = supervisor_result.get("parsed", {})
        decision = supervisor_parsed.get("decision")
        receipt_path = supervisor_result.get("receipt_path", "")
        result["pre_commit_decision"] = decision
        result["pre_commit_summary"] = _supervisor_reason_text(supervisor_parsed)
        log(f"Post-reentry supervisor decision: {decision}")
        if result.get("pre_commit_summary"):
            log(f"Post-reentry supervisor summary: {result['pre_commit_summary']}")
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="pre_commit_supervisor_completed",
                state=f"reentry_{decision or 'unknown'}",
                transition_key=_phase_b_transition_key(
                    str(receipt_path or package_path.relative_to(repo_root)),
                    f"reentry_supervisor_completed:{decision or 'unknown'}",
                ),
                summary=f"Pre-commit supervisor re-entry completed with {decision or 'unknown'}",
                artifact_paths={
                    "supervisor_package": str(package_path.relative_to(repo_root)),
                    "supervisor_receipt": str(receipt_path or ""),
                },
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [f"Phase B pager emission failed after re-entry supervisor: {exc}"]
            _clear_state(repo_root)
            return result

        if decision == "NEEDS_PHASE_B":
            changed_files = _collect_wave_owned_files(
                repo_root,
                plan_path,
                plan_declared_files,
                implementer_changed or None,
                executor_created or None,
                baseline_wave_files or None,
            )
            changed_files = _collect_commit_bound_files(
                repo_root,
                changed_files,
                allowed_files=exact_stage_scope_files or None,
            )
            changed_files = _bridge_review_scope_files(changed_files)
            result["status"] = "needs_phase_b"
            result["step"] = "post_reentry_supervisor"
            detail = result.get("pre_commit_summary", "")
            message = "Supervisor returned NEEDS_PHASE_B after reentry convergence. Manual intervention required."
            if detail:
                message += f" {detail}"
            result["detail"] = message
            result["reason"] = message
            result["resume_after"] = "needs_phase_b_reentry"
            result["errors"] = [message]
            result["changed_files"] = sorted(changed_files)
            result["bridge_scope_fingerprint"] = _bridge_scope_fingerprint(repo_root, changed_files)
            result["implementer_changed"] = sorted(implementer_changed)
            result["executor_created"] = sorted(executor_created)
            result["baseline_wave_files"] = sorted(baseline_wave_files)
            result["all_non_blocking"] = all_non_blocking
            result["finding_history"] = finding_history
            try:
                _emit_phase_b_hard_fail(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    state="needs_phase_b",
                    changed_files=changed_files,
                    summary=message,
                    reentry=True,
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"].append(
                    f"Phase B pager emission failed on re-entry NEEDS_PHASE_B: {exc}"
                )
                _clear_state(repo_root)
                return result
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
            try:
                _emit_phase_b_event(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    event_type="phase_b_final_verdict",
                    state="reentry_supervisor_rejected",
                    transition_key=_phase_b_transition_key(
                        str(receipt_path or "post-reentry-supervisor"),
                        f"supervisor_rejected:{decision or 'unknown'}",
                    ),
                    summary=message,
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"].append(
                    f"Phase B pager emission failed on re-entry supervisor verdict: {exc}"
                )
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
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="phase_b_final_verdict",
                state="supervisor_rejected",
                transition_key=_phase_b_transition_key(
                    str(receipt_path or "pre-commit-supervisor"),
                    f"supervisor_rejected:{decision or 'unknown'}",
                ),
                summary=message,
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"].append(
                f"Phase B pager emission failed on supervisor verdict: {exc}"
            )
        _clear_state(repo_root)
        return result

    # Step 8: Prepare commit handoff with explicit receipt path
    #
    # COMMIT_GO means the package is implemented and must remain routable to
    # commit_executor; dispatcher intentionally rejects COMPLETED packets.
    # The status mutation is itself part of the commit-bound packet.  Stage it
    # and rerun the supervisor before writing the handoff so the receipt's
    # staged_sha authorizes the exact index commit_executor will receive.
    if not plan_path.startswith("<"):
        update_plan_packet_status(
            repo_root, plan_path, "IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT",
        )
        if plan_path not in changed_files:
            changed_files.append(plan_path)
            changed_files = sorted(set(changed_files))
        status_staged, status_stage_detail = _stage_files_for_pipeline(repo_root, [plan_path])
        if not status_staged:
            return {
                "status": "error",
                "step": "commit_handoff_packet_status_stage",
                "stderr": status_stage_detail,
                "errors": [
                    "Failed to stage final Phase B packet status before commit handoff",
                    status_stage_detail,
                ],
            }
        pre_status_refresh_scope = list(changed_files)
        changed_files = _collect_wave_owned_files(
            repo_root,
            plan_path,
            plan_declared_files,
            implementer_changed or None,
            executor_created or None,
            baseline_wave_files or None,
        )
        changed_files = _collect_commit_bound_files(
            repo_root,
            changed_files,
            allowed_files=exact_stage_scope_files or None,
        )
        changed_files = sorted({*pre_status_refresh_scope, *changed_files})
        changed_files = _phase_b_pre_supervisor_note_scope(changed_files)
        scope_items = [plan_path]
        for path in changed_files:
            if path.startswith("reports/l4_wave_indicators/") and path not in scope_items:
                scope_items.append(path)
        supervisor_package["changed_files"] = changed_files
        supervisor_package["fenced_files"] = _collect_fenced_dirty_files(repo_root, changed_files)
        supervisor_package["scope_items"] = scope_items
        supervisor_package["deferred_items"] = _collect_supervisor_deferred_items(
            changed_files,
            deferred_packet_path,
            repo_root=repo_root,
        )
        supervisor_package["evidence_handles"] = _collect_supervisor_evidence_handles(
            repo_root,
            wave_id,
        )
        package_path.write_text(json.dumps(supervisor_package, indent=2) + "\n", encoding="utf-8")

        log("Re-running supervisor after commit-ready packet status refresh...")
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="pre_commit_supervisor_started",
                state="commit_ready_status_refresh_started",
                transition_key=_phase_b_transition_key(
                    str(package_path.relative_to(repo_root)),
                    "commit_ready_status_refresh_started",
                ),
                summary="Pre-commit supervisor re-started after commit-ready packet status refresh",
                artifact_paths={"supervisor_package": str(package_path.relative_to(repo_root))},
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [
                f"Phase B pager emission failed before commit-ready status supervisor: {exc}"
            ]
            _clear_state(repo_root)
            return result
        supervisor_result = run_pre_commit_supervisor(
            repo_root, package_path, verbose=verbose, bus_dir=_active_bus_dir(),
        )
        supervisor_parsed = supervisor_result.get("parsed", {})
        decision = supervisor_parsed.get("decision")
        receipt_path = supervisor_result.get("receipt_path", "")
        result["pre_commit_decision"] = decision
        result["pre_commit_summary"] = _supervisor_reason_text(supervisor_parsed)
        log(f"Commit-ready status supervisor decision: {decision}, receipt: {receipt_path}")
        if result.get("pre_commit_summary"):
            log(f"Commit-ready status supervisor summary: {result['pre_commit_summary']}")
        try:
            _emit_phase_b_event(
                repo_root,
                routing_record=routing_record,
                plan=plan,
                plan_path=plan_path,
                event_type="pre_commit_supervisor_completed",
                state=f"commit_ready_status_refresh_{decision or 'unknown'}",
                transition_key=_phase_b_transition_key(
                    str(receipt_path or package_path.relative_to(repo_root)),
                    f"commit_ready_status_refresh_completed:{decision or 'unknown'}",
                ),
                summary=(
                    "Pre-commit supervisor commit-ready status refresh completed "
                    f"with {decision or 'unknown'}"
                ),
                artifact_paths={
                    "supervisor_package": str(package_path.relative_to(repo_root)),
                    "supervisor_receipt": str(receipt_path or ""),
                },
            )
        except Exception as exc:
            result["status"] = "error"
            result["step"] = "phase_b_pager"
            result["errors"] = [
                f"Phase B pager emission failed after commit-ready status supervisor: {exc}"
            ]
            _clear_state(repo_root)
            return result
        if decision == "NEEDS_PHASE_B":
            changed_files = _bridge_review_scope_files(changed_files)
            message = (
                "Supervisor returned NEEDS_PHASE_B after commit-ready packet "
                "status refresh. Manual intervention required."
            )
            detail = result.get("pre_commit_summary", "")
            if detail:
                message += f" {detail}"
            result["status"] = "needs_phase_b"
            result["step"] = "commit_ready_status_supervisor"
            result["detail"] = message
            result["reason"] = message
            result["resume_after"] = "commit_ready_status_supervisor"
            result["errors"] = [message]
            result["changed_files"] = sorted(changed_files)
            result["bridge_scope_fingerprint"] = _bridge_scope_fingerprint(repo_root, changed_files)
            result["implementer_changed"] = sorted(implementer_changed)
            result["executor_created"] = sorted(executor_created)
            result["baseline_wave_files"] = sorted(baseline_wave_files)
            result["all_non_blocking"] = all_non_blocking
            result["finding_history"] = finding_history
            try:
                _emit_phase_b_hard_fail(
                    repo_root,
                    routing_record=routing_record,
                    plan=plan,
                    plan_path=plan_path,
                    state="needs_phase_b",
                    changed_files=changed_files,
                    summary=message,
                    reentry=bool("reentry_converged" in locals() and locals()["reentry_converged"]),
                )
            except Exception as exc:
                result["status"] = "error"
                result["step"] = "phase_b_pager"
                result["errors"].append(
                    f"Phase B pager emission failed on commit-ready status NEEDS_PHASE_B: {exc}"
                )
            _clear_state(repo_root)
            return result
        if decision not in ("COMMIT_GO", "COMMIT_GO_HOLD_PUSH"):
            result["status"] = "supervisor_rejected"
            result["step"] = "commit_ready_status_supervisor"
            detail = result.get("pre_commit_summary", "")
            message = f"Commit-ready status supervisor returned {decision}"
            if detail:
                message += f". {detail}"
            result["errors"] = [message]
            _clear_state(repo_root)
            return result

    # FAIL CLOSED if receipt_path is empty — supervisor must provide a valid path
    if not receipt_path or not receipt_path.strip():
        return {
            "status": "error",
            "step": "commit_handoff",
            "errors": ["Supervisor returned empty receipt_path — cannot produce commit_ready handoff. Fail closed."],
        }

    # Scope to wave-owned files only — do not sweep all dirty files
    if exact_stage_scope_files:
        reconciled_ok, reconciled_detail = _unstage_out_of_exact_scope(
            repo_root,
            exact_stage_scope_files,
        )
        if not reconciled_ok:
            return {
                "status": "error",
                "step": "commit_handoff_stage_scope_reconcile",
                "stderr": reconciled_detail,
                "errors": [
                    "Failed to reconcile exact staged scope before commit handoff",
                    reconciled_detail,
                ],
            }
    pre_handoff_scope = list(changed_files)
    wave_owned_files = _collect_wave_owned_files(
        repo_root,
        plan_path,
        plan_declared_files,
        implementer_changed or None,
        executor_created or None,
        baseline_wave_files or None,
    )
    wave_owned_files = _collect_commit_bound_files(
        repo_root,
        wave_owned_files,
        allowed_files=exact_stage_scope_files or None,
    )
    wave_owned_files = sorted({*pre_handoff_scope, *wave_owned_files})
    wave_owned_files = _phase_b_pre_supervisor_note_scope(wave_owned_files)
    if not wave_owned_files:
        return {
            "status": "error",
            "step": "commit_handoff",
            "errors": ["files_to_stage is empty — cannot produce a commit_ready handoff with no files"],
        }
    handoff_deferred_items = _collect_supervisor_deferred_items(
        wave_owned_files,
        deferred_packet_path,
        repo_root=repo_root,
    )
    handoff_files_to_stage, handoff_staged_deletions = _split_commit_handoff_stage_files(
        repo_root,
        wave_id,
        wave_owned_files,
    )
    if not handoff_files_to_stage:
        return {
            "status": "error",
            "step": "commit_handoff",
            "errors": [
                "files_to_stage is empty after staged-deletion reconciliation - "
                "cannot produce a commit_ready handoff with no add-able files"
            ],
        }
    handoff_bridge_status = _build_effective_bridge_status(
        repo_root,
        wave_id,
        plan_path,
        result.get("bridge_rounds", 0),
        reentry=bool("reentry_converged" in locals() and locals()["reentry_converged"]),
    )
    handoff_test_files = locals().get("reentry_test_files") or locals().get("final_test_files") or []
    tracker_note_text = build_phase_b_tracker_note(
        wave_id=wave_id,
        task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        plan_path=plan_path,
        plan_content=plan.get("content", ""),
        changed_files=wave_owned_files,
        test_files=handoff_test_files,
        receipt_path=receipt_path,
        bridge_rounds=_bridge_rounds_for_tracker_note(handoff_bridge_status),
        reentry=bool("reentry_converged" in locals() and locals()["reentry_converged"]),
        founder_override=plan.get("founder_override", ""),
        unblocks_wave_id=plan.get("unblocks_wave_id", ""),
        unblocks_runtime_blocker=plan.get("unblocks_runtime_blocker", ""),
    )
    handoff_scope_items = list(dict.fromkeys([plan_path, *handoff_staged_deletions]))
    log(
        "Preparing commit handoff "
        f"({len(wave_owned_files)} wave-owned files; {len(handoff_files_to_stage)} stage paths)..."
    )
    commit_target_branch: str | None = None
    commit_branch_prefix = "jabramsja"
    (
        routed_branch_prefix,
        routed_target_branch,
        routed_target_branch_error,
    ) = _launch_target_branch_authority_from_routing_record(
        routing_record,
        wave_id=wave_id,
    )
    if routed_target_branch_error is not None:
        result["status"] = "error"
        result["step"] = "commit_target_branch_authority"
        result["errors"] = [routed_target_branch_error]
        _clear_state(repo_root)
        return result
    if routed_target_branch:
        commit_branch_prefix = routed_branch_prefix
        commit_target_branch = routed_target_branch
    else:
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if branch_result.returncode == 0:
            observed_branch = branch_result.stdout.strip()
            if "/" in observed_branch and observed_branch not in ("dev", "main", "master", "HEAD"):
                observed_branch_prefix = observed_branch.split("/", 1)[0].strip() or "jabramsja"
                preserved_target_branch = _phase_b_target_branch_for_current_worktree(
                    observed_branch,
                    wave_id=wave_id,
                    wave_class=wave_class,
                    plan_content=str(plan.get("content") or ""),
                    branch_prefix=observed_branch_prefix,
                )
                if preserved_target_branch:
                    commit_branch_prefix = observed_branch_prefix
                    commit_target_branch = preserved_target_branch
    handoff_path = prepare_commit_handoff(
        repo_root,
        wave_id=wave_id,
        task_id=routing_record.get("task_id", "[EXECUTOR-SURFACES]"),
        wave_class=wave_class,
        target_gate_id=target_gate_id,
        branch_prefix=commit_branch_prefix,
        target_branch=commit_target_branch or None,
        tracker_note_text=tracker_note_text,
        fixes_implemented=["Phase B implementation per locked plan"],
        files_to_stage=handoff_files_to_stage,
        pre_commit_receipt_path=receipt_path,
        commit_message=f"feat: Phase B implementation for {wave_id}\n\nCo-Authored-By: Codex GPT-5.5 xhigh <noreply@openai.com>",
        pr_title=f"feat: Phase B - {wave_id}",
        pr_body=f"## Summary\nPhase B implementation per locked plan at {plan_path}",
        tracked_packet=plan_path if not plan_path.startswith("<") else None,
        supervisor_lane="hooks/agents/bridge control-surface",
        deferred_items=handoff_deferred_items,
        bridge_status=handoff_bridge_status,
        scope_items=handoff_scope_items,
        evidence_handles={"indicator": f"reports/l4_wave_indicators/{wave_id}.json"},
        pager_route=str(routing_record.get("pager_route") or "").strip() or None,
        bus_dir=_active_bus_dir(),
    )
    result["status"] = "commit_ready"
    result["handoff_path"] = str(handoff_path)
    result["pre_commit_decision"] = decision
    result["receipt_path"] = receipt_path
    try:
        _emit_phase_b_event(
            repo_root,
            routing_record=routing_record,
            plan=plan,
            plan_path=plan_path,
            event_type="phase_b_final_verdict",
            state=str(decision or "commit_ready"),
            transition_key=_phase_b_transition_key(str(receipt_path), "phase_b_final_verdict"),
            summary=f"Phase B final verdict {decision or 'COMMIT_GO'}",
            artifact_paths={
                "handoff": str(handoff_path),
                "supervisor_receipt": str(receipt_path),
            },
        )
        _emit_phase_b_event(
            repo_root,
            routing_record=routing_record,
            plan=plan,
            plan_path=plan_path,
            event_type="commit_ready",
            state="commit_ready",
            transition_key=_phase_b_transition_key(str(receipt_path or result.get("bridge_job_id") or ""), "commit_ready"),
            summary="Phase B reached commit_ready",
            artifact_paths={
                "handoff": str(handoff_path),
                "supervisor_receipt": str(receipt_path),
            },
        )
    except Exception as exc:
        result["status"] = "error"
        result["step"] = "phase_b_pager"
        result["errors"] = [f"Phase B pager emission failed at commit_ready: {exc}"]
        _clear_state(repo_root)
        return result
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
    parser.add_argument(
        "--dispatcher-owned-recovery",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--bus-dir",
        default=None,
        help="Active repo-root agent bus (.agent_bus or .agent_bus-<id>)",
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
        bus_dir=args.bus_dir,
    )

    if (
        result.get("status") not in ("success", "ready", "commit_ready")
        and not args.dispatcher_owned_recovery
    ):
        try:
            from recovery_gate import attempt_recovery
        except ImportError:
            _rg_path = SCRIPT_DIR / "recovery_gate.py"
            import importlib.util as _rg_ilu
            _rg_spec = _rg_ilu.spec_from_file_location("recovery_gate", str(_rg_path))
            _rg_mod = _rg_ilu.module_from_spec(_rg_spec)
            assert _rg_spec.loader is not None
            _rg_spec.loader.exec_module(_rg_mod)
            attempt_recovery = _rg_mod.attempt_recovery
        try:
            recovery_wave = str(
                result.get("wave_id")
                or (routing_record_override or {}).get("wave_name", "")
                or (routing_record_override or {}).get("wave_id", "")
                or (Path(args.plan).stem if args.plan else "wave-unknown")
            ).strip() or "wave-unknown"
            recovery = attempt_recovery(
                repo_root,
                result,
                normalize_wave_id(recovery_wave),
                bus_dir=args.bus_dir,
            )
            result["recovery"] = recovery
        except Exception as exc:
            if args.verbose or not args.json:
                print(f"[phase-b] Recovery gate unavailable in standalone: {exc}")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"[phase-b] Status: {result.get('status')}")
        if result.get("errors"):
            for e in result["errors"]:
                print(f"[phase-b] Error: {e}")
        if result.get("recovery"):
            recovery = result["recovery"]
            print(f"[phase-b] Recovery: class={recovery.get('failure_class')} "
                  f"tier={recovery.get('tier')} recovered={recovery.get('recovered')}")

    if result.get("recovery", {}).get("recovered"):
        return 0
    return 0 if result.get("status") in ("success", "ready", "commit_ready") else 1


if __name__ == "__main__":
    sys.exit(main())
