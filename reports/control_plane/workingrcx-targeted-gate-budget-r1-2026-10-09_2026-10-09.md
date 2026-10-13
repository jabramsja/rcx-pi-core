# Finish PR1332 with measured targeted-test budgets and complete timeout evidence

Date: 2026-10-09
Status: STOPPED / PRESERVED UNMERGED; superseded by targeted-gate-budget R2
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-targeted-gate-budget-r1-2026-10-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: cc4030452e5cd6a290d2cf4e6781bbc2eeb7fcd82fdd08d9b07e8859c14d6300
Purpose: Authorized control-surface L4_ENABLER under founder autonomous cleanup/landing direction. Finish the preserved parser repair by correcting its measured targeted-test budget and retaining complete timeout evidence; reuse the pending lifecycle-budget enabler in the same helper.

## Scope

Targeted pytest budget and diagnostic propagation, their existing tests, preserved parser candidate and own governance. Preserve all merge/review/receipt controls.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py: only _run_pytest_on_files finite exact-selector budget/output behavior and the Step8b failure envelope needed to retain that diagnostic. All receipt, branch, review, quota, merge/base identity, cleanup and other executor behavior remain unchanged.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py: extend its existing real runner-boundary budget/failure tests, including the pending PR1330 cases; no new test module. Meaningful public Step8b propagation proof may use existing fixtures with external effects isolated.
- Carry unchanged R2 implementation in mu/tools/executors/executor_dispatch.py and its two existing test modules. They are unfinished staged work that must remain in the reviewed candidate; no further parser or Phase B implementation edit is needed.
- TASKS.md, CHANGELOG.md, reports/control_plane/workingrcx-targeted-gate-budget-r1-2026-10-09_2026-10-09.md, reports/control_plane/workingrcx-targeted-gate-budget-r1-2026-10-09_2026-10-09_implementation_evidence.json, reports/l4_wave_indicators/workingrcx-targeted-gate-budget-r1-2026-10-09.json and the own optional nonblocker report. Carry the existing R1/R2 packets, implementation evidence and indicators as historical predecessor evidence; minimal truthful lifecycle wording only.
- mu/tests/docs/test_growth_caps.py only for mechanical native generation. No manual cap adjustment.
- reports/deferred/non_blocking/workingrcx-targeted-gate-budget-r1-2026-10-09_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-09 tracker sync note for wave `workingrcx-targeted-gate-budget-r1-2026-10-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. This is an authorized control-surface L4_ENABLER repair. Continue on the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR1332. FOUNDER_OVERRIDE:workingrcx-targeted-gate-budget-r1-2026-10-09. Keep these positive authority and existing PR branch forms in the canonical indexed packet. Before full gates and after final packet observations, exercise the actual indexed reader and real Phase B selector/builder; use temporary fixtures for negative controls.
2. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/terminal-result-r2-stopped-preserved/preservation.json, verified snapshotddf13a8d83d91d4cb649148a48e15e15b4e6cc083c627bdfb2a7fbf1734cf5ba, and /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/terminal-result-r2-step8-diagnostic/diagnostic.json plus timing-summary.json, stdout.txt and results.xml. Diagnostic ran the original Step8b selectors and production validation environment, adding duration/JUnit reporting and a1200s diagnostic deadline. It passed2154tests in473.648s, with source/index unchanged. Per-module testcase time totals: dispatcher159.190s; PhaseB305.332s. Its timeout allocation was240s per ordinary selector. Do not claim which test was interrupted originally or that the earlier timed-out invocation passed.
3. Give only the exact full mu/tests/tools/test_phase_b_executor.py module a finite600s allocation in _run_pytest_on_files. Retain the full-fleet900s allocation, every selector, marker/import settings, production validation environment, bounded full-fleet xdist policy, caller timeout maxima, and the240s default for node selectors/unrelated paths. Mixed gates sum their allocations and remain finite. No broad global timeout increase, skipped tests, xfails, or altered pass criteria.
4. Reuse the already-pending PR1330 targeted lifecycle-budget work in this same helper and test module: commit817e470362ef632b60ab13bb4321571676f564ee adds exact full mu/tests/tools/test_worktree_lifecycle.py600s while preserving node/path/default/caller behavior. Inspect its actual source/test diff and preserve all its meaningful regression cases. This is existing authorized cleanup-enabler work, not historical-code reconciliation during retention. Record provenance and pending coverage; do not close PR1330 or mark its old commit merged. Fresh full-PR CI and later native disposition remain required.
5. Preserve full available TimeoutExpired stdout/stderr, including bytes/string/None forms, and bind the failed command and selected finite deadline in the Step8b failure evidence reaching recovery. A timeout remains failure. Earlier supervisor chatter must not substitute for actual pytest progress. Preserve existing successful/nonzero/empty-collection semantics and compatibility with callers. Limit production changes to the declared runner and Step8b failure-envelope boundary.
6. Extend existing tests for exact full-module policies, mixed/order-independent gates, node/foreign-path negatives, caller maxima, nonzero/collection/interruption failures, finite deadline, and complete timeout diagnostics. Exercise the actual Step8b failure path with isolated side effects. Do not introduce a test-only production bypass or weaken receipt/branch/review controls.
7. R2 parser/transport code is already validated and chained automatically into commit. Keep dispatcher SHA2bc2148e65cd770ced3fee2c41b6511209af2cce2ef4a1bc7a79b7621fe42979, test_executor_dispatch SHAdcd0efae3be1e99d6e4e1dc984324fd60dcd41e6944f8168542fe44fecb49bb8, test_phase_b_executor SHA5addcf4f6913891532b84df4d6da5b5648c3fc9889d7a2e4fda50cb9942235aa, and phase_b_executor SHA34908b76fe6c635130910321233ac4fd4799212355c4983953a8ebf420f61dd7 unchanged. All commit code outside the declared narrow runner/Step8b boundary must match parent5780234. Preserve local-review/Step14 tests and prior CI/prompt-isolation fixes byte-for-byte.
8. Run the declared three existing modules and record exact command/output/exit/timing plus before/after source hashes at /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/targeted-gate-budget-r1-validation. Own evidence goes in reports/control_plane/workingrcx-targeted-gate-budget-r1-2026-10-09_2026-10-09_implementation_evidence.json. Native final gates, staging, inventory, indicator/cap generation, supervisor receipts, hooks, commit, push and merge remain pipeline-owned.
9. Synchronize existing TASKS rows38/40 and the top working to-do without losing268taskIDs or44queue owners. R2 is stopped/preserved after the480s gate and three missing-module delegation failures; this fresh wave is current. Read PRIMARY TASKS at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/TASKS.md, SHA2563d0679aaac241d79efefb58624e89e76379d3fcf6c7be02cfbfa7fc5116a64e9; reconcile its current checkpoint without erasing candidate history. Keep existing row40 follow-ups for invalid delegation feedback/admission, broad authorization-text scanning, early builder admission and advanced PhaseB-to-PhaseA retry routing. Recovery-gate source changes are outside this wave.
10. Keep both R1 and R2 indicator/packet/evidence records explicitly listed as preserved predecessors. The R2 supervisor noted a nonblocking generated indicator-scope wording inconsistency; make new owned wording clear without altering historical receipts or Phase B source. If the native template reproduces the wording, retain precise existing-row40 follow-up instead of creating another prerequisite.
11. Preserve all three original Bot findings and complete bodies. Queue P1 threadPRRT_kwDOQvy8bs6qI-5e/commentPRRC_kwDOQvy8bs77IAg6 bodySHAff2c6b22b5f36ec3b2347da074a3be12739fe0643a6748f3cffb1fc883860fbc; base P1 threadPRRT_kwDOQvy8bs6qMIWE/commentPRRC_kwDOQvy8bs77NDtC bodySHAc161930ad5ed0dede0fa2aabca3885d88af3712087ef6828783c99c77f39b078; parser P2 threadPRRT_kwDOQvy8bs6qRZES/commentPRRC_kwDOQvy8bs77VkbW bodySHA9cfd90ae8c6ce97db941773bf3ee93ff18bde9f38b1d1314c8eb9bf430797661. Implementation performs no GitHub action. Founder autonomous landing authorizes only proof-backed individual disposition after actual fixes, fresh final native approval, all corrected-head required CI and independent authenticated current-head cloud clearance while old findings remain unresolved. Re-fetch complete comments/authors/bodies; added/changed/human findings require renewed assessment. No blanket resolution, deletion or dismissal; final aggregate must include retained local sweeps.
12. After actual landing and verified PRIMARY sync, verify PR1331 disposition and PR1330 source/test coverage plus native disposition, then complete PR1329. Producer retention remains separately scoped after these enablers. Preserve paused PR1325 and remaining folder/registration/useful-work obligations. No pre-Oct6 APPLY replay, live archive purge, historical reconciliation during retention, or Backblaze/Time Machine/Parallels/Crucial changes.
13. Postmerge task-id routing may request a same-wave apply_plan despite this tooling repair. If reproduced, report actual landing separately from routing hold and retain existing-row40 evidence. Never fabricate an APPLY plan. Old R1/R2 buses, receipts, recovery counters and lifecycle budgets remain historical; launch exactly once with the fresh bus after current owner absence and preservation are verified.

## Constraints

- Authorized control-surface L4_ENABLER under existing row38/row40 and founder autonomous cleanup/landing direction. FOUNDER_OVERRIDE:workingrcx-targeted-gate-budget-r1-2026-10-09. No new numbered prerequisite.
- One mutation lane. Root owns configuration/tracking/diagnostics; native actors own source implementation/staging/commit/push/merge/conflict resolution. Development remains local; recovery evidence uses the UUID-resolved WD store.
- Only the declared runner budget/diagnostic boundary and existing test module may gain production/test behavior. Preserve all review/merge/base/receipt authority and every existing gate; runtime/hosts/seeds/hooks/launchers/recovery source remain unchanged.
- Preserve existing PR branch and parent5780234568130f7116922ecc29d854a6db9e069e. No old native state or budget resets; fresh same-wave reviews govern the new candidate.
- Only proven addressed unchanged Bot findings receive individual conditional disposition after fresh current-head review and required CI. Added/changed/human findings retain full assessment.
- No full local recovery archives, backup-setting changes, live purge, or premature claim of merge/retention integration.

## Stop conditions

- Hold on branch/head/PR/base mismatch, concurrent mutation, undeclared changes, missing exact packet/builder authority, altered protected parser/review code, or exhausted native recovery.
- If diagnosis requires source outside the declared runner/Step8b boundary, preserve evidence and give a precise admitted follow-up; do not broaden globs or suppress failure.
- No commit without the fresh final receipt and actual existing-PR target; no merge without current CI, independent review and complete aggregate clearance including local sweeps.
- Do not infer original test success from the later diagnostic; do not claim PR1330 merged or covered until landed bytes and its original hunks are verified.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py --tb=short`

