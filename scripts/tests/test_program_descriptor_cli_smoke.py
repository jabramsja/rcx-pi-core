from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run(argv: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    # CLI lives at rcx_pi.program_descriptor_cli (NOT under rcx_pi.programs)
    cmd = [sys.executable, "-m", "rcx_pi.program_descriptor_cli", *argv]
    return subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True)


def _discover_candidates(repo_root: Path) -> list[str]:
    """
    Prefer a few known names, but also discover *.mu files anywhere in-repo
    (this repo keeps them under rcx_pi_rust/mu_programs).
    """
    candidates: list[str] = [
        "rcx_core",
        "pingpong",
        "paradox_1over0",
        "triad_plus",
        "godel_liar",
        "vars_demo",
    ]

    # Common locations (fast paths)
    for d in [
        repo_root / "mu_programs",
        repo_root / "rcx_pi_rust" / "mu_programs",
    ]:
        if d.exists():
            for p in sorted(d.glob("*.mu"))[:25]:
                candidates.append(str(p.relative_to(repo_root)))
                candidates.append(p.stem)

    # Bounded recursive fallback (robust)
    for mp in sorted(repo_root.rglob("*.mu"))[:50]:
        try:
            candidates.append(str(mp.relative_to(repo_root)))
        except ValueError:
            candidates.append(str(mp))

    # De-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def test_program_descriptor_resolves_some_known_program():
    repo_root = Path(__file__).resolve().parents[2]
    candidates = _discover_candidates(repo_root)

    last = None
    for c in candidates:
        r = _run([c, "--json"], repo_root)
        if r.returncode == 0 and r.stdout.strip():
            last = r
            break

    assert last is not None, (
        f"Could not resolve any candidate program. Tried: {candidates[:20]}"
    )

    data = json.loads(last.stdout)

    # Contract shape: wrapper keys + nested descriptor payload.
    required = {"schema", "schema_doc", "program", "descriptor", "ok", "warnings"}
    missing = required - set(data.keys())
    assert not missing, f"missing keys: {sorted(missing)}"

    assert data["schema"] == "rcx-program-descriptor.v1"
    assert isinstance(data["warnings"], list)
    assert isinstance(data["ok"], bool)

    assert isinstance(data["descriptor"], dict), "descriptor must be an object"
    desc = data["descriptor"]
    desc_required = {"name", "resolved_path", "format", "bytes"}
    desc_missing = desc_required - set(desc.keys())
    assert not desc_missing, f"descriptor missing keys: {sorted(desc_missing)}"
