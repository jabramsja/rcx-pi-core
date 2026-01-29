"""
Archive conftest - blocks test collection even with explicit paths.

This prevents `pytest tests/archive/` from accidentally running archived tests.
The tests are preserved for reference but should not be part of any test run.
"""

import pytest


def pytest_ignore_collect(collection_path, config):
    """
    Ignore all test files in archive directory.

    This hook runs before collection and returns True to skip.
    Works even when archive/ is explicitly specified.
    """
    # Always skip collection for anything in this directory
    return True
