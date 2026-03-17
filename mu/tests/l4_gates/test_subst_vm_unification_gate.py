"""
Wave 3B gate test: subst_mu semantic unification to subst.v2 + VM runner.

Verifies that subst_mu() now executes via stage0_vm_run with the compiled
subst.v2 bundle, preserving public API behavior (including KeyError for
unbound variables).
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
        """Non-step-limit Stage0VMError must propagate, not be swallowed."""
        from rcx_pi.selfhost.stage0_vm import Stage0VMError
        import unittest.mock

        # Mock stage0_vm_run to raise a non-step-limit error
        fake_error = Stage0VMError("Op limit exceeded (test)")
        with unittest.mock.patch(
            "rcx_pi.selfhost.stage0_vm.stage0_vm_run",
            side_effect=fake_error,
        ):
            with pytest.raises(Stage0VMError, match="Op limit exceeded"):
                subst_mu({"var": "x"}, {"x": 42})
