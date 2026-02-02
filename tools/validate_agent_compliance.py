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
"""

import re
import sys
import argparse
from pathlib import Path


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


def check_compliance(output: str) -> dict:
    """
    Check agent output for guardrail compliance.

    Returns dict with metrics and compliance status.
    """
    # Normalize line endings (fixes Windows CRLF, old Mac CR)
    output = normalize_line_endings(output)

    # Count required elements
    findings = count_pattern(output, r'^FINDING:\s*[^\n]+')
    file_citations = count_pattern(output, r'^FILE:\s*/[^\n]+')
    line_citations = count_pattern(output, r'^LINES?:\s*\d+')
    # CODE block: accept tabs OR 2+ spaces as indentation (was: exactly 4 spaces)
    code_blocks = count_pattern(output, r'^CODE:\n(?:(?:\t|[ ]{2,})[^\n]+\n?)+')
    verified_yes = count_pattern(output, r'^VERIFIED:\s*Yes')
    verified_no = count_pattern(output, r'^VERIFIED:\s*No')

    # Check for STATUS.md mention in first ~50 lines
    first_section = '\n'.join(output.split('\n')[:50])
    status_md_early = 'STATUS.md' in first_section

    # Count hallucination words
    hallucination_words = count_pattern(output, HALLUCINATION_WORDS)

    # Determine compliance
    violations = []

    if verified_no > 0:
        violations.append(f"Contains {verified_no} VERIFIED: No entries (should be 0)")

    if findings > 0 and file_citations < findings:
        violations.append(f"Only {file_citations} FILE: citations for {findings} findings")

    if findings > 0 and verified_yes < findings:
        violations.append(f"Only {verified_yes} VERIFIED: Yes for {findings} findings")

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
    }


def format_report(metrics: dict) -> str:
    """Format compliance check results as readable report."""
    lines = [
        "=" * 50,
        "AGENT COMPLIANCE REPORT",
        "=" * 50,
        "",
        "METRICS:",
        f"  Findings:          {metrics['findings']}",
        f"  File citations:    {metrics['file_citations']}",
        f"  Line citations:    {metrics['line_citations']}",
        f"  Code blocks:       {metrics['code_blocks']}",
        f"  VERIFIED: Yes:     {metrics['verified_yes']}",
        f"  VERIFIED: No:      {metrics['verified_no']}",
        f"  STATUS.md early:   {metrics['status_md_early']}",
        f"  Hallucination words: {metrics['hallucination_words']}",
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

    args = parser.parse_args()

    # Read input
    if args.file:
        output = args.file.read_text()
    else:
        output = sys.stdin.read()

    # Check compliance
    metrics = check_compliance(output)

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
