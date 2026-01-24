#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import sys

USAGE = "usage: freeze_core_mu.py <baseline.mu> <mutated.mu>"

FROZEN_LHS = [
    r"^\[omega,.*\]\s*->",
    r"^\[expand,.*\]\s*->",
    r"^\[collapse\]\s*->",
]


def extract_frozen_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines(True):
        s = line.strip()
        if not s or s.startswith("#") or "->" not in s:
            continue
        lhs = s.split("->", 1)[0].strip()
        for pat in FROZEN_LHS:
            if re.match(pat, s):
                out[lhs] = line
                break
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print(USAGE, file=sys.stderr)
        return 2

    base = Path(sys.argv[1])
    mut = Path(sys.argv[2])

    bt = base.read_text(encoding="utf-8", errors="replace")
    mt = mut.read_text(encoding="utf-8", errors="replace")

    base_frozen = extract_frozen_lines(bt)

    new_lines = []
    replaced = 0
    kept = 0

    for line in mt.splitlines(True):
        s = line.strip()
        if not s or s.startswith("#") or "->" not in s:
            new_lines.append(line)
            continue

        lhs = s.split("->", 1)[0].strip()
        if lhs in base_frozen:
            new_lines.append(base_frozen[lhs])
            replaced += 1
        else:
            new_lines.append(line)
            kept += 1

    # Ensure any missing frozen rules are present (append at end)
    existing_lhs = set()
    for line in new_lines:
        s = line.strip()
        if not s or s.startswith("#") or "->" not in s:
            continue
        existing_lhs.add(s.split("->", 1)[0].strip())

    missing = [lhs for lhs in base_frozen.keys() if lhs not in existing_lhs]
    if missing:
        new_lines.append("\n# --- restored frozen core rules from baseline ---\n")
        for lhs in missing:
            new_lines.append(base_frozen[lhs])

    mut.write_text("".join(new_lines), encoding="utf-8")
    print(
        f"OK: froze core rules into {mut} (replaced={replaced}, appended_missing={len(missing)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
