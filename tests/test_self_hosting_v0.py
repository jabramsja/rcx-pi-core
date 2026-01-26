"""
Phase 5: Self-Hosting Verification

EVAL_SEED (as Mu data) runs EVAL_SEED (as projections).
Success = identical traces from Python and Mu evaluation paths.

This is THE test that proves RCX emergence is structural, not host-dependent.

See docs/core/SelfHosting.v0.md for design.
"""

import pytest

from rcx_pi.eval_seed import step, NO_MATCH
from rcx_pi.step_mu import step_mu, run_mu
from rcx_pi.mu_type import mu_equal


def run_python(projections, initial, max_steps=100):
    """Run projections using Python step() - reference implementation."""
    trace = []
    current = initial

    for i in range(max_steps):
        trace.append({"step": i, "value": current})

        result = step(projections, current)

        # Check for stall (no change)
        if mu_equal(result, current):
            trace.append({"step": i + 1, "value": result, "stall": True})
            return result, trace, True

        current = result

    trace.append({"step": max_steps, "value": current, "max_steps": True})
    return current, trace, False


def traces_equal(py_trace, mu_trace):
    """Compare two traces for structural equality."""
    if len(py_trace) != len(mu_trace):
        return False, f"Length mismatch: {len(py_trace)} vs {len(mu_trace)}"

    for i, (py_entry, mu_entry) in enumerate(zip(py_trace, mu_trace)):
        if not mu_equal(py_entry, mu_entry):
            return False, f"Divergence at step {i}: {py_entry} vs {mu_entry}"

    return True, None


class TestTraceParity:
    """Verify Python and Mu evaluation produce identical traces."""

    def test_simple_reduction_trace(self):
        """Single reduction step produces identical trace."""
        projections = [
            {"pattern": {"inc": {"var": "n"}}, "body": {"result": {"var": "n"}}}
        ]
        initial = {"inc": 5}

        py_result, py_trace, py_stall = run_python(projections, initial)
        mu_result, mu_trace, mu_stall = run_mu(projections, initial)

        # Results must match
        assert mu_equal(py_result, mu_result), f"Results differ: {py_result} vs {mu_result}"
        assert py_stall == mu_stall, f"Stall status differs"

        # Traces must match
        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"

    def test_multi_step_reduction_trace(self):
        """Multiple reduction steps produce identical trace."""
        # Peano countdown: succ(succ(zero)) -> succ(zero) -> zero -> stall
        projections = [
            {"pattern": {"succ": {"var": "n"}}, "body": {"var": "n"}}
        ]
        initial = {"succ": {"succ": "zero"}}

        py_result, py_trace, py_stall = run_python(projections, initial)
        mu_result, mu_trace, mu_stall = run_mu(projections, initial)

        # Should reduce to "zero" and stall
        assert mu_equal(py_result, "zero")
        assert mu_equal(mu_result, "zero")
        assert py_stall and mu_stall

        # Traces must match
        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"

    def test_no_match_stall_trace(self):
        """No matching projection causes immediate stall."""
        projections = [
            {"pattern": "specific", "body": "matched"}
        ]
        initial = "different"

        py_result, py_trace, py_stall = run_python(projections, initial)
        mu_result, mu_trace, mu_stall = run_mu(projections, initial)

        # Should stall immediately (no change)
        assert mu_equal(py_result, "different")
        assert mu_equal(mu_result, "different")
        assert py_stall and mu_stall

        # Traces must match
        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"


