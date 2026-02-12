"""
RCX Engine Integration Tests - Full Cycle Testing.

9-agent finding (Grounding, Advisor): rcx_engine.v1.json tests only verify
individual projection patterns, not the full engine cycle:
  init → trace → recurrence → exhaustion → unwrap

Engine projections emit _boundary_request effects (algebraic effect protocol).
The host loop services these requests generically. These tests verify:
1. Each projection emits the correct _boundary_request
2. The context in each request IS the pattern for the next projection
3. Standalone recurrence/exhaustion algorithms work independently
4. Combined projection ordering is correct
"""

from __future__ import annotations

import hashlib
import json as _json

import pytest

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path


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
    seed = load_verified_seed(get_seed_path("recurrence.v2.json"))
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
# Engine Initialization Tests (_boundary_request protocol)
# =============================================================================


class TestEngineInit:
    """Test engine initialization emits _boundary_request."""

    def test_init_creates_boundary_request(self, combined_projections):
        """_run_engine should emit _boundary_request with operation: run_trace."""
        input_data = {
            "_run_engine": {
                "projections": [{"pattern": "A", "body": "B"}],
                "input": "A"
            }
        }

        result = single_step(combined_projections, input_data)

        assert "_boundary_request" in result, f"Expected _boundary_request, got: {result}"
        req = result["_boundary_request"]
        assert req["operation"] == "run_trace"
        assert req["input"]["max_steps"] == 100  # default
        assert req["context"]["_mode"] == "engine"
        assert req["context"]["_frozen"] is None
        assert req["inject_key"] == "_trace_result"

    def test_init_with_config(self, combined_projections):
        """_run_engine with config should emit _boundary_request preserving custom settings."""
        input_data = {
            "_run_engine": {
                "projections": [{"pattern": "A", "body": "B"}],
                "input": "A",
                "max_steps": 50,
                "frozen": {"head": "op1", "tail": None}
            }
        }

        result = single_step(combined_projections, input_data)

        req = result["_boundary_request"]
        assert req["operation"] == "run_trace"
        assert req["input"]["max_steps"] == 50
        assert req["context"]["_frozen"] == {"head": "op1", "tail": None}


# =============================================================================
# Engine Phase Transition Tests (_boundary_request protocol)
# =============================================================================


