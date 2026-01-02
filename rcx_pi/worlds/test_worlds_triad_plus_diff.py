from __future__ import annotations

from rcx_pi.worlds.worlds_diff import diff_world_against_spec
from rcx_pi.worlds.worlds_evolve import SPEC_PRESETS


def test_triad_router_matches_triad_plus_spec():
    spec_name = "rcx_triad_plus"
    spec = SPEC_PRESETS[spec_name]
    report = diff_world_against_spec(
        "rcx_triad_router", spec_name, spec, max_steps=20)

    assert report.mismatches == [], f"mismatches (mu, expected, got): {
        report.mismatches}"
