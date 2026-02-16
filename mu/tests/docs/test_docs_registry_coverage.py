"""
Docs registry coverage tests.

Goal: every markdown file must be classified by the central docs registry.
This prevents silent drift when new docs or folders are added.
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
# If tests/tools was imported first, it can shadow repo tools package.
if "tools" in _sys.modules:
    _tools_mod = _sys.modules["tools"]
    _mod_file = str(getattr(_tools_mod, "__file__", "") or "")
    _mod_path = str(next(iter(getattr(_tools_mod, "__path__", [])), ""))
    if "tests/tools" in _mod_file or "tests/tools" in _mod_path:
        del _sys.modules["tools"]

from pathlib import Path

import pytest

from tools.shared_doc_config import REPO_ROOT, classify_md_path


def iter_all_markdown_files() -> list[Path]:
    return sorted(REPO_ROOT.rglob("*.md"))


class TestDocsRegistryCoverage:
    def test_all_markdown_files_are_classified(self):
        unknown: list[str] = []

        for doc in iter_all_markdown_files():
            classification = classify_md_path(doc)
            if classification == "unknown":
                unknown.append(str(doc.relative_to(REPO_ROOT)))

        if unknown:
            msg = "\nUnclassified markdown files (update tools/docs_registry.json):\n"
            for path in unknown:
                msg += f"  - {path}\n"
            pytest.fail(msg)

    def test_no_registry_regression_for_root_canonical_files(self):
        expected = {"STATUS.md", "TASKS.md", "ROADMAP.md", "README.md", "CLAUDE.md", "CHANGELOG.md"}
        missing = [name for name in expected if not (REPO_ROOT / name).exists()]
        assert not missing, f"Missing root canonical files: {missing}"
