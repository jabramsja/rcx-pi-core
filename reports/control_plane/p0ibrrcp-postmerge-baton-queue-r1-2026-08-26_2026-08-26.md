# P0IBRRCP Postmerge Baton Queue Authority R1 2026-08-26

Date: 2026-08-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [P0IBRRCP-POSTMERGE-BATON-QUEUE-R1]
Wave ID: p0ibrrcp-postmerge-baton-queue-r1-2026-08-26
Phase-A-Lock: LOCKED
Purpose: Make the providerless postmerge queue selector honor the existing unnumbered prerequisite and reconstruction batons before numbered PROGRAM QUEUE row 23, so the PR 1219 recovery landing chain advances in its declared order instead of publishing an unrelated cleanup wave.

## Scope

Recognize the two existing unnumbered baton forms within the PROGRAM QUEUE section, preserve their textual precedence and existing completion authority, prove exact-merge self-skip selects provider-isolation R3, and keep every numbered row and queued task intact.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py (MODIFY) -- recognize only bold Unnumbered prerequisite baton and Unnumbered reconstruction baton entries inside the PROGRAM QUEUE section; feed them through existing identity, WaveConfig, completion, and successor machinery in textual order; normalize the existing AFTER BOTH trailer without changing the wave identity.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py (MODIFY) -- add focused ordering and exact-merge successor regressions without adding a test file.
- TASKS.md (MODIFY) -- record this prerequisite current, provider-isolation R2 preserved, provider-isolation R3 next, then hybrid-reader, provider-neutral reconstruction, and numbered row 23; preserve all other tasks and all five TODO-bearing lines byte-for-byte.
- reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md (GENERATED) -- sole canonical same-wave packet.
- reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json (PHASE B GENERATED GOVERNANCE) -- same-wave indicator collected and staged before review.
- reports/deferred/non_blocking/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- same-wave nonblocking findings only.
- TASKS.md -- tracker-sync authority. The 2026-08-26 tracker sync note for wave `p0ibrrcp-postmerge-baton-queue-r1-2026-08-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Reconstruct only from exact origin/dev f0841a9738912784a3b6b2b06ef66aa592a51fa1. Do not copy, resume, cherry-pick, diff-apply, source, stage, or mutate provider-isolation R2 or any other preserved candidate.
2. Add section-bounded recognition for only the two explicit bold unnumbered baton forms already used by TASKS. Do not broaden prose parsing or alter numbered-row and routed-tracker recognition.
3. Preserve textual order by feeding recognized batons through the existing simple PROGRAM QUEUE identity, WaveConfig resolution, merge-history completion, and next-open selection machinery.
4. Treat the existing AFTER BOTH state trailer as metadata rather than part of provider-neutral wave identity. Do not add a new generic prose normalizer.
5. Prove an incomplete unnumbered chain is selected before numbered row 23, earlier completed batons are skipped in order, and exact queue_commit_sha authority skips this merged queue-fix baton and selects provider-isolation R3.
6. Update TASKS without adding, deleting, relabeling, or renumbering PROGRAM rows. Preserve every task, stopped-lane record, open-PR/worktree retirement item, and the five TODO-bearing lines byte-for-byte.
7. Run focused changed-file gates, staged L4 enforcement, pre-push-fast, required CI, fresh Codex review, providerless commit/push/PR, and merge.

## Constraints

- Functional scope is exactly commit_executor.py and the existing test_commit_executor_post_merge_cleanup.py. No launcher, dispatcher, Phase A/B executor, executor config, bridge config, pager, receiver, provider boundary, runtime, substrate, seed, host, Mu, Claude-owned, or new test file may change.
- Recognize only the two explicit unnumbered baton forms inside the PROGRAM QUEUE section. Do not parse arbitrary bold prose, notes, stopped-lane records, or content outside that section.
- Do not change numbered PROGRAM row syntax, numbering, precedence, routed tracker parsing, completion authority, dispatcher behavior, or postmerge request generation.
- Keep every live implementation, review, meta-review, pager, bot-remediation, and recovery role Codex. Commit execution remains providerless.
- Do not fix provider isolation, hybrid reader identity, provider-neutral bridge context, normal-exit cleanup, open PR disposition, worktree retirement, stale prose, spelling, or unrelated nonblockers in this packet.
- Use launch_wave.py and the immutable-source pipeline only. No manual candidate patch, staging, commit, push, PR, merge, or preserved-lane folding.

## Stop conditions

- Stop before launch if source HEAD, target HEAD, origin/dev, or comparison_commit differs from f0841a9738912784a3b6b2b06ef66aa592a51fa1; if source or target is dirty; if identity collides; if packet paths exceed bounds; or if any model-bearing role is not Codex or commit execution is provider-backed.
- Stop and preserve if any file outside the six-path allowlist must change or if a second packet alias appears.
- Stop and preserve if recognition cannot remain confined to the PROGRAM QUEUE section and the two explicit baton forms, or if any numbered row must be added or renumbered.
- Do not stop, widen, or remediate for unrelated parser prose, provider-boundary cleanup, receipt edge cases, stale docs, Ruff-only style, or any nonblocking edge case.
- If review repeats a structurally identical blocking finding or cannot converge inside the parser/test scope, preserve and split again through launch_wave.py; never recursively relaunch or mutate a stopped lane.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- Only the six allowlisted paths change; the optional nonblocker report is absent unless needed; exactly one canonical packet exists; no new test file is added; and test growth governance remains unchanged.
- Launch metadata proves implementer_agent=codex, reviewer_agent=codex, pager_route=codex, exact comparison commit, collision-free identity, all model-bearing executor/bridge backends Codex, and providerless commit execution.
- The PROGRAM QUEUE parser recognizes both explicit unnumbered baton forms only within the bounded section and preserves their textual order before numbered row 23.
- Existing completion and exact merge-history authority skip completed unnumbered batons without falsely completing later ones; AFTER BOTH is not included in provider-neutral identity.
- The exact-commit postmerge refresh proof skips the merged queue-fix baton and selects provider-isolation R3 rather than numbered row 23 even when the live tree is contradictory.
- TASKS records provider-isolation R2 as preserved, this prerequisite current, provider-isolation R3 next, hybrid-reader then provider-neutral reconstruction afterward, and numbered row 23 only after those prerequisites; every other task and exactly five TODO-bearing lines remain present.
- The exact evidence command, changed-file tests, staged L4 enforcement, pre-push-fast, required CI, and fresh Codex review pass without any model provider invocation.
- Providerless terminal execution, push, PR, and merge complete through the normal pipeline.

## Grounding / Authorization

- Task: [P0IBRRCP-POSTMERGE-BATON-QUEUE-R1]; wave id `p0ibrrcp-postmerge-baton-queue-r1-2026-08-26`.
- Governing packet: this file, `reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md`.
- TASKS.md authority: the 2026-08-26 tracker sync note for wave `p0ibrrcp-postmerge-baton-queue-r1-2026-08-26` is canonical for this packet's L4 fields.
- Authorization: The founder requires waves to land, every live model-bearing role to use Codex, candidates to enter through launch_wave.py, stopped evidence never to be lost, TASKS and TODO truth to remain synchronized, and active structural blockers to be split narrowly instead of recursing. This packet exists solely because fresh Codex review proved the current provider-isolation packet cannot repair postmerge queue authority within its locked scope.

FOUNDER_OVERRIDE:p0ibrrcp-postmerge-baton-queue-r1-2026-08-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `p0ibrrcp-postmerge-baton-queue-r1-2026-08-26`
- Active packet: `reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md`
- Indicator artifact: `reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md`
  - `reports/deferred/non_blocking/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `p0ibrrcp-postmerge-baton-queue-r1-2026-08-26`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id p0ibrrcp-postmerge-baton-queue-r1-2026-08-26 --output reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md`, `reports/deferred/non_blocking/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_bridge_nonblockers.md`, `reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `p0ibrrcp-postmerge-baton-queue-r1-2026-08-26`
- Active packet: `reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6fb65430e1862cfb2fa26c2824c0cdc39aa385a25c28dffcce829a2a6ba24eda`
- Indicator artifact: `reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md`, `reports/deferred/non_blocking/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_bridge_nonblockers.md`, `reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_2026-08-26.md`
  - `reports/deferred/non_blocking/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/p0ibrrcp-postmerge-baton-queue-r1-2026-08-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
