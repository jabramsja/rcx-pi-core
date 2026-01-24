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
