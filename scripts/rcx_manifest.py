#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


DEFAULT_ROOTS = [
    ".rcx_library/CANON",
    ".rcx_library/CANON_EXEC",
    "rcx_omega",
    "rcx_pi",
    "scripts",
    "tests",
    "docs",
]


@dataclass(frozen=True)
class Entry:
    path: str
    sha256: str
    size: int
    mtime_ns: int


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_files(root: Path) -> Iterable[Path]:
    # Deterministic ordering: sort by POSIX path.
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        # Skip obvious noise
        name = p.name
        if name in {".DS_Store"}:
            continue
        if name.endswith((".pyc", ".pyo")):
            continue
        if "/.git/" in p.as_posix():
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser(description="Create a deterministic RCX repo manifest.")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: .)")
    ap.add_argument("--out", default=".rcx_manifest.json", help="Output JSON path")
    ap.add_argument(
        "--roots",
        nargs="*",
        default=DEFAULT_ROOTS,
        help=f"Root directories to include (default: {', '.join(DEFAULT_ROOTS)})",
    )
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_path = (repo_root / args.out).resolve()

    entries: list[Entry] = []
    included_roots: list[str] = []
    missing_roots: list[str] = []

    for r in args.roots:
        rp = (repo_root / r).resolve()
        rel = os.path.relpath(rp, repo_root).replace("\\", "/")
        if not rp.exists():
            missing_roots.append(rel)
            continue
        if rp.is_file():
            included_roots.append(rel)
            st = rp.stat()
            entries.append(
                Entry(
                    path=rel,
                    sha256=sha256_file(rp),
                    size=st.st_size,
                    mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
                )
            )
            continue

        included_roots.append(rel)
        for f in iter_files(rp):
            relp = os.path.relpath(f, repo_root).replace("\\", "/")
            st = f.stat()
            entries.append(
                Entry(
                    path=relp,
                    sha256=sha256_file(f),
                    size=st.st_size,
                    mtime_ns=getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)),
                )
            )

    # Deterministic overall ordering.
    entries = sorted(entries, key=lambda e: e.path)

    # Compute a content-only digest for quick comparisons across sessions.
    # (Path + sha256 only, independent of mtime.)
    h = hashlib.sha256()
    for e in entries:
        h.update(e.path.encode("utf-8"))
        h.update(b"\0")
        h.update(e.sha256.encode("utf-8"))
        h.update(b"\n")
    manifest_digest = h.hexdigest()

    data = {
        "format": "rcx-manifest-v1",
        "repo_root": str(repo_root),
        "included_roots": included_roots,
        "missing_roots": missing_roots,
        "file_count": len(entries),
        "manifest_sha256": manifest_digest,
        "files": [
            {"path": e.path, "sha256": e.sha256, "size": e.size, "mtime_ns": e.mtime_ns}
            for e in entries
        ],
    }

    out_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"OK: wrote {os.path.relpath(out_path, repo_root)}")
    print(f"OK: file_count={len(entries)} manifest_sha256={manifest_digest}")
    if missing_roots:
        print("NOTE: missing_roots=" + ", ".join(missing_roots))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
