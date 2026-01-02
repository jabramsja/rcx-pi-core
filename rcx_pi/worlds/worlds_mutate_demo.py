# rcx_pi/worlds_mutate_demo.py
"""
Tiny evolution demo for RCX-π worlds.

- Start from a base world (e.g. rcx_core).
- Make a few JSON mutants by flipping rule actions.
- Regenerate .mu files for those mutants.
- Probe each world via the Rust engine.
- Score them against a behavior spec derived from rcx_core itself.
"""

from __future__ import annotations

import copy
import json
import os
import random
import subprocess
from pathlib import Path
from typing import Dict, List

from rcx_pi.worlds_probe import probe_world


def _pattern_head(pattern_str: str) -> str:
    """
    Very small parser for patterns like "[inf,_]" or "[omega,_]".
    Returns the head symbol (e.g. "inf", "omega") or the whole
    string if it can't parse cleanly.
    """
    s = pattern_str.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return s
    inner = s[1:-1].strip()
    if "," not in inner:
        return inner
    head, _rest = inner.split(",", 1)
    return head.strip()


REPO_ROOT = Path(__file__).resolve().parents[2]
WORLDS_JSON_DIR = REPO_ROOT / "worlds_json"
MU_PROGRAMS_DIR = REPO_ROOT / "rcx_pi_rust" / "mu_programs"


def load_world_json(name: str) -> Dict:
    path = WORLDS_JSON_DIR / f"{name}.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_world_json(name: str, data: Dict) -> Path:
    WORLDS_JSON_DIR.mkdir(parents=True, exist_ok=True)
    path = WORLDS_JSON_DIR / f"{name}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    return path


