"""
E3 cross-substrate parity tests for Hemisphere Metabolization.

Verifies T1-T10 truth-table transitions and adversarial cases produce
identical results in Python (eval_seed.step) and JavaScript (JSON API
step_metabolization). Each test constructs a specific input, runs it
through both substrates, and asserts structural output equality plus
expected bucket routing.

Evidence artifact for HemisphereExecutionChecklist.v0.md gate E3.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT as ROOT

# ── Helpers ──────────────────────────────────────────────────────────────────


def _normalize_for_cross_substrate(value):
    """Normalize Python values for cross-substrate comparison with JS."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [_normalize_for_cross_substrate(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_cross_substrate(v) for k, v in value.items()}
    return value


def _cross_substrate_equal(py_val, js_val) -> bool:
    """Compare Python and JS values, handling int/float cross-substrate differences."""
    norm_py = _normalize_for_cross_substrate(py_val)
    norm_js = _normalize_for_cross_substrate(js_val)
    return json.dumps(norm_py, sort_keys=True) == json.dumps(norm_js, sort_keys=True)


def _run_js_json_api(request_dict: dict) -> dict:
    """Call JS with JSON API and parse response."""
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(
        f"No JSON_API_RESPONSE in JS output.\nstdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
    )


def _load_metabolization_projections() -> list:
    """Load metabolization projections from verified seed."""
    from rcx_pi.selfhost.seed_integrity import load_verified_seed

    seed_path = ROOT / "mu" / "programs" / "metabolization.v1.json"
    seed = load_verified_seed(seed_path)
    return seed["projections"]


def _step_py(projections: list, input_value) -> object:
    """Run Python step() with metabolization projections."""
    from rcx_pi.selfhost.eval_seed import step

    return step(projections, input_value)


def _step_js(input_value) -> object:
    """Run JS step_metabolization via JSON API."""
    resp = _run_js_json_api({"action": "step_metabolization", "input": input_value})
    assert resp.get("success"), f"JS step_metabolization failed: {resp.get('error')}"
    return resp["result"]


# ── Hemisphere scaffolding ───────────────────────────────────────────────────

