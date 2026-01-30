# Pre-v4.3 Agent Prompts Archive

**Archived:** 2026-01-29

These are the original agent prompt files before the v4.3 update was deployed.

## What Changed in v4.3

1. **Evidence requirements** - All verdicts now require code snippets, not just file:line
2. **Adversary A-K checklist** - 11 attack vectors with BLOCKED evidence requirement
3. **Expert M-N priority** - RCX-specific checks (M-N) now required, A-L advisory
4. **Structural-Proof A-F checklist** - Requires Bash execution evidence
5. **Grounding THEATER detection** - 17 red flag patterns for weak assertions
6. **Fuzzer priorities** - Reordered: roundtrip functions now #2
7. **Translator WHAT TO DETECT** - Added scope creep/deviation detection section

## Rollback Procedure

If v4.3 causes regressions:
```bash
# Copy pre-v4.3 files back
cp docs/agents/archive/pre-v4.3/*.md .claude/agents/

# Update AgentRig.v0.md history with rollback note
```

## Files

- adversary.md
- advisor.md
- expert.md
- fuzzer.md
- grounding.md
- structural-proof.md
- translator.md
- verifier.md
- visualizer.md
