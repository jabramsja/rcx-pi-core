"""
Recurrence Production Tests (v2 — Hash-Accelerated)

Tests that closure detection works via the production meta-circular kernel
path using recurrence.v2.json (hash-accelerated seen-set comparisons).

recurrence.v1.json fails these tests due to O(N^2) deep structural
comparisons exhausting the kernel step budget.  recurrence.v2.json fixes
this by pre-computing mu_hash at the boundary and comparing hash strings
(O(1) per comparison) instead of full states.

See: docs/core/recurrence_v2_design.md
"""

import signal
import pytest

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
from rcx_pi.selfhost.mu_type import mu_equal, mu_hash
from rcx_pi.selfhost.kernel import reset_step_budget


# Time limit per test (seconds).  The meta-circular kernel is inherently slow
# (~500 eval_steps per recurrence projection application).  Hash comparison
# makes each check O(1) but kernel normalization is still O(trace_length) per step.
# CI runners are ~3x slower than local; use RCX_CI env var to detect.
import os as _os
TEST_TIMEOUT_SECONDS = 360 if _os.environ.get("RCX_CI") else 120


def load_projections(seed_name: str) -> list:
    """Load projections from a verified seed."""
    seed = load_verified_seed(get_seed_path(seed_name))
    return seed["projections"]


class _Timeout(Exception):
    """Raised when a test exceeds the time limit."""


def _timeout_handler(signum, frame):
    raise _Timeout(
        f"Recurrence exceeded {TEST_TIMEOUT_SECONDS}s"
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
    Includes state_hash for recurrence.v2 compatibility.
    """
    trace = None  # null-terminated linked list
    for i in range(max_steps, 0, -1):
        step_num = max_steps - i
        state = states[step_num % len(states)]
        entry = {
            "step": step_num,
            "state": state,
            "projection": f"proj_{step_num % len(states)}",
            "state_hash": mu_hash(state),
        }
        trace = {"head": entry, "tail": trace}
    return trace


# ============================================================================
# Test class: Production closure detection with recurrence.v2
# ============================================================================

class TestRecurrenceV2Production:
    """Verify recurrence.v2 detects closures via the production
    meta-circular kernel path (step_kernel_mu with bridge).
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        reset_step_budget()
        self.recurrence_projs = load_projections("recurrence.v2.json")

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
    # Core test: Paxos deadlock demo
    # ------------------------------------------------------------------

    def test_paxos_livelock_closure_detected(self):
        """Paxos 3-state cycle over 5 steps MUST detect closure.

        Uses build_oscillating_trace with real Paxos states (4-key dicts)
        to test closure detection on complex multi-field state types.

        The 3-state Paxos cycle:
          idle/idle -> propose/idle -> rejected/propose -> idle/idle (repeat)

        5 steps gives nearly 2 full cycles, sufficient for closure detection.
        """
        paxos_states = [
            {"node_a": "idle", "node_b": "idle", "paxos_mode": "paxos_run", "status": "voting"},
            {"node_a": "propose", "node_b": "idle", "paxos_mode": "paxos_run", "status": "voting"},
            {"node_a": "rejected", "node_b": "propose", "paxos_mode": "paxos_run", "status": "voting"},
        ]
        trace = build_oscillating_trace(paxos_states, max_steps=5)
        recurrence_input = {
            "_detect_closure": {
                "trace": trace,
                "result": paxos_states[-1],
            }
        }

        result = self._run_with_timeout(recurrence_input)

        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
        assert result.get("closure_detected") is True, (
            f"Recurrence FAILED to detect Paxos 3-state closure. "
            f"Got: {_summarize(result)}"
        )

    # ------------------------------------------------------------------
    # Oscillation tests with various state types
    # ------------------------------------------------------------------

    def test_oscillation_10_steps_complex_state(self):
        """A/B oscillation with dict states over 10 steps MUST detect closure."""
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

    def test_oscillation_10_steps_string_state(self):
        """A/B oscillation with string states over 10 steps."""
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
    # Scaling: v2 should handle all trace lengths
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("trace_length", [3, 5, 8, 10, 15])
    def test_closure_detection_scaling(self, trace_length):
        """Test recurrence.v2 at increasing trace lengths with string states."""
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
