# WorkingRCX Pipeline Throughput R14 2026-11-26

Date: 2026-11-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-pipeline-throughput-r14-2026-11-26
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 060bbcf77eae334c87d5716212638b5504270a8684b8c647a8cdb60ab87ef04a
Purpose: Deliver the preserved throughput R7 candidate under the founder's Option A catalog decision: land bounded shared execution repairs and close stale common-module execution at the supervisor handoff while retaining every phase and delivery gate. Also carry the reviewed Phase B heartbeat observation test fix.

## Scope

R7's preserved shared bounded validation, native recovery scheduling and handoff/HOLD fixes, carried onto baced34fe827da129a02ae5264485be688924d8c; the Option A pinned catalog binding; the reviewed heartbeat observation test fix; closures under reports/archive/deferred/; R12's stale-import repair; the fixture fix; R13's runner repair; the docs sync report's git-ignore rule.

Files and surfaces in scope:

- TASKS.md (MODIFY) -- body equals the preserved PRIMARY checkpoint (sha256 370ec6712096af743cdb3ae4034eacfb58648631e9aa694ed03cbe800fca96e5) plus only this wave's tracker note.
- CHANGELOG.md -- MUTABLE truthful chronology; distinguish measured local improvements from native delivery.
- mu/docs/agents/AgentRunbook.v0.md -- MUTABLE document the actual shared execution/budget contract and unchanged phase sequence. Document the exact declared review-report contract, including rechecks after an envelope; all instruction changes receive native pipeline review.
- mu/tools/executors/validation_execution.py -- NEW small shared native validation execution/policy surface; avoid a second dispatcher or scheduler.
- mu/tools/executors/phase_b_executor.py -- MUTABLE native pytest execution/progress/budgets and the observed post-private-review GO/deferred-output checkpoint transition; preserve source/reviewer/ownership/replay guards and all phases. Also propagate validated exact review-artifact destinations and enforce candidate scope after review before admitting corrective implementation; preserve legacy behavior without required authority and all final guards.
- mu/tools/executors/commit_executor.py -- MUTABLE share bounded pytest execution and account for contained stages; retain all commit/CI/merge/cleanup checks and receipt bindings.
- mu/tools/executors/executor_common.py -- MUTABLE one typed source-bound execution/budget contract shared by existing native callers; retain role/model/routing policy.
- mu/tools/executors/executor_dispatch.py -- MUTABLE bounded parent/child stage budget admission and propagation only; retain all process ownership/release and checkpoint guards.
- mu/tools/executors/launch_wave.py -- MUTABLE native deterministic execution/budget admission and immutable transport; preserve packet builders, exactly-once launch and retry authority.
- mu/tools/executors/executor_config.json -- CONDITIONAL MUTABLE central validation policy only if necessary; preserve selected roles/models and existing unrelated timeout defaults. No blanket deadline increase.
- mu/tools/agents/meta_bridge_supervisor.py -- MUTABLE consume source-bound validation budget/progress while retaining actual evidence execution, independent review, state restoration and all validations.
- mu/tools/executors/recovery_gate.py -- CONDITIONAL MUTABLE propagation/typed classification of admitted validation budgets only; preserve bounded recovery, uncertainty HOLD and original cap/reset policy. Explicitly integrate the hybrid targeted validator with shared bounded execution, finite parent/leaf budget semantics and contained child output; preserve typed failures and scope audits.
- mu/tests/docs/test_growth_caps.py -- NATIVE GENERATED ONLY when Step5e actually requires a transition; preserve exact bytes for a no-op.
- mu/tests/tools/test_validation_execution.py -- NEW meaningful public execution/refusal/performance fixtures.
- mu/tests/tools/test_phase_b_executor.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage. Also carry the reviewed heartbeat observation fix in the native real-process release helper (atomic pulse publication and a bounded liveness wait), preserved in phase-b-heartbeat-fix-r1-terminal-candidate-20261126.
- mu/tests/tools/test_commit_executor_receipt.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage.
- mu/tests/tools/test_executor_common.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage.
- mu/tests/tools/test_executor_dispatch.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage.
- mu/tests/tools/test_launch_wave.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage.
- mu/tests/tools/test_meta_bridge_supervisor.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage.
- mu/tests/tools/test_executor_config_alignment.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage.
- mu/tests/tools/test_recovery_gate.py -- MUTABLE relevant actual caller/negative controls; retain all unrelated assertions and coverage. Add actual native hybrid caller containment, full selector/profile, finite-budget, structured-HOLD and failure controls.
- reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md -- NEW NATIVE BUILDER OWNED packet; never edit normative body, extra H2, lock or authority by hand.
- reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_implementation_evidence.json -- NEW own source-bound commands/results/timings/phase-preservation matrix and implementation evidence.
- reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json -- NEW NATIVE GENERATED own wave indicator; no historical approval transfer.
- reports/deferred/non_blocking/workingrcx-pipeline-throughput-r14-2026-11-26_bridge_nonblockers.md -- OPTIONAL NEW native nonblocking report for this wave only.
- mu/tools/agents/meta_bridge_client.py -- MUTABLE narrow common-module capability/source compatibility refresh at the real native supervisor handoff; preserve review/routing/state restoration behavior. Establish exact execution provenance for both supervisor dependencies while preserving prior callable ownership and fail-closed refresh rollback.
- mu/tests/tools/test_meta_bridge_client.py -- MUTABLE actual warm/cold native handoff fixtures and all existing refusal coverage. Add real common AND validation cached-bytecode/over-ceiling normal/-B regressions with warm/cold/absent, wrong-source, interruption and source-drift controls.
- reports/archive/deferred/workingrcx-pipeline-throughput-r7-2026-10-29_bridge_blockers_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md (ADD) -- R7's bridge blockers report, carried before launch as a closure record; update only its disposition and resolution lines.
- reports/archive/deferred/phase-b-heartbeat-observation-window-ci-flake-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md (ADD) -- the as-filed PRIMARY heartbeat blocking report as a closure record; update only its disposition and resolution lines.
- reports/archive/deferred/commit-targeted-pytest-gate-phase-b-module-budget-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md (ADD) -- the as-filed PRIMARY pre-commit gate budget report as a closure record; update only its disposition and resolution lines.
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py (MODIFY) -- founder-authorized: migrate only the targeted-runner tests to the shared validation_execution runner (carried from R11), preserving every behavioral assertion; no other change.
- mu/tools/docs/docs_sync_report.py (MODIFY) -- consider only markdown that git tracks or could add (tracked, or untracked and not ignored); git-ignored files are out of scope. Keep every classification rule.
- mu/tools/docs/shared_doc_config.py (MODIFY, only if needed) -- a shared helper for the git-visible markdown set.
- mu/tests/tools/test_docs_sync_report.py (MODIFY) -- regressions for the ignore rule.
- mu/tests/docs/test_doc_governance.py and mu/tests/docs/test_docs_registry_agent_memory_exempt.py (MODIFY, only if needed) -- apply the same rule where they walk the filesystem, preserving every behavioral assertion.
- mu/docs/core/DocGovernance.v0.md (MODIFY, only if needed) -- state the coverage rule.
- TASKS.md -- tracker-sync authority. The 2026-11-26 tracker sync note for wave `workingrcx-pipeline-throughput-r14-2026-11-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Founder explicitly authorized pipeline optimization before production, deterministic fixes for recurrent failures, and priority waves while preserving all phases and real convergence. Fresh L4_ENABLER workingrcx-pipeline-throughput-r14-2026-11-26; branch jabramsja/workingrcx-pipeline-throughput-r14-2026-11-26; comparison baced34fe827da129a02ae5264485be688924d8c; FOUNDER_OVERRIDE:workingrcx-pipeline-throughput-r14-2026-11-26. Existing task [FLEET-NATIVE-LIFECYCLE-PREVENTION], owner40; no new task IDs. R14 (the relaunch after R13's final docs check stop) delivers the preserved R7 finite execution/budget repair under the founder's Option A catalog decision; not wholesale replay of stopped runner R5.
2. CARRIED CANDIDATE FIRST: the 22 candidate files are carried byte-identically onto baced34fe827da129a02ae5264485be688924d8c from R13's reviewed, supervisor-approved staged blobs: R12's candidate (R7's code, tests and Runbook, the heartbeat fix, R8's implementer deltas, R10's implementer work, R11's migration and quoting fix, R12's stale-import repair), the fixture fix in test_recovery_gate.py reviewed in R13, and R13's repair of the validation runner's inherited-output completion. R13's re-entry review returned GO and its pre-commit supervisor returned COMMIT_GO on that implementation (preserved under pipeline-throughput-r13-terminal-lane-20261126). Per-file hashes are in this wave's admission record /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/workingrcx-pipeline-throughput-r14-2026-11-26-admission. Verify each carried file against that record; change carried files only where this wave's docs check fix or review requires. Do not import R13's tracker, packet, evidence, indicator, index, checkpoint or approval.
3. RE-RUN THE REPRODUCTION FIRST: the carried candidate contains R7's reproduction of the cached executor_common bytecode admission defect (a 9900-second ceiling retained while staged source declared 7200) and its normal/-B controls. Run those focused controls before the expensive gate pair and record the results.
4. CLOSE THE COMPLETE HANDOFF DEPENDENCY BOUNDARY: inspect meta_bridge_client.py, executor_common.py and validation_execution.py together. Establish execution provenance from exact bound source bytes for both dependencies; a module hashing current disk source does not prove which code executed. Cover warm, cold and absent cached modules, same timestamp/size pyc, wrong-source module refusal, source mutation during refresh, import/compile failure and interruption rollback. Preserve existing executor callables and their original module ownership; prove refreshed consumer behavior and old-owner continuity. Retain finite ceilings, original admission identity and clocks, guard symbols, typed HOLD transport and every ordinary failure path. Do not use global reloads, new caches/daemons, source-hash self-assertions, guard suppression, class-identity accidents or budget inflation as a workaround.
5. RECOVERY ACCEPTANCE: preserve the actual native hybrid caller, four-module full selector, at most four workers, existing finite parent/leaf schedule, durable output outside the candidate and final scope audit. Record exact argv, selected tests, Hypothesis setting, identities, elapsed/budget, exit and output hashes. Full selector and ci_full Hypothesis are different facts; never relabel ci_fast evidence as ci_full. Keep existing profile contracts and ordinary 300-second leaf policy; any policy change requires measured admissibility rather than scalar timeout inflation. Retain actual child interruption/zero-collection/worker-absence/HOLD and output-containment controls already present.
6. VERIFY INHERITED ENVIRONMENT: retain R2 real-child absent/single/multiple inherited-owner fixtures and symmetric ordinary-env checks; preserve every protected-key, unrelated-key, deterministic pin, parent-nonmutation and production ownership assertion. No production owner stripping.
7. VERIFY HANDOFF CONTINUITY: retain R2 deterministic post-private-review GO/deferred-report producer transition, original prepared source/reviewer bindings and single-use consumer. Prove real native preparation/review-output/final-failure/fresh-process continuation plus all drift/replay/ownership refusals. Do not re-seal unexplained bytes, delete checkpoints or replay completed actor approval.
8. VERIFY WARM CALLER AND BUDGET CONTINUITY: retain actual baseline-cached common AND client callables into the updated supervisor and source/capability guards. Extend the regression matrix through both common and validation module caches, including actual over-ceiling refusal after same-size/same-time edits under normal and -B execution. Preserve prior callable ownership, finite durable first admission and fresh-consumer missing/inconsistent/expired-record HOLD without fresh clocks. Exercise success/failure, failed-refresh rollback and foreign-source refusal before the complete pair.
9. BIG PICTURE: preserve design review, implementation, independent convergence, final native validation, pre-commit supervision, staged-candidate checks, commit hooks, push checks, exact-head hosted CI, bot/human review policy, merge, PRIMARY sync and verified cleanup. Produce a before/after phase-and-check matrix. Do not remove a stage, test, marker/profile contract, refusal, review or source binding to claim a speedup. Do not touch runtime/substrates or models.
10. UNIFY EXECUTION: consolidate duplicated native pytest policy behind a small shared implementation used by Phase B and commit execution, respecting their intentionally different full/fast test profiles. Preserve selected tests and deterministic environment; bound concurrency to at most four workers, omit all xdist-only flags for supported serial fallback or reject unavailable/disabled xdist before execution. Never silently drop selection, mock the production child, retry a crashed worker into green, or misclassify zero-collection/errors as success. Neutralize inherited exitfirst/maxfail where complete-suite execution is required. Keep failures and full durable stdout/stderr with bounded public progress.
11. MEASURE THE WIN: exercise actual public native caller paths in fresh child processes. Establish identical collected/executed test identities and outcome semantics between existing and optimized scheduling, including failing cases. Benchmark a deterministic fixture workload with independent slow jobs under both modes, report elapsed values and improvement, then validate with real relevant repository modules. Preserve all negative assertions. Do not consume another entire multi-hour retention suite as a speculative benchmark in this performance-only wave; its verified prior receipts are baseline evidence, and actual retained-suite acceptance belongs to the subsequent retention wave. Predeclared deterministic eight-independent-job fixture acceptance: optimized elapsed must be below80% of serial elapsed with identical executed identities and outcome semantics. Report both measurements; fixture improvement is not an end-to-end delivery speedup claim.
12. BUDGET CONSISTENCY: reproduce enclosing budget conflicts with real native caller/short-lived subprocess fixtures. Use one typed, immutable, invocation/source-bound budget contract admitted by existing launcher/dispatcher/builders; account for sequential child stages, review overhead and existing finite leaf budgets. Fail before expensive work if a requested schedule is inadmissible. Improve execution first; do not merely raise global defaults, introduce unlimited waits or silently mint extra retry time. Any justified per-invocation envelope must preserve finite ceiling, original baseline, remaining elapsed budget, per-key meaning and source/config/command binding across parent and fresh child. Unknown, stale, malformed, over-cap and mismatched budgets HOLD. Existing recovery overrides must not silently change a different key or reset an exhausted budget.
13. VISIBLE PROGRESS: retain actual argv, selected profile, start/finish time, elapsed/budget, exit status and diagnostic output for each native validation. Report real stage transitions through existing observability surfaces; bounded progress must not become a new always-running watchdog or another orchestration layer. Timeout/interruption diagnostics must preserve available output and identify the actual leaf/parent boundary; never diagnose assertion failure from timeout alone.
14. OWNERSHIP LIMIT: retain all currently landed process identity, uncertainty HOLD and non-replay guards. This wave does not solve full unsampled Darwin lifetime attribution and must not import the stopped R5 producer or call sampling/PGID absence/normal parent exit proof of whole-tree release. No broad signal, kill-unknown, mocked absence, false successful cleanup or old checkpoint/receipt replay. Verify interruption and timeout behavior of the new validation execution through actual children, including changed-identity/uncertainty refusal. If a new execution mode cannot satisfy existing safeguards, fail before actor admission rather than weaken them.
15. RECURRING FIXES: changes must live in native launcher/executor/recovery/shared-script paths and work for both configured orchestrators, with roles resolved from live config. No root-only repair command or another private learning store. Relevant agent instructions may be addressed in a later evidence-backed priority wave through pipeline review; this wave changes only the declared AgentRunbook documentation, not Claude-owned files or agent personas.
16. VALIDATION ORDER: narrow real success/failure/timeout/worker-absence/interruption/source-drift/budget controls first; then the complete declared fourteen-module gate and identical independent sweep on unchanged final source/index/config context. Keep all failed runs and exact command/env/count/duration/log hashes. Outer native gates, independent review and hosted CI remain required. Do not falsely reuse old proof as current acceptance. Full pair bounded by the existing7200-second validation ceiling each; no reduced selector sweep, assertion weakening or new skips/exemptions. Run the existing private-attribute integrity checker across changed test modules before the expensive full pair and review, retaining the final authoritative checker; use public constructors rather than new private-access exceptions. Also execute all six existing control-surface invariants before the expensive pair and retain authoritative final checks. Keep the checker unchanged; the preserved docstring fix already resolves the glob/global false positive.
17. OPTION A CATALOG BINDING (founder decision 2026-11-26): the catalog binding for the gate and the identical sweep is the admission-time pinned copy /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/workingrcx-pipeline-throughput-r14-2026-11-26-admission/models_cache.pinned.json (sha256 92696a48cd7be4ddcea309d48a64b760aaf1169899e6973b2c1073702e54362c, fetched_at 2026-11-27T04:07:06.919524Z), bound byte-for-byte and re-hashed before and after each run. The live /Users/jeffabrams/.codex/models_cache.json is observation-only: a change confined to its fetched_at value is recorded with full before/after bytes, and any change to its decoded model entries (canonical models sha256 583d4fd693d339ce050d46d1fdd003103e756db7a7c72e0974fa025b9941379b at admission) HOLDs before further actor admission. No gate or sweep module reads the catalog; never edit, refresh or replace the live catalog.
18. HEARTBEAT TEST FIX: carry the reviewed fix in mu/tests/tools/test_phase_b_executor.py: the native real-process release helper's detached heartbeat child publishes each pulse atomically (sibling temporary file then replace) and its liveness check waits boundedly for a changed, non-empty pulse; every other assertion, including the escaped child alive at the HOLD, is unchanged. Its regions do not overlap R7's hunks in that file.
19. CLOSURES: complete the three carried closure records under reports/archive/deferred/ (R7's bridge blockers, the Phase B heartbeat observation-window finding, and the pre-commit targeted pytest gate budget finding resolved by R7's bounded shared validation execution). Never add a non-README file under reports/deferred/blocking/: the route builder and the pre-commit supervisor package list every such file as an active blocker. Record any blocking finding of this wave in the packet and the implementation evidence JSON instead.
20. TRACKER: TASKS.md is carried verbatim from the preserved PRIMARY checkpoint and gains only this wave's tracker note. Owner40 is priority execution/budget repair; owner38 retention remains pending. Six exact folders still need native one-use retirement and the four original PRs 1337/1336/1335/1325 remain open; never claim stale PRs disposed or folders removed from this wave.
21. NATIVE GOVERNANCE: use actual packet validator before handoff; never mutate builder-owned normative content or append extra H2 sections. Native actors own all product/test/docs edits, staging, generated caps, commit/push/CI/review/merge/PRIMARY sync. Root admission is not approval. Record actual local status without prospective delivery claims. Preserve all newer dev guards and current source/config/catalog authority; no old whole-file donor transplant.
22. FOUNDER QUOTA: stop immediately at30percent remaining or less; Root one-shot private checks enforce this. No model downgrade, provider/access manipulation, durable quota latch, automatic reset or background quota watchdog. New diagnostics/review evidence belong in /Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/workingrcx-pipeline-throughput-r14-2026-11-26-phase-b on UUID-verified WD RCX Recovery; active code stays in the internal worktree. Preserve all recovery history; no source retirement or live purge in this wave; leave Parallels/Crucial/TimeMachine/Backblaze untouched.
23. PROOF AND SCOPE LIMITS: R7's passes and HOLDs are historical; this wave needs fresh source/index/config-bound proof and every delivery gate. Exhausted R6/R7 authorities are not reset or replayed; this is a fresh admission carrying R7's preserved source. Existing owner 40 follow-ups remain; no new numbered prerequisite queues. Preserve all old worktrees/recovery history. No scope expansion into runtime, model/persona/Claude surfaces, backups, retirement or the separate unsampled Darwin lifetime redesign.
24. Questions? Concerns? Thoughts? -- Think hard
25. VERIFY THE CARRIED MIGRATION (founder-authorized scope expansion, 2026-11-26; done in R11): R7's shared runner replaces the old pre-commit targeted runner, so the targeted-runner tests in mu/tests/tools/test_commit_executor_post_merge_cleanup.py no longer match the implementation. Migrate them to the shared validation_execution runner while preserving every behavioral assertion they make (selectors and per-selector budgets, nonzero-failure output, timeout reporting, marker-only deselection semantics, empty selection behavior and the bounded parallel execution policy); change nothing else in that module.
26. VERIFY THE CARRIED QUOTING FIX (done in R11): in the test_validation_execution.py fixture that builds PYTEST_ADDOPTS, quote the JUnit output path so runs under a base temporary directory containing spaces pass; add a regression with a space-containing base temporary directory.
27. VERIFY THE CARRIED STALE-IMPORT REPAIR (done in R12): R12's pre-commit supervisor found that the supervisor's conditional dependency refresh decided from path-and-symbol checks, which do not prove which source bytes executed (an isolated reproduction retained a stale 9900-second ceiling and admitted 9000 seconds). R12's re-entry repaired it in four production modules with tests in test_meta_bridge_client.py. Verify the repair and its regression; change it only where review requires.
28. VERIFY THE CARRIED FIXTURE FIX (made by R12's tier-3 recovery delegate, reviewed in R13): test_recovery_gate.py's retained_native_scratch fixture now sets gc.auto 0 and maintenance.auto false before its first commit, so automatic git maintenance cannot repack the fixture repository during the new test that compares exact .git bytes. Review it like any carried change, then run test_hybrid_child_receipts_and_live_environment_are_contained 20 times in a row and record every result.
29. EVIDENCE BINDING: after ANY code change in this wave, including re-entry repairs, re-run the declared gate and the identical sweep on the final candidate before writing or updating the evidence record. Record source and test file hashes as taken at evidence time; never present them as final hashes of files the executors generate later (the TASKS.md tracker note, the nonblocker report, the L4 indicator).
30. DOCS CHECK IGNORES GIT-IGNORED FILES: the Codex desktop app's external-agent import sync writes untracked, git-ignored copies of the Claude configuration (.codex/ and .agents/skills/*/SKILL.md) into lanes where a Claude session ran. R13's final docs check (check_docs_consistency.sh step 6, the docs sync report) counted four of them as unclassified markdown and stopped the wave. The report walks the filesystem; make it, and its docs/ subfolder discovery, consider only markdown that git tracks or could add (git ls-files --cached --others --exclude-standard semantics), because ignored files cannot be committed. Keep every classification rule. Add regressions: an ignored .agents/skills/x/SKILL.md is not reported; an untracked, non-ignored unclassified markdown file still is. Apply the same rule in test_doc_governance.py if its own filesystem walk counts ignored files. Never edit ~/.codex or any codex-owned file.
31. VERIFY THE CARRIED RUNNER REPAIR (done in R13): R13's pre-commit supervisor found that the validation runner treated the leader process's exit as completion and froze output and hashes while descendants inheriting its output were still writing. R13's re-entry repaired it and the re-entry review returned GO. Verify the repair and its regression; change it only where review requires.

## Constraints

- Keep active development internal and recovery evidence on the UUID-bound WD store.
- Preserve all phases, selected checks, assertions, source/authority bindings and current ownership/refusal guards.
- No runtime/substrate/model/access/Claude/backup changes, live purge, historical merge or original-PR disposition.
- No blanket timeout inflation, unbounded waits, shortened sweep, stale success, unsupported process-release claim or transplanted R5 authority.
- All reviewer output and post-envelope recheck files must stay within the frozen candidate allowlist. Use the exact declared nonblocking report slot; record blocking findings in the packet and the implementation evidence JSON, never as a file under reports/deferred/blocking/. Preserve truthful disposition; do not create ad-hoc report suffixes or widen live authority.
- Hybrid recovery validation may not silently narrow selectors/profile, exempt generated worktree output, reset clocks or mask the most recent validator failure behind old successful logs. Full required coverage and finite coherent scheduling are both mandatory.
- A cached module self-reporting the hash of current disk bytes is not execution provenance. Preserve all finite ceilings and old callable ownership; no exhausted-authority reset or replay.
- This wave is the next native publication, so it carries the founder tracker checkpoint (TASKS.md) verbatim. Its historical observation lines are records, not claims of this wave; findings against their historical wording are non-blocking DOC_ACCURACY, deferred, and never rewritten here.
- Founder authorization (immutable): the 2026-11-25 landing handoff (resolve R7's catalog boundary, then finish owner 40 delivery) and the 2026-11-26 standing instruction to execute the recommended option autonomously, under which Option A (one admission-time pinned catalog for both runs) was selected; the acceptance rule itself is unchanged.
- This wave runs with the native phase_a bridge turn-budget override (RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY=phase_a, 1500s) applied from the launch environment; tracked executor timeouts are unchanged.
- Tests outside this wave's allowlist that fail in CI but pass locally on the same head are owner-40 findings filed separately; do not edit them in this wave.
- Supersession: workingrcx-pipeline-throughput-r8-2026-11-26 passed Phase A, then its Phase B Claude implementer stopped on the Claude CLI's 100-turn cap (error_max_turns) and recovery escalated; nothing was committed. Its successor workingrcx-pipeline-throughput-r9-2026-11-26 was refused at launch setup because the per-wave max_turns override also targets the codex reviewer, which has no turn flag. This wave runs under the committed 400-turn Claude implementer budget (PR #1349) with no per-wave override.
- R8's implementer edits (preserved, unreviewed) are carried on top of the R7 candidate: a supervisor-import provenance check in meta_bridge_client with its tests, removal of the now-unused marker-deselection helper from commit_executor, and small meta_bridge_supervisor and AgentRunbook edits. Review them like every other carried change; keep, correct or revert them on the evidence.
- An untracked .codex/ and .agents/ mirror of the Claude configuration can appear in the lane after a Claude session (writer unidentified, under owner-40 investigation). Those paths are excluded locally; never stage, edit or depend on them.
- Supersession: workingrcx-pipeline-throughput-r10-2026-11-26 completed its Claude implementation inside the 400-turn budget, and its declared gate and identical sweep each passed 5306 tests on the pinned catalog. Its independent review returned QUESTION for authority to migrate the incompatible post-merge cleanup tests (POLICY_BOUND) and flagged the unquoted fixture JUnit path (DEFECT, low). Nothing was committed.
- Supersession: workingrcx-pipeline-throughput-r11-2026-11-26 completed the authorized migration and the quoting fix and ran the declared gate and the identical sweep (5662 passed in each, per its harness receipts), then its Claude implementer exhausted the 400-turn budget before writing the evidence record. Nothing was committed.
- Supersession: workingrcx-pipeline-throughput-r12-2026-11-26 carried that work. Its Phase B converged: the pre-commit supervisor found a stale-import defect, the re-entry repaired it, the re-entry review returned GO after the gate and sweep were re-run on the repaired code, and the supervisor's second pass returned COMMIT_GO. The commit executor's pre-commit targeted gate then failed one test that is new in the candidate (test_hybrid_child_receipts_and_live_environment_are_contained, an unexpected pack file in its fixture repository's .git snapshot). The tier-3 recovery delegate's fixture fix passed its validation runs, but recovery refused it three times because the launcher's log inside the lane counted as out-of-scope drift. Nothing was committed. This wave carries R12's candidate and that fixture fix: verify them, then run the declared gate and the identical sweep and write the evidence record; do not re-author carried work.
- This wave's launcher output is written outside the lane worktree: the hybrid tier-3 audit counts writes by any other process inside the lane as drift (filed separately as an owner-40 blocker).
- Founder authorization (immutable): the founder's standing instruction of 2026-11-26 to proceed autonomously on the orchestrator's recommendations authorizes adding mu/tests/tools/test_commit_executor_post_merge_cleanup.py to this candidate solely to migrate tests that pin the replaced runner, preserving their behavioral assertions.
- Supersession: workingrcx-pipeline-throughput-r13-2026-11-26 carried R12's work. Its Phase B converged: the pre-commit supervisor found the inherited-output completion regression in the validation runner, the re-entry repaired it, the re-entry review returned GO and the supervisor's second pass returned COMMIT_GO. Phase B's final docs check then counted four git-ignored .agents/skills copies, written by the Codex desktop import sync, as unclassified markdown; the closeout attestation refused and the wave stopped before commit. A wave that took a re-entry round cannot resume from that point, so this fresh wave carries R13's candidate. Nothing was committed.
- Orchestrator decision under the founder's standing autonomy (2026-11-27): the Codex desktop import sync stays on, because the founder uses Codex for other work; RCX's checks are made immune to its ignored copies instead.

## Stop conditions

- Hold on base/source/config drift, catalog drift as defined by the Option A binding (pinned-copy bytes changed, or the live catalog's decoded model entries changed), undeclared mutation, invalid authority, uncertain ownership or unavailable required execution primitive.
- Stop immediately at founder30percent reserve or provider capacity stop; preserve diagnostic outputs and source, never auto-reset.
- If the finite repair cannot preserve the existing guarantees, report the exact counterexample; do not expand into unsupported kernel-lifetime redesign or hide the limit.
- Halt before launch if origin/dev is not baced34fe827da129a02ae5264485be688924d8c.
- Halt before launch if the lane contains any non-README file under reports/deferred/blocking/.
- Halt if the carried TASKS.md or any carried candidate file cannot be verified against the admission record.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal --max-worker-restart=0 --maxfail=0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_validation_execution.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_common.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_docs_sync_report.py mu/tests/docs/test_doc_governance.py mu/tests/docs/test_docs_registry_agent_memory_exempt.py --tb=short --durations=20`

