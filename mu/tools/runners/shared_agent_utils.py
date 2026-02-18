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

import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any, Optional

# Strip CLAUDECODE from env when running inside a Claude Code session.
# CLAUDECODE=1 triggers nested session blocking in child claude processes.
# All agent runners import this module, so this runs once at import time.
os.environ.pop("CLAUDECODE", None)


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

# Canonical model policy (single source of truth).
# Agent runners and orchestrators should resolve model names only from here.
AGENT_DEFAULT_MODELS = {
    "verifier": "opus",
    "adversary": "opus",
    "expert": "opus",
    "advisor": "opus",
    "skeptic": "opus",
    "structural-proof": "sonnet",
    "grounding": "sonnet",
    "fuzzer": "sonnet",
    "translator": "sonnet",
    "visualizer": "sonnet",
    # Deep analysis aliases
    "deep_verifier": "opus",
    "deep_adversary": "opus",
    "deep_grounding": "sonnet",
    "deep_structural": "sonnet",
    "deep_advisor": "opus",
}

# Allowed short model aliases used in this repository.
# Keep this constrained to avoid silent typos in CLI overrides.
SUPPORTED_AGENT_MODELS = {"opus", "sonnet"}

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

# Adversary verdicts that can block merge when proof is machine-checkable.
ADVERSARY_BLOCKING_VERDICTS = {"VULNERABLE", "NEEDS_HARDENING"}
# Required proof markers for adversary hard-block escalation.
ADVERSARY_REQUIRED_PROOF_MARKERS = ("FILE", "LINES", "CODE", "CALL_PATH", "REPRO_STEPS")


def _flatten_sets(mapping: dict[str, set[str]]) -> set[str]:
    values: set[str] = set()
    for verdicts in mapping.values():
        values.update(verdicts)
    return values


# Good verdicts (pass) for quick checking and deep-analysis summaries.
GOOD_VERDICTS = _flatten_sets(AGENT_PASS_VERDICTS)

# Approval verdicts (non-deep) that trigger skeptic challenge and rubber-stamp checks.
# Single source of truth — imported by validate_agent_compliance and validate_agent_reasoning.
APPROVAL_VERDICTS = {
    verdict
    for agent, verdicts in AGENT_PASS_VERDICTS.items()
    if not agent.startswith("deep_")
    for verdict in verdicts
}

# Canonical regex for splitting on FINDING: blocks.
# Handles: FINDING:, **FINDING:**, **FINDING**:, ### FINDING:, - FINDING:
# Single source of truth — used by validate_agent_compliance and shared_agent_utils.
FINDING_BLOCK_PATTERN = r'^(?:\s*(?:[-*]\s+)?)?(?:\*\*)?(?:\#{1,3}\s*)?\s*FINDING(?:\*\*)?\s*:\s*(?:\*\*)?\s*'

# Zero-width and line-breaking Unicode characters that could hide injection payloads.
# Includes U+2028 (Line Separator) and U+2029 (Paragraph Separator) which act as
# newlines in JavaScript and some contexts, bypassing \n/\r replacement.
_ZERO_WIDTH_RE = re.compile(r'[\u200b\u200c\u200d\u2028\u2029\u2060\ufeff]')


def agent_passed(agent_name: str, verdict: str) -> bool:
    """Return True when a verdict is considered pass for that agent."""
    return verdict in AGENT_PASS_VERDICTS.get(agent_name, set())


def normalize_model_name(model: Optional[str]) -> Optional[str]:
    """Normalize model names to internal short aliases."""
    if model is None:
        return None
    normalized = model.strip().lower()
    return normalized or None


def resolve_agent_model(agent_name: str, override_model: Optional[str] = None) -> str:
    """Resolve model for an agent with optional override."""
    normalized_override = normalize_model_name(override_model)
    if normalized_override is not None:
        if normalized_override not in SUPPORTED_AGENT_MODELS:
            raise ValueError(
                f"Unsupported model override '{override_model}'. "
                f"Expected one of: {sorted(SUPPORTED_AGENT_MODELS)}"
            )
        return normalized_override

    raw_name = agent_name.strip().lower()
    # Accept both underscore and hyphen variants to prevent silent fallback
    # for deep-analysis aliases such as deep_verifier / deep-structural.
    candidates = [
        raw_name,
        raw_name.replace("_", "-"),
        raw_name.replace("-", "_"),
    ]
    for candidate in candidates:
        if candidate in AGENT_DEFAULT_MODELS:
            return AGENT_DEFAULT_MODELS[candidate]
    return "sonnet"


