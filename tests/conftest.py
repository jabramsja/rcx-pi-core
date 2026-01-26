"""
Pytest configuration for RCX tests.

Provides:
- Projection coverage tracking (enable with RCX_PROJECTION_COVERAGE=1)
"""

import os
import pytest


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