## Acceptance criteria

- Actual native public callers preserve phase/check coverage and test identities; the deterministic eight-job comparison achieves parallel elapsed below80% of serial elapsed without masked failures. This does not establish end-to-end delivery speedup.
- Deterministic admitted stage budgets remain finite, source/command/config bound and coherent across parent/child/recovery; invalid/stale/over-cap/reset attempts fail before expensive execution.
- Actual timeout/interruption/worker-unavailable controls retain output and refuse unsafe continuation; existing process-release semantics unchanged.
- Complete declared fourteen-module gate and identical sweep pass on final continuous bindings, with the catalog bound to the admission-time pinned copy and no change to the live catalog's decoded model entries; native independent review, staged L4 checks, exact-head hosted CI and actual merge/PRIMARY sync remain independent requirements.
- All tracker IDs/owners/history preserved and priority state accurate; no claim that preserved retention, historical PRs or folders are already merged/retired.
- No new agent persona/instruction files in this wave; any later such changes use the native review pipeline as founder authorized.
- Actual-child environment tests pass with absent and inherited ownership markers while preserving all hermeticity and ownership assertions.
- The native post-private-review GO/nonblocker transition can survive a later failed final gate and resume from exact durable authority in a fresh process; drift, replay and uncertain ownership still refuse. Root never refreshes or fabricates checkpoints.
- Warm and cold supervisor callers exercise the same source-compatible validation API; fresh budget consumers never turn missing retained state into a new clock for an admitted invocation.
- Inherited xdist-only options in explicit serial mode and a cached common module from an unexpected source path refuse before child admission; actual success/failure and current guard semantics remain intact.
- Retain the restored dispatcher launch/lifetime and actual resampling regression controls, including all child reaping, uncertainty refusal, exact intended launch assertions and real reparenting-with-birth negative coverage; old failure reproductions need not be repeated unchanged.
- Actual native review/correction fixtures prove validated exact report destinations, early refusal of undeclared review output before corrective mutation, and continued legitimate REQUEST_CHANGES-to-correction-to-fresh-review flow. Blocking findings stay blocking; candidate/source/index/configuration/owner drift and old-authority replay remain refused. Existing later guards and every phase/commit/CI/merge requirement remain intact.
- Actual hybrid recovery caller completes the selected four-module full-profile validation with an admissible finite schedule and preserved targets; no new undeclared repository output. Fixture comparisons retain identical identities and failure semantics, including live-lane environment isolation.
- Validation HOLD survives every touched caller and CLI boundary without checkpoint cleanup or further recovery/commit/review admission; ordinary failures retain existing behavior. Native scope audit and immutable authority checks remain effective.
- Actual supervisor handoff followed by actual budget admission refuses the reproduced over-ceiling request despite stale same-size/same-time common bytecode, under normal and -B execution; exact source identity and prior callable ownership are verified.
- Both handoff dependencies have focused warm/cold/absent, wrong-source, failed-refresh/interruption and source-drift coverage before the full unchanged gate/sweep. All existing recovery, review, handoff, finite-budget and scope guards remain effective.
- The heartbeat liveness check publishes pulses atomically and waits boundedly for a changed, non-empty pulse; no other assertion in test_phase_b_executor.py is weakened.
- The committed tree contains no non-README file under reports/deferred/blocking/; the three closure records live under reports/archive/deferred/.
- TASKS.md equals the preserved PRIMARY checkpoint plus only this wave's tracker note.
- The migrated post-merge cleanup tests pass against the shared runner with every original behavioral assertion preserved, and that module is part of the declared gate and the identical sweep.
- The test_validation_execution.py fixture quotes its JUnit path; a regression with a space-containing base temporary directory passes.
- test_hybrid_child_receipts_and_live_environment_are_contained passes 20 consecutive runs; its fixture disables automatic git gc and maintenance; no assertion is weakened.
- The evidence record's gate and sweep results bind the final candidate's source and test files.
- The docs sync report ignores git-ignored markdown and still reports untracked, non-ignored unclassified markdown; its regressions pass and its module is part of the declared gate and the identical sweep.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-pipeline-throughput-r14-2026-11-26`.
- Governing packet: this file, `reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md`.
- TASKS.md authority: the 2026-11-26 tracker sync note for wave `workingrcx-pipeline-throughput-r14-2026-11-26` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-pipeline-throughput-r14-2026-11-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-pipeline-throughput-r14-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/docs/agents/AgentRunbook.v0.md`
  - `mu/docs/core/DocGovernance.v0.md`
  - `mu/tests/docs/test_doc_governance.py`
  - `mu/tests/docs/test_docs_registry_agent_memory_exempt.py`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_docs_sync_report.py`
  - `mu/tests/tools/test_executor_common.py`
  - `mu/tests/tools/test_executor_config_alignment.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_meta_bridge_client.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tests/tools/test_validation_execution.py`
  - `mu/tools/agents/meta_bridge_client.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/docs/docs_sync_report.py`
  - `mu/tools/docs/shared_doc_config.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/executors/validation_execution.py`
  - `reports/archive/deferred/commit-targeted-pytest-gate-phase-b-module-budget-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`
  - `reports/archive/deferred/phase-b-heartbeat-observation-window-ci-flake-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`
  - `reports/archive/deferred/workingrcx-pipeline-throughput-r7-2026-10-29_bridge_blockers_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`
  - `reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md`
  - `reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-pipeline-throughput-r14-2026-11-26 --output reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal --max-worker-restart=0 --maxfail=0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_validation_execution.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_common.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_docs_sync_report.py mu/tests/docs/test_doc_governance.py mu/tests/docs/test_docs_registry_agent_memory_exempt.py --tb=short --durations=20`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 15 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/AgentRunbook.v0.md`, `mu/docs/core/DocGovernance.v0.md`, `mu/tests/docs/test_doc_governance.py`, `mu/tests/docs/test_docs_registry_agent_memory_exempt.py`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_docs_sync_report.py`, `mu/tests/tools/test_executor_common.py`, `mu/tests/tools/test_executor_config_alignment.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_meta_bridge_client.py`, `mu/tests/tools/test_meta_bridge_supervisor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tests/tools/test_validation_execution.py`, `mu/tools/agents/meta_bridge_client.py`, `mu/tools/agents/meta_bridge_supervisor.py`, `mu/tools/docs/docs_sync_report.py`, `mu/tools/docs/shared_doc_config.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/executor_common.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `mu/tools/executors/validation_execution.py`, `reports/archive/deferred/commit-targeted-pytest-gate-phase-b-module-budget-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`, `reports/archive/deferred/phase-b-heartbeat-observation-window-ci-flake-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`, `reports/archive/deferred/workingrcx-pipeline-throughput-r7-2026-10-29_bridge_blockers_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`, +3 more, `mu/tests/docs/test_growth_caps.py`.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-pipeline-throughput-r14-2026-11-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `workingrcx-pipeline-throughput-r14-2026-11-26`
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

