# PR1329 coverage R7: required standing obligations

Date: 2026-10-20
Wave: `workingrcx-fleet-pr-coverage-r7-2026-10-20`
Owners: existing row38 `FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION` for exact
original coverage and existing row40 `FLEET-NATIVE-LIFECYCLE-PREVENTION` for
prevention and prerequisite policy. Existing Mu owners retain runtime work.
Status: Phase B candidate accounting; independent native review pending.

This required tracked report is distinct from the optional executor-owned
`bridge_nonblockers.md`. An empty findings list cannot remove these standing
obligations. Native outer must include this file in its actual indexed handoff
and verify it survives findings cleanup. Admission's disposable cleanup test
is evidence about that test only, not proof of the eventual indexed delivery.

The [coverage manifest](../../control_plane/workingrcx-fleet-pr-coverage-r7-2026-10-20_coverage.json)
accounts for exactly PR1329's 20 paths and 62 hunks. The
[implementation evidence](../../control_plane/workingrcx-fleet-pr-coverage-r7-2026-10-20_implementation_evidence.json)
binds original blobs, merged/current whole files and exact ranges, commands,
timestamps and index observations. Neither hash equality nor a local test pass
is independent semantic approval or public disposition authority.

## Actual lineage and retained source

PR1329 remains OPEN at `537fb0461e7272e063c170e6d7d1cfa4de1b52a2`, based on
`35f7c225a25025aec893230c072754cf7d7c76fc`. Retain branch
`refs/heads/jabramsja/workingrcx-fleet-residual-pr-folders-r2-2026-10-04`.
The admission preserves its raw commit and complete tracked HEAD tree; that
tree closure does not by itself contain all parent history or untracked WIP.
The existing recovery records, source refs, histories and archives remain.

The aggregate replacement anchor is actual PR1339 merge
`ca6c3a93c176fc1da6b6bb6f0169edebf8c1a654`; current comparison is actual PR1340
merge `5921cf352db0f52aa469655371e8977c3f1a0848`.

| Actual merged PR | Contribution and limit |
| --- | --- |
| PR1333, `a9c4e699fd51c13d9501304d5c629d0212e33602` | Folder recovery, coordinated stale-watcher adoption/release with literal process parsing, OS PID absence and exact terminal registration, explicit/default archive protection and adjacent recording-only test repairs. The one-time Mu release exception was not carried. |
| PR1331, `244b09db076754ccb0489aaab30ca03d054f52d6` | Explicit default-bus pin across the detached monitor owner boundary. This is a separate behavior from the original unknown-reader lifetime failure. |
| PR1334, `b75972546901e3a09e08047f1a10c7684bf875bd` | Executor process-release, recovered retry and status-refresh continuation changes. It preserves the PR1333 lifecycle, lifecycle-test and recovery-gate bytes exactly; it did not introduce those strict watcher guards. |
| PR1339, `ca6c3a93c176fc1da6b6bb6f0169edebf8c1a654` | Shared private foreground controller/reaper and bounded observer fixtures. It contains earlier contributions; its merge alone does not prove it implemented them. |
| PR1340, `5921cf352db0f52aa469655371e8977c3f1a0848` | R6 coverage governance. Subsequent public native apply/verify recorded PR1330/PR1338 CLOSED_VERIFIED with local and remote original branches retained. |

The actual merge diff resolves an imprecise attribution in the locked plan:
strict watcher lifecycle checks are already present in PR1333. Direct blob
comparison finds identical `worktree_lifecycle.py`, its lifecycle doc/test,
`test_recovery_gate.py` and `recovery_gate.py` at PR1333 and PR1334. The evidence
records those comparisons and the actual eight executor/test paths changed by
PR1334. The frozen packet is preserved as issued.

## Original P2: tmux availability remains OPEN

