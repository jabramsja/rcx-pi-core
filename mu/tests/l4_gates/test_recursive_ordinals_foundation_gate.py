"""Foundation gate for the bounded RecursiveOrdinals v0 specification.

This test intentionally does not execute production recursive ordinal
semantics. It locks the first falsifiable docs criteria from the
recursive-ordinals-as-structure wave: the spec is discoverable, bounded,
structural-data-first, explicit about finite bridge obligations, and explicit
about proof limits.
"""

from __future__ import annotations

import json

from tests.repo_root import REPO_ROOT


WAVE_ID = "recursive-ordinals-as-structure-2026-06-26"
SPEC_PATH = REPO_ROOT / "mu" / "docs" / "core" / "RecursiveOrdinals.v0.md"
TEST_PATH = "mu/tests/l4_gates/test_recursive_ordinals_foundation_gate.py"
DOCS_TEST_PATH = "mu/tests/docs/test_recursive_ordinals_foundation_gate.py"
CONFIG_PATH = (
    REPO_ROOT
    / "reports"
    / "control_plane"
    / "recursive-ordinals-as-structure-2026-06-26_wave_config.json"
)
PACKET_REF = "reports/control_plane/recursive-ordinals-as-structure-2026-06-26_2026-06-26.md"
PACKET_PATH = REPO_ROOT / PACKET_REF
TASKS_PATH = REPO_ROOT / "TASKS.md"


def _spec_text() -> str:
    assert SPEC_PATH.exists(), "RecursiveOrdinals.v0.md must exist in mu/docs/core/"
    return SPEC_PATH.read_text(encoding="utf-8")


def _normalized_spec_text() -> str:
    return " ".join(_spec_text().split())


def test_recursive_ordinals_doc_has_governed_header_and_grounding_gate():
    text = _spec_text()

    assert "DOC_STATUS" in text[:400]
    assert "TYPE: REFERENCE" in text[:400]
    assert "LAST_VERIFIED: 2026-06-26" in text[:400]
    assert f"GROUNDING_TESTS: {TEST_PATH}" in text[:500]


def test_recursive_ordinals_doc_is_discoverable_from_wave_authority():
    text = _spec_text()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    packet_text = PACKET_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    assert config["wave_id"] == WAVE_ID
    assert config["wave_class"] == "L4_ENABLER"
    assert "workload_target" not in config
    assert "host_semantics_delta_before" not in config
    assert "host_semantics_delta_after" not in config
    assert "mu/docs/core/RecursiveOrdinals.v0.md" in config["structural_artifact_ref"]
    assert TEST_PATH in config["structural_artifact_ref"]
    assert DOCS_TEST_PATH in config["structural_artifact_ref"]
    assert "--wave-class L4_ENABLER" in config["evidence_command"]
    assert PACKET_REF in tasks_text
    assert TEST_PATH in tasks_text
    assert DOCS_TEST_PATH in tasks_text
    assert "mu/docs/core/RecursiveOrdinals.v0.md" in packet_text
    assert TEST_PATH in packet_text
    assert DOCS_TEST_PATH in packet_text
    assert WAVE_ID in tasks_text
    assert "Class: L4_ENABLER" in tasks_text
    assert "1. **Recursive ordinals** as structure." in tasks_text
    assert "5. **Optimization**" in tasks_text
    assert "First Foundation Gate Criteria" in text


def test_recursive_ordinals_spec_defines_structural_representation_boundary():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "not a host ordinal API",
        "not a host set-theory API",
        "not a host numeric execution API",
        'ordinal     ::= {"_ord": {"members": member_list}}',
        'member_list ::= {"_ord_members": null}',
        "finite recursive containment",
        "does not require host arrays, host sets, host numeric literals",
        "does not make an ordinal value, membership result, order result",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_recursive_ordinals_spec_binds_construction_and_order_obligations():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "Zero is the unique empty-member candidate",
        "successor(alpha)",
        "Every member is itself a previously constructed recursive ordinal",
        "Construction is founded",
        "beta member_of alpha  iff beta is present in alpha.members",
        "beta < alpha          iff beta member_of alpha",
        "It must not rely on Python `in`, JavaScript `includes`, host set membership",
        "every member of a member is also a member of the containing ordinal",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_recursive_ordinals_spec_names_finite_examples():
    text = _spec_text()

    required = [
        "O0 := {\"_ord\": {\"members\": E}}",
        "O1 := {\"_ord\": {\"members\": {\"_ord_members\": {\"member\": O0, \"rest\": E}}}}",
        "| `0` | `O0` |",
        "| `1` | `O1 = successor(O0)` |",
        "| `2` | `O2 = successor(O1)` |",
        "`0 member_of 1`",
        "`0 member_of 2`",
        "`1 member_of 2`",
        "`0 < 1 < 2`",
    ]
    for phrase in required:
        assert phrase in text


def test_recursive_ordinals_spec_records_structural_numbers_bridge_obligations():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "`StructuralNumbers.v0.md` remains the computational integer representation",
        "ord_to_N : RecursiveOrdinal -> StructuralNumbers N",
        "N_to_ord : StructuralNumbers N -> RecursiveOrdinal",
        "Zero round trip",
        "Mutual inverse",
        "Successor homomorphism",
        "Order preservation",
        "must not claim production bridge closure",
        "implemented `ord_to_N`",
        "implemented `N_to_ord`",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_recursive_ordinals_spec_withholds_runtime_transfinite_and_later_wave_authority():
    text = _spec_text()
    normalized = _normalized_spec_text()

    forbidden_claims = [
        "production recursive ordinal runtime semantics are authorized",
        "recursive ordinal semantic closure is complete",
        "transfinite closure is complete",
        "ordinal arithmetic closure is complete",
        "optimization is authorized",
        "StructuralNumbers semantics are changed",
    ]
    for phrase in forbidden_claims:
        assert phrase not in text

    required_limits = [
        "This v0 does not prove or authorize",
        "production recursive ordinal runtime semantics",
        "implemented `ord_to_N` or `N_to_ord` projections",
        "recursive ordinal arithmetic",
        "transfinite constructors such as `omega`",
        "W-types / inductive types, coinduction, fixpoint, or optimization work",
        "changes to runtime, substrate, seed, registry, projection, JavaScript parity",
        "host ordinal API behavior, host set-theory authority, host numeric coercion",
        "It is not evidence of recursive ordinal semantic closure",
    ]
    for phrase in required_limits:
        assert phrase in normalized or phrase in text
