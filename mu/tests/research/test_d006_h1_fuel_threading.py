"""D006: H1 Structural Fuel Threading — Research Artifact

Tests H1 criteria from mu/docs/core/G8CpsFeasibility.v0.md:
  C1: Test harness demonstrates fuel-threaded step producing correct terminal
      states for 5+ canonical vectors.
  C2: Results identical to current run_mu() on same inputs.
  C3: No new bootstrap primitive introduced.

Also tests failure criteria:
  F1: Does eval_step need to inspect fuel? (violates G2 if yes)
  F2: Does fuel construction require a host loop? (circular if yes)
  F3: Performance >100x degradation?

NOT production code. This file lives in tests/research/ and is never
imported by rcx_pi/.

Evidence for: mu/docs/core/L4DecisionCard.v0.md (D006)
               mu/docs/core/G8CpsFeasibility.v0.md (H1)
"""

import ast
import inspect
import time

import pytest

pytestmark = [pytest.mark.slow]

# We import the REAL production step/run for comparison
from rcx_pi.selfhost.eval_seed import step as eval_step
from rcx_pi.selfhost.mu_type import mu_hash_cached
from rcx_pi.selfhost.step_mu import run_mu, step_mu


# ---------------------------------------------------------------------------
# Structural fuel: Mu linked-list (research-only)
# ---------------------------------------------------------------------------


def make_fuel(n: int):
    """Build a Mu linked-list of n nodes.

    NOTE: This function uses a Python for-loop to construct the fuel.
    This is H1 failure criterion F2: fuel construction itself requires
    a host loop. The circularity is real but bounded — construction is
    one-time setup, consumption is runtime.
    """
    fuel = None  # empty = fuel exhausted
    for _ in range(n):
        fuel = {"head": None, "tail": fuel}
    return fuel


def fuel_remaining(fuel) -> int:
    """Count remaining fuel nodes (for test assertions only)."""
    count = 0
    while fuel is not None:
        count += 1
        fuel = fuel.get("tail") if isinstance(fuel, dict) else None
    return count


# ---------------------------------------------------------------------------
# fuel_step / fuel_run: Structural-fuel iteration (research-only)
#
# KEY DESIGN POINT: eval_step (step_mu) is called UNCHANGED.
# Fuel management is entirely external to eval_step.
# eval_step never sees, inspects, or branches on fuel.
# This preserves G2 (no domain branching in eval_step).
# ---------------------------------------------------------------------------


def fuel_step(projections, state, fuel):
    """One step: apply projections to state, consume one fuel node.

    Returns (new_state, remaining_fuel, status).
    Status is "ok", "stall", or "fuel_exhausted".

    eval_step is called with its EXISTING signature — no fuel argument.
    """
    if fuel is None:
        return state, None, "fuel_exhausted"

    # Call the REAL eval_step — unchanged, unaware of fuel
    new_state = step_mu(projections, state)

    # Consume one fuel node (structural decrement)
    remaining = fuel.get("tail") if isinstance(fuel, dict) else None

    # Check for stall
    if mu_hash_cached(new_state) == mu_hash_cached(state):
        return new_state, remaining, "stall"

    return new_state, remaining, "ok"


def fuel_run(projections, state, fuel):
    """Run projections on state using structural fuel until stall or exhaustion.

    Returns (final_state, trace, termination_reason).
    termination_reason is "stall" or "fuel_exhausted".

    NOTE: This function uses a Python while-loop. This is NOT a reduction
    of the host loop — it replaces `for i in range(N)` with
    `while fuel is not None`. The iteration mechanism is still host code.
    H3 (negative control) predicts this is irreducible.
    """
    trace = []
    current = state
    i = 0

    while True:
        trace.append({"step": i, "value": current})
        new_state, fuel, status = fuel_step(projections, current, fuel)

        if status == "stall":
            trace.append({"step": i + 1, "value": new_state, "stall": True})
            return new_state, trace, "stall"

        if status == "fuel_exhausted":
            return current, trace, "fuel_exhausted"

        current = new_state
        i += 1

    # Unreachable — loop exits via stall or fuel_exhausted
    return current, trace, "fuel_exhausted"  # pragma: no cover


