"""Tests for metabolize_cycle.v1.json — structural walker for hemisphere metabolization.

Structural contract tests (fast gate) + truth-table tests (slow — calls run_mu).

Design reference: reports/metabolize_cycle_design_convergence.md
"""
import pytest

from rcx_pi.selfhost.seed_integrity import (
    EXPECTED_PROJECTION_IDS,
    load_verified_seed,
    get_seed_path,
)
from rcx_pi.selfhost.engine_pipeline import (
    run_metabolization_cycle,  # SPEED_OK: tested via run_mu (slow-marked below)
    count_hemisphere_entries,
)


# =============================================================================
# Structural Contract Tests (fast gate — no run_mu)
# =============================================================================

class TestMetabolizeCycleSeedStructure:
    """Verify metabolize_cycle.v1.json seed integrity and structure."""

    def test_seed_loads_and_verifies(self):
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        assert "meta" in seed
        assert "projections" in seed

    def test_projection_count(self):
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        assert len(seed["projections"]) == 15

    def test_projection_ids_match_expected(self):
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        actual_ids = [p["id"] for p in seed["projections"]]
        expected_ids = EXPECTED_PROJECTION_IDS["metabolize_cycle.v1.json"]
        assert actual_ids == expected_ids

    def test_projection_ordering_null_before_var(self):
        """sink_to_r_null must precede sink_to_r_inf (first-match-wins correctness)."""
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        ids = [p["id"] for p in seed["projections"]]
        r_null_idx = ids.index("metabolize.cycle.sink_to_r_null")
        r_inf_idx = ids.index("metabolize.cycle.sink_to_r_inf")
        assert r_null_idx < r_inf_idx, "sink_to_r_null must precede sink_to_r_inf"

    def test_no_kernel_reserved_fields_in_intermediate_state(self):
        """No underscore-prefixed keys in patterns or bodies (intermediate state)."""
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        for proj in seed["projections"]:
            for section_name in ("pattern", "body"):
                section = proj.get(section_name, {})
                _check_no_underscore_keys(section, f"{proj['id']}.{section_name}")

    def test_all_patterns_are_linear(self):
        """All patterns should be linear-only (no bridge/non-linear required)."""
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        for proj in seed["projections"]:
            var_counts = []
            _collect_var_occurrences(proj["pattern"], var_counts)
            # Linear means each var appears at most once in the pattern
            from collections import Counter
            dupes = {v: c for v, c in Counter(var_counts).items() if c > 1}
            assert not dupes, (
                f"Non-linear pattern in {proj['id']}: vars appear >1 time: {dupes}"
            )

    def test_meta_fields(self):
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        meta = seed["meta"]
        assert meta["name"] == "METABOLIZE_CYCLE"
        assert meta["execution_layer"] == "APPLICATION"
        assert "linear" in meta["requires_patterns"]

    def test_phase_structure(self):
        """Verify projection IDs follow the expected phase structure."""
        seed = load_verified_seed(get_seed_path("metabolize_cycle.v1.json"))
        ids = [p["id"] for p in seed["projections"]]
        # Phase 0: init
        assert ids[0] == "metabolize.cycle.init"
        assert ids[1] == "metabolize.cycle.init_skip_sink"
        # Phase 1: sink
        assert ids[2] == "metabolize.cycle.sink_to_r_null"
        assert ids[3] == "metabolize.cycle.sink_to_r_inf"
        assert ids[4] == "metabolize.cycle.sink_next"
        assert ids[5] == "metabolize.cycle.sink_done"
        # Phase 2: lobes
        assert ids[6] == "metabolize.cycle.lobes_start"
        assert ids[7] == "metabolize.cycle.lobes_start_empty"
        assert ids[8] == "metabolize.cycle.lobes_promote"
        assert ids[9] == "metabolize.cycle.lobes_keep"
        assert ids[10] == "metabolize.cycle.lobes_next"
        assert ids[11] == "metabolize.cycle.lobes_done"
        # Phase 2b: reverse
        assert ids[12] == "metabolize.cycle.lobes_reverse_step"
        assert ids[13] == "metabolize.cycle.lobes_reverse_done"
        # Phase 3: exit
        assert ids[14] == "metabolize.cycle.unwrap"


# =============================================================================
# Boundary Validation Tests (fast gate — no run_mu)
# =============================================================================

