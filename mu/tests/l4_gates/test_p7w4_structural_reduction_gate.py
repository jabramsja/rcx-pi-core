"""P7 Wave 4: Structural Reduction + Boundary Reclassification — Gate Tests.

Validates:
  Part A (STRUCTURAL): Dead code removal from Stage 0 match, set() elimination,
    match()/substitute() reclassification as BOUNDARY.
  Part B (BOUNDARY): 7 boundary functions reclassified (4 Py + 3 JS).

Anti-laundering: All Part A changes are CODE CHANGES (dead code removal, host_builtin
surface reduction). Part B functions provably off kernel execution path:
  step_kernel_mu → _step_trusted → _apply_projection_trusted → _stage0_match/_stage0_substitute.

Evidence for: P7 Host Semantics Reduction, target gate G8.
L4 class: L4_STRUCTURAL.
"""

import ast
import inspect
import json
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

from rcx_pi.selfhost.eval_seed import (
    _stage0_match,  # ANTICHEAT_OK: AST inspection for P7W4 structural reduction gate
    _stage0_substitute,  # ANTICHEAT_OK: AST inspection for P7W4 structural reduction gate
    match,
    substitute,
)
from rcx_pi.selfhost.step_mu import step_kernel_mu  # SPEED_OK: source inspection only

from tests.repo_root import REPO_ROOT

JS_BOOTSTRAP_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "bootstrap_core.js"
JS_NORMALIZE_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "normalize.js"
JS_PIPELINE_PATH = REPO_ROOT / "mu" / "host" / "js" / "engine" / "pipeline.js"


def _get_function_source(func):
    return textwrap.dedent(inspect.getsource(func))


# ===========================================================================
# Part A: Structural Reduction Tests
# ===========================================================================

class TestStage0ListBranchRemoved:
    """Stage 0 match must NOT have list-handling code (dead code after normalization)."""

    def test_stage0_match_no_isinstance_list(self):
        """_stage0_match must not check isinstance(pattern, list)."""
        source = _get_function_source(_stage0_match)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                    if len(node.args) >= 2:
                        # Check if second arg is 'list' or tuple containing 'list'
                        arg = node.args[1]
                        if isinstance(arg, ast.Name) and arg.id == "list":
                            pytest.fail(
                                "_stage0_match still has isinstance(x, list) check "
                                "(P7W4: list branch should be removed)"
                            )

    def test_stage0_match_no_len_zip(self):
        """_stage0_match must not use len() or zip() (eliminated with list branch)."""
        source = _get_function_source(_stage0_match)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("len", "zip"):
                        pytest.fail(
                            f"_stage0_match still uses {node.func.id}() "
                            f"(P7W4: should be eliminated with list branch)"
                        )

    def test_stage0_match_no_set_wrapper(self):
        """_stage0_match must not wrap dict.keys() in set() (P7W4: direct view comparison)."""
        source = _get_function_source(_stage0_match)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "set":
                    pytest.fail(
                        "_stage0_match still wraps keys() in set() "
                        "(P7W4: dict_keys views support direct comparison)"
                    )

    def test_js_stage0_match_no_array_branch(self):
        """JS stage0Match must NOT have Array.isArray branch for patterns."""
        source = JS_BOOTSTRAP_PATH.read_text()
        # Find stage0Match function
        lines = source.splitlines()
        in_stage0 = False
        brace_depth = 0
        for i, line in enumerate(lines):
            if "function stage0Match(" in line:
                in_stage0 = True
                brace_depth = 0
            if in_stage0:
                brace_depth += line.count("{") - line.count("}")
                if "Array.isArray(pattern)" in line:
                    pytest.fail(
                        f"JS stage0Match still has Array.isArray(pattern) at line {i + 1} "
                        f"(P7W4: array branch should be removed)"
                    )
                if brace_depth <= 0 and in_stage0 and i > 0:
                    break