class TestEnginePhaseTransitions:
    """Test phase transitions via _boundary_request."""

    def test_trace_done_requests_hash(self, combined_projections):
        """When trace completes, engine should request hash_trace boundary operation."""
        # State injected by host after servicing run_trace:
        # context {_mode, _frozen} + inject_key _trace_result
        input_data = {
            "_mode": "engine",
            "_frozen": None,
            "_trace_result": {
                "result": "B",
                "trace": {
                    "head": {"step": 0, "state": "A", "projection": "to_b"},
                    "tail": None
                },
                "stall": False
            }
        }

        result = single_step(combined_projections, input_data)

        assert "_boundary_request" in result
        req = result["_boundary_request"]
        assert req["operation"] == "hash_trace"
        assert req["inject_key"] == "_hashed_trace"
        assert req["context"]["_raw_trace"] is not None

    def test_hash_done_requests_recurrence(self, engine_projections):
        """When hash completes, engine should request run_algorithm for recurrence."""
        # State injected by host after servicing hash_trace:
        # context {_mode, _result, _frozen, _stall, _raw_trace} + inject_key _hashed_trace
        input_data = {
            "_mode": "engine",
            "_result": "B",
            "_frozen": None,
            "_stall": False,
            "_raw_trace": {"head": {"step": 0, "state": "A", "projection": "to_b"}, "tail": None},
            "_hashed_trace": {"head": {"step": 0, "state": "A", "state_hash": "abc", "projection": "to_b"}, "tail": None}
        }

        result = single_step(engine_projections, input_data)

        assert "_boundary_request" in result
        req = result["_boundary_request"]
        assert req["operation"] == "run_algorithm"
        assert req["algorithm"] == "recurrence.v2.json"
        assert "_detect_closure" in req["input"]
        assert req["inject_key"] == "_recurrence_result"

    def test_recurrence_done_requests_exhaustion(self, engine_projections):
        """When recurrence completes, engine should request run_algorithm for exhaustion."""
        # State injected by host after servicing recurrence run_algorithm:
        # context {_mode, _frozen, _stall, _raw_trace} + inject_key _recurrence_result
        input_data = {
            "_mode": "engine",
            "_frozen": None,
            "_stall": False,
            "_raw_trace": {
                "head": {"step": 0, "state": "A", "projection": "op1"},
                "tail": {
                    "head": {"step": 1, "state": "B", "projection": "op1"},
                    "tail": None
                }
            },
            "_recurrence_result": {
                "closure_detected": True,
                "tau_step": 2,
                "final_result": "final_value"
            }
        }

        result = single_step(engine_projections, input_data)

        assert "_boundary_request" in result
        req = result["_boundary_request"]
        assert req["operation"] == "run_algorithm"
        assert req["algorithm"] == "exhaustion.v1.json"
        assert "_detect_exhaustion" in req["input"]
        assert req["input"]["_detect_exhaustion"]["tau_step"] == 2
        assert req["inject_key"] == "_exhaustion_result"

    def test_exhaustion_done_produces_final_result(self, engine_projections):
        """When exhaustion completes, engine should produce engine_result (no boundary request)."""
        # State injected by host after servicing exhaustion run_algorithm:
        # context {_mode, _stall, _closure_detected, _tau_step, _final_result} + inject_key _exhaustion_result
        input_data = {
            "_mode": "engine",
            "_stall": False,
            "_closure_detected": True,
            "_tau_step": 2,
            "_final_result": "final_value",
            "_exhaustion_result": {
                "exhaustion_detected": True,
                "operator_to_freeze": "op1",
                "frozen": {"head": "op1", "tail": None},
                "action": "freeze"
            }
        }

        result = single_step(engine_projections, input_data)

        assert "engine_result" in result, f"Should produce engine_result, got: {result}"
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
    """Test complete engine cycles.

    Engine projections emit _boundary_request effects. When stepping projections
    directly (without the host loop), _boundary_request stalls — no projection
    handles it. This is correct: the host loop is the effect handler.

    These tests verify:
    1. Engine produces _boundary_request that stalls for host service
    2. Standalone recurrence/exhaustion work independently
    """

    def test_boundary_request_stalls_without_host(self, combined_projections):
        """_boundary_request stalls when no host loop services it."""
        input_data = {
            "_mode": "engine",
            "_frozen": None,
            "_trace_result": {
                "result": "final",
                "trace": {"head": {"step": 0, "state": "A", "projection": "p1"}, "tail": None},
                "stall": False
            }
        }

        result = single_step(combined_projections, input_data)

        # Engine produces _boundary_request
        assert "_boundary_request" in result
        assert result["_boundary_request"]["operation"] == "hash_trace"

        # Running further should stall (no projection handles _boundary_request)
        result2 = run_until_stable(combined_projections, result, max_steps=10)
        assert "_boundary_request" in result2, \
            "Should stall at _boundary_request (host loop not present)"

    def test_standalone_recurrence_works(self, recurrence_projections):
        """Standalone recurrence detection works with proper format."""
        def _hash(state):
            return hashlib.sha256(_json.dumps(state, sort_keys=True).encode()).hexdigest()

        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "state_hash": _hash("A"), "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "state_hash": _hash("B"), "projection": "p2"},
                        "tail": None
                    }
                },
                "result": "final"
            }
        }

        result = run_until_stable(recurrence_projections, input_data, max_steps=100)

        assert result.get("closure_detected") is False, \
            f"Unique states should not trigger closure, got: {result}"

    def test_standalone_recurrence_closure_detected(self, recurrence_projections):
        """Standalone recurrence detects closure with proper format."""
        def _hash(state):
            return hashlib.sha256(_json.dumps(state, sort_keys=True).encode()).hexdigest()

        input_data = {
            "_detect_closure": {
                "trace": {
                    "head": {"step": 0, "state": "A", "state_hash": _hash("A"), "projection": "p1"},
                    "tail": {
                        "head": {"step": 1, "state": "B", "state_hash": _hash("B"), "projection": "p2"},
                        "tail": {
                            "head": {"step": 2, "state": "A", "state_hash": _hash("A"), "projection": "p3"},
                            "tail": None
                        }
                    }
                },
                "result": "final"
            }
        }

        result = run_until_stable(recurrence_projections, input_data, max_steps=100)

        assert result.get("closure_detected") is True, \
            f"Repeating state should trigger closure, got: {result}"
        assert result.get("tau_step") == 2, \
            f"tau_step should be 2, got: {result.get('tau_step')}"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEngineEdgeCases:
    """Test edge cases in engine execution."""

    def test_empty_trace_requests_hash(self, combined_projections):
        """Engine with empty trace still emits hash_trace boundary request."""
        input_data = {
            "_mode": "engine",
            "_frozen": None,
            "_trace_result": {
                "result": "A",  # Same as input (stalled immediately)
                "trace": None,  # No steps taken
                "stall": True
            }
        }

        result = single_step(combined_projections, input_data)

        assert "_boundary_request" in result
        req = result["_boundary_request"]
        assert req["operation"] == "hash_trace"
        assert req["input"] is None, "Empty trace should have null input"

    def test_already_frozen_operator(self, engine_projections):
        """Engine handles exhaustion result with already_frozen action."""
        # Exhaustion found nothing new to freeze
        input_data = {
            "_mode": "engine",
            "_stall": True,
            "_closure_detected": True,
            "_tau_step": 2,
            "_final_result": "final_value",
            "_exhaustion_result": {
                "exhaustion_detected": False,
                "operator_to_freeze": None,
                "frozen": {"head": "op1", "tail": None},
                "action": "already_frozen"
            }
        }

        result = single_step(engine_projections, input_data)

        assert "engine_result" in result
        assert result["engine_result"]["action"] == "already_frozen"
        assert result["engine_result"]["exhaustion_detected"] is False

    def test_pre_frozen_operators_preserved(self, combined_projections):
        """Engine should preserve pre-frozen operators from config."""
        input_data = {
            "_run_engine": {
                "projections": [{"pattern": "A", "body": "B"}],
                "input": "A",
                "max_steps": 100,
                "frozen": {"head": "pre_frozen_op", "tail": None}
            }
        }

        result = single_step(combined_projections, input_data)

        # Frozen is in the _boundary_request context
        assert result["_boundary_request"]["context"]["_frozen"] == {"head": "pre_frozen_op", "tail": None}