class TestCountHemisphereEntries:
    """Tests for count_hemisphere_entries boundary validator."""

    def test_empty_hemispheres(self):
        h = {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}
        assert count_hemisphere_entries(h) == 0

    def test_single_entry(self):
        h = {
            "r_null": None, "r_inf": None, "r_a": None, "lobes": None,
            "sink": [{"state": "x", "closure_flag": False, "origin": "test"}],
        }
        assert count_hemisphere_entries(h) == 1

    def test_multiple_entries_across_buckets(self):
        h = {
            "r_null": [{"state": None}],
            "r_inf": [{"state": "a"}, {"state": "b"}],
            "r_a": None,
            "lobes": [{"state": "c"}],
            "sink": None,
        }
        assert count_hemisphere_entries(h) == 4

    def test_malformed_node_raises(self):
        h = {
            "r_null": "not_a_list",
            "r_inf": None, "r_a": None, "lobes": None, "sink": None,
        }
        with pytest.raises(ValueError, match="must be null or list"):
            count_hemisphere_entries(h)

    def test_malformed_entry_raises(self):
        """Non-dict entry in bucket raises RcxEngineError (input.shape_mismatch)."""
        h = {
            "r_null": [1],
            "r_inf": None, "r_a": None, "lobes": None, "sink": None,
        }
        with pytest.raises(RuntimeError, match="entry\\[0\\] must be a plain object"):
            count_hemisphere_entries(h)

    def test_malformed_entry_null_raises(self):
        """Null entry in bucket raises RcxEngineError (input.shape_mismatch)."""
        h = {
            "r_null": [None],
            "r_inf": None, "r_a": None, "lobes": None, "sink": None,
        }
        with pytest.raises(RuntimeError, match="entry\\[0\\] must be a plain object"):
            count_hemisphere_entries(h)

    def test_depth_guard(self):
        """Depth guard catches overly deep lists."""
        h = {
            "r_null": [{"state": i} for i in range(5)],
            "r_inf": None, "r_a": None, "lobes": None, "sink": None,
        }
        with pytest.raises(ValueError, match="exceeds depth guard"):
            count_hemisphere_entries(h, max_entries_per_bucket=3)


# =============================================================================
# Truth-Table Tests (slow — calls run_metabolization_cycle → run_mu)
# =============================================================================

def _empty_hemispheres():
    return {"r_null": None, "r_inf": None, "r_a": None, "lobes": None, "sink": None}


def _make_entry(state, closure_flag=False, origin="test"):
    return {"state": state, "closure_flag": closure_flag, "origin": origin}


def _make_list(*entries):
    """Build a hemisphere bucket list from entries.

    The Mu runtime normalizes {head, tail} linked lists to Python lists.
    """
    if not entries:
        return None
    return list(entries)


def _collect_list(bucket):
    """Collect hemisphere bucket into a Python list of entries."""
    if bucket is None:
        return []
    return list(bucket)


