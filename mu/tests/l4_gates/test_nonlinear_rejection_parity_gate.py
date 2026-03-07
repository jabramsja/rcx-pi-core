"""L4 gate: JS non-linear domain projection rejection parity (W6).

Proves that JS direct-kernel entrypoints reject non-linear domain projections
in parity with Python's fail-closed guard.

Contract:
- Direct JS core-kernel entrypoints (stepKernel, runStructural) reject
  non-linear domain projections regardless of whether values agree or conflict.
- Bridge algorithm execution (runAlgorithmWithBridge) remains allowed because
  it bypasses these guard sites via _stepKernelCoreNonMeta.
- step_kernel_meta(kernelMode='bridge') is still treated as a direct external
  kernel API and rejects non-linear domain projections.
"""
from __future__ import annotations

import json
import subprocess

import pytest

from tests.repo_root import REPO_ROOT


NONLINEAR_PROJ = {
    "id": "nl.gate",
    "pattern": {"a": {"var": "x"}, "b": {"var": "x"}},
    "body": "ok",
}
AGREE_INPUT = {"a": "same", "b": "same"}
CONFLICT_INPUT = {"a": 1, "b": 2}


def _run_js_api(request_dict: dict) -> dict:
    result = subprocess.run(
        ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
    )
    for line in result.stdout.split("\n"):
        if line.startswith("JSON_API_RESPONSE:"):
            return json.loads(line[len("JSON_API_RESPONSE:"):])
    raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")


class TestNonlinearRejectionParityGate:
    """Gate: JS rejects non-linear projections on direct core paths."""

    def test_python_step_mu_rejects_nonlinear(self):
        """Python step_mu rejects non-linear projections (baseline)."""
        from rcx_pi.selfhost.step_mu import step_mu

        with pytest.raises(ValueError, match="non-linear pattern"):
            step_mu([NONLINEAR_PROJ], AGREE_INPUT)

    def test_js_run_vector_rejects_nonlinear_agree(self):
        """JS run_vector rejects non-linear projection (agree input)."""
        resp = _run_js_api({
            "action": "run_vector",
            "projection": NONLINEAR_PROJ,
            "input": AGREE_INPUT,
        })
        assert not resp["success"], "run_vector must reject by shape, not runtime"
        assert "non-linear pattern" in resp["error"]
        assert resp.get("error_code") == "input.nonlinear_pattern"

    def test_js_run_vector_rejects_nonlinear_conflict(self):
        """JS run_vector rejects non-linear projection (conflict input)."""
        resp = _run_js_api({
            "action": "run_vector",
            "projection": NONLINEAR_PROJ,
            "input": CONFLICT_INPUT,
        })
        assert not resp["success"]
        assert "non-linear pattern" in resp["error"]
        assert resp.get("error_code") == "input.nonlinear_pattern"

    def test_js_step_kernel_meta_rejects_nonlinear(self):
        """JS step_kernel_meta rejects non-linear domain projections."""
        resp = _run_js_api({
            "action": "step_kernel_meta",
            "input": AGREE_INPUT,
            "projections": [NONLINEAR_PROJ],
        })
        assert not resp["success"], "step_kernel_meta should reject non-linear"
        assert "non-linear pattern" in resp["error"]

    def test_js_run_structural_trace_rejects_nonlinear(self):
        """JS run_structural_trace rejects non-linear domain projections."""
        resp = _run_js_api({
            "action": "run_structural_trace",
            "projections": [NONLINEAR_PROJ],
            "input": AGREE_INPUT,
        })
        assert not resp["success"]
        assert "non-linear pattern" in resp["error"]

    def test_js_bridge_path_accepts_nonlinear(self):
        """JS run_recurrence (bridge path) accepts non-linear algorithm seeds."""
        resp = _run_js_api({
            "action": "run_recurrence",
            "input": [1, 2, 3, 1],
        })
        assert resp["success"], f"Bridge path must accept: {resp.get('error')}"


class TestNonlinearScannerAliasBypassGate:
    """Gate: non-linear scanner detects aliased (shared-ref) patterns.

    The old implementation used a seen set (Python id(), JS Set identity) to
    skip already-visited objects. This caused shared references to be traversed
    only once, hiding non-linear variable usage.

    Fix: remove seen set entirely; rely on iteration cap for cycle safety.
    """

    def test_python_alias_leaf_detected(self):
        """Python: same {var: x} object ref in two positions is non-linear."""
        from rcx_pi.selfhost.step_mu import _has_nonlinear_vars  # ANTICHEAT_OK: gate test for alias bypass fix

        v = {"var": "x"}
        pattern = {"a": v, "b": v}
        assert _has_nonlinear_vars(pattern)

    def test_python_alias_subtree_detected(self):
        """Python: shared subtree containing {var: x} is non-linear."""
        from rcx_pi.selfhost.step_mu import _has_nonlinear_vars  # ANTICHEAT_OK: gate test for alias bypass fix

        sub = {"inner": {"var": "x"}}
        pattern = {"a": sub, "b": sub}
        assert _has_nonlinear_vars(pattern)

    def test_js_alias_leaf_detected(self):
        """JS: same {var: x} object ref in two positions is non-linear."""
        result = subprocess.run(
            ["node", "-e",
             "const { hasNonlinearVars } = require('./mu/host/js/core/security');\n"
             "const v = {var: 'x'};\n"
             "const pattern = {a: v, b: v};\n"
             "console.log(hasNonlinearVars(pattern) ? 'NONLINEAR' : 'LINEAR');"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        assert result.returncode == 0, f"node failed: {result.stderr[:300]}"
        assert result.stdout.strip() == "NONLINEAR"

    def test_js_alias_subtree_detected(self):
        """JS: shared subtree containing {var: x} is non-linear."""
        result = subprocess.run(
            ["node", "-e",
             "const { hasNonlinearVars } = require('./mu/host/js/core/security');\n"
             "const sub = {inner: {var: 'x'}};\n"
             "const pattern = {a: sub, b: sub};\n"
             "console.log(hasNonlinearVars(pattern) ? 'NONLINEAR' : 'LINEAR');"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        assert result.returncode == 0, f"node failed: {result.stderr[:300]}"
        assert result.stdout.strip() == "NONLINEAR"