# ---------------------------------------------------------------------------
# Test Vectors (5 canonical + fuel exhaustion)
# ---------------------------------------------------------------------------

# V1: Identity stall — input matches no projection
V1_PROJECTIONS = [
    {"id": "v1.only", "pattern": {"key": "nonexistent"}, "body": {"result": "found"}}
]
V1_INPUT = {"different_key": "forty_two"}

# V2: Single match — one projection fires once, then stalls
V2_PROJECTIONS = [
    {"id": "v2.transform", "pattern": {"status": "ready"}, "body": {"status": "done", "value": "one"}}
]
V2_INPUT = {"status": "ready"}

# V3: Multi-step convergence — chains through 3 states before stall
V3_PROJECTIONS = [
    {"id": "v3.step1", "pattern": {"phase": "a"}, "body": {"phase": "b"}},
    {"id": "v3.step2", "pattern": {"phase": "b"}, "body": {"phase": "c"}},
    {"id": "v3.step3", "pattern": {"phase": "c"}, "body": {"phase": "done"}},
]
V3_INPUT = {"phase": "a"}

# V4: Fuel exhaustion — would take 10 steps but only gets 3 fuel
V4_PROJECTIONS = [
    {"id": "v4.inc", "pattern": {"n": "zero"}, "body": {"n": "one"}},
    {"id": "v4.inc2", "pattern": {"n": "one"}, "body": {"n": "two"}},
    {"id": "v4.inc3", "pattern": {"n": "two"}, "body": {"n": "three"}},
    {"id": "v4.inc4", "pattern": {"n": "three"}, "body": {"n": "four"}},
    {"id": "v4.inc5", "pattern": {"n": "four"}, "body": {"n": "five"}},
]
V4_INPUT = {"n": "zero"}
V4_FUEL = 3  # Only 3 steps, will exhaust before reaching n=5

# V5: Nested structure — complex Mu data
V5_PROJECTIONS = [
    {
        "id": "v5.unwrap",
        "pattern": {"outer": {"inner": {"value": "wrapped"}}},
        "body": {"result": "unwrapped", "depth": "two"},
    }
]
V5_INPUT = {"outer": {"inner": {"value": "wrapped"}}}


# ===========================================================================
# SUCCESS CRITERIA TESTS
# ===========================================================================


class TestH1SuccessCriteria:
    """H1 success criteria: correct results on 5+ vectors."""

    def test_v1_identity_stall(self):
        """V1: Input matches no projection -> immediate stall."""
        fuel = make_fuel(10)
        result, trace, reason = fuel_run(V1_PROJECTIONS, V1_INPUT, fuel)
        assert reason == "stall"
        assert result == V1_INPUT  # unchanged

    def test_v2_single_match(self):
        """V2: One projection fires, then stalls."""
        fuel = make_fuel(10)
        result, trace, reason = fuel_run(V2_PROJECTIONS, V2_INPUT, fuel)
        assert reason == "stall"
        assert result == {"status": "done", "value": "one"}

    def test_v3_multi_step_convergence(self):
        """V3: Three steps (a->b->c->done) then stall."""
        fuel = make_fuel(10)
        result, trace, reason = fuel_run(V3_PROJECTIONS, V3_INPUT, fuel)
        assert reason == "stall"
        assert result == {"phase": "done"}
        # Should take exactly 3 steps + 1 stall detection
        stall_entries = [t for t in trace if t.get("stall")]
        assert len(stall_entries) == 1

    def test_v4_fuel_exhaustion(self):
        """V4: Runs out of fuel before reaching terminal state."""
        fuel = make_fuel(V4_FUEL)
        result, trace, reason = fuel_run(V4_PROJECTIONS, V4_INPUT, fuel)
        assert reason == "fuel_exhausted"
        # With 3 fuel nodes, should reach "three" after three transitions.
        assert result == {"n": "three"}

    def test_v5_nested_structure(self):
        """V5: Complex nested Mu data matches and transforms correctly."""
        fuel = make_fuel(10)
        result, trace, reason = fuel_run(V5_PROJECTIONS, V5_INPUT, fuel)
        assert reason == "stall"
        assert result == {"result": "unwrapped", "depth": "two"}


