"""
Gate test: Normalize/Denormalize Iterative Conversion (A21a)

Enforces:
1. JS normalize() and denormalize() have no @host_recursion markers
2. JS normalize() and denormalize() have no recursive self-calls in body
3. Behavioral preservation: roundtrip, cycle detection, full JS suite
4. Ratchet evidence: JS host_recursion <= 3
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

NORMALIZE_JS = REPO_ROOT / "mu" / "host" / "js" / "core" / "normalize.js"
RATCHET_TOOL = REPO_ROOT / "tools" / "checks" / "check_host_semantics_ratchet.py"


def _extract_function_body(source: str, func_name: str) -> str:
    """Extract the body of a named JS function (from declaration to next top-level function or EOF).

    Uses 'function <name>(' as the start marker and the next top-level
    'function ' declaration (or EOF) as the end boundary. This prevents
    false positives from calls to the function elsewhere in the file
    (e.g., normalizeProjection calling normalize).
    """
    pattern = re.compile(rf'^function {re.escape(func_name)}\(', re.MULTILINE)
    match = pattern.search(source)
    if not match:
        pytest.fail(f"Could not find 'function {func_name}(' in source")
    start = match.start()

    # Find next top-level function declaration after the start
    next_func = re.compile(r'^function \w+\(', re.MULTILINE)
    rest = source[match.end():]
    next_match = next_func.search(rest)
    if next_match:
        end = match.end() + next_match.start()
    else:
        end = len(source)

    return source[start:end]


def _extract_docblock_above(source: str, func_name: str) -> str:
    """Extract the JSDoc comment block above a function declaration."""
    pattern = re.compile(
        rf'(/\*\*.*?\*/)\s*\nfunction {re.escape(func_name)}\(',
        re.DOTALL
    )
    match = pattern.search(source)
    if not match:
        pytest.fail(f"Could not find docblock above 'function {func_name}('")
    return match.group(1)


# ---------------------------------------------------------------------------
# TestRecursionRemoved — source locks
# ---------------------------------------------------------------------------

class TestRecursionRemoved:
    """Verify normalize/denormalize no longer carry @host_recursion markers
    and contain no recursive self-calls."""

    def test_js_normalize_no_host_recursion_marker(self):
        source = NORMALIZE_JS.read_text()
        docblock = _extract_docblock_above(source, "normalize")
        assert "@host_recursion" not in docblock, (
            "normalize() docblock still contains @host_recursion"
        )

    def test_js_denormalize_no_host_recursion_marker(self):
        source = NORMALIZE_JS.read_text()
        docblock = _extract_docblock_above(source, "denormalize")
        assert "@host_recursion" not in docblock, (
            "denormalize() docblock still contains @host_recursion"
        )

    def test_js_normalize_no_recursive_self_call(self):
        """No normalize( call within normalize's function body.

        _extract_function_body scopes to just the normalize function
        (stops at next 'function ' declaration), so normalizeProjection's
        calls to normalize() won't cause false positives.
        """
        source = NORMALIZE_JS.read_text()
        body = _extract_function_body(source, "normalize")
        # Remove the function declaration line itself (contains 'normalize(')
        lines = body.split("\n")[1:]
        body_without_decl = "\n".join(lines)
        assert not re.search(r'\bnormalize\s*\(', body_without_decl), (
            "normalize() body still contains recursive self-call"
        )

    def test_js_denormalize_no_recursive_self_call(self):
        """No denormalize( call within denormalize's function body."""
        source = NORMALIZE_JS.read_text()
        body = _extract_function_body(source, "denormalize")
        lines = body.split("\n")[1:]
        body_without_decl = "\n".join(lines)
        assert not re.search(r'\bdenormalize\s*\(', body_without_decl), (
            "denormalize() body still contains recursive self-call"
        )


# ---------------------------------------------------------------------------
# TestBehaviorPreserved — behavioral via subprocess
# ---------------------------------------------------------------------------

class TestBehaviorPreserved:
    """Verify iterative normalize/denormalize preserves all behavior."""

    def test_js_normalize_roundtrip(self):
        """Roundtrip normalize->denormalize for representative values."""
        js_code = """
        const { normalize, denormalize } = require('./mu/host/js/core/normalize');
        const cases = [
            [],
            {},
            [1, 2, 3],
            {"a": 1, "b": 2},
            [[1, 2], {"x": "y"}],
            {"nested": {"deep": [1, 2, 3]}},
            {"var": "x"},
            [{"var": "n"}, 42, "hello", true, null],
        ];
        let allPass = true;
        for (const c of cases) {
            const n = normalize(c);
            const d = denormalize(n);
            if (JSON.stringify(d) !== JSON.stringify(c)) {
                console.error('FAIL:', JSON.stringify(c), '->', JSON.stringify(d));
                allPass = false;
            }
        }
        if (allPass) {
            console.log('ROUNDTRIP_PASS');
        } else {
            process.exit(1);
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Roundtrip failed:\n{result.stderr}"
        assert "ROUNDTRIP_PASS" in result.stdout

    def test_js_normalize_cycle_detection(self):
        """Circular reference in normalize throws error."""
        js_code = """
        const { normalize } = require('./mu/host/js/core/normalize');
        const a = {};
        const b = {"ref": a};
        a.ref = b;
        try {
            normalize(a);
            console.log('NO_ERROR');
            process.exit(1);
        } catch (e) {
            console.log('CYCLE_DETECTED');
        }
        """
        result = subprocess.run(
            ["node", "-e", js_code],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"Cycle test failed:\n{result.stderr}"
        assert "CYCLE_DETECTED" in result.stdout

    def test_js_suite_passes(self):
        """Full JS eval_step.js test suite still passes."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"eval_step.js failed:\n{result.stdout[-500:]}\n{result.stderr[-500:]}"
        )
        assert "All tests passed: true" in result.stdout


# ---------------------------------------------------------------------------
# TestRatchetEvidence
# ---------------------------------------------------------------------------

class TestRatchetEvidence:
    """Verify ratchet passes and JS host_recursion is reduced."""

    def test_ratchet_passes(self):
        result = subprocess.run(
            ["python3", str(RATCHET_TOOL)],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"Ratchet check failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_js_host_recursion_reduced(self):
        result = subprocess.run(
            ["python3", str(RATCHET_TOOL), "--json"],
            capture_output=True, text=True, check=False,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        js_recursion = data["current"]["javascript"]["host_recursion"]
        assert js_recursion <= 3, (
            f"JS host_recursion should be <= 3, got {js_recursion}"
        )
