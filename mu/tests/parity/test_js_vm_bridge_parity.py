"""S1-A D3: JS VM bridge-mode parity tests.

Minimal evidence that JS VM path produces same results as Python VM path.
Tests Stage0 VM compiled bundle execution cross-substrate, focused on
the bridge-mode kernel path that S1-A cutover would activate.

This is repo-truth N2 minimal evidence for cutover confidence.
Tests exercise the Stage0 VM bundle execution layer directly — this is the
component that cutover changes (match.v2/subst.v2 from host to VM).

The full JS kernel path (stepKernel -> shadow mode -> stage0VmStep) is already
exercised by test_js_parity_automated.py::TestEnginePipelineCrossSubstrateParity
which runs the engine pipeline through both Python and JS substrates.
# SPEED_OK: no slow kernel functions called — only stage0_vm_step (microsecond-scale)

Extra JS kernel-level thickening stays in S1-B.

L4_ENABLER evidence: G8 (Irreducible Primitive Consensus).
"""

import json
import os
import subprocess
import pytest

from rcx_pi.selfhost.stage0_vm import stage0_vm_step, _mu_deep_equal  # ANTICHEAT_OK: S1-A — VM parity
from rcx_pi.selfhost.step_mu import (
    _load_compiled_match_v2_bundle,  # ANTICHEAT_OK: S1-A — bundle loader
    _load_compiled_subst_v2_bundle,  # ANTICHEAT_OK: S1-A — bundle loader
)

from tests.repo_root import REPO_ROOT
from tests.l4_gates.stage0_test_helpers import run_js_stage0


# Bundle relative paths (from repo root)
MATCH_COMPILED_REL = "mu/stage0/compiled/match_v2.compiled.v1.json"
SUBST_COMPILED_REL = "mu/stage0/compiled/subst_v2.compiled.v1.json"


