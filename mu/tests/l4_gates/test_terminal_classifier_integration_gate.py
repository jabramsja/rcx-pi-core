"""L4 gate: Terminal classifier runtime integration (Wave 19).

Proves that _is_terminal_shape / _is_engine_terminal (Python) and
isTerminalShape / isEngineTerminal (JS) delegate to classify_terminal_kind /
classifyTerminalKind respectively — eliminating duplicate key-set logic.

Source-lock tests verify function bodies contain classifier calls and no
direct frozenset/setsEqual comparisons.  Behavioral tests verify the
refactored predicates produce correct results.
"""
from __future__ import annotations

import inspect
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT

from rcx_pi.selfhost.step_mu import (
    TERMINAL_KINDS,
    _is_terminal_shape,  # ANTICHEAT_OK: gate tests verify runtime predicate delegation
    classify_terminal_kind,
)
from rcx_pi.selfhost.engine_pipeline import (
    ENGINE_EXIT_REASONS,
    _is_engine_terminal,  # ANTICHEAT_OK: gate tests verify runtime predicate delegation
)

# ---------------------------------------------------------------------------
# Python source lock
# ---------------------------------------------------------------------------

STEP_MU_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"
ENGINE_PIPELINE_PATH = REPO_ROOT / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "engine_pipeline.py"
EVAL_STEP_JS_PATH = REPO_ROOT / "mu" / "host" / "js" / "eval_step.js"


def _read_all_js_source() -> str:
    """Read all JS module files from mu/host/js/ recursively."""
    js_dir = REPO_ROOT / "mu" / "host" / "js"
    parts = []
    for f in sorted(js_dir.rglob("*.js")):
        parts.append(f.read_text())
    return "\n".join(parts)


def _get_python_function_body(source_path: Path, func_name: str) -> str:
    """Extract the body of a Python function from source."""
    source = source_path.read_text()
    # Find the function definition line
    pattern = re.compile(rf"^def {func_name}\b.*?:\n(.*?)(?=\ndef |\nclass |\Z)", re.MULTILINE | re.DOTALL)
    match = pattern.search(source)
    assert match, f"Function {func_name} not found in {source_path}"
    return match.group(1)


def _get_js_function_body(source_path: Path, func_name: str) -> str:
    """Extract the body of a JS function from all JS module sources."""
    source = _read_all_js_source()
    # Find function definition
    pattern = re.compile(rf"function {func_name}\b.*?\{{(.*?)\n\}}", re.DOTALL)
    match = pattern.search(source)
    assert match, f"Function {func_name} not found in {source_path}"
    return match.group(1)


class TestClassifierUsedByRuntimePredicates:
    """Source-lock: runtime predicates must delegate to classifier."""

    def test_python_is_terminal_shape_calls_classifier(self):
        body = _get_python_function_body(STEP_MU_PATH, "_is_terminal_shape")
        assert "classify_terminal_kind" in body, \
            "_is_terminal_shape must call classify_terminal_kind"

    def test_python_is_terminal_shape_no_direct_frozenset(self):
        body = _get_python_function_body(STEP_MU_PATH, "_is_terminal_shape")
        assert "frozenset" not in body, \
            "_is_terminal_shape must not use direct frozenset comparison"

    def test_python_is_engine_terminal_calls_classifier(self):
        body = _get_python_function_body(ENGINE_PIPELINE_PATH, "_is_engine_terminal")
        assert "classify_terminal_kind" in body, \
            "_is_engine_terminal must call classify_terminal_kind"

    def test_python_is_engine_terminal_no_direct_frozenset(self):
        body = _get_python_function_body(ENGINE_PIPELINE_PATH, "_is_engine_terminal")
        assert "frozenset" not in body, \
            "_is_engine_terminal must not use direct frozenset comparison"

    def test_js_isTerminalShape_calls_classifier(self):
        body = _get_js_function_body(EVAL_STEP_JS_PATH, "isTerminalShape")
        assert "classifyTerminalKind" in body, \
            "isTerminalShape must call classifyTerminalKind"

    def test_js_isTerminalShape_no_direct_setsEqual(self):
        body = _get_js_function_body(EVAL_STEP_JS_PATH, "isTerminalShape")
        assert "setsEqual" not in body, \
            "isTerminalShape must not use direct setsEqual comparison"

    def test_js_isEngineTerminal_calls_classifier(self):
        body = _get_js_function_body(EVAL_STEP_JS_PATH, "isEngineTerminal")
        assert "classifyTerminalKind" in body, \
            "isEngineTerminal must call classifyTerminalKind"

    def test_js_isEngineTerminal_no_direct_setsEqual(self):
        body = _get_js_function_body(EVAL_STEP_JS_PATH, "isEngineTerminal")
        assert "setsEqual" not in body, \
            "isEngineTerminal must not use direct setsEqual comparison"


