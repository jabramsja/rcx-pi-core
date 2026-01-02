# rcx_pi/worlds/worlds_mutate_loop.py

from __future__ import annotations

import os
import random
import shutil
from typing import Dict

from .worlds_evolve import score_world_against_spec, SPEC_PRESETS


# Where the .mu worlds live, relative to this file
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))  # .../WorkingRCX/rcx_pi
MU_DIR = os.path.join(ROOT_DIR, "..", "rcx_pi_rust", "mu_programs")


def _mu_path(world: str) -> str:
    """Return filesystem path to <world>.mu."""
    return os.path.join(MU_DIR, f"{world}.mu")


def mutate_world_file(base_world: str, gen: int) -> str:
    """
    Create a slightly mutated copy of a Mu world.

    Strategy:
      - Copy <base_world>.mu to <base_world>__g<gen>.mu
      - In the copy, randomly flip one occurrence of "Ra" / "Lobe" / "Sink"
        to a different bucket.
    """
    src_path = _mu_path(base_world)
    if not os.path.exists(src_path):
        raise FileNotFoundError(
            f"No .mu file found for world {
                base_world!r} at {src_path}")

    mutant_name = f"{base_world}__g{gen}"
    dst_path = _mu_path(mutant_name)

    # 1) Copy original file
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    shutil.copy2(src_path, dst_path)

    # 2) Read & mutate one bucket token
    with open(dst_path, "r", encoding="utf-8") as f:
        text = f.read()

    BUCKETS = ["Ra", "Lobe", "Sink"]

    # Find which bucket tokens are present at all
    present = [b for b in BUCKETS if b in text]
    if not present:
        # Nothing to mutate; return as-is
        return mutant_name

    # Pick one bucket that exists, and flip it to a different one
    old_bucket = random.choice(present)
    new_bucket_choices = [b for b in BUCKETS if b != old_bucket]
    new_bucket = random.choice(new_bucket_choices)

    # Replace only ONE occurrence to keep mutations small
    text_mutated = text.replace(old_bucket, new_bucket, 1)

    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(text_mutated)

    return mutant_name


def evolve(world: str, spec_name: str, generations: int) -> None:
    """
    Run a simple evolutionary loop for a given Mu world against a spec preset.

    Args:
        world:       base world name, e.g. "rcx_core" or "paradox_1over0".
        spec_name:   short spec name, e.g. "core" or "paradox_1over0".
        generations: number of mutation generations to run.
    """
    if spec_name not in SPEC_PRESETS:
        raise ValueError(
            f"Unknown spec preset {spec_name!r}. "
            f"Available: {sorted(SPEC_PRESETS.keys())}"
        )

    spec: Dict[str, str] = SPEC_PRESETS[spec_name]

    print(f"\n=== RCX Evolution: {world} -> spec:{spec_name} ===")

    # Score the base world
    base_score = score_world_against_spec(world, spec)
    print(
        f"Base world {world!r}: "
        f"accuracy={base_score.accuracy:.3f} "
        f"({base_score.total - base_score.mismatches}/{base_score.total})"
    )

    current_world = world
    current_score = base_score

    for gen in range(1, generations + 1):
        print(f"\n--- generation {gen} ---")

        # Propose a mutant of the *current best* world
        mutant_world = mutate_world_file(current_world, gen)
        mutant_score = score_world_against_spec(mutant_world, spec)

        print(
            f"Candidate {mutant_world!r}: "
            f"accuracy={mutant_score.accuracy:.3f} "
            f"({mutant_score.total - mutant_score.mismatches}/{mutant_score.total})"
        )

        # Simple hill-climbing: keep strictly better mutants
        if mutant_score.accuracy > current_score.accuracy:
            print(
                f"  ✓ Improvement! Replacing {
                    current_world!r} with {
                    mutant_world!r}")
            current_world = mutant_world
            current_score = mutant_score
        else:
            print(f"  ✗ No improvement; keeping {current_world!r}")

    print(
        f"\n=== Evolution complete for spec={spec_name!r} ===\n"
        f"Best world: {current_world!r}  "
        f"accuracy={current_score.accuracy:.3f} "
        f"({current_score.total - current_score.mismatches}/{current_score.total})"
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("\nUsage:")
        print(
            "  python3 -m rcx_pi.worlds.worlds_mutate_loop <world> <spec> [generations]")
        print("\nExamples:")
        print("  python3 -m rcx_pi.worlds.worlds_mutate_loop rcx_core core 30")
        print("  python3 -m rcx_pi.worlds.worlds_mutate_loop paradox_1over0 paradox_1over0 50\n")
        sys.exit(1)

    world_arg = sys.argv[1]
    spec_arg = sys.argv[2]
    gens = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    evolve(world_arg, spec_arg, gens)
