"""
Root File Governance Tests - The sources of truth must be trustworthy.

The root files (STATUS.md, TASKS.md, README.md, CLAUDE.md, CHANGELOG.md) are
EXEMPT from standard doc governance because they ARE the sources of truth.
But they need their OWN governance to ensure they stay accurate.

This module verifies:
1. Root files exist and have required structure
2. Cross-references between root files are valid
3. Root files reference docs correctly
4. Claims in root files match reality
5. Root files don't contradict each other

Usage:
    PYTHONHASHSEED=0 pytest tests/docs/test_root_files.py -v
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

# Root files and their required characteristics
ROOT_FILES = {
    "STATUS.md": {
        "required": True,
        "must_contain": ["PHASE:", "CURRENT:", "L1", "L2", "L3"],
        "must_link_to": [],  # STATUS.md is the source, doesn't need to link
    },
    "TASKS.md": {
        "required": True,
        "must_contain": ["## North Star", "## Ra", "## NEXT", "## VECTOR"],
        "must_link_to": ["STATUS.md"],
    },
    "README.md": {
        "required": True,
        "must_contain": ["RCX", "STATUS.md"],
        "must_link_to": ["STATUS.md"],
    },
    "CLAUDE.md": {
        "required": True,
        "must_contain": ["STATUS.md", "TASKS.md"],
        "must_link_to": ["STATUS.md", "TASKS.md"],
    },
    "CHANGELOG.md": {
        "required": True,
        "must_contain": ["#"],  # Just needs to have some headers
        "must_link_to": [],
    },
}

# Paths that should exist if referenced in root files
CRITICAL_PATHS = [
    "docs/core/",
    "rcx_pi/selfhost/",
    "mu/substrate/",
    "mu/host/js/eval_step.js",
    "tools/audit_fast.sh",
]


# =============================================================================
# Existence and Structure Tests
# =============================================================================

class TestRootFilesExist:
    """Verify all root files exist."""

    @pytest.mark.parametrize("filename,config", ROOT_FILES.items())
    def test_root_file_exists(self, filename: str, config: dict):
        """Required root files must exist."""
        if config["required"]:
            path = REPO_ROOT / filename
            assert path.exists(), f"Required root file {filename} is missing"

    @pytest.mark.parametrize("filename,config", ROOT_FILES.items())
    def test_root_file_has_required_content(self, filename: str, config: dict):
        """Root files must contain required sections/keywords."""
        path = REPO_ROOT / filename
        if not path.exists():
            pytest.skip(f"{filename} doesn't exist")

        content = path.read_text()
        missing = []
        for required in config["must_contain"]:
            if required not in content:
                missing.append(required)

        if missing:
            pytest.fail(
                f"{filename} missing required content: {missing}\n"
                f"These are structural requirements for the file to function as a source of truth."
            )


# =============================================================================
# Cross-Reference Tests
# =============================================================================

class TestRootFileCrossReferences:
    """Verify root files reference each other correctly."""

    @pytest.mark.parametrize("filename,config", ROOT_FILES.items())
    def test_required_links(self, filename: str, config: dict):
        """Root files must link to their required dependencies."""
        path = REPO_ROOT / filename
        if not path.exists():
            pytest.skip(f"{filename} doesn't exist")

        content = path.read_text()
        missing = []
        for link in config["must_link_to"]:
            if link not in content:
                missing.append(link)

        if missing:
            pytest.fail(
                f"{filename} must reference: {missing}\n"
                f"Root files form a cohesive system - they must link to each other."
            )

    def test_status_md_links_work(self):
        """Links in STATUS.md should point to existing files."""
        status_path = REPO_ROOT / "STATUS.md"
        if not status_path.exists():
            pytest.skip("STATUS.md doesn't exist")

        content = status_path.read_text()
        broken = self._find_broken_doc_links(content)

        if broken:
            pytest.fail(f"STATUS.md has broken links: {broken}")

    def test_tasks_md_links_work(self):
        """Links in TASKS.md should point to existing files."""
        tasks_path = REPO_ROOT / "TASKS.md"
        if not tasks_path.exists():
            pytest.skip("TASKS.md doesn't exist")

        content = tasks_path.read_text()
        broken = self._find_broken_doc_links(content)

        if broken:
            pytest.fail(f"TASKS.md has broken links: {broken}")

    def test_readme_links_work(self):
        """Links in README.md should point to existing files."""
        readme_path = REPO_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md doesn't exist")

        content = readme_path.read_text()
        broken = self._find_broken_doc_links(content)

        if broken:
            pytest.fail(f"README.md has broken links: {broken}")

    def test_claude_md_links_work(self):
        """Links in CLAUDE.md should point to existing files."""
        claude_path = REPO_ROOT / "CLAUDE.md"
        if not claude_path.exists():
            pytest.skip("CLAUDE.md doesn't exist")

        content = claude_path.read_text()
        broken = self._find_broken_doc_links(content)

        if broken:
            pytest.fail(f"CLAUDE.md has broken links: {broken}")

    def _find_broken_doc_links(self, content: str) -> list[str]:
        """Find markdown links that point to non-existent files."""
        broken = []
        # Match markdown links: [text](path) - only check explicit markdown links
        link_patterns = [
            r'\[.*?\]\(([^)]+)\)',  # [text](link)
        ]

        for pattern in link_patterns:
            for match in re.finditer(pattern, content):
                path = match.group(1)
                # Skip URLs and anchors
                if path.startswith(('http', '#', 'mailto')):
                    continue
                # Skip patterns with variables
                if '{' in path or '*' in path:
                    continue
                # Skip pytest test paths (e.g., tests/foo.py::test_bar)
                if '::' in path:
                    continue
                # Skip code references with function names (e.g., file.py:func())
                if re.search(r':\w+\(\)$', path):
                    continue
                # Skip code references with line numbers (e.g., file.py:123)
                if re.search(r':\d+$', path):
                    continue
                # Skip code references with constant names (e.g., file.py:CONSTANT)
                if re.search(r':[A-Z_]+$', path):
                    continue

                full_path = REPO_ROOT / path
                if not full_path.exists():
                    broken.append(path)

        return broken[:10]  # Limit to first 10


# =============================================================================
# STATUS.md Specific Tests
# =============================================================================

class TestStatusMd:
    """STATUS.md is the primary source of truth - it needs special validation."""

    def test_has_phase_declaration(self):
        """STATUS.md must declare current phase."""
        status_path = REPO_ROOT / "STATUS.md"
        content = status_path.read_text()

        # Check for PHASE: N or PHASE: Na format
        match = re.search(r'PHASE:\s*\d+[a-z]?', content, re.IGNORECASE)
        assert match, "STATUS.md must declare 'PHASE: N' (e.g., 'PHASE: 8b')"

    def test_freshness_via_git(self):
        """STATUS.md should be updated recently (check via git)."""
        import subprocess
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%cd", "--date=short", "STATUS.md"],
                capture_output=True, text=True, cwd=REPO_ROOT
            )
            if result.returncode == 0 and result.stdout.strip():
                date_str = result.stdout.strip()
                last_updated = datetime.strptime(date_str, "%Y-%m-%d")
                days_old = (datetime.now() - last_updated).days

                if days_old > 14:
                    import warnings
                    warnings.warn(
                        f"STATUS.md last git commit was {days_old} days ago ({date_str}). "
                        f"Consider reviewing if it's still accurate."
                    )
        except Exception:
            pytest.skip("Could not check git history")

    def test_debt_count_format(self):
        """STATUS.md must have a parseable debt count."""
        status_path = REPO_ROOT / "STATUS.md"
        content = status_path.read_text()

        # Look for CURRENT: N pattern
        match = re.search(r'CURRENT[:\s]+(\d+)', content)
        assert match, "STATUS.md must have 'CURRENT: N' debt count"

    def test_l_levels_declared(self):
        """STATUS.md must declare L1/L2/L3 status."""
        status_path = REPO_ROOT / "STATUS.md"
        content = status_path.read_text()

        for level in ["L1", "L2", "L3"]:
            assert level in content, f"STATUS.md must declare {level} status"


# =============================================================================
# TASKS.md Specific Tests
# =============================================================================

class TestTasksMd:
    """TASKS.md tracks work items - verify its structure."""

    def test_has_north_star_invariants(self):
        """TASKS.md must have North Star invariants section."""
        tasks_path = REPO_ROOT / "TASKS.md"
        content = tasks_path.read_text()

        assert "North Star" in content, "TASKS.md must have North Star section"
        # Should have numbered invariants
        assert re.search(r'\d+\.\s+\*\*', content), "North Star should have numbered invariants"

    def test_has_work_sections(self):
        """TASKS.md must have Ra/NEXT/VECTOR/SINK sections."""
        tasks_path = REPO_ROOT / "TASKS.md"
        content = tasks_path.read_text()

        required_sections = ["## Ra", "## NEXT", "## VECTOR", "## SINK"]
        missing = [s for s in required_sections if s not in content]

        if missing:
            pytest.fail(f"TASKS.md missing sections: {missing}")

    def test_sink_items_have_rationale(self):
        """SINK items should explain why they're parked."""
        tasks_path = REPO_ROOT / "TASKS.md"
        content = tasks_path.read_text()

        # Find SINK section
        sink_match = re.search(r'## SINK\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if not sink_match:
            pytest.skip("No SINK section found")

        sink_content = sink_match.group(1)
        # SINK items should have some explanation (at least 50 chars of content)
        if len(sink_content.strip()) < 50 and "None" not in sink_content:
            import warnings
            warnings.warn("SINK section seems sparse - consider documenting why items are parked")


# =============================================================================
# CLAUDE.md Specific Tests
# =============================================================================

class TestClaudeMd:
    """CLAUDE.md instructs AI - it must be accurate."""

    def test_references_status_and_tasks(self):
        """CLAUDE.md must tell AI to read STATUS.md and TASKS.md."""
        claude_path = REPO_ROOT / "CLAUDE.md"
        content = claude_path.read_text()

        assert "STATUS.md" in content, "CLAUDE.md must reference STATUS.md"
        assert "TASKS.md" in content, "CLAUDE.md must reference TASKS.md"

    def test_critical_paths_exist(self):
        """Paths mentioned in CLAUDE.md should exist."""
        claude_path = REPO_ROOT / "CLAUDE.md"
        content = claude_path.read_text()

        for critical_path in CRITICAL_PATHS:
            full_path = REPO_ROOT / critical_path
            if critical_path in content and not full_path.exists():
                pytest.fail(f"CLAUDE.md references non-existent path: {critical_path}")

    def test_no_hardcoded_phase_numbers(self):
        """CLAUDE.md shouldn't hardcode phase numbers (use STATUS.md reference instead)."""
        claude_path = REPO_ROOT / "CLAUDE.md"
        content = claude_path.read_text()

        # Look for hardcoded "Phase N" or "Phase Na" claims
        phase_claims = re.findall(r'Phase \d+[a-z]?\s+(?:is\s+)?(?:complete|done|in progress)', content, re.I)

        if phase_claims:
            import warnings
            warnings.warn(
                f"CLAUDE.md has hardcoded phase claims: {phase_claims[:3]}\n"
                f"Consider using 'See STATUS.md' instead to prevent drift."
            )


# =============================================================================
# Consistency Tests
# =============================================================================

class TestRootFileConsistency:
    """Root files must not contradict each other."""

    def test_readme_test_count_reasonable(self):
        """README.md test count should be in the right ballpark."""
        readme_path = REPO_ROOT / "README.md"
        if not readme_path.exists():
            pytest.skip("README.md doesn't exist")

        content = readme_path.read_text()

        # Look for test count claims like "2,100+ tests" or "2100 tests"
        match = re.search(r'(\d[,\d]*)\+?\s*tests', content, re.I)
        if match:
            claimed = int(match.group(1).replace(',', ''))
            # Just verify it's a reasonable number (>100, <50000)
            assert 100 < claimed < 50000, f"README claims {claimed} tests - seems unreasonable"

    def test_status_and_readme_l_levels_match(self):
        """L-level claims in README should match STATUS.md."""
        status_path = REPO_ROOT / "STATUS.md"
        readme_path = REPO_ROOT / "README.md"

        if not (status_path.exists() and readme_path.exists()):
            pytest.skip("Missing files")

        status_content = status_path.read_text()
        readme_content = readme_path.read_text()

        # Check each L-level
        for level in ["L1", "L2", "L3"]:
            status_complete = f"{level}" in status_content and "COMPLETE" in status_content
            readme_complete = f"{level}" in readme_content and "COMPLETE" in readme_content

            # If STATUS says complete, README shouldn't say incomplete
            if status_complete and f"{level}" in readme_content:
                # Look for contradictions
                if re.search(rf'{level}.*(?:TODO|IN PROGRESS|PENDING)', readme_content, re.I):
                    pytest.fail(
                        f"README.md claims {level} is incomplete but STATUS.md says COMPLETE"
                    )


# =============================================================================
# Meta Test
# =============================================================================

class TestRootFileGovernanceMeta:
    """Verify the governance system covers all root files."""

    def test_all_root_files_covered(self):
        """All markdown files in repo root should be in ROOT_FILES config."""
        uncovered = []
        for path in REPO_ROOT.glob("*.md"):
            if path.name not in ROOT_FILES:
                uncovered.append(path.name)

        if uncovered:
            import warnings
            warnings.warn(
                f"Markdown files in repo root not covered by governance: {uncovered}\n"
                f"Consider adding them to ROOT_FILES in test_root_files.py"
            )
