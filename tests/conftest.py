"""
Pytest configuration for RCX tests.

Provides:
- Projection coverage tracking (enable with RCX_PROJECTION_COVERAGE=1)
- Skips tests that require optional modules (rcx_omega, scripts)
- Shared test utilities (apply_mu for Phase 4d integration)
- Hypothesis configuration for deterministic fuzzing
"""

import os
import pytest

from rcx_pi.eval_seed import NO_MATCH
from rcx_pi.match_mu import match_mu
from rcx_pi.subst_mu import subst_mu

# =============================================================================
# Hypothesis Configuration (lossless optimization)
# =============================================================================
# - Database caches found examples for faster reruns (uses .hypothesis/ by default)
# - print_blob=True makes failures easy to reproduce
# - derandomize=False keeps search random but seeded for CI reproducibility
# NOTE: Do NOT set database=None - that DISABLES the database. Omit to use default.

try:
    from hypothesis import settings, Verbosity, Phase

    # Default profile: production settings with database caching
    # Omitting database= uses the default .hypothesis/ directory
    settings.register_profile(
        "default",
        print_blob=True,  # Print reproduction blob on failure
        derandomize=False,  # Keep randomized search
    )

    # CI profile: same as default but explicit for documentation
    settings.register_profile(
        "ci",
        print_blob=True,
        derandomize=False,
    )

    # Load profile from HYPOTHESIS_PROFILE env var, default to "default"
    profile = os.environ.get("HYPOTHESIS_PROFILE", "default")
    settings.load_profile(profile)

except ImportError:
    pass  # hypothesis not installed, skip configuration


# =============================================================================
# Shared Test Utilities
# =============================================================================

def apply_mu(projection: dict, value):
    """
    Apply a projection to a value using Mu-based match and substitute.

    This is the integration of match_mu + subst_mu (Phase 4d).
    Shared utility to avoid duplication across test files.

    Args:
        projection: Dict with "pattern" and "body" keys
        value: The value to match against the pattern

    Returns:
        The substituted body if pattern matches, NO_MATCH otherwise

    Raises:
        TypeError: If projection is not a dict
        KeyError: If projection missing pattern/body, or unbound variable in body
    """
    if not isinstance(projection, dict):
        raise TypeError(f"Projection must be dict, got {type(projection).__name__}")
    if "pattern" not in projection or "body" not in projection:
        raise KeyError("Projection must have 'pattern' and 'body' keys")

    pattern = projection["pattern"]
    body = projection["body"]

    bindings = match_mu(pattern, value)

    if bindings is NO_MATCH:
        return NO_MATCH

    return subst_mu(body, bindings)

# Skip tests that require optional modules not present in this repo
collect_ignore = [
    "test_semantic_goldens.py",     # requires rcx_omega
    "test_semantic_invariants.py",  # requires rcx_omega
    "test_normalize_graphviz_svg.py",  # requires scripts module
    "archive",  # archived tests (e.g., bytecode VM - superseded by kernel approach)
]


def pytest_configure(config):
    """Enable projection coverage if RCX_PROJECTION_COVERAGE is set."""
    if os.environ.get("RCX_PROJECTION_COVERAGE") == "1":
        from rcx_pi.projection_coverage import coverage
        coverage.enable()
        coverage.reset()


def pytest_unconfigure(config):
    """Print projection coverage report at end of test run."""
    if os.environ.get("RCX_PROJECTION_COVERAGE") == "1":
        from rcx_pi.projection_coverage import coverage
        print("\n")
        print(coverage.report())
