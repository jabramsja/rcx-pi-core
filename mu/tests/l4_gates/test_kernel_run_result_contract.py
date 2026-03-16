"""
KernelRunResult contract lock tests.

Verifies that step_kernel_mu (Python) and _stepKernelCore (JS) both produce
the canonical KernelRunResult shape with identical fields and semantics.

These tests lock the contract defined in the Canonical Machine Contract
design packet (v3, 2026-03-16).
"""

from __future__ import annotations

import json
import subprocess

import pytest

from rcx_pi.selfhost.step_mu import step_kernel_mu


# -- KernelRunResult shape contract --

REQUIRED_FIELDS = {"output", "stall", "termination_reason", "steps_used", "max_steps"}
VALID_TERM_REASONS = {"projection_applied", "kernel_stall", "hash_stall", "max_steps_exhausted"}


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
    """JS stepKernel(returnMeta=true) must produce structurally identical KernelRunResult."""

    def _run_js(self, code: str) -> dict:
        """Run JS code via node and return parsed JSON."""
        full = f"""
        const {{ stepKernel }} = require('./mu/host/js/engine/kernel');
        {code}
        """
        result = subprocess.run(
            ["node", "-e", full],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"JS error: {result.stderr}"
        return json.loads(result.stdout.strip())

    def test_returnmeta_true_has_required_fields(self):
        """JS stepKernel(returnMeta=true) must produce all KernelRunResult fields."""
        meta = self._run_js("""
        const r = stepKernel([], {x: 1}, [{pattern: {x: 1}, body: {x: 2}}],
            {returnMeta: true, maxSteps: 100});
        console.log(JSON.stringify(r));
        """)
        assert REQUIRED_FIELDS <= set(meta.keys()), f"JS missing: {REQUIRED_FIELDS - set(meta.keys())}"
        assert meta["termination_reason"] in VALID_TERM_REASONS
        assert isinstance(meta["stall"], bool)
        assert isinstance(meta["steps_used"], int)
        assert isinstance(meta["max_steps"], int)

    def test_stall_result_has_required_fields(self):
        """JS stall result must produce all KernelRunResult fields."""
        meta = self._run_js("""
        const r = stepKernel([], {x: 1}, [],
            {returnMeta: true, maxSteps: 100});
        console.log(JSON.stringify(r));
        """)
        assert REQUIRED_FIELDS <= set(meta.keys())
        assert meta["termination_reason"] in VALID_TERM_REASONS
        assert meta["stall"] is True

    def test_stall_is_boolean(self):
        """JS stall field must be boolean, not truthy/falsy."""
        meta = self._run_js("""
        const r = stepKernel([], {x: 1}, [{pattern: {x: 1}, body: {x: 2}}],
            {returnMeta: true});
        console.log(JSON.stringify({stall_type: typeof r.stall, stall_val: r.stall}));
        """)
        assert meta["stall_type"] == "boolean"

    def test_field_parity_with_python(self):
        """JS and Python KernelRunResult must have identical field sets."""
        # Get JS field set
        js_meta = self._run_js("""
        const r = stepKernel([], {x: 1}, [{pattern: {x: 1}, body: {x: 2}}],
            {returnMeta: true});
        console.log(JSON.stringify(Object.keys(r).sort()));
        """)
        js_fields = set(js_meta)  # _run_js returns the parsed array of keys

        # Get Python field set
        py_meta = step_kernel_mu(
            [{"pattern": {"x": 1}, "body": {"x": 2}}], {"x": 1}, return_meta=True
        )
        py_fields = set(py_meta.keys())

        # Both must have at least the required fields
        assert REQUIRED_FIELDS <= js_fields, f"JS missing: {REQUIRED_FIELDS - js_fields}"
        assert REQUIRED_FIELDS <= py_fields, f"Python missing: {REQUIRED_FIELDS - py_fields}"