def build_sdk_options(
    options_cls: Any,
    *,
    allowed_tools: list[str],
    max_turns: int,
    model: Optional[str],
    require_model_kwarg: bool = True,
    **extra_kwargs: Any,
) -> Any:
    """Construct ClaudeAgentOptions with explicit model wiring.

    Fail-closed behavior:
    - If a model is configured but SDK options class does not accept `model=`,
      raise RuntimeError (unless require_model_kwarg=False).
    """
    kwargs: dict[str, Any] = {
        "allowed_tools": allowed_tools,
        "max_turns": max_turns,
    }
    kwargs.update(extra_kwargs)

    normalized_model = normalize_model_name(model)
    if normalized_model is not None:
        try:
            return options_cls(model=normalized_model, **kwargs)
        except TypeError as exc:
            if require_model_kwarg:
                raise RuntimeError(
                    "ClaudeAgentOptions does not support `model=` but model "
                    f"policy requires it (requested '{normalized_model}')."
                ) from exc

    return options_cls(**kwargs)


def adversary_has_machine_verifiable_evidence(output: str) -> bool:
    """Return True when at least one FINDING block contains all required proof markers.

    This enforces evidence-gated hard blocks for adversary verdicts to reduce
    false-positive merge blockers while preserving security pressure.
    """
    if not output:
        return False

    finding_blocks = re.split(
        FINDING_BLOCK_PATTERN,
        output,
        flags=re.MULTILINE,
    )
    if len(finding_blocks) <= 1:
        return False

    for block in finding_blocks[1:]:
        has_all_markers = True
        for marker in ADVERSARY_REQUIRED_PROOF_MARKERS:
            marker_regex = (
                rf'^(?:\s*(?:[-*]\s+)?)?(?:\*\*)?{re.escape(marker)}(?:\*\*)?\s*:'
            )
            if not re.search(marker_regex, block, re.MULTILINE | re.IGNORECASE):
                has_all_markers = False
                break
        if has_all_markers:
            return True

    return False


def adversary_blocks_merge(verdict: str, output: str, is_compliant: bool) -> bool:
    """Adversary can block only with compliant output + machine-checkable proof."""
    if verdict not in ADVERSARY_BLOCKING_VERDICTS:
        return False
    if not is_compliant:
        return False
    return adversary_has_machine_verifiable_evidence(output)