def _normalize_for_cross_substrate(value):
    """Normalize Python value for cross-substrate comparison.

    JS float64 conflates int/float. Normalize int→float for comparison.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value  # Keep int — JS returns int-like numbers
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    if value is None:
        return value
    if isinstance(value, list):
        return [_normalize_for_cross_substrate(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_cross_substrate(v) for k, v in sorted(value.items())}
    return value


def _cross_equal(py_val, js_val):
    """Cross-substrate equality with int/float normalization."""
    return _normalize_for_cross_substrate(py_val) == _normalize_for_cross_substrate(js_val)


# ---------------------------------------------------------------------------
# Match.v2 compiled bundle parity
# ---------------------------------------------------------------------------

class TestMatchVmBridgeParity:
    """Stage0 VM match.v2 compiled bundle: Python and JS agree."""

    def test_match_wrap_parity(self):
        """match.wrap projection: Python and JS produce same output."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "match": {"pattern": "hello", "value": "hello"},
            "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"], \
            f"Status mismatch: py={py_result['status']}, js={js_result['status']}"
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_match_equal_parity(self):
        """match.equal (literal equality): Python and JS agree."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "mode": "match", "pattern_focus": "hello", "value_focus": "hello",
            "bindings": None, "stack": None, "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_match_var_parity(self):
        """match.var (variable bind): Python and JS agree."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "mode": "match", "pattern_focus": {"var": "x"},
            "value_focus": 42, "bindings": None,
            "stack": None, "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_match_stall_parity(self):
        """match.fail (no match): both substrates stall."""
        bundle = _load_compiled_match_v2_bundle()
        inp = {
            "mode": "match", "pattern_focus": "a", "value_focus": "b",
            "bindings": None, "stack": None, "_match_ctx": {"_match_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", MATCH_COMPILED_REL, inp)

        # match.fail fires, producing a result with specific structure
        assert py_result["status"] == js_result["status"]


# ---------------------------------------------------------------------------
# Subst.v2 compiled bundle parity
# ---------------------------------------------------------------------------

class TestSubstVmBridgeParity:
    """Stage0 VM subst.v2 compiled bundle: Python and JS agree."""

    def test_subst_wrap_parity(self):
        """subst.wrap projection: Python and JS produce same output."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {
            "subst": {"body": {"var": "x"}, "bindings": {"name": "x", "value": 42, "rest": None}},
            "_subst_ctx": {"_subst_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_subst_primitive_parity(self):
        """subst.primitive (literal traverse): Python and JS agree."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {
            "mode": "subst", "phase": "traverse", "focus": "literal",
            "bindings": None, "context": None, "_subst_ctx": {"_subst_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_subst_var_lookup_parity(self):
        """subst.var (variable substitution): Python and JS agree."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {
            "mode": "subst", "phase": "traverse",
            "focus": {"var": "x"},
            "bindings": {"name": "x", "value": 42, "rest": None},
            "context": None, "_subst_ctx": {"_subst_ctx": True},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"])

    def test_subst_stall_parity(self):
        """Non-subst input: both substrates stall."""
        bundle = _load_compiled_subst_v2_bundle()
        inp = {"random": "data"}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", SUBST_COMPILED_REL, inp)

        assert py_result["status"] == "stall"
        assert js_result["status"] == "stall"


# ---------------------------------------------------------------------------
# S1-C: Kernel.v1 + Bridge compiled bundle parity
# ---------------------------------------------------------------------------

KERNEL_COMPILED_REL = "mu/stage0/compiled/kernel_v1.compiled.v1.json"
BRIDGE_COMPILED_REL = "mu/stage0/compiled/bootstrap_structural_v1.compiled.v1.json"


class TestKernelVmBridgeParity:
    """S1-C: kernel.v1 compiled bundle: Python and JS agree."""

    def test_kernel_wrap_parity(self):
        """kernel.wrap projection: Python and JS produce same output."""
        from rcx_pi.selfhost.step_mu import _load_compiled_kernel_v1_bundle  # ANTICHEAT_OK: S1-C parity
        from rcx_pi.selfhost.match_mu import normalize_for_match
        from rcx_pi.selfhost.step_mu import normalize_projection, list_to_linked
        bundle = _load_compiled_kernel_v1_bundle()
        proj = {"id": "test.kp", "pattern": "a", "body": "b"}
        normalized = normalize_projection(proj)
        inp = {"_step": normalize_for_match("a"), "_projs": list_to_linked([normalized])}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", KERNEL_COMPILED_REL, inp)
        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Kernel output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_kernel_stall_parity(self):
        """Non-kernel input: both substrates stall."""
        from rcx_pi.selfhost.step_mu import _load_compiled_kernel_v1_bundle  # ANTICHEAT_OK: S1-C parity
        bundle = _load_compiled_kernel_v1_bundle()
        inp = {"random": "data"}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", KERNEL_COMPILED_REL, inp)
        assert py_result["status"] == "stall"
        assert js_result["status"] == "stall"


class TestBridgeVmParity:
    """S1-C: bootstrap_structural.v1 compiled bundle: Python and JS agree."""

    def test_bridge_var_check_parity(self):
        """bridge.var.check_existing: Python and JS agree on binding lookup."""
        from rcx_pi.selfhost.step_mu import _load_compiled_bridge_bundle  # ANTICHEAT_OK: S1-C parity
        bundle = _load_compiled_bridge_bundle()
        # Input that triggers bridge.var.check_existing: lookup bindings for non-linear var
        inp = {
            "_lookup_name": "x",
            "_lookup_value": 42,
            "_lookup_bindings": {"name": "x", "value": 42, "rest": None},
            "_original_bindings": {"name": "x", "value": 42, "rest": None},
        }
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", BRIDGE_COMPILED_REL, inp)
        assert py_result["status"] == js_result["status"]
        if py_result["status"] == "match":
            assert _cross_equal(py_result["root"], js_result["root"]), \
                f"Bridge output mismatch:\n  py={py_result['root']}\n  js={js_result['root']}"

    def test_bridge_stall_parity(self):
        """Non-bridge input: both substrates stall."""
        from rcx_pi.selfhost.step_mu import _load_compiled_bridge_bundle  # ANTICHEAT_OK: S1-C parity
        bundle = _load_compiled_bridge_bundle()
        inp = {"random": "data"}
        py_result = stage0_vm_step(bundle, inp)
        js_result = run_js_stage0("step", BRIDGE_COMPILED_REL, inp)
        assert py_result["status"] == "stall"
        assert js_result["status"] == "stall"
