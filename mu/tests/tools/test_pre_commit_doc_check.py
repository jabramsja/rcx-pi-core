"""Regression tests for tools/pre-commit-doc-check docs-change detection.

DOCS_CHANGED must recognize governed docs across:
- mu/docs/
- root roadmap folder (roadmap/)
- root canonical tracker files
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "tools" / "hooks" / "pre-commit-doc-check"


def _extract_docs_pattern() -> str:
    """Extract the grep -E pattern from the DOCS_CHANGED line."""
    text = HOOK_PATH.read_text()
    for line in text.splitlines():
        if "DOCS_CHANGED=" in line and "grep -E" in line:
            match = re.search(r"grep -E '([^']+)'", line)
            assert match, f"Could not parse DOCS_CHANGED pattern from: {line}"
            return match.group(1)
    raise AssertionError("DOCS_CHANGED= line not found in pre-commit-doc-check")


class TestPreCommitDocDetection:
    """Ensure the DOCS_CHANGED pattern covers all doc paths."""

    def test_mu_docs_core_detected(self):
        """mu/docs/core/ changes must trigger doc tests."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "mu/docs/core/SelfHosting.v0.md"), (
            f"Pattern {pattern!r} does not match mu/docs/core/ paths"
        )

    def test_root_roadmap_folder_detected(self):
        """roadmap/ changes must trigger doc tests."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "roadmap/MANIFEST.md"), (
            f"Pattern {pattern!r} does not match roadmap/ paths"
        )

    def test_root_roadmap_file_detected(self):
        """ROADMAP.md at repo root must trigger doc tests."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "ROADMAP.md"), (
            f"Pattern {pattern!r} does not match ROADMAP.md"
        )

    def test_mu_docs_agents_detected(self):
        """mu/docs/agents/ changes must trigger doc tests."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "mu/docs/agents/AgentRig.v0.md"), (
            f"Pattern {pattern!r} does not match mu/docs/agents/ paths"
        )

    def test_status_md_detected(self):
        """STATUS.md must still trigger doc tests."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "STATUS.md"), (
            f"Pattern {pattern!r} does not match STATUS.md"
        )

    def test_tasks_md_detected(self):
        """TASKS.md must still trigger doc tests."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "TASKS.md"), (
            f"Pattern {pattern!r} does not match TASKS.md"
        )

    def test_tools_agents_detected(self):
        """mu/tools/agents/ must trigger doc tests (git paths use mu/ prefix)."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "mu/tools/agents/verifier_prompt.md"), (
            f"Pattern {pattern!r} does not match mu/tools/agents/ paths"
        )

    def test_old_docs_path_not_detected(self):
        """Legacy docs/ (now moved) should NOT trigger — only mu/docs/ should."""
        pattern = _extract_docs_pattern()
        # docs/foo.md should NOT match (only mu/docs/ should)
        assert not re.search(pattern, "docs/core/SelfHosting.v0.md"), (
            f"Pattern {pattern!r} still matches bare docs/ — should only match mu/docs/"
        )

    def test_old_mu_docs_roadmap_path_not_detected(self):
        """Pattern should not carry a special-case mu/docs/roadmap entry."""
        pattern = _extract_docs_pattern()
        assert "mu/docs/roadmap/" not in pattern, (
            f"Pattern {pattern!r} still includes legacy mu/docs/roadmap/ special-case"
        )

    def test_debt_threshold_parser_takes_first_status_number(self):
        """THRESHOLD parsing must ignore explanatory numbers on the same line."""
        text = HOOK_PATH.read_text()
        threshold_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith("THRESHOLD=")
        ]
        assert threshold_lines, "pre-commit-doc-check missing THRESHOLD assignment"
        threshold_line = threshold_lines[0]
        assert "grep -E '^THRESHOLD:' STATUS.md" in threshold_line
        assert "grep -oE '[0-9]+'" in threshold_line
        assert "head -1" in threshold_line
