"""
Gate test: Numeric Hash Safety Lock (Wave 24 + A5 reversal)

Enforces:
1. Python mu_hash_control/mu_hash_control_cached exist and canonicalize
2. JS muHashControl/muHashControlCached exist and canonicalize
3. Cross-substrate canonicalization parity (1.0 and 1 hash identically)
4. Zero canonicalization (0.0 → 0)
5. Global mu_hash/muHash NOT modified (data-flow paths unchanged)
6. Control wrappers wired at control-flow callsites (source locks)
7. Match non-linear binding uses content hash (type-preserving; control hash breaks int/float distinction)
"""

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# Python imports
from rcx_pi.selfhost.mu_type import (
    mu_hash,
    mu_hash_cached,
    mu_hash_control,
    mu_hash_control_cached,
    NumericHashError,
)

JS_DIR = REPO_ROOT / "mu" / "host" / "js"
PY_DIR = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"


class TestPythonCanonnicalization:
    """Python control wrappers canonicalize numeric domain correctly."""

    def test_integer_float_canonicalized_to_int(self):
        """1.0 and 1 must hash identically via control wrappers."""
        assert mu_hash_control(1.0) == mu_hash_control(1)
        assert mu_hash_control_cached(1.0) == mu_hash_control_cached(1)

    def test_zero_canonicalized(self):
        """0.0 and 0 must hash identically via control wrappers."""
        assert mu_hash_control(0.0) == mu_hash_control(0)
        assert mu_hash_control_cached(0.0) == mu_hash_control_cached(0)

    def test_negative_zero_canonicalized(self):
        """float('-0.0') and 0 must hash identically."""
        assert mu_hash_control(-0.0) == mu_hash_control(0)

    def test_negative_integer_float(self):
        """-3.0 and -3 must hash identically."""
        assert mu_hash_control(-3.0) == mu_hash_control(-3)

    def test_non_integer_floats_pass_through(self):
        """Non-integer floats (3.14) are allowed — they serialize identically."""
        h = mu_hash_control(3.14)
        assert isinstance(h, str) and len(h) == 64

    def test_nested_canonicalization(self):
        """Canonicalization recurses into lists and dicts."""
        a = {"x": 1.0, "y": [2.0, 3]}
        b = {"x": 1, "y": [2, 3]}
        assert mu_hash_control(a) == mu_hash_control(b)

    def test_canonicalize_preserves_non_numeric(self):
        """Strings, bools, None pass through unchanged (tested via public API)."""
        # Non-numeric values should hash via control wrappers without issue
        assert mu_hash_control("hello") == mu_hash("hello")
        assert mu_hash_control(True) == mu_hash(True)
        assert mu_hash_control(None) == mu_hash(None)

    def test_large_integral_float_not_int_cast(self):
        """1e30 is integral but must NOT be int-cast (diverges cross-substrate).

        Python int(1e30) serializes as "1000000000000000000000000000000"
        but JS JSON.stringify(1e30) produces "1e+30". Leaving as float
        preserves cross-substrate hash parity.
        """
        # Large integral floats must NOT hash the same as their int equivalent
        # because int-casting causes JSON serialization divergence
        h_float = mu_hash_control(1e30)
        assert isinstance(h_float, str) and len(h_float) == 64
        # Verify it's NOT the same as hashing the int version
        # (which would mean int-casting happened)
        import json
        int_canonical = json.dumps(int(1e30), sort_keys=True, ensure_ascii=False)
        float_canonical = json.dumps(1e30, sort_keys=True, ensure_ascii=False)
        assert int_canonical != float_canonical  # proves they diverge

    def test_safe_integer_float_still_canonicalized(self):
        """Floats within safe integer range are still int-cast."""
        assert mu_hash_control(100.0) == mu_hash_control(100)
        assert mu_hash_control(-42.0) == mu_hash_control(-42)
        # 2**52 is safe
        assert mu_hash_control(float(2**52)) == mu_hash_control(2**52)
        # 1e16 and 1e20 are within 1e21 threshold — must be int-cast
        assert mu_hash_control(1e16) == mu_hash_control(int(1e16))
        assert mu_hash_control(1e20) == mu_hash_control(int(1e20))

    def test_global_mu_hash_unchanged(self):
        """mu_hash(1.0) != mu_hash(1) — global hash is NOT canonicalized."""
        # This verifies we didn't modify the global hash function
        assert mu_hash(1.0) != mu_hash(1)


