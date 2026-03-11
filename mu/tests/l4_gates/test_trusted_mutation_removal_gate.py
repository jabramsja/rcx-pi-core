"""Gate tests for CP-S1A: trusted-path mutation removal.

Validates that dict-key mutation (bindings[k] = v) is genuinely removed
from the active trusted runtime path (_step_trusted -> _apply_projection_trusted
-> _match_inner), not just laundered from wrapper bodies.

Anti-laundering rule: a marker can be removed only if the corresponding
construct is removed from the active trusted runtime call graph.
"""

import ast
import inspect
import json
import subprocess
import textwrap
from pathlib import Path

import pytest

from rcx_pi.selfhost.eval_seed import NO_MATCH, match
from rcx_pi.selfhost.eval_seed import _apply_projection_trusted  # ANTICHEAT_OK: trusted-path AST inspection for anti-laundering gate
from rcx_pi.selfhost.eval_seed import _match_inner  # ANTICHEAT_OK: trusted-path AST inspection for anti-laundering gate
from rcx_pi.selfhost.eval_seed import _step_trusted  # ANTICHEAT_OK: trusted-path source-lock gate test


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_function_source(func):
    """Return dedented source of a function."""
    return textwrap.dedent(inspect.getsource(func))


def _has_subscript_assignment(source: str) -> list[str]:
    """AST-based: find any assignment where target is a subscript (e.g. x[k] = v).

    Returns list of line descriptions for each violation found.
    """
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
                # Extract name if possible for reporting
                if isinstance(target.value, ast.Name):
                    violations.append(
                        f"line {node.lineno}: {target.value.id}[...] = ..."
                    )
                else:
                    violations.append(f"line {node.lineno}: <expr>[...] = ...")
    return violations


from tests.repo_root import REPO_ROOT

EVAL_SEED_PATH = REPO_ROOT / "rcx_pi" / "selfhost" / "eval_seed.py"


# ===========================================================================
# TestMutationRemovedFromTrustedPath
# ===========================================================================

class TestMutationRemovedFromTrustedPath:
    """Verify mutation constructs are genuinely removed from trusted path."""

    def test_match_inner_no_subscript_assignment(self):
        """AST-based: _match_inner must have zero subscript assignments."""
        source = _get_function_source(_match_inner)
        violations = _has_subscript_assignment(source)
        assert violations == [], (
            f"_match_inner still contains subscript assignment(s) "
            f"(anti-laundering violation): {violations}"
        )

    def test_apply_projection_trusted_no_subscript_assignment(self):
        """AST-based: _apply_projection_trusted must have zero subscript assignments."""
        source = _get_function_source(_apply_projection_trusted)
        violations = _has_subscript_assignment(source)
        assert violations == [], (
            f"_apply_projection_trusted still contains subscript assignment(s): {violations}"
        )

    def test_match_no_host_mutation_marker(self):
        """@host_mutation must not appear on match()."""
        source = EVAL_SEED_PATH.read_text()
        # Find the match function definition and check decorators above it
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("def match("):
                # Check preceding lines for @host_mutation
                window = "\n".join(lines[max(0, i - 5):i])
                assert "@host_mutation" not in window, (
                    f"@host_mutation marker still present on match() "
                    f"(lines {max(0, i - 5)}-{i})"
                )
                return
        pytest.fail("Could not find 'def match(' in eval_seed.py")


# ===========================================================================
# TestMarkersRetainedWhereConstructsRemain
# ===========================================================================

class TestMarkersRetainedWhereConstructsRemain:
    """Verify markers are NOT removed where constructs still exist on trusted path."""

    def test_match_retains_host_recursion(self):
        """@host_recursion must remain on match() — recursion is on trusted path."""
        source = EVAL_SEED_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("def match("):
                window = "\n".join(lines[max(0, i - 10):i])
                assert "@host_recursion" in window, (
                    "@host_recursion removed from match() but _match_inner "
                    "is still recursive on the trusted path"
                )
                return
        pytest.fail("Could not find 'def match(' in eval_seed.py")

    def test_match_retains_host_builtin(self):
        """@host_builtin must remain on match() — builtins are on trusted path."""
        source = EVAL_SEED_PATH.read_text()
        lines = source.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("def match("):
                window = "\n".join(lines[max(0, i - 10):i])
                assert "@host_builtin" in window, (
                    "@host_builtin removed from match() but isinstance/len/zip "
                    "remain in _match_inner on the trusted path"
                )
                return
        pytest.fail("Could not find 'def match(' in eval_seed.py")


# ===========================================================================
# TestTrustedPathSourceLock
# ===========================================================================

