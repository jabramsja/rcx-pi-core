"""Regression tests for tools/pre-commit-doc-check docs-change detection.

After Round 24C moved docs/ and roadmap/ into mu/docs/, the DOCS_CHANGED
pattern must recognise mu/docs/ paths so that doc governance tests trigger
on staged doc changes.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
HOOK_PATH = REPO_ROOT / "tools" / "pre-commit-doc-check"


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

    def test_mu_docs_roadmap_detected(self):
        """mu/docs/roadmap/ changes must trigger doc tests."""
        pattern = _extract_docs_pattern()
        assert re.search(pattern, "mu/docs/roadmap/ROADMAP.md"), (
            f"Pattern {pattern!r} does not match mu/docs/roadmap/ paths"
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

    def test_old_roadmap_path_not_detected(self):
        """Legacy roadmap/ (now moved) should NOT trigger."""
        pattern = _extract_docs_pattern()
        assert not re.search(pattern, "roadmap/ROADMAP.md"), (
            f"Pattern {pattern!r} still matches bare roadmap/ — should only match mu/docs/roadmap/"
        )
