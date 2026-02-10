"""
Cross-doc consistency checks for root canonical trackers.

This module enforces semantic agreement between STATUS.md and TASKS.md for
high-risk execution-layer claims that can otherwise drift silently.
"""

from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = REPO_ROOT / "STATUS.md"
TASKS_PATH = REPO_ROOT / "TASKS.md"

LAYER_TOKENS = ("BOOTSTRAP", "META_CIRCULAR")


def _extract_canonical_layer(text: str, label: str) -> str:
    pattern = re.compile(rf"^{re.escape(label)}:\s*(BOOTSTRAP|META_CIRCULAR)\s*$", re.MULTILINE)
    matches = pattern.findall(text)
    assert len(matches) == 1, (
        f"Expected exactly one canonical layer line for '{label}', found {len(matches)}.\n"
        f"Required format: '{label}: BOOTSTRAP|META_CIRCULAR'"
    )
    return matches[0]


def test_execution_layer_claims_match_between_status_and_tasks() -> None:
    """
    STATUS.md and TASKS.md must not disagree on canonical execution-layer lines.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    for label in ("Current Recurrence Layer", "Current Exhaustion Layer"):
        status_layer = _extract_canonical_layer(status_text, label)
        tasks_layer = _extract_canonical_layer(tasks_text, label)
        assert status_layer in LAYER_TOKENS
        assert tasks_layer in LAYER_TOKENS
        assert status_layer == tasks_layer, (
            f"STATUS.md and TASKS.md disagree for '{label}'. "
            f"status={status_layer}, tasks={tasks_layer}"
        )


def test_both_trackers_state_algorithm_path_matches_canonical_layer() -> None:
    """
    Runtime path text must match canonical layer declaration.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    status_layer = _extract_canonical_layer(status_text, "Current Recurrence Layer")
    tasks_layer = _extract_canonical_layer(tasks_text, "Current Recurrence Layer")
    assert status_layer == tasks_layer

    if status_layer == "META_CIRCULAR":
        status_has_marker = (
            "run_algorithm_meta_circular() defaults to `step_kernel_mu(" in status_text
            or "`run_algorithm_meta_circular()` defaults to `step_kernel_mu(" in status_text
            or "run_algorithm_meta_circular() now defaults to structural kernel bridge path" in status_text
        )
        tasks_has_marker = (
            "defaults to structural kernel bridge path" in tasks_text
            or "run_algorithm_meta_circular() defaults to `step_kernel_mu(" in tasks_text
            or "`run_algorithm_meta_circular()` defaults to `step_kernel_mu(" in tasks_text
        )
        assert status_has_marker, "STATUS.md missing Gate 4 structural runtime marker."
        assert tasks_has_marker, "TASKS.md missing Gate 4 structural runtime marker."
    else:
        assert "uses Python match/substitute" in status_text
        assert "uses Python match/substitute" in tasks_text


def test_status_l3_summary_is_not_self_contradictory() -> None:
    """
    STATUS.md must not claim both "L3 achieved/complete" and "L3 future".
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    has_l3_achieved = (
        "L3 COMPLETE" in status_text
        or "L3: Substrate Portability (ACHIEVED" in status_text
    )
    has_l3_future_row = any(
        "| **L3:" in line and "FUTURE" in line
        for line in status_text.splitlines()
    )
    assert not (has_l3_achieved and has_l3_future_row), (
        "STATUS.md has contradictory L3 claims (achieved/complete vs future)."
    )


def test_gate_snapshot_matches_between_status_and_tasks() -> None:
    """
    STATUS.md and TASKS.md must mirror Gate 3/4/5 snapshot lines exactly.

    This prevents drift where one tracker says Gate 4 started but the other
    still reads as pre-Gate-4.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    required_snapshot_lines = (
        "Gate 3: COMPLETE",
        "Gate 4: COMPLETE",
        "Gate 5: IN_PROGRESS",
    )

    for line in required_snapshot_lines:
        assert line in status_text, f"STATUS.md missing gate snapshot line: {line}"
        assert line in tasks_text, f"TASKS.md missing gate snapshot line: {line}"


def test_status_current_phase_name_matches_active_gate_snapshot() -> None:
    """
    STATUS.md "Current Phase" must align with the active IN_PROGRESS gate snapshot.

    Prevents drift where the phase header remains on an old milestone while
    canonical gate snapshot has advanced.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")

    phase_name_match = re.search(r"^NAME:\s*(.+)$", status_text, re.MULTILINE)
    assert phase_name_match, "STATUS.md must include 'NAME:' in Current Phase block."
    phase_name = phase_name_match.group(1).strip()

    active_gate_match = re.search(
        r"^\-\s*Gate\s+(\d+):\s*IN_PROGRESS\b", status_text, re.MULTILINE
    )
    assert active_gate_match, (
        "STATUS.md must include one active gate line in Gate Snapshot "
        "(e.g., '- Gate 5: IN_PROGRESS')."
    )
    active_gate = active_gate_match.group(1)

    assert f"Gate {active_gate}" in phase_name, (
        "STATUS.md Current Phase NAME does not match active gate snapshot.\n"
        f"  active gate: Gate {active_gate}\n"
        f"  phase name:  {phase_name}\n"
        "Update NAME to include the active gate."
    )


def test_tasks_next_section_has_active_work_only() -> None:
    """
    TASKS.md NEXT section should track active work, not completed history dumps.

    Historical implementation detail belongs in Ra/STATUS, not in NEXT.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    next_match = re.search(
        r"## NEXT \(short, bounded follow-ups\)\n(.*?)\n## VECTOR ",
        tasks_text,
        re.DOTALL,
    )
    assert next_match, "Could not isolate TASKS.md NEXT section."
    next_section = next_match.group(1)

    stale_patterns = (
        r"\[x\]",                         # completed checklist items
        r"\(DONE\s+\d{4}-\d{2}-\d{2}\)",  # dated done markers
        r"\b✅\b",                         # checkmark history style
        r"Promoted from VECTOR",          # historical progression detail
        r"All blockers resolved",         # postmortem wording
        r"### Step \d+:",                 # completed migration-plan dump style
    )

    stale_hits = []
    for pat in stale_patterns:
        if re.search(pat, next_section):
            stale_hits.append(pat)

    assert not stale_hits, (
        "TASKS.md NEXT contains stale completed-history markers. "
        "Keep NEXT focused on active follow-up work.\n"
        f"Matched patterns: {stale_hits}"
    )

    assert re.search(r"^\-\s*\[\s\]\s+", next_section, re.MULTILINE), (
        "TASKS.md NEXT should contain at least one active unchecked task "
        "('- [ ] ...')."
    )
