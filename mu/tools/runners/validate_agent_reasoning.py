#!/usr/bin/env python3
"""
Agent Reasoning Validator - Enforces accountability in agent decisions.

This validator goes beyond format compliance (AgentGuardrails) to check
the QUALITY and COMPLETENESS of agent reasoning.

Enforcement:
1. Reasoning Trace - Agents must show CHECKED/NOT_CHECKED sections
2. Uncertainty Acknowledgment - Agents must state limitations
3. Evidence Density - Claims must have proportional evidence

Usage:
    python tools/runners/validate_agent_reasoning.py < agent_output.txt
    python tools/runners/validate_agent_reasoning.py --file output.txt
    python tools/runners/validate_agent_reasoning.py --json  # Machine-readable

Created: 2026-02-04
"""

import sys
import re
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, asdict

try:
    from tools.runners.shared_agent_utils import AGENT_PASS_VERDICTS, AGENT_VERDICTS, APPROVAL_VERDICTS, extract_verdict_secure
except ModuleNotFoundError:
    # Allow direct execution: python tools/runners/validate_agent_reasoning.py
    _tools_dir = Path(__file__).resolve().parent
    if str(_tools_dir) not in sys.path:
        sys.path.insert(0, str(_tools_dir))
    from shared_agent_utils import AGENT_PASS_VERDICTS, AGENT_VERDICTS, APPROVAL_VERDICTS, extract_verdict_secure


# =============================================================================
# Reasoning Requirements by Verdict
# =============================================================================

# APPROVE is high-stakes (false negative = bad code ships)
# So APPROVE requires MORE evidence than rejection

VERDICT_REQUIREMENTS = {
    # High-confidence approvals require stronger evidence density.
    "APPROVE": {"min_checked": 3, "requires_not_checked": True, "min_evidence": 2},
    "SECURE": {"min_checked": 3, "requires_not_checked": True, "min_evidence": 2},
    "MINIMAL": {"min_checked": 2, "requires_not_checked": True, "min_evidence": 1},
    "COULD_SIMPLIFY": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "PROVEN": {"min_checked": 2, "requires_not_checked": True, "min_evidence": 2},
    "NO_STRUCTURAL_CLAIMS": {"min_checked": 1, "requires_not_checked": True, "min_evidence": 1},
    "REQUIRES_CI_VERIFICATION": {"min_checked": 1, "requires_not_checked": True, "min_evidence": 1},
    "GROUNDED": {"min_checked": 2, "requires_not_checked": True, "min_evidence": 1},
    "PARTIALLY_GROUNDED": {"min_checked": 1, "requires_not_checked": True, "min_evidence": 1},
    "ROBUST": {"min_checked": 2, "requires_not_checked": True, "min_evidence": 1},
    "MATCHES_INTENT": {"min_checked": 2, "requires_not_checked": True, "min_evidence": 1},
    "CLEAN": {"min_checked": 1, "requires_not_checked": True, "min_evidence": 1},
    "VIABLE_PATH": {"min_checked": 1, "requires_not_checked": True, "min_evidence": 1},

    # Negative/concern verdicts still require concrete evidence.
    "REQUEST_CHANGES": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "NEEDS_DISCUSSION": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 0},
    "VULNERABLE": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "NEEDS_HARDENING": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "OVER_ENGINEERED": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "UNPROVEN": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "IMPOSSIBLE_AS_CLAIMED": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "UNGROUNDED": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "THEATER": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "FRAGILE": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "BROKEN": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "NOT_EXECUTED": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 0},
    "DEVIATES": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "SCOPE_CREEP": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "HOST_SMUGGLING": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "STRUCTURAL_LIES": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "PYTHON_SMUGGLING": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "HIDDEN_CONSTRAINTS": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "FLAWED_APPROACH": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 1},
    "NEEDS_MORE_CONTEXT": {"min_checked": 1, "requires_not_checked": False, "min_evidence": 0},
}

# APPROVAL_VERDICTS imported from shared_agent_utils (single source of truth)

ALL_CANONICAL_VERDICTS = sorted({
    verdict for agent, verdicts in AGENT_VERDICTS.items()
    if not agent.startswith("deep_")
    for verdict in verdicts
})


# =============================================================================
# Extraction
# =============================================================================

