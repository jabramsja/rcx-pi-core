# Land the preserved prompt-checkout test with correctly scoped evidence on PR1332

Date: 2026-10-07
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-prompt-checkout-test-r2-2026-10-07
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: c44ada599799ceb4c56a39ec210e8d1d313340887265b2f59b2f15854d7a3c1e
Purpose: Carry the preserved, passing prompt-checkout test repair into existing PR1332 with accurate phase-scoped evidence. Keep fresh native review and final staged-candidate approval authoritative, then complete hooks, required CI and protected merge.

## Scope

Reuse one verified prompt-contract test repair; write fresh accurate evidence and native governance. The preserved bootstrap isolation commit, production code and executor behavior remain unchanged.

Files and surfaces in scope:

- mu/tests/tools/test_agent_prompt_contract_injection.py: make the stale-checkout assertion distinguish valid active-checkout injection, with deterministic nested/ordinary and stale-reference controls.
- TASKS.md, CHANGELOG.md, reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md, reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_implementation_evidence.json, reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json, optional native nonblocker report.
- mu/tests/docs/test_growth_caps.py only if generated mechanically by the native governance producer; no manual cap editing.
- reports/deferred/non_blocking/workingrcx-prompt-checkout-test-r2-2026-10-07_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-07 tracker sync note for wave `workingrcx-prompt-checkout-test-r2-2026-10-07` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/prompt-r1-preserved/preservation.json, /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/prompt-governance-approval-hold.json, and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/native-prompt-repair-launch.log. The preserved R1 candidate passed its test gate but its final approval stopped on outdated governance hashes. The terminal command output explicitly required a fresh wave after Phase A packet validation failed. Treat old packets, receipts, lifecycle claims and budgets as immutable historical evidence, never approval for this wave.
2. Verify the 74 restored files against the preservation manifest before using the selected test. Restore ONLY mu/tests/tools/test_agent_prompt_contract_injection.py through this native implementer from the snapshot's restored original-worktree path. Its verified SHA256 is 51c8c2eebc8796f372e34188c86172de919db747e19f009f38879aac8861f0e8. Do not copy the predecessor's TASKS, CHANGELOG, packet, evidence JSON, indicator, bus, index or administrative metadata into this checkout.
3. Before restoration, the new checkout must be on parent bed1639685bb62bfcbc64265aa837360296be280 and the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05. Remote PR1332 must still be d978fcff7b984b1739b3ae2ca88627276a16d5bc. Preserve the committed bootstrap isolation files and verify their hashes: test_mu_type.py 7e18fdba00fa23fdcbd2a0556ef77d34e40ad1f8301dde2854863843454d07da; test_stage0_vm_cutover.py 32c3349b6837ad90491cc0643a1393a49d3c202fc9551a6560839e83514b353f.
4. Read the restored test and shared_agent_utils.load_agent_prompt_with_contract. Retain the actual-checkout assertion, all nine agents, every original contract/read-only/in-band requirement, exactly one verified current-root injection, and stale-path checks on all remaining contract/template text. Preserve all 27 valid nested/ordinary/canonical combinations and 12 stale-reference controls. No production loader/template edits, assertion weakening, skips, cwd evasion, or hardcoded replacement checkout.
5. The original pre-repair failure and R1 passing run are historical evidence at /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/prompt-contract-reproduction and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z/prompt-checkout-phase-b-20261007T193923Z. They need not be rerun as deliberate red mutations. Run the declared five-module serial gate once after restoring the verified test. If the source changes for an accepted finding, rerun the affected proof and bind its exact new hash.
6. Write reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_implementation_evidence.json with phase-scoped source/test hashes, executed commands, result logs, parent/current commit identity, preservation provenance and explicit limits. Keep this evidence concise. Mutable TASKS, packet, tracker-note and indicator observations belong in a clearly named historical implementation_observation with timestamp and phase, if recorded at all; never label their implementation-time hashes as the final staged state or as remaining unchanged after native governance runs. The evidence file itself must not contain a self-hash.
7. Use the existing native finalization ownership: phase_b_executor stages its commit-ready packet status and invokes a fresh supervisor; commit_executor obtains fresh final approval and verifies the validated candidate before committing. Those native receipts bind the complete final staged package. The implementation evidence proves the exact test/source execution phase, not future governance bytes or approval. Do not assert that implementation-time governance hashes are current, demand a circular post-review rewrite, manufacture final bindings, or weaken any receipt/hash check. A real unexplained source or candidate mismatch remains a stop condition.
8. Native Phase A owns the packet; native governance owns tracker fields, indicator and any mechanical growth-cap update. Update only the existing row38 narrative and CHANGELOG within allowed scope to record R1's passing code review but terminal precommit hold and this fresh R2 continuation. Keep the earlier source evidence intact in recovery storage. Prior spent budgets and terminal receipts remain untouched.
9. Retain existing row40 as the precise automation owner for two observed issues: downstream governance changes outliving implementation-time observations, and a Phase B NEEDS_PHASE_B recovery retry entering Phase A and failing the native packet skeleton/status/authorization contract. Existing structured-result transport and missing raw-stream retention obligations remain. Do not modify executor, launcher, recovery, hook or review policy here; no new numbered prerequisite.
10. Use existing PR1332 only. Both parent bed1639685bb62bfcbc64265aa837360296be280 and this test repair must land through fresh native approval, hooks, required CI and protected merge. No replacement PR, force push, manual commit, skipped hook, administrative merge or reuse of predecessor approval.
11. Development stays local. New recovery evidence belongs under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/local-review-r3-20261007T161738Z on UUID-verified RCX Recovery 93064AFA-816D-43E3-BCC9-8A514F8F3D7D. The Crucial X10 Time Machine drive is separate. Preserve PRIMARY WIP; its latest verified snapshot is 7f27a69ac11933fa793a7a27054d4dd92feab6fb706bb4e2c41bf270d3a60b20 with 919 restored files. Deduplicated-store integration for existing automatic producers remains pending.
12. This auxiliary test repair does not produce a physical APPLY plan. Do not replay old retirement operations, remove preserved work, or resume paused PR1325. Keep PR1331/1330/1329 and all useful-work dispositions open. Report any task-ID-only postmerge APPLY-plan hold separately from actual merge and PRIMARY-sync evidence.

