#!/usr/bin/env python3
"""
RCX Skeptic Agent - Challenges approval decisions.

This agent is spawned ONLY when another agent issues an APPROVE verdict.
Its job is to find what the approving agent might have missed.

The skeptic is NOT adversarial for the sake of it. It asks:
- Are the CHECKED items sufficient?
- Are the NOT_CHECKED items safe to skip?
- What edge cases weren't considered?

Usage:
    # Typically called by run_review.py --rigorous, not directly
    python tools/run_skeptic.py --agent-output output.txt --files file1.py file2.py

    # Or pipe agent output
    cat agent_output.txt | python tools/run_skeptic.py --files file1.py
"""

import re
import sys
import json
import asyncio
import argparse
from pathlib import Path

# Ensure repo root is on sys.path for direct script invocation
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent.parent))

from claude_agent_sdk import query, ClaudeAgentOptions
from tools.runners.agent_runner_common import sanitize_files
from tools.runners.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    build_sdk_options,
    extract_text_from_message,
    resolve_agent_model,
    sanitize_for_prompt,
    validate_compliance,
)


# =============================================================================
# Skeptic Prompt
# =============================================================================

SKEPTIC_SYSTEM_PROMPT = """You are the RCX SKEPTIC - a devil's advocate for code review approvals.

## Your Role

You are NOT trying to reject everything. You are trying to ensure the approval is WELL-REASONED.

When another agent says "APPROVE", your job is to ask:
1. What might they have MISSED?
2. What ASSUMPTIONS did they make?
3. What EDGE CASES weren't considered?
4. Is there anything SUSPICIOUS they didn't mention?

## MANDATORY: Verification Protocol

You MUST read the actual files and verify claims. Do not trust the approving agent's summary.

For every concern you raise:
```
CONCERN: [description]
FILE: /path/to/file.py
LINES: 123-127
CODE:
    [actual code from Read tool]
SEVERITY: HIGH | MEDIUM | LOW
VERIFIED: Yes
```

## Output Format

```
## Skeptic Review

**Original Verdict:** [what the agent approved]
**Skeptic Verdict:** CONFIRMED | CONCERNS | OVERRIDE

### What They Checked
[List what the approving agent claimed to check]

### What They Missed
[Your findings - things they should have checked but didn't]

### Concerns Raised
[Specific concerns with FILE:LINE evidence]

### Final Assessment
[Your recommendation]
```

## Verdicts

- **CONFIRMED**: The approval is solid. Proceed with merge.
- **CONCERNS**: Found issues that should be addressed. List them.
- **OVERRIDE**: The approval is flawed. Should NOT merge.

## Rules

1. Always read the actual files - don't trust summaries
2. Be SPECIFIC - vague concerns are useless
3. Cite FILE:LINE for every claim
4. HIGH severity = blocks merge, MEDIUM = should fix, LOW = nice to have
5. If you find nothing concerning, say CONFIRMED and move on
"""


# validate_compliance imported from shared_agent_utils


CONSOLIDATED_SKEPTIC_PROMPT = """You are the RCX SKEPTIC - a devil's advocate for code review approvals.

## Your Role

Multiple review agents have ALL approved the same set of files.
Your job is to challenge ALL of them in a single pass:
1. What might EACH agent have MISSED?
2. Did they make overlapping ASSUMPTIONS (groupthink)?
3. What EDGE CASES weren't considered by ANY agent?
4. Is there a GLOBAL blind spot across all reviews?

## MANDATORY: Verification Protocol

You MUST read the actual files and verify claims. Do not trust any agent's summary.

For every concern you raise:
```
AGENT: <agent_name or ALL>
CONCERN: [description]
FILE: /path/to/file.py
LINES: 123-127
CODE:
    [actual code from Read tool]
SEVERITY: HIGH | MEDIUM | LOW
VERIFIED: Yes
```

## Output Format

```
## Consolidated Skeptic Review

### Per-Agent Assessment

AGENT_VERDICT: <agent_name>: CONFIRMED | CONCERNS | OVERRIDE
[Repeat for each agent]

### Global Blind Spots
AGENT: ALL
[Any concerns that ALL agents missed — groupthink / convergence gaps]

### Concerns Raised
[Specific concerns with AGENT tag, FILE:LINE evidence]

### Final Assessment
OVERALL_VERDICT: CONFIRMED | CONCERNS | OVERRIDE
[Your recommendation]
```

## Verdicts

Per-agent:
- **CONFIRMED**: That agent's approval is solid.
- **CONCERNS**: That agent missed something. List it.
- **OVERRIDE**: That agent's approval is flawed.

Overall:
- **CONFIRMED**: All approvals stand. No blind spots.
- **CONCERNS**: Issues found but not blocking.
- **OVERRIDE**: Significant blind spot. Should NOT merge without addressing.

## Rules

1. Always read the actual files - don't trust summaries
2. Be SPECIFIC - vague concerns are useless
3. Tag EVERY concern with AGENT: <name> or AGENT: ALL
4. Cite FILE:LINE for every claim
5. HIGH severity = blocks merge, MEDIUM = should fix, LOW = nice to have
6. If you find nothing concerning, say CONFIRMED and move on
"""


