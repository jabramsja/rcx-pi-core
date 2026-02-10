"""
Recurrence Production Failure Tests

Reproduces the production failure where recurrence.v1.json cannot detect
closures in real program traces.  The Paxos deadlock demo (15-step trace)
stalls because the O(N^2) linear seen-set scan exhausts the kernel step
budget before finding the repeated state.

Diagnosis:
- iter 0 (~5s): recurrence stuck in _phase=scan — kernel budget consumed
- iter 1 (~14s): recurrence reaches _phase=check_seen, then blows is_mu
  depth limit on the deeply nested intermediate state
- The intermediate state embeds the full trace linked-list, causing
  exponential depth in validation and pattern matching

This file exists to:
1. Prove the failure is real (not a test artifact)
2. Gate the recurrence.v2 fix (tests must pass after redesign)
3. Prevent regression (never allow closure detection to silently fail again)

All tests are marked xfail — they document KNOWN failures in recurrence.v1.
When recurrence.v2 is implemented, remove the xfail markers.

See: docs/proposals/recurrence_v2_design.md
"""

import signal
import pytest

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import (
    run_mu_structural,
    run_algorithm_meta_circular,
)
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget


# Time limit per test (seconds).  recurrence.v1 hangs on production traces,
# so we need a hard cutoff to keep the test suite fast.
TEST_TIMEOUT_SECONDS = 15


def load_projections(seed_name: str) -> list:
    """Load projections from a verified seed."""
    seed = load_verified_seed(get_seed_path(seed_name))
    return seed["projections"]


class _Timeout(Exception):
    """Raised when a test exceeds the time limit."""


def _timeout_handler(signum, frame):
    raise _Timeout(
        f"Recurrence exceeded {TEST_TIMEOUT_SECONDS}s — "
        f"O(N^2) seen-set scan cannot complete within budget"
    )


def run_recurrence_to_completion(recurrence_projs, recurrence_input, max_iterations=50):
    """Run recurrence algorithm repeatedly until terminal result or timeout.

    Each call to run_algorithm_meta_circular runs one kernel cycle (up to
    10000 kernel steps).  Recurrence needs many cycles to process a trace.
    """
    current = recurrence_input
    for i in range(max_iterations):
        reset_step_budget()
        result = run_algorithm_meta_circular(recurrence_projs, current)
        if mu_equal(result, current):
            return result  # Stalled — no further progress
        # Check for terminal result
        if isinstance(result, dict) and "closure_detected" in result:
            return result
        current = result
    return current


# ---------------------------------------------------------------------------
# Helpers to build traces without running full programs
# ---------------------------------------------------------------------------

def build_oscillating_trace(states: list, max_steps: int) -> dict:
    """Build a Mu linked-list trace from a list of oscillating states.

    Simulates what run_mu_structural produces for a simple livelock:
    states cycle through the list indefinitely until max_steps.
    """
    trace = None  # null-terminated linked list
    for i in range(max_steps, 0, -1):
        step_num = max_steps - i
        state = states[step_num % len(states)]
        entry = {
            "step": step_num,
            "state": state,
            "projection": f"proj_{step_num % len(states)}",
        }
        trace = {"head": entry, "tail": trace}
    return trace


# ============================================================================
# Test class: Reproduction of production failures
# ============================================================================