- Refresh wave: `workingrcx-pipeline-throughput-r14-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a1fd9beb8262267eee3a3929de0c0b51cdad7eee9ed86a529e083973e3f151c5`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal --max-worker-restart=0 --maxfail=0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_validation_execution.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_common.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_meta_bridge_supervisor.py mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_meta_bridge_client.py mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_docs_sync_report.py mu/tests/docs/test_doc_governance.py mu/tests/docs/test_docs_registry_agent_memory_exempt.py --tb=short --durations=20`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 15 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/docs/agents/AgentRunbook.v0.md`, `mu/docs/core/DocGovernance.v0.md`, `mu/tests/docs/test_doc_governance.py`, `mu/tests/docs/test_docs_registry_agent_memory_exempt.py`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tests/tools/test_docs_sync_report.py`, `mu/tests/tools/test_executor_common.py`, `mu/tests/tools/test_executor_config_alignment.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_meta_bridge_client.py`, `mu/tests/tools/test_meta_bridge_supervisor.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tests/tools/test_validation_execution.py`, `mu/tools/agents/meta_bridge_client.py`, `mu/tools/agents/meta_bridge_supervisor.py`, `mu/tools/docs/docs_sync_report.py`, `mu/tools/docs/shared_doc_config.py`, `mu/tools/executors/commit_executor.py`, `mu/tools/executors/executor_common.py`, `mu/tools/executors/executor_dispatch.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/recovery_gate.py`, `mu/tools/executors/validation_execution.py`, `reports/archive/deferred/commit-targeted-pytest-gate-phase-b-module-budget-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`, `reports/archive/deferred/phase-b-heartbeat-observation-window-ci-flake-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`, `reports/archive/deferred/workingrcx-pipeline-throughput-r7-2026-10-29_bridge_blockers_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`, +3 more, `mu/tests/docs/test_growth_caps.py`.
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/docs/agents/AgentRunbook.v0.md`
  - `mu/docs/core/DocGovernance.v0.md`
  - `mu/tests/docs/test_doc_governance.py`
  - `mu/tests/docs/test_docs_registry_agent_memory_exempt.py`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_docs_sync_report.py`
  - `mu/tests/tools/test_executor_common.py`
  - `mu/tests/tools/test_executor_config_alignment.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_meta_bridge_client.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tests/tools/test_validation_execution.py`
  - `mu/tools/agents/meta_bridge_client.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/docs/docs_sync_report.py`
  - `mu/tools/docs/shared_doc_config.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `mu/tools/executors/validation_execution.py`
  - `reports/archive/deferred/commit-targeted-pytest-gate-phase-b-module-budget-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`
  - `reports/archive/deferred/phase-b-heartbeat-observation-window-ci-flake-2026-11-26_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`
  - `reports/archive/deferred/workingrcx-pipeline-throughput-r7-2026-10-29_bridge_blockers_closed-by-workingrcx-pipeline-throughput-r14-2026-11-26.md`
  - `reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_2026-11-26.md`
  - `reports/control_plane/workingrcx-pipeline-throughput-r14-2026-11-26_implementation_evidence.json`
  - `reports/l4_wave_indicators/workingrcx-pipeline-throughput-r14-2026-11-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
