"""
Tests for Phase 8d structural trace model.

The structural trace enables EngineNews (stall/fix/promote/closure) by providing
execution history as Mu linked-list format that projections can analyze.
"""

import pytest
from rcx_pi.selfhost.step_mu import run_mu_structural, list_to_linked as list_to_linked
from rcx_pi.selfhost.mu_type import mu_equal
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

pytestmark = [pytest.mark.slow]


class TestListToLinked:
    """Test helper for list-to-linked conversion."""

    def test_empty_list(self):
        assert list_to_linked([]) is None

    def test_single_item(self):
        result = list_to_linked([42])
        assert result == {"head": 42, "tail": None}

    def test_multiple_items(self):
        result = list_to_linked([1, 2, 3])
        assert result == {
            "head": 1,
            "tail": {
                "head": 2,
                "tail": {
                    "head": 3,
                    "tail": None
                }
            }
        }

    def test_nested_items(self):
        result = list_to_linked([{"a": 1}, {"b": 2}])
        assert result["head"] == {"a": 1}
        assert result["tail"]["head"] == {"b": 2}


class TestRunMuStructural:
    """Test structural trace accumulation."""

    @pytest.fixture
    def simple_projections(self):
        """Simple projection set for testing."""
        return [
            {
                "id": "double",
                "pattern": {"op": "double", "value": {"var": "n"}},
                "body": {"result": {"var": "n"}}
            }
        ]

    @pytest.fixture
    def kernel_projections(self):
        """Full kernel + match + subst projections from mu/ canonical location."""
        kernel = load_verified_seed(get_seed_path("kernel.v1.json"))
        match_seed = load_verified_seed(get_seed_path("match.v2.json"))
        subst_seed = load_verified_seed(get_seed_path("subst.v2.json"))
        return kernel["projections"] + match_seed["projections"] + subst_seed["projections"]

    def test_returns_mu_compatible_structure(self, simple_projections):
        """Result structure has required fields."""
        result = run_mu_structural(simple_projections, {"op": "double", "value": 42}, max_steps=10)

        assert "result" in result
        assert "trace" in result
        assert "stall" in result
        assert "steps" in result

    def test_trace_is_linked_list(self, simple_projections):
        """Trace is Mu linked-list format, not Python list."""
        result = run_mu_structural(simple_projections, {"op": "double", "value": 42}, max_steps=10)

        trace = result["trace"]
        # Linked list has head/tail structure
        assert trace is None or ("head" in trace and "tail" in trace)

    def test_trace_entries_have_required_fields(self, simple_projections):
        """Each trace entry has step, state, projection."""
        result = run_mu_structural(simple_projections, {"op": "double", "value": 42}, max_steps=10)

        # Walk the linked list
        node = result["trace"]
        while node is not None:
            entry = node["head"]
            assert "step" in entry
            assert "state" in entry
            assert "projection" in entry
            node = node["tail"]

    def test_stall_detected(self, simple_projections):
        """Stall is detected when no projection matches."""
        # Input that won't match the "double" projection
        result = run_mu_structural(simple_projections, {"op": "unknown", "value": 42}, max_steps=10)

        assert result["stall"] is True
        assert result["steps"] == 1  # Immediate stall

    def test_match_recorded_in_trace(self, simple_projections):
        """Matched projection ID is recorded in trace."""
        result = run_mu_structural(simple_projections, {"op": "double", "value": 42}, max_steps=10)

        # First entry should show the "double" projection matched
        first_entry = result["trace"]["head"]
        assert first_entry["projection"] == "double"

    def test_stall_entry_has_null_projection(self, simple_projections):
        """Stall entries have projection=None."""
        result = run_mu_structural(simple_projections, {"op": "unknown", "value": 42}, max_steps=10)

        # Walk to find the stall entry
        node = result["trace"]
        last_entry = None
        while node is not None:
            last_entry = node["head"]
            node = node["tail"]

        assert last_entry["projection"] is None
        assert last_entry.get("stall") is True

    def test_structural_trace_step_is_single_pass(self, monkeypatch):
        """
        run_mu_structural should not pre-match and then re-run step_mu.

        Regression guard for double-evaluation debt: trace generation must be
        based on a single structural pass per loop iteration.
        """
        import rcx_pi.selfhost.step_mu as step_mu_module

        def _should_not_be_called(*_args, **_kwargs):
            raise AssertionError("run_mu_structural should not call step_mu")

        monkeypatch.setattr(step_mu_module, "step_mu", _should_not_be_called)

        projs = [{"id": "inc", "pattern": 0, "body": 1}]
        result = run_mu_structural(projs, 0, max_steps=2)
        assert result["trace"]["head"]["projection"] == "inc"
        assert result["result"] == 1

    def test_max_steps_without_stall(self, kernel_projections):
        """Max steps reached without stall returns stall=False."""
        # Create a projection that always transforms (never stalls)
        toggle = [
            {"id": "toggle_0", "pattern": 0, "body": 1},
            {"id": "toggle_1", "pattern": 1, "body": 0},
        ]
        result = run_mu_structural(toggle, 0, max_steps=5)

        assert result["stall"] is False
        assert result["steps"] == 5

    def test_trace_length_matches_steps(self, simple_projections):
        """Trace has entry for each step plus final."""
        result = run_mu_structural(simple_projections, {"op": "double", "value": 42}, max_steps=10)

        # Count linked list entries
        count = 0
        node = result["trace"]
        while node is not None:
            count += 1
            node = node["tail"]

        # Trace should have steps + 1 entries (initial + each step)
        assert count == result["steps"] + 1


class TestClosureDetection:
    """Tests for Rule 2.2 closure detection capability."""

    def test_oscillation_in_trace(self):
        """Trace captures oscillating states for closure detection."""
        # A→B→A cycle
        toggle = [
            {"id": "a_to_b", "pattern": "A", "body": "B"},
            {"id": "b_to_a", "pattern": "B", "body": "A"},
        ]
        result = run_mu_structural(toggle, "A", max_steps=10)

        # Collect all states from trace
        states = []
        node = result["trace"]
        while node is not None:
            states.append(node["head"]["state"])
            node = node["tail"]

        # Should see A, B, A, B, ... pattern
        assert states[0] == "A"
        assert states[1] == "B"
        assert states[2] == "A"

    def test_trace_enables_cycle_detection(self):
        """EngineNews can detect cycles by scanning trace for repeated states."""
        toggle = [
            {"id": "inc", "pattern": {"n": {"var": "x"}}, "body": {"n": {"var": "x"}}},
        ]
        result = run_mu_structural(toggle, {"n": 0}, max_steps=5)

        # This stalls immediately (pattern matches but body is same)
        assert result["stall"] is True

        # Trace is available for analysis
        assert result["trace"] is not None
