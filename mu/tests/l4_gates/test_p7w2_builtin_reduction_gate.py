"""P7 Wave 2: host_builtin Reduction — Gate Tests.

Validates that host_builtin count decreased by 2 (Python -1, JS -1):
  1. Python consume_budget: isinstance removed (trusting well-formed budget)
  2. JS muEqual: @host_builtin marker removed (demoted to test-only, parity with Python)

Evidence for: P7 Host Semantics Reduction, target gate G8.
L4 class: L4_STRUCTURAL.

Tests:
  1. consume_budget has no isinstance — AST proof
  2. consume_budget behavioral equivalence — well-formed and None inputs
  3. JS consumeBudget simplified — no typeof check in source
  4. JS muEqual demoted — no @host_builtin marker in source
  5. JS production code uses muHashCached not muEqual
  6. Ratchet shows host_builtin decrease (both substrates)
  7. Cross-substrate parity — JS eval_step passes
  8. Ratchet passes (no increases)
"""

import ast
import inspect
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from rcx_pi.selfhost.mu_type import consume_budget, make_depth_budget

from tests.repo_root import REPO_ROOT

JS_TYPES_PATH = REPO_ROOT / "mu" / "host" / "js" / "core" / "types.js"
JS_HANDLERS_PATH = REPO_ROOT / "mu" / "host" / "js" / "api" / "json_handlers.js"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_function_source(func):
    """Return dedented source of a function."""
    return textwrap.dedent(inspect.getsource(func))


def _find_isinstance_calls(source: str) -> list[str]:
    """AST-based: find any isinstance() calls in source."""
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                violations.append(f"line {node.lineno}: isinstance()")
    return violations


# ===========================================================================
# TestConsumeBudgetSimplified
# ===========================================================================

class TestConsumeBudgetSimplified:
    """Prove isinstance is genuinely removed from consume_budget."""

    def test_no_isinstance_calls(self):
        """AST proof: consume_budget must have zero isinstance() calls."""
        source = _get_function_source(consume_budget)
        violations = _find_isinstance_calls(source)
        assert violations == [], (
            f"consume_budget still contains isinstance() calls: {violations}"
        )

    def test_no_host_builtin_marker(self):
        """Source scan: consume_budget must not have @host_builtin marker."""
        source = _get_function_source(consume_budget)
        assert "@host_builtin" not in source, (
            "consume_budget still has @host_builtin marker"
        )


# ===========================================================================
# TestConsumeBudgetBehavior
# ===========================================================================

class TestConsumeBudgetBehavior:
    """Verify consume_budget produces correct results after simplification."""

    def test_none_returns_false(self):
        ok, remaining = consume_budget(None)
        assert ok is False
        assert remaining is None

    def test_well_formed_budget(self):
        budget = make_depth_budget(3)
        ok, remaining = consume_budget(budget)
        assert ok is True
        assert remaining is not None

    def test_exhausted_budget(self):
        """Single-level budget: consuming once gives tail=None, then False."""
        budget = make_depth_budget(1)
        ok, remaining = consume_budget(budget)
        assert ok is True
        assert remaining is None
        ok2, remaining2 = consume_budget(remaining)
        assert ok2 is False
        assert remaining2 is None

    def test_full_chain(self):
        """Consuming a budget of depth N succeeds N times, then fails."""
        depth = 5
        budget = make_depth_budget(depth)
        for i in range(depth):
            ok, budget = consume_budget(budget)
            assert ok is True, f"Expected ok=True at step {i}"
        ok, budget = consume_budget(budget)
        assert ok is False


# ===========================================================================
# TestJsSimplifications
# ===========================================================================

class TestJsSimplifications:
    """Verify JS-side changes: consumeBudget simplified, muEqual demoted."""

    def test_js_consume_budget_no_typeof(self):
        """JS consumeBudget must not use 'typeof budget' check."""
        source = JS_TYPES_PATH.read_text()
        # Find the consumeBudget function
        in_fn = False
        fn_lines = []
        for line in source.splitlines():
            if "function consumeBudget" in line:
                in_fn = True
            if in_fn:
                fn_lines.append(line)
                if line.strip() == "}":
                    break
        fn_source = "\n".join(fn_lines)
        assert "typeof budget" not in fn_source, (
            f"JS consumeBudget still uses typeof check:\n{fn_source}"
        )

    def test_js_mu_equal_no_host_builtin_marker(self):
        """JS muEqual must not have @host_builtin marker."""
        source = JS_TYPES_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if "function muEqual" in line:
                # Check JSDoc window above the function
                window = "\n".join(lines[max(0, i - 10):i])
                assert "@host_builtin" not in window, (
                    f"JS muEqual still has @host_builtin marker "
                    f"(lines {max(0, i - 10)}-{i})"
                )
                return
        pytest.fail("Could not find 'function muEqual' in types.js")

    def test_js_handlers_uses_hash_not_mu_equal(self):
        """json_handlers.js must use muHashCached, not muEqual, for stall detection."""
        source = JS_HANDLERS_PATH.read_text()
        assert "muEqual" not in source, (
            "json_handlers.js still uses muEqual — must use muHashCached directly"
        )


# ===========================================================================
# TestRatchetEvidence
# ===========================================================================

class TestRatchetEvidence:
    """Verify ratchet reflects genuine host_builtin decrease."""

    def test_ratchet_passes(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Ratchet failed:\n{result.stderr}"

    def test_host_builtin_decreased(self):
        """Both substrates must show host_builtin < baseline."""
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        py_current = data["current"]["python"]["host_builtin"]
        py_baseline = data["baseline_counts"]["python"]["host_builtin"]
        js_current = data["current"]["javascript"]["host_builtin"]
        js_baseline = data["baseline_counts"]["javascript"]["host_builtin"]
        assert py_current < py_baseline, (
            f"Python host_builtin not decreased: {py_current} (baseline {py_baseline})"
        )
        assert js_current < js_baseline, (
            f"JS host_builtin not decreased: {js_current} (baseline {js_baseline})"
        )

    def test_no_increases(self):
        """No host semantics category may increase."""
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["increases"] == [], (
            f"Ratchet shows increases (regression): {data['increases']}"
        )

    def test_js_eval_step_passes(self):
        """JS substrate must remain green after Python/JS builtin reduction."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"JS eval_step failed:\n{result.stderr}"
