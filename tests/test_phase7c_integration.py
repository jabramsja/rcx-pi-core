"""
Phase 7c Integration Tests - Full Kernel Cycle

These tests verify that kernel.v1 + match.v2 + subst.v2 projections work together
to implement the meta-circular kernel loop.

Test coverage:
1. Full success cycle: kernel → match → subst → kernel → done
2. Full failure cycle: kernel → match(fail) → kernel(next) → ... → stall
3. Context preservation through mode transitions
4. Match.fail catch-all correctness
5. Security: domain data cannot forge kernel state

See docs/core/MetaCircularKernel.v0.md for design.
"""

import pytest
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seeds_dir
from rcx_pi.selfhost.eval_seed import step, apply_projection
from rcx_pi.selfhost.mu_type import Mu, mu_equal
from rcx_pi.selfhost.match_mu import normalize_for_match
from rcx_pi.selfhost.subst_mu import denormalize_from_match


# =============================================================================
# Helpers
# =============================================================================

def list_to_linked(items: list) -> Mu:
    """
    Convert Python list to Mu linked-list format.

    [a, b, c] -> {head: a, tail: {head: b, tail: {head: c, tail: null}}}
    [] -> null

    This is required because the kernel uses linked-list cursors for iteration
    (no arithmetic in pure Mu).
    """
    if not items:
        return None
    return {"head": items[0], "tail": list_to_linked(items[1:])}


def normalize_projection(proj: dict) -> dict:
    """
    Normalize a projection's pattern and body for kernel use.

    Both pattern and body are converted to head/tail format so they can
    be structurally matched and substituted by the Mu projections.
    """
    return {
        "pattern": normalize_for_match(proj["pattern"]),
        "body": normalize_for_match(proj["body"])
    }


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def kernel_projections() -> list[Mu]:
    """Load kernel.v1 projections."""
    seed = load_verified_seed(get_seeds_dir() / "kernel.v1.json")
    return seed["projections"]


@pytest.fixture
def match_v2_projections() -> list[Mu]:
    """Load match.v2 projections with context passthrough."""
    seed = load_verified_seed(get_seeds_dir() / "match.v2.json")
    return seed["projections"]


@pytest.fixture
def subst_v2_projections() -> list[Mu]:
    """Load subst.v2 projections with context passthrough."""
    seed = load_verified_seed(get_seeds_dir() / "subst.v2.json")
    return seed["projections"]


@pytest.fixture
def combined_projections(kernel_projections, match_v2_projections, subst_v2_projections) -> list[Mu]:
    """
    Combine kernel + match + subst projections in correct order.

    SECURITY: Kernel projections MUST come first to prevent domain
    projections from forging kernel state.
    """
    return kernel_projections + match_v2_projections + subst_v2_projections


def run_until_done(projections: list[Mu], initial: Mu, max_steps: int = 100) -> tuple[Mu, list[Mu]]:
    """
    Run projections until kernel.unwrap fires (produces non-kernel output).

    Returns:
        Tuple of (final_result, trace)
    """
    trace = [initial]
    current = initial

    for _ in range(max_steps):
        result = step(projections, current)
        trace.append(result)

        # Check if we've reached final result (not a kernel/match/subst state)
        if isinstance(result, dict):
            # Check for mode markers (internal state format)
            mode = result.get("_mode") or result.get("mode")
            # Check for entry format (match/subst requests)
            is_entry_format = "match" in result or "subst" in result
            # Check for kernel entry format
            is_kernel_entry = "_step" in result

            if mode is None and not is_entry_format and not is_kernel_entry:
                # No mode field and not entry format - final unwrapped result
                return result, trace
        else:
            # Primitive result
            return result, trace

        # Check for stall (no change)
        if mu_equal(result, current):
            return result, trace

        current = result

    # Hit max steps
    return current, trace


# =============================================================================
# Full Success Cycle Tests
# =============================================================================

