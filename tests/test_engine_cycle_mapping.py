"""
EngineNew 10-step cycle → runtime evidence mapping.

Maps the RCXEngineNew.pdf stall-fix-promote cycle to current runtime
artifacts. This is EVIDENCE MAPPING, not feature implementation.

Spec source: RCXEngineNew.pdf (10-step stall-fix-promote cycle)
Runtime doc: docs/core/RCXEngine.v0.md (Engine Cycle section)
Engine seed: mu/programs/rcx_engine.v1.json (7 projections)
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed


# ---------------------------------------------------------------------------
# Mapping table: 10 rows, one per EngineNew cycle step
# ---------------------------------------------------------------------------

class CycleStep(NamedTuple):
    step_id: int
    enginenew_label: str
    runtime_artifact: str
    evidence_type: str  # "structural" or "gap"
    evidence_note: str


CYCLE_MAPPING: tuple[CycleStep, ...] = (
    CycleStep(
        step_id=1,
        enginenew_label="Initialize G₀ / gate setup",
        runtime_artifact="engine.init, engine.init_config",
        evidence_type="structural",
        evidence_note=(
            "rcx_engine.v1.json projections engine.init and engine.init_config "
            "set up engine run and dispatch trace via _boundary_request. "
            "Gate flags = projection set loading per RCXEngineNew.pdf Section 0."
        ),
    ),
    CycleStep(
        step_id=2,
        enginenew_label="Apply operator O to G (structural trace)",
        runtime_artifact="_boundary_request operation=run_trace",
        evidence_type="structural",
        evidence_note=(
            "engine.init body emits _boundary_request with operation=run_trace. "
            "Host services request via run_structural_trace (step_mu.py). "
            "Boundary effect protocol is structural; host is generic dispatcher."
        ),
    ),
    CycleStep(
        step_id=3,
        enginenew_label="Stall check: Ξ(O(G)) = Ξ(G) (hash trace)",
        runtime_artifact="engine.trace_done → _boundary_request operation=hash_trace",
        evidence_type="structural",
        evidence_note=(
            "engine.trace_done projection requests hash_trace via _boundary_request. "
            "mu_hash is a host primitive but dispatch is structural. "
            "Maps to Rule 0.5 (stall predicate)."
        ),
    ),
    CycleStep(
        step_id=4,
        enginenew_label="Fix routine: apply Fix(G) (Rule 0.6)",
        runtime_artifact="—",
        evidence_type="gap",
        evidence_note=(
            "No Fix projection exists in any seed. Fix semantics (add minimal "
            "structural edge) are implicit in engine re-application. "
            "Rule 0.6 requires explicit structural Fix — not yet implemented."
        ),
    ),
    CycleStep(
        step_id=5,
        enginenew_label="Recurrence detection (Rule 2.2♢)",
        runtime_artifact="engine.hash_done → recurrence.v2.json via run_algorithm",
        evidence_type="structural",
        evidence_note=(
            "engine.hash_done dispatches recurrence.v2.json via _boundary_request "
            "operation=run_algorithm. Recurrence seed has 9 projections for "
            "hash-accelerated closure detection."
        ),
    ),
    CycleStep(
        step_id=6,
        enginenew_label="LeafInvariance: log trace token τ (Rule 0.7c')",
        runtime_artifact="recurrence.v2.json tau_step field",
        evidence_type="structural",
        evidence_note=(
            "recurrence.v2.json captures tau_step in closure result. "
            "Maps to Rule 0.7c' (LeafInvariance degeneracy test). "
            "tau_step flows through engine.recurrence_done to terminal result."
        ),
    ),
    CycleStep(
        step_id=7,
        enginenew_label="Closure projection Ω(τ) (Rule 2.2♢)",
        runtime_artifact="engine.recurrence_done",
        evidence_type="structural",
        evidence_note=(
            "engine.recurrence_done captures closure_detected and tau_step from "
            "recurrence result. Forwards to exhaustion detection via "
            "_boundary_request. Closure-on-Second-Demand per Rule 2.2♢."
        ),
    ),
    CycleStep(
        step_id=8,
        enginenew_label="Operator exhaustion: freeze and switch (Rule 3.1)",
        runtime_artifact="engine.recurrence_done → exhaustion.v1.json via run_algorithm",
        evidence_type="structural",
        evidence_note=(
            "engine.recurrence_done dispatches exhaustion.v1.json via "
            "_boundary_request operation=run_algorithm. Exhaustion seed has "
            "11 projections. Produces operator_frozen + frozen_set + action."
        ),
    ),
    CycleStep(
        step_id=9,
        enginenew_label="Terminal assembly (8-field engine_result)",
        runtime_artifact="engine.exhaustion_done, engine.unwrap",
        evidence_type="structural",
        evidence_note=(
            "engine.exhaustion_done assembles 8-field engine_result: "
            "value, closure_detected, tau_step, exhaustion_detected, "
            "operator_frozen, frozen_set, action, stall. "
            "engine.unwrap extracts the inner dict."
        ),
    ),
    CycleStep(
        step_id=10,
        enginenew_label="Iteration control (loop to step 2)",
        runtime_artifact="host run_engine_pipeline while loop",
        evidence_type="gap",
        evidence_note=(
            "Iteration is host-driven: run_engine_pipeline (Python step_mu.py / "
            "JS eval_step.js) runs a while loop dispatching _boundary_request "
            "effects. No structural loop projection exists. "
            "Iteration as projection requires recursive kernel (Boot1+)."
        ),
    ),
)


# ---------------------------------------------------------------------------
# Gap registry: canonical record of non-structural steps
# ---------------------------------------------------------------------------


class GapEntry(NamedTuple):
    step_id: int
    gap_id: str
    rationale: str
    owner: str  # VECTOR item or SINK
    unblock_condition: str
    contract_doc: str  # path to design contract doc, or "" if none yet
    invariants: tuple[str, ...]  # invariant IDs that must hold when gap is closed


GAP_REGISTRY: tuple[GapEntry, ...] = (
    GapEntry(
        step_id=4,
        gap_id="GAP-04-FIX",
        rationale=(
            "No Fix projection exists. Fix semantics (add minimal structural "
            "edge per Rule 0.6) are implicit in engine re-application. An "
            "explicit Fix projection requires structural seed design + "
            "evidence that implicit fix is insufficient."
        ),
        owner="VECTOR",
        unblock_condition=(
            "Requires all 5 evidence items from EngineNewFixContract.v0.md: "
            "(E1) stall-recovery failure test, (E2) fix.v1.json seed draft, "
            "(E3) invariant test suite for I1-I5, (E4) engine integration "
            "sketch, (E5) VECTOR → NEXT promotion with rationale."
        ),
        contract_doc="docs/core/EngineNewFixContract.v0.md",
        invariants=(
            "I1:minimality",
            "I2:structural_purity",
            "I3:idempotence_safety",
            "I4:stall_breaking",
            "I5:no_semantic_drift",
        ),
    ),
    GapEntry(
        step_id=10,
        gap_id="GAP-10-LOOP",
        rationale=(
            "Iteration is host-driven: run_engine_pipeline runs a while "
            "loop dispatching _boundary_request effects. No structural loop "
            "projection exists. Structural iteration requires a recursive "
            "kernel that can re-enter itself (Boot1+ capability)."
        ),
        owner="VECTOR",
        unblock_condition=(
            "Implement recursive kernel capable of self-re-entry. Requires: "
            "(1) Boot1 recursive kernel design, (2) loop-as-projection seed "
            "draft, (3) evidence that host loop can be replaced without "
            "breaking engine_result contract, (4) VECTOR → NEXT promotion."
        ),
        contract_doc="",  # no contract doc yet — design not started
        invariants=(),
    ),
)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEngineCycleMapping:
    """Evidence mapping for EngineNew 10-step stall-fix-promote cycle."""

    def test_mapping_has_10_steps(self):
        """Exactly 10 steps in the cycle mapping."""
        assert len(CYCLE_MAPPING) == 10

    def test_step_ids_are_sequential(self):
        """Step IDs run 1..10 with no gaps."""
        ids = [s.step_id for s in CYCLE_MAPPING]
        assert ids == list(range(1, 11))

    def test_structural_evidence_count_at_least_6(self):
        """At least 6 of 10 steps have structural projection evidence."""
        structural = [s for s in CYCLE_MAPPING if s.evidence_type == "structural"]
        gap = [s for s in CYCLE_MAPPING if s.evidence_type == "gap"]
        assert len(structural) >= 6, (
            f"Only {len(structural)}/10 steps have structural evidence "
            f"(need ≥6). Gaps: {[s.step_id for s in gap]}"
        )

    def test_all_evidence_types_valid(self):
        """Every step has evidence_type of 'structural' or 'gap'."""
        for step in CYCLE_MAPPING:
            assert step.evidence_type in ("structural", "gap"), (
                f"Step {step.step_id} has invalid evidence_type: "
                f"{step.evidence_type!r}"
            )

    def test_gap_steps_are_explicitly_marked(self):
        """Every gap step has a non-trivial evidence_note explaining what's missing."""
        gaps = [s for s in CYCLE_MAPPING if s.evidence_type == "gap"]
        assert len(gaps) > 0, "No gaps found — suspicious; verify honesty"
        for step in gaps:
            assert len(step.evidence_note) >= 20, (
                f"Gap step {step.step_id} ({step.enginenew_label!r}) "
                f"has insufficient explanation: {step.evidence_note!r}"
            )
            assert step.runtime_artifact != "", (
                f"Gap step {step.step_id} must have a runtime_artifact "
                f"(even if '—' to mark absence)"
            )

    def test_no_silent_omissions(self):
        """Every step has non-empty fields — no hidden blanks."""
        for step in CYCLE_MAPPING:
            assert step.enginenew_label, f"Step {step.step_id}: empty label"
            assert step.runtime_artifact, f"Step {step.step_id}: empty artifact"
            assert step.evidence_type, f"Step {step.step_id}: empty evidence_type"
            assert step.evidence_note, f"Step {step.step_id}: empty note"

    def test_required_engine_projections_present(self):
        """rcx_engine.v1.json contains all required projection IDs."""
        seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
        ids = {p["id"] for p in seed["projections"]}

        required = {
            "engine.init",
            "engine.trace_done",
            "engine.hash_done",
            "engine.recurrence_done",
            "engine.exhaustion_done",
            "engine.unwrap",
        }
        missing = required - ids
        assert not missing, f"Missing engine projections: {missing}"

    def test_engine_terminal_shape_contract(self):
        """engine.exhaustion_done produces the 8-field terminal shape."""
        seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
        exhaust_done = next(
            p for p in seed["projections"]
            if p["id"] == "engine.exhaustion_done"
        )
        # The body should contain engine_result with exactly 8 keys
        body = exhaust_done["body"]
        assert "engine_result" in body, "exhaustion_done must produce engine_result"
        result_shape = body["engine_result"]

        expected_keys = {
            "value", "closure_detected", "tau_step", "exhaustion_detected",
            "operator_frozen", "frozen_set", "action", "stall",
        }
        actual_keys = set(result_shape.keys())
        assert actual_keys == expected_keys, (
            f"Terminal shape mismatch.\n"
            f"  Expected: {sorted(expected_keys)}\n"
            f"  Actual:   {sorted(actual_keys)}\n"
            f"  Missing:  {sorted(expected_keys - actual_keys)}\n"
            f"  Extra:    {sorted(actual_keys - expected_keys)}"
        )

    def test_boundary_request_protocol_in_engine_projections(self):
        """Engine projections use _boundary_request for inter-step dispatch."""
        seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
        boundary_users = [
            p["id"] for p in seed["projections"]
            if "_boundary_request" in str(p.get("body", {}))
        ]
        # init, init_config, trace_done, hash_done, recurrence_done all use boundary
        assert len(boundary_users) >= 5, (
            f"Expected ≥5 projections using _boundary_request, "
            f"got {len(boundary_users)}: {boundary_users}"
        )

    def test_no_false_implementation_claims(self):
        """Mapping does not claim metabolization, Xi/fold network, or RTM is implemented."""
        forbidden_claims = ["metaboliz", "xi_fold", "fold_network", "rtm.v1"]
        for step in CYCLE_MAPPING:
            combined = (
                step.runtime_artifact.lower()
                + step.evidence_note.lower()
            )
            for claim in forbidden_claims:
                assert claim not in combined, (
                    f"Step {step.step_id} falsely references "
                    f"{claim!r}: {step.evidence_note[:100]}"
                )


