# ==========================================================
# FILE 2: rcx_pi/worlds/test_worlds_paradox_1over0.py
# ==========================================================
"""
Tests for the paradox_1over0 world.

These tests assume:

    - worlds_json/paradox_1over0.json exists
    - you have run:
          python3 -m rcx_pi.worlds_json to-mu \
              worlds_json/paradox_1over0.json \
              rcx_pi_rust/mu_programs/paradox_1over0.mu

    - probe_world(world_name, seeds, max_steps) returns a fingerprint dict:

          {
            "world": "paradox_1over0",
            "routes": [
               { "mu": "[1/0]", "route": "Ra",   ... },
               ...
            ],
            ...
          }

If the JSON schema in your repo differs slightly, adjust the fields or patterns
to match your existing worlds.
"""

from rcx_pi.worlds_probe import probe_world


SEEDS_1O = [
    "[1/0]",
    "[1/0_numeric]",
    "[1/0_infty]",
    "[1/0_engine]",
    "[1=-0]",
    "[white_light]",
    "[RGB_split]",
    "[sink_flatten]",
    "[omega_cycle_1o]",
]


EXPECTED_ROUTES = {
    "[1/0]": "Ra",
    "[1/0_engine]": "Ra",
    "[1=-0]": "Ra",
    "[white_light]": "Ra",

    "[1/0_numeric]": "Lobe",
    "[RGB_split]": "Lobe",
    "[omega_cycle_1o]": "Lobe",

    "[1/0_infty]": "Ra",
    "[sink_flatten]": "Sink",
}


def _route_lookup(fingerprint):
    """Convert fingerprint['routes'] to a {mu: route} dict."""
    routes = fingerprint.get("routes", [])
    return {row["mu"]: row["route"] for row in routes}


def test_paradox_1over0_basic_routes():
    """
    Basic sanity check: paradox_1over0 should classify the nine seeds
    according to the conceptual spec:

        - Engine-level motifs: Ra
        - Structured projections / ω-cycles: Lobe
        - Destructive flattenings: Sink
    """
    fp = probe_world("paradox_1over0", SEEDS_1O, max_steps=20)
    assert fp["world"] == "paradox_1over0"

    route_by_mu = _route_lookup(fp)

    # Ensure we saw all seeds (no silent drops).
    for mu in SEEDS_1O:
        assert mu in route_by_mu, f"Missing route for {mu!r}"

    # Check the expected bucket for each seed.
    for mu, expected in EXPECTED_ROUTES.items():
        actual = route_by_mu[mu]
        assert actual == expected, f"{mu}: expected {expected}, got {actual}"


def test_paradox_1over0_engine_vs_numeric():
    """
    Specifically distinguish:

        - [1/0] and [1/0_engine] and [white_light] as Ra (engine lens)
        - [1/0_numeric] as Lobe (unresolved arithmetic lens)
        - [1/0_infty] as Ra (stable projective numeric interpretation)
    """
    fp = probe_world("paradox_1over0", SEEDS_1O, max_steps=20)
    route_by_mu = _route_lookup(fp)

    for mu in ("[1/0]", "[1/0_engine]", "[white_light]"):
        assert route_by_mu[mu] == "Ra"

    assert route_by_mu["[1/0_numeric]"] == "Lobe"
    assert route_by_mu["[1/0_infty]"] == "Ra"


def test_paradox_1over0_residue_in_sink():
    """
    [sink_flatten] stands for 'treat 1/0 as a normal finite number or forbid it';
    that should always land in Sink in this world.
    """
    fp = probe_world("paradox_1over0", ["[sink_flatten]"], max_steps=20)
    route_by_mu = _route_lookup(fp)
    assert route_by_mu["[sink_flatten]"] == "Sink"
