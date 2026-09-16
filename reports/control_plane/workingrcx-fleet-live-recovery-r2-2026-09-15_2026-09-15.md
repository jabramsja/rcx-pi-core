# Complete saved-result truth check and land live fleet recovery

Date: 2026-09-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-fleet-live-recovery-r2-2026-09-15
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 3ebe2255b7cfec00121bb560ac87b97f78ee150d4120f10746490559e24f4062
Purpose: Continue the same bounded row39 live-cleanup repair from preserved R1, correct its reproduced saved-result false-success, and land it so the already queued unconsumed folder batches can run. No new queue item or wider lifecycle scope.

## Scope

Same four existing code/test files as narrow R1 plus native bookkeeping. Preserve its working recovery changes and fix only the demonstrated saved-result truth gap. No new counted file, cap change, lifecycle module or pipeline redesign. Existing row39 remains current; existing row40 follows actual eligible batches.

Files and surfaces in scope:

- TASKS.md -- Existing row39 current cleanup recovery; row40 broader lifecycle preserved and next after live batches; preserve all268task IDs and current todo agreement.
- CHANGELOG.md -- Only the demonstrated live-cleanup recovery changes and accurate validation/landing state.
- mu/tools/executors/commit_executor.py -- Only recorded-owner journal discovery and exact Git-versus-filesystem permission restoration needed by existing sync.
- mu/tools/executors/workingrcx_fleet_apply.py -- Exact native marker transition and Git-representable stash admission; supported original-owner recovery CLI under committed authority.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py -- Focused source23/peer-isolation/permission regressions inside the existing module; no lifecycle teardown redesign.
- mu/tests/tools/test_workingrcx_fleet_apply.py -- Existing transaction regressions plus supported recovery CLI admission, preservation and no-replay proof.
- reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md -- Full packet owned by native Phase A; operator provides this STUB only.
- reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json -- Native L4 indicator for the narrow live-cleanup recovery.
- reports/deferred/non_blocking/workingrcx-fleet-live-recovery-r2-2026-09-15_bridge_nonblockers.md -- Optional native-generated current review output only; no durable link or promise that an empty latest review retains this file.
- TASKS.md -- tracker-sync authority. The 2026-09-15 tracker sync note for wave `workingrcx-fleet-live-recovery-r2-2026-09-15` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Verify all29stopped R1 archive hashes and the retained raw index before reuse. Reuse only its four scoped code/test files and implement the unresolved saved-result correction below. Do not carry old packet/indicator/TASKS, old receipt authority or wider R4 source wholesale. Preserve every stopped worktree/index, prior claim, stash and candidate. The exact source is the manifest in progress_proof_before.
2. Resolve the exact live defects without broadening admission: compare stash content using only Git-representable regular-file modes while retaining exact saved filesystem modes; restore saved permissions only when content/index and the native Git-created mode are exact; ignore another canonical worktree's pending journal without mutating it; reconcile native behind-dev-marker removal against the already derived authorized prepared state.
3. Keep the existing R1 public --recover-sync CLI and its landed committed dependency, canonical native manifest, recorded owner, native idle, durable single-use claim and no-replay boundaries. Correct repeated saved-result observation so success cannot contradict the bound native outcome and retained WIP. Do not treat result.state as authority by itself. Validate against the native recovery evidence already bound by this command; inconsistent or ambiguous saved results must remain held/incomplete without mutation. Preserve existing successful repeat observations, original-owner sync and apply/verify contracts; no lifecycle import or new files.
4. Implement the EXACT rejected case, not a generic extra audit: using the existing pending_sync_case(overlap=True) fixture, initial recovery returns exit3/INCOMPLETE with tracked_wip_held_paths containing tracked. Change ONLY the saved fleet-recovery-result.json state to RECOVERED and invoke the same public CLI again. It must NOT return exit0/RECOVERED; it must not call native sync again or change the claim, journals, stashes, checkout/index or saved result while rejecting/holding the contradiction. Add this regression in the existing fleet-apply test module and prove the correction before claiming the prior supervisor veto resolved. No additional hypothetical permutation matrix is requested.
5. Reproduce source23's actual PREPARED or legacy HOLD stash-before-publication shape and five unrelated peers in disposable fixtures. Verify owner recovery restores distinct staged/unstaged bytes and0600 permissions, foreign journal and stash bytes remain unchanged during peer sync, real content/index/identity drift remains held, and the supported CLI rejects uncommitted authority or replay. Preserve original whole-transaction regressions.
6. Run inexpensive collection checks for the two separate validation groups before the exact declared chained evidence command. Do not export shared PYTEST_ADDOPTS --basetemp into nested pytest. Keep all docs in a separate process, rerun full docs after bookkeeping, and let all native final/receipt/commit gates execute. No new counted files means no cap bump is requested.
7. Keep current TASKS and todo truth aligned: existing row39 is this narrow repair followed immediately by compatible unconsumed batches3-14; row40's broader lifecycle/PR/late-stage recovery work remains preserved and queued afterward, before remaining Mu. Retain the three historical technical nonblockers in durable existing tracker/packet text without linking or claiming restoration of a generated active report that empty bridge findings clear. Phase A alone owns the full packet; maintain native locked-section grammar and truthful artifacts. Record the demonstrated R1 lost-feedback/no-implementation loop under the already queued row40 permanent late-stage owner; it is not another prerequisite for eligible cleanup.

