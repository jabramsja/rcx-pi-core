"""
Grounding tests for check_test_theater_js.sh - verifies test theater detection works.

These tests create temporary JS files with known theater patterns and verify
check_test_theater_js.sh detects them. Without these tests, the script could miss
vacuous assertions and fake tests.

Created based on grounding agent finding (2026-01-30): check_test_theater_js.sh at 0% grounded.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT
SCRIPT = REPO_ROOT / "tools" / "checks" / "check_test_theater_js.sh"


def run_theater_check_on_code(code: str) -> subprocess.CompletedProcess:
    """Write JS code to temp file and run check_test_theater_js.sh on it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False) as f:
        f.write(code)
        f.flush()
        return subprocess.run(
            ["bash", str(SCRIPT), f.name],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )


class TestTheaterDetectsVacuousAssertions:
    """Verify check_test_theater_js.sh catches vacuous assertions."""

    def test_detects_assert_true(self):
        """check_test_theater_js.sh must fail when assert(true) found."""
        code = "assert(true);"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on assert(true)"
        assert "vacuous" in result.stdout.lower() or "true" in result.stdout.lower()

    def test_detects_assert_1(self):
        """check_test_theater_js.sh must fail when assert(1) found."""
        code = "assert(1);"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on assert(1)"

    def test_detects_assert_not_false(self):
        """check_test_theater_js.sh must fail when assert(!false) found."""
        code = "assert(!false);"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on assert(!false)"

    def test_detects_assert_not_0(self):
        """check_test_theater_js.sh must fail when assert(!0) found."""
        code = "assert(!0);"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on assert(!0)"

    def test_detects_console_assert_true(self):
        """check_test_theater_js.sh must fail when console.assert(true) found."""
        code = "console.assert(true, 'always passes');"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on console.assert(true)"


class TestTheaterDetectsSelfComparison:
    """Verify check_test_theater_js.sh catches self-comparison assertions."""

    def test_detects_self_comparison_strict_equality(self):
        """check_test_theater_js.sh must fail when comparing variable to itself."""
        code = "assert(x === x);"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on self-comparison"


class TestTheaterDetectsEmptyTests:
    """Verify check_test_theater_js.sh catches empty test bodies."""

    def test_detects_empty_test_function(self):
        """check_test_theater_js.sh must fail when empty test function found."""
        code = "function testSomething() {}"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on empty test function"

    def test_detects_empty_arrow_function(self):
        """check_test_theater_js.sh must fail when empty arrow function found."""
        code = "const test = () => {};"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on empty arrow function"


class TestTheaterDetectsCommentedAssertions:
    """Verify check_test_theater_js.sh catches commented-out assertions."""

    def test_detects_commented_assert(self):
        """check_test_theater_js.sh must fail when // assert found."""
        code = "// assert(result === expected);"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on commented assert"

    def test_detects_commented_expect(self):
        """check_test_theater_js.sh must fail when // expect found."""
        code = "// expect(result).toBe(expected);"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on commented expect"


class TestTheaterDetectsTodoPlaceholders:
    """Verify check_test_theater_js.sh catches TODO test placeholders."""

    def test_detects_todo_test(self):
        """check_test_theater_js.sh must fail when TODO test found."""
        code = "// TODO: add test for edge case"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on TODO test"

    def test_detects_fixme_test(self):
        """check_test_theater_js.sh must fail when FIXME test found."""
        code = "// FIXME: test is broken"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on FIXME test"


class TestTheaterDetectsPassComments:
    """Verify check_test_theater_js.sh catches pass/works comments."""

    def test_detects_pass_comment(self):
        """check_test_theater_js.sh must fail when // pass found."""
        code = "// pass"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on // pass comment"

    def test_detects_works_comment(self):
        """check_test_theater_js.sh must fail when // works found."""
        code = "// works"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on // works comment"


class TestTheaterCleanCode:
    """Verify clean test code passes check_test_theater_js.sh."""

    def test_real_assertion_passes(self):
        """Real assertions with actual comparisons should pass."""
        code = '''
function testAddition() {
    const result = add(1, 2);
    assert(result === 3);
}

function testMultiplication() {
    const result = multiply(2, 3);
    assert(result === 6, "2 * 3 should equal 6");
}
'''
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, f"Real assertions should pass: {result.stdout}"

    def test_structural_equality_passes(self):
        """Structural equality tests should pass."""
        code = '''
function testDeepEqual() {
    const a = {x: 1, y: 2};
    const b = {x: 1, y: 2};
    assert(muEqual(a, b));
}
'''
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, f"Structural equality should pass: {result.stdout}"
