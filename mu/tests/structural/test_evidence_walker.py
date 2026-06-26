"""Tests for evidence_walker.v1.json — structural trace walker for evidence collection.

Structural contract tests (fast gate) + truth-table tests (slow — calls run_mu).

Displacement target: _collect_ontology_evidence host iteration in step_mu.py.
"""
import pytest

from rcx_pi.selfhost.seed_integrity import (
    EXPECTED_PROJECTION_IDS,
    load_verified_seed,
    get_seed_path,
)
from rcx_pi.selfhost.step_mu import (
    run_mu,  # SPEED_OK: tested via run_mu (slow-marked below)
)

ZERO = {"_num": None}
ONE = {"_num": {"xH": None}}
TWO = {"_num": {"xO": {"xH": None}}}
THREE = {"_num": {"xI": {"xH": None}}}
FOUR = {"_num": {"xO": {"xO": {"xH": None}}}}


# =============================================================================
# Structural Contract Tests (fast gate — no run_mu)
# =============================================================================

class TestEvidenceWalkerSeedStructure:
    """Verify evidence_walker.v1.json seed integrity and structure."""

    def test_seed_loads_and_verifies(self):
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        assert "meta" in seed
        assert "projections" in seed

    def test_projection_count(self):
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        assert len(seed["projections"]) == 4

    def test_projection_ids_match_expected(self):
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        actual_ids = [p["id"] for p in seed["projections"]]
        expected_ids = EXPECTED_PROJECTION_IDS["evidence_walker.v1.json"]
        assert actual_ids == expected_ids

    def test_init_before_init_empty(self):
        """init must precede init_empty (first-match-wins: head/tail before null)."""
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        ids = [p["id"] for p in seed["projections"]]
        assert ids.index("evidence.walk.init") < ids.index("evidence.walk.init_empty")

    def test_collect_next_before_collect_done(self):
        """collect_and_next must precede collect_and_done (head/tail before null rest)."""
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        ids = [p["id"] for p in seed["projections"]]
        assert ids.index("evidence.walk.collect_and_next") < ids.index("evidence.walk.collect_and_done")

    def test_no_kernel_reserved_fields(self):
        """No underscore-prefixed keys in patterns or bodies."""
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        for proj in seed["projections"]:
            for section_name in ("pattern", "body"):
                section = proj.get(section_name, {})
                _check_no_underscore_keys(section, f"{proj['id']}.{section_name}")

    def test_all_patterns_are_linear(self):
        """All patterns should be linear-only (no bridge required)."""
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        for proj in seed["projections"]:
            var_counts = []
            _collect_var_occurrences(proj["pattern"], var_counts)
            from collections import Counter
            dupes = {v: c for v, c in Counter(var_counts).items() if c > 1}
            assert not dupes, (
                f"Non-linear pattern in {proj['id']}: vars appear >1 time: {dupes}"
            )

    def test_meta_fields(self):
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        meta = seed["meta"]
        assert meta["name"] == "EVIDENCE_WALKER"
        assert meta["execution_layer"] == "APPLICATION"
        assert "linear" in meta["requires_patterns"]

    def test_phase_structure(self):
        """Verify projection IDs follow init/collect/done structure."""
        seed = load_verified_seed(get_seed_path("evidence_walker.v1.json"))
        ids = [p["id"] for p in seed["projections"]]
        assert ids[0] == "evidence.walk.init"
        assert ids[1] == "evidence.walk.init_empty"
        assert ids[2] == "evidence.walk.collect_and_next"
        assert ids[3] == "evidence.walk.collect_and_done"


# =============================================================================
# Truth-Table Tests (slow — calls run_mu)
# =============================================================================

def _load_walker_projs():
    return load_verified_seed(get_seed_path("evidence_walker.v1.json"))["projections"]


def _make_trace(*entries):
    """Build a trace linked list from entries."""
    node = None
    for entry in reversed(entries):
        node = {"head": entry, "tail": node}
    return node


