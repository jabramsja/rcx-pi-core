"""
Projection Coverage Tracking for RCX

Tracks which projections have been matched during test execution.
Helps ensure every projection is exercised by tests.

Usage:
    # Enable coverage tracking
    from rcx_pi.projection_coverage import coverage

    coverage.enable()

    # Run tests...

    # Get report
    report = coverage.report()
    print(report)

    # Or check in tests
    assert coverage.projection_hit("append.base")
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

# Global coverage state
_coverage_enabled = False
_coverage_data: dict[str, dict[str, Any]] = defaultdict(lambda: {
    "hits": 0,
    "last_input": None,
    "last_output": None,
})
_total_steps = 0
_total_matches = 0


def enable():
    """Enable coverage tracking."""
    global _coverage_enabled
    _coverage_enabled = True


def disable():
    """Disable coverage tracking."""
    global _coverage_enabled
    _coverage_enabled = False


def reset():
    """Reset all coverage data."""
    global _coverage_data, _total_steps, _total_matches
    _coverage_data = defaultdict(lambda: {
        "hits": 0,
        "last_input": None,
        "last_output": None,
    })
    _total_steps = 0
    _total_matches = 0


def is_enabled() -> bool:
    """Check if coverage tracking is enabled."""
    return _coverage_enabled


def record_step():
    """Record that a step was attempted."""
    global _total_steps
    if _coverage_enabled:
        _total_steps += 1


def record_match(projection_id: str, input_value: Any = None, output_value: Any = None):
    """
    Record a projection match.

    Args:
        projection_id: ID of the matched projection (from projection["id"] or generated).
        input_value: The input that matched (optional, for debugging).
        output_value: The output produced (optional, for debugging).
    """
    global _total_matches
    if _coverage_enabled:
        _coverage_data[projection_id]["hits"] += 1
        _coverage_data[projection_id]["last_input"] = input_value
        _coverage_data[projection_id]["last_output"] = output_value
        _total_matches += 1


def record_no_match(projection_id: str):
    """Record that a projection was tried but didn't match."""
    if _coverage_enabled:
        # Just ensure the projection is in the data (with 0 hits if never matched)
        _ = _coverage_data[projection_id]


def projection_hit(projection_id: str) -> bool:
    """Check if a projection was ever matched."""
    return _coverage_data[projection_id]["hits"] > 0


def projection_hits(projection_id: str) -> int:
    """Get the number of times a projection was matched."""
    return _coverage_data[projection_id]["hits"]


def get_unmatched() -> list[str]:
    """Get list of projection IDs that were tried but never matched."""
    return [pid for pid, data in _coverage_data.items() if data["hits"] == 0]


def get_matched() -> list[str]:
    """Get list of projection IDs that were matched at least once."""
    return [pid for pid, data in _coverage_data.items() if data["hits"] > 0]


def report() -> str:
    """Generate a human-readable coverage report."""
    lines = [
        "=" * 50,
        "       Projection Coverage Report",
        "=" * 50,
        "",
        f"Total steps:     {_total_steps}",
        f"Total matches:   {_total_matches}",
        f"Unique matched:  {len(get_matched())}",
        f"Never matched:   {len(get_unmatched())}",
        "",
    ]

    if _coverage_data:
        lines.append("Projection Hits:")
        lines.append("-" * 50)

        # Sort by hits (descending)
        sorted_projs = sorted(
            _coverage_data.items(),
            key=lambda x: (-x[1]["hits"], x[0])
        )

        for proj_id, data in sorted_projs:
            hits = data["hits"]
            status = "✓" if hits > 0 else "✗"
            lines.append(f"  {status} {proj_id}: {hits} hits")

    lines.append("")
    lines.append("=" * 50)

    # Summary
    total_projs = len(_coverage_data)
    matched = len(get_matched())
    if total_projs > 0:
        pct = (matched / total_projs) * 100
        lines.append(f"Coverage: {matched}/{total_projs} ({pct:.1f}%)")
    else:
        lines.append("Coverage: No projections tracked")

    lines.append("=" * 50)

    return "\n".join(lines)


def report_json() -> dict:
    """Generate a JSON-serializable coverage report."""
    return {
        "total_steps": _total_steps,
        "total_matches": _total_matches,
        "projections": {
            pid: {
                "hits": data["hits"],
                "matched": data["hits"] > 0,
            }
            for pid, data in _coverage_data.items()
        },
        "unmatched": get_unmatched(),
        "matched": get_matched(),
        "coverage_pct": (len(get_matched()) / len(_coverage_data) * 100) if _coverage_data else 0,
    }


# Convenience object for import
class _Coverage:
    enable = staticmethod(enable)
    disable = staticmethod(disable)
    reset = staticmethod(reset)
    is_enabled = staticmethod(is_enabled)
    record_step = staticmethod(record_step)
    record_match = staticmethod(record_match)
    record_no_match = staticmethod(record_no_match)
    projection_hit = staticmethod(projection_hit)
    projection_hits = staticmethod(projection_hits)
    get_unmatched = staticmethod(get_unmatched)
    get_matched = staticmethod(get_matched)
    report = staticmethod(report)
    report_json = staticmethod(report_json)


coverage = _Coverage()
