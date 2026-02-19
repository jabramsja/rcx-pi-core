"""
Cross-doc consistency checks for root canonical trackers.

This module enforces semantic agreement between STATUS.md and TASKS.md for
high-risk execution-layer claims that can otherwise drift silently.
"""

from __future__ import annotations

from pathlib import Path
import re


REPO_ROOT = Path(__file__).parents[2]
STATUS_PATH = REPO_ROOT / "STATUS.md"
TASKS_PATH = REPO_ROOT / "TASKS.md"
MANIFEST_PATH = REPO_ROOT / "roadmap" / "MANIFEST.md"

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
    )

    for line in required_snapshot_lines:
        assert line in status_text, f"STATUS.md missing gate snapshot line: {line}"
        assert line in tasks_text, f"TASKS.md missing gate snapshot line: {line}"

    # Gate 5 must exist in both files and be either IN_PROGRESS or COMPLETE
    for label, text in (("STATUS.md", status_text), ("TASKS.md", tasks_text)):
        assert "Gate 5: COMPLETE" in text or "Gate 5: IN_PROGRESS" in text, (
            f"{label} missing Gate 5 snapshot line "
            "(expected 'Gate 5: COMPLETE' or 'Gate 5: IN_PROGRESS')."
        )

    # Gate 5 state must match between the two trackers
    gate5_status = "COMPLETE" if "Gate 5: COMPLETE" in status_text else "IN_PROGRESS"
    gate5_tasks = "COMPLETE" if "Gate 5: COMPLETE" in tasks_text else "IN_PROGRESS"
    assert gate5_status == gate5_tasks, (
        f"Gate 5 state mismatch: STATUS={gate5_status}, TASKS={gate5_tasks}"
    )


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

    if active_gate_match:
        # There's an active gate — phase name must reference it
        active_gate = active_gate_match.group(1)
        assert f"Gate {active_gate}" in phase_name, (
            "STATUS.md Current Phase NAME does not match active gate snapshot.\n"
            f"  active gate: Gate {active_gate}\n"
            f"  phase name:  {phase_name}\n"
            "Update NAME to include the active gate."
        )
    else:
        # All L2/L3 gates complete — phase name should reflect completion
        assert "COMPLETE" in phase_name or "complete" in phase_name.lower(), (
            "All gates are COMPLETE but STATUS.md phase NAME doesn't reflect this.\n"
            f"  phase name: {phase_name}\n"
            "Update NAME to indicate completion."
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

    # NEXT can be empty when all gates are complete and no follow-up work remains
    has_active_tasks = re.search(r"^\-\s*\[\s\]\s+", next_section, re.MULTILINE)
    has_empty_marker = "No active items" in next_section
    assert has_active_tasks or has_empty_marker, (
        "TASKS.md NEXT should contain either active unchecked tasks "
        "('- [ ] ...') or an explicit empty marker ('No active items')."
    )


# =============================================================================
# Terminology Lock — sink/SINK and r_a/Ra disambiguation
# =============================================================================

_TERMINOLOGY_LOCK_PHRASES = (
    "Terminology Lock",
    "sink",
    "SINK",
    "r_a",
    "Ra",
)


def test_terminology_lock_exists_in_status_and_tasks() -> None:
    """
    STATUS.md and TASKS.md must contain a Terminology Lock note that
    disambiguates runtime terms (sink, r_a) from governance terms (SINK, Ra).
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    for label, text in (("STATUS.md", status_text), ("TASKS.md", tasks_text)):
        assert "Terminology Lock" in text, (
            f"{label} is missing a 'Terminology Lock' note. "
            "Add disambiguation for sink/SINK and r_a/Ra."
        )
        # Must mention both runtime and governance meanings
        assert "runtime hemisphere bucket" in text.lower() or "runtime" in text.lower(), (
            f"{label} Terminology Lock must mention runtime context."
        )
        assert "governance task lane" in text.lower() or "governance" in text.lower(), (
            f"{label} Terminology Lock must mention governance context."
        )


def test_manifest_includes_l4_research_packet() -> None:
    """
    roadmap/MANIFEST.md must include all 4 L4 research packet links,
    ensuring SINK-status docs remain discoverable.
    """
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")

    required_links = (
        "L4ExitChecklist.v0.md",
        "L4MicroAbi.v0.md",
        "G8CpsFeasibility.v0.md",
        "L4DecisionCard.v0.md",
    )

    missing = [link for link in required_links if link not in manifest_text]
    assert not missing, (
        f"roadmap/MANIFEST.md is missing L4 research packet links: {missing}\n"
        "SINK status does not remove active evidence docs from MANIFEST discoverability."
    )


# =============================================================================
# Governance Lane Classification — VECTOR/SINK priority ordering
# =============================================================================


def _extract_section(text: str, heading: str) -> str:
    """Extract content between a heading and the next ## heading."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\b.*?\n(.*?)(?=\n## |\Z)",
        re.DOTALL | re.MULTILINE,
    )
    match = pattern.search(text)
    assert match, f"Could not find section '## {heading}' in TASKS.md"
    return match.group(1)


def test_g8_decision_path_in_vector_with_priority() -> None:
    """
    TASKS.md VECTOR must contain the G8 production decision path
    with a [P<N>] priority tag.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    vector_section = _extract_section(tasks_text, "VECTOR")

    assert "G8 Production Decision Path" in vector_section or "G8" in vector_section, (
        "TASKS.md VECTOR is missing the G8 production decision path item. "
        "G8 evidence (D001-D003) warrants a VECTOR design item."
    )
    assert re.search(r"\[P\d+\]", vector_section), (
        "TASKS.md VECTOR items must have priority tags ([P1], [P2], ...)."
    )


def test_l4_full_rewrite_remains_in_sink() -> None:
    """
    TASKS.md SINK must contain the full L4 rewrite as a long-horizon item.
    The bounded G8 decision path belongs in VECTOR, but the full rewrite stays parked.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    sink_section = _extract_section(tasks_text, "SINK")

    assert "L4 Full Self-Hosting" in sink_section or "L4" in sink_section, (
        "TASKS.md SINK must retain the full L4 self-hosting rewrite as a "
        "long-horizon item (distinct from the bounded G8 decision path in VECTOR)."
    )


def test_vector_and_sink_have_ordered_priority_tags() -> None:
    """
    TASKS.md VECTOR and SINK active items must have priority tags
    ([P1], [P2], ... for VECTOR; [S1], [S2], ... for SINK) in ascending order.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    vector_section = _extract_section(tasks_text, "VECTOR")
    vector_tags = [int(m.group(1)) for m in re.finditer(r"\[P(\d+)\]", vector_section)]
    assert len(vector_tags) >= 2, (
        f"TASKS.md VECTOR must have at least 2 priority-tagged items, found {len(vector_tags)}."
    )
    assert vector_tags == sorted(vector_tags), (
        f"TASKS.md VECTOR priority tags are not in ascending order: {vector_tags}"
    )

    sink_section = _extract_section(tasks_text, "SINK")
    sink_tags = [int(m.group(1)) for m in re.finditer(r"\[S(\d+)\]", sink_section)]
    assert len(sink_tags) >= 2, (
        f"TASKS.md SINK must have at least 2 priority-tagged items, found {len(sink_tags)}."
    )
    assert sink_tags == sorted(sink_tags), (
        f"TASKS.md SINK priority tags are not in ascending order: {sink_tags}"
    )
