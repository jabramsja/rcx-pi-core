"""P7 Wave 5: Outer Loop Boundary Reclassification — Gate Tests.

Validates:
  Part A: Python reclassification — run_mu(), run_mu_structural(), list-to-linked-list
    removed from @host_iteration, marked BOUNDARY.
  Part B: JavaScript reclassification — run(), runStructural(), listToLinked(),
    runAlgorithmWithBridge(), runEnginePipelineRecursive() removed from @host_iteration,
    marked BOUNDARY.

Anti-laundering: All reclassified functions are provably OFF the kernel execution path.
Kernel path: step_kernel_mu → _step_trusted → _apply_projection_trusted →
  _stage0_match/_stage0_substitute (Python) / step → stage0Match/stage0Substitute (JS).
The reclassified functions CALL the kernel but are not ON the kernel path.

Evidence for: P7 Host Semantics Reduction, target gate G8.
L4 class: L4_STRUCTURAL.
"""

import inspect
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from rcx_pi.selfhost.step_mu import (
    run_mu,  # SPEED_OK: source inspection only
    run_mu_structural,  # SPEED_OK: source inspection only
    step_kernel_mu,  # SPEED_OK: source inspection only
)

from tests.repo_root import REPO_ROOT

JS_BOOTSTRAP_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js"
JS_KERNEL_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
JS_NORMALIZE_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "normalize.js"
JS_PIPELINE_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"


def _get_function_source(func):
    return textwrap.dedent(inspect.getsource(func))


# ===========================================================================
# Part A: Python Reclassification Tests
# ===========================================================================

class TestPythonOuterLoopBoundary:
    """Python outer-loop functions must be BOUNDARY, not @host_iteration."""

    def test_run_mu_no_host_iteration_decorator(self):
        """run_mu must NOT have @host_iteration decorator."""
        source = _get_function_source(run_mu)
        assert "@host_iteration" not in source, (
            "run_mu still has @host_iteration decorator (should be BOUNDARY since P7W5)"
        )

    def test_run_mu_has_boundary_docstring(self):
        """run_mu must have BOUNDARY in docstring."""
        source = _get_function_source(run_mu)
        assert "BOUNDARY" in source, (
            "run_mu missing BOUNDARY marker (reclassified P7W5)"
        )

    def test_run_mu_structural_no_host_iteration_decorator(self):
        """run_mu_structural must NOT have @host_iteration decorator."""
        source = _get_function_source(run_mu_structural)
        assert "@host_iteration" not in source, (
            "run_mu_structural still has @host_iteration (should be BOUNDARY since P7W5)"
        )

    def test_run_mu_structural_has_boundary_docstring(self):
        """run_mu_structural must have BOUNDARY in docstring."""
        source = _get_function_source(run_mu_structural)
        assert "BOUNDARY" in source, (
            "run_mu_structural missing BOUNDARY marker (reclassified P7W5)"
        )

    def test_step_kernel_mu_still_has_host_iteration(self):
        """step_kernel_mu MUST still have @host_iteration (irreducible kernel core)."""
        source = _get_function_source(step_kernel_mu)
        assert "@host_iteration" in source, (
            "step_kernel_mu lost @host_iteration — this is the irreducible kernel loop!"
        )

    def test_list_to_linked_boundary_comment(self):
        """list-to-linked-list conversion must have BOUNDARY comment, not @host_iteration."""
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
        text = path.read_text()
        assert "# BOUNDARY: list-to-linked-list conversion" in text, (
            "list-to-linked-list conversion missing BOUNDARY comment"
        )
        # Verify no @host_iteration on that specific line
        for line in text.splitlines():
            if "list-to-linked-list conversion" in line:
                assert "@host_iteration" not in line, (
                    "list-to-linked-list line still has @host_iteration marker"
                )
                break


# ===========================================================================
# Part B: JavaScript Reclassification Tests
# ===========================================================================

class TestJSOuterLoopBoundary:
    """JS outer-loop functions must be BOUNDARY, not @host_iteration."""

    def _check_js_function_boundary(self, filepath, func_name):
        """Verify a JS function has BOUNDARY and no @host_iteration in its JSDoc."""
        text = filepath.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if f"function {func_name}(" in line:
                block = "\n".join(lines[max(0, i - 15):i])
                assert "@host_iteration" not in block, (
                    f"JS {func_name}() still has @host_iteration marker"
                )
                assert "BOUNDARY" in block, (
                    f"JS {func_name}() missing BOUNDARY comment"
                )
                return
        pytest.fail(f"JS {func_name}() function not found in {filepath.name}")

    def test_js_run_boundary(self):
        self._check_js_function_boundary(JS_BOOTSTRAP_PATH, "run")

    def test_js_run_structural_boundary(self):
        self._check_js_function_boundary(JS_KERNEL_PATH, "runStructural")

    def test_js_list_to_linked_boundary(self):
        self._check_js_function_boundary(JS_NORMALIZE_PATH, "listToLinked")

    def test_js_run_algorithm_with_bridge_boundary(self):
        self._check_js_function_boundary(JS_PIPELINE_PATH, "runAlgorithmWithBridge")

    def test_js_run_engine_pipeline_recursive_boundary(self):
        self._check_js_function_boundary(JS_PIPELINE_PATH, "runEnginePipelineRecursive")

    def test_js_step_still_has_host_iteration(self):
        """JS step() MUST still have @host_iteration (irreducible kernel core)."""
        text = JS_BOOTSTRAP_PATH.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function step(" in line:
                block = "\n".join(lines[max(0, i - 10):i])
                assert "@host_iteration" in block, (
                    "JS step() lost @host_iteration — this is the irreducible kernel loop!"
                )
                return
        pytest.fail("JS step() function not found")


# ===========================================================================
# Kernel Path Exclusion Tests
# ===========================================================================

class TestKernelPathExclusion:
    """Prove reclassified functions are NOT on the kernel execution path."""

    def test_step_kernel_mu_does_not_call_run_mu(self):
        """step_kernel_mu must not call run_mu() — it IS the kernel, not the outer loop."""
        source = _get_function_source(step_kernel_mu)
        assert "run_mu(" not in source, (
            "step_kernel_mu calls run_mu() — these are separate layers"
        )

    def test_step_kernel_mu_does_not_call_run_mu_structural(self):
        """step_kernel_mu must not call run_mu_structural()."""
        source = _get_function_source(step_kernel_mu)
        assert "run_mu_structural(" not in source, (
            "step_kernel_mu calls run_mu_structural() — kernel does not call trace runner"
        )

    def test_run_mu_calls_step_mu(self):
        """run_mu MUST call step_mu — it's the outer driver that invokes the kernel."""
        source = _get_function_source(run_mu)
        assert "step_mu(" in source, (
            "run_mu doesn't call step_mu — outer loop must call kernel via step_mu"
        )


# ===========================================================================
# Ratchet Evidence
# ===========================================================================

class TestRatchetEvidence:
    """Verify ratchet reflects the P7W5 reduction."""

    def test_ratchet_passes(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Ratchet failed:\n{result.stderr}"

    def test_no_increases(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["increases"] == [], (
            f"Ratchet shows increases (regression): {data['increases']}"
        )

    def test_js_eval_step_passes(self):
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"JS eval_step failed:\n{result.stderr}"

    def test_js_debt_check_passes(self):
        result = subprocess.run(
            ["bash", "mu/tools/checks/check_js_debt.sh"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"JS debt check failed:\n{result.stdout}\n{result.stderr}"
