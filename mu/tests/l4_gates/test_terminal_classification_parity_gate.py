"""
L4 Gate Test: Terminal Classification Parity (Wave 17).

Verifies that terminal classification constants and functions are identical
across Python and JavaScript substrates. Fail-closed: any drift is a violation.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_terminal_classification_parity_gate.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import (
    ENGINE_EXIT_REASONS,
    TERMINAL_KINDS,
    _ENGINE_TERMINAL_KEYS,  # ANTICHEAT_OK: parity gate compares Python key sets against JS source
    _EXHAUSTION_TERMINAL_KEYS,  # ANTICHEAT_OK: parity gate compares Python key sets against JS source
    _RECURRENCE_TERMINAL_KEYS,  # ANTICHEAT_OK: parity gate compares Python key sets against JS source
    classify_terminal_kind,
)

JS_DIR = REPO_ROOT / "mu" / "host" / "js"
PY_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"


# ---------------------------------------------------------------------------
# Helpers — extract JS constants via regex
# ---------------------------------------------------------------------------

def _js_source() -> str:
    """Read all JS module files concatenated (monolith was split into modules)."""
    parts = []
    for f in sorted(JS_DIR.rglob("*.js")):
        parts.append(f.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _extract_js_set(source: str, var_name: str) -> set[str]:
    """Extract a Set([...]) constant from JS source."""
    pattern = rf"const\s+{re.escape(var_name)}\s*=\s*new\s+Set\(\[(.*?)\]\)"
    m = re.search(pattern, source, re.DOTALL)
    if not m:
        pytest.fail(f"Could not find {var_name} in eval_step.js")
    return set(re.findall(r"'([^']+)'", m.group(1)))


# =============================================================================
# Constant parity: terminal key sets
# =============================================================================

class TestTerminalKeySetParity:
    """Terminal shape key sets must be identical across substrates."""

    def test_recurrence_terminal_keys_match(self):
        js = _js_source()
        js_keys = _extract_js_set(js, "RECURRENCE_TERMINAL_KEYS")
        assert set(_RECURRENCE_TERMINAL_KEYS) == js_keys

    def test_exhaustion_terminal_keys_match(self):
        js = _js_source()
        js_keys = _extract_js_set(js, "EXHAUSTION_TERMINAL_KEYS")
        assert set(_EXHAUSTION_TERMINAL_KEYS) == js_keys

    def test_engine_terminal_keys_match(self):
        js = _js_source()
        js_keys = _extract_js_set(js, "ENGINE_TERMINAL_KEYS")
        assert set(_ENGINE_TERMINAL_KEYS) == js_keys


# =============================================================================
# Constant parity: enums
# =============================================================================

class TestEnumParity:
    """Terminal classification enums must be identical across substrates."""

    def test_terminal_kinds_match(self):
        js = _js_source()
        js_kinds = _extract_js_set(js, "TERMINAL_KINDS")
        assert set(TERMINAL_KINDS) == js_kinds

    def test_engine_exit_reasons_match(self):
        js = _js_source()
        js_reasons = _extract_js_set(js, "ENGINE_EXIT_REASONS")
        assert set(ENGINE_EXIT_REASONS) == js_reasons

    def test_terminal_kinds_constant(self):
        assert TERMINAL_KINDS == {
            "kernel_done", "recurrence_terminal", "exhaustion_terminal",
            "engine_terminal", "non_terminal",
        }

    def test_engine_exit_reasons_constant(self):
        assert ENGINE_EXIT_REASONS == {"closure", "exhaustion", "stall", "completed"}


# =============================================================================
# Function parity: classify_terminal_kind source presence
# =============================================================================

class TestClassifyTerminalKindSourceParity:
    """classifyTerminalKind function must exist in JS with matching logic."""

    def test_js_has_classify_function(self):
        js = _js_source()
        assert "function classifyTerminalKind(value)" in js

    def test_js_returns_all_terminal_kinds(self):
        js = _js_source()
        for kind in TERMINAL_KINDS:
            assert f"'{kind}'" in js, f"JS source missing terminal kind: {kind!r}"

    def test_python_returns_all_terminal_kinds(self):
        source = PY_PATH.read_text()
        for kind in TERMINAL_KINDS:
            assert f'"{kind}"' in source, f"Python source missing terminal kind: {kind!r}"

    def test_js_classify_priority_matches_python(self):
        """JS function checks kernel_done before seed-based classification.

        Wave 25: classification now delegates to terminal_classify.v1.json seed.
        Priority is: kernel_done (host-side) checked first, then seed step() handles
        recurrence > exhaustion > engine via projection order.
        """
        js = _js_source()
        # Extract function body
        start = js.index("function classifyTerminalKind(value)")
        body = js[start:start + 600]
        # kernel_done must appear before step() call (host-side check first)
        kernel_pos = body.index("kernel_done")
        step_pos = body.index("step(")
        assert kernel_pos < step_pos, (
            "kernel_done must be checked before seed step() delegation"
        )


# =============================================================================
# Behavioral tests: classify_terminal_kind (Python)
# =============================================================================

class TestClassifyTerminalKindBehavior:
    """classify_terminal_kind must produce correct classifications."""

    def test_kernel_done(self):
        val = {"_mode": "done", "_result": {"x": 1}, "_stall": False}
        assert classify_terminal_kind(val) == "kernel_done"

    def test_kernel_done_with_stall(self):
        val = {"_mode": "done", "_result": None, "_stall": True}
        assert classify_terminal_kind(val) == "kernel_done"

    def test_recurrence_terminal(self):
        val = {"closure_detected": True, "final_result": {"x": 1}, "tau_step": 3}
        assert classify_terminal_kind(val) == "recurrence_terminal"

    def test_exhaustion_terminal(self):
        val = {"action": "freeze", "exhaustion_detected": True,
               "frozen": {"a": 1}, "operator_to_freeze": "op"}
        assert classify_terminal_kind(val) == "exhaustion_terminal"

    def test_engine_terminal(self):
        val = {
            "value": {"x": 1}, "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": None, "stall": False,
        }
        assert classify_terminal_kind(val) == "engine_terminal"

    def test_non_terminal_dict(self):
        assert classify_terminal_kind({"x": 1, "y": 2}) == "non_terminal"

    def test_non_terminal_string(self):
        assert classify_terminal_kind("hello") == "non_terminal"

    def test_non_terminal_int(self):
        assert classify_terminal_kind(42) == "non_terminal"

    def test_non_terminal_none(self):
        assert classify_terminal_kind(None) == "non_terminal"

    def test_non_terminal_list(self):
        assert classify_terminal_kind([1, 2, 3]) == "non_terminal"

    def test_non_terminal_empty_dict(self):
        assert classify_terminal_kind({}) == "non_terminal"

    def test_kernel_intermediate_not_terminal(self):
        """_mode present but not 'done' is non_terminal (not kernel_done)."""
        val = {"_mode": "match", "_match_ctx": {}, "_result": None, "_stall": False}
        assert classify_terminal_kind(val) == "non_terminal"

    def test_kernel_done_priority_over_key_match(self):
        """kernel_done check happens before key-set comparison."""
        # A dict with _mode=done that also happens to have extra keys
        val = {"_mode": "done", "_result": None, "_stall": False, "extra": True}
        assert classify_terminal_kind(val) == "kernel_done"

    def test_partial_recurrence_keys_not_terminal(self):
        """Subset of recurrence keys is non_terminal."""
        val = {"closure_detected": True, "final_result": {"x": 1}}
        assert classify_terminal_kind(val) == "non_terminal"

    def test_superset_engine_keys_not_terminal(self):
        """Engine keys + extra key is non_terminal."""
        val = {
            "value": 1, "closure_detected": False, "tau_step": 0,
            "exhaustion_detected": False, "operator_frozen": False,
            "frozen_set": None, "action": None, "stall": False,
            "extra_key": True,
        }
        assert classify_terminal_kind(val) == "non_terminal"
