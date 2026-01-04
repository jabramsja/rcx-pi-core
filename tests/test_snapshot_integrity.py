from __future__ import annotations

import hashlib
from pathlib import Path


SNAP_DIR = Path("rcx_pi_rust/snapshots")
SUMS = SNAP_DIR / "SHA256SUMS"


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _parse_sha256sums(text: str) -> dict[str, str]:
    """
    Format: "<sha256><two spaces><filename>"
    """
    m: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "  " not in line:
            raise AssertionError(f"Malformed SHA256SUMS line: {raw!r}")
        sha, name = line.split("  ", 1)
        sha = sha.strip()
        name = name.strip()
        if len(sha) != 64:
            raise AssertionError(f"Bad sha256 length for {name}: {sha!r}")
        if not name.endswith(".state"):
            raise AssertionError(f"Unexpected file in SHA256SUMS (must be .state): {name}")
        if name in m:
            raise AssertionError(f"Duplicate entry in SHA256SUMS: {name}")
        m[name] = sha
    return m


def test_rust_snapshots_sha256_locked():
    assert SNAP_DIR.is_dir(), "Not found in provided corpus/output: rcx_pi_rust/snapshots/"
    assert SUMS.is_file(), "Not found in provided corpus/output: rcx_pi_rust/snapshots/SHA256SUMS"

    expected = _parse_sha256sums(SUMS.read_text(encoding="utf-8"))

    # Ensure every expected snapshot exists and matches.
    for name, exp_sha in sorted(expected.items()):
        p = SNAP_DIR / name
        assert p.is_file(), f"Missing snapshot file listed in SHA256SUMS: {name}"
        got = _sha256_bytes(p.read_bytes())
        assert got == exp_sha, f"Snapshot drift: {name} sha256={got} expected={exp_sha}"

    # Ensure no extra snapshots exist without being tracked in SHA256SUMS.
    actual = {p.name for p in SNAP_DIR.glob('*.state') if p.is_file()}
    extra = sorted(actual - set(expected.keys()))
    assert not extra, f"Untracked snapshot(s) present (add to SHA256SUMS): {extra}"