def _collect_entries(result):
    """Extract entry list from walker result."""
    if not isinstance(result, dict) or "evidence_done" not in result:
        return []
    collected = result["evidence_done"].get("collected")
    entries = []
    node = collected
    while isinstance(node, dict) and "head" in node:
        entries.append(node["head"])
        node = node.get("tail")
    # Mu runtime may normalize {head, tail} to Python lists
    if isinstance(collected, list):
        return list(collected)
    return entries


@pytest.mark.slow
class TestEvidenceWalkerTruthTable:
    """Truth-table tests for evidence_walker.v1.json."""

    def test_null_trace(self):
        """Null trace → done with null collected."""
        projs = _load_walker_projs()
        wrapped = {"evidence_walk": {"trace": None}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        assert isinstance(result, dict)
        assert "evidence_done" in result
        assert result["evidence_done"]["collected"] is None

    def test_single_entry_with_projection(self):
        """Single trace entry with projection → entry collected."""
        projs = _load_walker_projs()
        trace = _make_trace({"state": "a", "step": ZERO, "projection": "test.rewrite"})
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        entries = _collect_entries(result)
        assert len(entries) == 1
        assert entries[0]["projection"] == "test.rewrite"

    def test_single_entry_without_projection(self):
        """Single trace entry without projection → still collected (boundary filters)."""
        projs = _load_walker_projs()
        trace = _make_trace({"state": "a", "step": ZERO})
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        entries = _collect_entries(result)
        assert len(entries) == 1
        assert "projection" not in entries[0]

    def test_mixed_entries(self):
        """Mix of entries → all collected for boundary post-processing."""
        projs = _load_walker_projs()
        trace = _make_trace(
            {"state": "a", "step": ZERO, "projection": "p1"},
            {"state": "b", "step": ONE},
            {"state": "c", "step": TWO, "projection": "p2"},
        )
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=30)
        entries = _collect_entries(result)
        assert len(entries) == 3

    def test_multiple_entries_all_with_projection(self):
        """All entries have projection → all collected."""
        projs = _load_walker_projs()
        trace = _make_trace(
            {"state": "a", "step": ZERO, "projection": "id.1"},
            {"state": "b", "step": ONE, "projection": "id.2"},
            {"state": "c", "step": TWO, "projection": "id.1"},
        )
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=30)
        entries = _collect_entries(result)
        assert len(entries) == 3

    def test_non_string_projection_collected(self):
        """Non-string projection values collected (boundary filters later)."""
        projs = _load_walker_projs()
        trace = _make_trace(
            {"state": "a", "step": ZERO, "projection": ONE},
        )
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=20)
        entries = _collect_entries(result)
        assert len(entries) == 1
        assert entries[0]["projection"] == ONE

    def test_trace_len_from_entry_count(self):
        """Total entry count equals trace length."""
        projs = _load_walker_projs()
        trace = _make_trace(
            {"state": "a", "step": ZERO},
            {"state": "b", "step": ONE, "projection": "p1"},
            {"state": "c", "step": TWO},
            {"state": "d", "step": THREE, "projection": "p2"},
            {"state": "e", "step": FOUR},
        )
        wrapped = {"evidence_walk": {"trace": trace}}
        result, _trace, _stall = run_mu(projs, wrapped, max_steps=50)
        entries = _collect_entries(result)
        assert len(entries) == 5


# =============================================================================
# Helpers
# =============================================================================

def _check_no_underscore_keys(obj, path=""):
    """Recursively check that no keys start with underscore."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(key, str) and key.startswith("_"):
                raise AssertionError(
                    f"Kernel-reserved underscore key '{key}' found at {path}"
                )
            _check_no_underscore_keys(val, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _check_no_underscore_keys(item, f"{path}[{i}]")


def _collect_var_occurrences(obj, var_list):
    """Collect all var name occurrences from a pattern (list-based, preserves duplicates)."""
    if isinstance(obj, dict):
        if "var" in obj and len(obj) == 1:
            var_list.append(obj["var"])
        else:
            for val in obj.values():
                _collect_var_occurrences(val, var_list)
    elif isinstance(obj, list):
        for item in obj:
            _collect_var_occurrences(item, var_list)