# =============================================================================
# Verdict Parsing Helpers
# =============================================================================

def _extract_verdict(text: str) -> str:
    """Extract a single verdict from skeptic output using secure marker parsing."""
    verdict_pattern = re.compile(
        r'(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*)?(?:Skeptic\s+)?[Vv][Ee][Rr][Dd][Ii][Cc][Tt](?:\*\*)?\s*:\s*(?:\*\*)?\s*([A-Z_]+)',
        re.MULTILINE
    )
    for match in verdict_pattern.finditer(text):
        found = match.group(1).upper()
        if found in {"CONFIRMED", "OVERRIDE", "CONCERNS"}:
            return found

    # Also check CHALLENGE_RESULT: marker (from validate_agent_reasoning)
    challenge_pattern = re.compile(
        r'CHALLENGE_RESULT[:\s]+(\w+)',
        re.IGNORECASE
    )
    challenge_match = challenge_pattern.search(text)
    if challenge_match:
        found = challenge_match.group(1).upper()
        if found in {"CONFIRMED", "CONCERNS", "REJECTED"}:
            return "OVERRIDE" if found == "REJECTED" else found

    return "UNKNOWN"


def _extract_per_agent_verdicts(text: str, agent_names: list[str]) -> dict[str, str]:
    """Extract per-agent verdicts from consolidated skeptic output.

    Parses lines like: AGENT_VERDICT: verifier: CONFIRMED
    """
    verdicts = {}
    pattern = re.compile(
        r'AGENT_VERDICT\s*:\s*(\S+)\s*:\s*(CONFIRMED|CONCERNS|OVERRIDE)',
        re.IGNORECASE
    )
    for match in pattern.finditer(text):
        agent = match.group(1).lower().rstrip(':')
        verdict = match.group(2).upper()
        verdicts[agent] = verdict

    # Fill in missing agents: agents not explicitly evaluated by skeptic
    # default to UNKNOWN (fail-closed). Only explicit AGENT_VERDICT: CONFIRMED
    # counts as confirmation — silence is not approval.
    for name in agent_names:
        if name not in verdicts:
            verdicts[name] = "UNKNOWN"

    return verdicts


def _extract_global_concerns(text: str) -> list[str]:
    """Extract concerns tagged with AGENT: ALL."""
    concerns = []
    # Match AGENT: ALL blocks followed by CONCERN:
    pattern = re.compile(
        r'AGENT\s*:\s*ALL\s*\n\s*CONCERN\s*:\s*(.+?)(?=\nAGENT\s*:|$)',
        re.DOTALL | re.IGNORECASE
    )
    for match in pattern.finditer(text):
        concerns.append(match.group(1).strip()[:500])

    return concerns


