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

import json
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

# Patch SDK to handle rate_limit_event (CLI v2.1.45+ sends this but SDK
# v0.1.37 doesn't recognize it, crashing all agents with MessageParseError).
# Placed here so ALL runners get the fix (was previously only in run_review.py).
try:
    import claude_agent_sdk._internal.message_parser as _msg_parser
    import claude_agent_sdk._internal.client as _int_client
    from claude_agent_sdk.types import SystemMessage as _SystemMessage
    _original_parse = _msg_parser.parse_message

    def _patched_parse_message(data):
        if isinstance(data, dict) and data.get("type") == "rate_limit_event":
            return _SystemMessage(subtype="rate_limit_event", data=data)
        return _original_parse(data)

    _msg_parser.parse_message = _patched_parse_message
    _int_client.parse_message = _patched_parse_message
except Exception:
    pass  # If patching fails, fall through to original behavior


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

# Import canonical control-surface file set from single source of truth.
try:
    _checks_dir = str(Path(__file__).resolve().parent.parent / "checks")
    if _checks_dir not in sys.path:
        sys.path.insert(0, _checks_dir)
    from check_control_surface_invariants import (
        CONTROL_SURFACE_FILES,
        normalize_repo_relative_path,
    )
except ImportError:
    # Fallback: hardcoded set if checker not importable (should not happen in repo)
    CONTROL_SURFACE_FILES = frozenset({
        "mu/tools/executors/phase_b_executor.py",
        "mu/tools/executors/phase_b_implementer.py",
        "mu/tools/executors/commit_executor.py",
        "mu/tools/agents/meta_bridge_supervisor.py",
        "mu/tools/agents/meta_bridge_client.py",
    })

    def normalize_repo_relative_path(path: str) -> str:
        return path.replace("\\", "/").removeprefix("./")


def build_control_surface_context(files: list[str]) -> str:
    """Build control-surface review context if relevant files are in scope.

    Returns a prompt section with proof obligations for Phase B / commit
    authority chain files. Returns empty string for non-control-surface files.
    """
    normalized = {normalize_repo_relative_path(f) for f in files}
    if not normalized & CONTROL_SURFACE_FILES:
        return ""
    return """
---
CONTROL-SURFACE REVIEW MODE: These files are part of the Phase B / commit authority chain.
When reviewing, inspect these cross-file invariants:
1. Implementer must use bridge_adapters.run_adapter(), NOT bridge_supervisor review mode.
2. Bridge loop must re-invoke implementer on REQUEST_CHANGES/NO_GO. QUESTION must fail closed.
3. Receipt authority: use the canonical live chain only: mu/tools/agents/meta_bridge_supervisor.py::write_pre_commit_receipt() -> mu/tools/agents/meta_bridge_client.py::run_meta_bridge_package() -> mu/tools/executors/phase_b_executor.py::prepare_commit_handoff() -> mu/tools/executors/commit_executor.py verification. The returned receipt path must be the exact per-invocation artifact.
4. Canonical hook receipt must still be written by mu/tools/agents/meta_bridge_supervisor.py::write_pre_commit_receipt() while executor flow uses the per-invocation receipt. Do not substitute legacy/nonexistent aliases.
5. Protocol docs must not present manual git push/PR/merge as normal commit path.
6. Do NOT invoke live control-plane surfaces from Bash while reviewing.
   That includes Phase A/B executors, executor_dispatch, commit_executor,
   and meta_bridge_supervisor. Inspect them read-only or with focused tests only.
If any obligation is unverifiable, list it under NOT_CHECKED.
---"""

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
# Includes U+2028 (Line Separator), U+2029 (Paragraph Separator), VT (U+000B),
# FF (U+000C), and NEL (U+0085) which act as line separators in various contexts.
_ZERO_WIDTH_RE = re.compile(r'[\u000b\u000c\u0085\u200b\u200c\u200d\u2028\u2029\u2060\ufeff]')
_KEYWORD_CONFUSABLE_TRANSLATION = str.maketrans({
    "Α": "A",
    "А": "A",
    "Β": "B",
    "В": "B",
    "С": "C",
    "Ε": "E",
    "Е": "E",
    "Η": "H",
    "І": "I",
    "Ι": "I",
    "Κ": "K",
    "М": "M",
    "Ν": "N",
    "Ο": "O",
    "О": "O",
    "Ρ": "P",
    "Р": "P",
    "Ѕ": "S",
    "Τ": "T",
    "Т": "T",
    "Υ": "Y",
    "Χ": "X",
    "а": "a",
    "е": "e",
    "і": "i",
    "ј": "j",
    "ο": "o",
    "о": "o",
    "р": "p",
    "ѕ": "s",
    "с": "c",
    "х": "x",
    "у": "y",
})


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
    active_repo_root = Path.cwd().resolve()
    active_checkout_text = (
        "## Active Checkout (Injected)\n\n"
        f"- Current repo root for this run: `{active_repo_root}`\n"
        "- Keep all file reads, evidence, and absolute paths inside this checkout.\n"
        "- Return the full review in-band in the final response. Do not redirect to external plan/report files.\n"
    )
    return f"{contract_text}\n\n{active_checkout_text}\n---\n\n{prompt_text}"


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
    Calls tools/runners/validate_agent_compliance.py as a subprocess.

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

