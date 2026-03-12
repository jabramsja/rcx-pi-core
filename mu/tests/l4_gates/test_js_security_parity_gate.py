"""
L4 Gate: JS Security Parity — lambda-calculus guard + projection validation.

Proves:
1. JS security.js contains assertNotLambdaCalculus (source proof)
2. JS applyProjection calls assertNotLambdaCalculus (source proof)
3. JS applyProjection validates projection structure (source proof)
4. JS run() uses single-pass matching (N6 double-match fix, source proof)
5. Python/JS behavioral parity: lambda-calc projections rejected by both (behavioral)

Usage:
    PYTHONHASHSEED=0 pytest mu/tests/l4_gates/test_js_security_parity_gate.py -v
"""

from __future__ import annotations

import ast
import json
import subprocess

import pytest

from tests.repo_root import REPO_ROOT


# ---------------------------------------------------------------------------
# Source proof helpers
# ---------------------------------------------------------------------------

def _read_source(module_path: str) -> str:
    """Read source file from mu/ path."""
    return (REPO_ROOT / module_path).read_text()


# ---------------------------------------------------------------------------
# Gate Tests: Lambda-Calculus Guard in JS (B1 fix)
# ---------------------------------------------------------------------------

class TestJSLambdaCalculusGuard:
    """Gate: JS security.js has assertNotLambdaCalculus parity with Python."""

    def test_security_js_has_assert_not_lambda_calculus(self):
        """Source proof: assertNotLambdaCalculus function exists in security.js."""
        src = _read_source("mu/host/js/core/security.js")
        assert "function assertNotLambdaCalculus(" in src, (
            "security.js must contain assertNotLambdaCalculus function"
        )

    def test_security_js_exports_assert_not_lambda_calculus(self):
        """Source proof: assertNotLambdaCalculus is exported from security.js."""
        src = _read_source("mu/host/js/core/security.js")
        assert "assertNotLambdaCalculus" in src.split("module.exports")[1], (
            "security.js must export assertNotLambdaCalculus"
        )

    def test_bootstrap_core_imports_guard(self):
        """Source proof: bootstrap_core.js imports assertNotLambdaCalculus."""
        src = _read_source("mu/host/js/core/bootstrap_core.js")
        assert "assertNotLambdaCalculus" in src, (
            "bootstrap_core.js must import assertNotLambdaCalculus"
        )

    def test_apply_projection_calls_guard(self):
        """Source proof: applyProjection() calls assertNotLambdaCalculus."""
        src = _read_source("mu/host/js/core/bootstrap_core.js")
        # Find the applyProjection function and verify it calls the guard
        in_func = False
        found_guard = False
        for line in src.splitlines():
            if "function applyProjection(" in line:
                in_func = True
            elif in_func and line.strip().startswith("function "):
                break
            elif in_func and "assertNotLambdaCalculus(" in line:
                found_guard = True
                break
        assert found_guard, (
            "applyProjection() must call assertNotLambdaCalculus() "
            "(parity with Python apply_projection)"
        )


# ---------------------------------------------------------------------------
# Gate Tests: Projection Structure Validation (wave-F item 4)
# ---------------------------------------------------------------------------

class TestJSProjectionValidation:
    """Gate: JS applyProjection validates projection structure."""

    def test_apply_projection_checks_pattern_key(self):
        """Source proof: applyProjection checks 'pattern' in projection."""
        src = _read_source("mu/host/js/core/bootstrap_core.js")
        in_func = False
        found_check = False
        for line in src.splitlines():
            if "function applyProjection(" in line:
                in_func = True
            elif in_func and line.strip().startswith("function "):
                break
            elif in_func and "'pattern'" in line and "'body'" in line:
                found_check = True
                break
        assert found_check, (
            "applyProjection() must validate presence of 'pattern' and 'body' keys"
        )

    def test_apply_projection_validates_input(self):
        """Source proof: applyProjection validates input with isValidMu."""
        src = _read_source("mu/host/js/core/bootstrap_core.js")
        in_func = False
        found_validation = False
        for line in src.splitlines():
            if "function applyProjection(" in line:
                in_func = True
            elif in_func and line.strip().startswith("function "):
                break
            elif in_func and "isValidMu(input)" in line:
                found_validation = True
                break
        assert found_validation, (
            "applyProjection() must validate input with isValidMu "
            "(parity: Python calls assert_mu on input)"
        )


# ---------------------------------------------------------------------------
# Gate Tests: run() Single-Pass Fix (N6 double-match)
# ---------------------------------------------------------------------------

