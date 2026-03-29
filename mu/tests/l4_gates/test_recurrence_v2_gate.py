"""
L4 gate test: recurrence.v2.json structural contract verification.

Verifies the production closure detection seed (hash-accelerated, 9 projections)
meets its structural contract:
1. Seed loads and has exactly 9 projections
2. All required projection IDs are present
3. Execution layer is META_CIRCULAR (runs through step_kernel_mu)
4. Closure detection produces correct shape on recurring trace
5. No false closure on non-recurring trace
6. Terminal result shape matches contract

Spec reference: RCXEngineNew.pdf Rule 2.2 (Closure-on-Second-Demand)
Seed: mu/closures/recurrence.v2.json
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path
from rcx_pi.selfhost.step_mu import run_algorithm_meta_circular
from rcx_pi.selfhost.mu_type import mu_equal, mu_hash
from rcx_pi.selfhost.kernel import reset_step_budget


def _load_recurrence_v2_projections() -> list:
    seed = load_verified_seed(get_seed_path("recurrence.v2.json"))
    return seed["projections"]


def _load_recurrence_v2_seed() -> dict:
    return load_verified_seed(get_seed_path("recurrence.v2.json"))


def _run_recurrence(projs, input_val, max_iterations=30):
    """Run recurrence to completion (terminal result or stall)."""
    current = input_val
    for _ in range(max_iterations):
        reset_step_budget()
        result = run_algorithm_meta_circular(projs, current)
        if mu_equal(result, current):
            return result
        if isinstance(result, dict) and "closure_detected" in result:
            return result
        current = result
    return current


def _build_trace_with_hashes(entries: list[dict]) -> dict:
    """Build a Mu linked-list trace with pre-computed state_hash fields."""
    trace = None
    for entry in reversed(entries):
        state = entry.get("state", entry)
        entry_with_hash = dict(entry)
        if "state_hash" not in entry_with_hash:
            entry_with_hash["state_hash"] = mu_hash(state)
        trace = {"head": entry_with_hash, "tail": trace}
    return trace


class TestRecurrenceV2SeedStructure:
    """Seed loads correctly with expected projection count and IDs."""

    def test_projection_count_is_9(self):
        projs = _load_recurrence_v2_projections()
        assert len(projs) == 9, f"Expected 9 projections, got {len(projs)}"

    def test_required_projection_ids(self):
        projs = _load_recurrence_v2_projections()
        ids = {p["id"] for p in projs}
        required = {
            "recurrence.init",
            "recurrence.end_of_trace",
            "recurrence.check_state_stall",
            "recurrence.check_state_maxsteps",
            "recurrence.check_state",
            "recurrence.hash_match",
            "recurrence.hash_no_match",
            "recurrence.not_found",
            "recurrence.unwrap",
        }
        missing = required - ids
        assert not missing, f"Missing projection IDs: {missing}"

    def test_execution_layer_is_meta_circular(self):
        seed = _load_recurrence_v2_seed()
        meta = seed.get("meta", {})
        assert meta.get("execution_layer") == "META_CIRCULAR"
        assert meta.get("meta_circular_capable") is True

    def test_seed_declares_non_linear_patterns(self):
        seed = _load_recurrence_v2_seed()
        meta = seed.get("meta", {})
        assert "non-linear" in meta.get("requires_patterns", [])


class TestRecurrenceV2ClosureDetection:
    """Closure detection produces correct results via meta-circular path."""

    @pytest.mark.slow  # SPEED_OK: runs meta-circular kernel (~500 eval_steps per projection)
    def test_recurring_trace_detects_closure(self):
        """A trace with duplicate state hashes must produce closure_detected=True."""
        projs = _load_recurrence_v2_projections()
        state_a = {"value": "A"}
        state_b = {"value": "B"}
        hash_a = mu_hash(state_a)
        hash_b = mu_hash(state_b)
        entries = [
            {"step": 0, "state": state_a, "state_hash": hash_a, "projection": None, "stall": True},
            {"step": 1, "state": state_b, "state_hash": hash_b, "projection": None, "stall": True},
            {"step": 2, "state": state_a, "state_hash": hash_a, "projection": None, "stall": True},
        ]
        trace = _build_trace_with_hashes(entries)
        input_val = {"_detect_closure": {"trace": trace, "result": state_a}}
        result = _run_recurrence(projs, input_val)
        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
        assert result.get("closure_detected") is True, f"Expected closure_detected=True, got {result}"

    @pytest.mark.slow  # SPEED_OK: runs meta-circular kernel
    def test_non_recurring_trace_no_closure(self):
        """A trace with all unique state hashes must produce closure_detected=False."""
        projs = _load_recurrence_v2_projections()
        states = [{"value": f"unique_{i}"} for i in range(3)]
        entries = [
            {"step": i, "state": s, "state_hash": mu_hash(s), "projection": None, "stall": True}
            for i, s in enumerate(states)
        ]
        trace = _build_trace_with_hashes(entries)
        input_val = {"_detect_closure": {"trace": trace, "result": states[-1]}}
        result = _run_recurrence(projs, input_val)
        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
        assert result.get("closure_detected") is False, f"Expected closure_detected=False, got {result}"


class TestRecurrenceV2ResultShape:
    """Terminal result matches the structural contract."""

    @pytest.mark.slow  # SPEED_OK: runs meta-circular kernel
    def test_terminal_result_has_required_fields(self):
        """Terminal result must have closure_detected field."""
        projs = _load_recurrence_v2_projections()
        state = {"value": "X"}
        entries = [
            {"step": 0, "state": state, "state_hash": mu_hash(state), "projection": None, "stall": True},
        ]
        trace = _build_trace_with_hashes(entries)
        input_val = {"_detect_closure": {"trace": trace, "result": state}}
        result = _run_recurrence(projs, input_val)
        assert isinstance(result, dict)
        assert "closure_detected" in result, f"Terminal result missing closure_detected: {list(result.keys())}"


class TestRecurrenceV2SeedCountRegistry:
    """Seed is registered in EXPECTED_COUNTS with correct count."""

    def test_recurrence_v2_in_expected_counts(self):
        from mu.tests.structural.test_seed_counts import EXPECTED_COUNTS  # ANTICHEAT_OK: test-only — cross-referencing seed registry
        assert "recurrence.v2.json" in EXPECTED_COUNTS
        assert EXPECTED_COUNTS["recurrence.v2.json"] == 9
