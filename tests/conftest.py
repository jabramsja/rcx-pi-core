"""
Pytest configuration for RCX tests.

Provides:
- Projection coverage tracking (enable with RCX_PROJECTION_COVERAGE=1)
- Skips tests that require optional modules (rcx_omega, scripts)
"""

import os
import pytest

# Skip tests that require optional modules not present in this repo
collect_ignore = [
    "test_semantic_goldens.py",     # requires rcx_omega
    "test_semantic_invariants.py",  # requires rcx_omega
    "test_normalize_graphviz_svg.py",  # requires scripts module
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
