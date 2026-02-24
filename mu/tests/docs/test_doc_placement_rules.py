"""
Doc placement rules to reduce tracker drift.

These rules ensure task/state sections stay in canonical root trackers.
"""

from __future__ import annotations

# PATH SETUP - Ensure repo root is at position 0 for 'tools' imports
# pytest adds tests/ to sys.path which can shadow repo root's tools package
import sys as _sys
from pathlib import Path as _Path
from tests.repo_root import REPO_ROOT as _REPO_ROOT
_repo_root = str(_REPO_ROOT)
if _sys.path[0] != _repo_root:
    if _repo_root in _sys.path:
        _sys.path.remove(_repo_root)
    _sys.path.insert(0, _repo_root)

import re
from pathlib import Path

import pytest

from tools.docs.shared_doc_config import REPO_ROOT, classify_md_path


TRACKER_SECTION_PATTERN = re.compile(r"^##\s*(NOW|NEXT|VECTOR|SINK)\b", re.MULTILINE)


class TestDocPlacementRules:
    def test_tracker_sections_only_in_root_canonical_docs(self):
        violations: list[tuple[str, str]] = []

        for doc_path in sorted(REPO_ROOT.rglob("*.md")):
            rel = str(doc_path.relative_to(REPO_ROOT))
            classification = classify_md_path(doc_path)
            content = doc_path.read_text(encoding="utf-8")

            match = TRACKER_SECTION_PATTERN.search(content)
            if not match:
                continue

            # Root canonical files are the only allowed place for tracker sections.
            if classification != "root_canonical":
                violations.append((rel, match.group(1)))

        if violations:
            msg = "\nTracker section headers outside root canonical docs:\n"
            for rel, section in violations:
                msg += f"  - {rel}: ## {section}\n"
            msg += "\nMove task/state sections to TASKS.md or STATUS.md.\n"
            pytest.fail(msg)