def _validate_concern_tags(text: str, agent_names: list[str]) -> list[str]:
    """Flag CONCERN: blocks that lack a preceding AGENT: tag.

    Returns list of warning strings for untagged concerns.
    Untagged concerns degrade to warnings — they do NOT silently pass.

    Each CONCERN: must have an AGENT: tag in the same block (separated by
    blank lines). An AGENT: tag from a previous block does NOT carry over.
    """
    warnings = []
    valid_agents = {name.lower() for name in agent_names} | {"all"}

    # Split into blocks separated by blank lines
    # Each block should be self-contained: AGENT + CONCERN + evidence
    concern_pattern = re.compile(r'CONCERN\s*:\s*(.+)', re.IGNORECASE)
    agent_pattern = re.compile(r'AGENT\s*:\s*(\S+)', re.IGNORECASE)

    # Find all CONCERN: positions and look for AGENT: in the same block
    for match in concern_pattern.finditer(text):
        concern_pos = match.start()
        concern_text = match.group(1).strip()[:120]

        # Find the block boundary: look backward for a blank line or start of text
        block_start = text.rfind('\n\n', 0, concern_pos)
        block_start = block_start + 2 if block_start != -1 else 0

        # Search for AGENT: tag only within this block
        block_text = text[block_start:concern_pos]
        agent_matches = list(agent_pattern.finditer(block_text))

        if not agent_matches:
            warnings.append(f"UNTAGGED CONCERN (no AGENT: marker): {concern_text}")
        else:
            tagged_agent = agent_matches[-1].group(1).lower().rstrip(':')
            if tagged_agent not in valid_agents:
                warnings.append(
                    f"UNKNOWN AGENT '{tagged_agent}' on concern: {concern_text}"
                )

    return warnings


# =============================================================================
# Skeptic Runners
# =============================================================================

async def run_skeptic(
    agent_output: str,
    files: list[str],
    original_agent: str = "unknown",
    model_override: str | None = None,
) -> dict:
    """Run the skeptic agent to challenge a single agent's approval.

    Kept for backward compatibility (CLI usage, single-agent challenges).
    For multi-agent reviews, use run_consolidated_skeptic() instead.
    """

    file_list = ", ".join(sanitize_files(files, max_len=100))

    # Security: Sanitize agent output to prevent prompt injection
    safe_output = sanitize_for_prompt(agent_output)
    safe_agent = original_agent.replace('`', '').replace('\n', ' ')[:50]

    prompt = f"""{SKEPTIC_SYSTEM_PROMPT}

---

## Context

The **{safe_agent}** agent reviewed these files: {file_list}

Their output was:
```
{safe_output}
```

Now, read the actual files yourself and challenge this approval.
Look for what they might have missed.
"""

    result_text = await _run_skeptic_query(prompt, model_override=model_override)

    verdict = _extract_verdict(result_text)
    high_severity = result_text.count("SEVERITY: HIGH")
    medium_severity = result_text.count("SEVERITY: MEDIUM")
    is_compliant, compliance_error, _ = validate_compliance(result_text, json_output=True)

    return {
        "verdict": verdict,
        "high_severity_count": high_severity,
        "medium_severity_count": medium_severity,
        "is_compliant": is_compliant,
        "compliance_error": compliance_error,
        "output": result_text,
    }


