#!/usr/bin/env python3
"""
RCX CLI Smoke Test

This script verifies that all published RCX CLIs:
- resolve in PATH or via python -m
- execute successfully
- emit valid JSON where expected

It is intentionally boring and deterministic.
"""

from __future__ import annotations
import json
import subprocess
import sys
from typing import List

def run(cmd: List[str]) -> str:
    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(cmd)}\n"
            f"stderr:\n{p.stderr}"
        )
    return p.stdout.strip()

def must_be_json(label: str, s: str):
    try:
        json.loads(s)
    except Exception as e:
        raise RuntimeError(f"{label} did not emit valid JSON:\n{s}") from e

def main() -> int:
    print("== RCX CLI smoke test ==")

    # 1) Umbrella help
    out = run(["rcx-cli", "--help"])
    assert "RCX umbrella CLI" in out
    print("[OK] rcx-cli --help")

    # 2) Program descriptor schema
    out = run(["rcx-cli", "program", "describe", "--schema"])
    assert "rcx-program-descriptor" in out
    print("[OK] program describe --schema")

    # 3) Program run schema
    out = run(["rcx-cli", "program", "run", "--schema"])
    assert "rcx-program-run" in out
    print("[OK] program run --schema")

    # 4) World trace schema
    out = run(["rcx-cli", "world", "trace", "--schema"])
    assert "rcx-world-trace" in out
    print("[OK] world trace --schema")

    # 5) Run a real program
    out = run(["rcx-cli", "program", "run", "succ-list", "[1,2,3]"])
    must_be_json("program run", out)
    data = json.loads(out)
    assert data["output"] == [2,3,4]
    print("[OK] program run succ-list")

    # 6) Run a real world trace
    out = run([
        "rcx-cli", "trace", "pingpong", "ping",
        "--max-steps", "6"
    ])
    must_be_json("world trace", out)
    data = json.loads(out)
    assert data["orbit"]["period"] == 2
    print("[OK] world trace pingpong")

    print("== ALL CLI SMOKE CHECKS PASSED ==")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
