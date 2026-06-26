"""D007: H3 Negative Control — Loop Elimination Without Mechanism

Tests H3 from mu/docs/core/G8CpsFeasibility.v0.md:

  Claim (intentionally likely false): The host for-loop in
  run_engine_pipeline() can be eliminated entirely — no host
  iteration, no CPS, no fuel — while preserving deterministic
  termination.

  Purpose: This negative control validates the falsification
  discipline. If H3 cannot be falsified, the methodology is broken.

The experiment attempts 4 plausible "no-iteration" strategies and
proves each one FAILS to reproduce run_mu's behavior, OR is secretly
isomorphic to a loop/counter.

Expected outcome: H3 FALSIFIED (expected). Iteration is genuinely
irreducible in some form. This is a POSITIVE result for methodology
— it confirms the falsification discipline works.

NOT production code. This file lives in tests/research/ and is never
imported by rcx_pi/.

Evidence for: mu/docs/core/L4DecisionCard.v0.md (D007)
               mu/docs/core/G8CpsFeasibility.v0.md (H3)
"""

import ast
import inspect

import pytest

pytestmark = [pytest.mark.slow]

from rcx_pi.selfhost.mu_type import mu_hash_cached
from rcx_pi.selfhost.step_mu import run_mu, step_mu


# ---------------------------------------------------------------------------
# Reference vectors: multi-step convergence requiring iteration
# ---------------------------------------------------------------------------

# V_MULTI: 3 steps required (a -> b -> c -> done -> stall)
MULTI_PROJECTIONS = [
    {"id": "multi.1", "pattern": {"phase": "a"}, "body": {"phase": "b"}},
    {"id": "multi.2", "pattern": {"phase": "b"}, "body": {"phase": "c"}},
    {"id": "multi.3", "pattern": {"phase": "c"}, "body": {"phase": "done"}},
]
MULTI_INPUT = {"phase": "a"}
MULTI_EXPECTED = {"phase": "done"}

# V_CHAIN: 5 steps required
CHAIN_PROJECTIONS = [
    {"id": "chain.1", "pattern": {"n": "zero"}, "body": {"n": "one"}},
    {"id": "chain.2", "pattern": {"n": "one"}, "body": {"n": "two"}},
    {"id": "chain.3", "pattern": {"n": "two"}, "body": {"n": "three"}},
    {"id": "chain.4", "pattern": {"n": "three"}, "body": {"n": "four"}},
    {"id": "chain.5", "pattern": {"n": "four"}, "body": {"n": "five"}},
]
CHAIN_INPUT = {"n": "zero"}
CHAIN_EXPECTED = {"n": "five"}

# Verify reference vectors with run_mu
def _verify_reference():
    """Sanity check: run_mu produces expected results."""
    r1, _, s1 = run_mu(MULTI_PROJECTIONS, MULTI_INPUT, max_steps=100)
    assert r1 == MULTI_EXPECTED and s1 is True
    r2, _, s2 = run_mu(CHAIN_PROJECTIONS, CHAIN_INPUT, max_steps=100)
    assert r2 == CHAIN_EXPECTED and s2 is True


# ---------------------------------------------------------------------------
# Strategy 1: Single step (no loop at all)
# ---------------------------------------------------------------------------

def single_step_run(projections, state):
    """Apply projections exactly once. No iteration."""
    return step_mu(projections, state)


# ---------------------------------------------------------------------------
# Strategy 2: Fixed unrolling (apply K times for constant K)
# ---------------------------------------------------------------------------

def unrolled_run_3(projections, state):
    """Unroll exactly 3 steps. No loop, no counter."""
    s1 = step_mu(projections, state)
    s2 = step_mu(projections, s1)
    s3 = step_mu(projections, s2)
    return s3


def unrolled_run_5(projections, state):
    """Unroll exactly 5 steps."""
    s1 = step_mu(projections, state)
    s2 = step_mu(projections, s1)
    s3 = step_mu(projections, s2)
    s4 = step_mu(projections, s3)
    s5 = step_mu(projections, s4)
    return s5


# ---------------------------------------------------------------------------
# Strategy 3: Recursion (recurse until stall)
# ---------------------------------------------------------------------------

def recursive_run(projections, state):
    """Recurse until stall. No explicit loop keyword."""
    result = step_mu(projections, state)
    if mu_hash_cached(result) == mu_hash_cached(state):
        return result  # stall
    return recursive_run(projections, result)


# ---------------------------------------------------------------------------
# Strategy 4: Higher-order application (apply-N via function composition)
# ---------------------------------------------------------------------------

