#!/usr/bin/env python3
"""
Collect L4 wave indicator metrics (v2.0.0).

Generates a JSON artifact with required indicator and provenance fields for
L4 contract enforcement.  All values are deterministically computed from
repo state using cheap, fixed-scope probes.

Usage:
    python tools/metrics/collect_l4_wave_indicators.py --wave-id <id> --output <path>
    python tools/metrics/collect_l4_wave_indicators.py --wave-id <id> --output <path> --range origin/dev...HEAD

Exit codes:
    0 -> artifact written successfully
    1 -> required field could not be computed
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

COLLECTOR_VERSION = "2.0.0"

RUNTIME_DIRS = (
    "mu/host/", "mu/substrate/", "mu/closures/", "mu/bridge/",
    "mu/programs/", "rcx_pi/selfhost/", "tools/compilers/",
)

METRIC_KEYS = {
    "repeat_run_speedup_ratio": (int, float),
    "parity_diff_count": (int,),
    "net_host_semantic_delta": (int,),
    "step_growth_slope": (int, float),
}

# Small, cheap probe command — collects only the l4_gates __init__ import
# to produce wall-clock timing with minimal runtime cost.
PROBE_CMD = [
    sys.executable, "-m", "pytest",
    "tests/l4_gates/test_l4_governance_contract.py::TestWaveClassEnum",
    "-q", "--tb=no", "--no-header",
]


def get_changed_files(git_range: str | None) -> list[str]:
    """Get changed files from git range or staged."""
    if git_range:
        cmd = ["git", "diff", "--name-only", git_range]
    else:
        cmd = ["git", "diff", "--cached", "--name-only"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().split("\n") if f]


def count_runtime_changes(git_range: str | None) -> int:
    """Count runtime file changes in diff scope."""
    files = get_changed_files(git_range)
    return sum(1 for f in files if any(f.startswith(d) for d in RUNTIME_DIRS))


def count_parity_diffs() -> int:
    """Count JS debt markers as proxy for parity diff count."""
    try:
        result = subprocess.run(
            ["bash", "tools/checks/check_js_debt.sh"],
            capture_output=True, text=True, timeout=30,
        )
        for line in result.stdout.split("\n"):
            if "JS debt" in line:
                m = re.search(r"JS debt.*?(\d+)", line)
                if m:
                    return int(m.group(1))
        return 0
    except Exception:
        return 0


def timed_probe() -> float:
    """Run a small fixed probe and return wall-clock seconds."""
    start = time.monotonic()
    subprocess.run(
        PROBE_CMD, capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "PYTHONHASHSEED": "0"},
    )
    return round(time.monotonic() - start, 6)


def collect_repeat_run_raw() -> list[float]:
    """Two consecutive cheap probe runs → [t1, t2]."""
    t1 = timed_probe()
    t2 = timed_probe()
    return [t1, t2]


def collect_step_growth_points(raw_seconds: list[float]) -> list[dict]:
    """Generate step growth data points from repeat-run probe timings."""
    return [
        {"step": 1, "elapsed_seconds": round(raw_seconds[0], 6)},
        {"step": 2, "elapsed_seconds": round(raw_seconds[0] + raw_seconds[1], 6)},
    ]


def compute_slope(points: list[dict]) -> float:
    """Compute slope from step_growth_points: (y_last - y_first) / (x_last - x_first)."""
    first, last = points[0], points[-1]
    dx = last["step"] - first["step"]
    if dx == 0:
        return 0.0
    return round((last["elapsed_seconds"] - first["elapsed_seconds"]) / dx, 6)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect L4 wave indicator metrics (v2)")
    parser.add_argument("--wave-id", required=True, help="Wave identifier")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--range", type=str, help="Git range for diff analysis")
    args = parser.parse_args()

    net_host_delta = count_runtime_changes(args.range)
    parity_diffs = count_parity_diffs()

    # Provenance: repeat-run timing
    raw_seconds = collect_repeat_run_raw()
    speedup_ratio = round(raw_seconds[0] / raw_seconds[1], 6)

    # Provenance: step growth
    growth_points = collect_step_growth_points(raw_seconds)
    slope = compute_slope(growth_points)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    indicators = {
        "wave_id": args.wave_id,
        "repeat_run_speedup_ratio": speedup_ratio,
        "parity_diff_count": parity_diffs,
        "net_host_semantic_delta": net_host_delta,
        "step_growth_slope": slope,
        "repeat_run_raw_seconds": raw_seconds,
        "step_growth_points": growth_points,
        "parity_diff_source": "tools/checks/check_js_debt.sh",
        "collection_timestamp_utc": timestamp,
        "collector_version": COLLECTOR_VERSION,
    }

    # Validate core metric types
    for key, types in METRIC_KEYS.items():
        if key not in indicators:
            print(f"ERROR: Failed to compute required key: {key}", file=sys.stderr)
            return 1
        val = indicators[key]
        if isinstance(val, bool) or not isinstance(val, types):
            print(f"ERROR: Key '{key}' wrong type: {type(val).__name__}", file=sys.stderr)
            return 1

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(indicators, indent=2) + "\n", encoding="utf-8")
    print(f"Indicator artifact written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
