"""
Documentation Contract Tests - Prevents doc drift by verifying claims.

This implements Phase 2 of the documentation drift solution:
- DOC_CONTRACTS defines what each doc claims about the codebase
- Tests verify those claims against actual code/seeds
- CI fails if docs drift from reality

The key insight: Claims are tests. If a doc says "7 projections",
there's a test that asserts len(projections) == 7.

Usage:
    pytest tests/docs/test_doc_contracts.py -v

Add to audit_fast.sh for CI enforcement.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
DOCS_CORE = REPO_ROOT / "mu" / "docs" / "core"


# =============================================================================
# DOC_CONTRACTS: The authoritative mapping of doc claims to verifiable facts
# =============================================================================
#
# When updating this file:
# 1. If a seed's projection count changes, update the count here
# 2. If a function is renamed/moved, update the path here
# 3. If a doc is archived, remove its entry
#
# This is analogous to SEED_CHECKSUMS in seed_integrity.py

DOC_CONTRACTS: dict[str, dict[str, Any]] = {
    # =========================================================================
    # BootstrapPrimitives.v0.md - Claims about the 4 irreducible primitives
    # (mu_equal DEMOTED 2026-02-10, now derivable from mu_hash_cached)
    # =========================================================================
    "BootstrapPrimitives.v0.md": {
        "functions": [
            "rcx_pi.selfhost.eval_seed.step",           # eval_step primitive
            "rcx_pi.selfhost.mu_type.mu_equal",         # mu_equal (DEMOTED, kept as convenience wrapper)
            "rcx_pi.selfhost.mu_type.is_mu",            # validation primitive
            "rcx_pi.selfhost.seed_integrity.load_verified_seed",  # projection_loader
        ],
        "constants": {
            # max_steps and stack_guard are constants, not functions
            "rcx_pi.selfhost.step_mu.KERNEL_RESERVED_FIELDS": 24,  # Security boundary (Gate 3: entry points moved out, Boot1 P2/P3: +_run_engine, +_tail_call)
        },
        "seeds": {},  # No specific seed counts claimed
    },

    # =========================================================================
    # EVAL_SEED.v0.md - Claims about pattern matching and substitution
    # =========================================================================
    "EVAL_SEED.v0.md": {
        "functions": [
            "rcx_pi.selfhost.eval_seed.match",
            "rcx_pi.selfhost.eval_seed.substitute",
            "rcx_pi.selfhost.eval_seed.apply_projection",
            "rcx_pi.selfhost.eval_seed.step",
        ],
        "constants": {},
        "seeds": {},
    },

    # =========================================================================
    # MetaCircularKernel.v0.md - Claims about kernel projections
    # =========================================================================
    "MetaCircularKernel.v0.md": {
        "functions": [
            "rcx_pi.selfhost.step_mu.step_kernel_mu",
            "rcx_pi.selfhost.step_mu.load_combined_kernel_projections",
        ],
        "constants": {},
        "seeds": {
            "kernel.v1.json": 7,   # 7 kernel projections
            "match.v2.json": 8,    # 8 match projections (7 + match.fail)
            "subst.v2.json": 12,   # 12 subst projections
        },
    },

    # =========================================================================
    # SelfHosting.v0.md - Claims about the self-hosting journey
    # =========================================================================
    "SelfHosting.v0.md": {
        "functions": [
            "rcx_pi.selfhost.match_mu.match_mu",
            "rcx_pi.selfhost.subst_mu.subst_mu",
            "rcx_pi.selfhost.step_mu.step_mu",
        ],
        "constants": {},
        "seeds": {
            "match.v1.json": 7,    # Original match seed
            "subst.v1.json": 12,   # Original subst seed
            "classify.v1.json": 6, # Classification seed
        },
    },

    # =========================================================================
    # BootstrapStructuralBridge.v0.md - Non-linear pattern support
    # =========================================================================
    "BootstrapStructuralBridge.v0.md": {
        "functions": [
            "rcx_pi.selfhost.step_mu.load_combined_kernel_with_bridge_projections",
        ],
        "constants": {},
        "seeds": {
            "bootstrap_structural.v1.json": 5,  # 5 bridge projections
        },
    },

    # =========================================================================
    # EngineNewsStructural.v0.md - Closure detection (recurrence)
    # =========================================================================
    "EngineNewsStructural.v0.md": {
        "functions": [
            "rcx_pi.selfhost.step_mu.run_mu_structural",
        ],
        "constants": {},
        "seeds": {
            "recurrence.v1.json": 9,  # 9 recurrence projections
        },
    },

    # =========================================================================
    # OperatorExhaustion.v0.md - Operator exhaustion detection
    # =========================================================================
    "OperatorExhaustion.v0.md": {
        "functions": [],
        "constants": {},
        "seeds": {
            "exhaustion.v1.json": 13,  # 13 exhaustion projections (v1.3.0: +2 sentinel-skip)
        },
    },

    # =========================================================================
    # Boot0Architecture.v0.md - Bootstrap layer architecture
    # =========================================================================
    "Boot0Architecture.v0.md": {
        "functions": [
            "rcx_pi.selfhost.step_mu.validate_no_kernel_reserved_fields",
            "rcx_pi.selfhost.step_mu.validate_kernel_projections_first",
            "rcx_pi.selfhost.mu_type.assert_mu",
        ],
        "constants": {
            "rcx_pi.selfhost.mu_type.MAX_MU_DEPTH": 300,
        },
        "seeds": {},
    },

    # =========================================================================
    # MuType.v0.md - Mu type definition
    # =========================================================================
    "MuType.v0.md": {
        "functions": [
            "rcx_pi.selfhost.mu_type.is_mu",
            "rcx_pi.selfhost.mu_type.mu_equal",
            "rcx_pi.selfhost.mu_type.mu_hash",
        ],
        "constants": {
            "rcx_pi.selfhost.mu_type.MAX_MU_DEPTH": 300,
            "rcx_pi.selfhost.mu_type.MAX_MU_WIDTH": 1000,
        },
        "seeds": {},
    },

    # =========================================================================
    # RCXKernel.v0.md - RCX kernel overview
    # =========================================================================
    "RCXKernel.v0.md": {
        "functions": [
            "rcx_pi.selfhost.kernel.reset_step_budget",
        ],
        "constants": {},
        "seeds": {
            "kernel.v1.json": 7,
        },
    },

    # =========================================================================
    # ObserverEventContract.v0.md - Observer event schema and event names
    # =========================================================================
    "ObserverEventContract.v0.md": {
        "functions": [],
        "constants": {
            "rcx_pi.selfhost.step_mu.ENGINE_EXIT_REASONS": 4,  # 4 exit reasons (closure, exhaustion, stall, completed)
        },
        "seeds": {},
    },
}


# =============================================================================
# Test Helpers
# =============================================================================

def get_module_and_attr(dotted_path: str) -> tuple[str, str]:
    """Split 'module.path.function' into ('module.path', 'function')."""
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid path: {dotted_path}")
    return parts[0], parts[1]


def function_exists(dotted_path: str) -> bool:
    """Check if a function exists at the given module path."""
    try:
        module_path, func_name = get_module_and_attr(dotted_path)
        module = importlib.import_module(module_path)
        return hasattr(module, func_name) and callable(getattr(module, func_name))
    except (ImportError, AttributeError):
        return False


def get_constant_value(dotted_path: str) -> Any:
    """Get the value of a constant at the given module path."""
    module_path, const_name = get_module_and_attr(dotted_path)
    module = importlib.import_module(module_path)
    value = getattr(module, const_name)
    # For collections, return length
    if hasattr(value, "__len__"):
        return len(value)
    return value


def get_seed_projection_count(seed_name: str) -> int:
    """Get the projection count for a seed file."""
    from rcx_pi.selfhost.seed_integrity import get_seed_path, load_verified_seed
    seed_path = get_seed_path(seed_name)
    seed = load_verified_seed(seed_path)
    return len(seed.get("projections", []))


# =============================================================================
# Structure Tests (L1) - Verify docs have required headers
# =============================================================================

class TestDocHeaders:
    """Verify all docs have DOC_STATUS headers."""

    def test_all_core_docs_have_headers(self):
        """Every doc in mu/docs/core/ must have a DOC_STATUS header."""
        missing = []
        for doc_path in sorted(DOCS_CORE.glob("*.md")):
            content = doc_path.read_text()
            if "DOC_STATUS" not in content[:1000]:
                missing.append(doc_path.name)

        assert not missing, (
            f"Docs missing DOC_STATUS header: {missing}\n"
            f"Run: python tools/docs/add_doc_headers.py"
        )

    @pytest.mark.parametrize("doc_name", list(DOC_CONTRACTS.keys()))
    def test_contracted_doc_exists(self, doc_name):
        """Every doc in DOC_CONTRACTS must exist."""
        doc_path = DOCS_CORE / doc_name
        assert doc_path.exists(), (
            f"DOC_CONTRACTS references nonexistent doc: {doc_name}\n"
            f"Either create the doc or remove it from DOC_CONTRACTS"
        )


# =============================================================================
# Function Contract Tests (L2) - Verify claimed functions exist
# =============================================================================

class TestFunctionContracts:
    """Verify functions claimed in docs actually exist."""

    @pytest.mark.parametrize(
        "doc_name,func_path",
        [
            (doc, func)
            for doc, contract in DOC_CONTRACTS.items()
            for func in contract.get("functions", [])
        ],
        ids=lambda x: x if isinstance(x, str) and "." in x else None
    )
    def test_function_exists(self, doc_name, func_path):
        """Function claimed in doc must exist in code."""
        assert function_exists(func_path), (
            f"{doc_name} claims function '{func_path}' exists, but it doesn't.\n"
            f"Either:\n"
            f"  1. Update the doc to remove/fix the reference\n"
            f"  2. Update DOC_CONTRACTS to reflect the new function location\n"
            f"  3. Restore the function if it was accidentally deleted"
        )


# =============================================================================
# Constant Contract Tests (L2) - Verify claimed constants have expected values
# =============================================================================

class TestConstantContracts:
    """Verify constants claimed in docs have expected values."""

    @pytest.mark.parametrize(
        "doc_name,const_path,expected_value",
        [
            (doc, const, value)
            for doc, contract in DOC_CONTRACTS.items()
            for const, value in contract.get("constants", {}).items()
        ],
        ids=lambda x: x if isinstance(x, str) and "." in x else None
    )
    def test_constant_value(self, doc_name, const_path, expected_value):
        """Constant claimed in doc must have expected value."""
        actual_value = get_constant_value(const_path)
        assert actual_value == expected_value, (
            f"{doc_name} claims '{const_path}' = {expected_value}, "
            f"but actual value is {actual_value}.\n"
            f"Either:\n"
            f"  1. Update the doc to reflect the new value\n"
            f"  2. Update DOC_CONTRACTS with the new expected value\n"
            f"  3. Fix the code if the value changed accidentally"
        )


# =============================================================================
# Seed Contract Tests (L2) - Verify claimed projection counts match reality
# =============================================================================

class TestSeedContracts:
    """Verify seed projection counts match doc claims."""

    @pytest.mark.parametrize(
        "doc_name,seed_name,expected_count",
        [
            (doc, seed, count)
            for doc, contract in DOC_CONTRACTS.items()
            for seed, count in contract.get("seeds", {}).items()
        ],
        ids=lambda x: x if isinstance(x, str) and ".json" in x else None
    )
    def test_seed_projection_count(self, doc_name, seed_name, expected_count):
        """Seed projection count must match doc claim."""
        actual_count = get_seed_projection_count(seed_name)
        assert actual_count == expected_count, (
            f"{doc_name} claims '{seed_name}' has {expected_count} projections, "
            f"but actual count is {actual_count}.\n"
            f"Either:\n"
            f"  1. Update the doc to reflect the new count\n"
            f"  2. Update DOC_CONTRACTS with the new expected count\n"
            f"  3. Fix the seed if projections changed accidentally"
        )


# =============================================================================
# Cross-Reference Tests (L2) - Verify internal doc links
# =============================================================================

class TestDocCrossReferences:
    """Verify internal doc links are valid."""

    def test_status_md_exists(self):
        """STATUS.md must exist (referenced by all doc headers)."""
        assert (REPO_ROOT / "STATUS.md").exists()

    def test_tasks_md_exists(self):
        """TASKS.md must exist (referenced by all doc headers)."""
        assert (REPO_ROOT / "TASKS.md").exists()

    def test_no_line_number_references(self):
        """Docs should not contain fragile line number references."""
        violations = []
        # Pattern: file.py:123 or file.py:123-456
        line_ref_pattern = re.compile(r'\b\w+\.py:\d+(?:-\d+)?\b')

        for doc_path in sorted(DOCS_CORE.glob("*.md")):
            content = doc_path.read_text()
            matches = line_ref_pattern.findall(content)
            if matches:
                violations.append((doc_path.name, matches[:3]))  # First 3 examples

        # This is a WARNING, not a failure (yet)
        # Uncomment the assert when ready to enforce
        if violations:
            msg = "Docs with line number references (consider using function names):\n"
            for doc, refs in violations:
                msg += f"  {doc}: {refs}\n"
            # pytest.fail(msg)  # Uncomment to enforce
            import warnings
            warnings.warn(msg)


# =============================================================================
# Meta Tests - Verify the verification system works
# =============================================================================

class TestDocContractsMetaValidation:
    """Verify DOC_CONTRACTS itself is valid."""

    def test_all_docs_in_contracts_exist(self):
        """Every doc in DOC_CONTRACTS must exist on disk."""
        missing = []
        for doc_name in DOC_CONTRACTS:
            if not (DOCS_CORE / doc_name).exists():
                missing.append(doc_name)
        assert not missing, f"DOC_CONTRACTS references nonexistent docs: {missing}"

    def test_no_empty_contracts(self):
        """Every doc in DOC_CONTRACTS must have at least one claim."""
        empty = []
        for doc_name, contract in DOC_CONTRACTS.items():
            has_functions = bool(contract.get("functions"))
            has_constants = bool(contract.get("constants"))
            has_seeds = bool(contract.get("seeds"))
            if not (has_functions or has_constants or has_seeds):
                empty.append(doc_name)
        assert not empty, (
            f"Docs with empty contracts (no claims to verify): {empty}\n"
            f"Either add claims or remove from DOC_CONTRACTS"
        )

    def test_contracts_cover_high_drift_docs(self):
        """High-drift docs must have contracts."""
        high_drift_docs = [
            "Boot0Architecture.v0.md",
            "SelfHosting.v0.md",
            "MetaCircularKernel.v0.md",
            "BootstrapPrimitives.v0.md",
        ]
        missing = [d for d in high_drift_docs if d not in DOC_CONTRACTS]
        assert not missing, f"High-drift docs missing from DOC_CONTRACTS: {missing}"
