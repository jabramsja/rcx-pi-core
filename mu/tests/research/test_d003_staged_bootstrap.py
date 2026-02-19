"""D003: H2 Stage 0->1 Transition — Research Artifact

Tests H2 criteria 3 and 4:
  C3: Stage 0->1 transition produces identical results to expected terminals
  C4: eval_step contract (G2 minimality, G7 non-recursive) preserved

Builds on D002 micro_match (31 LOC). Adds micro_substitute + micro_step +
micro_run as research-only Stage 0 kernel. Validates against 5 canonical
test vectors exercising match.v2 and subst.v2 projections.

NOT production code. This file lives in tests/research/ and is never
imported by rcx_pi/.

Evidence for: mu/docs/core/L4DecisionCard.v0.md (D003)
               mu/docs/core/G8CpsFeasibility.v0.md (H2 criteria 3-4)
"""

import ast
import inspect
import json
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT
from tests.research.test_d002_micro_matcher import micro_match

# ---------------------------------------------------------------------------
# micro_substitute: Stage 0 substitution (research-only)
# Walks body tree, replaces {"var": "name"} with bindings[name].
# ---------------------------------------------------------------------------


def micro_substitute(body, bindings):
    if body is None:
        return None
    if isinstance(body, (str, int, float, bool)):
        return body
    if isinstance(body, dict):
        if "var" in body and len(body) == 1:
            name = body["var"]
            if name in bindings:
                return bindings[name]
            return body
        return {k: micro_substitute(v, bindings) for k, v in body.items()}
    if isinstance(body, list):
        return [micro_substitute(item, bindings) for item in body]
    return body


# ---------------------------------------------------------------------------
# micro_step: Stage 0 eval_step (research-only)
# First-match-wins projection application. No domain branching.
# ---------------------------------------------------------------------------


def micro_step(projections, value):
    for proj in projections:
        pattern = proj["pattern"]
        body = proj["body"]
        bindings = micro_match(pattern, value)
        if bindings is not None:
            return micro_substitute(body, bindings)
    return value


# ---------------------------------------------------------------------------
# micro_run: Iterative driver until terminal state
# ---------------------------------------------------------------------------

_TERMINAL_MODES = frozenset(["match_done", "subst_done"])


def micro_run(projections, value, max_steps=1000):
    for _ in range(max_steps):
        if isinstance(value, dict) and value.get("_mode") in _TERMINAL_MODES:
            return value
        next_value = micro_step(projections, value)
        if next_value is value:
            return value
        value = next_value
    return value


# ---------------------------------------------------------------------------
# Seed loading
# ---------------------------------------------------------------------------

SEEDS_DIR = REPO_ROOT / "mu" / "substrate"


def _load_seed_projections(name):
    seed = json.loads((SEEDS_DIR / name).read_text())
    return seed["projections"]


MATCH_V2 = _load_seed_projections("match.v2.json")
SUBST_V2 = _load_seed_projections("subst.v2.json")
ALL_PROJECTIONS = MATCH_V2 + SUBST_V2


# ---------------------------------------------------------------------------
# H2-C3: Stage 0->1 identical results (5 vectors)
# ---------------------------------------------------------------------------

class TestStage0TransitionCorrectness:
    """H2 criterion 3: micro_run produces correct terminal states."""

    def test_vector1_literal_match(self):
        """match.wrap -> match.equal -> match.done"""
        value = {"match": {"pattern": "x", "value": "x"}, "_match_ctx": {}}
        result = micro_run(ALL_PROJECTIONS, value)
        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        assert result["_bindings"] is None

    def test_vector2_var_bind(self):
        """match.wrap -> match.var -> match.done"""
        value = {"match": {"pattern": {"var": "a"}, "value": 42}, "_match_ctx": {}}
        result = micro_run(ALL_PROJECTIONS, value)
        assert result["_mode"] == "match_done"
        assert result["_status"] == "success"
        assert result["_bindings"] == {"name": "a", "value": 42, "rest": None}

    def test_vector3_match_failure(self):
        """match.wrap -> match.fail"""
        value = {"match": {"pattern": "x", "value": "y"}, "_match_ctx": {}}
        result = micro_run(ALL_PROJECTIONS, value)
        assert result["_mode"] == "match_done"
        assert result["_status"] == "no_match"

    def test_vector4_simple_subst(self):
        """subst.wrap -> subst.var -> subst.lookup.found -> subst.done"""
        value = {
            "subst": {
                "body": {"var": "x"},
                "bindings": {"name": "x", "value": 42, "rest": None},
            },
            "_subst_ctx": {},
        }
        result = micro_run(ALL_PROJECTIONS, value)
        assert result["_mode"] == "subst_done"
        assert result["_result"] == 42

    def test_vector5_structural_subst(self):
        """subst.wrap -> subst.descend -> ... -> subst.done"""
        value = {
            "subst": {
                "body": {"head": 1, "tail": {"var": "y"}},
                "bindings": {"name": "y", "value": 2, "rest": None},
            },
            "_subst_ctx": {},
        }
        result = micro_run(ALL_PROJECTIONS, value)
        assert result["_mode"] == "subst_done"
        assert result["_result"] == {"head": 1, "tail": 2}


# ---------------------------------------------------------------------------
# H2-C4: G2 preserved (AST-based — no domain branching in micro_step)
# ---------------------------------------------------------------------------

_DOMAIN_KEYS = {
    "_boundary_request", "_tail_call", "_run_engine",
    "_hemisphere", "_routing", "_engine_cmd",
}


