#!/usr/bin/env python3
"""
Projection Coverage Report Tool

Run this after tests to see which projections were exercised.

Usage:
    # Run tests with coverage enabled
    PYTHONHASHSEED=0 RCX_PROJECTION_COVERAGE=1 pytest -q

    # Then view the report
    python tools/projection_coverage.py

Or use as a pytest plugin:
    pytest --projection-coverage
"""

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="Projection Coverage Report")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--check", type=float, default=0,
                        help="Exit 1 if coverage below threshold (0-100)")
    args = parser.parse_args()

    from rcx_pi.projection_coverage import coverage

    if args.json:
        print(json.dumps(coverage.report_json(), indent=2))
    else:
        print(coverage.report())

    if args.check > 0:
        report = coverage.report_json()
        if report["coverage_pct"] < args.check:
            print(f"\n❌ Coverage {report['coverage_pct']:.1f}% below threshold {args.check}%")
            sys.exit(1)
        else:
            print(f"\n✅ Coverage {report['coverage_pct']:.1f}% meets threshold {args.check}%")


if __name__ == "__main__":
    main()