class TestStage0IsProductionPath:
    """Verify Stage 0 functions are the sole production kernel path (flag removed Wave 4)."""

    def test_stage0_functions_callable(self):
        assert callable(_stage0_match), "_stage0_match must be callable"
        assert callable(_stage0_substitute), "_stage0_substitute must be callable"

    def test_trusted_path_uses_stage0_directly(self):
        """_apply_projection_trusted must call Stage0 directly (no flag routing)."""
        import inspect
        from rcx_pi.selfhost.eval_seed import _apply_projection_trusted  # ANTICHEAT_OK: contract test
        source = inspect.getsource(_apply_projection_trusted)
        assert "_stage0_match(" in source, "trusted path must call _stage0_match"
        assert "_stage0_substitute(" in source, "trusted path must call _stage0_substitute"
        assert "_STAGE0_PILOT" not in source, (
            "trusted path must not reference _STAGE0_PILOT (flag removed Wave 4)"
        )


# ===========================================================================
# Part A: match/substitute Reclassification Tests
# ===========================================================================

class TestMatchSubstituteReclassified:
    """match() and substitute() must be BOUNDARY (off kernel path)."""

    def test_match_no_host_recursion_marker(self):
        source = _get_function_source(match)
        assert "@host_recursion" not in source, (
            "match() still has @host_recursion (should be BOUNDARY since P7W4)"
        )

    def test_match_has_boundary_comment(self):
        source = _get_function_source(match)
        assert "BOUNDARY" in source, (
            "match() missing BOUNDARY comment (reclassified P7W4)"
        )

    def test_substitute_no_host_recursion_marker(self):
        source = _get_function_source(substitute)
        assert "@host_recursion" not in source, (
            "substitute() still has @host_recursion (should be BOUNDARY since P7W4)"
        )

    def test_substitute_has_boundary_comment(self):
        source = _get_function_source(substitute)
        assert "BOUNDARY" in source, (
            "substitute() missing BOUNDARY comment (reclassified P7W4)"
        )

    def test_js_match_no_host_recursion(self):
        """JS match() must NOT have @host_recursion marker."""
        source = JS_BOOTSTRAP_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if "function match(" in line:
                block = "\n".join(lines[max(0, i - 10):i])
                assert "@host_recursion" not in block, (
                    f"JS match() still has @host_recursion (reclassified P7W4)"
                )
                assert "BOUNDARY" in block, (
                    f"JS match() missing BOUNDARY comment"
                )
                return
        pytest.fail("JS match() function not found")

    def test_js_substitute_no_host_recursion(self):
        """JS substitute() must NOT have @host_recursion marker."""
        source = JS_BOOTSTRAP_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if "function substitute(" in line:
                block = "\n".join(lines[max(0, i - 10):i])
                assert "@host_recursion" not in block, (
                    f"JS substitute() still has @host_recursion (reclassified P7W4)"
                )
                assert "BOUNDARY" in block, (
                    f"JS substitute() missing BOUNDARY comment"
                )
                return
        pytest.fail("JS substitute() function not found")


# ===========================================================================
# Part B: Boundary Reclassification Tests
# ===========================================================================

