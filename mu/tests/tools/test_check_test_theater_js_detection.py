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


class TestTheaterDefaultDirectoryScan:
    """P2 regression lock: no-arg invocation must scan mu/host/js/ directory."""

    def test_no_arg_scans_directory_not_single_file(self):
        """No-arg default must scan mu/host/js/ (all files), not eval_step.js alone."""
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Default scan should pass: {result.stdout}"
        # Must report scanning multiple files, not just 1
        assert "mu/host/js/" in result.stdout, "Should report scanning mu/host/js/ directory"
        import re
        m = re.search(r"(\d+) JS file\(s\)", result.stdout)
        assert m, f"Should report file count in output: {result.stdout}"
        file_count = int(m.group(1))
        assert file_count > 1, f"Must scan >1 file (got {file_count}), not just eval_step.js shim"

    def test_default_target_is_mu_host_js(self):
        """Script source must default to mu/host/js/, not eval_step.js."""
        script_text = SCRIPT.read_text()
        assert 'TARGET="${1:-mu/host/js/}"' in script_text, (
            "Default TARGET must be mu/host/js/ directory"
        )
        # Must NOT default to the old single-file target
        assert 'JS_FILE="${1:-mu/host/js/eval_step.js}"' not in script_text, (
            "Must not default to eval_step.js (old single-file behavior)"
        )

    def test_directory_mode_catches_theater_in_subdir(self):
        """Directory scan must catch theater in nested files, not just top-level."""
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "nested")
            os.makedirs(subdir)
            # Clean file at top level
            with open(os.path.join(tmpdir, "clean.js"), "w") as f:
                f.write("assert(result === 42);\n")
            # Theater in nested file
            with open(os.path.join(subdir, "bad.js"), "w") as f:
                f.write("assert(true);\n")
            result = subprocess.run(
                ["bash", str(SCRIPT), tmpdir],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            assert result.returncode != 0, "Should catch theater in nested subdir"
            assert "2 JS file(s)" in result.stdout, "Should scan both files"


class TestTheaterOkSuppression:
    """P2 regression lock: THEATER_OK marker suppression semantics."""

    def test_theater_ok_suppresses_same_line(self):
        """THEATER_OK on same line must suppress that match."""
        code = "assert(true); // THEATER_OK: intentional vacuous check for test harness\n"
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, (
            f"THEATER_OK on same line should suppress: {result.stdout}"
        )

    def test_theater_ok_does_not_suppress_different_line(self):
        """THEATER_OK on line N must NOT suppress theater on line N+1."""
        code = "// THEATER_OK: this marker is on the wrong line\nassert(true);\n"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, (
            "THEATER_OK on different line must NOT suppress theater"
        )

    def test_theater_ok_in_directory_mode(self):
        """THEATER_OK suppression must work in directory scan mode too."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # File with suppressed theater
            with open(Path(tmpdir) / "suppressed.js", "w") as f:
                f.write("assert(true); // THEATER_OK: intentional\n")
            result = subprocess.run(
                ["bash", str(SCRIPT), tmpdir],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            assert result.returncode == 0, (
                f"THEATER_OK should suppress in directory mode: {result.stdout}"
            )

    def test_theater_ok_marker_must_appear_in_script(self):
        """Script source must reference THEATER_OK as its suppression marker."""
        script_text = SCRIPT.read_text()
        assert "THEATER_OK" in script_text, (
            "Script must support THEATER_OK suppression marker"
        )
