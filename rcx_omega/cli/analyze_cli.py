#!/usr/bin/env python3
"""
Analyze CLI.

Consumes JSON from stdin. Accepts BOTH:
- trace_cli payloads (with steps[])
- omega_cli payloads (summary-only, no steps)

Must never crash on shape differences.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

from rcx_omega.core.report_contract import detect_kind, extract_summary


def main() -> int:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.stderr.write("analyze_cli: empty stdin\n")
            return 1

        payload = json.loads(raw)

    except Exception as e:
        sys.stderr.write(f"analyze_cli: invalid JSON ({e})\n")
        return 1

    kind = detect_kind(payload).kind

    # ---- TRACE PAYLOAD -------------------------------------------------
    if kind == "trace":
        steps = payload.get("steps", [])
        if not isinstance(steps, list):
            sys.stderr.write("analyze_cli: malformed trace payload\n")
            return 1

        sys.stdout.write("analyze: trace\n")
        sys.stdout.write(f"steps: {len(steps)}\n")
        # converged: last step has no deltas (best-effort)
        converged = False
        try:
            _steps = payload.get('steps') or []
            if _steps:
                _last = _steps[-1] if isinstance(_steps[-1], dict) else {}
                converged = (_last.get('delta_nodes') == 0) and (_last.get('delta_depth') == 0)
        except Exception:
            converged = False
        sys.stdout.write(f"converged: {str(converged).lower()}\n")

        stats = payload.get("stats")
        if isinstance(stats, dict):
            sys.stdout.write(f"stats: {stats}\n")

        sys.stdout.write("== Ω analyze ==\n")
        return 0

    # ---- OMEGA / SUMMARY PAYLOAD --------------------------------------
    summary = extract_summary(payload)

    sys.stdout.write("analyze: summary\n")

    classification = summary.get("classification")
    if isinstance(classification, dict):
        ctype = classification.get("type", "unknown")
        period = classification.get("period", "?")
        max_steps = classification.get("max_steps", "?")
        sys.stdout.write(
            f"classification: {ctype} period={period} max_steps={max_steps}\n"
        )

    stats = summary.get("stats")
    if isinstance(stats, dict):
        sys.stdout.write(f"stats: {stats}\n")

    sys.stdout.write("== Ω analyze ==\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