def extract_verdict(output: str) -> str | None:
    """Extract the verdict from agent output.

    Security: Only looks for explicit VERDICT: markers to prevent spoofing
    via incidental mentions like "This code is NOT ROBUST".
    """
    verdict = extract_verdict_secure(output, valid_verdicts=ALL_CANONICAL_VERDICTS)
    if verdict == "UNKNOWN":
        return None
    return verdict


def extract_checked_items(output: str) -> list[str]:
    """Extract items from CHECKED section.

    Handles multiple agent output formats:
    - Markdown headers: ### CHECKED, ## CHECKED
    - Plain headers: CHECKED:, What I Checked:
    - Bullet items: - item, * item
    - Numbered items: 1. item, 2. item
    """
    items = []

    # Look for CHECKED section with optional markdown header prefix (###, ##, #)
    # Uses [^\n]+ instead of .+ to prevent ReDoS via catastrophic backtracking
    # Allows optional blank lines between header and first bullet item
    checked_match = re.search(
        r'(?:^|\n)(?:#{1,3}\s+)?(?:CHECKED|What I Checked|Verified)[:\s]*\n\n?((?:(?:[-*]|\d+\.)\s+[^\n]+\n)+)',
        output,
        re.MULTILINE | re.IGNORECASE
    )

    if checked_match:
        section = checked_match.group(1)
        items = re.findall(r'(?:[-*]|\d+\.)\s+(.+?)(?:\n|$)', section)

    return [item.strip() for item in items if item.strip()]


def extract_not_checked_items(output: str) -> list[str]:
    """Extract items from NOT_CHECKED section.

    Handles multiple agent output formats:
    - Markdown headers: ### NOT_CHECKED, ## NOT_CHECKED
    - Plain headers: NOT_CHECKED:, Not Checked:, Limitations:
    - Bullet items: - item, * item
    - Numbered items: 1. item, 2. item
    """
    items = []

    # Look for NOT_CHECKED section with optional markdown header prefix
    # Uses [^\n]+ instead of .+ to prevent ReDoS via catastrophic backtracking
    # Allows optional blank lines between header and first bullet item
    not_checked_match = re.search(
        r'(?:^|\n)(?:#{1,3}\s+)?(?:NOT_CHECKED|Not Checked|What I Did NOT Check|Limitations|Blind Spots)[:\s]*\n\n?((?:(?:[-*]|\d+\.)\s+[^\n]+\n)+)',
        output,
        re.MULTILINE | re.IGNORECASE
    )

    if not_checked_match:
        section = not_checked_match.group(1)
        items = re.findall(r'(?:[-*]|\d+\.)\s+(.+?)(?:\n|$)', section)

    return [item.strip() for item in items if item.strip()]


def count_evidence_citations(output: str) -> int:
    """Count FILE:LINE evidence citations."""
    # Pattern: FILE: /path or file.py:123
    file_citations = len(re.findall(r'(?:FILE:|\.py:\d+|\.json:\d+|\.js:\d+)', output))
    return file_citations


def detect_hedging_language(output: str) -> list[str]:
    """Detect hedging/uncertain language that should be explicit."""
    hedges = []

    hedge_patterns = [
        (r'\bprobably\b', "probably"),
        (r'\blikely\b', "likely"),
        (r'\bmight\b', "might"),
        (r'\bcould be\b', "could be"),
        (r'\bseems to\b', "seems to"),
        (r'\bappears to\b', "appears to"),
        (r'\bI think\b', "I think"),
        (r'\bI believe\b', "I believe"),
        (r'\bshould be\b', "should be (without verification)"),
    ]

    for pattern, label in hedge_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            hedges.append(label)

    return hedges


# =============================================================================
# Validation
# =============================================================================

@dataclass
class ReasoningValidation:
    """Result of reasoning validation."""
    verdict: str | None
    is_approval: bool
    checked_items: list[str]
    not_checked_items: list[str]
    evidence_count: int
    hedging_detected: list[str]
    violations: list[str]
    is_valid: bool
    requires_challenge: bool  # Should this be challenged by skeptic?