class TestGapRegistry:
    """Lock EngineNew gaps as intentional contracts with promotion criteria."""

    def test_gap_count_matches_mapping(self):
        """GAP_REGISTRY count must equal gap steps in CYCLE_MAPPING."""
        mapping_gaps = [s for s in CYCLE_MAPPING if s.evidence_type == "gap"]
        assert len(GAP_REGISTRY) == len(mapping_gaps), (
            f"GAP_REGISTRY has {len(GAP_REGISTRY)} entries but "
            f"CYCLE_MAPPING has {len(mapping_gaps)} gap steps. "
            f"Registry step_ids: {[g.step_id for g in GAP_REGISTRY]}, "
            f"Mapping gap step_ids: {[s.step_id for s in mapping_gaps]}"
        )

    def test_gap_step_ids_match_mapping(self):
        """GAP_REGISTRY step_ids must exactly match gap steps in CYCLE_MAPPING."""
        mapping_gap_ids = {s.step_id for s in CYCLE_MAPPING if s.evidence_type == "gap"}
        registry_ids = {g.step_id for g in GAP_REGISTRY}
        assert registry_ids == mapping_gap_ids, (
            f"Step ID mismatch: registry={sorted(registry_ids)}, "
            f"mapping gaps={sorted(mapping_gap_ids)}"
        )

    def test_each_gap_has_required_fields(self):
        """Every gap entry has non-trivial rationale, owner, and unblock condition."""
        for gap in GAP_REGISTRY:
            assert len(gap.rationale) >= 30, (
                f"{gap.gap_id}: rationale too short ({len(gap.rationale)} chars)"
            )
            assert gap.owner in ("VECTOR", "SINK", "NEXT"), (
                f"{gap.gap_id}: owner must be VECTOR/SINK/NEXT, got {gap.owner!r}"
            )
            assert len(gap.unblock_condition) >= 30, (
                f"{gap.gap_id}: unblock_condition too short ({len(gap.unblock_condition)} chars)"
            )

    def test_gap_ids_are_unique(self):
        """No duplicate gap IDs."""
        ids = [g.gap_id for g in GAP_REGISTRY]
        assert len(ids) == len(set(ids)), f"Duplicate gap IDs: {ids}"

    def test_no_gap_flipped_without_evidence(self):
        """A step cannot be structural in CYCLE_MAPPING while still in GAP_REGISTRY.

        If a gap is resolved, the GAP_REGISTRY entry must be removed first.
        This prevents silent gap→structural flips without explicit promotion.
        """
        structural_ids = {s.step_id for s in CYCLE_MAPPING if s.evidence_type == "structural"}
        for gap in GAP_REGISTRY:
            assert gap.step_id not in structural_ids, (
                f"{gap.gap_id} (step {gap.step_id}) is in GAP_REGISTRY but "
                f"CYCLE_MAPPING marks it as 'structural'. Remove the gap entry "
                f"only after evidence is provided and VECTOR → NEXT promotion."
            )

    def test_structural_gap_tally(self):
        """Print and assert the current structural/gap tally."""
        structural = [s for s in CYCLE_MAPPING if s.evidence_type == "structural"]
        gaps = [s for s in CYCLE_MAPPING if s.evidence_type == "gap"]
        assert len(structural) + len(gaps) == 10
        assert len(structural) == 8, f"Expected 8 structural, got {len(structural)}"
        assert len(gaps) == 2, f"Expected 2 gaps, got {len(gaps)}"