class TestH1ParityWithRunMu:
    """H1 criterion 2: Results identical to current run_mu() on same inputs."""

    @pytest.mark.parametrize(
        "projections, initial, label",
        [
            (V1_PROJECTIONS, V1_INPUT, "v1_stall"),
            (V2_PROJECTIONS, V2_INPUT, "v2_single"),
            (V3_PROJECTIONS, V3_INPUT, "v3_multi"),
            (V5_PROJECTIONS, V5_INPUT, "v5_nested"),
        ],
    )
    def test_fuel_run_matches_run_mu(self, projections, initial, label):
        """fuel_run with sufficient fuel produces same result as run_mu."""
        # run_mu with generous max_steps
        mu_result, mu_trace, mu_stall = run_mu(projections, initial, max_steps=100)

        # fuel_run with generous fuel
        fuel = make_fuel(100)
        fuel_result, fuel_trace, fuel_reason = fuel_run(projections, initial, fuel)

        assert fuel_result == mu_result, (
            f"Vector {label}: fuel_run result != run_mu result\n"
            f"  fuel_run: {fuel_result}\n"
            f"  run_mu:   {mu_result}"
        )
        # Both should stall (all converge with sufficient budget)
        assert mu_stall is True
        assert fuel_reason == "stall"


class TestH1NoPrimitiveIncrease:
    """H1 criterion 3: No new bootstrap primitive introduced."""

    def test_fuel_step_calls_existing_step_mu(self):
        """fuel_step must call the existing step_mu, not a new primitive."""
        source = inspect.getsource(fuel_step)
        tree = ast.parse(source)
        calls = [
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        assert "step_mu" in calls, "fuel_step must call existing step_mu"

    def test_no_new_bootstrap_primitive_marker(self):
        """This research artifact must not introduce BOOTSTRAP_PRIMITIVE markers."""
        source_path = __file__
        with open(source_path) as f:
            content = f.read()
        assert "BOOTSTRAP_PRIMITIVE" not in content.split("test_no_new_bootstrap_primitive_marker")[0], (
            "Research artifact must not introduce new BOOTSTRAP_PRIMITIVE markers"
        )


# ===========================================================================
# FAILURE CRITERIA TESTS (documenting known limitations)
# ===========================================================================


class TestH1FailureCriteria:
    """H1 failure criteria — documenting honestly what H1 cannot achieve."""

    def test_f1_eval_step_does_not_inspect_fuel(self):
        """F1: eval_step (step_mu) must NOT inspect fuel.

        AST-verify that step_mu's source contains no reference to 'fuel',
        'head', 'tail' as variable names. This proves G2 is preserved.
        """
        source = inspect.getsource(step_mu)
        tree = ast.parse(source)
        all_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        fuel_names = all_names & {"fuel", "head", "tail", "fuel_remaining"}
        assert not fuel_names, (
            f"step_mu references fuel-related names: {fuel_names}\n"
            "This would violate G2 (no domain branching in eval_step)."
        )

    def test_f1_eval_step_signature_unchanged(self):
        """F1 corollary: eval_step signature has no fuel parameter."""
        from rcx_pi.selfhost.eval_seed import step as real_eval_step

        sig = inspect.signature(real_eval_step)
        param_names = list(sig.parameters.keys())
        assert "fuel" not in param_names, "eval_step must not accept a fuel parameter"
        assert param_names == ["projections", "input_value"], (
            f"eval_step signature changed: {param_names}"
        )

    def test_f2_fuel_construction_requires_host_loop(self):
        """F2: make_fuel uses a host for-loop — fuel construction is circular.

        This is an honest documentation of H1's limitation: building N-node
        fuel requires iteration. The host loop is relocated (from runtime to
        setup) but not eliminated.
        """
        source = inspect.getsource(make_fuel)
        tree = ast.parse(source)
        has_for = any(isinstance(node, ast.For) for node in ast.walk(tree))
        # This test EXPECTS the for-loop to exist — documenting the limitation
        assert has_for, (
            "make_fuel should use a for-loop (documenting F2: "
            "fuel construction requires host iteration)"
        )

    def test_f2_fuel_run_still_uses_host_loop(self):
        """F2 corollary: fuel_run uses a host while-loop.

        The outer iteration is still host code. We replaced
        `for i in range(N)` with `while True` + fuel check.
        This is isomorphic, not reduced.
        """
        source = inspect.getsource(fuel_run)
        tree = ast.parse(source)
        has_while = any(isinstance(node, ast.While) for node in ast.walk(tree))
        assert has_while, (
            "fuel_run should use a while-loop (documenting that "
            "iteration mechanism is still host code)"
        )


# ===========================================================================
# STRUCTURAL PROPERTIES
# ===========================================================================


class TestH1StructuralProperties:
    """Verify structural properties of fuel threading."""

    def test_fuel_is_valid_mu(self):
        """Fuel linked-list must be valid Mu data (dict/None only)."""
        from rcx_pi.selfhost.mu_type import is_mu

        fuel = make_fuel(5)
        assert is_mu(fuel), "Fuel linked-list must be valid Mu"
        assert is_mu(None), "Empty fuel (None) must be valid Mu"

    def test_fuel_consumption_is_monotonic(self):
        """Each fuel_step must consume exactly one fuel node."""
        fuel = make_fuel(5)
        remaining_counts = [fuel_remaining(fuel)]

        state = V3_INPUT
        for _ in range(5):
            state, fuel, status = fuel_step(V3_PROJECTIONS, state, fuel)
            remaining_counts.append(fuel_remaining(fuel))
            if status != "ok":
                break

        # Each step decreases fuel by exactly 1
        for i in range(1, len(remaining_counts)):
            assert remaining_counts[i] == remaining_counts[i - 1] - 1, (
                f"Fuel not monotonically decreasing: {remaining_counts}"
            )

    def test_zero_fuel_immediate_exhaustion(self):
        """Zero fuel must immediately return fuel_exhausted."""
        result, trace, reason = fuel_run(V2_PROJECTIONS, V2_INPUT, None)
        assert reason == "fuel_exhausted"
        assert result == V2_INPUT  # unchanged — no step executed

    def test_one_fuel_exactly_one_step(self):
        """One fuel node allows exactly one step."""
        fuel = make_fuel(1)
        result, trace, reason = fuel_run(V3_PROJECTIONS, V3_INPUT, fuel)
        assert reason == "fuel_exhausted"
        assert result == {"phase": "b"}  # one step: a -> b

    def test_fuel_run_loc_count(self):
        """fuel_run + fuel_step must be ≤50 LOC total (research budget)."""
        run_lines = len([
            line for line in inspect.getsource(fuel_run).splitlines()
            if line.strip() and not line.strip().startswith("#")
            and not line.strip().startswith('"""')
            and not line.strip().startswith("'")
        ])
        step_lines = len([
            line for line in inspect.getsource(fuel_step).splitlines()
            if line.strip() and not line.strip().startswith("#")
            and not line.strip().startswith('"""')
            and not line.strip().startswith("'")
        ])
        total = run_lines + step_lines
        assert total <= 50, f"fuel_run + fuel_step = {total} LOC (threshold: 50)"
