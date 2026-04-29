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

for _mod_name in list(_sys.modules):
    if _mod_name != "tools" and not _mod_name.startswith("tools."):
        continue
    _mod = _sys.modules[_mod_name]
    _mod_path = str(next(iter(getattr(_mod, "__path__", [])), ""))
    _mod_file = str(getattr(_mod, "__file__", "") or "")
    if "mu/tests/tools" in _mod_path or "mu/tests/tools" in _mod_file:
        del _sys.modules[_mod_name]

import re
import subprocess
from pathlib import Path

import pytest

from tools.docs.shared_doc_config import REPO_ROOT, classify_md_path


TRACKER_SECTION_PATTERN = re.compile(r"^##\s*(NOW|NEXT|VECTOR|SINK)\b", re.MULTILINE)


def _gitignore_pattern_for(rel_path: str) -> str:
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", "--", rel_path],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 1:
        return ""
    assert result.returncode == 0, result.stderr
    line = result.stdout.strip().splitlines()[-1]
    return line.split(":", 2)[2].split("\t", 1)[0]


class TestDocPlacementRules:
    def test_canonical_archive_lane_is_not_gitignored_for_new_snapshots(self):
        archive_pattern = _gitignore_pattern_for(
            "reports/archive/deferred/example_closed-by-example-wave.md"
        )
        assert archive_pattern == "" or archive_pattern.startswith("!")

        historical_archive_pattern = _gitignore_pattern_for(
            "reports/archive/deferred/probe_new_file.md"
        )
        assert historical_archive_pattern and not historical_archive_pattern.startswith("!")

        random_report_pattern = _gitignore_pattern_for("reports/random/probe_new_file.md")
        assert random_report_pattern and not random_report_pattern.startswith("!")

    def test_tracker_sections_only_in_root_canonical_docs(self):
        violations: list[tuple[str, str]] = []

        for doc_path in sorted(REPO_ROOT.rglob("*.md")):
            rel = str(doc_path.relative_to(REPO_ROOT))
            classification = classify_md_path(doc_path)
            if classification == "exempt":
                continue
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
