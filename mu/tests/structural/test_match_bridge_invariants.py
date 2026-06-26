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
pytestmark = [pytest.mark.slow]

ONE = {"_num": {"xH": None}}
TWO = {"_num": {"xO": {"xH": None}}}


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
        result = apply_mu(proj, {"a": ONE, "b": TWO})
        assert result is NO_MATCH, "apply_mu must detect non-linear conflicts"

    def test_apply_mu_accepts_nonlinear_agreement(self):
        """apply_mu routes through match_mu (bridge) — same values succeed."""
        from rcx_pi.selfhost.step_mu import apply_mu

        proj = {"pattern": {"a": {"var": "x"}, "b": {"var": "x"}}, "body": "ok"}
        result = apply_mu(proj, {"a": ONE, "b": ONE})
        assert result == "ok", "apply_mu must succeed when non-linear vars agree"

    def test_step_mu_uses_core_kernel_for_linear(self):
        """step_mu routes through step_kernel_mu(core) for linear patterns."""
        from rcx_pi.selfhost.step_mu import step_mu

        projs = [{"pattern": {"op": "double", "v": {"var": "x"}},
                  "body": {"op": "done", "v": {"var": "x"}}}]
        result = step_mu(projs, {"op": "double", "v": ONE})
        assert result == {"op": "done", "v": ONE}

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


# =============================================================================
# JS Cross-Substrate Non-Linear Rejection (W6 parity)
# =============================================================================