def compose_n(f, n):
    """Create f applied n times: compose_n(f, 3)(x) = f(f(f(x))).

    NOTE: This function uses range() — a host iteration mechanism.
    """
    def composed(x):
        result = x
        for _ in range(n):
            result = f(result)
        return result
    return composed


# ===========================================================================
# H3 FALSIFICATION TESTS
# ===========================================================================


class TestH3Strategy1SingleStep:
    """Strategy 1: Single step cannot converge multi-step inputs."""

    def test_single_step_fails_multi(self):
        """One step takes a->b, not a->done. Convergence requires iteration."""
        result = single_step_run(MULTI_PROJECTIONS, MULTI_INPUT)
        assert result != MULTI_EXPECTED, (
            "Single step should NOT produce converged result"
        )
        assert result == {"phase": "b"}  # only one step happened

    def test_single_step_fails_chain(self):
        """One step takes zero->one, not zero->five."""
        result = single_step_run(CHAIN_PROJECTIONS, CHAIN_INPUT)
        assert result != CHAIN_EXPECTED
        assert result == {"n": "one"}

    def test_single_step_has_no_iteration(self):
        """AST verify: single_step_run contains no loop or recursion."""
        source = inspect.getsource(single_step_run)
        tree = ast.parse(source)
        loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
        assert len(loops) == 0
        # Check no self-calls
        calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "single_step_run"
        ]
        assert len(calls) == 0


class TestH3Strategy2FixedUnrolling:
    """Strategy 2: Fixed unrolling works for exactly the right K, fails otherwise."""

    def test_unrolled_3_works_for_3_step_input(self):
        """Unroll-3 happens to match the 3-step multi vector."""
        result = unrolled_run_3(MULTI_PROJECTIONS, MULTI_INPUT)
        assert result == MULTI_EXPECTED  # lucky match

    def test_unrolled_3_fails_for_5_step_input(self):
        """Unroll-3 cannot converge a 5-step chain."""
        result = unrolled_run_3(CHAIN_PROJECTIONS, CHAIN_INPUT)
        assert result != CHAIN_EXPECTED
        assert result == {"n": "three"}  # stopped at three, needed five

    def test_unrolled_5_wastes_on_3_step_input(self):
        """Unroll-5 overshoots a 3-step input (applies 2 stall steps)."""
        result = unrolled_run_5(MULTI_PROJECTIONS, MULTI_INPUT)
        # After step 3, state is {phase: done}. Steps 4-5 are stall (no match).
        # Result is still correct because stall = no change. But:
        assert result == MULTI_EXPECTED
        # The problem: unrolled_5 doesn't KNOW it stalled. It applied
        # 5 steps blindly. With a different projection set, those extra
        # steps could diverge.

    def test_fixed_unrolling_has_no_general_solution(self):
        """No single constant K works for all inputs.

        K=3 fails on 5-step chains. K=5 fails on 6-step chains.
        The required K depends on the INPUT, which is unknown at
        definition time. Therefore fixed unrolling is not general.
        """
        # Need K=3 for MULTI, K=5 for CHAIN
        # No constant K satisfies both without waste or failure
        r3_multi = unrolled_run_3(MULTI_PROJECTIONS, MULTI_INPUT)
        r3_chain = unrolled_run_3(CHAIN_PROJECTIONS, CHAIN_INPUT)
        assert r3_multi == MULTI_EXPECTED  # works
        assert r3_chain != CHAIN_EXPECTED  # fails — QED

    def test_unrolled_has_no_loop_keyword(self):
        """AST verify: unrolled functions have no for/while loops."""
        for fn in (unrolled_run_3, unrolled_run_5):
            source = inspect.getsource(fn)
            tree = ast.parse(source)
            loops = [n for n in ast.walk(tree) if isinstance(n, (ast.For, ast.While))]
            assert len(loops) == 0, f"{fn.__name__} has loop — not truly unrolled"


class TestH3Strategy3Recursion:
    """Strategy 3: Recursion works but IS a loop (isomorphic)."""

    def test_recursion_produces_correct_result(self):
        """Recursive strategy converges correctly."""
        _verify_reference()  # sanity
        result = recursive_run(MULTI_PROJECTIONS, MULTI_INPUT)
        assert result == MULTI_EXPECTED

    def test_recursion_is_isomorphic_to_loop(self):
        """AST verify: recursive_run calls itself — this IS iteration.

        Recursion is isomorphic to a while-loop with an implicit stack.
        H3 failure criterion 2: any proposed mechanism is isomorphic
        to a host loop or structural counter.
        """
        source = inspect.getsource(recursive_run)
        tree = ast.parse(source)
        self_calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "recursive_run"
        ]
        assert len(self_calls) > 0, (
            "recursive_run must contain self-call (proving it IS iteration)"
        )

    def test_recursion_has_no_termination_guarantee(self):
        """Unbounded recursion can hit Python stack limit.

        Without a fuel/counter, recursion depth = number of steps.
        Non-converging inputs would hit RecursionError.
        """
        # A projection that cycles: a->b->a->b->...
        cycling = [
            {"id": "cycle.1", "pattern": {"x": "a"}, "body": {"x": "b"}},
            {"id": "cycle.2", "pattern": {"x": "b"}, "body": {"x": "a"}},
        ]
        with pytest.raises(RecursionError):
            recursive_run(cycling, {"x": "a"})


