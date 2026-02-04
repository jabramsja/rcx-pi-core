<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-02-04
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

Purpose: practical, minimal instructions for when and how to run RCX agents.

**Flow:** Preflight → Agents → Guardrail Validation → Merge

## Trigger Map (Which Agents to Run)

1. **Core logic change** (`rcx_pi/selfhost/`, `mu/`, `tests/structural/`)
   - Run: verifier, adversary, structural-proof, grounding, fuzzer, expert, translator, visualizer.
   - Advisor only if design trade-offs are unclear.

2. **Seed change only** (`mu/**/*.json`)
   - Run: verifier, adversary, structural-proof, grounding, fuzzer.
   - Translator if founder-facing intent needs confirmation.

3. **Doc-only change** (`docs/`, `roadmap/`)
   - Run: verifier + translator.
   - Expert only if architecture decisions change.

4. **CI / audit / tooling change** (`tools/`, `.github/`)
   - Run: verifier + adversary + expert.
   - Advisor optional for design trade-offs.

## Preflight (Always)

1. Run local checks:
```
PYTHONHASHSEED=0 ./tools/audit_fast.sh
```

2. Optional (once per environment):
```
python3 tools/check_agent_sdk.py
```

## Runner Matrix

**Dedicated SDK runners exist for:**
- `tools/run_verifier.py`
- `tools/run_adversary.py`
- `tools/run_expert.py`
- `tools/run_structural_proof.py`

**Other agents (grounding, fuzzer, translator, visualizer, advisor):**
- Run via Claude Code manual invocation.
- Reason: these agents benefit from interactive context and iterative refinement.
- Wrappers can be added if batch automation becomes needed.

## Guardrails (Non‑Negotiable)

- Every finding must include `FILE:LINE` + code snippet.
- Guardrail validation is enforced by:
  - `.claude/hooks/validate-agent-compliance.sh`
  - `tools/validate_agent_compliance.py --strict`

## Decision Rules (Gates)

1. **Verifier** = gate. Any FAIL blocks merge.
2. **Adversary** = security gate. Any SUCCEEDED attack blocks merge.
3. **Structural‑proof** = truth gate. Any UNPROVEN structural claim blocks merge.
4. **Grounding** = test gate. Any UNGROUNDED claim must be converted to tests.
5. **Fuzzer** = robustness gate. BROKEN/NOT_EXECUTED must be resolved.
6. **Visualizer** = soft gate by default.
   - Hard gate when changes touch normalization, Mu list/dict encoding, kernel/trace shapes.

## Storage (Optional, Recommended)

Persist findings for regression checks:
```
python3 tools/agent_memory.py store <agent> "<message>" --file <path> --severity <level>
python3 tools/agent_memory.py check-regressions
```

## Notes

- Use `docs/agents/AgentRig.v0.md` and `docs/agents/AgentGuardrails.v0.md` as the canonical spec.
- This runbook is the operational shortcut, not the authority.
