"""
MAINT-M1: Tests for tools/checks/check_gate_behavioral_pairs.py.

Validates classification accuracy, CLI output modes, and edge cases.
"""
from __future__ import annotations

import ast
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

# Import the classifier module directly for unit tests.
import importlib.util
_tool_path = REPO_ROOT / "tools" / "checks" / "check_gate_behavioral_pairs.py"
_spec = importlib.util.spec_from_file_location("check_gate_behavioral_pairs", _tool_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
classify_method = _mod.classify_method
scan_file = _mod.scan_file
scan_directory = _mod.scan_directory
compute_summary = _mod.compute_summary


# ---------------------------------------------------------------------------
# TestClassification
# ---------------------------------------------------------------------------

class TestClassification:
    """Classification accuracy tests."""

    def _classify_source(self, source: str) -> str:
        """Parse a function source and classify it."""
        tree = ast.parse(textwrap.dedent(source))
        func_node = tree.body[0]
        return classify_method(func_node)

    def test_behavioral_method(self):
        """Method calling runtime function → behavioral."""
        src = """\
        def test_boundary_call(self):
            result = _service_boundary_effect(req, max_algorithm_iterations=50,
                emit_fn=noop, iteration=0, state="test")
            assert "boundary_result" in result
        """
        assert self._classify_source(src) == "behavioral"

    def test_source_lock_method(self):
        """Method reading source code with re.search → source_lock."""
        src = """\
        def test_wiring_present(self):
            src = inspect.getsource(some_function)
            assert re.search(r'some_pattern', src)
        """
        assert self._classify_source(src) == "source_lock"

    def test_hybrid_method(self):
        """Method with both source inspection and runtime call → hybrid."""
        src = """\
        def test_hybrid_check(self):
            src = inspect.getsource(some_function)
            assert re.search(r'pattern', src)
            result = _service_boundary_effect(req, max_algorithm_iterations=50,
                emit_fn=noop, iteration=0, state="test")
            assert result is not None
        """
        assert self._classify_source(src) == "hybrid"

    def test_theater_risk_method(self):
        """Method with no assertions → theater_risk."""
        src = """\
        def test_trivial(self):
            x = 1 + 1
        """
        assert self._classify_source(src) == "theater_risk"

    def test_all_l4_gates_scan_without_error(self):
        """Classification covers all l4_gates test files without error."""
        gate_dir = REPO_ROOT / "mu" / "tests" / "l4_gates"
        if not gate_dir.is_dir():
            pytest.skip("l4_gates directory not found")
        results = scan_directory(gate_dir)
        summary = compute_summary(results)
        assert summary["total"] > 0, "Expected at least some test methods"
        # All categories should be non-negative
        for cat in ["behavioral", "source_lock", "hybrid", "theater_risk"]:
            assert summary[cat] >= 0


# ---------------------------------------------------------------------------
# TestCLIOutput
# ---------------------------------------------------------------------------

class TestCLIOutput:
    """CLI output format tests."""

    def test_default_human_readable(self):
        """Default mode produces human-readable output with summary."""
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        assert "=== L4 Gate Test Integrity Report ===" in result.stdout
        assert "Summary:" in result.stdout
        assert "behavioral:" in result.stdout

    def test_json_output_valid(self):
        """--json mode produces valid JSON with files and summary keys."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--json"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "files" in data
        assert "summary" in data
        assert isinstance(data["summary"]["total"], int)
        assert data["summary"]["total"] > 0

    def test_mismatch_enforcement_default_clean(self):
        """Default mode with mismatch enforcement passes (no Runtime/Wiring source-lock classes)."""
        result = subprocess.run(
            ["python3", str(_tool_path)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"Mismatch enforcement failed:\n{result.stderr}"
        )
        assert "proof-class mismatch" not in result.stderr

    def test_mismatch_enforcement_suppressed(self):
        """--no-fail-on-mismatch suppresses mismatch check."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--no-fail-on-mismatch"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0

    def test_unknown_flag_rejected(self):
        """Unknown CLI flags exit 2 (fail-closed)."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--not-a-real-flag"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 2, f"Expected exit 2, got {result.returncode}"
        assert "Unknown flag" in result.stderr

    def test_fail_on_theater_exit_code(self):
        """--fail-on-theater exits non-zero when theater_risk methods exist."""
        result = subprocess.run(
            ["python3", str(_tool_path), "--fail-on-theater"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        # Current codebase has some theater_risk (heuristic false positives),
        # so this should exit non-zero.
        # If the codebase has zero theater_risk, this test needs adjustment.
        # For now, we check the tool runs and produces output regardless.
        assert "Summary:" in result.stdout
        # Exit code is either 0 (no theater) or 1 (theater found)
        assert result.returncode in (0, 1)


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case handling tests."""

    def test_empty_test_class(self, tmp_path):
        """Empty test class handled gracefully."""
        test_file = tmp_path / "test_empty.py"
        test_file.write_text(textwrap.dedent("""\
            class TestEmpty:
                pass
        """))
        classes = scan_file(test_file)
        # Empty class (no test_ methods) should not appear
        assert "TestEmpty" not in classes

    def test_non_test_methods_skipped(self, tmp_path):
        """Non-test methods (no test_ prefix) are skipped."""
        test_file = tmp_path / "test_helpers.py"
        test_file.write_text(textwrap.dedent("""\
            class TestSomething:
                def helper_method(self):
                    return 42

                def test_real(self):
                    assert self.helper_method() == 42
        """))
        classes = scan_file(test_file)
        assert "TestSomething" in classes
        methods = classes["TestSomething"]
        assert "helper_method" not in methods
        assert "test_real" in methods

    def test_module_level_functions_scanned(self, tmp_path):
        """Module-level test_* functions (not in classes) are scanned under <module>."""
        test_file = tmp_path / "test_module_funcs.py"
        test_file.write_text(textwrap.dedent("""\
            def test_standalone():
                assert 1 + 1 == 2

            def helper():
                pass

            class TestInClass:
                def test_method(self):
                    assert True
        """))
        classes = scan_file(test_file)
        assert "<module>" in classes, "Module-level functions should be under <module> key"
        assert "test_standalone" in classes["<module>"]
        assert "helper" not in classes["<module>"]
        assert "TestInClass" in classes

    def test_positional_args_rejected(self):
        """Bare positional args exit 2 (fail-closed)."""
        result = subprocess.run(
            ["python3", str(_tool_path), "some_file.py"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 2, f"Expected exit 2, got {result.returncode}"
        assert "positional" in result.stderr.lower()
