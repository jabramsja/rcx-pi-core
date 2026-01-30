"""
L2 Cursor Grounding Tests

Grounds the claim that L2 projection selection uses a linked-list cursor,
not arithmetic indexing. This is a key L2 architectural requirement.

From STATUS.md L2 Completion Criteria:
- [x] Projection selection uses linked-list cursor (`_remaining` field, no index arithmetic)

These tests verify that claim is true in the actual code.
"""

import json
import pytest

from rcx_pi.selfhost.step_mu import (
    list_to_linked,
    normalize_projection,
    load_combined_kernel_projections,
)
from rcx_pi.selfhost.eval_seed import step as eval_step


class TestLinkedListCursorExists:
    """Verify _remaining field is structural linked-list, not integer index."""

    def test_list_to_linked_produces_head_tail_structure(self):
        """list_to_linked produces {head: x, tail: ...} linked list."""
        result = list_to_linked([1, 2, 3])

        # Must be dict with head and tail
        assert isinstance(result, dict)
        assert "head" in result
        assert "tail" in result

        # First element is 1
        assert result["head"] == 1

        # Tail is nested linked list
        tail = result["tail"]
        assert isinstance(tail, dict)
        assert tail["head"] == 2
        assert tail["tail"]["head"] == 3
        assert tail["tail"]["tail"] is None

    def test_list_to_linked_empty_is_none(self):
        """Empty list becomes None (linked-list terminator)."""
        result = list_to_linked([])
        assert result is None

    def test_list_to_linked_single_element(self):
        """Single element list has None tail."""
        result = list_to_linked([42])
        assert result == {"head": 42, "tail": None}


class TestKernelUsesRemainingField:
    """Verify kernel.v1.json projections use _remaining for cursor."""

    def test_kernel_wrap_creates_remaining_linked_list(self):
        """kernel.wrap creates _remaining from _projs linked list."""
        projs = load_combined_kernel_projections()

        # Find kernel.wrap projection
        wrap = None
        for p in projs:
            if p.get("id") == "kernel.wrap":
                wrap = p
                break

        assert wrap is not None, "kernel.wrap projection must exist"

        # Pattern must match _projs
        pattern = wrap["pattern"]
        assert "_projs" in pattern or (isinstance(pattern.get("_projs"), dict) and "var" in pattern["_projs"])

        # Body must create _remaining
        body = wrap["body"]
        assert "_remaining" in body, "kernel.wrap must create _remaining field"

    def test_kernel_try_consumes_remaining_head(self):
        """kernel.try reads head of _remaining linked list."""
        projs = load_combined_kernel_projections()

        # Find kernel.try projection
        try_proj = None
        for p in projs:
            if p.get("id") == "kernel.try":
                try_proj = p
                break

        assert try_proj is not None, "kernel.try projection must exist"

        # Pattern must match _remaining with head structure
        pattern = try_proj["pattern"]
        remaining = pattern.get("_remaining", {})

        # _remaining must be {head: ..., tail: ...} pattern (linked list)
        assert "head" in remaining, "_remaining must be matched as linked list"
        assert "tail" in remaining, "_remaining must have tail for cursor advancement"

    def test_kernel_match_fail_advances_cursor(self):
        """kernel.match_fail advances cursor by setting _remaining to tail."""
        projs = load_combined_kernel_projections()

        # Find kernel.match_fail projection (this is where cursor advances)
        match_fail = None
        for p in projs:
            if p.get("id") == "kernel.match_fail":
                match_fail = p
                break

        assert match_fail is not None, "kernel.match_fail projection must exist"

        # Pattern should have _match_ctx with _remaining
        pattern = match_fail["pattern"]
        match_ctx = pattern.get("_match_ctx", {})
        assert "_remaining" in match_ctx, "_match_ctx must have _remaining"

        # Body should set _remaining to the captured "rest" (tail of list)
        body = match_fail["body"]
        new_remaining = body.get("_remaining", {})

        # The new _remaining should reference var "rest" - the tail
        # This is structural cursor advancement (no arithmetic)
        assert isinstance(new_remaining, dict), "_remaining in body must be dict"
        assert new_remaining.get("var") == "rest", "_remaining should be set to 'rest' (the tail)"


class TestNoArithmeticIndexing:
    """Verify kernel projections don't use integer indexing."""

    def test_kernel_projections_have_no_integer_index_fields(self):
        """No kernel projection uses integer index fields like _index or _position."""
        projs = load_combined_kernel_projections()

        kernel_projs = [p for p in projs if p.get("id", "").startswith("kernel.")]

        # Fields that would indicate arithmetic indexing (NOT valid semantic fields)
        arithmetic_fields = ["_index", "_position", "_count", "_cursor_int", "_offset"]

        for proj in kernel_projs:
            pattern_json = json.dumps(proj["pattern"])
            body_json = json.dumps(proj["body"])
            combined = pattern_json + body_json

            # Check for explicit index-like field names
            # Note: _input is valid (not an index), so we check explicit patterns
            for field in arithmetic_fields:
                # Check as JSON key: "field_name":
                json_key = f'"{field}":'
                assert json_key not in combined, f"{proj['id']} uses {field} (arithmetic indexing)"

    def test_remaining_is_structural_not_numeric(self):
        """_remaining field contains structure, not number."""
        projs = load_combined_kernel_projections()

        # Build a test input
        test_projs = list_to_linked([
            normalize_projection({"pattern": 1, "body": 2}),
            normalize_projection({"pattern": 3, "body": 4}),
        ])

        test_input = {"_step": 42, "_projs": test_projs}

        # Apply kernel.wrap
        result = eval_step(projs, test_input)

        # _remaining should be a linked list, not an integer
        if isinstance(result, dict) and "_remaining" in result:
            remaining = result["_remaining"]

            # Must NOT be an integer (arithmetic cursor)
            assert not isinstance(remaining, int), "_remaining must be structure, not integer"

            # Should be None or a dict with head/tail
            assert remaining is None or isinstance(remaining, dict)
            if remaining is not None:
                assert "head" in remaining or remaining == {}, \
                    "_remaining must be linked list (head/tail) or empty"


class TestCursorTraversalEndToEnd:
    """Verify cursor traversal works structurally from start to finish."""

    def test_cursor_reaches_none_at_end(self):
        """After trying all projections, _remaining becomes None."""
        projs = load_combined_kernel_projections()

        # Input that won't match any domain projection
        test_projs = list_to_linked([
            normalize_projection({"pattern": "never_matches", "body": "x"}),
        ])

        test_input = {"_step": 42, "_projs": test_projs}

        # Run until terminal or max steps
        current = test_input
        seen_states = []

        for _ in range(20):  # Bounded iteration
            result = eval_step(projs, current)

            if isinstance(result, dict):
                if "_remaining" in result:
                    remaining = result["_remaining"]
                    seen_states.append(("_remaining", type(remaining).__name__))

                if result.get("_mode") == "done":
                    break

            if result == current:  # Stall
                break

            current = result

        # Should have seen _remaining eventually become None
        # (cursor exhausted the linked list)
        remaining_types = [s[1] for s in seen_states if s[0] == "_remaining"]

        # Either we reached done state, or _remaining became None/NoneType
        assert "NoneType" in remaining_types or (
            isinstance(current, dict) and current.get("_mode") == "done"
        ), "Cursor should exhaust linked list (reach None) or complete"
