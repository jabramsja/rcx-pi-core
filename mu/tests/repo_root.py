"""Symlink-safe repo root discovery (single source of truth for tests).

Works regardless of whether tests are accessed via:
  - tests/...          (symlink path, 3 levels to root)
  - mu/tests/...       (canonical path, 4 levels to root)

Uses upward search for pyproject.toml instead of fragile parent counting.
"""
import os
from pathlib import Path


def find_repo_root() -> Path:
    """Find repo root by searching upward for pyproject.toml."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        if os.path.isfile(os.path.join(d, "pyproject.toml")):
            return Path(d)
        d = os.path.dirname(d)
    raise RuntimeError("Cannot find repo root (no pyproject.toml)")


REPO_ROOT = find_repo_root()