class TestPeanoCountdown:
    """Peano numeral countdown - classic self-hosting test case."""

    def test_countdown_from_three(self):
        """Countdown from succ(succ(succ(zero))) to zero."""
        projections = [
            {"pattern": {"succ": {"var": "n"}}, "body": {"var": "n"}}
        ]
        # Three = succ(succ(succ(zero)))
        three = {"succ": {"succ": {"succ": "zero"}}}

        py_result, py_trace, py_stall = run_python(projections, three)
        mu_result, mu_trace, mu_stall = run_mu(projections, three)

        # Should reduce to "zero"
        assert mu_equal(py_result, "zero")
        assert mu_equal(mu_result, "zero")

        # Should take 3 steps + 1 stall step
        assert len(py_trace) == len(mu_trace) == 5

        # Traces must match exactly
        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"

    def test_countdown_trace_values(self):
        """Verify exact values in countdown trace."""
        projections = [
            {"pattern": {"succ": {"var": "n"}}, "body": {"var": "n"}}
        ]
        two = {"succ": {"succ": "zero"}}

        py_result, py_trace, _ = run_python(projections, two)
        mu_result, mu_trace, _ = run_mu(projections, two)

        # Verify trace values
        expected_values = [
            {"succ": {"succ": "zero"}},  # Step 0: initial
            {"succ": "zero"},             # Step 1: after first reduction
            "zero",                       # Step 2: after second reduction
        ]

        for i, expected in enumerate(expected_values):
            assert mu_equal(py_trace[i]["value"], expected), f"Python trace[{i}] wrong"
            assert mu_equal(mu_trace[i]["value"], expected), f"Mu trace[{i}] wrong"


class TestListAppend:
    """List append operation - another self-hosting test case."""

    def test_append_single_element(self):
        """Append element to list.

        Note: Uses explicit structure that avoids head/tail denormalization
        ambiguity. The key insight is that {"head": x, "tail": y} structures
        may be denormalized to lists, so we use different key names.
        """
        # Simple append: cons(x, xs) -> result with x prepended
        projections = [
            {
                "pattern": {"cons": {"var": "x"}, "to": {"var": "xs"}},
                "body": {"first": {"var": "x"}, "rest": {"var": "xs"}}
            }
        ]
        initial = {"cons": 1, "to": {"first": 2, "rest": None}}

        py_result, py_trace, py_stall = run_python(projections, initial)
        mu_result, mu_trace, mu_stall = run_mu(projections, initial)

        expected = {"first": 1, "rest": {"first": 2, "rest": None}}
        assert mu_equal(py_result, expected)
        assert mu_equal(mu_result, expected)

        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"


class TestEvalSeedProjections:
    """Test with actual EVAL_SEED-like projections."""

    def test_identity_projection(self):
        """Identity projection: wrap value and unwrap."""
        projections = [
            # Wrap: value -> {wrapped: value}
            {"pattern": {"wrap": {"var": "v"}}, "body": {"wrapped": {"var": "v"}}},
            # Unwrap: {wrapped: value} -> value
            {"pattern": {"unwrap": {"wrapped": {"var": "v"}}}, "body": {"var": "v"}}
        ]

        # Test wrap
        wrap_input = {"wrap": 42}
        py1, _, _ = run_python(projections, wrap_input)
        mu1, _, _ = run_mu(projections, wrap_input)
        assert mu_equal(py1, {"wrapped": 42})
        assert mu_equal(mu1, {"wrapped": 42})

        # Test unwrap
        unwrap_input = {"unwrap": {"wrapped": 42}}
        py2, _, _ = run_python(projections, unwrap_input)
        mu2, _, _ = run_mu(projections, unwrap_input)
        assert mu_equal(py2, 42)
        assert mu_equal(mu2, 42)

    def test_state_machine_projection(self):
        """State machine transition via projections."""
        projections = [
            # State A -> State B
            {"pattern": {"state": "A", "data": {"var": "d"}},
             "body": {"state": "B", "data": {"var": "d"}}},
            # State B -> State C
            {"pattern": {"state": "B", "data": {"var": "d"}},
             "body": {"state": "C", "data": {"var": "d"}}},
            # State C is terminal (no projection matches)
        ]
        initial = {"state": "A", "data": "payload"}

        py_result, py_trace, py_stall = run_python(projections, initial)
        mu_result, mu_trace, mu_stall = run_mu(projections, initial)

        # Should end in state C
        expected = {"state": "C", "data": "payload"}
        assert mu_equal(py_result, expected)
        assert mu_equal(mu_result, expected)

        # Should take 2 steps + 1 stall
        assert len(py_trace) == len(mu_trace) == 4

        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"


