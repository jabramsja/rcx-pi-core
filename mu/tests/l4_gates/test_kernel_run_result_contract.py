"""
KernelRunResult contract lock tests.

Verifies that step_kernel_mu (Python) and _stepKernelCore (JS) both produce
the canonical KernelRunResult shape with identical fields and semantics.

These tests lock the contract defined in the Canonical Machine Contract
design packet (v3, 2026-03-16).
"""

from __future__ import annotations

import ast
import json
import subprocess

import pytest

from rcx_pi.selfhost.step_mu import step_kernel_mu
from tests.repo_root import REPO_ROOT


# -- KernelRunResult shape contract --

REQUIRED_FIELDS = {"output", "stall", "termination_reason", "steps_used", "max_steps"}
VALID_TERM_REASONS = {
    "projection_applied",
    "kernel_stall",
    "hash_stall",
    "max_steps_exhausted",
    "fuel_exhausted",
}
FUEL_FIELDS = {"fuel_supplied", "fuel_remaining", "fuel_exhausted"}
SHARED_RESULT_FIELDS = (
    "output",
    "stall",
    "termination_reason",
    "steps_used",
    "max_steps",
)
def _shared_kernel_result(meta: dict) -> dict:
    return {field: meta[field] for field in SHARED_RESULT_FIELDS}


def _make_kernel_fuel(count: int):
    fuel = None
    for _ in range(count):
        fuel = {"head": None, "tail": fuel}
    return fuel


def _fuel_remaining_count(fuel) -> int:
    count = 0
    cursor = fuel
    while cursor is not None:
        assert isinstance(cursor, dict), f"fuel cursor must be dict/null, got {type(cursor).__name__}"
        assert set(cursor) == {"head", "tail"}
        count += 1
        cursor = cursor["tail"]
    return count


