# PR Live Census Reconciliation R2

Date: 2026-09-09
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR-LIVE-CENSUS-RECONCILIATION]
Wave ID: pr-live-census-reconciliation-r2-2026-09-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: df973ff8454f8b8f67de3e82324d047da49a6a0b2592f23de82a23b0bea7237b
Purpose: Produce a fresh evidence-backed census of every currently open GitHub PR against exact current dev, determine independently whether each claimed task is satisfied and whether unique patch value remains, and advance queue truth without mutating any censused PR or source candidate.

## Scope

Read-only census of every live pre-existing open PR, exact current-dev patch/task reconciliation, and changes only to the five exact governance paths listed below.

Files and surfaces in scope:

- TASKS.md
- reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md
- reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_census.md
- reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json
- reports/deferred/non_blocking/pr-live-census-reconciliation-r2-2026-09-09_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-09-09 tracker sync note for wave `pr-live-census-reconciliation-r2-2026-09-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr-live-census-reconciliation-r2-2026-09-09_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Treat this external JSON WaveConfig as the operator stub and the builder-generated tracked Markdown as the sole canonical Phase A packet. Do not hand-author or revise the generated packet.
2. Preserve R1 as PHASE_A_REQUEST_CHANGES_CORRECTED_CONFIG_REQUIRED with no census implementation: exact worktree /private/tmp/WorkingRCX-source-pr-live-census-reconciliation-r1-Codex0909, bus .agent_bus-pr-live-census-reconciliation-r1-0909, reviewer job phase-a-r1-aa905a1e, and three builder-input findings covering exact path enumeration, carrier-lifecycle qualification, and nonexclusive taxonomy. R2 is a fresh builder reconstruction from the same exact #1277 merge; do not resume or edit R1.
3. From exact comparison commit ca1295cd8e7e9f13d4639735536d863e718fd760, query GitHub once for the complete open-PR set. The starting observation is PRs 1219, 1213, 1212, 1211, 1210, 1203, 1197, and 1196, but live results are authority and any difference must be recorded rather than forced to eight.
4. For every live pre-existing open PR, record number, title, URL, base branch, head branch, exact head SHA, update time, GitHub merge-state status, commit count, changed-file list, additions/deletions, and exact reproducible commands. Fetch or inspect refs read-only as needed; do not check out, rebase, push, comment, label, close, merge, approve, or otherwise mutate a censused PR.
5. Compare every PR head against exact current dev using commit ancestry, stable patch identity or reverse-apply/equivalent current-code evidence, and current file truth. Do not infer task completion from title, stale discussion, checks, or mergeability alone.
6. For each PR, record two independent axes. Task satisfaction must be exactly one of SATISFIED_ON_DEV, PARTIALLY_SATISFIED, UNSATISFIED, or TASK_UNVERIFIED. Patch uniqueness must be exactly one of NO_UNIQUE_PATCH, UNIQUE_HUNKS_REMAIN, or PATCH_UNVERIFIED. Then record successor handling as NO_PRESERVATION_NEEDED, PRESERVE_EXACT_RESIDUALS, RECONSTRUCT_FROM_EVIDENCE, or HOLD_UNVERIFIED. State exact reusable files or hunks and proof limits. PR 1219 remains reconstruction-only and must never be recommended for direct merge.
7. Explicitly determine whether PRs 1197 and 1196 contain still-unique never-behind, fast-forward-to-dev, or post-reentry pipeline value after later merged waves. Record which requirements current code already satisfies and which exact residual hunks, if any, require preservation or fresh reconstruction.
8. Write reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_census.md with an executive table, per-PR evidence, cross-PR overlap, task mappings, both classification axes, successor handling, preservation holds, exact commands, proof limits, and a final structured handoff for NEVER-BEHIND-FLEET-AUTHORITY. Do not execute or prescribe unsupported terminal action.
9. Synchronize TASKS without loss: mark urgent queue authority landed through PR 1277 at ca1295cd8e7e9f13d4639735536d863e718fd760; preserve R1 as stopped corrected-config evidence; make R2 the sole CURRENT item while active; make NEVER-BEHIND-FLEET-AUTHORITY the sole immediate NEXT item after landing; then retain PR disposition, fleet cleanup builder/apply, recovery R2, R3C6-R2, the PR1219 chain, Mu production, and every later TODO in the landed order.
10. At the end, re-query the open-PR number/head-SHA set once. Refresh any changed entry once and disclose drift; if exact identity still cannot be established, use TASK_UNVERIFIED and PATCH_UNVERIFIED with HOLD_UNVERIFIED instead of widening scope or blocking verified entries.
11. Land the governed R2 carrier normally through staged L4, independent Codex review, providerless commit, its own branch push and PR, required CI, review policy, merge, and cleanup. After landing, create a fresh narrow NEVER-BEHIND-FLEET-AUTHORITY WaveConfig only from the exact R2 merge and census handoff.

## Constraints

- Only the five exact scope paths may change; substantive changes are confined to TASKS.md and reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_census.md.
- Every pre-existing censused PR, its head branch, review threads, and source candidate are read-only. The only authorized remote mutation is the normal governed lifecycle of this same R2 carrier branch and PR after COMMIT_GO, including its post-merge cleanup.
- Do not import, cherry-pick, apply, copy, or edit code from any censused PR or preserved worktree. Identify valuable residuals by exact evidence for later reconstruction.
- Do not treat DIRTY status as proof that code is obsolete, and do not treat an old green check or matching title as proof that a task is satisfied.
- Do not inspect or inventory the WorkingRCX directory fleet in this wave; the dated 223-directory observation remains non-authoritative until FLEET-CLEANUP-BUILDER.
- Do not launch either stale combined 2026-08-21 PR/fleet config, and do not turn this census into never-behind preservation, PR disposition, or fleet cleanup.
- Every Phase A author/reviewer and Phase B implementer/reviewer remains foreground-only and single-agent: do not spawn or delegate to subagents, and do not call wait_agent, sleep, poll, or an equivalent wait surface. Perform bounded inspection and emit the required result in the same turn.
- Do not add non-occurring edge cases or speculative remediation. Fail uncertainty closed through the explicit UNVERIFIED/HOLD values and continue verified census work.
- Every model-bearing role and pager remains Codex gpt-5.6-sol ultra; commit remains providerless.

## Stop conditions

- Stop before launch unless source, target, and comparison authority are exact ca1295cd8e7e9f13d4639735536d863e718fd760, the R2 worktree and bus are fresh, every model-bearing role resolves to Codex, and commit is providerless.
- Stop if GitHub authentication or remote access prevents obtaining the complete open-PR number/head-SHA set; do not substitute the dated observation as live authority.
- Stop if producing the census requires mutating a pre-existing PR, source code, user WIP, or the WorkingRCX fleet.
- Do not stop or widen because one PR is hard to classify: assign both UNVERIFIED values and HOLD_UNVERIFIED with exact missing evidence, then continue.
- Stop as DEFECT if TASKS loses any queued or preserved obligation, places terminal action before never-behind preservation, recommends direct merge of PR 1219, or fails to preserve R1's stopped identity.

## Validation gates

- evidence_command: `gh pr list --state open --limit 100 --json number,title,url,headRefName,headRefOid,baseRefName,mergeStateStatus,updatedAt`

## Acceptance criteria

- Only the five explicitly enumerated scope paths change; no runtime, test, executor, configuration, censused PR/branch, source candidate, user worktree, or fleet mutation occurs, while the governed R2 carrier completes its normal pipeline lifecycle.
- The report names the exact action-time open-PR set and records metadata, current-dev divergence, changed files, patch/code overlap, task mapping, both orthogonal census axes, successor handling, exact residual value, preservation hold, reproducible commands, and proof limits for every entry.
- PRs 1197 and 1196 receive explicit current-code adjudication of never-behind, fast-forward-to-dev, and post-reentry claims; PR 1219 is explicitly reconstruction-only and not a direct-merge candidate.
- No PR is marked satisfied solely from title, merge status, discussion, or checks; uncertainty uses TASK_UNVERIFIED plus PATCH_UNVERIFIED plus HOLD_UNVERIFIED.
- TASKS records PR 1277 landed at ca1295cd8e7e9f13d4639735536d863e718fd760, R1 stopped at Phase A corrected-config-required, R2 sole CURRENT while active, and NEVER-BEHIND-FLEET-AUTHORITY sole immediate NEXT while preserving all later work.
- A bounded end-of-run re-query confirms or discloses open-set/head drift without mutating censused remote state or widening the wave.
- The packet is generated and locked by launch_wave.py, all roles remain Codex gpt-5.6-sol ultra, and staged L4, independent review, providerless commit, required checks, R2 carrier merge, and cleanup complete through the pipeline.

## Grounding / Authorization

- Task: [PR-LIVE-CENSUS-RECONCILIATION]; wave id `pr-live-census-reconciliation-r2-2026-09-09`.
- Governing packet: this file, `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md`.
- TASKS.md authority: the 2026-09-09 tracker sync note for wave `pr-live-census-reconciliation-r2-2026-09-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr-live-census-reconciliation-r2-2026-09-09

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr-live-census-reconciliation-r2-2026-09-09`
- Active packet: `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md`
- Indicator artifact: `reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md`
  - `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_census.md`
  - `reports/deferred/non_blocking/pr-live-census-reconciliation-r2-2026-09-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr-live-census-reconciliation-r2-2026-09-09`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr-live-census-reconciliation-r2-2026-09-09_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr-live-census-reconciliation-r2-2026-09-09 --output reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json.
- `target_gate_id`: G8.
- `evidence_command`: `gh pr list --state open --limit 100 --json number,title,url,headRefName,headRefOid,baseRefName,mergeStateStatus,updatedAt`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md. (2) Commit handoff carries 5 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md`, `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_census.md`, `reports/deferred/non_blocking/pr-live-census-reconciliation-r2-2026-09-09_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr-live-census-reconciliation-r2-2026-09-09.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr-live-census-reconciliation-r2-2026-09-09`
- Active packet: `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c7a6665f531fd86661136772e1adc078cf0b64f9cb3e9ede9284458298a5a21e`
- Indicator artifact: `reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json`
- Evidence command: `gh pr list --state open --limit 100 --json number,title,url,headRefName,headRefOid,baseRefName,mergeStateStatus,updatedAt`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md. (2) Commit handoff carries 5 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md`, `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_census.md`, `reports/deferred/non_blocking/pr-live-census-reconciliation-r2-2026-09-09_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_2026-09-09.md`
  - `reports/control_plane/pr-live-census-reconciliation-r2-2026-09-09_census.md`
  - `reports/deferred/non_blocking/pr-live-census-reconciliation-r2-2026-09-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr-live-census-reconciliation-r2-2026-09-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
