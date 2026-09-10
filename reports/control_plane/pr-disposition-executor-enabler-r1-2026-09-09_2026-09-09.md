# PR Disposition Executor Enabler R1

Date: 2026-09-09
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR-DISPOSITION-EXECUTION]
Wave ID: pr-disposition-executor-enabler-r1-2026-09-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 905ba880a591271054b3c8174c2a2be37e51ad50882342bf84a67e3e082e0fe6
Purpose: Land a narrow deterministic executor, exact target manifest, semantic verifier, and crash/restart tests required before the separate apply wave may close any of the eight stale PRs.

## Scope

Add only the fixed-set disposition executor, its focused tests, the exact target manifest, TASKS synchronization, and builder governance; do not close or otherwise mutate a PR in this enabler.

Files and surfaces in scope:

- TASKS.md
- mu/tools/executors/pr_disposition_executor.py
- mu/tests/tools/test_pr_disposition_executor.py
- reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md
- reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json
- reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json
- reports/deferred/non_blocking/pr-disposition-executor-enabler-r1-2026-09-09_bridge_nonblockers.md (optional only for a genuine nonblocker)
- TASKS.md -- tracker-sync authority. The 2026-09-09 tracker sync note for wave `pr-disposition-executor-enabler-r1-2026-09-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Preserve stopped broad R1 and R2 unchanged. R1 is at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-preservation/pr-disposition-execution-r1-phase-a-corrected-config-20260909 with packet SHA-256 576fed6403abb88622f5211ac67f16b5e0927eb402923caa1cfd30303379365a. R2 is at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-preservation/pr-disposition-execution-r2-phase-a-corrected-config-20260909 with packet SHA-256 6f014ac3d9a7625db7bf803489c3f25a5e126eea8ff1290821aef735d6922d98. Neither mutated a PR.
2. Generate the tracked self-hashed target manifest for repository nameWithOwner jabramsja/rcx-pi-core, repository ID R_kgDOQvy8bg, URL https://github.com/jabramsja/rcx-pi-core, and head repository ID R_kgDOQvy8bg owned by login jabramsja / owner ID MDQ6VXNlcjI3MjU3NDg3. Every target requires state OPEN, mergedAt null, and baseRefName dev.
3. Manifest targets are exact: #1219 node PR_kwDOQvy8bs74MpV0 branch jabramsja/roles-all-codex-current-dev-2026-07-29 head 28081acd74c549a7afd4292351b214228d45f451; #1213 node PR_kwDOQvy8bs7wx1P- branch jabramsja/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12 head 28b9beed3b8fbc793058446bf9854f363b82ead5; #1212 node PR_kwDOQvy8bs7wnEHo branch jabramsja/codex-reviewer-56sol-ultra-2026-07-11 head b6eb91a61439c2cb3a08f377d0d07a69546fd7db; #1211 node PR_kwDOQvy8bs7t2Sw3 branch jabramsja/never-behind-checkignore-fence-2026-07-04 head 10d157c4eb5b667b07006686fea86d88af268646.
4. Remaining exact targets: #1210 node PR_kwDOQvy8bs7t02-L branch jabramsja/never-behind-stash-ff-hold-surface-2026-07-04 head b846d2e93be9ffbd3e25b30c1b7983ceb52c4ae7; #1203 node PR_kwDOQvy8bs7tral- branch jabramsja/post-reentry-defer-not-loop-2026-07-03 head 4c466d1001b838e69ce141801fbbbe35f410d466; #1197 node PR_kwDOQvy8bs7tS-PM branch jabramsja/pager-route-claude-2026-07-01 head 02d6900ec39c3bd9da1e95e7cf0ae5507e4c7f92; #1196 node PR_kwDOQvy8bs7s8IjQ branch jabramsja/roles-claude-opus-2026-07-01 head 1131ae748dc373f0a96f0d0875a40d4e3ccc68ba.
5. Implement a fixed-set CLI with contract-check, apply, and verify modes. It must reject any repository or PR set beyond the literal eight and require the target manifest bytes to be committed in the supplied exact comparison ancestry before apply. contract-check and verify are nonmutating; this wave runs only contract-check and tests, never apply.
6. For future apply, bind_terminal_target_identity first, then atomically create and fsync a common-git-dir intent at rcx_pr_disposition_operations/<wave_id>/pr-<number>.json using exclusive creation. The intent must contain the exact repository/PR tuple, full target binding including operation ID, comparison commit, manifest hash, and PREPARED state before execute_terminal_mutation_once can consume authority.
7. The terminal callback itself must perform the authoritative gh repo and gh PR/node reads using the explicit repository, compare every immutable and expected-state field, durably advance the intent, and only then invoke one closePullRequest mutation addressed by the exact PR node ID. No pre-callback observation authorizes the mutation; no comment, merge, branch/ref deletion, push, or unrelated API write is allowed.
8. After the boundary returns, future apply rereads the exact remote object and writes an atomic self-hashed receipt. On process restart, any pre-existing intent without a valid receipt is never executed again in that wave: reconcile current remote state to CLOSED_RECONCILED when exact CLOSED/not-merged/head-preserved proof exists, otherwise emit a consumed-or-unknown HOLD. This deliberately conservative rule covers interruption before, during, or after authority consumption without private API access or retry.
9. Define complete statuses: CLOSED and CLOSED_RECONCILED require exact before/terminal-or-intent/after preservation proof; HOLD_REMOTE_DRIFT may record the actual drifted snapshot and consumed no-close outcome; HOLD_ACTION_OR_POSTVERIFY records consumed/ambiguous authority and observed state without retry; HOLD_SHARED_UNATTEMPTED covers remaining peers after a shared stop with no intent/action. Any HOLD makes PR-DISPOSITION-RECONCILIATION sole next before fleet cleanup.
10. Implement verify as a semantic fixed-set gate over exactly eight receipts: validate canonical self-hashes, repository and PR tuples, comparison/manifest identity, unique operation IDs and intent paths when present, allowed CLOSED/HOLD state machines, no merged/deleted/rewritten head claim, and batch completeness. Focused tests use temporary repositories and mocked gh/subprocess calls; they must prove callback-local revalidation ordering, durable intent-before-execute, no restart replay, drift and shared-stop receipts, closed reconciliation, tamper/duplicate/missing rejection, and no live network mutation.
11. Synchronize TASKS with #1279 LANDED at ac2d5d8e68cd124e6cd257445271538d3e8af36e, R1/R2 stopped preservation, this enabler CURRENT, PR-DISPOSITION-APPLY sole NEXT after its merge, then conditional reconciliation, fleet builder/apply, and every retained recovery/PR1219/later/Mu-production item. Preserve #1219/#1203 exact reconstruction and #1210/#1211 supersession evidence.
12. Stage only the six required paths plus an optional genuine nonblocker report; run focused tests and contract-check, independent Codex review, providerless commit, required CI, merge, and cleanup. Confirm all eight PRs remain OPEN throughout this enabler.

## Constraints

- Only the seven explicitly listed paths may change; six are required and the deferred nonblocker report is optional.
- No live apply, GitHub mutation, PR close/merge/comment/edit/label/review/lock, ref/branch/commit write, push, legacy-worktree mutation, or fleet-directory mutation is permitted in this enabler.
- All model-bearing roles and pager remain Codex gpt-5.6-sol ultra; commit remains providerless.
- Do not modify commit_executor.py: use only its public bind_terminal_target_identity and execute_terminal_mutation_once seams. Restart safety is conservative no-replay from the new tool's own durable pre-action intent.
- Do not add a generic arbitrary-repository/PR mutation surface, unrelated source fixes, speculative edge cases, recovery changes, fleet census, or Mu runtime work.
- Nonblocking wording or optional-report absence cannot delay landing.

## Stop conditions

- Stop implementation if the tool cannot express exact repository/PR-node/head identity validation inside the one-shot callback, durable intent before execute, and no-replay restart reconciliation using only the seven-path scope.
- Stop if any test or tool command would contact or mutate live GitHub in this enabler; all network behavior must be dependency-injected or subprocess-mocked.
- Stop if a callback can close by PR number alone, if intent is published after execute begins, if restart can invoke an existing intent again, or if verifier accepts a contradictory CLOSED/HOLD receipt.
- Do not stop for nonblocking style, a nonoccurring unrelated edge case, or the optional report being absent.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_pr_disposition_executor.py && python3 mu/tools/executors/pr_disposition_executor.py contract-check --manifest reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json`

