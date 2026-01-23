"""
RCX World Mutation Engine
-------------------------

Generates mutated variants of existing Mu-worlds.
Medium-risk evolution: occasional bold rewrites, mostly safe drifts.

Core idea:
    Parent world -> mutate rules -> spawn child world file -> evaluate -> select best.

Produced files live under rcx_pi/worlds/generated/<world>_mut_*.
"""

import os
import random
import shutil
from typing import Dict, List, Tuple

GENERATED_DIR = "rcx_pi/worlds/generated"
os.makedirs(GENERATED_DIR, exist_ok=True)

# Buckets used in routing
BUCKETS = ["Ra", "Lobe", "Sink", "None"]


# --------------------------
# Mutation rules
# --------------------------
def mutate_bucket(bucket: str) -> str:
    """
    Mutate a route bucket with medium-risk probability distribution.
    """
    r = random.random()

    # Mostly keep original
    if r < 0.65:
        return bucket

    # Gentle drift
    if r < 0.80:
        # neighbor shift
        if bucket == "Ra":
            return "Lobe"
        if bucket == "Lobe":
            return random.choice(["Ra", "Sink"])
        if bucket == "Sink":
            return "Lobe"
        if bucket == "None":
            return random.choice(["Sink", "Lobe"])

    # Bold mutation
    if r < 0.95:
        return random.choice(BUCKETS)

    # Rare wild jump
    return random.choice(["Ra", "Sink"])  # polarity swap


# --------------------------
# World mutation
# --------------------------
def mutate_world_dict(route_map: Dict[str, str]) -> Dict[str, str]:
    """
    Input:  {"[null,a]":"Ra", "[inf,a]":"Lobe", ...}
    Output: new mutated version of same dict
    """
    new = {}
    for mu, bucket in route_map.items():
        new[mu] = mutate_bucket(bucket)
    return new


def write_mutated_world_file(
    parent: str, generation: int, routes: Dict[str, str]
) -> str:
    """
    Writes a new Python file expressing this world's routing table.
    """

    filename = f"{parent}_g{generation:03}.py"
    path = os.path.join(GENERATED_DIR, filename)

    with open(path, "w") as f:
        f.write("# Auto-generated RCX mutated world\n")
        f.write(f"# parent: {parent}, generation {generation}\n\n")
        f.write("ROUTES = {\n")
        for mu, bucket in routes.items():
            f.write(f"    {mu!r}: {bucket!r},\n")
        f.write("}\n\n")
        f.write("""
def classify(mu: str) -> str:
    return ROUTES.get(mu, "None")
""")

    return path


def load_route_map_from_file(path: str) -> Dict[str, str]:
    ns = {}
    exec(open(path).read(), ns)
    return ns.get("ROUTES", {})


def load_base_world_routes(world: str) -> Dict[str, str]:
    """
    Extract classification table from existing worlds by probing dynamic seeds.
    We reuse probe_world to infer buckets.
    """
    from rcx_pi.worlds.worlds_probe_wrapper import probe_world_all_mu

    result = probe_world_all_mu(world)
    return {row["mu"]: row["route"] for row in result["routes"]}


def mutate_world(parent_world: str, generation: int) -> Tuple[str, Dict[str, str]]:
    """
    Produce a mutated world. Returns (world_name, route_map).
    """
    base_routes = load_base_world_routes(parent_world)
    mutated = mutate_world_dict(base_routes)

    file_path = write_mutated_world_file(parent_world, generation, mutated)

    world_name = os.path.splitext(os.path.basename(file_path))[0]
    return world_name, mutated