class TestKernelRunResultPython:
    """Python step_kernel_mu(return_meta=True) must produce KernelRunResult."""

    def test_projection_applied_shape(self):
        """Successful projection produces all required fields."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        meta = step_kernel_mu(projs, {"x": 1}, return_meta=True)
        assert isinstance(meta, dict)
        assert REQUIRED_FIELDS <= set(meta.keys()), f"Missing fields: {REQUIRED_FIELDS - set(meta.keys())}"
        assert meta["termination_reason"] in VALID_TERM_REASONS
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert meta["output"] == {"x": 2}

    def test_kernel_stall_shape(self):
        """No matching projection produces kernel_stall with undefined_motif."""
        meta = step_kernel_mu([], {"x": 1}, return_meta=True)
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "kernel_stall"
        assert meta["stall"] is True
        assert "undefined_motif" in meta, "kernel_stall must include undefined_motif"
        assert meta["undefined_motif"]["_undefined"] is True

    def test_stall_shape(self):
        """Stall (kernel_stall or hash_stall) produces stall=True with required fields."""
        # No projections -> kernel_stall (no projection matches)
        meta = step_kernel_mu([], {"x": 1}, return_meta=True)
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] in ("hash_stall", "kernel_stall")
        assert meta["stall"] is True

    def test_max_steps_exhausted_shape(self):
        """Oscillating projection with low max_steps produces max_steps_exhausted."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        meta = step_kernel_mu(projs, {"s": "a"}, return_meta=True, max_steps=4)
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True, "NB4 fix: max_steps must have stall=True"
        assert meta["steps_used"] == 4

    def test_kernel_fuel_zero_exhausts_before_attempting_step(self):
        """Python kernel fuel uses explicit empty Mu fuel as execution authority."""
        meta = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}],
            {"x": 1},
            return_meta=True,
            max_steps=100,
            kernel_fuel=None,
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["output"] == {"x": 1}
        assert meta["steps_used"] == 0
        assert meta["max_steps"] == 100
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_exhaustion_is_authority_not_max_steps(self):
        """Python Mu fuel exhaustion terminates before the numeric watchdog cap."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        fuel_count = 4
        meta = step_kernel_mu(
            projs,
            {"s": "a"},
            return_meta=True,
            max_steps=100,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == fuel_count
        assert meta["max_steps"] == 100
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_numeric_watchdog_reports_remaining_fuel(self):
        """Python numeric cap is a watchdog when Mu fuel still remains."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        max_steps = 3
        fuel_count = 5
        meta = step_kernel_mu(
            projs,
            {"s": "a"},
            return_meta=True,
            max_steps=max_steps,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == max_steps
        assert meta["max_steps"] == max_steps
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - max_steps

    @pytest.mark.parametrize(
        "bad_max_steps",
        [
            pytest.param(float("nan"), id="nan"),
            pytest.param(float("inf"), id="positive-infinity"),
            pytest.param(float("-inf"), id="negative-infinity"),
        ],
    )
    def test_kernel_watchdog_rejects_non_finite_max_steps(self, bad_max_steps):
        """Python rejects non-finite watchdog values before the fuel driver can run."""
        with pytest.raises(ValueError, match="max_steps"):
            step_kernel_mu(
                [{"pattern": {"x": 1}, "body": {"x": 2}}],
                {"x": 1},
                return_meta=True,
                max_steps=bad_max_steps,
                kernel_fuel=_make_kernel_fuel(2),
            )

    def test_python_watchdog_guard_does_not_add_math_host_capability(self):
        """The watchdog guard must not import math into the runtime kernel."""
        step_mu_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        tree = ast.parse(step_mu_path.read_text(), filename=str(step_mu_path))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module.split(".", 1)[0])
        assert "math" not in imported_modules

    def test_kernel_fuel_success_reports_remaining_mu_fuel(self):
        """Python successful projection returns remaining Mu fuel."""
        fuel_count = 80
        meta = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}],
            {"x": 1},
            return_meta=True,
            max_steps=100,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert meta["output"] == {"x": 2}
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert 0 < meta["steps_used"] < fuel_count
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - meta["steps_used"]

    @pytest.mark.parametrize(
        "kernel_fuel",
        [
            [],
            {"head": None, "tail": 0},
            {"head": None, "tail": None, "extra": None},
        ],
    )
    def test_kernel_fuel_rejects_non_linked_mu_data(self, kernel_fuel):
        """Python kernel fuel fails closed when consumed fuel is not head/tail linked-list data."""
        projs = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        with pytest.raises(TypeError, match="kernel_fuel"):
            step_kernel_mu(
                projs,
                {"s": "a"},
                return_meta=True,
                max_steps=4,
                kernel_fuel=kernel_fuel,
            )

    def test_kernel_fuel_rejects_malformed_tail_before_returning_remaining(self):
        """Python validates the full fuel list before returning remaining fuel."""
        with pytest.raises(TypeError, match="kernel_fuel"):
            step_kernel_mu(
                [{"pattern": {"x": 1}, "body": {"x": 2}}],
                {"x": 1},
                return_meta=True,
                max_steps=100,
                kernel_fuel={"head": None, "tail": 0},
            )

    def test_undefined_motif_only_on_kernel_stall(self):
        """undefined_motif must NOT be present on non-kernel_stall results."""
        # projection_applied
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        meta = step_kernel_mu(projs, {"x": 1}, return_meta=True)
        assert "undefined_motif" not in meta, "undefined_motif must not appear on projection_applied"

        # max_steps_exhausted
        projs2 = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        meta2 = step_kernel_mu(projs2, {"s": "a"}, return_meta=True, max_steps=4)
        assert "undefined_motif" not in meta2, "undefined_motif must not appear on max_steps_exhausted"

    def test_return_meta_false_returns_bare_output(self):
        """return_meta=False returns bare Mu value, not KernelRunResult dict."""
        projs = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        result = step_kernel_mu(projs, {"x": 1}, return_meta=False)
        assert result == {"x": 2}
        assert not isinstance(result, dict) or "termination_reason" not in result


class TestKernelRunResultJS:
    """JS stepKernel via --json-api (live seeded kernel) must produce KernelRunResult."""

    def _run_json_api_response(self, payload: dict) -> dict:
        """Run JS via eval_step.js --json-api with real seed loading."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(payload)],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        # Extract JSON_API_RESPONSE from stdout (self-tests print first)
        stdout = result.stdout
        marker = "JSON_API_RESPONSE:"
        idx = stdout.find(marker)
        assert idx >= 0, f"No JSON_API_RESPONSE in output: {stdout[-200:]}"
        json_str = stdout[idx + len(marker):]
        return json.loads(json_str.strip())

    def _run_json_api(self, payload: dict) -> dict:
        resp = self._run_json_api_response(payload)
        assert resp.get("success"), f"JS API error: {resp.get('error', 'unknown')}"
        return resp["result"]

    def _run_direct_step_kernel_with_max_steps(self, max_steps_expr: str) -> dict:
        script = f"""
