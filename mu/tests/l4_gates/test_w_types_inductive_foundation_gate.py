"""Foundation gate for the bounded WTypesInductiveTypes v0 specification.

This test intentionally does not execute production W-type or AST semantics.
It locks the first falsifiable docs criteria from the
w-types-inductive-types-ast-as-inductive-structure wave: the spec is
discoverable, bounded, structural-data-first, explicit about constructor and
child-list obligations, and explicit about proof limits.
"""

from __future__ import annotations

import json

from tests.repo_root import REPO_ROOT


WAVE_ID = "w-types-inductive-types-ast-as-inductive-structure-2026-06-26"
SPEC_PATH = REPO_ROOT / "mu" / "docs" / "core" / "WTypesInductiveTypes.v0.md"
TEST_PATH = "mu/tests/l4_gates/test_w_types_inductive_foundation_gate.py"
DOCS_TEST_PATH = "mu/tests/docs/test_w_types_inductive_foundation_gate.py"
CONFIG_PATH = (
    REPO_ROOT
    / "reports"
    / "control_plane"
    / "w-types-inductive-types-ast-as-inductive-structure-2026-06-26_wave_config.json"
)
PACKET_REF = (
    "reports/control_plane/"
    "w-types-inductive-types-ast-as-inductive-structure-2026-06-26_2026-06-26.md"
)
PACKET_PATH = REPO_ROOT / PACKET_REF
TASKS_PATH = REPO_ROOT / "TASKS.md"


def _spec_text() -> str:
    assert SPEC_PATH.exists(), "WTypesInductiveTypes.v0.md must exist in mu/docs/core/"
    return SPEC_PATH.read_text(encoding="utf-8")


def _normalized_spec_text() -> str:
    return " ".join(_spec_text().split())


def test_w_types_doc_has_governed_header_and_grounding_gate():
    text = _spec_text()

    assert "DOC_STATUS" in text[:400]
    assert "TYPE: REFERENCE" in text[:400]
    assert "LAST_VERIFIED: 2026-06-26" in text[:400]
    assert f"GROUNDING_TESTS: {TEST_PATH}" in text[:500]


def test_w_types_doc_is_discoverable_from_wave_authority():
    text = _spec_text()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    packet_text = PACKET_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    assert config["wave_id"] == WAVE_ID
    assert config["date"] == "2026-06-26"
    assert config["wave_class"] == "L4_ENABLER"
    assert config["task_id"] == "[NEXT-CODEX-POST-REDTEAM]"
    assert config["target_gate_id"] == "G8"
    assert config["tracked_packet"] == PACKET_REF
    assert "workload_target" not in config
    assert "host_semantics_delta_before" not in config
    assert "host_semantics_delta_after" not in config
    assert "mu/docs/core/WTypesInductiveTypes.v0.md" in config["structural_artifact_ref"]
    assert TEST_PATH in config["structural_artifact_ref"]
    assert DOCS_TEST_PATH in config["structural_artifact_ref"]
    assert "--wave-class L4_ENABLER" in config["evidence_command"]
    assert PACKET_REF in tasks_text
    assert TEST_PATH in tasks_text
    assert DOCS_TEST_PATH in tasks_text
    assert WAVE_ID in tasks_text
    assert "Class: L4_ENABLER" in tasks_text
    assert "mu/docs/core/WTypesInductiveTypes.v0.md" in packet_text
    assert TEST_PATH in packet_text
    assert DOCS_TEST_PATH in packet_text
    assert "WTypesInductiveTypes.v0.md exists as a bounded design/spec" in packet_text
    assert "Optimization remains out of scope and LAST in TASKS.md." in packet_text
    assert "First Foundation Gate Criteria" in text


def test_w_types_spec_defines_structural_representation_boundary():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "not a host algebraic data type API",
        "not a host typeclass API",
        "not a host parser API",
        "not a TypeScript interface authority",
        "not a host class/dataclass authority",
        'w_signature     ::= {"_w_signature":',
        'constructor     ::= {"_w_constructor":',
        'child_list      ::= {"_w_children": null}',
        'inductive_node  ::= {"_w_node":',
        'position        ::= {"_position":',
        "do not require host arrays, host tuples, host enum variants",
        "does not authorize production W-type runtime semantics",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_w_types_spec_binds_constructor_signature_and_child_obligations():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "A signature node names one inductive family",
        "Each constructor node names one introduction form",
        "Parameter positions are explicit structural positions",
        "Child positions are explicit structural positions",
        "Child lists must be linked Mu lists",
        '"recursive": true',
        '"recursive": false',
        "Recursive subtree containment is founded for finite values",
        "same family or a structurally declared mutually inductive family",
        "not Python constructors",
        "not host algebraic data types",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_w_types_spec_records_recursion_obligations_without_claiming_execution():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "Induction and structural recursion are later implementation obligations",
        "Constructor coverage",
        "Child decrease",
        "Parameter preservation",
        "Branch result shape",
        "Deterministic traversal",
        "Fail-closed malformed nodes",
        "does not claim induction principle execution",
        "structural recursion execution",
        "eliminator closure",
        "recursive AST evaluator closure",
        "pattern compiler closure",
        "self-hosting closure",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_w_types_spec_names_finite_examples():
    text = _spec_text()

    required = [
        "### Bool",
        "BoolSig",
        "TrueCtor",
        "FalseCtor",
        "BoolTrue",
        "BoolFalse",
        "### List",
        "ConsChildren",
        "tail is the recursive subtree",
        "### Binary Tree",
        "TreeSig(A) has constructors:",
        "left` and `right` are recursive subtree children",
        "### Tiny Expression AST",
        "ExprSig has constructors:",
        "ZeroExpr",
        "VarX",
        "AddZeroX",
        "This is AST-as-inductive-structure",
    ]
    for phrase in required:
        assert phrase in text


def test_w_types_spec_defers_later_queue_items_and_withholds_runtime_authority():
    text = _spec_text()
    normalized = _normalized_spec_text()

    forbidden_claims = [
        "production W-type runtime semantics are authorized",
        "W-type semantic closure is complete",
        "induction principle execution is complete",
        "eliminator closure is complete",
        "recursive AST evaluator closure is complete",
        "self-hosting closure is complete",
        "coinduction closure is complete",
        "fixpoint closure is complete",
        "optimization is authorized",
    ]
    for phrase in forbidden_claims:
        assert phrase not in text

    required_limits = [
        "This v0 does not prove or authorize",
        "production W-type runtime semantics",
        "production inductive type runtime semantics",
        "production constructor checker, recursor, eliminator",
        "AST parser, or AST evaluator",
        "coinduction closure, fixpoint closure, or optimization closure",
        "changes to runtime, substrate, seed, registry, projection, JavaScript parity",
        "host algebraic data type behavior, host typeclass authority",
        "host parser authority, host class/dataclass authority",
        "Optimization remains LAST",
        "This wave does not advance coinduction",
        "This wave does not advance fixpoint",
    ]
    for phrase in required_limits:
        assert phrase in normalized or phrase in text


def test_w_types_spec_links_existing_architecture_without_expanding_scope():
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