def validate_reasoning(output: str) -> ReasoningValidation:
    """Validate the reasoning quality of agent output."""

    verdict = extract_verdict(output)
    is_approval = verdict in APPROVAL_VERDICTS if verdict else False
    checked = extract_checked_items(output)
    not_checked = extract_not_checked_items(output)
    evidence = count_evidence_citations(output)
    hedging = detect_hedging_language(output)

    violations = []

    # Get requirements for this verdict
    if verdict and verdict in VERDICT_REQUIREMENTS:
        reqs = VERDICT_REQUIREMENTS[verdict]

        # Check minimum CHECKED items
        if len(checked) < reqs["min_checked"]:
            violations.append(
                f"Verdict {verdict} requires {reqs['min_checked']}+ CHECKED items, found {len(checked)}"
            )

        # Check NOT_CHECKED requirement
        if reqs["requires_not_checked"] and len(not_checked) == 0:
            violations.append(
                f"Verdict {verdict} requires NOT_CHECKED section (acknowledge limitations)"
            )

        # Check evidence density
        if evidence < reqs["min_evidence"]:
            violations.append(
                f"Verdict {verdict} requires {reqs['min_evidence']}+ FILE:LINE citations, found {evidence}"
            )

    elif verdict is None:
        violations.append("No verdict found in output")

    # Hedging in approval is suspicious
    if is_approval and hedging:
        violations.append(
            f"Approval verdict uses hedging language: {', '.join(hedging)}. "
            f"Either verify or move to NOT_CHECKED."
        )

    # Approval without NOT_CHECKED is overconfident
    if is_approval and len(not_checked) == 0:
        violations.append(
            "Approval without NOT_CHECKED section suggests overconfidence. "
            "What WASN'T verified?"
        )

    is_valid = len(violations) == 0

    # Challenge approvals that pass validation (skeptic review)
    requires_challenge = is_approval and is_valid

    return ReasoningValidation(
        verdict=verdict,
        is_approval=is_approval,
        checked_items=checked,
        not_checked_items=not_checked,
        evidence_count=evidence,
        hedging_detected=hedging,
        violations=violations,
        is_valid=is_valid,
        requires_challenge=requires_challenge,
    )


# =============================================================================
# Output
# =============================================================================

def format_report(validation: ReasoningValidation) -> str:
    """Format validation result as human-readable report."""
    lines = [
        "=" * 60,
        "AGENT REASONING VALIDATION",
        "=" * 60,
        "",
        f"Verdict: {validation.verdict or 'NOT FOUND'}",
        f"Is Approval: {validation.is_approval}",
        "",
        f"CHECKED items: {len(validation.checked_items)}",
    ]

    for item in validation.checked_items[:5]:
        lines.append(f"  - {item[:60]}")
    if len(validation.checked_items) > 5:
        lines.append(f"  ... and {len(validation.checked_items) - 5} more")

    lines.append("")
    lines.append(f"NOT_CHECKED items: {len(validation.not_checked_items)}")

    for item in validation.not_checked_items[:5]:
        lines.append(f"  - {item[:60]}")

    lines.extend([
        "",
        f"Evidence citations: {validation.evidence_count}",
        f"Hedging language: {', '.join(validation.hedging_detected) or 'none'}",
        "",
    ])

    if validation.is_valid:
        lines.append("STATUS: VALID REASONING")
    else:
        lines.append("STATUS: INVALID REASONING")
        lines.append("")
        lines.append("VIOLATIONS:")
        for v in validation.violations:
            lines.append(f"  - {v}")

    if validation.requires_challenge:
        lines.extend([
            "",
            "NOTE: Approval verdict - should be challenged by skeptic agent",
        ])

    lines.append("=" * 60)
    return "\n".join(lines)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Validate agent reasoning quality"
    )
    parser.add_argument(
        '--file', '-f',
        type=Path,
        help="File containing agent output (default: stdin)"
    )
    parser.add_argument(
        '--json', '-j',
        action='store_true',
        help="Output as JSON"
    )
    args = parser.parse_args()

    # Read input
    if args.file:
        output = args.file.read_text()
    else:
        output = sys.stdin.read()

    # Validate
    validation = validate_reasoning(output)

    # Output
    if args.json:
        result = asdict(validation)
        print(json.dumps(result, indent=2))
    else:
        print(format_report(validation))

    # Exit code
    sys.exit(0 if validation.is_valid else 1)


if __name__ == "__main__":
    main()
