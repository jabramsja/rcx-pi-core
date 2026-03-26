"""Shared test helper for loading repo modules by file path."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_module(name: str, path: Path):
    """Load a module from *path* and register it in sys.modules."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
