"""
Wave 3B/3E gate test: subst_mu semantic unification to subst.v2 + VM runner.

Verifies that subst_mu() executes via stage0_vm_run_bounded with the compiled
subst.v2 bundle, preserving public API behavior (including KeyError for
unbound variables).

Wave 3E additions: budget accounting, exhaustion path, stall budget, mock update.
"""

from __future__ import annotations

import json

import pytest

from rcx_pi.selfhost.subst_mu import subst_mu
from rcx_pi.selfhost.subst_mu import _load_compiled_subst_v2_bundle  # ANTICHEAT_OK: test-only — gate test for bundle loading + provenance
from rcx_pi.selfhost.subst_mu import _clear_compiled_subst_v2_bundle  # ANTICHEAT_OK: test-only — cache clear for provenance test


class TestSubstVMUnificationGate:
    """Evidence that subst_mu uses compiled subst.v2 + VM execution."""

    def test_simple_substitution_via_vm(self):
        """Basic substitution works through VM path."""
        result = subst_mu({"var": "x"}, {"x": 42})
        assert result == 42

    def test_dict_substitution_via_vm(self):
        """Dict body with var substitution works through VM path."""
        result = subst_mu({"a": {"var": "x"}, "b": 1}, {"x": 99})
        assert result == {"a": 99, "b": 1}

    def test_no_vars_passthrough(self):
        """Body without vars returns unchanged."""
        result = subst_mu({"a": 1, "b": 2}, {"x": 99})
        assert result == {"a": 1, "b": 2}

    def test_unbound_variable_raises_keyerror(self):
        """Unbound variable must still raise KeyError (public API contract)."""
        with pytest.raises(KeyError, match="Unbound variable"):
            subst_mu({"var": "z"}, {"x": 42})

    def test_compiled_bundle_loads(self):
        """Compiled subst.v2 bundle loads and validates."""
        bundle = _load_compiled_subst_v2_bundle()
        assert isinstance(bundle, dict)
        assert "programs" in bundle
        assert len(bundle["programs"]) > 0

    def test_bundle_provenance_rejects_wrong_digest(self):
        """N15: wrong source_digest raises ValueError through the factory loader."""
        from rcx_pi.selfhost.seed_integrity import SEED_CHECKSUMS
        import rcx_pi.selfhost.subst_mu as subst_mod

        # Load the real bundle to get seed name for assertion
        bundle = _load_compiled_subst_v2_bundle()
        source_seed = bundle.get("source_seed", "")
        seed_filename = source_seed if source_seed.endswith(".json") else source_seed + ".json"
        assert seed_filename in SEED_CHECKSUMS, "subst.v2 must be in SEED_CHECKSUMS"

        # Clear cache via factory clear function, then mock open to return tampered bundle
        tampered = dict(bundle)
        tampered["source_digest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        subst_mod._clear_compiled_subst_v2_bundle()  # ANTICHEAT_OK: test-only — clear factory cache

        import unittest.mock
        with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(tampered))):
            with pytest.raises(ValueError, match="SECURITY.*provenance mismatch"):
                subst_mod._load_compiled_subst_v2_bundle()  # ANTICHEAT_OK: test-only — verifying provenance rejection

        # Restore cache
        subst_mod._clear_compiled_subst_v2_bundle()  # ANTICHEAT_OK: test-only — clear for reload
        subst_mod._load_compiled_subst_v2_bundle()  # ANTICHEAT_OK: test-only — restore valid bundle

    def test_vm_fault_propagates(self):
        """Stage0VMError from VM must propagate, not be swallowed.

        Wave 3E: mock target updated from stage0_vm_run to
        stage0_vm_run_bounded (subst_mu no longer calls stage0_vm_run).
        """
        from rcx_pi.selfhost.stage0_vm import Stage0VMError
        import unittest.mock

        fake_error = Stage0VMError("Op limit exceeded (test)")
        with unittest.mock.patch(
            "rcx_pi.selfhost.stage0_vm.stage0_vm_run_bounded",
            side_effect=fake_error,
        ):
            with pytest.raises(Stage0VMError, match="Op limit exceeded"):
                subst_mu({"var": "x"}, {"x": 42})

    # --- Wave 3E gate tests: bounded helper integration ---

    def test_bounded_budget_consumed_on_terminal(self):
        """Budget is consumed on successful terminal substitution."""
        from rcx_pi.selfhost.kernel import get_step_budget

        budget = get_step_budget()
        budget.start()
        try:
            before = budget.get_remaining()
            subst_mu({"var": "x"}, {"x": 42})
            after = budget.get_remaining()
            # At least 1 step consumed (simple var lookup takes >0 VM steps)
            assert after < before, f"Budget not consumed: before={before}, after={after}"
        finally:
            budget.stop()

    def test_bounded_stall_budget_plus_one(self):
        """Stall path consumes steps+1 (the +1 accounts for stall-detection probe).

        Wave 3E: locks the stall-budget contract that was previously only
        indirectly covered by existing parity tests.
        """
        from rcx_pi.selfhost.stage0_vm import stage0_vm_run_bounded
        from rcx_pi.selfhost.kernel import get_step_budget
        import unittest.mock

        # Mock bounded helper to return a stall with known step count
        stall_outcome = {"status": "stall", "root": {"_mode": "subst", "phase": "unknown"}, "steps": 5}
        with unittest.mock.patch(
            "rcx_pi.selfhost.stage0_vm.stage0_vm_run_bounded",
            return_value=stall_outcome,
        ):
            budget = get_step_budget()
            budget.start()
            try:
                before = budget.get_remaining()
                with pytest.raises(RuntimeError, match="Substitute stalled unexpectedly"):
                    subst_mu({"var": "x"}, {"x": 42})
                after = budget.get_remaining()
                consumed = before - after
                assert consumed == 6, f"Expected steps+1=6, got {consumed}"
            finally:
                budget.stop()

    def test_bounded_exhaustion_raises_runtime_error(self):
        """Exhaustion raises RuntimeError (not KeyError), even if last state is in lookup phase.

        Wave 3E: explicit exhaustion branch prevents false KeyError for bound
        variables that ran out of steps before completing lookup traversal.
        Also verifies budget consumption is exactly 1000 on exhaustion.
        """
        from rcx_pi.selfhost.kernel import get_step_budget
        import unittest.mock

        # Simulate exhaustion where last state happens to be in lookup phase
        # (the adversary-found edge case: variable IS bound, just ran out of steps)
        exhaustion_outcome = {
            "status": "exhaustion",
            "root": {"_mode": "subst", "phase": "lookup", "lookup_name": "x"},
            "steps": 1000,
        }
        with unittest.mock.patch(
            "rcx_pi.selfhost.stage0_vm.stage0_vm_run_bounded",
            return_value=exhaustion_outcome,
        ):
            budget = get_step_budget()
            budget.start()
            try:
                before = budget.get_remaining()
                with pytest.raises(RuntimeError, match="Substitute exhausted budget"):
                    subst_mu({"var": "x"}, {"x": 42})
                after = budget.get_remaining()
                consumed = before - after
                assert consumed == 1000, f"Expected 1000, got {consumed}"
            finally:
                budget.stop()

    def test_bounded_stall_lookup_raises_keyerror(self):
        """Stall in lookup phase raises KeyError for unbound variable.

        Wave 3E: defensive path — v2 seed routes unbound vars via error-as-value
        terminal, so this path only activates with incomplete bundles.

        Note: in-progress v2 states use "mode" (not "_mode"). "_mode" is only
        for terminal states. The mock shape must match real VM stall output.
        """
        import unittest.mock

        # Real stalled v2 state uses "mode": "subst" (not "_mode")
        stall_outcome = {
            "status": "stall",
            "root": {"mode": "subst", "phase": "lookup", "lookup_name": "z"},
            "steps": 3,
        }
        with unittest.mock.patch(
            "rcx_pi.selfhost.stage0_vm.stage0_vm_run_bounded",
            return_value=stall_outcome,
        ):
            with pytest.raises(KeyError, match="Unbound variable: z"):
                subst_mu({"var": "z"}, {"x": 42})

    def test_bounded_stall_lookup_sabotaged_bundle(self):
        """Negative control: sabotaged bundle (missing lookup.exhausted) stalls
        in lookup phase and raises KeyError, not RuntimeError.

        Bridge-required test: proves the stall handler works with real VM output,
        not just mocked shapes. Removes subst.lookup.exhausted from the compiled
        bundle so the VM cannot route unbound variables to the error-as-value
        terminal path — forcing a genuine stall in lookup phase.
        """
        from copy import deepcopy
        import unittest.mock
        import rcx_pi.selfhost.subst_mu as subst_mod

        bundle = deepcopy(_load_compiled_subst_v2_bundle())
        # Sabotage: remove the lookup.exhausted program
        bundle["program_order"] = [
            pid for pid in bundle["program_order"]
            if pid != "subst.lookup.exhausted"
        ]
        bundle["programs"] = [
            p for p in bundle["programs"]
            if p["id"] != "subst.lookup.exhausted"
        ]

        with unittest.mock.patch.object(
            subst_mod, "_load_compiled_subst_v2_bundle",
            return_value=bundle,
        ):
            with pytest.raises(KeyError, match="Unbound variable: z"):
                subst_mu({"var": "z"}, {})