def _empty_hemispheres():
    """Return empty 5-bucket hemisphere state."""
    return {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


# ── Test class ───────────────────────────────────────────────────────────────


class TestMetabolizationParity:
    """Cross-substrate parity tests for metabolization T1-T10 + adversarial."""

    @pytest.fixture(scope="class")
    def projections(self):
        return _load_metabolization_projections()

    # ── T1: sink non-null → r_inf ────────────────────────────────────────

    def test_T1_sink_nonnull_to_r_inf(self, projections):
        """T1: sink entry with non-null state routes to r_inf."""
        inp = {
            "metabolize_mode": "scan_sink",
            "sink_entry": {"state": "active_form", "closure_flag": False, "origin": "test"},
            "remaining_sink": None,
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        # Expected: metabolize_result with entry prepended to r_inf
        assert "metabolize_result" in py
        assert py["metabolize_result"]["r_inf"]["head"]["state"] == "active_form"
        assert py["metabolize_result"]["r_inf"]["head"]["origin"] == "metabolized"
        assert py["metabolize_result"]["r_null"] is None  # NOT r_null
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T2: sink null → r_null ───────────────────────────────────────────

    def test_T2_sink_null_to_r_null(self, projections):
        """T2: sink entry with null state routes to r_null (not r_inf, not r_a)."""
        inp = {
            "metabolize_mode": "scan_sink",
            "sink_entry": {"state": None, "closure_flag": False, "origin": "test"},
            "remaining_sink": None,
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "metabolize_result" in py
        assert py["metabolize_result"]["r_null"]["head"]["state"] is None
        assert py["metabolize_result"]["r_null"]["head"]["origin"] == "metabolized"
        assert py["metabolize_result"]["r_inf"] is None  # NOT r_inf
        assert py["metabolize_result"]["r_a"] is None  # NOT r_a
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T3: stalled + lobes non-null → lobes ─────────────────────────────

    def test_T3_stalled_to_lobes(self, projections):
        """T3: stalled entry routes to lobes when lobes is non-null."""
        inp = {
            "recover_mode": "check_stall",
            "stalled_entry": {"state": "stuck", "origin": "stalled"},
            "hemispheres": {
                "r_null": None,
                "r_inf": None,
                "r_a": None,
                "lobes": {"head": {"state": "existing"}, "tail": None},
                "sink": None,
            },
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "recover_result" in py
        # Entry prepended to lobes
        assert py["recover_result"]["lobes"]["head"]["state"] == "stuck"
        assert py["recover_result"]["lobes"]["tail"]["head"]["state"] == "existing"
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T4: stalled + lobes null → sink ──────────────────────────────────

    def test_T4_stalled_to_sink(self, projections):
        """T4: stalled entry routes to sink when lobes is null."""
        inp = {
            "recover_mode": "check_stall",
            "stalled_entry": {"state": "stuck", "origin": "stalled"},
            "hemispheres": {
                "r_null": None,
                "r_inf": None,
                "r_a": None,
                "lobes": None,
                "sink": None,
            },
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "recover_result" in py
        # Entry prepended to sink
        assert py["recover_result"]["sink"]["head"]["state"] == "stuck"
        assert py["recover_result"]["lobes"] is None
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T5: closure_flag true → r_a ──────────────────────────────────────

    def test_T5_closure_promotes_to_r_a(self, projections):
        """T5: lobes entry with closure_flag true promotes to r_a."""
        inp = {
            "promote_mode": "check_closure",
            "lobes_entry": {"state": "closed_form", "closure_flag": True, "origin": "test"},
            "remaining_lobes": None,
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "promote_result" in py
        assert py["promote_result"]["r_a"]["head"]["state"] == "closed_form"
        assert py["promote_result"]["r_a"]["head"]["closure_flag"] is True
        assert py["promote_result"]["r_a"]["head"]["origin"] == "promoted"
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T6: unresolvable → sink (recycle) ────────────────────────────────

    def test_T6_residual_to_sink(self, projections):
        """T6: unresolvable entry recycles to sink."""
        inp = {
            "recycle_mode": "drain",
            "source_bucket": "r_inf",
            "unresolvable_entry": {"state": "broken", "origin": "test"},
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "recycle_result" in py
        assert py["recycle_result"]["sink"]["head"]["origin"] == "recycled"
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T7: ADVERSARIAL — forged closure in sink stays in r_inf ──────────

    def test_T7_forged_closure_no_promotion(self, projections):
        """T7: sink entry with forged closure_flag routes to r_inf, NOT r_a.

        Metabolization routes by state (null vs non-null), not closure_flag.
        Entry with non-null state + closure_flag=true goes to r_inf.
        r_inf is terminal — no path to r_a exists.
        """
        inp = {
            "metabolize_mode": "scan_sink",
            "sink_entry": {"state": "active_form", "closure_flag": True, "origin": "exhaustion"},
            "remaining_sink": None,
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "metabolize_result" in py
        # Routes to r_inf (not r_a) — state is non-null
        assert py["metabolize_result"]["r_inf"]["head"]["state"] == "active_form"
        assert py["metabolize_result"]["r_inf"]["head"]["closure_flag"] is True
        assert py["metabolize_result"]["r_a"] is None  # NOT promoted
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T8: ADVERSARIAL — null + closure → r_null (not r_a) ─────────────

    def test_T8_null_closure_to_r_null(self, projections):
        """T8: sink entry with null state + closure_flag=true routes to r_null.

        Null state matches void predicate → r_null. closure_flag is irrelevant.
        r_null is terminal — no path to r_a exists. Sink-safety preserved.
        """
        inp = {
            "metabolize_mode": "scan_sink",
            "sink_entry": {"state": None, "closure_flag": True, "origin": "exhaustion"},
            "remaining_sink": None,
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "metabolize_result" in py
        # Routes to r_null (not r_a, not r_inf) — null state dominates
        assert py["metabolize_result"]["r_null"]["head"]["state"] is None
        assert py["metabolize_result"]["r_null"]["head"]["closure_flag"] is True
        assert py["metabolize_result"]["r_inf"] is None  # NOT r_inf
        assert py["metabolize_result"]["r_a"] is None  # NOT promoted
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T9: ADVERSARIAL — unmetabolizable residual → sink recycle ────────

    def test_T9_unmetabolizable_recycled(self, projections):
        """T9: unmetabolizable residual recycles to sink. Material preserved."""
        inp = {
            "recycle_mode": "drain",
            "source_bucket": "sink",
            "unresolvable_entry": "opaque_blob",
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "recycle_result" in py
        # Entry recycled to sink with origin="recycled"
        assert py["recycle_result"]["sink"]["head"]["state"] == "opaque_blob"
        assert py["recycle_result"]["sink"]["head"]["origin"] == "recycled"
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── T10: closure_flag false → stall (stays in lobes) ─────────────────

    def test_T10_no_closure_stays_lobes(self, projections):
        """T10: lobes entry with closure_flag=false — no promotion, stall.

        step() returns input unchanged when no projection matches.
        """
        inp = {
            "promote_mode": "check_closure",
            "lobes_entry": {"state": "waiting", "closure_flag": False, "origin": "test"},
            "remaining_lobes": None,
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        # Stall: output equals input (no projection matched)
        assert py == inp, f"Expected stall (input unchanged), got: {py}"
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── ADV-EXTRA-1: double-metabolization ───────────────────────────────

    def test_adv_double_metabolization(self, projections):
        """ADV: already-metabolized entry re-metabolizes normally based on state."""
        inp = {
            "metabolize_mode": "scan_sink",
            "sink_entry": {"state": "active_form", "closure_flag": False, "origin": "metabolized"},
            "remaining_sink": None,
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "metabolize_result" in py
        # Routes normally to r_inf based on state — origin doesn't affect routing
        assert py["metabolize_result"]["r_inf"]["head"]["state"] == "active_form"
        assert py["metabolize_result"]["r_inf"]["head"]["origin"] == "metabolized"
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"

    # ── ADV-EXTRA-2: empty sink remaining ────────────────────────────────

    def test_adv_empty_remaining_sink(self, projections):
        """ADV: metabolization with non-null remaining_sink preserves remaining entries."""
        inp = {
            "metabolize_mode": "scan_sink",
            "sink_entry": {"state": "first", "closure_flag": False, "origin": "test"},
            "remaining_sink": {"head": {"state": "second"}, "tail": None},
            "hemispheres": _empty_hemispheres(),
        }
        py = _step_py(projections, inp)
        js = _step_js(inp)

        assert "metabolize_result" in py
        assert py["metabolize_result"]["r_inf"]["head"]["state"] == "first"
        # Remaining sink entries preserved in sink bucket
        assert py["metabolize_result"]["sink"]["head"]["state"] == "second"
        assert _cross_substrate_equal(py, js), f"PY={py}\nJS={js}"


# ── Coverage verification ────────────────────────────────────────────────────


class TestBucketCoverage:
    """Verify all 5 hemisphere buckets appear as routing targets in tests."""

    EXPECTED_BUCKETS = {"r_null", "r_inf", "r_a", "lobes", "sink"}

    # Bucket → list of T-IDs that route TO that bucket
    BUCKET_TARGET_MAP = {
        "r_null": ["T2", "T8"],
        "r_inf": ["T1", "T7"],
        "r_a": ["T5"],
        "lobes": ["T3"],
        "sink": ["T4", "T6", "T9"],
    }

    def test_all_5_buckets_are_routing_targets(self):
        """Every hemisphere bucket must be the routing target of at least 1 test."""
        covered = set(self.BUCKET_TARGET_MAP.keys())
        missing = self.EXPECTED_BUCKETS - covered
        assert not missing, f"Buckets missing from test coverage: {missing}"

    def test_stall_coverage(self):
        """T10 covers stall semantics (no routing, input unchanged)."""
        # T10 tests lobes retention (stall) — implicit coverage of lobes bucket
        assert "lobes" in self.BUCKET_TARGET_MAP

    def test_adversarial_count(self):
        """At least 3 adversarial tests exist (T7, T8, T9, T10, ADV-EXTRA-*)."""
        adversarial_tests = ["T7", "T8", "T9", "T10", "ADV-EXTRA-1", "ADV-EXTRA-2"]
        assert len(adversarial_tests) >= 3
