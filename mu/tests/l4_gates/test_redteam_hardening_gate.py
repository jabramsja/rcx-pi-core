"""L4 gate tests for red-team hardening.

Evidence for:
- substitute() depth parity with JS
- Centralized _validate_reentry_payload / validateReentryPayload helpers
- RT-001: denormalize() typed-path typeof guard (A18-P0)
- RT-002: match()/substitute() isValidMu entry validation (A18-P0)
"""
from __future__ import annotations

import json
import subprocess

import pytest

from tests.repo_root import REPO_ROOT


def _read_all_js_source() -> str:
    """Read all JS module files from mu/host/js/ recursively."""
    js_dir = REPO_ROOT / "mu" / "host" / "js"
    parts = []
    for f in sorted(js_dir.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


class TestSubstituteDepthGuard:
    """Verify Python substitute() has MAX_MU_DEPTH guard matching JS."""

    def test_substitute_rejects_beyond_max_depth(self):
        """substitute() must raise TypeError when _depth exceeds MAX_MU_DEPTH."""
        from rcx_pi.selfhost.eval_seed import substitute
        from rcx_pi.selfhost.mu_type import MAX_MU_DEPTH

        # Call substitute with _depth already at the limit — triggers guard
        # before assert_mu (which is only called at _depth==0)
        body = {"nested": "leaf"}
        with pytest.raises(TypeError, match="Max depth exceeded"):
            substitute(body, {}, _depth=MAX_MU_DEPTH + 1)

    def test_substitute_accepts_within_depth(self):
        """substitute() must work for values within MAX_MU_DEPTH."""
        from rcx_pi.selfhost.eval_seed import substitute

        # Depth 10 is well within bounds
        body = {"var": "x"}
        for _ in range(10):
            body = {"nested": body}

        result = substitute(body, {"x": 42})
        # Unwind to verify substitution happened
        for _ in range(10):
            assert "nested" in result
            result = result["nested"]
        assert result == 42

    def test_substitute_depth_guard_source_lock(self):
        """Python substitute must reference MAX_MU_DEPTH (not hardcoded)."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/eval_seed.py").read_text()
        assert "MAX_MU_DEPTH" in src, "substitute must use MAX_MU_DEPTH constant"
        assert "_depth" in src, "substitute must track recursion depth"


class TestReentryPayloadHelperExists:
    """Verify both substrates define a centralized re-entry payload validator.

    Wave A3 centralized inline validation into _validate_reentry_payload (Python)
    and validateReentryPayload (JS). These helpers provide shape validation AND
    reserved-field checks in one call, preventing raw TypeError/KeyError on
    malformed payloads.
    """

    def test_python_helper_defined(self):
        """Python must define _validate_reentry_payload."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert "def _validate_reentry_payload(" in src

    def test_js_helper_defined(self):
        """JS must define validateReentryPayload."""
        src = _read_all_js_source()
        assert "function validateReentryPayload(" in src

    def test_python_helper_validates_input_reserved_fields(self):
        """Python helper must call validate_no_kernel_reserved_fields on payload input."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert 'validate_no_kernel_reserved_fields(payload["input"]' in src

    def test_python_helper_validates_frozen_reserved_fields(self):
        """Python helper must call validate_no_kernel_reserved_fields on payload frozen."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert "validate_no_kernel_reserved_fields(frozen," in src

    def test_js_helper_validates_input_reserved_fields(self):
        """JS helper must call validateNoKernelReservedFields on payload.input."""
        src = _read_all_js_source()
        assert "validateNoKernelReservedFields(payload.input," in src

    def test_js_helper_validates_frozen_reserved_fields(self):
        """JS helper must call validateNoKernelReservedFields on payload.frozen,"""
        src = _read_all_js_source()
        assert "validateNoKernelReservedFields(payload.frozen," in src

    def test_python_helper_validates_mu_type_input(self):
        """Python helper must check is_mu on payload input."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert 'is_mu(payload["input"])' in src

    def test_python_helper_validates_mu_type_frozen(self):
        """Python helper must check is_mu on frozen."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert "is_mu(frozen)" in src

    def test_js_helper_validates_mu_type_input(self):
        """JS helper must check isValidMu on payload.input."""
        src = _read_all_js_source()
        assert "isValidMu(payload.input)" in src

    def test_js_helper_validates_mu_type_frozen(self):
        """JS helper must check isValidMu on payload.frozen."""
        src = _read_all_js_source()
        assert "isValidMu(payload.frozen)" in src


class TestBoot1ReentryValidation:
    """Verify Boot1 re-entry paths call centralized payload validator."""

    def test_python_boot1_run_engine_calls_helper(self):
        """Python Boot1 _run_engine path must call _validate_reentry_payload."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert '_validate_reentry_payload(payload, "Boot1 _run_engine")' in src

    def test_python_boot1_tail_call_calls_helper(self):
        """Python Boot1 _tail_call path must call _validate_reentry_payload."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert '_validate_reentry_payload(payload, "Boot1 _tail_call")' in src

    def test_js_boot1_run_engine_calls_helper(self):
        """JS Boot1 _run_engine path must call validateReentryPayload."""
        src = _read_all_js_source()
        assert "validateReentryPayload(payload, 'Boot1 _run_engine')" in src

    def test_js_boot1_tail_call_calls_helper(self):
        """JS Boot1 _tail_call path must call validateReentryPayload."""
        src = _read_all_js_source()
        assert "validateReentryPayload(payload, 'Boot1 _tail_call')" in src

    def test_cross_substrate_boot1_validation_parity(self):
        """Both substrates must have 2 Boot1 helper call sites (_run_engine + _tail_call)."""
        py_src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        js_src = _read_all_js_source()
        py_boot1 = py_src.count('_validate_reentry_payload(payload, "Boot1')
        js_boot1 = js_src.count("validateReentryPayload(payload, 'Boot1")
        assert py_boot1 == 2, f"Python must have 2 Boot1 helper calls, got {py_boot1}"
        assert js_boot1 == 2, f"JS must have 2 Boot1 helper calls, got {js_boot1}"


class TestTrampolineTailCallValidation:
    """Verify trampoline _tail_call path calls centralized payload validator.

    The trampoline engine loop in run_engine_pipeline must validate payloads
    via the centralized helper, matching Boot1 path behavior.
    """

    def test_python_trampoline_calls_helper(self):
        """Python trampoline must call _validate_reentry_payload for tail_call."""
        src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        assert '_validate_reentry_payload(payload, "trampoline _tail_call")' in src

    def test_js_trampoline_calls_helper(self):
        """JS trampoline must call validateReentryPayload for tail_call."""
        src = _read_all_js_source()
        assert "validateReentryPayload(payload, 'trampoline _tail_call')" in src

    def test_all_reentry_paths_use_helper(self):
        """All 4 re-entry paths in both substrates must use the centralized helper."""
        py_src = (REPO_ROOT / "mu/host/python/rcx_pi/selfhost/engine_pipeline.py").read_text()
        js_src = _read_all_js_source()
        # Count "helperName(" occurrences — includes definition + call sites.
        # Python: 1 def + 4 calls = 5.  JS: 1 function def + 4 calls = 5.
        py_total = py_src.count("_validate_reentry_payload(")
        js_total = js_src.count("validateReentryPayload(")
        # Subtract 1 for the function definition line in each
        py_calls = py_total - 1  # def _validate_reentry_payload(
        js_calls = js_total - 1  # function validateReentryPayload(
        assert py_calls == 4, f"Python must have 4 helper call sites (Boot1 _run_engine, Boot1 _tail_call, trampoline _tail_call, trampoline _run_engine), got {py_calls}"
        assert js_calls == 4, f"JS must have 4 helper call sites (Boot1 _run_engine, Boot1 _tail_call, trampoline _tail_call, trampoline _run_engine), got {js_calls}"


# ---------------------------------------------------------------------------
# Helper — run JS via node -e (A18-P0 behavioral tests)
# ---------------------------------------------------------------------------

def _js_eval(script: str) -> str:
    """Run a JS script via node -e and return stdout."""
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT), timeout=10,
    )
    assert result.returncode == 0, f"JS error: {result.stderr}"
    return result.stdout.strip()


# =============================================================================
# RT-001: denormalize() typed-path typeof guard (A18-P0)
# =============================================================================

class TestDenormalizeTypedPathGuard:
    """Typed denormalize paths must not crash on non-object tail (RT-001)."""

    def test_list_typed_path_primitive_tail(self):
        """Typed list denormalize with primitive tail raises (fail-closed)."""
        script = """
const { denormalize } = require('./mu/host/js/core/normalize');
const { muCopy } = require('./mu/host/js/core/stage0_vm');
const malformed = muCopy({ _type: 'list', head: 42, tail: 'not_an_object' }, true, 'typed list guard fixture');
try {
    denormalize(malformed);
    console.log('ERROR: should have thrown');
    process.exit(1);
} catch (e) {
    console.log(e.message);
}
"""
        out = _js_eval(script)
        assert "Improper linked list tail" in out, f"Expected error, got: {out}"

    def test_dict_typed_path_primitive_tail(self):
        """Typed dict denormalize with primitive tail raises (fail-closed)."""
        script = """
const { denormalize } = require('./mu/host/js/core/normalize');
const { muCopy } = require('./mu/host/js/core/stage0_vm');
const malformed = muCopy({
    _type: 'dict',
    head: { head: 'key1', tail: { head: 'val1', tail: null } },
    tail: 99
}, true, 'typed dict guard fixture');
try {
    denormalize(malformed);
    console.log('ERROR: should have thrown');
    process.exit(1);
} catch (e) {
    console.log(e.message);
}
"""
        out = _js_eval(script)
        assert "Improper linked list tail" in out, f"Expected error, got: {out}"


# =============================================================================
# RT-002: match()/substitute() isValidMu entry validation (A18-P0)
# =============================================================================

class TestMatchSubstituteEntryValidation:
    """match() and substitute() must reject non-Mu inputs with typed error (RT-002)."""

    def test_match_rejects_undefined_pattern(self):
        """match() with undefined pattern throws input.invalid_type."""
        script = """
const bc = require('./mu/host/js/core/bootstrap_core');
try {
    bc.match(undefined, {a: 1});
    console.log(JSON.stringify({error_code: null}));
} catch (e) {
    console.log(JSON.stringify({error_code: e.error_code || null}));
}
"""
        parsed = json.loads(_js_eval(script))
        assert parsed["error_code"] == "input.invalid_type"

    def test_match_rejects_function_input(self):
        """match() with function input throws input.invalid_type."""
        script = """
const bc = require('./mu/host/js/core/bootstrap_core');
try {
    bc.match({a: 1}, function() {});
    console.log(JSON.stringify({error_code: null}));
} catch (e) {
    console.log(JSON.stringify({error_code: e.error_code || null}));
}
"""
        parsed = json.loads(_js_eval(script))
        assert parsed["error_code"] == "input.invalid_type"

    def test_substitute_rejects_undefined_body(self):
        """substitute() with undefined body throws input.invalid_type."""
        script = """
const bc = require('./mu/host/js/core/bootstrap_core');
try {
    bc.substitute(undefined, {x: 1});
    console.log(JSON.stringify({error_code: null}));
} catch (e) {
    console.log(JSON.stringify({error_code: e.error_code || null}));
}
"""
        parsed = json.loads(_js_eval(script))
        assert parsed["error_code"] == "input.invalid_type"

    def test_match_accepts_valid_mu(self):
        """match() with valid Mu inputs succeeds (no regression)."""
        script = """
const bc = require('./mu/host/js/core/bootstrap_core');
const { muCopy } = require('./mu/host/js/core/stage0_vm');
const result = bc.match(
  muCopy({a: 1}, true, 'match pattern fixture'),
  muCopy({a: 1}, true, 'match input fixture')
);
console.log(JSON.stringify(result));
"""
        parsed = json.loads(_js_eval(script))
        assert parsed == {}