class TestGapContractDocs:
    """Verify gap entries with contract docs have complete design contracts."""

    ROOT = Path(__file__).parent.parent

    def test_gap04_fix_has_contract_doc(self):
        """GAP-04-FIX must reference a contract doc that exists on disk."""
        gap = next(g for g in GAP_REGISTRY if g.gap_id == "GAP-04-FIX")
        assert gap.contract_doc, "GAP-04-FIX must have a contract_doc path"
        doc_path = self.ROOT / gap.contract_doc
        assert doc_path.exists(), (
            f"Contract doc not found: {gap.contract_doc}"
        )

    def test_gap04_fix_has_invariants(self):
        """GAP-04-FIX must declare at least 3 invariants."""
        gap = next(g for g in GAP_REGISTRY if g.gap_id == "GAP-04-FIX")
        assert len(gap.invariants) >= 3, (
            f"GAP-04-FIX has {len(gap.invariants)} invariants, need ≥3"
        )

    def test_gap04_fix_invariants_in_contract_doc(self):
        """Every invariant ID declared in GAP-04-FIX must appear in the contract doc."""
        gap = next(g for g in GAP_REGISTRY if g.gap_id == "GAP-04-FIX")
        doc_path = self.ROOT / gap.contract_doc
        doc_text = doc_path.read_text()
        for inv in gap.invariants:
            # Invariant format is "I1:minimality" — check the label part
            label = inv.split(":")[0]  # e.g., "I1"
            assert label in doc_text, (
                f"Invariant {inv} (label {label}) not found in {gap.contract_doc}"
            )

    def test_gap04_fix_unblock_references_evidence(self):
        """GAP-04-FIX unblock_condition must reference evidence items from contract doc."""
        gap = next(g for g in GAP_REGISTRY if g.gap_id == "GAP-04-FIX")
        for evidence_id in ("E1", "E2", "E3", "E4", "E5"):
            assert evidence_id in gap.unblock_condition, (
                f"GAP-04-FIX unblock_condition missing evidence reference {evidence_id}"
            )

    def test_contract_doc_has_doc_status_header(self):
        """Contract docs must have a DOC_STATUS header for governance compliance."""
        gap = next(g for g in GAP_REGISTRY if g.gap_id == "GAP-04-FIX")
        doc_path = self.ROOT / gap.contract_doc
        doc_text = doc_path.read_text()
        assert "DOC_STATUS" in doc_text, (
            f"{gap.contract_doc} missing DOC_STATUS header"
        )
        assert "DESIGN_SPEC" in doc_text, (
            f"{gap.contract_doc} should be TYPE: DESIGN_SPEC"
        )

    def test_gaps_without_contract_doc_have_empty_invariants(self):
        """Gaps with no contract doc should have empty invariants (nothing to check yet)."""
        for gap in GAP_REGISTRY:
            if not gap.contract_doc:
                assert len(gap.invariants) == 0, (
                    f"{gap.gap_id} has no contract_doc but declares invariants: "
                    f"{gap.invariants}. Add a contract doc first."
                )
