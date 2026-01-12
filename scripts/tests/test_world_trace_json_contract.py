from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(script: Path, repo_root: Path, world: str, seed: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), world, seed, "--json", "--pretty", "--max-steps", "3"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )


def test_world_trace_json_contract_minimal_world():
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "world_trace.sh"
    assert script.exists(), f"missing: {script}"

    # Seed motif strings seen elsewhere in RCX logs/tests
    seeds = ["[null,a]", "[1/0]", "[omega,[a,b]]", "[inf,a]"]

    # 1) Try likely registered world names first (fast path)
    world_names = [
        "rcx_core",
        "triad_plus",
        "godel_liar",
        "paradox_1over0",
        "vars_demo",
        "pingpong",
    ]

    # 2) Also try file-like worlds if the CLI accepts a path
    worlds_dir = repo_root / "rcx_pi" / "worlds"
    file_candidates: list[str] = []
    if worlds_dir.exists():
        exts = (".mu", ".json", ".txt")
        for p in sorted(worlds_dir.rglob("*")):
            if p.is_file() and p.suffix in exts:
                rel = p.relative_to(repo_root)
                file_candidates.append(str(rel))
                if len(file_candidates) >= 12:
                    break

    candidates: list[str] = world_names + file_candidates

    last: subprocess.CompletedProcess[str] | None = None
    for world in candidates:
        for seed in seeds:
            r = _run(script, repo_root, world, seed)
            if r.returncode == 0 and r.stdout.strip():
                last = r
                break
        if last is not None:
            break

    assert last is not None, (
        "Could not find any (world, seed) combo that runs successfully.\n"
        "Tried worlds:\n  - " + "\n  - ".join(candidates[:20]) + "\n"
        "Seeds:\n  - " + "\n  - ".join(seeds) + "\n"
    )

    out = last.stdout.strip()
    data = json.loads(out)

    # ---- Minimal stable JSON contract (matches current CLI output) ----
    assert isinstance(data, dict), f"expected object, got {type(data)}"

    required = {"schema", "world", "seed", "max_steps", "orbit", "trace"}
    missing = required - set(data.keys())
    assert not missing, f"missing keys: {sorted(missing)}; got keys={sorted(data.keys())}"

    # Allow future additions without breaking, but keep it bounded.
    allowed = required | {"ok", "warnings", "stats", "meta", "classification"}
    extra = set(data.keys()) - allowed
    assert not extra, f"unexpected keys: {sorted(extra)}; allowed={sorted(allowed)}"

    # schema tag (canonical today, plus forward-compatible family)
    assert isinstance(data["schema"], str) and data["schema"]
    schema = data["schema"]
    assert (
        schema == "rcx-world-trace.v1" or schema.startswith("rcx-world-trace.")
    ), f"unexpected schema tag: {schema}"

    assert isinstance(data["world"], str) and data["world"]
    assert isinstance(data["seed"], str) and data["seed"]
    assert isinstance(data["max_steps"], int) and data["max_steps"] >= 0

    # orbit is an object today: {kind, period, states:[...]}
    assert isinstance(data["orbit"], dict), f"expected orbit object, got {type(data['orbit'])}"
    assert "states" in data["orbit"], f"orbit missing 'states': keys={sorted(data['orbit'].keys())}"
    assert isinstance(data["orbit"]["states"], list), f"expected orbit.states list, got {type(data['orbit']['states'])}"

    # trace is a list of step entries (shape may evolve)
    assert isinstance(data["trace"], list)
