<!-- DOC_STATUS: REFERENCE -->
# PR1330 deferred-topic accounting

Date: 2026-10-19. Wave: `workingrcx-fleet-pr-coverage-r5-2026-10-19`.
Owner: existing TASKS row40 `[FLEET-NATIVE-LIFECYCLE-PREVENTION]`.
Disposition owner: existing row38 `[FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]`.
Status: Phase B implementation; independent native review and landing pending.

This standing report supplies the two bounded follow-ups absent from original
PR1330's referenced report. The original head
`817e470362ef632b60ab13bb4321571676f564ee` remains on retained branch
`refs/heads/jabramsja/workingrcx-lifecycle-gate-budget-r1-2026-10-04`.
PR1330 is OPEN in the admission snapshot, including the unresolved missing-report
thread. This report does not resolve that public thread or authorize closure.

The inspected landed lineage is PR1334, head
`51f575945e2bd3563cc8d0a77506c5ae0f78c432`, merge/current-dev comparison
`b75972546901e3a09e08047f1a10c7684bf875bd`, merged 2026-10-14T05:02:20Z.
The referenced behavior is present in its ancestry; PR1334 did not necessarily
introduce each line. Exact ranges and hashes are recorded in this wave's
`reports/control_plane/workingrcx-fleet-pr-coverage-r5-2026-10-19_implementation_evidence.json`.
Source inspection below is distinct from fresh execution of those assertion
bodies: this wave's declared gate selects docs, disposition and Phase B tests.

## Partial stdout/stderr on pytest timeout

Actual behavior: `commit_executor._run_pytest_on_files` retains both available
TimeoutExpired streams, decodes bytes using UTF-8/backslashreplace, reports the
selected finite deadline, and returns exit -1 with `passed=False`. Step8b
returns the raw streams separately from its bounded recovery summary, with
command identity, timeout and failure metadata, before any commit.

The landed `test_targeted_pytest_timeout_reports_selected_budget` assertions
cover None/None, long bytes/text, invalid UTF-8 and one-sided streams. The real
public-pipeline test `test_step8b_public_pipeline_retains_complete_pytest_failure`
checks exact streams after JSON transport, timeout/nonzero/empty failures,
retained command metadata, unchanged HEAD and no commit/push/merge.

Remaining limit: only output supplied by the timed-out subprocess can be
retained. Neither a helper pass nor a bounded recovery prompt establishes pipe
flushing, complete durable outer-wrapper logs or repair of a historical job.
Row40 acceptance is independent confirmation of the landed helper AND Step8b
assertions for empty and long mixed streams, the finite deadline and failure
before commit. Keep any missing outer-boundary guarantee explicitly open.
No additional production edit is authorized by this coverage wave.

## Unchanged undersized-gate recovery reinspection

Actual commit-helper budgets are exact full lifecycle600, fleet900 and PhaseB600,
ordinary240, summed per selector with the caller floor. These landed values
satisfy the original budget obligation. Recovery has a separate policy:
`_run_pytest_targeted_validator` retains the caller deadline for a non-fleet
module, while the delegate caller bounds that deadline at 300 seconds. Full
fleet has its separate 900-plus-240 policy.

The generic `run_recovery_loop` may verify a command and feed failure into another
bounded iteration. Applied shell/edit work without a verification command can
return `retry_requested`; that is not proof the original gate passed. Command
diagnostic hashes retain evidence but grant no retry authority. Inspection of
these branches does not establish general suppression based on an unchanged
source/selector/budget identity. The existing
`test_validation_failure_is_fed_into_next_iteration` asserts failure after two
iterations and forwards the error/timeout diagnostics.

This suppression obligation remains OPEN/advisory under the same row40 owner,
independent of PR1330 disposition. Bounded acceptance for a later authorized
repair: bind the actual source/index identity, exact selectors, effective finite
deadline and retained failure diagnostic. An unchanged failed or undersized
combination must HOLD without another identical invocation. Changed inputs may
enter only the existing bounded retry path with a newly recorded actual result.
Disposable public-boundary regressions must distinguish unchanged suppression
from changed-input admission while retaining genuine failures, empty collection,
timeouts, prior receipts, consumed claims and existing budgets. No timeout
inflation, retry-counter reset, exhausted replay or assertion weakening is
authorized here. These source observations do not explain an R19 timeout or the
historical R4 foreign-proof producer refusal.

## Source bindings and delivery limits

All source ranges below refer to the exact comparison commit above.

| Topic | Implementation and assertion ranges |
|---|---|
| Timeout streams | `mu/tools/executors/commit_executor.py:4915-4932`, `:22549-22583`; `mu/tests/tools/test_commit_executor_post_merge_cleanup.py:270-320`, `:342-423` |
| Exact budgets and original assertions | `mu/tools/executors/commit_executor.py:4833-4897`; `mu/tests/tools/test_commit_executor_post_merge_cleanup.py:112-267` |
| Recovery limit | `mu/tools/executors/recovery_gate.py:8895-8951`, `:9145-9185`, `:9940-10055`; `mu/tests/tools/test_recovery_gate.py:9124-9185` |
| Native empty-findings cleanup | `mu/tools/executors/phase_b_executor.py:763-775`, `:798-873` |

The required `_row40_advisories.md` file is separate from optional native
`_bridge_nonblockers.md`, which empty findings can clear. No P2 findings are
fabricated to keep a generated report alive. Native cleanup survival is checked
in the implementation evidence; actual indexed handoff remains outer-owned and
must include these exact standing bytes before approval.

Schema-2 coverage accounts for all seven original paths/fourteen hunks. Mechanical
validation is not independent semantic approval. Fresh native review, packet and
index authority, indicator/Step5e, complete prepush/CI, protected merge, separate
PRIMARY synchronization and released lane remain required. Only then may later
public lifecycle plan/apply/verify consume committed authority. The other five
original PRs remain independently OPEN/owned at admission. Original source
branches, held transactions/stashes and recovery history remain preserved.
