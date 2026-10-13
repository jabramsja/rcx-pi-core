# Make native local-review failures terminal before dispatcher recovery

Date: 2026-10-09
Status: Phase B (pre-supervisor pending, bridge-converged)
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-local-review-terminal-r2-2026-10-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 2cd5ee9e69dbf1a9f6ca691eb9813cfd3562f75722d49fd0e64f4a8a83bc5c62
Purpose: Authorized control-surface L4_ENABLER under founder autonomous cleanup and landing direction. Repair the blocking full-PR review finding at the native local-review and dispatcher recovery boundary; preserve all completed PR1332 work.

## Scope

Native local-review failure/rejection transport and immutable evidence, exact dispatcher terminal/retry admission, adjacent recovery classification and regression coverage, plus own governance.

Files and surfaces in scope:

- mu/tools/executors/commit_executor.py: native local quota review error/negative-verdict handling, durable continuation admission and typed terminal result. Preserve complete authoritative output, refusal/capacity provenance and immutable negative verdicts; correct same-input reentry behavior. Other review identity/aggregate/merge and gate controls retain their existing protections.
- mu/tools/executors/executor_dispatch.py: exact terminal commit-result parsing/classification and direct/surface/chained retry admission needed to stop this local-review outcome before recovery. Preserve the already-correct strict Phase B terminal parser and handoff identity behavior.
- mu/tools/executors/recovery_gate.py: only the producer-bound local-review terminal classification/pre-delegation fence required at this boundary, if necessary. Preserve unrelated transient-rate-limit, Phase B safety-refusal, learned-pattern and bounded recovery behavior.
- The three existing test modules in the allowlist: meaningful actual producer-to-dispatcher and recovery/reentry tests, using temporary fixtures and isolated external effects. Existing tests remain enabled. Own TASKS/CHANGELOG/packet/implementation evidence/indicator/optional nonblocker only; growth-cap changes only through native generation.
- reports/deferred/non_blocking/workingrcx-local-review-terminal-r2-2026-10-09_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-10-09 tracker sync note for wave `workingrcx-local-review-terminal-r2-2026-10-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. This is an authorized control-surface L4_ENABLER. Continue on the existing PR branch jabramsja/workingrcx-local-review-quota-r3-2026-10-05 for PR1332 at parentf36b982b8b45774cf68fc621acf0d9727d72e6d5. FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r2-2026-10-09. Preserve these exact existing PR branch and override forms in the canonical indexed packet. Exercise the actual indexed reader, real Phase B branch selector and commit builder before expensive gates and after final packet reporting changes. Negative controls use temporary fixtures.
2. Read /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r1-evidence-admission.json and its original receipt path .agent_bus-targeted-gate-budget-r2-20261009/meta/local_pr_reviews/local-pr-review-a92850a15e6f4411992770ace160cdaf/receipt.json. That authoritative reviewer read the entire13,073-line/53-file PR diff and found one blocking defect. Its exact head/base/diff identity, full output and findings stay preserved. Review proof used narrow in-memory production-classifier probes, not a live provider failure. Do not claim an actual provider refusal occurred.
3. Reproduce with realistic adapter error objects and terminal command output: commit_executor._run_local_quota_review loses structured provider_refusal and its Step15 exception handler returns a generic error; executor_dispatch._is_terminal_executor_outcome and chained result classification allow recovery; recovery_gate.classify_failure routes usage exhaustion to transient retry. Exact line evidence remains in the immutable reviewer receipt. Existing test_local_execution_failure_is_terminal_without_retry only observes one commit invocation. Test the real subprocess-result classifier, direct and chained dispatcher loops, and recovery boundary. Actual stopped lane separately demonstrates REQUEST_CHANGES followed by native retry_requested; it does not prove a live refusal/capacity event.
4. Preserve producer-authenticated adapter refusal/capacity information, relevant return code/raw streams/job/turn/reviewer identity and evidence hashes through the local-review receipt and executor terminal result. Stop before generic recovery, learned-pattern remediation, backoff or any repeated reviewer call when this native local-review attempt reports provider refusal or unavailable capacity. Reuse existing native failure contracts where sound; arbitrary prompt/prose mentions must not gain producer authority. Do not contact a provider to reproduce refusal or work around provider policy/capacity.
5. Keep full-PR negative verdicts and blocking findings durable. REQUEST_CHANGES or other unapproved/malformed/incomplete local outcomes must not be transformed into approval or an unchanged-input review loop. Bind terminal continuation evidence to the exact candidate and request identity; reentry with that same failed identity makes zero new review/merge/remediation calls. A genuinely corrected candidate requires fresh governed native review and all current protections, while the old receipt remains historical. Keep implementation bounded: a terminal repair-required result is sufficient; a new autonomous remediation subsystem is outside scope.
6. Prove positive and negative controls through real public/production boundaries with isolated GitHub/provider/process effects: configured adapter refusal and capacity failure, code findings, nonzero/timeout/malformed verdict, same-input reentry and interruption after durable negative evidence, fresh corrected identity, direct/surface/chained dispatcher paths, noisy pretty-JSON terminal output, malformed/ambiguous/unbound terminal claims, and ordinary unrelated transient failures. Assert zero recovery, remediation, repeated reviewer or merge calls for the terminal local outcomes. Preserve existing successful full-PR review, aggregate/CI/source/base identity checks and merge behavior. Production fixtures may inject external boundaries; no test-only production bypass.
7. Run the declared full three-module gate and all required native checks; capture exact commands, outputs, exit status, timings and before/after source hashes under /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/local-review-terminal-r2-validation. Write own implementation evidence at reports/control_plane/workingrcx-local-review-terminal-r2-2026-10-09_2026-10-09_implementation_evidence.json. Record any initial failing reproduction and repair honestly. Native actors own implementation, staging, indicators/caps, supervisor receipts, commit, push, merge and conflict resolution.
8. Synchronize PRIMARY TASKS checkpoint (SHA2567fc0b938ad97f86891516016191fed3313e9577a15c78db572dbdb3bfa4f9867) into candidate history without erasing either side. Keep268canonical task IDs and44ordered queue owners. Existing row38 owns this correction and subsequent landing/folder/retention work; row40 retains wait/adjudication automation, branch admission, invalid delegation feedback, broad authorization scanning, advanced packet routing and task-ID-only postmerge APPLY routing followups. Targeted-gate-budget R2 committed f36 and passed CI but received REQUEST_CHANGES from complete-PR review; do not describe it as landed.
9. The original three Bot findings are individually resolved with exact-body preservation and independent GO adjudication at /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261009/targeted-gate-budget-r2-retained-finding-assessment/result.json and targeted-gate-budget-r2-review-wait-diagnostic/assessed-thread-disposition-result.json. That is not full-PR approval. Preserve all original comments and dispositions, and retain the new negative full-PR review. Native policy already permits one read-only complete-PR local review on authenticated current-request cloud code-review quota; configured Codex/gpt-6-astra/max, all7CI checks, immutable full PR/base identity and complete retained findings remain required. No fabricated cloud clearance or manual approval receipt.
10. After actual landing and PRIMARY sync, verify PR1331 disposition and PR1330 landed source/test coverage plus native PR disposition, then PR1329 useful portable folder work through fresh authority. Retention remains a separate next scope using UUID93064AFA-816D-43E3-BCC9-8A514F8F3D7D. Preserve pausedPR1325 and remaining physical/registration/useful-work obligations. No historical APPLY replay, live archive purge, dev relocation or backup configuration changes.
11. If the native postmerge package asks for a same-wave apply_plan despite this tooling correction, retain its honest routing HOLD separately from merge and sync evidence. Never fabricate an APPLY plan. Root stopped the old owners; native closeout is ESCALATED with source retained. Old buses, terminal receipts, approvals, recovery counters and lifecycle budgets remain unchanged and are not execution authority for this fresh wave.
12. The first launch-input attempt stopped in setup_packet line-ref lint before writing a packet, creating a bus or launching dispatcher. Its lifecycle completion budget is historical and remains consumed. This fresh attempt has identical correction scope and adds complete check_packet_fences admission before launch. Keep the actual rendered packet fences, positive authorization predicate, indexed reader and real builder valid through final machine reporting sections; carry exact line-level diagnostic references in external evidence, using stable function names in the packet.

## Constraints

- Authorized control-surface L4_ENABLER under existing row38/row40. FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r2-2026-10-09. One mutation lane; root owns configuration/tracking/evidence, native actors own product source and landing.
- Keep parentf36b982b8b45774cf68fc621acf0d9727d72e6d5 and the existing PR1332 branch. All source outside the declared local-review/terminal/recovery boundary remains unchanged, including pytest budget/diagnostics, Phase B source, runtimes, seeds, hooks, launcher, adapters and models.
- Preserve the stop-without-retry contract for provider refusal/capacity, source and review evidence. Fresh correction is authorized for a code finding; it is not authorization to rephrase a refused request, change accounts/models, raise review limits, or retry unavailable provider capacity.
- Keep all gate/receipt/source/index/head/base/CI/aggregate/queue/ordered-parent protections. No blanket thread resolution, admin merge, failing-test suppression, old-bus replay, recovery/lifecycle-budget reset or local persistent full recovery archive.

## Stop conditions

- Hold on mismatched head/branch/base, concurrent mutation, undeclared changes, missing indexed packet/builder authority, provider refusal/unavailable capacity, quota stop threshold, or exhausted native recovery.
- If a necessary source change lies outside the declared boundary, preserve evidence and return exact required admission; do not widen scope or silence the gate.
- No commit without the new exact receipt and correct existing PR target. No merge without fresh corrected-head CI, independent complete-PR review and aggregate clearance. Retain every negative verdict and unresolved finding.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_commit_executor_local_review.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_recovery_gate.py --tb=short`

