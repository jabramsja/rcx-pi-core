"""
L4 Gate: Performance canary — step_kernel_mu termination reason observability.

Proves the L4_STRUCTURAL semantic shift: step_kernel_mu(return_meta=True) and
JS stepKernel(returnMeta=true) now expose termination_reason, steps_used, and
max_steps in their meta payloads. Four deterministic reasons:

    projection_applied  — kernel reached terminal {_mode: "done", _stall: false}
    kernel_stall        — kernel reached terminal {_mode: "done", _stall: true}
    hash_stall          — non-intermediate result hash equals previous hash
    max_steps_exhausted — for-loop completed without termination

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_performance_canary_gate.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import step_kernel_mu
from rcx_pi.selfhost.kernel import reset_step_budget


def _read_all_js_source() -> str:
    """Read all JS module files from mu/host/js/ recursively."""
    js_dir = REPO_ROOT / "mu" / "host" / "js"
    parts = []
    for f in sorted(js_dir.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REASON_ENUM = frozenset([
    "projection_applied",
    "kernel_stall",
    "hash_stall",
    "max_steps_exhausted",
])


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


def _assert_meta_shape(meta, *, expected_reason):
    """Assert meta dict has all required fields with correct types."""
    assert isinstance(meta, dict), f"meta must be dict, got {type(meta)}"
    assert "output" in meta, "meta missing 'output'"
    assert "stall" in meta, "meta missing 'stall'"
    assert "termination_reason" in meta, "meta missing 'termination_reason'"
    assert "steps_used" in meta, "meta missing 'steps_used'"
    assert "max_steps" in meta, "meta missing 'max_steps'"
    assert isinstance(meta["stall"], bool), f"stall must be bool, got {type(meta['stall'])}"
    assert isinstance(meta["steps_used"], int), f"steps_used must be int, got {type(meta['steps_used'])}"
    assert isinstance(meta["max_steps"], int), f"max_steps must be int, got {type(meta['max_steps'])}"
    assert meta["termination_reason"] in REASON_ENUM, (
        f"Unknown reason: {meta['termination_reason']!r}"
    )
    assert meta["termination_reason"] == expected_reason, (
        f"Expected reason={expected_reason!r}, got {meta['termination_reason']!r}"
    )
    assert meta["steps_used"] >= 0, "steps_used must be non-negative"
    assert meta["steps_used"] <= meta["max_steps"], "steps_used cannot exceed max_steps"


# A simple identity projection: pattern "a" -> body "a" (matches, returns same)
IDENTITY_PROJ = {"id": "test.identity", "pattern": "a", "body": "a"}

# A rewrite projection: "a" -> "b"
REWRITE_PROJ = {"id": "test.rewrite", "pattern": "a", "body": "b"}

# A projection that won't match anything simple
NO_MATCH_PROJ = {"id": "test.nomatch", "pattern": {"x": "never_match_this"}, "body": "z"}


# =============================================================================
# Python: termination_reason for each case
# =============================================================================

class TestPythonTerminationReason:
    """Python step_kernel_mu(return_meta=True) reports correct termination reasons."""

    def test_projection_applied(self):
        """Successful projection match yields 'projection_applied'."""
        reset_step_budget()
        meta = step_kernel_mu([REWRITE_PROJ], "a", return_meta=True)
        _assert_meta_shape(meta, expected_reason="projection_applied")
        assert meta["output"] == "b"
        assert meta["stall"] is False

    def test_kernel_stall(self):
        """No projection matches yields 'kernel_stall'."""
        reset_step_budget()
        meta = step_kernel_mu([NO_MATCH_PROJ], "a", return_meta=True)
        _assert_meta_shape(meta, expected_reason="kernel_stall")
        assert meta["stall"] is True

    def test_max_steps_exhausted(self):
        """max_steps=0 yields 'max_steps_exhausted' immediately."""
        reset_step_budget()
        meta = step_kernel_mu([REWRITE_PROJ], "a", return_meta=True, max_steps=0)
        _assert_meta_shape(meta, expected_reason="max_steps_exhausted")
        assert meta["stall"] is True
        assert meta["steps_used"] == 0
        assert meta["max_steps"] == 0

    def test_hash_stall_via_monkeypatch(self):
        """hash_stall is a defensive path (kernel projections always progress).

        Controlled monkeypatch: force _step_trusted to return a fixed
        non-terminal, non-intermediate value. On second iteration the
        hash matches, triggering hash_stall.
        """
        import rcx_pi.selfhost.step_mu as _step_mu_mod
        reset_step_budget()
        sentinel = "hash_stall_sentinel"
        # Disable P7-d shadow check — monkeypatching _step_trusted makes shadow meaningless
        _step_mu_mod._STAGE0_SHADOW_ENABLED = False  # ANTICHEAT_OK: disable shadow for monkeypatch test
        try:
            with patch(
                "rcx_pi.selfhost.step_mu._step_trusted",  # ANTICHEAT_OK: testing defensive kernel path
                return_value=sentinel,
            ):
                meta = step_kernel_mu([REWRITE_PROJ], "a", return_meta=True, max_steps=100)
        finally:
            _step_mu_mod._STAGE0_SHADOW_ENABLED = True  # ANTICHEAT_OK: restore shadow flag
        _assert_meta_shape(meta, expected_reason="hash_stall")
        assert meta["stall"] is True
        assert meta["steps_used"] == 2  # iteration 0: new hash, iteration 1: same hash

    def test_identity_projection_is_projection_applied(self):
        """Identity projection (a→a) yields projection_applied, not hash_stall.

        The kernel matches and reaches terminal state with _stall=false,
        even though the output equals the input.
        """
        reset_step_budget()
        meta = step_kernel_mu([IDENTITY_PROJ], "a", return_meta=True)
        _assert_meta_shape(meta, expected_reason="projection_applied")
        assert meta["output"] == "a"
        assert meta["stall"] is False

    def test_steps_used_positive_on_success(self):
        """steps_used reflects actual kernel iterations, not zero."""
        reset_step_budget()
        meta = step_kernel_mu([REWRITE_PROJ], "a", return_meta=True)
        assert meta["steps_used"] >= 1
        assert meta["max_steps"] == 10000  # default

    def test_meta_false_returns_bare_value(self):
        """return_meta=False returns bare Mu value (no dict wrapping)."""
        reset_step_budget()
        result = step_kernel_mu([REWRITE_PROJ], "a", return_meta=False)
        assert result == "b", f"Bare mode should return 'b', got {result!r}"
        assert not isinstance(result, dict) or "termination_reason" not in result

    def test_meta_false_stall_returns_input(self):
        """return_meta=False on stall returns original input unchanged."""
        reset_step_budget()
        result = step_kernel_mu([NO_MATCH_PROJ], "a", return_meta=False)
        assert result == "a", f"Stall bare mode should return 'a', got {result!r}"


# =============================================================================
# JS: termination_reason via step_kernel_meta API
# =============================================================================

class TestJsTerminationReason:
    """JS step_kernel_meta API reports correct termination reasons."""

    def test_projection_applied(self):
        """Successful projection match yields 'projection_applied'."""
        resp = _js_request(
            "step_kernel_meta",
            input="a",
            projections=[REWRITE_PROJ],
            maxSteps=100,
        )
        assert resp["success"], f"JS failed: {resp.get('error')}"
        meta = resp["result"]
        _assert_meta_shape(meta, expected_reason="projection_applied")
        assert meta["output"] == "b"
        assert meta["stall"] is False

    def test_kernel_stall(self):
        """No projection matches yields 'kernel_stall'."""
        resp = _js_request(
            "step_kernel_meta",
            input="a",
            projections=[NO_MATCH_PROJ],
            maxSteps=100,
        )
        assert resp["success"], f"JS failed: {resp.get('error')}"
        meta = resp["result"]
        _assert_meta_shape(meta, expected_reason="kernel_stall")
        assert meta["stall"] is True

    def test_max_steps_exhausted(self):
        """maxSteps=0 yields 'max_steps_exhausted' immediately."""
        resp = _js_request(
            "step_kernel_meta",
            input="a",
            projections=[REWRITE_PROJ],
            maxSteps=0,
        )
        assert resp["success"], f"JS failed: {resp.get('error')}"
        meta = resp["result"]
        _assert_meta_shape(meta, expected_reason="max_steps_exhausted")
        assert meta["stall"] is True
        assert meta["steps_used"] == 0
        assert meta["max_steps"] == 0

    def test_identity_projection_is_projection_applied(self):
        """Identity projection (a→a) yields projection_applied in JS too.

        hash_stall is a defensive path — kernel projections always progress.
        Verified via source lock (TestReasonSourceLock) and Python monkeypatch.
        """
        resp = _js_request(
            "step_kernel_meta",
            input="a",
            projections=[IDENTITY_PROJ],
            maxSteps=100,
        )
        assert resp["success"], f"JS failed: {resp.get('error')}"
        meta = resp["result"]
        _assert_meta_shape(meta, expected_reason="projection_applied")
        assert meta["output"] == "a"
        assert meta["stall"] is False


# =============================================================================
# Cross-substrate parity: reason strings match for same inputs
# =============================================================================

class TestCrossSubstrateReasonParity:
    """Python and JS produce identical termination reasons for same inputs."""

    @pytest.mark.parametrize("projs,input_val,expected_reason", [
        ([REWRITE_PROJ], "a", "projection_applied"),
        ([NO_MATCH_PROJ], "a", "kernel_stall"),
        ([IDENTITY_PROJ], "a", "projection_applied"),
    ], ids=["rewrite", "no_match", "identity"])
    def test_reason_parity(self, projs, input_val, expected_reason):
        """Same projections + input → same termination_reason in both substrates."""
        reset_step_budget()
        py_meta = step_kernel_mu(projs, input_val, return_meta=True, max_steps=100)

        js_resp = _js_request(
            "step_kernel_meta",
            input=input_val,
            projections=projs,
            maxSteps=100,
        )
        assert js_resp["success"], f"JS failed: {js_resp.get('error')}"
        js_meta = js_resp["result"]

        assert py_meta["termination_reason"] == js_meta["termination_reason"], (
            f"Reason mismatch: Python={py_meta['termination_reason']!r}, "
            f"JS={js_meta['termination_reason']!r}"
        )
        assert py_meta["stall"] == js_meta["stall"], (
            f"Stall mismatch: Python={py_meta['stall']}, JS={js_meta['stall']}"
        )
        assert py_meta["output"] == js_meta["output"], (
            f"Output mismatch: Python={py_meta['output']!r}, JS={js_meta['output']!r}"
        )

    def test_max_steps_exhausted_parity(self):
        """max_steps=0 produces same meta shape in both substrates."""
        reset_step_budget()
        py_meta = step_kernel_mu(
            [REWRITE_PROJ], "a", return_meta=True, max_steps=0,
        )
        js_resp = _js_request(
            "step_kernel_meta",
            input="a",
            projections=[REWRITE_PROJ],
            maxSteps=0,
        )
        assert js_resp["success"], f"JS failed: {js_resp.get('error')}"
        js_meta = js_resp["result"]

        assert py_meta["termination_reason"] == js_meta["termination_reason"] == "max_steps_exhausted"
        assert py_meta["steps_used"] == js_meta["steps_used"] == 0
        assert py_meta["max_steps"] == js_meta["max_steps"] == 0


# =============================================================================
# Source lock: reason strings exist in both substrates
# =============================================================================

class TestReasonSourceLock:
    """Verify all 4 reason strings are present in both substrate source files."""

    def test_python_source_contains_all_reasons(self):
        """Python step_mu.py contains all 4 termination reason strings."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        source = py_path.read_text()
        for reason in REASON_ENUM:
            assert reason in source, (
                f"Python source missing reason string: {reason!r}"
            )

    def test_js_source_contains_all_reasons(self):
        """JS eval_step.js contains all 4 termination reason strings."""
        source = _read_all_js_source()
        for reason in REASON_ENUM:
            assert reason in source, (
                f"JS source missing reason string: {reason!r}"
            )

    def test_reason_enum_is_exactly_four(self):
        """Reason enum has exactly 4 members — no silent additions."""
        assert len(REASON_ENUM) == 4, (
            f"Expected 4 reasons, got {len(REASON_ENUM)}: {REASON_ENUM}"
        )
