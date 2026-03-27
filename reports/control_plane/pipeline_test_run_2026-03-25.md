<!-- DOC_STATUS: REFERENCE -->

# Pipeline Test Run

Date: 2026-03-25
Status: Eighteenth live follow-up on 2026-03-27 turned the local Step 14 plus supervisor-context slice into a tracker-note uniqueness follow-up. The resubmitted pre-commit package eventually cleared with `COMMIT_GO`, but the resumed commit executor then failed at Step 3 because `ensure_tracker_note` treated the canonical tracker note and the authorized `[PIPELINE-TEST-RUN]` NEXT-item reference as a duplicate wave-id collision. The active fix is now Step 14 registration wait plus supervisor-context preservation plus tracker-note uniqueness keyed to actual tracker-note lines instead of arbitrary whole-file wave-id mentions.
Phase-A-Lock: LOCKED
Purpose: smallest honest end-to-end pipeline smoke on a low-risk control-plane-only task

## Goal

Exercise the normal post-merge -> Phase A -> Phase B -> pre-commit -> commit path
using a deliberately trivial lane. The purpose is to learn where the mechanics
break when the task itself is not demanding.

## Task Shape

The task is intentionally boring:

1. stay inside control-plane / doc-truth surfaces
2. avoid runtime or substrate semantics
3. prefer one bounded tracked artifact or note update over broad changes
4. stop at the first hard pipeline failure instead of fixing through it

## Success Condition

The pipeline advances mechanically without substantive blocker findings that are
caused by the task itself. If it fails, the failure should be attributable to
pipeline mechanics, package truth, or routing logic rather than task complexity.

## Founder Scope Lock

- `[PIPELINE-TEST-RUN]` remains a full-fidelity live-agent smoke. Live
  SDK/Bun readiness is part of the proof because Phase A invokes the real
  `run_review.py` path through the executor surface.
- Do not normalize SDK/Bun readiness out-of-band before resuming this packet.
  If the live runner stack is the thing that breaks, that is the boring-path
  result.
- Manual follow-up after a stop is allowed only to keep packet/tracker truth
  honest or to fix the pipeline itself. It does not rewrite the original stop.

## Notes

- This packet exists to test pipeline mechanics, not to advance RCX runtime work.
- Non-blocking observations may be logged only if the clean run actually gets
  through to merge.

## Canonical rollout order

1. ~~Truth-sync the active control-plane queue so `[PIPELINE-TEST-RUN]` is the
   first unambiguous next proof item after continuation hardening `s1+s2`.~~
   **(done 2026-03-26)**
2. Run the deliberately boring control-plane smoke through post-merge ->
   Phase A -> Phase B -> pre-commit -> commit/merge.
3. If the run stops, record the exact stage and reason in this packet before
   any corrective follow-up.
4. Only after a clean boring-path pass should `[COMMIT-EXECUTOR-E2E]` run on a
   disposable branch.
5. Only after both execution proofs are green should latency optimization
   proceed aggressively.

## First Live Stop (2026-03-26)

- `post-merge-supervisor` passed all 6 validation gates and then returned
  `STOP_FOR_TRIAGE_DISCUSSION`.
- Exact stop reason: this packet had no canonical rollout order section, and
  `TASKS.md` still placed `[COMMIT-EXECUTOR-E2E]` ahead of this item with stale
  blocker/packet truth.
- Result: the smoke run did not reach Phase A or Phase B. Rerun only after the
  tracker/packet truth sync is in repo-tracked form.

## Second Live Stop (2026-03-26)

- After `pipeline-smoke-truth-sync` landed on PR `#672`, rerunning
  `python3 mu/tools/executors/executor_dispatch.py post-merge-supervisor --package .scratch/pipeline_test_post_merge_package.json --json --verbose`
  returned `ROUTE_PHASE_A` and confirmed `[PIPELINE-TEST-RUN]` as the canonical
  next bounded item.
