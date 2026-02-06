#!/usr/bin/env python3
"""
Shared documentation configuration - single source of truth.

This module centralizes GOVERNED_FOLDERS so there's one place to update
when adding new governed doc folders.

Used by:
- tools/add_doc_headers.py
- tests/docs/test_doc_freshness.py
- tests/docs/test_doc_governance.py
"""

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# Canonical list of governed folders (strings for portability)
# Per DocGovernance.v0.md: "Every .md file outside the root must declare its status"
GOVERNED_FOLDER_NAMES = [
    "docs/core",
    "docs/agents",
    "docs/audit",
    "docs/execution",
    "docs/cli",
    "docs/schemas",
    "docs/reviews",
    ".claude/agents",
]


def get_governed_folders_as_paths() -> list[Path]:
    """Get governed folders as Path objects (for tools that need Path operations)."""
    return [REPO_ROOT / folder for folder in GOVERNED_FOLDER_NAMES]


def get_governed_folders_as_strings() -> list[str]:
    """Get governed folders as strings (for tests with string comparison)."""
    return GOVERNED_FOLDER_NAMES.copy()
