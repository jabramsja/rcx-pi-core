"""
L4 Gate Test: Terminal Classification Parity (Wave 17).

Verifies that terminal classification constants and functions are identical
across Python and JavaScript substrates. Fail-closed: any drift is a violation.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_terminal_classification_parity_gate.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import (
    TERMINAL_KINDS,
    _load_tc_key_sets,  # ANTICHEAT_OK: parity gate compares seed-derived key sets against JS source
    classify_terminal_kind,
)
from rcx_pi.selfhost.engine_pipeline import (
    ENGINE_EXIT_REASONS,
    _derive_engine_exit_reason,  # ANTICHEAT_OK: parity gate tests coercion parity (muBool vs bool)
)

JS_DIR = REPO_ROOT / "mu" / "host" / "js"
PY_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"


# ---------------------------------------------------------------------------
# Helpers — extract JS constants via regex
# ---------------------------------------------------------------------------

def _js_source() -> str:
    """Read all JS module files concatenated (monolith was split into modules)."""
    parts = []
    for f in sorted(JS_DIR.rglob("*.js")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)



# =============================================================================
# Constant parity: terminal key sets
# =============================================================================

class TestTerminalKeySetParity:
    """Terminal shape key sets must be identical across substrates (A7: both seed-derived)."""

    def _js_eval(self, script):
        """Run a JS script via node -e and return stdout."""
        import subprocess
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return result.stdout.strip()

    def _js_key_set(self, export_name):
        """Get a JS terminal key Set via node -e evaluation."""
        import json
        script = (
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            f"console.log(JSON.stringify([...tc.{export_name}]));\n"
        )
        return set(json.loads(self._js_eval(script)))

    def test_recurrence_terminal_keys_match(self):
        js_keys = self._js_key_set("RECURRENCE_TERMINAL_KEYS")
        tc_sets = _load_tc_key_sets()
        assert set(tc_sets["tc.recurrence"]) == js_keys

    def test_exhaustion_terminal_keys_match(self):
        js_keys = self._js_key_set("EXHAUSTION_TERMINAL_KEYS")
        tc_sets = _load_tc_key_sets()
        assert set(tc_sets["tc.exhaustion"]) == js_keys

    def test_engine_terminal_keys_match(self):
        js_keys = self._js_key_set("ENGINE_TERMINAL_KEYS")
        tc_sets = _load_tc_key_sets()
        assert set(tc_sets["tc.engine"]) == js_keys


# =============================================================================
# Constant parity: enums
# =============================================================================

class TestEnumParity:
    """Terminal classification enums must be identical across substrates."""

    def _js_eval(self, script):
        """Run a JS script via node -e and return stdout."""
        import subprocess
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return result.stdout.strip()

    def test_terminal_kinds_match(self):
        import json
        script = (
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "console.log(JSON.stringify([...tc.TERMINAL_KINDS]));\n"
        )
        js_kinds = set(json.loads(self._js_eval(script)))
        assert set(TERMINAL_KINDS) == js_kinds

    def test_engine_exit_reasons_match(self):
        import json
        script = (
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "console.log(JSON.stringify([...tc.ENGINE_EXIT_REASONS]));\n"
        )
        js_reasons = set(json.loads(self._js_eval(script)))
        assert set(ENGINE_EXIT_REASONS) == js_reasons

    def test_terminal_kinds_constant(self):
        assert TERMINAL_KINDS == {
            "kernel_done", "recurrence_terminal", "exhaustion_terminal",
            "engine_terminal", "non_terminal",
        }

    def test_engine_exit_reasons_constant(self):
        assert ENGINE_EXIT_REASONS == {"closure", "exhaustion", "stall", "completed"}


# =============================================================================
# Function parity: classify_terminal_kind source presence
# =============================================================================

class TestClassifyTerminalKindSourceParity:
    """classifyTerminalKind function must exist in JS with matching logic."""

    def test_js_has_classify_function(self):
        js = _js_source()
        assert "function classifyTerminalKind(value)" in js

    def test_js_returns_all_terminal_kinds(self):
        js = _js_source()
        for kind in TERMINAL_KINDS:
            assert f"'{kind}'" in js, f"JS source missing terminal kind: {kind!r}"

    def test_python_returns_all_terminal_kinds(self):
        source = PY_PATH.read_text()
        for kind in TERMINAL_KINDS:
            assert f'"{kind}"' in source, f"Python source missing terminal kind: {kind!r}"

    def test_js_classify_priority_matches_python(self):
        """JS function checks kernel_done before seed-based classification.

        Wave 25: classification now delegates to terminal_classify.v1.json seed.
        Priority is: kernel_done (host-side) checked first, then seed step() handles
        recurrence > exhaustion > engine via projection order.
        """
        js = _js_source()
        # Extract function body
        start = js.index("function classifyTerminalKind(value)")
        body = js[start:start + 600]
        # kernel_done must appear before step() call (host-side check first)
        kernel_pos = body.index("kernel_done")
        step_pos = body.index("step(")
        assert kernel_pos < step_pos, (
            "kernel_done must be checked before seed step() delegation"
        )


# =============================================================================
# Behavioral tests: classify_terminal_kind (Python)
# =============================================================================

class TestClassifyTerminalKindBehavior:
    """classify_terminal_kind must produce correct classifications."""

    def test_kernel_done(self):
        val = {"_mode": "done", "_result": {"x": 1}, "_stall": False}
        assert classify_terminal_kind(val) == "kernel_done"

    def test_kernel_done_with_stall(self):
        val = {"_mode": "done", "_result": None, "_stall": True}
        assert classify_terminal_kind(val) == "kernel_done"

    def test_recurrence_terminal(self):
        val = {"closure_detected": True, "final_result": {"x": 1}, "tau_step": 3}
        assert classify_terminal_kind(val) == "recurrence_terminal"

    def test_exhaustion_terminal(self):
        val = {"action": "freeze", "exhaustion_detected": True,
               "frozen": {"a": 1}, "operator_to_freeze": "op"}
        assert classify_terminal_kind(val) == "exhaustion_terminal"

    def test_engine_terminal(self):
        val = {
            "value": {"x": 1}, "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": None, "stall": False,
        }
        assert classify_terminal_kind(val) == "engine_terminal"

    def test_non_terminal_dict(self):
        assert classify_terminal_kind({"x": 1, "y": 2}) == "non_terminal"

    def test_non_terminal_string(self):
        assert classify_terminal_kind("hello") == "non_terminal"

    def test_non_terminal_int(self):
        assert classify_terminal_kind(42) == "non_terminal"

    def test_non_terminal_none(self):
        assert classify_terminal_kind(None) == "non_terminal"

    def test_non_terminal_list(self):
        assert classify_terminal_kind([1, 2, 3]) == "non_terminal"

    def test_non_terminal_empty_dict(self):
        assert classify_terminal_kind({}) == "non_terminal"

    def test_kernel_intermediate_not_terminal(self):
        """_mode present but not 'done' is non_terminal (not kernel_done)."""
        val = {"_mode": "match", "_match_ctx": {}, "_result": None, "_stall": False}
        assert classify_terminal_kind(val) == "non_terminal"

    def test_kernel_done_priority_over_key_match(self):
        """kernel_done check happens before key-set comparison."""
        # A dict with _mode=done that also happens to have extra keys
        val = {"_mode": "done", "_result": None, "_stall": False, "extra": True}
        assert classify_terminal_kind(val) == "kernel_done"

    def test_partial_recurrence_keys_not_terminal(self):
        """Subset of recurrence keys is non_terminal."""
        val = {"closure_detected": True, "final_result": {"x": 1}}
        assert classify_terminal_kind(val) == "non_terminal"

    def test_superset_engine_keys_not_terminal(self):
        """Engine keys + extra key is non_terminal."""
        val = {
            "value": 1, "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": None, "stall": False,
            "extra_key": True,
        }
        assert classify_terminal_kind(val) == "non_terminal"


# =============================================================================
# JS cache hardening (A8): defensive copy exports + muBool parity
# =============================================================================

class TestJSCacheHardening:
    """A8: JS exported Sets/Arrays are defensive copies — mutations don't corrupt internals."""

    def _js_eval(self, script):
        """Run a JS script via node -e and return stdout."""
        import subprocess
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return result.stdout.strip()

    def test_mutating_exported_set_does_not_affect_classification(self):
        """Mutating tc.RECURRENCE_TERMINAL_KEYS does not alter classifyTerminalKind."""
        script = """
const tc = require('./mu/host/js/core/terminal_classification');
const { muCopy } = require('./mu/host/js/core/stage0_vm');
const rec = tc.RECURRENCE_TERMINAL_KEYS;
rec.add('injected');
rec.clear();
const result = tc.classifyTerminalKind(
  muCopy({closure_detected: true, final_result: 42, tau_step: 1}, true, 'terminal cache fixture')
);
console.log(result);
"""
        assert self._js_eval(script) == "recurrence_terminal"

    def test_refetch_after_mutation_returns_intact_set(self):
        """Re-fetching key set after mutation returns original members."""
        script = """
const tc = require('./mu/host/js/core/terminal_classification');
const rec1 = tc.RECURRENCE_TERMINAL_KEYS;
rec1.clear();
const rec2 = tc.RECURRENCE_TERMINAL_KEYS;
console.log(JSON.stringify(rec2.size > 0 && rec1.size === 0));
"""
        assert self._js_eval(script) == "true"

    def test_hemisphere_key_order_is_defensive_copy(self):
        """Mutating HEMISPHERE_KEY_ORDER does not corrupt internal state."""
        script = """
const tc = require('./mu/host/js/core/terminal_classification');
const hko = tc.HEMISPHERE_KEY_ORDER;
hko.push('evil');
const hko2 = tc.HEMISPHERE_KEY_ORDER;
console.log(hko2.length);
"""
        assert self._js_eval(script) == "5"

    def test_engine_exit_reasons_is_defensive_copy(self):
        """Mutating ENGINE_EXIT_REASONS does not corrupt internal state."""
        script = """
const tc = require('./mu/host/js/core/terminal_classification');
tc.ENGINE_EXIT_REASONS.clear();
console.log(tc.ENGINE_EXIT_REASONS.size);
"""
        assert self._js_eval(script) == "4"

    def test_clear_tc_cache_rebuilds_correctly(self):
        """_clearTcCache clears and rebuilds without classification drift."""
        script = """
const tc = require('./mu/host/js/core/terminal_classification');
const { muCopy } = require('./mu/host/js/core/stage0_vm');
tc.classifyTerminalKind(muCopy({closure_detected: true, final_result: 42, tau_step: 1}, true, 'terminal cache fixture'));
tc._clearTcCache();  // # ANTICHEAT_OK: testing JS cache clear export
const r1 = tc.classifyTerminalKind(muCopy({closure_detected: true, final_result: 42, tau_step: 1}, true, 'terminal cache fixture'));
const r2 = tc.classifyTerminalKind(muCopy({
  value: 1, closure_detected: false, tau_step: 0,
  exhaustion_detected: false, operator_frozen: false,
  frozen_set: [], action: null, stall: false,
}, true, 'terminal engine fixture'));
console.log(JSON.stringify([r1, r2]));
"""
        assert self._js_eval(script) == '["recurrence_terminal","engine_terminal"]'


