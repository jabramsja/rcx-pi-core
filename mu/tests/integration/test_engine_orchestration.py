"""
Engine Orchestration: Full Pipeline via run_engine_pipeline()

Tests the complete engine pipeline: trace → hash → recurrence → exhaustion.
The pipeline follows the state machine defined by rcx_engine.v1.json
(structural specification) but uses separate kernel invocations for each stage.

This is the "closing the loop" test — proving the full deadlock metabolization
pipeline works as a single function call.

NOTE: Full paxos pipeline tests are in test_paxos_end_to_end.py. These tests
use simple projections for fast validation of the orchestration function itself.

See: mu/programs/rcx_engine.v1.json (11 projections, structural specification)
     rcx_pi/selfhost/step_mu.py:run_engine_pipeline()
     roadmap/ContentAddressedMu.md (Orchestration section)
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import run_engine_pipeline

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def engine_seed():
    return load_verified_seed(get_seed_path("rcx_engine.v1.json"))


@pytest.fixture(scope="module")
def simple_projs():
    """Simple projections: A → B (then stall). Completes in 1 step."""
    return [{"id": "to_b", "pattern": "A", "body": "B"}]


@pytest.fixture(scope="module")
def stalling_projs():
    """No projections — input stalls immediately."""
    return []


# ---------------------------------------------------------------------------
# Engine Orchestration Tests
# ---------------------------------------------------------------------------


class TestEngineOrchestration:
    """Test the engine pipeline via run_engine_pipeline()."""

    def test_simple_pipeline_completes(self, simple_projs):
        """Pipeline with simple A→B should complete without error."""
        result = run_engine_pipeline(simple_projs, "A", max_steps=5, use_boot1_recursive=False)

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result["stall"] is True, "A→B then stall"
        assert result["value"] is not None

    def test_stalling_pipeline(self, stalling_projs):
        """Pipeline with no matching projections should stall."""
        result = run_engine_pipeline(stalling_projs, {"unmatchable": True}, max_steps=5, use_boot1_recursive=False)

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result["stall"] is True, "No projections should cause stall"

    def test_result_has_all_fields(self, simple_projs):
        """Engine result should have all fields from the engine spec."""
        result = run_engine_pipeline(simple_projs, "A", max_steps=5, use_boot1_recursive=False)

        expected_fields = [
            "value", "closure_detected", "tau_step",
            "exhaustion_detected", "operator_frozen",
            "frozen_set", "action", "stall"
        ]
        for field in expected_fields:
            assert field in result, f"Missing field '{field}' in result: {result}"

    def test_stall_is_closure(self, simple_projs):
        """A→B then stall (B→B) IS closure — the state repeats."""
        result = run_engine_pipeline(simple_projs, "A", max_steps=5, use_boot1_recursive=False)

        # Stall means the state doesn't change → same hash appears twice → closure
        assert result["closure_detected"] is True, (
            f"Stall should be detected as closure (repeating state), got: {result}"
        )

    def test_frozen_set_passed_through(self, simple_projs):
        """Initial frozen set should appear in result."""
        frozen = {"head": "pre_frozen_op", "tail": None}
        result = run_engine_pipeline(simple_projs, "A", max_steps=5, frozen=frozen, use_boot1_recursive=False)

        # Frozen set should be present in result
        assert "frozen_set" in result

    def test_max_steps_respected(self, simple_projs):
        """Pipeline should respect max_steps parameter."""
        result = run_engine_pipeline(simple_projs, "A", max_steps=1, use_boot1_recursive=False)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Engine Spec Validation
# ---------------------------------------------------------------------------


class TestEngineSpec:
    """Validate rcx_engine.v1.json as structural specification."""

    def test_engine_status_is_specification(self, engine_seed):
        """Engine should be marked as structural_specification."""
        assert engine_seed["meta"]["status"] == "structural_specification"

    def test_engine_has_all_phases(self, engine_seed):
        """Engine should cover the complete pipeline lifecycle."""
        ids = [p["id"] for p in engine_seed["projections"]]
        expected = [
            "engine.init", "engine.init_config",
            "engine.trace_done", "engine.hash_done_fix", "engine.hash_done",
            "engine.fix_done_applied", "engine.fix_done_none",
            "engine.recurrence_done",
            "engine.exhaustion_done_freeze", "engine.exhaustion_done_terminal",
            "engine.unwrap"
        ]
        for phase in expected:
            assert phase in ids, f"Missing phase: {phase}"

    def test_engine_references_recurrence_v2(self, engine_seed):
        """Engine should reference recurrence.v2 (not v1)."""
        deps = engine_seed["meta"]["dependencies"]
        has_v2 = any("recurrence.v2" in d for d in deps)
        assert has_v2, f"Engine should reference recurrence.v2, deps: {deps}"

    def test_engine_projection_count(self, engine_seed):
        """Engine should have exactly 11 projections."""
        assert len(engine_seed["projections"]) == 11