## Acceptance criteria

- All seven allowed paths are explicit; exactly six required paths are staged unless a genuine optional report exists.
- The manifest self-hash and exact repository ID/name plus all eight PR node/base/head tuples validate under contract-check and cannot authorize any ninth or substituted target.
- Focused tests prove callback-local exact remote validation, pre-execute durable PR-to-operation intent, fixed-node close only, no-replay interruption recovery, complete CLOSED/HOLD semantics, semantic receipt verification, and zero live network mutation.
- TASKS records #1279 and stopped R1/R2 evidence, makes the enabler current and apply next, preserves all unique heads/later work, and retains conditional reconciliation ahead of fleet only when apply emits HOLD.
- Independent review and pre-commit return GO/COMMIT_GO, providerless commit and required CI pass, the enabler merges, carrier cleanup completes, and all eight legacy PRs remain open and unmodified.

## Grounding / Authorization

- Task: [PR-DISPOSITION-EXECUTION]; wave id `pr-disposition-executor-enabler-r1-2026-09-09`.
- Governing packet: this file, `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md`.
- TASKS.md authority: the 2026-09-09 tracker sync note for wave `pr-disposition-executor-enabler-r1-2026-09-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr-disposition-executor-enabler-r1-2026-09-09

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr-disposition-executor-enabler-r1-2026-09-09`
- Active packet: `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md`
- Indicator artifact: `reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pr_disposition_executor.py`
  - `mu/tools/executors/pr_disposition_executor.py`
  - `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md`
  - `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json`
  - `reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr-disposition-executor-enabler-r1-2026-09-09 --output reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_pr_disposition_executor.py && python3 mu/tools/executors/pr_disposition_executor.py contract-check --manifest reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pr_disposition_executor.py`, `mu/tools/executors/pr_disposition_executor.py`, `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md`, `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json`, `reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json`, `mu/tests/docs/test_growth_caps.py`.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr-disposition-executor-enabler-r1-2026-09-09.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `pr-disposition-executor-enabler-r1-2026-09-09`
