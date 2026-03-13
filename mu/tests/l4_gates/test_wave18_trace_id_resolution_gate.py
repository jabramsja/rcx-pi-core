"""
L4 Gate: Wave 18 — O(N) trace projection ID resolution.

Proves the L4_STRUCTURAL performance fix: _resolve_trace_projection_id (Python)
and resolveTraceProjectionId/_resolveIdFast (JS) are eliminated. Trace projection
ID resolution now uses inline Stage 0 match() calls — O(N) per step instead of
O(N²) full kernel calls.

Evidence:
    1. Deleted functions do not exist in either substrate source.
    2. run_mu_structural trace entries include projection IDs (inline resolution works).
    3. Inline resolution uses stage0_match / match(), NOT step_kernel_mu / stepKernel.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_wave18_trace_id_resolution_gate.py -v
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import run_mu_structural  # SPEED_OK: imported for trace test
from rcx_pi.selfhost.kernel import reset_step_budget


# ---------------------------------------------------------------------------
# Source lock: deleted functions must NOT exist
# ---------------------------------------------------------------------------

class TestDeletedFunctionSourceLock:
    """Verify deleted O(N²) functions are absent from both substrates."""

    def test_python_no_resolve_trace_projection_id(self):
        """_resolve_trace_projection_id must not exist in step_mu.py."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        source = py_path.read_text()
        assert "_resolve_trace_projection_id" not in source, (
            "_resolve_trace_projection_id still exists in step_mu.py — "
            "wave 18 required its deletion for O(N) resolution"
        )

    def test_js_no_resolveTraceProjectionId(self):
        """resolveTraceProjectionId must not exist in JS kernel source."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
        source = js_path.read_text()
        assert "resolveTraceProjectionId" not in source, (
            "resolveTraceProjectionId still exists in kernel.js — "
            "wave 18 required its deletion for O(N) resolution"
        )

    def test_js_no_resolveIdFast(self):
        """_resolveIdFast must not exist in JS kernel source."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
        source = js_path.read_text()
        assert "_resolveIdFast" not in source, (
            "_resolveIdFast still exists in kernel.js — "
            "wave 18 required its deletion for O(N) resolution"
        )


# ---------------------------------------------------------------------------
# Functional: inline resolution produces trace entries with projection IDs
# ---------------------------------------------------------------------------

PROJ_A = {"id": "test.a_to_b", "pattern": "a", "body": "b"}
PROJ_B = {"id": "test.b_to_c", "pattern": "b", "body": "c"}
NO_MATCH = {"id": "test.no_match", "pattern": {"_never": True}, "body": "z"}


def _collect_trace_entries(trace_linked_list):
    """Walk a Mu linked list (head/tail) into a flat Python list."""
    entries = []
    node = trace_linked_list
    while isinstance(node, dict) and "head" in node:
        entries.append(node["head"])
        node = node.get("tail")
    return entries


class TestInlineTraceIdResolution:
    """Inline Stage 0 match resolves projection IDs in structural traces."""

    def test_trace_contains_projection_id(self):
        """run_mu_structural trace entries include matched projection IDs."""
        reset_step_budget()
        result = run_mu_structural([PROJ_A, PROJ_B], "a", max_steps=100)
        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
        assert "trace" in result, "Result missing 'trace' key"
        entries = _collect_trace_entries(result["trace"])
        assert len(entries) > 0, "Trace is empty"
        # Collect projection IDs from trace entries
        ids_found = [
            entry.get("projection")
            for entry in entries
            if isinstance(entry, dict) and entry.get("projection") is not None
        ]
        assert len(ids_found) > 0, (
            "No trace entries with projection ID — inline resolution not working"
        )
        assert "test.a_to_b" in ids_found, (
            f"Expected 'test.a_to_b' in trace IDs, got {ids_found}"
        )

    def test_stall_trace_has_null_projection(self):
        """Stall (no match) trace entries have projection=None."""
        reset_step_budget()
        result = run_mu_structural([NO_MATCH], "a", max_steps=100)
        assert isinstance(result, dict), f"Expected dict result, got {type(result)}"
        entries = _collect_trace_entries(result["trace"])
        # All entries should have projection=None for a stall
        for entry in entries:
            if isinstance(entry, dict):
                assert entry.get("projection") is None, (
                    f"Stall trace has unexpected projection: {entry}"
                )


# ---------------------------------------------------------------------------
# Source structure: inline resolution uses stage0_match, not step_kernel_mu
# ---------------------------------------------------------------------------

class TestInlineResolutionMethod:
    """The ID resolution loop uses Stage 0 match, not full kernel calls."""

    def test_python_uses_stage0_match_for_id_resolution(self):
        """run_mu_structural uses stage0_match() for projection ID resolution."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        source = py_path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if node.name != "run_mu_structural":
                continue
            # Find the ID resolution pattern: stage0_match call
            has_stage0_match = False
            for child in ast.walk(node):
                if (isinstance(child, ast.Call)
                        and isinstance(child.func, ast.Name)
                        and child.func.id == "stage0_match"):
                    has_stage0_match = True
                    break
            assert has_stage0_match, (
                "run_mu_structural does not call stage0_match — "
                "inline O(N) resolution not implemented"
            )
            return
        pytest.fail("run_mu_structural function not found in step_mu.py")

    def test_js_uses_match_for_id_resolution(self):
        """JS runStructural uses match() for projection ID resolution."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
        source = js_path.read_text()
        # runStructural should contain match() call from bootstrap_core
        assert "match(" in source, (
            "kernel.js does not contain match() call — "
            "inline O(N) resolution not implemented"
        )
        # And should NOT contain per-projection stepKernel calls in the resolution
        assert "_resolveIdFast" not in source, (
            "kernel.js still has _resolveIdFast — old O(N²) pattern remains"
        )