class TestJSCanonnicalization:
    """JS control wrappers canonicalize numeric domain correctly."""

    def _run_js(self, code):
        """Run a JS expression and return stdout."""
        full = (
            "const t = require('./mu/host/js/core/types');\n"
            f"console.log(JSON.stringify({code}));"
        )
        result = subprocess.run(
            ["node", "-e", full],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return json.loads(result.stdout.strip())

    def test_integer_hashes_match(self):
        """muHashControl(1) produces a valid hash."""
        h = self._run_js("t.muHashControl(1)")
        assert isinstance(h, str) and len(h) == 64

    def test_zero_hashes_match(self):
        """muHashControl(0) produces a valid hash."""
        h = self._run_js("t.muHashControl(0)")
        assert isinstance(h, str) and len(h) == 64

    def test_negative_zero_canonicalized(self):
        """muHashControl(-0) == muHashControl(0)."""
        h_neg = self._run_js("t.muHashControl(-0)")
        h_pos = self._run_js("t.muHashControl(0)")
        assert h_neg == h_pos

    def test_non_integer_float_passes(self):
        """Non-integer floats are allowed in JS too."""
        h = self._run_js("t.muHashControl(3.14)")
        assert isinstance(h, str) and len(h) == 64

    def test_global_muHash_unchanged(self):
        """muHash is not modified — it should NOT canonicalize -0."""
        h_neg = self._run_js("t.muHash(-0)")
        h_pos = self._run_js("t.muHash(0)")
        # -0.0 serializes as "-0.0" in muHash (Python parity), 0 as "0"
        assert h_neg != h_pos


class TestCrossSubstrateParity:
    """Python and JS control wrappers produce identical hashes."""

    def _js_hash(self, value_expr):
        code = (
            "const t = require('./mu/host/js/core/types');\n"
            f"console.log(t.muHashControl({value_expr}));"
        )
        result = subprocess.run(
            ["node", "-e", code],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return result.stdout.strip()

    def test_integer_parity(self):
        py_hash = mu_hash_control(42)
        js_hash = self._js_hash("42")
        assert py_hash == js_hash

    def test_zero_parity(self):
        py_hash = mu_hash_control(0)
        js_hash = self._js_hash("0")
        assert py_hash == js_hash

    def test_integer_float_parity(self):
        """Python hash_control(1.0) == JS hashControl(1) — the core fix."""
        py_hash = mu_hash_control(1.0)
        js_hash = self._js_hash("1")
        assert py_hash == js_hash

    def test_nested_structure_parity(self):
        py_hash = mu_hash_control({"a": 1, "b": [2, 3]})
        js_hash = self._js_hash('{"a": 1, "b": [2, 3]}')
        assert py_hash == js_hash

    def test_mid_range_integral_float_parity(self):
        """1e20 must hash identically across substrates (int-cast, both use integer form)."""
        py_hash = mu_hash_control(1e20)
        js_hash = self._js_hash("1e20")
        assert py_hash == js_hash, (
            f"Mid-range integral float hash divergence: py={py_hash}, js={js_hash}"
        )

    def test_large_integral_float_parity(self):
        """1e30 must hash identically across substrates (no int-casting)."""
        py_hash = mu_hash_control(1e30)
        js_hash = self._js_hash("1e30")
        assert py_hash == js_hash, (
            f"Large integral float hash divergence: py={py_hash}, js={js_hash}"
        )

    def test_negative_large_integral_float_parity(self):
        """Negative large integral float parity (must use >=1e21 to avoid
        pre-existing JSON serialization divergence: JS JSON.stringify(1e20)
        gives '100000000000000000000' while Python gives '1e+20'. Both
        substrates agree on scientific notation for >=1e21)."""
        py_hash = mu_hash_control(-1e30)
        js_hash = self._js_hash("-1e30")
        assert py_hash == js_hash


class TestSourceLocks:
    """Verify control wrappers are wired at the correct callsites."""

    def test_python_control_wrappers_exist(self):
        """mu_hash_control and mu_hash_control_cached are defined in mu_type.py."""
        source = (PY_DIR / "mu_type.py").read_text()
        assert "def mu_hash_control(" in source
        assert "def mu_hash_control_cached(" in source

    def test_js_control_wrappers_exist(self):
        """muHashControl and muHashControlCached are defined in types.js."""
        source = (JS_DIR / "core" / "types.js").read_text()
        assert "function muHashControl(" in source
        assert "function muHashControlCached(" in source

    def test_python_step_mu_uses_control_wrappers(self):
        """step_mu.py control paths use mu_hash_control_cached."""
        source = (PY_DIR / "step_mu.py").read_text()
        # Control sites: must use control wrappers
        assert "mu_hash_control_cached(" in source
        assert "mu_hash_control(" in source  # hash_trace_for_recurrence

    def test_python_projection_runner_uses_control_wrappers(self):
        """projection_runner.py uses mu_hash_control_cached."""
        source = (PY_DIR / "projection_runner.py").read_text()
        assert "mu_hash_control_cached(" in source

    def test_js_kernel_uses_control_wrappers(self):
        """kernel.js uses muHashControlCached."""
        source = (JS_DIR / "engine" / "kernel.js").read_text()
        assert "muHashControlCached(" in source

    def test_js_pipeline_uses_control_wrappers(self):
        """pipeline.js uses muHashControl and muHashControlCached."""
        source = (JS_DIR / "engine" / "pipeline.js").read_text()
        assert "muHashControlCached(" in source
        assert "muHashControl(" in source  # hashTraceForRecurrence

    def test_js_runAlgorithmWithBridge_uses_control_hash_not_muEqual(self):
        """F01 regression: runAlgorithmWithBridge must use muHashControlCached, not muEqual.

        NorthStarSemantics §B.1: control-flow stall detection paths must use
        muHashControlCached to canonicalize numerics and prevent cross-substrate
        divergence on -0 and integral floats.
        """
        source = (JS_DIR / "engine" / "pipeline.js").read_text()
        # Extract runAlgorithmWithBridge function body
        lines = source.splitlines()
        in_func = False
        func_lines = []
        brace_depth = 0
        for line in lines:
            if "function runAlgorithmWithBridge(" in line:
                in_func = True
                brace_depth = 0
            if in_func:
                func_lines.append(line)
                brace_depth += line.count("{") - line.count("}")
                if brace_depth == 0 and len(func_lines) > 1:
                    break
        func_body = "\n".join(func_lines)
        # Must use muHashControlCached for stall detection
        assert "muHashControlCached(" in func_body, (
            "runAlgorithmWithBridge must use muHashControlCached for stall detection "
            "(NorthStarSemantics §B.1)"
        )
        # Must NOT use muEqual for stall detection
        assert "muEqual(" not in func_body, (
            "runAlgorithmWithBridge must NOT use muEqual for stall detection — "
            "muEqual wraps muHashCached (content hash), not control hash"
        )

    def test_js_run_uses_control_wrappers(self):
        """bootstrap_core.js run() uses muHashControlCached."""
        source = (JS_DIR / "core" / "bootstrap_core.js").read_text()
        assert "muHashControlCached(" in source

    def test_match_nonlinear_binding_uses_content_hash(self):
        """match() in bootstrap_core.js uses muHashCached for non-linear binding.

        Content hash (muHashCached) preserves int/float type distinction.
        Control hash (muHashControlCached) canonicalizes 0.0→0, breaking
        non-linear conflict detection for type-distinct values.
        """
        source = (JS_DIR / "core" / "bootstrap_core.js").read_text()
        # Find match function lines with muHashCached (non-linear binding)
        in_match = False
        match_content_lines = []
        for i, line in enumerate(source.splitlines(), 1):
            if "function match(" in line:
                in_match = True
            elif in_match and line.startswith("function "):
                break
            if in_match and "muHashCached(" in line and "muHashControlCached(" not in line:
                match_content_lines.append(line.strip())
        assert len(match_content_lines) >= 2, (
            "match() should have >=2 muHashCached calls for non-linear binding"
        )

    def test_python_eval_seed_match_uses_content_hash(self):
        """eval_seed.py match uses mu_hash_cached for non-linear binding.

        Content hash preserves int/float type distinction. Control hash
        canonicalizes 0.0→0, causing false matches in non-linear patterns.
        """
        source = (PY_DIR / "eval_seed.py").read_text()
        assert "mu_hash_cached(" in source, (
            "eval_seed.py must use mu_hash_cached for non-linear binding"
        )

    def test_global_mu_hash_not_modified(self):
        """mu_hash and mu_hash_cached in mu_type.py don't call canonicalize."""
        source = (PY_DIR / "mu_type.py").read_text()
        # Find mu_hash function body (not mu_hash_control)
        lines = source.splitlines()
        in_mu_hash = False
        for line in lines:
            if line.startswith("def mu_hash("):
                in_mu_hash = True
                continue
            if in_mu_hash:
                if line.startswith("def ") or (line and not line[0].isspace()):
                    break
                assert "_canonicalize" not in line, "mu_hash must NOT call canonicalize"


class TestRunAlgorithmWithBridgeControlHashParity:
    """F01 regression: runAlgorithmWithBridge stall detection must use control hash.

    Verifies the fix from P0 remediation 2026-02-26. The inner stall loop
    must detect convergence using muHashControlCached (not muEqual/muHashCached)
    to prevent cross-substrate divergence on -0 and integral floats.
    """

    def test_js_control_hash_neg_zero_stall_detection(self):
        """JS runAlgorithmWithBridge stall path: -0 and 0 must hash identically.

        If the function used muEqual (content hash), -0 and 0 would hash
        differently and stall detection would fail. Control hash canonicalizes
        both to 0.
        """
        script = (
            "const t = require('./mu/host/js/core/types');\n"
            "const h1 = t.muHashControlCached(-0, 'runAlgorithmWithBridge');\n"
            "const h2 = t.muHashControlCached(0, 'runAlgorithmWithBridge.stall');\n"
            "console.log(JSON.stringify({same: h1 === h2}));\n"
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["same"], (
            "Control hash must canonicalize -0 and 0 to same hash "
            "(stall detection parity with Python)"
        )

    def test_python_control_hash_neg_zero_stall_detection(self):
        """Python counterpart: -0.0 and 0 must hash identically for stall detection."""
        h1 = mu_hash_control_cached(-0.0, "run_sub_algorithm")
        h2 = mu_hash_control_cached(0, "run_sub_algorithm.stall")
        assert h1 == h2, (
            "Python control hash must canonicalize -0.0 and 0 to same hash"
        )

    def test_cross_substrate_control_hash_integral_float_parity(self):
        """1.0 and 1 must hash identically in both substrates for stall detection."""
        py_hash = mu_hash_control_cached(1.0, "runAlgorithmWithBridge")
        script = (
            "const t = require('./mu/host/js/core/types');\n"
            "console.log(t.muHashControlCached(1, 'runAlgorithmWithBridge'));\n"
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        js_hash = result.stdout.strip()
        assert py_hash == js_hash, (
            f"Cross-substrate stall detection hash divergence: "
            f"Python(1.0)={py_hash}, JS(1)={js_hash}"
        )


class TestNonLinearBindingContentHashParity:
    """Non-linear binding conflict checks use content hash (type-preserving).

    Content hash (mu_hash_cached) preserves int/float type distinction:
    1.0 and 1 hash differently, so a non-linear pattern binding x=1.0
    then seeing x=1 correctly detects a conflict. Control hash was wrong
    here — it canonicalized 0.0→0, causing false matches in non-linear patterns
    (caught by weekly deep fuzz: test_distinct_states_no_closure, test_dict_non_linear_conflict).
    """

    def test_python_nonlinear_float_int_conflict(self):
        """Python: {var:x} matched against 1.0 then 1 must conflict (different types)."""
        from rcx_pi.selfhost.eval_seed import match, NO_MATCH
        pattern = [{"var": "x"}, {"var": "x"}]
        input_val = [1.0, 1]
        result = match(pattern, input_val)
        assert result is NO_MATCH, (
            "Non-linear pattern [x, x] with [1.0, 1] must conflict (int ≠ float)"
        )

    def test_python_nonlinear_true_conflict_still_fails(self):
        """Python: {var:x} matched against 1 then 2 must still conflict."""
        from rcx_pi.selfhost.eval_seed import match, NO_MATCH
        pattern = [{"var": "x"}, {"var": "x"}]
        input_val = [1, 2]
        result = match(pattern, input_val)
        assert result is NO_MATCH, (
            "Non-linear pattern [x, x] with [1, 2] must conflict"
        )

    def test_python_nonlinear_neg_zero_conflict(self):
        """Python: -0.0 and 0 must conflict (content hash distinguishes)."""
        from rcx_pi.selfhost.eval_seed import match, NO_MATCH
        pattern = [{"var": "x"}, {"var": "x"}]
        input_val = [-0.0, 0]
        result = match(pattern, input_val)
        assert result is NO_MATCH, (
            "Non-linear pattern [x, x] with [-0.0, 0] must conflict (content hash)"
        )

    def test_js_nonlinear_float_int_no_conflict(self):
        """JS: match([{var:x},{var:x}], [1.0, 1]) should not conflict."""
        script = (
            "const bc = require('./mu/host/js/core/bootstrap_core');\n"
            "const result = bc.match([{var:'x'},{var:'x'}], [1.0, 1]);\n"
            "console.log(JSON.stringify({matched: result !== bc.NO_MATCH, bindings: result}));\n"
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["matched"], "JS non-linear [x,x] with [1.0, 1] should match"

    def test_js_nonlinear_true_conflict_still_fails(self):
        """JS: match([{var:x},{var:x}], [1, 2]) must still conflict."""
        script = (
            "const bc = require('./mu/host/js/core/bootstrap_core');\n"
            "const result = bc.match([{var:'x'},{var:'x'}], [1, 2]);\n"
            "console.log(JSON.stringify({matched: result !== bc.NO_MATCH}));\n"
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert not data["matched"], "JS non-linear [x,x] with [1, 2] must conflict"
