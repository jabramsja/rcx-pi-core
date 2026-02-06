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
from pathlib import Path
from typing import Any, Optional


# =============================================================================
# Single Source of Truth: Valid Verdicts per Agent
# =============================================================================

AGENT_VERDICTS = {
    "verifier": ["APPROVE", "REQUEST_CHANGES", "NEEDS_DISCUSSION"],
    "adversary": ["SECURE", "VULNERABLE", "NEEDS_HARDENING"],
    "expert": ["MINIMAL", "COULD_SIMPLIFY", "OVER_ENGINEERED"],
    "structural-proof": [
        "PROVEN",
        "UNPROVEN",
        "IMPOSSIBLE_AS_CLAIMED",
        "NO_STRUCTURAL_CLAIMS",
        "REQUIRES_CI_VERIFICATION",
    ],
    "grounding": ["GROUNDED", "PARTIALLY_GROUNDED", "UNGROUNDED", "THEATER"],
    "fuzzer": ["ROBUST", "FRAGILE", "BROKEN", "NOT_EXECUTED"],
    "translator": ["MATCHES_INTENT", "DEVIATES", "SCOPE_CREEP", "HOST_SMUGGLING"],
    "visualizer": ["CLEAN", "STRUCTURAL_LIES", "PYTHON_SMUGGLING"],
    "advisor": ["VIABLE_PATH", "HIDDEN_CONSTRAINTS", "FLAWED_APPROACH", "NEEDS_MORE_CONTEXT"],
    # Deep analysis verdicts
    "deep_verifier": ["ALIGNED", "DRIFT_DETECTED"],
    "deep_adversary": ["SECURE", "CONCERNS"],
    "deep_grounding": ["GROUNDED", "GAPS_FOUND"],
    "deep_structural": ["VALID", "INVALID"],
    "deep_advisor": ["HEALTHY", "NEEDS_ATTENTION", "AT_RISK"],
}

AGENT_PASS_VERDICTS = {
    "verifier": {"APPROVE"},
    "adversary": {"SECURE"},
    "expert": {"MINIMAL", "COULD_SIMPLIFY"},
    "structural-proof": {"PROVEN", "NO_STRUCTURAL_CLAIMS", "REQUIRES_CI_VERIFICATION"},
    "grounding": {"GROUNDED", "PARTIALLY_GROUNDED"},
    "fuzzer": {"ROBUST"},
    "translator": {"MATCHES_INTENT"},
    "visualizer": {"CLEAN"},
    # Advisor is explicitly non-gating; all advisor outcomes are advisory-pass.
    "advisor": {"VIABLE_PATH", "HIDDEN_CONSTRAINTS", "FLAWED_APPROACH", "NEEDS_MORE_CONTEXT"},
    # Deep analysis pass states
    "deep_verifier": {"ALIGNED"},
    "deep_adversary": {"SECURE"},
    "deep_grounding": {"GROUNDED"},
    "deep_structural": {"VALID"},
    "deep_advisor": {"HEALTHY"},
}

# Runtime gate policy for orchestrated review.
HARD_GATE_AGENTS = {"verifier", "adversary", "structural-proof"}


def _flatten_sets(mapping: dict[str, set[str]]) -> set[str]:
    values: set[str] = set()
    for verdicts in mapping.values():
        values.update(verdicts)
    return values


# Good verdicts (pass) for quick checking and deep-analysis summaries.
GOOD_VERDICTS = _flatten_sets(AGENT_PASS_VERDICTS)


def agent_passed(agent_name: str, verdict: str) -> bool:
    """Return True when a verdict is considered pass for that agent."""
    return verdict in AGENT_PASS_VERDICTS.get(agent_name, set())


# =============================================================================
# Prompt Loading
# =============================================================================

AGENT_PROMPTS_DIR = Path("tools/agents")
REDTEAM_CONTRACT_PATH = AGENT_PROMPTS_DIR / "_contract_redteam.md"


def _normalize_agent_name(agent_name: str) -> str:
    """Normalize runner names to canonical hyphen form."""
    return agent_name.strip().lower().replace("_", "-")


def get_agent_prompt_path(agent_name: str) -> Path:
    """Resolve prompt path for an agent."""
    normalized = _normalize_agent_name(agent_name)
    file_name = f"{normalized.replace('-', '_')}_prompt.md"
    return AGENT_PROMPTS_DIR / file_name


def load_agent_prompt_with_contract(agent_name: str) -> str:
    """Load prompt with shared red-team contract prepended.

    This keeps compliance boilerplate centralized so per-agent prompts can
    focus on attack lens and domain specifics.
    """
    prompt_path = get_agent_prompt_path(agent_name)
    if not prompt_path.exists():
        raise FileNotFoundError(f"Agent prompt not found: {prompt_path}")

    prompt_text = prompt_path.read_text()
    if not REDTEAM_CONTRACT_PATH.exists():
        return prompt_text

    contract_text = REDTEAM_CONTRACT_PATH.read_text().strip()
    return f"{contract_text}\n\n---\n\n{prompt_text}"


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
        specific_pattern = rf'(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*)?(?:###?\s*)?[Vv]erdict(?:\*\*)?\s*:\s*(?:\*\*)?\s*({verdict_options})\b'
        match = re.search(specific_pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Multi-line verdict format:
        # "### Verdict" then next line "**SECURE**" (or plain SECURE)
        multiline_specific_pattern = rf'(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*)?(?:###?\s*)?[Vv]erdict(?:\*\*)?\s*\n+\s*(?:\*\*)?({verdict_options})(?:\*\*)?\b'
        match = re.search(multiline_specific_pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).upper()

    # Generic verdict pattern (fallback)
    generic_pattern = r'(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?(?:###?\s*)?(?:\*\*)?[Vv]erdict(?:\*\*)?\s*:\s*(?:\*\*)?\s*([A-Z_]+)'
    match = re.search(generic_pattern, output, re.MULTILINE)
    if match:
        found = match.group(1).upper()
        # Only return if it looks like a verdict (not random word)
        if found in GOOD_VERDICTS or (valid_verdicts and found in [v.upper() for v in valid_verdicts]):
            return found

    return "UNKNOWN"


# =============================================================================
# SDK Message Text Extraction
# =============================================================================

def _extract_text_from_content_block(block: Any) -> str:
    """Extract text from a Claude SDK content block with tolerant shape handling."""
    if block is None:
        return ""
    if isinstance(block, str):
        return block.strip()
    if isinstance(block, dict):
        text = block.get("text")
        if isinstance(text, str):
            return text.strip()
        return ""

    text_attr = getattr(block, "text", None)
    if isinstance(text_attr, str):
        return text_attr.strip()

    # Some SDK objects expose model_dump(); use it as fallback.
    model_dump = getattr(block, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            if isinstance(dumped, dict):
                text = dumped.get("text")
                if isinstance(text, str):
                    return text.strip()
        except Exception:
            pass

    return ""


def extract_text_from_message(message: Any) -> str:
    """Extract best-effort text from a Claude SDK message object."""
    if message is None:
        return ""

    result = getattr(message, "result", None)
    if isinstance(result, str) and result.strip():
        return result.strip()

    content = getattr(message, "content", None)
    if isinstance(content, list):
        text_parts = []
        for block in content:
            text = _extract_text_from_content_block(block)
            if text:
                text_parts.append(text)
        if text_parts:
            return "\n".join(text_parts).strip()
    elif content is not None:
        text = _extract_text_from_content_block(content)
        if text:
            return text

    return ""


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
