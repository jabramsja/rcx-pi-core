"""
A20.1: RCX Engine Workload Contract — Cross-Substrate Parity.

Runs the same workload contract vectors through Python and JavaScript
engine pipelines and verifies terminal shape and invariant agreement.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rcx_pi.selfhost.step_mu import run_engine_pipeline

from tests.repo_root import REPO_ROOT

pytestmark = [pytest.mark.slow]

VECTORS_PATH = Path(__file__).parents[1] / "fixtures" / "rcx_engine_workload_contract.json"


def _load_vectors() -> list:
    with open(VECTORS_PATH) as f:
        data = json.load(f)
    return data["vectors"]


def _run_js_engine_pipeline(projections: list, input_val: dict) -> dict:
    """Invoke JS engine pipeline via JSON API."""
    request = {
        "action": "run_engine_pipeline",
        "projections": projections,
        "input": input_val,
    }
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(
        f"No JSON_API_RESPONSE in JS output.\n"
        f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
    )


def _normalize_for_cross_substrate(value):
    """Normalize Python values for cross-substrate comparison with JS."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_normalize_for_cross_substrate(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_cross_substrate(v) for k, v in value.items()}
    return value


def _cross_substrate_equal(py_val, js_val) -> bool:
    """Compare Python and JS values, handling int/float differences."""
    norm_py = _normalize_for_cross_substrate(py_val)
    norm_js = _normalize_for_cross_substrate(js_val)
    return json.dumps(norm_py, sort_keys=True) == json.dumps(norm_js, sort_keys=True)


class TestWorkloadContractParity:
    """Python and JS must agree on workload contract vectors."""

    def test_python_js_agree_on_contract_vectors(self):
        """Each contract vector produces matching terminal output in both substrates."""
        vectors = _load_vectors()
        for vector in vectors:
            projs = vector["input"]["_run_engine"]["projections"]
            inp = vector["input"]["_run_engine"]["input"]

            # Python
            py_result = run_engine_pipeline(projs, inp)

            # JavaScript
            js_response = _run_js_engine_pipeline(projs, inp)
            assert js_response.get("success"), (
                f"[{vector['id']}] JS engine pipeline failed: {js_response.get('error')}"
            )
            js_result = js_response["result"]

            # Terminal key agreement
            py_keys = set(py_result.keys())
            js_keys = set(js_result.keys())
            assert py_keys == js_keys, (
                f"[{vector['id']}] Terminal key mismatch.\n"
                f"  Python: {sorted(py_keys)}\n"
                f"  JS:     {sorted(js_keys)}"
            )

            # Invariant agreement
            for key, expected_val in vector["expected_invariants"].items():
                py_val = py_result.get(key)
                js_val = js_result.get(key)
                assert _cross_substrate_equal(py_val, js_val), (
                    f"[{vector['id']}] Parity mismatch for '{key}'.\n"
                    f"  Python: {py_val}\n"
                    f"  JS:     {js_val}"
                )
