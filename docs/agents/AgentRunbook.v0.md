<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-05
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: tests/docs/test_doc_contracts.py

This header enables automated doc drift detection.
- REFERENCE: Stable definitions, rarely changes
- DESIGN_SPEC: Architectural intent, may diverge from implementation
- IMPLEMENTATION: Active development, should match current code

If this doc's claims don't match reality, update the doc or fix the code.
Run: pytest tests/docs/test_doc_contracts.py -v
-->

# Agent Runbook v0

Purpose: practical instructions for running RCX agents via SDK runners.

**Quick Reference:** `./tools/agents.sh`

## Quick Start

```bash
# Full parallel review (recommended)
python tools/run_review.py rcx_pi/selfhost/ --depth full

# Quick review (4 agents)
python tools/run_review.py rcx_pi/selfhost/step_mu.py --depth quick

# PR review (auto-selects depth from diff)
python tools/run_review.py --pr

# Interactive session with follow-up
python tools/run_interactive.py adversary rcx_pi/selfhost/step_mu.py
```

## Orchestrators

| Command | Purpose | Agents |
|---------|---------|--------|
| `run_review.py --depth quick` | Fast review | 4: verifier, adversary, expert, structural-proof |
| `run_review.py --depth full` | Full review | 6: + grounding, fuzzer |
| `run_review.py --founder` | Founder review | 8: + translator, visualizer |
| `run_review.py --depth all` | Complete | 9: + advisor |
| `run_ci_review.py` | CI/CD | Auto-selects based on diff risk |
| `run_interactive.py` | Conversational | Single agent with follow-up |

## Individual Runners

All 9 agents have dedicated SDK runners with built-in compliance validation:

```bash
python tools/run_verifier.py <files>           # North Star compliance
python tools/run_adversary.py <files>          # Security/attack vectors
python tools/run_expert.py <files>             # Complexity review
python tools/run_structural_proof.py "claim"   # Verify structural claims
python tools/run_grounding.py <files>          # Test coverage
python tools/run_fuzzer.py <files>             # Property-based testing
python tools/run_translator.py <files>         # Plain English
python tools/run_visualizer.py <files>         # Mermaid diagrams
python tools/run_advisor.py "problem"          # Strategic advice
```

## Trigger Map (Which Agents to Run)

| Change Type | Recommended Depth |
|-------------|-------------------|
| Core logic (`rcx_pi/selfhost/`, `mu/`) | `--depth full` or `--founder` |
| Seed change (`mu/**/*.json`) | `--depth full` |
| Doc-only (`docs/`) | `--depth quick` |
| CI/tooling (`tools/`, `.github/`) | `--depth quick` |

## Compliance Validation

**All runners enforce `AgentGuardrails.v0.md`:**
- Every finding requires `FILE:LINE` + code snippet
- Fabrications are detected and blocked (code verified against actual files)
- Exit code 3 = compliance failure

**Validation is automatic** - built into every runner via `validate_agent_compliance.py --strict`.

## Rigorous Mode

For high-stakes changes, add `--rigorous` to challenge approvals:

```bash
python tools/run_review.py rcx_pi/selfhost/ --rigorous
```

**What it does:**
1. **Reasoning validation** (`validate_agent_reasoning.py`) - CHECKED/NOT_CHECKED sections required for approvals
2. **Skeptic challenge** (`run_skeptic.py`) - Spawns separate agent to challenge any APPROVE verdicts
3. Skeptic can OVERRIDE approvals if it finds issues the original agent missed

**Use for:** Security-sensitive code, major refactors, pre-release audits.

**Skeptic verdicts:**
- `CONFIRMED` - Approval stands, proceed with merge
- `CONCERNS` - Issues found, should address before merge
- `OVERRIDE` - Approval rejected, do not merge

## Decision Rules (Gates)

| Agent | Gate Type | Blocks Merge If |
|-------|-----------|-----------------|
| verifier | Hard | REQUEST_CHANGES or NEEDS_DISCUSSION |
| adversary | Hard | VULNERABLE |
| structural-proof | Hard | UNPROVEN or IMPOSSIBLE |
| expert | Soft | OVER_ENGINEERED (review recommended) |
| grounding | Hard | UNGROUNDED (claims need tests) |
| fuzzer | Hard | BROKEN |
| translator | Soft | DEVIATES (founder review) |
| visualizer | Soft | Red flags detected |
| advisor | None | Advisory only |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Pass |
| 1 | Fail (hard gate) |
| 2 | Warnings (soft gate) |
| 3 | Compliance failure |

## Interactive Mode

```bash
# Start session
python tools/run_interactive.py verifier rcx_pi/selfhost/

# Commands during session
/switch adversary    # Switch agent (keeps context)
/files               # Show files in scope
/add <file>          # Add file
/save                # Save session
/exit                # End session

# Resume later
python tools/run_interactive.py --list
python tools/run_interactive.py --resume <session_id>
```

## CI Integration

**GitHub Actions workflow:** `.github/workflows/agent-review.yml`

```bash
# Manual trigger
python tools/run_ci_review.py --pr-number 123 --post-comment

# Auto-trigger (uncomment in workflow)
# Runs on PR to rcx_pi/ or mu/
```

## Preflight

Before running agents:
```bash
PYTHONHASHSEED=0 ./tools/audit_fast.sh
```

## Agent Memory

Findings are automatically stored for regression tracking:

```bash
# View recent findings
python tools/agent_memory.py list

# View findings for a file
python tools/agent_memory.py list --file step_mu.py

# Check for regressions
python tools/agent_memory.py check-regressions

# Mark finding as fixed
python tools/agent_memory.py fix 42

# Clear old findings
python tools/agent_memory.py clear --days 30
```

**Memory is enabled by default.** The orchestrator:
- Stores each FINDING from agent output with file:line and severity
- Warns when reviewing files with previously-fixed issues
- Associates findings with PR numbers (`--pr-number 123`)

Disable with `--no-memory` if needed.

## Notes

- Orchestrators run agents **in parallel** for speed
- All agents load prompts from `tools/agents/*_prompt.md`
- Session transcripts persist in `.claude/sessions/`
- Findings persist in `.agent_memory/findings.json`
- See `docs/agents/AgentGuardrails.v0.md` for format requirements
- See `docs/agents/AgentRig.v0.md` for architecture and trust model
