# PR 1219 P0IA Pre Review Candidate Authority 2026-08-20

Date: 2026-08-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IA-PRE-REVIEW-CANDIDATE-AUTHORITY]
Wave ID: roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20
Phase-A-Lock: LOCKED
Purpose: Land the smallest pipeline-native authority primitive that deterministically binds the complete staged candidate, literal comparison commit, exact allowlist, same-wave indicator, plan, phase, and review round before every Phase B reviewer starts. This packet fixes recurring review-entry failures without absorbing terminal-lifecycle, process-tree, INV-2, role/model, or deterministic carry-forward work.

## Scope

Fresh P0IA refresh lane at literal base and comparison authority 0b000e7bb14a09be8570e2a4e1a22fd56ee1d705 (PR #1222 P0IC2, current origin/dev at refresh construction). Exact scope is the shared candidate-authority builder, launcher integration, Phase B pre-review integration, focused tests, TASKS queue reconciliation, and same-wave generated governance artifacts only. The root WaveConfig is external launch input and is never candidate content.

Files and surfaces in scope:

- mu/tools/executors/candidate_authority.py (CREATE) -- implement literal-base inventory, exact allowlist staging, indicator collection, staged L4 enforcement, atomic bus-local authority receipts, and a verify-current CLI.
- mu/tools/executors/launch_wave.py (MODIFY) -- add validated structured comparison-commit, exact candidate-allowlist, pre-review-authority, and precommit-inventory fields plus an explicit prepare-review recovery entry point; preserve current simple configs.
- mu/tools/executors/phase_b_executor.py (MODIFY) -- invoke stable shared authority after each implementation or fix and immediately before initial, ordinary bridge, private-attribute, and re-entry reviewer Popen.
- mu/tests/tools/test_candidate_authority.py (CREATE) -- cover literal-base inventory, rename and deletion fidelity, untracked paths, exact staging, receipt binding, tamper rejection, and deterministic rerun.
- mu/tests/tools/test_launch_wave.py (MODIFY) -- cover new schema validation, bus-local authority-spec creation, prepare-review recovery refusal during active review, and compatibility for configs without the opt-in fields.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- prove every reviewer path requires a current candidate-bound receipt after the latest mutation and that stable canonical-root authority targets the candidate lane.
- TASKS.md (MODIFY THROUGH PIPELINE) -- start from P0IC2 merge blob 810755dc1d95df7bd468800b7ec9a8ab49f7391f (SHA-256 20b07420778307bd112383b852d0843f083789462e6d7d6a172a33578b13c95c), mark P0IC2 landed, keep P0IA first launchable, insert the already-configured Phase A line-reference guard after row 16, and preserve every other TODO as a 57-row canonical PROGRAM QUEUE.
- reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json (GENERATED BEFORE REVIEW) -- current-candidate indicator.
- reports/deferred/non_blocking/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave reviewer deferrals; its presence is admitted but its findings cannot widen or delay P0IA.
- TASKS.md -- tracker-sync authority. The 2026-08-20 tracker sync note for wave `roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Validate literal comparison commit 0b000e7bb14a09be8570e2a4e1a22fd56ee1d705 and normalize an exact repo-relative allowlist. Inventory tracked statuses with NUL-safe rename fidelity plus every non-ignored untracked path; reject, never hide or restore, every outside path.
2. Stage the exact allowed paths with deletion support, collect and stage the declared same-wave indicator, then recompute the complete literal-base inventory and require no unstaged allowed residue or non-ignored untracked residue.
3. Atomically write an ignored bus-local receipt bound to repository identity, wave id, literal base, sorted status inventory, allowlist hash, plan hash, phase and round, indicator hash, and staged binary-diff or index-tree hash. Any post-receipt candidate mutation invalidates review entry.
4. Add structured optional WaveConfig fields for comparison commit, candidate allowlist, pre-review authority requirement, and precommit inventory requirement. Fail closed on invalid commits, unsafe paths, duplicate paths, missing generated-governance paths, and mismatched indicator commands.
5. Reconcile TASKS.md through the implementer from exact P0IC2 merge 0b000e7bb14a09be8570e2a4e1a22fd56ee1d705, TASKS blob 810755dc1d95df7bd468800b7ec9a8ab49f7391f, SHA-256 20b07420778307bd112383b852d0843f083789462e6d7d6a172a33578b13c95c. Preserve the launcher's P0IA tracker note and unrelated historical evidence. Mark row 2 P0IC2 LANDED with PR #1222 and exact merge evidence; keep row 3 P0IA as the first NEXT/launchable row; preserve rows 3 through 16 in order; insert row 17 [PHASE-A-POST-REMEDIATION-LINE-REF-PREBRIDGE-GUARD] NEXT after [LAUNCH-WAVE-DETERMINISTIC-CANDIDATE-CARRY-FORWARD-BUILDER], explicitly runnable only after P5 and row 16 and nonblocking for the active landing chain; renumber former rows 17 through 55 to 18 through 56 without dropping, merging, or reordering them. The final PROGRAM QUEUE must contain exactly 57 sequential unique rows 0 through 56, with PIPELINE-FIX-61 at row 18 and MU-OPTIMIZATION-LAST at row 56.
6. Run the builder after the initial implementer and after every remediation, directly before each SDK, ordinary bridge, private-attribute, and re-entry reviewer subprocess. Emit reviewer-started only after authority succeeds.
7. Provide a canonical-root prepare-review mode for bounded recovery. It must use the same shared builder, refuse when a reviewer is already active, and never launch, commit, push, merge, restore, or silently unstage paths.
8. Bootstrap P0IA once through the ordinary operator-visible pipeline because the old canonical root has no safe pause or pre-review authority hook and cannot load the unmerged candidate code into its already-running Phase B process. Invoke launch_wave exactly once with --launch and never race it with a same-config rerun. The founder-authorized waiver covers only the expected absence of P0IA's not-yet-landed pre-review receipt/indicator transaction during P0IA SDK, bridge, fix, private-attribute, and re-entry reviews. It does not waive implementation review, exact scope, focused tests, commit-time indicator collection, staged L4 enforcement, providerless commit, CI, or merge. After P0IA merges, this waiver is forbidden for every successor.
9. Route implementation, review, pager, staging, commit, push, PR, CI, and merge through all-Codex pipeline roles and providerless commit execution. P0IA alone uses the predecessor catalog's Codex gpt-5.5/xhigh invocation because gpt-5.6-sol/ultra is unmerged P0R evidence; the immediately following P0IM packet upgrades the landed model catalog before P0IB.

## Constraints

- The only P0IA refresh starting and comparison commit is 0b000e7bb14a09be8570e2a4e1a22fd56ee1d705. The intended fresh lane is /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-refresh-20260821, its branch is jabramsja/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-refresh-2026-08-21, and the unique bus is .agent_bus-roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-refresh-20260821. The prior 20260820 P0IA worktree, branch, bus evidence, and preservation directories are read-only historical evidence and must not be resumed, rewritten, removed, staged, or committed.
- The exact literal-base candidate allowlist contains only TASKS.md; mu/tools/executors/candidate_authority.py; mu/tools/executors/launch_wave.py; mu/tools/executors/phase_b_executor.py; mu/tests/tools/test_candidate_authority.py; mu/tests/tools/test_launch_wave.py; mu/tests/tools/test_phase_b_executor.py; the same-wave generated packet; the same-wave indicator; and, only when produced by review, the exact same-wave deferred nonblocker report.
- The root WaveConfig is external launch input and is excluded from staging, candidate inventory, commit, PR, and merge.
- The exact P0IC2 TASKS blob and external prevention-wave configs are read-only launch evidence, never candidate content. Only TASKS.md may carry their reconciled queue truth; preservation files and root WaveConfigs must not be copied, staged, committed, or modified from the candidate lane.
- P0IA's one-time review-authority and predecessor-model bootstrap waiver is an explicit operator-visible exception, not proof that current automation is self-authoritative. It permits no concurrent launcher rerun, manual git add, index editing, patch application, commit, push, merge, or direct PR mutation.
- The prepare-review authority must run from landed canonical-root code against the target lane after P0IA. It must not load authority implementation from the candidate lane or depend on an already-active candidate executor.
- Implementation, review, and pager resolve to Codex through launch-owned role overrides. For P0IA only, the clean predecessor catalog supplies gpt-5.5/xhigh; P0IM owns the immediate gpt-5.6-sol/ultra catalog upgrade. Commit execution remains providerless.
- Do not modify executor_dispatch.py, commit_executor.py, recovery_gate.py, collector semantics, bridge supervisor, runtime, substrate, role/model configuration, receipts outside the new ignored authority receipt, or any terminal-lifecycle/INV-2 behavior. The existing deterministic carry-forward config remains a separate later queue item and is not edited, deleted, launched, or claimed by P0IA.
- Reviewer findings and edge cases outside the exact pre-review authority bootstrap are deferred and cannot delay P0IA.

## Stop conditions

- Halt before launch if the refresh lane is not fresh at 0b000e7bb14a09be8570e2a4e1a22fd56ee1d705, the refresh bus is not unique and idle, the prior 20260820 lane is being resumed, any model-bearing role is not Codex using the predecessor's gpt-5.5/xhigh catalog, or commit execution is provider-backed.
- After P0IA merges, halt every successor reviewer entry if the exact literal-base inventory, current indicator, staged L4 enforcement, or candidate-bound receipt is absent, stale, malformed, or admits an outside path. During P0IA only, apply the explicit review-authority waiver above and no broader waiver.
- Halt as NEEDS_RESCOPING if stable pre-review authority requires executing an unreviewed candidate authority module, changing dispatcher routing, or widening into P0IB precommit logic or P0T lifecycle/checker repairs.
- Do not mark P0IA complete or release P0IB until deterministic merge evidence exists.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_candidate_authority.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- Focused tests prove every post-P0IA Phase B reviewer path is mechanically preceded by one successful authority transaction over the latest candidate; no successor reviewer subprocess or reviewer-started event can occur with an absent or stale receipt. P0IA's own old-root reviews are the sole declared bootstrap waiver.
- Literal-base inventory includes tracked additions, modifications, deletions, renames, mode/type changes, symlink identity, and every non-ignored untracked path and rejects any path outside the exact allowlist.
- The same-wave packet, TASKS note, indicator, and optional exact deferred report are governed explicitly, while the external root config never enters candidate state.
- Candidate TASKS.md contains exactly 57 sequential unique PROGRAM QUEUE rows 0 through 56 before the non-launchable boundary: P0IC0, P0IC1, and P0IC2 carry exact LANDED evidence; P0IA is the first NEXT/launchable row followed by P0IM and P0IB; the full strict PR1219 chain and every existing TODO disposition remain; the deterministic carry-forward builder stays at row 16 after P5; the Phase A post-remediation line-reference guard is row 17 and explicitly nonblocking until row 16 lands; PIPELINE-FIX-61 is row 18; MU optimization remains last at row 56.
- Receipt tampering, candidate mutation, plan/wave/round mismatch, stale indicator, collector mismatch, invalid comparison commit, or incomplete staging fails closed before review.
- The normal post-P0IA path uses landed canonical-root authority without manual Git work and without relying on a candidate executor already being active.
- P0IA lands through all-Codex predecessor-catalog gpt-5.5/xhigh implementation, review, and pager roles with providerless commit; P0IM immediately upgrades the catalog, and all unrelated lifecycle, checker, partition, and nonblocker work remains deferred.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IA-PRE-REVIEW-CANDIDATE-AUTHORITY]; wave id `roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20`.
- Governing packet: this file, `reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md`.
- TASKS.md authority: the 2026-08-20 tracker sync note for wave `roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20` is canonical for this packet's L4 fields.
- Authorization: Founder authorized narrower packets when convergence fails, required deterministic launch-wave authority if needed, prohibited nonblockers from delaying landings, and required preservation rather than manual candidate manipulation.

FOUNDER_OVERRIDE:roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20`
- Active packet: `reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_candidate_authority.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/candidate_authority.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md`
  - `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20 --output reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_candidate_authority.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md. (2) Final pytest gate covered 10 pytest selector(s) across 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/candidate_authority.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md`, `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json`, `mu/tests/docs/test_growth_caps.py`.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20`
- Step-5e provenance: `already_recorded`
- Purpose: commit automation may bind the exact same-wave growth-cap governance file after Phase B review; first bumps require staged-index proof, while already-recorded reuse requires clean HEAD/index proof.
- Authorized generated governance path(s):
  - `mu/tests/docs/test_growth_caps.py`
- Scope binding: the path above is in scope only as the Step-5e same-wave growth-cap governance mutation or exact clean same-wave continuation evidence.
- Pre-review boundary: this block does not add the path to the locked Phase B/pre-review candidate allowlist and cannot authorize arbitrary implementation files.
- Acceptance binding: unsupported, malformed, outside-repo, dirty, wrong-wave, worktree-only, index/HEAD-mismatched, or provenance-free generated governance paths fail before supervisor.
<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20`
- Active packet: `reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6a64073f1f8b2b3c728bc1b2fff1496ccb00218dc46051929bee58d9136a6e41`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_candidate_authority.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md. (2) Final pytest gate covered 10 pytest selector(s) across 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/candidate_authority.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md`, `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json`, `mu/tests/docs/test_growth_caps.py`.
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/executors/candidate_authority.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20_2026-08-20.md`
  - `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ia-pre-review-candidate-authority-2026-08-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
