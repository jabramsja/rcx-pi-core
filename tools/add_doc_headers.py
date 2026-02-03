#!/usr/bin/env python3
"""
Add DOC_STATUS headers to all governed docs.

This implements the documentation governance solution:
- Every governed doc gets a machine-readable header
- Headers indicate TYPE, LAST_VERIFIED, and where to find current state
- AI agents can parse these to understand doc freshness

Usage:
    python tools/add_doc_headers.py              # Add headers to docs without them
    python tools/add_doc_headers.py --check      # Verify all docs have headers
    python tools/add_doc_headers.py --dry-run    # Show what would be done
"""

import argparse
import re
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent

# All folders under FULL governance (require headers)
FULL_GOVERNANCE_FOLDERS = [
    REPO_ROOT / "docs" / "core",
    REPO_ROOT / "docs" / "agents",
    REPO_ROOT / "docs" / "audit",
    REPO_ROOT / "docs" / "execution",
]

# Doc classification based on content/folder
DOC_TYPES = {
    # docs/core - REFERENCE: Stable definitions
    "MuType.v0.md": "REFERENCE",
    "DebtCategories.v0.md": "REFERENCE",
    "StructuralPurity.v0.md": "REFERENCE",
    "Why_RCX_PI_VM_EXISTS.md": "REFERENCE",
    "EntropyBudget.md": "REFERENCE",
    "DocGovernance.v0.md": "REFERENCE",

    # docs/core - DESIGN_SPEC: Architectural decisions
    "BootstrapPrimitives.v0.md": "DESIGN_SPEC",
    "BootstrapStructuralBridge.v0.md": "DESIGN_SPEC",
    "RCXKernel.v0.md": "DESIGN_SPEC",
    "EVAL_SEED.v0.md": "DESIGN_SPEC",
    "RecursiveKernel.v0.md": "DESIGN_SPEC",

    # docs/core - IMPLEMENTATION: Active development
    "Boot0Architecture.v0.md": "IMPLEMENTATION",
    "SelfHosting.v0.md": "IMPLEMENTATION",
    "MetaCircularKernel.v0.md": "IMPLEMENTATION",
    "EngineNewsStructural.v0.md": "IMPLEMENTATION",
    "OperatorExhaustion.v0.md": "IMPLEMENTATION",
    "UniversalEval.v0.md": "IMPLEMENTATION",

    # docs/agents - REFERENCE
    "AgentGuardrails.v0.md": "REFERENCE",
    "AgentRig.v0.md": "REFERENCE",

    # docs/audit - REFERENCE (audit reports are frozen records)
    "CI_POLICY.md": "REFERENCE",
    "GuardrailsAudit.v0.md": "REFERENCE",
    "MetaCircularReadiness.v1.md": "REFERENCE",

    # docs/execution - REFERENCE (execution specs)
    "ClosureEvidence.v0.md": "REFERENCE",
    "DeepStep.v0.md": "REFERENCE",
    "DeepStep_Guards.md": "REFERENCE",
    "DeepStep_HandTrace.md": "REFERENCE",
    "EnginenewsSpecMapping.v0.md": "REFERENCE",
    "IndependentEncounter.v0.md": "REFERENCE",
    "RuleAsMotif.v0.md": "REFERENCE",
    "StallFixExecution.v0.md": "REFERENCE",
    "StallFixObservability.v0.md": "REFERENCE",
    "TraceReadingPrimer.v0.md": "REFERENCE",
}

HEADER_TEMPLATE = """<!--
DOC_STATUS
TYPE: {doc_type}
LAST_VERIFIED: {date}
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

"""


def has_doc_header(content: str) -> bool:
    """Check if content already has a DOC_STATUS header."""
    header_pattern = re.compile(r'<!--[\s\S]*?DOC_STATUS[\s\S]*?-->', re.MULTILINE)
    match = header_pattern.search(content[:1500])
    return match is not None


def add_header_to_doc(doc_path: Path, dry_run: bool = False) -> bool:
    """Add DOC_STATUS header to a doc file.

    Returns True if header was added, False if already present.
    """
    content = doc_path.read_text()

    if has_doc_header(content):
        return False

    doc_name = doc_path.name
    doc_type = DOC_TYPES.get(doc_name, "REFERENCE")  # Default to REFERENCE
    today = date.today().isoformat()

    header = HEADER_TEMPLATE.format(doc_type=doc_type, date=today)
    new_content = header + content

    if not dry_run:
        doc_path.write_text(new_content)

    return True


def get_all_governed_docs() -> list[Path]:
    """Get all docs in FULL governance folders."""
    docs = []
    for folder in FULL_GOVERNANCE_FOLDERS:
        if folder.exists():
            docs.extend(folder.glob("*.md"))
    return sorted(docs)


def check_all_docs() -> tuple[list[str], list[str]]:
    """Check which docs have/don't have headers.

    Returns (docs_with_headers, docs_without_headers)
    """
    with_headers = []
    without_headers = []

    for doc_path in get_all_governed_docs():
        rel_path = doc_path.relative_to(REPO_ROOT)
        content = doc_path.read_text()
        if has_doc_header(content):
            with_headers.append(str(rel_path))
        else:
            without_headers.append(str(rel_path))

    return with_headers, without_headers


def main():
    parser = argparse.ArgumentParser(description="Add DOC_STATUS headers to docs")
    parser.add_argument("--check", action="store_true", help="Check which docs have headers")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    if args.check:
        with_headers, without_headers = check_all_docs()

        print(f"Docs WITH headers ({len(with_headers)}):")
        for doc in with_headers:
            print(f"  ✓ {doc}")

        print(f"\nDocs WITHOUT headers ({len(without_headers)}):")
        for doc in without_headers:
            print(f"  ✗ {doc}")

        if without_headers:
            print(f"\nRun 'python tools/add_doc_headers.py' to add headers")
            return 1
        else:
            print("\nAll governed docs have headers!")
            return 0

    # Add headers to all governed docs
    added = 0
    skipped = 0

    for doc_path in get_all_governed_docs():
        rel_path = doc_path.relative_to(REPO_ROOT)
        if add_header_to_doc(doc_path, dry_run=args.dry_run):
            action = "Would add" if args.dry_run else "Added"
            print(f"{action} header to {rel_path}")
            added += 1
        else:
            print(f"Skipped {rel_path} (already has header)")
            skipped += 1

    print(f"\nSummary: {added} added, {skipped} skipped")

    if args.dry_run:
        print("(Dry run - no files modified)")


if __name__ == "__main__":
    exit(main() or 0)
