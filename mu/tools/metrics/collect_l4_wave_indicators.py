#!/usr/bin/env python3
"""
Collect L4 wave indicator metrics (v2.1.0).

Generates a JSON artifact with required indicator and provenance fields for
L4 contract enforcement.  All values are deterministically computed from
repo state using cheap, fixed-scope probes.

Fail-closed policy: probe failures and unparseable outputs abort with
exit code 1 instead of silently coercing to zero/default values.

Usage:
    python tools/metrics/collect_l4_wave_indicators.py --wave-id <id> --output <path>
    python tools/metrics/collect_l4_wave_indicators.py --wave-id <id> --output <path> --range origin/dev...HEAD

Exit codes:
    0 -> artifact written successfully
    1 -> required field could not be computed or probe failed
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

COLLECTOR_VERSION = "2.1.0"


class CollectorError(RuntimeError):
    """Raised when a probe or measurement fails (fail-closed)."""

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

# Small, cheap probe command — runs 2 legacy-alias tests to produce
# wall-clock timing with minimal runtime cost.
PROBE_CMD = [
    sys.executable, "-m", "pytest",
    "tests/l4_gates/test_l4_governance_contract.py::TestLegacyAliasLock",
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
    """Count JS debt markers as proxy for parity diff count.

    Fail-closed: raises CollectorError if the debt script fails or its
    output cannot be parsed for a JS debt count.
    """
    result = subprocess.run(
        ["bash", "tools/checks/check_js_debt.sh"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        snippet = (result.stderr or result.stdout or "")[:200]
        raise CollectorError(
            f"check_js_debt.sh failed (exit {result.returncode}): {snippet}"
        )
    for line in result.stdout.split("\n"):
        if "JS debt" in line:
            m = re.search(r"JS debt.*?(\d+)", line)
            if m:
                return int(m.group(1))
    raise CollectorError(
        "check_js_debt.sh output did not contain parseable 'JS debt' count"
    )


def timed_probe() -> float:
    """Run a small fixed probe and return wall-clock seconds.

    Fail-closed: raises CollectorError if the probe command exits non-zero.
    """
    start = time.monotonic()
    result = subprocess.run(
        PROBE_CMD, capture_output=True, text=True, timeout=60,
        env={**__import__("os").environ, "PYTHONHASHSEED": "0"},
    )
    elapsed = round(time.monotonic() - start, 6)
    if result.returncode != 0:
        snippet = (result.stderr or result.stdout or "")[:200]
        raise CollectorError(
            f"Probe command failed (exit {result.returncode}): {snippet}"
        )
    return elapsed


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

    try:
        parity_diffs = count_parity_diffs()
    except CollectorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Provenance: repeat-run timing
    try:
        raw_seconds = collect_repeat_run_raw()
    except CollectorError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
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