class TestG2Preserved:
    """G2: micro_step must not inspect domain-specific keys."""

    def test_micro_step_no_domain_key_references_ast(self):
        """AST check: no string constant in micro_step matches a domain key."""
        source = inspect.getsource(micro_step)
        tree = ast.parse(source)
        found_domain_refs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in _DOMAIN_KEYS:
                    found_domain_refs.append(node.value)
        assert found_domain_refs == [], (
            f"micro_step references domain keys: {found_domain_refs}"
        )

    def test_micro_step_no_getattr_or_subscript_on_domain_keys_ast(self):
        """AST check: no subscript access using domain key strings."""
        source = inspect.getsource(micro_step)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Subscript):
                if isinstance(node.slice, ast.Constant):
                    if isinstance(node.slice.value, str):
                        assert node.slice.value not in _DOMAIN_KEYS, (
                            f"micro_step subscripts domain key: {node.slice.value}"
                        )


# ---------------------------------------------------------------------------
# H2-C4: G7 preserved (AST-based — non-recursive)
# ---------------------------------------------------------------------------

class TestG7Preserved:
    """G7: micro_step must not call itself (non-recursive)."""

    def test_micro_step_no_self_call_ast(self):
        """AST check: micro_step contains no Call node targeting 'micro_step'."""
        source = inspect.getsource(micro_step)
        tree = ast.parse(source)
        self_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "micro_step":
                    self_calls.append(node.lineno)
        assert self_calls == [], (
            f"micro_step calls itself at lines: {self_calls}"
        )

    def test_micro_run_no_recursion_ast(self):
        """AST check: micro_run does not call itself."""
        source = inspect.getsource(micro_run)
        tree = ast.parse(source)
        self_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "micro_run":
                    self_calls.append(node.lineno)
        assert self_calls == [], (
            f"micro_run calls itself at lines: {self_calls}"
        )


# ---------------------------------------------------------------------------
# No new production BOOTSTRAP_PRIMITIVE markers
# ---------------------------------------------------------------------------

class TestNoNewPrimitiveMarkers:
    """Production BOOTSTRAP_PRIMITIVE marker count must not increase."""

    def test_python_bootstrap_primitive_count(self):
        """Exactly 4 BOOTSTRAP_PRIMITIVE markers in rcx_pi/selfhost/."""
        selfhost_dir = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost"
        count = 0
        for py_file in selfhost_dir.glob("*.py"):
            content = py_file.read_text()
            count += content.count("BOOTSTRAP_PRIMITIVE")
        assert count == 4, (
            f"Expected 4 BOOTSTRAP_PRIMITIVE markers in selfhost/, found {count}"
        )

    def test_js_bootstrap_primitive_count(self):
        """Exactly 8 BOOTSTRAP_PRIMITIVE markers in eval_step.js."""
        js_file = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"
        content = js_file.read_text()
        count = content.count("BOOTSTRAP_PRIMITIVE")
        assert count == 8, (
            f"Expected 8 BOOTSTRAP_PRIMITIVE markers in eval_step.js, found {count}"
        )


# ---------------------------------------------------------------------------
# LOC measurements
# ---------------------------------------------------------------------------

def _count_code_lines(func):
    """Count non-blank, non-comment lines excluding def line."""
    source = inspect.getsource(func)
    lines = source.split("\n")
    return len([
        line for line in lines[1:]
        if line.strip() and not line.strip().startswith("#")
    ])


class TestLOCConstraints:
    """Stage 0 kernel LOC must be within thresholds."""

    def test_micro_match_loc(self):
        loc = _count_code_lines(micro_match)
        assert loc <= 50, f"micro_match is {loc} LOC (limit 50)"

    def test_micro_substitute_loc(self):
        loc = _count_code_lines(micro_substitute)
        assert loc <= 50, f"micro_substitute is {loc} LOC (limit 50)"

    def test_micro_step_loc(self):
        loc = _count_code_lines(micro_step)
        assert loc <= 15, f"micro_step is {loc} LOC (limit 15)"

    def test_total_stage0_kernel_loc(self):
        total = (
            _count_code_lines(micro_match)
            + _count_code_lines(micro_substitute)
            + _count_code_lines(micro_step)
        )
        assert total <= 100, f"Total Stage 0 kernel is {total} LOC (limit 100)"

    def test_micro_substitute_no_new_primitives(self):
        """micro_substitute uses only standard Python."""
        source = inspect.getsource(micro_substitute)
        assert "import " not in source
        assert "open(" not in source
        assert "global " not in source
        assert "sys." not in source
        assert "os." not in source


# ---------------------------------------------------------------------------
# Convergence tests (ensure micro_run terminates reasonably)
# ---------------------------------------------------------------------------

class TestConvergence:
    """Verify all vectors converge within reasonable step counts."""

    VECTORS = [
        {"match": {"pattern": "x", "value": "x"}, "_match_ctx": {}},
        {"match": {"pattern": {"var": "a"}, "value": 42}, "_match_ctx": {}},
        {"match": {"pattern": "x", "value": "y"}, "_match_ctx": {}},
        {"subst": {"body": {"var": "x"}, "bindings": {"name": "x", "value": 42, "rest": None}}, "_subst_ctx": {}},
        {"subst": {"body": {"head": 1, "tail": {"var": "y"}}, "bindings": {"name": "y", "value": 2, "rest": None}}, "_subst_ctx": {}},
    ]

    @pytest.mark.parametrize("vector", VECTORS, ids=[f"v{i+1}" for i in range(5)])
    def test_converges_under_100_steps(self, vector):
        """Each vector should reach terminal state in <100 steps."""
        value = vector
        for step_count in range(100):
            if isinstance(value, dict) and value.get("_mode") in _TERMINAL_MODES:
                break
            next_value = micro_step(ALL_PROJECTIONS, value)
            if next_value is value:
                break
            value = next_value
        else:
            pytest.fail(f"Did not converge in 100 steps")
        assert step_count < 100, f"Took {step_count} steps"