# Fenced code block pattern: ```<optional-lang>\n...\n```
# Must strip these before verdict extraction so that verdict-like tokens
# inside reviewed code samples cannot spoof the parser.
_FENCED_CODE_BLOCK_RE = re.compile(
    r'```[^\n]*\n.*?```',
    re.DOTALL,
)

def _strip_code_blocks(text: str) -> str:
    """Remove fenced and indented code blocks from text to prevent verdict spoofing.

    Agent output often quotes reviewed code that may contain verdict-like
    tokens (e.g., ``Verdict: APPROVE`` inside a code sample). Stripping
    code blocks before verdict extraction ensures only the agent's own
    prose is parsed.

    Handles both triple-backtick fenced blocks and CommonMark indented
    code blocks (lines indented 4+ spaces beyond the text's base indent).
    """
    text = _FENCED_CODE_BLOCK_RE.sub('', text)

    # Detect the base (minimum) indentation of non-blank lines.
    # Lines indented 4+ spaces beyond this base are CommonMark indented code.
    lines = text.split('\n')
    min_indent = None
    for line in lines:
        stripped = line.lstrip(' \t')
        if not stripped:
            continue
        indent = len(line) - len(stripped)
        if min_indent is None or indent < min_indent:
            min_indent = indent
    if min_indent is None:
        min_indent = 0

    threshold = min_indent + 4
    result_lines = []
    for line in lines:
        stripped = line.lstrip(' \t')
        if stripped:
            # Check if line uses tabs (any tab = code) or spaces beyond threshold
            leading = line[:len(line) - len(stripped)]
            if '\t' in leading and (len(line) - len(stripped)) > min_indent:
                result_lines.append('')
                continue
            indent = len(line) - len(stripped)
            if indent >= threshold:
                result_lines.append('')
                continue
        result_lines.append(line)
    return '\n'.join(result_lines)


