"""
Docs registry coverage tests.

Goal: every markdown file must be classified by the central docs registry.
This prevents silent drift when new docs or folders are added.
"""

from __future__ import annotations

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
        expected = {"STATUS.md", "TASKS.md", "README.md", "CLAUDE.md", "CHANGELOG.md"}
        missing = [name for name in expected if not (REPO_ROOT / name).exists()]
        assert not missing, f"Missing root canonical files: {missing}"
