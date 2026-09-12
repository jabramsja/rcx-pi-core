# Reconcile Observed Fleet Apply Outcomes Without Replaying R1

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: f85fe0197d370925ed420d1f951305808450a06d5d75bb8e8211eb8f9a81d417
Purpose: Finish the existing bounded cleanup slot after its actual zero-move attempt: reconcile only three ownership-state HOLDs and one verified fast-forward preparation. Preserve the consumed R1 operation unchanged.

## Scope

Existing apply CLI/tests, deterministic follow-up plan and generated governance/tracker artifacts. Repair actual observed cleanup blockers, not general recovery or fleet management.

Files and surfaces in scope:

- mu/tools/executors/workingrcx_fleet_apply.py and mu/tests/tools/test_workingrcx_fleet_apply.py
- reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json
- TASKS.md, CHANGELOG.md and this wave's generated packet/indicator/optional nonblocker report
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Preserve exact landed classification/R1 plan authority. Reconciliation is limited to the same four original conditional candidates; all 407 others stay untouched HOLDs. Pin original operation root /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/fleet-apply-preserved-workingrcx-fleet-apply-r1-2026-09-11 and metadata hashes {"intent.json":"a5d34bc15ba7a3fb72d000e8fa80a94196fbe0610a7131a9fe11c9f7a7cc2ed8","plan.json":"8387fd46b515a0f939ca2c9a7b1438833584369dc2092babd172a8d67f6e1433","summary.json":"b1f786822c76da35b0f0de916dc71a6adf521489468c5c2ed38ea82f34de21f8","159/outcome.json":"b6b58ddc4a53471df915360657484cb1d64b5c9650c3304b0a84bc2ebaa23cbb","163/outcome.json":"afae12ffde80fffe4dd5d6397fd57d79feb63f91f2a573806a4f13f6d417c615","292/intent.json":"d2cb2d14de9ff97136ab8eaeb016a04b3be9ee872401b2557fe9ec81f43e6fde","292/outcome.json":"1826bbe3c8a512395330e0a1649f800891c3c74deb49ff288e0422c48f388873","292/preparation.json":"552b5d007a9f7c1df177464887a79cc3793cdd6ecbfa009c84d06ccd64fe374f","292/before.json":"444886f28e2b0a343f8ad77a8d9aaef9da6a278b2e7798591334c981c65a8fa5","292/gitdir-before.json":"be8ce4908ad9d009dff3abb6bd7110841a3590d25fba14523a08e6ab8a5b3671","305/outcome.json":"e47921523c305a56b27d16aa5d8410177608572814abd0e2b70a4465f5238271"}. Planning/evidence commands remain deterministic and non-mutating, including CI without host-local files; verify actual local receipts and preserved evidence before explicit postmerge execution.
2. Fix the reproduced mismatch narrowly: native_idle omits tier3_exhausted and tier3_short_circuited, which recovery_gate._finish_recovery_status emits with active=false and finished_at. These exact states occur on three targets; recorded owners were absent. Accept only coherent inactive finished records with no live owner/child or held lock, retaining TASKS protection and preservation checks. Unknown, contradictory or active state stays HOLD. Do not edit recovery_gate, target status files or old failed evidence.
3. Indices 159, 163 and 305 never began preparation and retain their recorded original HEADs. Index 292 has the immutable preparation record, original worktree/admin archives and history bundle; its HEAD was verified at a9e8d85a3d2f08b1a599c8f8ddecdc23f6ea38ec, exactly its recorded prepared head. Its original HEAD remains ba51ce3e32043fcc529a258ad967c0630a644425. All four R1 boundary fields are null, with no terminal identity, move-started record or destination. Reconcile these exact facts; preserve original provenance separately from proven prepared action-time HEAD. Contradictory evidence, drift, a started prior terminal action or unverifiable preservation stays HOLD.
4. Add the explicit bounded --reconcile-r1 planning mode named in evidence_command and its exact postmerge apply command. Give the follow-up a distinct fixed operation identity, immutable claim and new preservation destination. Original R1 mode, operation root, common-dir claim, packets, receipts, counters and archives remain unchanged and non-replayable. Reuse landed apply/terminal helpers; do not clone a general executor or create a generic retry framework.
5. The post-fast-forward refusal is process_idle's lsof predicate. R1 retained only a generic message; the original handle or warning is unknown. A later exact-target lsof probe returned 1 with empty stdout/stderr. Retain useful new diagnostic evidence without inventing the old cause. Bounded fresh read-only settling checks before binding may wait for quiescence, but never ignore a live handle, kill a process, clear metadata or reuse an old idle result as mutation authority.
6. Verify original source/admin archives, history and original-to-prepared transition before adopting the prepared target. Preserve current evidence before any further fast-forward, without overwriting R1 backups. Use strictly fast-forward-only preparation without losing ignored/untracked bytes or history; bind the exact final TARGET, not the carrier, and pass each actual move through execute_terminal_mutation_once with that invocation's fresh fetch and behind(origin/dev)=0. No removal, prune, reset, stash, force, branch deletion or terminal mutation outside that callback.
7. Disposable tests reproduce these actual terminal statuses and the exact no-terminal-action/prepared-head receipt shape; retain R1 replay refusal and four-target safety proofs. Cover contradictory/changed receipts, genuine active ownership, uncertain lsof, ignored evidence and fresh callback gating. Isolate Git configuration/maintenance; fixtures stay outside the fleet and arbitrary new .scratch descendants. No speculative compatibility matrix.
8. Land code before live follow-up. Keep TASKS/CHANGELOG honest: #1289 code landed, R1 moved nothing, reconciliation stays nested in the existing cleanup slot, and recovery R2/PR1219/Mu order is unchanged. Document the exact one-time postmerge command and outcome locations. Do not claim fleet-wide cleanup or add a precursor for a legitimately held target.

