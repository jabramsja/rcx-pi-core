"""
Grounding tests for contraband.sh - verifies the script actually catches violations.

These tests create temporary files with known violations and verify contraband.sh
detects them. Without these tests, contraband.sh could have broken patterns and
we wouldn't know until a human manually tests them.

Created based on 7-agent review finding (2026-01-30): security checks had no grounding tests.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
CONTRABAND_SCRIPT = REPO_ROOT / "tools" / "contraband.sh"


def run_contraband_on_code(code: str) -> subprocess.CompletedProcess:
    """Write code to temp file and run contraband.sh on it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal package structure
        pkg_dir = Path(tmpdir) / "test_pkg"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        test_file = pkg_dir / "test_code.py"
        test_file.write_text(code)

        return subprocess.run(
            ["bash", str(CONTRABAND_SCRIPT), str(pkg_dir)],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )


class TestContrabanDetectsEval:
    """Verify contraband.sh catches eval() calls."""

    def test_detects_direct_eval(self):
        """contraband.sh must fail when eval() found."""
        code = 'result = eval("1 + 1")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on eval()"
        assert "eval" in result.stdout.lower()

    def test_allows_eval_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = 'result = eval("1 + 1")  # CONTRABAND_OK: test case'
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsExec:
    """Verify contraband.sh catches exec() calls."""

    def test_detects_direct_exec(self):
        """contraband.sh must fail when exec() found."""
        code = 'exec("print(1)")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on exec()"
        assert "exec" in result.stdout.lower()

    def test_allows_exec_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = 'exec("x = 1")  # CONTRABAND_OK: test case'
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsLambda:
    """Verify contraband.sh catches lambda expressions (not in sort keys)."""

    def test_detects_lambda_assignment(self):
        """contraband.sh must fail when lambda assigned to variable."""
        code = "fn = lambda x: x + 1"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on lambda assignment"
        assert "lambda" in result.stdout.lower()

    def test_allows_lambda_in_sort_key(self):
        """Lambda in sort key is allowed (idiomatic Python)."""
        code = "data.sort(key=lambda x: x.name)"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "Lambda in sort key should be allowed"

    def test_allows_lambda_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass lambda check."""
        code = "fn = lambda x: x  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestContrabanDetectsGlobals:
    """Verify contraband.sh catches globals()/locals() calls."""

    def test_detects_globals(self):
        """contraband.sh must fail when globals() found."""
        code = "g = globals()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on globals()"
        assert "globals" in result.stdout.lower()

    def test_detects_locals(self):
        """contraband.sh must fail when locals() found."""
        code = "l = locals()"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on locals()"
        assert "locals" in result.stdout.lower()


class TestContrabanDetectsDunders:
    """Verify contraband.sh catches dangerous dunder access."""

    def test_detects_class_dunder(self):
        """contraband.sh must fail when __class__ accessed."""
        code = "x.__class__.__bases__"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __class__"
        assert "__class__" in result.stdout or "dunder" in result.stdout.lower()

    def test_detects_mro_dunder(self):
        """contraband.sh must fail when __mro__ accessed."""
        code = "x.__class__.__mro__"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __mro__"


class TestContrabanDetectsPickle:
    """Verify contraband.sh catches pickle imports."""

    def test_detects_pickle_import(self):
        """contraband.sh must fail when pickle imported."""
        code = "import pickle"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on pickle import"
        assert "pickle" in result.stdout.lower()

    def test_detects_pickle_from_import(self):
        """contraband.sh must fail when from pickle import used."""
        code = "from pickle import loads"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from pickle import"


class TestContrabanDetectsCompile:
    """Verify contraband.sh catches compile() calls."""

    def test_detects_compile(self):
        """contraband.sh must fail when compile() found."""
        code = 'code = compile("x = 1", "<string>", "exec")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on compile()"
        assert "compile" in result.stdout.lower()

    def test_allows_re_compile(self):
        """re.compile() is allowed (regex, not code)."""
        code = "import re\npattern = re.compile(r'\\d+')"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "re.compile should be allowed"


class TestContrabanDetectsGetattrBuiltins:
    """Verify contraband.sh catches dynamic __builtins__ access."""

    def test_detects_getattr_builtins(self):
        """contraband.sh must fail when getattr(__builtins__) found."""
        code = 'fn = getattr(__builtins__, "eval")'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on getattr(__builtins__)"
        assert "__builtins__" in result.stdout

    def test_detects_builtins_subscript(self):
        """contraband.sh must fail when __builtins__[...] found."""
        code = 'fn = __builtins__["eval"]'
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on __builtins__[...]"


class TestContrabanDetectsImportBuiltins:
    """Verify contraband.sh catches import builtins (eval/exec bypass)."""

    def test_detects_import_builtins(self):
        """contraband.sh must fail when import builtins found."""
        code = "import builtins\nfn = builtins.eval"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on import builtins"
        assert "builtins" in result.stdout.lower()

    def test_detects_from_builtins_import(self):
        """contraband.sh must fail when from builtins import used."""
        code = "from builtins import eval as safe_eval"
        result = run_contraband_on_code(code)
        assert result.returncode != 0, "Should fail on from builtins import"

    def test_allows_import_builtins_with_contraband_ok(self):
        """CONTRABAND_OK comment must bypass check."""
        code = "import builtins  # CONTRABAND_OK: test case"
        result = run_contraband_on_code(code)
        assert result.returncode == 0, "CONTRABAND_OK should whitelist"


class TestCleanCodePasses:
    """Verify clean code passes contraband check."""

    def test_clean_code_passes(self):
        """Normal Python code should pass."""
        code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

result = add(1, 2)
'''
        result = run_contraband_on_code(code)
        assert result.returncode == 0, f"Clean code should pass: {result.stdout}"