## Acceptance criteria

- Exact full Phase B and lifecycle modules receive measured finite600s allocations; full fleet retains900s; other/node/foreign selectors retain240s and caller maxima.
- Actual available timeout progress, command and chosen deadline survive the Step8b failure boundary; nonzero and timeout outcomes remain failures.
- The preserved parser and protected review/merge controls remain intact; meaningful existing regression cases and all declared gates pass.
- Actual indexed same-wave packet and real selector/builder preserve the existing PR branch before commit.
- Fresh native approvals, corrected-head CI and independent cloud review enable precise finding disposition and landing; PRIMARY sync and any postmerge routing hold are separately verified.
- Task truth retains every existing owner and accurately distinguishes preserved work, newly landed implementation, pending PR disposition and unimplemented retention.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-targeted-gate-budget-r1-2026-10-09`.
- Governing packet: this file, `reports/control_plane/workingrcx-targeted-gate-budget-r1-2026-10-09_2026-10-09.md`.
- TASKS.md authority: the 2026-10-09 tracker sync note for wave `workingrcx-targeted-gate-budget-r1-2026-10-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-targeted-gate-budget-r1-2026-10-09


## Preserved predecessor lifecycle (2026-10-09)

The gate started 2026-10-09T09:01:14Z and was interrupted before completion. Three adjacent receipt assertions failed in a separate unchanged-source diagnostic; no completed R1 gate or final receipt exists. Runner and regression bytes carry into fresh R2 unchanged. Fresh authority belongs to `workingrcx-targeted-gate-budget-r2-2026-10-09`; prior approvals do not transfer.
