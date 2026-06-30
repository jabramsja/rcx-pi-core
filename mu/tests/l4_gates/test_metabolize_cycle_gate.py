"""
L4 Gate: metabolize_cycle.v1.json structural walker verification.

Proves the L4_STRUCTURAL semantic shift: metabolization cycle is wired
into run_engine_with_routing and correctly routes sink/lobes entries
in BOTH substrates.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_metabolize_cycle_gate.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.engine_pipeline import (
    run_hemisphere_routing,  # SPEED_OK: boundary wrapper tested via run_mu_structural
    run_metabolization_cycle,  # SPEED_OK: boundary wrapper tested via run_mu
    count_hemisphere_entries,
)
from rcx_pi.selfhost.seed_integrity import (
    load_verified_seed,
    get_seed_path,
    EXPECTED_PROJECTION_IDS,
)
from tests.helpers.structural_numbers import sn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _js_request(action, **kwargs):
    """Send a JSON API request to eval_step.js and return the parsed response."""
    request = {"action": action, **kwargs}
    js_path = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
    result = subprocess.run(
        ["node", str(js_path), "--json-api", json.dumps(request)],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(f"No JSON_API_RESPONSE in JS output: {result.stdout[:300]}")


def _empty_hemispheres():
    return {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


def _make_entry(state, closure_flag=False, origin="test"):
    return {"state": state, "closure_flag": closure_flag, "origin": origin}


# ---------------------------------------------------------------------------
# Gate Tests
# ---------------------------------------------------------------------------

class TestMetabolizeCycleSeedGate:
    """Gate: metabolize_cycle.v1.json loaded and verified in Python."""

    def test_seed_loads_with_15_projections(self):
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        assert len(seed["projections"]) == 15

    def test_projection_ids_registered(self):
        assert "metabolize_cycle.v1.json" in EXPECTED_PROJECTION_IDS
        assert len(EXPECTED_PROJECTION_IDS["metabolize_cycle.v1.json"]) == 15


class TestMetabolizeCycleJSParityGate:
    """Gate: JS substrate loads metabolize_cycle and handles the API action."""

    def test_js_loads_metabolize_cycle_seed(self):
        resp = _js_request("get_constants")
        assert resp["success"]
        assert resp["seed_count"] == 16

    def test_js_metabolize_cycle_empty_noop(self):
        h = _empty_hemispheres()
        resp = _js_request("run_metabolization_cycle", hemispheres=h)
        assert resp["success"]
        assert resp["result"] == h

    def test_js_metabolize_cycle_sink_routing(self):
        h = _empty_hemispheres()
        h["sink"] = [_make_entry("val")]
        resp = _js_request("run_metabolization_cycle", hemispheres=h)
        assert resp["success"]
        result = resp["result"]
        assert result["sink"] is None
        assert len(result["r_inf"]) == 1
        assert result["r_inf"][0]["origin"] == "metabolized"

    def test_js_rejects_malformed_entry(self):
        h = _empty_hemispheres()
        h["r_null"] = [1]
        resp = _js_request("run_metabolization_cycle", hemispheres=h)
        assert not resp["success"]
        assert resp["error_code"] == "input.shape_mismatch"


class TestHemisphereNumeralRoutingGate:
    """Gate: host-int engine_result routing is structural before projection match."""

    def test_python_boundary_routes_host_int_value_and_tau_step(self):
        engine_result = {
            "value": 42,
            "closure_detected": True,
            "tau_step": 3,
            "exhaustion_detected": False,
            "operator_frozen": False,
            "frozen_set": None,
            "action": None,
            "stall": True,
        }

        # SPEED_OK: exact NR-1 production boundary regression requires run_mu_structural.
        result = run_hemisphere_routing(engine_result, _empty_hemispheres())

        assert set(result) == {"r_null", "r_inf", "r_a", "lobes", "sink"}
        populated = [k for k in ("r_null", "r_inf", "r_a", "lobes", "sink") if result[k] is not None]
        assert populated == ["r_a"]
        assert mu_equal(result["r_a"][0]["state"], sn(42))
        assert result["r_a"][0]["closure_flag"] is True

    def test_js_boundary_routes_host_int_value_and_tau_step_at_json_api(self):
        engine_result = {
            "value": 42,
            "closure_detected": True,
            "tau_step": 3,
            "exhaustion_detected": False,
            "operator_frozen": False,
            "frozen_set": None,
            "action": None,
            "stall": True,
        }

        # SPEED_OK: exact NR-1 JSON API parity vector requires node.
        resp = _js_request(
            "run_hemisphere_routing",
            engine_result=engine_result,
            hemispheres=_empty_hemispheres(),
        )

        assert resp["success"], resp.get("error")
        result = resp["result"]
        assert set(result) == {"r_null", "r_inf", "r_a", "lobes", "sink"}
        populated = [k for k in ("r_null", "r_inf", "r_a", "lobes", "sink") if result[k] is not None]
        assert populated == ["r_a"]
        assert mu_equal(result["r_a"][0]["state"], sn(42))
        assert result["r_a"][0]["closure_flag"] is True

    def test_js_boundary_rejects_fractional_numeric_leaf_at_json_api(self):
        engine_result = {
            "value": 3.5,
            "closure_detected": True,
            "tau_step": 3,
            "exhaustion_detected": False,
            "operator_frozen": False,
            "frozen_set": None,
            "action": None,
            "stall": True,
        }

        # SPEED_OK: exact NR-1 JSON API numeric-boundary guard requires node.
        resp = _js_request(
            "run_hemisphere_routing",
            engine_result=engine_result,
            hemispheres=_empty_hemispheres(),
        )

        assert not resp["success"]
        assert resp.get("error_code") == "input.invalid_type"
        assert "numeric leaf must be an integer" in resp.get("error", "")


@pytest.mark.slow
@pytest.mark.l4_expensive
class TestMetabolizeCycleWiringGate:
    """Gate: metabolization is wired into run_engine_with_routing."""

    def test_python_metabolize_sink_to_r_null(self):
        """Sink entry with null state routes to r_null."""
        h = _empty_hemispheres()
        h["sink"] = [_make_entry(None)]
        result = run_metabolization_cycle(h)
        assert result["sink"] is None
        assert len(result["r_null"]) == 1
        assert result["r_null"][0]["origin"] == "metabolized"

    def test_python_metabolize_lobes_promote(self):
        """Lobes entry with closure_flag=True promotes to r_a."""
        h = _empty_hemispheres()
        h["lobes"] = [_make_entry("closed", closure_flag=True)]
        result = run_metabolization_cycle(h)
        assert result["lobes"] is None
        assert len(result["r_a"]) == 1
        assert result["r_a"][0]["origin"] == "promoted"