def json_to_mu(json_name: str, mu_name: str) -> None:
    """
    Call the existing CLI:

        python3 -m rcx_pi.worlds_json to-mu INPUT.json OUTPUT.mu
    """
    json_path = WORLDS_JSON_DIR / f"{json_name}.json"
    mu_path = MU_PROGRAMS_DIR / f"{mu_name}.mu"

    MU_PROGRAMS_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3",
        "-m",
        "rcx_pi.worlds_json",
        "to-mu",
        str(json_path),
        str(mu_path),
    ]
    print(f"[json→mu] {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"worlds_json to-mu failed for {json_name}")


def derive_spec_from_world(
    world: str,
    seeds: List[str],
    max_steps: int = 20,
) -> Dict[str, str]:
    """
    Probe a world and return a mapping:

        MU string -> route ("Ra" | "Lobe" | "Sink" | "None")
    """
    fingerprint = probe_world(world, seeds, max_steps=max_steps)
    spec: Dict[str, str] = {}
    for row in fingerprint["routes"]:
        mu = row["mu"]
        route = row["route"]
        spec[mu] = route
    return spec


def score_world_against_spec(
    world: str,
    spec: Dict[str, str],
    seeds: List[str],
    max_steps: int = 20,
) -> Dict:
    """
    Returns a dict like:

        {
          "world": "rcx_core",
          "accuracy": 1.0,
          "mismatches": 0,
          "total": N,
          "rows": [
             { "mu": "...", "desired": "...", "actual": "...", "match": True/False },
             ...
          ]
        }
    """
    fingerprint = probe_world(world, seeds, max_steps=max_steps)
    rows = []
    mismatches = 0

    # Build a quick lookup from fingerprint
    route_by_mu = {row["mu"]: row["route"] for row in fingerprint["routes"]}

    for mu, desired in spec.items():
        actual = route_by_mu.get(mu, "None")
        match = (actual == desired)
        if not match:
            mismatches += 1
        rows.append(
            {
                "mu": mu,
                "desired": desired,
                "actual": actual,
                "match": match,
            }
        )

    total = len(rows)
    accuracy = 0.0 if total == 0 else (total - mismatches) / float(total)

    return {
        "world": world,
        "accuracy": accuracy,
        "mismatches": mismatches,
        "total": total,
        "rows": rows,
    }


def mutate_world_json_once(base: Dict) -> Dict:
    """
    Mutation v2:

      - Prefer mutating rules whose head is in TARGET_HEADS
        (e.g. inf / omega / shadow).
      - If no such rule exists, fall back to any bucket rule.
      - Flip ra/lobe/sink to a *different* bucket.
      - Leave rewrite actions alone.

    This makes it more likely that mutations affect the behaviors
    we actually probe.
    """
    TARGET_HEADS = {"inf", "omega", "shadow"}

    mutant = copy.deepcopy(base)
    rules = mutant.get("rules", [])
    if not rules:
        return mutant

    bucket_indices = []
    preferred_indices = []

    for idx, rule in enumerate(rules):
        action = rule.get("action")
        if action not in ("ra", "lobe", "sink"):
            continue  # skip rewrites etc.
        bucket_indices.append(idx)

        pat = rule.get("pattern", "")
        head = _pattern_head(pat)
        if head in TARGET_HEADS:
            preferred_indices.append(idx)

    if not bucket_indices:
        # Nothing bucket-like to mutate
        return mutant

    if preferred_indices:
        idx = random.choice(preferred_indices)
    else:
        idx = random.choice(bucket_indices)

    rule = rules[idx]
    action = rule.get("action")
    buckets = ["ra", "lobe", "sink"]
    choices = [b for b in buckets if b != action]
    new_action = random.choice(choices)

    print(
        f"[mutate] rule {idx}: pattern={rule.get('pattern')} "
        f"{action} -> {new_action}"
    )
    rule["action"] = new_action

    return mutant


def main() -> None:
    random.seed(42)

    base_name = "rcx_core"
    num_mutants = 4

    print("=== RCX-π world mutation demo ===")
    print(f"Base world: {base_name}")
    print(f"Generating {num_mutants} mutants...\n")

    # 1) Load base JSON
    base_json = load_world_json(base_name)

    # 2) Make sure base .mu is in sync (sanity)
    json_to_mu(base_name, base_name)

    # 3) Seeds and spec derived from base rcx_core behavior
    seeds = [
        "[null,a]",
        "[inf,a]",
        "[paradox,a]",
        "[omega,[a,b]]",
        "[a,a]",
        "[dog,cat]",
        "[shadow,a]",
        "[sink,x]",
        "[lobe,x]",
    ]

    print("=== deriving desired spec from rcx_core ===")
    spec = derive_spec_from_world(base_name, seeds, max_steps=20)
    for mu, route in spec.items():
        print(f"  {mu:14} -> {route}")
    print()

    # 4) Generate mutants
    world_names = [base_name]
    for i in range(1, num_mutants + 1):
        mname = f"{base_name}_mut{i}"
        mutant_json = mutate_world_json_once(base_json)
        save_world_json(mname, mutant_json)
        json_to_mu(mname, mname)
        world_names.append(mname)

    # 5) Score all worlds
    print("\n=== scoring worlds against rcx_core spec ===")
    scores = []
    for w in world_names:
        print(f"[score] probing {w}...")
        result = score_world_against_spec(w, spec, seeds, max_steps=20)
        scores.append(result)

    scores.sort(key=lambda r: r["accuracy"], reverse=True)

    print("\n=== ranked worlds ===")
    for s in scores:
        print(
            f"  {s['world']:12} accuracy={s['accuracy']:.3f}  "
            f"({s['total'] - s['mismatches']}/{s['total']}) "
            f"mismatches={s['mismatches']}"
        )

    # 6) Show details for the best mutant (skipping the base if you want)
    print("\n=== detailed view of best non-base world (if any) ===")
    non_base = [s for s in scores if s["world"] != base_name]
    if not non_base:
        print("(no mutants?)")
        return

    best = non_base[0]
    print(f"=== world: {best['world']} ===")
    print(
        f"accuracy:  {best['accuracy']:.3f}  "
        f"({best['total'] - best['mismatches']}/{best['total']})"
    )
    print(f"mismatches: {best['mismatches']}\n")

    print("rows:")
    for row in best["rows"]:
        mark = "✓" if row["match"] else "✗"
        print(
            f"  {mark} {row['mu']:14} "
            f"desired={row['desired']:<5} actual={row['actual']:<5}"
        )


if __name__ == "__main__":
    main()