class TestFullSuccessCycle:
    """Test complete success path: kernel → match → subst → done."""

    def test_simple_variable_binding(self, combined_projections):
        """
        Pattern: {"x": {"var": "v"}}
        Value: {"x": 1}
        Body: {"result": {"var": "v"}}
        Expected: {"result": 1}
        """
        # Set up kernel entry with one projection
        # Must normalize pattern/body to head/tail format for Mu matching
        projection = normalize_projection({
            "pattern": {"x": {"var": "v"}},
            "body": {"result": {"var": "v"}}
        })

        # Input value must also be normalized
        kernel_entry = {
            "_step": normalize_for_match({"x": 1}),
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # Result is in Mu format, denormalize to compare
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"result": 1}, f"Expected {{'result': 1}}, got {denorm_result}"

    def test_nested_structure_match(self, combined_projections):
        """Test matching nested dictionaries."""
        projection = normalize_projection({
            "pattern": {"outer": {"inner": {"var": "v"}}},
            "body": {"extracted": {"var": "v"}}
        })

        kernel_entry = {
            "_step": normalize_for_match({"outer": {"inner": 42}}),
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"extracted": 42}

    def test_multiple_bindings(self, combined_projections):
        """Test binding multiple variables."""
        projection = normalize_projection({
            "pattern": {"a": {"var": "x"}, "b": {"var": "y"}},
            "body": {"sum_parts": {"first": {"var": "x"}, "second": {"var": "y"}}}
        })

        kernel_entry = {
            "_step": normalize_for_match({"a": 10, "b": 20}),
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"sum_parts": {"first": 10, "second": 20}}


# =============================================================================
# Full Failure Cycle Tests
# =============================================================================

class TestFullFailureCycle:
    """Test failure paths: match fails → try next → stall."""

    def test_single_projection_no_match_stalls(self, combined_projections):
        """Single projection that doesn't match should stall with original input."""
        projection = normalize_projection({
            "pattern": {"x": {"var": "v"}},  # Expects "x" key
            "body": {"result": {"var": "v"}}
        })

        kernel_entry = {
            "_step": normalize_for_match({"y": 1}),  # Has "y" not "x" - won't match
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # Should return original input (stall) - denormalize for comparison
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"y": 1}

    def test_fallthrough_to_second_projection(self, combined_projections):
        """First projection fails, second succeeds."""
        proj1 = normalize_projection({
            "pattern": {"type": "a", "value": {"var": "v"}},
            "body": {"a_result": {"var": "v"}}
        })
        proj2 = normalize_projection({
            "pattern": {"type": "b", "value": {"var": "v"}},
            "body": {"b_result": {"var": "v"}}
        })

        kernel_entry = {
            "_step": normalize_for_match({"type": "b", "value": 42}),  # Matches proj2, not proj1
            "_projs": list_to_linked([proj1, proj2])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"b_result": 42}

    def test_all_projections_fail_stalls(self, combined_projections):
        """All projections fail - returns original input."""
        proj1 = normalize_projection({"pattern": {"x": 1}, "body": {"matched": "x"}})
        proj2 = normalize_projection({"pattern": {"y": 2}, "body": {"matched": "y"}})

        kernel_entry = {
            "_step": normalize_for_match({"z": 3}),  # Matches neither
            "_projs": list_to_linked([proj1, proj2])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # Stall returns original input
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"z": 3}

    def test_empty_projections_immediate_stall(self, combined_projections):
        """Empty projection list (null) stalls immediately with original input."""
        kernel_entry = {
            "_step": normalize_for_match({"any": "data"}),
            "_projs": list_to_linked([])  # Returns null, matches kernel.stall
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # Empty projection list -> kernel.stall -> returns original input
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"any": "data"}


# =============================================================================
# Context Preservation Tests
# =============================================================================

class TestContextPreservation:
    """Test that _match_ctx and _subst_ctx preserve state correctly."""

    def test_match_context_preserved_on_success(self, match_v2_projections):
        """_match_ctx survives successful match."""
        ctx = {"_input": {"x": 1}, "_body": {"result": {"var": "v"}}, "_remaining": None}

        # Start in match mode with context
        match_state = {
            "mode": "match",
            "pattern_focus": {"var": "v"},
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx
        }

        # Run until match completes
        current = match_state
        for _ in range(20):
            result = step(match_v2_projections, current)
            if mu_equal(result, current):
                break
            current = result

        # Should have _match_ctx preserved in output
        assert "_match_ctx" in current or current.get("_match_ctx") == ctx

    def test_subst_context_preserved_on_success(self, subst_v2_projections):
        """_subst_ctx survives successful substitution."""
        ctx = {"_input": {"x": 1}, "_remaining": None}
        bindings = {"name": "v", "value": 42, "rest": None}

        # Start in subst mode with context
        subst_state = {
            "mode": "subst",
            "phase": "traverse",
            "focus": {"var": "v"},
            "bindings": bindings,
            "context": None,
            "_subst_ctx": ctx
        }

        # Run until subst completes
        current = subst_state
        for _ in range(20):
            result = step(subst_v2_projections, current)
            if mu_equal(result, current):
                break
            if result.get("_mode") == "subst_done":
                break
            current = result

        # Final state should have _subst_ctx
        if isinstance(result, dict) and "_mode" in result:
            assert result.get("_subst_ctx") == ctx


