# Deferred Replay Hardening

Date: 2026-04-02
Parent task: `[DEFERRED-CONSOLIDATION]`
Lane: control-surface
Classification: MAINTENANCE
Status: LANDED

## Why This Slice Exists

The live E5/E6 deferred-consolidation replay still could not be completed honestly from the dirty control-plane lane. Before Phase B could rerun from a clean worktree, the replay exposed three control-plane gaps:

1. SDK review prompts/compliance were still permissive enough to allow malformed or off-repo review output to waste the hard gate.
2. Phase A packet-section detection and bridge prompting were too brittle around `Grounding / Authorization`.
3. Phase B replay-time review parsing and local pytest gating still had avoidable fail-closed rough edges.

This slice hardens those surfaces, replays the Phase A packet path end-to-end, and records the next honest blocker instead of pretending the E5/E6 wave itself is closed.

## Files Changed

- `mu/tools/agents/_contract_redteam.md`
- `mu/tools/executors/executor_dispatch.py`
- `mu/tools/executors/phase_a_executor.py`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/phase_b_implementer.py`
- `mu/tools/runners/run_review.py`
- `mu/tools/runners/shared_agent_utils.py`
- `mu/tools/runners/validate_agent_compliance.py`
- `mu/tests/tools/test_agent_prompt_contract_injection.py`
- `mu/tests/tools/test_executor_dispatch.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_run_review.py`
- `mu/tests/tools/test_validate_agent_compliance.py`

## What Landed

- Review contract/prompt hardening:
  - review outputs must stay self-contained in-band
  - external plan/report redirects and off-checkout paths are rejected
  - active repo root is injected into review prompts
  - strict compliance now requires `CHECKED`, `NOT_CHECKED`, and `VERDICT`
- Phase A packet-loop hardening:
  - `Grounding / Authorization` now satisfies the required grounding section
  - bridge prompts and implementer prompts use the same canonical section contract
  - mixed stdout+JSON Phase A outputs now still yield a plan path
- Phase B replay hardening:
  - bridge raw JSONL agent-message findings are parsed directly before rendered fallback
  - local pytest gates are bounded and scoped more tightly to newly changed fix-round tests
  - implementer zero-output hangs time out even when helper subprocesses keep the tree alive

## Replay Proof

Live replay run in dirty control-plane lane:

1. Phase A stub packet created.
2. Bridge round 1 rejected stub.
3. Implementer rewrote the same packet file.
4. Bridge round 2 rejected real packet on grounded content issues.
5. Implementer rewrote the same packet again.
6. Bridge round 3 returned `GO`.
7. Deferred SDK review ran on the refined packet and returned soft warnings only (`exit=2`).
8. Bridge round 4 consumed the SDK warning context and still returned `GO`.
9. Phase A locked the packet and chained automatically into Phase B.
10. Phase B then inherited the dirty control-plane baseline and started SDK review on unrelated dirty files plus `_pane_prci.sh`.

That final Phase B scope expansion is the next honest blocker for the E5/E6 wave in this lane. It is consistent with the locked packet's own requirement that Phase B execute from a fresh clean worktree. This slice does not claim to resolve that operational isolation requirement.

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_executor_dispatch.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_phase_b_executor.py -q --tb=short`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_run_review.py mu/tests/tools/test_validate_agent_compliance.py mu/tests/tools/test_agent_prompt_contract_injection.py -q --tb=short`

## Invariant Tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; control-surface only

## Next Step

Rerun the E5/E6 deferred-consolidation wave from a truly clean worktree on top of this slice. Do not continue that wave from a dirty control-plane lane, because Phase B intentionally preserves the dirty baseline and will review/package unrelated files.
