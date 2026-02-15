#!/usr/bin/env python3
"""
Docs relocate tool — safely move documentation files with validation.

Usage:
  python3 scripts/docs_relocate.py --dry-run moves.json
  python3 scripts/docs_relocate.py --apply  moves.json

moves.json format:
  {
    "moves": [
      {"from": "mu/docs/roadmap/MuHemispheresDesign.md", "to": "mu/docs/core/MuHemispheresDesign.md"},
      ...
    ]
  }

Features:
  - Pre-flight validation (source exists, dest doesn't, dest dir exists)
  - Detects code references to moved files (Python, JS, JSON, shell)
  - Uses git mv for tracked files
  - --dry-run shows what would happen without changes
  - --apply executes moves and reports references to update
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    )
    return Path(result.stdout.strip())


def find_references(root: Path, old_path: str) -> list[dict[str, str]]:
    """Find files that reference the given path string."""
    refs = []
    # Escape dots for regex but keep slashes
    pattern = re.escape(old_path)

    for ext in ("*.py", "*.js", "*.json", "*.sh", "*.md", "*.yml"):
        for f in root.rglob(ext):
            # Skip archive directories and .git
            parts = f.relative_to(root).parts
            if ".git" in parts or "__pycache__" in parts:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            if re.search(pattern, content):
                rel = str(f.relative_to(root))
                # Don't report self-references
                if rel != old_path:
                    refs.append({"file": rel, "pattern": old_path})
    return refs


def validate_moves(root: Path, moves: list[dict[str, str]]) -> list[str]:
    """Validate all moves. Returns list of error messages (empty = OK)."""
    errors = []
    seen_dests = set()

    for move in moves:
        src = root / move["from"]
        dst = root / move["to"]

        if not src.exists():
            errors.append(f"Source does not exist: {move['from']}")
        if dst.exists():
            errors.append(f"Destination already exists: {move['to']}")
        if not dst.parent.exists():
            errors.append(f"Destination directory does not exist: {dst.parent.relative_to(root)}")
        if move["to"] in seen_dests:
            errors.append(f"Duplicate destination: {move['to']}")
        seen_dests.add(move["to"])

    return errors


def dry_run(root: Path, moves: list[dict[str, str]]) -> int:
    """Show what would happen without making changes."""
    print(f"=== DRY RUN: {len(moves)} moves ===\n")

    errors = validate_moves(root, moves)
    if errors:
        print("VALIDATION ERRORS:")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    all_refs = []
    for move in moves:
        print(f"  {move['from']}")
        print(f"    -> {move['to']}")
        refs = find_references(root, move["from"])
        if refs:
            print(f"    REFERENCES ({len(refs)} files):")
            for ref in refs:
                print(f"      - {ref['file']}")
            all_refs.extend(refs)
        else:
            print("    No references found")
        print()

    print(f"=== Summary ===")
    print(f"Files to move: {len(moves)}")
    print(f"References to update: {len(all_refs)}")
    if all_refs:
        print("\nFiles needing reference updates:")
        unique_files = sorted(set(r["file"] for r in all_refs))
        for f in unique_files:
            print(f"  - {f}")

    return 0


def apply_moves(root: Path, moves: list[dict[str, str]]) -> int:
    """Execute moves using git mv."""
    print(f"=== APPLYING {len(moves)} moves ===\n")

    errors = validate_moves(root, moves)
    if errors:
        print("VALIDATION ERRORS — aborting:")
        for e in errors:
            print(f"  ERROR: {e}")
        return 1

    all_refs = []
    for move in moves:
        src = move["from"]
        dst = move["to"]

        # Ensure destination directory exists
        dst_dir = (root / dst).parent
        dst_dir.mkdir(parents=True, exist_ok=True)

        # git mv
        result = subprocess.run(
            ["git", "mv", src, dst],
            cwd=root, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"  FAILED: git mv {src} {dst}")
            print(f"    {result.stderr.strip()}")
            return 1

        print(f"  MOVED: {src} -> {dst}")

        refs = find_references(root, src)
        if refs:
            print(f"    WARNING: {len(refs)} files still reference old path")
            all_refs.extend(refs)

    print(f"\n=== Done ===")
    print(f"Moved: {len(moves)} files")
    if all_refs:
        print(f"\nWARNING: {len(all_refs)} stale references need manual update:")
        unique_files = sorted(set(r["file"] for r in all_refs))
        for f in unique_files:
            print(f"  - {f}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Safely relocate documentation files.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Show what would happen")
    group.add_argument("--apply", action="store_true", help="Execute moves")
    ap.add_argument("moves_file", help="JSON file defining moves")

    args = ap.parse_args()

    moves_path = Path(args.moves_file)
    if not moves_path.exists():
        print(f"ERROR: moves file not found: {moves_path}", file=sys.stderr)
        return 2

    data = json.loads(moves_path.read_text(encoding="utf-8"))
    moves = data.get("moves", [])

    if not moves:
        print("No moves defined in moves file.")
        return 0

    root = repo_root()

    if args.dry_run:
        return dry_run(root, moves)
    else:
        return apply_moves(root, moves)


if __name__ == "__main__":
    raise SystemExit(main())
