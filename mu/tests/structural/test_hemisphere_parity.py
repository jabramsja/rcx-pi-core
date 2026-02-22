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

from tests.hemisphere_helpers import load_hemisphere_projections as _load_hemisphere_projections


ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


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

    def test_route_exhaustion_to_sink_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_exhaustion_to_sink")
        result = self._compare(projs, v["input"], v["id"])
        assert result["sink"] is not None

    def test_route_stall_to_r_inf_parity(self, projs, vectors):
        v = next(x for x in vectors if x["id"] == "route_stall_to_r_inf")
        result = self._compare(projs, v["input"], v["id"])
        assert result["r_inf"] is not None


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


# =============================================================================
# TestCurrentEnforcedParityFalsification (F5-F8)
# =============================================================================


def _js_api(request_dict):
    """Send a JSON API request to JS and return the parsed response."""
    req = json.dumps(request_dict)
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
    return last


def _make_engine_result_dict(
    value=None, closure_detected=False, exhaustion_detected=False,
    stall=False, tau_step=None, operator_frozen=None,
    frozen_set=None, action="continue",
):
    return {
        "value": value,
        "closure_detected": closure_detected,
        "tau_step": tau_step,
        "exhaustion_detected": exhaustion_detected,
        "operator_frozen": operator_frozen,
        "frozen_set": frozen_set,
        "action": action,
        "stall": stall,
    }


def _empty_hemi():
    return {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


@pytest.mark.slow
class TestCurrentEnforcedParityFalsification:
    """CURRENT_ENFORCED cross-substrate falsification tests F5-F8.

    These tests verify that Python and JS agree on hemisphere routing
    results AND failure behavior.
    """

    def test_f5_identical_engine_result_identical_hemispheres(self):
        """F5: Same engine_result → structurally equal hemisphere dicts."""
        projs = _load_hemisphere_projections()
        er = _make_engine_result_dict(value="parity_check", closure_detected=True)
        hemispheres = _empty_hemi()
        input_val = {"route_hemisphere": {"engine_result": er, "hemispheres": hemispheres}}

        py_result = _run_python(projs, input_val)
        js_result = _run_js(input_val)

        assert mu_equal(py_result, js_result), (
            f"F5 parity failure:\n"
            f"  Python: {json.dumps(py_result, default=str)[:300]}\n"
            f"  JS:     {json.dumps(js_result, default=str)[:300]}"
        )
        # Confirm it went to r_a (closure=true)
        assert py_result["r_a"] is not None

    def test_f6_extra_key_both_reject(self):
        """F6: engine_result with extra key → both substrates reject.

        Python raises via run_hemisphere_routing shape check.
        JS returns {success: false, error_code: ...} via JSON API.
        Both must fail-closed — equivalent failure category.
        """
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing

        er = _make_engine_result_dict(value="test")
        er["extra_bogus_key"] = "should_not_be_here"  # 9 keys instead of 8

        # Python: run_hemisphere_routing should fail because hemisphere.init
        # pattern expects exactly 8 fields — extra key prevents match.
        # The routing stalls and fails shape check.
        py_failed = False
        try:
            run_hemisphere_routing(er, _empty_hemi())
        except (RuntimeError, ValueError):
            py_failed = True
        assert py_failed, "Python must reject engine_result with extra key"

        # JS: run_hemisphere_routing via JSON API
        js_resp = _js_api({
            "action": "run_hemisphere_routing",
            "engine_result": er,
            "hemispheres": _empty_hemi(),
        })
        assert not js_resp["success"], "JS must reject engine_result with extra key"
        # Verify equivalent failure category (not same class name)
        assert "error_code" in js_resp, "JS must return error_code on failure"
        allowed = {"api.bad_request", "input.shape_mismatch"}
        assert js_resp["error_code"] in allowed, (
            f"JS error_code should be one of {allowed}, got '{js_resp['error_code']}'"
        )

    def test_f7_null_engine_result_both_fail_closed(self):
        """F7: null engine_result → both fail-closed with equivalent failure category.

        Python raises ValueError; JS returns {success: false, error_code: "input.invalid_type"}.
        Parity is on failure category, not exception class name.
        """
        from rcx_pi.selfhost.step_mu import run_hemisphere_routing

        # Python: ValueError expected
        py_error_type = None
        try:
            run_hemisphere_routing(None, _empty_hemi())
        except ValueError:
            py_error_type = "invalid_type"
        except TypeError:
            py_error_type = "invalid_type"
        assert py_error_type == "invalid_type", (
            "Python must raise ValueError/TypeError for null engine_result"
        )

        # JS: error_code should indicate type/input error
        js_resp = _js_api({
            "action": "run_hemisphere_routing",
            "engine_result": None,
            "hemispheres": _empty_hemi(),
        })
        assert not js_resp["success"], "JS must reject null engine_result"
        assert js_resp.get("error_code") == "input.invalid_type", (
            f"JS error_code should be 'input.invalid_type', got '{js_resp.get('error_code')}'"
        )

    def test_f8_six_key_hemispheres_both_reject(self):
        """F8: hemispheres with 6 keys (extra key) → both reject before routing.

        Both substrates must reject the malformed hemisphere dict.
        """
        from rcx_pi.selfhost.step_mu import run_engine_with_routing

        bad_hemi = _empty_hemi()
        bad_hemi["extra_bucket"] = None  # 6 keys

        # Python: run_engine_with_routing validates hemisphere shape on input
        py_failed = False
        try:
            run_engine_with_routing([], "dummy", hemispheres=bad_hemi)
        except (ValueError, TypeError, RuntimeError):
            py_failed = True
        assert py_failed, "Python must reject hemispheres with 6 keys"

        # JS: run_engine_with_routing via JSON API
        js_resp = _js_api({
            "action": "run_engine_with_routing",
            "input": "dummy",
            "hemispheres": bad_hemi,
        })
        assert not js_resp["success"], "JS must reject hemispheres with 6 keys"
        assert js_resp.get("error_code") == "input.shape_mismatch", (
            f"JS error_code should be 'input.shape_mismatch', got '{js_resp.get('error_code')}'"
        )
