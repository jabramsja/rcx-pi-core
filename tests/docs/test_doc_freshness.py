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
from pathlib import Path
from typing import NamedTuple

import pytest

from tools.shared_doc_config import REPO_ROOT, get_governed_folders_as_paths

# All governed folders - single source of truth: tools/shared_doc_config.py
GOVERNED_FOLDERS = get_governed_folders_as_paths()


def iter_governed_docs():
    """Iterate over all markdown files in governed folders."""
    for folder in GOVERNED_FOLDERS:
        if folder.exists():
            for doc_path in sorted(folder.glob("*.md")):
                yield doc_path


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
        r'`seeds/[a-z_]+\.v\d+\.json`',
        "Root seeds/ directory deleted - seeds moved to mu/",
        "Use mu/substrate/, mu/closures/, mu/utilities/, mu/bridge/, mu/programs/",
    ),
    ForbiddenPattern(
        r'(?<![/a-z])seeds/(?:kernel|match|subst|classify|eval|recurrence|exhaustion)',
        "Root seeds/ directory deleted - seeds moved to mu/",
        "Use mu/substrate/, mu/closures/, mu/utilities/, etc.",
    ),
    # Script paths must include directory
    ForbiddenPattern(
        r'(?<![/a-z])`(?:green_gate|audit_fast|audit_all|contraband|seed_police)\.sh`',
        "Script references must include directory path",
        "Use scripts/green_gate.sh, tools/audit_fast.sh, etc.",
    ),
    # Doc paths must include full path from docs/
    ForbiddenPattern(
        r'`docs/(?:Stall|Rule|Engine|Bootstrap|Operator)[A-Za-z]+\.v\d+\.md`',
        "Doc paths must include subdirectory (core/, execution/, etc.)",
        "Use docs/execution/StallFixExecution.v0.md, docs/core/RuleAsMotif.v0.md, etc.",
    ),
    # Note: bytecode_vm.py still exists but is legacy code
    # References are OK in historical context (audit docs, archive docs)
    ForbiddenPattern(
        r'BytecodeVM',
        "BytecodeVM is legacy (prefer projection-based execution)",
        "Use kernel/seed-based approach unless documenting historical context",
        exceptions=["MuType.v0.md", "MetaCircularReadiness.v1.md"],  # Historical context OK
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
        r'JS substrate does not load bridge',
        "Outdated bridge claim: JS now loads bootstrap_structural.v1.json",
        "Update to reflect current behavior in mu/host/js/eval_step.js",
    ),
    ForbiddenPattern(
        r'(?<![/a-z])normalized_prototype/',
        "normalized_prototype/ archived to archive/normalized_prototype/ (Round 22E)",
        "Use archive/normalized_prototype/ or remove reference",
    ),
    ForbiddenPattern(
        r'(?<![/a-z])corpus/Universalrecursion',
        "corpus/ archived to archive/corpus/ (Round 22F)",
        "Use archive/corpus/ or remove reference",
    ),
    ForbiddenPattern(
        r'(?<![/a-z])rcx_python_examples/',
        "rcx_python_examples/ archived to archive/rcx_python_examples/ (Round 22G)",
        "Use archive/rcx_python_examples/ or remove reference",
    ),
    # Note: trace_canon.py still exists and is actively used for trace canonicalization
    # No forbidden pattern needed - it's a valid reference

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
    ForbiddenPattern(
        r'Algorithm execution uses Python match/substitute for practical reasons',
        "Outdated Gate 4 runtime claim: production algorithm execution is structural-default",
        "Update wording to structural-default runtime and explicit bootstrap fallback only",
    ),

    # =========================================================================
    # Law 3 Violations - Inline status claims that should be in STATUS.md/TASKS.md
    # =========================================================================
    ForbiddenPattern(
        r'\*\*Status:\s*(?:APPROVED|IN PROGRESS|PENDING|BLOCKED|TODO)',
        "Inline status claims violate Law 3 (docs describe WHAT, not progress)",
        "Remove status line; reference STATUS.md for current state",
    ),
    ForbiddenPattern(
        r'Status:\s*(?:APPROVED|IN PROGRESS|PENDING|BLOCKED|TODO)',
        "Inline status claims violate Law 3 (docs describe WHAT, not progress)",
        "Remove status line; reference STATUS.md for current state",
    ),
    ForbiddenPattern(
        r'VECTOR #\d+',
        "VECTOR references drift (VECTORs move to Ra when completed)",
        "Remove VECTOR reference; work status belongs in TASKS.md only",
    ),
    ForbiddenPattern(
        r'promotion path for (?:VECTOR|NEXT|SINK)',
        "Promotion path references drift when work completes",
        "Remove promotion reference; work status belongs in TASKS.md only",
    ),

    # =========================================================================
    # Duplicate status - sections that should defer to STATUS.md
    # =========================================================================
    ForbiddenPattern(
        r'Updated \d{4}-\d{2}-\d{2}\).*\n\n\*\*Completed:\*\*',
        "Inline status sections drift from STATUS.md",
        "Reference STATUS.md instead: 'See STATUS.md for current state'",
    ),

    # =========================================================================
    # Hardcoded counts that drift - test counts, debt counts, etc.
    # =========================================================================
    ForbiddenPattern(
        r'\b[1-9]\d{2,3}\+?\s+tests\b',
        "Hardcoded test counts drift (e.g., '800+ tests', '1000+ tests')",
        "Reference STATUS.md for test counts, or use 'comprehensive test coverage'",
        exceptions=["DocGovernance.v0.md"],  # Meta-doc about governance can discuss counts
    ),
    ForbiddenPattern(
        r'L[1-4]:\s*(?:DESIGN|FUTURE|BLOCKED|PENDING)',
        "L-level status claims drift from STATUS.md",
        "Use ACHIEVED/DONE for completed levels, or reference STATUS.md directly",
        exceptions=["DocGovernance.v0.md"],  # Governance doc can discuss the concept
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

        for doc_path in iter_governed_docs():
            if doc_path.name in forbidden.exceptions:
                continue

            content = doc_path.read_text()
            # Remove code blocks before checking (they might contain examples)
            content_no_code = re.sub(r'```[\s\S]*?```', '', content)
            matches = pattern.findall(content_no_code)
            if matches:
                # Include relative path for clarity across folders
                rel_path = doc_path.relative_to(REPO_ROOT)
                violations.append((str(rel_path), matches[:2]))

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
        # Search all governed folders for the doc
        doc_path = None
        for folder in GOVERNED_FOLDERS:
            candidate = folder / required.doc_name
            if candidate.exists():
                doc_path = candidate
                break

        if doc_path is None:
            # Skip if doc doesn't exist (covered by other tests)
            pytest.skip(f"Doc {required.doc_name} not found in governed folders")

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

        for doc_path in iter_governed_docs():
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
                        rel_path = doc_path.relative_to(REPO_ROOT)
                        violations.append((str(rel_path), file_path, path_type))

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
        for doc_path in iter_governed_docs():
            content = doc_path.read_text()
            rel_path = doc_path.relative_to(REPO_ROOT)

            # Look for claims that contradict STATUS.md
            if l1_complete and re.search(r'L1[:\s]+(?:IN PROGRESS|TODO|PENDING)', content, re.I):
                violations.append((str(rel_path), "Claims L1 incomplete but STATUS.md says COMPLETE"))
            if l2_complete and re.search(r'L2[:\s]+(?:IN PROGRESS|TODO|PENDING)', content, re.I):
                violations.append((str(rel_path), "Claims L2 incomplete but STATUS.md says COMPLETE"))
            if l3_complete and re.search(r'L3[:\s]+(?:IN PROGRESS|TODO|PENDING)', content, re.I):
                violations.append((str(rel_path), "Claims L3 incomplete but STATUS.md says COMPLETE"))

        if violations:
            msg = "\nDocs contradict STATUS.md:\n"
            for doc, issue in violations:
                msg += f"  - {doc}: {issue}\n"
            pytest.fail(msg)


class TestNoHardcodedCounts:
    """FAIL on hardcoded counts that should reference code/tests."""

    def test_no_hardcoded_projection_counts(self):
        """FAIL on hardcoded projection counts (prefer test references).

        Convention:
        - Estimates use "~": "~6 projections" (acceptable)
        - Claims reference tests: "see test_seed_counts.py for count"
        - Historical context (changelog, revision history) is exempt
        - Acceptable patterns: "originally N", "target N", "N edits", "with N projection" (trace descriptions)

        This is a FAILURE, not a warning. Hardcoded counts drift and cause confusion.
        """
        violations = []

        # Pattern: "N projections" where N is a number (not preceded by ~)
        # This catches "7 projections" but not "~7 projections"
        count_pattern = re.compile(r'(?<!~)\b(\d+)\s+projections?\b', re.I)

        # Patterns that indicate acceptable context (not actual seed count claims)
        acceptable_context_patterns = [
            r'originally\s+\d+\s+projections?',      # Historical: "originally 2 projections"
            r'target\s+\d+[-–]\d+\s+projections?',   # Target range: "target 10-15 projections"
            r'target\s+\d+\s+projections?',          # Target: "target 6 projections"
            r'\d+\s+projection\s+edits?',            # Effort: "3 projection edits"
            r'with\s+\d+\s+projection',              # Trace description: "Trace with 1 projection"
            r'down\s+from\s+\d+',                    # Comparison: "down from 10"
            r'not\s+\d+',                            # Negation: "not 37"
        ]

        for doc_path in iter_governed_docs():
            content = doc_path.read_text()

            # Remove changelog/history sections (these are historical context)
            content_no_history = re.sub(
                r'(?:^|\n)##\s*(?:Changelog|Revision History|History).*?(?=\n##|\Z)',
                '', content, flags=re.DOTALL | re.IGNORECASE
            )

            # Remove lines matching acceptable context patterns
            content_filtered = content_no_history
            for pattern in acceptable_context_patterns:
                content_filtered = re.sub(pattern, '', content_filtered, flags=re.I)

            matches = count_pattern.findall(content_filtered)

            # Filter out counts that are verified by grounding tests
            # These are the actual seed projection counts (from test_seed_counts.py)
            verified_counts = {"5", "6", "7", "8", "9", "11", "12"}
            suspicious = [m for m in matches if m not in verified_counts]

            if suspicious:
                rel_path = doc_path.relative_to(REPO_ROOT)
                violations.append((str(rel_path), suspicious))

        if violations:
            msg = "\nDocs with hardcoded projection counts (MUST be fixed):\n"
            for doc, counts in violations:
                msg += f"  {doc}: {counts}\n"
            msg += "\nHow to fix:\n"
            msg += "  - Use '~' prefix for estimates: '~6 projections'\n"
            msg += "  - Reference tests for actual counts: 'see test_seed_counts.py'\n"
            msg += "  - Historical context is OK: 'originally N projections'\n"
            msg += "  - Verified counts (from test_seed_counts.py): {5, 6, 7, 8, 9, 11, 12}\n"
            pytest.fail(msg)


# =============================================================================
# Utility: Scan for drift
# =============================================================================

def scan_for_drift() -> dict:
    """
    Scan all governed docs and return a drift report.

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

    for doc_path in iter_governed_docs():
        content = doc_path.read_text()
        rel_path = str(doc_path.relative_to(REPO_ROOT))

        # Check forbidden patterns
        for forbidden in FORBIDDEN_PATTERNS:
            if doc_path.name in forbidden.exceptions:
                continue
            pattern = re.compile(forbidden.pattern, re.IGNORECASE)
            matches = pattern.findall(content)
            if matches:
                report["forbidden_violations"].append(
                    (rel_path, forbidden.description, matches[:2])
                )

        # Check required patterns
        for required in REQUIRED_PATTERNS:
            if doc_path.name != required.doc_name:
                continue
            pattern = re.compile(required.pattern)
            if not pattern.search(content):
                report["missing_required"].append(
                    (rel_path, required.description)
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
                            (rel_path, file_path)
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