- The next command,
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`,
  stopped before any bridge round. Phase A reported `agent_exit_code: 2` and
  failed closed on the SDK agent-review hard gate.
- Direct repro of the underlying review path,
  `PYTHONHASHSEED=0 python3 tools/runners/run_review.py reports/control_plane/pipeline_test_run_2026-03-25.md --depth quick --no-memory`,
  returned `exit 4` with `AGENT PREFLIGHT FAILED` and the exact reason
  `SDK preflight timed out after 20s`.
- The runtime shell itself is not generically broken:
  `PYTHONHASHSEED=0 python3 tools/checks/check_agent_runtime.py` returned
  `Overall runnable in this shell: PASS`.
- Result at that time: the boring-path smoke was no longer blocked on routing
  truth. It was blocked on a Phase A `run_review.py` preflight mismatch that had
  to be recorded before any corrective follow-up.

## Authoritative Repro Contract For The Second Live Stop

- Primary stop command:
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
- Authoritative failure surface: the Phase A executor result for that exact
  command. At the time of the stop, Phase A surfaced `agent_exit_code: 2`
  and the underlying `run_review.py` invocation was still using its default
  `--preflight-timeout 20` budget.
- Supporting direct repro command for the live runner path:
  `PYTHONHASHSEED=0 python3 tools/runners/run_review.py reports/control_plane/pipeline_test_run_2026-03-25.md --depth quick --no-memory`
- Host/runtime tuple for the stop environment:
  `python3 3.13.2 x86_64` on `macOS-26.3.1-x86_64-i386-64bit-Mach-O`,
  `uname -m = x86_64`, `bun 1.3.11` at
  `/Users/jeffabrams/.local/bin/bun` (`Mach-O 64-bit executable arm64`), with
  live runner output warning that the current CPU/Bun pairing lacks AVX support.
- Diagnostic precedence:
  1. the Phase A executor output for the failing run
  2. a same-tree direct `run_review.py` repro
  3. `check_agent_runtime.py` as a secondary environment probe only
- Later reruns on a dirty worktree are secondary evidence. Once warm-state
  effects or corrective follow-up change the runner behavior, they do not
  supersede the original stop record.

## Third Live Stop (2026-03-26)

- After the preflight retry + diagnostic follow-up was patched locally,
  `PYTHONHASHSEED=0 python3 tools/checks/check_agent_runtime.py` returned
  `SDK preflight: PASS` and `Overall runnable in this shell: PASS`.
- Rerunning
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
  again still stopped before bridge review, but this time with a different
  failure shape:
  `agent_exit_code: 2` and `SDK agent review failed (exit=2). Hard gate: agents must pass before bridge review.`
- Current runner truth says that interpretation is wrong. `run_review.py`
  classifies exit code `2` as warnings / soft gate, not a hard failure:
  `mu/tools/runners/run_review.py` returns `2` for non-hard-gate residue, and
  `mu/docs/agents/AgentRunbook.v0.md` defines `2 = Warnings (soft gate)`.
- Sampled same-tree direct repro during this stop reached live agent verdicts
  instead of preflight failure: `structural-proof` reported
  `NO_STRUCTURAL_CLAIMS` and `expert` reported `COULD_SIMPLIFY`.
- Result: the active boring-path blocker has moved again. The next pipeline
  defect is now Phase A misclassifying soft `run_review.py` exit `2` warnings as
  a hard stop instead of allowing bridge review to begin.

## Fourth Live Stop (2026-03-26)

- After the Phase A soft-gate fix, rerunning
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
  advanced past agent review and created bridge job `phase-a-r1-f825d257`.
- The run then stalled inside bridge review instead of producing a reviewer
  envelope. After more than 7 minutes, the bridge job still reported
  `status: REVIEWER_RUNNING`, the in-flight reviewer raw file remained `0`
  bytes, and the rendered transcript still showed only the synthetic reader turn.
- Direct status repro:
  `python3 tools/agents/bridge_supervisor.py status phase-a-r1-f825d257`
  reported `raw_size_bytes: 0` for the reviewer turn started at
  `2026-03-26T20:38:38+00:00`.
- Process repro at the same time showed an idle bridge stack:
  `bridge_supervisor.py review`, `node ... codex exec`, and the native
  `codex exec` child were all still alive with near-zero CPU while the reviewer
  raw output remained empty.
- Result: the active boring-path blocker moved again. Phase A still used the
  opaque bridge subprocess wrapper, so this reviewer-running/no-output state had
  no stale watchdog and would have waited until the outer 1200s timeout instead
  of failing closed promptly.

## Fifth Live Stop (2026-03-26)

- After the local follow-up patched the SDK preflight retry, the Phase A
  soft-gate interpretation, the repo-root detection in
  `check_agent_runtime.py`, and an external Phase A bridge stale watchdog,
  another same-tree rerun of
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
  still stopped at the agent-review gate.
- Same-tree direct repro,
  `PYTHONHASHSEED=0 python3 tools/runners/run_review.py reports/control_plane/pipeline_test_run_2026-03-25.md --depth quick --no-memory --output .scratch/pipeline_test_run_review.md`,
  showed the remaining hard-gate blockers more precisely.
- `verifier` blocked on docs-truth drift in this packet itself: the file was
  tagged `DOC_STATUS: DESIGN_SPEC` even though it is an operational run log,
  and the packet/tracker state had drifted behind the current dirty-tree
  follow-up.
- `adversary` blocked on two bridge hardening gaps surfaced by this packet:
  crash recovery accepted a completed reviewer verdict when
  `reviewer_input_validation_sha` was missing, and direct
  `bridge_supervisor.py review` still relied on the full adapter timeout rather
  than an internal shorter per-turn fail-closed cap.
- Result: the active boring-path blocker moved again. The next corrective slice
  is no longer queue truth, SDK preflight, or Phase A soft-gate handling. It is
  now packet/tracker truth sync plus the bridge recovery / turn-time fail-closed
  path.

## Landed Pre-req Reference

- The earlier continuation hardening that made this smoke run possible remains
  tracked in `pipeline-continuation-hardening-s1` and
  `pipeline-continuation-hardening-s2`; keep this packet focused on the
  boring-path stop sequence itself.

## Sixth Live Stop (2026-03-26)

- After the current same-tree direct repro of `run_review.py` finished with
  `Overall: APPROVED` and only a medium adversary warning, rerunning
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
  finally cleared the agent-review gate and re-entered bridge review.
- The bridge job `phase-a-r1-ff762af9` then reproduced the reviewer stall in a
  more precise form. `python3 tools/agents/bridge_supervisor.py status phase-a-r1-ff762af9`
  reported `status: REVIEWER_RUNNING` with
  `raw_size_bytes: 0` for the reviewer turn, even though the bridge stderr log
  kept growing rapidly.
- Phase A's external stale watchdog did not fire because its progress snapshot
  still treated stderr-log growth as activity. In this stop, that meant noisy
  reviewer stderr masked a zero-output reviewer stall instead of allowing the
  outer watchdog to fail closed at the intended stale threshold.
- Local process inspection confirmed the exact shape:
  `phase_a_executor.py` was sleeping in its bridge poll loop, the bridge
  supervisor was still running, the reviewer raw output stayed at `0` bytes,
  and `.scratch/phase_a_bridge_phase-a-r1-ff762af9.stderr.log` grew to nearly
  1 MB with reviewer stderr chatter.
- Result: the active boring-path blocker moved again. The next required fix is
  an internal bridge zero-output watchdog that fails reviewer turns closed based
  on authoritative raw-output progress, not just outer stderr growth.

## Seventh Live Stop (2026-03-26)

- After the internal bridge zero-output watchdog patch, rerunning
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
  reached bridge review again and stopped promptly instead of hanging.
- The exact bridge stderr now shows the intended fail-closed reason:
  `Adapter 'codex' produced no stdout after 120.0s`.
- The remaining defect was in Phase A's interpretation layer, not in the bridge
  watchdog itself. The bridge subprocess exited nonzero, but
  `phase_a_executor.py` still inspected the stale rendered transcript first and
  reported `Bridge returned unrecognized decision — cannot proceed`.
- Status repro for job `phase-a-r1-c012ad26` confirmed the mismatch:
  `python3 tools/agents/bridge_supervisor.py status phase-a-r1-c012ad26`
  still showed `AWAITING_REVIEWER_APPROVAL`, no terminal decision, and only the
  reader turn in the rendered transcript.
- Result: the active boring-path blocker moved again. The next required fix is
  Phase A bridge error propagation: nonzero bridge exits must surface the real
  stderr cause and must not be masked by stale rendered output from a paused
  reader-only transcript.

## Eighth Live Stop (2026-03-26)

- After the Phase A bridge error-propagation patch, rerunning
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
  no longer stopped on bridge interpretation. The executor cleared the prior
  nonzero-exit masking bug and now failed earlier at the SDK-review gate.
- The exact live Phase A result for that rerun was:
  `agent_exit_code: 1` with stderr dominated by Bun AVX warnings, so the old
  truncated executor surface was not sufficient to explain the hard gate.
- Same-tree follow-up proved the actual blocker shape. A controlled direct run
  with
  `RCX_REVIEW_STATUS_PATH=.scratch/phase_a_review_status_latest.json PYTHONHASHSEED=0 python3 tools/runners/run_review.py reports/control_plane/pipeline_test_run_2026-03-25.md --depth quick --no-memory --output .scratch/phase_a_review_report_latest.md`
  reached the full agent group and failed hard because `adversary` returned
  `UNKNOWN` after `AGENT TIMEOUT: adversary exceeded 360s`.
- A separate same-tree direct run on the same file had already returned exit
  `2` with `Overall: APPROVED` and only a medium adversary warning. So the
  active defect is not the old bridge path anymore; it is Phase A SDK-review
  stability and observability under live agent variance.
- Result: the active boring-path blocker moved again. The next required fix is
  to give Phase A the same supervised SDK-review surface Phase B already has:
  persistent report/status artifacts, explicit timeout budget threading into
  `run_review.py`, and fail-closed diagnostics that preserve the authoritative
  hard-gate report instead of a truncated stderr summary.

## Ninth Live Stop (2026-03-26)

- After the Phase A follow-up landed in the working tree, the boring-path rerun
  advanced into modular Phase B instead of stopping in Phase A again.
- The resumed Phase B invocation reused a saved
  `.agent_bus/executors/phase_b_state.json` checkpoint at
  `completed_step: needs_phase_b_reentry`. That checkpoint still carried old
  `reentry_findings` and no scope fingerprint, even though the current staged
  candidate already contained the bridge stderr-envelope fix those findings were
  asking for.
- The live re-entry implementer output at
  `.scratch/phase_b_implementer_output_impl-ba50180d.txt` eventually recognized
  that the staged diff already contained the fix, but the implementer surface
  had no stale-progress watchdog. The parent Phase B executor stayed alive,
  emitted no new terminal state, and had to be cut manually after several
  minutes of no progress.
- Killing the stalled parent also exposed a second fail-closed gap: an orphaned
  pytest shell spawned through the implementer's tool surface outlived the
  parent executor and had to be cleaned separately.
- Result: the active boring-path blocker moved again. The next required fix is
  no longer Phase A. It is Phase B re-entry freshness plus implementer stale
  progress cleanup: refresh bridge findings when a saved re-entry checkpoint has
  drifted or lacks a scope fingerprint, and fail closed if the implementer stops
  showing output/process-tree activity before the outer 1200s timeout.

## Tenth Live Stop (2026-03-26)

- After the Phase B re-entry freshness + implementer stale-progress cleanup
  landed in the working tree, rerunning
  `python3 mu/tools/executors/executor_dispatch.py phase-a --plan-name pipeline_test_run --max-rounds 15 --json --verbose`
  advanced through the live SDK review and then through Phase A bridge review
  job `phase-a-r1-0976fc3d`, which returned `GO`.
- The Phase A executor then crashed locally while finalizing the reused packet:
  `PhaseAExecutorError: Expected one unlock line in reports/control_plane/pipeline_test_run_2026-03-25.md, found 0`.
  The reused canonical packet already carried `Phase-A-Lock: LOCKED`, so the
  rerun path reached `lock_plan()` with an already-locked control line.
- Exact live sequence:
  `agent_exit_code: 1` from `run_review.py` with contextual semantic findings,
  Phase A explicitly continued to bridge for blocking/non-blocking
  classification, the bridge subprocess exited `0`, and the rendered bridge
  transcript recorded terminal decision `GO`.
- Result: the active boring-path blocker moved again. The next required fix is
  no longer Phase B re-entry freshness or implementer cleanup. It is Phase A
  idempotent lock handling for reused tracked packets, plus structured
  fail-closed reporting if the packet's `Phase-A-Lock` control line is
  malformed instead of merely already locked.

## Eleventh Live Stop (2026-03-26)

- After the Phase A idempotent-lock fix and packet/tracker truth sync landed in
  the working tree, rerunning Phase A converged cleanly: the live SDK review
  returned warnings-only `exit_code: 2`, bridge job `phase-a-r1-32b232f1`
  returned `GO`, and `lock_plan()` preserved `Phase-A-Lock: LOCKED` on the
  reused canonical packet without crashing.
- That allowed the next supported modular step into Phase B with an explicit
  `ROUTE_PHASE_B` routing payload against the same locked packet. Phase B
  persisted the `implementer` and `agent_review` checkpoints, the narrowed SDK
  review returned warnings-only `exit_code: 2`, and bridge job
  `phase-b-r1-7453513f` returned `GO`.
- The Phase B executor still failed closed after that `GO`, but the stop was
  not in bridge or review execution. The rendered bridge transcript carried a
  low-severity `DOC_ACCURACY` finding titled
  `Bridge exit-code=1 conflates non-GO review with BridgeError infrastructure crash`.
  The local disposition heuristic promoted it to blocking solely because the
  title contained the keyword `crash`, even though the bridge summary said
  there were no blocking findings.
- Result: the active boring-path blocker moved again. The next required fix is
  Phase B disposition refinement, not more bridge plumbing: low/medium
  `DOC_ACCURACY` findings should remain non-blocking even when their wording
  quotes a blocker keyword while describing prior behavior, and the GO-path
  regression must be locked in tests.

## Twelfth Live Stop (2026-03-27)

- After the disposition refinement follow-up landed in the candidate, the
  automated commit executor ran end-to-end through Step 14 on branch
  `jabramsja/pipeline-test-run-2026-03-25`: pre-commit supervisor returned
  `COMMIT_GO`, the local commit was created, `pre-push-fast` passed, the branch
  pushed to origin, PR `#673` opened, and both required CI checks (`test` and
  `green-gate`) passed.
