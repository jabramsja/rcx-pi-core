# PR 1219 P0IMRP Receipt Model Provenance Activation 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMRP-RECEIPT-MODEL-PROVENANCE-ACTIVATION-2026-08-22]
Wave ID: pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22
Phase-A-Lock: LOCKED
Purpose: From exact merged PR #1233 authority c0bcd910d5e835411b23ac56c830819356161a5b, exercise the landed P0IMRPA/P0IMRPAS/P0IMRPAT source through one fresh ordinary pipeline wave so it mints and verifies the first honest live candidate-authority reviewer launch-provenance receipt. Commit only the truthful PROGRAM QUEUE transition and standard same-wave governance; do not reopen the stopped P0IMRP candidate or absorb broader meta/pre-commit, commit-consumer, bot-remediation, model-default, inventory, runtime, or deferred work.

## Scope

Fresh activation lane at exact PR #1233 merge c0bcd910. Let the landed candidate-authority control path automatically mint and verify the first honest live new-schema phase_b-bridge_pre_review receipt. Modify only TASKS queue truth through the pipeline and generate the exact same-wave packet, indicator, and optional nonblocker report. Preserve every code/test byte, the stopped P0IMRP lane/bus, and all unrelated TODOs.

Files and surfaces in scope:

- TASKS.md (MODIFY THROUGH PIPELINE) -- refresh live dev truth to PR #1233 at c0bcd910d5e835411b23ac56c830819356161a5b; record that the combined merge contains P0IMRPA commit 7e95e66d plus P0IMRPAS and P0IMRPAT; mark row 11 LANDED and row 12 fresh activation CURRENT; leave P0IM nonlaunchable until exact activation merge; preserve the stopped old P0IMRP record and every unrelated row/TODO/order.
- .agent_bus-pr1219-p0imrp-receipt-model-provenance-activation-20260822/meta/candidate_authority_receipts/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22/phase_b-bridge_pre_review.json (LIVE BUS EVIDENCE, NOT CANDIDATE CONTENT) -- must be minted and verified by exact landed c0bcd910 source and retain truthful codex/gpt-5.5/xhigh launch provenance plus command/config identity.
- reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md (GENERATED) -- sole governing same-wave activation packet.
- reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json (GENERATED BEFORE REVIEW) -- exact same-wave current-candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave reviewer deferrals; nonblockers and edge cases cannot widen or delay activation.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from a fresh clean worktree, canonical branch, and unique namespaced bus whose HEAD and comparison commit are exact merged PR #1233 SHA c0bcd910d5e835411b23ac56c830819356161a5b. Use the clean detached source at that same SHA as launcher/executor authority.
2. Use the ordinary landed launcher, Phase A, candidate-authority preparation, and Phase B entry without importing candidate code into any trusted process. Permit exact landed source to mint the phase_b-bridge_pre_review receipt and immediately verify it against trusted launch metadata before reviewer execution.
3. Run the unchanged focused candidate-authority test module and verify-current against the exact fresh live receipt. Prove reviewer_agent codex, model gpt-5.5, effort xhigh, command_sha256, bridge_config_path, and bridge_config_sha256 are present and current without manually creating, rewriting, or copying a receipt.
4. Update only canonical queue truth: PR #1233/c0bcd910 landed the combined P0IMRPA/P0IMRPAS/P0IMRPAT history; fresh P0IMRP is current; P0IM remains serialized and nonlaunchable until exact fresh P0IMRP merge. Preserve all other TODOs and historical evidence.
5. Route independent review, providerless commit, push, PR, required CI, merge, exact origin/dev proof, and cleanup only through the pipeline.

## Constraints

