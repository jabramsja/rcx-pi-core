<!-- DOC_STATUS: REFERENCE -->
# Exact P0IBRRCP closure evidence

Evidence date: 2026-09-12. Task: `[PR1219-P0IBRRCP-EXACT-CLOSURE]`.
Wave: `pr1219-p0ibrrcp-exact-closure-r1-2026-09-12`, class `MAINTENANCE`.
This report supports the [locked native packet](pr1219-p0ibrrcp-exact-closure-r1-2026-09-12_2026-09-12.md).
The exact obligation has passing local evidence; this queue slot remains
**CURRENT until native landing**.

Implementation credit belongs to PR #1256, merge
`0a4c24120141723d70e6dd1c476ffaa70b1ff9ca`, from parent PR #1255 merge
`922081269684f74404ba2c405ddab57c5af4f4eb`. The retained requirement is in
`reports/control_plane/pr1219-p0ibrrcp-normal-root-recorded-child-cleanup-r4-2026-09-01_2026-09-01.md`
and work items at lines 32–35. Its original narrow task is numbered row 23 in
`git show 0a4c24120141723d70e6dd1c476ffaa70b1ff9ca:TASKS.md`: the later exact
closure is already present in that successor sequence, and R3C5/R3C6 explicitly
do not satisfy P0IBRRCO. This wave adds no production or test behavior.

All current source lines below refer to comparison commit
`f7e27eadabd7d599ae2fd550aef23b21349b9b96`. Comparing the landed PR #1256
diff and current source confirms identical snapshot/poll and normal-return
blocks; the entire synchronized regression is also source-identical.

| Exact retained requirement | Current code and test evidence |
| --- | --- |
| Retain prior/current recorded children until root status is known. | `mu/tools/executors/phase_b_executor.py` captures initial child authority; `:4488` captures the current snapshot before polling at `:4493`; `:4495` advances `last_child_pids` only after a nonterminal poll. The synchronized test at `mu/tests/tools/test_phase_b_executor.py` releases the real parent after a live poll, then proves the detached child was present in the first snapshot and absent but still live in the next (`:7259`). |
| Complete existing bounded cleanup of their sorted union before normal return. | `mu/tools/executors/phase_b_executor.py` passes the sorted union to `_terminate_bridge_subprocess` before return at `:4524`. The existing helper at `:4382` sends TERM, waits up to two seconds, then escalates to KILL with bounded waits (`:4414`); `:4342` attempts `waitpid` when the PID is a child of this process. The test verifies TERM handling at `mu/tests/tools/test_phase_b_executor.py` and child non-liveness at `:7306` before its safety cleanup. |
| Preserve root exit code and output. | `mu/tools/executors/phase_b_executor.py` saves log sizes before cleanup; `:4521` truncates cleanup-generated output before reading logs and returning the previously polled exit code. The test's child deliberately writes both streams during TERM (`mu/tests/tools/test_phase_b_executor.py`); assertions at `:7303` require exit 0 and exactly the root's stdout/stderr. |
| Use a synchronized real-process regression with a final safety net. | `mu/tests/tools/test_phase_b_executor.py` launches a detached real child and holds the parent on a release file; `:7230` waits for child readiness. The snapshot wrapper calls real discovery, and the poll wrapper calls real polling. Assertions precede the test-only `finally` cleanup at `:7307`. |

Fresh Phase B-local validation at the comparison commit above:

```bash
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py::TestBridgeReviewMonitoring::test_bridge_normal_exit_preserves_recorded_child_across_poll_snapshot_race --tb=short
```

Initial result: **exit 0; 1 passed in 1.04s**. The identical declared command
passed again during classification re-entry: **exit 0; 1 passed in 0.93s**.
This directly proves the recorded-child
snapshot race with successful root exit, exact stdout/stderr and observed child
non-liveness. Reaping remains the existing bounded helper's behavior, including
`waitpid` only where the monitor is the parent; this is not a new universal
reaping guarantee. Nonzero-root behavior is supported by the unchanged return
code path, not a second fresh real-process test.

