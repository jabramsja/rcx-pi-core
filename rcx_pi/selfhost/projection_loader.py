"""
Projection Loader Factory - Phase 6d Consolidation

This module provides a factory for creating projection loaders with caching.
It consolidates the duplicated loader pattern from match_mu.py, subst_mu.py,
and classify_mu.py.

See docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

from typing import Callable

from .mu_type import Mu
from .seed_integrity import load_verified_seed, get_seeds_dir


def make_projection_loader(seed_filename: str) -> tuple[
    Callable[[], list[Mu]],
    Callable[[], None]
]:
    """
    Create a projection loader for a specific seed file.

    Returns a (load_fn, clear_fn) tuple:
    - load_fn: Returns cached projections, loading from disk on first call
    - clear_fn: Clears the cache (for testing)

    This consolidates the loader pattern used by match/subst/classify.

    Args:
        seed_filename: The seed file name (e.g., "match.v1.json")

    Returns:
        Tuple of (load_projections, clear_projection_cache) functions

    Example:
        load_match_projections, clear_projection_cache = make_projection_loader("match.v1.json")
        projections = load_match_projections()  # Loads and caches
        projections = load_match_projections()  # Returns cached
        clear_projection_cache()                 # Clears cache
    """
    # Cache stored in closure (avoids global state)
    cache: list[list[Mu] | None] = [None]  # Use list to allow mutation in closure

    def load() -> list[Mu]:
        """Load projections from seed file with integrity verification."""
        if cache[0] is not None:
            return cache[0]

        seed_path = get_seeds_dir() / seed_filename
        seed = load_verified_seed(seed_path)

        cache[0] = seed["projections"]
        return cache[0]

    def clear() -> None:
        """Clear cached projections (for testing)."""
        cache[0] = None

    return load, clear
