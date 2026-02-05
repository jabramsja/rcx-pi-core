#!/usr/bin/env python3
"""
Agent Output Compliance Validator

Validates that agent outputs follow AgentGuardrails.v0.md requirements.
This validator checks TRUTH, not just FORMAT:
- Verifies FILE paths exist
- Verifies CODE actually appears at FILE:LINE
- Verifies line numbers are accurate

Usage:
    python tools/validate_agent_compliance.py < agent_output.txt
    python tools/validate_agent_compliance.py --file agent_output.txt
    python tools/validate_agent_compliance.py --strict  # Fail on any mismatch

Created: 2026-02-01 (9-agent review recommendation)
Updated: 2026-02-01 (9-agent self-review fixes: line endings, tabs, hallucination words)
Updated: 2026-02-02 (Critical fixes: structured blocks, file verification, empty lines)
Updated: 2026-02-02 (Fix: CODE regex in extract_finding_blocks now matches global pattern)
Updated: 2026-02-03 (CRITICAL: Now verifies CODE actually appears at FILE:LINE - not just format)
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import NamedTuple
from difflib import SequenceMatcher


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

        # Extract CODE: block
        # Accepts TWO formats:
        # 1. Indented code (tabs or 2+ spaces)
        # 2. Markdown code blocks (```python or ```)
        # Try markdown format first (more specific)
        markdown_code_match = re.search(
            r'^CODE:\s*\n```(?:\w+)?\n(.*?)```',
            part, re.MULTILINE | re.DOTALL
        )
        if markdown_code_match:
            code = markdown_code_match.group(1)
        else:
            # Fall back to indented format
            indent_code_match = re.search(
                r'^CODE:\n((?:\t|[ ]{2,})[^\n]+(?:\n(?:(?:\t|[ ]{2,})[^\n]*|[ \t]*))*)',
                part, re.MULTILINE
            )
            code = indent_code_match.group(1) if indent_code_match else None

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


def normalize_code_for_comparison(code: str) -> str:
    """
    Normalize code for comparison by removing common formatting differences.

    - Strips leading/trailing whitespace from each line
    - Removes empty lines
    - Normalizes whitespace within lines
    """
    lines = code.strip().split('\n')
    normalized = []
    for line in lines:
        stripped = line.strip()
        if stripped:  # Skip empty lines
            normalized.append(stripped)
    return '\n'.join(normalized)


def verify_code_at_location(block: FindingBlock) -> tuple[bool, str]:
    """
    CRITICAL: Verify that CODE actually appears at FILE:LINE.

    This is the key anti-hallucination check. An agent can fabricate
    a convincing-looking citation, but this function reads the actual
    file and checks if the claimed code is really there.

    Returns:
        (is_valid, error_message)
        - (True, "") if code matches
        - (False, "reason") if mismatch or error
    """
    if not block.file_path:
        return False, "No FILE path provided"

    if not block.code:
        return False, "No CODE block provided"

    if not block.lines:
        return False, "No LINES provided"

    # Check file exists
    if not os.path.exists(block.file_path):
        return False, f"File not found: {block.file_path}"

    try:
        # Read the actual file
        with open(block.file_path, 'r') as f:
            file_lines = f.readlines()

        # Parse line range (e.g., "123" or "123-127")
        if '-' in block.lines:
            start, end = block.lines.split('-')
            start_line = int(start)
            end_line = int(end)
        else:
            start_line = int(block.lines)
            end_line = start_line

        # Validate line numbers
        if start_line < 1 or end_line > len(file_lines):
            return False, f"Line range {block.lines} out of bounds (file has {len(file_lines)} lines)"

        # Extract actual code at that location (1-indexed to 0-indexed)
        actual_lines = file_lines[start_line - 1:end_line]
        actual_code = ''.join(actual_lines)

        # Normalize both for comparison
        claimed_normalized = normalize_code_for_comparison(block.code)
        actual_normalized = normalize_code_for_comparison(actual_code)

        # Check for exact match after normalization
        if claimed_normalized == actual_normalized:
            return True, ""

        # Check for substring match (agent may have excerpted)
        if claimed_normalized in actual_normalized or actual_normalized in claimed_normalized:
            return True, ""

        # Check similarity ratio
        similarity = SequenceMatcher(None, claimed_normalized, actual_normalized).ratio()

        if similarity >= 0.8:
            # Close enough - minor formatting differences
            return True, ""

        # Code doesn't match - this is a FABRICATION
        return False, (
            f"CODE MISMATCH at {block.file_path}:{block.lines}\n"
            f"  Claimed ({len(claimed_normalized)} chars): {claimed_normalized[:100]}...\n"
            f"  Actual ({len(actual_normalized)} chars): {actual_normalized[:100]}...\n"
            f"  Similarity: {similarity:.1%}"
        )

    except Exception as e:
        return False, f"Error reading file: {e}"


def verify_all_code_citations(blocks: list[FindingBlock]) -> list[str]:
    """
    Verify all CODE citations in finding blocks.

    Returns list of fabrication errors (empty if all valid).
    """
    fabrications = []

    for block in blocks:
        if block.file_path and block.code and block.lines:
            is_valid, error = verify_code_at_location(block)
            if not is_valid:
                fabrications.append(error)

    return fabrications


def check_compliance(output: str, verify_files: bool = False, verify_code: bool = False, strict: bool = False) -> dict:
    """
    Check agent output for guardrail compliance.

    Args:
        output: Agent output text to validate
        verify_files: If True, check that cited FILE paths actually exist
        verify_code: If True, verify CODE actually appears at FILE:LINE (CRITICAL)
        strict: If True, any mismatch is a violation (recommended for CI)

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
    # CODE block: accepts two formats
    # 1. Markdown: CODE:\n```python\ncode\n```
    # 2. Indented: CODE:\n    code here
    code_blocks_markdown = count_pattern(output, r'^CODE:\s*\n```(?:\w+)?\n.*?```')
    code_blocks_indented = count_pattern(output, r'^CODE:\n(?:\t|[ ]{2,})[^\n]+(?:\n(?:(?:\t|[ ]{2,})[^\n]*|[ \t]*))*')
    code_blocks = code_blocks_markdown + code_blocks_indented
    verified_yes = count_pattern(output, r'^VERIFIED:\s*Yes')
    verified_no = count_pattern(output, r'^VERIFIED:\s*No')

    # Check for STATUS.md mention in first ~50 lines
    first_section = '\n'.join(output.split('\n')[:50])
    status_md_early = 'STATUS.md' in first_section

    # Count hallucination words
    hallucination_words = count_pattern(output, HALLUCINATION_WORDS)

    # Determine compliance
    violations = []
    fabrications = []

    # === CRITICAL: Check each finding block has required components ===
    # Core components: FILE, LINES, CODE (required for evidence)
    # VERIFIED: optional if FILE+LINES+CODE all present (the evidence itself is verification)
    incomplete_blocks = []
    for i, block in enumerate(finding_blocks):
        missing = []
        if not block.file_path:
            missing.append("FILE")
        if not block.lines:
            missing.append("LINES")
        if not block.code:
            missing.append("CODE")
        # VERIFIED is only required if FILE/LINES/CODE are incomplete
        # When all evidence is present, the code itself serves as verification
        has_all_evidence = block.file_path and block.lines and block.code
        if not has_all_evidence and not block.verified:
            missing.append("VERIFIED")
        elif block.verified and block.verified.lower() == 'no':
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

    # === CRITICAL: Verify CODE actually appears at FILE:LINE ===
    # This is the key anti-fabrication check
    if verify_code and finding_blocks:
        fabrications = verify_all_code_citations(finding_blocks)
        if fabrications:
            violations.append(f"FABRICATION DETECTED: {len(fabrications)} code citations don't match actual files")
            for fab in fabrications[:3]:
                violations.append(f"  - {fab}")

    # Legacy count-based checks (kept for backwards compatibility)
    if verified_no > 0:
        violations.append(f"Contains {verified_no} VERIFIED: No entries (should be 0)")

    if not status_md_early and findings > 0:
        violations.append("STATUS.md not mentioned in first 50 lines")

    # Hallucination threshold: agents use words like "appears", "could" appropriately in analysis
    # Only flag truly excessive usage (>10) that suggests unsupported claims
    if hallucination_words > 10:
        violations.append(f"High hallucination word count: {hallucination_words}")

    # === CRITICAL: Approval verdicts require evidence ===
    # Security fix: Prevent rubber-stamp approvals without findings
    # BUT: Legitimate "clean" reviews have no findings - they need explicit analysis evidence
    approval_verdicts = {"APPROVE", "SECURE", "PROVEN", "GROUNDED", "ROBUST", "MINIMAL", "CLEAN", "MATCHES_INTENT"}
    output_upper = output.upper()
    has_approval_verdict = any(v in output_upper for v in approval_verdicts)

    if has_approval_verdict and findings == 0:
        # Check if this looks like a genuine approval (has VERDICT marker)
        verdict_marker = re.search(r'(?:^|\n)\s*(?:\*\*)?(?:###?\s*)?VERDICT', output, re.IGNORECASE)
        if verdict_marker:
            # Check for evidence of genuine review without findings:
            # 1. Explicit "no issues/findings/violations" statements
            # 2. Clean review patterns (NO_STRUCTURAL_CLAIMS, etc.)
            # 3. Files reviewed patterns
            clean_review_patterns = [
                r'no\s+(issues?|findings?|violations?|concerns?|problems?)\s+(found|detected|identified)',
                r'(code|implementation)\s+(is\s+)?(clean|correct|valid|sound)',
                r'no\s+structural\s+claims',
                r'no_structural_claims',
                r'nothing\s+to\s+(report|flag|cite)',
                r'files?\s+reviewed',
                r'checked\s+.*files?',
                r'analysis\s+(complete|done)',
                r'review(ed)?\s+\d+\s+files?',
            ]
            has_clean_review_evidence = any(
                re.search(pattern, output, re.IGNORECASE)
                for pattern in clean_review_patterns
            )

            if not has_clean_review_evidence:
                violations.append("Approval verdict without any FINDING blocks - missing evidence")

    # Strict mode: require all verifications to pass
    if strict and finding_blocks:
        if not verify_files:
            violations.append("STRICT MODE: --verify-files required but not enabled")
        if not verify_code:
            violations.append("STRICT MODE: --verify-code required but not enabled")

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
        # Fabrication detection
        "fabrications": len(fabrications),
        "fabrication_details": fabrications,
    }