def extract_verdict_secure(
    output: str,
    agent_name: Optional[str] = None,
    valid_verdicts: Optional[list[str]] = None
) -> str:
    """Extract verdict from agent output using secure marker parsing.

    Security: Strips fenced code blocks first, then looks for explicit
    VERDICT: markers to prevent spoofing via code samples or incidental
    mentions like "This code is NOT ROBUST".

    Args:
        output: Agent output text
        agent_name: Optional agent name to get valid verdicts from AGENT_VERDICTS
        valid_verdicts: Optional explicit list of valid verdicts

    Returns:
        Extracted verdict string, or "UNKNOWN" if not found
    """
    if not output:
        return "UNKNOWN"

    # Strip fenced code blocks so reviewed code cannot spoof verdicts.
    output = _strip_code_blocks(output)

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
        # LAST match wins — agents may revise verdicts during analysis.
        specific_pattern = rf'(?:^|\n)[^\n]*[Vv]erdict[^\n]*:\s*[^\n]*?\b({verdict_options})\b'
        matches = list(re.finditer(specific_pattern, output, re.MULTILINE | re.IGNORECASE))
        if matches:
            return matches[-1].group(1).upper()

        # Tier 2: Multi-line — "### Verdict" then next line "**TOKEN**" or "TOKEN"
        # LAST match wins.
        multiline_specific_pattern = rf'(?:^|\n)[^\n]*[Vv]erdict[^\n]*\n+\s*(?:\*\*)?({verdict_options})(?:\*\*)?\b'
        matches = list(re.finditer(multiline_specific_pattern, output, re.MULTILINE | re.IGNORECASE))
        if matches:
            return matches[-1].group(1).upper()

        # Tier 3: Bracket format — "### Verdict\n[TOKEN / TOKEN2 / ...]"
        # Agents produce this when prompts show options as [A / B / C]
        # LAST match wins.
        bracket_pattern = rf'(?:^|\n)[^\n]*[Vv]erdict[^\n]*\n+\s*\[\s*({verdict_options})\b'
        matches = list(re.finditer(bracket_pattern, output, re.MULTILINE | re.IGNORECASE))
        if matches:
            return matches[-1].group(1).upper()

    # Tier 4: Search lines near a "Verdict" header for embedded tokens.
    # Catches: "## Final Verdict\n\nAll claims are **VALID**."
    # Handles "Final Verdict", "L3 Verdict", etc. — any line containing "Verdict".
    # Security: only matches tokens from agent's allowlist as whole words.
    # LAST header wins — agents may revise verdicts during analysis.
    if valid_verdicts:
        verdict_headers = list(re.finditer(
            r'(?:^|\n)[^\n]*[Vv]erdict',
            output, re.MULTILINE,
        ))
        if verdict_headers:
            after_header = output[verdict_headers[-1].end():]
            lines_after = after_header.split('\n')[:8]
            for line in lines_after:
                for v in valid_verdicts:
                    if re.search(rf'\b{re.escape(v)}\b', line, re.IGNORECASE):
                        return v.upper()

    # Generic verdict pattern (fallback) — requires colon
    # LAST match wins.
    generic_pattern = r'(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?(?:###?\s*)?(?:\*\*)?[Vv]erdict(?:\*\*)?\s*:\s*(?:\*\*)?\s*([A-Z_]+)'
    generic_matches = list(re.finditer(generic_pattern, output, re.MULTILINE))
    if generic_matches:
        found = generic_matches[-1].group(1).upper()
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
    - Stripping zero-width and line-separator control chars (VT, FF, NEL,
      U+200B-U+200D, U+2028-U+2029, U+2060, U+FEFF)
    - Replacing newlines/carriage returns with spaces
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

    # Normalize a small set of visually confusable Greek/Cyrillic characters
    # before keyword redaction so VERDICT/instruction markers cannot hide in
    # mixed-script near-matches.
    text = text.translate(_KEYWORD_CONFUSABLE_TRANSLATION)

    # Strip zero-width characters that could hide injection payloads
    text = _ZERO_WIDTH_RE.sub('', text)

    # Escape triple backticks to prevent code block breakout
    text = text.replace('```', '` ` `')

    # Replace newlines/carriage returns (VT/FF/NEL handled by _ZERO_WIDTH_RE above)
    text = text.replace('\n', ' ').replace('\r', ' ')

    # Remove instruction-like patterns (case-insensitive, word-boundary aware)
    # Uses \b word boundaries to prevent partial-word false positives
    # and \s* between words to catch space-insertion bypass attempts
    # Word-bounded patterns (need \b on both sides to avoid partial matches)
    word_patterns = [
        r'ignore\s+previous',
        r'disregard',
        r'new\s+instructions',
        r'system\s+prompt',
        r'forget\s+everything',
        r'you\s+are\s+now',
        r'override\s+instructions',
    ]
    for pattern in word_patterns:
        text = re.sub(r'\b' + pattern + r'\b', '[REDACTED]', text, flags=re.IGNORECASE)

    # Verdict patterns: redact any visible marker occurrence, even if a removed
    # line-separator collapsed it into a larger token like prefixVERDICT:.
    verdict_patterns = [
        r'VERDICT\s*:',
        r'OVERALL_VERDICT\s*:',
    ]
    for pattern in verdict_patterns:
        text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)

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