# =============================================================================
# Prompt Loading
# =============================================================================

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT_PROMPTS_DIR = _REPO_ROOT / "tools" / "agents"
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
        cmd = [sys.executable, str(_REPO_ROOT / "tools" / "runners" / "validate_agent_compliance.py")]
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
        # Exit code 0 = compliant, 2 = compliant with imprecise citation warnings
        if result.returncode in (0, 2):
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

        # Tier 1: Colon format — "Verdict: TOKEN" or "**Verdict:** TOKEN"
        # Allows emojis/symbols between colon and token (e.g., "Verdict: ✅ **VALID**")
        # Also handles "Final Verdict:", "L3 Verdict:", etc.
        specific_pattern = rf'(?:^|\n)[^\n]*[Vv]erdict[^\n]*:\s*[^\n]*?\b({verdict_options})\b'
        match = re.search(specific_pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Tier 2: Multi-line — "### Verdict" then next line "**TOKEN**" or "TOKEN"
        multiline_specific_pattern = rf'(?:^|\n)[^\n]*[Vv]erdict[^\n]*\n+\s*(?:\*\*)?({verdict_options})(?:\*\*)?\b'
        match = re.search(multiline_specific_pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).upper()

        # Tier 3: Bracket format — "### Verdict\n[TOKEN / TOKEN2 / ...]"
        # Agents produce this when prompts show options as [A / B / C]
        bracket_pattern = rf'(?:^|\n)[^\n]*[Vv]erdict[^\n]*\n+\s*\[\s*({verdict_options})\b'
        match = re.search(bracket_pattern, output, re.MULTILINE | re.IGNORECASE)
        if match:
            return match.group(1).upper()

    # Tier 4: Search lines near a "Verdict" header for embedded tokens.
    # Catches: "## Final Verdict\n\nAll claims are **VALID**."
    # Handles "Final Verdict", "L3 Verdict", etc. — any line containing "Verdict".
    # Security: only matches tokens from agent's allowlist as whole words.
    if valid_verdicts:
        verdict_header = re.search(
            r'(?:^|\n)[^\n]*[Vv]erdict',
            output, re.MULTILINE,
        )
        if verdict_header:
            after_header = output[verdict_header.end():]
            lines_after = after_header.split('\n')[:8]
            for line in lines_after:
                for v in valid_verdicts:
                    if re.search(rf'\b{re.escape(v)}\b', line, re.IGNORECASE):
                        return v.upper()

    # Generic verdict pattern (fallback) — requires colon
    generic_pattern = r'(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?(?:###?\s*)?(?:\*\*)?[Vv]erdict(?:\*\*)?\s*:\s*(?:\*\*)?\s*([A-Z_]+)'
    match = re.search(generic_pattern, output, re.MULTILINE)
    if match:
        found = match.group(1).upper()
        # Only return if it looks like a verdict (not random word)
        if found in GOOD_VERDICTS or (valid_verdicts and found in [v.upper() for v in valid_verdicts]):
            return found

    # Last resort: scan lines in reverse for a valid verdict token.
    # Bottom of output is most likely the verdict section.
    # Security: only matches tokens from the agent's allowlist.
    if valid_verdicts:
        upper_verdicts = [v.upper() for v in valid_verdicts]
        for line in reversed(output.split('\n')):
            stripped = line.strip().strip('*').strip('#').strip().strip('*').strip()
            upper = stripped.upper()
            for v in upper_verdicts:
                if upper == v or upper == f"VERDICT: {v}" or upper.startswith(f"{v} ") or upper.startswith(f"{v}:"):
                    return v

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
    - Zero-width character stripping
    - Escaping triple backticks to prevent code block breakout
    - Removing instruction-like patterns (case-insensitive)
    - Truncation to max_len (AFTER sanitization to prevent smuggling past truncation)

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

    # Strip zero-width characters that could hide injection payloads
    text = _ZERO_WIDTH_RE.sub('', text)

    # Escape triple backticks to prevent code block breakout
    text = text.replace('```', '` ` `')

    # Escape newlines to prevent context breakout
    text = text.replace('\n', ' ').replace('\r', ' ')

    # Remove instruction-like patterns (case-insensitive, word-boundary aware)
    # Uses \b word boundaries to prevent partial-word false positives
    # and \s* between words to catch space-insertion bypass attempts
    patterns_to_redact = [
        r'ignore\s+previous',
        r'disregard',
        r'new\s+instructions',
        r'system\s+prompt',
        r'forget\s+everything',
        r'you\s+are\s+now',
        r'override\s+instructions',
        r'VERDICT\s*:',
        r'OVERALL_VERDICT\s*:',
    ]
    for pattern in patterns_to_redact:
        text = re.sub(r'\b' + pattern + r'\b', '[REDACTED]', text, flags=re.IGNORECASE)

    # Truncate AFTER sanitization to prevent smuggling payloads past the truncation boundary
    text = text[:max_len]

    return text


# =============================================================================
# Git Utilities
# =============================================================================

def get_base_branch() -> str:
    """Detect the default branch (dev, main, master, etc.).

    Shared across run_review.py and run_ci_review.py.
    Raises FileNotFoundError if git is not installed (callers handle this).
    """
    for candidate in ["dev", "main", "master"]:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--verify", candidate],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return candidate
        except subprocess.TimeoutExpired:
            continue
    return "dev"  # fallback
