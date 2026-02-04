"""
Roadmap Document Governance Tests - Lightweight enforcement for roadmap/ folder.

The roadmap/ folder follows DIFFERENT rules than docs/core/ and other governed folders:
- Roadmap docs define SEQUENCE and DESIGN only, not current state
- They must link UP to STATUS.md and TASKS.md (not duplicate their content)
- They do NOT require DOC_STATUS headers (they're planning docs, not specs)

This is enforced separately from the main doc governance per the exception
documented in DocGovernance.v0.md.

See roadmap/MANIFEST.md for the full linking rules.

Usage:
    PYTHONHASHSEED=0 pytest tests/docs/test_roadmap_governance.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
ROADMAP_FOLDER = REPO_ROOT / "roadmap"


# =============================================================================
# Helper Functions
# =============================================================================

def get_roadmap_docs() -> list[Path]:
    """Get all .md files in roadmap/."""
    if not ROADMAP_FOLDER.exists():
        return []
    return sorted(ROADMAP_FOLDER.glob("*.md"))


# =============================================================================
# Reference Header Checks
# =============================================================================

class TestRoadmapReferenceHeaders:
    """Roadmap docs must link UP to canonical sources."""

    # Required reference patterns - docs must link to STATUS.md and TASKS.md
    REQUIRED_REFERENCES = [
        (r'\[`?STATUS\.md`?\]', "STATUS.md reference"),
        (r'\[`?TASKS\.md`?\]', "TASKS.md reference"),
    ]

    def test_roadmap_folder_exists(self):
        """roadmap/ folder must exist."""
        assert ROADMAP_FOLDER.exists(), "roadmap/ folder missing"

    def test_manifest_exists(self):
        """MANIFEST.md must exist to define reading order."""
        manifest = ROADMAP_FOLDER / "MANIFEST.md"
        assert manifest.exists(), "roadmap/MANIFEST.md missing - required for linking rules"

    def test_all_docs_have_status_reference(self):
        """All roadmap docs must reference STATUS.md."""
        missing = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Check for STATUS.md reference
            if not re.search(r'\[`?STATUS\.md`?\]', content):
                missing.append(doc_path.name)

        if missing:
            msg = "\nRoadmap docs missing STATUS.md reference:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nFix: Add reference header per roadmap/MANIFEST.md linking rules:\n"
            msg += '  > **Current State**: See [`STATUS.md`](../STATUS.md)\n'
            pytest.fail(msg)

    def test_all_docs_have_tasks_reference(self):
        """All roadmap docs must reference TASKS.md."""
        missing = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Check for TASKS.md reference
            if not re.search(r'\[`?TASKS\.md`?\]', content):
                missing.append(doc_path.name)

        if missing:
            msg = "\nRoadmap docs missing TASKS.md reference:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nFix: Add reference header per roadmap/MANIFEST.md linking rules:\n"
            msg += '  > **Authorization**: See [`TASKS.md`](../TASKS.md)\n'
            pytest.fail(msg)


# =============================================================================
# No Inline State Checks
# =============================================================================

class TestRoadmapNoInlineState:
    """Roadmap docs must not contain inline current state."""

    # Patterns that indicate inline state (not allowed in roadmap docs)
    FORBIDDEN_STATE_PATTERNS = [
        (r'^#+\s*Current State\s*$', "## Current State section header"),
        (r'\*\*(?:Completed|In Progress|Awaiting):\*\*', "**Completed:**/**In Progress:** lists"),
        (r'^\s*-\s*\[[ x]\]', "Checkbox task lists (use TASKS.md instead)"),
    ]

    def test_no_current_state_sections(self):
        """Roadmap docs should not have 'Current State' sections."""
        violations = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Remove code blocks (they might contain examples)
            content_no_code = re.sub(r'```[\s\S]*?```', '', content)

            for pattern, desc in self.FORBIDDEN_STATE_PATTERNS:
                if re.search(pattern, content_no_code, re.MULTILINE | re.IGNORECASE):
                    violations.append((doc_path.name, desc))
                    break  # One violation per doc is enough

        if violations:
            msg = "\nRoadmap docs with inline state (violates roadmap linking rules):\n"
            for doc, desc in sorted(set(violations)):
                msg += f"  - {doc}: {desc}\n"
            msg += "\nFix: Roadmap docs define SEQUENCE only. Track state in STATUS.md.\n"
            pytest.fail(msg)


# =============================================================================
# Link Validation
# =============================================================================

class TestRoadmapLinkValidation:
    """Validate that links in roadmap docs point to existing files."""

    def test_status_md_exists(self):
        """STATUS.md must exist at repo root."""
        assert (REPO_ROOT / "STATUS.md").exists(), "STATUS.md missing from repo root"

    def test_tasks_md_exists(self):
        """TASKS.md must exist at repo root."""
        assert (REPO_ROOT / "TASKS.md").exists(), "TASKS.md missing from repo root"

    def test_internal_links_valid(self):
        """Links within roadmap/ should point to existing files."""
        broken = []

        for doc_path in get_roadmap_docs():
            content = doc_path.read_text()

            # Find markdown links: [text](path)
            links = re.findall(r'\[([^\]]*)\]\(([^)]+)\)', content)

            for link_text, link_target in links:
                # Skip external links
                if link_target.startswith(('http://', 'https://', '#')):
                    continue

                # Resolve relative path
                if link_target.startswith('../'):
                    target_path = doc_path.parent / link_target
                else:
                    target_path = doc_path.parent / link_target

                # Normalize and check existence
                target_path = target_path.resolve()
                if not target_path.exists():
                    broken.append((doc_path.name, link_target))

        if broken:
            msg = "\nBroken links in roadmap docs:\n"
            for doc, target in sorted(set(broken)):
                msg += f"  - {doc} -> {target}\n"
            pytest.fail(msg)


# =============================================================================
# Scope Declaration Check
# =============================================================================

class TestRoadmapScopeDeclaration:
    """Roadmap docs should declare their scope."""

    # Acceptable scope declarations
    SCOPE_PATTERNS = [
        r'This document defines (?:SEQUENCE|DESIGN|EXIT CRITERIA)',
        r'\*\*Scope\*\*:.*(?:SEQUENCE|DESIGN|DECISION|sequence|design|only)',
        r'Draft specs live in `roadmap/`',
    ]

    def test_docs_declare_scope(self):
        """Roadmap docs should declare their limited scope."""
        missing_scope = []

        for doc_path in get_roadmap_docs():
            # Skip MANIFEST.md (it defines the rules, doesn't need to follow them)
            if doc_path.name == "MANIFEST.md":
                continue

            content = doc_path.read_text()

            has_scope = any(
                re.search(pattern, content, re.IGNORECASE)
                for pattern in self.SCOPE_PATTERNS
            )

            if not has_scope:
                missing_scope.append(doc_path.name)

        if missing_scope:
            msg = "\nRoadmap docs missing scope declaration:\n"
            for doc in sorted(missing_scope):
                msg += f"  - {doc}\n"
            msg += "\nFix: Add scope line to reference header, e.g.:\n"
            msg += '  > **Scope**: This document defines SEQUENCE only.\n'
            pytest.fail(msg)


# =============================================================================
# Coverage Report
# =============================================================================

class TestRoadmapCoverage:
    """Report on roadmap doc coverage."""

    def test_minimum_roadmap_docs(self):
        """Verify minimum roadmap docs exist."""
        docs = get_roadmap_docs()
        MIN_DOCS = 3  # At least MANIFEST, ROADMAP, and one spec

        if len(docs) < MIN_DOCS:
            pytest.fail(
                f"Too few roadmap docs: {len(docs)} (minimum: {MIN_DOCS})\n"
                f"Expected at least: MANIFEST.md, ROADMAP.md, and one spec"
            )

    def test_required_docs_exist(self):
        """Required roadmap docs must exist."""
        required = ["MANIFEST.md", "ROADMAP.md"]
        missing = []

        for doc_name in required:
            if not (ROADMAP_FOLDER / doc_name).exists():
                missing.append(doc_name)

        if missing:
            msg = "\nRequired roadmap docs missing:\n"
            for doc in missing:
                msg += f"  - roadmap/{doc}\n"
            pytest.fail(msg)