class TestJSNonlinearRejectionParity:
    """Verify JS direct-kernel entrypoints reject non-linear domain projections.

    Contract (W6):
    - Direct JS core-kernel entrypoints reject non-linear domain projections
      regardless of whether values would agree or conflict.
    - Bridge algorithm execution remains allowed because it bypasses these guard sites.
    - step_kernel_meta(kernelMode='bridge') is still treated as a direct external
      kernel API and therefore rejects non-linear domain projections.
    """

    NONLINEAR_PROJ = {"id": "nl.test", "pattern": {"a": {"var": "x"}, "b": {"var": "x"}}, "body": "ok"}
    AGREE_INPUT = {"a": "same", "b": "same"}
    CONFLICT_INPUT = {"a": 1, "b": 2}

    def _run_js_api(self, request_dict):
        import json
        import subprocess
        from tests.repo_root import REPO_ROOT
        result = subprocess.run(
            ["node", "mu/host/js/eval_step.js", "--json-api", json.dumps(request_dict)],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        for line in result.stdout.split('\n'):
            if line.startswith('JSON_API_RESPONSE:'):
                return json.loads(line[len('JSON_API_RESPONSE:'):])
        raise RuntimeError(f"No JSON_API_RESPONSE: {result.stdout[:500]}")

    def test_js_run_vector_rejects_nonlinear_conflict(self):
        """JS run_vector rejects non-linear projection (conflict input)."""
        resp = self._run_js_api({
            "action": "run_vector",
            "projection": self.NONLINEAR_PROJ,
            "input": self.CONFLICT_INPUT,
        })
        assert not resp["success"], "run_vector should reject non-linear projection"
        assert "non-linear pattern" in resp["error"]
        assert resp.get("error_code") == "input.nonlinear_pattern"

    def test_js_run_vector_rejects_nonlinear_agree(self):
        """JS run_vector rejects non-linear projection even when values agree."""
        resp = self._run_js_api({
            "action": "run_vector",
            "projection": self.NONLINEAR_PROJ,
            "input": self.AGREE_INPUT,
        })
        assert not resp["success"], "run_vector must reject by shape, not runtime"
        assert "non-linear pattern" in resp["error"]

    def test_js_step_kernel_meta_rejects_nonlinear(self):
        """JS step_kernel_meta rejects non-linear domain projections.

        step_kernel_meta is a direct external kernel API — non-linear domain
        projections are rejected even when kernelMode='bridge'.
        """
        resp = self._run_js_api({
            "action": "step_kernel_meta",
            "input": self.AGREE_INPUT,
            "projections": [self.NONLINEAR_PROJ],
        })
        assert not resp["success"], "step_kernel_meta should reject non-linear"
        assert "non-linear pattern" in resp["error"]

    def test_js_run_structural_trace_rejects_nonlinear(self):
        """JS run_structural_trace rejects non-linear domain projections."""
        resp = self._run_js_api({
            "action": "run_structural_trace",
            "projections": [self.NONLINEAR_PROJ],
            "input": self.AGREE_INPUT,
        })
        assert not resp["success"], "run_structural_trace should reject non-linear"
        assert "non-linear pattern" in resp["error"]

    def test_js_run_recurrence_bridge_accepts_nonlinear(self):
        """JS run_recurrence (bridge algorithm path) accepts non-linear seeds.

        Bridge algorithm execution bypasses stepKernel/runStructural entirely
        (uses _stepKernelCoreNonMeta). Non-linear patterns in algorithm seeds
        (recurrence, exhaustion) are valid and expected.
        """
        resp = self._run_js_api({
            "action": "run_recurrence",
            "input": [1, 2, 3, 1],
        })
        # run_recurrence uses recurrence seeds which contain non-linear patterns.
        # It must succeed (bridge path, not guarded).
        assert resp["success"], f"run_recurrence should succeed: {resp.get('error')}"


# =============================================================================
# Non-Linear Scanner Alias Bypass Tests
# =============================================================================


class TestNonlinearScannerAliasBypass:
    """Prove that the non-linear scanner treats shared object references as
    repeated structure — not as host-identity dedup targets.

    The old implementation used a seen set (Python id(), JS Set identity) to
    skip already-visited objects. This caused shared references to be traversed
    only once, hiding non-linear variable usage when callers reused the same
    object in multiple pattern positions.
    """

    def test_python_alias_leaf_detected(self):
        """Python: same {var: x} object in two positions is non-linear."""
        from rcx_pi.selfhost.step_mu import _has_nonlinear_vars  # ANTICHEAT_OK: grounding test for alias bypass fix

        v = {"var": "x"}
        pattern = {"a": v, "b": v}  # same object ref
        assert _has_nonlinear_vars(pattern), (
            "Aliased var leaf must be counted twice (non-linear)"
        )

    def test_python_alias_subtree_detected(self):
        """Python: same subtree object containing {var: x} in two positions is non-linear."""
        from rcx_pi.selfhost.step_mu import _has_nonlinear_vars  # ANTICHEAT_OK: grounding test for alias bypass fix

        sub = {"inner": {"var": "x"}}
        pattern = {"a": sub, "b": sub}  # same object ref
        assert _has_nonlinear_vars(pattern), (
            "Aliased subtree containing var must be traversed twice (non-linear)"
        )

    def test_python_distinct_repeated_structure_detected(self):
        """Python: distinct objects with same var name is non-linear."""
        from rcx_pi.selfhost.step_mu import _has_nonlinear_vars  # ANTICHEAT_OK: grounding test for alias bypass fix

        pattern = {"a": {"var": "x"}, "b": {"var": "x"}}  # distinct objects
        assert _has_nonlinear_vars(pattern), (
            "Distinct repeated var structure must be detected as non-linear"
        )

    def test_python_cycle_fails_closed(self):
        """Python: cyclic pattern hits iteration cap and fail-closes as non-linear."""
        from rcx_pi.selfhost.step_mu import _has_nonlinear_vars  # ANTICHEAT_OK: grounding test for alias bypass fix

        # Create a cycle: pattern -> inner -> pattern
        pattern = {"inner": None}
        pattern["inner"] = pattern
        assert _has_nonlinear_vars(pattern), (
            "Cyclic pattern must fail-closed as non-linear (iteration cap)"
        )

    def _run_js_helper(self, script):
        """Run a node -e script that requires hasNonlinearVars directly."""
        import subprocess
        from tests.repo_root import REPO_ROOT
        # Wrap script with require and output
        full_script = (
            "const { hasNonlinearVars } = require('./mu/host/js/core/security');\n"
            + script
        )
        result = subprocess.run(
            ["node", "-e", full_script],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=60,
        )
        assert result.returncode == 0, (
            f"node -e failed: stdout={result.stdout[:300]} stderr={result.stderr[:300]}"
        )
        return result.stdout.strip()

    def test_js_alias_leaf_detected(self):
        """JS: same {var: x} object ref in two positions is non-linear."""
        output = self._run_js_helper(
            "const v = {var: 'x'};\n"
            "const pattern = {a: v, b: v};\n"  # same object ref
            "const result = hasNonlinearVars(pattern);\n"
            "console.log(result ? 'NONLINEAR' : 'LINEAR');\n"
        )
        assert output == "NONLINEAR", (
            f"JS hasNonlinearVars must detect aliased var leaf: got {output}"
        )

    def test_js_alias_subtree_detected(self):
        """JS: same subtree object ref containing {var: x} in two positions is non-linear."""
        output = self._run_js_helper(
            "const sub = {inner: {var: 'x'}};\n"
            "const pattern = {a: sub, b: sub};\n"  # same object ref
            "const result = hasNonlinearVars(pattern);\n"
            "console.log(result ? 'NONLINEAR' : 'LINEAR');\n"
        )
        assert output == "NONLINEAR", (
            f"JS hasNonlinearVars must detect aliased subtree: got {output}"
        )

    def test_js_distinct_repeated_structure_detected(self):
        """JS: distinct objects with same var name is non-linear."""
        output = self._run_js_helper(
            "const pattern = {a: {var: 'x'}, b: {var: 'x'}};\n"  # distinct objects
            "const result = hasNonlinearVars(pattern);\n"
            "console.log(result ? 'NONLINEAR' : 'LINEAR');\n"
        )
        assert output == "NONLINEAR", (
            f"JS hasNonlinearVars must detect distinct repeated var: got {output}"
        )

    def test_js_cycle_fails_closed(self):
        """JS: cyclic pattern hits iteration cap and fail-closes as non-linear."""
        output = self._run_js_helper(
            "const pattern = {inner: null};\n"
            "pattern.inner = pattern;\n"  # cycle
            "const result = hasNonlinearVars(pattern);\n"
            "console.log(result ? 'NONLINEAR' : 'LINEAR');\n"
        )
        assert output == "NONLINEAR", (
            f"JS hasNonlinearVars must fail-closed on cycle: got {output}"
        )