# =============================================================================
# Projection Order Tests
# =============================================================================


class TestCombinedProjectionOrder:
    """Test that combined projections are in correct order."""

    def test_engine_comes_before_algorithms(self, combined_projections):
        """Engine projections must come before algorithm projections."""
        ids = [p.get("id", "unknown") for p in combined_projections]

        engine_idx = next(i for i, id in enumerate(ids) if id.startswith("engine."))
        recurrence_idx = next(i for i, id in enumerate(ids) if id.startswith("recurrence."))
        exhaustion_idx = next(i for i, id in enumerate(ids) if id.startswith("exhaustion."))

        assert engine_idx < recurrence_idx < exhaustion_idx, (
            f"Order should be engine < recurrence < exhaustion, "
            f"got indices: engine={engine_idx}, recurrence={recurrence_idx}, exhaustion={exhaustion_idx}"
        )

    def test_combined_projection_count(self, combined_projections):
        """Combined projections should have engine + recurrence + exhaustion."""
        # engine: 7, recurrence: 9, exhaustion: 11 = 27 total
        assert len(combined_projections) == 27, \
            f"Expected 27 combined projections, got {len(combined_projections)}"


# =============================================================================
# Meta Tests
# =============================================================================


class TestEngineDesignStatus:
    """Tests for engine design status."""

    def test_engine_has_all_phases_covered(self, engine_projections):
        """Engine should have projections for all workflow phases."""
        ids = [p["id"] for p in engine_projections]

        expected_phases = [
            "engine.init",
            "engine.init_config",
            "engine.trace_done",
            "engine.hash_done",
            "engine.recurrence_done",
            "engine.exhaustion_done",
            "engine.unwrap"
        ]

        for phase in expected_phases:
            assert phase in ids, f"Missing projection: {phase}"

    def test_engine_projections_count(self, engine_projections):
        """Engine should have exactly 7 projections."""
        assert len(engine_projections) == 7, \
            f"Expected 7 engine projections, got {len(engine_projections)}"
