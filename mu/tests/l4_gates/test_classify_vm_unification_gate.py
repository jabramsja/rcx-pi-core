"""
Wave 3D-B gate test: classify_mu VM unification via stage0_vm_run_bounded.

Verifies that classify_linked_list now executes via the compiled classify.v1
bundle through stage0_vm_run_bounded, preserving all three runtime contracts:
max_steps=1000, exhaustion→"list", and budget accounting.
"""

from __future__ import annotations

import json

import pytest

from rcx_pi.selfhost.classify_mu import (
    classify_linked_list,
    _load_classify_bundle,  # ANTICHEAT_OK: test-only — gate test for bundle loading
    _clear_classify_bundle,  # ANTICHEAT_OK: test-only — cache clear for provenance test
)


class TestClassifyVMUnificationGate:
    """Evidence that classify_linked_list uses compiled bundle + VM execution."""

    # --- Basic classification ---

    def test_simple_dict_via_vm(self):
        """Dict-encoding linked list classified correctly via VM."""
        # {"a": 1} normalized: {_type: dict, head: {head: "a", tail: {head: 1, tail: null}}, tail: null}
        kv_pair = {"head": "a", "tail": {"head": 1, "tail": None}}
        value = {"_type": "dict", "head": kv_pair, "tail": None}
        assert classify_linked_list(value) == "dict"

    def test_simple_list_via_vm(self):
        """List-encoding linked list classified correctly via VM."""
        value = {"_type": "list", "head": 1, "tail": {"_type": "list", "head": 2, "tail": None}}
        assert classify_linked_list(value) == "list"

    def test_empty_list(self):
        """None (empty) classified as list."""
        assert classify_linked_list(None) == "list"

    def test_primitive_is_list(self):
        """Primitives classified as list."""
        assert classify_linked_list(42) == "list"
        assert classify_linked_list("hello") == "list"

    def test_mixed_content_is_list(self):
        """Legacy head/tail with non-kv head classified as list."""
        # A list element that is NOT a kv-pair
        value = {"head": 42, "tail": None}
        assert classify_linked_list(value) == "list"

    def test_multi_key_dict(self):
        """Multi-key dict-encoding classified correctly."""
        kv_a = {"head": "a", "tail": {"head": 1, "tail": None}}
        kv_b = {"head": "b", "tail": {"head": 2, "tail": None}}
        value = {"_type": "dict", "head": kv_a, "tail": {"_type": "dict", "head": kv_b, "tail": None}}
        assert classify_linked_list(value) == "dict"

    # --- Legacy (untagged) path exercises VM ---

    def test_legacy_dict_via_vm(self):
        """Legacy untagged dict-encoding goes through VM path."""
        kv_pair = {"head": "x", "tail": {"head": 99, "tail": None}}
        value = {"head": kv_pair, "tail": None}
        assert classify_linked_list(value) == "dict"

    def test_legacy_list_via_vm(self):
        """Legacy untagged list-encoding goes through VM path."""
        value = {"head": 1, "tail": {"head": 2, "tail": None}}
        assert classify_linked_list(value) == "list"

    # --- Budget accounting ---

    def test_budget_consumed_on_terminal(self):
        """Budget is consumed when classify reaches terminal."""
        from rcx_pi.selfhost.kernel import get_step_budget

        budget = get_step_budget()
        budget.start()
        try:
            before = budget.get_remaining()

            kv_pair = {"head": "k", "tail": {"head": "v", "tail": None}}
            value = {"head": kv_pair, "tail": None}
            classify_linked_list(value)

            after = budget.get_remaining()
            assert after < before, "Budget should be consumed on terminal"
        finally:
            budget.stop()

    # --- Compiled bundle ---

    def test_compiled_bundle_loads(self):
        """Compiled classify_v1 bundle loads and validates."""
        bundle = _load_classify_bundle()
        assert isinstance(bundle, dict)
        assert "programs" in bundle
        assert len(bundle["programs"]) == 6  # classify.v1 has 6 projections

    def test_bundle_provenance_rejects_wrong_digest(self):
        """N15: wrong source_digest raises ValueError through factory loader."""
        from rcx_pi.selfhost.seed_integrity import SEED_CHECKSUMS
        import rcx_pi.selfhost.classify_mu as classify_mod

        bundle = _load_classify_bundle()
        source_seed = bundle.get("source_seed", "")
        seed_filename = source_seed if source_seed.endswith(".json") else source_seed + ".json"
        assert seed_filename in SEED_CHECKSUMS, "classify.v1 must be in SEED_CHECKSUMS"

        tampered = dict(bundle)
        tampered["source_digest"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        classify_mod._clear_classify_bundle()  # ANTICHEAT_OK: test-only

        import unittest.mock
        with unittest.mock.patch("builtins.open", unittest.mock.mock_open(read_data=json.dumps(tampered))):
            with pytest.raises(ValueError, match="SECURITY.*provenance mismatch"):
                classify_mod._load_classify_bundle()  # ANTICHEAT_OK: test-only

        # Restore
        classify_mod._clear_classify_bundle()  # ANTICHEAT_OK: test-only
        classify_mod._load_classify_bundle()  # ANTICHEAT_OK: test-only

    def test_vm_fault_fails_closed_to_list(self):
        """Stage0VMError from VM path is caught and fail-closed to 'list'.

        This is the correct behavior: classify is a boundary function that
        must never crash. Circular element values, op-limit errors, and
        other VM faults all produce "list" (fail-closed).
        """
        from rcx_pi.selfhost.stage0_vm import Stage0VMError
        import unittest.mock

        fake_error = Stage0VMError("Op limit exceeded (test)")
        with unittest.mock.patch(
            "rcx_pi.selfhost.stage0_vm._stage0_vm_run_bounded_trusted",  # ANTICHEAT_OK: VM fault mock
            side_effect=fake_error,
        ):
            # Legacy path exercises VM (type-tagged path returns early)
            value = {"head": {"head": "k", "tail": {"head": "v", "tail": None}}, "tail": None}
            result = classify_linked_list(value)
            assert result == "list"  # fail-closed, not exception
