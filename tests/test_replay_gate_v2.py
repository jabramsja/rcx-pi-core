"""
v2 Trace Observability and Execution Gate

Validates that v2 trace events are deterministic and canonical.
- Observability: reduction.stall, reduction.applied, reduction.normal (RCX_TRACE_V2=1)
- Execution: execution.stall, execution.fix, execution.fixed (RCX_EXECUTION_V0=1)

This gate is ADDITIVE and does not affect v1 gates.
"""

from pathlib import Path
import subprocess
import os


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_v2_fixtures_are_canonical() -> None:
    """
    All v2 fixtures must be in canonical form.
    This ensures v2 replay is deterministic.
    """
    root = _repo_root()
    fixtures_dir = root / "tests" / "fixtures" / "traces_v2"
    fixtures = sorted(fixtures_dir.glob("*.jsonl"))
    assert fixtures, f"No v2 fixtures found in {fixtures_dir}"

    for fixture in fixtures:
        result = subprocess.run(
            ["python3", "-m", "rcx_pi.rcx_cli", "replay", "--trace", str(fixture), "--check-canon"],
            cwd=str(root),
            env={**os.environ, "PYTHONHASHSEED": "0"},
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"v2 fixture {fixture.name} is not canonical:\n{result.stderr}"


def test_v2_observer_emits_when_enabled() -> None:
    """
    When RCX_TRACE_V2=1, observer emits events.
    When disabled (default), observer is a no-op.
    """
    from rcx_pi.trace_canon import TraceObserver

    # Disabled by default (no env var set)
    obs_disabled = TraceObserver(enabled=False)
    obs_disabled.stall("test")
    assert obs_disabled.get_events() == [], "Observer should not emit when disabled"

    # Enabled explicitly
    obs_enabled = TraceObserver(enabled=True)
    obs_enabled.stall("test")
    events = obs_enabled.get_events()
    assert len(events) == 1, "Observer should emit when enabled"
    assert events[0]["type"] == "reduction.stall"
    assert events[0]["v"] == 2


def test_execution_engine_stall_fix_cycle() -> None:
    """
    ExecutionEngine tracks stall/fix state transitions.
    Feature flag: RCX_EXECUTION_V0=1
    """
    from rcx_pi.trace_canon import ExecutionEngine, ExecutionStatus, value_hash

    # Disabled by default
    eng_disabled = ExecutionEngine(enabled=False)
    eng_disabled.stall("test", {"foo": "bar"})
    assert eng_disabled.get_events() == [], "Engine should not emit when disabled"
    assert eng_disabled.status == ExecutionStatus.ACTIVE, "Status unchanged when disabled"

    # Enabled explicitly
    eng = ExecutionEngine(enabled=True)
    assert eng.status == ExecutionStatus.ACTIVE

    # Stall
    test_value = {"op": "add", "a": 0, "b": 1}
    eng.stall("add.succ", test_value)
    assert eng.status == ExecutionStatus.STALLED
    assert eng.is_stalled

    events = eng.get_events()
    assert len(events) == 1
    assert events[0]["type"] == "execution.stall"
    assert events[0]["v"] == 2
    assert events[0]["mu"]["pattern_id"] == "add.succ"
    assert events[0]["mu"]["value_hash"] == value_hash(test_value)

    # Fix (validate target hash)
    target_hash = value_hash(test_value)
    result = eng.fix("add.zero", target_hash)
    assert result is True

    # Fixed (confirm and transition back to active)
    new_value = {"result": 1}
    eng.fixed("add.zero", target_hash, new_value)
    assert eng.status == ExecutionStatus.ACTIVE
    assert not eng.is_stalled

    events = eng.get_events()
    assert len(events) == 2
    assert events[1]["type"] == "execution.fixed"
    assert events[1]["t"] == "add.zero"
    assert events[1]["mu"]["before_hash"] == target_hash
    assert events[1]["mu"]["after_hash"] == value_hash(new_value)


def test_execution_engine_error_conditions() -> None:
    """
    ExecutionEngine enforces state machine invariants.
    """
    from rcx_pi.trace_canon import ExecutionEngine, value_hash
    import pytest

    eng = ExecutionEngine(enabled=True)

    # Cannot fix when not stalled
    with pytest.raises(RuntimeError, match="Cannot fix.*expected STALLED"):
        eng.fix("rule", "hash")

    # Cannot confirm fix when not stalled
    with pytest.raises(RuntimeError, match="Cannot confirm fix.*expected STALLED"):
        eng.fixed("rule", "hash", {})

    # Stall, then try to stall again
    eng.stall("pattern", {"a": 1})
    with pytest.raises(RuntimeError, match="Cannot stall.*expected ACTIVE"):
        eng.stall("pattern2", {"b": 2})

    # Fix with wrong hash
    wrong_hash = "wrong_hash_value"
    with pytest.raises(RuntimeError, match="Fix target mismatch"):
        eng.fix("rule", wrong_hash)


def test_value_hash_deterministic() -> None:
    """
    value_hash produces deterministic hashes for canonical JSON.
    """
    from rcx_pi.trace_canon import value_hash

    # Same value = same hash
    v1 = {"b": 2, "a": 1}
    v2 = {"a": 1, "b": 2}
    assert value_hash(v1) == value_hash(v2), "Hash should be key-order independent"

    # Different values = different hashes
    v3 = {"a": 1, "b": 3}
    assert value_hash(v1) != value_hash(v3)

    # Primitives work
    assert value_hash(42) == value_hash(42)
    assert value_hash("test") == value_hash("test")
    assert value_hash(None) == value_hash(None)


def test_execution_engine_integration_with_pattern_matching() -> None:
    """
    ExecutionEngine integrates with PatternMatcher for stall tracking.
    When pattern match fails and execution_engine is provided, stall() is called.
    """
    from rcx_pi.trace_canon import ExecutionEngine, ExecutionStatus
    from rcx_pi.reduction.pattern_matching import PatternMatcher, PROJECTION
    from rcx_pi.core.motif import Motif, μ

    # Without execution engine - no state tracking
    pm_no_engine = PatternMatcher()
    # Create a projection that won't match
    proj = μ(PROJECTION, μ(μ()), μ())  # pattern: μ(μ()), body: μ()
    value = μ(μ(μ()))  # different structure, won't match
    result = pm_no_engine.apply_projection(proj, value)
    assert result is value, "Value should be returned unchanged on mismatch"

    # With execution engine - stall tracking enabled
    engine = ExecutionEngine(enabled=True)
    pm_with_engine = PatternMatcher(execution_engine=engine)

    # Same projection/value that won't match
    result = pm_with_engine.apply_projection(proj, value)
    assert result is value, "Value should still be returned unchanged"
    assert engine.status == ExecutionStatus.STALLED, "Engine should be stalled after pattern mismatch"
    assert engine.is_stalled

    # Verify stall event was emitted
    events = engine.get_events()
    assert len(events) == 1
    assert events[0]["type"] == "execution.stall"
    assert events[0]["mu"]["pattern_id"] == "projection.pattern_mismatch"


# --- Negative tests for replay validation (NOW-C) ---


def test_replay_validation_rejects_fix_without_stall() -> None:
    """
    Replay validation must HALT_ERR if execution.fix appears without prior stall.
    """
    from rcx_pi.replay_cli import _validate_v2_execution_sequence
    import pytest

    # execution.fix without preceding execution.stall
    bad_trace = [
        {"v": 2, "type": "execution.fix", "i": 0, "t": "rule", "mu": {"target_hash": "abc123"}},
    ]
    with pytest.raises(ValueError, match="fix without stall"):
        _validate_v2_execution_sequence(bad_trace)


def test_replay_validation_rejects_fixed_without_stall() -> None:
    """
    Replay validation must HALT_ERR if execution.fixed appears without prior stall.
    """
    from rcx_pi.replay_cli import _validate_v2_execution_sequence
    import pytest

    # execution.fixed without preceding execution.stall
    bad_trace = [
        {"v": 2, "type": "execution.fixed", "i": 0, "t": "rule", "mu": {"before_hash": "abc", "after_hash": "def"}},
    ]
    with pytest.raises(ValueError, match="fixed without stall"):
        _validate_v2_execution_sequence(bad_trace)


def test_replay_validation_rejects_mismatched_fix_hash() -> None:
    """
    Replay validation must HALT_ERR if execution.fix target_hash doesn't match stall value_hash.
    """
    from rcx_pi.replay_cli import _validate_v2_execution_sequence
    import pytest

    # execution.fix with wrong target_hash
    bad_trace = [
        {"v": 2, "type": "execution.stall", "i": 0, "mu": {"pattern_id": "p1", "value_hash": "correct_hash"}},
        {"v": 2, "type": "execution.fix", "i": 1, "t": "rule", "mu": {"target_hash": "wrong_hash"}},
    ]
    with pytest.raises(ValueError, match="target_hash mismatch"):
        _validate_v2_execution_sequence(bad_trace)


def test_replay_validation_rejects_mismatched_fixed_hash() -> None:
    """
    Replay validation must HALT_ERR if execution.fixed before_hash doesn't match stall value_hash.
    """
    from rcx_pi.replay_cli import _validate_v2_execution_sequence
    import pytest

    # execution.fixed with wrong before_hash
    bad_trace = [
        {"v": 2, "type": "execution.stall", "i": 0, "mu": {"pattern_id": "p1", "value_hash": "correct_hash"}},
        {"v": 2, "type": "execution.fixed", "i": 1, "t": "rule", "mu": {"before_hash": "wrong_hash", "after_hash": "new"}},
    ]
    with pytest.raises(ValueError, match="before_hash mismatch"):
        _validate_v2_execution_sequence(bad_trace)


def test_replay_validation_rejects_double_stall() -> None:
    """
    Replay validation must HALT_ERR if execution.stall appears while already stalled.
    """
    from rcx_pi.replay_cli import _validate_v2_execution_sequence
    import pytest

    # Two stalls without intervening fixed
    bad_trace = [
        {"v": 2, "type": "execution.stall", "i": 0, "mu": {"pattern_id": "p1", "value_hash": "hash1"}},
        {"v": 2, "type": "execution.stall", "i": 1, "mu": {"pattern_id": "p2", "value_hash": "hash2"}},
    ]
    with pytest.raises(ValueError, match="double stall"):
        _validate_v2_execution_sequence(bad_trace)


def test_replay_validation_accepts_stall_at_trace_end() -> None:
    """
    Replay validation must accept stall without fix at trace end (normal form termination).
    """
    from rcx_pi.replay_cli import _validate_v2_execution_sequence

    # Stall at end of trace = normal form, should NOT raise
    valid_trace = [
        {"v": 2, "type": "execution.stall", "i": 0, "mu": {"pattern_id": "p1", "value_hash": "hash1"}},
    ]
    # Should not raise
    _validate_v2_execution_sequence(valid_trace)


def test_replay_validation_accepts_valid_stall_fix_cycle() -> None:
    """
    Replay validation must accept valid stall → fixed sequence.
    """
    from rcx_pi.replay_cli import _validate_v2_execution_sequence

    # Valid cycle: stall → fixed (fix is optional)
    valid_trace = [
        {"v": 2, "type": "execution.stall", "i": 0, "mu": {"pattern_id": "p1", "value_hash": "abc123"}},
        {"v": 2, "type": "execution.fixed", "i": 1, "t": "rule", "mu": {"before_hash": "abc123", "after_hash": "def456"}},
    ]
    # Should not raise
    _validate_v2_execution_sequence(valid_trace)


# --- Record Mode v0 Tests ---


def test_record_mode_stall_then_fix() -> None:
    """
    Record mode: PatternMatcher emits execution.stall on mismatch,
    then execution.fixed when a later pattern matches the same value.

    This tests the inverse of replay: actual reduction → trace.
    """
    from rcx_pi.trace_canon import ExecutionEngine, ExecutionStatus, value_hash
    from rcx_pi.reduction.pattern_matching import (
        PatternMatcher,
        PROJECTION,
        PATTERN_VAR_MARKER,
        _motif_to_json,
    )
    from rcx_pi.core.motif import Motif, μ

    engine = ExecutionEngine(enabled=True)
    pm = PatternMatcher(execution_engine=engine)

    # Value: μ(μ())
    value = μ(μ())
    value_repr = _motif_to_json(value)
    value_h = value_hash(value_repr)

    # Projection 1: pattern that won't match (expects μ(μ(μ())))
    non_matching_pattern = μ(μ(μ()))
    proj_fail = μ(PROJECTION, non_matching_pattern, μ())

    # Apply projection that fails → stall
    result1 = pm.apply_projection(proj_fail, value)
    assert result1 is value, "Value unchanged on mismatch"
    assert engine.is_stalled, "Engine should be stalled"
    assert engine._current_value_hash == value_h

    # Projection 2: pattern that matches (expects μ(X)) with variable X
    var_x = μ(PATTERN_VAR_MARKER, μ())  # pattern variable
    matching_pattern = μ(var_x)  # matches μ(anything)
    proj_match = μ(PROJECTION, matching_pattern, μ())  # body = μ()

    # Apply projection that matches → fixed
    result2 = pm.apply_projection(proj_match, value)
    assert result2.structurally_equal(μ()), "Should transform to μ()"
    assert not engine.is_stalled, "Engine should be active after fix"
    assert engine.status == ExecutionStatus.ACTIVE

    # Verify events
    events = engine.get_events()
    assert len(events) == 2, f"Expected 2 events, got {len(events)}"

    # Event 0: execution.stall
    assert events[0]["type"] == "execution.stall"
    assert events[0]["mu"]["pattern_id"] == "projection.pattern_mismatch"
    assert events[0]["mu"]["value_hash"] == value_h

    # Event 1: execution.fixed
    assert events[1]["type"] == "execution.fixed"
    assert events[1]["t"] == "projection.match"
    assert events[1]["mu"]["before_hash"] == value_h
    result_repr = _motif_to_json(μ())
    assert events[1]["mu"]["after_hash"] == value_hash(result_repr)


def test_record_mode_no_fixed_without_stall() -> None:
    """
    Record mode: execution.fixed is NOT emitted if there was no prior stall.
    Normal reductions (pattern matches on first try) do not emit fixed.
    """
    from rcx_pi.trace_canon import ExecutionEngine
    from rcx_pi.reduction.pattern_matching import (
        PatternMatcher,
        PROJECTION,
        PATTERN_VAR_MARKER,
    )
    from rcx_pi.core.motif import μ

    engine = ExecutionEngine(enabled=True)
    pm = PatternMatcher(execution_engine=engine)

    # Value: μ(μ())
    value = μ(μ())

    # Projection that matches immediately (no stall first)
    var_x = μ(PATTERN_VAR_MARKER, μ())
    matching_pattern = μ(var_x)
    proj = μ(PROJECTION, matching_pattern, μ())

    # Apply - matches first time, no stall
    result = pm.apply_projection(proj, value)
    assert result.structurally_equal(μ())

    # No events should be emitted - no stall, so no fixed
    events = engine.get_events()
    assert len(events) == 0, f"Expected 0 events (no stall), got {len(events)}: {events}"


def test_record_mode_fixture_matches_generated_trace() -> None:
    """
    Record mode: generated trace matches the golden fixture.
    This verifies determinism: same input → same trace.
    """
    from pathlib import Path
    import json
    from rcx_pi.trace_canon import ExecutionEngine, value_hash, canon_event_json
    from rcx_pi.reduction.pattern_matching import (
        PatternMatcher,
        PROJECTION,
        PATTERN_VAR_MARKER,
        _motif_to_json,
    )
    from rcx_pi.core.motif import μ

    engine = ExecutionEngine(enabled=True)
    pm = PatternMatcher(execution_engine=engine)

    # Reproduce the exact scenario from the fixture
    value = μ(μ())

    # First: mismatch → stall
    non_matching_pattern = μ(μ(μ()))
    proj_fail = μ(PROJECTION, non_matching_pattern, μ())
    pm.apply_projection(proj_fail, value)

    # Second: match → fixed
    var_x = μ(PATTERN_VAR_MARKER, μ())
    matching_pattern = μ(var_x)
    proj_match = μ(PROJECTION, matching_pattern, μ())
    pm.apply_projection(proj_match, value)

    # Serialize events to canonical JSONL
    events = engine.get_events()
    generated = "".join(canon_event_json(ev) + "\n" for ev in events)

    # Load fixture
    fixture_path = Path(__file__).parent / "fixtures" / "traces_v2" / "record_mode.v2.jsonl"
    expected = fixture_path.read_text(encoding="utf-8")

    assert generated == expected, f"Generated trace differs from fixture:\nGenerated:\n{generated}\nExpected:\n{expected}"


def test_record_mode_replay_validates() -> None:
    """
    Record mode fixture passes replay validation.
    """
    root = _repo_root()
    fixture = root / "tests" / "fixtures" / "traces_v2" / "record_mode.v2.jsonl"

    result = subprocess.run(
        ["python3", "-m", "rcx_pi.rcx_cli", "replay", "--trace", str(fixture), "--check-canon"],
        cwd=str(root),
        env={**os.environ, "PYTHONHASHSEED": "0"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Record mode fixture failed replay validation:\n{result.stderr}"
