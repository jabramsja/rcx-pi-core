# Pipeline Proof Hardening

Date: 2026-04-02
Status: ACTIVE
Phase-A-Lock: UNLOCKED
Task: [PIPELINE-PROOF-HARDENING]
Purpose: Harden the live Phase A/bridge/recovery proof surfaces so packet review stays bounded, Codex reviewer output is parsed correctly, and routed recovery proof does not collapse on wrapper noise.

## Scope

**Files in scope (write):**
- `mu/tools/executors/phase_a_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tools/runners/run_review.py`
- `mu/tools/agents/bridge_adapters.py`
- `mu/tools/agents/bridge_supervisor.py`
- `mu/tools/agents/templates/bridge_reviewer_prompt.txt`
- `mu/tools/agents/_contract_redteam.md`
- `mu/tools/agents/adversary_prompt.md`
- `mu/tools/agents/expert_prompt.md`
- `mu/tools/agents/grounding_prompt.md`
- `mu/tools/agents/structural_proof_prompt.md`
- `mu/tools/agents/verifier_prompt.md`
- `TASKS.md`
- `reports/control_plane/recovery_tier3_wiring_2026-04-01.md`

**Files in scope (tests/proof):**
- `mu/tests/tools/test_executor_dispatch.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tests/tools/test_agent_bridge_supervisor.py`
- `mu/tests/tools/test_agent_prompt_contract_injection.py`
- `mu/tests/tools/test_run_review.py`
- `reports/control_plane/recovery_tier3_recovery_probe_2026-04-02.md`

## Work Items

1. Detect Phase A stub packets structurally and defer SDK review until the bridge/implementer loop produces a real packet.
2. Preserve reviewer evidence fields (`class`, file/line refs, reproduce command, evidence result, status) into the Phase A implementer prompt so packet rewrites stay grounded in current code truth.
3. Add packet-review mode to the bridge supervisor so `--no-diff` packet reviews do not accidentally become broad design deliberations.
4. Normalize Codex `--json` reviewer output from `item.completed.agent_message.text` so bridge parsing sees the actual envelope text and can stop after the envelope.
5. Tighten reviewer contracts: bootstrap still required, but review stays repo-state read-only, uses current-checkout absolute paths, and SDK review runs in read-only plan permission mode.
6. Harden recovery proof surfaces: classify wrapped Phase A SDK timeouts as process timeouts, target the inner `agent_review` timeout knob, widen dangerous git push detection, and trim oversized diagnosis prompt blocks.
7. Sync `[RECOVERY-TIER3-WIRING]` tracker/packet truth to the already-landed code path uncovered by the live proof pass.

## Constraints

1. Control-surface only. No seed, kernel, Stage0, or JS runtime changes.
2. No repo-mutating review behavior. Reviewer-side fixes must preserve read-only repo-state semantics.
3. No new external dependencies for recovery hardening.
4. Keep changes bounded to packet review, reviewer I/O normalization, recovery classification, and tracker truth-sync.

## Stop Conditions

1. Stop if the bridge/supervisor path requires changing commit-receipt authority semantics.
2. Stop if recovery hardening would require new subprocess ownership outside the existing dispatcher boundary.
3. Stop if packet-review mode cannot stay narrow without weakening existing review guarantees.

## Acceptance Criteria

1. A stub Phase A packet is rejected/reworked before SDK review, and the same canonical packet path is reread on later rounds.
2. Bridge reviewer prompts can run bounded packet review with `--packet-review` and no git diff.
3. Codex JSON reviewer output is normalized into parseable envelope text.
4. Reviewer prompts and SDK review stay read-only with current-checkout path guidance.
5. Wrapped Phase A SDK timeout failures classify into routed recovery cleanly, and diagnosis prompts stay within prompt budget.
6. `[RECOVERY-TIER3-WIRING]` no longer appears as an active unfinished task while its tracker note and packet say landed.
7. Targeted dispatcher/recovery/bridge/docs tests pass.

## Grounding

- **Authorization:** founder-directed pipeline hardening on 2026-04-02 after live recovery/Phase A proof runs.
- **Supporting proof packet:** `reports/control_plane/recovery_tier3_recovery_probe_2026-04-02.md`.
- **Closed packet synced by this wave:** `reports/control_plane/recovery_tier3_wiring_2026-04-01.md`.
- **Parent context:** `[PIPELINE-RECOVERY]` remains open only for the learning-store follow-on.
