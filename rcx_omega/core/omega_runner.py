"""
RCX-Ω omega runner (staging)

Runs repeated evaluation steps (ω-orbit) from a seed motif, detects:
- fixed point
- limit cycle
- cutoff (max steps reached)

Intentionally tiny + dependency-light.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from rcx_pi import new_evaluator
from rcx_omega.core.motif_codec import motif_to_json_obj


@dataclass(frozen=True)
class OmegaOrbitStep:
    i: int
    value: Any


@dataclass(frozen=True)
class OmegaRun:
    seed: Any
    orbit: List[OmegaOrbitStep]
    result: Any
    classification: str  # "fixed_point" | "limit_cycle" | "cutoff"
    period: Optional[int] = None
    mu: Optional[int] = None  # start index of cycle if limit_cycle


def _children(x: Any) -> List[Any]:
    """
    RCX-π Motif exposes children via .structure (tuple of motifs).
    If something else sneaks in, treat it as a leaf.
    """
    try:
        s = getattr(x, "structure", None)
        if isinstance(s, tuple):
            return list(s)
    except Exception:
        pass
    return []


def _count_nodes_depth(x: Any) -> Dict[str, int]:
    """
    Local motif metrics to avoid depending on a moving module name.

    nodes: number of Motif nodes in the tree (leaf motif counts as 1)
    depth: max depth (leaf motif depth = 1)
    """
    kids = _children(x)
    if not kids:
        return {"nodes": 1, "depth": 1}
    child_stats = [_count_nodes_depth(k) for k in kids]
    nodes = 1 + sum(cs["nodes"] for cs in child_stats)
    depth = 1 + max(cs["depth"] for cs in child_stats)
    return {"nodes": nodes, "depth": depth}


def _key(x: Any) -> str:
    # Canonical key for cycle detection: stable JSON-ish identity.
    return str(motif_to_json_obj(x, include_meta=False))


def run_omega(seed: Any, *, max_steps: int = 64) -> OmegaRun:
    """
    Run ω orbit for up to max_steps transitions (inclusive of step 0 seed snapshot).

    Orbit includes step 0 = seed, step i = state after i transitions.
    """
    ev = new_evaluator()

    orbit: List[OmegaOrbitStep] = [OmegaOrbitStep(0, seed)]
    seen: Dict[str, int] = {_key(seed): 0}

    x = seed
    for i in range(1, max_steps + 1):
        y = ev.reduce(x)

        orbit.append(OmegaOrbitStep(i, y))
        ky = _key(y)

        if ky in seen:
            mu = seen[ky]
            period = i - mu
            classification = "fixed_point" if (period == 1 and mu == i - 1) else "limit_cycle"
            return OmegaRun(
                seed=seed,
                orbit=orbit,
                result=y,
                classification=classification,
                period=period,
                mu=mu,
            )

        seen[ky] = i
        x = y

    return OmegaRun(
        seed=seed,
        orbit=orbit,
        result=orbit[-1].value,
        classification="cutoff",
        period=None,
        mu=None,
    )


def omega_run_to_json(run: OmegaRun, *, include_meta: bool = False) -> Dict[str, Any]:
    """
    JSON object suitable for piping into analyze_cli.
    """
    seed_obj = motif_to_json_obj(run.seed, include_meta=include_meta)
    result_obj = motif_to_json_obj(run.result, include_meta=include_meta)

    seed_stats = _count_nodes_depth(run.seed)
    result_stats = _count_nodes_depth(run.result)

    orbit_rows = []
    for s in run.orbit:
        m = _count_nodes_depth(s.value)
        orbit_rows.append({"i": s.i, "nodes": m["nodes"], "depth": m["depth"]})

    return {
        "kind": "omega",
        "seed": seed_obj,
        "result": result_obj,
        "stats": {
            "seed": {"nodes": seed_stats["nodes"], "depth": seed_stats["depth"]},
            "result": {"nodes": result_stats["nodes"], "depth": result_stats["depth"]},
        },
        "classification": {
            "type": run.classification,
            "mu": run.mu,
            "period": run.period,
            "max_steps": len(run.orbit) - 1,
        },
        "orbit": orbit_rows,
    }
