from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    return subprocess.run(
        [sys.executable, "-m", "rcx_pi.program_descriptor_cli", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )


def test_program_descriptor_cli_help_smoke():
    r = run(["--help"])
    assert r.returncode == 0


def test_program_descriptor_schema_flag():
    r = run(["--schema"])
    assert r.returncode == 0
    assert "rcx-program-descriptor.v1" in r.stdout
    assert "docs/program_descriptor_schema.md" in r.stdout


def test_program_descriptor_resolves_some_known_program():
    repo_root = Path(__file__).resolve().parents[2]
    candidates = ["rcx_core", "pingpong", "paradox_1over0", "triad_plus", "godel_liar", "vars_demo"]

    mu_dir = repo_root / "mu_programs"
    if mu_dir.exists():
        for p in sorted(mu_dir.glob("*.mu"))[:10]:
            candidates.append(p.stem)

    # Fallback: in this repo, .mu may live outside repo_root/mu_programs.
    # Try a bounded recursive search and pass relative paths (fast + robust).
    if not (repo_root / "mu_programs").exists():
        for mp in sorted(repo_root.rglob("*.mu"))[:25]:
            try:
                rel = mp.relative_to(repo_root)
            except ValueError:
                rel = mp
            candidates.append(str(rel))

    last = None
    for c in candidates:
        r = run([c])
        if r.returncode == 0 and r.stdout.strip():
            last = r
            break

    assert last is not None, f"Could not resolve any candidate program. Tried: {candidates[:20]}"
    data = json.loads(last.stdout)

    required = {
        "schema",
        "schema_doc",
        "kind",
        "name",
        "language",
        "source_path",
        "source_sha256",
        "entrypoint",
        "determinism",
        "version",
    }
    assert required.issubset(set(data.keys())), f"missing keys: {sorted(required - set(data.keys()))}"

    assert data["schema"] == "rcx-program-descriptor.v1"
    assert data["kind"] == "mu_program"
    assert data["language"] == "mu"
    assert isinstance(data["source_sha256"], str) and len(data["source_sha256"]) == 64
