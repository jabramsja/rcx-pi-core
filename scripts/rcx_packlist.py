#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

def sh(cmd: list[str]) -> str:
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise SystemExit(f"cmd failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout

def repo_root() -> Path:
    return Path(sh(["git", "rev-parse", "--show-toplevel"]).strip())

def git_ls_files() -> list[str]:
    out = sh(["git", "ls-files"])
    return [x.strip() for x in out.splitlines() if x.strip()]

EXCLUDE_DIR_PARTS = {
    ".git", "target", "__pycache__", ".pytest_cache", ".mypy_cache",
    "rcx_pi_core.egg-info", "dist", "build", ".venv", "venv",
    "sandbox_runs", ".ruff_cache",
}
EXCLUDE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".tar", ".tgz"}

# "Minimal spine" = what you need to understand/rehydrate the current working system.
MINIMAL_GLOBS = [
    "README.md",
    "TASKS.md",
    ".github/workflows/*.yml",
    ".github/workflows/*.md",
    "scripts/check_*.sh",
    "scripts/rcx_*.py",
    "scripts/rcx_*.sh",
    "scripts/tests/*.py",
    "rcx_pi_rust/src/*.rs",
    "rcx_pi/*.py",
    "rcx_pi/**/*.py",
    "rcx_omega/*.py",
    "rcx_omega/**/*.py",
    # schema locations (both)
    "docs/schemas/**/*.json",
    "docs/schemas/**/*.md",
    "docs/*schema*.json",
    "docs/*schema*.md",
]

# "Extended" = minimal + docs + fixtures + latex (still reasonable; still tracked)
EXTENDED_GLOBS = MINIMAL_GLOBS + [
    "docs/**/*.md",
    "docs/**/*.json",
    "docs/fixtures/**/*",
    "docs/latex/**/*",
    "tests/**/*.py",
    "tests/golden/**/*",
    "rcx_pi_rust/examples/**/*",
    "rcx_pi_rust/mu_programs/**/*",
    "rcx_pi_rust/mu_worlds/**/*",
    "rcx_pi_rust/tests/**/*",
    "rcx_pi_rust/docs/**/*",
]

def excluded(path: str) -> bool:
    p = Path(path)
    if any(part in EXCLUDE_DIR_PARTS for part in p.parts):
        return True
    if p.suffix.lower() in EXCLUDE_SUFFIXES:
        return True
    return False

def matches_any_glob(path: str, globs: list[str]) -> bool:
    # Use fnmatch over POSIX-ish paths (git returns / separators)
    return any(fnmatch.fnmatch(path, g) for g in globs)

@dataclass(frozen=True)
class Pack:
    name: str
    globs: list[str]
    out_list: str
    out_tar: str | None

def build_pack(files: list[str], globs: list[str]) -> list[str]:
    # Keep stable ordering
    chosen = []
    for f in sorted(files):
        if excluded(f):
            continue
        if matches_any_glob(f, globs):
            chosen.append(f)
    # De-dupe stable
    seen = set()
    out = []
    for f in chosen:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out

def filter_existing(root: Path, paths: list[str]) -> tuple[list[str], list[str]]:
    kept, missing = [], []
    for p in paths:
        if (root / p).exists():
            kept.append(p)
        else:
            missing.append(p)
    return kept, missing

def write_list(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

def main() -> None:
    ap = argparse.ArgumentParser(description="Build deterministic re-upload packlists from tracked repo files.")
    ap.add_argument("--mode", choices=["minimal", "extended", "both"], default="both")
    ap.add_argument("--no-tar", action="store_true", help="Do not create tarballs.")
    ap.add_argument("--outdir", default=".", help="Output directory (relative to repo root).")
    args = ap.parse_args()

    root = repo_root()
    outdir = (root / args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    files = git_ls_files()

    packs: list[Pack] = []
    if args.mode in ("minimal", "both"):
        packs.append(Pack(
            name="minimal",
            globs=MINIMAL_GLOBS,
            out_list="rcx_pack_minimal.txt",
            out_tar="rcx_pack_minimal.tgz" if not args.no_tar else None
        ))
    if args.mode in ("extended", "both"):
        packs.append(Pack(
            name="extended",
            globs=EXTENDED_GLOBS,
            out_list="rcx_pack_extended.txt",
            out_tar="rcx_pack_extended.tgz" if not args.no_tar else None
        ))

    print(f"repo: {root}")
    for pack in packs:
        raw = build_pack(files, pack.globs)
        kept, missing = filter_existing(root, raw)

        out_list = outdir / pack.out_list
        write_list(out_list, kept)

        print(f"\n== pack: {pack.name} ==")
        print(f"listed: {len(raw)}   kept(existing): {len(kept)}   missing(filtered): {len(missing)}")
        if missing:
            # show a few, but this should generally be empty now
            print("missing (first 15):")
            for m in missing[:15]:
                print(" -", m)
        print(f"wrote: {out_list.relative_to(root)}")

        if pack.out_tar:
            out_tar = outdir / pack.out_tar
            # tar reads paths relative to cwd; run from repo root
            subprocess.run(["tar", "-czf", str(out_tar), "-T", str(out_list)], cwd=root, check=True)
            print(f"wrote: {out_tar.relative_to(root)}")

if __name__ == "__main__":
    main()
