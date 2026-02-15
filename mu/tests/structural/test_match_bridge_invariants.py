"""
Match bridge invariant tests.

Validates the B-structural approach: match_mu uses match.v2 + bridge projections
for non-linear pattern conflict detection. These tests lock the structural invariants
that make this work correctly.
"""

from __future__ import annotations

import pytest

from rcx_pi.selfhost.match_mu import (
    load_match_with_bridge_projections,
    clear_match_bridge_cache,
    _validate_match_bridge_ordering,  # ANTICHEAT_OK: grounding test for bridge ordering invariant
)
from rcx_pi.selfhost.projection_runner import make_projection_runner

pytestmark = [pytest.mark.slow]


# =============================================================================
# Bridge Ordering Invariants
# =============================================================================


class TestBridgeOrderingInvariant:
    """Lock the projection ordering that makes non-linear conflict detection work."""

    def test_all_five_bridge_projections_present(self):
        """All 5 bridge projections must be in the combined set."""
        projs = load_match_with_bridge_projections()
        ids = [p.get("id") for p in projs]

        expected_bridge = [
            "bridge.var.check_existing",
            "bridge.lookup.found_same",
            "bridge.lookup.found_different",
            "bridge.lookup.not_found_yet",
            "bridge.lookup.not_found",
        ]
        for bid in expected_bridge:
            assert bid in ids, f"Bridge projection {bid} missing from combined set"

    def test_bridge_check_existing_before_match_var(self):
        """bridge.var.check_existing MUST come before match.var."""
        projs = load_match_with_bridge_projections()
        ids = [p.get("id") for p in projs]

        bridge_idx = ids.index("bridge.var.check_existing")
        var_idx = ids.index("match.var")

        assert bridge_idx < var_idx, (
            f"bridge.var.check_existing (idx {bridge_idx}) must come before "
            f"match.var (idx {var_idx})"
        )

    def test_bridge_found_same_before_found_different(self):
        """bridge.lookup.found_same MUST come before bridge.lookup.found_different.

        Same-value case must be checked first; different-value returns NO_MATCH.
        """
        projs = load_match_with_bridge_projections()
        ids = [p.get("id") for p in projs]

        same_idx = ids.index("bridge.lookup.found_same")
        diff_idx = ids.index("bridge.lookup.found_different")

        assert same_idx < diff_idx, (
            f"bridge.lookup.found_same (idx {same_idx}) must come before "
            f"bridge.lookup.found_different (idx {diff_idx})"
        )

    def test_match_wrap_is_last(self):
        """match.wrap (entry point) must be the last projection."""
        projs = load_match_with_bridge_projections()
        assert projs[-1].get("id") == "match.wrap", (
            f"match.wrap must be last, got {projs[-1].get('id')}"
        )

    def test_total_projection_count(self):
        """Combined set should have 13 projections (8 match.v2 + 5 bridge)."""
        projs = load_match_with_bridge_projections()
        assert len(projs) == 13, f"Expected 13 projections, got {len(projs)}"

    def test_validate_rejects_wrong_ordering(self):
        """_validate_match_bridge_ordering rejects if bridge comes after match.var."""
        wrong_order = [
            {"id": "match.var"},
            {"id": "bridge.var.check_existing"},
        ]
        with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
            _validate_match_bridge_ordering(wrong_order)

    def test_validate_rejects_missing_bridge(self):
        """_validate_match_bridge_ordering rejects if bridge missing."""
        no_bridge = [
            {"id": "match.var"},
        ]
        with pytest.raises(ValueError, match="INVARIANT VIOLATION"):
            _validate_match_bridge_ordering(no_bridge)

    def test_cache_clear_forces_reload(self):
        """clear_match_bridge_cache forces a fresh load."""
        # Load once (populates cache)
        projs1 = load_match_with_bridge_projections()

        # Clear and reload
        clear_match_bridge_cache()
        projs2 = load_match_with_bridge_projections()

        # Both should have same structure
        assert len(projs1) == len(projs2)
        assert [p.get("id") for p in projs1] == [p.get("id") for p in projs2]


# =============================================================================
# Projection Runner terminal_field Tests
# =============================================================================


