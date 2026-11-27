#!/usr/bin/env python3
"""
Shared documentation configuration and registry access.

This module is the single source of truth for markdown governance classification.

Used by:
- tools/add_doc_headers.py
- tests/docs/test_doc_freshness.py
- tests/docs/test_doc_governance.py
- tests/docs/test_docs_registry_coverage.py
- tools/docs_sync_report.py
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
REGISTRY_PATH = REPO_ROOT / "tools" / "docs" / "docs_registry.json"

# Finite bound for the git listing; it normally completes in well under a second.
GIT_LIST_TIMEOUT_SECONDS = 60


def _load_registry() -> dict:
    """Load docs registry from JSON."""
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing docs registry: {REGISTRY_PATH}")

    with REGISTRY_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    required_keys = {
        "version",
        "root_canonical_files",
        "special_folders",
        "governed_folders",
        "docs_registered_subfolders",
        "exempt_patterns",
    }
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"docs_registry.json missing keys: {sorted(missing)}")

    return data


DOCS_REGISTRY = _load_registry()

# Backward-compatible exports
GOVERNED_FOLDER_NAMES = DOCS_REGISTRY["governed_folders"]
ROOT_CANONICAL_FILES = set(DOCS_REGISTRY["root_canonical_files"])
SPECIAL_FOLDERS = set(DOCS_REGISTRY["special_folders"])
DOCS_REGISTERED_SUBFOLDERS = set(DOCS_REGISTRY["docs_registered_subfolders"])
EXEMPT_PATTERNS = tuple(DOCS_REGISTRY["exempt_patterns"])


def get_governed_folders_as_paths() -> list[Path]:
    """Get governed folders as Path objects (for tools that need Path operations)."""
    return [REPO_ROOT / folder for folder in GOVERNED_FOLDER_NAMES]


def get_governed_folders_as_strings() -> list[str]:
    """Get governed folders as strings (for tests with string comparison)."""
    return GOVERNED_FOLDER_NAMES.copy()


def get_registered_docs_subfolders() -> set[str]:
    """Get registered first-level docs/ subfolders."""
    return set(DOCS_REGISTERED_SUBFOLDERS)


def get_exempt_patterns() -> tuple[str, ...]:
    """Get exemption regex patterns."""
    return EXEMPT_PATTERNS


def list_git_visible_markdown(root: Path = REPO_ROOT) -> list[Path]:
    """Return the markdown files under ``root`` that git tracks or could add.

    Docs governance covers only markdown that can be committed: tracked files,
    plus untracked files that no ignore rule matches (``.gitignore``,
    ``$GIT_DIR/info/exclude`` or ``core.excludesFile``). This is
    ``git ls-files --cached --others --exclude-standard`` run in ``root``.
    Git-ignored files cannot be committed, so they are out of scope.

    A tracked path that is missing from the working tree is skipped, as the
    on-disk walk this replaces never saw it. The ``*.md`` match is applied
    here, case-sensitively, rather than through a git pathspec.

    Returns absolute ``root / <path>`` entries, de-duplicated and sorted.
    Fails closed: raises ``RuntimeError`` when git cannot produce the listing
    (no git, not a work tree, timeout), instead of falling back to a walk that
    would include ignored files.
    """
    command = [
        "git",
        "-C",
        str(root),
        "ls-files",
        "-z",
        "--cached",
        "--others",
        "--exclude-standard",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=GIT_LIST_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"cannot list git-visible markdown under {root}: {exc}") from exc
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"cannot list git-visible markdown under {root}: git ls-files "
            f"exited {result.returncode}: {stderr}"
        )

    found: set[Path] = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = os.fsdecode(raw)
        if not rel.endswith(".md"):
            continue
        path = root / rel
        if os.path.lexists(path):
            found.add(path)
    return sorted(found)


def classify_md_path(doc_path: Path) -> str:
    """
    Classify a markdown path into governance buckets.

    Returns one of:
    - root_canonical
    - roadmap
    - governed
    - exempt
    - unknown
    """
    rel_path = str(doc_path.relative_to(REPO_ROOT))

    if doc_path.parent == REPO_ROOT and doc_path.name in ROOT_CANONICAL_FILES:
        return "root_canonical"

    if rel_path.startswith("roadmap/"):
        return "roadmap"

    for folder in GOVERNED_FOLDER_NAMES:
        if rel_path.startswith(folder + "/"):
            return "governed"

    # Keep existing behavior from test_doc_governance:
    # subproject README files are governed
    if re.match(r"^[^/]+/README\.md$", rel_path):
        return "governed"
    if rel_path == "mu/docs/README.md":
        return "governed"

    for pattern in EXEMPT_PATTERNS:
        if re.search(pattern, rel_path):
            return "exempt"

    return "unknown"
