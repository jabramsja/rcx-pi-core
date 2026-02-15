"""
Documentation Governance Tests - Enforces the Three Laws across entire repo.

Law 1: Two files own current state (STATUS.md, TASKS.md)
Law 2: Every doc has a lifecycle (DOC_STATUS header with ALL required fields)
Law 3: Design docs describe WHAT, not progress

This module enforces STRICT governance per DocGovernance.v0.md:
- ALL docs in docs/ folders require DOC_STATUS headers
- Headers must have ALL 5 required fields: TYPE, LAST_VERIFIED, OWNER, FOR_CURRENT_STATE, GROUNDING_TESTS
- Only truly generated/test content is exempt

Exempt paths (no governance required):
- .pytest_cache/, .github/ - generated/config
- /archive/ paths - historical, read-only
- tests/golden/, tests/archive/ - test fixtures
- rcx_pi_rust/, rcx_omega/, rcx_python_examples/ - all archived

See mu/docs/core/DocGovernance.v0.md for full policy.

Usage:
    PYTHONHASHSEED=0 pytest tests/docs/test_doc_governance.py -v
"""

from __future__ import annotations

# PATH SETUP - Ensure repo root is at position 0 for 'tools' imports
# pytest adds tests/ to sys.path which shadows repo root's tools package
import sys as _sys
from pathlib import Path as _Path
_repo_root = str(_Path(__file__).parent.parent.parent)
if _sys.path[0] != _repo_root:
    if _repo_root in _sys.path:
        _sys.path.remove(_repo_root)
    _sys.path.insert(0, _repo_root)

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import pytest

from tools.shared_doc_config import REPO_ROOT, get_governed_folders_as_strings

# =============================================================================
# Strict Governance Configuration (per DocGovernance.v0.md)
# =============================================================================

# ALL folders under governance - ALL Three Laws enforced
# Single source of truth: tools/shared_doc_config.py
GOVERNED_FOLDERS = get_governed_folders_as_strings()

# EXEMPT - truly no governance required (generated, archived, separate projects)
EXEMPT_PATTERNS = [
    r"^\.pytest_cache/",           # pytest generated
    r"^\.github/",                 # GitHub templates
    r"^\.rcx_library/",            # Library files
    r"/archive/",                  # Any archive folder (historical, read-only)
    r"tools/agents/.*_prompt\.md$", # Agent prompt templates (not docs)
    r"\.auto\.md$",                # Auto-generated docs
    r"^archive/",                    # All archived content (docs, roadmap, subprojects)
    r"^tests/archive/",            # Archived tests
    r"^tests/golden/",             # Golden test files
    r"^mu/docs/TESTING_PERFORMANCE_ISSUE\.md$",  # Historical context (resolved issue)
]

# Root files that are exempt (they ARE the source of truth)
EXEMPT_ROOT_FILES = {
    "STATUS.md",
    "TASKS.md",
    "README.md",
    "CLAUDE.md",
    "CHANGELOG.md",
}

# Valid DOC_STATUS types
VALID_DOC_TYPES = {"REFERENCE", "DESIGN_SPEC", "IMPLEMENTATION", "SUPERSEDED", "ARCHIVED"}

# Required header fields per DocGovernance.v0.md
REQUIRED_HEADER_FIELDS = ["TYPE", "LAST_VERIFIED", "OWNER", "FOR_CURRENT_STATE", "GROUNDING_TESTS"]

# Maximum days since LAST_VERIFIED before warning
STALE_THRESHOLD_DAYS = 90


# =============================================================================
# Helper Types and Functions
# =============================================================================

class DocHeader(NamedTuple):
    """Parsed DOC_STATUS header."""
    doc_type: str | None
    last_verified: str | None
    owner: str | None
    for_current_state: str | None
    grounding_tests: str | None
    superseded_by: str | None
    archived_reason: str | None
    raw_content: str


def parse_doc_header(content: str) -> DocHeader | None:
    """Extract DOC_STATUS header from doc content."""
    match = re.search(r'<!--\s*\nDOC_STATUS\n(.*?)\n-->', content, re.DOTALL)
    if not match:
        return None

    header_content = match.group(1)

    def extract_field(field: str) -> str | None:
        field_match = re.search(rf'^{field}:\s*(.+)$', header_content, re.MULTILINE)
        return field_match.group(1).strip() if field_match else None

    return DocHeader(
        doc_type=extract_field("TYPE"),
        last_verified=extract_field("LAST_VERIFIED"),
        owner=extract_field("OWNER"),
        for_current_state=extract_field("FOR_CURRENT_STATE"),
        grounding_tests=extract_field("GROUNDING_TESTS"),
        superseded_by=extract_field("SUPERSEDED_BY"),
        archived_reason=extract_field("ARCHIVED_REASON"),
        raw_content=header_content,
    )


