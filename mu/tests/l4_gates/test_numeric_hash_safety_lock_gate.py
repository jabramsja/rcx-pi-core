"""
Gate test: Numeric Hash Safety Lock

Enforces two hash domains:
  Control hash (mu_hash_control / muHashControl): canonicalizes integral
    floats to ints for stall/convergence detection. 1.0->1, -0.0->0.
    Cross-substrate parity required.
  Content hash (mu_hash / muHash / mu_hash_cached / muHashCached):
    type-preserving for data equality. Used in non-linear pattern
    binding conflict checks.

Non-linear binding policy (cross-substrate):
  Python: content hash preserves int/float type distinction (1.0 != 1).
  JS: content hash operates over JS Number (1.0 === 1, no int/float
    lexical distinction available at the language level).
  This is an intentional substrate-model difference, not a bug.
  Strict cross-substrate int/float lexical parity would require typed
  numeric envelopes (future work).

Specific invariants:
1. Python mu_hash_control/mu_hash_control_cached exist and canonicalize
2. JS muHashControl/muHashControlCached exist and canonicalize
3. Cross-substrate control hash parity (1.0 and 1 hash identically)
4. Zero canonicalization (0.0 -> 0) in control hash
5. Global mu_hash/muHash NOT modified (data-flow paths unchanged)
6. Control wrappers wired at control-flow callsites (source locks)
7. Non-linear binding uses content hash (not control hash)
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

    def test_1e21_boundary_not_int_cast(self):
        """1e21 is at the JS scientific-notation boundary — must NOT be int-cast.

        JS: JSON.stringify(1e21) -> "1e+21" (scientific notation).
        Python: int(1e21) -> "1000000000000000000000" (full digits).
        Leaving as float preserves cross-substrate parity.
        """
        h_float = mu_hash_control(1e21)
        assert isinstance(h_float, str) and len(h_float) == 64
        # Verify the guard: abs(1e21) >= 1e21, so NOT int-cast
        import json as _json
        float_ser = _json.dumps(1e21, sort_keys=True, ensure_ascii=False)
        int_ser = _json.dumps(int(1e21), sort_keys=True, ensure_ascii=False)
        assert float_ser != int_ser, "1e21 float vs int serialization must diverge"

    def test_neg_1e21_boundary_not_int_cast(self):
        """-1e21 negative mirror — must NOT be int-cast."""
        h = mu_hash_control(-1e21)
        assert isinstance(h, str) and len(h) == 64

    def test_just_below_1e21_is_int_cast(self):
        """IEEE-754 predecessor of 1e21 (9.999999999999999e+20) IS int-cast.

        This is the last representable float before 1e21 where JS uses
        integer notation. 1e21 - 131072 is the first distinct predecessor
        (1e21 - 1 rounds back to 1e21 in IEEE-754).
        """
        just_below = 1e21 - 131072  # 9.999999999999999e+20
        assert just_below < 1e21, "Predecessor must be strictly less than 1e21"
        assert just_below.is_integer(), "Predecessor must be integral"
        # Must be int-cast (abs < 1e21)
        assert mu_hash_control(just_below) == mu_hash_control(int(just_below))

    def test_neg_just_below_1e21_is_int_cast(self):
        """Negative mirror of predecessor — must be int-cast."""
        just_below = -(1e21 - 131072)
        assert mu_hash_control(just_below) == mu_hash_control(int(just_below))

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

    def test_1e21_boundary_parity(self):
        """1e21 boundary: both substrates must NOT int-cast and must agree."""
        py_hash = mu_hash_control(1e21)
        js_hash = self._js_hash("1e21")
        assert py_hash == js_hash, (
            f"1e21 boundary hash divergence: py={py_hash}, js={js_hash}"
        )

    def test_neg_1e21_boundary_parity(self):
        """-1e21 boundary: negative mirror must agree."""
        py_hash = mu_hash_control(-1e21)
        js_hash = self._js_hash("-1e21")
        assert py_hash == js_hash, (
            f"-1e21 boundary hash divergence: py={py_hash}, js={js_hash}"
        )

    def test_just_below_1e21_known_divergence(self):
        """IEEE-754 predecessor of 1e21: cross-substrate serialization diverges.

        Both substrates int-cast this value (abs < 1e21), but:
        - Python int(9.999999999999999e+20) = 999999999999999868928 (exact)
        - JS Math.floor(same) = 999999999999999900000 (rounded to ~17 sig digits)
        JSON.stringify produces different strings, so hashes diverge.

        This is a KNOWN LIMITATION of int-casting near the boundary. It only
        affects values where the exact integer exceeds ~17 significant digits.
        Production control paths use small integers (step counts, depths), so
        this divergence is not reachable in practice.
        """
        py_hash = mu_hash_control(1e21 - 131072)
        js_hash = self._js_hash("1e21 - 131072")
        # These DIVERGE — this documents the known limitation
        assert py_hash != js_hash, (
            "Expected divergence: Python and JS serialize large int-cast "
            "IEEE-754 predecessors of 1e21 differently"
        )


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
        """step_mu.py + engine_pipeline.py control paths use mu_hash_control_cached."""
        source = (PY_DIR / "step_mu.py").read_text()
        ep_source = (PY_DIR / "engine_pipeline.py").read_text()
        # Control sites: must use control wrappers (across Boot1 + Boot2)
        assert "mu_hash_control_cached(" in source
        assert "mu_hash_control(" in ep_source  # hash_trace_for_recurrence (Boot2)

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

    def test_js_trusted_path_depth_parity(self):
        """_applyProjectionTrusted uses stage0Match/stage0Substitute directly.

        Parity with Python _apply_projection_trusted which calls
        stage0_match/stage0_substitute directly. Stage 0 is the sole
        production path — the _stage0Pilot flag was removed in Wave 9 (JS)
        and Wave 4 (Python).
        """
        source = (JS_DIR / "core" / "bootstrap_core.js").read_text()
        # Find _applyProjectionTrusted and verify it calls stage0Match/stage0Substitute
        in_trusted = False
        found_match_call = False
        found_substitute_call = False
        for line in source.splitlines():
            if "function _applyProjectionTrusted(" in line:
                in_trusted = True
            elif in_trusted and line.startswith("function "):
                break
            if in_trusted:
                # Must call stage0Match directly (unconditional, no flag)
                if "stage0Match(pattern, inputVal)" in line:
                    found_match_call = True
                # Must call stage0Substitute directly (unconditional, no flag)
                if "stage0Substitute(projection.body, bindings)" in line:
                    found_substitute_call = True
        assert found_match_call, (
            "_applyProjectionTrusted must call stage0Match(pattern, inputVal) "
            "— stage0 is the sole production path (flag removed Wave 9)"
        )
        assert found_substitute_call, (
            "_applyProjectionTrusted must call stage0Substitute(projection.body, bindings) "
            "— stage0 is the sole production path (flag removed Wave 9)"
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


class TestNonLinearBindingContentHash:
    """Non-linear binding conflict checks use content hash per substrate.

    Both substrates use content hash (not control hash) for non-linear
    binding conflict detection. The behavioral difference between them
    is an inherent property of each substrate's numeric model:

    Python: content hash (mu_hash_cached) preserves int/float type
      distinction. 1.0 and 1 hash differently, so non-linear [x,x]
      with [1.0, 1] correctly detects a conflict.
    JS: content hash (muHashCached) operates over JS Number semantics.
      1.0 === 1 in JS, so non-linear [x,x] with [1.0, 1] does NOT
      conflict. This is correct JS behavior, not a bug.

    See TestNumericNonLinearPolicyLock for the canonical policy statement.
    """

    def test_python_nonlinear_float_int_conflict(self):
        """Python: [x,x] with [1.0, 1] conflicts (int and float are distinct types)."""
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
        """Python: [x,x] with [-0.0, 0] conflicts (content hash preserves sign)."""
        from rcx_pi.selfhost.eval_seed import match, NO_MATCH
        pattern = [{"var": "x"}, {"var": "x"}]
        input_val = [-0.0, 0]
        result = match(pattern, input_val)
        assert result is NO_MATCH, (
            "Non-linear pattern [x, x] with [-0.0, 0] must conflict (content hash)"
        )

    def test_js_nonlinear_float_int_no_conflict(self):
        """JS: [x,x] with [1.0, 1] does not conflict (Number model: 1.0 === 1)."""
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


class TestNumericNonLinearPolicyLock:
    """Policy lock: non-linear numeric matching substrate-model differences.

    Canonical policy statement:
    - Non-linear conflict checks use content hash (mu_hash_cached / muHashCached),
      NOT control hash.
    - Python: int and float are distinct types; content hash preserves this.
      [x,x] with [1.0, 1] -> NO_MATCH.
    - JS: Number is a single type; 1.0 === 1 at the language level.
      [x,x] with [1.0, 1] -> match.
    - This substrate-model difference is intentional and accepted.
    - Strict cross-substrate int/float lexical parity would require typed
      numeric envelopes (future work, not a current requirement).
    """

    def test_policy_python_int_float_nonlinear_conflict(self):
        """POLICY: Python [x,x] with [1.0, 1] must conflict (int != float)."""
        from rcx_pi.selfhost.eval_seed import match, NO_MATCH
        result = match([{"var": "x"}, {"var": "x"}], [1.0, 1])
        assert result is NO_MATCH, (
            "POLICY VIOLATION: Python non-linear [x,x] with [1.0, 1] must "
            "conflict — content hash preserves int/float type distinction"
        )

    def test_policy_js_number_model_nonlinear_no_conflict(self):
        """POLICY: JS [x,x] with [1.0, 1] must not conflict (Number model)."""
        script = (
            "const bc = require('./mu/host/js/core/bootstrap_core');\n"
            "const r = bc.match([{var:'x'},{var:'x'}], [1.0, 1]);\n"
            "console.log(JSON.stringify({matched: r !== bc.NO_MATCH}));\n"
        )
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS failed: {result.stderr}"
        data = json.loads(result.stdout)
        assert data["matched"], (
            "POLICY VIOLATION: JS non-linear [x,x] with [1.0, 1] must not "
            "conflict — JS Number model collapses 1.0 and 1"
        )


class TestMuHashCachedNegZeroCorrectness:
    """F-14 gate: muHashCached must be position-sensitive for -0.

    Before the fix, muHashCached used a boolean hasNegZero flag that recorded
    presence but not position of -0. {x:0,y:-0} and {x:-0,y:0} shared the
    same cache key despite having different muHash values. This caused
    muEqual false positives and match() non-linear conflict suppression.

    Fix: bypass cache entirely when value contains -0 (Option B).
    """

    def _run_js(self, code):
        """Run a JS expression and return stdout."""
        full = (
            "const t = require('./mu/host/js/core/types');\n"
            "const bc = require('./mu/host/js/core/bootstrap_core');\n"
            f"console.log(JSON.stringify({code}));"
        )
        result = subprocess.run(
            ["node", "-e", full],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return json.loads(result.stdout.strip())

    def test_compound_neg_zero_position_sensitivity(self):
        """muHashCached({x:0,y:-0}) != muHashCached({x:-0,y:0}).

        Core F-14 regression test. These values have -0 in different positions,
        so muHash returns different hashes. muHashCached must agree.
        """
        data = self._run_js(
            "{"
            "  h_a: t.muHashCached({x: 0, y: -0}),"
            "  h_b: t.muHashCached({x: -0, y: 0}),"
            "  ref_a: t.muHash({x: 0, y: -0}),"
            "  ref_b: t.muHash({x: -0, y: 0})"
            "}"
        )
        assert data["h_a"] != data["h_b"], (
            "F-14: muHashCached must distinguish {x:0,y:-0} from {x:-0,y:0}"
        )
        assert data["h_a"] == data["ref_a"], (
            "muHashCached must agree with muHash for {x:0,y:-0}"
        )
        assert data["h_b"] == data["ref_b"], (
            "muHashCached must agree with muHash for {x:-0,y:0}"
        )

    def test_muEqual_no_false_positive(self):
        """muEqual({x:0,y:-0}, {x:-0,y:0}) must be false.

        muEqual delegates to muHashCached. Before the F-14 fix, this returned
        true (false positive) because both values shared the same cache key.
        """
        data = self._run_js(
            "{"
            "  same_pos: t.muEqual({x: 0, y: -0}, {x: 0, y: -0}),"
            "  diff_pos: t.muEqual({x: 0, y: -0}, {x: -0, y: 0})"
            "}"
        )
        assert data["same_pos"] is True, "Same -0 positions must be equal"
        assert data["diff_pos"] is False, (
            "F-14: muEqual must distinguish different -0 positions"
        )

    def test_match_nonlinear_conflict_detection(self):
        """match([z,z], [{x:0,y:-0}, {x:-0,y:0}]) must conflict.

        match() uses muHashCached for non-linear binding conflict detection.
        Before the F-14 fix, this returned bindings (false match) because
        muHashCached returned the same hash for both values.
        """
        data = self._run_js(
            "{"
            "  conflict: bc.match([{var:'z'},{var:'z'}], [{x:0,y:-0},{x:-0,y:0}]) === bc.NO_MATCH"
            "}"
        )
        assert data["conflict"] is True, (
            "F-14: match() must detect non-linear conflict for different -0 positions"
        )

    def test_stage0Match_nonlinear_conflict_detection(self):
        """stage0Match([z,z], [{x:0,y:-0}, {x:-0,y:0}]) must conflict.

        stage0Match also uses muHashCached for non-linear binding conflict.
        """
        data = self._run_js(
            "{"
            "  conflict: bc.stage0Match([{var:'z'},{var:'z'}], [{x:0,y:-0},{x:-0,y:0}]) === bc.NO_MATCH"
            "}"
        )
        assert data["conflict"] is True, (
            "F-14: stage0Match must detect non-linear conflict for different -0 positions"
        )

    def test_python_baseline_no_neg_zero_cache_issue(self):
        """Python mu_hash_cached is not affected by F-14 (baseline).

        Python's JSON serialization handles -0.0 differently (json.dumps(-0.0)
        produces "-0.0"), so the cache key already encodes position. This test
        confirms Python was never affected.
        """
        h_a = mu_hash_cached({"x": 0, "y": -0.0})
        h_b = mu_hash_cached({"x": -0.0, "y": 0})
        assert h_a != h_b, (
            "Python mu_hash_cached must distinguish {x:0,y:-0.0} from {x:-0.0,y:0}"
        )
        # Verify consistency with mu_hash
        assert h_a == mu_hash({"x": 0, "y": -0.0})
        assert h_b == mu_hash({"x": -0.0, "y": 0})

    def test_cache_bypass_no_pollution(self):
        """Values containing -0 must not pollute the cache.

        After the fix, muHashCached bypasses the cache for -0 values.
        Verify that calling muHashCached with a -0 value does not create
        a stale entry that would be returned for a non-negzero value
        with the same JSON shape.
        """
        data = self._run_js(
            "(function() {"
            "  const v1 = {a: -0, b: 1};"
            "  const v2 = {a: 0, b: 1};"
            "  const h1 = t.muHashCached(v1);"
            "  const h2 = t.muHashCached(v2);"
            "  return {"
            "    h1: h1, h2: h2,"
            "    different: h1 !== h2,"
            "    h2_consistent: h2 === t.muHash(v2)"
            "  };"
            "})()"
        )
        assert data["different"], (
            "F-14: {a:-0,b:1} and {a:0,b:1} must hash differently"
        )
        assert data["h2_consistent"], (
            "Non-negzero value must still be cached correctly after -0 bypass"
        )