- Exact PR #1233 merge c0bcd910d5e835411b23ac56c830819356161a5b is the hard dependency and must equal source HEAD, target HEAD before implementation, comparison_commit, and origin/dev immediately before launch.
- The comparison-relative candidate allowlist is only TASKS.md, the exact same-wave packet, the exact same-wave indicator, and only if generated the exact same-wave deferred nonblocker report. This external WaveConfig and all bus-local receipts are excluded from candidate content.
- Do not modify executor_common.py, candidate_authority.py, meta_bridge_supervisor.py, commit_executor.py, any test, launcher, Phase A/B, recovery, bridge adapter/client/config, executor config/default, role/pager topology, hook, runtime, substrate, seed, registry, or unrelated documentation.
- The broader meta/pre-commit receipt, commit Step-7 consumer, and bot-remediation provenance gaps are outside this canonical activation scope unless the live pipeline proves one is an actual blocker to this exact governance-only candidate. Do not preemptively fix those gaps; if one actively blocks landing, halt and create the minimum separate serialized packet rather than widening this candidate.
- Preserve the old unsuffixed P0IMRP worktree, branch, bus, ten-path staged candidate, Phase B round-two NO_GO state, and TASKS PRESERVED_RESCOPED_NOT_COMPLETE record unchanged. Do not resume, relaunch, copy, or treat any of them as authority.
- All model-bearing implementation/review roles and pager routing use Codex on the predecessor gpt-5.5/xhigh catalog. Commit execution remains providerless. No manual candidate edit, index mutation, receipt mint, commit, push, review-thread mutation, PR closure, merge, or gate bypass is authorized.

## Stop conditions

- Halt before launch unless origin/dev, clean detached launcher source, fresh target HEAD, and comparison_commit all equal exact c0bcd910d5e835411b23ac56c830819356161a5b; the canonical branch/worktree/bus identities are unique; roles/pager are Codex; and commit is providerless.
- Halt as DEFECT if exact landed source does not automatically mint the fresh phase_b-bridge_pre_review receipt with complete reviewer launch provenance or verify-current does not return current. Do not manually mint, patch, copy, downgrade, or self-attest the receipt.
- Halt as NEEDS_RESCOPING if landing requires any production/test change, any path outside the literal allowlist, or any change to the stopped lane. Preserve the fresh lane and create the minimum separate blocker packet if and only if the blocker is active.
- Halt if TASKS deletes, reorders, closes, or rewrites any unrelated queue/TODO/history item, fails to preserve the stopped P0IMRP record, or releases P0IM before exact activation merge.
- Do not claim activation complete or release P0IM until deterministic PR merge, exact merge SHA, origin/dev equality, and pipeline cleanup evidence exist.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`

## Acceptance criteria

- Before initial Phase B reviewer entry, exact landed c0bcd910 source mints the fresh bus-local phase_b-bridge_pre_review receipt and verify-current recomputes it as current against trusted launch metadata.
- The live receipt truthfully records reviewer_agent codex plus reviewer_launch_provenance version, selected_agent codex, model gpt-5.5, effort xhigh, command_sha256, bridge_config_path, and bridge_config_sha256; stripped, malformed, downgraded, or drifted provenance remains fail-closed under the unchanged landed tests.
- TASKS records PR #1233 at exact c0bcd910 as the combined P0IMRPA/P0IMRPAS/P0IMRPAT landing, marks row 11 LANDED and fresh activation row 12 CURRENT while in flight, keeps P0IM nonlaunchable until exact fresh P0IMRP merge, and preserves every unrelated row/TODO and the old stopped-lane record.
- The comparison-relative staged set contains only TASKS.md, the generated activation packet, the generated activation indicator, and only if needed the exact activation deferred nonblocker report. Every production and test file remains byte-identical to c0bcd910.
- The unchanged focused candidate-authority suite, exact live receipt verification, staged L4 gate, cached diff check, independent review, providerless commit, normal pre-push, required CI, merge, exact dev proof, and cleanup all pass.
- After deterministic activation merge, refreshed dev retains the landed provenance producer/verifier authority and P0IM becomes the next serialized launchable packet; no broader receipt/commit, model, inventory, runtime, or deferred work has entered this wave.

## Grounding / Authorization

- Task: [PR1219-P0IMRP-RECEIPT-MODEL-PROVENANCE-ACTIVATION-2026-08-22]; wave id `pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous narrow packets whenever a wave stops converging and prioritized landing valuable work over edge cases and nonblockers. PR #1233 landed the migration-safe provenance producer/verifier bootstrap; this fresh activation is the minimum canonical proof and queue transition before P0IM. Any newly demonstrated active blocker must be isolated rather than widening this wave.

FOUNDER_OVERRIDE:pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `bb9cf15b62f4ae1ef655ac9eb5298bbde50253276bd259c7bc00d1553a83bb3a`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
