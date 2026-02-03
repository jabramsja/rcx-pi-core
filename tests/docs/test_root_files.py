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

        # Find SINK section (header may have parenthetical text like "## SINK (ideas parked; ...)")
        sink_match = re.search(r'## SINK[^\n]*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
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

    def test_critical_test_files_count_matches(self):
        """CRITICAL_TEST_FILES count must match between README and STATUS."""
        status_path = REPO_ROOT / "STATUS.md"
        readme_path = REPO_ROOT / "README.md"

        if not (status_path.exists() and readme_path.exists()):
            pytest.skip("Missing files")

        status_content = status_path.read_text()
        readme_content = readme_path.read_text()

        # Extract counts from both files
        # Pattern: "N CRITICAL_TEST_FILES" or "**N CRITICAL_TEST_FILES**"
        status_match = re.search(r'(\d+)\s*CRITICAL_TEST_FILES', status_content)
        readme_match = re.search(r'(\d+)\s*CRITICAL_TEST_FILES', readme_content)

        if status_match and readme_match:
            status_count = int(status_match.group(1))
            readme_count = int(readme_match.group(1))

            if status_count != readme_count:
                pytest.fail(
                    f"CRITICAL_TEST_FILES count mismatch:\n"
                    f"  STATUS.md: {status_count}\n"
                    f"  README.md: {readme_count}\n"
                    f"Update README.md to match STATUS.md (source of truth)"
                )

    def test_debt_count_matches(self):
        """Debt count in README should match STATUS.md."""
        status_path = REPO_ROOT / "STATUS.md"
        readme_path = REPO_ROOT / "README.md"

        if not (status_path.exists() and readme_path.exists()):
            pytest.skip("Missing files")

        status_content = status_path.read_text()
        readme_content = readme_path.read_text()

        # Extract debt counts
        # STATUS: "CURRENT: N" or similar
        status_match = re.search(r'CURRENT[:\s]+(\d+)', status_content)
        # README: "N semantic debt" or "**N semantic debt**"
        readme_match = re.search(r'(\d+)\s*semantic\s*debt', readme_content, re.I)

        if status_match and readme_match:
            status_count = int(status_match.group(1))
            readme_count = int(readme_match.group(1))

            if status_count != readme_count:
                pytest.fail(
                    f"Debt count mismatch:\n"
                    f"  STATUS.md: {status_count}\n"
                    f"  README.md: {readme_count}\n"
                    f"Update README.md to match STATUS.md (source of truth)"
                )


# =============================================================================
# Markdown Syntax Tests
# =============================================================================

class TestMarkdownSyntax:
    """Verify markdown syntax is valid in root files."""

    @pytest.mark.parametrize("filename", [f for f in ROOT_FILES.keys() if f != "CHANGELOG.md"])
    def test_root_level_file_references_exist(self, filename: str):
        """References to root-level files (FOO.md, BAR.md) should exist.

        CHANGELOG.md is excluded as it contains historical references.
        """
        path = REPO_ROOT / filename
        if not path.exists():
            pytest.skip(f"{filename} doesn't exist")

        content = path.read_text()
        broken = []

        # Find references to root-level .md files: `FOO.md` or see FOO.md or FOO.md (line start)
        # Pattern: word boundary, ALLCAPS or CamelCase filename, .md extension
        for match in re.finditer(r'`([A-Z][A-Z_]*\.md)`|(?:see|See)\s+`?([A-Z][A-Z_]*\.md)`?', content):
            ref_file = match.group(1) or match.group(2)
            if ref_file:
                full_path = REPO_ROOT / ref_file
                if not full_path.exists():
                    broken.append(ref_file)

        if broken:
            pytest.fail(
                f"{filename} references non-existent root files:\n" +
                "\n".join(f"  - {b}" for b in set(broken)) +
                "\n\nEither create these files or remove/update the references"
            )

    @pytest.mark.parametrize("filename", ROOT_FILES.keys())
    def test_code_blocks_balanced(self, filename: str):
        """Code fence markers (```) must be balanced (even count)."""
        path = REPO_ROOT / filename
        if not path.exists():
            pytest.skip(f"{filename} doesn't exist")

        content = path.read_text()
        fence_count = content.count('```')

        if fence_count % 2 != 0:
            # Find the unclosed block for better error message
            lines = content.split('\n')
            open_blocks = []
            for i, line in enumerate(lines, 1):
                if line.strip().startswith('```'):
                    if open_blocks and not lines[open_blocks[-1]-1].strip().startswith('```'):
                        open_blocks.pop()
                    else:
                        open_blocks.append(i)

            pytest.fail(
                f"{filename} has unbalanced code fences ({fence_count} markers, should be even)\n"
                f"Likely unclosed block near line(s): {open_blocks[-3:] if open_blocks else 'unknown'}"
            )

    @pytest.mark.parametrize("filename", [f for f in ROOT_FILES.keys() if f != "CHANGELOG.md"])
    def test_inline_file_references_exist(self, filename: str):
        """Inline file references (backtick paths with directories) should point to existing files.

        Only checks paths with '/' to avoid false positives from bare filenames.
        CHANGELOG.md is excluded as it contains historical references.
        """
        path = REPO_ROOT / filename
        if not path.exists():
            pytest.skip(f"{filename} doesn't exist")

        content = path.read_text()
        broken = []

        # Find backtick references that look like file paths WITH directories
        # Pattern: `path/to/file.ext` - must contain at least one /
        for match in re.finditer(r'`([A-Za-z_][A-Za-z0-9_./]*?/[A-Za-z0-9_./]*\.[a-z]{1,5})`', content):
            ref_path = match.group(1)
            # Skip obvious non-paths
            if ref_path.startswith(('http', 'example')):
                continue
            # Skip patterns with wildcards or variables
            if '*' in ref_path or '{' in ref_path:
                continue
            # Skip test fixture patterns
            if '.v2.jsonl' in ref_path:
                continue

            full_path = REPO_ROOT / ref_path
            if not full_path.exists():
                found = False

                # Check common alternate locations for seed files
                if ref_path.startswith('seeds/'):
                    # seeds/ moved to mu/ subdirectories
                    alt_paths = [
                        ref_path.replace('seeds/', 'mu/substrate/'),
                        ref_path.replace('seeds/', 'mu/utilities/'),
                        ref_path.replace('seeds/', 'mu/closures/'),
                        ref_path.replace('seeds/', 'mu/programs/'),
                    ]
                    if any((REPO_ROOT / alt).exists() for alt in alt_paths):
                        found = True

                # Check docs/ subdirectories for doc paths
                if not found and ref_path.startswith('docs/'):
                    # docs/Foo.md might be docs/core/Foo.md, docs/cli/Foo.md, etc.
                    basename = ref_path.replace('docs/', '')
                    for subdir in ['core', 'cli', 'audit', 'execution', 'schemas', 'archive']:
                        if (REPO_ROOT / 'docs' / subdir / basename).exists():
                            found = True
                            break

                if not found:
                    broken.append(ref_path)

        if broken:
            pytest.fail(
                f"{filename} references non-existent files:\n" +
                "\n".join(f"  - {b}" for b in broken[:10]) +
                "\n\nEither create these files, update the paths, or remove the references"
            )


# =============================================================================
# Cross-Document L-Level Consistency
# =============================================================================

class TestLLevelConsistency:
    """L-level claims must be consistent across ALL docs, not just README."""

    def test_docs_dont_claim_outdated_l_levels(self):
        """Docs in docs/core/ and docs/audit/ shouldn't claim outdated L-levels."""
        status_path = REPO_ROOT / "STATUS.md"
        if not status_path.exists():
            pytest.skip("STATUS.md doesn't exist")

        status_content = status_path.read_text()

        # Determine current L-level status from STATUS.md
        # Look for explicit status markers
        l_status = {}
        for level in ["L1", "L2", "L3", "L4"]:
            if re.search(rf'{level}.*(?:DONE|COMPLETE|FULL|ACHIEVED)', status_content, re.I):
                l_status[level] = "complete"
            elif re.search(rf'{level}.*(?:FUTURE|SINK|TODO)', status_content, re.I):
                l_status[level] = "future"
            else:
                l_status[level] = "unknown"

        violations = []
        for doc_dir in ["docs/core", "docs/audit"]:
            doc_path = REPO_ROOT / doc_dir
            if not doc_path.exists():
                continue

            for doc_file in doc_path.glob("*.md"):
                content = doc_file.read_text()

                # Check for outdated claims
                for level, status in l_status.items():
                    if status == "complete":
                        # Doc shouldn't say this level is incomplete/in-progress
                        if re.search(rf'(?:current|project)\s+(?:state|status).*{level}', content, re.I):
                            # Found a claim about current state being at this level
                            if re.search(rf'{level}.*(?:IN PROGRESS|TODO|PENDING|INCOMPLETE)', content, re.I):
                                violations.append(
                                    f"{doc_file.name}: Claims {level} is incomplete but STATUS.md says it's complete"
                                )

        if violations:
            pytest.fail(
                f"L-level inconsistencies found:\n" +
                "\n".join(f"  - {v}" for v in violations[:5])
            )


# =============================================================================
# Forbidden Patterns in Root Files
# =============================================================================

class TestForbiddenPatternsRootFiles:
    """Root files should not contain certain patterns."""

    def test_no_current_state_heading_in_docs(self):
        """Docs should not have 'Current State' as a heading (use STATUS.md reference)."""
        violations = []

        for doc_dir in ["docs/core", "docs/audit", "docs/execution"]:
            doc_path = REPO_ROOT / doc_dir
            if not doc_path.exists():
                continue

            for doc_file in doc_path.glob("*.md"):
                content = doc_file.read_text()

                # Remove code blocks before checking (they might contain examples)
                content_no_code = re.sub(r'```[\s\S]*?```', '', content)

                # Look for "Current State" as a markdown heading
                # Pattern: ## Current State or # Current State or ### Current State
                if re.search(r'^#+\s*Current\s+State', content_no_code, re.MULTILINE | re.IGNORECASE):
                    violations.append(doc_file.name)

        if violations:
            pytest.fail(
                f"Docs with 'Current State' heading (forbidden - use STATUS.md reference):\n" +
                "\n".join(f"  - {v}" for v in violations) +
                "\n\nRename to 'Implementation Status' and add 'See STATUS.md for current state.'"
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
