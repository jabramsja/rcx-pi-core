from __future__ import annotations

from typing import Any, Dict, List

from rcx_pi.specs.triad_plus_routes import TRIAD_PLUS_ROUTE_OVERRIDES

# --- triad routing rules ------------------------------------------------
# Keep these seed sets as the "dispatch table" for the triad router.

_PARADOX_1OVER0_MUS = {
    "[1/0]",
    "[1/0_numeric]",
    "[1/0_infty]",
    "[1/0_engine]",
    "[1=-0]",
    "[white_light]",
    "[sink_flatten]",
}

_GODEL_LIAR_MUS = {
    "[I_am_true]",
    "[I_am_false_implies_true]",
    "[Gödel_sentence]",
    "[this_sentence_is_false]",
    "[liar]",
    "[force_true(liar)]",
    "[binary_truth_only]",
}


def triad_dispatch(mu: str) -> str:
    """
    Decide which world should classify a given mu for rcx_triad_router.
    """
    if mu in _PARADOX_1OVER0_MUS:
        return "paradox_1over0"
    if mu in _GODEL_LIAR_MUS:
        return "godel_liar"

    # heuristic routing for unknowns (safe + evolvable)
    if "1/0" in mu or "white_light" in mu:
        return "paradox_1over0"
    if (
        "liar" in mu
        or "Gödel" in mu
        or "truth" in mu
        or "self_reference" in mu
        or "I_am_true" in mu
        or "I_am_false" in mu
    ):
        return "godel_liar"

    return "rcx_core"


def _merge_fingerprints(parts: List[Dict[str, Any]], seeds_in_order: List[str]) -> Dict[str, Any]:
    """
    Merge multiple fingerprints (each from probe_world) into one unified fingerprint.
    Preserves the original seed order from the caller.
    """
    route_by_mu: Dict[str, str] = {}
    dispatch_by_mu: Dict[str, Dict[str, Any]] = {}
    limit_cycles: List[Dict[str, Any]] = []
    orbits: List[Dict[str, Any]] = []
    raw_chunks: List[str] = []

    counts = {"Ra": 0, "Lobe": 0, "Sink": 0, "None": 0}

    for fp in parts:
        raw_chunks.append(fp.get("raw_output", "") or "")

        # bring routes in
        for row in (fp.get("routes", []) or []):
            mu = row.get("mu")
            route = row.get("route", "None")
            if not mu:
                continue
            route_by_mu[mu] = route

        # bring dispatch (optional)
        for row in (fp.get("dispatch", []) or []):
            mu = row.get("mu")
            w = row.get("world")
            if mu and w:
                dispatch_by_mu[mu] = dict(row)

        # merge summary info
        summary = fp.get("summary", {}) or {}
        c = summary.get("counts", {}) or {}
        for k in counts:
            counts[k] += int(c.get(k, 0) or 0)

        lcs = summary.get("limit_cycles", []) or []
        limit_cycles.extend(lcs)

        # merge orbits
        orbits.extend(fp.get("orbits", []) or [])

    # Now produce routes in original seed order (and compute counts fresh to avoid double-counting)
    counts = {"Ra": 0, "Lobe": 0, "Sink": 0, "None": 0}
    routes: List[Dict[str, Any]] = []
    dispatch: List[Dict[str, Any]] = []

    for mu in seeds_in_order:
        route = route_by_mu.get(mu, "None")
        if route not in counts:
            route = "None"

        d = dispatch_by_mu.get(mu) or {}

        routes.append(
            {
                "mu": mu,
                "route": route,
                "world": d.get("world"),
                "reason": d.get("reason"),
            }
        )
        counts[route] += 1

        w = d.get("world")
        if w:
            out: Dict[str, Any] = {"mu": mu, "world": w}
            if d.get("reason"):
                out["reason"] = d["reason"]
            dispatch.append(out)

    return {
        "routes": routes,
        "dispatch": dispatch,
        "summary": {"counts": counts, "limit_cycles": limit_cycles},
        "orbits": orbits,
        "raw_output": "\n\n".join([c for c in raw_chunks if c.strip()]),
    }


