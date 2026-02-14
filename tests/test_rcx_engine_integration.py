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
from rcx_pi.selfhost.step_mu import KERNEL_RESERVED_FIELDS, run_engine_pipeline
from tests.conftest import run_until_stable


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
            "_config": {"projections": [{"pattern": "A", "body": "B"}], "max_steps": 100},
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
            "_config": {"projections": [{"pattern": "A", "body": "B"}], "max_steps": 100},
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
            "_config": {"projections": [{"pattern": "A", "body": "B"}], "max_steps": 100},
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
        """When exhaustion completes (non-freeze), engine should produce engine_result."""
        # State injected by host after servicing exhaustion run_algorithm:
        # context {_mode, _stall, _closure_detected, _tau_step, _final_result, _config} + inject_key _exhaustion_result
        # Note: action=freeze now produces trampoline (tested in TestLoopTrampolineProjectionLevel)
        input_data = {
            "_mode": "engine",
            "_stall": False,
            "_closure_detected": True,
            "_tau_step": 2,
            "_final_result": "final_value",
            "_config": {"projections": [{"pattern": "A", "body": "B"}], "max_steps": 100},
            "_exhaustion_result": {
                "exhaustion_detected": False,
                "operator_to_freeze": None,
                "frozen": None,
                "action": "continue"
            }
        }

        result = single_step(engine_projections, input_data)

        assert "engine_result" in result, f"Should produce engine_result, got: {result}"
        engine_result = result["engine_result"]
        assert engine_result["closure_detected"] is True
        assert engine_result["action"] == "continue"

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
            "_config": {"projections": [{"pattern": "A", "body": "B"}], "max_steps": 100},
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
            "_config": {"projections": [{"pattern": "A", "body": "B"}], "max_steps": 100},
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
            "_config": {"projections": [{"pattern": "A", "body": "B"}], "max_steps": 100},
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
        # engine: 11, recurrence: 9, exhaustion: 11 = 31 total
        assert len(combined_projections) == 31, \
            f"Expected 31 combined projections, got {len(combined_projections)}"


# =============================================================================
# E1: Implicit Fix Failure (GAP-04-FIX evidence)
# =============================================================================


