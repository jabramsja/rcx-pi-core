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

from tools.docs.shared_doc_config import REPO_ROOT, get_governed_folders_as_paths

# All folders under governance (require headers)
# Single source of truth: tools/shared_doc_config.py
GOVERNED_FOLDERS = get_governed_folders_as_paths()

# Specific standalone files that need headers
GOVERNED_FILES = [
    REPO_ROOT / "mu" / "docs" / "README.md",
    REPO_ROOT / "rcx_pi" / "README.md",
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
    "TraceReadingPrimer.v0.md": "REFERENCE",

    # docs/cli - REFERENCE (CLI documentation)
    "cli_quickstart.md": "REFERENCE",
    "cli_schema.md": "REFERENCE",
    "Flags.md": "REFERENCE",
    "orbit_viz_dot.md": "REFERENCE",
    "orbit_viz_svg.md": "REFERENCE",

    # docs/schemas - REFERENCE (schema documentation)
    "program_descriptor_schema.md": "REFERENCE",
    "program_run_schema.md": "REFERENCE",
    "snapshot_json_schema.md": "REFERENCE",
    "world_trace_json_schema.md": "REFERENCE",

    # tools/agents - REFERENCE (agent prompt configurations)
    "adversary_prompt.md": "REFERENCE",
    "advisor_prompt.md": "REFERENCE",
    "expert_prompt.md": "REFERENCE",
    "fuzzer_prompt.md": "REFERENCE",
    "grounding_prompt.md": "REFERENCE",
    "structural_proof_prompt.md": "REFERENCE",
    "translator_prompt.md": "REFERENCE",
    "verifier_prompt.md": "REFERENCE",
    "visualizer_prompt.md": "REFERENCE",

    # README files
    "README.md": "REFERENCE",
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
    """Check if content already has a DOC_STATUS header.

    Uses the same strict pattern as test_doc_governance.py:parse_doc_header()
    to ensure consistency between detection and validation.
    """
    # Strict pattern: <!-- followed by whitespace+newline, DOC_STATUS on its own line
    # Must match test_doc_governance.py:108 pattern
    header_pattern = re.compile(r'<!--\s*\nDOC_STATUS\n.*?\n-->', re.DOTALL)
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
    """Get all docs under governance."""
    docs = []
    for folder in GOVERNED_FOLDERS:
        if folder.exists():
            docs.extend(folder.glob("*.md"))
    # Add standalone governed files
    for f in GOVERNED_FILES:
        if f.exists():
            docs.append(f)
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
