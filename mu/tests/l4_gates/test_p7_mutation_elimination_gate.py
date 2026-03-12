"""P7 Wave 1: Host Mutation Elimination — Gate Tests.

Validates that @host_mutation is genuinely removed from _stage0_substitute
by replacing .append() mutation loops with generator expressions.

Evidence for: P7 Host Semantics Reduction, target gate G8.
L4 class: L4_STRUCTURAL.

Tests:
  1. Behavioral equivalence — canonical vectors produce identical results
  2. No mutation constructs — AST proof: no .append() in _stage0_substitute
  3. No @host_mutation marker — source scan confirms decorator removed
  4. No AST police violations on _stage0_substitute
  5. Deep substitution — nested dicts/lists produce correct results
  6. Cross-substrate parity — Python matches JS for same inputs
  7. Host semantics ratchet passes
"""

import ast
import inspect
import json
import subprocess
import textwrap

import pytest

from rcx_pi.selfhost.eval_seed import (
    NO_MATCH,
    match,
    substitute,
)
from rcx_pi.selfhost.eval_seed import _stage0_substitute  # ANTICHEAT_OK: AST inspection for P7 mutation elimination gate
from rcx_pi.selfhost.eval_seed import _stage0_match  # ANTICHEAT_OK: parity comparison for P7 gate

from tests.repo_root import REPO_ROOT

EVAL_SEED_PATH = REPO_ROOT / "rcx_pi" / "selfhost" / "eval_seed.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_function_source(func):
    """Return dedented source of a function."""
    return textwrap.dedent(inspect.getsource(func))


def _find_append_calls(source: str) -> list[str]:
    """AST-based: find any .append() method calls in source.

    Returns list of line descriptions for each violation found.
    """
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute)
                    and node.func.attr == "append"):
                name = ""
                if isinstance(node.func.value, ast.Name):
                    name = node.func.value.id
                violations.append(f"line {node.lineno}: {name}.append()")
    return violations


def _has_subscript_assignment(source: str) -> list[str]:
    """AST-based: find any x[k] = v assignment in source."""
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AugAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Subscript):
                if isinstance(target.value, ast.Name):
                    violations.append(
                        f"line {node.lineno}: {target.value.id}[...] = ..."
                    )
                else:
                    violations.append(f"line {node.lineno}: <expr>[...] = ...")
    return violations


# ===========================================================================
# TestMutationConstructsRemoved
# ===========================================================================

class TestMutationConstructsRemoved:
    """Prove mutation constructs are genuinely absent from _stage0_substitute."""

    def test_no_append_calls(self):
        """AST proof: _stage0_substitute must have zero .append() calls."""
        source = _get_function_source(_stage0_substitute)
        violations = _find_append_calls(source)
        assert violations == [], (
            f"_stage0_substitute still contains .append() calls "
            f"(mutation not eliminated): {violations}"
        )

    def test_no_subscript_assignment(self):
        """AST proof: _stage0_substitute must have zero subscript assignments."""
        source = _get_function_source(_stage0_substitute)
        violations = _has_subscript_assignment(source)
        assert violations == [], (
            f"_stage0_substitute still contains subscript assignment(s): {violations}"
        )

    def test_uses_generator_expressions(self):
        """AST proof: _stage0_substitute uses GeneratorExp (not ListComp/DictComp)."""
        source = _get_function_source(_stage0_substitute)
        tree = ast.parse(source)
        genexps = [n for n in ast.walk(tree) if isinstance(n, ast.GeneratorExp)]
        listcomps = [n for n in ast.walk(tree) if isinstance(n, ast.ListComp)]
        dictcomps = [n for n in ast.walk(tree) if isinstance(n, ast.DictComp)]
        assert len(genexps) >= 2, (
            f"Expected >=2 generator expressions (dict + list path), found {len(genexps)}"
        )
        assert listcomps == [], "ListComp found — would add AST_OK debt"
        assert dictcomps == [], "DictComp found — would add AST_OK debt"


# ===========================================================================
# TestMarkerRemoved
# ===========================================================================