- Step 15 then waited for a fresh current-head `chatgpt-codex-connector`
  review, observed one on commit `78e08c92`, and stopped with
  `Unresolved human review thread from chatgpt-codex-connector`.
- The actual review finding was real, but it was not a merge-policy reason to
  classify the connector as human. The review thread identified an adjacent
  control-surface defect in `phase_a_executor.py`: `run_phase_a()` still failed
  immediately on bridge exit `1` before parsing the rendered decision, even
  though `bridge_supervisor.py review` uses exit `1` for normal `REQUEST_CHANGES`
  / `NO_GO` outcomes.
- Result: the boring-path stop moved again. The next required fix is two-part:
  `phase_a_executor.py` must mirror the Phase B non-GO bridge exit contract,
  and `commit_executor.py` Step 15 must treat `chatgpt-codex-connector` as bot
  review state and ignore outdated unresolved bot threads instead of promoting
  them to human blockers.

## Thirteenth Live Stop (2026-03-27)

- After the Twelfth-stop fixes landed in the working tree, a fresh pre-commit
  supervisor run returned `COMMIT_GO` on the staged five-file follow-up and the
  automated commit executor created local commit `8c2bc0e`
  (`fix: address pipeline-test-run review follow-up`).
- The rerun did not stop in Step 15 again. It stopped earlier at Step 11 when
  `pre-push-fast` reached the anti-cheat scan and flagged the new direct
  `_run_post_commit_pipeline()` behavioral regression in
  `mu/tests/tools/test_executor_dispatch.py` as private-helper access.