## Constraints

- Only9listed paths, with4existing implementation/test files. Reuse the narrow R1 candidate, not the mixed R4 candidate; no new module, core doc, test file, growth cap, runtime/host/seed or Claude-owned edit.
- All LLM roles Codex gpt-6-astra/max; commit is providerless. All code, full packet, tests, review, commit and merge belong to the native pipeline/builders.
- No live cleanup, journal/claim/stash mutation before actual merge and PRIMARY sync. Tests use disposable fixtures. Never replay consumed1-2 or the23historical operations.
- Preserve all268unique task IDs, all stopped candidates and useful-work landing obligations. A true individual HOLD does not block unrelated eligible cleanup or Mu forever; evidence plus exact existing owner/next action are required.
- No extra queue row and no technical nonblocker/hypothetical hardening prerequisite. Broader permanent lifecycle controls remain owned by row40, not silently removed.
- The precise saved-result defect was reproduced by a native supervisor, not observed corruption of live folders. Do not mislabel it or use it to expand scope into unrelated failure permutations. Structural lost-feedback/no-fix reentry recurrence is retained under existing row40 after actual eligible cleanup.

## Stop conditions

- An actual mandatory out-of-scope dependency requires exact evidence before mutation; do not silently expand this narrow packet.
- On ambiguous original-owner state, preserve evidence and return an honest held/incomplete result; never force cleanup or claim backup equals integration.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- The reproduced held-WIP saved-result state flip cannot produce successful RECOVERED observation. Existing valid repeat-observation tests still pass, all observed recovery state remains bound to native evidence, and a rejected observation performs no replay or mutation.
- Disposable source23/peer, saved-permission and native-marker regressions pass, along with both full declared validation groups and native commit gates.
- The supported public recovery CLI uses exact landed authority and original-owner identity, preserves WIP/index/stashes, refuses replay, and leaves existing apply/verify behavior intact.
- No automatic lifecycle worker, PR lifecycle redesign, cap mechanism or unrelated pipeline repair enters this diff. Reviewed wider R4 work remains recoverable and queued.
- Current native packet/TASKS/CHANGELOG are truthful, all268task IDs survive, and no report restoration or durable generated-report link is claimed.
- Actual merge and PRIMARY sync authorize recovery and remaining eligible cleanup; no complete fleet or useful-hunk integration claim before observed outcomes.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-fleet-live-recovery-r2-2026-09-15`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md`.
- TASKS.md authority: the 2026-09-15 tracker sync note for wave `workingrcx-fleet-live-recovery-r2-2026-09-15` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-live-recovery-r2-2026-09-15

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-live-recovery-r2-2026-09-15`
- Active packet: `reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-live-recovery-r2-2026-09-15 --output reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md`, `reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-live-recovery-r2-2026-09-15.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-live-recovery-r2-2026-09-15`
- Active packet: `reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5d2883302db5fd5eb84833527da3952c2554ce8fdb05dc7dcfee868a7792b47b`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_workingrcx_fleet_apply.py mu/tests/tools/test_commit_executor_receipt.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md`, `reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `reports/control_plane/workingrcx-fleet-live-recovery-r2-2026-09-15_2026-09-15.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-live-recovery-r2-2026-09-15.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