- Step-5e provenance: `bumped`
- Purpose: commit automation may bind the exact same-wave growth-cap governance file after Phase B review; first bumps require staged-index proof, while already-recorded reuse requires clean HEAD/index proof.
- Authorized generated governance path(s):
  - `mu/tests/docs/test_growth_caps.py`
- Scope binding: the path above is in scope only as the Step-5e same-wave growth-cap governance mutation or exact clean same-wave continuation evidence.
- Pre-review boundary: this block does not add the path to the locked Phase B/pre-review candidate allowlist and cannot authorize arbitrary implementation files.
- Acceptance binding: unsupported, malformed, outside-repo, dirty, wrong-wave, worktree-only, index/HEAD-mismatched, or provenance-free generated governance paths fail before supervisor.
<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr-disposition-executor-enabler-r1-2026-09-09`
- Active packet: `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c51fba17550f7add6fe4734826cdb75232c420aebdbc53ed4bf7001852adab2f`
- Indicator artifact: `reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_pr_disposition_executor.py && python3 mu/tools/executors/pr_disposition_executor.py contract-check --manifest reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pr_disposition_executor.py`, `mu/tools/executors/pr_disposition_executor.py`, `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md`, `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json`, `reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json`, `mu/tests/docs/test_growth_caps.py`.
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_pr_disposition_executor.py`
  - `mu/tools/executors/pr_disposition_executor.py`
  - `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_2026-09-09.md`
  - `reports/control_plane/pr-disposition-executor-enabler-r1-2026-09-09_targets.json`
  - `reports/l4_wave_indicators/pr-disposition-executor-enabler-r1-2026-09-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