def is_exempt(doc_path: Path) -> bool:
    """Check if a doc is exempt from governance."""
    rel_path = str(doc_path.relative_to(REPO_ROOT))

    # Root exempt files
    if doc_path.parent == REPO_ROOT and doc_path.name in EXEMPT_ROOT_FILES:
        return True

    # Exempt patterns
    for pattern in EXEMPT_PATTERNS:
        if re.search(pattern, rel_path):
            return True

    return False


def is_governed(doc_path: Path) -> bool:
    """Check if a doc is under governance (not exempt)."""
    if is_exempt(doc_path):
        return False

    rel_path = str(doc_path.relative_to(REPO_ROOT))

    # Check governed folders
    for folder in GOVERNED_FOLDERS:
        if rel_path.startswith(folder + "/") or rel_path.startswith(folder.replace("/", "\\") + "\\"):
            return True

    # Subproject READMEs (like rcx_pi/README.md) are governed
    if re.match(r"^[^/]+/README\.md$", rel_path):
        return True

    # mu/docs/README.md is governed
    if rel_path == "mu/docs/README.md":
        return True

    return False


def get_all_md_files() -> list[Path]:
    """Get all .md files in repo."""
    return sorted(REPO_ROOT.rglob("*.md"))


def get_governed_docs() -> list[Path]:
    """Get all docs under governance."""
    return [doc for doc in get_all_md_files() if is_governed(doc)]


def get_exempt_docs() -> list[Path]:
    """Get all exempt docs."""
    return [doc for doc in get_all_md_files() if is_exempt(doc)]


# =============================================================================
# Law 1: Two Files Own Current State
# =============================================================================

class TestLaw1SingleSourceOfTruth:
    """STATUS.md and TASKS.md are the only sources of current state."""

    def test_status_md_exists(self):
        """STATUS.md must exist at repo root."""
        assert (REPO_ROOT / "STATUS.md").exists(), "STATUS.md missing from repo root"

    def test_tasks_md_exists(self):
        """TASKS.md must exist at repo root."""
        assert (REPO_ROOT / "TASKS.md").exists(), "TASKS.md missing from repo root"

    def test_no_inline_current_state_sections(self):
        """ALL governed docs should not have 'Current State' sections."""
        violations = []

        # Patterns that indicate inline status sections
        bad_patterns = [
            (r'^#+\s*Current State', "## Current State section"),
            (r'\*\*(?:Completed|In Progress|Awaiting):\*\*', "**Completed:**/**In Progress:** lists"),
        ]

        for doc_path in get_governed_docs():
            content = doc_path.read_text()

            # Remove code blocks before checking (they might contain examples)
            content_no_code = re.sub(r'```[\s\S]*?```', '', content)

            for pattern, desc in bad_patterns:
                if re.search(pattern, content_no_code, re.MULTILINE | re.IGNORECASE):
                    # Exception: if it immediately references STATUS.md
                    lines = content_no_code.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            # Check next few lines for STATUS.md reference
                            context = '\n'.join(lines[i:i+5])
                            if 'STATUS.md' not in context:
                                violations.append((doc_path.name, desc))
                                break

        if violations:
            # Deduplicate
            violations = list(set(violations))
            msg = "\nDocs with inline 'Current State' sections (violates Law 1):\n"
            for doc, desc in sorted(violations)[:10]:
                msg += f"  - {doc}: {desc}\n"
            msg += "\nFix: Replace with 'See STATUS.md for current state.'\n"
            pytest.fail(msg)


# =============================================================================
# Law 2: Every Doc Has a Lifecycle (STRICT - all 5 required fields)
# =============================================================================

