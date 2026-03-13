"""
L4 Gate: Wave 5 cleanup — validation helper, JS registry asymmetry, docstring accuracy.

Proves:
1. step_mu.py contains _validate_projection_fields helper (source proof)
2. JS seed_loader.js fails-closed on registry asymmetry (source proof)
3. eval_seed.py _match_inner documents 26 isinstance calls (source proof)

Usage:
    PYTHONHASHSEED=0 pytest mu/tests/l4_gates/test_wave5_cleanup_gate.py -v
"""

from __future__ import annotations

import ast
import re

from tests.repo_root import REPO_ROOT


# ---------------------------------------------------------------------------
# Source proof helpers
# ---------------------------------------------------------------------------

def _read_source(module_path: str) -> str:
    """Read source file from mu/ path."""
    return (REPO_ROOT / module_path).read_text()


# ---------------------------------------------------------------------------
# Gate Tests: _validate_projection_fields helper extraction
# ---------------------------------------------------------------------------

class TestValidateProjectionFieldsHelper:
    """Gate: step_mu.py has shared _validate_projection_fields helper."""

    def test_helper_function_exists(self):
        """AST proof: _validate_projection_fields defined in step_mu.py."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/step_mu.py")
        tree = ast.parse(src)
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_validate_projection_fields":
                found = True
                break
        assert found, (
            "step_mu.py must define _validate_projection_fields helper"
        )

    def test_helper_called_by_run_mu(self):
        """Source proof: run_mu calls _validate_entry_point (which calls _validate_projection_fields)."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/step_mu.py")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_mu":
                func_src = ast.get_source_segment(src, node)
                assert func_src and "_validate_entry_point" in func_src, (
                    "run_mu must call _validate_entry_point"
                )
                return
        raise AssertionError("run_mu not found in step_mu.py")

    def test_helper_called_by_run_mu_structural(self):
        """Source proof: run_mu_structural calls _validate_entry_point (which calls _validate_projection_fields)."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/step_mu.py")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "run_mu_structural":
                func_src = ast.get_source_segment(src, node)
                assert func_src and "_validate_entry_point" in func_src, (
                    "run_mu_structural must call _validate_entry_point"
                )
                return
        raise AssertionError("run_mu_structural not found in step_mu.py")

    def test_validate_entry_point_calls_validate_projection_fields(self):
        """Source proof: _validate_entry_point delegates to _validate_projection_fields."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/step_mu.py")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_validate_entry_point":
                func_src = ast.get_source_segment(src, node)
                assert func_src and "_validate_projection_fields" in func_src, (
                    "_validate_entry_point must call _validate_projection_fields"
                )
                return
        raise AssertionError("_validate_entry_point not found in step_mu.py")


# ---------------------------------------------------------------------------
# Gate Tests: JS seed_loader registry asymmetry fail-closed
# ---------------------------------------------------------------------------

class TestJsSeedLoaderRegistryAsymmetry:
    """Gate: JS seed_loader.js fails-closed when checksum exists but projection IDs don't."""

    def test_registry_asymmetry_throws(self):
        """Source proof: seed_loader.js throws on missing CORE_SEED_PROJECTION_IDS entry."""
        src = _read_source("mu/host/js/core/seed_loader.js")
        # The fail-closed pattern: if (!expectedIds) { throw new Error(...registry asymmetry...) }
        assert "registry asymmetry" in src, (
            "seed_loader.js must throw on registry asymmetry "
            "(checksum present but projection IDs missing)"
        )

    def test_fail_closed_before_id_comparison(self):
        """Source proof: registry asymmetry check precedes projection ID comparison."""
        src = _read_source("mu/host/js/core/seed_loader.js")
        asymmetry_pos = src.find("registry asymmetry")
        id_compare_pos = src.find("JSON.stringify(actualIds)")
        assert asymmetry_pos > 0, "registry asymmetry throw must exist"
        assert id_compare_pos > 0, "projection ID comparison must exist"
        assert asymmetry_pos < id_compare_pos, (
            "registry asymmetry check must come BEFORE projection ID comparison "
            "(fail-closed: reject unknown seeds before comparing IDs)"
        )


# ---------------------------------------------------------------------------
# Gate Tests: eval_seed.py _match_inner isinstance count accuracy
# ---------------------------------------------------------------------------

class TestMatchInnerIsinstanceCount:
    """Gate: _match_inner docstring accurately documents isinstance call count."""

    def test_docstring_claims_26(self):
        """Source proof: _match_inner docstring states 26 isinstance calls."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/eval_seed.py")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_match_inner":
                docstring = ast.get_docstring(node)
                assert docstring and "26 isinstance" in docstring, (
                    "_match_inner docstring must claim 26 isinstance calls "
                    "(13 budget path + 13 depth path)"
                )
                return
        raise AssertionError("_match_inner not found in eval_seed.py")

    def test_actual_isinstance_count(self):
        """AST proof: _match_inner body contains exactly 26 isinstance calls."""
        src = _read_source("mu/host/python/rcx_pi/selfhost/eval_seed.py")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "_match_inner":
                count = 0
                for child in ast.walk(node):
                    if (isinstance(child, ast.Call)
                            and isinstance(child.func, ast.Name)
                            and child.func.id == "isinstance"):
                        count += 1
                assert count == 26, (
                    f"_match_inner must contain exactly 26 isinstance calls "
                    f"(13 budget path + 13 depth path), found {count}"
                )
                return
        raise AssertionError("_match_inner not found in eval_seed.py")