All review-thread/comment pages in the fresh captured `pr1329.json` are
complete. Its one unresolved thread, `PRRT_kwDOQvy8bs6owpXc`, contains
[the original P2](https://github.com/jabramsja/rcx-pi-core/pull/1329#discussion_r4176869500).
The reviewer reported five setup failures in a tmux-less environment. That
report is retained as the review observation; this wave does not claim to have
reproduced those five failures.

Current `mu/tests/tools/test_pipeline_monitor_autofollow.py:214-215` still calls
`shutil.which("tmux")` and asserts availability. Current
`.github/workflows/green_gate.yml:50-66` installs ripgrep and can return early
when `rg` exists; the entire committed workflow contains no tmux installation.
The R7 prerequisite observation binds both current source hashes.

**Bounded acceptance:** retain this as an actual OPEN source/prerequisite concern
under existing row40 while this governance-only wave accounts for retained work
and validates on an explicitly observed tmux-provisioned environment. Admission
observed `/opt/homebrew/bin/tmux`, version 3.6a. Any fresh local result is limited
to the environment recorded in its run receipt. Prior hosted green runs prove
those runner instances only. Neither is universal provisioning or supported
tmux-less behavior.

Row40 must separately admit a bounded provisioning or supported-environment
policy change, reproduce the missing-executable case and establish the promised
environment contract. This wave does not choose skip/xfail, weaken assertions,
modify workflows or resolve the review thread. Independent native review may
HOLD this acceptance if the remaining prerequisite gap blocks disposition.
Shared watcher ownership/reaping addresses process lifetime, not availability.

## Removed one-time Mu release: superseded policy, not landed code

Original `OLDEST_MU_RELEASE`, `_reviewed_oldest_mu_release`, its API argument,
policy output and `--reviewed-oldest-mu-release` CLI option are absent from
current source. The exception bound only the October4 R2 wave, original MuR1
head `fa13dada1e0d2d58d4981a279358f63fa6674ab4`, exact path/branch/admin identity,
actual PR1327 replacement merge `146ca4955dca1c56111fc482876290ee1c0b12e2` and
predecessor `35f7c225a25025aec893230c072754cf7d7c76fc`. It permitted
`NEEDS_LANDING` only with independent preservation; it never proved integration.

The exception's positive case and fourteen refusal parameters are removed
together with that capability. They are explicitly superseded, not reported as
passing current tests. Current classifier lines409-420 always protect the
original Mu source in retirement mode. Lines508-523 preserve default owners,
explicit exact/parent protections, active base branches and unfinished journals.
Current classification tests29-81 retain both archived-source parameters and
real completed-archive exact/parent HOLD assertions with unchanged receipts.
Those useful protection changes landed separately from the exception.

R7's locked authority preserves original Mu work and authorizes no retirement.
Reviving a release tied to obsolete census/identity evidence would exceed that
authority. Existing row38 and Mu owners retain original MuR1/R8/R9 useful-work
review, missing hunks, original PR1325 coverage and any later independently
admitted action. A future need for a release requires fresh authority and
preservation; this supersession does not close those owners or delete sources.

## Distinct process histories and current assertions

Keep these as separate events:

- Original PR1329 unknown-reader process-lifetime assertion failure.
- Later R5 Linux unreaped-zombie failures, including both CI attempts.
- Private fixture R2 changing-PID refusal; the unknown process and exact cause
  remain qualified rather than attributed to either earlier event.

The current source does not establish a common cause or a retrospective fix
for all three. The PR1339/R3 implementation report retains the latter failures
and their source-bound records. Original PR1329 source and observations remain
in its retained branch/admission and prior recovery evidence.

Current lifecycle tests441-549 retain `None`, `writer`, `unknown-reader`,
one-claim success, three-claim descriptor HOLD, preserved log bytes, actual
old watcher/tail PID absence, immutable receipts and no replay. Normal/delayed
reaper parameters extend those original controls. Tests626-670 retain
missing-pane/changed-start and extend changed-PPID/command negatives, zero claims
and no release receipt. Tests295-339 keep a genuinely paused parent and
unreaped child as HOLD until actual reaping; a zombie is never absence.

The shared monitor fixture208-404 owns a foreground `tmux -D` controller,
checks parent/child birth identities, notifies its own reaper and verifies
actual process absence during teardown. Monitor health407-444 preserves the
pre-update unhealthy state, replacement identity and real reaping assertions.
The separate PR1339 positive-consumer coherent-observer fixture retains fresh
OS observations only for that unchanged positive consumer and restores the
original observer before adverse injections. None of these boundaries is
weakened or edited by R7.

## Independent standing owners and stage limits

- Main synchronization to PR1340 and prior native lifecycle completion are
  recorded outcomes. Linked dev checkout ownership synchronization remains
  HOLD under row40. Preserve transaction `f82a652ae9ca461aa1b5a069948e73f4` and
  stash `991ef3e02a0f76e967829f29d85ef5a868d92187`, plus all older transactions,
  held WIP, source/index snapshots and native one-shot journals.
- Native runner/R19 remains preserved and unmerged with owed import, scheduler,
  cancellation, timeout and source-bound validation work. R6's distinction
  between landed partial stdout/stderr preservation and unproved suppression
  of an unchanged undersized retry remains open under row40.
- Retention, deduplication, usable capacity, independently verified recovery
  and empty-store restoration require their own admission. Folder/registration
  and physical/useful-work followups do not inherit action rights here.
- Original PR1325's 25-path/40-hunk historical manifest contains 21 missing
  hunks across eight paths. Keep its owner and all original19-source ledgers,
  twelve landing owners, nine recent recovery owners and inherited245/55/122
  owner histories. Preserve absent-checkout unknown intent. Archive recovery
  does not prove semantic integration.
- Mu/Coinduction, paused original PR1325, productivity, bisimulation, scheduler,
  stream-runtime and self-hosting obligations retain their existing owners and
  order. Hemisphere's closed milestone, Phase8c and host debt remain unchanged.
- Row40 retains late-review automation, no-change CI retry prevention, coverage
  admission, xdist/runner enforcement, false-idle attribution and monitor
  verification. PR1333 late monitor topic4257009407 remains separately owned;
  the recorded private macOS/tmux observation did not establish its described
  health2 failure. Dead-pane product repair still requires native reproduction.
- At admission PR1329/1325/1335/1336/1337 remain independently OPEN. PR1330/1338
  are CLOSED_VERIFIED. These are per-owner outcomes, not a barrier requiring
  all unfinished work to finish before exact1329 coverage can proceed.

The startup guard's exit1 with three failing commands and attestation exit0
are retained admission observations; no all-green startup is claimed. Native
outer owns the frozen tracker restoration, generated indicators, growth-cap
transition or exact no-op, indexed L4, independent review, precommit inventory,
full prepush, current-head CI, protected merge, MainSync and lane completion.
Only actual landed R7 authority and fresh readiness can precede a separate
public lifecycle-plan/apply/verify for PR1329. No intent rearm, direct PR close,
branch deletion, stash replay, archive purge or source retirement is authorized.