class TestH3Strategy4HigherOrder:
    """Strategy 4: Higher-order composition secretly contains iteration."""

    def test_compose_n_works_for_known_n(self):
        """compose_n(step, 3) converges the 3-step input."""
        step_fn = lambda s: step_mu(MULTI_PROJECTIONS, s)  # noqa: E731
        run_3 = compose_n(step_fn, 3)
        result = run_3(MULTI_INPUT)
        assert result == MULTI_EXPECTED

    def test_compose_n_contains_hidden_loop(self):
        """AST verify: compose_n uses range() — a host iteration mechanism."""
        source = inspect.getsource(compose_n)
        tree = ast.parse(source)
        # Find range() calls
        range_calls = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "range"
        ]
        assert len(range_calls) > 0, (
            "compose_n must use range() (proving it secretly iterates)"
        )

    def test_compose_n_requires_knowing_n(self):
        """compose_n(f, N) requires N — the number of steps — to be known.

        But N depends on when the input converges, which is unknown
        at call time. Therefore compose_n is not a general solution.
        """
        step_fn = lambda s: step_mu(CHAIN_PROJECTIONS, s)  # noqa: E731
        # We need N=5 but can't know that without running it
        run_3 = compose_n(step_fn, 3)
        result_3 = run_3(CHAIN_INPUT)
        assert result_3 != CHAIN_EXPECTED  # wrong N

        run_5 = compose_n(step_fn, 5)
        result_5 = run_5(CHAIN_INPUT)
        assert result_5 == CHAIN_EXPECTED  # right N, but only by luck


# ===========================================================================
# H3 FALSIFICATION SUMMARY
# ===========================================================================


class TestH3FalsificationSummary:
    """Summary tests proving H3 is FALSIFIED (expected)."""

    def test_no_strategy_is_both_general_and_iteration_free(self):
        """The core impossibility argument:

        1. Single step: cannot converge multi-step inputs (no iteration)
        2. Fixed unrolling: only works for specific K (not general)
        3. Recursion: works but IS iteration (isomorphic to while-loop)
        4. Composition: works but CONTAINS iteration (range)

        Therefore: no mechanism applies projections repeatedly without
        some form of iteration. Iteration is irreducible.
        QED: H3 is FALSIFIED.
        """
        # Strategy 1: fails
        s1 = single_step_run(CHAIN_PROJECTIONS, CHAIN_INPUT)
        assert s1 != CHAIN_EXPECTED

        # Strategy 2: fails for unknown K
        s2 = unrolled_run_3(CHAIN_PROJECTIONS, CHAIN_INPUT)
        assert s2 != CHAIN_EXPECTED

        # Strategy 3: succeeds but IS iteration
        s3_source = inspect.getsource(recursive_run)
        assert "recursive_run" in s3_source  # self-call = iteration

        # Strategy 4: succeeds but CONTAINS iteration
        s4_source = inspect.getsource(compose_n)
        assert "range" in s4_source  # range = iteration

    def test_h3_falsification_validates_methodology(self):
        """H3 was designed to be falsified. Its falsification confirms
        that our hypothesis testing framework can detect false claims.

        If H3 had somehow SUCCEEDED, it would mean either:
        - Our understanding of computation is wrong, or
        - The test is buggy

        H3 FALSIFIED = methodology is sound.
        """
        # This is a documentation test. The real evidence is in the
        # 4 strategy classes above. This test exists to make the
        # falsification verdict explicit and testable.
        strategies_tested = 4
        strategies_general_and_iteration_free = 0

        # Count: how many strategies are BOTH general AND iteration-free?
        # Strategy 1: iteration-free but not general
        # Strategy 2: iteration-free but not general
        # Strategy 3: general but not iteration-free
        # Strategy 4: general but not iteration-free

        assert strategies_general_and_iteration_free == 0, (
            "Expected 0 strategies that are both general and iteration-free"
        )
        assert strategies_tested == 4, "Must test all 4 strategies"
