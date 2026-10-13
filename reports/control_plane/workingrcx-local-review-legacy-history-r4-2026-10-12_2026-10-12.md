# Reconcile carried growth-cap provenance under fresh native authority

Date: 2026-10-12
Status: Phase B (pre-supervisor pending, bridge-converged)
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-local-review-legacy-history-r4-2026-10-12
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 5f6b590dd0d01135de20f3bed64cf2ccdbcfffb544b2e3798b2ff6a59a6ca990
Purpose: Authorized control-surface L4_ENABLER with the same existing owner under existing row38/row40. Carry the preserved R3 recovery implementation and its new regression, reconcile inherited generated-governance bytes through the existing native recomputation, and obtain fresh validation, review and commit authority. The executor guard is correct and remains unchanged.

## Scope

Generated-governance provenance reconciliation and validation of the preserved local-review recovery implementation; all production executor/source guards are frozen.

Files and surfaces in scope:

- mu/tests/docs/test_growth_caps.py: materialize only the exact current-wave postimage derived by the existing native growth-cap recomputation. Keep inherited numerical cap values and unrelated comments/content unchanged.
- mu/tests/tools/test_commit_executor_local_review.py: validate the preserved prior-wave rejection/preservation/demotion regression; admit only directly necessary fixture corrections and a current-wave positive control. Retain all existing assertions and parameter coverage.
- All carried production executors, legacy history utility, history-recovery and validator test modules, receipt tests and prior governance remain byte-exact under the39protected hashes. Carry18verified candidate paths from the R3 interruption snapshot.
- TASKS.md, CHANGELOG.md and own R4 packet/evidence/indicator/optional advisory. Only the R4 indicator is newly collected; carried R2/R3 indicators are preserved historical artifacts, not active R4 indicators.
- reports/deferred/non_blocking/workingrcx-local-review-legacy-history-r4-2026-10-12_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-12 tracker sync note for wave `workingrcx-local-review-legacy-history-r4-2026-10-12` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Authorized same-owner L4_ENABLER under existing row38/row40 on existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05, exact parent e75ce9f7db3fd66cb240026e75f7066d68b9f6fc. FOUNDER_OVERRIDE:workingrcx-local-review-legacy-history-r4-2026-10-12. Root owns launch/tracker/recovery evidence; native actors own implementation/staging/commit/push/merge. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/local-review-legacy-history-r4-admission/initial-facts.json. Carry all18verified paths from snapshotdbe8e52e98c4fc3a0db22ed946a77a8e8d6446cf5173e400a1fbe2adb2de5674. Its197files and3258raw-index objects independently restored. No old bus, receipt, handoff, lifecycle, budget or checkpoint is reset or replayed.
2. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/legacy-history-r3-growth-cap-blocker.json, local-review-legacy-history-r3-terminal-observation.json, legacy-history-r3-scope-stop-correction.json and legacy-history-r3-native-continuation-admission.json. R3 had two Phase B COMMIT_GO receipts, then failed settle_commit_generated_governance before git_commit. Its first delegate made no edits; a retry reproduced the guard. The second delegate added an admitted local-review regression. Root interrupted it after wrongly inferring a disallowed target; that operator error is explicitly corrected. There was no proven scope violation. Native post_commit_admitted=false and phase_b_admitted=false. Preserve the interrupted state and distinguish earlier gates from the unvalidated added test.
3. Reproduce the growth-cap mismatch using the existing read-only HEAD/index authority capture and plan computation in commit_executor.py. Lines20136-20144 derive current-wave provenance from HEAD and indexed new paths; lines20657-20660 correctly reject a candidate that is neither exact HEAD preimage nor exact recomputed current-wave postimage in both index and worktree. The inherited cap file is numerically correct at CAP_TEST_FILES175 and CAP_TOOL_SCRIPTS64, but its two new provenance suffixes name R2. Record actual old/current-wave byte hashes and numerical values. No executor ordering, recomputation or guard defect was established.
4. This Phase B scope explicitly admits the generated-governance correction that the prior narrow hybrid delegate could not perform. Use the existing native recomputation to derive the ENTIRE exact postimage for this R4 wave from the unchanged HEAD and indexed candidate. Materialize those derived bytes only in the cap worktree file. Preserve the original R2-provenance file through the verified snapshot. Keep numerical caps and unrelated content unchanged; do not manually increase caps, accept a prior-wave postimage, loosen the guard or edit production code. Do not self-stage: outer native staging synchronizes the index. A temporarily different index/worktree during implementation is not final indexed authority.
5. Front-load validation of test_prior_wave_growth_cap_rejection_preserves_candidate_and_demotes_retry, added by native impl-83ab891b and preserved unvalidated at source SHA2563d99cc35a09ff49222c689bc55117ff1f034bf359c29502260ae04698727876c. It must retain rejection of prior-wave generated bytes, unchanged source/index/refs and pending-state demotion. Add or exercise a complementary real-Git current-wave positive control using the exact native generated postimage, with unchanged numerical caps. Only a directly reproduced fixture correction is admitted in this test module; keep all112pre-existing local-review definitions and existing negative assertions/parameter cases intact.
6. Before final review and commit, independently verify the ACTUAL indexed cap file and worktree both equal the native current-wave recomputed postimage, using the read-only native authority classifier. Require that result in review evidence before reporting the candidate ready. Do not return a cosmetic regression-only success while the actual provenance mismatch remains. Initial implementer evidence must accurately separate worktree correction from later native staging; never claim the implementer changed or validated an index it was forbidden to write.
7. Keep all39protected source/governance hashes and all60old R2/R3 authority hashes from /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/local-review-legacy-history-r4-admission/initial-facts.json unchanged. Production commit_executor.py, local_review_history_recovery.py, recovery_gate.py, dispatcher, Phase B, launcher, configuration, private-attribute checker, prior history/validator/receipt tests and original R1/R2/R3 packets/receipts stay frozen. The historical R1 IN_FLIGHT checkpoint remains immutable. The two recovered-history message sequences, refusal/unknown holds, source/Git/provenance checks, bounded four-worker selection and finite deadlines are already implemented; do not redesign them.
8. The actual original legacy attempt is .agent_bus-targeted-gate-budget-r2-20261009/meta/local_pr_reviews/local-pr-review-a705c468d1154ffa8364ac2b595f39d5. It has exactly prompt.md SHAffe70e514896ebf0654bb5e123d6f59cf81bed84b54edbc30cc7e5e222e19fad, pr.diff SHAf9ccd79a96a3ae013f910fe9853345c4329ea4a30a1be8b1c89c3f2ce4ca7a93 and raw.jsonl SHAcaf8042462b1a52b748582d0c1c1f91502bfc809266c88835926be92bcc5a5e0. Its interruption cause remains unknown. No missing original receipt, process result, request identity or approval is invented. The separate a92850a15e6f4411992770ace160cdaf receipt retains SHA57bc2129a98e471de4ea162fb8e5b60695cc1627b03fefcb60afa5208289d70e and ERROR/REQUEST_CHANGES.
9. After current validation, repeat the public read-only actual-history plan using the exact command recorded in /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/legacy-history-r3-root-actual-plan.json and pinned provenance at /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-legacy-history-r1-admission/legacy-provenance-binding.json, SHA6e4a9b4178f9ce61c29f28fa7a2f368bb1ba09274658c5074a882861e8d27cf9. Preserve original head f36b982b8b45774cf68fc621acf0d9727d72e6d5, original remote base35f7c225a25025aec893230c072754cf7d7c76fc, PR1332 and exact branch identity. Do not change refs or use the stale local dev branch as authority. Verify approval=false, unchanged original bytes/refs/index and a928 historical binding. Fixtures use temporary Git repositories and have no mounted-drive/provider/GitHub dependency.
10. Run scoped private-attribute integrity on the editable test file, then the FULL declared five-selector four-worker gate, including growth-cap tests. Record exact argv, environment, exit, stdout/stderr, elapsed time and source hashes in reports/control_plane/workingrcx-local-review-legacy-history-r4-2026-10-12_2026-10-12_implementation_evidence.json. Keep large raw ref inventories and actual-history diagnostic copies on the UUID-resolved WD under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011; bind them by hash instead of duplicating entire ref listings throughout tracked evidence. Prior R3 2927PASS does not validate the new regression or current governance bytes. Native-generated packet/indicator/staging updates have separate phase-specific authority.
11. Reconcile PRIMARY TASKS admission baseline SHA5833b7b3aa97edb1c7e3138a332ed01b73c089afd556030b3f7aa1dfa5ffc8af with the WT, retaining all268canonical IDs,44ordered owners and all historical tracker notes. Current checkpoint/to-do/row38/row40 identify fresh R4 progress and the unresolved landing work. Record the operator interruption correction honestly. Clarify in the R4 packet that only its indicator is active/newly collected while R2/R3 indicators are immutable preserved artifacts. Do not edit old packets to erase the wording note. No new numbered prerequisite.
12. Fresh independent reviewers must assess the actual staged cap postimage, inherited source protections, new regression and genuine public-history result. Fresh exact receipts gate native commit. Inner implementer must not launch executors, call live recovery apply, push, merge or retire sources. Root may publish recovery only using reviewed COMMITTED native code, the original pinned evidence and successful public verification. Then require corrected-head CI, authenticated-current-request complete-PR review, aggregate clearance and protected merge before claiming landing or PRIMARY synchronization.
13. Preserve the outer startup limitation: resumption-preflight.log had passing repository checks but local Codex binary/cache canary failures. Existing PRIMARY docs-registry residue remains separately recorded. No binary/cache/hooks/model/provider-role/global timeout/backup changes are admitted. Live configured implementer/reviewer are Codex/Codex. Honor founder quota-stop policy without alternate-model/account workarounds. One final native envelope with exact proof limits is required.
14. After actual PR1332 landing and verified PRIMARY sync, verify PR1331 disposition, then continue the prepared folder wave in /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/folder-wave-launch-preparation-20261011.json, separate deduplicated retention, final coverage/native disposition and fresh physical/useful-work obligations. Preserve paused PR1325, all recovery history and the main repository. Recovery evidence stays on the UUID-resolved WD; development stays local. No live archive purge, historical code reconciliation, Time Machine/Backblaze/Crucial/Parallels changes. Preserved work is not merged work.

