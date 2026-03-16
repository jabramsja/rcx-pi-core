"""
Cross-doc consistency checks for root canonical trackers.

This module enforces semantic agreement between STATUS.md and TASKS.md for
high-risk execution-layer claims that can otherwise drift silently.
"""

from __future__ import annotations

from pathlib import Path
import re


from tests.repo_root import REPO_ROOT
STATUS_PATH = REPO_ROOT / "STATUS.md"
TASKS_PATH = REPO_ROOT / "TASKS.md"
MANIFEST_PATH = REPO_ROOT / "roadmap" / "MANIFEST.md"

LAYER_TOKENS = ("BOOTSTRAP", "META_CIRCULAR")

# Shared regex for extracting NEXT section from TASKS.md (used by multiple tests)
_NEXT_SECTION_RE = re.compile(
    r"## NEXT \(short, bounded follow-ups\)\n(.*?)\n## VECTOR ",
    re.DOTALL,
)


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
    next_match = _NEXT_SECTION_RE.search(tasks_text)
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
    has_promoted_tasks = re.search(r"^\-\s*\*\*\w+", next_section, re.MULTILINE)
    has_completed_tasks = re.search(r"^\-\s*~~\*\*\w+", next_section, re.MULTILINE)
    has_empty_marker = "No active items" in next_section
    assert has_active_tasks or has_promoted_tasks or has_completed_tasks or has_empty_marker, (
        "TASKS.md NEXT should contain active tasks "
        "('- [ ] ...' or '- **Name**'), completed tasks ('- ~~**Name**~~'), "
        "or an explicit empty marker ('No active items')."
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


L4_DECISION_CARD_PATH = REPO_ROOT / "mu" / "docs" / "core" / "L4DecisionCard.v0.md"
G8_FEASIBILITY_PATH = REPO_ROOT / "mu" / "docs" / "core" / "G8CpsFeasibility.v0.md"
L4_EXIT_CHECKLIST_PATH = REPO_ROOT / "mu" / "docs" / "core" / "L4ExitChecklist.v0.md"


def test_d008_decision_packet_exists_in_decision_card() -> None:
    """
    L4DecisionCard.v0.md must contain D008 with target_gate_id G8
    and an explicit decision outcome line.
    """
    text = L4_DECISION_CARD_PATH.read_text(encoding="utf-8")
    assert "Decision ID: D008" in text, (
        "L4DecisionCard.v0.md is missing D008 decision card."
    )
    assert "target_gate_id: G8" in text.split("Decision ID: D008")[1], (
        "D008 must target G8."
    )


def test_g8_feasibility_has_evidence_closure() -> None:
    """
    G8CpsFeasibility.v0.md must contain an Evidence Closure section
    with boundary statements (what is proven / what is not).
    """
    text = G8_FEASIBILITY_PATH.read_text(encoding="utf-8")
    assert "Evidence Closure" in text, (
        "G8CpsFeasibility.v0.md is missing 'Evidence Closure' section."
    )
    assert "What this proves" in text or "PROVES" in text, (
        "Evidence Closure must state what IS proven."
    )
    assert "What this does NOT prove" in text or "DOES NOT PROVE" in text, (
        "Evidence Closure must state what is NOT proven."
    )


def test_l4_exit_checklist_g8_references_d008() -> None:
    """
    L4ExitChecklist.v0.md G8 section must reference D008 decision packet
    and reflect G8 PASS (classification gate, caveated).
    """
    text = L4_EXIT_CHECKLIST_PATH.read_text(encoding="utf-8")
    # Find the G8 section
    g8_idx = text.find("### L4-G8")
    assert g8_idx != -1, "L4ExitChecklist.v0.md missing G8 section."
    g8_section = text[g8_idx:]
    assert "D008" in g8_section, (
        "L4ExitChecklist.v0.md G8 section must reference D008 decision packet."
    )
    assert "G8 PASS" in g8_section, (
        "G8 must reflect PASS (classification gate, caveated) verdict."
    )
    # G8 PASS does NOT imply L4 completion
    assert "not L4 completion" in g8_section, (
        "G8 section must explicitly state G8 PASS does not imply L4 completion."
    )


def test_heartbeat_tracker_wave7_done_wave8_d008() -> None:
    """
    TASKS.md heartbeat tracker must show wave7 DONE (D007) and
    wave8 with D008 decision packet.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    sink_section = _extract_section(tasks_text, "SINK")
    assert "wave7" in sink_section and "DONE" in sink_section, (
        "TASKS.md heartbeat tracker must show wave7 as DONE."
    )
    assert "wave8" in sink_section and "D008" in sink_section, (
        "TASKS.md heartbeat tracker wave8 must reference D008."
    )


def test_hypothesis_matrix_complete_across_docs() -> None:
    """
    G8CpsFeasibility.v0.md and L4DecisionCard.v0.md must both reflect
    the complete hypothesis matrix: H1 PARTIALLY, H2 ALL MET, H3 FALSIFIED.
    """
    g8_text = G8_FEASIBILITY_PATH.read_text(encoding="utf-8")
    dc_text = L4_DECISION_CARD_PATH.read_text(encoding="utf-8")

    for label, text in (("G8CpsFeasibility", g8_text), ("L4DecisionCard", dc_text)):
        assert "PARTIALLY CONFIRMED" in text, (
            f"{label} must reference H1 PARTIALLY CONFIRMED."
        )
        assert "ALL 4 CRITERIA MET" in text, (
            f"{label} must reference H2 ALL 4 CRITERIA MET."
        )
        assert "FALSIFIED" in text, (
            f"{label} must reference H3 FALSIFIED."
        )


def test_post_d008_operating_mode_in_status_and_tasks() -> None:
    """
    STATUS.md and TASKS.md must both contain a Post-D008 Operating Mode note
    stating Boot1/NEXT primacy while preserving L4 heartbeat continuity.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    for label, text in (("STATUS.md", status_text), ("TASKS.md", tasks_text)):
        assert "Post-D008 Operating Mode" in text, (
            f"{label} is missing 'Post-D008 Operating Mode' note."
        )
        assert "Boot1" in text and "NEXT" in text, (
            f"{label} Post-D008 note must reference Boot1 as NEXT primary lane."
        )
        assert "DEFER" in text, (
            f"{label} Post-D008 note must reference D008 DEFER outcome."
        )


def test_l4_heartbeat_not_removed() -> None:
    """
    TASKS.md must retain the L4 Heartbeat Tracker even after D008 DEFER.
    L4 is deferred, not abandoned.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    assert "L4 Heartbeat Tracker" in tasks_text, (
        "TASKS.md must retain 'L4 Heartbeat Tracker' section. "
        "D008 DEFER means deferred, not abandoned."
    )
    assert "wave6" in tasks_text and "wave7" in tasks_text and "wave8" in tasks_text, (
        "TASKS.md heartbeat tracker must retain all 3 waves (6-8)."
    )


# =============================================================================
# Hemisphere Metabolization — promotion and execution checklist consistency
# =============================================================================

HEMISPHERE_CHECKLIST_PATH = REPO_ROOT / "mu" / "docs" / "core" / "HemisphereExecutionChecklist.v0.md"


def test_hemisphere_promoted_to_next() -> None:
    """
    TASKS.md NEXT must contain Hemisphere Metabolization Contract
    with an explicit PROMOTED FROM VECTOR note.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    next_match = _NEXT_SECTION_RE.search(tasks_text)
    assert next_match, "Could not isolate TASKS.md NEXT section."
    next_section = next_match.group(1)

    assert "Hemisphere Metabolization Contract" in next_section, (
        "TASKS.md NEXT must contain 'Hemisphere Metabolization Contract'."
    )
    assert "PROMOTED FROM VECTOR" in next_section, (
        "Hemisphere NEXT entry must include 'PROMOTED FROM VECTOR' rationale."
    )


def test_hemisphere_removed_from_vector_active() -> None:
    """
    TASKS.md VECTOR active designs must NOT have Hemisphere as a [P<N>] item.
    It should appear only in the 'Promoted to NEXT' subsection.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    vector_section = _extract_section(tasks_text, "VECTOR")

    # Split at "Promoted to NEXT" to get only active designs
    active_part = vector_section.split("Promoted to NEXT")[0] if "Promoted to NEXT" in vector_section else vector_section

    # Should not have Hemisphere as an active [P<N>] item
    assert not re.search(r"\[P\d+\].*Hemisphere Metabolization", active_part), (
        "Hemisphere Metabolization should not be an active VECTOR [P<N>] item "
        "after promotion to NEXT."
    )


def test_hemisphere_in_vector_promoted_subsection() -> None:
    """
    TASKS.md VECTOR 'Promoted to NEXT' must list Hemisphere Metabolization.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    vector_section = _extract_section(tasks_text, "VECTOR")

    assert "Promoted to NEXT" in vector_section, (
        "TASKS.md VECTOR must have a 'Promoted to NEXT' subsection."
    )
    promoted_idx = vector_section.index("Promoted to NEXT")
    promoted_section = vector_section[promoted_idx:]

    assert "Hemisphere Metabolization" in promoted_section, (
        "VECTOR 'Promoted to NEXT' must list Hemisphere Metabolization."
    )


def test_hemisphere_execution_checklist_exists() -> None:
    """
    mu/docs/core/HemisphereExecutionChecklist.v0.md must exist
    with E1-E5 evidence gates.
    """
    assert HEMISPHERE_CHECKLIST_PATH.exists(), (
        f"Hemisphere execution checklist not found at {HEMISPHERE_CHECKLIST_PATH}"
    )
    text = HEMISPHERE_CHECKLIST_PATH.read_text(encoding="utf-8")

    for gate in ("E1:", "E2:", "E3:", "E4:", "E5:"):
        assert gate in text, (
            f"HemisphereExecutionChecklist.v0.md missing evidence gate {gate}"
        )


def test_hemisphere_checklist_referenced_in_manifest() -> None:
    """
    roadmap/MANIFEST.md must reference HemisphereExecutionChecklist.v0.md
    for discoverability.
    """
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")
    assert "HemisphereExecutionChecklist.v0.md" in manifest_text, (
        "roadmap/MANIFEST.md must reference HemisphereExecutionChecklist.v0.md "
        "for hemisphere execution gate discoverability."
    )


def test_status_next_milestone_reflects_hemisphere() -> None:
    """
    STATUS.md 'Next milestone' line must reference Hemisphere Metabolization
    (not stale Boot1 reference).
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    assert "Hemisphere Metabolization" in status_text, (
        "STATUS.md must reference Hemisphere Metabolization as the active milestone."
    )
    # Should not still point to Boot1 as the *next* milestone
    milestone_match = re.search(r"\*\*Next milestone:\*\*(.+)", status_text)
    assert milestone_match, "STATUS.md must have a 'Next milestone' line."
    milestone_line = milestone_match.group(1)
    assert "Hemisphere" in milestone_line, (
        f"STATUS.md 'Next milestone' should reference Hemisphere, "
        f"got: {milestone_line.strip()}"
    )


# ── E5 Governance Closure Locks ──────────────────────────────────────────────


def test_hemisphere_e5_tasks_marked_complete() -> None:
    """TASKS.md NEXT must mark Hemisphere Metabolization Contract as COMPLETE."""
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    next_match = _NEXT_SECTION_RE.search(tasks_text)
    assert next_match, "Could not isolate TASKS.md NEXT section."
    next_section = next_match.group(1)
    assert "COMPLETE" in next_section, (
        "TASKS.md NEXT Hemisphere entry must be marked COMPLETE."
    )
    assert "E1-E5" in next_section, (
        "TASKS.md NEXT Hemisphere COMPLETE entry must reference E1-E5 evidence."
    )


def test_hemisphere_e5_checklist_all_gates_met() -> None:
    """HemisphereExecutionChecklist.v0.md must show all 5 gates MET."""
    text = HEMISPHERE_CHECKLIST_PATH.read_text(encoding="utf-8")
    for gate in ("E1 MET", "E2 MET", "E3 MET", "E4 MET", "E5 MET"):
        assert gate in text, (
            f"HemisphereExecutionChecklist.v0.md must contain '{gate}' "
            f"for E5 governance closure."
        )


def test_hemisphere_e5_checklist_last_verified_current() -> None:
    """HemisphereExecutionChecklist.v0.md LAST_VERIFIED must be 2026-02-20."""
    text = HEMISPHERE_CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "LAST_VERIFIED: 2026-02-20" in text, (
        "HemisphereExecutionChecklist.v0.md LAST_VERIFIED must be updated to 2026-02-20."
    )


def test_hemisphere_e5_boot1_cross_reference() -> None:
    """HemisphereExecutionChecklist must cross-reference Boot1LoopContract."""
    text = HEMISPHERE_CHECKLIST_PATH.read_text(encoding="utf-8")
    assert "Boot1LoopContract.v0.md" in text, (
        "HemisphereExecutionChecklist.v0.md must cross-reference Boot1LoopContract.v0.md."
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


# =============================================================================
# Conjecture Parking — fail-closed governance guard
# =============================================================================


def test_conjecture_parking_exists_in_sink() -> None:
    """
    TASKS.md SINK must contain a 'Conjecture Parking (NOT ACTIVE)' subsection
    to prevent uncontrolled expansion of speculative hypotheses.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    sink_section = _extract_section(tasks_text, "SINK")
    assert "Conjecture Parking (NOT ACTIVE)" in sink_section, (
        "TASKS.md SINK must contain 'Conjecture Parking (NOT ACTIVE)' subsection."
    )


def test_conjecture_parking_parked_in_both_trackers() -> None:
    """
    STATUS.md and TASKS.md must both reflect conjecture as parked/not-active.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    assert "PARKED" in status_text and "conjecture" in status_text.lower(), (
        "STATUS.md must reflect conjecture parking as PARKED."
    )
    assert "PARKED" in tasks_text and "conjecture" in tasks_text.lower(), (
        "TASKS.md must reflect conjecture parking as PARKED."
    )


def test_conjecture_parking_has_founder_trigger() -> None:
    """
    Conjecture parking must require explicit founder GO + gate mapping
    before any re-evaluation.
    """
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")
    sink_section = _extract_section(tasks_text, "SINK")

    assert "founder GO" in sink_section or "founder go" in sink_section.lower(), (
        "Conjecture parking re-evaluation trigger must require 'founder GO'."
    )
    assert "gate" in sink_section.lower(), (
        "Conjecture parking promotion rule must reference gate mapping."
    )


# =============================================================================
# L3 Truth Statement Lock
# =============================================================================


def test_l3_truth_statement_in_status() -> None:
    """
    STATUS.md must contain the canonical L3 truth statement with the
    precision phrase 'evaluation rules are structural data'.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    assert "evaluation rules are structural data" in status_text, (
        "STATUS.md missing canonical L3 truth statement. Required phrase: "
        "'The evaluation rules are structural data, but execution iteration, "
        "resource bounding, and API normalization remain irreducible host-language mechanics.'"
    )


def test_l3_truth_statement_not_overclaimed() -> None:
    """
    STATUS.md must NOT claim 'pure structural execution' — the host
    iteration/clock/normalization layer is irreducible.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    assert "pure structural execution" not in status_text.lower(), (
        "STATUS.md contains 'pure structural execution' — overclaim. "
        "Use 'structural projections with host execution substrate'."
    )


# =============================================================================
# Prompt Contract Lock — Codex→Claude prompt quality governance
# =============================================================================

CLAUDE_MD_PATH = REPO_ROOT / "CLAUDE.md"


def test_claude_md_has_prompt_contract_section() -> None:
    """
    CLAUDE.md must contain a 'Codex→Claude Prompt Contract' section
    that locks prompt quality for multi-wave sessions.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "Codex→Claude Prompt Contract" in text, (
        "CLAUDE.md missing 'Codex→Claude Prompt Contract' section."
    )


def test_prompt_contract_has_required_fields() -> None:
    """
    The prompt contract must specify all 7 required fields.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    required_fields = (
        "Preflight gate",
        "Primary uncertainty",
        "Allowed/forbidden scope",
        "Evidence delta",
        "Stop conditions",
        "Validation gates",
        "Push/merge block",
    )
    missing = [f for f in required_fields if f not in text]
    assert not missing, (
        f"CLAUDE.md prompt contract missing required fields: {missing}"
    )


def test_prompt_contract_has_governance_ratio_cap() -> None:
    """
    The prompt contract must enforce a governance-wave ratio cap
    to prevent unbounded governance-only waves.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "Governance ratio cap" in text or "governance ratio cap" in text.lower(), (
        "CLAUDE.md prompt contract missing governance ratio cap rule."
    )
    # Must reference the specific limit
    assert "1 governance/docs-only wave" in text or "1 governance" in text.lower(), (
        "Governance ratio cap must specify the max consecutive governance waves."
    )


# =============================================================================
# Primitive vs Debt Count Precision Lock
# =============================================================================


def test_status_distinguishes_primitives_from_debt_sites() -> None:
    """
    STATUS.md must not conflate '4 bootstrap primitives' with
    '12 host-debt decorator sites'. These are distinct concepts.
    """
    status_text = STATUS_PATH.read_text(encoding="utf-8")
    # Must NOT say "12 semantic bootstrap primitives" or "12 bootstrap primitives"
    assert "12 semantic bootstrap primitives" not in status_text, (
        "STATUS.md conflates debt count (12) with primitive count (4). "
        "There are 4 bootstrap primitives and 12 host-debt sites."
    )
    assert "12 bootstrap primitives" not in status_text, (
        "STATUS.md conflates debt count (12) with primitive count (4)."
    )
    # Must contain the correct distinction
    assert "4 bootstrap primitives" in status_text, (
        "STATUS.md must explicitly state '4 bootstrap primitives'."
    )


# =============================================================================
# L4 Execution Contract — CLAUDE.md phrase locks
# =============================================================================


def test_claude_md_has_l4_execution_contract_section() -> None:
    """
    CLAUDE.md must contain the L4 Execution Contract (Hard Gate) section
    that enforces wave classification.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "L4 Execution Contract (Hard Gate)" in text, (
        "CLAUDE.md missing 'L4 Execution Contract (Hard Gate)' section."
    )


def test_claude_md_l4_contract_references_canonical_doc() -> None:
    """
    CLAUDE.md L4 contract section must reference the canonical policy doc (v2).
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "L4ExecutionContract.v2.md" in text, (
        "CLAUDE.md L4 contract section must reference L4ExecutionContract.v2.md."
    )


def test_claude_md_l4_contract_references_enforcement_checker() -> None:
    """
    CLAUDE.md L4 contract section must reference the enforcement checker.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "enforce_l4_execution_contract.py" in text, (
        "CLAUDE.md L4 contract section must reference enforce_l4_execution_contract.py."
    )


def test_claude_md_l4_contract_has_all_three_wave_classes() -> None:
    """
    CLAUDE.md must document all 3 v2 wave classes: L4_STRUCTURAL, L4_ENABLER, MAINTENANCE.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "L4_STRUCTURAL" in text, (
        "CLAUDE.md must document L4_STRUCTURAL wave class."
    )
    assert "L4_ENABLER" in text, (
        "CLAUDE.md must document L4_ENABLER wave class."
    )
    assert "MAINTENANCE" in text, (
        "CLAUDE.md must document MAINTENANCE wave class."
    )


def test_status_md_references_l4_execution_contract() -> None:
    """
    STATUS.md must contain a pointer to L4ExecutionContract.v2.md.
    """
    text = STATUS_PATH.read_text(encoding="utf-8")
    assert "L4ExecutionContract.v2.md" in text, (
        "STATUS.md must reference L4ExecutionContract.v2.md."
    )


def test_claude_md_preflight_read_list_includes_manifest() -> None:
    """
    CLAUDE.md preflight read list must include roadmap/MANIFEST.md.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "roadmap/MANIFEST.md" in text, (
        "CLAUDE.md preflight read list must include roadmap/MANIFEST.md."
    )


def test_claude_md_preflight_read_list_includes_roadmap() -> None:
    """
    CLAUDE.md preflight read list must include ROADMAP.md.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "ROADMAP.md" in text, (
        "CLAUDE.md preflight read list must include ROADMAP.md."
    )


def test_claude_md_references_codex_audit_contract() -> None:
    """
    CLAUDE.md must reference the Codex→Claude Prompt Contract.
    """
    text = CLAUDE_MD_PATH.read_text(encoding="utf-8")
    assert "Codex→Claude Prompt Contract" in text, (
        "CLAUDE.md must reference 'Codex→Claude Prompt Contract'."
    )


def test_deferred_blocker_count_matches_prose() -> None:
    """If no deferred blockers exist, STATUS.md must not imply active blockers remain."""
    blocking_dir = REPO_ROOT / "reports" / "deferred" / "blocking"
    if not blocking_dir.exists():
        return

    blocker_files = [
        f for f in blocking_dir.iterdir()
        if f.is_file() and f.name != "README.md"
    ]

    if len(blocker_files) == 0:
        status = STATUS_PATH.read_text(encoding="utf-8")
        assert "active blocker" not in status.lower(), (
            "STATUS.md mentions 'active blocker' but reports/deferred/blocking/ "
            "contains no blocker files (only README.md)."
        )


def test_tasks_next_completed_item_count() -> None:
    """NEXT must not accumulate too many completed items without a historical disclaimer."""
    tasks = TASKS_PATH.read_text(encoding="utf-8")
    next_match = _NEXT_SECTION_RE.search(tasks)
    if not next_match:
        return

    next_section = next_match.group(1)

    # Count struck-through items (completed)
    completed = re.findall(r"^\-\s*~~\*\*", next_section, re.MULTILINE)

    if len(completed) > 3:
        # Must have a historical disclaimer if >3 completed items
        has_disclaimer = (
            "historical" in next_section.lower()
            or "no active" in next_section.lower()
            or "NOT active authorization" in next_section
        )
        assert has_disclaimer, (
            f"TASKS.md NEXT has {len(completed)} completed (struck-through) items "
            f"but no historical disclaimer. Add 'No active NEXT items' or similar."
        )
