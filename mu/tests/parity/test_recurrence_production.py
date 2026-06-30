"""
Recurrence Production Tests (v2 — Hash-Accelerated)

Tests that closure detection works via the production meta-circular kernel
path using recurrence.v2.json (hash-accelerated seen-set comparisons).

recurrence.v1.json fails these tests due to O(N^2) deep structural
comparisons exhausting the kernel step budget.  recurrence.v2.json fixes
this by pre-computing mu_hash at the boundary and comparing hash strings
(O(1) per comparison) instead of full states.

See: mu/docs/core/recurrence_v2_design.md
"""

import signal
import pytest

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import list_to_linked, run_algorithm_meta_circular
from rcx_pi.selfhost.engine_pipeline import hash_trace_for_recurrence
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.kernel import reset_step_budget

# Module-level slow marker: meta-circular recurrence is inherently expensive
# (~500 eval_steps per projection application). Skipped in CI fast gate;
# runs in audit_all.sh and nightly.
pytestmark = pytest.mark.slow

# Time limit per test (seconds).
TEST_TIMEOUT_SECONDS = 120


def load_projections(seed_name: str) -> list:
    """Load projections from a verified seed."""
    seed = load_verified_seed(get_seed_path(seed_name))
    return seed["projections"]


def _sn_positive(n: int) -> dict:
    """Encode a positive host int as a StructuralNumbers positive numeral."""
    if n <= 0:
        raise ValueError("_sn_positive requires n >= 1")
    if n == 1:
        return {"xH": None}
    quotient, remainder = divmod(n, 2)
    return {"xI" if remainder else "xO": _sn_positive(quotient)}


def _sn(n: int) -> dict:
    """Encode a non-negative host int as a StructuralNumbers numeral."""
    if n < 0:
        raise ValueError("_sn requires n >= 0")
    if n == 0:
        return {"_num": None}
    return {"_num": _sn_positive(n)}


def _is_structural_number(value) -> bool:
    if not isinstance(value, dict) or set(value.keys()) != {"_num"}:
        return False
    node = value["_num"]
    seen = set()
    while node is not None:
        if not isinstance(node, dict) or len(node) != 1:
            return False
        node_id = id(node)
        if node_id in seen:
            return False
        seen.add(node_id)
        digit, rest = next(iter(node.items()))
        if digit == "xH":
            return rest is None
        if digit not in {"xI", "xO"}:
            return False
        if rest is None:
            return False
        node = rest
    return True


def _trace_entries(trace):
    current = trace
    while isinstance(current, dict) and "head" in current:
        yield current["head"]
        current = current.get("tail")


def _assert_trace_steps_are_structural(trace) -> None:
    for entry in _trace_entries(trace):
        assert _is_structural_number(entry.get("step")), (
            f"trace entry step must be StructuralNumbers, got {entry.get('step')!r}"
        )


def _assert_detected_closure(result, context: str) -> None:
    assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
    assert result.get("closure_detected") is True, (
        f"Recurrence FAILED on {context}. Got: {_summarize(result)}"
    )
    assert _is_structural_number(result.get("tau_step")), (
        f"Recurrence returned non-structural tau_step for {context}: "
        f"{result.get('tau_step')!r}"
    )


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

    Simulates what run_mu_structural produces for a simple livelock: trace
    entries are chronological, step counters are StructuralNumbers numerals,
    and state_hash is added through hash_trace_for_recurrence, the same
    boundary used by the production Paxos path. Host integers stay outside
    matcher-visible trace/tau data.
    """
    entries = []
    for step_num in range(max_steps):
        state = states[step_num % len(states)]
        entries.append({
            "step": _sn(step_num),
            "state": state,
            "projection": f"proj_{step_num % len(states)}",
        })
    trace = hash_trace_for_recurrence(list_to_linked(entries))
    _assert_trace_steps_are_structural(trace)
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

    def test_oscillating_trace_builder_uses_structural_step_numerals(self):
        """Regression: production-style trace helper must not emit host-int steps."""
        trace = build_oscillating_trace(["A", "B"], max_steps=4)
        steps = [entry["step"] for entry in _trace_entries(trace)]
        assert steps == [_sn(0), _sn(1), _sn(2), _sn(3)]
        assert not any(isinstance(step, int) for step in steps)

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

        _assert_detected_closure(result, "Paxos 3-state closure")

    # ------------------------------------------------------------------
    # Oscillation tests with various state types
    # ------------------------------------------------------------------

    def test_oscillation_10_steps_complex_state(self):
        """A/B oscillation with dict states over 10 steps MUST detect closure."""
        states = [
            {"mode": "active", "counter": _sn(0), "status": "running"},
            {"mode": "active", "counter": _sn(1), "status": "running"},
        ]
        trace = build_oscillating_trace(states, max_steps=10)
        recurrence_input = {
            "_detect_closure": {
                "trace": trace,
                "result": states[-1],
            }
        }

        result = self._run_with_timeout(recurrence_input)

        _assert_detected_closure(result, "10-step dict-state oscillation")

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

        _assert_detected_closure(result, "10-step string-state oscillation")

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

        _assert_detected_closure(result, f"trace_length={trace_length}")


def _summarize(result: dict) -> str:
    """One-line summary of recurrence result for error messages."""
    if not isinstance(result, dict):
        return str(result)
    parts = []
    for key in ("_phase", "_mode", "closure_detected", "_timeout"):
        if key in result:
            parts.append(f"{key}={result[key]}")
    return ", ".join(parts) if parts else str(list(result.keys())[:5])
