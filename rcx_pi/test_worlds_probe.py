# rcx_pi/test_worlds_probe.py
"""
Tests for the Python↔Rust world bridge + probe_world.

These are sanity/invariant tests:
- rcx_core routes core tags as expected.
- pingpong has a 2-cycle limit orbit for 'ping'.
"""

from rcx_pi.worlds_probe import probe_world


def test_rcx_core_fingerprint_basic():
    seeds = ["[null,a]", "[inf,a]", "[paradox,a]", "[omega,[a,b]]"]
    fp = probe_world("rcx_core", seeds, max_steps=20)

    summary = fp["summary"]
    routes = {r["mu"]: r["route"] for r in fp["routes"]}

    # Basic route expectations
    assert routes["[null,a]"] == "Ra"
    assert routes["[inf,a]"] == "Lobe"
    assert routes["[paradox,a]"] == "Sink"
    # Current core behavior: omega goes to Sink
    assert routes["[omega,[a,b]]"] == "Lobe"

    # Count invariants: 1 Ra, 1 Lobe, 2 Sink
    assert summary["counts"]["Ra"] == 1
    assert summary["counts"]["Lobe"] == 2
    assert summary["counts"]["Sink"] == 1
    assert summary["counts"]["None"] == 0


def test_pingpong_limit_cycle():
    fp = probe_world("pingpong", ["ping"], max_steps=12)

    summary = fp["summary"]
    assert summary["limit_cycles"], "expected at least one limit cycle"
    cycle = summary["limit_cycles"][0]

    assert cycle["mu"] == "ping"
    assert cycle["period"] == 2

    orbit = fp["orbits"][0]["orbit"]
    assert orbit["kind"] == "limit_cycle"
    assert orbit["period"] == 2
    assert orbit["states"][0] == "ping"
    assert orbit["states"][1] == "pong"