class TestTrustedPathSourceLock:
    """Source-lock the trusted path call graph assumptions."""

    def test_apply_projection_trusted_calls_match_inner(self):
        source = _get_function_source(_apply_projection_trusted)
        assert "_match_inner(" in source, (
            "_apply_projection_trusted no longer calls _match_inner — "
            "trusted path assumption violated"
        )

    def test_step_trusted_calls_apply_projection_trusted(self):
        source = _get_function_source(_step_trusted)
        assert "_apply_projection_trusted(" in source, (
            "_step_trusted no longer calls _apply_projection_trusted — "
            "trusted path assumption violated"
        )


# ===========================================================================
# TestBehaviorPreserved — non-linear patterns
# ===========================================================================

class TestBehaviorPreserved:
    """Verify pure merge produces identical results to mutating merge."""

    def test_nonlinear_agreement(self):
        """Same variable, same value — should succeed."""
        result = match([{"var": "x"}, {"var": "x"}], [1, 1])
        assert result == {"x": 1}

    def test_nonlinear_conflict(self):
        """Same variable, different values — should fail."""
        result = match([{"var": "x"}, {"var": "x"}], [1, 2])
        assert result is NO_MATCH

    def test_nonlinear_dict(self):
        """Same variable in dict values — should succeed when equal."""
        result = match(
            {"a": {"var": "x"}, "b": {"var": "x"}},
            {"a": 1, "b": 1},
        )
        assert result == {"x": 1}

    def test_nonlinear_dict_conflict(self):
        """Same variable in dict values — should fail when different."""
        result = match(
            {"a": {"var": "x"}, "b": {"var": "x"}},
            {"a": 1, "b": 2},
        )
        assert result is NO_MATCH

    def test_multi_var_merge(self):
        """Multiple distinct variables — should all bind."""
        result = match(
            [{"var": "x"}, {"var": "y"}],
            [1, 2],
        )
        assert result == {"x": 1, "y": 2}

    def test_nested_merge(self):
        """Deeply nested pattern with multiple variables."""
        result = match(
            {"a": [{"var": "x"}, {"var": "y"}], "b": {"var": "z"}},
            {"a": [10, 20], "b": 30},
        )
        assert result == {"x": 10, "y": 20, "z": 30}

    def test_empty_match(self):
        """Literal match — no variables, empty bindings."""
        result = match(42, 42)
        assert result == {}

    def test_var_binding(self):
        """Single variable binding."""
        result = match({"var": "x"}, 42)
        assert result == {"x": 42}

    def test_js_eval_step_passes(self):
        """JS substrate remains green."""
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"JS eval_step failed:\n{result.stderr}"


# ===========================================================================
# TestRatchetEvidence
# ===========================================================================

class TestRatchetEvidence:
    """Verify ratchet reflects genuine debt decrease."""

    def test_ratchet_passes(self):
        """Ratchet checker must exit 0."""
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Ratchet failed:\n{result.stderr}"

    def test_py_host_mutation_zero(self):
        """Python host_mutation must be 1 (Wave I: _stage0_substitute @host_mutation)."""
        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout)
        assert data["current"]["python"]["host_mutation"] == 1, (
            f"Python host_mutation is {data['current']['python']['host_mutation']}, "
            f"expected 1"
        )

    def test_total_decreased(self):
        """Current total must be strictly less than before-snapshot total."""
        before_path = Path("/tmp/cp_s1a_before.json")
        if not before_path.exists():
            pytest.skip("Before-snapshot not found at /tmp/cp_s1a_before.json")
        before = json.loads(before_path.read_text())
        before_total = sum(
            v for cat in before["current"].values() for v in cat.values()
        )

        result = subprocess.run(
            ["python3", "mu/tools/checks/check_host_semantics_ratchet.py", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        after = json.loads(result.stdout)
        after_total = sum(
            v for cat in after["current"].values() for v in cat.values()
        )

        assert after_total < before_total, (
            f"Total did not decrease: before={before_total}, after={after_total}"
        )


# ===========================================================================
# TestBaselineUntouched
# ===========================================================================

class TestBaselineUntouched:
    """Verify baseline file is not co-staged with runtime files (Rule 20)."""

    def test_baseline_not_co_staged_with_runtime(self):
        """Rule 20: baseline + runtime in same commit is a structural violation."""
        staged = set(subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip().splitlines())

        baseline_paths = {
            "mu/tools/checks/host_semantics_baseline.json",
            "tools/checks/host_semantics_baseline.json",
        }
        runtime_prefixes = (
            "rcx_pi/selfhost/",
            "mu/host/",
            "mu/substrate/",
            "mu/closures/",
            "mu/bridge/",
            "mu/programs/",
            "mu/tools/compilers/",
        )

        baseline_staged = any(p in staged for p in baseline_paths)
        runtime_staged = any(
            any(f.startswith(pref) for pref in runtime_prefixes) for f in staged
        )

        assert not (baseline_staged and runtime_staged), (
            "Rule 20 violation: baseline file co-staged with runtime/substrate files — "
            "baseline updates must be a separate MAINTENANCE wave"
        )