## Constraints

- Authorized same-owner L4_ENABLER, FOUNDER_OVERRIDE:workingrcx-local-review-legacy-history-r4-2026-10-12; one native mutation lane on the existing PR branch at parente75ce9f7db3fd66cb240026e75f7066d68b9f6fc.
- Product executor/source guards and old governance are immutable under the39protected hashes. Implementation edits are limited to exact generated cap provenance, the declared local-review regression/fixture and current trackers/own R4 governance.
- Original and same-content histories remain held; recovered interruption is never review approval. Preserve default orphan, refusal/capacity, malformed/foreign/unknown and concurrency controls.
- No runtime/Mu/seed/host semantics, dispatcher, Phase B, launcher, adapter, hook, model/role/global timeout/backup changes. No manual product Git staging/commit/merge, hidden bus relocation, synthetic receipt, budget reset, administrative merge or historical purge.
- Use the existing native cap computation; numerical caps stay175/64 and every unrelated byte remains unchanged. Native staging and current indexed verification precede fresh approval.

## Stop conditions

- Hold on wrong head/branch/base, concurrent writer, corrupted or insufficient historical binding, undeclared mutation, unresolved mandatory finding, missing final indexed authority, refusal/capacity/quota stop or exhausted native authority.
- If indispensable recovery requires broader product scope, preserve evidence and state the exact additional admission. Do not weaken default protection or fabricate missing original provenance.
- Explicit live recovery publication must use reviewed committed native code and original immutable inputs; preserve the committed postcommit hold until that operation verifies.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_local_review_history_recovery.py mu/tests/tools/test_recovery_gate.py mu/tests/docs/test_growth_caps.py mu/tests/tools/test_commit_executor_receipt.py::TestCommitExecutorPytestGate --tb=short`

## Acceptance criteria

- The actual cap worktree and native index equal the exact current-wave native postimage, while numerical caps remain175/64 and prior-wave byte candidates still fail closed without mutation.
- The preserved prior-wave/demotion regression and a real-Git current-wave positive control pass, with all pre-existing assertions/parameters retained and no production guard changes.
- All39protected paths,60old authority records, the original R1 checkpoint and a705/a928 evidence remain unchanged; actual public history planning remains approval=false.
- Private-attribute integrity, the full declared gate and fresh indexed review/supervision pass on current source/governance. Evidence distinguishes implementation, later generated governance, commit and remote landing.
- All268IDs/44owners and historical notes remain; TASKS/to-do reflect actual state and the corrected operator interruption diagnosis. Folder/retention/disposition obligations remain open.
- Actual native commit, verified explicit history recovery, fresh corrected-head CI/full-PR review, protected merge and verified PRIMARY sync precede completion claims.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-local-review-legacy-history-r4-2026-10-12`.
- Governing packet: this file, `reports/control_plane/workingrcx-local-review-legacy-history-r4-2026-10-12_2026-10-12.md`.
- TASKS.md authority: the 2026-10-12 tracker sync note for wave `workingrcx-local-review-legacy-history-r4-2026-10-12` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-local-review-legacy-history-r4-2026-10-12