@pytest.mark.slow
class TestMetabolizeCycleTruthTable:
    """Truth-table tests per MuHemispheresDesign.md T1-T10 (cycle-level)."""

    def test_empty_hemispheres_noop(self):
        """Empty hemispheres → identity (no-op)."""
        h = _empty_hemispheres()
        result = run_metabolization_cycle(h)
        assert result == _empty_hemispheres()

    def test_t2_sink_null_state_to_r_null(self):
        """T2: sink entry with null state → r_null."""
        h = _empty_hemispheres()
        h["sink"] = _make_list(_make_entry(None))
        result = run_metabolization_cycle(h)
        assert result["sink"] is None
        entries = _collect_list(result["r_null"])
        assert len(entries) == 1
        assert entries[0]["state"] is None
        assert entries[0]["origin"] == "metabolized"

    def test_t1_sink_nonnull_state_to_r_inf(self):
        """T1: sink entry with non-null state → r_inf."""
        h = _empty_hemispheres()
        h["sink"] = _make_list(_make_entry("some_value"))
        result = run_metabolization_cycle(h)
        assert result["sink"] is None
        entries = _collect_list(result["r_inf"])
        assert len(entries) == 1
        assert entries[0]["state"] == "some_value"
        assert entries[0]["origin"] == "metabolized"

    def test_t5_lobes_closure_true_to_r_a(self):
        """T5: lobes entry with closure_flag=true → r_a (promoted)."""
        h = _empty_hemispheres()
        h["lobes"] = _make_list(_make_entry("closed_value", closure_flag=True))
        result = run_metabolization_cycle(h)
        assert result["lobes"] is None
        entries = _collect_list(result["r_a"])
        assert len(entries) == 1
        assert entries[0]["state"] == "closed_value"
        assert entries[0]["closure_flag"] is True
        assert entries[0]["origin"] == "promoted"

    def test_t10_lobes_closure_false_stays_in_lobes(self):
        """T10: lobes entry with closure_flag=false → stays in lobes."""
        h = _empty_hemispheres()
        h["lobes"] = _make_list(_make_entry("pending", closure_flag=False, origin="original"))
        result = run_metabolization_cycle(h)
        entries = _collect_list(result["lobes"])
        assert len(entries) == 1
        assert entries[0]["state"] == "pending"
        assert entries[0]["closure_flag"] is False
        assert entries[0]["origin"] == "original"

    def test_multi_sink_entries(self):
        """Multiple sink entries → all routed correctly."""
        h = _empty_hemispheres()
        e1 = _make_entry(None)          # → r_null
        e2 = _make_entry("val1")        # → r_inf
        e3 = _make_entry(None)          # → r_null
        h["sink"] = _make_list(e1, e2, e3)
        result = run_metabolization_cycle(h)
        assert result["sink"] is None
        r_null_entries = _collect_list(result["r_null"])
        r_inf_entries = _collect_list(result["r_inf"])
        assert len(r_null_entries) == 2
        assert len(r_inf_entries) == 1
        assert all(e["origin"] == "metabolized" for e in r_null_entries)
        assert all(e["origin"] == "metabolized" for e in r_inf_entries)

    def test_mixed_lobes(self):
        """Mixed lobes: some promote, some keep → correct partition."""
        h = _empty_hemispheres()
        e1 = _make_entry("a", closure_flag=True, origin="orig1")   # → r_a
        e2 = _make_entry("b", closure_flag=False, origin="orig2")  # → lobes (kept)
        e3 = _make_entry("c", closure_flag=True, origin="orig3")   # → r_a
        e4 = _make_entry("d", closure_flag=False, origin="orig4")  # → lobes (kept)
        h["lobes"] = _make_list(e1, e2, e3, e4)
        result = run_metabolization_cycle(h)
        r_a_entries = _collect_list(result["r_a"])
        lobes_entries = _collect_list(result["lobes"])
        assert len(r_a_entries) == 2
        assert len(lobes_entries) == 2
        # Promoted entries have origin "promoted"
        assert all(e["origin"] == "promoted" for e in r_a_entries)
        # Kept entries preserve original origin
        assert lobes_entries[0]["origin"] == "orig2"
        assert lobes_entries[1]["origin"] == "orig4"

    def test_lobes_order_preserved(self):
        """Lobes order is preserved after metabolization (reverse phase)."""
        h = _empty_hemispheres()
        entries = [_make_entry(f"val_{i}", closure_flag=False, origin=f"o{i}") for i in range(5)]
        h["lobes"] = _make_list(*entries)
        result = run_metabolization_cycle(h)
        result_entries = _collect_list(result["lobes"])
        assert len(result_entries) == 5
        for i, e in enumerate(result_entries):
            assert e["state"] == f"val_{i}"
            assert e["origin"] == f"o{i}"

    def test_sink_and_lobes_combined(self):
        """Both sink and lobes have entries → both phases run."""
        h = _empty_hemispheres()
        h["sink"] = _make_list(_make_entry("s1"), _make_entry(None))
        h["lobes"] = _make_list(
            _make_entry("l1", closure_flag=True),
            _make_entry("l2", closure_flag=False),
        )
        result = run_metabolization_cycle(h)
        assert result["sink"] is None
        assert len(_collect_list(result["r_inf"])) == 1
        assert len(_collect_list(result["r_null"])) == 1
        assert len(_collect_list(result["r_a"])) == 1
        assert len(_collect_list(result["lobes"])) == 1

    def test_existing_r_buckets_preserved(self):
        """Pre-existing entries in r_null/r_inf/r_a are preserved (prepend, not replace)."""
        h = _empty_hemispheres()
        h["r_null"] = _make_list(_make_entry(None, origin="existing"))
        h["sink"] = _make_list(_make_entry(None))  # → r_null
        result = run_metabolization_cycle(h)
        r_null_entries = _collect_list(result["r_null"])
        assert len(r_null_entries) == 2
        # New metabolized entry prepended before existing
        assert r_null_entries[0]["origin"] == "metabolized"
        assert r_null_entries[1]["origin"] == "existing"

    def test_input_validation_type(self):
        """Non-dict input raises TypeError."""
        with pytest.raises(TypeError, match="hemispheres must be dict"):
            run_metabolization_cycle("not a dict")

    def test_input_validation_keys(self):
        """Wrong keys raise ValueError."""
        with pytest.raises(ValueError, match="shape mismatch"):
            run_metabolization_cycle({"wrong": None})


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


def _collect_vars(obj, vars_seen):
    """Collect unique var names from a pattern (set-based, deduplicates)."""
    if isinstance(obj, dict):
        if "var" in obj and len(obj) == 1:
            vars_seen.add(obj["var"])
        else:
            for val in obj.values():
                _collect_vars(val, vars_seen)
    elif isinstance(obj, list):
        for item in obj:
            _collect_vars(item, vars_seen)


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
