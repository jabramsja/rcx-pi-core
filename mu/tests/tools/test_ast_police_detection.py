"""
Grounding tests for ast_police.py - verifies the script actually catches violations.

These tests create temporary files with known violations and verify ast_police.py
detects them. Without these tests, ast_police.py could have broken patterns and
we wouldn't know until a human manually tests them.

Created based on 7-agent review finding (2026-01-30): security checks had no grounding tests.
"""
import subprocess
import tempfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent.parent
AST_POLICE_SCRIPT = REPO_ROOT / "tools" / "checks" / "ast_police.py"


def run_ast_police_on_code(code: str) -> subprocess.CompletedProcess:
    """Write code to temp file and run ast_police.py on it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        f.flush()
        filepath = f.name

    try:
        return subprocess.run(
            ["python3", str(AST_POLICE_SCRIPT), filepath],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    finally:
        Path(filepath).unlink()


class TestAstPoliceDetectsSetLiteral:
    """Verify ast_police.py catches set literals (non-determinism)."""

    def test_detects_set_literal(self):
        """ast_police.py must fail when unapproved set literal found."""
        code = "x = {1, 2, 3}"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on set literal"
        assert "Set literal" in result.stdout or "set" in result.stdout.lower()

    def test_allows_approved_set_literal(self):
        """Approved set literals for key comparison should pass."""
        code = 'if keys == {"head", "tail"}: pass'
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, "Approved set {'head', 'tail'} should pass"


class TestAstPoliceDetectsSetComprehension:
    """Verify ast_police.py catches set comprehensions."""

    def test_detects_set_comprehension(self):
        """ast_police.py must fail when set comprehension found."""
        code = "x = {i for i in range(10)}"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on set comprehension"
        assert "comprehension" in result.stdout.lower() or "set" in result.stdout.lower()


class TestAstPoliceDetectsListComprehension:
    """Verify ast_police.py catches list comprehensions (unless marked)."""

    def test_detects_list_comprehension(self):
        """ast_police.py must fail when unmarked list comprehension found."""
        code = "x = [i for i in range(10)]"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on list comprehension"
        assert "List comprehension" in result.stdout or "comprehension" in result.stdout.lower()

    def test_allows_marked_list_comprehension(self):
        """AST_OK marker must bypass list comprehension check."""
        code = "x = [i for i in range(10)]  # AST_OK: bootstrap - test case"
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, "AST_OK: bootstrap should whitelist"


class TestAstPoliceDetectsDictComprehension:
    """Verify ast_police.py catches dict comprehensions (unless marked)."""

    def test_detects_dict_comprehension(self):
        """ast_police.py must fail when unmarked dict comprehension found."""
        code = "x = {i: i*2 for i in range(10)}"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on dict comprehension"
        assert "Dict comprehension" in result.stdout or "comprehension" in result.stdout.lower()

    def test_allows_marked_dict_comprehension(self):
        """AST_OK marker must bypass dict comprehension check."""
        code = "x = {k: v for k, v in items}  # AST_OK: infra - boundary conversion"
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, "AST_OK: infra should whitelist"


class TestAstPoliceDetectsLambda:
    """Verify ast_police.py catches lambda expressions."""

    def test_detects_lambda(self):
        """ast_police.py must fail when lambda found."""
        code = "fn = lambda x: x + 1"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on lambda"
        assert "lambda" in result.stdout.lower()

    def test_detects_multiline_lambda(self):
        """ast_police.py catches multiline lambda (grep can miss these)."""
        code = """fn = (
    lambda x: x + 1
)"""
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on multiline lambda"


class TestAstPoliceDetectsWalrus:
    """Verify ast_police.py catches walrus operator."""

    def test_detects_walrus(self):
        """ast_police.py must fail when := found."""
        code = "if (n := len(data)) > 0: print(n)"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on walrus operator"
        assert "walrus" in result.stdout.lower() or ":=" in result.stdout


class TestAstPoliceDetectsYield:
    """Verify ast_police.py catches yield/yield from."""

    def test_detects_yield(self):
        """ast_police.py must fail when yield found."""
        code = """
def gen():
    yield 1
"""
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on yield"
        assert "yield" in result.stdout.lower()

    def test_detects_yield_from(self):
        """ast_police.py must fail when yield from found."""
        code = """
def gen():
    yield from range(10)
"""
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on yield from"


class TestAstPoliceDetectsAsync:
    """Verify ast_police.py catches async constructs."""

    def test_detects_async_def(self):
        """ast_police.py must fail when async def found."""
        code = """
async def fetch():
    pass
"""
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on async def"
        assert "async" in result.stdout.lower()


class TestAstPoliceDetectsDangerousBuiltins:
    """Verify ast_police.py catches dangerous builtin calls."""

    def test_detects_eval_call(self):
        """ast_police.py must fail when eval() called."""
        code = 'result = eval("1 + 1")'
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on eval()"
        assert "Dangerous builtin" in result.stdout or "eval" in result.stdout.lower()

    def test_detects_exec_call(self):
        """ast_police.py must fail when exec() called."""
        code = 'exec("x = 1")'
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on exec()"


class TestAstOkCategoryValidation:
    """Verify AST_OK markers must use approved categories."""

    def test_rejects_invalid_category(self):
        """AST_OK with invalid category must fail."""
        code = "x = [i for i in data]  # AST_OK: fake_reason"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on invalid AST_OK category"
        assert "Invalid AST_OK" in result.stdout or "invalid" in result.stdout.lower()

    def test_accepts_bootstrap_category(self):
        """AST_OK: bootstrap is a valid category."""
        code = "x = [i for i in data]  # AST_OK: bootstrap - eval_seed comprehension"
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, "AST_OK: bootstrap should be accepted"

    def test_accepts_infra_category(self):
        """AST_OK: infra is a valid category."""
        code = "x = [i for i in data]  # AST_OK: infra - boundary scaffolding"
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, "AST_OK: infra should be accepted"

    def test_accepts_boundary_category(self):
        """AST_OK: boundary is a valid category."""
        code = "x = [i for i in data]  # AST_OK: boundary - host conversion"
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, "AST_OK: boundary should be accepted"

    def test_accepts_test_category(self):
        """AST_OK: test is a valid category."""
        code = "x = [i for i in data]  # AST_OK: test - test helper"
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, "AST_OK: test should be accepted"

    def test_accepts_cycle_category(self):
        """AST_OK: cycle is a valid category."""
        code = "seen = {id(x)}  # AST_OK: cycle - cycle detection"
        result = run_ast_police_on_code(code)
        # Single element sets are allowed for cycle detection anyway
        assert result.returncode == 0


class TestAstPoliceHandlesEdgeCases:
    """Verify ast_police.py handles edge cases correctly."""

    def test_handles_syntax_error(self):
        """ast_police.py should report syntax errors."""
        code = "def broken(:"
        result = run_ast_police_on_code(code)
        assert result.returncode != 0, "Should fail on syntax error"
        assert "Syntax Error" in result.stdout or "syntax" in result.stdout.lower()

    def test_clean_code_passes(self):
        """Normal Python code should pass."""
        code = '''
def add(a, b):
    """Add two numbers."""
    return a + b

result = add(1, 2)
'''
        result = run_ast_police_on_code(code)
        assert result.returncode == 0, f"Clean code should pass: {result.stdout}"
