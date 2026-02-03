"""
Documentation Governance Tests - Enforces the Three Laws across entire repo.

Law 1: Two files own current state (STATUS.md, TASKS.md)
Law 2: Every doc has a lifecycle (DOC_STATUS header)
Law 3: Design docs describe WHAT, not progress

This module uses TIERED governance:
- FULL: docs/core/, docs/agents/, docs/audit/, docs/execution/ - all rules enforced
- LIGHT: docs/cli/, docs/schemas/, READMEs - just needs header
- EXEMPT: archives, generated files, tool prompts, .github/, .pytest_cache/

See docs/core/DocGovernance.v0.md for full policy.

Usage:
    PYTHONHASHSEED=0 pytest tests/docs/test_doc_governance.py -v
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

# =============================================================================
# Tiered Governance Configuration
# =============================================================================

# FULL governance - all Three Laws enforced
FULL_GOVERNANCE_FOLDERS = [
    "docs/core",
    "docs/agents",
    "docs/audit",
    "docs/execution",
]

# LIGHT governance - just needs DOC_STATUS header (Law 2 only)
LIGHT_GOVERNANCE_FOLDERS = [
    "docs/cli",
    "docs/schemas",
    "docs/reviews",
]

# LIGHT governance for specific patterns (READMEs at various levels)
LIGHT_GOVERNANCE_PATTERNS = [
    r"^[^/]+/README\.md$",  # Subproject READMEs like rcx_pi/README.md
    r"^docs/README\.md$",
]

# EXEMPT - no governance required
EXEMPT_PATTERNS = [
    r"^\.pytest_cache/",           # pytest generated
    r"^\.github/",                 # GitHub templates
    r"^\.claude/agents/archive",   # Archived agent configs
    r"^\.rcx_library/",            # Library files
    r"/archive/",                  # Any archive folder
    r"/archive_pre_guardrails/",   # Old agent archives
    r"tools/agents/.*_prompt\.md$", # Agent prompt templates
    r"\.auto\.md$",                # Auto-generated docs
    r"^rcx_pi_rust/",              # Rust subproject (separate governance)
    r"^rcx_omega/",                # Omega subproject
    r"^rcx_python_examples/",      # Examples subproject
    r"^tests/archive/",            # Archived tests
    r"^tests/golden/",             # Golden test files
    r"^docs/README\.md$",          # Auto-generated docs index
    r"^docs/TESTING_PERFORMANCE_ISSUE\.md$",  # Historical context (resolved issue)
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
    grounding_tests: str | None
    superseded_by: str | None
    archived_reason: str | None
    raw_content: str


class GovernanceTier:
    """Governance tier for a doc."""
    FULL = "full"
    LIGHT = "light"
    EXEMPT = "exempt"


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
        grounding_tests=extract_field("GROUNDING_TESTS"),
        superseded_by=extract_field("SUPERSEDED_BY"),
        archived_reason=extract_field("ARCHIVED_REASON"),
        raw_content=header_content,
    )


def get_governance_tier(doc_path: Path) -> str:
    """Determine governance tier for a doc."""
    rel_path = str(doc_path.relative_to(REPO_ROOT))

    # Check if root exempt file
    if doc_path.parent == REPO_ROOT and doc_path.name in EXEMPT_ROOT_FILES:
        return GovernanceTier.EXEMPT

    # Check exempt patterns
    for pattern in EXEMPT_PATTERNS:
        if re.search(pattern, rel_path):
            return GovernanceTier.EXEMPT

    # Check full governance folders
    for folder in FULL_GOVERNANCE_FOLDERS:
        if rel_path.startswith(folder + "/"):
            return GovernanceTier.FULL

    # Check light governance folders
    for folder in LIGHT_GOVERNANCE_FOLDERS:
        if rel_path.startswith(folder + "/"):
            return GovernanceTier.LIGHT

    # Check light governance patterns
    for pattern in LIGHT_GOVERNANCE_PATTERNS:
        if re.match(pattern, rel_path):
            return GovernanceTier.LIGHT

    # Default: LIGHT governance for any other doc
    # This ensures future docs are covered but not over-strict
    return GovernanceTier.LIGHT


def get_all_md_files() -> list[Path]:
    """Get all .md files in repo."""
    return sorted(REPO_ROOT.rglob("*.md"))


def get_governed_docs(tier: str | None = None) -> list[Path]:
    """Get docs at a specific governance tier (or all governed if tier=None)."""
    docs = []
    for doc_path in get_all_md_files():
        doc_tier = get_governance_tier(doc_path)
        if doc_tier == GovernanceTier.EXEMPT:
            continue
        if tier is None or doc_tier == tier:
            docs.append(doc_path)
    return docs


def get_full_governance_docs() -> list[Path]:
    """Get docs under full governance."""
    return get_governed_docs(GovernanceTier.FULL)


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
        """FULL governance docs should not have 'Current State' sections."""
        violations = []

        # Patterns that indicate inline status sections
        bad_patterns = [
            (r'^#+\s*Current State', "## Current State section"),
            (r'\*\*(?:Completed|In Progress|Awaiting):\*\*', "**Completed:**/**In Progress:** lists"),
        ]

        for doc_path in get_full_governance_docs():
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
# Law 2: Every Doc Has a Lifecycle
# =============================================================================

class TestLaw2DocLifecycle:
    """Every governed doc must have a valid DOC_STATUS header."""

    def test_full_governance_docs_have_headers(self):
        """FULL governance docs must have DOC_STATUS headers."""
        missing = []

        for doc_path in get_full_governance_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header is None:
                rel_path = doc_path.relative_to(REPO_ROOT)
                missing.append(str(rel_path))

        if missing:
            msg = f"\nFULL governance docs missing DOC_STATUS header:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
            msg += "\nRun: python tools/add_doc_headers.py\n"
            pytest.fail(msg)

    def test_light_governance_docs_have_headers(self):
        """LIGHT governance docs should have headers (warning, not failure)."""
        missing = []

        for doc_path in get_governed_docs(GovernanceTier.LIGHT):
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header is None:
                rel_path = doc_path.relative_to(REPO_ROOT)
                missing.append(str(rel_path))

        if missing:
            import warnings
            msg = f"LIGHT governance docs without headers (recommended):\n"
            for doc in sorted(missing)[:20]:
                msg += f"  - {doc}\n"
            if len(missing) > 20:
                msg += f"  ... and {len(missing) - 20} more\n"
            warnings.warn(msg)

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
        """FULL governance docs must have LAST_VERIFIED."""
        missing = []

        for doc_path in get_full_governance_docs():
            content = doc_path.read_text()
            header = parse_doc_header(content)
            if header and not header.last_verified:
                missing.append(doc_path.name)

        if missing:
            msg = f"\nFULL governance docs missing LAST_VERIFIED:\n"
            for doc in sorted(missing):
                msg += f"  - {doc}\n"
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

        for doc_path in get_full_governance_docs():
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

        for doc_path in get_full_governance_docs():
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

    def test_report_coverage(self):
        """Report how many docs are in each tier."""
        all_docs = get_all_md_files()

        full_count = len(get_governed_docs(GovernanceTier.FULL))
        light_count = len(get_governed_docs(GovernanceTier.LIGHT))
        exempt_count = len([d for d in all_docs if get_governance_tier(d) == GovernanceTier.EXEMPT])

        # This is informational, not a failure
        import warnings
        msg = f"\nGovernance coverage:\n"
        msg += f"  FULL (all laws): {full_count} docs\n"
        msg += f"  LIGHT (header only): {light_count} docs\n"
        msg += f"  EXEMPT: {exempt_count} docs\n"
        msg += f"  TOTAL: {len(all_docs)} docs\n"
        warnings.warn(msg)


# =============================================================================
# Structural Checks
# =============================================================================

class TestDocStructure:
    """Verify doc folder structure."""

    def test_no_ungoverned_docs_in_docs_folder(self):
        """All docs in docs/ should be in a governed subfolder or archive."""
        ungoverned = []
        docs_folder = REPO_ROOT / "docs"

        if not docs_folder.exists():
            return

        for doc_path in docs_folder.rglob("*.md"):
            rel_path = doc_path.relative_to(REPO_ROOT)
            tier = get_governance_tier(doc_path)

            # Check if it's orphaned (not in a known folder)
            rel_str = str(rel_path)
            in_known_folder = any(
                rel_str.startswith(f + "/")
                for f in FULL_GOVERNANCE_FOLDERS + LIGHT_GOVERNANCE_FOLDERS + ["docs/archive"]
            )

            if not in_known_folder and tier != GovernanceTier.EXEMPT:
                ungoverned.append(str(rel_path))

        if ungoverned:
            import warnings
            msg = f"Docs in docs/ not in a governed subfolder:\n"
            for doc in sorted(ungoverned):
                msg += f"  - {doc}\n"
            msg += "Consider moving to docs/core/, docs/archive/, or adding to LIGHT_GOVERNANCE_FOLDERS\n"
            warnings.warn(msg)


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
        gov_path = REPO_ROOT / "docs" / "core" / "DocGovernance.v0.md"
        assert gov_path.exists(), "DocGovernance.v0.md must exist"

    def test_governance_doc_has_valid_header(self):
        """The governance doc must have a valid header."""
        gov_path = REPO_ROOT / "docs" / "core" / "DocGovernance.v0.md"
        if gov_path.exists():
            content = gov_path.read_text()
            header = parse_doc_header(content)
            assert header is not None, "DocGovernance.v0.md needs DOC_STATUS header"
            assert header.doc_type == "REFERENCE", "DocGovernance.v0.md should be REFERENCE"
