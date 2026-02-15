from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from rcx_pi.worlds_probe import probe_world

# ---------------------------------------------------------------------------
# Canonical candidate worlds for spec ranking / evolution
# ---------------------------------------------------------------------------

DEFAULT_CANDIDATE_WORLDS: List[str] = [
    "rcx_core",
    "vars_demo",
    "pingpong",
    "news",
    "paradox_1over0",
    "godel_liar",
    "rcx_triad_router",
]

# ---------------------------------------------------------------------------
# Core spec: baseline RCX engine lens
# ---------------------------------------------------------------------------

# This is the same behavior you already confirmed for rcx_core:
#   [null,a]       → Ra
#   [inf,a]        → Lobe
#   [paradox,a]    → Sink
#   [omega,[a,b]]  → Sink
#   [a,a]          → Lobe
#   [dog,cat]      → Sink
DESIRED_SPEC: Dict[str, str] = {
    "[null,a]": "Ra",
    "[inf,a]": "Lobe",
    "[paradox,a]": "Sink",
    "[omega,[a,b]]": "Lobe",
    "[a,a]": "Lobe",
    "[dog,cat]": "Sink",
}


# ---------------------------------------------------------------------------
# 1/0 paradox spec: lens on division-by-zero & white-light motifs
# ---------------------------------------------------------------------------

# Matches the behavior you see from paradox_1over0:
#   [1/0], [1/0_infty], [1/0_engine], [1=-0], [white_light] → Ra
#   [1/0_numeric]                                          → Lobe
#   [sink_flatten]                                         → Sink
PARADOX_1OVER0_SPEC: Dict[str, str] = {
    "[1/0]": "Ra",
    "[1/0_numeric]": "Lobe",
    "[1/0_infty]": "Ra",
    "[1/0_engine]": "Ra",
    "[1=-0]": "Ra",
    "[white_light]": "Ra",
    "[sink_flatten]": "Sink",
}


# ---------------------------------------------------------------------------
# Gödel / liar spec: self-reference / truth-oscillation lens
# ---------------------------------------------------------------------------

# Mirrors rcx_pi/worlds/test_worlds_godel_liar.py expectations:
#   [I_am_true]                 → Ra
#   [I_am_false_implies_true]   → Ra
#   [Gödel_sentence]            → Ra
#   [this_sentence_is_false]    → Lobe
#   [liar]                      → Lobe
#   [force_true(liar)]          → Sink
#   [binary_truth_only]         → Sink
GODEL_LIAR_SPEC: Dict[str, str] = {
    "[I_am_true]": "Ra",
    "[I_am_false_implies_true]": "Ra",
    "[Gödel_sentence]": "Ra",
    "[this_sentence_is_false]": "Lobe",
    "[liar]": "Lobe",
    "[force_true(liar)]": "Sink",
    "[binary_truth_only]": "Sink",
    "[truth_object]": "Ra",
    "[self_reference]": "Lobe",
    "[forbid_self_reference]": "Sink",
}


# ---------------------------------------------------------------------------
# Public spec registry (base presets)
# ---------------------------------------------------------------------------

SPEC_PRESETS: Dict[str, Dict[str, str]] = {
    "core": DESIRED_SPEC,
    "paradox_1over0": PARADOX_1OVER0_SPEC,
    "godel_liar": GODEL_LIAR_SPEC,
}


# ---------------------------------------------------------------------------
# Combined RCX triad spec: core + 1/0 + Gödel/liar
# ---------------------------------------------------------------------------

RCX_TRIAD_SPEC: Dict[str, str] = {}
RCX_TRIAD_SPEC.update(DESIRED_SPEC)
RCX_TRIAD_SPEC.update(PARADOX_1OVER0_SPEC)
RCX_TRIAD_SPEC.update(GODEL_LIAR_SPEC)

# Register as another spec preset
SPEC_PRESETS["rcx_triad"] = RCX_TRIAD_SPEC