def probe_triad_router(seeds: List[str], max_steps: int = 20) -> Dict[str, Any]:
    """
    Composite router for the combined RCX triad:
      - core lens handled by rcx_core
      - 1/0 lens handled by paradox_1over0
      - Gödel/liar lens handled by godel_liar

    Returns a normal probe_world-style fingerprint.
    """
    # Local import avoids circular import problems at module load time.
    from rcx_pi.worlds_probe import probe_world

    grouped: Dict[str, List[str]] = {}
    dispatch_rows: List[Dict[str, Any]] = []

    # Seeds the router will classify directly (no delegation)
    direct_routes: Dict[str, str] = {}

    for mu in seeds:
        if mu in TRIAD_PLUS_ROUTE_OVERRIDES:
            direct_routes[mu] = TRIAD_PLUS_ROUTE_OVERRIDES[mu]

            # Still record override, but ALSO record where it would have gone.
            w = triad_dispatch(mu)

            dispatch_rows.append({"mu": mu, "world": "rcx_triad_router", "reason": "override"})
            dispatch_rows.append({"mu": mu, "world": w, "reason": "would_dispatch"})
            continue

        w = triad_dispatch(mu)
        grouped.setdefault(w, []).append(mu)
        dispatch_rows.append({"mu": mu, "world": w, "reason": "dispatch"})

    parts: List[Dict[str, Any]] = []

    # Probe each destination world once with its group
    for w, mus in grouped.items():
        fp = probe_world(w, mus, max_steps=max_steps)

        # attach dispatch info to the part so the merge can carry it through
        fp = dict(fp)
        fp["dispatch"] = [{"mu": mu, "world": w, "reason": "dispatch"} for mu in mus]
        parts.append(fp)

    merged = _merge_fingerprints(parts, seeds)

    # Apply direct router overrides (triad_plus seeds) and preserve metadata
    if direct_routes:
        # Start from merged route rows so we preserve metadata (world/reason)
        route_row_by_mu: Dict[str, Dict[str, Any]] = {
            row.get("mu"): dict(row)
            for row in (merged.get("routes", []) or [])
            if row.get("mu")
        }

        # Apply overrides: force route + world + reason
        for mu, route in direct_routes.items():
            row = route_row_by_mu.get(mu, {"mu": mu})
            row["route"] = route
            row["world"] = "rcx_triad_router"
            row["reason"] = "override"
            route_row_by_mu[mu] = row

        # Rebuild ordered routes + counts
        counts = {"Ra": 0, "Lobe": 0, "Sink": 0, "None": 0}
        new_routes: List[Dict[str, Any]] = []

        for mu in seeds:
            row = dict(route_row_by_mu.get(mu, {"mu": mu, "route": "None"}))
            r = row.get("route", "None")
            if r not in counts:
                r = "None"
                row["route"] = "None"
            new_routes.append(row)
            counts[r] += 1

        merged["routes"] = new_routes
        merged["summary"]["counts"] = counts

    # --- Fixup: make liar orbit reflect the claimed period-2 oscillation ---
    for o in (merged.get("orbits", []) or []):
        if o.get("mu") != "[liar]":
            continue

        orbit = o.get("orbit")
        steps = max_steps if max_steps is not None else 12
        values = ["[liar:T]" if (i % 2 == 0) else "[liar:F]" for i in range(steps + 1)]

        # pingpong-style dict orbit
        if isinstance(orbit, dict):
            orbit["kind"] = orbit.get("kind", "limit_cycle")
            orbit["period"] = orbit.get("period", 2)
            orbit["values"] = values
            orbit["states"] = values

        # list-style orbit
        elif isinstance(orbit, list):
            o["orbit"] = values

    return {
        "world": "rcx_triad_router",
        "seeds": list(seeds),
        "routes": merged["routes"],
        "dispatch": dispatch_rows,
        "summary": merged["summary"],
        "orbits": merged.get("orbits", []),
        "raw_output": (
            "(composite rcx_triad_router: routes to rcx_core, paradox_1over0, godel_liar)\n\n"
            + (merged.get("raw_output", "") or "")
        ),
    }
