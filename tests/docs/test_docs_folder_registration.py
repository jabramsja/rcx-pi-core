"""
Docs folder registration tests.

Goal: if a new docs/<subfolder>/ appears with markdown files, it must be
explicitly registered in tools/docs_registry.json.
"""

from __future__ import annotations

# PATH SETUP - Ensure repo root is at position 0 for 'tools' imports
# pytest adds tests/ to sys.path which can shadow repo root's tools package
import sys as _sys
from pathlib import Path as _Path
_repo_root = str(_Path(__file__).parent.parent.parent)
if _sys.path[0] != _repo_root:
    if _repo_root in _sys.path:
        _sys.path.remove(_repo_root)
    _sys.path.insert(0, _repo_root)

from pathlib import Path

import pytest

from tools.shared_doc_config import REPO_ROOT, get_registered_docs_subfolders


DOCS_ROOT = REPO_ROOT / "mu" / "docs"


class TestDocsFolderRegistration:
    def test_docs_subfolders_with_markdown_are_registered(self):
        discovered: set[str] = set()
        for md_file in DOCS_ROOT.rglob("*.md"):
            rel = md_file.relative_to(DOCS_ROOT)
            if len(rel.parts) >= 2:
                discovered.add(rel.parts[0])

        registered = get_registered_docs_subfolders()
        unregistered = sorted(discovered - registered)
        if unregistered:
            msg = "\nUnregistered docs/ subfolders containing markdown:\n"
            for folder in unregistered:
                msg += f"  - docs/{folder}/\n"
            msg += "\nUpdate tools/docs_registry.json -> docs_registered_subfolders.\n"
            pytest.fail(msg)

    def test_registry_subfolders_are_nonempty_or_removed(self):
        registered = get_registered_docs_subfolders()
        stale: list[str] = []
        for folder in sorted(registered):
            folder_path = DOCS_ROOT / folder
            has_markdown = folder_path.exists() and any(folder_path.rglob("*.md"))
            if not has_markdown:
                stale.append(folder)

        if stale:
            msg = "\nRegistered docs/ subfolders with no markdown files:\n"
            for folder in stale:
                msg += f"  - docs/{folder}/\n"
            msg += "\nRemove stale entries from tools/docs_registry.json if intentional.\n"
            pytest.fail(msg)