# ---------------------------------------------------------------------------
# Triad+ spec: triad + boundary/hybrid seeds for evolution signal
# ---------------------------------------------------------------------------

TRIAD_PLUS_SPEC: Dict[str, str] = {}
TRIAD_PLUS_SPEC.update(RCX_TRIAD_SPEC)

TRIAD_PLUS_SPEC.update(
    {
        # core-ish but edgy
        "[null,[1/0]]": "Ra",
        "[inf,[1/0]]": "Lobe",
        "[paradox,[1/0]]": "Sink",
        # godel-ish but grounded
        "[truth_object]": "Ra",
        "[self_reference]": "Lobe",
        "[forbid_self_reference]": "Sink",
        # triad collisions
        "[liar,1/0]": "Lobe",
        "[Gödel,1/0_engine]": "Ra",
        "[binary_truth_only,1/0_numeric]": "Sink",
        # omega pressure tests
        "[omega,[1/0]]": "Sink",
        "[omega,[liar]]": "Sink",
        # “world selection” stressors
        "[white_light,paradox]": "Ra",
        "[sink_flatten,null]": "Sink",
        "[I_am_true,null]": "Ra",
        # noise seeds
        "[maybe]": "Lobe",
        "[collapse]": "Sink",
        "[expand]": "Ra",
        "[observer]": "Lobe",
        "[flatten]": "Sink",
    }
)

SPEC_PRESETS["rcx_triad_plus"] = TRIAD_PLUS_SPEC


# ---------------------------------------------------------------------------
# Scoring structures
# ---------------------------------------------------------------------------


@dataclass
class ScoreResult:
    world: str
    matches: int
    mismatches: int
    total: int

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.matches / self.total


# ---------------------------------------------------------------------------
# Core scoring against a spec
# ---------------------------------------------------------------------------


def score_world_against_spec(world: str, spec: Dict[str, str]) -> ScoreResult:
    """
    Score a Mu world against a Mu→{Ra,Lobe,Sink,None} spec.

    assert callable(probe_world), "probe_world not imported; worlds_evolve.py requires
    rcx_pi.worlds_probe.probe_world"

    Args:
        world: world name (e.g. "rcx_core", "paradox_1over0").
        spec:  dict mapping Mu seed → expected route bucket.

    Returns:
        ScoreResult with match/mismatch counts and accuracy.
    """
    # Seeds are just the keys of the spec.
    seeds: List[str] = list(spec.keys())

    # Use the unified probe_world API (Rust-backed or synthetic).
    fp: Dict[str, Any] = probe_world(world, seeds, max_steps=20)
    routes_list = fp.get("routes", []) or []

    # Map mu → actual route (default "None")
    actual_by_mu: Dict[str, str] = {}
    for row in routes_list:
        mu = row.get("mu", "")
        route = row.get("route", "None")
        if not mu:
            continue
        if route not in ("Ra", "Lobe", "Sink", "None"):
            route = "None"
        actual_by_mu[mu] = route

    matches = 0
    mismatches = 0

    for mu, expected in spec.items():
        actual = actual_by_mu.get(mu, "None")
        if actual == expected:
            matches += 1
        else:
            mismatches += 1

    total = matches + mismatches
    return ScoreResult(
        world=world,
        matches=matches,
        mismatches=mismatches,
        total=total,
    )


# ---------------------------------------------------------------------------
# World ranking helper
# ---------------------------------------------------------------------------


def rank_worlds(worlds: List[str], spec: Dict[str, str]) -> List[ScoreResult]:
    """
    Score multiple worlds against a spec and return them ranked.

    Sort order:
        1. Highest accuracy
        2. Fewest mismatches
        3. World name (lexicographically) to keep ordering deterministic.
    """
    results: List[ScoreResult] = [score_world_against_spec(w, spec) for w in worlds]

    results.sort(key=lambda r: (-r.accuracy, r.mismatches, r.world))
    return results