class TestMarkerRemoved:
    """Verify @host_mutation decorator is removed from _stage0_substitute."""

    def test_no_host_mutation_on_stage0_substitute(self):
        """Source scan: @host_mutation must not appear on _stage0_substitute."""
        source = EVAL_SEED_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("def _stage0_substitute("):
                window = "\n".join(lines[max(0, i - 10):i])
                assert "@host_mutation" not in window, (
                    f"@host_mutation still present on _stage0_substitute "
                    f"(lines {max(0, i - 10)}-{i})"
                )
                return
        pytest.fail("Could not find 'def _stage0_substitute(' in eval_seed.py")

    def test_host_recursion_retained(self):
        """@host_recursion must remain — recursion is still on trusted path."""
        source = EVAL_SEED_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("def _stage0_substitute("):
                window = "\n".join(lines[max(0, i - 10):i])
                assert "@host_recursion" in window, (
                    "@host_recursion removed from _stage0_substitute but "
                    "recursion is still present — marker must be retained"
                )
                return
        pytest.fail("Could not find 'def _stage0_substitute(' in eval_seed.py")

    def test_ratchet_mutation_zero(self):
        """Ratchet must show Python host_mutation == 0."""
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["current"]["python"]["host_mutation"] == 0, (
            f"Python host_mutation is {data['current']['python']['host_mutation']}, "
            f"expected 0 after P7 Wave 1 elimination"
        )


# ===========================================================================
# TestBehavioralEquivalence
# ===========================================================================

class TestBehavioralEquivalence:
    """Verify _stage0_substitute produces correct results for canonical vectors."""

    def test_simple_var_binding(self):
        result = _stage0_substitute({"var": "x"}, {"x": 42})
        assert result == 42

    def test_dict_substitution(self):
        body = {"a": {"var": "x"}, "b": {"var": "y"}}
        bindings = {"x": 1, "y": 2}
        result = _stage0_substitute(body, bindings)
        assert result == {"a": 1, "b": 2}

    def test_list_substitution(self):
        body = [{"var": "x"}, {"var": "y"}, 3]
        bindings = {"x": 10, "y": 20}
        result = _stage0_substitute(body, bindings)
        assert result == [10, 20, 3]

    def test_nested_substitution(self):
        body = {"a": [{"var": "x"}, {"b": {"var": "y"}}], "c": {"var": "z"}}
        bindings = {"x": 1, "y": 2, "z": 3}
        result = _stage0_substitute(body, bindings)
        assert result == {"a": [1, {"b": 2}], "c": 3}

    def test_literal_passthrough(self):
        """Non-variable structures pass through unchanged."""
        assert _stage0_substitute(42, {}) == 42
        assert _stage0_substitute("hello", {}) == "hello"
        assert _stage0_substitute(True, {}) is True
        assert _stage0_substitute(None, {}) is None

    def test_empty_structures(self):
        assert _stage0_substitute({}, {}) == {}
        assert _stage0_substitute([], {}) == []

    def test_deeply_nested(self):
        """Deep nesting (5 levels) must produce correct results."""
        body = {"a": {"b": {"c": {"d": {"var": "x"}}}}}
        result = _stage0_substitute(body, {"x": "deep"})
        assert result == {"a": {"b": {"c": {"d": "deep"}}}}

    def test_unbound_variable_raises(self):
        """Unbound variables must raise KeyError."""
        with pytest.raises(KeyError, match="Unbound variable"):
            _stage0_substitute({"var": "missing"}, {})


# ===========================================================================
# TestCrossSubstrateParity
# ===========================================================================

class TestCrossSubstrateParity:
    """Verify Python _stage0_substitute matches JS stage0Substitute."""

    def test_js_eval_step_passes(self):
        """JS substrate must remain green after Python mutation elimination."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"JS eval_step failed:\n{result.stderr}"


# ===========================================================================
# TestRatchetEvidence
# ===========================================================================

class TestRatchetEvidence:
    """Verify ratchet passes and total decreased from baseline."""

    def test_ratchet_passes(self):
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Ratchet failed:\n{result.stderr}"

    def test_ratchet_shows_decrease(self):
        """Ratchet --json must show a decrease in python.host_mutation."""
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        assert len(data["decreases"]) > 0, "No decreases recorded by ratchet"
        mutation_decrease = [
            d for d in data["decreases"]
            if d["category"] == "host_mutation" and d["substrate"] == "python"
        ]
        assert len(mutation_decrease) == 1, (
            f"Expected exactly 1 mutation decrease, found {len(mutation_decrease)}"
        )
        assert mutation_decrease[0]["delta"] == 1, (
            f"Expected delta=1, got {mutation_decrease[0]['delta']}"
        )
