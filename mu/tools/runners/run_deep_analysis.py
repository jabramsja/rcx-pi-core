#!/usr/bin/env python3
"""
RCX Deep Analysis - Full-stack agent analysis for comprehensive codebase health.

This tool sends the full codebase to agents for DYNAMIC analysis - finding issues
that static tests miss (architectural drift, doc/code consistency, security issues
requiring reasoning).

Run monthly or before major releases. This is NOT for every push - that's what
audit_fast.sh and run_review.py are for.

Usage:
    python tools/run_deep_analysis.py
    python tools/run_deep_analysis.py --agents verifier,adversary  # subset
    python tools/run_deep_analysis.py --verbose  # show full agent output

Cost: FREE (runs locally via Claude Code Max subscription)
Time: ~5-10 minutes (agents run in parallel)
"""

import sys
import os
import re
import argparse
import asyncio
from pathlib import Path
from datetime import datetime

# Ensure we can import from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from claude_agent_sdk import query, ClaudeAgentOptions
from tools.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    GOOD_VERDICTS,
    build_sdk_options,
    extract_text_from_message,
    extract_verdict_secure,
    resolve_agent_model,
    validate_compliance,
)


# =============================================================================
# Analysis Prompts - What we ask each agent to analyze
# =============================================================================

ANALYSIS_PROMPTS = {
    "verifier": """You are analyzing the FULL RCX codebase for North Star drift and invariant violations.

**Scope:**
- Core code: rcx_pi/selfhost/*.py
- Seeds: mu/**/*.json
- Docs: STATUS.md, TASKS.md, mu/docs/core/*.md

**Your task:**
1. Read STATUS.md to understand current phase (L1/L2/L3) and claimed invariants
2. Read key docs in mu/docs/core/ for architectural claims
3. Sample core code in rcx_pi/selfhost/
4. Check: Do the docs match the implementation?

**Report format:**
```
## North Star Drift Analysis

### Claims Verified
- [claim]: [evidence from code]

### Claims Violated
- [claim]: [contradiction found]

### Verdict: ALIGNED | DRIFT_DETECTED
```

Focus on semantic drift, not style issues.""",

    "adversary": """You are a security adversary analyzing the FULL RCX codebase for cross-component vulnerabilities.

**Scope:**
- Execution: rcx_pi/selfhost/step_mu.py, rcx_pi/selfhost/eval_seed.py
- Seeds: mu/substrate/*.json, mu/closures/*.json
- Bridge: mu/bridge/*.json

**Your task:**
1. Trace how seeds are loaded and executed
2. Look for trust boundary violations between components
3. Check for injection points where untrusted data crosses into execution

**Report format:**
```
## Security Analysis

### Trust Boundaries Checked
- [boundary]: [status]

### Vulnerabilities Found
FINDING: [description]
FILE: [path]
SEVERITY: CRITICAL | HIGH | MEDIUM | LOW
ATTACK: [how to exploit]

### Verdict: SECURE | CONCERNS
```

Focus on architectural security, not code style.""",

    "grounding": """You are checking that ALL claims in RCX docs have corresponding tests.

**Scope:**
- Claims: STATUS.md, TASKS.md, mu/docs/core/*.md
- Tests: tests/**/*.py

**Your task:**
1. Extract claims from STATUS.md (phase claims, invariant claims)
2. Extract claims from mu/docs/core/ (architectural claims)
3. For each claim, find the grounding test
4. Report claims WITHOUT test coverage

**Report format:**
```
## Grounding Analysis

### Claims With Tests
- [claim] → [test file:function]

### Claims WITHOUT Tests (GAPS)
- [claim]: No test found

### Coverage: X/Y claims grounded
### Verdict: GROUNDED | GAPS_FOUND
```""",

    "structural-proof": """You are verifying that L1/L2/L3 self-hosting claims are still valid.

**Scope:**
- STATUS.md (current phase claims)
- rcx_pi/selfhost/*.py (implementation)
- mu/**/*.json (seed projections)

**Your task:**
1. Read STATUS.md for current L1/L2/L3 claims
2. Verify each claim against actual implementation
3. Check seed count claims, debt claims, parity claims

**Report format:**
```
## Structural Proof Analysis

### L1 Claims
- [claim]: VERIFIED | VIOLATED

### L2 Claims
- [claim]: VERIFIED | VIOLATED

### L3 Claims
- [claim]: VERIFIED | VIOLATED

### Verdict: VALID | INVALID
```""",

    "advisor": """You are a strategic advisor analyzing RCX codebase health and recommending next steps.

**Scope:**
- STATUS.md, TASKS.md (current state)
- Recent changes (git log)
- Debt markers in code

**Your task:**
1. Assess overall project health
2. Identify highest-priority issues
3. Recommend concrete next steps

**Report format:**
```
## Strategic Analysis

### Health Assessment
- Phase progress: [assessment]
- Debt status: [assessment]
- Test coverage: [assessment]

### Top 3 Priorities
1. [priority with rationale]
2. [priority with rationale]
3. [priority with rationale]

### Recommended Next Steps
1. [concrete action]
2. [concrete action]
3. [concrete action]

### Verdict: HEALTHY | NEEDS_ATTENTION | AT_RISK
```"""
}

DEFAULT_AGENTS = ["verifier", "adversary", "grounding", "structural-proof", "advisor"]

# GOOD_VERDICTS imported from shared_agent_utils


# =============================================================================
# Agent Runner
# =============================================================================

