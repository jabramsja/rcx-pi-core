# PR1329 / PR1341 coverage R8: required standing obligations

Date: 2026-10-20
Wave: `workingrcx-fleet-pr-coverage-r8-2026-10-20`
Owners: existing row38 `FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION`, existing
row40 `FLEET-NATIVE-LIFECYCLE-PREVENTION`, and the existing Mu production owners.
Status: Phase B implementation; independent native semantic review pending.

This is required tracked delivery, distinct from optional executor-generated
`bridge_nonblockers.md`. Empty native findings must not remove this report.
The outer actor must verify its exact bytes in the actual index after findings
cleanup and before handoff. Its presence in this worktree alone is not that proof.

The [schema2 manifest](../../control_plane/workingrcx-fleet-pr-coverage-r8-2026-10-20_coverage.json)
accounts for exactly PR1329's 20 paths/62 hunks and PR1341's 9 paths/14 hunks.
The [implementation evidence](../../control_plane/workingrcx-fleet-pr-coverage-r8-2026-10-20_implementation_evidence.json)
binds original blobs, contributing merges, exact current ranges, historical
source/index receipts and actual local results. Mechanical completeness and
passing tests do not replace independent semantic review.

## Sources, lineage and limits

Retain both original branches and all separate recovery history:

| Original | Head and source base | Retained branch |
| --- | --- | --- |
| PR1329 | `537fb0461e7272e063c170e6d7d1cfa4de1b52a2`, base `35f7c225a25025aec893230c072754cf7d7c76fc` | `refs/heads/jabramsja/workingrcx-fleet-residual-pr-folders-r2-2026-10-04` |
| PR1341 | `167dd035b0ff56fea92fd3b5f4794ddb69c6420a`, base `5921cf352db0f52aa469655371e8977c3f1a0848` | `refs/heads/jabramsja/workingrcx-fleet-pr-coverage-r7-2026-10-20` |

Both are OPEN at admission. Original raw commits and complete tracked HEAD trees
are preserved by admission. Full parent history, untracked WIP and original
journals use their separate retained sources/snapshots; a tree pack alone does
not prove that broader recovery.

| Actual merged PR | Contribution |
| --- | --- |
| PR1331, `244b09db076754ccb0489aaab30ca03d054f52d6` | Detached monitor default-bus pin, separate from old raw-reader lifetime failures. |
| PR1333, `a9c4e699fd51c13d9501304d5c629d0212e33602` | Watcher protocol/adoption, literal process parsing, exact terminal-record and PID-absence guards, default/explicit archive protection and adjacent fake-tmux repairs. The one-time Mu release was not carried. |
| PR1334, `b75972546901e3a09e08047f1a10c7684bf875bd` | Executor release/status-refresh recovery. The watcher lifecycle/doc/test and recovery-gate files are byte-identical to PR1333; their implementation is not attributed to this later merge. |
| PR1339, `ca6c3a93c176fc1da6b6bb6f0169edebf8c1a654` | Private foreground controller/reaper and bounded observers; positive observation is retained only where required and restored before adverse injections. |
| PR1340, `5921cf352db0f52aa469655371e8977c3f1a0848` | R6 governance coverage. Subsequent native disposition separately established originals PR1330/PR1338 CLOSED_VERIFIED with branches retained. |
| PR1342, `9e3323108d81561e31cb5b83e72cc21b13accca2` | Fresh R4 stable controller birth/server identity, actual parent wait/reaping and exception-safe query-failure cleanup. |

PR1342 is the manifest's merged replacement/comparison anchor, not the alleged
author of every inherited feature. Contributing source/patch hashes are recorded
separately. R4 commit `68c6558502addb867ba78b3544eac427730ccd96`, paired3530/3530
receipts, green hosted attempt1, MainSync/native COMPLETE and snapshot
`3cc9fe25150bbd614ba87436828bab372c887ca7f2675390577e0c4d45625379` are fresh R4
proofs. They transfer no old R7 GO or R8 disposition authority.

## Tmux availability P2 remains OPEN