## Constraints

- Fresh carrier from exact PR #1289 merge only. Extend landed code, never stopped candidates. Do not copy/adopt stopped implementations or change preserved buses, packets, receipts or counters.
- No live fleet mutation during Phase A, implementation, review, tests or repeated evidence. Only merged reconciliation code may perform its one explicit bounded follow-up.
- No changes to census/classification artifacts or code, executor/dispatcher/launcher/recovery/terminal-boundary code, model defaults, Claude-owned files, runtime or Mu. Never rewrite the landed R1 plan or consumed operation metadata.
- Only the four original conditional identities may be reconciled with fresh safety proof. No census, promotion of 407 HOLDs, blanket terminal-state acceptance, generic retry surface or hypothetical hardening.
- All selected local roles remain Codex gpt-6-astra/max. Only the native pipeline refines, implements, stages, reviews, commits, pushes and merges. Keep this in the existing cleanup queue slot.

## Stop conditions

- Stop on changed source/receipt hashes, missing or contradictory old outcomes/preservation evidence, a started prior terminal action, or scope outside the closed allowlist.
- Individual unresolved protection, liveness, identity or preservation stays HOLD; never widen targets, edit evidence or force a move.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_apply.py --classification reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json --classification-sha256 19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf --classification-commit 23197ef9079ec47a022611dcc90fa848cbf4ee9f --reconcile-r1 --plan-output reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11 --wave-class L4_ENABLER`

## Acceptance criteria

- Focused tests and repeated non-mutating evidence pass; R1 remains non-replayable.
- The plan binds only four observed outcomes to a distinct one-shot follow-up and preserves old metadata plus all 407 other HOLDs.
- Coherent inactive terminal states are handled faithfully; any move still requires fresh protection/idle/preservation/identity/behind-zero callback checks.
- Trackers distinguish code landing from live outcomes; no extra program-queue item or false cleanup closure.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11

## Phase B Implementation Evidence

The existing apply CLI now has the fixed `--reconcile-r1` mode. Its generated
`workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json` retains all
411 original rows, the four observed outcomes and eleven pinned R1 metadata
hashes. Planning reads only the carrier's landed classification/R1 plan blobs;
local receipts and targets are checked only by explicit postmerge apply.

Reconciliation preserves original source identity separately from the admitted
action-time HEAD. It verifies R1's unchanged claim, exact receipt stages,
source/admin archives and branch-history bundle. Index 292 additionally requires
the recorded original-to-prepared transition and unchanged original ignored
evidence. New source/admin archives and history precede further fast-forward;
both old and new preservation are checked again inside the exact-target terminal
callback, along with fresh protection, ownership, process and content checks.
Only coherent inactive finished records for the two observed recovery states
are newly admitted. Fresh lsof stdout/stderr and timeout diagnostics are written
only to new local outcomes; no historical cause is inferred.

TASKS contains the exact one-time postmerge command, the distinct operation root
and common-directory claim, and the summary/per-target receipt locations. The
plan's `postmerge_command` records the same command. No live follow-up ran during
implementation. R1 remains consumed and unchanged, with zero moves; the 407
other HOLDs and downstream recovery R2/PR1219/Mu order remain unchanged.

The declared staged L4 gate currently refuses the empty implementation index:
`Cannot verify wave against empty change set.` Native staging, generated
indicator collection, staged revalidation, review and publication belong to the
outer pipeline. This packet's L4 fields derive from the same-wave 2026-09-11
tracker sync note in TASKS; no independent indicator measurements are claimed.

Final Phase B-local evidence: the declared pytest command passed **102 tests in
136.84 seconds**. The declared `--reconcile-r1` planning command passed repeatedly
with identical output and no fleet actions. The complete evidence command exited
1 only at the staged L4 check above. One added preservation regression initially
asserted against the boundary's generic `reason`; it now checks the detailed
`action_error` and the absence of a move-started receipt, and passes.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11 --output reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_apply.py --classification reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json --classification-sha256 19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf --classification-commit 23197ef9079ec47a022611dcc90fa848cbf4ee9f --reconcile-r1 --plan-output reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json`, `reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `fba76a7536e3f596b8f0b026df9510060d2be31698ccf12bd8f5a45bb0ff4bd8`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_apply.py --classification reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json --classification-sha256 19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf --classification-commit 23197ef9079ec47a022611dcc90fa848cbf4ee9f --reconcile-r1 --plan-output reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json`, `reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11_plan.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-apply-action-reconciliation-r2-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