Fresh carrier HEAD, primary worktree HEAD, `origin/dev`, `git ls-remote origin
refs/heads/dev`, and the new candidate spec's `comparison_commit` all equal
`f7e27eadabd7d599ae2fd550aef23b21349b9b96`. `git merge-base --is-ancestor`
for PR #1256's merge against HEAD returned 0. The single registered fresh carrier
is `WorkingRCX-pr1219-p0ibrrcp-closure-r1-20260912`, branch
`jabramsja/pr1219-p0ibrrcp-exact-closure-r1-2026-09-12`, bus
`.agent_bus-pr1219-p0ibrrcp-closure-r1-20260912`. Its launcher routing record
was created at `2026-09-12T13:25:04+00:00` and binds this wave, packet, comparison
commit and allowlist. Independent Phase A reviewer job
`phase-a-r1-c2a688ba--r1-reviewer-3b5a9bc6` returned GO; the reader was synthetic,
not a second independent review. Selected implementer/reviewer/pager are Codex
with the bus's `gpt-6-astra`/`max` configuration; commit remains providerless.
No predecessor authority was imported.

PR #1292 / R3C6-R4 separately **LANDED** at the comparison merge above on
`2026-09-12T13:11:06Z`, from head
`9674ec343f0455efdfaca03109692477db3d308e` and parent
`fdfc58d52c717785a5696a8c3d36f9c934ee0030`. The primary-only archive
`reports/archive/control_plane/r3c6-r4-evidence-2026-09-12/README.md` retains
1510 passing module tests and 61 passing independent Phase B tests. Its
`terminal_closeout_observation.json` records seven completed SUCCESS checks;
the README binds green-gate run `34695050659`, attempt 1, to that exact head,
with 11107 main-suite passes and 22 skips. These predecessor results are reused
as historical evidence, not rerun, summed, or represented as this wave's CI.

The same read-only terminal observation records a separate native **exit 1**
at `2026-09-12T13:12:50Z` after retirement: recovery could not import the deleted
pager, then terminal-receipt persistence lacked routing authority. The prior
failed/timeout payload was not retained; its cause and successful old successor
publication are **NOT_ESTABLISHED**. Fresh process inspection found no owner
command matching the retired carrier/wave; worktree inspection found it
deregistered with `.git` absent. This known bookkeeping issue is nonblocking
for this independently launched documentation closure. The archive was only
read in the primary worktree, never copied into this candidate or used as
execution authority; no exit 0, restoration or replay is claimed.

The existing closure baton is rich numbered entry 28, with inline
`Task: [NEXT-CODEX-POST-REDTEAM]`, exact Wave ID, class `MAINTENANCE`, category
`PROGRAM QUEUE` and canonical packet. Read-only invocation of the actual native
`commit_executor._next_open_founder_ordered_queue_entry(Path.cwd())` returned:

```json
{
  "wave_id": "pr1219-p0ibrrcp-exact-closure-r1-2026-09-12",
  "packet": "reports/control_plane/pr1219-p0ibrrcp-exact-closure-r1-2026-09-12_2026-09-12.md",
  "state": "CURRENT",
  "category": "PROGRAM QUEUE"
}
```

All 152 queue heading identities retain their original semantic order; only
later display ordinals shift. The header, Binding order, Parallelism rule,
R3C6-R4 and closure owners agree, and the two specified inherited successor
paragraphs preserve historical merges while naming the actual live order:
P0IBRRCP CURRENT -> P0IBRRCO NEXT -> P0IBRRC -> P0IBRRT -> P0IBRR -> P0IB1 ->
P0IB2 -> every later recorded item, with Mu optimization last. Private-review
R2, all aliases/stopped evidence, immutable operation claims/backups and consumed
cleanup outcomes **1 MOVED / 3 INCOMPLETE / 407 prior HOLD** remain preserved.

Supervisor re-entry reconciles the generated `L4_ENABLER` tracker classification
with the locked `MAINTENANCE` scope. The native tracker writer records the
maintenance no-op proof and defer reason; the packet's authoritative `Class`
header and native L4-field block derive from that same-wave note. The existing
indicator measurements and comparison commit remain unchanged. The native
Phase B owner must regenerate and stage the supervisor package from these
corrected inputs and refresh its governance validations before resubmission.

Proof limits: no pre-first-snapshot, PID-reuse, exceptional cleanup,
`on_started` failure, in-flight implementer ownership, broader P0T3, provider,
dispatcher/recovery, runtime, substrate or Mu completion follows from this
normal-return proof. No later obligation is closed or combined. Debt and host
semantics are unchanged by this documentation-only diff; runtime/substrate
delta is zero. The same-wave TASKS tracker note owns L4 fields; packet/indicator
refresh, independent Phase B review, staged MAINTENANCE gates, supervisors,
providerless commit, pre-push, CI, merge and postmerge remain with native owners.
This report claims local functional evidence, not this wave's landing.