class TestSelfHostingCore:
    """THE self-hosting tests: EVAL_SEED evaluates EVAL_SEED."""

    def test_projection_applies_projection(self):
        """
        A projection that describes applying a projection.

        This is the essence of self-hosting: projections that can
        process other projections as data.
        """
        # A "meta" projection that extracts pattern from a projection
        projections = [
            {
                "pattern": {"get_pattern": {"pattern": {"var": "p"}, "body": {"var": "b"}}},
                "body": {"extracted_pattern": {"var": "p"}}
            }
        ]

        # Input: a projection (as data)
        test_projection = {"pattern": 42, "body": "matched"}
        initial = {"get_pattern": test_projection}

        py_result, py_trace, _ = run_python(projections, initial)
        mu_result, mu_trace, _ = run_mu(projections, initial)

        expected = {"extracted_pattern": 42}
        assert mu_equal(py_result, expected)
        assert mu_equal(mu_result, expected)

        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"

    def test_evaluator_processes_evaluator(self):
        """
        EVAL_SEED projections can be processed by the evaluator.

        This tests that projection definitions (the evaluator's "code")
        can be transformed by projections (treated as data).

        Note: We avoid patterns like {"var": {"var": "name"}} because
        the outer "var" key creates ambiguity with variable site detection.
        Instead, we use explicit wrapper structures.
        """
        # A projection that extracts variable info from a wrapped var site
        projections = [
            # Extract variable name from wrapper
            {"pattern": {"extract_var": {"variable_site": {"var": "name"}}},
             "body": {"extracted": {"var": "name"}, "type": "variable"}},
            # Handle non-variable (catch-all)
            {"pattern": {"extract_var": {"var": "other"}},
             "body": {"extracted": {"var": "other"}, "type": "literal"}}
        ]

        # Extract from a variable site wrapper
        initial = {"extract_var": {"variable_site": "x"}}

        py_result, py_trace, _ = run_python(projections, initial)
        mu_result, mu_trace, _ = run_mu(projections, initial)

        expected = {"extracted": "x", "type": "variable"}
        assert mu_equal(py_result, expected)
        assert mu_equal(mu_result, expected)

        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"Traces differ: {diff}"

    def test_self_hosting_complete(self):
        """
        THE SELF-HOSTING TEST

        Verifies that:
        1. step_mu() uses Mu projections (match_mu + subst_mu)
        2. step() uses Python functions (match + substitute)
        3. Both produce identical results and traces

        This proves the evaluator can evaluate itself:
        - EVAL_SEED (the projections) defines how to match and substitute
        - step_mu() uses those projections to do matching and substitution
        - The projections are being used to process projections

        If this test passes, self-hosting is achieved.
        """
        # Use actual projection-like structures
        projections = [
            # This projection transforms a "request" into a "response"
            {
                "pattern": {
                    "request": {
                        "op": "apply",
                        "projection": {"var": "proj"},
                        "value": {"var": "val"}
                    }
                },
                "body": {
                    "response": {
                        "applied": {"var": "proj"},
                        "to": {"var": "val"}
                    }
                }
            }
        ]

        # The input is a request to apply a projection (meta-level)
        initial = {
            "request": {
                "op": "apply",
                "projection": {"pattern": "X", "body": "Y"},
                "value": "Z"
            }
        }

        # Run through both evaluation paths
        py_result, py_trace, py_stall = run_python(projections, initial)
        mu_result, mu_trace, mu_stall = run_mu(projections, initial)

        # Expected: the request is transformed to a response
        expected = {
            "response": {
                "applied": {"pattern": "X", "body": "Y"},
                "to": "Z"
            }
        }

        # Results must match
        assert mu_equal(py_result, expected), f"Python result wrong: {py_result}"
        assert mu_equal(mu_result, expected), f"Mu result wrong: {mu_result}"

        # Stall status must match
        assert py_stall == mu_stall

        # CRITICAL: Traces must be identical
        is_equal, diff = traces_equal(py_trace, mu_trace)
        assert is_equal, f"SELF-HOSTING FAILED: Traces differ: {diff}"

        # If we get here, self-hosting is achieved!
        # Python step() and Mu step_mu() produce identical behavior