def format_report(metrics: dict) -> str:
    """Format compliance check results as readable report."""
    lines = [
        "=" * 60,
        "AGENT COMPLIANCE REPORT",
        "=" * 60,
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
        "FABRICATION DETECTION:",
        f"  Code mismatches:     {metrics.get('fabrications', 'NOT CHECKED')}",
        "",
    ]

    if metrics.get('fabrications', 0) > 0:
        lines.extend([
            "*** FABRICATIONS FOUND ***",
            "The following CODE citations do not match the actual file contents:",
            "",
        ])
        for detail in metrics.get('fabrication_details', []):
            lines.append(f"  {detail}")
        lines.append("")

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

    lines.append("=" * 60)
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
    parser.add_argument(
        '--verify-code', '-c',
        action='store_true',
        help="CRITICAL: Verify CODE actually appears at FILE:LINE (catches fabrications)"
    )
    parser.add_argument(
        '--strict', '-s',
        action='store_true',
        help="Strict mode: require all verifications, fail on any mismatch (recommended for CI)"
    )

    args = parser.parse_args()

    # Strict mode implies all verifications
    if args.strict:
        args.verify_files = True
        args.verify_code = True

    # Read input
    if args.file:
        output = args.file.read_text()
    else:
        output = sys.stdin.read()

    # Check compliance
    metrics = check_compliance(
        output,
        verify_files=args.verify_files,
        verify_code=args.verify_code,
        strict=args.strict
    )

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
