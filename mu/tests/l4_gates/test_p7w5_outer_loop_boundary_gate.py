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
Kernel path: step_kernel_mu(return_packet=True) → _step_kernel_with_vm → Stage0 VM for all
  Python projection groups / _stepKernelCore → Stage0 VM or _stepTrusted (JS).
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
    step_mu,  # SPEED_OK: source inspection only
    step_kernel_mu,  # SPEED_OK: source inspection only
)

from tests.repo_root import REPO_ROOT

JS_BOOTSTRAP_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js"
JS_KERNEL_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "kernel.js"
JS_NORMALIZE_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "normalize.js"
JS_PIPELINE_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"
JS_ROUTING_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "routing.js"
JS_CLI_MAIN_PATH = REPO_ROOT / "mu" / "host" / "js" / "cli" / "main.js"
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


def _js_function_body(lines: list[str], function_index: int) -> str:
    body = []
    depth = 0
    opened = False
    for line in lines[function_index:]:
        body.append(line)
        if "{" in line:
            opened = True
        depth += line.count("{") - line.count("}")
        if opened and depth == 0:
            return "\n".join(body)
    pytest.fail(f"Could not find JS function body ending after line {function_index + 1}")


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

    def test_step_kernel_mu_is_single_step_packet_boundary(self):
        """step_kernel_mu(return_packet=True) returns one terminal-or-continuation packet per call."""
        source = _get_function_source(step_kernel_mu)
        assert "@host_iteration" in source, (
            "step_kernel_mu still carries host transition authority and must stay ratchet-visible"
        )
        assert "single-step" in source
        assert "KernelDriverStepPacket" in source
        assert "for step_i in range(max_steps)" not in source, (
            "step_kernel_mu reintroduced the old max_steps-owned kernel loop"
        )
        assert "while (not caller_supplied_fuel) or (fuel_cursor is not None):" not in source, (
            "step_kernel_mu must not retain the old omitted-fuel run-until-terminal loop"
        )
        assert "list_to_linked([None] * (max_steps + 1))" not in source, (
            "step_kernel_mu must not construct host-counted no-fuel compatibility fuel"
        )
        assert "compatibility_fuel" not in source, (
            "step_kernel_mu must not hide omitted-fuel compatibility behind a helper fuel cursor"
        )
        assert "[None] *" not in source, (
            "step_kernel_mu must not turn max_steps into a host-sized fuel list"
        )
        assert "range(max_steps)" not in source, (
            "step_kernel_mu must not reintroduce max_steps as the semantic loop owner"
        )
        assert "if steps_used >= watchdog_cap:" in source, (
            "step_kernel_mu must keep max_steps as a watchdog check, not the loop owner"
        )
        assert '"kind": "terminal"' in source
        assert '"kind": "continuation"' in source
        assert '"kernel_driver_continuation_state"' in source
        assert "continuation_state" in source
        assert "return_packet=True" in source
        assert "BOUNDARY: legacy public no-fuel behavior" in source
        assert "while packet[\"kind\"] == \"continuation\":" in source
        assert "if caller_supplied_fuel:" in source and 'fuel_cursor = fuel_cursor["tail"]' in source, (
            "step_kernel_mu must consume Mu fuel only on the explicit supplied-fuel path"
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

    def test_js_routing_continuation_driver_is_bounded_packet_boundary(self):
        """Routing/metabolization must drive explicit packets through kernel domain validation."""
        routing_lines = JS_ROUTING_PATH.read_text().splitlines()
        routing_text = "\n".join(routing_lines)
        assert "const KERNEL_DRIVER_BOUNDARY_WATCHDOG = 1000;" in routing_text
        assert "../core/security" not in routing_text

        for func_name in ("runHemisphereRouting", "runMetabolizationCycle"):
            for i, line in enumerate(routing_lines):
                if f"function {func_name}(" in line:
                    body = _js_function_body(routing_lines, i)
                    break
            else:
                pytest.fail(f"JS {func_name}() function not found in routing.js")

            assert "validateNoKernelReservedFields(wrapped" not in body
            assert "validateDomainBoundary(wrapped" in body
            assert "returnPacket: true" in body
            assert "continuationState: packet.continuation" in body
            assert "validationMode: 'algorithm_runtime'" in body
            assert "maxSteps: KERNEL_DRIVER_BOUNDARY_WATCHDOG" in body
            assert "maxSteps: 10000" not in body

    def test_json_api_dispatch_does_not_run_cli_self_tests(self):
        """JSON API parity calls must not pay the human CLI self-test suite."""
        request = {
            "action": "step_kernel_meta",
            "input": "a",
            "projections": [{"id": "test.rewrite", "pattern": "a", "body": "b"}],
            "maxSteps": 1,
        }
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request)],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=10,
        )
        assert result.returncode == 0, result.stderr
        assert "JSON_API_RESPONSE:" in result.stdout
        assert "Same projections, same semantics" not in result.stdout
        assert "All tests passed" not in result.stdout

    def test_json_api_dispatch_precedes_self_tests_in_cli_main(self):
        """Source lock: cli/main.js dispatches JSON API before requiring self_tests."""
        source = JS_CLI_MAIN_PATH.read_text(encoding="utf-8")
        json_idx = source.index("if (process.argv.includes('--json-api'))")
        self_tests_require_idx = source.index("require('../tests/self_tests')")
        self_tests_call_idx = source.index("runSelfTests(seedsContext)")
        assert json_idx < self_tests_require_idx < self_tests_call_idx

    def test_js_active_kernel_core_is_single_step_packet_boundary(self):
        """JS _stepKernelCore returns one terminal-or-continuation packet per call."""
        kernel_lines = JS_KERNEL_PATH.read_text().splitlines()
        for i, line in enumerate(kernel_lines):
            if "function _stepKernelCore(" in line:
                block = "\n".join(kernel_lines[max(0, i - 10):i])
                body = _js_function_body(kernel_lines, i)
                assert "@host_iteration" in block, (
                    "JS _stepKernelCore still carries host transition authority and must stay ratchet-visible"
                )
                assert "single-step" in block
                assert "for (let i = 0; i < maxSteps; i++)" not in body, (
                    "JS _stepKernelCore reintroduced the old maxSteps-owned kernel loop"
                )
                assert "while (!callerSuppliedFuel || fuelCursor !== null)" not in body, (
                    "JS _stepKernelCore must not retain the omitted-fuel run-until-terminal loop"
                )
                assert "compatibilityFuelNode <= maxSteps" not in body, (
                    "JS _stepKernelCore must not construct host-counted no-fuel compatibility fuel"
                )
                assert "listToLinked(compatibilityFuelItems)" not in body, (
                    "JS _stepKernelCore must not convert a maxSteps-sized host list into fuel"
                )
                assert "compatibilityFuel" not in body, (
                    "JS _stepKernelCore must not hide omitted-fuel compatibility behind a helper fuel cursor"
                )
                assert "Array.from" not in body and ".fill(" not in body, (
                    "JS _stepKernelCore must not construct host-sized synthetic fuel arrays"
                )
                assert "if (stepsUsed >= watchdogCap)" in body, (
                    "JS _stepKernelCore must keep maxSteps as a watchdog check, not the loop owner"
                )
                assert "kind: 'terminal'" in body
                assert "kind: 'continuation'" in body
                assert "kernel_driver_continuation_state" in body
                assert "continuationState" in body
                assert "matchResultForContext" not in body, (
                    "JS _stepKernelCore must not move continuation authority into a nested helper site"
                )
                assert "if (callerSuppliedFuel)" in body and "fuelCursor = fuelCursor.tail" in body, (
                    "JS _stepKernelCore must consume Mu fuel only on the explicit supplied-fuel path"
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

    def test_step_mu_uses_reviewed_kernel_boundary(self):
        """step_mu remains the reviewed public compatibility caller for the kernel."""
        source = _get_function_source(step_mu)
        assert "step_kernel_mu(" in source, (
            "step_mu must stay the reviewed direct step_kernel_mu compatibility caller"
        )
        assert "while packet" not in source, (
            "step_mu must not add a second host loop authority site"
        )

    def test_run_mu_uses_step_mu_boundary(self):
        """run_mu repeats the reviewed step_mu boundary instead of becoming a raw kernel caller."""
        source = _get_function_source(run_mu)
        assert "step_mu(" in source, (
            "run_mu must drive progress through the reviewed step_mu boundary"
        )
        assert "step_kernel_mu(" not in source, (
            "run_mu must not add an unreviewed raw step_kernel_mu callsite"
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
    """Verify ratchet reflects honest residual kernel markers."""

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
