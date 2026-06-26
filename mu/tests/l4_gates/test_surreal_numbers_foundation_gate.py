"""Foundation gate for the bounded SurrealNumbers v0 specification.

This test intentionally does not execute production Surreals semantics. It
locks the first falsifiable docs criteria from the Surreals-as-structure wave:
the spec is discoverable, bounded, structural-data-first, and explicit about
proof limits.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.repo_root import REPO_ROOT


WAVE_ID = "surreals-as-structure-2026-06-26"
SPEC_PATH = REPO_ROOT / "mu" / "docs" / "core" / "SurrealNumbers.v0.md"
TEST_PATH = "mu/tests/l4_gates/test_surreal_numbers_foundation_gate.py"
DOCS_TEST_PATH = "mu/tests/docs/test_surreal_numbers_foundation_gate.py"
CONFIG_PATH = (
    REPO_ROOT
    / "reports"
    / "control_plane"
    / "surreals-as-structure-2026-06-26_wave_config.json"
)
PACKET_REF = "reports/control_plane/surreals-as-structure-2026-06-26_2026-06-26.md"
PACKET_PATH = REPO_ROOT / PACKET_REF
TASKS_PATH = REPO_ROOT / "TASKS.md"


def _spec_text() -> str:
    assert SPEC_PATH.exists(), "SurrealNumbers.v0.md must exist in mu/docs/core/"
    return SPEC_PATH.read_text(encoding="utf-8")


def _normalized_spec_text() -> str:
    return " ".join(_spec_text().split())


def test_surreal_numbers_doc_has_governed_header_and_grounding_gate():
    text = _spec_text()

    assert "DOC_STATUS" in text[:400]
    assert "TYPE: REFERENCE" in text[:400]
    assert "LAST_VERIFIED: 2026-06-26" in text[:400]
    assert f"GROUNDING_TESTS: {TEST_PATH}" in text[:500]


def test_surreal_numbers_doc_is_discoverable_from_wave_authority():
    text = _spec_text()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    packet_text = PACKET_PATH.read_text(encoding="utf-8")
    tasks_text = TASKS_PATH.read_text(encoding="utf-8")

    assert config["wave_id"] == WAVE_ID
    assert config["wave_class"] == "L4_ENABLER"
    assert "workload_target" not in config
    assert "host_semantics_delta_before" not in config
    assert "host_semantics_delta_after" not in config
    assert "mu/docs/core/SurrealNumbers.v0.md" in config["structural_artifact_ref"]
    assert TEST_PATH in config["structural_artifact_ref"]
    assert DOCS_TEST_PATH in config["structural_artifact_ref"]
    assert "--wave-class L4_ENABLER" in config["evidence_command"]
    assert PACKET_REF in tasks_text
    assert TEST_PATH in tasks_text
    assert DOCS_TEST_PATH in tasks_text
    assert "mu/docs/core/SurrealNumbers.v0.md" in packet_text
    assert TEST_PATH in packet_text
    assert DOCS_TEST_PATH in packet_text
    assert WAVE_ID in tasks_text
    assert "Class: L4_ENABLER" in tasks_text
    assert "First Foundation Gate Criteria" in text


def test_surreal_numbers_spec_defines_structural_representation_boundary():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "not a host numeric API",
        "does not authorize production Surreals runtime semantics",
        'surreal_cut ::= {"_surreal": {"left": option_set, "right": option_set}}',
        'option_set  ::= {"_options": null}',
        "finite structural option sets",
        "does not require host arrays, host sets, host numeric literals",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_surreal_numbers_spec_binds_construction_and_proof_obligations():
    text = _spec_text()
    normalized = _normalized_spec_text()

    required = [
        "Every option member is itself a previously constructed surreal cut",
        "The construction is founded",
        "Every left option is proven less than every right option",
        "Rule 4 is a proof obligation, not a host comparison",
        "Representation identity is not enough for surreal equality",
        "x <= y  iff no left option x_l of x satisfies y <= x_l",
        "x == y  iff x <= y and y <= x",
        "They are not Python `<=`, JavaScript `<=`, content-hash",
    ]
    for phrase in required:
        assert phrase in normalized or phrase in text


def test_surreal_numbers_spec_names_bounded_examples_and_negative_case():
    text = _spec_text()

    required = [
        "| `0` | `{ | }` |",
        "| `1` | `{0 | }` |",
        "| `-1` | `{ | 0}` |",
        "| `1/2` | `{0 | 1}` |",
        "| invalid | `{0 | 0}` |",
        "Must fail because `0 < 0` is false",
    ]
    for phrase in required:
        assert phrase in text


def test_surreal_numbers_spec_withholds_runtime_and_later_wave_authority():
    text = _spec_text()
    normalized = _normalized_spec_text()

    forbidden_claims = [
        "production Surreals runtime semantics are authorized",
        "Surreals arithmetic closure is complete",
        "optimization is authorized",
        "StructuralNumbers semantics are changed",
    ]
    for phrase in forbidden_claims:
        assert phrase not in text

    required_limits = [
        "This v0 does not prove or authorize",
        "production Surreals runtime semantics",
        "Surreals arithmetic",
        "global canonicalization or quotienting",
        "recursive ordinals, W-types / inductive types, coinduction, fixpoint, or",
        "optimization work",
        "changes to runtime, substrate, seed, registry, projection, JavaScript parity",
        "host numeric API behavior or host numeric coercion",
        "It is not evidence of Surreals semantic closure",
    ]
    for phrase in required_limits:
        assert phrase in normalized or phrase in text
