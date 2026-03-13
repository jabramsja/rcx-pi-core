"""
A20.1: RCX Engine Workload Accuracy Contract.

Fixed test vectors with deterministic terminal invariants.
Verifies engine produces correct terminal shape and field values.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rcx_pi.selfhost.engine_pipeline import run_engine_pipeline

from rcx_pi.selfhost.mu_type import mu_equal

pytestmark = [pytest.mark.slow]

VECTORS_PATH = Path(__file__).parents[1] / "fixtures" / "rcx_engine_workload_contract.json"


@pytest.fixture
def workload_vectors() -> list:
    with open(VECTORS_PATH) as f:
        data = json.load(f)
    return data["vectors"]


class TestRCXEngineWorkloadContract:
    """Deterministic terminal invariants for RCX engine workloads."""

    def test_terminal_shape_matches_contract(self, workload_vectors):
        """Each vector produces terminal result with expected key set."""
        for vector in workload_vectors:
            projs = vector["input"]["_run_engine"]["projections"]
            inp = vector["input"]["_run_engine"]["input"]
            result = run_engine_pipeline(projs, inp)
            assert isinstance(result, dict), (
                f"[{vector['id']}] Expected dict, got {type(result).__name__}"
            )
            actual_keys = set(result.keys())
            expected_keys = set(vector["expected_terminal_keys"])
            assert actual_keys == expected_keys, (
                f"[{vector['id']}] Terminal key mismatch.\n"
                f"  Expected: {sorted(expected_keys)}\n"
                f"  Actual:   {sorted(actual_keys)}"
            )

    def test_terminal_invariants_match(self, workload_vectors):
        """Specific field values match contract invariants."""
        for vector in workload_vectors:
            projs = vector["input"]["_run_engine"]["projections"]
            inp = vector["input"]["_run_engine"]["input"]
            result = run_engine_pipeline(projs, inp)
            for key, expected_val in vector["expected_invariants"].items():
                actual_val = result.get(key)
                assert mu_equal(actual_val, expected_val), (
                    f"[{vector['id']}] Invariant mismatch for '{key}'.\n"
                    f"  Expected: {expected_val}\n"
                    f"  Actual:   {actual_val}"
                )

    def test_vectors_are_deterministic(self, workload_vectors):
        """Same input produces identical output across two runs."""
        for vector in workload_vectors:
            projs = vector["input"]["_run_engine"]["projections"]
            inp = vector["input"]["_run_engine"]["input"]
            result_1 = run_engine_pipeline(projs, inp)
            result_2 = run_engine_pipeline(projs, inp)
            assert mu_equal(result_1, result_2), (
                f"[{vector['id']}] Non-deterministic: two runs produced different results"
            )