class TestProjectionRunnerTerminalField:
    """Verify terminal_field parameter backward compatibility and v2 support."""

    def test_default_terminal_field_uses_mode(self):
        """Default terminal_field='mode' works for v1 callers."""
        is_done, is_state, _ = make_projection_runner("match")

        # v1 terminal state
        v1_done = {"mode": "match_done", "status": "success", "bindings": None}
        assert is_done(v1_done) is True

        # v1 in-progress state
        v1_progress = {"mode": "match", "pattern": "...", "value": "..."}
        assert is_state(v1_progress) is True

        # v2 terminal state should NOT match v1 runner
        v2_done = {"_mode": "match_done", "_status": "success", "_bindings": None}
        assert is_done(v2_done) is False

    def test_underscore_mode_terminal_field_for_v2(self):
        """terminal_field='_mode' works for v2 callers."""
        is_done_v2, is_state_v2, _ = make_projection_runner("match", terminal_field="_mode")

        # v2 terminal state
        v2_done = {"_mode": "match_done", "_status": "success", "_bindings": None}
        assert is_done_v2(v2_done) is True

        # v1 terminal state should NOT match v2 runner
        v1_done = {"mode": "match_done", "status": "success", "bindings": None}
        assert is_done_v2(v1_done) is False

        # v2 in-progress state still uses "mode" (not "_mode")
        v2_progress = {"mode": "match", "match": {"pattern": "...", "value": "..."}}
        assert is_state_v2(v2_progress) is True

    def test_is_done_rejects_non_dict(self):
        """is_done returns False for non-dict values."""
        is_done, _, _ = make_projection_runner("match")
        assert is_done("not a dict") is False
        assert is_done(42) is False
        assert is_done(None) is False

    def test_is_done_rejects_wrong_mode(self):
        """is_done returns False for wrong mode value."""
        is_done, _, _ = make_projection_runner("match")
        assert is_done({"mode": "subst_done"}) is False
        assert is_done({"mode": "match"}) is False

    def test_subst_runner_unaffected(self):
        """Existing subst runner still works with default terminal_field."""
        is_done, is_state, _ = make_projection_runner("subst")
        assert is_done({"mode": "subst_done", "result": 42}) is True
        assert is_state({"mode": "subst", "body": "...", "bindings": "..."}) is True


# =============================================================================
# Split Semantics Documentation (step_mu/run_mu vs apply_mu/match_mu)
# =============================================================================


class TestSplitSemanticsContract:
    """Document and lock the intentional semantic split (fail-closed).

    apply_mu/match_mu: Use match.v2 + bridge (non-linear conflict detection).
    step_mu/run_mu: Use core kernel (linear-only). Rejects non-linear patterns.
    run_algorithm_meta_circular: Uses bridge kernel for algorithm seeds
        (recurrence, exhaustion) which contain non-linear patterns.
    """

    def test_apply_mu_detects_nonlinear_conflict(self):
        """apply_mu routes through match_mu (bridge) — detects conflicts."""
        from rcx_pi.selfhost.step_mu import apply_mu
        from rcx_pi.selfhost.eval_seed import NO_MATCH

        proj = {"pattern": {"a": {"var": "x"}, "b": {"var": "x"}}, "body": "ok"}
        result = apply_mu(proj, {"a": 1, "b": 2})
        assert result is NO_MATCH, "apply_mu must detect non-linear conflicts"

    def test_apply_mu_accepts_nonlinear_agreement(self):
        """apply_mu routes through match_mu (bridge) — same values succeed."""
        from rcx_pi.selfhost.step_mu import apply_mu

        proj = {"pattern": {"a": {"var": "x"}, "b": {"var": "x"}}, "body": "ok"}
        result = apply_mu(proj, {"a": 1, "b": 1})
        assert result == "ok", "apply_mu must succeed when non-linear vars agree"

    def test_step_mu_uses_core_kernel_for_linear(self):
        """step_mu routes through step_kernel_mu(core) for linear patterns."""
        from rcx_pi.selfhost.step_mu import step_mu

        projs = [{"pattern": {"op": "double", "v": {"var": "x"}},
                  "body": {"op": "done", "v": {"var": "x"}}}]
        result = step_mu(projs, {"op": "double", "v": 7})
        assert result == {"op": "done", "v": 7}

    def test_step_mu_rejects_nonlinear_patterns(self):
        """step_mu is fail-closed: rejects non-linear patterns with ValueError."""
        from rcx_pi.selfhost.step_mu import step_mu

        projs = [{"pattern": {"a": {"var": "x"}, "b": {"var": "x"}}, "body": "ok"}]
        with pytest.raises(ValueError, match="non-linear pattern"):
            step_mu(projs, {"a": 1, "b": 2})

    def test_run_mu_rejects_nonlinear_patterns(self):
        """run_mu is fail-closed: rejects non-linear patterns with ValueError."""
        from rcx_pi.selfhost.step_mu import run_mu

        projs = [{"pattern": {"a": {"var": "x"}, "b": {"var": "x"}}, "body": "ok"}]
        with pytest.raises(ValueError, match="non-linear pattern"):
            run_mu(projs, {"a": 1, "b": 2})
