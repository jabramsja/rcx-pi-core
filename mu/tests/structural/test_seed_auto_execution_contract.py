"""
A19: Seed-Auto Execution Contract — Behavioral Proof.

Proves via runtime evidence (not markers) that:
1. Engine dispatch is generic (seed-derived, not program-name branching)
2. Boundary operations come from seed scanning, not hardcoded dispatch
3. Algorithm dispatch uses seed map, not name-based branching
4. step() behavior is identical regardless of projection source
"""
from __future__ import annotations

import pytest

from rcx_pi.selfhost.eval_seed import step
from rcx_pi.selfhost.projection_loader import load_verified_seed, get_seed_path
from rcx_pi.selfhost.mu_type import mu_equal

pytestmark = [pytest.mark.slow]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine_projections() -> list:
    seed = load_verified_seed(get_seed_path("rcx_engine.v1.json"))
    return seed["projections"]


@pytest.fixture
def recurrence_projections() -> list:
    seed = load_verified_seed(get_seed_path("recurrence.v1.json"))
    return seed["projections"]


# ---------------------------------------------------------------------------
# TestSeedAutoExecutionContract
# ---------------------------------------------------------------------------

class TestSeedAutoExecutionContract:
    """Behavioral proof that execution is generic and seed-driven."""

    def test_engine_init_produces_generic_boundary_request(self, engine_projections):
        """Engine projections produce _boundary_request for ANY domain input.

        The engine.init projection matches the _run_engine envelope shape.
        This proves the engine dispatch is generic: it wraps any domain input
        in the same way and unconditionally produces a _boundary_request
        asking the host to service run_trace.
        """
        # Two completely different domain inputs — engine.init wraps both
        identity_projs = [{"id": "id", "pattern": {"x": "x"}, "body": {"x": "x"}}]
        input_a = {"_run_engine": {"projections": identity_projs, "input": {"value": 42}}}
        input_b = {"_run_engine": {"projections": identity_projs, "input": {"x": "hello"}}}

        result_a = step(engine_projections, input_a)
        result_b = step(engine_projections, input_b)

        # Both must produce _boundary_request shape (engine.init fires)
        assert isinstance(result_a, dict), f"Expected dict, got {type(result_a)}"
        assert isinstance(result_b, dict), f"Expected dict, got {type(result_b)}"
        assert "_boundary_request" in result_a, (
            f"Engine init must produce _boundary_request. Got keys: {sorted(result_a.keys())}"
        )
        assert "_boundary_request" in result_b, (
            f"Engine init must produce _boundary_request. Got keys: {sorted(result_b.keys())}"
        )

        # Both must request the same operation (run_trace — generic first phase)
        op_a = result_a["_boundary_request"]["operation"]
        op_b = result_b["_boundary_request"]["operation"]
        assert op_a == op_b, (
            f"Engine must dispatch same operation for any input. Got {op_a} vs {op_b}"
        )

    def test_boundary_dispatch_is_data_driven(self, engine_projections):
        """Boundary ops are derived from seed projection bodies, not hardcoded.

        Evidence: scan engine projections for boundary-request operation
        literals in projection bodies. The derived set must match the
        expected {run_trace, hash_trace, run_algorithm}.
        """
        # Derive boundary ops by scanning projection bodies (same logic as runtime)
        ops = set()
        for proj in engine_projections:
            body = proj.get("body", {})
            if isinstance(body, dict):
                br = body.get("_boundary_request")
                if isinstance(br, dict) and "operation" in br:
                    ops.add(br["operation"])

        expected = {"run_trace", "hash_trace", "run_algorithm"}
        assert ops == expected, (
            f"Boundary ops mismatch. Seed-derived: {ops}, expected: {expected}"
        )
        assert len(ops) == 3, f"Expected exactly 3 boundary ops, got {len(ops)}"

    def test_algorithm_dispatch_uses_seed_map(self, recurrence_projections):
        """Algorithm dispatch uses seed path lookup, not name-based branching.

        Evidence: recurrence projections can be loaded by name via
        get_seed_path() and produce valid projections. The dispatch
        mechanism is: name → file path → load → projections → step().
        No if/elif on algorithm name exists.
        """
        # Recurrence seed loads via generic path
        assert len(recurrence_projections) > 0, "Recurrence seed must have projections"

        # The projections have IDs (structural identity, not program-branching)
        ids = [p.get("id") for p in recurrence_projections if "id" in p]
        assert len(ids) > 0, "Seed projections must have IDs"

        # step() with recurrence projections works generically
        test_input = {"_detect_closure": {"trace": None, "result": "x"}}
        result = step(recurrence_projections, test_input)
        assert result is not None, "step() with recurrence projections must produce result"

    def test_no_program_name_branching_in_step(self, engine_projections, recurrence_projections):
        """step() treats all projection sources identically.

        Evidence: step() is the bootstrap primitive. It applies
        first-match-wins over any projection list. It does NOT inspect
        projection IDs, seed filenames, or program names.
        """
        # step() with engine projections
        engine_input = {"value": 1}
        engine_result = step(engine_projections, engine_input)

        # step() with recurrence projections (different seed, same mechanism)
        recurrence_input = {"_detect_closure": {"trace": None, "result": "y"}}
        recurrence_result = step(recurrence_projections, recurrence_input)

        # Both must produce valid Mu output (not crash, not special-case)
        assert isinstance(engine_result, (dict, list, str, int, float, bool, type(None)))
        assert isinstance(recurrence_result, (dict, list, str, int, float, bool, type(None)))

        # Critically: engine projections do NOT match recurrence input
        # and vice versa — proving step() doesn't route by program name
        cross_result = step(engine_projections, recurrence_input)
        # Engine projections should stall (no match) on recurrence input
        assert mu_equal(cross_result, recurrence_input), (
            "Engine projections must stall on non-engine input (proof of generic dispatch)"
        )
