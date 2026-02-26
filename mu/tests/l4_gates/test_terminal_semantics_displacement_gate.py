"""
L4 Gate Test: Terminal Semantics Displacement (Wave 25 + A6 key-set authority).

Proves that terminal classification and engine exit-reason decision logic
has been structurally displaced from host if/else chains into the
terminal_classify.v1.json seed projections. A6 additionally proves that
terminal key sets are seed-derived, not hardcoded.

Usage:
    PYTHONHASHSEED=0 pytest tests/l4_gates/test_terminal_semantics_displacement_gate.py -v
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.eval_seed import step as eval_step
from rcx_pi.selfhost.step_mu import (
    _load_tc_key_sets,  # ANTICHEAT_OK: gate verifies seed-derived key sets
    classify_terminal_kind,
    _derive_engine_exit_reason,  # ANTICHEAT_OK: gate verifies seed-backed exit reason
)
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path


# ---------------------------------------------------------------------------
# Seed loading
# ---------------------------------------------------------------------------

SEED_PATH = get_seed_path("terminal_classify.v1.json")

EXPECTED_IDS = [
    "tc.recurrence",
    "tc.exhaustion",
    "tc.engine",
    "tc.exit.closure",
    "tc.exit.exhaustion",
    "tc.exit.stall",
    "tc.exit.completed",
]

JS_CORE_DIR = REPO_ROOT / "mu" / "host" / "js" / "core"
PY_STEP_MU = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"


def _load_seed():
    return load_verified_seed(SEED_PATH)


# ---------------------------------------------------------------------------
# Terminal shape test fixtures
# ---------------------------------------------------------------------------

KERNEL_DONE = {"_mode": "done", "_result": 42, "_stall": False}
RECURRENCE_SHAPE = {"closure_detected": True, "final_result": 42, "tau_step": 1}
EXHAUSTION_SHAPE = {"action": "freeze", "exhaustion_detected": True, "frozen": [], "operator_to_freeze": "op"}
ENGINE_SHAPE = {
    "value": 1, "closure_detected": False, "tau_step": 0,
    "exhaustion_detected": False, "operator_frozen": False,
    "frozen_set": [], "action": None, "stall": False,
}
NON_TERMINAL = {"random": "dict", "with": "keys"}


# ===========================================================================
# Test 1: Seed exists with correct structure
# ===========================================================================

class TestSeedExists:
    def test_seed_file_exists(self):
        assert SEED_PATH.exists(), f"Seed not found: {SEED_PATH}"

    def test_seed_has_7_projections(self):
        seed = _load_seed()
        assert len(seed["projections"]) == 7

    def test_projection_ids_match_expected(self):
        seed = _load_seed()
        actual_ids = [p["id"] for p in seed["projections"]]
        assert actual_ids == EXPECTED_IDS

    def test_projection_ids_are_top_level(self):
        """Verify IDs use top-level 'id' field (not meta.id)."""
        seed = _load_seed()
        for p in seed["projections"]:
            assert "id" in p, f"Projection missing top-level 'id': {p}"


# ===========================================================================
# Test 2: Classification via projections
# ===========================================================================

class TestClassificationViaProjections:
    def test_recurrence_classification(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc": RECURRENCE_SHAPE})
        assert result == "recurrence_terminal"

    def test_exhaustion_classification(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc": EXHAUSTION_SHAPE})
        assert result == "exhaustion_terminal"

    def test_engine_classification(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc": ENGINE_SHAPE})
        assert result == "engine_terminal"

    def test_non_terminal_passthrough(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc": NON_TERMINAL})
        # Non-matching input passes through unchanged (not a string)
        assert not isinstance(result, str)


# ===========================================================================
# Test 3: Exit reason via projections
# ===========================================================================

class TestExitReasonViaProjections:
    def test_closure_exit(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc_exit": {"cd": True, "ed": False, "st": False}})
        assert result == "closure"

    def test_exhaustion_exit(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc_exit": {"cd": False, "ed": True, "st": False}})
        assert result == "exhaustion"

    def test_stall_exit(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc_exit": {"cd": False, "ed": False, "st": True}})
        assert result == "stall"

    def test_completed_exit(self):
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc_exit": {"cd": False, "ed": False, "st": False}})
        assert result == "completed"

    def test_closure_priority_over_exhaustion(self):
        """closure_detected=True takes priority even if exhaustion_detected=True."""
        seed = _load_seed()
        result = eval_step(seed["projections"], {"_tc_exit": {"cd": True, "ed": True, "st": True}})
        assert result == "closure"


# ===========================================================================
# Test 4: Source lock — Python uses eval_step
# ===========================================================================

class TestSourceLockUsesEvalStep:
    def test_classify_calls_eval_step(self):
        """classify_terminal_kind must call eval_step() (structural seed path)."""
        source = PY_STEP_MU.read_text(encoding="utf-8")
        # Find the function body
        fn_match = re.search(
            r'def classify_terminal_kind\(.*?\).*?:\n(.*?)(?=\ndef |\Z)',
            source, re.DOTALL
        )
        assert fn_match, "classify_terminal_kind not found in step_mu.py"
        body = fn_match.group(1)
        assert "eval_step(" in body, (
            "classify_terminal_kind must call eval_step() for structural displacement"
        )

    def test_derive_exit_reason_calls_eval_step(self):
        """_derive_engine_exit_reason must call eval_step() (structural seed path)."""
        source = PY_STEP_MU.read_text(encoding="utf-8")
        lines = source.splitlines()
        # Find the function start line
        start = None
        for i, line in enumerate(lines):
            if "def _derive_engine_exit_reason(" in line:
                start = i
                break
        assert start is not None, "_derive_engine_exit_reason not found in step_mu.py"
        # Extract body (next 20 lines is more than enough for this function)
        body = "\n".join(lines[start:start + 20])
        assert "eval_step(" in body, (
            "_derive_engine_exit_reason must call eval_step() for structural displacement"
        )


# ===========================================================================
# Test 5: Source lock — JS uses step
# ===========================================================================

class TestJSSourceLockUsesStep:
    def test_classify_calls_step(self):
        """JS classifyTerminalKind must call step() (structural seed path)."""
        source = (JS_CORE_DIR / "terminal_classification.js").read_text(encoding="utf-8")
        fn_match = re.search(
            r'function classifyTerminalKind\(.*?\)\s*\{(.*?)\n\}',
            source, re.DOTALL
        )
        assert fn_match, "classifyTerminalKind not found in terminal_classification.js"
        body = fn_match.group(1)
        assert "step(" in body, (
            "classifyTerminalKind must call step() for structural displacement"
        )

    def test_derive_exit_reason_calls_step(self):
        """JS deriveEngineExitReason must call step() (structural seed path)."""
        source = (JS_CORE_DIR / "terminal_classification.js").read_text(encoding="utf-8")
        fn_match = re.search(
            r'function deriveEngineExitReason\(.*?\)\s*\{(.*?)\n\}',
            source, re.DOTALL
        )
        assert fn_match, "deriveEngineExitReason not found in terminal_classification.js"
        body = fn_match.group(1)
        assert "step(" in body, (
            "deriveEngineExitReason must call step() for structural displacement"
        )


# ===========================================================================
# Test 6: kernel_done stays host-side
# ===========================================================================

class TestKernelDoneStaysHost:
    def test_kernel_done_returns_correctly(self):
        assert classify_terminal_kind(KERNEL_DONE) == "kernel_done"

    def test_kernel_done_not_in_seed(self):
        """No seed projection should produce 'kernel_done'."""
        seed = _load_seed()
        for p in seed["projections"]:
            assert p["id"] != "tc.kernel_done", "kernel_done must NOT be in seed"
            body = p.get("body", "")
            if isinstance(body, str):
                assert body != "kernel_done", f"Projection {p['id']} produces kernel_done"


# ===========================================================================
# Test 7: Behavior parity — same results as pre-displacement
# ===========================================================================

class TestBehaviorParity:
    """All known terminal shapes produce the same classification as before displacement."""

    # Regression lock: this legacy wrapper shape is NOT a terminal output shape.
    # It previously caused confusion in reviews and should stay non-terminal.
    LEGACY_RECURRENCE_WRAPPER = {"recurrence_result": {}, "recurrence_trace": []}

    CASES = [
        (KERNEL_DONE, "kernel_done"),
        (RECURRENCE_SHAPE, "recurrence_terminal"),
        (EXHAUSTION_SHAPE, "exhaustion_terminal"),
        (ENGINE_SHAPE, "engine_terminal"),
        (LEGACY_RECURRENCE_WRAPPER, "non_terminal"),
        (NON_TERMINAL, "non_terminal"),
        ("hello", "non_terminal"),
        (42, "non_terminal"),
        (None, "non_terminal"),
        ([], "non_terminal"),
    ]

    @pytest.mark.parametrize("value,expected", CASES, ids=[c[1] for c in CASES])
    def test_classify_parity(self, value, expected):
        assert classify_terminal_kind(value) == expected

    EXIT_CASES = [
        ({"closure_detected": True, "exhaustion_detected": False, "stall": False}, "closure"),
        ({"closure_detected": False, "exhaustion_detected": True, "stall": False}, "exhaustion"),
        ({"closure_detected": False, "exhaustion_detected": False, "stall": True}, "stall"),
        ({"closure_detected": False, "exhaustion_detected": False, "stall": False}, "completed"),
    ]

    @pytest.mark.parametrize("result,expected", EXIT_CASES, ids=[c[1] for c in EXIT_CASES])
    def test_exit_reason_parity(self, result, expected):
        assert _derive_engine_exit_reason(result) == expected


# ===========================================================================
# Test 8: Terminal key sets are seed-derived (A6 displacement)
# ===========================================================================

class TestSeedDerivedKeysets:
    """Verify terminal key sets are derived from seed, not hardcoded."""

    def test_derivation_returns_three_key_sets(self):
        """_load_tc_key_sets extracts exactly 3 terminal key sets from seed."""
        tc_sets = _load_tc_key_sets()
        assert len(tc_sets) == 3

    def test_derivation_ids_correct(self):
        """Derived key set IDs match expected projection IDs."""
        tc_sets = _load_tc_key_sets()
        assert set(tc_sets.keys()) == {"tc.recurrence", "tc.exhaustion", "tc.engine"}

    def test_recurrence_keys_cardinality(self):
        """Recurrence terminal has 3 keys."""
        tc_sets = _load_tc_key_sets()
        assert len(tc_sets["tc.recurrence"]) == 3

    def test_exhaustion_keys_cardinality(self):
        """Exhaustion terminal has 4 keys."""
        tc_sets = _load_tc_key_sets()
        assert len(tc_sets["tc.exhaustion"]) == 4

    def test_engine_keys_cardinality(self):
        """Engine terminal has 8 keys."""
        tc_sets = _load_tc_key_sets()
        assert len(tc_sets["tc.engine"]) == 8

    def test_derived_keys_match_seed_directly(self):
        """Derived key sets match raw seed projection patterns."""
        seed = _load_seed()
        tc_sets = _load_tc_key_sets()
        for p in seed["projections"]:
            pat = p.get("pattern") or {}
            if "_tc" in pat:
                seed_keys = frozenset(pat["_tc"].keys())
                assert tc_sets[p["id"]] == seed_keys, (
                    f"Derived keys for {p['id']} don't match seed"
                )

    def test_no_hardcoded_frozensets_in_python_source(self):
        """step_mu.py must NOT contain hardcoded terminal key frozensets (A6 source lock)."""
        source = PY_STEP_MU.read_text(encoding="utf-8")
        assert "_RECURRENCE_TERMINAL_KEYS = frozenset(" not in source, (
            "Hardcoded _RECURRENCE_TERMINAL_KEYS found — must be seed-derived"
        )
        assert "_EXHAUSTION_TERMINAL_KEYS = frozenset(" not in source, (
            "Hardcoded _EXHAUSTION_TERMINAL_KEYS found — must be seed-derived"
        )
        assert "_ENGINE_TERMINAL_KEYS = frozenset(" not in source, (
            "Hardcoded _ENGINE_TERMINAL_KEYS found — must be seed-derived"
        )

    def test_no_hardcoded_sets_in_js_source(self):
        """terminal_classification.js must NOT contain hardcoded terminal key Sets (A7 source lock)."""
        source = (JS_CORE_DIR / "terminal_classification.js").read_text(encoding="utf-8")
        assert "RECURRENCE_TERMINAL_KEYS = new Set([" not in source, (
            "Hardcoded RECURRENCE_TERMINAL_KEYS Set found — must be seed-derived"
        )
        assert "EXHAUSTION_TERMINAL_KEYS = new Set([" not in source, (
            "Hardcoded EXHAUSTION_TERMINAL_KEYS Set found — must be seed-derived"
        )
        assert "ENGINE_TERMINAL_KEYS = new Set([" not in source, (
            "Hardcoded ENGINE_TERMINAL_KEYS Set found — must be seed-derived"
        )


# ===========================================================================
# Test 9: Key-set prefilter short-circuits non-candidate dicts
# ===========================================================================

class TestPrefilterShortCircuit:
    """Non-candidate dicts must return non_terminal without touching eval_step."""

    def test_deep_nested_dict_is_non_terminal(self):
        """Deeply nested engine-internal state must not hang classify_terminal_kind."""
        import time
        # Build a deeply nested dict that would hang if eval_step/assert_mu walked it
        deep = {"x": 1}
        for _ in range(200):
            deep = {"nested": deep}
        t0 = time.time()
        assert classify_terminal_kind(deep) == "non_terminal"
        elapsed = time.time() - t0
        # Prefilter should make this near-instant (< 0.01s), not minutes
        assert elapsed < 1.0, f"classify_terminal_kind took {elapsed:.2f}s on deep dict"

    def test_extra_keys_beyond_terminal_shape(self):
        """A dict with terminal keys PLUS extra keys is non_terminal."""
        almost_recurrence = {"closure_detected": True, "final_result": 42, "tau_step": 1, "extra": True}
        assert classify_terminal_kind(almost_recurrence) == "non_terminal"

    def test_subset_of_terminal_keys(self):
        """A dict with only some terminal keys is non_terminal."""
        partial = {"closure_detected": True, "final_result": 42}
        assert classify_terminal_kind(partial) == "non_terminal"

    def test_empty_dict_is_non_terminal(self):
        assert classify_terminal_kind({}) == "non_terminal"

    def test_unrelated_keys_are_non_terminal(self):
        assert classify_terminal_kind({"foo": 1, "bar": 2}) == "non_terminal"


# ===========================================================================
# Test 10: Source lock — terminal_classification.js does NOT import main.js
# ===========================================================================

class TestNoMainJsImport:
    def test_no_main_import(self):
        """terminal_classification.js must not import cli/main.js (side effects)."""
        source = (JS_CORE_DIR / "terminal_classification.js").read_text(encoding="utf-8")
        assert "main" not in source.lower() or "main.js" not in source, (
            "terminal_classification.js must not import main.js (triggers self-tests)"
        )
        # More specific: no require path containing 'main'
        requires = re.findall(r"require\(['\"]([^'\"]+)['\"]\)", source)
        for req in requires:
            assert "main" not in req, f"Forbidden import of main.js: require('{req}')"