## Acceptance criteria

- Actual native local-review refusal/capacity and negative review outcomes remain non-approvals and stop across dispatcher recovery and same-input reentry; immutable producer evidence survives. Meaningful production-boundary tests assert zero unauthorized additional calls.
- Unrelated transient recovery and approved review/merge behavior remain intact; no provider/source/test bypass. The full declared existing modules and required checks pass.
- Actual indexed packet and native builder retain PR1332 branch and comparison ancestry; final source/test hashes match evidence. Fresh native reviews, corrected-head CI and complete-PR review precede actual landing and separately verified PRIMARY sync.
- TASKS retains268IDs/44owners and distinguishes preserved, committed, CI-passing, review-blocked and landed work. Remaining folder/PR/retention obligations remain explicit.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-local-review-terminal-r2-2026-10-09`.
- Governing packet: this file, `reports/control_plane/workingrcx-local-review-terminal-r2-2026-10-09_2026-10-09.md`.
- TASKS.md authority: the 2026-10-09 tracker sync note for wave `workingrcx-local-review-terminal-r2-2026-10-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-local-review-terminal-r2-2026-10-09

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-local-review-terminal-r2-2026-10-09`
- Active packet: `reports/control_plane/workingrcx-local-review-terminal-r2-2026-10-09_2026-10-09.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-local-review-terminal-r2-2026-10-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_local_review.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-local-review-terminal-r2-2026-10-09_2026-10-09.md`
  - `reports/control_plane/workingrcx-local-review-terminal-r2-2026-10-09_2026-10-09_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-local-review-terminal-r2-2026-10-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->