class TestExitReasonCoercionParity:
    """A8: deriveEngineExitReason uses muBool (Python bool() parity) not JS !!."""

    def _js_eval(self, script):
        """Run a JS script via node -e and return stdout."""
        import subprocess
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return result.stdout.strip()

    def _derive_exit_reason_js(self, engine_result_js):
        """Call JS deriveEngineExitReason and return result string."""
        script = f"""
const tc = require('./mu/host/js/core/terminal_classification');
const result = tc.deriveEngineExitReason({engine_result_js});
console.log(result);
"""
        return self._js_eval(script)

    def test_empty_list_closure_detected_is_completed(self):
        """closure_detected=[] should coerce to false (Python bool([])=False)."""
        # Python: bool([]) = False => cd=False, completed

        py_result = _derive_engine_exit_reason(
            {"closure_detected": [], "exhaustion_detected": False, "stall": False}
        )
        js_result = self._derive_exit_reason_js(
            "{closure_detected: [], exhaustion_detected: false, stall: false}"
        )
        assert py_result == "completed", f"Python got {py_result}"
        assert js_result == "completed", f"JS got {js_result}"
        assert py_result == js_result

    def test_empty_dict_closure_detected_is_completed(self):
        """closure_detected={} should coerce to false (Python bool({})=False)."""

        py_result = _derive_engine_exit_reason(
            {"closure_detected": {}, "exhaustion_detected": False, "stall": False}
        )
        js_result = self._derive_exit_reason_js(
            "{closure_detected: {}, exhaustion_detected: false, stall: false}"
        )
        assert py_result == "completed", f"Python got {py_result}"
        assert js_result == "completed", f"JS got {js_result}"
        assert py_result == js_result

    def test_nonempty_list_closure_detected_is_closure(self):
        """closure_detected=[1] should coerce to true."""

        py_result = _derive_engine_exit_reason(
            {"closure_detected": [1], "exhaustion_detected": False, "stall": False}
        )
        js_result = self._derive_exit_reason_js(
            "{closure_detected: [1], exhaustion_detected: false, stall: false}"
        )
        assert py_result == "closure", f"Python got {py_result}"
        assert js_result == "closure", f"JS got {js_result}"
        assert py_result == js_result

    def test_nonempty_dict_exhaustion_detected_is_exhaustion(self):
        """exhaustion_detected={a:1} should coerce to true."""

        py_result = _derive_engine_exit_reason(
            {"closure_detected": False, "exhaustion_detected": {"a": 1}, "stall": False}
        )
        js_result = self._derive_exit_reason_js(
            '{closure_detected: false, exhaustion_detected: {a: 1}, stall: false}'
        )
        assert py_result == "exhaustion", f"Python got {py_result}"
        assert js_result == "exhaustion", f"JS got {js_result}"
        assert py_result == js_result

    def test_boolean_coercion_unchanged_for_true_false(self):
        """Standard boolean values still work correctly after muBool change."""

        py_result = _derive_engine_exit_reason(
            {"closure_detected": True, "exhaustion_detected": False, "stall": False}
        )
        js_result = self._derive_exit_reason_js(
            "{closure_detected: true, exhaustion_detected: false, stall: false}"
        )
        assert py_result == "closure"
        assert js_result == "closure"

    def test_js_source_uses_muBool_not_double_bang(self):
        """JS deriveEngineExitReason must use _muBool, not !! for coercion."""
        source = (JS_DIR / "core" / "terminal_classification.js").read_text(encoding="utf-8")
        # Find the function body
        fn_match = re.search(
            r'function deriveEngineExitReason\(.*?\)\s*\{(.*?)\n\}',
            source, re.DOTALL
        )
        assert fn_match, "deriveEngineExitReason not found"
        body = fn_match.group(1)
        assert "_muBool(" in body, (
            "deriveEngineExitReason must use _muBool() for Python bool() parity"
        )
        assert "!!" not in body, (
            "deriveEngineExitReason must NOT use !! (diverges from Python bool())"
        )