Complete captured PR1329 threads retain
[the original P2](https://github.com/jabramsja/rcx-pi-core/pull/1329#discussion_r4176869500).
The reviewer reported five setup failures without tmux. That is retained review
evidence; R8 does not claim to have reproduced those five failures.

Current `stale_live_watcher` in `mu/tests/tools/test_pipeline_monitor_autofollow.py`
still uses `shutil.which("tmux")` followed by an assertion. The complete committed
`.github/workflows/green_gate.yml` contains no tmux installation; its system-deps
step installs ripgrep and can return early when ripgrep exists. Exact source
hashes are bound in the implementation evidence.

**Bounded existing-row40 disposition:** keep this prerequisite concern OPEN while
this governance wave validates only on the tmux-equipped environment observed in
its own receipts. Local availability and successful hosted instances do not prove
universal provisioning or supported tmux-less operation. Row40 must separately
admit a provisioning/supported-environment policy change, reproduce the absent
executable case and validate the promised environment contract. Independent
review may HOLD this bounded acceptance if the gap blocks original-PR disposition.
No skips, xfails, weaker assertions, workflow edits or thread resolution are made.

## Removed Mu exception: superseded policy

Original `OLDEST_MU_RELEASE`, `_reviewed_oldest_mu_release`, the API argument,
policy output and `--reviewed-oldest-mu-release` option are absent from current
source. The old opt-in bound the October4 wave, MuR1 head
`fa13dada1e0d2d58d4981a279358f63fa6674ab4`, exact path/branch/admin identity,
PR1327 replacement merge `146ca4955dca1c56111fc482876290ee1c0b12e2` and predecessor
`35f7c225a25025aec893230c072754cf7d7c76fc`. It allowed retained NEEDS_LANDING work
only with independent preservation, never semantic integration.

The exception and its fifteen positive/refusal parameter cases are superseded,
not described as landed code or current passing tests. Current classifier
`classify` unconditionally protects the original Mu source in retirement mode;
its archive branch preserves exact default owners and explicit exact/parent
protections. Current classifier tests retain both archived-source parameters and
real completed-archive exact/parent HOLD assertions with unchanged receipts.
`WorktreeLifecycle.v0.md` retains stopped Mu and requires fresh committed
authority, preservation and synchronized PRIMARY before any future action.

R8 authorizes no retirement and never revives obsolete census/identity permission.
Existing row38/Mu owners retain original MuR1/R8/R9 useful-work review, missing
hunks and original PR1325 coverage. A future need for release requires separate
fresh authority; these owners and sources are not closed by supersession.

## R7 contributions and failed histories remain distinct

PR1341's nine files were evaluated independently. Useful tracker and chronology
corrections are reconciled with captured PRIMARY and actual R6/R4 outcomes;
single-target R7 approval/intent is not imported. Its original coverage ledger,
packet, indicators and source-bound validations remain immutable historical
evidence. Its standing owner obligations are carried here, not dismissed merely
because a later fixture wave passed.

The [PR1341 inventory finding](https://github.com/jabramsja/rcx-pi-core/pull/1341#discussion_r4321554073)
concerns post-generation packet/indicator bytes at `19f499d6`. The corrected
`167dd035` artifact matches its final inventory, with original run maps unchanged.
That correction is neither retrospective approval nor a replacement for failed CI.
R8 likewise keeps immutable per-run maps and timestamps separate from an artifact
inventory. Native packet/indicator changes require a new final inventory after
generation; original receipt hashes must never be overwritten.

Keep these observations separate:

- Original PR1329 unknown-reader/lifetime failure.
- Later R5 Linux zombie failures and R2 changing-PID refusal.
- R7 repaired-head attempt1 release-positive child-presence assertion: exact
  cause remains unproved.
- R7 attempt2 mutable command identity failure: directly evidenced and addressed
  by PR1342 stable PID/PPID/birth plus independent private-server identity.
- R7 out-of-scope fixture repair: retained terminal snapshot `af8ba281` and patch
  `e06255aa`; preserved work was not imported or approved wholesale.
- R4 re-entry query-failure cleanup: repaired and tested through fresh native
  review; it is distinct from tmux availability and the unproved attempt1 cause.

Current tests retain real old watcher/tail absence, one-claim success, writer and
unknown-reader holds, immutable spent receipts, no replay, missing-pane and
changed-birth/PPID/command refusal, and unreaped-process HOLD. R8 edits none of
those fixture or production bytes.

## Standing owners and delivery boundary

- Retain both complete original19-source useful-work ledgers, twelve landing
  owners, nine recent recovery owners and inherited245/55/122 owner histories.
  R8 evidence records every ledger entry digest and exact owner scope. Original
  PR1325's separate25-path40-hunk ledger retains21 missing hunks across eight
  paths. Reverse-patch mismatch is not missing-code proof; absent-checkout
  unstaged/untracked intent remains UNKNOWN. No generic evidence-only label
  closes a useful-work owner.
- Runner/R19 remains preserved and unmerged. Import/scheduler/cancellation/
  timeout obligations remain. Landed partial stdout/stderr preservation is
  distinct from unproved suppression of unchanged undersized retries.
- Native T2's 3600-to-5400 execution-envelope recovery is temporary. Existing
  `native-stage-aware-executor-envelope-followup-20261020.json` and
  `native-post-remediation-ci-envelope-followup-20261020.json` retain durable
  stage-aware work under row40. No local timeout inflation is introduced.
- Main synchronization and R4 lane COMPLETE do not resolve linked-dev ownership.
  Preserve transactions `39a5bf00192d4bdd86e0b0f39390f35c` and
  `f82a652ae9ca461aa1b5a069948e73f4`, and stashes
  `8123d4dc54d1c9244b06a95fa7f03bb1247ebc64` and
  `991ef3e02a0f76e967829f29d85ef5a868d92187`, plus older held sources/journals.
- Retention/deduplication, capacity and independently verified empty-store
  recovery need their own admission. The native producer still creates internal
  archives. No live archive purge, source retirement or branch deletion occurs.
- Mu/Coinduction, productivity, bisimulation, scheduler, stream-runtime and
  self-hosting work remain with existing owners. Hemisphere, Phase8c and host
  debt are unchanged. PR1325/1335/1336/1337 stay independently OPEN; their
  unfinished work is not a new blanket prerequisite for exact1329/1341 coverage.
- Row40 retains monitor verification, late-review automation, no-change CI retry
  prevention, xdist/runner enforcement and false-idle attribution. PR1333 late
  monitor topic4257009407 still needs its own native reproduction/disposition;
  a private macOS/tmux observation did not establish the described health2 failure.
- Main startup has four core exits0 and docs consistency exit1; docs subchecks
  42/50/8 pass while inventory reports3395 unclassified/four placement failures
  involving preserved Git metadata and Claude learning archives. Separate clean
  worktree admission measured a clean status and passing docs/core checks.
  `native-doc-inventory-recovery-boundary-followup-20261020.json` remains row40
  work. No global-green claim, archive deletion, Claude edit or inventory-tool
  change is made in R8.

Native outer owns Ra restoration, measured indicators, generated growth-cap
transition or exact no-op, indexed L4, independent review, precommit_inventory,
full prepush, exact-head CI, protected merge/MainSync and lane COMPLETE. Only
landed fresh coverage plus exact-head/UUID/quota/readiness/unspent-intent checks
can enable later separate public lifecycle-plan/apply/verify for1329/1341.
No direct close, consumed intent rearm, stash replay or old authority reuse.
