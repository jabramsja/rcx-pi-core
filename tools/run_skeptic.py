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

import sys
import json
import subprocess
import asyncio
import argparse
from pathlib import Path

# Ensure tools directory is importable when run directly
_tools_dir = Path(__file__).parent
if str(_tools_dir.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent))

from claude_agent_sdk import query, ClaudeAgentOptions
from tools.shared_agent_utils import extract_text_from_message, sanitize_for_prompt, validate_compliance


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

# =============================================================================
# Skeptic Runner
# =============================================================================

async def run_skeptic(
    agent_output: str,
    files: list[str],
    original_agent: str = "unknown"
) -> dict:
    """Run the skeptic agent to challenge an approval."""

    # Security: Sanitize file list to prevent prompt injection via file paths
    safe_files = [f.replace('\n', '_').replace('\r', '_').replace('`', '_')[:100] for f in files]
    file_list = ", ".join(safe_files)

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

    result_text = ""
    fragments: list[str] = []

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob"],
                max_turns=20,
            )
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

    # Extract verdict using secure marker parsing (no substring matching)
    import re
    verdict = "UNKNOWN"

    # Look for explicit verdict markers only
    verdict_pattern = re.compile(
        r'(?:^|\n)\s*(?:[-*]\s+|\d+\.\s+)?(?:\*\*)?(?:Skeptic\s+)?[Vv][Ee][Rr][Dd][Ii][Cc][Tt](?:\*\*)?\s*:\s*(?:\*\*)?\s*([A-Z_]+)',
        re.MULTILINE
    )
    for match in verdict_pattern.finditer(result_text):
        found = match.group(1).upper()
        if found in {"CONFIRMED", "OVERRIDE", "CONCERNS"}:
            verdict = found
            break

    # Also check CHALLENGE_RESULT: marker (from validate_agent_reasoning)
    challenge_pattern = re.compile(
        r'CHALLENGE_RESULT[:\s]+(\w+)',
        re.IGNORECASE
    )
    challenge_match = challenge_pattern.search(result_text)
    if challenge_match and verdict == "UNKNOWN":
        found = challenge_match.group(1).upper()
        if found in {"CONFIRMED", "CONCERNS", "REJECTED"}:
            verdict = "OVERRIDE" if found == "REJECTED" else found

    # Count high severity concerns
    high_severity = result_text.count("SEVERITY: HIGH")
    medium_severity = result_text.count("SEVERITY: MEDIUM")

    # Compliance check (shared_agent_utils returns 3-tuple)
    is_compliant, compliance_error, _ = validate_compliance(result_text, json_output=True)

    return {
        "verdict": verdict,
        "high_severity_count": high_severity,
        "medium_severity_count": medium_severity,
        "is_compliant": is_compliant,
        "compliance_error": compliance_error,
        "output": result_text,
    }


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
