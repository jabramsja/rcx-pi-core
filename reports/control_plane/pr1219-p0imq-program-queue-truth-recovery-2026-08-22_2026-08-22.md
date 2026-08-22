# PR 1219 P0IMQ Program Queue Truth Recovery 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMQ-PROGRAM-QUEUE-TRUTH-RECOVERY]
Wave ID: pr1219-p0imq-program-queue-truth-recovery-2026-08-22
Phase-A-Lock: LOCKED
Purpose: From exact P0IX PR #1228 merge 1a18a2e3146c0f573e7c71fdb0a42ab0d3899300, repair only the stale operational PROGRAM QUEUE in TASKS.md so the commit-executor parser selects the new P0IMF launch-bound model-authority prerequisite instead of already-landed P0IAH. Preserve every existing TODO and its relative order, record exact P0IAH/P0IAR/P0IX landing truth, serialize P0IMF then P0IMRP before P0IM, and leave the terminal P0IM candidate untouched.

## Scope

One docs/queue-authority prerequisite between landed P0IX and P0IMF. Start and compare at exact P0IX merge 1a18a2e3146c0f573e7c71fdb0a42ab0d3899300. Modify only TASKS.md plus generated same-wave packet, indicator, and optional nonblocker report. Do not modify any Python, JSON model config, receipt schema, runtime, substrate, or preserved candidate.

Files and surfaces in scope:

- TASKS.md (MODIFY THROUGH PIPELINE) -- replace the stale top PROGRAM QUEUE baseline and row states with exact P0IX-era truth; retain every existing TODO and historical row exactly once in relative order; renumber the resulting 64 rows sequentially 0 through 63; make exact wave pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22 the sole first open row; place exact P0IMRP next; keep P0IM immediately after P0IMRP and nonlaunchable until exact P0IMRP merge.
- reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md (GENERATED) -- sole governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json (GENERATED BEFORE REVIEW) -- exact same-wave current-candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave deferrals only; nonblockers cannot delay P0IMQ.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imq-program-queue-truth-recovery-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Replace the stale PROGRAM QUEUE header and baseline paragraphs with exact origin/dev/P0IX truth. Record P0IAH landed through PR #1226 at 1a6c47371ec0b9829ea6023943d708dc573e3939, P0IAR through PR #1227 at 01e0cf774aef8ac1b272df24ad9ad159b9ec0a1a, and P0IX through PR #1228 at 1a18a2e3146c0f573e7c71fdb0a42ab0d3899300.
2. Treat P0IMQ as the current transition described in queue prose and the canonical tracker ledger, not as an open post-merge numbered row. Do not falsely mark it landed before merge.
3. Keep rows 0-5 as the existing landed P0IC0-P0IA history, change row 6 P0IAH to LANDED, insert row 7 P0IAR LANDED and row 8 P0IX LANDED, make row 9 exact [PR1219-P0IMF-LAUNCH-BOUND-MODEL-AUTHORITY-FREEZE-2026-08-22] NEXT, row 10 exact [PR1219-P0IMRP-RECEIPT-MODEL-PROVENANCE-2026-08-22] NEXT but blocked on P0IMF, row 11 P0IM QUEUED and explicitly nonlaunchable until exact P0IMRP merge, then retain P0IB and every prior row in unchanged relative order through MU-OPTIMIZATION-LAST at row 63.
4. Update only stale dependency wording needed to express P0IMF -> P0IMRP -> P0IM -> P0IB. Do not revise the substance, scope, priority, or disposition of any later TODO, deferred item, or legacy owner.
5. Mechanically prove the live commit-executor queue parser selects exact P0IMF and no landed P0IAH/P0IAR/P0IX row. Route review, providerless commit, CI, merge, and cleanup only through the pipeline.

## Constraints

- Exact P0IX PR #1228 merge 1a18a2e3146c0f573e7c71fdb0a42ab0d3899300 is the only start and comparison authority. Use a fresh unique lane and bus.
- The candidate allowlist is only TASKS.md, the generated same-wave packet, the generated same-wave indicator, and the optional exact same-wave deferred nonblocker report. This external WaveConfig is never candidate content.
- Do not modify executor code, bridge code, tests, model configuration, receipt schemas, runtime, substrate, reports outside exact same-wave generated artifacts, or any preserved P0IM/P0IX lane.
- Preserve all 60 prior PROGRAM QUEUE items exactly once in relative order; the only added numbered items are landed P0IAR, landed P0IX, pending P0IMF, and pending P0IMRP. The result is exactly 64 unique sequential rows numbered 0 through 63.
- All model-bearing roles and pager routing use Codex. Commit execution remains providerless. Nonblockers and edge cases cannot delay this exact queue repair.

## Stop conditions

- Halt before launch if origin/dev or HEAD differs from exact P0IX merge, the lane/bus is not fresh, any model-bearing role or pager is not Codex, or commit execution is provider-backed.
- Halt as NEEDS_RESCOPING if any file outside the exact allowlist must change, any prior TODO would be deleted/duplicated/reordered in substance, or the queue parser cannot select exact P0IMF from the staged TASKS document.
- Halt if the candidate claims P0IMQ already landed, marks P0IMRP launchable before P0IMF, marks P0IM launchable before P0IMRP, or alters the terminal preserved P0IM candidate.
- Do not release P0IMF until deterministic P0IMQ PR, merge SHA, origin/dev equality, and cleanup evidence exist.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imq-program-queue-truth-recovery-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`

## Acceptance criteria

- TASKS top baseline is exact P0IX-era truth and contains no statement that origin/dev is P0IA, P0IAH is open, or P0IM is waiting only on P0IAH.
- The PROGRAM QUEUE has exactly 64 unique sequential rows 0 through 63: prior rows preserved in relative order, P0IAH/P0IAR/P0IX landed, P0IMF first open, P0IMRP next and blocked on P0IMF, P0IM next and blocked on P0IMRP, P0IB after P0IM, and MU-OPTIMIZATION-LAST last.
- The live commit-executor parser returns wave_id pr1219-p0imf-launch-bound-model-authority-freeze-2026-08-22 as the first open queue entry.
- Only TASKS.md and exact generated same-wave governance artifacts change; staged L4 enforcement, independent review, providerless commit, CI, merge, exact dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMQ-PROGRAM-QUEUE-TRUTH-RECOVERY]; wave id `pr1219-p0imq-program-queue-truth-recovery-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imq-program-queue-truth-recovery-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous convergence, complete TASKS/TODO synchronization, preservation of valuable unmerged state, and narrower serialized packets whenever a wave stops converging. P0IM round 1 reproduced stale queue authority as a landing blocker; this is the minimum docs-only prerequisite.

FOUNDER_OVERRIDE:pr1219-p0imq-program-queue-truth-recovery-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imq-program-queue-truth-recovery-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imq-program-queue-truth-recovery-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imq-program-queue-truth-recovery-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imq-program-queue-truth-recovery-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imq-program-queue-truth-recovery-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `63f45275e41e69848f05eb1790ceeaf417190f827d2dc8514e38318453f7ad71`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imq-program-queue-truth-recovery-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/pr1219-p0imq-program-queue-truth-recovery-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imq-program-queue-truth-recovery-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
