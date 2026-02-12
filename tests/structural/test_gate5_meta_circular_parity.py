"""
Gate 5 meta-circular parity tests.

This suite is dedicated to Gate 5 verification:
- Structural path remains default for algorithm execution.
- Bootstrap fallback requires explicit opt-in.
- Python and JS bridge-backed algorithm runtimes agree on canonical vectors.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from rcx_pi.selfhost.step_mu import (
    run_algorithm_meta_circular,
    run_mu_structural,
    step_kernel_mu,
)


pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def _load_projections(seed_name: str) -> list[dict]:
    seed = load_verified_seed(get_seed_path(seed_name))
    return seed["projections"]


def _run_python_until_stall(projections: list[dict], initial: dict, max_steps: int = 200) -> dict:
    current = initial
    for _ in range(max_steps):
        nxt = run_algorithm_meta_circular(projections, current)
        if mu_equal(nxt, current):
            return nxt
        current = nxt
    return current


def _run_js_action(action: str, initial: dict, max_steps: int = 200) -> dict:
    req = json.dumps({"action": action, "input": initial, "maxSteps": max_steps})
    proc = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", req],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    last = None
    for line in proc.stdout.splitlines():
        if line.startswith("JSON_API_RESPONSE:"):
            last = json.loads(line[len("JSON_API_RESPONSE:"):])
    assert last is not None, f"no JSON_API_RESPONSE in stdout: {proc.stdout[:500]}"
    assert last.get("success"), f"js action failed: {last.get('error')}"
    return last["result"]


def test_gate5_bootstrap_fallback_requires_explicit_opt_in():
    state = {"_detect_closure": {"trace": None, "result": "A"}}
    with pytest.raises(ValueError, match="allow_bootstrap_fallback=True"):
        run_algorithm_meta_circular([], state, execution_mode="bootstrap")


def test_gate5_bootstrap_fallback_runs_when_opted_in():
    state = {"_detect_closure": {"trace": None, "result": "A"}}
    result = run_algorithm_meta_circular(
        [],
        state,
        execution_mode="bootstrap",
        allow_bootstrap_fallback=True,
    )
    assert isinstance(result, dict)


def test_gate5_recurrence_python_js_parity_vectors():
    rec_projs = _load_projections("recurrence.v1.json")
    vectors = json.loads((FIXTURES / "recurrence_vectors.json").read_text(encoding="utf-8"))["vectors"]
    for vec in vectors:
        py = _run_python_until_stall(rec_projs, vec["input"], max_steps=200)
        js = _run_js_action("run_recurrence_with_bridge", vec["input"], max_steps=200)
        assert mu_equal(py, js), f"recurrence parity mismatch for vector {vec['id']}: py={py} js={js}"


def test_gate5_exhaustion_python_js_parity_vectors():
    exh_projs = _load_projections("exhaustion.v1.json")
    vectors = json.loads((FIXTURES / "exhaustion_vectors.json").read_text(encoding="utf-8"))["vectors"]
    for vec in vectors:
        py = _run_python_until_stall(exh_projs, vec["input"], max_steps=200)
        js = _run_js_action("run_exhaustion_with_bridge", vec["input"], max_steps=200)
        assert mu_equal(py, js), f"exhaustion parity mismatch for vector {vec['id']}: py={py} js={js}"


def test_gate5_run_mu_structural_matches_bridge_nonlinear_semantics():
    projections = [
        {
            "id": "nonlinear.eq",
            "pattern": {"a": {"var": "x"}, "b": {"var": "x"}},
            "body": "ok",
        }
    ]
    input_value = {"a": 1, "b": 2}

    trace_result = run_mu_structural(projections, input_value, max_steps=3)
    bridge_result = step_kernel_mu(
        projections,
        input_value,
        kernel_mode="bridge",
        validation_mode="domain",
    )

    assert trace_result["stall"] is True
    assert mu_equal(trace_result["result"], input_value)
    assert mu_equal(trace_result["result"], bridge_result)


def test_gate5_run_mu_structural_records_projection_id_via_bridge_path():
    projections = [
        {
            "id": "nonlinear.eq",
            "pattern": {"a": {"var": "x"}, "b": {"var": "x"}},
            "body": "ok",
        }
    ]
    input_value = {"a": 1, "b": 1}

    trace_result = run_mu_structural(projections, input_value, max_steps=3)
    first_entry = trace_result["trace"]["head"]

    assert first_entry["projection"] == "nonlinear.eq"


def test_gate5_run_mu_structural_identity_match_keeps_projection_id():
    projections = [{"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}}]
    trace_result = run_mu_structural(projections, {"x": 1}, max_steps=3)
    first_entry = trace_result["trace"]["head"]
    assert first_entry["projection"] == "identity"


# =============================================================================
# Cross-substrate structural trace parity tests
# =============================================================================

def _run_js_structural_trace(projections, input_value, max_steps=10):
    """Run JS structural trace via JSON API and return trace array."""
    req = json.dumps({
        "action": "run_structural_trace",
        "projections": projections,
        "input": input_value,
        "maxSteps": max_steps,
    })
    proc = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", req],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    last = None
    for line in proc.stdout.splitlines():
        if line.startswith("JSON_API_RESPONSE:"):
            last = json.loads(line[len("JSON_API_RESPONSE:"):])
    assert last is not None, f"no JSON_API_RESPONSE in stdout: {proc.stdout[:500]}"
    assert last.get("success"), f"js action failed: {last.get('error')}"
    return last


def test_gate5_cross_substrate_identity_trace_projection_id():
    """Identity projection must keep projection ID in trace on BOTH substrates.

    Regression test for JS stepKernel stall detection bug: value equality
    misclassified identity projections as stalls, losing projection ID.
    Fix: JS uses kernel terminal state (_stall field) like Python.
    """
    projections = [{"id": "identity", "pattern": {"var": "x"}, "body": {"var": "x"}}]
    input_value = {"x": 1}

    # Python
    py_trace = run_mu_structural(projections, input_value, max_steps=5)
    py_first = py_trace["trace"]["head"]
    assert py_first["projection"] == "identity", (
        f"Python lost identity projection ID: {py_first}"
    )

    # JS
    js_result = _run_js_structural_trace(projections, input_value, max_steps=5)
    js_first = js_result["trace"][0]
    assert js_first["projection"] == "identity", (
        f"JS lost identity projection ID: {js_first}"
    )

    # Cross-substrate: both must agree
    assert py_first["projection"] == js_first["projection"], (
        f"Trace projection ID mismatch: Python={py_first['projection']}, JS={js_first['projection']}"
    )


def test_gate5_cross_substrate_transform_trace_projection_id():
    """Non-identity transform must track projection ID on both substrates."""
    projections = [
        {"id": "double", "pattern": {"op": "double", "value": {"var": "v"}},
         "body": {"op": "doubled", "value": {"var": "v"}}},
    ]
    input_value = {"op": "double", "value": 42}

    # Python
    py_trace = run_mu_structural(projections, input_value, max_steps=5)
    py_first = py_trace["trace"]["head"]
    assert py_first["projection"] == "double"

    # JS
    js_result = _run_js_structural_trace(projections, input_value, max_steps=5)
    js_first = js_result["trace"][0]
    assert js_first["projection"] == "double"

    # Both results should match
    assert mu_equal(py_trace["result"], js_result["result"])
