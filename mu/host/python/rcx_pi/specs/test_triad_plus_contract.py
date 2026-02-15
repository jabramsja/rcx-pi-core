from __future__ import annotations

from rcx_pi.worlds.worlds_evolve import SPEC_PRESETS
from rcx_pi.worlds_probe import probe_world


def test_triad_router_matches_triad_plus_spec():
    """Contract: rcx_triad_router must exactly match rcx_triad_plus spec."""
    spec = SPEC_PRESETS["rcx_triad_plus"]
    seeds = list(spec.keys())

    fp = probe_world("rcx_triad_router", seeds, max_steps=20)
    got = {r["mu"]: r.get("route", "None") for r in fp.get("routes", [])}

    mismatches = [
        (mu, exp, got.get(mu, "None"))
        for mu, exp in spec.items()
        if got.get(mu, "None") != exp
    ]
    assert mismatches == [], f"mismatches (mu, expected, got): {mismatches}"
