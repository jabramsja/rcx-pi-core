"""
Grounding tests for check_test_theater.sh - verifies the script catches vacuous assertions.

These tests create temporary test files with known theater patterns and verify
check_test_theater.sh detects them. Without these tests, the theater check could
have broken patterns and we wouldn't know.

Created based on 7-agent review finding (2026-01-30): security checks had no grounding tests.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest


from tests.repo_root import REPO_ROOT
THEATER_SCRIPT = REPO_ROOT / "tools" / "checks" / "check_test_theater.sh"


def run_theater_check_on_code(code: str) -> subprocess.CompletedProcess:
    """Write code to temp test file and run check_test_theater.sh on it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_example.py"
        test_file.write_text(code)

        return subprocess.run(
            ["bash", str(THEATER_SCRIPT), tmpdir],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )


class TestTheaterDetectsAssertTrue:
    """Verify check_test_theater.sh catches vacuous 'assert True'."""

    def test_detects_bare_assert_true(self):
        """check_test_theater.sh must fail when bare 'assert True' found."""
        # Build test code with "assert True" split to avoid grep matching THIS file
        # Note: need trailing newline for grep to match end-of-line pattern
        code = "\n".join([
            "def test_something():",
            "    # This is theater - verifies nothing",
            "    assert " + "True",  # THEATER_OK: test data, not actual assertion
            "",  # Trailing newline ensures grep sees end-of-line
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on bare assert True"
        assert "assert" in result.stdout.lower() or "theater" in result.stdout.lower()

    def test_detects_assert_true_with_comment(self):
        """check_test_theater.sh must fail when vacuous assertion with comment found."""
        # Build test code with "assert True" split to avoid grep matching THIS file
        code = "\n".join([
            "def test_something():",
            "    assert " + "True  # TODO: add real assertion",  # THEATER_OK: test data
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on vacuous assertion with comment"


class TestTheaterAllowsLegitimatePatterns:
    """Verify check_test_theater.sh allows legitimate assert True patterns."""

    def test_allows_assert_true_equals(self):
        """'assert True == 1' is legitimate (tests type coercion)."""
        code = """
def test_type_coercion():
    assert True == 1  # Tests Python's type coercion
"""
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "'assert True ==' should be allowed"

    def test_allows_assert_true_is(self):
        """'assert True is True' is legitimate."""
        code = """
def test_identity():
    assert True is True
"""
        result = run_theater_check_on_code(code)
        # 'is True' doesn't match the bare 'assert True' pattern
        assert result.returncode == 0, "'assert True is True' should be allowed"

    def test_allows_theater_ok_whitelist(self):
        """THEATER_OK comment must bypass check."""
        code = """
def test_something():
    assert True  # THEATER_OK: placeholder for future assertion
"""
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "THEATER_OK should whitelist"


class TestTheaterCleanTests:
    """Verify clean tests pass the theater check."""

    def test_meaningful_assertions_pass(self):
        """Tests with meaningful assertions should pass."""
        code = """
def test_addition():
    result = 1 + 1
    assert result == 2

def test_type():
    data = {"key": "value"}
    assert isinstance(data, dict)
    assert "key" in data

def test_not_none():
    result = some_function()
    assert result is not None
"""
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, f"Clean tests should pass: {result.stdout}"

    def test_empty_file_passes(self):
        """Empty test file should pass (no theater)."""
        code = ""
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "Empty file should pass"


class TestTheaterDetectsTautologies:
    """Verify check_test_theater.sh catches tautological assertions."""

    def test_detects_assertTrue_True(self):
        """assertTrue(True) is always true - theater."""  # THEATER_OK: docstring
        # Use concatenation so THEATER_OK is on same line as pattern
        code = "\n".join([
            "def test_something():",
            "    self.assertTrue(True)",  # THEATER_OK: test data
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on assertTrue(True)"  # THEATER_OK: docstring
        assert "tautology" in result.stdout.lower() or "theater" in result.stdout.lower()

    def test_detects_assertEqual_True_True(self):
        """assertEqual(True, True) is always true - theater."""  # THEATER_OK: docstring
        code = "\n".join([
            "def test_something():",
            "    self.assertEqual(True, True)",  # THEATER_OK: test data
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on assertEqual(True, True)"  # THEATER_OK: docstring

    def test_detects_assertEqual_1_1(self):
        """assertEqual(1, 1) is always true - theater."""  # THEATER_OK: docstring
        code = "\n".join([
            "def test_something():",
            "    self.assertEqual(1, 1)",  # THEATER_OK: test data
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on assertEqual(1, 1)"  # THEATER_OK: docstring


class TestTheaterDetectsEmptyTests:
    """Verify check_test_theater.sh catches empty test bodies."""

    def test_detects_pass_body(self):
        """def test_foo(): pass is theater."""
        code = "def test_something(): pass\n"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on empty test body with pass"

    def test_detects_ellipsis_body(self):
        """def test_foo(): ... is theater."""
        code = "def test_something(): ...\n"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on empty test body with ellipsis"


class TestTheaterDetectsSkipWithoutReason:
    """Verify check_test_theater.sh catches skip decorators without reasons."""

    def test_detects_pytest_skip_bare(self):
        """@pytest.mark.skip without reason is theater."""  # THEATER_OK: docstring
        code = "\n".join([
            "@pytest.mark.skip",  # THEATER_OK: test data
            "def test_something():",
            "    x = 1",
            "    assert x == 1",
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on @pytest.mark.skip without reason"  # THEATER_OK: docstring

    def test_detects_pytest_skip_empty_parens(self):
        """@pytest.mark.skip() without reason is theater."""  # THEATER_OK: docstring
        code = "\n".join([
            "@pytest.mark.skip()",  # THEATER_OK: test data
            "def test_something():",
            "    x = 1",
            "    assert x == 1",
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on @pytest.mark.skip() without reason"  # THEATER_OK: docstring

    def test_allows_pytest_skip_with_reason(self):
        """@pytest.mark.skip(reason='...') is legitimate."""
        code = "\n".join([
            '@pytest.mark.skip(reason="Known bug, see issue #123")',
            "def test_something():",
            "    result = compute()",
            "    assert result == expected",
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "Should allow @pytest.mark.skip with reason"


class TestTheaterDetectsCommentedAssertions:
    """Verify check_test_theater.sh catches commented-out assertions."""

    def test_detects_commented_assert(self):
        """Commented-out assertion is theater."""
        code = "\n".join([
            "def test_something():",
            "    result = do_thing()",
            "    # assert result == expected",  # THEATER_OK: test data
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on commented-out assertion"

    def test_detects_commented_self_assert(self):
        """Commented-out self.assert is theater."""  # THEATER_OK: docstring
        code = "\n".join([
            "def test_something():",
            "    result = do_thing()",
            "    # self.assertEqual(result, expected)",  # THEATER_OK: test data
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on commented-out self.assert"  # THEATER_OK: docstring
