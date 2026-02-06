#!/usr/bin/env python3
"""
Shared utilities for agent runners.

This module provides common functions used across all agent runners to avoid
duplication and ensure consistency:
- validate_compliance(): Run compliance validation on agent output
- extract_verdict_secure(): Extract verdict using secure marker parsing
- sanitize_for_prompt(): Sanitize text before prompt injection
- AGENT_VERDICTS: Single source of truth for valid verdicts per agent

All agent runners should import from this module instead of duplicating code.
"""

import re
import subprocess
import unicodedata
from typing import Optional


# =============================================================================
# Single Source of Truth: Valid Verdicts per Agent
# =============================================================================

AGENT_VERDICTS = {
    "verifier": ["APPROVE", "REQUEST_CHANGES", "NEEDS_DISCUSSION"],
    "adversary": ["SECURE", "VULNERABLE", "NEEDS_HARDENING"],
    "expert": ["MINIMAL", "COULD_SIMPLIFY", "OVER_ENGINEERED"],
    # structural-proof has expanded verdicts per prompt (Mode A/B support)
    "structural-proof": [
        "PROVEN", "UNPROVEN", "PARTIAL", "NO_STRUCTURAL_CLAIMS",
        "IMPOSSIBLE_AS_CLAIMED", "REQUIRES_CI_VERIFICATION"
    ],
    "grounding": ["GROUNDED", "GAPS_FOUND", "NEEDS_TESTS", "PARTIALLY_GROUNDED", "UNGROUNDED"],
    "fuzzer": ["PASS", "FAIL", "NEEDS_INVESTIGATION", "ROBUST", "BROKEN"],
    "translator": ["CLEAR", "NEEDS_REVISION", "DEVIATES"],
    "visualizer": ["COMPLETE", "PARTIAL", "NEEDS_DIAGRAMS"],
    # advisor uses OPTIONS_PROVIDED per prompt
    "advisor": ["OPTIONS_PROVIDED", "RECOMMENDATION", "NEEDS_MORE_CONTEXT", "RECOMMENDED", "OPTIONAL", "NOT_RECOMMENDED"],
    # Deep analysis verdicts
    "deep_verifier": ["ALIGNED", "DRIFT_DETECTED"],
    "deep_adversary": ["SECURE", "CONCERNS"],
    "deep_grounding": ["GROUNDED", "GAPS_FOUND"],
    "deep_structural": ["VALID", "INVALID"],
    "deep_advisor": ["HEALTHY", "NEEDS_ATTENTION", "AT_RISK"],
}

# Good verdicts (pass) for quick checking
GOOD_VERDICTS = {
    "APPROVE", "SECURE", "MINIMAL", "COULD_SIMPLIFY", "PROVEN", "PARTIAL",
    "GROUNDED", "PARTIALLY_GROUNDED", "PASS", "ROBUST", "CLEAR", "COMPLETE",
    "RECOMMENDED", "OPTIONAL", "OPTIONS_PROVIDED", "RECOMMENDATION",
    "ALIGNED", "VALID", "HEALTHY", "NO_STRUCTURAL_CLAIMS", "REQUIRES_CI_VERIFICATION"
}


# =============================================================================
# Compliance Validation
# =============================================================================

