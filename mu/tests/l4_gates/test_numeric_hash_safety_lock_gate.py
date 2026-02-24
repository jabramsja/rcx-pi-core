"""
Gate test: Numeric Hash Safety Lock (Wave 24)

Enforces:
1. Python mu_hash_control/mu_hash_control_cached exist and canonicalize
2. JS muHashControl/muHashControlCached exist and canonicalize
3. Cross-substrate canonicalization parity (1.0 and 1 hash identically)
4. Zero canonicalization (0.0 → 0)
5. Global mu_hash/muHash NOT modified (data-flow paths unchanged)
6. Control wrappers wired at control-flow callsites (source locks)
7. Match non-linear binding NOT wired (explicit exclusion)
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

    def test_js_run_uses_control_wrappers(self):
        """bootstrap_core.js run() uses muHashControlCached."""
        source = (JS_DIR / "core" / "bootstrap_core.js").read_text()
        assert "muHashControlCached(" in source

    def test_match_nonlinear_binding_excluded(self):
        """match() in bootstrap_core.js still uses muHashCached, NOT control."""
        source = (JS_DIR / "core" / "bootstrap_core.js").read_text()
        # Find match function lines with muHashCached (non-linear binding)
        in_match = False
        match_hash_lines = []
        for i, line in enumerate(source.splitlines(), 1):
            if "function match(" in line:
                in_match = True
            elif in_match and line.startswith("function "):
                break
            if in_match and "muHashCached(" in line:
                match_hash_lines.append(line.strip())
        assert len(match_hash_lines) >= 2, "match() should have muHashCached for non-linear binding"
        for line in match_hash_lines:
            assert "muHashControlCached" not in line, (
                f"match() non-linear binding should NOT use control wrapper: {line}"
            )

    def test_python_eval_seed_match_excluded(self):
        """eval_seed.py match uses mu_hash_cached, NOT control."""
        source = (PY_DIR / "eval_seed.py").read_text()
        # eval_seed uses mu_hash_cached for non-linear binding in _match_inner
        assert "mu_hash_cached(" in source
        # Should NOT import mu_hash_control
        assert "mu_hash_control" not in source

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
