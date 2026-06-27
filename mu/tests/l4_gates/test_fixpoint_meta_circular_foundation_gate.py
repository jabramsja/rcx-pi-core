"""Foundation gate for the bounded FixpointMetaCircularEvaluator v0 spec.

This test intentionally does not execute production evaluator, fixed-point, or
self-application semantics. It locks the first falsifiable docs criteria from
the fixpoint-meta-circular-evaluator-as-structure wave: the spec is
discoverable, bounded, structural-data-first, explicit about evaluator-as-data
and proof-limit obligations, and explicit about non-claims.
"""

from __future__ import annotations

import json

from tests.repo_root import REPO_ROOT


WAVE_ID = "fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-payoff"
SPEC_PATH = REPO_ROOT / "mu" / "docs" / "core" / "FixpointMetaCircularEvaluator.v0.md"
TEST_PATH = "mu/tests/l4_gates/test_fixpoint_meta_circular_foundation_gate.py"
DOCS_TEST_PATH = "mu/tests/docs/test_fixpoint_meta_circular_foundation_gate.py"
PACKET_REF = (
    "reports/control_plane/"
    "fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-payoff_2026-06-27.md"
)
PACKET_PATH = REPO_ROOT / PACKET_REF
BRIDGE_PACKET_REF = (
    "reports/control_plane/"
    "fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-pa_2026-06-27.md"
)
BRIDGE_PACKET_PATH = REPO_ROOT / BRIDGE_PACKET_REF
INDICATOR_REF = (
    "reports/l4_wave_indicators/"
    "fixpoint-meta-circular-evaluator-as-structure-the-meta-circularity-payoff.json"
)
INDICATOR_PATH = REPO_ROOT / INDICATOR_REF
TASKS_PATH = REPO_ROOT / "TASKS.md"
ACCEPTED_PACKET_STATUSES = (
    "Status: Phase B (pre-supervisor pending, bridge-converged)",
    "Status: IMPLEMENTED - PIPELINE REPAIR PENDING COMMIT",
    # Commit executor restores retry-pending packets to commit-ready before
    # pre-commit supervisor validation, then demotes them again on failure.
    "Status: IMPLEMENTED / LOCAL EVIDENCE",
)


def _spec_text() -> str:
    assert SPEC_PATH.exists(), (
        "FixpointMetaCircularEvaluator.v0.md must exist in mu/docs/core/"
    )
    return SPEC_PATH.read_text(encoding="utf-8")


def _normalized_spec_text() -> str:
    return " ".join(_spec_text().split())


def test_fixpoint_doc_has_governed_header_and_grounding_gate():
    text = _spec_text()

    assert "DOC_STATUS" in text[:400]
    assert "TYPE: REFERENCE" in text[:400]
    assert "LAST_VERIFIED: 2026-06-27" in text[:400]
    assert f"GROUNDING_TESTS: {TEST_PATH}" in text[:500]


def test_fixpoint_doc_is_discoverable_from_single_packet_authority():
    text = _spec_text()
    packet_text = PACKET_PATH.read_text(encoding="utf-8")
    bridge_packet_text = BRIDGE_PACKET_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    assert WAVE_ID in tasks_text
    assert "Class: L4_ENABLER" in tasks_text
    assert "target_gate_id: G8" in tasks_text
    assert f"Packet: `{PACKET_REF}`" in tasks_text
    assert "mu/docs/core/FixpointMetaCircularEvaluator.v0.md" in tasks_text
    assert TEST_PATH in tasks_text
    assert DOCS_TEST_PATH in tasks_text
    assert INDICATOR_REF in tasks_text
    assert "Optimization and production runtime/substrate/seed/parity edits remain out of scope" in tasks_text
    assert "Optimization is LAST" in tasks_text

    assert any(
        status in packet_text
        for status in ACCEPTED_PACKET_STATUSES
    )
    assert "Phase-A-Lock: LOCKED" in packet_text
    assert "Governing packet: this file" in packet_text
    assert "TASKS.md authority:" in packet_text
    assert "mu/docs/core/FixpointMetaCircularEvaluator.v0.md" in packet_text
    assert TEST_PATH in packet_text
    assert DOCS_TEST_PATH in packet_text
    assert INDICATOR_REF in packet_text
    assert "FixpointMetaCircularEvaluator design/spec" in packet_text
    assert "not production fixpoint execution" in packet_text
    assert "Phase B (locked, implementing)" in bridge_packet_text
    assert "Governing packet and launcher/commit authority surface" in bridge_packet_text

    assert "Bridge-review normalization surface only" in bridge_packet_text
    assert "must not supersede" in bridge_packet_text
    assert PACKET_REF in bridge_packet_text
    assert "First Foundation Gate Criteria" in text