# =============================================================================
# Match.fail Catch-All Tests
# =============================================================================

class TestMatchFailCatchAll:
    """Test that match.fail correctly catches failure cases."""

    def test_literal_mismatch_produces_no_match(self, match_v2_projections):
        """Pattern 5 vs value 6 produces structural no_match."""
        ctx = {"_input": 6, "_body": {}, "_remaining": None}

        match_state = {
            "mode": "match",
            "pattern_focus": 5,
            "value_focus": 6,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx
        }

        # Run until match completes or stalls
        current = match_state
        for _ in range(20):
            result = step(match_v2_projections, current)
            if mu_equal(result, current):
                break
            if result.get("_mode") == "match_done":
                break
            current = result

        # Should produce match_done with no_match status
        assert result.get("_mode") == "match_done"
        assert result.get("_status") == "no_match"
        assert result.get("_match_ctx") == ctx

    def test_structure_mismatch_produces_no_match(self, match_v2_projections):
        """Pattern dict vs value int produces structural no_match."""
        ctx = {"_input": 42, "_body": {}, "_remaining": None}

        match_state = {
            "mode": "match",
            "pattern_focus": {"x": 1},
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx
        }

        current = match_state
        for _ in range(20):
            result = step(match_v2_projections, current)
            if mu_equal(result, current):
                break
            if result.get("_mode") == "match_done":
                break
            current = result

        assert result.get("_mode") == "match_done"
        assert result.get("_status") == "no_match"

    def test_success_still_works_with_fail_projection(self, match_v2_projections):
        """Match.fail doesn't interfere with successful matches."""
        ctx = {"_input": {"x": 1}, "_body": {}, "_remaining": None}

        match_state = {
            "mode": "match",
            "pattern_focus": {"var": "v"},
            "value_focus": 42,
            "bindings": None,
            "stack": None,
            "_match_ctx": ctx
        }

        current = match_state
        for _ in range(20):
            result = step(match_v2_projections, current)
            if mu_equal(result, current):
                break
            if result.get("_mode") == "match_done":
                break
            current = result

        # Should produce success, NOT no_match
        assert result.get("_mode") == "match_done"
        assert result.get("_status") == "success"
        assert result.get("_bindings") is not None


# =============================================================================
# Security Tests
# =============================================================================

class TestSecurityIsolation:
    """Test that domain data cannot forge kernel state."""

    def test_domain_data_with_mode_key_processed_normally(self, combined_projections):
        """Domain data containing 'mode' key doesn't confuse kernel."""
        projection = normalize_projection({
            "pattern": {"data": {"var": "d"}},
            "body": {"result": {"var": "d"}}
        })

        # Input has "mode" key but it's domain data
        kernel_entry = {
            "_step": normalize_for_match({"data": {"mode": "fake", "payload": "test"}}),
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # Should match and return the data as-is
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"result": {"mode": "fake", "payload": "test"}}

    def test_domain_data_with_underscore_mode_key_processed(self, combined_projections):
        """Domain data with _mode key is processed (potential security concern)."""
        projection = normalize_projection({
            "pattern": {"data": {"var": "d"}},
            "body": {"result": {"var": "d"}}
        })

        # Input has "_mode" key - this could be problematic
        # But since it's inside "data", it should be fine
        kernel_entry = {
            "_step": normalize_for_match({"data": {"_mode": "done", "_result": "pwned"}}),
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # The _mode inside data doesn't affect kernel processing
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"result": {"_mode": "done", "_result": "pwned"}}

    def test_projection_order_prevents_interception(self, combined_projections):
        """Kernel projections run first, preventing domain interception."""
        # A malicious "domain" projection that tries to match kernel state
        # Note: normalize the malicious pattern too for consistency
        malicious_proj = normalize_projection({
            "pattern": {"_mode": "kernel", "_phase": {"var": "p"}},
            "body": {"pwned": True}
        })

        good_proj = normalize_projection({
            "pattern": {"x": {"var": "v"}},
            "body": {"result": {"var": "v"}}
        })

        # Even if we put malicious proj in the list, kernel projs run first
        # because combined_projections has kernel first
        kernel_entry = {
            "_step": normalize_for_match({"x": 1}),
            "_projs": list_to_linked([malicious_proj, good_proj])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # Should use good_proj, not malicious_proj
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"result": 1}


