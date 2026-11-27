# Throughput R7 Phase B blocking validation result

Wave: `workingrcx-pipeline-throughput-r7-2026-10-29`
Task: `[FLEET-NATIVE-LIFECYCLE-PREVENTION]` (existing owner40)
Disposition: **BLOCKING / HOLD**
Classification: **POLICY_BOUND**; no new lifetime or ownership defect is inferred.

## Bridge round 3: unresolved catalog boundary, no new acceptance attempt

The round 3 finding remains **BLOCKING**. This implementer did not admit a
new gate, sweep, recovery or reviewer after inspecting the retained HOLD.
The locked plan still requires unchanged raw catalog bindings and prohibits
model/access changes. It provides no exception for `fetched_at`. There is no
in-scope source correction that can turn the interrupted round 2 gate and
unlaunched sweep into the required passing pair. Replacing that failed binding
with the latest cache hash would not resolve the underlying condition.

Read-only verification on the UUID-bound WD store established:

- All 20 restored donor hashes and modes still match snapshot `2eeba4a1`.
- The 25 bound source/test/Runbook/checker files match the round 2 entry bytes
  and modes. No new code defect is inferred from the missing acceptance proof.
- All 19 retained command receipts and their stdout/stderr hashes verify.
  Their prior successes, failures and interruptions remain historical.
- At `2026-10-29T03:19:48.330284Z`, the raw catalog SHA-256 was
  `0d4deb08ae6d32d7a59b9de2c888479d4cb2b53130a3010015ccad3f1a9c3163`,
  with `fetched_at=2026-10-29T03:19:15.407198Z`. Full bytes retained in
  `bridge-round3-entry.catalog.json` differ from the round 2 post-stop capture
  only in `fetched_at`; every other decoded field is identical. The writer is
  still unestablished. This observation does not establish a new validation
  interval or modify any earlier result.

Only the four declared reporting files are updated for this correction.
Original report bytes, the catalog copy, donor verification, receipt verification
and candidate/index/ref bindings are retained under the existing evidence root
with the `bridge-round3-` prefix. No pipeline, checkpoint, clock, catalog or
approval authority is reset. The outer owner must resolve the catalog boundary
under the locked contract before a new acceptance pair can establish compliance;
this report grants no retry or exemption. All native review and delivery gates,
owner38 retention, exact folder retirements and original PR obligations remain.

## Bridge round 2 correction: catalog refresh stops the new gate

The source/test/Runbook repair is unchanged. Fresh focused controls passed
**173 tests in 46.01s**; private-attribute integrity, all six control-surface
invariants and native packet validation passed. Before each admission, the
implementer checked the same candidate, index, HEAD, frozen configuration,
refs/stashes and raw catalog bindings. The complete declared ten-module gate
started at `2026-10-29T03:08:04.671313Z` with the exact selectors, four workers,
`ci_fast` Hypothesis setting and unchanged 7200-second ceiling.

The raw catalog changed during this gate. Full before/after bytes were captured
on the UUID-verified WD volume. Unlike round 1, this interval has exact evidence
that **only the `fetched_at` value changed**:

- Before: `2026-10-29T03:04:09.015047Z`, SHA-256
  `d82cde09e77f7507b14fbf1f4c10d6548d42c21980ad6d90239a5cf88d28cd94`.
- After: `2026-10-29T03:09:11.118881Z`, SHA-256
  `6c802a84335805a882bc99b434a2f7c7d9de87fe4f365804d7119486c8a68d71`.
- Model entries and every other decoded field are identical; canonical model
  entries SHA-256 is
  `5e61ea9dd12ae10f7640def620a92b50a25f797a3aec405e822e0e7458544db4`.

This proves metadata-only change for this new interval, not round 1. It does
not satisfy the locked unchanged raw-binding requirement or authorize a
semantic-only exemption. The refresh's writer is not established by these
snapshots. No model/access/cache edit, catalog baseline replacement, retry or
guard change followed the drift.

The binding comparison returned 125. After rechecking the launched pytest PID,
its parent runner, birth and exact command, SIGINT was sent only to that pytest
root at `2026-10-29T03:10:20.940293Z`. Its parent reaped **exit 2; 1170 passed in
142.56s** (142.984s enclosing elapsed). This is interrupted partial evidence,
not an assertion failure, passing gate or whole-tree release proof. **The
dependent sweep was never launched.** Candidate/source/index/config/refs/stashes
remained unchanged through the stop. Only the four authorized reporting files
were subsequently amended to record this result.

The round 2 finding remains **BLOCKING**: no complete passing gate/sweep pair
exists on continuous raw catalog bindings. The Phase B implementer cannot
repair an external catalog refresh by changing models/access or weakening the
locked binding requirement. No further validation or actor admission follows
this HOLD. Fresh outer authority is required to resolve that boundary before
another acceptance attempt; no checkpoint, clock or exhausted authority was
reset here.

The evidence directory retains `bridge-round2-before.json` and its full catalog
copy, the before-gate snapshot, catalog-drift snapshot and catalog copy,
`bridge-round2-catalog-diff.json`, exact interruption identity/request records,
`bridge-round2-full-gate.json`, complete stdout/stderr and child receipts, plus
the post-stop bindings. The implementation evidence lists their hashes and
preserves every earlier failed run and HOLD. Its original round 2 entry bytes
are retained as `bridge-round2-original-implementation-evidence.json`.