class TestFixIntegrationEvidence:
    """E1→E4 evidence: prove the engine Fix mechanism works for stalled states.

    Originally E1 tests proved GAP-04-FIX was real (stall with no fix).
    After E4 integration, Fix is wired into the engine pipeline via
    engine.hash_done_fix → fix.v1.json → engine.fix_done_applied/none.
    These tests now prove the gap is CLOSED.

    Contract ref: docs/core/EngineNewFixContract.v0.md
    """

    # A structured graph that deterministically stalls under identity projection.
    # Fix(G) adds a minimal edge to break the structural stall.
    STALL_INPUT = {
        "graph": {"vertices": [1, 2], "edges": [{"src": 1, "dst": 2}]},
    }

    # Identity projection: maps any input to itself. Guarantees stall.
    IDENTITY_PROJS = [
        {"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}},
    ]

    def test_stall_with_fix_is_perturbed(self):
        """Engine stalls, Fix applies, and value is perturbed.

        Proves: engine.hash_done_fix dispatches to fix.v1.json when stall=true.
        fix.edge_add prepends a fix edge, breaking structural identity.
        engine.fix_done_applied forwards the fixed state with stall=false.
        """
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.mu_type import mu_hash

        result = run_engine_pipeline(
            self.IDENTITY_PROJS,
            self.STALL_INPUT,
            max_steps=5,
        )

        # Fix broke the stall — stall is now False
        assert result["stall"] is False, (
            f"Expected stall=False after Fix applied, got: {result}"
        )

        # Value is perturbed — fix edge was prepended
        assert result["value"] != self.STALL_INPUT, (
            f"Expected fixed value to differ from input.\n"
            f"  Input:    {self.STALL_INPUT}\n"
            f"  Returned: {result['value']}"
        )

        # Hash-level confirmation: structural change occurred
        assert mu_hash(result["value"]) != mu_hash(self.STALL_INPUT), (
            "Fixed value hash should differ from input hash — fix was applied"
        )

    def test_fix_result_has_engine_fields(self):
        """Engine result after Fix contains all standard engine_result fields.

        After Fix, the value flows through recurrence and exhaustion as normal.
        The engine_result must still contain all standard fields.
        """
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.mu_type import mu_hash

        result = run_engine_pipeline(
            self.IDENTITY_PROJS,
            self.STALL_INPUT,
            max_steps=5,
        )

        # All standard engine_result fields present
        assert "value" in result, "engine_result must have 'value'"
        assert "stall" in result, "engine_result must have 'stall'"
        assert "tau_step" in result, "engine_result must have 'tau_step'"
        assert "closure_detected" in result, "engine_result must have 'closure_detected'"

        # tau_step is valid
        tau_step = result["tau_step"]
        assert isinstance(tau_step, int) and tau_step >= 0, (
            f"tau_step must be a non-negative int, got: {tau_step!r}"
        )

        # mu_hash of value is computable (valid Mu structure)
        h = mu_hash(result["value"])
        assert isinstance(h, str) and len(h) == 64, (
            f"value must be hashable to 64-char hex, got: {h!r}"
        )


class TestFixSeedExecution:
    """Smoke tests: fix.v1.json executes through algorithm runtime.

    Proves the remediated seed (v1.0.1, non-underscore routing keys)
    runs through run_algorithm_meta_circular for all 3 routing paths.
    """

    @pytest.fixture
    def fix_projections(self):
        seed = load_verified_seed(get_seed_path("fix.v1.json"))
        return seed["projections"]

    def _run_fix(self, fix_projections, stalled_state):
        from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
        from rcx_pi.selfhost.mu_type import mu_hash
        fix_input = {
            "apply_fix": {
                "stalled_state": stalled_state,
                "stall_hash": "abc123",
                "tau_step": 1,
                "engine_iteration": 0,
            }
        }
        # Fix is a 2-step pipeline (init → route), loop until stall
        current = fix_input
        for _ in range(5):
            result = run_algorithm_meta_circular(fix_projections, current)
            if mu_hash(result) == mu_hash(current):
                break
            current = result
        return current

    def test_fix_edge_add_for_graph_with_edges(self, fix_projections):
        """Graph with vertices+edges routes to fix.edge_add."""
        reset_step_budget()
        state = {"graph": {"vertices": [1, 2], "edges": [{"src": 1, "dst": 2}]}}
        result = self._run_fix(fix_projections, state)
        assert result["fix_applied"] is True
        assert result["fix_type"] == "edge_add"
        assert "fixed_state" in result

    def test_fix_vertex_add_for_graph_without_edges(self, fix_projections):
        """Graph without edges routes to fix.vertex_add."""
        reset_step_budget()
        state = {"graph": {"vertices": [1, 2, 3]}}
        result = self._run_fix(fix_projections, state)
        assert result["fix_applied"] is True
        assert result["fix_type"] == "vertex_add"
        assert "fixed_state" in result

    def test_fix_pass_through_for_non_graph(self, fix_projections):
        """Non-graph state routes to fix.pass_through."""
        reset_step_budget()
        state = {"value": 42, "status": "stalled"}
        result = self._run_fix(fix_projections, state)
        assert result["fix_applied"] is False
        assert result["fix_type"] == "none"
        assert result["fixed_state"] == state


class TestEngineFixIntegration:
    """E4: Verify fix.v1.json is wired into the engine pipeline."""

    # Identity projection guarantees stall — triggers the fix path
    IDENTITY_PROJS = [
        {"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}},
    ]

    def test_stall_graph_routes_through_fix(self):
        """Stalled graph state triggers Fix and returns perturbed value."""
        from rcx_pi.selfhost.step_mu import run_engine_pipeline
        from rcx_pi.selfhost.mu_type import mu_hash

        graph_input = {"graph": {"vertices": [1, 2], "edges": [{"src": 1, "dst": 2}]}}
        reset_step_budget()
        result = run_engine_pipeline(
            self.IDENTITY_PROJS, graph_input, max_steps=5,
        )
        # Fix broke the stall — engine.fix_done_applied sets _stall: false
        assert result["stall"] is False, (
            f"Fix should break the stall, got stall={result['stall']}"
        )
        # Value should be DIFFERENT from input (fix edge was prepended)
        assert result["value"] != graph_input, (
            "Fix should perturb the stalled value"
        )
        assert mu_hash(result["value"]) != mu_hash(graph_input), (
            "Fixed value hash should differ from input hash"
        )

    def test_pass_through_fix_preserves_value(self):
        """Non-graph stalled state passes through Fix unchanged."""
        from rcx_pi.selfhost.step_mu import run_engine_pipeline

        scalar_input = {"value": 42, "status": "test"}
        reset_step_budget()
        result = run_engine_pipeline(
            self.IDENTITY_PROJS, scalar_input, max_steps=5,
        )
        assert result["stall"] is True
        # Non-graph: fix.pass_through returns value unchanged
        assert result["value"] == scalar_input

    def test_non_stall_path_still_works(self):
        """Non-stalling input bypasses Fix path entirely."""
        from rcx_pi.selfhost.step_mu import run_engine_pipeline

        # Projection that transforms input — no stall
        projs = [
            {"id": "double", "pattern": {"op": "double", "value": {"var": "n"}},
             "body": {"result": {"var": "n"}, "doubled": {"var": "n"}}},
        ]
        reset_step_budget()
        result = run_engine_pipeline(projs, {"op": "double", "value": 42}, max_steps=10)
        assert result["stall"] is True  # stalls after one transform
        assert result["value"] == {"result": 42, "doubled": 42}


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
            "engine.hash_done_fix",
            "engine.hash_done",
            "engine.fix_done_applied",
            "engine.fix_done_none",
            "engine.recurrence_done",
            "engine.exhaustion_done_freeze",
            "engine.exhaustion_done_terminal",
            "engine.unwrap"
        ]

        for phase in expected_phases:
            assert phase in ids, f"Missing projection: {phase}"

    def test_engine_projections_count(self, engine_projections):
        """Engine should have exactly 11 projections."""
        assert len(engine_projections) == 11, \
            f"Expected 11 engine projections, got {len(engine_projections)}"


# =============================================================================
# GAP-10-LOOP: Structural Iteration Tests (E1/E3)
# =============================================================================


class TestLoopTrampolineProjectionLevel:
    """E1 gap proof + E3 invariant tests for GAP-10-LOOP trampoline.

    Tests at projection level: step engine projections once on crafted states.
    Proves the structural loop-back decision works correctly.
    """

    TEST_PROJS = [{"id": "test.proj", "pattern": {}, "body": {}}]

    @pytest.fixture
    def engine_projections(self) -> list:
        seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
        return seed["projections"]

    def test_freeze_triggers_reentry(self, engine_projections):
        """E1/L2: action=freeze produces _run_engine trampoline (gap proof)."""
        reset_step_budget()
        state = {
            "_mode": "engine",
            "_stall": False,
            "_closure_detected": True,
            "_tau_step": 5,
            "_final_result": {"computed": "result"},
            "_config": {
                "projections": self.TEST_PROJS,
                "max_steps": 100
            },
            "_exhaustion_result": {
                "exhaustion_detected": True,
                "operator_to_freeze": "op1",
                "frozen": {"head": "op1", "tail": None},
                "action": "freeze"
            }
        }
        result = step(engine_projections, state)
        # Must produce _run_engine (trampoline re-entry), NOT engine_result (terminal)
        assert "_run_engine" in result, \
            f"action=freeze must produce _run_engine, got keys: {sorted(result.keys())}"
        assert "engine_result" not in result, \
            "action=freeze must NOT produce engine_result"
        # Re-entry envelope carries correct values
        re_entry = result["_run_engine"]
        assert re_entry["projections"] == self.TEST_PROJS
        assert re_entry["input"] == {"computed": "result"}
        assert re_entry["max_steps"] == 100
        assert re_entry["frozen"] == {"head": "op1", "tail": None}

    def test_continue_produces_terminal(self, engine_projections):
        """L2: action=continue produces engine_result (terminal, not re-entry)."""
        reset_step_budget()
        state = {
            "_mode": "engine",
            "_stall": False,
            "_closure_detected": False,
            "_tau_step": None,
            "_final_result": {"value": 42},
            "_config": {
                "projections": self.TEST_PROJS,
                "max_steps": 100
            },
            "_exhaustion_result": {
                "exhaustion_detected": False,
                "operator_to_freeze": None,
                "frozen": None,
                "action": "continue"
            }
        }
        result = step(engine_projections, state)
        assert "engine_result" in result, \
            f"action=continue must produce engine_result, got keys: {sorted(result.keys())}"
        assert "_run_engine" not in result

    def test_already_frozen_produces_terminal(self, engine_projections):
        """L2: action=already_frozen produces engine_result (terminal)."""
        reset_step_budget()
        state = {
            "_mode": "engine",
            "_stall": False,
            "_closure_detected": True,
            "_tau_step": 3,
            "_final_result": {"value": 99},
            "_config": {
                "projections": self.TEST_PROJS,
                "max_steps": 50
            },
            "_exhaustion_result": {
                "exhaustion_detected": True,
                "operator_to_freeze": "op1",
                "frozen": {"head": "op1", "tail": None},
                "action": "already_frozen"
            }
        }
        result = step(engine_projections, state)
        assert "engine_result" in result
        assert "_run_engine" not in result

    def test_config_not_in_terminal_output(self, engine_projections):
        """L1: _config must NOT appear in terminal engine_result output."""
        reset_step_budget()
        state = {
            "_mode": "engine",
            "_stall": False,
            "_closure_detected": False,
            "_tau_step": None,
            "_final_result": {"value": 42},
            "_config": {
                "projections": self.TEST_PROJS,
                "max_steps": 100
            },
            "_exhaustion_result": {
                "exhaustion_detected": False,
                "operator_to_freeze": None,
                "frozen": None,
                "action": "continue"
            }
        }
        result = step(engine_projections, state)
        engine_result = result["engine_result"]
        assert "_config" not in engine_result, \
            "_config must be stripped from terminal engine_result"

    def test_terminal_shape_unchanged(self, engine_projections):
        """L3: terminal engine_result has exactly 8 keys (unchanged contract)."""
        reset_step_budget()
        state = {
            "_mode": "engine",
            "_stall": True,
            "_closure_detected": True,
            "_tau_step": 5,
            "_final_result": {"value": 42},
            "_config": {
                "projections": self.TEST_PROJS,
                "max_steps": 100
            },
            "_exhaustion_result": {
                "exhaustion_detected": True,
                "operator_to_freeze": "op1",
                "frozen": {"head": "op1", "tail": None},
                "action": "already_frozen"
            }
        }
        result = step(engine_projections, state)
        engine_result = result["engine_result"]
        expected_keys = {
            "value", "closure_detected", "tau_step", "exhaustion_detected",
            "operator_frozen", "frozen_set", "action", "stall",
        }
        assert set(engine_result.keys()) == expected_keys, \
            f"Terminal shape mismatch: {sorted(engine_result.keys())}"

    def test_config_not_kernel_reserved(self):
        """L6: _config is not a kernel-reserved field."""
        assert "_config" not in KERNEL_RESERVED_FIELDS, \
            "_config must not be kernel-reserved (would block context carry-through)"

    def test_freeze_reentry_hits_init_config(self, engine_projections):
        """L2: freeze trampoline output matches engine.init_config pattern."""
        reset_step_budget()
        # Craft freeze state
        state = {
            "_mode": "engine",
            "_stall": False,
            "_closure_detected": True,
            "_tau_step": 5,
            "_final_result": {"computed": "result"},
            "_config": {
                "projections": self.TEST_PROJS,
                "max_steps": 100
            },
            "_exhaustion_result": {
                "exhaustion_detected": True,
                "operator_to_freeze": "op1",
                "frozen": {"head": "op1", "tail": None},
                "action": "freeze"
            }
        }
        # Step 1: freeze → _run_engine
        trampoline = step(engine_projections, state)
        assert "_run_engine" in trampoline
        # Step 2: _run_engine → engine.init_config → _boundary_request
        reentry = step(engine_projections, trampoline)
        assert "_boundary_request" in reentry, \
            f"Trampoline output must trigger engine.init_config → _boundary_request, got: {sorted(reentry.keys())}"
        assert reentry["_boundary_request"]["operation"] == "run_trace"


class TestLoopPipelineLevel:
    """E3 invariant tests at pipeline level (run_engine_pipeline).

    Tests use identity projections + graph input to trigger the full
    engine cycle including fix, recurrence, exhaustion. Verifies the
    trampoline works end-to-end through the host effect handler loop.
    """

    IDENTITY_PROJS = [{"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}}]

    @pytest.mark.slow
    def test_pipeline_produces_terminal_result(self):
        """L3/L5: pipeline produces terminal result within iteration bounds."""
        result = run_engine_pipeline(
            self.IDENTITY_PROJS,
            {"value": 42},
            max_steps=10,
            max_engine_iterations=20,
        )
        # Must produce terminal result (8 keys)
        expected_keys = {
            "value", "closure_detected", "tau_step", "exhaustion_detected",
            "operator_frozen", "frozen_set", "action", "stall",
        }
        assert set(result.keys()) == expected_keys, \
            f"Pipeline result shape mismatch: {sorted(result.keys())}"
        # _config must not leak into terminal result
        assert "_config" not in result
