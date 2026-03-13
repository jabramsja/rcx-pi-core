"""
L4 Gate: Deferred Parity Fixes — nested head/tail + control hash.

Proves the L4_STRUCTURAL parity fixes:
  1. subst_mu preserves nested head/tail structures (matching eval_seed.substitute)
  2. run_exhaustion API handler uses control hash (matching core engine path)

Evidence:
    1. _reconcile_parity and _substitute_direct exist in subst_mu.py.
    2. Nested typed head/tail parity with eval_seed.substitute is verified.
    3. json_handlers.js run_exhaustion stall uses muHashControlCached.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_parity_fix_deferred_gate.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.eval_seed import substitute
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.subst_mu import subst_mu


# ---------------------------------------------------------------------------
# Source lock: required functions must exist
# ---------------------------------------------------------------------------

class TestParityFixSourceLock:
    """Verify parity fix functions exist in subst_mu.py."""

    def test_reconcile_parity_exists(self):
        """_reconcile_parity must exist in subst_mu.py."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "subst_mu.py"
        source = py_path.read_text()
        assert "_reconcile_parity" in source, (
            "_reconcile_parity must exist in subst_mu.py for nested head/tail parity"
        )

    def test_substitute_direct_exists(self):
        """_substitute_direct must exist in subst_mu.py."""
        py_path = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "subst_mu.py"
        source = py_path.read_text()
        assert "_substitute_direct" in source, (
            "_substitute_direct must exist in subst_mu.py for head/tail body substitution"
        )


# ---------------------------------------------------------------------------
# Parity evidence: nested head/tail structures preserved
# ---------------------------------------------------------------------------

class TestNestedHeadTailParity:
    """Verify subst_mu matches eval_seed.substitute for nested head/tail."""

    def test_typed_head_tail_in_dict(self):
        """Dict containing typed head/tail: subst_mu must match substitute."""
        body = {"data": {"_type": "list", "head": 1, "tail": None}}
        py_result = substitute(body, {})
        mu_result = subst_mu(body, {})
        assert mu_equal(py_result, mu_result), (
            f"Parity failure: Python={py_result}, Mu={mu_result}"
        )

    def test_binding_value_is_typed_head_tail(self):
        """Binding value as typed head/tail: must not be denormalized."""
        body = {"result": {"var": "x"}}
        bindings = {"x": {"_type": "list", "head": 1, "tail": {"head": 2, "tail": None}}}
        py_result = substitute(body, bindings)
        mu_result = subst_mu(body, bindings)
        assert mu_equal(py_result, mu_result), (
            f"Parity failure: Python={py_result}, Mu={mu_result}"
        )

    def test_nested_head_tail_with_var(self):
        """Nested head/tail containing var: must substitute and preserve."""
        body = {"a": {"b": {"c": {"head": {"var": "x"}, "tail": None}}}}
        bindings = {"x": 99}
        py_result = substitute(body, bindings)
        mu_result = subst_mu(body, bindings)
        assert mu_equal(py_result, mu_result), (
            f"Parity failure: Python={py_result}, Mu={mu_result}"
        )


# ---------------------------------------------------------------------------
# JS source lock: control hash in run_exhaustion
# ---------------------------------------------------------------------------

class TestJSControlHashLock:
    """Verify json_handlers.js uses control hash for stall detection."""

    def test_run_exhaustion_uses_control_hash(self):
        """run_exhaustion stall detection must use muHashControlCached."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "api" / "json_handlers.js"
        source = js_path.read_text()
        assert "muHashControlCached" in source, (
            "json_handlers.js must use muHashControlCached for run_exhaustion stall detection"
        )

    def test_run_exhaustion_not_content_hash(self):
        """run_exhaustion must NOT use muHashCached for stall (content vs control)."""
        js_path = REPO_ROOT / "mu" / "host" / "js" / "api" / "json_handlers.js"
        source = js_path.read_text()
        # Find the run_exhaustion handler section and check it doesn't use content hash
        lines = source.split("\n")
        in_exhaustion = False
        for line in lines:
            if "run_exhaustion" in line:
                in_exhaustion = True
            if in_exhaustion and "muHashCached(" in line and "muHashControlCached" not in line:
                pytest.fail(
                    f"run_exhaustion still uses muHashCached (content hash): {line.strip()}"
                )
            if in_exhaustion and line.strip().startswith("case "):
                break  # Left the run_exhaustion handler
