"""
Documentation Freshness Tests - Catches semantic drift that DOC_CONTRACTS misses.

DOC_CONTRACTS verifies that functions/constants/seeds exist with correct values.
This module catches SEMANTIC drift:
- Outdated status claims (e.g., "in progress" for completed work)
- Outdated file paths (e.g., deleted directories)
- References to archived components
- Outdated terminology (e.g., old phase names)
- Stale "Current State" sections that should reference STATUS.md

These are CONTENT checks, not STRUCTURAL checks.

Usage:
    PYTHONHASHSEED=0 pytest tests/docs/test_doc_freshness.py -v
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
DOCS_CORE = REPO_ROOT / "docs" / "core"


# =============================================================================
# Forbidden Patterns - Things that should NOT appear in docs
# =============================================================================

class ForbiddenPattern(NamedTuple):
    """A pattern that should not appear in documentation."""
    pattern: str  # Regex pattern
    description: str  # Human-readable description
    suggestion: str  # What to do instead
    exceptions: list[str] = []  # Files where this is allowed


FORBIDDEN_PATTERNS = [
    # =========================================================================
    # Outdated paths - directories/files that no longer exist
    # =========================================================================
    ForbiddenPattern(
        r'rcx_pi/seeds/',
        "Seeds moved from rcx_pi/seeds/ to mu/",
        "Use mu/substrate/, mu/closures/, mu/utilities/, etc.",
    ),
    ForbiddenPattern(
        r'bytecode_vm\.py',
        "BytecodeVM was archived",
        "Remove reference or mark as historical context",
    ),
    ForbiddenPattern(
        r'BytecodeVM',
        "BytecodeVM was archived",
        "Remove reference or mark as historical context",
        exceptions=["MuType.v0.md"],  # Allow historical reference if marked
    ),
    ForbiddenPattern(
        r'docs/BytecodeExecution',
        "BytecodeExecution docs were archived",
        "Remove reference or update to current architecture",
    ),
    ForbiddenPattern(
        r'substrates/js/',
        "JavaScript substrate moved to mu/host/js/",
        "Use mu/host/js/eval_step.js",
    ),
    ForbiddenPattern(
        r'trace_canon\.py',
        "trace_canon.py was removed/consolidated",
        "Use mu_type.py for hashing functions",
    ),

    # =========================================================================
    # Outdated terminology - old phase/level names
    # =========================================================================
    ForbiddenPattern(
        r'Phase [23] (?:is |in progress|deliverables)',
        "Phase 2/3 terminology is outdated (now L1/L2/L3)",
        "Use L1 (Algorithmic), L2 (Operational), L3 (Substrate Portability)",
        exceptions=["EVAL_SEED.v0.md"],  # Historical spec context
    ),
    ForbiddenPattern(
        r'EVAL_SEED Phase [234]',
        "EVAL_SEED Phase terminology replaced by L1/L2/L3/L4",
        "Use L1 (match/subst), L2 (kernel), L3 (parity), L4 (meta-circular)",
    ),

    # =========================================================================
    # Stale status indicators - things that suggest incomplete work
    # =========================================================================
    ForbiddenPattern(
        r'In Progress:.*\n.*deep_step',
        "deep_step blocker was resolved",
        "Update to reflect current status (L2 complete)",
    ),
    ForbiddenPattern(
        r'Key blocker:.*deep_step',
        "deep_step blocker was resolved",
        "Remove or mark as resolved",
    ),
    ForbiddenPattern(
        r'Awaiting:.*Phase 4',
        "Phase 4 terminology outdated",
        "Update to L4 (True Self-Hosting) in SINK status",
    ),

    # =========================================================================
    # Duplicate status - sections that should defer to STATUS.md
    # =========================================================================
    ForbiddenPattern(
        r'Updated \d{4}-\d{2}-\d{2}\).*\n\n\*\*Completed:\*\*',
        "Inline status sections drift from STATUS.md",
        "Reference STATUS.md instead: 'See STATUS.md for current state'",
    ),
]


# =============================================================================
# Required Patterns - Things that SHOULD appear in certain docs
# =============================================================================

class RequiredPattern(NamedTuple):
    """A pattern that should appear in specific docs."""
    doc_name: str
    pattern: str
    description: str


REQUIRED_PATTERNS = [
    # Docs that discuss bootstrap primitives should reference the canonical source
    RequiredPattern(
        "RecursiveKernel.v0.md",
        r'BootstrapPrimitives\.v0\.md',
        "Should reference BootstrapPrimitives.v0.md for canonical primitive list",
    ),
    RequiredPattern(
        "RCXKernel.v0.md",
        r'BootstrapPrimitives\.v0\.md',
        "Should reference BootstrapPrimitives.v0.md for canonical primitive list",
    ),
    # Docs with "Current State" sections should reference STATUS.md
    RequiredPattern(
        "Why_RCX_PI_VM_EXISTS.md",
        r'STATUS\.md',
        "Current state section should reference STATUS.md",
    ),
]


# =============================================================================
# Path Existence Checks - Paths mentioned in docs should exist
# =============================================================================

PATH_PATTERNS = [
    # Regex to find file path references (e.g., rcx_pi/selfhost/foo.py)
    (r'`(rcx_pi/[a-zA-Z_/]+\.py)`', "Python file"),
    (r'`(mu/[a-zA-Z_/]+\.json)`', "Mu seed file"),
    (r'`(mu/[a-zA-Z_/]+\.js)`', "JavaScript file"),
    (r'`(tests/[a-zA-Z_/]+\.py)`', "Test file"),
    (r'`(tools/[a-zA-Z_/]+\.sh)`', "Tool script"),
    (r'`(tools/[a-zA-Z_/]+\.py)`', "Tool script"),
]


# =============================================================================
# Test Classes
# =============================================================================

class TestForbiddenPatterns:
    """Detect outdated content that should be removed or updated."""

    @pytest.mark.parametrize(
        "forbidden",
        FORBIDDEN_PATTERNS,
        ids=lambda f: f.description[:40],
    )
    def test_no_forbidden_patterns(self, forbidden: ForbiddenPattern):
        """Docs should not contain forbidden patterns."""
        violations = []
        pattern = re.compile(forbidden.pattern, re.IGNORECASE)

        for doc_path in sorted(DOCS_CORE.glob("*.md")):
            if doc_path.name in forbidden.exceptions:
                continue

            content = doc_path.read_text()
            # Remove code blocks before checking (they might contain examples)
            content_no_code = re.sub(r'```[\s\S]*?```', '', content)
            matches = pattern.findall(content_no_code)
            if matches:
                violations.append((doc_path.name, matches[:2]))

        if violations:
            msg = f"\nForbidden pattern: {forbidden.description}\n"
            msg += f"Suggestion: {forbidden.suggestion}\n"
            msg += "Violations:\n"
            for doc, matches in violations:
                msg += f"  - {doc}: {matches}\n"
            pytest.fail(msg)


class TestRequiredPatterns:
    """Verify docs contain required references."""

    @pytest.mark.parametrize(
        "required",
        REQUIRED_PATTERNS,
        ids=lambda r: f"{r.doc_name}:{r.description[:30]}",
    )
    def test_required_patterns(self, required: RequiredPattern):
        """Specific docs should contain required patterns."""
        doc_path = DOCS_CORE / required.doc_name
        if not doc_path.exists():
            # Skip if doc doesn't exist (covered by other tests)
            pytest.skip(f"Doc {required.doc_name} not found")

        content = doc_path.read_text()
        pattern = re.compile(required.pattern)

        if not pattern.search(content):
            pytest.fail(
                f"{required.doc_name}: {required.description}\n"
                f"Expected pattern: {required.pattern}"
            )


class TestPathReferences:
    """Verify file paths mentioned in docs actually exist."""

    def test_referenced_paths_exist(self):
        """File paths mentioned in docs should exist."""
        violations = []

        for doc_path in sorted(DOCS_CORE.glob("*.md")):
            content = doc_path.read_text()

            for pattern_str, path_type in PATH_PATTERNS:
                pattern = re.compile(pattern_str)
                for match in pattern.finditer(content):
                    file_path = match.group(1)
                    full_path = REPO_ROOT / file_path

                    # Skip if it looks like an example/template
                    if "example" in file_path.lower() or "{" in file_path:
                        continue

                    if not full_path.exists():
                        violations.append((doc_path.name, file_path, path_type))

        if violations:
            # Group by doc for cleaner output
            by_doc = {}
            for doc, path, ptype in violations:
                by_doc.setdefault(doc, []).append(f"{path} ({ptype})")

            msg = "\nDocs reference non-existent files:\n"
            for doc, paths in by_doc.items():
                msg += f"  {doc}:\n"
                for p in paths[:5]:  # Limit to 5 per doc
                    msg += f"    - {p}\n"
                if len(paths) > 5:
                    msg += f"    ... and {len(paths) - 5} more\n"

            pytest.fail(msg)


class TestStatusConsistency:
    """Verify status claims in docs match STATUS.md."""

    def test_l_level_claims_match_status(self):
        """L1/L2/L3 claims in docs should match STATUS.md."""
        status_path = REPO_ROOT / "STATUS.md"
        status_content = status_path.read_text()

        # Extract current L-level status from STATUS.md
        l1_complete = "L1" in status_content and "COMPLETE" in status_content
        l2_complete = "L2" in status_content and "COMPLETE" in status_content
        l3_complete = "L3" in status_content and "COMPLETE" in status_content

        # Check docs don't claim incomplete status for completed levels
        violations = []
        for doc_path in sorted(DOCS_CORE.glob("*.md")):
            content = doc_path.read_text()

            # Look for claims that contradict STATUS.md
            if l1_complete and re.search(r'L1[:\s]+(?:IN PROGRESS|TODO|PENDING)', content, re.I):
                violations.append((doc_path.name, "Claims L1 incomplete but STATUS.md says COMPLETE"))
            if l2_complete and re.search(r'L2[:\s]+(?:IN PROGRESS|TODO|PENDING)', content, re.I):
                violations.append((doc_path.name, "Claims L2 incomplete but STATUS.md says COMPLETE"))
            if l3_complete and re.search(r'L3[:\s]+(?:IN PROGRESS|TODO|PENDING)', content, re.I):
                violations.append((doc_path.name, "Claims L3 incomplete but STATUS.md says COMPLETE"))

        if violations:
            msg = "\nDocs contradict STATUS.md:\n"
            for doc, issue in violations:
                msg += f"  - {doc}: {issue}\n"
            pytest.fail(msg)


class TestNoHardcodedCounts:
    """Warn about hardcoded counts that should reference code/tests."""

    def test_warn_hardcoded_projection_counts(self):
        """Warn about hardcoded projection counts (prefer test references).

        Convention:
        - Estimates use "~": "~6 projections" (acceptable)
        - Claims reference tests: "see test_seed_counts.py for count"
        - Historical context (changelog, revision history) is exempt
        """
        # This is a warning, not a failure - some counts are fine
        warnings = []

        # Pattern: "N projections" where N is a number (not preceded by ~)
        # This catches "7 projections" but not "~7 projections"
        count_pattern = re.compile(r'(?<!~)\b(\d+)\s+projections?\b', re.I)

        for doc_path in sorted(DOCS_CORE.glob("*.md")):
            content = doc_path.read_text()

            # Remove changelog/history sections (these are historical context)
            content_no_history = re.sub(
                r'(?:^|\n)##\s*(?:Changelog|Revision History|History).*?(?=\n##|\Z)',
                '', content, flags=re.DOTALL | re.IGNORECASE
            )

            matches = count_pattern.findall(content_no_history)

            # Filter out counts that are verified by grounding tests
            # These are the actual seed projection counts
            verified_counts = {"5", "6", "7", "8", "9", "11", "12"}
            suspicious = [m for m in matches if m not in verified_counts]

            if suspicious:
                warnings.append((doc_path.name, suspicious))

        if warnings:
            import warnings as warn_module
            msg = "Docs with potentially hardcoded projection counts:\n"
            for doc, counts in warnings:
                msg += f"  {doc}: {counts}\n"
            msg += "\nConvention for projection counts:\n"
            msg += "  - Estimates: use '~' prefix (e.g., '~6 projections')\n"
            msg += "  - Claims: reference tests (e.g., 'see test_seed_counts.py')\n"
            warn_module.warn(msg)


# =============================================================================
# Utility: Scan for drift
# =============================================================================

def scan_for_drift() -> dict:
    """
    Scan all docs and return a drift report.

    This can be called from tools/check_docs_consistency.sh or as a standalone script.
    Returns a dict with:
    - forbidden_violations: list of (doc, pattern, matches)
    - missing_required: list of (doc, pattern)
    - missing_paths: list of (doc, path)
    """
    report = {
        "forbidden_violations": [],
        "missing_required": [],
        "missing_paths": [],
    }

    for doc_path in sorted(DOCS_CORE.glob("*.md")):
        content = doc_path.read_text()

        # Check forbidden patterns
        for forbidden in FORBIDDEN_PATTERNS:
            if doc_path.name in forbidden.exceptions:
                continue
            pattern = re.compile(forbidden.pattern, re.IGNORECASE)
            matches = pattern.findall(content)
            if matches:
                report["forbidden_violations"].append(
                    (doc_path.name, forbidden.description, matches[:2])
                )

        # Check required patterns
        for required in REQUIRED_PATTERNS:
            if doc_path.name != required.doc_name:
                continue
            pattern = re.compile(required.pattern)
            if not pattern.search(content):
                report["missing_required"].append(
                    (doc_path.name, required.description)
                )

        # Check path references
        for pattern_str, path_type in PATH_PATTERNS:
            pattern = re.compile(pattern_str)
            for match in pattern.finditer(content):
                file_path = match.group(1)
                full_path = REPO_ROOT / file_path
                if "example" not in file_path.lower() and "{" not in file_path:
                    if not full_path.exists():
                        report["missing_paths"].append(
                            (doc_path.name, file_path)
                        )

    return report


if __name__ == "__main__":
    """Run as standalone drift scanner."""
    report = scan_for_drift()

    print("=== Documentation Drift Report ===\n")

    if report["forbidden_violations"]:
        print("FORBIDDEN PATTERNS FOUND:")
        for doc, desc, matches in report["forbidden_violations"]:
            print(f"  {doc}: {desc}")
            print(f"    Matches: {matches}")
        print()

    if report["missing_required"]:
        print("MISSING REQUIRED PATTERNS:")
        for doc, desc in report["missing_required"]:
            print(f"  {doc}: {desc}")
        print()

    if report["missing_paths"]:
        print("MISSING FILE REFERENCES:")
        for doc, path in report["missing_paths"]:
            print(f"  {doc}: {path}")
        print()

    if not any(report.values()):
        print("No drift detected!")