- The underlying code-path fixes were already green at that point: the direct
  Phase A regression and Step 15 bot-thread classification regressions both
  passed their focused pytest slices, and the only failing gate was the missing
  `ANTICHEAT_OK` marker on the internal-helper test line.
- Result: the boring-path stop moved again, but only by one gate. The next
  required fix is a one-line anti-cheat allowlist on the direct post-commit
  helper regression, then another bounded rerun of the automated commit path.

## Fourteenth Live Stop (2026-03-27)

- After the Thirteenth-stop follow-up landed locally, the automated commit
  executor created commit `dc15396`
  (`fix: unblock pipeline-test-run pre-push gate`), `pre-push-fast` passed,
  the branch pushed to origin, PR `#673` reused the new head, and both required
  checks (`test`, `green-gate`) passed.
- The rerun then stopped at automated Step 15. `commit_executor.py` correctly
  rejected the stale connector review on `78e08c92` and waited for a fresh
  `chatgpt-codex-connector` review on the current head `dc15396`, but no such
  review appeared within the built-in 210-second freshness window.
- A manual `@codex review` comment was posted on PR `#673` only after the
  executor had already timed out. GitHub showed the request comment with an
  `eyes` reaction, but still no current-head review object had materialized
  when the run failed closed.
- Result: the boring-path stop moved again, and it is now an honest Step 15
  orchestration defect rather than a code-review semantics bug. The next
  required fix is for Step 15 to request a current-head connector review itself
  before starting freshness polling, and to remember that request per head so
  reruns do not spam duplicate `@codex review` comments.

