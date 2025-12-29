#!/usr/bin/env python3
"""
Unified RCX-π test runner.

Right now this is intentionally boring: it just runs pytest -vv
so that the *single source of truth* for test status is pytest.
"""

import subprocess
import sys


def main() -> int:
    print("=== RCX-π: running full pytest suite ===")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-vv"],
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())