class TestRunSinglePass:
    """Gate: JS run() uses single-pass matching (no double-match)."""

    def test_run_uses_apply_projection_trusted(self):
        """Source proof: run() loop uses _applyProjectionTrusted, not step()."""
        src = _read_source("mu/host/js/core/bootstrap_core.js")
        in_run = False
        in_loop = False
        uses_trusted = False
        calls_step = False
        for line in src.splitlines():
            if "function run(" in line:
                in_run = True
            elif in_run and line.strip().startswith("function "):
                break
            elif in_run and "for (let i" in line:
                in_loop = True
            elif in_loop and "_applyProjectionTrusted(" in line:
                uses_trusted = True
            elif in_loop and line.strip().startswith("const next = step("):
                calls_step = True

        assert uses_trusted, (
            "run() must use _applyProjectionTrusted in its loop "
            "(single-pass matching, N6 fix)"
        )
        assert not calls_step, (
            "run() must NOT call step() inside its loop "
            "(that causes double-match, N6 regression)"
        )

    def test_run_no_separate_match_scan(self):
        """Source proof: run() does not have a separate match-only scan loop."""
        src = _read_source("mu/host/js/core/bootstrap_core.js")
        in_run = False
        run_body = []
        brace_depth = 0
        for line in src.splitlines():
            if "function run(" in line:
                in_run = True
                brace_depth = 0
            if in_run:
                brace_depth += line.count("{") - line.count("}")
                run_body.append(line)
                if brace_depth <= 0 and len(run_body) > 1:
                    break
        run_src = "\n".join(run_body)
        assert "match(proj.pattern, current)" not in run_src, (
            "run() must not contain a separate match-only scan "
            "(that's the N6 double-match pattern)"
        )

    def test_run_validates_projections_up_front(self):
        """Source proof: run() calls assertNotLambdaCalculus on projections."""
        src = _read_source("mu/host/js/core/bootstrap_core.js")
        in_run = False
        found_guard = False
        for line in src.splitlines():
            if "function run(" in line:
                in_run = True
            elif in_run and line.strip().startswith("function "):
                break
            elif in_run and "assertNotLambdaCalculus" in line:
                found_guard = True
                break
        assert found_guard, (
            "run() must validate projections with assertNotLambdaCalculus "
            "before entering the step loop (boundary guard parity)"
        )


# ---------------------------------------------------------------------------
# Gate Tests: Behavioral Parity — Python & JS both reject lambda-calc
# ---------------------------------------------------------------------------

class TestLambdaCalcBehavioralParity:
    """Gate: Both Python and JS reject lambda-calculus projections."""

    def test_python_rejects_lambda_calc_pattern(self):
        """Python apply_projection rejects higher-order patterns."""
        from rcx_pi.selfhost.eval_seed import apply_projection
        lambda_proj = {
            "pattern": {"pattern": "literal", "body": "literal"},
            "body": {"var": "x"},
        }
        with pytest.raises(ValueError, match="lambda calculus"):
            apply_projection(lambda_proj, "test_input")

    def test_js_rejects_lambda_calc_pattern(self):
        """JS applyProjection rejects higher-order patterns (same input)."""
        result = subprocess.run(
            ["node", "-e", """
const { applyProjection } = require('./mu/host/js/core/bootstrap_core');
try {
  applyProjection({pattern: {pattern: 'literal', body: 'literal'}, body: {var: 'x'}}, 'test');
  console.log(JSON.stringify({error: null}));
} catch(e) {
  console.log(JSON.stringify({error: e.message}));
}
"""],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Node process failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["error"] is not None, (
            "JS applyProjection must reject lambda-calculus patterns"
        )
        assert "lambda calculus" in output["error"], (
            f"JS error message should mention lambda calculus, got: {output['error']}"
        )

    def test_js_rejects_malformed_projection(self):
        """JS applyProjection rejects projection without pattern/body keys."""
        result = subprocess.run(
            ["node", "-e", """
const { applyProjection } = require('./mu/host/js/core/bootstrap_core');
try {
  applyProjection({foo: 'bar'}, 'test');
  console.log(JSON.stringify({error: null}));
} catch(e) {
  console.log(JSON.stringify({error: e.message}));
}
"""],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Node process failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["error"] is not None, (
            "JS applyProjection must reject projections without pattern/body keys"
        )

    def test_js_accepts_normal_projection(self):
        """JS applyProjection accepts well-formed projections (control case)."""
        result = subprocess.run(
            ["node", "-e", """
const { applyProjection, NO_MATCH } = require('./mu/host/js/core/bootstrap_core');
try {
  const r = applyProjection({pattern: {var: 'x'}, body: {var: 'x'}}, 42);
  console.log(JSON.stringify({result: r, error: null}));
} catch(e) {
  console.log(JSON.stringify({result: null, error: e.message}));
}
"""],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Node process failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["error"] is None, (
            f"JS should accept normal projection, got error: {output['error']}"
        )
        assert output["result"] == 42, (
            f"Identity projection should return input, got: {output['result']}"
        )

    def test_js_rejects_non_mu_projection(self):
        """JS applyProjection rejects non-Mu projection (e.g. containing function)."""
        result = subprocess.run(
            ["node", "-e", """
const { applyProjection } = require('./mu/host/js/core/bootstrap_core');
try {
  // Non-Mu projection: pattern contains a function (not valid Mu)
  applyProjection({pattern: function(){}, body: 'x'}, 'test');
  console.log(JSON.stringify({error: null}));
} catch(e) {
  console.log(JSON.stringify({error: e.message}));
}
"""],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Node process failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["error"] is not None, (
            "JS applyProjection must reject non-Mu projections (function values)"
        )

    def test_js_run_rejects_lambda_calc_projections(self):
        """JS run() rejects lambda-calculus projections (not just applyProjection)."""
        result = subprocess.run(
            ["node", "-e", """
const { run } = require('./mu/host/js/core/bootstrap_core');
try {
  const lambdaProj = {pattern: {pattern: 'literal', body: 'literal'}, body: {var: 'x'}};
  run([lambdaProj], 'test', 10);
  console.log(JSON.stringify({error: null}));
} catch(e) {
  console.log(JSON.stringify({error: e.message}));
}
"""],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Node process failed: {result.stderr}"
        output = json.loads(result.stdout.strip())
        assert output["error"] is not None, (
            "JS run() must reject lambda-calculus projections"
        )
        assert "lambda calculus" in output["error"], (
            f"run() error should mention lambda calculus, got: {output['error']}"
        )