## Fifteenth Live Stop (2026-03-27)

- After the Fourteenth-stop follow-up landed in the working tree, the automated
  commit executor created commit `72a5d9e`
  (`fix: request current-head bot review in step15`), `pre-push-fast` passed,
  the branch pushed to origin, PR `#673` reused the new head, and both required
  checks (`test`, `green-gate`) passed.
- Step 15 then exercised the new self-request path exactly as intended. The
  executor posted one current-head `@codex review` comment on PR `#673`,
  persisted `bot_review_request_sha: 72a5d9e...` in the continuation record,
  and started the 210-second current-head freshness wait without spamming extra
  request comments.
- The run still failed closed after the full wait window because no fresh
  current-head review object ever appeared. Direct API repro showed the request
  comment acknowledged only with an `eyes` reaction from
  `chatgpt-codex-connector[bot]`, which proves request receipt but not review
  completion.
- Separate repo truth shows that review-object-only acceptance is too strict for
  the connector's actual benign path. PR `#672` received no review object at
  all; instead, the connector cleared the PR via an issue comment:
  `Codex Review: Didn't find any major issues. Swish!`
- Result: the boring-path stop moved again, but the remaining gap is now narrow
  and explicit. The next required fix is for Step 15 to accept a connector
  current-head no-issues issue comment after the latest `@codex review`
  request, while still rejecting acknowledgment-only signals (`eyes`) and any
  other non-clear bot issue comment.