async def run_analysis_agent(
    agent_name: str,
    verbose: bool = False,
    model_override: str | None = None,
) -> dict:
    """Run a single analysis agent."""

    prompt = ANALYSIS_PROMPTS.get(agent_name)
    if not prompt:
        return {
            "agent": agent_name,
            "verdict": "ERROR",
            "error": f"Unknown agent: {agent_name}",
            "output": ""
        }

    print(f"  Running {agent_name}...", end=" ", flush=True)
    model_key = "deep_structural" if agent_name == "structural-proof" else f"deep_{agent_name}"
    agent_model = resolve_agent_model(model_key, model_override)

    result_text = ""
    fragments: list[str] = []
    try:
        async for message in query(
            prompt=prompt,
            options=build_sdk_options(
                ClaudeAgentOptions,
                allowed_tools=["Read", "Glob", "Grep"],  # No Bash for security
                max_turns=30,  # Allow thorough exploration
                model=agent_model,
                require_model_kwarg=True,
            ),
        ):
            extracted = extract_text_from_message(message)
            if extracted:
                fragments.append(extracted)
            if hasattr(message, 'result') and message.result:
                result_text = message.result
    except Exception as e:
        print(f"ERROR")
        return {
            "agent": agent_name,
            "verdict": "ERROR",
            "error": str(e),
            "output": ""
        }

    if not result_text and fragments:
        result_text = "\n".join(dict.fromkeys(fragments))

    # Extract verdict using shared secure parser (handles markdown formatting)
    deep_agent_key = "deep_structural" if agent_name == "structural-proof" else f"deep_{agent_name}"
    verdict = extract_verdict_secure(result_text, agent_name=deep_agent_key)

    status_icon = "✅" if verdict in GOOD_VERDICTS else "⚠️"
    print(f"{status_icon} {verdict}")

    # Optional compliance validation
    is_compliant = True
    compliance_error = ""
    if verbose:  # Only run compliance check in verbose mode to save time
        is_compliant, compliance_error, _ = validate_compliance(result_text, strict=False)
        if not is_compliant:
            print(f"    ⚠️ Compliance: {compliance_error[:50]}...")

    return {
        "agent": agent_name,
        "verdict": verdict,
        "output": result_text,
        "error": None,
        "is_compliant": is_compliant,
        "compliance_error": compliance_error
    }


async def run_deep_analysis(
    agents: list[str],
    verbose: bool = False,
    model_override: str | None = None,
) -> dict:
    """Run deep analysis with specified agents."""

    print(f"\n{'='*70}")
    print(f"  RCX DEEP ANALYSIS")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Agents: {', '.join(agents)}")
    print(f"{'='*70}\n")

    print("Running agents in parallel (this may take 5-10 minutes):\n")

    # Run all agents in parallel for faster execution
    tasks = [run_analysis_agent(agent, verbose, model_override=model_override) for agent in agents]
    results = await asyncio.gather(*tasks)

    return {
        "timestamp": datetime.now().isoformat(),
        "agents": agents,
        "results": results
    }


def print_synthesis(analysis: dict, verbose: bool = False):
    """Print synthesis summary."""

    print(f"\n{'═'*70}")
    print(f"  DEEP ANALYSIS SYNTHESIS")
    print(f"  {analysis['timestamp'][:19]}")
    print(f"{'═'*70}\n")

    print(f"  {'AGENT':<20} {'VERDICT':<20} {'STATUS'}")
    print(f"  {'-'*20} {'-'*20} {'-'*10}")

    all_good = True
    for result in analysis["results"]:
        agent = result["agent"]
        verdict = result["verdict"]

        if verdict in GOOD_VERDICTS:
            status = "✅ PASS"
        elif verdict == "ERROR":
            status = "❌ ERROR"
            all_good = False
        elif verdict == "UNKNOWN":
            status = "❓ UNKNOWN"
            all_good = False
        else:
            status = "⚠️  REVIEW"
            all_good = False

        print(f"  {agent:<20} {verdict:<20} {status}")

    print(f"\n{'═'*70}")
    if all_good:
        print(f"  ✅ OVERALL: CODEBASE HEALTHY")
    else:
        print(f"  ⚠️  OVERALL: REVIEW RECOMMENDED")
    print(f"{'═'*70}\n")

    if verbose:
        print("\n" + "="*70)
        print("DETAILED OUTPUT")
        print("="*70)
        for result in analysis["results"]:
            print(f"\n--- {result['agent'].upper()} ---\n")
            print(result.get("output", result.get("error", "No output")))


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="RCX Deep Analysis - Full-stack agent analysis"
    )
    parser.add_argument(
        "--agents", "-a",
        type=str,
        default=",".join(DEFAULT_AGENTS),
        help=f"Comma-separated agent list (default: {','.join(DEFAULT_AGENTS)})"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full agent output"
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List available agents and exit"
    )
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for deep-analysis agents (default uses per-agent policy)",
    )

    args = parser.parse_args()

    if args.list_agents:
        print("Available agents:")
        for name, prompt in ANALYSIS_PROMPTS.items():
            first_line = prompt.strip().split('\n')[0]
            print(f"  {name}: {first_line[:60]}...")
        return

    agents = [a.strip() for a in args.agents.split(",")]

    # Validate agents
    invalid = [a for a in agents if a not in ANALYSIS_PROMPTS]
    if invalid:
        print(f"Error: Unknown agents: {invalid}")
        print(f"Available: {list(ANALYSIS_PROMPTS.keys())}")
        sys.exit(1)

    analysis = await run_deep_analysis(
        agents,
        args.verbose,
        model_override=args.model,
    )
    print_synthesis(analysis, args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
