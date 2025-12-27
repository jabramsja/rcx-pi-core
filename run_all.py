#!/usr/bin/env python3
"""
RCX-π test runner

Runs every test/demo in WorkingRCX and prints output clearly so Jeff can
paste results into ChatGPT to verify structural correctness.

Files auto-detected:
    example_*.py
    test_*.py
    demo_*.py
"""

import subprocess
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run_file(file: Path):
    print("\n" + "="*70)
    print(f">>> Running {file.name}")
    print("="*70)

    try:
        result = subprocess.run(
            ["python3", str(file)],
            capture_output=True,
            text=True,
            cwd=ROOT
        )
        
        # stdout
        if result.stdout.strip():
            print(result.stdout.rstrip())
        
        # stderr (highlighted if exists)
        if result.stderr.strip():
            print("\n[stderr]")
            print(result.stderr.rstrip())

        if result.returncode != 0:
            print(f"\n[ERROR] exit code {result.returncode}")
        else:
            print("[OK]")

    except Exception as e:
        print(f"[CRASH] {e}")


def main():
    print("\n=== RCX-π Full Test & Demo Runner ===\n")

    # All scripts matching test_, example_, demo_
    files = sorted([
        f for f in ROOT.iterdir()
        if f.suffix == ".py" and (
            f.name.startswith("test_") or
            f.name.startswith("example_") or
            f.name.startswith("demo_")
        ) and f.name != "run_all.py"
    ])

    if not files:
        print("No test/example/demo files found!")
        return

    for file in files:
        run_file(file)

    print("\n=== End of RCX-π test suite ===\n")


if __name__ == "__main__":
    main()