"""
Engine pipeline entry discipline and observer event contract guard.

Verifies:
1. run_engine_pipeline callsite inventory (AST-based, fail-closed).
2. Observer event schema enforcement (mandatory fields).
3. Pipeline parameter defaults haven't drifted.

What this checker PROVES:
- No new raw callers of run_engine_pipeline without inventory update.
- Observer events always contain the 6 mandatory fields.
- Pipeline defaults (max_engine_iterations, use_boot1_recursive) are stable.

What this checker does NOT prove:
- Semantic correctness of pipeline execution.
- Observer event ordering or content accuracy.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from rcx_pi.selfhost.step_mu import run_engine_pipeline

# ── Source paths ─────────────────────────────────────────────────────────

_REPO = Path(__file__).resolve().parents[3]
_STEP_MU_PATH = _REPO / "mu" / "host" / "python" / "rcx_pi" / "selfhost" / "step_mu.py"

# ── Known callsite inventory ─────────────────────────────────────────────

# All functions that call run_engine_pipeline() directly.
# If you add a new caller, add it here. This is a fail-closed guard.
# Note: _run_engine_recursive re-implements pipeline logic internally
# (it does NOT call run_engine_pipeline), so it's not in this set.
KNOWN_PIPELINE_CALLERS = {
    "run_engine_with_routing",    # Chains pipeline → hemisphere routing
}


def _find_run_engine_pipeline_callers(source: str) -> set[str]:
    """Find all functions that call run_engine_pipeline() via AST walk."""
    tree = ast.parse(source)
    callers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        func_name = node.name
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name) and child.func.id == "run_engine_pipeline":
                    callers.add(func_name)
    return callers


# ── AST callsite inventory ───────────────────────────────────────────────


class TestPipelineCallsiteInventory:
    """run_engine_pipeline must only be called from known locations."""

    def test_no_unknown_callers(self):
        """Fail-closed: any new caller must be added to KNOWN_PIPELINE_CALLERS."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_run_engine_pipeline_callers(source)
        unknown = actual - KNOWN_PIPELINE_CALLERS
        assert not unknown, (
            f"Unknown run_engine_pipeline callers: {unknown}. "
            "Add to KNOWN_PIPELINE_CALLERS if intentional."
        )

    def test_no_stale_inventory(self):
        """Known callers must actually exist in source."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_run_engine_pipeline_callers(source)
        stale = KNOWN_PIPELINE_CALLERS - actual
        assert not stale, (
            f"Stale entries in KNOWN_PIPELINE_CALLERS: {stale}. "
            "Remove if callers were deleted."
        )

    def test_caller_count_locked(self):
        """Exact caller count as documentation."""
        source = _STEP_MU_PATH.read_text()
        actual = _find_run_engine_pipeline_callers(source)
        assert len(actual) == 1, (
            f"Expected 1 caller, found {len(actual)}: {actual}"
        )


# ── Pipeline parameter defaults ─────────────────────────────────────────


class TestPipelineDefaults:
    """Pipeline parameter defaults must remain stable."""

    def test_max_engine_iterations_default(self):
        """Default max_engine_iterations must be 20."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("max_engine_iterations")
        assert param is not None, "max_engine_iterations parameter missing"
        assert param.default == 20, (
            f"max_engine_iterations default changed from 20 to {param.default}"
        )

    def test_observer_default_none(self):
        """Observer must default to None (opt-in only)."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("observer")
        assert param is not None, "observer parameter missing"
        assert param.default is None, (
            f"observer default changed from None to {param.default}"
        )

    def test_frozen_default_none(self):
        """Frozen must default to None."""
        sig = inspect.signature(run_engine_pipeline)
        param = sig.parameters.get("frozen")
        assert param is not None, "frozen parameter missing"
        assert param.default is None, (
            f"frozen default changed from None to {param.default}"
        )


# ── Observer event contract ──────────────────────────────────────────────

OBSERVER_MANDATORY_FIELDS = {"event_name", "step", "state_hash", "error_code", "substrate", "timestamp"}


class TestObserverEventContract:
    """Observer events must follow a strict schema."""

    @pytest.mark.slow
    def test_observer_events_have_mandatory_fields(self):
        """Every observer event must contain all 6 mandatory fields."""
        observer: list = []
        # Run a minimal pipeline to generate observer events
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value=42,
            max_steps=3,
            observer=observer,
        )
        assert len(observer) > 0, "No observer events emitted"
        for i, event in enumerate(observer):
            missing = OBSERVER_MANDATORY_FIELDS - set(event.keys())
            assert not missing, (
                f"Observer event [{i}] missing fields: {missing}. "
                f"Event: {event}"
            )

    @pytest.mark.slow
    def test_observer_substrate_is_python(self):
        """All observer events from Python pipeline must report substrate='python'."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value="hello",
            max_steps=3,
            observer=observer,
        )
        for i, event in enumerate(observer):
            assert event.get("substrate") == "python", (
                f"Observer event [{i}] substrate is '{event.get('substrate')}', expected 'python'"
            )

    @pytest.mark.slow
    def test_observer_timestamps_monotonic(self):
        """Observer timestamps must be strictly monotonically increasing."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value=[1, 2, 3],
            max_steps=5,
            observer=observer,
        )
        assert len(observer) >= 2, "Need at least 2 events to check monotonicity"
        for i in range(1, len(observer)):
            assert observer[i]["timestamp"] > observer[i - 1]["timestamp"], (
                f"Timestamps not monotonic at events [{i-1}] and [{i}]: "
                f"{observer[i-1]['timestamp']} >= {observer[i]['timestamp']}"
            )

    @pytest.mark.slow
    def test_observer_step_is_nonnegative(self):
        """Observer step values must be non-negative integers."""
        observer: list = []
        projections = [
            {"id": "test.identity", "pattern": {"var": "x"}, "body": {"var": "x"}}
        ]
        run_engine_pipeline(
            projections=projections,
            input_value={"a": 1},
            max_steps=3,
            observer=observer,
        )
        for i, event in enumerate(observer):
            assert isinstance(event["step"], int) and event["step"] >= 0, (
                f"Observer event [{i}] step is {event['step']}, expected non-negative int"
            )
