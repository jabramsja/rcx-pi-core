"""
A20.1: RCX Engine Workload Accuracy Contract.

Fixed test vectors with deterministic terminal invariants.
Verifies engine produces correct terminal shape and field values.
This module is the rcx_engine_cycle workload-target proof binding for
Stage 4 L4_STRUCTURAL contract enforcement.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import rcx_pi.selfhost.engine_pipeline as engine_pipeline
from rcx_pi.selfhost.engine_pipeline import (
    _service_boundary_effect,  # ANTICHEAT_OK: boundary fast-reject regression path
    run_engine_pipeline,
    run_hemisphere_routing,
)

from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.step_mu import RcxEngineError

pytestmark = [pytest.mark.slow]

VECTORS_PATH = Path(__file__).parents[1] / "fixtures" / "rcx_engine_workload_contract.json"
ROOT = Path(__file__).parents[3]
_JS_API_TIMEOUT = 180


def _empty_hemispheres() -> dict:
    return {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


def _js_api(request: dict) -> dict:
    proc = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=_JS_API_TIMEOUT,
        check=False,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise AssertionError(f"no JSON_API_RESPONSE in stdout: {proc.stdout[:500]}")


def _structural_num(n: int) -> dict:
    if n < 0:
        raise ValueError("StructuralNumbers helper requires non-negative integer")
    if n == 0:
        return {"_num": None}
    lower_bits = []
    while n > 1:
        lower_bits.append(n & 1)
        n >>= 1
    node = {"xH": None}
    for bit in reversed(lower_bits):
        node = {"xI": node} if bit else {"xO": node}
    return {"_num": node}


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

    def test_host_tau_step_zero_fails_closed_on_python_and_js(self):
        """Legacy host zero must not become matcher-facing StructuralNumbers zero."""
        engine_result = {
            "value": "legacy-zero",
            "closure_detected": True,
            "tau_step": 0,
            "exhaustion_detected": False,
            "operator_frozen": None,
            "frozen_set": None,
            "action": "continue",
            "stall": False,
        }
        hemispheres = _empty_hemispheres()

        with pytest.raises(RuntimeError) as py_error:
            run_hemisphere_routing(engine_result, hemispheres)
        assert getattr(py_error.value, "error_code", None) == "input.shape_mismatch"

        js_response = _js_api({
            "action": "run_hemisphere_routing",
            "engine_result": engine_result,
            "hemispheres": hemispheres,
        })
        assert not js_response["success"]
        assert js_response.get("error_code") == "input.shape_mismatch"

    def test_run_trace_over_cap_budget_rejects_before_structural_reduction(self, monkeypatch):
        """Boundary budget cap rejects over-cap StructuralNumbers before ADD/COMPARE."""
        def reject_structural_step(*args, **kwargs):
            raise AssertionError("over-cap run_trace budget used structural reduction")

        monkeypatch.setattr(engine_pipeline, "_step_trusted", reject_structural_step)
        request = {
            "operation": "run_trace",
            "input": {
                "projections": [
                    {"pattern": "A", "body": "B"},
                    {"pattern": "B", "body": "A"},
                ],
                "value": "A",
                "max_steps": _structural_num(10001),
            },
            "context": {},
            "inject_key": "result",
        }
        with pytest.raises(RcxEngineError) as exc:
            _service_boundary_effect(
                request,
                max_algorithm_iterations=10,
                emit_fn=lambda *args, **kwargs: None,
                step=0,
                state={},
            )
        assert exc.value.error_code == "api.bad_request"
        assert "10000" in str(exc.value)
