"""
L4 Gate: Python error_code parity for engine fail-closed outcomes.

Proves the L4_STRUCTURAL semantic shift: Python engine error paths now raise
RcxEngineError(RuntimeError) with machine-readable .error_code attribute,
matching JS RcxError. Backward compatible: existing except RuntimeError and
pytest.raises(RuntimeError, match=...) patterns remain valid.

Error codes locked (source lock — must exist as string literals in both substrates):
    engine.exhausted             — engine loop exhausted iterations
    engine.stalled_non_terminal  — engine stalled in intermediate state
    engine.boot1_depth_exceeded  — Boot1 re-entry depth limit hit
    input.shape_mismatch         — post-routing shape check (internal fail-closed)

Note: Pre-routing hemisphere key-set validation raises ValueError (user-input
validation), NOT RcxEngineError. Only post-routing fail-closed paths use typed
error codes.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_python_error_code_parity_gate.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import (
    RcxEngineError,
    run_engine_pipeline,
    run_engine_with_routing,
)
from rcx_pi.selfhost.kernel import reset_step_budget

pytestmark = [pytest.mark.slow]

# Locked error codes (must exist in both substrates)
LOCKED_ERROR_CODES = frozenset({
    "engine.exhausted",
    "engine.stalled_non_terminal",
    "engine.boot1_depth_exceeded",
    "input.shape_mismatch",
})


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
    pytest.fail(
        f"No JSON_API_RESPONSE in JS output.\n"
        f"returncode: {result.returncode}\n"
        f"stdout: {result.stdout[:500]}\n"
        f"stderr: {result.stderr[:500]}"
    )


# =============================================================================
# Exception class contract
# =============================================================================

class TestRcxEngineErrorContract:
    """RcxEngineError has correct class hierarchy and attributes."""

    def test_subclasses_runtime_error(self):
        """RcxEngineError is a subclass of RuntimeError."""
        assert issubclass(RcxEngineError, RuntimeError)

    def test_has_error_code_attribute(self):
        """RcxEngineError instances carry .error_code."""
        err = RcxEngineError("engine.exhausted", "test message")
        assert err.error_code == "engine.exhausted"
        assert str(err) == "test message"

    def test_caught_by_except_runtime_error(self):
        """RcxEngineError is caught by except RuntimeError."""
        with pytest.raises(RuntimeError):
            raise RcxEngineError("engine.exhausted", "test")


# =============================================================================
# Python runtime error-code presence
# =============================================================================

class TestPythonErrorCodePresence:
    """Python engine paths raise RcxEngineError with correct error_code."""

    def test_engine_exhausted_has_error_code(self):
        """engine.exhausted path raises RcxEngineError with matching code."""
        reset_step_budget()
        with pytest.raises(RcxEngineError) as exc_info:
            run_engine_pipeline(
                [], "test_input",
                max_steps=10, max_engine_iterations=1,
                max_algorithm_iterations=50,
            )
        assert exc_info.value.error_code == "engine.exhausted"

    def test_engine_exhausted_message_preserved(self):
        """engine.exhausted message still contains 'exhausted' substring."""
        reset_step_budget()
        with pytest.raises(RuntimeError, match="exhausted"):
            run_engine_pipeline(
                [], "test_input",
                max_steps=10, max_engine_iterations=1,
                max_algorithm_iterations=50,
            )

    def test_hemisphere_pre_validation_raises_valueerror(self):
        """Pre-routing hemisphere key validation raises ValueError, not RcxEngineError.

        This is user-input validation, not an engine fail-closed path.
        Post-routing shape checks use RcxEngineError (internal fail-closed).
        """
        reset_step_budget()
        bad_hemispheres = {"wrong": "shape"}
        with pytest.raises(ValueError, match="shape mismatch"):
            run_engine_with_routing(
                [], "test_input",
                hemispheres=bad_hemispheres,
                max_steps=10, max_engine_iterations=20,
                max_algorithm_iterations=50,
            )


# =============================================================================
# Backward compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Existing RuntimeError catch patterns remain valid."""

    def test_legacy_exhausted_catch(self):
        """pytest.raises(RuntimeError, match='exhausted') still catches."""
        reset_step_budget()
        with pytest.raises(RuntimeError, match="exhausted"):
            run_engine_pipeline(
                [], "test_input",
                max_steps=10, max_engine_iterations=1,
                max_algorithm_iterations=50,
            )

    def test_legacy_shape_catch_via_valueerror(self):
        """pytest.raises(ValueError, match='shape mismatch') still catches pre-validation."""
        reset_step_budget()
        bad_hemispheres = {"wrong": "shape"}
        with pytest.raises(ValueError, match="shape mismatch"):
            run_engine_with_routing(
                [], "test_input",
                hemispheres=bad_hemispheres,
                max_steps=10, max_engine_iterations=20,
                max_algorithm_iterations=50,
            )


# =============================================================================
# Cross-substrate parity
# =============================================================================

class TestCrossSubstrateErrorCodeParity:
    """Python .error_code matches JS error_code for same failure scenarios."""

    def test_engine_exhausted_parity(self):
        """Both substrates report 'engine.exhausted' for same failure."""
        reset_step_budget()
        with pytest.raises(RcxEngineError) as exc_info:
            run_engine_pipeline(
                [], "test_input",
                max_steps=10, max_engine_iterations=1,
                max_algorithm_iterations=50,
            )
        py_code = exc_info.value.error_code

        js_resp = _js_request(
            "run_engine_pipeline_meta",
            input="test_input",
            projections=[],
            maxSteps=10, maxEngineIterations=1, maxAlgorithmIterations=50,
        )
        assert not js_resp["success"]
        js_code = js_resp["error_code"]

        assert py_code == js_code == "engine.exhausted"

    def test_js_shape_mismatch_has_error_code(self):
        """JS reports 'input.shape_mismatch' for bad hemispheres key-set."""
        bad_hemispheres = {"wrong": "shape"}
        js_resp = _js_request(
            "run_engine_with_routing",
            input="test_input",
            projections=[],
            hemispheres=bad_hemispheres,
            maxSteps=10, maxEngineIterations=20, maxAlgorithmIterations=50,
        )
        assert not js_resp["success"]
        assert js_resp["error_code"] == "input.shape_mismatch"


# =============================================================================
# Source lock: error codes in both substrates
# =============================================================================

class TestErrorCodeSourceLock:
    """All locked error codes must appear as string literals in both substrates."""

    def test_python_source_contains_all_codes(self):
        """Python step_mu.py contains all locked error code strings."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        source = py_path.read_text()
        for code in LOCKED_ERROR_CODES:
            assert f'"{code}"' in source, (
                f"Python source missing error code string: {code!r}"
            )

    def test_js_source_contains_all_codes(self):
        """JS source contains all locked error code strings."""
        js_dir = REPO_ROOT / "mu" / "host" / "js"
        source = "\n".join(f.read_text() for f in sorted(js_dir.rglob("*.js")))
        for code in LOCKED_ERROR_CODES:
            assert f"'{code}'" in source, (
                f"JS source missing error code string: {code!r}"
            )

    def test_locked_code_count(self):
        """Locked error code set has exactly 4 members."""
        assert len(LOCKED_ERROR_CODES) == 4, (
            f"Expected 4 locked codes, got {len(LOCKED_ERROR_CODES)}: {LOCKED_ERROR_CODES}"
        )