async def run_consolidated_skeptic(
    agent_outputs: dict[str, str],
    files: list[str],
    model_override: str | None = None,
) -> dict:
    """Run a single skeptic session to challenge ALL approved agents at once.

    Args:
        agent_outputs: {agent_name: output_text} for each approved agent
        files: List of files that were reviewed

    Returns:
        {
            "verdict": overall verdict,
            "verdict_per_agent": {agent_name: verdict},
            "global_concerns": [concern strings],
            "high_severity_count": int,
            "medium_severity_count": int,
            "is_compliant": bool,
            "compliance_error": str,
            "output": raw text,
        }
    """
    file_list = ", ".join(sanitize_files(files, max_len=100))

    # Build labeled sections for each agent's output
    agent_sections = []
    for agent_name, output in agent_outputs.items():
        safe_name = agent_name.replace('`', '').replace('\n', ' ')[:50]
        safe_output = sanitize_for_prompt(output)
        agent_sections.append(
            f"### {safe_name}\n```\n{safe_output}\n```"
        )

    agents_block = "\n\n".join(agent_sections)
    agent_names = list(agent_outputs.keys())

    prompt = f"""{CONSOLIDATED_SKEPTIC_PROMPT}

---

## Context

The following agents reviewed these files: {file_list}

{agents_block}

Now, read the actual files yourself and challenge these approvals.
For each agent, issue AGENT_VERDICT: <name>: CONFIRMED|CONCERNS|OVERRIDE.
Tag every concern with AGENT: <name> or AGENT: ALL for global blind spots.
End with OVERALL_VERDICT: CONFIRMED|CONCERNS|OVERRIDE.
"""

    result_text = await _run_skeptic_query(prompt, model_override=model_override)

    # Parse structured output
    overall_verdict = "UNKNOWN"
    overall_match = re.search(
        r'OVERALL_VERDICT\s*:\s*(CONFIRMED|CONCERNS|OVERRIDE)',
        result_text, re.IGNORECASE
    )
    if overall_match:
        overall_verdict = overall_match.group(1).upper()
    else:
        overall_verdict = _extract_verdict(result_text)

    per_agent = _extract_per_agent_verdicts(result_text, agent_names)
    global_concerns = _extract_global_concerns(result_text)

    # Validate that all concerns have proper AGENT: tags
    untagged_warnings = _validate_concern_tags(result_text, agent_names)

    high_severity = result_text.count("SEVERITY: HIGH")
    medium_severity = result_text.count("SEVERITY: MEDIUM")
    is_compliant, compliance_error, _ = validate_compliance(result_text, json_output=True)

    return {
        "verdict": overall_verdict,
        "verdict_per_agent": per_agent,
        "global_concerns": global_concerns,
        "untagged_warnings": untagged_warnings,
        "high_severity_count": high_severity,
        "medium_severity_count": medium_severity,
        "is_compliant": is_compliant,
        "compliance_error": compliance_error,
        "output": result_text,
    }


async def _run_skeptic_query(prompt: str, model_override: str | None = None) -> str:
    """Shared query execution for both single and consolidated skeptic."""
    result_text = ""
    fragments: list[str] = []
    skeptic_model = resolve_agent_model("skeptic", model_override)

    try:
        async for message in query(
            prompt=prompt,
            options=build_sdk_options(
                ClaudeAgentOptions,
                allowed_tools=["Read", "Grep", "Glob"],
                max_turns=20,
                model=skeptic_model,
                require_model_kwarg=True,
            ),
        ):
            extracted = extract_text_from_message(message)
            if extracted:
                fragments.append(extracted)
            if hasattr(message, 'result') and message.result:
                result_text = message.result
    except Exception as e:
        result_text = f"Skeptic error: {e}"

    if not result_text and fragments:
        result_text = "\n".join(dict.fromkeys(fragments))

    return result_text


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="RCX Skeptic - Challenge approval decisions"
    )
    parser.add_argument(
        "--agent-output", "-a",
        type=Path,
        help="File containing the approving agent's output"
    )
    parser.add_argument(
        "--files", "-f",
        nargs="+",
        required=True,
        help="Files that were reviewed"
    )
    parser.add_argument(
        "--original-agent",
        default="unknown",
        help="Name of the agent being challenged"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for skeptic (default uses policy)",
    )

    args = parser.parse_args()

    # Read agent output
    if args.agent_output:
        agent_output = args.agent_output.read_text()
    else:
        agent_output = sys.stdin.read()

    print(f"🔍 Skeptic reviewing {args.original_agent}'s approval...")
    print("=" * 60)

    result = await run_skeptic(
        agent_output=agent_output,
        files=args.files,
        original_agent=args.original_agent,
        model_override=args.model,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["output"])
        print("=" * 60)

        if not result["is_compliant"]:
            print(f"\n⚠️ COMPLIANCE WARNING: {result['compliance_error']}")

        if result["verdict"] == "CONFIRMED":
            print("\n✅ SKEPTIC CONFIRMED - Approval stands")
        elif result["verdict"] == "OVERRIDE":
            print("\n❌ SKEPTIC OVERRIDE - Approval rejected")
            sys.exit(1)
        elif result["verdict"] == "CONCERNS":
            print(f"\n⚠️ SKEPTIC CONCERNS - {result['high_severity_count']} high, {result['medium_severity_count']} medium")
            if result["high_severity_count"] > 0:
                sys.exit(1)
            else:
                sys.exit(2)  # Warnings
        else:
            print("\n❓ SKEPTIC UNCLEAR - Manual review needed")
            sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