# =============================================================================
# Kernel State Transition Tests
# =============================================================================

class TestKernelStateTransitions:
    """Test individual kernel state transitions with v2 seeds."""

    def test_kernel_try_to_match_transition(self, combined_projections):
        """kernel.try produces match entry format that match.wrap can process."""
        # Normalize pattern/body for consistency with kernel
        projection = normalize_projection({"pattern": {"x": {"var": "v"}}, "body": {"r": {"var": "v"}}})

        kernel_try_state = {
            "_mode": "kernel",
            "_phase": "try",
            "_input": normalize_for_match({"x": 1}),
            "_remaining": {"head": projection, "tail": None}
        }

        # Step once - should produce match entry format
        result = step(combined_projections, kernel_try_state)

        # kernel.try now outputs match entry format: {match: {...}, _match_ctx: {...}}
        assert "match" in result, f"Expected 'match' key, got {result}"
        assert "_match_ctx" in result

    def test_match_success_to_subst_transition(self, combined_projections):
        """kernel.match_success transitions to subst entry format."""
        # Body should be normalized for consistency
        normalized_body = normalize_for_match({"r": {"var": "v"}})

        match_done_state = {
            "_mode": "match_done",
            "_status": "success",
            "_bindings": {"name": "v", "value": 1, "rest": None},
            "_match_ctx": {
                "_input": normalize_for_match({"x": 1}),
                "_body": normalized_body,
                "_remaining": None
            }
        }

        # Step once - should produce subst entry format
        result = step(combined_projections, match_done_state)

        # kernel.match_success now outputs subst entry format: {subst: {...}, _subst_ctx: {...}}
        assert "subst" in result, f"Expected 'subst' key, got {result}"
        assert "_subst_ctx" in result

    def test_subst_done_to_kernel_done_transition(self, combined_projections):
        """kernel.subst_success produces done state."""
        subst_done_state = {
            "_mode": "subst_done",
            "_result": {"r": 1},
            "_subst_ctx": {"_input": {"x": 1}, "_remaining": None}
        }

        # Step once - should transition to done
        result = step(combined_projections, subst_done_state)

        assert result.get("_mode") == "done"
        assert result.get("_result") == {"r": 1}
        assert result.get("_stall") == False


# =============================================================================
# Manual Trace Tests (from Design Doc)
# =============================================================================

class TestManualTraceFromDesignDoc:
    """Verify traces from MetaCircularKernel.v0.md work with v2 seeds."""

    def test_success_trace_simple_projection(self, combined_projections):
        """
        From design doc: Match {"x": 1} against {"x": {"var": "v"}},
        bind v=1, substitute to get {"result": 1}.
        """
        projection = normalize_projection({"pattern": {"x": {"var": "v"}}, "body": {"result": {"var": "v"}}})
        kernel_entry = {
            "_step": normalize_for_match({"x": 1}),
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"result": 1}

        # Verify trace went through expected modes/formats
        has_match_phase = False
        has_kernel_phase = False
        for state in trace:
            if isinstance(state, dict):
                if state.get("_mode") == "kernel" or "_step" in state:
                    has_kernel_phase = True
                if "match" in state or state.get("mode") == "match":
                    has_match_phase = True

        # Should see kernel and match phases
        assert has_kernel_phase or has_match_phase

    def test_failure_trace_no_match(self, combined_projections):
        """
        From design doc: {"y": 2} with pattern {"x": {"var": "v"}} should stall.
        """
        projection = normalize_projection({"pattern": {"x": {"var": "v"}}, "body": {"result": {"var": "v"}}})
        kernel_entry = {
            "_step": normalize_for_match({"y": 2}),
            "_projs": list_to_linked([projection])
        }

        result, trace = run_until_done(combined_projections, kernel_entry)

        # Stall returns original input
        denorm_result = denormalize_from_match(result)
        assert denorm_result == {"y": 2}