class TestBehavioralParityUnchanged:
    """Behavioral tests: refactored predicates produce correct results."""

    def test_recurrence_terminal_detected(self):
        value = {"closure_detected": True, "final_result": 42, "tau_step": 3}
        assert _is_terminal_shape(value) is True
        assert classify_terminal_kind(value) == "recurrence_terminal"

    def test_exhaustion_terminal_detected(self):
        value = {"action": "freeze", "exhaustion_detected": True,
                 "frozen": [], "operator_to_freeze": "+"}
        assert _is_terminal_shape(value) is True
        assert classify_terminal_kind(value) == "exhaustion_terminal"

    def test_engine_terminal_detected(self):
        value = {"value": 1, "closure_detected": True, "tau_step": 3,
                 "exhaustion_detected": False, "operator_frozen": None,
                 "frozen_set": [], "action": "none", "stall": False}
        assert _is_engine_terminal(value) is True
        assert classify_terminal_kind(value) == "engine_terminal"

    def test_non_terminal_rejected_by_is_terminal_shape(self):
        assert _is_terminal_shape({"foo": 1}) is False
        assert _is_terminal_shape(42) is False
        assert _is_terminal_shape(None) is False
        assert _is_terminal_shape([1, 2]) is False

    def test_non_terminal_rejected_by_is_engine_terminal(self):
        assert _is_engine_terminal({"foo": 1}) is False
        assert _is_engine_terminal(42) is False
        assert _is_engine_terminal(None) is False

    def test_kernel_done_not_confused_with_terminal_shape(self):
        """kernel_done has higher priority in classifier but is not a terminal shape."""
        value = {"_mode": "done", "_result": 42, "_stall": False}
        assert _is_terminal_shape(value) is False
        assert _is_engine_terminal(value) is False
        assert classify_terminal_kind(value) == "kernel_done"

    def test_engine_terminal_not_confused_with_terminal_shape(self):
        """Engine terminal is detected by _is_engine_terminal, not _is_terminal_shape."""
        value = {"value": 1, "closure_detected": True, "tau_step": 3,
                 "exhaustion_detected": False, "operator_frozen": None,
                 "frozen_set": [], "action": "none", "stall": False}
        assert _is_terminal_shape(value) is False
        assert _is_engine_terminal(value) is True

    def test_partial_keys_not_terminal(self):
        """Subset of terminal keys should not match."""
        partial = {"closure_detected": True, "final_result": 42}  # missing tau_step
        assert _is_terminal_shape(partial) is False
        assert classify_terminal_kind(partial) == "non_terminal"

    def test_superset_keys_not_terminal(self):
        """Superset of terminal keys should not match."""
        superset = {"closure_detected": True, "final_result": 42,
                    "tau_step": 3, "extra_key": True}
        assert _is_terminal_shape(superset) is False
        assert classify_terminal_kind(superset) == "non_terminal"


class TestNoRegressionToExistingGates:
    """Behavioral regression: each test exercises a production entrypoint from its gate domain."""

    def test_classification_parity_gate_behavioral(self):
        """Parity gate domain: classifier produces valid terminal kinds."""
        value = {"closure_detected": True, "final_result": 42, "tau_step": 3}
        kind = classify_terminal_kind(value)
        assert kind in TERMINAL_KINDS, f"Unknown terminal kind: {kind}"

    def test_engine_exit_reason_gate_behavioral(self):
        """Exit reason gate domain: ENGINE_EXIT_REASONS has expected members."""
        expected = {"closure", "exhaustion", "stall", "completed"}
        assert ENGINE_EXIT_REASONS == frozenset(expected)

    def test_engine_terminal_event_gate_behavioral(self):
        """Terminal event gate domain: only engine terminals trigger observer events."""
        engine = {"value": 1, "closure_detected": True, "tau_step": 3,
                  "exhaustion_detected": False, "operator_frozen": None,
                  "frozen_set": [], "action": "none", "stall": False}
        assert _is_engine_terminal(engine) is True
        recurrence = {"closure_detected": True, "final_result": 42, "tau_step": 3}
        assert _is_engine_terminal(recurrence) is False

    def test_js_parity_suite_passes(self):
        """JS substrate still passes all its internal tests."""
        result = subprocess.run(
            ["node", str(EVAL_STEP_JS_PATH)],
            capture_output=True, text=True, timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, f"JS suite failed:\n{result.stderr}"