## Constraints

- Authorized control-surface L4_ENABLER under founder standing pipeline-bug-fix authorization and autonomous continuation. This repair must use the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR #1332; FOUNDER_OVERRIDE:workingrcx-prompt-checkout-test-r2-2026-10-07.
- Root authors config/tracking/diagnostics; native Phase A/B and commit actors own implementation, review, staging, push and merge. One mutation lane, configured Codex implementation/review roles, providerless commit.
- Fresh same-owner authority on a new local carrier at preserved parent bed1639685bb62bfcbc64265aa837360296be280. Restore only the manifest-verified test through the native implementer; no predecessor relaunch, packet rewrite, receipt/reset/reseal, consumed lifecycle retry or transfer of review approval.
- No production runtime/substrate, seed, prompt loader/template, executor/recovery/launcher, model defaults, branch protection, CI workflow/policy or OS hook edits. No assertion weakening or failure suppression; the negative stale-path control is required.
- Preserve PRIMARY WIP, all distinct unfinished work and recovery storage mappings. Pipeline deduplicated-store integration remains a separately owned automation obligation.
- No new numbered prerequisite and no blanket cleanup/useful-work completion claim. Existing PR1331/1330/1329 and PR1325 disposition obligations remain in the current queue.

## Stop conditions

- Stop on a parent/branch mismatch, unexpected remote PR1332 change before native push, concurrent ownership, changed restored-source hash, changed preserved isolation source, or an out-of-allowlist repair requirement.
- Stop on native authority rejection or exhausted recovery; preserve the new attempt and diagnose without bypass, budget reset, forced push or review replay.
- Do not claim merge, PRIMARY sync, retirement or useful-work completion without actual receipts. The known postmerge APPLY-plan ownership defect remains distinct from any proven merge.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_agent_prompt_contract_injection.py mu/tests/engine/test_mu_type.py mu/tests/l4_gates/test_stage0_vm_cutover.py mu/tests/l4_gates/test_trusted_mutation_removal_gate.py mu/tests/l4_gates/test_w3_crash_guards_gate.py --tb=short`

## Acceptance criteria

- The manifest-verified prompt repair is restored through the native implementer, its 27 valid-root and 12 negative controls remain, and the declared combined five-module gate passes freshly.
- Regression controls prove valid nested, ordinary and canonical current roots are accepted and injected stale foreign template/contract references still cause assertion failure.
- Only the scoped test and fresh governance/evidence differ from parent bed1639685bb62bfcbc64265aa837360296be280; the two committed isolation-test files and all production code remain unchanged.
- Implementation observations are explicitly phase-scoped; fresh native final approval owns the final staged-candidate binding, with no stale current-governance hash claims or weakened checks.
- Fresh native review, hooks, required GitHub CI and protected merge land the combined changes on existing PR1332, with truthful PRIMARY sync and remaining-work status.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-prompt-checkout-test-r2-2026-10-07`.
- Governing packet: this file, `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md`.
- TASKS.md authority: the 2026-10-07 tracker sync note for wave `workingrcx-prompt-checkout-test-r2-2026-10-07` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-prompt-checkout-test-r2-2026-10-07

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-prompt-checkout-test-r2-2026-10-07`
- Active packet: `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_agent_prompt_contract_injection.py`
  - `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md`
  - `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-prompt-checkout-test-r2-2026-10-07 --output reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_agent_prompt_contract_injection.py mu/tests/engine/test_mu_type.py mu/tests/l4_gates/test_stage0_vm_cutover.py mu/tests/l4_gates/test_trusted_mutation_removal_gate.py mu/tests/l4_gates/test_w3_crash_guards_gate.py --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_agent_prompt_contract_injection.py`, `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md`, `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-prompt-checkout-test-r2-2026-10-07.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-prompt-checkout-test-r2-2026-10-07`
- Active packet: `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8c8bafc4bfc24aa72ca0d13b853afe3babe3acaf0009f3f52f9685800ee60638`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_agent_prompt_contract_injection.py mu/tests/engine/test_mu_type.py mu/tests/l4_gates/test_stage0_vm_cutover.py mu/tests/l4_gates/test_trusted_mutation_removal_gate.py mu/tests/l4_gates/test_w3_crash_guards_gate.py --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_agent_prompt_contract_injection.py`, `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md`, `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_implementation_evidence.json`, `reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_agent_prompt_contract_injection.py`
  - `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_2026-10-07.md`
  - `reports/control_plane/workingrcx-prompt-checkout-test-r2-2026-10-07_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-prompt-checkout-test-r2-2026-10-07.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
