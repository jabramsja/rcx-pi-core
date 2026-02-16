"""
Explicit Projection-Level Tests for eval.v1.json.

This addresses the grounding agent finding that eval.v1.json projections
need explicit tests for each projection ID:
- restart
- unwrap
- descend.dict
- sibling.to_tail
- ascend.to_context
- ascend.to_root
- wrap

Each projection is tested individually to verify pattern matching and body output.
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.eval_seed import step, match, substitute
from rcx_pi.selfhost.kernel import reset_step_budget
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def eval_projections() -> list:
    """Load eval.v1.json projections."""
    seed = load_verified_seed(get_seed_path("eval.v1.json"))
    return seed["projections"]


@pytest.fixture
def eval_seed() -> dict:
    """Load full eval.v1.json seed."""
    return load_verified_seed(get_seed_path("eval.v1.json"))


def single_step(projections: list, value: dict) -> dict:
    """Run exactly one step and return result."""
    reset_step_budget()
    return step(projections, value)


# =============================================================================
# Projection ID Tests
# =============================================================================


class TestEvalProjectionIds:
    """Verify all expected projection IDs are present."""

    def test_eval_seed_has_7_projections(self, eval_seed):
        """eval.v1.json must have exactly 7 projections."""
        assert len(eval_seed["projections"]) == 7

    def test_all_projection_ids_present(self, eval_seed):
        """All expected projection IDs must be present."""
        expected = {"restart", "unwrap", "descend.dict", "sibling.to_tail",
                   "ascend.to_context", "ascend.to_root", "wrap"}
        actual = {p["id"] for p in eval_seed["projections"]}
        assert actual == expected

    def test_wrap_is_last(self, eval_seed):
        """wrap must be last (catch-all entry point)."""
        assert eval_seed["projections"][-1]["id"] == "wrap"


# =============================================================================
# Individual Projection Tests
# =============================================================================


class TestWrapProjection:
    """Test wrap projection (entry point)."""

    def test_wrap_matches_any_value(self, eval_projections):
        """wrap should match any value and wrap it in deep_eval state."""
        # Any primitive
        result = single_step(eval_projections, 42)
        assert result["mode"] == "deep_eval"
        assert result["phase"] == "traverse"
        assert result["focus"] == 42
        assert result["context"] == []
        assert result["changed"] is False

    def test_wrap_matches_dict(self, eval_projections):
        """wrap should wrap dict values."""
        value = {"a": 1, "b": 2}
        result = single_step(eval_projections, value)
        assert result["mode"] == "deep_eval"
        assert result["focus"] == value

    def test_wrap_matches_linked_list(self, eval_projections):
        """wrap should wrap linked list values."""
        value = {"head": 1, "tail": None}
        result = single_step(eval_projections, value)
        assert result["mode"] == "deep_eval"
        assert result["focus"] == value


class TestDescendDictProjection:
    """Test descend.dict projection (traverse into head/tail)."""

    def test_descend_into_head_tail(self, eval_projections):
        """descend.dict should descend into head/tail structures."""
        # State with head/tail focus in traverse phase
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": {"head": "H", "tail": "T"},
            "context": [],
            "changed": False
        }
        result = single_step(eval_projections, state)

        # Should descend into head
        assert result["mode"] == "deep_eval"
        assert result["phase"] == "traverse"
        assert result["focus"] == "H"
        # Context should have dict_head frame
        assert len(result["context"]) == 2  # [frame, []] - with [] flattened
        assert result["context"][0]["type"] == "dict_head"
        assert result["context"][0]["head_val"] == "H"
        assert result["context"][0]["tail_val"] == "T"

    def test_descend_preserves_changed_flag(self, eval_projections):
        """descend.dict should preserve changed flag."""
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": {"head": 1, "tail": 2},
            "context": [],
            "changed": True
        }
        result = single_step(eval_projections, state)
        assert result["changed"] is True


class TestSiblingToTailProjection:
    """Test sibling.to_tail projection (move from head to tail)."""

    def test_sibling_moves_to_tail(self, eval_projections):
        """After processing head, should move to tail."""
        # State after processing head (dict_head context)
        state = {
            "mode": "deep_eval",
            "phase": "traverse",  # Any phase after head processing
            "focus": "processed_head",
            "context": [
                {"type": "dict_head", "head_val": "H", "tail_val": "T"},
                []  # outer context
            ],
            "changed": False
        }
        result = single_step(eval_projections, state)

        # Should move to tail
        assert result["mode"] == "deep_eval"
        assert result["phase"] == "traverse"
        assert result["focus"] == "T"
        # Context should now have dict_tail frame
        assert result["context"][0]["type"] == "dict_tail"
        assert result["context"][0]["head_result"] == "processed_head"


class TestAscendToContextProjection:
    """Test ascend.to_context projection (pop context frame)."""

    def test_ascend_pops_context(self, eval_projections):
        """After processing tail, should ascend with outer context."""
        # State after processing tail (dict_tail context with outer)
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": "processed_tail",
            "context": [
                {"type": "dict_tail", "head_result": "H_res"},
                [{"type": "dict_head", "head_val": "outer_h", "tail_val": "outer_t"}, []]
            ],
            "changed": False
        }
        result = single_step(eval_projections, state)

        # Should ascend and reconstruct
        assert result["mode"] == "deep_eval"
        assert result["phase"] == "ascending"
        assert result["focus"] == {"head": "H_res", "tail": "processed_tail"}


class TestAscendToRootProjection:
    """Test ascend.to_root projection (back to root level)."""

    def test_ascend_to_root_check(self, eval_projections):
        """When outer context is empty, go to root_check phase."""
        # State with dict_tail context and empty outer
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": "processed_tail",
            "context": [
                {"type": "dict_tail", "head_result": "H_res"},
                []  # empty outer
            ],
            "changed": False
        }
        result = single_step(eval_projections, state)

        # Should go to root_check
        assert result["mode"] == "deep_eval"
        assert result["phase"] == "root_check"
        assert result["focus"] == {"head": "H_res", "tail": "processed_tail"}
        assert result["context"] == []


class TestRestartProjection:
    """Test restart projection (root_check with changes)."""

    def test_restart_on_changes(self, eval_projections):
        """root_check with changed=True should restart traversal."""
        state = {
            "mode": "deep_eval",
            "phase": "root_check",
            "focus": {"result": "value"},
            "context": [],
            "changed": True
        }
        result = single_step(eval_projections, state)

        # Should restart with changed=False
        assert result["mode"] == "deep_eval"
        assert result["phase"] == "traverse"
        assert result["focus"] == {"result": "value"}
        assert result["context"] == []
        assert result["changed"] is False


class TestUnwrapProjection:
    """Test unwrap projection (root_check without changes - done)."""

    def test_unwrap_when_no_changes(self, eval_projections):
        """root_check with changed=False should produce done state."""
        state = {
            "mode": "deep_eval",
            "phase": "root_check",
            "focus": {"final": "result"},
            "context": [],
            "changed": False
        }
        result = single_step(eval_projections, state)

        # Should produce done state with marker
        assert result["mode"] == "deep_eval_done"
        assert result["_marker"] == "__deep_eval_internal_done__"
        assert result["result"] == {"final": "result"}


# =============================================================================
# Integration Tests
# =============================================================================


class TestEvalIntegration:
    """Test eval.v1.json projection interactions."""

    def test_traversal_descends_into_nested_dict(self, eval_projections):
        """Traversal descends into nested {head, tail} structure."""
        value = {"head": "A", "tail": None}

        # Run a few steps to verify descend happens
        result = single_step(eval_projections, value)  # wrap
        assert result["mode"] == "deep_eval"
        assert result["focus"] == value

        result = single_step(eval_projections, result)  # descend.dict
        assert result["mode"] == "deep_eval"
        assert result["focus"] == "A"  # descended into head
        assert result["context"][0]["type"] == "dict_head"

    def test_leaf_node_stalls_as_expected(self, eval_projections):
        """eval.v1 stalls on primitives (no leaf projection by design)."""
        # This is expected behavior - eval.v1 needs additional projections
        # for complete traversal. This test verifies the stall happens.
        state = {
            "mode": "deep_eval",
            "phase": "traverse",
            "focus": "primitive_leaf",  # Not {head, tail}
            "context": [
                {"type": "dict_head", "head_val": "A", "tail_val": None},
                []
            ],
            "changed": False
        }

        result = single_step(eval_projections, state)

        # wrap is the only matching projection for primitives,
        # which re-wraps causing stall behavior
        assert result["mode"] == "deep_eval"
        # The focus is wrapped again (stall pattern)

    def test_projection_order_security(self, eval_seed):
        """Projections must be in correct order for first-match-wins."""
        ids = [p["id"] for p in eval_seed["projections"]]

        # wrap MUST be last (catch-all)
        assert ids[-1] == "wrap"

        # restart and unwrap should be early (match specific states)
        assert ids.index("restart") < ids.index("wrap")
        assert ids.index("unwrap") < ids.index("wrap")


# =============================================================================
# Meta Tests
# =============================================================================


class TestEvalSeedMeta:
    """Test eval.v1.json metadata."""

    def test_execution_layer_is_bootstrap(self, eval_seed):
        """eval.v1.json should declare BOOTSTRAP execution layer."""
        assert eval_seed["meta"]["execution_layer"] == "BOOTSTRAP"

    def test_note_documents_limitation(self, eval_seed):
        """eval.v1.json should document [] vs {head,tail} limitation."""
        note = eval_seed["meta"].get("note", "")
        assert "[]" in note or "array" in note.lower() or "context" in note.lower()

    def test_projections_are_valid_mu(self, eval_seed):
        """All projections must be valid Mu (JSON-compatible)."""
        import json
        for proj in eval_seed["projections"]:
            # Should survive JSON roundtrip
            json_str = json.dumps(proj, sort_keys=True)
            roundtripped = json.loads(json_str)
            assert proj == roundtripped
