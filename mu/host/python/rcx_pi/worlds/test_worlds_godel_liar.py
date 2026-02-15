import pytest
from rcx_pi.worlds_probe import probe_world

# Core seed set defining the Godel/Liar world behavior
SEEDS = [
    "[I_am_true]",
    "[I_am_false_implies_true]",
    "[Gödel_sentence]",
    "[this_sentence_is_false]",
    "[liar]",
    "[force_true(liar)]",
    "[binary_truth_only]",
]


def _route_lookup(fp):
    """Convert fingerprint['routes'] to a {mu: route} dict for easy assertion."""
    return {r["mu"]: r["route"] for r in fp["routes"]}


def test_godel_liar_basic_routes():
    """Ensure core classification of self-reference paradox seeds matches spec."""
    fp = probe_world("godel_liar", SEEDS, max_steps=20)

    assert fp["world"] == "godel_liar"
    routes = _route_lookup(fp)

    # Stable self-reference → Ra
    assert routes["[I_am_true]"] == "Ra"
    assert routes["[I_am_false_implies_true]"] == "Ra"
    assert routes["[Gödel_sentence]"] == "Ra"

    # Oscillators → Lobe
    assert routes["[this_sentence_is_false]"] == "Lobe"
    assert routes["[liar]"] == "Lobe"

    # Forced collapse → Sink
    assert routes["[force_true(liar)]"] == "Sink"
    assert routes["[binary_truth_only]"] == "Sink"


def test_godel_liar_summary_counts():
    """Check Ra/Lobe/Sink population distribution."""
    fp = probe_world("godel_liar", SEEDS, max_steps=20)
    summary = fp["summary"]
    counts = summary["counts"]

    assert counts["Ra"] == 3  # 3 stable fixed-point truth-objects
    assert counts["Lobe"] == 2  # 2 oscillatory paradox seeds
    assert counts["Sink"] == 2  # 2 collapse conditions
    assert counts["None"] == 0


def test_godel_liar_limit_cycle_liar():
    """The liar sentence should produce detectable oscillation."""
    fp = probe_world("godel_liar", ["[liar]"], max_steps=12)
    summary = fp["summary"]

    assert summary["limit_cycles"], "liar must generate a limit-cycle"
    cycle = summary["limit_cycles"][0]

    assert cycle["mu"] == "[liar]"
    assert cycle["period"] in (2, 4)


def test_godel_liar_orbit_trace_exists():
    """Pingpong-like orbit trace should be observable."""
    fp = probe_world("godel_liar", ["[liar]"], max_steps=8)
    orbits = fp["orbits"]

    assert orbits, "orbit trace required"
    orbit = orbits[0]["orbit"]

    assert len(orbit) >= 4, "cycle must have observable temporal spread"
    assert orbit.count("[liar]") > 1, "should recur"
