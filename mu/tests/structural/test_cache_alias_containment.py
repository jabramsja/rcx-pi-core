"""
F-39: Cache alias containment tests.

Verify that public projection loader APIs do not expose live shared cache
references, while the internal trusted path (step_kernel_mu) uses the
private shared helpers for performance.

What we claim: public shared-cache aliasing is closed; shared cache is
restricted to private trusted internal use.

What we do NOT claim: cache immutability, projection dict immutability,
or elimination of all cache poisoning vectors.
"""

import time

import pytest

from rcx_pi.selfhost.step_mu import (
    clear_combined_kernel_cache,
    load_combined_kernel_projections,
    load_combined_kernel_with_bridge_projections,
    step_kernel_mu,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset caches before and after each test."""
    clear_combined_kernel_cache()
    yield
    clear_combined_kernel_cache()


# =========================================================================
# Test 1: Public core loader mutation does not persist
# =========================================================================


class TestPublicCoreLoaderIsolation:
    """Public load_combined_kernel_projections returns independent copies."""

    def test_mutation_does_not_persist(self):
        """Mutating the returned list does not affect subsequent calls."""
        first = load_combined_kernel_projections()
        original_len = len(first)
        assert original_len > 0

        # Mutate: append junk, pop items, modify a dict
        first.append({"id": "INJECTED", "pattern": {}, "body": {}})
        first.pop(0)
        if first:
            first[0]["POISONED"] = True

        # Second call must return pristine data
        second = load_combined_kernel_projections()
        assert len(second) == original_len
        assert all("POISONED" not in p for p in second)
        assert all(p.get("id") != "INJECTED" for p in second)


# =========================================================================
# Test 2: Public bridge loader mutation does not persist
# =========================================================================


class TestPublicBridgeLoaderIsolation:
    """Public load_combined_kernel_with_bridge_projections returns independent copies."""

    def test_mutation_does_not_persist(self):
        """Mutating the returned list does not affect subsequent calls."""
        first = load_combined_kernel_with_bridge_projections()
        original_len = len(first)
        assert original_len > 0

        # Mutate: append junk, modify a dict
        first.append({"id": "INJECTED", "pattern": {}, "body": {}})
        if first:
            first[0]["POISONED"] = True

        # Second call must return pristine data
        second = load_combined_kernel_with_bridge_projections()
        assert len(second) == original_len
        assert all("POISONED" not in p for p in second)
        assert all(p.get("id") != "INJECTED" for p in second)


# =========================================================================
# Test 3: step_kernel_mu core path still works
# =========================================================================


class TestStepKernelMuCorePath:
    """step_kernel_mu with kernel_mode='core' produces correct results."""

    def test_core_passthrough(self):
        """Non-matching input passes through unchanged."""
        result = step_kernel_mu([], {"ok": True}, kernel_mode="core")
        assert result == {"ok": True}


# =========================================================================
# Test 4: step_kernel_mu bridge path still works
# =========================================================================


class TestStepKernelMuBridgePath:
    """step_kernel_mu with kernel_mode='bridge' produces correct results."""

    def test_bridge_passthrough(self):
        """Non-matching input passes through unchanged."""
        result = step_kernel_mu([], {"ok": True}, kernel_mode="bridge")
        assert result == {"ok": True}


# =========================================================================
# Test 5: Monkeypatch proof — internal path uses private helper
# =========================================================================


class TestInternalPathUsesPrivateHelper:
    """step_kernel_mu must call the private _shared helpers, not the public copy path."""

    def test_core_uses_private_shared_helper(self, monkeypatch):
        """Monkeypatching private helper changes step_kernel_mu behavior."""
        sentinel = [{"id": "SENTINEL", "pattern": {"_no_match": True}, "body": {}}]
        called = {"count": 0}

        def fake_shared():
            called["count"] += 1
            return sentinel

        monkeypatch.setattr(
            "rcx_pi.selfhost.step_mu._load_combined_kernel_projections_shared",  # ANTICHEAT_OK: F-39 private helper proof
            fake_shared,
        )
        step_kernel_mu([], {"ok": True}, kernel_mode="core")
        assert called["count"] == 1, "step_kernel_mu must call private shared helper"

    def test_bridge_uses_private_shared_helper(self, monkeypatch):
        """Monkeypatching private bridge helper changes step_kernel_mu behavior."""
        sentinel = [{"id": "SENTINEL", "pattern": {"_no_match": True}, "body": {}}]
        called = {"count": 0}

        def fake_shared():
            called["count"] += 1
            return sentinel

        monkeypatch.setattr(
            "rcx_pi.selfhost.step_mu._load_combined_kernel_with_bridge_projections_shared",  # ANTICHEAT_OK: F-39 private helper proof
            fake_shared,
        )
        step_kernel_mu([], {"ok": True}, kernel_mode="bridge")
        assert called["count"] == 1, "step_kernel_mu must call private shared bridge helper"


# =========================================================================
# Test 6: Timing sanity — private path has no deep-copy overhead
# =========================================================================


class TestTimingSanity:
    """Verify the internal path does not pay deep-copy cost."""

    def test_private_path_faster_than_public_copy(self):
        """step_kernel_mu (private path) should not regress vs public copy cost."""
        # Warm caches
        load_combined_kernel_projections()
        step_kernel_mu([], {"ok": True}, kernel_mode="core")

        # Time public copy path
        n = 200
        t0 = time.perf_counter()
        for _ in range(n):
            load_combined_kernel_projections()
        copy_time = (time.perf_counter() - t0) / n

        # Time step_kernel_mu (which uses private shared path internally)
        t0 = time.perf_counter()
        for _ in range(n):
            step_kernel_mu([], {"ok": True}, kernel_mode="core")
        step_time = (time.perf_counter() - t0) / n

        # The step path includes eval_step overhead but should NOT include
        # deep copy overhead. The copy path should be >= the deep copy cost.
        # We just verify the step path isn't absurdly slower than the copy path
        # (which would indicate it's secretly doing a copy too).
        # Generous threshold: step_time < copy_time * 5
        # (step does eval work; copy only does JSON round-trip)
        assert step_time < copy_time * 5, (
            f"step_kernel_mu ({step_time*1e6:.0f}us) is suspiciously slow vs "
            f"public copy ({copy_time*1e6:.0f}us) — may be doing unwanted deep copy"
        )
