"""
Grounding tests for audit infrastructure claims.

These tests verify that the audit infrastructure works as documented.
Created based on grounding agent recommendations (2026-01-29).
"""

import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent


class TestArchiveBlocking:
    """Verify that archived tests cannot be run even with explicit paths."""

    def test_archive_conftest_exists(self):
        """Archive conftest.py must exist to block collection."""
        conftest = REPO_ROOT / "tests" / "archive" / "conftest.py"
        assert conftest.exists(), "tests/archive/conftest.py missing"

    def test_archive_conftest_has_ignore_hook(self):
        """Archive conftest.py must have pytest_ignore_collect hook."""
        conftest = REPO_ROOT / "tests" / "archive" / "conftest.py"
        content = conftest.read_text()
        assert "pytest_ignore_collect" in content, (
            "Archive conftest.py must define pytest_ignore_collect hook"
        )
        assert "return True" in content, (
            "pytest_ignore_collect must return True to block collection"
        )

    def test_archive_readme_exists(self):
        """Archive README.md must document the archive purpose."""
        readme = REPO_ROOT / "tests" / "archive" / "README.md"
        assert readme.exists(), "tests/archive/README.md missing"

    def test_archive_in_collect_ignore(self):
        """Archive must be in conftest.py collect_ignore list."""
        conftest = REPO_ROOT / "tests" / "conftest.py"
        content = conftest.read_text()
        assert "collect_ignore" in content, (
            "tests/conftest.py must define collect_ignore"
        )
        assert '"archive"' in content or "'archive'" in content, (
            "collect_ignore must include 'archive'"
        )


class TestDeprecationEnforcement:
    """Verify that deprecation warnings are enforced as errors."""

    def test_pyproject_has_filterwarnings(self):
        """pyproject.toml must configure filterwarnings."""
        pyproject = REPO_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        assert "filterwarnings" in content, (
            "pyproject.toml must configure filterwarnings"
        )
        assert "error::DeprecationWarning" in content, (
            "filterwarnings must treat DeprecationWarning as error"
        )

    def test_kernel_class_deleted(self):
        """Kernel class must be deleted (was legacy scaffolding)."""
        # Kernel class was removed in 2026-01-29 cleanup
        with pytest.raises(ImportError):
            from rcx_pi.selfhost.kernel import Kernel  # noqa: F401

    def test_create_kernel_deleted(self):
        """create_kernel() must be deleted (was legacy scaffolding)."""
        # create_kernel was removed in 2026-01-29 cleanup
        with pytest.raises(ImportError):
            from rcx_pi.selfhost.kernel import create_kernel  # noqa: F401


class TestAuditScriptStructure:
    """Verify audit scripts have correct structure."""

    def test_green_gate_exists(self):
        """green_gate.sh must exist."""
        script = REPO_ROOT / "scripts" / "green_gate.sh"
        assert script.exists(), "scripts/green_gate.sh missing"

    def test_green_gate_has_contraband_check(self):
        """green_gate.sh must run contraband check."""
        script = REPO_ROOT / "scripts" / "green_gate.sh"
        content = script.read_text()
        assert "contraband" in content.lower(), (
            "green_gate.sh must include contraband check"
        )

    def test_green_gate_has_ast_police(self):
        """green_gate.sh must run AST police."""
        script = REPO_ROOT / "scripts" / "green_gate.sh"
        content = script.read_text()
        assert "ast_police" in content, (
            "green_gate.sh must include AST police check"
        )

    def test_green_gate_check_order(self):
        """green_gate.sh must run checks in correct order (syntax, contraband, AST, tests)."""
        script = REPO_ROOT / "scripts" / "green_gate.sh"
        content = script.read_text()

        # Extract run_python function for ordering check
        # (avoid false positives from comments about pytest-xdist)
        run_python_start = content.find("run_python()")
        run_python_end = content.find("}", run_python_start)
        run_python_func = content[run_python_start:run_python_end]

        # Find positions within run_python function
        syntax_pos = run_python_func.find("py_compile")
        contraband_pos = run_python_func.find("contraband")
        ast_pos = run_python_func.find("ast_police")
        pytest_pos = run_python_func.find("-m pytest")

        assert syntax_pos != -1, "py_compile check missing from run_python"
        assert contraband_pos != -1, "contraband check missing from run_python"
        assert ast_pos != -1, "ast_police check missing from run_python"
        assert pytest_pos != -1, "pytest missing from run_python"

        # Verify order within run_python
        assert syntax_pos < contraband_pos, (
            "Syntax check must come before contraband"
        )
        assert contraband_pos < ast_pos, (
            "Contraband must come before AST police"
        )
        assert ast_pos < pytest_pos, (
            "AST police must come before pytest"
        )

    def test_audit_fast_exists(self):
        """audit_fast.sh must exist."""
        script = REPO_ROOT / "tools" / "audit_fast.sh"
        assert script.exists(), "tools/audit_fast.sh missing"

    def test_audit_all_exists(self):
        """audit_all.sh must exist."""
        script = REPO_ROOT / "tools" / "audit_all.sh"
        assert script.exists(), "tools/audit_all.sh missing"


class TestLambdaCalculusGuardrails:
    """Verify lambda calculus guardrails are tested."""

    def test_lambda_guardrails_test_file_exists(self):
        """Lambda calculus guardrails test file must exist."""
        test_file = REPO_ROOT / "tests" / "structural" / "test_lambda_calculus_guardrails.py"
        assert test_file.exists(), (
            "tests/structural/test_lambda_calculus_guardrails.py missing"
        )

    def test_lambda_guardrails_has_tests(self):
        """Lambda guardrails file must have actual tests."""
        test_file = REPO_ROOT / "tests" / "structural" / "test_lambda_calculus_guardrails.py"
        content = test_file.read_text()
        # Count test functions
        test_count = content.count("def test_")
        assert test_count >= 5, (
            f"Lambda guardrails must have at least 5 tests, found {test_count}"
        )


class TestStepBudgetCoverage:
    """Verify step budget infrastructure is properly tested."""

    def test_step_budget_test_file_exists(self):
        """Step budget test file must exist."""
        test_file = REPO_ROOT / "tests" / "structural" / "test_step_budget.py"
        assert test_file.exists(), (
            "tests/structural/test_step_budget.py missing"
        )

    def test_step_budget_tests_no_deprecation(self):
        """Step budget tests must not trigger deprecation warnings."""
        test_file = REPO_ROOT / "tests" / "structural" / "test_step_budget.py"
        content = test_file.read_text()

        # Should NOT import Kernel or create_kernel
        assert "from rcx_pi.selfhost.kernel import Kernel" not in content, (
            "Step budget tests should not import deprecated Kernel class"
        )
        assert "create_kernel()" not in content, (
            "Step budget tests should not use deprecated create_kernel"
        )

        # Should use active step budget functions
        assert "get_step_budget" in content, (
            "Step budget tests must test get_step_budget"
        )
        assert "reset_step_budget" in content, (
            "Step budget tests must test reset_step_budget"
        )