const {{ stepKernel }} = require('./mu/host/js/engine/kernel');
try {{
  stepKernel(
    [],
    {{ x: 1 }},
    [{{ pattern: {{ x: 1 }}, body: {{ x: 2 }} }}],
    {{
      returnMeta: true,
      maxSteps: {max_steps_expr},
      kernelFuel: {{ head: null, tail: {{ head: null, tail: null }} }},
    }}
  );
  console.log(JSON.stringify({{ success: true }}));
}} catch (e) {{
  console.log(JSON.stringify({{
    success: false,
    error_code: e.error_code || null,
    error: e.message,
  }}));
}}
"""
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=15,
        )
        assert result.returncode == 0, f"JS direct stepKernel error: {result.stderr}"
        return json.loads(result.stdout.strip())

    def test_projection_applied_has_required_fields(self):
        """JS live kernel produces KernelRunResult on successful projection."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
        })
        assert REQUIRED_FIELDS <= set(meta.keys()), f"JS missing: {REQUIRED_FIELDS - set(meta.keys())}"
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert isinstance(meta["steps_used"], int)
        assert isinstance(meta["max_steps"], int)
        assert not (FUEL_FIELDS & set(meta)), "default path must not emit fuel metadata"

    def test_kernel_stall_has_required_fields(self):
        """JS live kernel produces KernelRunResult on stall."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [],
            "input": {"x": 1},
            "maxSteps": 100,
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "kernel_stall"
        assert meta["stall"] is True
        assert not (FUEL_FIELDS & set(meta)), "default path must not emit fuel metadata"

    def test_max_steps_stall_true(self):
        """JS live kernel: max_steps must have stall=true (NB4 parity)."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [
                {"pattern": {"s": "a"}, "body": {"s": "b"}},
                {"pattern": {"s": "b"}, "body": {"s": "a"}},
            ],
            "input": {"s": "a"},
            "maxSteps": 4,
        })
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True, "JS NB4: max_steps must have stall=true"
        assert not (FUEL_FIELDS & set(meta)), "default path must not emit fuel metadata"

    def test_kernel_fuel_zero_exhausts_before_attempting_step(self):
        """JS live kernel consumes no step when caller supplies empty Mu fuel."""
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
            "kernelFuel": None,
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["output"] == {"x": 1}
        assert meta["steps_used"] == 0
        assert meta["max_steps"] == 100
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_exhaustion_consumes_one_node_per_kernel_step(self):
        """JS live kernel classifies exact structural-fuel exhaustion at maxSteps."""
        fuel_count = 3
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [
                {"pattern": {"s": "a"}, "body": {"s": "b"}},
                {"pattern": {"s": "b"}, "body": {"s": "a"}},
            ],
            "input": {"s": "a"},
            "maxSteps": fuel_count,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "fuel_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == fuel_count
        assert meta["max_steps"] == fuel_count
        assert meta["fuel_supplied"] is True
        assert meta["fuel_remaining"] is None
        assert meta["fuel_exhausted"] is True

    def test_kernel_fuel_numeric_watchdog_reports_remaining_fuel(self):
        """JS live kernel reports watchdog exhaustion while Mu fuel remains."""
        max_steps = 3
        fuel_count = 5
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [
                {"pattern": {"s": "a"}, "body": {"s": "b"}},
                {"pattern": {"s": "b"}, "body": {"s": "a"}},
            ],
            "input": {"s": "a"},
            "maxSteps": max_steps,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "max_steps_exhausted"
        assert meta["stall"] is True
        assert meta["steps_used"] == max_steps
        assert meta["max_steps"] == max_steps
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - max_steps

    @pytest.mark.parametrize(
        "max_steps_expr",
        [
            pytest.param("NaN", id="nan"),
            pytest.param("Infinity", id="positive-infinity"),
            pytest.param("-Infinity", id="negative-infinity"),
        ],
    )
    def test_direct_step_kernel_watchdog_rejects_non_finite_max_steps(self, max_steps_expr):
        """JS direct stepKernel rejects non-finite watchdog values before the fuel driver can run."""
        resp = self._run_direct_step_kernel_with_max_steps(max_steps_expr)
        assert resp["success"] is False
        assert resp.get("error_code") == "api.bad_request"
        assert "maxSteps" in resp.get("error", "")

    def test_kernel_fuel_success_reports_remaining_mu_fuel(self):
        """JS live kernel returns unconsumed Mu fuel when fuel exceeds required steps."""
        fuel_count = 80
        meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] == "projection_applied"
        assert meta["stall"] is False
        assert meta["output"] == {"x": 2}
        assert meta["fuel_supplied"] is True
        assert meta["fuel_exhausted"] is False
        assert 0 < meta["steps_used"] < fuel_count
        assert _fuel_remaining_count(meta["fuel_remaining"]) == fuel_count - meta["steps_used"]

    def test_kernel_fuel_success_shared_result_matches_python(self):
        """Fuel-backed JS success preserves the Python/JS KernelRunResult contract."""
        projections = [{"pattern": {"x": 1}, "body": {"x": 2}}]
        input_value = {"x": 1}
        max_steps = 100
        fuel_count = 80

        js_meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": projections,
            "input": input_value,
            "maxSteps": max_steps,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        py_meta = step_kernel_mu(
            projections,
            input_value,
            return_meta=True,
            max_steps=max_steps,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )

        assert _shared_kernel_result(js_meta) == _shared_kernel_result(py_meta)
        assert js_meta["fuel_supplied"] is True
        assert js_meta["fuel_exhausted"] is False
        assert _fuel_remaining_count(js_meta["fuel_remaining"]) == (
            fuel_count - py_meta["steps_used"]
        )

    def test_kernel_fuel_exhaustion_shared_result_matches_python_budget(self):
        """JS fuel exhaustion matches Python's shared fields for the same step budget."""
        projections = [
            {"pattern": {"s": "a"}, "body": {"s": "b"}},
            {"pattern": {"s": "b"}, "body": {"s": "a"}},
        ]
        input_value = {"s": "a"}
        fuel_count = 4
        max_steps = 100

        js_meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": projections,
            "input": input_value,
            "maxSteps": max_steps,
            "kernelFuel": _make_kernel_fuel(fuel_count),
        })
        py_meta = step_kernel_mu(
            projections,
            input_value,
            return_meta=True,
            max_steps=max_steps,
            kernel_fuel=_make_kernel_fuel(fuel_count),
        )

        assert js_meta["output"] == py_meta["output"]
        assert js_meta["stall"] == py_meta["stall"] is True
        assert js_meta["steps_used"] == py_meta["steps_used"] == fuel_count
        assert js_meta["termination_reason"] == "fuel_exhausted"
        assert py_meta["termination_reason"] == "fuel_exhausted"
        assert js_meta["max_steps"] == py_meta["max_steps"] == max_steps
        assert js_meta["fuel_supplied"] is True
        assert py_meta["fuel_supplied"] is True
        assert js_meta["fuel_remaining"] is None
        assert py_meta["fuel_remaining"] is None
        assert js_meta["fuel_exhausted"] is True
        assert py_meta["fuel_exhausted"] is True

    @pytest.mark.parametrize(
        "kernel_fuel",
        [
            {"head": None, "tail": 0},
            {"head": None, "tail": None, "extra": None},
            [],
        ],
    )
    def test_kernel_fuel_rejects_non_linked_mu_data(self, kernel_fuel):
        """JSON API fuel is fail-closed as Mu head/tail linked-list data."""
        resp = self._run_json_api_response({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
            "maxSteps": 100,
            "kernelFuel": kernel_fuel,
        })
        assert not resp.get("success")
        assert resp.get("error_code") == "api.bad_request"
        assert "kernelFuel" in resp.get("error", "")

    def test_field_set_parity_with_python(self):
        """JS and Python KernelRunResult must have identical required field sets."""
        # JS projection_applied via live seeded kernel
        js_meta = self._run_json_api({
            "action": "step_kernel_meta",
            "projections": [{"pattern": {"x": 1}, "body": {"x": 2}}],
            "input": {"x": 1},
        })
        js_fields = set(js_meta.keys())

        # Python projection_applied
        py_meta = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}], {"x": 1}, return_meta=True
        )
        py_fields = set(py_meta.keys())

        # Required fields must be present in both
        assert REQUIRED_FIELDS <= js_fields, f"JS missing: {REQUIRED_FIELDS - js_fields}"
        assert REQUIRED_FIELDS <= py_fields, f"Python missing: {REQUIRED_FIELDS - py_fields}"
        # Required fields must match exactly (no extra required fields on either side)
        js_required = js_fields & REQUIRED_FIELDS
        py_required = py_fields & REQUIRED_FIELDS
        assert js_required == py_required, (
            f"Required field mismatch: JS={js_required}, Python={py_required}"
        )