class TestBoundaryReclassified:
    """Functions reclassified from @host_iteration to BOUNDARY."""

    def test_py_normalize_for_match_boundary(self):
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "match_mu.py"
        text = path.read_text()
        assert "@host_iteration: boundary normalization" not in text, (
            "normalize_for_match still has @host_iteration marker"
        )
        assert "BOUNDARY: normalization loop" in text, (
            "normalize_for_match missing BOUNDARY comment"
        )

    def test_py_denormalize_from_match_boundary(self):
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "match_mu.py"
        text = path.read_text()
        assert "@host_iteration: boundary denormalization" not in text, (
            "denormalize_from_match still has @host_iteration marker"
        )
        assert "BOUNDARY: denormalization loop" in text, (
            "denormalize_from_match missing BOUNDARY comment"
        )

    def test_py_make_depth_budget_boundary(self):
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "mu_type.py"
        text = path.read_text()
        assert "@host_iteration" not in text, (
            "make_depth_budget still has @host_iteration marker"
        )
        assert "BOUNDARY:" in text, (
            "make_depth_budget missing BOUNDARY comment"
        )

    def test_py_classify_linked_list_boundary(self):
        path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "classify_mu.py"
        text = path.read_text()
        assert "@host_iteration:" not in text, (
            "classify_linked_list still has @host_iteration marker"
        )
        assert "BOUNDARY:" in text, (
            "classify_linked_list missing BOUNDARY comment"
        )

    def test_js_normalize_boundary(self):
        text = JS_NORMALIZE_PATH.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function normalize(" in line:
                block = "\n".join(lines[max(0, i - 10):i])
                assert "@host_recursion" not in block, (
                    "JS normalize() still has @host_recursion"
                )
                assert "@host_iteration" not in block, (
                    "JS normalize() still has @host_iteration"
                )
                assert "BOUNDARY" in block, (
                    "JS normalize() missing BOUNDARY comment"
                )
                return
        pytest.fail("JS normalize() not found")

    def test_js_denormalize_boundary(self):
        text = JS_NORMALIZE_PATH.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function denormalize(" in line:
                block = "\n".join(lines[max(0, i - 10):i])
                assert "@host_recursion" not in block, (
                    "JS denormalize() still has @host_recursion"
                )
                assert "@host_iteration" not in block, (
                    "JS denormalize() still has @host_iteration"
                )
                assert "BOUNDARY" in block, (
                    "JS denormalize() missing BOUNDARY comment"
                )
                return
        pytest.fail("JS denormalize() not found")

    def test_js_run_engine_pipeline_boundary(self):
        text = JS_PIPELINE_PATH.read_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "function runEnginePipeline(" in line:
                block = "\n".join(lines[max(0, i - 10):i])
                assert "@host_iteration" not in block, (
                    "JS runEnginePipeline() still has @host_iteration"
                )
                assert "BOUNDARY" in block, (
                    "JS runEnginePipeline() missing BOUNDARY comment"
                )
                return
        pytest.fail("JS runEnginePipeline() not found")


# ===========================================================================
# Kernel Path Exclusion Tests
# ===========================================================================

class TestKernelPathExclusion:
    """Prove reclassified functions are NOT on the kernel execution path."""

    def test_step_kernel_mu_does_not_call_match(self):
        """step_kernel_mu must not call standalone match() — uses _step_trusted instead."""
        source = _get_function_source(step_kernel_mu)
        # Use word-boundary regex to avoid false positives like normalize_for_match(
        standalone_match_calls = re.findall(r'(?<![_\w])match\(', source)
        assert not standalone_match_calls, (
            "step_kernel_mu calls match() (should use _step_trusted → _stage0_match)"
        )

    def test_step_kernel_mu_does_not_call_substitute(self):
        """step_kernel_mu must not call standalone substitute()."""
        source = _get_function_source(step_kernel_mu)
        standalone_sub_calls = re.findall(r'(?<![_\w])substitute\(', source)
        assert not standalone_sub_calls, (
            "step_kernel_mu calls substitute() (should use _step_trusted → _stage0_substitute)"
        )

    def test_no_seed_patterns_contain_arrays(self):
        """Verify zero seed projection patterns/bodies contain raw arrays."""
        import json
        seed_dirs = ["substrate", "closures", "bridge", "programs"]
        for d in seed_dirs:
            p = REPO_ROOT / "mu" / d
            if not p.exists():
                continue
            for f in p.glob("*.json"):
                data = json.loads(f.read_text())
                projs = data if isinstance(data, list) else data.get("projections", [])
                for proj in projs:
                    if not isinstance(proj, dict):
                        continue
                    pat = proj.get("pattern", {})
                    body = proj.get("body", {})
                    assert not isinstance(pat, list), (
                        f"{f.name}: pattern is a raw array (Stage 0 list branch assumption violated)"
                    )
                    assert not isinstance(body, list), (
                        f"{f.name}: body is a raw array (Stage 0 list branch assumption violated)"
                    )


# ===========================================================================
# Ratchet Evidence
# ===========================================================================

class TestRatchetEvidence:
    """Verify ratchet reflects the P7W4 reduction."""

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