## Phase B implementation evidence (worktree correction; native staging pending)

The canonical 2026-10-12 R4 tracker sync note in `TASKS.md` owns this
packet's L4 fields. Its updated progress proof records local implementation
and validation, with actual indexed verification and fresh approval still
pending. Evidence is in
`reports/control_plane/workingrcx-local-review-legacy-history-r4-2026-10-12_2026-10-12_implementation_evidence.json`.

- The existing native authority capture and plan derived the entire cap
  postimage from unchanged HEAD `e75ce9f7db3fd66cb240026e75f7066d68b9f6fc`
  and the indexed new paths. HEAD cap SHA256 is
  `ba9964c72588ab7a8be6decd44ffc037e34e6f679ff53e89cb237b82c239e955`;
  inherited R2 index/worktree SHA256 was
  `117f68c057bbf3f0bde25e13c63a7f98e1c832d6528bc637b0751831a350bf57`.
  The exact R4 worktree SHA256 is
  `f2d3161eb471aee86f93f57298105ddc08023debd026d230e51e41c75fca68f3`.
  Only the two new provenance suffixes differ from the inherited candidate;
  numerical caps remain 175/64 and all unrelated bytes are unchanged.
- The carried prior-wave rejection/preservation/demotion regression passed
  before edits. One new real-Git positive control proves that correcting the
  worktree alone stays invalid, while the exact staged successor postimage
  settles without another increment. Its small fixture cap remains 1; actual
  repository verification independently proves unchanged 175/64 limits.
  All 112 pre-existing tests plus the carried regression remain byte-exact,
  including decorators, assertions and parameter coverage. No fixture correction
  or production-source change was necessary.
