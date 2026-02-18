"""
Kernel mode caller-discipline hardening.

Ensures step_kernel_mu is only called with safe, hardcoded mode flags.
Prevents future misuse by:
1. Inventorying all production callsites (fail-closed on new raw usage).
2. Proving invalid mode routing is rejected.
3. Verifying all wrappers enforce mode discipline.

Zero semantic behavior changes — this is guardrail enforcement only.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from rcx_pi.selfhost.step_mu import (
    step_kernel_mu,
    step_mu,
    run_mu,
    run_mu_structural,
    run_algorithm_meta_circular,
    KERNEL_RESERVED_FIELDS,
)


# ── Callsite inventory: fail-closed guard against new raw usage ─────────


# The ONLY production functions that call step_kernel_mu directly.
# If a new callsite appears, this test FAILS — forcing explicit review.
KNOWN_PRODUCTION_CALLERS = {
    "step_mu",                      # core kernel, domain validation (default modes)
    "run_algorithm_meta_circular",  # bridge kernel, algorithm_runtime validation
    "_resolve_trace_projection_id", # bridge kernel, domain validation
    "run_mu_structural",            # bridge kernel, domain validation
}


def _find_step_kernel_mu_callers(source: str) -> set[str]:
    """AST-walk to find all functions that call step_kernel_mu."""
    tree = ast.parse(source)
    callers = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        func_name = node.name
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                # Direct call: step_kernel_mu(...)
                if isinstance(child.func, ast.Name) and child.func.id == "step_kernel_mu":
                    callers.add(func_name)
                # Attribute call: self.step_kernel_mu(...) or module.step_kernel_mu(...)
                elif (isinstance(child.func, ast.Attribute)
                      and child.func.attr == "step_kernel_mu"):
                    callers.add(func_name)
    return callers


def test_step_kernel_mu_callsite_inventory():
    """
    Fail-closed: only KNOWN_PRODUCTION_CALLERS may call step_kernel_mu.

    If you add a new callsite, either:
    1. Add a safe wrapper instead of calling step_kernel_mu directly.
    2. Add the function name to KNOWN_PRODUCTION_CALLERS with review.
    """
    step_mu_path = Path(inspect.getfile(step_kernel_mu))
    source = step_mu_path.read_text()
    actual_callers = _find_step_kernel_mu_callers(source)

    # step_kernel_mu itself is a definition, not a caller — exclude it
    actual_callers.discard("step_kernel_mu")

    unexpected = actual_callers - KNOWN_PRODUCTION_CALLERS
    missing = KNOWN_PRODUCTION_CALLERS - actual_callers

    assert not unexpected, (
        f"New step_kernel_mu callsite(s) found: {unexpected}. "
        "Add safe wrapper or update KNOWN_PRODUCTION_CALLERS with review."
    )
    assert not missing, (
        f"Expected callsite(s) missing: {missing}. "
        "Was a wrapper removed? Update KNOWN_PRODUCTION_CALLERS."
    )


# ── Invalid mode rejection (fail-closed) ───────────────────────────────


class TestInvalidModeRejection:
    """step_kernel_mu rejects invalid mode values."""

    def test_invalid_kernel_mode_raises(self):
        with pytest.raises(ValueError, match="kernel_mode"):
            step_kernel_mu([], "input", kernel_mode="invalid")

    def test_invalid_validation_mode_raises(self):
        with pytest.raises(ValueError, match="validation_mode"):
            step_kernel_mu([], "input", validation_mode="invalid")

    def test_empty_kernel_mode_raises(self):
        with pytest.raises(ValueError, match="kernel_mode"):
            step_kernel_mu([], "input", kernel_mode="")

    def test_empty_validation_mode_raises(self):
        with pytest.raises(ValueError, match="validation_mode"):
            step_kernel_mu([], "input", validation_mode="")


# ── Wrapper mode discipline verification ────────────────────────────────


class TestWrapperModeDiscipline:
    """Verify wrappers use correct hardcoded modes."""

    def test_step_mu_uses_default_core_domain(self):
        """step_mu calls step_kernel_mu with default (core, domain)."""
        # step_mu rejects non-linear patterns then calls step_kernel_mu
        # with default args. Verify it doesn't pass exotic modes.
        source = inspect.getsource(step_mu)
        # Should NOT contain kernel_mode= or validation_mode= (uses defaults)
        assert "kernel_mode=" not in source
        assert "validation_mode=" not in source

    def test_run_algorithm_uses_bridge_algorithm_runtime(self):
        """run_algorithm_meta_circular uses bridge + algorithm_runtime."""
        source = inspect.getsource(run_algorithm_meta_circular)
        assert 'kernel_mode="bridge"' in source
        assert 'validation_mode="algorithm_runtime"' in source

    def test_run_mu_structural_uses_bridge_domain(self):
        """run_mu_structural uses bridge + domain."""
        source = inspect.getsource(run_mu_structural)
        assert 'kernel_mode="bridge"' in source
        assert 'validation_mode="domain"' in source


# ── Reserved field security boundary ────────────────────────────────────


class TestReservedFieldBoundary:
    """Domain mode rejects all kernel-reserved fields in input."""

    def test_domain_rejects_run_engine_in_input(self):
        """_run_engine cannot be smuggled in domain input."""
        poisoned = {"_run_engine": {"projections": [], "input": "x"}}
        with pytest.raises(ValueError, match="_run_engine"):
            step_kernel_mu([], poisoned, validation_mode="domain")

    def test_domain_rejects_tail_call_in_input(self):
        """_tail_call cannot be smuggled in domain input."""
        poisoned = {"_tail_call": {"projections": [], "input": "x"}}
        with pytest.raises(ValueError, match="_tail_call"):
            step_kernel_mu([], poisoned, validation_mode="domain")

    def test_domain_rejects_mode_field_in_input(self):
        """_mode cannot be smuggled in domain input."""
        poisoned = {"_mode": "done", "_result": "hacked"}
        with pytest.raises(ValueError, match="_mode"):
            step_kernel_mu([], poisoned, validation_mode="domain")

    def test_reserved_fields_count_is_stable(self):
        """Fail if reserved fields set changes without review."""
        # 24 fields as of Phase 8c hardening
        assert len(KERNEL_RESERVED_FIELDS) == 24, (
            f"KERNEL_RESERVED_FIELDS count changed: {len(KERNEL_RESERVED_FIELDS)}. "
            "Review security implications and update this test."
        )
