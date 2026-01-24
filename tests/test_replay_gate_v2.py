"""
v2 Trace Observability Gate

Validates that v2 trace events (reduction.stall, reduction.applied, reduction.normal)
are deterministic and canonical. This gate is ADDITIVE and does not affect v1 gates.

Feature flag: RCX_TRACE_V2=1 must be set to enable v2 event emission.
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
