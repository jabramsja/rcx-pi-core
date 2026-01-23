#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

def sh(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise SystemExit(f"cmd failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout.strip()

def repo_root() -> Path:
    return Path(sh(["git", "rev-parse", "--show-toplevel"]))

def read_lines(p: Path) -> list[str]:
    return [x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

@dataclass(frozen=True)
class Bucket:
    name: str
    desc: str
    pred: Callable[[str], bool]

def main() -> None:
    root = repo_root()
    pack = root / "rcx_pack_minimal.txt"
    if not pack.exists():
        raise SystemExit("Missing rcx_pack_minimal.txt. Run: scripts/rcx_packlist.py --mode minimal")

    paths = read_lines(pack)

    buckets = [
        Bucket("Top-level", "Project entrypoints and task spine.", lambda p: p in ("README.md", "TASKS.md")),
        Bucket("CI / Gates", "Workflows + deterministic gate scripts.", lambda p: p.startswith(".github/workflows/") or p.startswith("scripts/check_") or p in ("scripts/green_gate.sh",)),
        Bucket("Schemas", "Canonical schema sources (docs/schemas) + legacy schema docs in docs/.", lambda p: p.startswith("docs/schemas/") or ("schema" in p and p.startswith("docs/"))),
        Bucket("Rust Core", "Rust core that emits/consumes orbit JSON and related artifacts.", lambda p: p.startswith("rcx_pi_rust/src/")),
        Bucket("Python Core (rcx_pi)", "Python core evaluator/program registry/worlds.", lambda p: p.startswith("rcx_pi/")),
        Bucket("Omega (rcx_omega)", "Omega/trace/analyze contracts and CLIs.", lambda p: p.startswith("rcx_omega/")),
        Bucket("Scripts", "Helper scripts for PR watching, sync, rehydrate, etc.", lambda p: p.startswith("scripts/") and not p.startswith("scripts/check_")),
        Bucket("Tests", "Smoke/contract tests that define behavior.", lambda p: p.startswith("scripts/tests/") or p.startswith("tests/")),
    ]

    grouped: dict[str, list[str]] = {b.name: [] for b in buckets}
    leftovers: list[str] = []

    for p in paths:
        placed = False
        for b in buckets:
            if b.pred(p):
                grouped[b.name].append(p)
                placed = True
                break
        if not placed:
            leftovers.append(p)

    md = []
    md.append("# RCX Minimal Spine Manifest\n")
    md.append(f"- Repo root: `{root}`")
    md.append(f"- Pack source: `{pack.name}`")
    md.append(f"- Files: **{len(paths)}**\n")

    for b in buckets:
        items = grouped[b.name]
        if not items:
            continue
        md.append(f"## {b.name}\n")
        md.append(f"{b.desc}\n")
        for p in items:
            md.append(f"- `{p}`")
        md.append("")

    if leftovers:
        md.append("## Other\n")
        md.append("Included by the minimal pack rules but not categorized above.\n")
        for p in leftovers:
            md.append(f"- `{p}`")
        md.append("")

    out_md = root / "RCX_MINIMAL_SPINE_MANIFEST.md"
    out_json = root / "RCX_MINIMAL_SPINE_MANIFEST.json"
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "repo_root": str(root),
        "pack_file": pack.name,
        "file_count": len(paths),
        "buckets": grouped,
        "leftovers": leftovers,
    }
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote: {out_md.name}")
    print(f"Wrote: {out_json.name}")

if __name__ == "__main__":
    main()