def test_fixpoint_spec_defines_structural_representation_boundary():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "not a host evaluator API",
        "not a host recursion API",
        "not a host scheduler API",
        "not a host coroutine API",
        "not a host iterator API",
        "not a host parser API",
        "not an optimizer pass",
        'evaluator_envelope ::= {"_fix_eval_envelope":',
        'evaluator_ref      ::= {"_fix_evaluator_ref":',
        'fixed_point_witness ::= {"_fix_witness":',
        'self_application_trace ::= {"_fix_trace": null}',
        'closure_boundary   ::= {"_fix_boundary":',
        'stall_boundary     ::= {"_fix_stall_boundary":',
        'proof_limit        ::= {"_fix_proof_limit":',
        "do not require host callables, host recursion frames",
        "does not execute a fixed point",
        "does not authorize production evaluator semantics",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_fixpoint_spec_binds_envelope_witness_trace_and_boundary_obligations():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "An evaluator-as-data envelope carries an evaluator reference",
        "An evaluator reference carries the evaluator body as Mu data",
        "A fixed-point witness names a candidate evaluator",
        "A self-application trace prefix is finite",
        "Closure and stall boundaries remain explicit",
        "Budget exhaustion is distinct from closure",
        "Proof limits are first-class records",
        "Evaluator step relation",
        "Self-application relation",
        "Fixed-point witness validation",
        "Closure/stall verification",
        "Budget/exhaustion discipline",
        "Fail-closed malformed envelopes",
        "Proof-limit preservation",
        "not Python callable semantics",
        "not host recursion semantics",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_fixpoint_spec_names_finite_examples():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "### Evaluator-As-Data Envelope",
        "IdentityEvaluatorData",
        "EnvelopeIdentityA",
        "production evaluator execution",
        "### Self-Application Trace Prefix",
        "SelfApplyEvent0",
        "TracePrefix1",
        "not a host recursive call",
        "### Fixed-Point Witness Candidate",
        "WitnessIdentityOpen",
        "same-shape-under-one-unfolding",
        "does not prove a working fixed point",
        "### Closure And Stall Boundary",
        "StallBoundaryIdentity",
        "BudgetBoundaryOpen",
        "budget exhaustion is not closure",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_fixpoint_spec_defers_runtime_authority_and_optimization():
    text = _spec_text()
    normalized = _normalized_spec_text()

    forbidden_claims = [
        "production evaluator semantics are authorized",
        "fixed-point execution is complete",
        "self-application execution is complete",
        "meta-circular closure is complete",
        "evaluator closure is complete",
        "fixed-point closure is complete",
        "self-hosting closure is complete",
        "optimization is authorized",
        "Optimization is authorized",
    ]
    for phrase in forbidden_claims:
        assert phrase not in text

    required_limits = [
        "This v0 does not prove or authorize",
        "production evaluator semantics",
        "fixed-point execution, self-application execution, meta-circular closure",
        "self-hosting closure",
        "production proof that evaluator-as-data can run itself",
        "changes to runtime, substrate, seed, registry, projection, JavaScript parity",
        "pager/autoping, tmux, evaluator, parser, scheduler, or execution semantics",
        "host evaluator behavior, host recursion authority",
        "host scheduler authority, host parser authority",
        "Coinduction remains separate completed structural foundation work",
        "Optimization remains LAST",
        "This wave does not authorize optimization work",
    ]
    for phrase in required_limits:
        assert phrase in normalized or phrase in text


def test_fixpoint_indicator_artifact_is_bound_to_wave_id():
    assert INDICATOR_PATH.exists(), "L4 indicator artifact must be produced"
    data = json.loads(INDICATOR_PATH.read_text(encoding="utf-8"))

    assert data["wave_id"] == WAVE_ID
    for key in (
        "repeat_run_speedup_ratio",
        "parity_diff_count",
        "net_host_semantic_delta",
        "step_growth_slope",
        "repeat_run_raw_seconds",
        "step_growth_points",
        "parity_diff_source",
        "collection_timestamp_utc",
        "collector_version",
    ):
        assert key in data


def test_fixpoint_spec_links_existing_architecture_without_expanding_scope():
    text = _spec_text()

    required = [
        "`MuType.v0.md` remains the base value contract",
        "`SelfHosting.v0.md` and `MetaCircularKernel.v0.md` remain the current",
        "`StructuralPurity.v0.md` remains the guardrail",
        "`NorthStarSemantics.v0.md` remains the semantic policy lock",
        "`OntologyPromotionContract.v0.md` remains the promotion discipline",
        "`L3SubstrateArchitecture.v0.md` remains the L3/L4 boundary reference",
    ]
    for phrase in required:
        assert phrase in text