## Bridge round 1 correction: incomplete validation pair

The complete declared ten-module gate now ran: **5279 passed in 491.37s,
exit 0** (491.903s enclosing elapsed). The exact command, all ten selectors,
four workers, `ci_fast` Hypothesis setting and 7200-second ceiling were retained.
Candidate bytes/modes, raw index, index entries, HEAD, frozen configuration,
refs and stashes were unchanged. Fresh focused controls passed 173 tests;
the unchanged private-attribute checker, all six control-surface invariants
and native packet validator also passed before the complete gate.

A separate comparison after the gate detected a different SHA-256 for
`/Users/jeffabrams/.codex/models_cache.json`:

- Before: `1881fd736118b8c60bff0e4686c08eb97e1dc1e96e2d13a37214e369dde47165`
- After: `b77e287aa45ed0fbf69a93d9e8346f20aea99fc54b8d36cd2e65675cb47f7e88`

The current cache has `fetched_at=2026-10-29T02:56:25.797569Z`. Only its
pre-run hash was retained, not the original bytes; whether this changed only
refresh metadata or model entries is **unestablished**. The implementer did not
edit the cache or infer an effective model change. The candidate-only runner's
`bindings_unchanged=true` does not cover this separate catalog observation.

The implementer incorrectly launched the dependent sweep after the binding
comparison exited 1. On identifying the changed path, the implementer sent
SIGINT only to the exact newly launched pytest root, verifying its PID, parent,
birth/command identity and the parent's matching evidence-runner invocation.
The parent reaped pytest with **exit 2; 698 passed in 55.00s** (55.418s enclosing
elapsed). This is interrupted partial evidence, not a passing sweep, assertion
failure or whole-tree release proof. No subsequent validation was admitted,
and no guard, budget, source, checkpoint or catalog was changed to bypass HOLD.

The round 1 finding remains **BLOCKING**: the required complete passing gate
and identical sweep on continuous bindings are still unsatisfied. All earlier
failures and the original observer HOLD below remain preserved. No new runtime
defect is inferred from either observation, and no delivery authority is claimed.

New durable records in the existing UUID-verified WD evidence directory are
`bridge-round1-before.json`, `bridge-round1-between-gate-sweep.json`,
`bridge-round1-full-gate.json`, `bridge-round1-independent-sweep.json` and
`bridge-round1-sweep-interruption.json`, plus their complete stdout/stderr and
child receipts. The candidate implementation evidence records their hashes.

## Preserved initial implementation HOLD

The source-bound common/validation handoff repair is implemented. The actual
comparison-commit client and common callables retained their original module
ownership while the current supervisor executed the new dependencies. The first
real validation child exited 0. Before the next requested exit-7 child, the native
process observer returned `process observation gap absence is uncertain`.
`run_validation` refused before `subprocess.Popen`; the supervisor propagated
`ValidationExecutionHold`. The second child was not admitted. The diagnostic
stopped before its remaining `-B` cases.

The locked plan requires a HOLD on uncertain ownership. No retry, fabricated
absence, owner stripping, clock reset, guard change or broader lifetime repair was
performed. At that initial checkpoint, the complete declared ten-module gate
and identical sweep were **NOT RUN**. This report must retain its blocking disposition until current native
validation establishes the required acceptance without weakening the observer.
No independent review, commit, push, hosted CI, merge or PRIMARY synchronization
is claimed.

Prior local results remain limited evidence: 173 focused tests passed; the actual
four-module hybrid caller passed 1970 tests in 279.97s within its unchanged
300-second leaf and completed the native scope audit with no drift. Its selector
was full and Hypothesis was `ci_fast`. The unchanged private-attribute checker,
all six control-surface invariants and native packet validator passed. R6 proof
remains historical and unapproved. The earlier fixture-order import failure and
the initial stale-bytecode reproduction are retained with all logs.

Exact commands, binding hashes, failed outputs and receipts are recorded in
`reports/control_plane/workingrcx-pipeline-throughput-r7-2026-10-29_implementation_evidence.json` and the UUID-verified WD directory
`/Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/workingrcx-pipeline-throughput-r7-2026-10-29-phase-b`. The decisive artifacts are `actual-baseline-handoff.json`,
`actual-baseline-handoff.stderr` and `baseline-cached-handoff-results.json`.

The outer executor still owns tracker-note restoration, generated indicators and
caps, final native checks, independent review and all delivery stages. Owner38
retention, the six later exact folder retirements and original PRs1337/1336/1335/1325
remain unresolved; this implementation retires no source and disposes no PR.

Read-only causal trace after the initial HOLD: the exact refusal originates at
`executor_common.py:2177-2183`. A PID retained from either process census was not
in the intersection of the current graph and identity censuses. Its
`os.kill(pid, 0)` probe raised `OSError` or `OverflowError`, other than
`ProcessLookupError`. That branch returns the precise recorded diagnostic.
The observer function is byte-for-byte identical to comparison `fbe43a5e`.
`validation_execution.py:159-161` rejects the incomplete observation before its
child launch at line210; `meta_bridge_supervisor.py:1378-1379` propagates HOLD.

The historical PID and exception/errno were discarded by the observer. The
preserved output therefore does not establish permission denial, process churn,
or another specific OS-level cause. Those remain unresolved; no live snapshot
can reconstruct this historical event. This pass performed no new validation
admission or retry and preserves the blocking disposition.