## Sixteenth Live Stop (2026-03-27)

- After the Fifteenth-stop follow-up landed in the working tree, the automated
  commit executor created commit `9605f10`
  (`fix: accept connector issue-comment clearance in step15`), `pre-push-fast`
  passed, the branch pushed to origin, and PR `#673` reused the new head.
- The rerun then stopped immediately in Step 14 with the structured error
  `CI checks failed: no checks reported on the 'jabramsja/pipeline-test-run-2026-03-25' branch`.
  The continuation record at that point had advanced cleanly through
  `ensure_pr`, which proves the stop was not in pre-commit, commit, push, or PR
  sync.
- Direct repo/GitHub truth seconds later showed the failure was a registration
  race rather than a missing CI trigger. `gh pr view 673 --json statusCheckRollup`
  showed PR head `9605f10` with in-progress `test` and `green-gate` checks, and
  `gh run list --branch jabramsja/pipeline-test-run-2026-03-25 --limit 10`
  showed the new push/PR runs already live on that head.
- Additional CLI repro tightened the contract further:
  `gh pr checks 673 --required` returned pending required checks with exit `8`
  once the checks had registered, so the only bad case is the transient
  `no checks reported` window immediately after push.
- Result: the boring-path stop moved again, but the next fix is narrow and
  mechanical. Step 14 needs a bounded registration wait that retries only the
  transient `no checks reported` response before handing off to the normal
  required-check watcher.

