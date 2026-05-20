"""P7 Wave 5: Outer Loop Boundary Reclassification — Gate Tests.

Validates:
  Part A: Python reclassification — run_mu(), run_mu_structural()
    removed from @host_iteration, marked BOUNDARY.
  Part B: JavaScript reclassification — run(), runStructural(),
    runAlgorithmWithBridge(), runEnginePipelineRecursive() removed from
    @host_iteration, marked BOUNDARY.
  Part C: step_kernel_with_vm has no stale @host_iteration marker after S1-C.
  Part D: list_to_linked/listToLinked are boundary-normalization conversion
    loops, not tracked @host_iteration debt.

Anti-laundering: All reclassified functions are provably OFF the kernel execution path.
Kernel path: step_kernel_mu → _step_kernel_with_vm → Stage0 VM for all
  Python projection groups / _stepKernelCore → _stepTrusted (JS).
The reclassified functions CALL the kernel but are not ON the kernel path.
list_to_linked/listToLinked are bounded host-to-Mu boundary construction loops
that prepare linked-list input for the kernel but do not execute projections.

Evidence for: P7 Host Semantics Reduction, target gate G8.
L4 class: L4_STRUCTURAL.
"""

import ast
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
STEP_MU_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"


def _get_function_source(func):
    return textwrap.dedent(inspect.getsource(func))


def _get_function_source_from_file(path: Path, name: str) -> str:
    source = path.read_text()
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            decorator_lines = [decorator.lineno for decorator in node.decorator_list]
            start = min([node.lineno, *decorator_lines]) - 1
            return textwrap.dedent("\n".join(lines[start:node.end_lineno]))
    pytest.fail(f"{name} not found in {path}")


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

    def test_step_kernel_with_vm_has_no_host_iteration_decorator(self):
        """_step_kernel_with_vm dispatches through Stage0 VM, not host projection iteration."""
        source = _get_function_source_from_file(STEP_MU_PATH, "_step_kernel_with_vm")
        assert "@host_iteration" not in source, (
            "_step_kernel_with_vm still has stale @host_iteration marker after S1-C VM cutover"
        )
        assert "ALL projections via Stage0 VM" in source, (
            "_step_kernel_with_vm source must keep explicit Stage0 VM cutover grounding"
        )

    def test_list_to_linked_boundary_normalization_only(self):
        """list_to_linked remains boundary-normalization evidence, not tracked debt."""
        text = STEP_MU_PATH.read_text()
        for line in text.splitlines():
            if "for item in reversed(items):" in line:
                assert "@host_iteration" not in line, (
                    "list_to_linked conversion loop must not count as tracked @host_iteration debt"
                )
                assert "BOUNDARY" in line and "boundary-normalization" in line, (
                    "list_to_linked conversion loop must remain boundary-normalization evidence"
                )
                return
        pytest.fail("list_to_linked for-loop not found in step_mu.py")


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

    def test_js_run_algorithm_with_bridge_boundary(self):
        self._check_js_function_boundary(JS_PIPELINE_PATH, "runAlgorithmWithBridge")

    def test_js_run_engine_pipeline_recursive_boundary(self):
        self._check_js_function_boundary(JS_PIPELINE_PATH, "runEnginePipelineRecursive")

    def test_js_active_kernel_core_still_has_host_iteration(self):
        """JS _stepKernelCore owns @host_iteration; bootstrap step is boundary scan."""
        kernel_lines = JS_KERNEL_PATH.read_text().splitlines()
        for i, line in enumerate(kernel_lines):
            if "function _stepKernelCore(" in line:
                block = "\n".join(kernel_lines[max(0, i - 10):i])
                body = "\n".join(kernel_lines[i:i + 80])
                assert "@host_iteration" in block, (
                    "JS _stepKernelCore lost @host_iteration — this is the active kernel loop!"
                )
                assert "for (let i = 0; i < maxSteps; i++)" in body, (
                    "JS _stepKernelCore must remain the maxSteps kernel driver loop"
                )
                break
        else:
            pytest.fail("JS _stepKernelCore() function not found")

        bootstrap_lines = JS_BOOTSTRAP_PATH.read_text().splitlines()
        for i, line in enumerate(bootstrap_lines):
            if "function step(" in line:
                block = "\n".join(bootstrap_lines[max(0, i - 10):i])
                assert "@host_iteration" not in block, (
                    "JS bootstrap_core.step must not retain stale @host_iteration tracking"
                )
                assert "BOUNDARY" in block, (
                    "JS bootstrap_core.step must remain boundary evidence after marker move"
                )
                return
        pytest.fail("JS step() function not found")

    def test_js_list_to_linked_boundary_normalization_only(self):
        """JS listToLinked remains boundary-normalization evidence, not tracked debt."""
        text = JS_NORMALIZE_PATH.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function listToLinked(" in line:
                block = "\n".join(lines[max(0, i - 10):i])
                assert "@host_iteration" not in block, (
                    "JS listToLinked() must not count as tracked @host_iteration debt"
                )
                assert "BOUNDARY" in block and "boundary-normalization" in block, (
                    "JS listToLinked() must remain boundary-normalization evidence"
                )
                return
        pytest.fail("JS listToLinked() function not found")


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

    def test_step_kernel_mu_calls_list_to_linked_for_boundary_cursor(self):
        """step_kernel_mu still receives boundary-normalized linked-list cursor input."""
        source = _get_function_source(step_kernel_mu)
        assert "list_to_linked(" in source, (
            "step_kernel_mu must call list_to_linked for bounded linked-list data preparation"
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
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["increases"] == [], (
            f"Ratchet shows increases (regression): {data['increases']}"
        )
        current = data["current"]
        assert current["python"]["host_iteration"] == 1
        assert current["javascript"]["host_iteration"] == 1
        assert sum(current["python"].values()) == 2
        assert sum(current["javascript"].values()) == 3

    def test_js_eval_step_passes(self):
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"JS eval_step failed:\n{result.stderr}"

    def test_baseline_locks_boundary_demotion_counts(self):
        baseline = json.loads(
            (REPO_ROOT / "tools" / "checks" / "host_semantics_baseline.json").read_text()
        )
        assert baseline["counts"]["python"]["host_iteration"] == 1
        assert baseline["counts"]["javascript"]["host_iteration"] == 1
        assert baseline["total_python"] == 2
        assert baseline["total_javascript"] == 3
        assert baseline["total"] == 5