class TestRecurrenceProductionFailure:
    """Reproduce the failure where recurrence.v1 cannot detect closures
    in production-length traces (15+ steps with complex states).

    All tests are marked xfail (strict=True) — they MUST fail with
    recurrence.v1.  If any unexpectedly passes, that means either the
    test is wrong or recurrence.v1 was secretly fixed.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        reset_step_budget()
        self.recurrence_projs = load_projections("recurrence.v1.json")

    def _run_with_timeout(self, recurrence_input):
        """Run recurrence with a hard time limit."""
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(TEST_TIMEOUT_SECONDS)
        try:
            return run_recurrence_to_completion(
                self.recurrence_projs, recurrence_input
            )
        except _Timeout:
            return {"_timeout": True, "_phase": "budget_exhausted"}
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    # ------------------------------------------------------------------
    # Core reproduction: Paxos deadlock demo
    # ------------------------------------------------------------------

    @pytest.mark.xfail(strict=True, reason="recurrence.v1 O(N^2) budget exhaustion on 15-step trace")
    def test_paxos_livelock_closure_detected(self):
        """Paxos 4-state livelock over 15 steps MUST detect closure.

        This is the exact scenario from prototypes/run_paxos_demo.py.
        The Paxos seed creates a cycle:
          idle/idle -> propose/idle -> rejected/propose -> idle/idle (repeat)

        With 15 steps this clearly repeats.  recurrence.v1 should detect it
        but CANNOT due to O(N^2) seen-set scan.
        """
        paxos_projs = load_projections("paxos_demo.v1.json")

        # Generate livelock trace
        trace_result = run_mu_structural(
            paxos_projs, {"paxos_trigger": "start_paxos"}, max_steps=15
        )

        # Feed trace to recurrence
        recurrence_input = {
            "_detect_closure": {
                "trace": trace_result["trace"],
                "result": trace_result["result"],
            }
        }

        result = self._run_with_timeout(recurrence_input)

        # MUST detect closure — the trace has a clear 3-step cycle
        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
        assert result.get("closure_detected") is True, (
            f"Recurrence FAILED to detect closure in 15-step Paxos livelock. "
            f"Got: {_summarize(result)}"
        )

    # ------------------------------------------------------------------
    # Simpler reproduction: minimal oscillation with complex states
    # ------------------------------------------------------------------

    @pytest.mark.xfail(strict=True, reason="recurrence.v1 O(N^2) budget exhaustion on dict states")
    def test_oscillation_10_steps_complex_state(self):
        """A/B oscillation with dict states over 10 steps MUST detect closure.

        Uses multi-field dict states (like real programs produce).
        """
        states = [
            {"mode": "active", "counter": 0, "status": "running"},
            {"mode": "active", "counter": 1, "status": "running"},
        ]
        trace = build_oscillating_trace(states, max_steps=10)
        recurrence_input = {
            "_detect_closure": {
                "trace": trace,
                "result": states[-1],
            }
        }

        result = self._run_with_timeout(recurrence_input)

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("closure_detected") is True, (
            f"Recurrence FAILED on 10-step dict-state oscillation. "
            f"Got: {_summarize(result)}"
        )

    @pytest.mark.xfail(strict=True, reason="recurrence.v1 O(N^2) budget exhaustion on 10-step trace")
    def test_oscillation_10_steps_string_state(self):
        """A/B oscillation with string states over 10 steps.

        Even simple string states fail at 10 steps because the
        normalized Mu representation of the trace linked-list is deep
        enough to exhaust the kernel step budget.
        """
        states = ["state_A", "state_B"]
        trace = build_oscillating_trace(states, max_steps=10)
        recurrence_input = {
            "_detect_closure": {
                "trace": trace,
                "result": states[-1],
            }
        }

        result = self._run_with_timeout(recurrence_input)

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("closure_detected") is True, (
            f"Recurrence FAILED even on simple string states (10 steps). "
            f"Got: {_summarize(result)}"
        )

    # ------------------------------------------------------------------
    # Scaling boundary: find where recurrence.v1 breaks
    # ------------------------------------------------------------------

    @pytest.mark.xfail(strict=True, reason="recurrence.v1 fails at ALL trace lengths via meta-circular kernel")
    @pytest.mark.parametrize("trace_length", [3, 5, 8, 10, 15])
    def test_closure_detection_scaling(self, trace_length):
        """Test recurrence.v1 at increasing trace lengths with string states.

        FINDING: Even 3-step traces fail on the production meta-circular
        path (step_kernel_mu).  Existing recurrence tests pass only because
        they use eval_seed.step() (bootstrap path), which is much cheaper
        per projection application.

        The meta-circular kernel wraps each recurrence projection in a full
        kernel cycle (wrap/try/match/subst/unwrap), making each step ~7x
        more expensive.  Combined with O(N^2) seen-set scan, the budget
        is exhausted before even trivial traces complete.
        """
        states = ["A", "B"]  # Simple 2-state oscillation
        trace = build_oscillating_trace(states, max_steps=trace_length)
        recurrence_input = {
            "_detect_closure": {
                "trace": trace,
                "result": states[(trace_length - 1) % len(states)],
            }
        }

        result = self._run_with_timeout(recurrence_input)

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("closure_detected") is True, (
            f"Recurrence FAILED at trace_length={trace_length}. "
            f"Got: {_summarize(result)}"
        )


def _summarize(result: dict) -> str:
    """One-line summary of recurrence result for error messages."""
    if not isinstance(result, dict):
        return str(result)
    parts = []
    for key in ("_phase", "_mode", "closure_detected", "_timeout"):
        if key in result:
            parts.append(f"{key}={result[key]}")
    return ", ".join(parts) if parts else str(list(result.keys())[:5])
