"""
RCX Engine Integration Tests - Full Cycle Testing.

9-agent finding (Grounding, Advisor): rcx_engine.v1.json tests only verify
individual projection patterns, not the full engine cycle:
  init → trace → recurrence → exhaustion → unwrap

These tests run the complete engine workflow by combining:
- rcx_engine.v1.json (6 projections) - orchestration
- recurrence.v1.json (9 projections) - closure detection
- exhaustion.v1.json (11 projections) - operator exhaustion

IMPORTANT: The engine expects intermediate results from:
1. run_mu_structural (trace generation)
2. _detect_closure (recurrence detection)
3. _detect_exhaustion (exhaustion detection)

We simulate these by providing pre-computed intermediate states.
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.mu_type import mu_equal


# JSON null -> Python None alias
null = None


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def engine_projections() -> list:
    """Load engine projections."""
    seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
    return seed["projections"]


@pytest.fixture
def recurrence_projections() -> list:
    """Load recurrence projections."""
    seed = load_verified_seed(get_seed_path("recurrence.v1.json"))
    return seed["projections"]


@pytest.fixture
def exhaustion_projections() -> list:
    """Load exhaustion projections."""
    seed = load_verified_seed(get_seed_path("exhaustion.v1.json"))
    return seed["projections"]


@pytest.fixture
def combined_projections(engine_projections, recurrence_projections, exhaustion_projections) -> list:
    """Combine all projections for full engine execution.

    Order: engine -> recurrence -> exhaustion
    Engine patterns (_run_engine, _mode:engine) must come first.
    Algorithm patterns (_detect_closure, _detect_exhaustion) come next.
    """
    return engine_projections + recurrence_projections + exhaustion_projections


def run_until_stable(projections: list, value: dict, max_steps: int = 200) -> dict:
    """Run projections until stall or max_steps."""
    reset_step_budget()
    current = value
    for i in range(max_steps):
        result = step(projections, current)
        if result == current:
            return result
        current = result
    return current


def single_step(projections: list, value: dict) -> dict:
    """Run exactly one step."""
    reset_step_budget()
    return step(projections, value)


# =============================================================================
# Engine Initialization Tests
# =============================================================================


class TestEngineInit:
    """Test engine initialization with combined projections."""

    def test_init_creates_engine_state(self, combined_projections):
        """_run_engine should create engine state with run_trace phase."""
        input_data = {
            "_run_engine": {
                "projections": [{"pattern": "A", "body": "B"}],
                "input": "A"
            }
        }

        result = single_step(combined_projections, input_data)

        assert result.get("_mode") == "engine"
        assert result.get("_phase") == "run_trace"
        assert result.get("_max_steps") == 100  # default
        assert result.get("_frozen") is None

    def test_init_with_config(self, combined_projections):
        """_run_engine with config should preserve custom settings."""
        input_data = {
            "_run_engine": {
                "projections": [{"pattern": "A", "body": "B"}],
                "input": "A",
                "max_steps": 50,
                "frozen": {"head": "op1", "tail": None}
            }
        }

        result = single_step(combined_projections, input_data)

        assert result.get("_mode") == "engine"
        assert result.get("_max_steps") == 50
        assert result.get("_frozen") == {"head": "op1", "tail": None}


# =============================================================================
# Engine Phase Transition Tests
# =============================================================================


class TestEnginePhaseTransitions:
    """Test phase transitions in the engine workflow."""

    def test_trace_done_triggers_recurrence(self, combined_projections):
        """When trace completes, engine should trigger _detect_closure."""
        # State: engine in run_trace phase with completed trace
        input_data = {
            "_mode": "engine",
            "_phase": "run_trace",
            "_projections": [{"pattern": "A", "body": "B"}],
            "_input": "A",
            "_max_steps": 100,
            "_frozen": None,
            "_trace_result": {
                "result": "B",
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "to_b"},
                    "tail": None
                },
                "stall": False
            },
            "_recurrence_result": None,
            "_exhaustion_result": None
        }

        result = single_step(combined_projections, input_data)

        # Should output _detect_closure for recurrence
        assert "_detect_closure" in result, "Should trigger recurrence detection"
        assert "_engine_context" in result, "Should preserve engine context"

    def test_recurrence_result_triggers_exhaustion(self, combined_projections):
        """When recurrence completes with closure, engine should trigger exhaustion."""
        # State: recurrence detection completed (closure found)
        input_data = {
            "closure_detected": True,
            "tau_step": 2,
            "final_result": "final_value",
            "_engine_context": {
                "frozen": None,
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "op1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "op1"},
                        "tail": None
                    }
                },
                "stall": False
            }
        }

        result = single_step(combined_projections, input_data)

        # Should output _detect_exhaustion
        assert "_detect_exhaustion" in result, "Should trigger exhaustion detection"
        assert result["_detect_exhaustion"]["tau_step"] == 2, "Should pass tau_step"

    def test_exhaustion_result_produces_final(self, combined_projections):
        """When exhaustion completes, engine should produce final result."""
        # State: exhaustion detection completed
        input_data = {
            "exhaustion_detected": True,
            "operator_to_freeze": "op1",
            "frozen": {"head": "op1", "tail": None},
            "action": "freeze",
            "_engine_recurrence": {
                "closure_detected": True,
                "tau_step": 2,
                "result": "final_value",
                "stall": False
            }
        }

        result = single_step(combined_projections, input_data)

        # Should produce engine_result
        assert "engine_result" in result, "Should produce engine_result"
        engine_result = result["engine_result"]
        assert engine_result["closure_detected"] is True
        assert engine_result["exhaustion_detected"] is True
        assert engine_result["operator_frozen"] == "op1"

    def test_unwrap_extracts_final(self, combined_projections):
        """engine.unwrap should extract the final result."""
        input_data = {
            "engine_result": {
                "value": "final_value",
                "closure_detected": True,
                "tau_step": 2,
                "exhaustion_detected": True,
                "operator_frozen": "op1",
                "frozen_set": {"head": "op1", "tail": None},
                "action": "freeze",
                "stall": False
            }
        }

        result = single_step(combined_projections, input_data)

        # Should unwrap to just the result
        assert result["value"] == "final_value"
        assert result["closure_detected"] is True
        assert result["exhaustion_detected"] is True


# =============================================================================
# Full Cycle Integration Tests
# =============================================================================


class TestFullEngineCycle:
    """Test complete engine cycles with recurrence and exhaustion.

    NOTE: The engine.trace_done projection outputs:
    {"_detect_closure": {...}, "_engine_context": {...}}

    However, recurrence.v1.json patterns expect _detect_closure at the TOP level
    without additional keys. This means the engine output format and recurrence
    input format are currently INCOMPATIBLE.

    This is a known design limitation of rcx_engine.v1.json (status: design_only).
    Full integration would require either:
    1. Updating recurrence patterns to ignore _engine_context, or
    2. Adding an engine projection to strip _engine_context before passing to recurrence

    These tests verify the CURRENT behavior (engine produces intermediate state
    that stalls on recurrence entry).
    """

    def test_engine_to_recurrence_format_documented(self, combined_projections):
        """Document: engine.trace_done output format vs recurrence input format."""
        # Engine produces: {"_detect_closure": {...}, "_engine_context": {...}}
        # Recurrence expects: {"_detect_closure": {...}} (no extra keys)

        # Start with engine state that would trigger trace_done
        input_data = {
            "_mode": "engine",
            "_phase": "run_trace",
            "_projections": [],
            "_input": "A",
            "_max_steps": 100,
            "_frozen": None,
            "_trace_result": {
                "result": "final",
                "trace": {"head": {"step": 0, "state": "A", "projection": "p1"}, "tail": None},
                "stall": False
            },
            "_recurrence_result": None,
            "_exhaustion_result": None
        }

        result = single_step(combined_projections, input_data)

        # Verify engine produces _detect_closure with _engine_context
        assert "_detect_closure" in result, "Engine should produce _detect_closure"
        assert "_engine_context" in result, "Engine should produce _engine_context"

        # Running further should stall (recurrence doesn't match this format)
        result2 = run_until_stable(combined_projections, result, max_steps=10)

        # Should stall at same state (format mismatch)
        assert "_detect_closure" in result2, \
            "Should stall at _detect_closure (recurrence patterns don't match)"

    def test_standalone_recurrence_works(self, recurrence_projections):
        """Standalone recurrence detection works with proper format."""
        # Direct recurrence input (without _engine_context)
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "p2"},
                        "tail": None
                    }
                },
                "result": "final"
            }
        }

        result = run_until_stable(recurrence_projections, input_data, max_steps=100)

        # Should complete with no closure
        assert result.get("closure_detected") is False, \
            f"Unique states should not trigger closure, got: {result}"

    def test_standalone_recurrence_closure_detected(self, recurrence_projections):
        """Standalone recurrence detects closure with proper format."""
        # Direct recurrence input with repeating state
        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "projection": "p2"},
                        "tail": {
                            "head": {"step": 2, "state": "A", "projection": "p3"},
                            "tail": None
                        }
                    }
                },
                "result": "final"
            }
        }

        result = run_until_stable(recurrence_projections, input_data, max_steps=100)

        # Should detect closure
        assert result.get("closure_detected") is True, \
            f"Repeating state should trigger closure, got: {result}"
        assert result.get("tau_step") == 2, \
            f"tau_step should be 2, got: {result.get('tau_step')}"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEngineEdgeCases:
    """Test edge cases in engine execution."""

    def test_empty_trace_produces_recurrence_entry(self, combined_projections):
        """Engine with empty trace produces _detect_closure entry."""
        input_data = {
            "_mode": "engine",
            "_phase": "run_trace",
            "_projections": [],
            "_input": "A",
            "_max_steps": 100,
            "_frozen": None,
            "_trace_result": {
                "result": "A",  # Same as input (stalled immediately)
                "trace": None,  # No steps taken
                "stall": True
            },
            "_recurrence_result": None,
            "_exhaustion_result": None
        }

        result = single_step(combined_projections, input_data)

        # Engine should produce _detect_closure entry
        assert "_detect_closure" in result, \
            f"Engine should produce _detect_closure for empty trace, got: {result}"
        assert result["_detect_closure"]["trace"] is None, \
            "Empty trace should have null trace"

    def test_already_frozen_operator(self, combined_projections):
        """Engine should handle already frozen operator."""
        # Simulate exhaustion with already frozen operator
        input_data = {
            "exhaustion_detected": False,
            "operator_to_freeze": None,
            "frozen": {"head": "op1", "tail": None},  # Already frozen
            "action": "already_frozen",
            "_engine_recurrence": {
                "closure_detected": True,
                "tau_step": 2,
                "result": "final_value",
                "stall": True
            }
        }

        result = single_step(combined_projections, input_data)

        # Should produce engine_result with already_frozen action
        assert "engine_result" in result
        assert result["engine_result"]["action"] == "already_frozen"
        assert result["engine_result"]["exhaustion_detected"] is False

    def test_pre_frozen_operators_preserved(self, combined_projections):
        """Engine should preserve pre-frozen operators from config."""
        # Init with pre-frozen operator
        input_data = {
            "_run_engine": {
                "projections": [{"pattern": "A", "body": "B"}],
                "input": "A",
                "max_steps": 100,
                "frozen": {"head": "pre_frozen_op", "tail": None}
            }
        }

        result = single_step(combined_projections, input_data)

        # Should preserve frozen list
        assert result.get("_frozen") == {"head": "pre_frozen_op", "tail": None}


# =============================================================================
# Projection Order Tests
# =============================================================================


class TestCombinedProjectionOrder:
    """Test that combined projections are in correct order."""

    def test_engine_comes_before_algorithms(self, combined_projections):
        """Engine projections must come before algorithm projections."""
        ids = [p.get("id", "unknown") for p in combined_projections]

        # Find first engine, recurrence, exhaustion projections
        engine_idx = next(i for i, id in enumerate(ids) if id.startswith("engine."))
        recurrence_idx = next(i for i, id in enumerate(ids) if id.startswith("recurrence."))
        exhaustion_idx = next(i for i, id in enumerate(ids) if id.startswith("exhaustion."))

        assert engine_idx < recurrence_idx < exhaustion_idx, (
            f"Order should be engine < recurrence < exhaustion, "
            f"got indices: engine={engine_idx}, recurrence={recurrence_idx}, exhaustion={exhaustion_idx}"
        )

    def test_combined_projection_count(self, combined_projections):
        """Combined projections should have engine + recurrence + exhaustion."""
        # engine: 6, recurrence: 9, exhaustion: 11 = 26 total
        assert len(combined_projections) == 26, \
            f"Expected 26 combined projections, got {len(combined_projections)}"


# =============================================================================
# Meta Tests
# =============================================================================


class TestEngineDesignStatus:
    """Tests for engine design status."""

    def test_engine_has_all_phases_covered(self, engine_projections):
        """Engine should have projections for all workflow phases."""
        ids = [p["id"] for p in engine_projections]

        # Must have: init, init_config, trace_done, recurrence_done, exhaustion_done, unwrap
        expected_phases = [
            "engine.init",
            "engine.init_config",
            "engine.trace_done",
            "engine.recurrence_done",
            "engine.exhaustion_done",
            "engine.unwrap"
        ]

        for phase in expected_phases:
            assert phase in ids, f"Missing projection: {phase}"

    def test_engine_projections_count(self, engine_projections):
        """Engine should have exactly 6 projections."""
        assert len(engine_projections) == 6, \
            f"Expected 6 engine projections, got {len(engine_projections)}"
