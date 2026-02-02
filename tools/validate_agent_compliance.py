#!/usr/bin/env python3
"""
Agent Output Compliance Validator

Validates that agent outputs follow AgentGuardrails.v0.md requirements.
Run on agent output text to check for required evidence format.

Usage:
    python tools/validate_agent_compliance.py < agent_output.txt
    python tools/validate_agent_compliance.py --file agent_output.txt

Created: 2026-02-01 (9-agent review recommendation)
Updated: 2026-02-01 (9-agent self-review fixes: line endings, tabs, hallucination words)
Updated: 2026-02-02 (Critical fixes: structured blocks, file verification, empty lines)
Updated: 2026-02-02 (Fix: CODE regex in extract_finding_blocks now matches global pattern)
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import NamedTuple


def normalize_line_endings(text: str) -> str:
    """Normalize line endings to Unix-style (LF).

    Fixes: Windows CRLF and old Mac CR would break line-based regex patterns.
    """
    return text.replace('\r\n', '\n').replace('\r', '\n')


def count_pattern(text: str, pattern: str) -> int:
    """Count regex pattern matches in text."""
    return len(re.findall(pattern, text, re.MULTILINE | re.IGNORECASE))


# Expanded hallucination word list (9-agent self-review finding)
# Original: probably, likely, seems, assume, maybe, might, presumably
# Added: appears, possibly, could, perhaps, believe, suspect, think, suggests
HALLUCINATION_WORDS = (
    r'\b('
    r'probably|likely|seems|assume|maybe|might|presumably|'
    r'appears|possibly|could|perhaps|believe|suspect|suggests'
    r')\b'
)


class FindingBlock(NamedTuple):
    """Structured representation of a FINDING block."""
    finding: str
    file_path: str | None
    lines: str | None
    code: str | None
    verified: str | None


def extract_finding_blocks(text: str) -> list[FindingBlock]:
    """
    Extract structured FINDING blocks from agent output.

    A valid block has FINDING followed by FILE, LINES, CODE, VERIFIED
    in sequence (with possible intervening text).

    Returns list of FindingBlock tuples with extracted components.
    """
    blocks = []

    # Split on FINDING: to get each block
    parts = re.split(r'^FINDING:\s*', text, flags=re.MULTILINE)

    for part in parts[1:]:  # Skip first empty part
        # Extract finding description (first line)
        finding_match = re.match(r'([^\n]+)', part)
        finding = finding_match.group(1).strip() if finding_match else ""

        # Extract FILE: path
        file_match = re.search(r'^FILE:\s*(/[^\n]+)', part, re.MULTILINE)
        file_path = file_match.group(1).strip() if file_match else None

        # Extract LINES: or LINE:
        lines_match = re.search(r'^LINES?:\s*(\d+(?:-\d+)?)', part, re.MULTILINE)
        lines = lines_match.group(1) if lines_match else None

        # Extract CODE: block (first line must be indented, subsequent can be empty)
        # Pattern matches global count pattern at line 155 for consistency
        code_match = re.search(
            r'^CODE:\n((?:\t|[ ]{2,})[^\n]+(?:\n(?:(?:\t|[ ]{2,})[^\n]*|[ \t]*))*)',
            part, re.MULTILINE
        )
        code = code_match.group(1) if code_match else None

        # Extract VERIFIED:
        verified_match = re.search(r'^VERIFIED:\s*(Yes|No)', part, re.MULTILINE | re.IGNORECASE)
        verified = verified_match.group(1) if verified_match else None

        blocks.append(FindingBlock(
            finding=finding,
            file_path=file_path,
            lines=lines,
            code=code,
            verified=verified
        ))

    return blocks


def verify_file_paths(blocks: list[FindingBlock], check_exists: bool = True) -> list[str]:
    """
    Verify that FILE paths in finding blocks are valid.

    Returns list of invalid/missing file paths.
    """
    invalid_paths = []

    for block in blocks:
        if block.file_path:
            # Check path format (must be absolute)
            if not block.file_path.startswith('/'):
                invalid_paths.append(f"{block.file_path} (not absolute path)")
                continue

            # Check file exists (optional, for CI environments)
            if check_exists and not os.path.exists(block.file_path):
                invalid_paths.append(f"{block.file_path} (file not found)")

    return invalid_paths


def check_compliance(output: str, verify_files: bool = False) -> dict:
    """
    Check agent output for guardrail compliance.

    Args:
        output: Agent output text to validate
        verify_files: If True, check that cited FILE paths actually exist

    Returns dict with metrics and compliance status.
    """
    # Normalize line endings (fixes Windows CRLF, old Mac CR)
    output = normalize_line_endings(output)

    # === STRUCTURED BLOCK PARSING (Critical fix: associate FINDING with FILE) ===
    finding_blocks = extract_finding_blocks(output)

    # Count from structured blocks
    findings = len(finding_blocks)
    blocks_with_file = sum(1 for b in finding_blocks if b.file_path)
    blocks_with_lines = sum(1 for b in finding_blocks if b.lines)
    blocks_with_code = sum(1 for b in finding_blocks if b.code)
    blocks_with_verified_yes = sum(1 for b in finding_blocks if b.verified and b.verified.lower() == 'yes')
    blocks_with_verified_no = sum(1 for b in finding_blocks if b.verified and b.verified.lower() == 'no')

    # Also count global patterns for backwards compatibility
    file_citations = count_pattern(output, r'^FILE:\s*/[^\n]+')
    line_citations = count_pattern(output, r'^LINES?:\s*\d+')
    # CODE block: first line must be indented, subsequent lines can be empty or indented
    # Pattern: CODE:\n followed by indented line, then any number of (empty or indented) lines
    code_blocks = count_pattern(output, r'^CODE:\n(?:\t|[ ]{2,})[^\n]+(?:\n(?:(?:\t|[ ]{2,})[^\n]*|[ \t]*))*')
    verified_yes = count_pattern(output, r'^VERIFIED:\s*Yes')
    verified_no = count_pattern(output, r'^VERIFIED:\s*No')

    # Check for STATUS.md mention in first ~50 lines
    first_section = '\n'.join(output.split('\n')[:50])
    status_md_early = 'STATUS.md' in first_section

    # Count hallucination words
    hallucination_words = count_pattern(output, HALLUCINATION_WORDS)

    # Determine compliance
    violations = []

    # === CRITICAL: Check each finding block has required components ===
    incomplete_blocks = []
    for i, block in enumerate(finding_blocks):
        missing = []
        if not block.file_path:
            missing.append("FILE")
        if not block.lines:
            missing.append("LINES")
        if not block.code:
            missing.append("CODE")
        if not block.verified:
            missing.append("VERIFIED")
        elif block.verified.lower() == 'no':
            missing.append("VERIFIED=No (should be Yes)")

        if missing:
            incomplete_blocks.append(f"Finding '{block.finding[:30]}...' missing: {', '.join(missing)}")

    if incomplete_blocks:
        violations.append(f"{len(incomplete_blocks)} incomplete finding blocks")
        # Add details for first 3 incomplete blocks
        for detail in incomplete_blocks[:3]:
            violations.append(f"  - {detail}")

    # === CRITICAL: Verify file paths exist (optional, enabled via flag) ===
    if verify_files and finding_blocks:
        invalid_paths = verify_file_paths(finding_blocks, check_exists=True)
        if invalid_paths:
            violations.append(f"{len(invalid_paths)} invalid/missing file paths")
            for path in invalid_paths[:3]:
                violations.append(f"  - {path}")

    # Legacy count-based checks (kept for backwards compatibility)
    if verified_no > 0:
        violations.append(f"Contains {verified_no} VERIFIED: No entries (should be 0)")

    if not status_md_early and findings > 0:
        violations.append("STATUS.md not mentioned in first 50 lines")

    if hallucination_words > 3:
        violations.append(f"High hallucination word count: {hallucination_words}")

    return {
        "findings": findings,
        "file_citations": file_citations,
        "line_citations": line_citations,
        "code_blocks": code_blocks,
        "verified_yes": verified_yes,
        "verified_no": verified_no,
        "status_md_early": status_md_early,
        "hallucination_words": hallucination_words,
        "violations": violations,
        "compliant": len(violations) == 0,
        # New structured metrics
        "blocks_with_file": blocks_with_file,
        "blocks_with_lines": blocks_with_lines,
        "blocks_with_code": blocks_with_code,
        "blocks_with_verified_yes": blocks_with_verified_yes,
        "incomplete_blocks": len(incomplete_blocks),
    }


def format_report(metrics: dict) -> str:
    """Format compliance check results as readable report."""
    lines = [
        "=" * 50,
        "AGENT COMPLIANCE REPORT",
        "=" * 50,
        "",
        "METRICS:",
        f"  Findings:            {metrics['findings']}",
        f"  File citations:      {metrics['file_citations']}",
        f"  Line citations:      {metrics['line_citations']}",
        f"  Code blocks:         {metrics['code_blocks']}",
        f"  VERIFIED: Yes:       {metrics['verified_yes']}",
        f"  VERIFIED: No:        {metrics['verified_no']}",
        f"  STATUS.md early:     {metrics['status_md_early']}",
        f"  Hallucination words: {metrics['hallucination_words']}",
        "",
        "STRUCTURED BLOCK ANALYSIS:",
        f"  Blocks with FILE:    {metrics.get('blocks_with_file', 'N/A')}",
        f"  Blocks with LINES:   {metrics.get('blocks_with_lines', 'N/A')}",
        f"  Blocks with CODE:    {metrics.get('blocks_with_code', 'N/A')}",
        f"  Blocks verified:     {metrics.get('blocks_with_verified_yes', 'N/A')}",
        f"  Incomplete blocks:   {metrics.get('incomplete_blocks', 'N/A')}",
        "",
    ]

    if metrics['compliant']:
        lines.extend([
            "STATUS: COMPLIANT",
            "",
            "All guardrail requirements met.",
        ])
    else:
        lines.extend([
            "STATUS: NON-COMPLIANT",
            "",
            "VIOLATIONS:",
        ])
        for v in metrics['violations']:
            lines.append(f"  - {v}")
        lines.extend([
            "",
            "Agent output requires revision before acceptance.",
        ])

    lines.append("=" * 50)
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Validate agent output compliance with AgentGuardrails.v0.md"
    )
    parser.add_argument(
        '--file', '-f',
        type=Path,
        help="File containing agent output (default: stdin)"
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help="Output as JSON instead of formatted report"
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help="Only output COMPLIANT/NON-COMPLIANT"
    )
    parser.add_argument(
        '--verify-files', '-v',
        action='store_true',
        help="Verify that cited FILE paths actually exist on disk"
    )

    args = parser.parse_args()

    # Read input
    if args.file:
        output = args.file.read_text()
    else:
        output = sys.stdin.read()

    # Check compliance
    metrics = check_compliance(output, verify_files=args.verify_files)

    # Output results
    if args.json:
        import json
        print(json.dumps(metrics, indent=2))
    elif args.quiet:
        print("COMPLIANT" if metrics['compliant'] else "NON-COMPLIANT")
        sys.exit(0 if metrics['compliant'] else 1)
    else:
        print(format_report(metrics))
        sys.exit(0 if metrics['compliant'] else 1)


if __name__ == "__main__":
    main()
