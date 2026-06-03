"""
Grounding tests for check_test_theater.sh - verifies the script catches vacuous assertions.

These tests create temporary test files with known theater patterns and verify
check_test_theater.sh detects them. Without these tests, the theater check could
have broken patterns and we wouldn't know.

Created based on 7-agent review finding (2026-01-30): security checks had no grounding tests.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


from tests.repo_root import REPO_ROOT
THEATER_SCRIPT = REPO_ROOT / "tools" / "checks" / "check_test_theater.sh"
THEATER_LINTER = REPO_ROOT / "tools" / "checks" / "linters" / "check_test_theater.py"


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

    def test_detects_multiline_pass_body(self):
        """F-07: def test_foo():\\n    pass is theater (multiline)."""
        code = "def test_something():\n    pass\n"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on multiline empty test body with pass"

    def test_detects_multiline_ellipsis_body(self):
        """F-07: def test_foo():\\n    ... is theater (multiline)."""
        code = "def test_something():\n    ...\n"
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on multiline empty test body with ellipsis"

    def test_detects_multiline_docstring_plus_pass(self):
        """F-07: def test_foo():\\n    '''doc'''\\n    pass is theater."""
        code = 'def test_something():\n    """Docstring."""\n    pass\n'
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "Should fail on docstring-only + pass test"

    def test_multiline_empty_with_theater_ok_on_def_line_passes(self):
        """F-07: THEATER_OK on def line whitelists multiline empty test."""
        code = "def test_something():  # THEATER_OK: placeholder\n    pass\n"
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "THEATER_OK on def line should whitelist"

    def test_multiline_empty_with_theater_ok_preceding_line_passes(self):
        """F-07: THEATER_OK on immediately preceding line whitelists."""
        code = "# THEATER_OK: placeholder for future\ndef test_something():\n    pass\n"
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "THEATER_OK on preceding line should whitelist"

    def test_real_test_body_not_flagged(self):
        """F-07: Test with real assertions is not flagged by multiline check."""
        code = "def test_something():\n    result = 1 + 1\n    assert result == 2\n"
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "Real test body should not be flagged"


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


def _run_linter_directly(scan_dir: str) -> subprocess.CompletedProcess:
    """Invoke the AST linter EXACTLY as check_test_theater.sh invokes it.

    argv[1] is the directory scanned DIRECTLY (walked recursively for
    ``*.py``), NOT a root under which ``tests/`` + ``mu/tests/`` are
    re-discovered. This mirrors the wrapper's
    ``python3 .../check_test_theater.py "$TESTS_DIR"`` call.
    """
    return subprocess.run(
        ["python3", str(THEATER_LINTER), scan_dir],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


class TestAstLinterVacuousAssertionsAndFailClosed:
    """Regression for the AST-ified vacuous-assertion check
    (wave check-test-theater-ast-2026-06-03).

    The six TEXT-based vacuous-assertion greps in check_test_theater.sh were
    replaced by an AST linter (tools/checks/linters/check_test_theater.py)
    wired FAIL-CLOSED. These pin the six packet behaviors:
      (a) a vacuous assertion inside a fixture STRING is clean (BUG #1);
      (b) a real vacuous assertion is flagged;
      (c) a trailing THEATER_OK whitelists it;
      (d) a linter execution failure (exit >=2) FAILS the gate (BUG #2),
          proven for both the real linter and a silent (no-stdout) failure;
      (e) the linter scans the passed directory directly + recursively (BUG #3);
      (f) a target with zero *.py files fails closed (BUG #3 belt-and-suspenders).
    """

    def test_a_vacuous_assertion_inside_fixture_string_is_clean(self):
        # The vacuous assertion lives ONLY inside a textwrap.dedent fixture
        # string (the PR #1065 false positive). The AST linter ignores string
        # contents, so the gate stays CLEAN with NO THEATER_OK -- the point of
        # the wave. (The token is split in THIS source so the generated fixture
        # holds it verbatim while this file does not.)
        code = "\n".join([
            "import textwrap",
            "",
            "def test_classifier_handles_vacuous_fixture():",
            "    fixture = textwrap.dedent('''",
            "        def test_inner():",
            "            " + "assert " + "True",
            "    ''')",
            "    assert 'test_inner' in fixture",
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, (
            "vacuous assertion inside a fixture string must be CLEAN "
            f"(BUG #1); gate output:\n{result.stdout}"
        )

    def test_b_real_vacuous_assertion_is_flagged(self):
        # A real (top-level) vacuous assertion -- not inside a string -- is
        # flagged. Token split + THEATER_OK keep THIS source clean; the
        # generated file gets the bare statement with no whitelist.
        code = "\n".join([
            "def test_something():",
            "    " + "assert " + "True",  # THEATER_OK: generated fixture, not a real assertion
            "",
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode != 0, "a real vacuous assertion must be flagged"
        assert "theater" in result.stdout.lower()

    def test_c_trailing_theater_ok_is_skipped(self):
        # A trailing THEATER_OK on the offending line whitelists it.
        code = "\n".join([
            "def test_something():",
            "    assert True  # THEATER_OK: placeholder for future assertion",
            "",
        ])
        result = run_theater_check_on_code(code)
        assert result.returncode == 0, "trailing THEATER_OK must whitelist the assertion"

    def test_d_gate_fails_closed_when_real_linter_cannot_scan(self, tmp_path):
        # BUG #2 (real integration): an unparseable target makes the REAL
        # linter exit >=2 (could-not-scan), and the REAL wrapper must turn that
        # into a gate FAILURE -- a scan failure must never silently pass.
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "test_broken.py").write_text("def test_x(:\n    pass\n")
        result = subprocess.run(
            ["bash", str(THEATER_SCRIPT), str(bad_dir)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode != 0, (
            "gate must FAIL CLOSED when the linter cannot scan a file "
            f"(BUG #2); got rc=0:\n{result.stdout}"
        )

    def test_d2_gate_fails_closed_on_silent_linter_failure(self, tmp_path):
        # BUG #2 (the exact fail-open): a linter that prints NOTHING to stdout
        # and exits >=2 (syntax/import/runtime failure) must STILL fail the
        # gate. The naive `out=$(... || true)` + stdout-presence design would
        # have swallowed this. A copy of the REAL wrapper is exercised against a
        # stub linter so the wrapper's own fail-closed wiring is under test.
        wrapper = tmp_path / "check_test_theater.sh"
        shutil.copy(THEATER_SCRIPT, wrapper)
        (tmp_path / "linters").mkdir()
        (tmp_path / "linters" / "check_test_theater.py").write_text(
            "import sys\nsys.exit(2)\n"  # prints nothing; exits >=2
        )
        scan_dir = tmp_path / "scan"
        scan_dir.mkdir()
        (scan_dir / "test_clean.py").write_text(
            "def test_ok():\n    value = 1 + 1\n    assert value == 2\n"
        )
        result = subprocess.run(
            ["bash", str(wrapper), str(scan_dir)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert result.returncode != 0, (
            "gate must FAIL CLOSED when the linter exits >=2 while printing "
            f"nothing (BUG #2); got rc=0:\n{result.stdout}"
        )

    def test_e_linter_scans_passed_dir_directly_and_recursively(self, tmp_path):
        # SCAN-COVERAGE (BUG #3): invoked as the wrapper invokes it
        # (argv[1] = scan dir), the linter flags a real vacuous assertion
        # living in a NON-"tests" subdir UNDER that dir. A linter that
        # re-discovered tests/+mu/tests/ below argv[1] would find nothing in
        # pkg/; rc==1 proves it scans the passed dir directly and recursively.
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "test_deep.py").write_text(
            "def test_deep():\n    " + "assert " + "True\n"
        )
        result = _run_linter_directly(str(tmp_path))
        assert result.returncode == 1, (
            "linter must flag the vacuous assertion under the passed dir "
            f"(rc==1, proving direct recursive scan); got rc={result.returncode}, "
            f"stdout={result.stdout!r} stderr={result.stderr!r}"
        )
        assert "test_deep.py" in result.stdout

    def test_f_linter_fails_closed_on_zero_python_files(self, tmp_path):
        # ZERO-FILES (BUG #3 belt-and-suspenders): a target resolving to zero
        # *.py files is an EXECUTION ERROR (exit >=2) -- scanning nothing FAILS
        # closed, never exit 0.
        (tmp_path / "notes.txt").write_text("no python here\n")
        result = _run_linter_directly(str(tmp_path))
        assert result.returncode >= 2, (
            "linter must fail closed (exit >=2) on zero *.py files; "
            f"got rc={result.returncode}"
        )