# ── A9: Hemisphere authority source-lock ──────────────────────────────────

class TestHemisphereSourceLock:
    """Hemisphere key authority must be seed-derived in both substrates (A9)."""

    def _js_eval(self, script):
        """Run a JS script via node -e and return stdout."""
        import subprocess
        result = subprocess.run(
            ["node", "-e", script], capture_output=True, text=True,
            cwd=str(REPO_ROOT), timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return result.stdout.strip()

    def test_python_js_hemisphere_keys_parity(self):
        """Both substrates must derive identical hemisphere key sets from seed."""
        import json
        from rcx_pi.selfhost.step_mu import _get_hemisphere_keys  # ANTICHEAT_OK: A9 source-lock test
        py_keys = _get_hemisphere_keys()
        js_out = self._js_eval(
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "console.log(JSON.stringify([...tc.HEMISPHERE_KEYS]));\n"
        )
        js_keys = set(json.loads(js_out))
        assert py_keys == js_keys, (
            f"Hemisphere key parity violation!\n"
            f"  Python-only: {py_keys - js_keys}\n"
            f"  JS-only: {js_keys - py_keys}"
        )

    def test_default_hemispheres_keys_match_derived(self):
        """defaultHemispheres() keys must match seed-derived keys (both substrates)."""
        import json
        from rcx_pi.selfhost.step_mu import _get_hemisphere_keys  # ANTICHEAT_OK: A9 source-lock test (seed-derived keys)
        from rcx_pi.selfhost.engine_pipeline import _default_hemispheres  # ANTICHEAT_OK: A9 source-lock test
        py_keys = _get_hemisphere_keys()
        assert set(_default_hemispheres().keys()) == py_keys, "Python _default_hemispheres() key drift"
        js_out = self._js_eval(
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "console.log(JSON.stringify(Object.keys(tc.defaultHemispheres())));\n"
        )
        js_default_keys = set(json.loads(js_out))
        assert js_default_keys == py_keys, (
            f"JS defaultHemispheres() key drift!\n"
            f"  Expected: {sorted(py_keys)}\n"
            f"  Got: {sorted(js_default_keys)}"
        )

    def test_cache_clear_re_derives_hemisphere_keys(self):
        """After cache clear, hemisphere keys must re-derive from seed."""
        from rcx_pi.selfhost.step_mu import _clear_hemi_cache, _get_hemisphere_keys  # ANTICHEAT_OK: A9 source-lock test
        expected = _get_hemisphere_keys()
        _clear_hemi_cache()
        re_derived = _get_hemisphere_keys()
        assert re_derived == expected, "Hemisphere key re-derivation after cache clear failed"
        # JS: verify _clearTcCache also clears hemisphere caches
        js_out = self._js_eval(
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "tc._clearTcCache(); // # ANTICHEAT_OK: A9 tests cache clear behavior\n"
            "console.log(JSON.stringify([...tc.HEMISPHERE_KEYS]));\n"
        )
        import json
        js_keys = set(json.loads(js_out))
        assert js_keys == expected, "JS hemisphere key re-derivation after _clearTcCache failed"

    def test_python_hemisphere_key_order_matches_seed_projection_order(self):
        """Python _get_hemisphere_key_order() must match hemispheres.v1.json projection order."""
        import json
        from rcx_pi.selfhost.step_mu import _get_hemisphere_key_order  # ANTICHEAT_OK: A9 order-lock test
        seed_path = REPO_ROOT / "mu" / "programs" / "hemispheres.v1.json"
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        prefix = "hemisphere.add."
        seed_order = tuple(
            p["id"][len(prefix):] for p in seed["projections"] if p["id"].startswith(prefix)
        )
        assert _get_hemisphere_key_order() == seed_order, (
            f"Python hemisphere key order does not match seed projection order!\n"
            f"  Seed:   {seed_order}\n"
            f"  Python: {_get_hemisphere_key_order()}"
        )

    def test_js_hemisphere_key_order_matches_seed_projection_order(self):
        """JS HEMISPHERE_KEY_ORDER must match hemispheres.v1.json projection order."""
        import json
        seed_path = REPO_ROOT / "mu" / "programs" / "hemispheres.v1.json"
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        prefix = "hemisphere.add."
        seed_order = [
            p["id"][len(prefix):] for p in seed["projections"] if p["id"].startswith(prefix)
        ]
        js_out = self._js_eval(
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "console.log(JSON.stringify(tc.HEMISPHERE_KEY_ORDER));\n"
        )
        js_order = json.loads(js_out)
        assert js_order == seed_order, (
            f"JS hemisphere key order does not match seed projection order!\n"
            f"  Seed: {seed_order}\n"
            f"  JS:   {js_order}"
        )

    def test_default_hemispheres_order_matches_key_order_both_substrates(self):
        """defaultHemispheres() key iteration order must match derived key order (both substrates)."""
        import json
        from rcx_pi.selfhost.step_mu import _get_hemisphere_key_order  # ANTICHEAT_OK: A9 order-lock test (seed-derived order)
        from rcx_pi.selfhost.engine_pipeline import _default_hemispheres  # ANTICHEAT_OK: A9 order-lock test
        py_default_order = list(_default_hemispheres().keys())
        py_key_order = list(_get_hemisphere_key_order())
        assert py_default_order == py_key_order, (
            f"Python _default_hemispheres() order drift!\n"
            f"  Key order: {py_key_order}\n"
            f"  Default:   {py_default_order}"
        )
        js_out = self._js_eval(
            "const tc = require('./mu/host/js/core/terminal_classification');\n"
            "console.log(JSON.stringify({"
            "  default_order: Object.keys(tc.defaultHemispheres()),"
            "  key_order: tc.HEMISPHERE_KEY_ORDER"
            "}));\n"
        )
        js_data = json.loads(js_out)
        assert js_data["default_order"] == js_data["key_order"], (
            f"JS defaultHemispheres() order drift!\n"
            f"  Key order: {js_data['key_order']}\n"
            f"  Default:   {js_data['default_order']}"
        )

    def test_no_hardcoded_hemisphere_constant_assignments(self):
        """No module-level hardcoded _HEMISPHERE_KEY_ORDER/_HEMISPHERE_KEYS assignments in either substrate."""
        py_source = PY_PATH.read_text(encoding="utf-8")
        js_source = (JS_DIR / "core" / "terminal_classification.js").read_text(encoding="utf-8")
        # Narrow assignment-only patterns (avoid comments/docs)
        py_patterns = [
            r'^_HEMISPHERE_KEY_ORDER\s*=',
            r'^_HEMISPHERE_KEYS\s*=\s*frozenset',
        ]
        js_patterns = [
            r'^const _HEMISPHERE_KEY_ORDER\s*=',
            r'^const _HEMISPHERE_KEYS\s*=',
        ]
        for pat in py_patterns:
            matches = re.findall(pat, py_source, re.MULTILINE)
            assert not matches, (
                f"Hardcoded hemisphere constant found in step_mu.py: {pat}"
            )
        for pat in js_patterns:
            matches = re.findall(pat, js_source, re.MULTILINE)
            assert not matches, (
                f"Hardcoded hemisphere constant found in terminal_classification.js: {pat}"
            )

    def test_js_seed_registration_loads(self):
        """hemispheres.v1.json must be registered in seed_loader.js and loadable."""
        self._js_eval(
            "const { loadVerifiedSeed } = require('./mu/host/js/core/seed_loader');\n"
            "const seed = loadVerifiedSeed('hemispheres.v1.json', 'programs');\n"
            "if (!seed.projections || seed.projections.length !== 12) {\n"
            "  throw new Error('Expected 12 projections, got ' + (seed.projections ? seed.projections.length : 'none'));\n"
            "}\n"
            "console.log('OK');\n"
        )
