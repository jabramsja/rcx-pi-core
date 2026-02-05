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

from claude_agent_sdk import query, ClaudeAgentOptions


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


# =============================================================================
# Compliance Validation
# =============================================================================

def validate_compliance(output: str) -> tuple[bool, str]:
    """Run compliance validation on skeptic output."""
    try:
        result = subprocess.run(
            ["python3", "tools/validate_agent_compliance.py", "--json", "--strict"],
            input=output,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0 and not result.stdout:
            return False, f"Validator crashed: {result.stderr}"

        metrics = json.loads(result.stdout)
        if not metrics.get("compliant", False):
            violations = metrics.get("violations", ["Unknown violation"])
            return False, "; ".join(violations[:3])

        return True, ""
    except Exception as e:
        return False, f"Validation error: {e}"


# =============================================================================
# Skeptic Runner
# =============================================================================

async def run_skeptic(
    agent_output: str,
    files: list[str],
    original_agent: str = "unknown"
) -> dict:
    """Run the skeptic agent to challenge an approval."""

    file_list = ", ".join(files)

    prompt = f"""{SKEPTIC_SYSTEM_PROMPT}

---

## Context

The **{original_agent}** agent reviewed these files: {file_list}

Their output was:
```
{agent_output[:4000]}
```

Now, read the actual files yourself and challenge this approval.
Look for what they might have missed.
"""

    result_text = ""

    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeAgentOptions(
                allowed_tools=["Read", "Grep", "Glob"],
                max_turns=20,
            )
        ):
            if hasattr(message, 'result') and message.result:
                result_text = message.result
    except Exception as e:
        result_text = f"Skeptic error: {e}"

    # Extract verdict
    verdict = "UNKNOWN"
    if "CONFIRMED" in result_text:
        verdict = "CONFIRMED"
    elif "OVERRIDE" in result_text:
        verdict = "OVERRIDE"
    elif "CONCERNS" in result_text:
        verdict = "CONCERNS"

    # Count high severity concerns
    high_severity = result_text.count("SEVERITY: HIGH")
    medium_severity = result_text.count("SEVERITY: MEDIUM")

    # Compliance check
    is_compliant, compliance_error = validate_compliance(result_text)

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
