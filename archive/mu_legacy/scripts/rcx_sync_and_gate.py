#!/usr/bin/env python3
from __future__ import annotations

import os, subprocess, sys
from pathlib import Path

BASE = os.environ.get("RCX_BASE", "dev")
GATES = [
    ["./scripts/check_orbit_all.sh"],
]


def run(cmd: list[str], check: bool = True) -> int:
    print("+", " ".join(cmd))
    p = subprocess.run(cmd, text=True)
    if check and p.returncode != 0:
        raise SystemExit(p.returncode)
    return p.returncode


def out(cmd: list[str]) -> str:
    print("+", " ".join(cmd))
    return subprocess.check_output(cmd, text=True).strip()


def main() -> None:
    root = out(["git", "rev-parse", "--show-toplevel"])
    os.chdir(root)

    run(["git", "checkout", BASE])
    run(["git", "pull", "--ff-only"])

    for gate in GATES:
        run(gate)

    print(f"OK: {BASE} synced; deterministic gates green")


if __name__ == "__main__":
    main()
