from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "rcx_pi.program_descriptor_cli", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )


def _discover_candidates(repo_root: Path) -> list[str]:
    """
    Prefer real artifacts in the repo so the smoke doesn't depend on name registration.
    Order:
      1) known friendly names (fast path)
      2) mu_programs/*.mu stems
    """
    candidates: list[str] = [
        "rcx_core",
        "pingpong",
        "paradox_1over0",
        "triad_plus",
        "godel_liar",
        "vars_demo",
    ]

    mu_dir = repo_root / "mu_programs"
    if mu_dir.exists():
        for p in sorted(mu_dir.glob("*.mu"))[:50]:
            candidates.append(p.stem)

    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def test_program_descriptor_json_contract():
    repo_root = Path(__file__).resolve().parents[2]
    candidates = _discover_candidates(repo_root)

    last = None
    for c in candidates:
        r = run([c, "--json"], repo_root)
        if r.returncode == 0 and r.stdout.strip():
            last = r
            break

    assert last is not None, (
        f"Could not resolve any candidate program for contract. Tried: {candidates[:30]}"
    )

    data = json.loads(last.stdout)

    required = {"schema", "schema_doc", "program", "descriptor"}
    missing = required - set(data.keys())
    assert not missing, (
        f"missing keys: {sorted(missing)}; got keys={sorted(data.keys())}"
    )

    allowed = required | {"ok", "warnings", "meta"}
    extra = set(data.keys()) - allowed
    assert not extra, f"unexpected keys: {sorted(extra)}; allowed={sorted(allowed)}"
