"""
L4 gate test: F-39 cache alias containment.

Proves that public projection loader APIs do not expose the live shared
projection cache. Mutation of a public return value must not corrupt the
internal cache or subsequent callers.

Gate: G5 (meta-circular parity — projection integrity).
"""

import pytest

from rcx_pi.selfhost.step_mu import (
    clear_combined_kernel_cache,
    load_combined_kernel_projections,
    load_combined_kernel_with_bridge_projections,
)


@pytest.fixture(autouse=True)
def reset_cache():
    clear_combined_kernel_cache()
    yield
    clear_combined_kernel_cache()


class TestF39PublicCacheIsolation:
    """Public loader returns must be independent of the internal cache."""

    def test_core_loader_mutation_does_not_corrupt_cache(self):
        """Mutating core loader result does not affect next call."""
        a = load_combined_kernel_projections()
        n = len(a)
        a.append({"id": "INJECTED"})
        a[0]["POISONED"] = True

        b = load_combined_kernel_projections()
        assert len(b) == n
        assert all(p.get("id") != "INJECTED" for p in b)
        assert all("POISONED" not in p for p in b)

    def test_bridge_loader_mutation_does_not_corrupt_cache(self):
        """Mutating bridge loader result does not affect next call."""
        a = load_combined_kernel_with_bridge_projections()
        n = len(a)
        a.append({"id": "INJECTED"})
        a[0]["POISONED"] = True

        b = load_combined_kernel_with_bridge_projections()
        assert len(b) == n
        assert all(p.get("id") != "INJECTED" for p in b)
        assert all("POISONED" not in p for p in b)

    def test_no_copy_parameter_on_public_api(self):
        """Public loaders must not accept _copy parameter (F-39: removed)."""
        import inspect
        core_sig = inspect.signature(load_combined_kernel_projections)
        bridge_sig = inspect.signature(load_combined_kernel_with_bridge_projections)

        assert "_copy" not in core_sig.parameters, \
            "load_combined_kernel_projections must not have _copy parameter"
        assert "_copy" not in bridge_sig.parameters, \
            "load_combined_kernel_with_bridge_projections must not have _copy parameter"