- Scoped private-attribute integrity passed. The full declared five-selector,
  four-worker gate passed 2,935 tests in 166.22s, exit 0, with stable source
  hashes. Earlier R3 2,927PASS and two COMMIT_GO receipts remain historical;
  they predate the added regression. Root's interruption of that admitted
  delegate followed an incorrect scope inference, not a proven scope violation.
- The exact public history plan from the pinned R3 command succeeded with
  approval=false. Original a705 bytes/modes, Git refs/index and the complete a928
  ERROR/REQUEST_CHANGES binding are unchanged. Default orphan admission still
  holds; no live recovery was applied. The original interruption cause remains
  unknown. Diagnostic copies and raw ref inventories live on WD volume UUID
  `93064AFA-816D-43E3-BCC9-8A514F8F3D7D`, with paths and hashes in the evidence.
- Only `reports/l4_wave_indicators/workingrcx-local-review-legacy-history-r4-2026-10-12.json`
  is the active, newly collected R4 indicator. The carried R2/R3 indicators are
  immutable preserved historical artifacts. Their original packets remain
  unchanged; the historical wording note remains tracked under row40.
- PRIMARY TASKS admission SHA256
  `5833b7b3aa97edb1c7e3138a332ed01b73c089afd556030b3f7aa1dfa5ffc8af`
  is reconciled without modifying PRIMARY: all 268 canonical IDs, 44 ordered
  owners and 617 distinct historical tracker notes are retained. All 39 protected
  source/governance hashes, 60 old authority hashes and R1 IN_FLIGHT bytes match.

