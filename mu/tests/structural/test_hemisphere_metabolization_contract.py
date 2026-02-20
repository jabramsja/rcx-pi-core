"""
E1 contract tests for Hemisphere Metabolization.

Locks the 6 metabolization projection IDs, truth-table coverage (T1-T10),
and sink-safety invariants (S1-S5) BEFORE implementation begins. Tests that
check actual seed/projection existence are skip-marked until the seed is
created; design-doc ground-truth checks run now.

This is the test-first artifact for HemisphereExecutionChecklist.v0.md gate E1.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parents[2]
DESIGN_DOC = REPO_ROOT / "roadmap" / "MuHemispheresDesign.md"
EXECUTION_CHECKLIST = REPO_ROOT / "mu" / "docs" / "core" / "HemisphereExecutionChecklist.v0.md"
EXISTING_HEMISPHERE_SEED = REPO_ROOT / "mu" / "programs" / "hemispheres.v1.json"

# ── Canonical metabolization projection IDs (from design doc) ──

METABOLIZATION_PROJECTION_IDS = (
    "hemisphere.metabolize.sink_to_r_inf",
    "hemisphere.metabolize.sink_to_r_null",
    "hemisphere.recover.stall_to_lobes",
    "hemisphere.recover.stall_to_sink",
    "hemisphere.promote.lobes_to_r_a",
    "hemisphere.recycle.residual_to_sink",
)

# ── Truth-table transition IDs ──

TRUTH_TABLE_IDS = ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9", "T10")

# ── Sink-safety invariant IDs ──

SINK_SAFETY_IDS = ("S1", "S2", "S3", "S4", "S5")


# =============================================================================
# Design Doc Ground Truth (run now — no implementation required)
# =============================================================================


class TestDesignDocGroundTruth:
    """Verify design doc contains the canonical metabolization contract."""

    def test_design_doc_exists(self) -> None:
        assert DESIGN_DOC.exists(), f"Design doc not found: {DESIGN_DOC}"

    def test_design_doc_contains_all_projection_ids(self) -> None:
        text = DESIGN_DOC.read_text(encoding="utf-8")
        missing = [pid for pid in METABOLIZATION_PROJECTION_IDS if pid not in text]
        assert not missing, (
            f"Design doc missing metabolization projection IDs: {missing}"
        )

    def test_design_doc_contains_truth_table(self) -> None:
        text = DESIGN_DOC.read_text(encoding="utf-8")
        missing = [tid for tid in TRUTH_TABLE_IDS if f"| {tid} " not in text]
        assert not missing, (
            f"Design doc missing truth-table transitions: {missing}"
        )

    def test_design_doc_contains_sink_safety_invariants(self) -> None:
        text = DESIGN_DOC.read_text(encoding="utf-8")
        missing = [sid for sid in SINK_SAFETY_IDS if f"| {sid} " not in text]
        assert not missing, (
            f"Design doc missing sink-safety invariants: {missing}"
        )

    def test_design_doc_contains_option_b(self) -> None:
        text = DESIGN_DOC.read_text(encoding="utf-8")
        assert "Option B" in text, "Design doc missing engine exception policy Option B"
        assert "exception_sink" in text, (
            "Design doc missing 'exception_sink' action value for synthesized results"
        )


class TestExecutionChecklistGroundTruth:
    """Verify execution checklist aligns with design contract."""

    def test_checklist_exists(self) -> None:
        assert EXECUTION_CHECKLIST.exists(), (
            f"Execution checklist not found: {EXECUTION_CHECKLIST}"
        )

    def test_checklist_has_all_five_gates(self) -> None:
        text = EXECUTION_CHECKLIST.read_text(encoding="utf-8")
        for gate in ("### E1:", "### E2:", "### E3:", "### E4:", "### E5:"):
            assert gate in text, f"Checklist missing gate {gate}"


class TestExistingHemisphereSeedBaseline:
    """Verify the existing hemispheres.v1.json baseline is intact."""

    def test_existing_seed_exists(self) -> None:
        assert EXISTING_HEMISPHERE_SEED.exists()

    def test_existing_seed_has_12_projections(self) -> None:
        import json
        seed = json.loads(EXISTING_HEMISPHERE_SEED.read_text(encoding="utf-8"))
        assert len(seed["projections"]) == 12, (
            f"Expected 12 existing hemisphere projections, got {len(seed['projections'])}"
        )

    def test_existing_seed_is_application_layer(self) -> None:
        import json
        seed = json.loads(EXISTING_HEMISPHERE_SEED.read_text(encoding="utf-8"))
        assert seed["meta"]["execution_layer"] == "APPLICATION"

    def test_existing_seed_requires_linear_patterns(self) -> None:
        import json
        seed = json.loads(EXISTING_HEMISPHERE_SEED.read_text(encoding="utf-8"))
        assert seed["meta"]["requires_patterns"] == ["linear"]


# =============================================================================
# E1 Implementation Contract (skip-marked until seed exists)
# =============================================================================

# Candidate seed paths — metabolization may be added to hemispheres.v1.json
# or in a new file. Tests check both.
_METABOLIZATION_SEED_CANDIDATES = (
    REPO_ROOT / "mu" / "programs" / "metabolization.v1.json",
    EXISTING_HEMISPHERE_SEED,  # may be extended
)


def _find_metabolization_seed() -> Path | None:
    """Return the seed file containing metabolization projections, or None."""
    import json
    for candidate in _METABOLIZATION_SEED_CANDIDATES:
        if not candidate.exists():
            continue
        seed = json.loads(candidate.read_text(encoding="utf-8"))
        ids = {p["id"] for p in seed.get("projections", [])}
        if METABOLIZATION_PROJECTION_IDS[0] in ids:
            return candidate
    return None


_E1_SKIP = pytest.mark.skip(reason="E1: metabolization seed not yet implemented")


@_E1_SKIP
class TestMetabolizationSeedExists:
    """Gate E1: metabolization projections exist and are loadable."""

    def test_seed_file_found(self) -> None:
        seed_path = _find_metabolization_seed()
        assert seed_path is not None, (
            "No seed file contains metabolization projections. "
            f"Expected one of: {[str(p) for p in _METABOLIZATION_SEED_CANDIDATES]}"
        )

    def test_all_6_projection_ids_present(self) -> None:
        import json
        seed_path = _find_metabolization_seed()
        assert seed_path is not None
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        ids = {p["id"] for p in seed["projections"]}
        missing = [pid for pid in METABOLIZATION_PROJECTION_IDS if pid not in ids]
        assert not missing, f"Seed missing metabolization projection IDs: {missing}"

    def test_projections_have_required_fields(self) -> None:
        import json
        seed_path = _find_metabolization_seed()
        assert seed_path is not None
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        metab_ids = set(METABOLIZATION_PROJECTION_IDS)
        for proj in seed["projections"]:
            if proj["id"] in metab_ids:
                for field in ("id", "pattern", "body"):
                    assert field in proj, (
                        f"Projection {proj['id']} missing required field '{field}'"
                    )

    def test_seed_integrity_loadable(self) -> None:
        """Metabolization seed must pass seed_integrity verification."""
        from rcx_pi.selfhost.seed_integrity import load_verified_seed
        seed_path = _find_metabolization_seed()
        assert seed_path is not None
        # This will raise if checksum/structure validation fails
        load_verified_seed(seed_path)