def validate_compliance(
    output: str,
    strict: bool = True,
    verify_files: bool = False,
    verify_code: bool = False,
    json_output: bool = False
) -> tuple[bool, str, dict]:
    """Run compliance validation on agent output.

    This is the single implementation used by all agent runners.
    Calls tools/validate_agent_compliance.py as a subprocess.

    Args:
        output: Agent output text to validate
        strict: Enable strict mode (default True)
        verify_files: Verify FILE: paths exist
        verify_code: Verify CODE: blocks match actual files
        json_output: Request JSON output from validator

    Returns:
        Tuple of (is_compliant, error_message, metrics_dict)
    """
    try:
        cmd = ["python3", "tools/validate_agent_compliance.py"]
        if strict:
            cmd.append("--strict")
        if verify_files:
            cmd.append("--verify-files")
        if verify_code:
            cmd.append("--verify-code")
        if json_output:
            cmd.append("--json")

        result = subprocess.run(
            cmd,
            input=output,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0 and not result.stdout:
            return False, f"Validator crashed: {result.stderr}", {}

        if json_output and result.stdout:
            import json
            try:
                metrics = json.loads(result.stdout)
                if not metrics.get("compliant", False):
                    violations = metrics.get("violations", ["Unknown violation"])
                    return False, "; ".join(violations[:3]), metrics
                return True, "", metrics
            except json.JSONDecodeError:
                pass

        # Non-JSON mode or JSON parse failed
        if result.returncode == 0:
            return True, "", {}
        else:
            return False, result.stderr or "Validation failed", {}

    except subprocess.TimeoutExpired:
        return False, "Validation timed out", {}
    except Exception as e:
        return False, f"Validation error: {e}", {}


# =============================================================================
# Secure Verdict Extraction
# =============================================================================

def extract_verdict_secure(
    output: str,
    agent_name: Optional[str] = None,
    valid_verdicts: Optional[list[str]] = None
) -> str:
    """Extract verdict from agent output using secure marker parsing.

    Security: Only looks for explicit VERDICT: markers to prevent spoofing
    via incidental mentions like "This code is NOT ROBUST".

    Args:
        output: Agent output text
        agent_name: Optional agent name to get valid verdicts from AGENT_VERDICTS
        valid_verdicts: Optional explicit list of valid verdicts

    Returns:
        Extracted verdict string, or "UNKNOWN" if not found
    """
    if not output:
        return "UNKNOWN"

    # Determine valid verdicts
    if valid_verdicts is None and agent_name:
        valid_verdicts = AGENT_VERDICTS.get(agent_name, [])
    if valid_verdicts is None:
        valid_verdicts = []

    # Build pattern for this agent's verdicts
    if valid_verdicts:
        verdict_options = "|".join(re.escape(v) for v in valid_verdicts)
        specific_pattern = rf'(?:^|\n)\s*(?:\*\*)?[Vv]erdict(?:\*\*)?[:\s]+({verdict_options})\b'
        match = re.search(specific_pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).upper()

    # Generic verdict pattern (fallback)
    generic_pattern = r'(?:^|\n)\s*(?:###?\s*)?(?:\*\*)?[Vv]erdict(?:\*\*)?[:\s]+(\w+)'
    match = re.search(generic_pattern, output, re.MULTILINE)
    if match:
        found = match.group(1).upper()
        # Only return if it looks like a verdict (not random word)
        if found in GOOD_VERDICTS or (valid_verdicts and found in [v.upper() for v in valid_verdicts]):
            return found

    return "UNKNOWN"


# =============================================================================
# Prompt Sanitization
# =============================================================================

def sanitize_for_prompt(text: str, max_len: int = 4000) -> str:
    """Sanitize text before injecting into prompt.

    Prevents prompt injection by:
    - Unicode normalization (NFKC) to prevent lookalike bypasses
    - Truncation to max_len
    - Escaping triple backticks to prevent code block breakout
    - Removing instruction-like patterns

    Args:
        text: Text to sanitize
        max_len: Maximum length (default 4000)

    Returns:
        Sanitized text safe for prompt injection
    """
    if not text:
        return ""

    # Unicode normalization first - converts lookalikes (Greek omicron -> Latin o)
    text = unicodedata.normalize('NFKC', text)

    # Truncate
    text = text[:max_len]

    # Escape triple backticks to prevent code block breakout
    text = text.replace('```', '` ` `')

    # Escape newlines to prevent context breakout
    text = text.replace('\n', ' ').replace('\r', ' ')

    # Remove instruction-like patterns
    patterns_to_redact = [
        'ignore previous',
        'disregard',
        'new instructions',
        'system prompt',
        'forget everything'
    ]
    for pattern in patterns_to_redact:
        text = text.replace(pattern.lower(), '[REDACTED]')
        text = text.replace(pattern.upper(), '[REDACTED]')
        text = text.replace(pattern.title(), '[REDACTED]')

    return text