Actual indexed authority is **pending**: this implementer did not stage files.
The worktree equals the native R4 postimage, while the actual index retains R2
bytes; the read-only native classifier correctly returns `invalid`. After outer
native staging, independent reviewers must repeat the following read-only check
against the actual repository and bind its result to their fresh review evidence.
A passing temporary-repository test does not satisfy this actual-index gate.

```python
from pathlib import Path
import hashlib
import re
import sys

root = Path.cwd()
sys.path.insert(0, str(root / "mu/tools/executors"))
import commit_executor as commit

snapshot, error = commit._capture_growth_cap_retry_authority(
    root, wave_id="workingrcx-local-review-legacy-history-r4-2026-10-12",
    base_branch="dev",
)
assert error is None, error
assert commit._growth_cap_snapshot_candidate_state(snapshot) == "postimage"
assert snapshot["index_target"] == snapshot["expected_target"]
assert snapshot["worktree_bytes"] == snapshot["expected_bytes"]
assert hashlib.sha256(snapshot["expected_bytes"]).hexdigest() == (
    "f2d3161eb471aee86f93f57298105ddc08023debd026d230e51e41c75fca68f3"
)
assert dict(re.findall(
    rb"^(CAP_TEST_FILES|CAP_TOOL_SCRIPTS) = (\d+)", snapshot["expected_bytes"], re.M,
)) == {b"CAP_TEST_FILES": b"175", b"CAP_TOOL_SCRIPTS": b"64"}
```

Native staging, fresh indexed review/supervision and exact receipts remain
outer-owned. No commit, recovery publication, push, merge, PRIMARY synchronization
or retirement is claimed. Reviewed committed code, explicit pinned recovery and
public verification, corrected-head CI/authenticated complete-PR review and
protected landing precede completion. Then verify PR1331 disposition and continue
folder, separate retention, final coverage/disposition and physical/useful-work
obligations. Preserve paused PR1325 and the main repository. Outer startup's
binary/cache-canary failures and PRIMARY docs-registry residue remain recorded
limitations; no local settings or provider roles changed. Current quota
observation is unavailable in this implementer; no percentage or reset is inferred.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-local-review-legacy-history-r4-2026-10-12`
- Active packet: `reports/control_plane/workingrcx-local-review-legacy-history-r4-2026-10-12_2026-10-12.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-local-review-legacy-history-r4-2026-10-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_local_review_history_recovery.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/local_review_history_recovery.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r1-2026-10-09_2026-10-09.md`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r1-2026-10-09_2026-10-09_implementation_evidence.json`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r2-2026-10-11_2026-10-11.md`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r2-2026-10-11_2026-10-11_implementation_evidence.json`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r3-2026-10-11_2026-10-11.md`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r3-2026-10-11_2026-10-11_implementation_evidence.json`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r4-2026-10-12_2026-10-12.md`
  - `reports/control_plane/workingrcx-local-review-legacy-history-r4-2026-10-12_2026-10-12_implementation_evidence.json`
  - `reports/deferred/non_blocking/workingrcx-local-review-legacy-history-r1-2026-10-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/workingrcx-local-review-legacy-history-r2-2026-10-11.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-legacy-history-r3-2026-10-11.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-legacy-history-r4-2026-10-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->