class TestLaw2DocLifecycle:
    """Every governed doc must have a valid DOC_STATUS header with ALL required fields."""

    def test_all_governed_docs_have_headers(self):
        """ALL governed docs must have DOC_STATUS headers (no exceptions)."""
        missing = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header is None:
                rel_path = doc_path.relative_to(REPO_ROOT)
                missing.append(str(rel_path))

        if missing:
            msg = f"\nGoverned docs missing DOC_STATUS header ({len(missing)} total):\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nRun: python tools/add_doc_headers.py\n"
            msg += "Per DocGovernance.v0.md: 'A doc without DOC_STATUS fails CI.'\n"
            pytest.fail(msg)

    def test_headers_have_valid_type(self):
        """DOC_STATUS TYPE must be valid."""
        invalid = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and header.doc_type and header.doc_type not in VALID_DOC_TYPES:
                invalid.append((doc_path.name, header.doc_type))

        if invalid:
            msg = f"\nDocs with invalid TYPE (must be one of {VALID_DOC_TYPES}):\n"
            for doc, dtype in invalid:
                msg += f"  - {doc}: {dtype}\n"
            pytest.fail(msg)

    def test_headers_have_last_verified(self):
        """ALL governed docs must have LAST_VERIFIED."""
        missing = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and not header.last_verified:
                rel_path = doc_path.relative_to(REPO_ROOT)
                missing.append(str(rel_path))

        if missing:
            msg = f"\nGoverned docs missing LAST_VERIFIED:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            pytest.fail(msg)

    def test_headers_have_owner(self):
        """ALL governed docs must have OWNER."""
        missing = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and not header.owner:
                rel_path = doc_path.relative_to(REPO_ROOT)
                missing.append(str(rel_path))

        if missing:
            msg = f"\nGoverned docs missing OWNER:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            pytest.fail(msg)

    def test_headers_have_for_current_state(self):
        """ALL governed docs must have FOR_CURRENT_STATE."""
        missing = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and not header.for_current_state:
                rel_path = doc_path.relative_to(REPO_ROOT)
                missing.append(str(rel_path))

        if missing:
            msg = f"\nGoverned docs missing FOR_CURRENT_STATE:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nPer DocGovernance.v0.md, should be: 'See STATUS.md and TASKS.md'\n"
            pytest.fail(msg)

    def test_headers_have_grounding_tests(self):
        """ALL governed docs must have GROUNDING_TESTS (can be 'none')."""
        missing = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and not header.grounding_tests:
                rel_path = doc_path.relative_to(REPO_ROOT)
                missing.append(str(rel_path))

        if missing:
            msg = f"\nGoverned docs missing GROUNDING_TESTS:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nPer DocGovernance.v0.md, use 'none' if no grounding tests exist.\n"
            pytest.fail(msg)

    def test_last_verified_format(self):
        """LAST_VERIFIED must be valid YYYY-MM-DD format."""
        invalid = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and header.last_verified:
                try:
                    datetime.strptime(header.last_verified, "%Y-%m-%d")
                except ValueError:
                    invalid.append((doc_path.name, header.last_verified))

        if invalid:
            msg = f"\nDocs with invalid LAST_VERIFIED format:\n"
            for doc, date in invalid:
                msg += f"  - {doc}: {date}\n"
            pytest.fail(msg)

    def test_superseded_docs_have_replacement(self):
        """SUPERSEDED docs must have SUPERSEDED_BY."""
        missing = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and header.doc_type == "SUPERSEDED" and not header.superseded_by:
                missing.append(doc_path.name)

        if missing:
            msg = f"\nSUPERSEDED docs missing SUPERSEDED_BY:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            pytest.fail(msg)

    def test_warn_stale_docs(self):
        """Warn about docs not verified recently."""
        stale = []
        threshold = datetime.now() - timedelta(days=STALE_THRESHOLD_DAYS)

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and header.last_verified:
                try:
                    verified_date = datetime.strptime(header.last_verified, "%Y-%m-%d")
                    if verified_date < threshold:
                        days_old = (datetime.now() - verified_date).days
                        stale.append((doc_path.name, days_old))
                except ValueError:
                    pass

        if stale:
            import warnings
            msg = f"Docs not verified in {STALE_THRESHOLD_DAYS}+ days:\n"
            for doc, days in sorted(stale, key=lambda x: -x[1])[:10]:
                msg += f"  - {doc}: {days} days old\n"
            warnings.warn(msg)


# =============================================================================
# Law 3: Design Docs Describe WHAT, Not Progress
# =============================================================================

class TestLaw3NoProgressInDesignDocs:
    """DESIGN_SPEC docs should not contain progress tracking."""

    def test_no_phase_progress_claims(self):
        """DESIGN_SPEC docs should not claim phases are in progress."""
        violations = []

        progress_patterns = [
            r'Phase \d+[a-z]?\s+(?:is\s+)?(?:in progress|complete|done|TODO)',
            r'Step \d+\s+(?:is\s+)?(?:in progress|complete|done|TODO)',
            r'(?:Currently|Now)\s+(?:working on|implementing|building)',
        ]

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)

            if header and header.doc_type == "DESIGN_SPEC":
                for pattern in progress_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        violations.append((doc_path.name, matches[0]))

        if violations:
            violations = list(set(violations))
            msg = "\nDESIGN_SPEC docs with progress claims (violates Law 3):\n"
            for doc, match in sorted(violations)[:10]:
                msg += f"  - {doc}: '{match}'\n"
            msg += "\nFix: Move progress to STATUS.md, or change TYPE to IMPLEMENTATION\n"
            pytest.fail(msg)


