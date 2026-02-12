"""
Hemisphere cross-substrate parity tests.

Verifies that hemisphere routing produces identical results on Python and
JavaScript substrates. Same projections, same inputs, same outputs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
from rcx_pi.selfhost.step_mu import run_mu


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def _load_hemisphere_projections() -> list[dict]:
    seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
    return seed["projections"]


def _run_python(projs, input_val, max_steps=20):
    result, trace, stall = run_mu(projs, input_val, max_steps=max_steps)
    return result


def _run_js(input_val, max_steps=100):
    req = json.dumps({"action": "run_hemisphere", "input": input_val, "maxSteps": max_steps})
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


def _load_vectors():
    with open(FIXTURES / "hemisphere_vectors.json") as f:
        return json.load(f)["vectors"]


@pytest.mark.slow
class TestHemisphereCrossSubstrateParity:
    """Python and JS produce identical hemisphere routing results."""

    @pytest.fixture
    def projs(self):
        return _load_hemisphere_projections()

    @pytest.fixture
    def vectors(self):
        return _load_vectors()

    def _compare(self, projs, input_val, vector_id):
        py_result = _run_python(projs, input_val)
        js_result = _run_js(input_val)
        assert mu_equal(py_result, js_result), (
            f"Parity failure for {vector_id}:\n"
            f"  Python: {json.dumps(py_result, default=str)[:200]}\n"
            f"  JS:     {json.dumps(js_result, default=str)[:200]}"
        )
        return py_result

    def test_route_null_value_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_null_value")
        result = self._compare(projs, v["input"], v["id"])
        assert result[v["expected_target"]] is not None

    def test_route_closure_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_closure")
        result = self._compare(projs, v["input"], v["id"])
        assert result[v["expected_target"]] is not None

    def test_route_default_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_default")
        result = self._compare(projs, v["input"], v["id"])
        assert result[v["expected_target"]] is not None

    def test_route_null_with_closure_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_null_with_closure")
        result = self._compare(projs, v["input"], v["id"])
        assert result["r_null"] is not None
        assert result["r_a"] is None

    def test_route_nested_value_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_nested_value")
        result = self._compare(projs, v["input"], v["id"])
        assert result[v["expected_target"]] is not None

    def test_route_preserves_existing_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_preserves_existing")
        result = self._compare(projs, v["input"], v["id"])
        assert len(result["lobes"]) == v["expected_lobes_count"]
        assert len(result["r_a"]) == v["expected_existing_r_a_count"]


class TestHemisphereProjectionCountParity:
    """Verify JS loads same number of hemisphere projections as Python."""

    def test_projection_count_matches(self):
        py_seed = load_verified_seed(get_seed_path("hemispheres.v1.json"))
        py_count = len(py_seed["projections"])

        req = json.dumps({"action": "get_constants"})
        proc = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", req],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        last = None
        for line in proc.stdout.splitlines():
            if line.startswith("JSON_API_RESPONSE:"):
                last = json.loads(line[len("JSON_API_RESPONSE:"):])
        assert last is not None
        assert last["success"]
        js_count = last["hemisphere_projection_count"]

        assert py_count == js_count == 12, (
            f"Projection count mismatch: Python={py_count}, JS={js_count}"
        )