## Seventeenth Live Stop (2026-03-27)

- After the Step 14 registration-wait follow-up was staged, rerunning
  `python3 mu/tools/executors/executor_dispatch.py pre-commit-supervisor --package .scratch/pipeline_test_run_followup_package.json -v --json`
  returned `NEEDS_PHASE_B` instead of a fresh commit-capable receipt.
- The meta-review did validate the staged wave truth, blocker acknowledgment,
  and the Step 14 repro, but it failed closed on two control-surface
  obligations it could not directly verify within the bounded package pass:
  canonical hook-receipt preservation and the absence of normal-path manual
  `git push` / `gh pr` / `merge_pr.sh` fallback in the active protocol surface.
- Local repro showed the underlying issue was package truth, not those
  obligations themselves. `mu/tools/agents/meta_bridge_supervisor.py` still
  writes both the canonical hook-compatible receipt and the per-invocation
  receipt, `mu/tools/agents/meta_bridge_client.py` still captures the exact
  per-invocation path directly, `mu/tools/checks/check_control_surface_invariants.py`
  still enforces the no-manual-fallback invariant, and
  `mu/tools/executors/phase_b_implementer.py` still forbids Phase B-local
  `git push`, `gh pr`, and merge-script execution.
- The real automation defect was one layer lower: `commit_executor.py` step 6
  was auto-building `.scratch/auto_supervisor_package.json` with
  `scope_items = files_to_stage` and indicator-only `evidence_handles`, which
  means any richer bounded review context would be lost before the automated
  supervisor pass even if the manual resubmission package were corrected.
- Result: the boring-path stop moved from CI registration timing to commit-local
  review-context preservation. The active fix is to keep the Step 14
  registration wait, teach commit handoffs to carry optional supervisor
  `scope_items` and `evidence_handles`, and preserve those fields through
  `commit_executor.py` step 6 so the automated control-surface review sees the
  same direct proof surfaces as the manual resubmission.

## Eighteenth Live Stop (2026-03-27)

- After the supervisor-context package fix landed locally, rerunning
  `python3 mu/tools/executors/executor_dispatch.py pre-commit-supervisor --package .scratch/pipeline_test_run_followup_package.json -v --json`
  first failed closed on package-truth drift in `.scratch/`, then cleared with
  `COMMIT_GO` once the package evidence surface matched the live handoff and
  the exact receipt `.agent_bus/meta/pre_commit_receipts/receipt_2026-03-27T08-37-33p00-00_c8d9f36b.json`
  was written.
- The next command,
  `python3 mu/tools/executors/executor_dispatch.py commit --handoff .agent_bus/executors/phase_b_handoff.json -v --json`,
  advanced through input validation and feature-branch checks but failed closed
  in Step 3 with
  `wave_id 'pipeline-test-run-2026-03-25' appears 2 times in TASKS.md (duplicate)`.
- Direct repo truth showed this was an executor defect, not TASKS drift.
  `TASKS.md` contained one canonical tracker note for the wave and one
  authorized `[PIPELINE-TEST-RUN]` NEXT entry whose current-status prose
  necessarily referenced the same wave-id. The old Step 3 guard counted exact
  whole-file mentions before it checked tracker-note shape, so a legitimate
  NEXT-item reference could collide with the tracker note and stop the pipeline
  before staging or commit.
- Result: the boring-path stop moved again, this time from commit-local review
  context to tracker-note uniqueness semantics. The active fix is to keep the
  Step 14 wait and supervisor-context preservation, but narrow Step 3 duplicate
  detection to actual tracker-note-line collisions so authorized NEXT-item wave
  references no longer fail the mechanical commit path.

## Next Mechanical Questions

1. Can the deliberately trivial control-plane wave now go post-merge -> Phase A
   -> Phase B -> pre-commit -> commit/merge with zero manual takeover?
2. If the run still stops, is the stop caused by real package truth or by
   remaining pipeline mechanics?
3. Only after a clean end-to-end run should latency optimization proceed
   aggressively (validation batching, polling cost reduction, redundant check
   trimming).