# =============================================================================
# Governance Coverage Report
# =============================================================================

class TestGovernanceCoverage:
    """Report on governance coverage."""

    def test_governance_coverage_minimum(self):
        """Verify minimum governance coverage is maintained."""
        all_docs = get_all_md_files()
        governed_count = len(get_governed_docs())
        exempt_count = len(get_exempt_docs())
        total = len(all_docs)

        # Governance coverage must meet minimum threshold
        # Currently: 47 governed, 86 exempt = 35% governed
        # This prevents accidental expansion of EXEMPT patterns
        MIN_GOVERNED = 45  # At least 45 docs must be governed
        MIN_GOVERNED_PERCENT = 30  # At least 30% of docs must be governed

        governed_percent = (governed_count / total * 100) if total > 0 else 0

        if governed_count < MIN_GOVERNED:
            pytest.fail(
                f"Governance coverage too low!\n"
                f"  GOVERNED: {governed_count} (minimum: {MIN_GOVERNED})\n"
                f"  EXEMPT: {exempt_count}\n"
                f"  Check EXEMPT_PATTERNS in test_doc_governance.py - too many docs exempt?"
            )

        if governed_percent < MIN_GOVERNED_PERCENT:
            pytest.fail(
                f"Governance coverage percentage too low!\n"
                f"  GOVERNED: {governed_count}/{total} ({governed_percent:.1f}%)\n"
                f"  Minimum: {MIN_GOVERNED_PERCENT}%\n"
                f"  Check EXEMPT_PATTERNS - too many docs exempt?"
            )


# =============================================================================
# Structural Checks
# =============================================================================

class TestDocStructure:
    """Verify doc folder structure."""

    def test_no_ungoverned_docs_in_docs_folder(self):
        """All docs in mu/docs/ should be in a governed subfolder or roadmap."""
        ungoverned = []
        docs_folder = REPO_ROOT / "mu" / "docs"

        if not docs_folder.exists():
            return

        for doc_path in docs_folder.rglob("*.md"):
            rel_path = doc_path.relative_to(REPO_ROOT)
            rel_str = str(rel_path)

            # Skip if in archive
            if "/archive/" in rel_str:
                continue

            # Skip if exempt
            if is_exempt(doc_path):
                continue

            # mu/docs/README.md is allowed at root level
            if rel_str == "mu/docs/README.md":
                continue

            # Check if it's in a governed folder or roadmap (special folder)
            in_governed_folder = any(
                rel_str.startswith(f + "/")
                for f in GOVERNED_FOLDERS + ["mu/docs/roadmap"]
            )

            if not in_governed_folder:
                ungoverned.append(str(rel_path))

        if ungoverned:
            msg = f"\nDocs in mu/docs/ not in a governed subfolder:\n"
            for doc in sorted(ungoverned):
                msg += f"  - {doc}\n"
            msg += "\nMove to mu/docs/core/, archive/docs/, or add folder to GOVERNED_FOLDERS\n"
            pytest.fail(msg)


# =============================================================================
# Cross-Reference Validation
# =============================================================================

class TestDocCrossReferences:
    """Verify cross-references between docs are valid."""

    def test_superseded_by_targets_exist(self):
        """SUPERSEDED_BY targets must exist."""
        broken = []

        for doc_path in get_governed_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and header.superseded_by:
                target_path = REPO_ROOT / header.superseded_by
                if not target_path.exists():
                    broken.append((doc_path.name, header.superseded_by))

        if broken:
            msg = "\nBroken SUPERSEDED_BY references:\n"
            for doc, target in broken:
                msg += f"  - {doc} -> {target}\n"
            pytest.fail(msg)


# =============================================================================
# Meta Validation
# =============================================================================

class TestGovernanceMeta:
    """Verify the governance system itself is valid."""

    def test_governance_doc_exists(self):
        """The governance doc must exist."""
        gov_path = REPO_ROOT / "mu" / "docs" / "core" / "DocGovernance.v0.md"
        assert gov_path.exists(), "DocGovernance.v0.md must exist"

    def test_governance_doc_has_valid_header(self):
        """The governance doc must have a valid header."""
        gov_path = REPO_ROOT / "mu" / "docs" / "core" / "DocGovernance.v0.md"
        if gov_path.exists():
            content = gov_path.read_text()
            header = parse_doc_header(content)
            assert header is not None, "DocGovernance.v0.md needs DOC_STATUS header"
            assert header.doc_type == "REFERENCE", "DocGovernance.v0.md should be REFERENCE"
