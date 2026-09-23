# Changelog

This file is a selected historical changelog, not the complete current
merge ledger. For live recent wave chronology, use `TASKS.md` plus
`git log --oneline`.

## 2026-09-23

### PR1312 R2 lifecycle fixture isolation (Phase B; native landing pending)

- Reproduced the exact four-worker gate at **8 failed, 1,716 passed in 119.80s**.
  Retained process snapshots identify live dispatcher fixture PIDs 46727, 58730
  and 68578 matching other repositories solely through the shared `native-wave`
  branch literal in their child-program arguments. Failed completion receipts
  preserve all three process-identity holds; the R2 packet references raw evidence.
- Lifecycle tests now derive deterministic branch and wave identities from each
  disposable repository path and pass them through the real child processes,
  handoffs and owner assertions. Paired real-process controls prove that a shared
  branch exhausts three holds, an isolated lane completes while its peer lives,
  and each peer's own registered owner still prevents retirement. Releasing the
  collision leaves the sealed hold and consumed budget intact.
- Supervisor re-entry found the same interference in the cleanup fixture:
  **1 failed, 3 passed in 7.58s**, with three process-identity holds. Fresh
  process captures identify cleanup child PID 52701 matching independent
  repositories solely through `fixture-feature`. Keeping real cleanup peers
  alive made all four ambient-filter cases fail before correction. The cleanup
  fixture now derives branch and wave identities from each repository and passes
  its branch as a child argument. All four cases complete on their first attempt
  beside live peers; each peer's own lane, tree and index remain held. Exact
  branch/history and PR-owner assertions remain, with durable PID diagnostics.
- The exact declared chain passed: packet authorization; anti-theater with zero
  findings/exceptions; **1,726 tools/growth tests in 124.88s**; **351 docs tests in
  9.82s**, with two existing freshness warnings. The focused four-worker cleanup
  command passed **4 tests in 8.04s**. Production lifecycle/fleet guards, the R1
  ambient-Git boundary and classifier repair, and the original R1 packet/indicator
  are preserved. All 268 IDs and 39 parked obligations remain. The R2 packet
  references the retained failure, process captures and corrected validation.
- Native indexed handoff, review, commit, pre-push, CI, PR1312 merge, PRIMARY
  synchronization and carrier closeout remain outer-executor work. Eligible
  physical cleanup/useful-work landing stays directly next, then Mu.

### PR1312 R1 bounded CI continuation (preserved failed attempt)

- Reproduced the remaining cleanup fixture escalation with ambient runner Git
  filters. The fixture now isolates system/global configuration at Git exec,
  including the lifecycle child and census, while retaining actual retirement,
  closeout and PR-owner assertions. System/global clean/process cases also
  verify that exposed filters still trigger production retention without execution.
- Reproduced the historical successful TASKS read misclassification from the
  preserved 1,580,135-byte commit stdout and its exact CI terminal JSON. Recovery
  now recognizes the coherent native `wait_ci` test-failure envelope. Current
  outer/terminal diagnostics, CI excerpts and bootstrap faults retain authority;
  malformed or mismatched envelopes retain the full-stdout fallback.
- Adds a bounded self-contained capture regression and current-diagnostic
  negative controls. Scope/Git-control audits and finite attempt budgets remain
  intact. All 268 task IDs and 39 parked obligations stay with row40; eligible
  physical cleanup/useful-work landing remains directly next, then Mu.
- Packet authorization and anti-theater passed with zero findings/exceptions.
  The required tools/growth gate stopped at **7 failed, 1,717 passed in 119.51s**;
  all seven failures are in unchanged `test_worktree_lifecycle.py`. The repaired
  cleanup and recovery cases passed. The docs command short-circuited; the
  locked-plan stop condition remains in force. Exact selectors are in the packet.
  The governed footprint remains 361 test files,
  131 tool scripts and 67 core docs, so caps 171/63/19 need no adjustment.
  Native indicator collection, indexed handoff, review, commit, CI, PR1312 merge,
  PRIMARY synchronization and carrier closeout remain with the outer pipeline.
- Bridge-round-1 revalidation again passed packet authorization and anti-theater,
  then stopped at **8 failed, 1,716 passed in 122.96s** in the unchanged lifecycle
  tests. Six failing fixture receipts recorded three holds each with
  `Active process references target identity`. Shared fixture branch names and
  machine-wide process matching suggest worker interference; exact process
  attribution and candidate causation remain unresolved. The cleanup/recovery
  cases passed; docs again short-circuited. The blocking finding remains open
  under the locked scope, with lifecycle source/tests preserved.

## 2026-09-22

### Fleet native lifecycle R8 (Phase B implementation; native review and landing pending)

- Verified preserved R7 manifest SHA256
  `391c47f4c04f4524e411f8a8fb3ed15d0dd30740e8628dd15baac7a7c64af65a`
  and all 64 file lengths/hashes before carrying its 17 source/test/lifecycle-doc
  files onto the unchanged PR1311 merge `3fe05fdf8a61ec7d40398175e161a73e0006b20a`.
  R7 stopped at 2026-09-22T19:52:56Z on the live-dispatcher retry dependency.
  Its full evidence, original index and terminal authority remain preserved.
- A real dispatcher owner process and sequential commit children reproduced
  both missing pre-mutation completion evidence and reuse of a failed post-merge
  closeout at unchanged HEAD. Successor admission now accepts a verified failed
  closeout before completion only when no attempt has started. Fresh successful
  closeout remains mandatory; original failure bytes, consumed attempts and
  interrupted-mutation protections remain. The real worker completes retirement
  only after its dispatcher exits, using the original three-attempt budget.
- Retains the R7/R6 implementation and PR1311 receipt/fixture behavior described
  below. Canonical current-wave cap generation uses projected counts 361/131/67
  and exact caps 171/63/19; no new exception or optional report is introduced.
  All 268 task IDs and 39 parked obligations remain with existing row40.
- The actual native dispatcher/commit-boundary regression failed all three
  cases against the preserved R7 helper and passed with the correction,
  including an already-consumed completion attempt. Collection passed for
  4,546 tools/growth cases and 351 docs cases. The exact anti-theater-first
  chain exited 0: zero findings/exceptions, **4,546 tests passed in 677.85
  seconds**, then **351 docs tests passed in 1.79 seconds** with two existing
  freshness warnings. All fixtures used default system temporary storage;
  native stdout retains the results. Review, final gates, commit, CI, merge,
  PRIMARY synchronization and durable operational closeout remain outer-owned.
  Eligible physical cleanup/useful-work landing remains directly next, then Mu;
  all 37 consumed fleet operations and held source196 evidence remain unchanged.

The R7/R6 entries below retain their authoring-time validation evidence, not
current approval. Both attempts stopped without landing. PR1311
landed at 2026-09-22T16:25:05Z; its older pending-status entries are historical.

### Fleet native lifecycle R7 (stopped; preserved authoring-time evidence)

- Carries the preserved R6 lifecycle implementation onto verified PR1311 merge
  `3fe05fdf8a61ec7d40398175e161a73e0006b20a` using clean three-way source,
  test and lifecycle-document merges from R6 base `4cf7d5f4`. Verified the
  terminal manifest SHA256
  `dda50d4d72d5614d951d8b2627d44e7df4f4ce6f368aef229f7293f82e728c73`
  and all 69 preserved files. The original carrier, index and evidence remain.
- Retains PR1311 mechanical gates before fresh final approval, exact staged
  bytes, hook-receipt revocation with per-invocation provenance and isolated
  fixture repositories. Durable native completion, bounded same-HEAD
  stopped-to-merged ownership, committed-source sync, original transaction
  ownership, surviving-root coverage and tracked-report deletion intent now
  coexist with those repairs. Latest supervisor findings and failed shell
  diagnostics retain their bounded native continuation paths.
- Reconciles current row40 owner/parallel/next facts from PRIMARY and the
  durable R7 launch checkpoint. Preserves all 268 task IDs, the complete 39
  parked obligations, both substantive changelog histories and held journals.
  PR1311 landed at 2026-09-22T16:25:05Z; the older entries below describe their
  authoring-time evidence and pending status. R6 stopped without a commit.
- Derives current-base counts 361/131/67 and caps 171/63/19 from the unchanged
  committed algorithm v2 producer, with R7 provenance. Strict `note.txt`,
  existing L4 behavioral proofs and the empty exception registry remain.
  The exact optional nonblocking report is admitted without creating one.
- Initial implementation collection passed: 4,517 tools/growth cases and 351 docs cases.
  The exact anti-theater-first chain exited 0 with zero risks/exceptions:
  **4,517 tests passed in 693.90 seconds**, then **351 docs tests passed in
  1.73 seconds** with two existing freshness warnings. Fixtures use default
  system temporary storage outside checkouts; native stdout retains evidence.
  Native review, final gates, commit, CI, merge, PRIMARY sync and durable
  operational closeout remain with the outer pipeline. Existing eligible
  retirement and useful-work landing follow, then Mu; all 37 old fleet
  operations remain consumed.

- Supervisor reentry repairs commit-owned failed closeout followed by native
  continuation at unchanged HEAD, both before and after merge. The successor
  verifies and hashes the failed closeout, preserves prior terminal/attempt
  evidence, requires its own fresh successful closeout, and shares the original
  three-attempt budget across repeated failures. Interrupted preparation and
  changed predecessor evidence remain rejected. Reentry collection passed
  4,531 tools/growth cases and 351 docs cases. The exact anti-theater-first
  chain exited 0 with zero risks/exceptions: **4,531 tests passed in 678.23
  seconds**, then **351 docs tests passed in 1.77 seconds** with the same two
  freshness warnings. All 14 new regression cases passed. The preceding
  counts record the initial implementation only; native review and landing
  remain pending.

### Fleet native lifecycle R6 (stopped; preserved authoring-time evidence)

- Continues existing row40 on PR1310 merge `4cf7d5f4`. Verified the complete
  46-file R5 preservation manifest and the three-file generated-report failure
  manifest before selecting missing source, test and lifecycle-document hunks.
- Adds bounded durable completion for successful, stopped and failed native
  lanes, with useful-work and PR ownership, immutable attempts, and a verified
  same-HEAD stopped-to-merged successor sharing the original retry budget.
  Actual closeout/config/receipt evidence survives retirement in the common Git
  directory. Missing or failed closeout retains the source and correction owner.
- Uses freshly loaded committed recovery code and the existing identity/lock
  API for PRIMARY sync. Keeps transaction R2 as the R3 recovery enabler's plan
  owner and consumes replacement coverage from a synchronized surviving root.
  Stale localdev and unrelated untracked evidence remain preserved.
- Preserves source196 tracked-report deletion intent across admission, native
  journal and stash, including a real-layout fixture with a retained neighbor.
  Late-supervisor findings reach one bounded repair; failed shell diagnostics
  retain actionable stdout/stderr for the next planner and durable attempt log.
- The builder binds the exact optional same-wave nonblocking report before
  locking. Tests cover native production, absent/removed reports, unauthorized
  paths and refusal to expand an older locked contract. No placeholder report
  or persistence requirement is introduced.
- Uses the byte-verified committed PRIMARY algorithm v2 cap producer for the
  actual helper/test/doc additions: counts 361/131/67, caps 171/63/19, with R6
  provenance. Preserves the landed cap regressions, strict `note.txt` fixture,
  L4 behavioral proofs and empty exception registry.
- Separate collection passed: 4501 tool/growth cases and 351 docs cases. The
  exact anti-theater-first evidence chain exited 0: zero risks/exceptions,
  **4501 tests passed in 685.79 seconds**, then **351 docs tests passed in
  1.69 seconds** with two existing freshness warnings. Native review, final
  gate, commit, CI, merge, PRIMARY sync and completed-wave operational
  verification remain outer-owned.
- All 268 task IDs and 39 parked obligations remain. The 14 consumed/verified
  batches retain 137 MOVED / 1 SYNCED_LOCAL_DEV / 19 HOLD / 8 INCOMPLETE. The
  dated census of 92 direct folders and conservative 86 NEEDS_LANDING entries
  do not establish useful-hunk landing. Fresh eligible retirement authority and
  useful-work comparison remain with the existing cleanup owner immediately
  after this recurrence-control task; all 37 old operations are immutable.
### PR1311 existing-branch packet authority (Phase B; native review and landing pending)

- Preserves the explicit authorized control-surface L4_ENABLER purpose in the
  native R2 packet. Its real same-wave/authorization check passes before the
  declared evidence chain; final packet bookkeeping receives the same check.
- Carries all three reviewed receipt fixture repairs, both predecessor packets
  and the R1 indicator intact. The generated R2 indicator and canonical TASKS
  tracker note retain their incoming bytes. Production executor SHA256 remains
  `d72e695d1b564239ee91d5644b7a44d8f24ce10cceaa5f70106a3a25fbe4d239`.
- The declared evidence chain exited 0: zero theater risks or exceptions,
  **1,061 tool tests in 140.50 seconds** and **351 documentation tests in
  60.07 seconds**, with two existing freshness warnings. Native captured stdout
  and default system pytest temporary paths were used. Existing PR1311, row40
  and all 268 task IDs remain. Indexed handoff, fresh
  review, commit, full pre-push, CI, merge, PRIMARY sync and carrier closeout
  remain pending, followed by retained R6, physical cleanup/useful-work landing
  and Mu.

### Recovered PR1311 receipt fixtures (Phase B; native review and landing pending)

- Adopts the three preserved native fixture repairs. Durable Phase B and
  supervisor receipts use separate paths from canonical hook authority;
  temporary Git repositories isolate pager routing and ignore probes. Retains
  both approval checks, one final commit-ready event, exact missing-receipt
  rejection, persisted HOLD and no-replay assertions. The existing clock test
  also requires canonical hook revocation before final review while durable
  Phase B receipt bytes remain intact.
- The declared evidence chain passed: zero theater risks or exceptions,
  **1,061 tool tests in 142.10 seconds**, then **351 documentation tests in
  60.41 seconds**, with two existing documentation freshness warnings. Uses
  default system pytest temporary paths and captured stdout; the predecessor's
  reported 1,055 passes remain historical evidence.
- Continues on the existing PR1311 branch and carrier at local HEAD
  `21e55c437bb662838e90018661d9ccab4be0b6d8`. Production code, receipt lifetime
  and committed bot revocation remain unchanged. Same row40 and all 268 task
  IDs remain; native review/commit/full pre-push/CI/merge/PRIMARY sync and
  carrier closeout are pending, followed by R6, eligible physical cleanup,
  useful-work landing and Mu.

### Fresh final commit approval after mechanical validation (Phase B; native review and landing pending)

- Repairs the reproduced R6 ordering defect: successful native validation
  consumed 2,426 seconds after approval, beyond the unchanged 1,800-second
  receipt lifetime. The subsequent staged-hash mismatch is exactly accounted
  for by native failure-status demotion; the stale-item checker passed.
- Preserves the initial supervisor and receipt-checked mechanical hook, then
  requests fresh supervisor approval and validates the original handoff/final
  receipt chain after all mechanical checks pass. Candidate inventory and exact
  staged bytes reject drift before final review and again before Git, including
  legacy handoffs without inventory receipts. Commit-ready notification follows
  final approval; hold and post-commit continuation remain intact.
- Adds fast controlled-clock regressions using the shipped receipt writer,
  verifier and real temporary Git hooks, covering expired initial approval,
  failed gates/review, final staged drift, invalid receipts and hold/continuation.
  Existing canonical growth-cap producer/rejection, pager and no-replay tests
  remain selected. Separate collection passed 313 tool cases and 351 docs
  cases. The declared evidence chain passed with zero theater risks/exceptions,
  313 tool tests in 58.28 seconds and 351 docs tests in 1.65 seconds, with two
  existing documentation freshness warnings.
- Existing row40 retains ownership. Native review/commit/CI/merge/PRIMARY sync
  precede supported fresh-code R6 continuation, eligible fleet retirement and
  useful-work integration, then Mu. This repair does not close fleet cleanup.

## 2026-09-21

### Preserved cap producer R4 with complete native report authority (Phase B; native review and landing pending)

- Verified terminal R3 manifest SHA256
  `5a655745550b4c93a2af20479db6e3be092efc5ec97fbfeefd6ff1575fb051a6`
  and all 52 archived destination sizes/hashes. Restored exactly its seven
  scoped product files byte-for-byte onto fresh dev `59ddd15b`; old trackers,
  packets, indicators, reports, bus, receipts, claims and indexes remain history.
- Retains canonical three-cap producer algorithm v2, exact HEAD/index/worktree
  authority, finite shortfall, same-wave override and authored-content guards.
  Includes all six cap receipt regressions and six native recovery cases proving
  unlisted same-wave reports, other-wave reports and source paths are rejected
  before mutation. Diagnostics use actual errors without unlanded R5 fields.
- Preserves the ungoverned `note.txt` no-growth fixture with strict
  `no_new_test_files` and authority/cap/index/worktree assertions. All nine L4
  behavioral proof repairs retain route arguments, validator calls, depth 200,
  MAX_MU_DEPTH and JS/parity checks. The exception registry is empty; classifier,
  runtime/seed semantics and numeric cap bytes are unchanged. No governed file
  was added.
- The unchanged launch-owned 12-path authority admits only this wave's exact
  optional native `bridge_nonblockers.md` report. It remains absent without
  findings; this implementer creates no substitute artifact or new authority.
- Fresh local evidence at 2026-09-22T03:37:21Z: separate collections found
  **608 targeted cases and 351 docs cases**. The exact anti-theater-first chain
  exited 0: **current 0 / allowlist 0 / new 0 / expired 0 / real 0**, then
  **608 tests passed in 80.73 seconds** and **351 docs tests passed in 1.73 seconds**
  with two existing freshness warnings. Native final/review/precommit/prepush,
  CI, merge and PRIMARY sync remain pending with the outer executor.
- Keeps existing row40, all 268 task IDs, 39 parked obligations and useful-work
  owners. R1/R2 unpushed commits, stopped/uncommitted R3 and retained R5 remain
  distinct from current approval. Historical fleet results remain 14 consumed
  and verified operations, 137 MOVED / 1 SYNCED_LOCAL_DEV / 19 HOLD / 8 INCOMPLETE.
  After verified merge/sync, retained R5 lifecycle controls and deterministic
  optional-report admission precede eligible retained work, Mu and optimization.

## 2026-09-16

### PR1307 landed replacement coverage (Phase B; native review and disposition pending)

- Adds the same-wave schema-version2 coverage manifest for PR1307 only: all
  eight source paths and 23 hunks from `9e595b2bd8518e6debb4e88a51dca8412221db49`
  to `2be3fbfcde1dca0e409e9059fc52d9406f6ef750`. Canonical manifest digest:
  `12457690a8aec13d067368614862a82083da7f21391f0995ddda0f3e8daf68a6`.
  Thirteen useful hunks landed byte-exact; one is superseded by PR1308's two
  added eager-import dependencies and explanatory comments. Nine historical
  bookkeeping hunks remain preserved evidence, with current PRIMARY tracker
  facts authoritative. All four cited source/test files remain unchanged.
- Fresh native identity checks at 09:13:14Z confirm PR1307 OPEN at its retained
  source branch, PR1308 MERGED as `d774fbe711529e9bb9591f67fac5a8313941428a`,
  and live dev at that merge. The frozen R2 manifest SHA256
  `076b4e34cfdcaacfe989e07cabebb1e554c03edd7a54ec12f3f12a7c1b46933c`
  and all 48 stored sizes/hashes verify. Its separately staged import correction
  is credited to PR1308, not to the original PR1307 commit.
- Adds exact artifact identity, complete inventory, ancestry and byte-range
  proofs to the existing disposition tests, retaining all lifecycle/no-replay
  protections. The exact chained command passed **55 tool tests in 6.45 seconds**,
  then **351 full-docs tests in 1.60 seconds**, exit 0, with two existing
  documentation freshness warnings.
- Preserves all 268 task IDs, 39 parked obligations and existing row40 ownership.
  All 14 fleet batches have executed and been verified; 87 retained directories
  and held/useful-work obligations remain incomplete. Native staged indicator
  collection, review, commit, merge and PRIMARY sync precede foreground lifecycle
  plan/apply/verify with the actual landed authority. PR closure and permanent
  recurrence repairs remain pending under the same row40.

### Fleet live recovery R3 measured pytest deadline (Phase B; landing and live cleanup pending)

- Verified the stopped R2 manifest SHA256
  `076b4e34cfdcaacfe989e07cabebb1e554c03edd7a54ec12f3f12a7c1b46933c`
  and all 48 archived file sizes/hashes. Restored only its four scoped source/test
  files, including the staged P1 correction. Original stopped sources, raw index,
  PR1307, claims and stashes remain preserved; no old bookkeeping or wider R4
  source was copied.
- Retains recorded-owner journal isolation, Git-representable stash modes,
  exact saved filesystem permissions, authorized native behind-dev-marker
  removal, and the committed original-owner recovery CLI with single-use claims
  and no replay. Saved success remains checked against bound native completion
  and held-WIP evidence. Both eager imports, `bridge_adapters.py` and
  `tracker_sync_note.py`, are admitted before import/claim; all eight dependency
  rejection cases and prior recovery regressions remain intact.
- The shared targeted pytest runner grants 900 seconds to the exact full fleet
  module, retaining 240 seconds for each other selector and any larger explicit
  caller timeout. Twelve deterministic cases preserve selection, command flags,
  nonzero output, empty-selection behavior and finite timeout reporting. The
  preserved 293-test/574.48-second serial diagnostic is separate evidence from
  the failed 240-second gate; the interrupted 250.80-second run is not a pass.
- Both declared collection checks passed. The exact chained command passed
  **714 tool/receipt tests in 215.11 seconds**, then **351 documentation tests in
  1.65 seconds**, exit 0, with two existing freshness warnings. Post-bookkeeping
  full docs also passed **351 tests**, with the same two warnings. No module,
  counted file, cap or queue row was added.
- All 268 unique task IDs and useful-work owners remain. Row39 stays CURRENT:
  native review/final/receipt/commit/merge gates and PRIMARY sync precede committed
  original-owner recovery and unconsumed cleanup batches3-14. PR1307 remains
  STOPPED/PRESERVED until landed replacement coverage supports native disposition.
  Row40 retains broader lifecycle/PR/lost-feedback and wrong-scope recurrence
  ownership after actual eligible cleanup, before Mu. No live cleanup occurred.

## 2026-09-15

### Fleet transaction R2 ownership admission (Phase B; native landing and live actions pending)

- Verifies the newest stopped R1 manifest against SHA256
  `0257cefcc93dfed220c72047d3783446ec0343067e55f1e293b2999224a0e23f`
  and all 27 stored file sizes and hashes, then carries its eight source/test
  files. Complete transaction, index-blob, stash, safe-sync and committed
  authority repairs remain intact. The commit executor remains byte-exact
  to that snapshot; its baton regression additionally covers transaction R2.
- Contains ordinary exceptions at the existing read-only native ownership
  admission boundary as explicit uncertain-ownership HOLDs. Existing HOLD
  reasons and permission uncertainty remain protected, and operator
  interruptions propagate. No PID range allowlist or mutation-error catch is
  added.
- Extends the real disposable-Git batch regression with the synthetic oversized
  PID and a custom ordinary observation failure. Both retain the affected
  source, files, index and HEAD, record its HOLD, complete four eligible peers,
  verify outcomes and retain unchanged claims/receipts after rejected replay.
  Permission uncertainty and KeyboardInterrupt/SystemExit cases also pass.
- The declared eight-module command first reproduced **2 failed, 1533 passed,
  1 skipped in 281.73 seconds, exit 1**. With containment, the same command passed
  **1535 tests, 1 skipped in 277.79 seconds, exit 0**. The four witness modules
  remain unchanged; the earlier 1527 passing cases retain their coverage.
- Generates fresh R2 census/classification/useful-work/plan artifacts: 359
  entries, 218 direct directories, 140 behind-dev linked roots, and 14
  unconsumed operations for 164 worktree preservations and one local-dev sync.
  There are 194 HOLDs and 209 direct-source useful-work landing owners.
  PRIMARY, the current lane, preservation roots and all four stopped candidates
  remain protected. Historical consumed operations and stopped plans are
  unchanged. These artifacts record preparation, not physical cleanup.
- Preserves PRIMARY tracker history and all 39 parked obligations. Transaction
  R2 remains CURRENT at row 39, permanent native prevention and actual resume
  repair remain NEXT at row 40, then Mu. The locked Ra note retains L4
  authority; packet evidence uses the reserved non-normative clarification.
  Indicator collection, staged packet gates, independent native review/merge,
  PRIMARY synchronization and committed foreground apply/verify remain pending.

### Stopped fleet transaction R1 (historical; not landed)

Preserved from the hash-verified stopped R1 snapshot. Counts and validation
results in this section describe R1; its operations remain unconsumed.

- Carries the hash-verified R2 fleet inventory, detached-source, classification,
  complete lsof-reader, native-idle and saved-fixture repairs. The commit helper
  changes are limited to staged-deletion safe sync and the fresh task-keyed
  committed-action baton; baseline post-merge cleanup remains in place.
- Binds admitted semantic index entries and file content across preservation,
  native fast-forward/WIP preparation and retirement. Preserves index-only blob
  bytes and native temporary-stash history; later verification checks the
  retired index. Drift retains unresolved landing ownership and immutable
  evidence. Incidental Git stat-cache refreshes remain valid.
- Fresh bulk authority binds executing dependencies and wave artifacts to exact
  committed bytes, index entries and modes without the excluded lifecycle
  worker. Consumed operations cannot be replayed.
- Malformed stale native lock documents, holder types and timestamps produce
  explicit per-target HOLD receipts. Real Git regressions verify the held
  source's files, index and HEAD remain intact, eligible peers continue, and
  verification and rejected replay leave operation claims and receipts unchanged.
- Generates a complete 358-entry census with 217 present direct-prefix
  directories, including five standalone repositories and 140 behind-dev direct
  linked roots. The new plan contains 14 unconsumed operations for 164 worktree
  retirements and one separate local-dev synchronization; 193 rows remain HOLD
  and 208 direct sources retain useful-work landing owners. PRIMARY, live and
  stopped lanes, and preservation roots remain protected.
- Reproduces the original false-MOVED index race before the fix. Earlier Phase B
  evidence: 1505 passed, 1 skipped in 248.59 seconds (exit 0). Stale-lock re-entry
  reproduced 15 failures with 1512 passed and 1 skipped in 261.41 seconds (exit 1).
  After the repair, the same declared gate passed: 1527 passed, 1 skipped in
  268.04 seconds (exit 0). All fleet mutation in tests uses disposable
  repositories. Native merge, committed foreground apply/verify and the required
  NEXT permanent-prevention child remain outstanding.

## 2026-09-14

### Fleet residual completion (Phase B; landing and live actions pending)

- Retains PR1304's landed scalar `merged_pr` and native deferred-report
  provenance fixes at `ec14a25d44c3f70d9c7307b71ed863f36c1feafb`.
  The residual work does not reimplement those fixes or claim live retirement.
- Generates a fresh 440-row identity ledger, including 324 present direct
  prefix directories, and 23 bounded operations: 189 worktrees, 85 bus shells,
  one explicit local-dev synchronization candidate, and 165 owned HOLDs.
  The prior three incomplete targets are reassessed; canonical preservation,
  PRIMARY and the active lane remain protected. Old manifests and receipts
  are unchanged. Every candidate still needs committed action-time checks.
- Adds recoverable plan/apply/verify with byte archives, history bundles,
  retained Git registrations, native WIP-preserving checkout synchronization,
  separate local-dev outcomes and consumed-once terminal boundaries.
  Terminal pager events bind surviving PRIMARY and the selected route before
  lane retirement. Review activity metadata cannot mask unresolved findings;
  deferred resolution uses exact thread/comment snapshots and rechecks review
  after the asynchronous child commit.
- The exact declared eleven-module evidence command passed **1597 tests,
  1 skipped in 196.84s, exit 0**. Temporary repositories cover recoverable
  moves, registration retention, dirty local-dev WIP/stashes, no replay,
  terminal pager delivery after retirement and the demonstrated review races.
  The same fleet owner remains CURRENT after code merge until foreground
  outcomes and preservation are verified. Native landing, L4 collection and
  real directory retirement belong to the outer executor and foreground.

## 2026-09-13

### Hanging PR Lifecycle Completion R4 (Phase B; live outcomes incomplete)

- reconstructs the two production files and six regression modules from the
  content-addressed stopped R3 snapshot. All 85 preserved files match their
  recorded sizes and SHA256 hashes. Seven reconstructed files are byte-exact;
  `test_pr_disposition_executor.py` changes only its current-wave coverage path
  to R4. This retains manifest-bound one-time disposition, append-only ownership
  in the common Git directory, fresh per-target terminal authority, no replay,
  independent target HOLDs and the post-merge stop while live outcomes are owed
- rebinds the [coverage ledger](reports/control_plane/pr-open-lifecycle-completion-r4-2026-09-13_coverage.json)
  by changing only wave/owner/path identity and its canonical self-hash to
  `9cdc90d7471ce2b446a5833ecb446c415c96594fd6040e8dd3c9fe1043760603`.
  Local Git checks retain both exact source branches/heads, replacement
  PR1286/1299 ancestry, all 13 per-PR changed paths and 41 hunks, and all
  124 cited ranges (100 unique) against comparison commit
  `eb92c2e404addd69c2eb7dd54e808929bcff86a4`. These checks establish retained
  references and bytes; independent native review remains pending
- the declared six-module, four-worker evidence command passed **1232 tests in
  117.16s, exit 0**. No additional implementation/fixture repair or growth-cap
  adjustment was required. TASKS was synchronized mechanically from PRIMARY,
  preserving PR1303 landed history, all 142 task identities, 39 parked pipeline
  obligations, and the dirty-dev-checkout obligation under the next fleet owner.
  The same-wave tracker note remains the packet's L4 metadata authority
- R3 commit `1ed7b24e6b80488006b55ef83a0c7f39013e73ca` remains stopped and
  unpushed. R4 reviews, indicator collection, commit/pre-push/CI/merge and
  post-merge authority remain outer-executor work. PIPELINE-FIX-53 stays CURRENT
  until actual PR1284/1298 outcomes are verified or retain exact incomplete
  owners. After landing, committed lifecycle-plan/apply/verify must use surviving
  synchronized PRIMARY and the actual landed authority commit. Preserve any
  stale dirty-dev adoption HOLD and use the authorized committed CLI from
  verified PRIMARY. Fleet cleanup remains NEXT, then Mu production; code landing
  alone does not complete this task

### P0T3 Retained Fast-Root Process Ownership Closure R2 (Phase B, CURRENT)

- addresses only retained finding8 and subsumed P0A/P0B on exact PR #1302
  merge `75e323921116c2ea6cc739d3472c4cb97c730d9f`. Installs a unique
  inherited bridge ownership marker before launch and reconciles matching
  processes with recorded/current descendants at each cleanup boundary.
  This recovers ownership when the root exits before the first parent-graph
  snapshot, including when `on_started` raises. The existing bounded
  termination, received-output boundary and `on_result` ordering are retained
- adds two real-process cases in `TestBridgeReviewMonitoring`, arranging root
  exit before any snapshot without mocking discovery or liveness. The declared
  command `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py::TestBridgeReviewMonitoring --tb=short`
  first produced **2 failed / 7 passed in 4.18s, exit 1** at the post-return
  child-liveness assertions, then **9 passed in 4.13s, exit 0** after the fix.
  Both cases verify owned children dead after return/unwind, unrelated
  processes alive and unconditional fixture cleanup. Existing recorded-child,
  monitor-exception, callback, timeout and ordinary cleanup retain their credit
- keeps the rich P0T3 row 36 CURRENT with class `L4_ENABLER`, P0T4 immediately
  NEXT, then P0R2/P1-P5 and every later queue identity/order. The 2026-09-13
  same-wave TASKS tracker note owns L4 fields; the native packet derives them
  while preserving its nine launcher-owned header lines. Native packet/indicator
  generation, changed-test/control-surface gates, independent reviews and
  commit/CI/merge remain outer-executor work. R1 stays stopped and preserved;
  no new prerequisite, fleet/stopped-PR/stash action or Mu semantic advancement.
  The proof covers the two retained environment-inheriting schedules with
  process enumeration available; it makes no arbitrary-process containment claim

### P0T2 Landed Private-Review Durability Evidence (Landed)

- landed through PR #1302 at
  `75e323921116c2ea6cc739d3472c4cb97c730d9f` on 2026-09-13T21:16:20Z,
  from head `917e460b979995451424a949f91e7d30e6389186`. The recorded
  predecessor closeout reports native exit 0 at 21:19:55Z, exact PRIMARY
  fast-forward, absent owners and all seven CI checks SUCCESS. Its green-gate
  passed 11689 tests with 22 skipped and 6 warnings in 615.84s, plus separate
  1/515/149 passing gates. These are historical results for that landed head

- documents existing P0L round-2 findings 5/6 and subsumed P0C on exact
  PR #1301 merge `8e7c32a1438c21d47337ad16c77e9cec4bcb5ab6`. Implementation
  credit belongs to ancestor PR #1291
  (`fdfc58d52c717785a5696a8c3d36f9c934ee0030`) for prepared byte/mode/blob
  review authority, PR #1294 (`cdf2e02507cde0a3f1909ed00177ab1c474155a9`)
  for pre-actor ownership and sealed success, and PR #1295
  (`e8bb22ee251c5bf81f7ca6d98651fd507e508257`) for reentry-private
  findings/runtime context retention. This MAINTENANCE wave changes no
  production or test bytes and adds no queue position
- the declared existing focused command passed again during class reconciliation:
  **28 tests, 1184 deselected in 53.70s, exit 0**, including all parametrizations. The
  [closure report](reports/control_plane/pr1219-p0t2-private-review-closure-r1-2026-09-13_closure.md)
  maps current guards/callers and tests to the retained requirements.
  Ambiguous IN_FLIGHT fails closed without actor replay; sealed-success
  continuation preserves owed fresh review. Historical inline fault scripts
  and the old P0C max_bridge_rounds=2 transcript were not independently
  replayed; no exhaustive crash or broader private-review proof is claimed
- explicitly declares `MAINTENANCE` in the governing packet header and canonical
  same-wave tracker note, including maintenance no-op/defer metadata. The native
  package reader uses that header for regeneration, matching the launch-bound
  specification, rich queue selector row and closure report
- synchronizes the live queue owners and native tracker notes: P0T1 row 34
  LANDED PR #1301, P0T2 row 35 LANDED PR #1302, rich P0T3 row 36
  CURRENT, P0T4 immediately NEXT, then P0R2/P1-P5 and all remaining recorded
  work, Mu production before optimization. P0T2 native independent reviews,
  indicator collection and commit/CI/merge completed; P0T3 has its own pending
  native gates. Held P0T2 TASKS `7bfc528ba351bf6800e3aea12278d584457505be`,
  the earlier `8271020746511cb9a7917f584dc23766660072de`, older stashes/stopped carriers,
  open stopped PR #1284/#1298 and consumed fleet 1 MOVED / 3 INCOMPLETE /
  407 prior HOLDs remain preserved. The late P0T1 bootstrap-exception review
  stays deferred/nonblocking; post-retirement pager fallback belongs to P0R2

### P0T1 Terminal Identity and QUESTION Journaling R2 (Landed)

- landed through PR #1301 at
  `8e7c32a1438c21d47337ad16c77e9cec4bcb5ab6` on 2026-09-13T19:35:02Z,
  from final head `0fe48c3a1754d396fb9ef70683b8dd8c4f83ef3f`. The preserved
  terminal observation records native exit 0 at 19:38:37Z, exact
  PRIMARY/origin/dev/remote equality, absent owners and retired carrier.
  All seven final-head CI checks succeeded; green-gate run `34777230279`,
  job `103777456749`, passed 11689 tests with 22 skipped and 6 warnings in
  702.90s, plus separate 1/515/149 passing gates. These are historical results
  for this exact head. The final review request returned no clearance within
  59s before native clean-head/CI merge policy proceeded; the late 19:44:33Z
  bootstrap-exception review is not premerge approval
- initially reconstructed the three locked R1 source/test files on landed IB2/PR #1300
  merge `3ed23cf38edc47eb13e23e5471016f810467b79f`. The Phase B executor,
  its complete test module and the existing dispatch fixture exactly matched
  the preserved SHA256 values at initial reconstruction
- binds terminal recovery to the contained bus, canonical contained plan,
  wave and existing invocation. Safe plan aliases retain founder authority;
  foreign identity is refused without erasing the checkpoint. Accepted
  QUESTION is journaled before existing cleanup, rendering or pager failures,
  and redispatch returns founder-wait without new actors, validation or commit
- preserves R1's shared accepted-decision parser for trailing diagnostics and
  output without a final newline. On the same final Phase B test bytes, R1's
  12 failed / 1200 passed became 1212 passed in 287.03s after native reentry
  `3c97c9f1`; those results are historical evidence
- initial reconstruction included native `4bae8b05`'s required dispatch mock repair: accept,
  assert callable and invoke `on_result`, retaining all 11 supervisor package
  fields and Codex reader routing. Its historical target failed in 1.83s,
  then the complete dispatch module passed 748 tests in 244.16s. R1 stopped
  because its immutable allowlist excluded this fixture; commit
  `723d0a865f860c98f48b0b41bfcc6e9ed373df46` remains preserved and unmerged,
  with no PR. R2 includes the fixture in scope and complete-module validation
- initial fresh R2 validation passed both complete modules: 1960 tests in 340.59s,
  exit0, using the declared four-worker command with `PYTHONHASHSEED=0`,
  bytecode writes disabled and ordinary external OS temporary fixtures.
  That result binds the initial three-file reconstruction, not every later
  follow-up. Same-PR changes normalized routing aliases, durably retained
  rendered questions and isolated timeout fixtures after actual inherited
  5400-second failures. Final-head native gates and CI above cover that final
  candidate; no additional final local full-suite count is invented
- completes existing P0T1 row 34. P0T2 row 35 remains CURRENT pending its
  native closure merge, with P0T3 immediately NEXT and all later identities
  and order retained. Held TASKS `8271020746511cb9a7917f584dc23766660072de`
  and every older stash/stopped carrier remain preserved, including stopped
  PR #1284/#1298. The original eight PR closures remain preservation and
  reconstruction dispositions; consumed fleet never replays, and Mu production
  remains before optimization. Predecessor evidence is in PRIMARY's
  `reports/archive/control_plane/p0t1-terminal-identity-r2-evidence-2026-09-13/terminal_closeout_observation.json`

### P0IB2 Commit-Time Candidate Inventory (Landed)

- landed through PR #1300 at `3ed23cf38edc47eb13e23e5471016f810467b79f`
  on 2026-09-13T11:56:37Z, from head
  `523c1755e87210288cdfee92a74a45b9137fba5f`. The preserved predecessor
  closeout records native exit0, exact PRIMARY/origin/dev/remote equality
  and all seven current-head GitHub checks passing. No returned fresh
  GitHub review clearance is claimed

- binds the candidate after native Step 5/5e settlement to the existing shared
  authority builder before supervisor packaging, using the selected bus's
  launch-bound spec and exact comparison commit. The builder and routing reader
  load from committed executor source; candidate Python cannot approve itself
- verifies the same reviewed receipt and current index without preparation or
  restaging immediately before git commit. Existing receipt-chain validation,
  hooks, private-review integrity, ownership and no-replay checks remain active;
  legacy routes without configured authority retain their optional behavior
- public-entry baseline on IB1 merge `56cb682c1d440b776496aa00d49f499dfcfa69b9`
  reproduced the missing finalized-candidate receipt: 9 failed / 306 passed.
  Current production/test postimages passed all 318 tests in 34.08s using the
  declared complete two-module command, four workers and external OS temp
  fixtures. Public controls cover finalized generated governance, exact-base
  scope, required authority, stale receipts, missing generated index artifacts,
  index drift, optional legacy paths and candidate/ambient-module nonexecution
  under both bytecode settings. The shared builder is unchanged
- completed the existing unnumbered IB2 baton; at that landing, P0T1 became
  sole CURRENT with P0T2 next and every other queue identity/order retained. No
  runtime/substrate changes or debt reduction are attributed to this wave

### P0IB1 Recovery Authority R2 Preserved Bytecode Repair (Landed)

- landed through PR #1299 at `56cb682c1d440b776496aa00d49f499dfcfa69b9`,
  final head `eb525d891b9be3bfaf50f0b05e2e359c1b652d6e`. The predecessor
  closeout records native success and exact PRIMARY/origin/dev/remote equality.
  The original 900-second CI wait completed through the existing receipt-bound
  native continuation; it added no wave or prerequisite. The same PR's final
  repair replaced candidate Phase B imports with committed task/scope readers.
  All seven final-head checks passed, including 11619 tests / 22 skipped and
  the separate 1/515/149-test gates

- restored only the preserved `recovery_gate.py` and `test_recovery_gate.py`
  postimages on exact PR #1297 merge
  `5d852e20bd73ff75147c8fb6b117c195c0ec4855`, matching SHA256
  `6021cf7ce3c1d3f60663c5686dcc3bbd84a45f427b3cbebb7a0ebe6e6cddd007`
  and `a4e8f95b5b52cf1ac62b216138e1ab05ba267b75568d5797e2c0679b7957316e`.
  The shared candidate-authority builder and its test remain unchanged
- preserves the selected launch bus, required/optional spec identity and
  committed builder authority through actual recovery retry. Recovery rebuilds
  and verifies the current receipt before producing the retry; helper imports
  suppress bytecode writes and restore the caller setting
- credits R1's preserved 15 authority-loss reproductions and later seven
  bytecode-enabled failures: the helper import generated an unallowlisted
  `phase_b_executor.pyc` before receipt preparation. The test-only dual-mode
  baseline was 7 failed / 1402 passed in 88.31s; the bounded repair then passed
  1409 recovery-module tests in 89.87s. These are historical results. The first
  delegate's new scratch log failed audit; the second repository-nested-temp
  rerun was interrupted with an undiagnosed failure marker, not a completed
  validation or a second final audit rejection
- fresh R2 validation passed all 1456 tests in 47.03s with the declared complete
  two-module command and four workers, ordinary external OS temp fixtures and
  streamed output. The retained tests force both bytecode settings, verify the
  producer receipt before the existing consumer can rebuild it, and retain
  required-authority, legacy, candidate-code nonexecution and receipt controls
- at IB1's landing, existing row33 became LANDED, the retained unnumbered IB2
  baton became sole CURRENT and P0T1 was next; all114 queue identities/order
  were retained and Mu remained before optimization.
  PR #1298 remains OPEN stopped evidence; its branch/worktree/logs and held
  TASKS stash `c5c096f235692045998e37c36533e89c0b84220a` remain preserved.
  Held overlapping TASKS stash `2c5be99d4dfecac3cd9bcc75ad08ccbb0fcd03c1`
  and all older stopped/held evidence remain preserved. The initial 1456-test
  result above predates the final committed-reader repair; final-head native
  and CI evidence is recorded in the predecessor closeout

### P0IBRR Reviewer-Refusal R2 Bounded Reconstruction (Landed)

- landed in PR #1297 at exact merge
  `5d852e20bd73ff75147c8fb6b117c195c0ec4855` on 2026-09-13T07:05:52Z.
  Native exit0 at 07:09:22Z and exact PRIMARY/dev fast-forward were verified
  in the terminal observation recorded by TASKS; all seven current-head GitHub
  checks succeeded. The held TASKS stash
  `c5c096f235692045998e37c36533e89c0b84220a` remains retained

- reconstructs the six owned bridge/recovery paths from hash-verified R1
  implementation evidence on exact PR #1296 merge
  `8aa09a6bde8b947ffe61810a0d616ce40d95b100`. Only the observed terminal
  nonzero Codex reviewer JSONL chronology produces invocation-bound refusal
  evidence. One fresh review retains provider safety and the tightened
  read-only prompt; repeated or unresolved refusal review stops durably
- closes the recorded stale-fresh terminal-before-render defect by invoking
  the existing `fresh_turn_stale` terminal producer before optional rendering.
  The real bridge producer, public Phase B transport and recovery fixture
  reproduced one missing-terminal/Tier3 classification failure in 2.50s before
  repair. After repair it proves durable terminal emission despite injected
  rendering failure, no extra refusal turn and no Tier3/candidate mutation
- fresh R2 controls passed 22 tests in 2.23s; focused refusal/staleness tests
  passed 78 in 9.64s; the complete declared two-module command passed 1625 in
  45.14s with four workers and unchanged six-file hashes. R1's 1624 tests in
  45.50s remain historical evidence; R1 is preserved STOPPED_NOT_LANDED
- RR is LANDED; existing IB1 remains sole CURRENT with IB2 immediately NEXT,
  all existing queue identities/order and held/stopped/consumed evidence
  retained. No runtime/substrate or launcher change

## 2026-09-12

### P0IBRRT Lossless Phase B Terminal-Result Transport (Landed)

- landed in PR #1296 at exact merge
  `8aa09a6bde8b947ffe61810a0d616ce40d95b100` on 2026-09-13T04:38:26Z.
  Native launcher/dispatcher exit0 at 04:42:03Z and exact PRIMARY/dev
  fast-forward were verified in the preserved terminal observation. The held
  TASKS stash `594557af7a878a2693b6dc3c6126bd5064f844e9` remains retained

- carries the complete final standalone reviewer terminal JSON object through
  ordinary, reentry, private-attribute and reentry-private-attribute review
  failures, including the prepared-review material error return. Qualification
  requires a nonzero integer exit other than the three executor sentinels,
  exact active/bridge/payload job identity, and nonblank direct error and
  terminal-decision strings. Opaque members retain their decoded values;
  companion exit, job and complete-stream paths bind to the failed invocation
- fresh public-path tests on exact PR #1295 merge
  `e8bb22ee251c5bf81f7ca6d98651fd507e508257` reproduced all 16 missing-object
  failures in 3.15s. Two prepared private-review resume cases then reproduced
  the same omission in the retained-material error return in 2.54s, with
  candidate bytes and checkpoint authority preserved. Existing verdict,
  timeout, prepared-review and cleanup controls passed all 138 tests in 38.18s.
  After repair, all 300 focused regressions/controls passed in 46.98s and the
  exact declared full Phase B module command passed all 1155 tests in 267.74s.
  Production and test SHA256 values remained unchanged throughout the full run
- keeps the existing recognized verdict branches and PR #1291/#1292/#1294/#1295
  lifecycle authority. RRT is LANDED; existing RR is the sole CURRENT policy
  consumer, followed by IB1/IB2 and every later task in order, Mu production
  before optimization. Its transport remains unchanged in RR reconstruction

### Preserved P0IBRRC Reentry-Private Checkpoint Handoff R2 (Landed)

- landed through PR #1295 at exact merge
  `e8bb22ee251c5bf81f7ca6d98651fd507e508257` on 2026-09-13T02:17:31Z,
  from head `f79a88188870caf01b1a92c20f4bb40ee779f2f0`; TASKS records exact
  PRIMARY/remote fast-forward and old-owner absence at 02:30:22Z. The native
  post-retirement exit1 remains preserved: pager import/fallback failed against
  retired source and terminal-receipt persistence lost routing authority.
  The original triggering failure payload was not retained. The held TASKS
  stash `249344221c03f8c1baa551f36e51efb61a2c4422` remains immutable evidence

- reconstructs the two production and two test modules from the preserved R1
  repair on exact PR #1294 merge
  `cdf2e02507cde0a3f1909ed00177ab1c474155a9`; all four tested source hashes
  match the archived 1720-test observation. The stopped second delta supplies
  the same-handoff tests and two bounded corrections evaluated freshly here
- retains explicit reentry-private identity, exact current findings and boolean
  runtime-pre-push authority through correction, finalization and owed review.
  A consumed private GO followed by supervisor NEEDS_PHASE_B atomically hands
  off to the fresh supervisor continuation, retained until the next mutator
  takes ownership. Both dispatcher routes preserve/refuse that authority,
  including interrupted notification before the actor, without repeating the
  successful private correction or review. Non-string supervisor steps refuse
  before membership testing
- fresh public baseline on unchanged PR1294 production reproduced both missing
  context-marker failures in 2.63s. The preserved repair with the stopped
  handoff tests reproduced 10 failures/51 passes in 29.51s: pre-actor checkpoint
  loss and a non-string supervisor-step exception. After the two corrections,
  all 134 focused regressions passed in 55.48s and all six control-surface
  invariants passed. The unchanged complete two-module evidence command passed
  all 1741 tests in 315.70s with four work-stealing workers; production and test
  hashes remained unchanged throughout validation. Independent Phase B GO,
  native final pytest PASS, three COMMIT_GO supervisors with all 11 gates PASS,
  and all seven current-head GitHub checks passed before the recorded merge
- credits PR #1291 prepared review, PR #1292 ordinary ownership and PR #1294
  general implementer ownership. R1 is STOPPED_NO_LANDING after actual
  pre-validation scratch-audit rejection; its evidence and all held stashes
  remain preserved. This run uses the ordinary external OS temporary directory
- retains existing RRC row30 as LANDED, RRT CURRENT and RR immediately NEXT, then
  IB1/IB2 and every later task in order, Mu production before optimization.
  Both consumed fleet operations retain 1 MOVED/3 INCOMPLETE/407 prior HOLD

### Preserved P0IBRRCO Implementer Ownership R2 (Landed)

- landed through PR #1294 at exact merge
  `cdf2e02507cde0a3f1909ed00177ab1c474155a9` on 2026-09-12T21:39:59Z,
  from head `465e9d547e3d12d1577dccecd90b2702ad496bb9`; native
  launcher/dispatcher exited 0 at 21:43:35Z and primary fast-forward reached
  the exact merge. The bounded landing evidence is recorded in TASKS.md
- ports exactly the two production and two test modules from the read-only
  R1 terminal `candidate_snapshot` under
  `reports/archive/control_plane/p0ibrrco-inflight-r1-evidence-2026-09-12/terminal_recovery_timeout_stop/`;
  all four SHA256 values match its manifest on exact PR #1293 merge
  `c7fed5bba8de7898b686a636cecc42e379968eec`. R1 execution artifacts and
  approvals remain historical evidence
- retains durable ownership before initial, private-remediation and reentry
  mutation; seals known success before fallible finalization; carries ownership
  through SDK review and post-GO pager/convergence checkpoint handling. Both
  dispatcher routes preserve unresolved ownership before retry, recovery or
  state clearing. Ordinary success, explicit failure, corrective
  REQUEST_CHANGES/NO_GO and QUESTION refusal retain their existing behavior
- credits the archived R1 public before/after reproductions: 14 initial
  ownership failures, three SDK replay failures and seven post-GO failures
  before their respective repairs. The completed candidate passed 51 focused
  checks and all 1613 tests in 268.76s with four work-stealing workers; these
  are historical results. R1 stopped after the separate native serial recovery
  validation hit its 300-second cap and repeated the same target, without a CO
  commit or merge
- the fresh R2 control-surface invariant check passes all six invariants,
  including INV-2; the exact full two-module command with four work-stealing
  workers passed all 1613 tests in 268.41s. Independent Phase B GO, native
  final pytest PASS, three COMMIT_GO supervisors and all seven current-head
  GitHub checks passed; no independent GitHub review clearance is claimed
- retains this same CO queue position as LANDED, with P0IBRRC CURRENT and
  P0IBRRT immediately NEXT, all later task identities in order, Mu production
  before optimization, stopped evidence and the held TASKS stash preserved.
  No later RRC semantics, recovery infrastructure, runtime, substrate or fleet
  behavior changes

### Exact P0IBRRCP Landed-Evidence and Queue Closure (Landed)

- landed through PR #1293 at exact merge
  `c7fed5bba8de7898b686a636cecc42e379968eec` on 2026-09-12T14:55:50Z,
  from repaired head `f39be0ab874ac951b386c957c684c3c5c779472e`;
  native launcher/dispatcher exited 0 at 14:59:27Z and primary fast-forward
  reached the exact merge
- verifies only the normal-root recorded-child requirement already implemented
  and tested in PR #1256, merge `0a4c24120141723d70e6dd1c476ffaa70b1ff9ca`,
  an ancestor of exact PR #1292 merge
  `f7e27eadabd7d599ae2fd550aef23b21349b9b96`; this MAINTENANCE wave changes
  documentation and native governance only
- the [bounded closure report](reports/control_plane/pr1219-p0ibrrcp-exact-closure-r1-2026-09-12_closure.md)
  maps current file:line evidence to preserved prior/current child snapshots,
  bounded cleanup before normal return, root exit/output preservation and the
  unchanged synchronized real-process regression; the single declared fresh
  regression passed (1 passed in 1.04s), and the identical command passed again
  during classification re-entry (1 passed in 0.93s)
- reconciles the existing closure baton into one rich numbered entry at its
  existing semantic position; the native selector returns this exact wave and
  canonical packet. The two inherited successor paragraphs retain their
  historical merge facts and now match current queue order
- exact P0IBRRCP closure and P0IBRRCO ownership are LANDED; P0IBRRC is
  CURRENT, then P0IBRRT immediately NEXT, P0IBRR, P0IB1, P0IB2 and every later
  recorded item, with Mu optimization last. Private-review R2, all aliases,
  stopped evidence, immutable cleanup claims/backups and consumed outcomes
  1 MOVED/3 INCOMPLETE/407 prior HOLD remain preserved; no fleet replay or PR
  terminal action is added by this ownership implementation
- predecessor Phase A/Phase B and three supervisors approved after same-wave
  MAINTENANCE class-header correction. The independent same-PR P1
  packet-lifecycle finding was repaired in two docs; green-gate run
  `34700014415`, attempt 1, passed 11107 main-suite tests with 22 skipped in
  529.75s, and all seven checks passed. Native current-head review wait timed
  out after 59s; its clean current-head snapshot policy proceeded through fresh
  CI verification and merge. No independent repaired-head review clearance is
  claimed. Full terminal evidence remains in
  `reports/archive/control_plane/p0ibrrcp-exact-closure-r1-evidence-2026-09-12/`;
  held TASKS stash `673a84136e45aba8d69686d41b2039e27447193d` remains preserved
- supervisor re-entry reconciled the same-wave canonical tracker to the locked
  MAINTENANCE classification, including its no-op proof and defer reason; a
  tracker-derived packet Class header prevented native package refresh from
  falling back to L4_ENABLER. No broader process, runtime, substrate or Mu
  completion is credited to this documentation closure

### Ordinary Bridge-Fix Outcome and Dispatcher Boundary R3C6-R4 (Landed)

- landed through PR #1292 at exact merge
  `f7e27eadabd7d599ae2fd550aef23b21349b9b96` on 2026-09-12T13:11:06Z, from
  head `9674ec343f0455efdfaca03109692477db3d308e`; primary HEAD and remote
  `dev` match the merge
- reconstructed only the four hash-preserved R3 source/test diffs on exact
  PR #1291 merge `fdfc58d52c717785a5696a8c3d36f9c934ee0030`; stopped R3/R2
  remain noncomplete evidence
- retains verified durable `IN_FLIGHT`, strictly sealed
  `SUCCESS_PENDING_FINALIZE`, independent input authority, actor-free
  finalization and exact-command success continuation
- preserves native ordinary authority, mutation, finalizer and post-success
  validation errors before dispatcher recovery or checkpoint clearing, through
  both CLI entrypoints, A-to-B chaining and later continuation results; shared
  pre-actor errors require the selected bus's ordinary checkpoint
- reproduced the required checkpoint-loss defect with eight failing public
  regressions before correction; those eight now pass, and the extended
  48-case native CLI/dispatcher set passes with no protected-error recovery or
  replay. Explicit actor failures retain their existing recovery behavior
- the complete declared two-module command passed 1510 tests in 912.78
  seconds, including the existing identity, private-review and reentry controls;
  independent Phase B passed 61 focused tests, three supervisors returned
  COMMIT_GO, and native pre-commit/pre-push and all seven GitHub checks passed.
  Green-gate run `34695050659`, attempt 1, passed 11107 main-suite tests with
  22 skipped on the exact head above. These are retained predecessor results,
  not fresh full-suite validation of this documentation closure
- post-retirement closeout is a separate nonblocking bookkeeping exception:
  native R4 exited 1 at 2026-09-12T13:12:50Z after carrier removal; recovery
  could not import the deleted pager and terminal-receipt persistence failed.
  The prior failed/timeout triggering payload was not retained; its cause and
  successful old successor-package publication remain NOT_ESTABLISHED.
  Read-only primary evidence is
  `reports/archive/control_plane/r3c6-r4-evidence-2026-09-12/terminal_closeout_observation.json`;
  no native exit 0, restored/replayed carrier or imported predecessor authority
  is claimed. The carrier is deregistered and no predecessor owner remains
- R4 landed in the same slot; exact P0IBRRCP closure later LANDED in PR #1293
  and P0IBRRCO in PR #1294; P0IBRRC is CURRENT with P0IBRRT immediately NEXT,
  and both consumed fleet operations and every later independent obligation
  remain unchanged

## 2026-09-11

### Commit-Supervisor NEEDS_PHASE_A Terminal Retry Fence R2

- landed through PR #1285 at exact merge
  `c382fcfc2277676a4354190e326ead312faab7dd`
- recovery now treats only an exact structured failed same-candidate
  `NEEDS_PHASE_A` decision as terminal, without combining status, decision, or
  provenance from different result objects

### Native Stub Same-Config Phase B Relaunch Repair R4 (Landed)

- landed through PR #1286 at exact merge
  `8bc47cfa28965fc629fc4e1eb113a7a6adc7427c`
- preserves corrected R2 after its three-finding Phase A stop and R3 after its
  five-finding broad-lock nonconvergence; neither carrier is completion or
  implementation authority
- records a versioned, artifact-bound terminal receipt only after a native
  dispatcher returns a normal nonzero integer, then gives one exact locked
  same-config Phase B candidate a single-use no-clobber claim
- revalidates route, packet worktree/index bytes, tracker, candidate authority,
  lifecycle exclusions, active-review absence, and receipt hashes before any
  bridge mutation; an interruption leaves the claim fail-closed
- reconciles only the established bridge fields and resumes through the
  explicit dispatcher Phase B surface without rerunning Phase A or tracked
  setup producers
- preserves ordinary same-config unlocked Phase A retries after a dispatcher
  failure; an existing claimed receipt still refuses re-entry
- fleet cleanup census R3 followed and landed together with its fixture repair
  in PR #1287

### Fresh WorkingRCX Fleet Census R3 and Codex Astra Defaults (Landed)

- landed together with the same-PR fixture repair through PR #1287 at exact
  merge `c209bf29841425305003eeceddfd567a93874742` on 2026-09-11T20:13:36Z

- implements a new read-only CLI and temporary-fixture tests for the direct
  WorkingRCX-prefixed sibling and registered-worktree union, path-preserving
  metadata, dirty counts, missing entries and explicit inspection failures;
  every observation remains `UNCLASSIFIED`
- synchronizes the existing Codex registry selection, fallback and committed
  default expectation to `gpt-6-astra` / `max`, preserving other providers and
  existing all-Codex routing; the migration landed with PR #1287
- the supplied revision environment selects installed Git 2.55.0 at
  `/opt/homebrew/bin/git`, satisfying both required Git capabilities after
  Bridge Round 1's Apple Git 2.24.3 failure; the CLI documents its requirements
  and focused regressions retain explicit errors for both legacy behaviors
- repairs repeated wave evidence after the declared census artifact exists:
  the same regular output may be refreshed for the same fleet root and anchor
  using fresh observations; unrelated files, mismatched inputs, symlinks and
  hard links remain refused, and no prior census observations are reused
- supervisor re-entry reproduced target writes from configured clean/process
  filters, including effective local, included, global and worktree settings
  and submodule inspection; the CLI now skips unsafe dirty probes and records
  explicit unknown dirty status/counts while retaining available Git metadata
- ten disposable filter-trigger regressions now prove no filter execution or
  target byte/mtime changes, including Git indexes and refs; configuration and
  index inspection failures also retain explicit unknown evidence
- original-wave local validation recorded 46 passed and 1 skipped (the
  filesystem rejects the non-UTF-8 pathname fixture); the fresh declared JSON
  artifact records 411 UNCLASSIFIED entries from 296 direct siblings and 337
  worktree registrations with 222 duplicate paths and both sources complete;
  89 missing-path records retain explicit errors; all three declared
  validations, including the census refresh and staged L4 contract, passed locally
- this original ten-path package and the fixture repair below landed in the
  same PR; captured evidence remains preserved and the source census unchanged
- classification is now current, pending its own merge, followed immediately by
  apply and the existing downstream order; all stopped attempts remain
  preserved noncomplete evidence, and the census authorizes no fleet mutation

### Census R3 CI Fixture Isolation on PR #1287 (Landed)

- reproduced all eight fixture failures at reviewed head
  `4658184dd456d48e702176831d43c84fa5b8bfd0` using disposable ambient Git-filter
  configuration; the executable never ran, and unknown dirty observations
  were the production CLI's intended safety behavior
- fixture setup and every census invocation now use temporary home/XDG paths
  and a Git wrapper that disables system configuration at exec; explicit
  fixture home and PATH overrides retain the existing global-filter and
  inspection-error coverage
- six ambient clean/process regressions cover home, XDG and disposable system
  configuration, asserting exact clean/dirty counts, no filter execution and
  unchanged target/configuration bytes and mtimes; all ten existing explicit
  local/include/global/worktree filter and submodule safety cases still pass
- the declared focused tests pass in both ordinary and ambient-filter
  environments: 52 passed, 1 skipped in each (the existing non-UTF-8 pathname
  fixture is unsupported on this filesystem); disposable validation trees
  were removed without adding fixture links to the active scratch baseline
- the original Phase B staged L4 check rejected the empty implementation index;
  the outer executor subsequently completed staging, revalidation, review,
  supervisor gates, pre-push and all seven successful GitHub checks, then
  merged the existing PR at `c209bf29841425305003eeceddfd567a93874742`
- production census code, captured census, Astra/max defaults, original locked
  packet and preserved recovery evidence remained unchanged by the test repair;
  the executor retired the merged R3 carrier after separate verified evidence
  preservation and exited 0; classification is current and apply remains next

### WorkingRCX Fleet Preservation-First Classification R1 (Landed)

- landed through PR #1288 at exact merge
  `23197ef9079ec47a022611dcc90fa848cbf4ee9f` on 2026-09-11T22:15:34Z;
  all seven GitHub checks succeeded and the final focused suite passed 76 tests

- implements `mu/tools/executors/workingrcx_fleet_classification.py`, consuming
  only the landed R3 census with raw SHA-256
  `ac6f61337081c9adb7c100bac061270f6c7864aaed55d48912f50b8473d0cd81`
  and exact comparison commit `c209bf29841425305003eeceddfd567a93874742`
- accounts for all 411 input rows: **4 CONDITIONAL_RETIRE_CANDIDATE and 407
  HOLD**; a finite 14-path policy screens recorded identities, with local
  carrier object queries proving four ancestors, retaining nine unmerged
  heads on HOLD and excluding one standalone repository
- preserves complete source identities, observation/error evidence and all
  89 missing-path records; primary/preservation/audit/admin/carrier and
  canonical queue evidence remain HOLD, including clean preserved attempts
- every conditional candidate retains unmet identity, idle/protection,
  valuable/untracked/ignored evidence and branch/history preservation, safe
  never-behind preparation and exact `execute_terminal_mutation_once`
  prerequisites, including the boundary's fresh fetch and behind-zero check
- 65 disposable focused tests passed, including all 411 remapped recorded rows,
  source binding, local-only Git probes, dirty/unmerged/protected/unknown HOLD,
  target byte/mtime preservation and deterministic no-clobber repeated output;
  the real source was neither regenerated nor used to inspect live targets
- the classifier generated the complete report; after the initial empty-index
  L4 rejection, the outer pipeline completed generated governance, staging,
  revalidation, review and landing
- no fleet or stale-PR mutation occurred. All 407 HOLD obligations remain
  unresolved; bounded apply is current, followed by the retained recovery,
  exact PR1219 and Mu-production order

### Bounded Recoverable WorkingRCX Fleet Apply R1 (Code Landed; Zero Moves)

- landed through PR #1289 at exact merge
  `a9e8d85a3d2f08b1a599c8f8ddecdc23f6ea38ec`; its one postmerge invocation
  exited 3 with **0 MOVED, 3 HOLD, 1 INCOMPLETE** and 407 untouched HOLDs

- implements a finite plan/apply CLI bound to the exact PR #1288 classification
  and raw SHA-256 `19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf`;
  its deterministic plan accounts for all 411 rows, four conditional targets
  and 407 untouched HOLDs, without refreshing the census or inspecting targets
- the separate postmerge command in
  `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json`
  requires freshly fetched landed tool/plan authority, exact target identity,
  clean tracked/untracked state, idle process/native evidence and TASKS protection checks
- verified local source/admin archives and a branch-history bundle precede
  strictly fast-forward-only preparation with ignored-file overwrite disabled;
  each whole-worktree move runs inside the existing target-bound one-shot
  callback after its fresh fetch and behind-zero proof
- fixed local intent and per-target receipts preserve ambiguous/incomplete
  outcomes and refuse replay; destinations are new subdirectories outside all
  411 source targets, and private evidence remains local
- 40 disposable focused tests and repeated deterministic plan validation passed;
  the outer pipeline completed staging, governance, review, supervisors and
  seven successful GitHub checks before merge
- three targets stopped at inactive recovery states the tool did not recognize;
  index 292 fast-forwarded to the recorded prepared head, then stopped at lsof.
  The old probe retained no handle or warning detail. All boundary fields are
  null, and no terminal identity, move-started receipt or destination exists
- original receipts, source/admin archives, history and the consumed common-dir
  claim remain immutable; R1 must never be replayed. Cleanup remains incomplete

### Observed Fleet Apply Action Reconciliation R2 (Landed; Live Attempt Consumed)

- landed through PR #1290 at exact merge
  `d6be67a8019c373f961e8c224cd7cb9c0646d746` on 2026-09-12T00:52:55Z

- adds the fixed `--reconcile-r1` planning/apply mode in the existing cleanup
  slot; deterministic planning binds the landed classification and R1 plan
  without inspecting live targets or requiring host-local receipts in CI
- pins eleven R1 metadata hashes, all four no-terminal-action outcomes and the
  original claim; verifies index 292's archives, branch history, fast-forward
  transition and original ignored evidence before adopting its prepared HEAD
- retains original source provenance separately from action-time HEAD, with a
  new one-shot claim and preservation destination; all moves still use the
  existing exact-target callback and its fresh fetch/behind-zero proof
- admits only coherent inactive finished `tier3_exhausted` and
  `tier3_short_circuited` recovery records during reconciliation; live owners,
  children, locks, protection, drift and uncertain process probes remain HOLD
- retains each fresh lsof observation in new local outcomes, including output,
  warnings and timeout evidence; the historical lsof cause remains unknown
- the one-time live follow-up exited 3: index 292 made one recoverable move to
  `292/worktree`; indices 159, 163 and 305 remain INCOMPLETE at their source
  paths after preparation, with no destination or terminal callback
- the recorded lsof observations retain open-file refusals after fast-forward;
  no process was killed or gate relaxed. All 407 original HOLDs remain untouched
- TASKS retains the consumed command, outcome locations and summary SHA-256
  `22a6302ed49034823912b5ffecc7bf233d0b1ecaf6cf81e21a24e26240a6bf80`;
  neither R1 nor R2 may be replayed, and this result is not fleet-wide closure
- recovery R2 is the existing current slot, followed by fresh R3C6-R2 and every
  retained PR1219/Mu obligation, with no additional cleanup queue item

### Private-Review Prepared-Checkpoint Byte-Preserving Resume R2 (PR #1291 Unmerged)

- reconstructed from exact PR #1290 merge; all stopped candidates remain
  preserved noncomplete evidence, with no imported code or review authority
- ordinary and reentry private-attribute remediation retain a non-resumable
  pre-preparation checkpoint, then save distinct prepared pending state after
  successful staging, bound to launch identity, review round, saved findings,
  deferred identity, staged path inventory, index modes and object/blob bytes
- prepared recovery verifies the saved authority and index/worktree equality
  before mutation, then invokes the owed reviewer without preparing, collecting
  L4 evidence, restaging or replaying implementation before that review
- recovered decisions require the retained canonical reviewer envelope and
  exact job/turn/decision identity before continuation; malformed or missing
  material preserves pending state, and valid QUESTION remains terminal
- the declared full `test_phase_b_executor.py` module passed all 693 tests;
  public regressions exercise both recovery paths, preparation crash boundaries,
  authority and byte mismatches, recovered QUESTION material and GO continuation
- original implementation passed first-round Phase A/B, three supervisors and
  pre-push and is committed in open, UNMERGED PR #1291 at
  `571f0999288f6a5c8f4d76bda9aa0c45ddc58ea5`; green-gate run `34668334150`
  attempts 1 and 2 failed on the unchanged census fixture's disappearing
  `maintenance.lock`. The 693-test result covers the private-review module;
  the census fixture repair has its own whole-module evidence below

### PR #1291 Fixture CI Repair R2 — Native Existing-Branch Binding (Phase B)

- prior narrow repair `private-review-r2-ci-fixture-maintenance-2026-09-11`
  passed 40 tests/1 existing skip, first-round Phase A/B and two supervisors,
  then stopped before commit/push because its input omitted the literal
  `existing PR branch` marker and explicit control-surface authorization;
  native commit selected a new branch from origin/dev. This was a branch-binding
  stop, not a test failure; all stopped candidates, indexes and evidence remain
  preserved and supply no fresh approval authority
- corrected wave `private-review-r2-ci-fixture-maintenance-r2-2026-09-11`
  implements exactly the preserved 19-line repair, SHA256
  `74a9c5e0a3abe0affcd9541d8a736cccb8cfc630418dfcbf9dfd6e8aeb9ac33b`:
  fixture Git calls receive `-c maintenance.auto=false`, and a trace regression
  requires a real fixture commit with no Git maintenance/gc child starts
- declared Phase B-local validation
  `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py --tb=short`
  passed **40 tests with 1 unchanged skip in 44.81s**. Snapshot bytes, mtimes,
  indexes, refs, output-preservation assertions and explicit filter/submodule
  coverage remain unchanged; the prior unsuppressed trace proof is retained
- the fresh locked native packet preserves `existing PR branch` and
  `Authorized control-surface L4_ENABLER`. Read-only evaluation of the native
  Phase B selector resolves exactly
  `jabramsja/phase-b-private-review-byte-preserving-resume-r2-2026-09-11`;
  native staging, indexed packet authorization and commit handoff remain with
  the outer pipeline
- this repair is locally implemented and validated, still uncommitted;
  current-wave Phase B review, supervisors, push, CI and merge remain pending.
  PR #1291 remains unmerged in the same landing slot, with no new PR
- cleanup remains **1 MOVED / 3 INCOMPLETE / 407 prior HOLD**, and both R1/R2
  one-shot operations remain consumed. Fresh R3C6-R2 stays immediate next only
  after actual PR #1291 merge and native closeout, followed by every retained
  PR1219/Mu obligation in its existing order

## 2026-09-10

### Commit-Generated Governance Retry Idempotency R3

- reconstructs the exact useful R2 code/test result after that preserved lane
  passed 33 focused tests and all 258 receipt-chain tests but did not complete
  because malformed reviewer-envelope text failed closed and the documented
  same-config native-stub relaunch was deterministically rejected
- `commit_executor.py` preserves exact failed-attempt retry settlement: Step 5e
  stages one canonical same-wave growth-cap increment and provenance entry, and
  a retry recognizes the recomputed postimage without adding a second increment
  or provenance suffix
- canonical target absence retains the established non-mutating
  `growth_cap_file_absent` outcome only when the target is absent from `HEAD`,
  the stage-0 index, and the worktree; partial absence, tracked deletion,
  index/worktree-only presence, and byte or mode drift remain fail-closed
- focused regressions remain in the existing commit-executor test file, and the
  unchanged complete receipt-chain suite remains the compatibility gate for the
  three canonical-absence regressions that stopped R1
- the separately queued native-stub same-config Phase-B relaunch repair remains
  next before fresh fleet census R3; this wave changes no launcher or fleet code

## 2026-04-04

### Linked Worktree Pre-Commit Gate Truth

- `meta_bridge_supervisor.py` Gate 5 now accepts the shared managed
  `tools/hooks/pre-commit-doc-check` hook when a linked worktree resolves it
  through the common git directory of the primary checkout, instead of falsely
  treating that valid shared-hook install as missing delegation
- `mu/tests/tools/test_meta_bridge_supervisor.py` now locks that behavior with
  a real `git worktree add` regression so routed post-merge review cannot block
  the end-to-end proof on the same false worktree mismatch again

### Post-Commit Round-Trip Follow-On

- `phase_a_executor.py` now gives stub-only Phase A packet rewrites a much
  shorter implementer timeout budget than full implementation work, so a simple
  blank-packet rewrite cannot sit on the full generic 15-minute implementer
  budget before failing stale
- `mu/tests/tools/test_executor_dispatch.py` now locks that stub-rewrite budget
  directly in the existing packet-scope regression, so the shorter timeout
  cannot silently revert
- `reports/control_plane/post_commit_roundtrip_2026-04-04.md` now records that
  the old direct `phase-a --plan-name recovery_live_probe_2026-04-03` shortcut
  is no longer a valid end-to-end proof path under the current bridge review
  contract, and that the next proof must use the real routed post-merge /
  commit path instead

### Executor Fallback Config Truth Sync

- `executor_common.py` fallback executor config now matches the checked-in
  operational `executor_config.json` for Phase B backend/reviewer selection and
  for the long-running Phase A / Phase B / commit timeouts
- this closes the drift where a missing or partial executor config could fall
  back to older short timeout budgets and older Phase B defaults, making the
  routed control-plane behave differently from the repo's live configuration
- `mu/tests/tools/test_executor_dispatch.py` now locks the default-load config
  values directly so fallback config truth cannot silently regress

### Findings Pane Fallback

- `_pane_findings.sh` now renders a plain-English fallback state when there is
  no active Phase A / Phase B bridge round, instead of looping back to a blank
  shell prompt
- that fallback now surfaces the latest meta-review decision and the latest
  commit-path state, so the pane stays useful during supervisor/commit-only
  waves
- `RCX_PANE_ONESHOT=1` now renders the pane once and exits, which gives the
  observability suite a stable non-interactive proof surface
- `mu/tests/tools/test_recovery_gate.py` now locks both the no-bridge fallback
  and the meta-review rendering path directly

### Tracker-Only Handoff Compatibility

- `prepare_handoff_from_routing_record()` now builds a contract-complete
  tracker note for routed `UPDATE_TRACKER_ONLY` handoffs when upstream omitted
  `tracker_note_text`, instead of falling back to the older one-line note that
  `validate_handoff()` now rejects
- `mu/tests/tools/test_executor_dispatch.py` and
  `mu/tests/tools/test_commit_executor_receipt.py` now lock that tracker-only
  fallback path directly by proving the synthesized handoff validates cleanly
  without a pre-populated tracker note

## 2026-04-03

### Meta-Bridge Task-ID Path Safety

- `meta_bridge_supervisor.py` now sanitizes slash-bearing `task_id` values
  before embedding them in pre-commit and post-merge reviewer `job_id` /
  `turn_id` filenames, so exact tracker task IDs like
  `[PIPELINE-RECOVERY/pipeline-monitor-worktree-rebind-2026-04-03]` no longer
  crash prompt/raw-output path creation
- `mu/tests/tools/test_meta_bridge_supervisor.py` now locks slash-bearing task
  IDs for the filename token helper and for both the pre-commit and post-merge
  reviewer launch paths, so the supervisor cannot regress back to raw
  slash-bearing filenames silently

### Hook Audit Env Sanitization

- `mu/tools/hooks/pre-push-fast`, `dev.sh`, `mu/tools/audits/audit_fast.sh`,
  and `mu/tools/audits/audit_all.sh` now clear Git hook-local `GIT_*`
  variables before
  spawning deeper audits, so nested git-aware tests rediscover the worktree
  normally instead of inheriting hook-only state
- `mu/tests/structural/test_subtree_root_guard.py` now locks that hook-env
  sanitization contract without duplicating the new structural checks
- a simulated hook-env proof shows representative untracked-artifact,
  meta-bridge, and ensure_feature_branch tests return to green once the
  inherited hook-local vars are cleared

### Pipeline Monitor Linked-Worktree Rebind

- `pipeline_monitor.sh` now resolves a real linked worktree when launched from
  the bare/common repo path, and the tmux pane commands explicitly `cd` into
  that resolved worktree before starting the watcher, findings, timeline, and
  process panes
- `pipeline_status.sh` now uses the same linked-worktree resolver, so the
  one-shot pipeline summary works from the bare/common repo path instead of
  failing on an empty `git rev-parse --show-toplevel`
- both entrypoints now ignore stale non-final executor state after a bounded
  age window, so ancient root-worktree `post_commit_pending` artifacts stop
  masking the real live pipeline in another linked worktree
- both observability entrypoints now implement the same resolver rules:
  prefer the exact current-branch worktree, then a uniquely active pipeline
  worktree, then a sole linked worktree, then the unique linked `dev`
  worktree, and only then fail closed
- `pipeline_dashboard.py --render-recovery` now shows recent matching recovery
  attempts from `.agent_bus/recovery/recovery_log.json`, giving the tmux
  recovery block loop/outcome detail instead of only a static status snapshot
- `mu/tests/tools/test_recovery_gate.py` now locks the exact linked-worktree
  success path, the stale-branch active-worktree fallback, the sole-linked
  fallback, the unique-`dev` fallback, the quiet-current-root stale-state
  override, and recent-attempt recovery rendering without increasing test-file
  count
- this closes the concrete stale-pane failure mode where tmux started from the
  bare/common path launched `/mu/tools/observability/...` commands or kept
  showing ancient root-worktree state instead of the live recovery-aware pane

### Routed Commit Recovery And Bridge Watchdog Hardening

- `executor_dispatch.py` now routes the modular `commit` surface through the
  same recovery wrapper used by `phase-a` / `phase-b`, derives commit-wave
  identity from the handoff or routing record, and treats structured commit
  `status:error` output as a real failed commit surface instead of a silent
  success
- `bridge_adapters.py` now starts the zero-output watchdog after prompt
  delivery and writes stderr to the raw transcript incrementally with the
  normal `[stderr]` sentinel, so noisy reviewers no longer fail closed with an
  empty raw transcript just because CI process startup consumed the original
  timer budget
- `mu/tests/tools/test_agent_bridge_supervisor.py` now gives the zero-output
  bridge watchdog proof a realistic CI margin and locks the stderr-only raw
  transcript prefix directly
- `mu/tests/tools/test_executor_dispatch.py` now locks commit-surface recovery,
  commit-surface recovery-wrapper routing from `main()`, and structured
  commit-status error classification directly

### Recovery Observability And Watcher-Noise Hardening

- `recovery_gate.py` now writes a structured
  `.agent_bus/recovery/recovery_status.json` file with the current recovery
  tier, failure class, retry target, wave invocation count, tuple attempt
  index, owner PID, live child PID/role, current state, and terminal outcome
- `recovery_gate.py` on current `dev` now also restores live Tier 3 wiring in
  `attempt_recovery()`, so routed dispatcher failures actually enter the
  recovery loop instead of returning `not_implemented`
- `pipeline_dashboard.py` now renders that status into plain-English recovery
  lines for tmux and other text dashboards, and `_pane_processes.sh` now shows
  the recovery section directly by calling the existing dashboard surface
- `_pane_processes.sh`, `pipeline_dashboard.py`,
  `pipeline_dashboard_web.py`, and `pipeline_status.sh` now ignore `tail -f`
  log watchers and other observability helper processes when detecting the
  active pipeline phase, so stale panes no longer report fake live executors
- `pipeline_dashboard_web.py` and `pipeline_status.sh` now surface the same
  live recovery facts directly, including tier, target, loop counter, live
  PIDs, plain-English reason, and terminal outcome
- recovery reason extraction now pulls the embedded executor error from routed
  Phase A JSON output, so the pane shows the actual bridge failure string
  instead of a useless trailing `}` line
- `commit_executor.py` now generates contract-complete tracker notes for ad hoc
  routed commit handoffs by default and rejects incomplete tracker notes during
  input validation, so the commit surface fails early instead of getting all
  the way to pre-push before the L4 tracker-note contract trips
- `commit_executor.py` now gives `pre-push-fast` a longer Step 11 timeout, so
  the real fast-audit path can finish instead of being misreported as a failed
  push gate when the audit is still making forward progress
- `mu/tests/tools/test_executor_dispatch.py` and
  `mu/tests/tools/test_commit_executor_receipt.py` now lock both the stronger
  handoff-note validation and the default note-generation path directly
- `mu/tests/tools/test_executor_dispatch.py` now also locks the extended
  `pre-push-fast` timeout contract directly
- `mu/tests/tools/test_recovery_gate.py` now locks both the recovery-status
  rendering contract and the watcher-noise regression directly, without adding
  new test files

## 2026-03-27

### Pipeline Test Run Review-Cycle Floor, Cleanup Wait, And Post-Commit Follow-Ups

- `commit_executor.py` Step 15 now uses the fresher of the latest
  `@codex review` request and the latest current-head connector review as the
  review-cycle floor, and current-head connector issue-comment clearance uses
  that same floor so older request-era comments or unresolved bot threads
  cannot leak back in after a newer current-head review
- `bridge_adapters.py` stale-timeout cleanup now waits for tracked PIDs to
  disappear, not merely to stop being non-zombie, so zombie descendants are not
  treated as fully cleaned up until they are actually reaped
- `mu/tests/tools/test_executor_dispatch.py` and
  `mu/tests/tools/test_agent_bridge_supervisor.py` now lock the current-head
  review-floor regression and the zombie-presence cleanup regression directly
- `mu/tests/tools/test_executor_dispatch.py` now also marks the direct
  Step 15 issue-comment freshness helper regression with `# ANTICHEAT_OK`, so
  the intentional private-helper proof survives the post-commit anti-cheat scan
- `bridge_adapters.py` stale-timeout cleanup now kills tracked descendants
  before the root process, reaps the root process when possible, and waits only
  on live non-zombie descendants during stale-timeout cleanup
- `mu/tests/tools/test_agent_bridge_supervisor.py` now locks the root-reap and
  live-non-zombie wait semantics for stale-timeout cleanup
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Thirty-Third live stop honestly: head `5989b55` passed CI,
  received a fresh current-head connector review, and then surfaced these two
  remaining control-plane defects
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  also record the Thirty-Fourth live stop honestly: after automated local
  commit `cfe94c6`, the next rerun stopped at Step 10 `pre-push-fast` only
  because the new direct helper regression lacked the required anti-cheat
  annotation
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  also record the Thirty-Fifth live stop honestly: after the anti-cheat
  follow-up landed as `cc67c9a`, the next current-head review narrowed the
  remaining blocker to stale-timeout cleanup waiting on zombie PID presence

### Pipeline Test Run Review-Cycle Truth, Zombie Cleanup, And Canonical Receipt-Proof Paths

- `commit_executor.py` now scopes unresolved bot-thread findings to the active
  review cycle by requesting thread-comment timestamps, falling back to the
  current-head connector review timestamp when needed, and ignoring stale prior
  review-cycle bot threads that remained non-outdated on unchanged lines
- `bridge_adapters.py` stale-timeout cleanup now treats zombie descendants as
  exited instead of using `os.kill(pid, 0)` alone as the liveness probe
- `meta_bridge_supervisor.py`, `bridge_supervisor.py`, and
  `shared_agent_utils.py` now bind the receipt-authority proof contract to the
  canonical live chain in `mu/tools/agents/meta_bridge_supervisor.py`,
  `mu/tools/agents/meta_bridge_client.py`,
  `mu/tools/executors/phase_b_executor.py`, and
  `mu/tools/executors/commit_executor.py`, and explicitly reject legacy
  aliases such as `mu/tools/executors/meta_bridge_client.py` and
  `mu/tools/hooks/pre_commit_receipt.py`
- `mu/tests/tools/test_executor_dispatch.py`,
  `mu/tests/tools/test_agent_bridge_supervisor.py`,
  `mu/tests/tools/test_meta_bridge_supervisor.py`, and
  `mu/tests/tools/test_control_surface_review.py` now lock the active
  review-cycle, zombie-aware cleanup, and canonical proof-path expectations
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Thirty-Second live stop honestly: the fresh per-invocation receipt
  was present, but the next automated commit still failed closed because the
  commit-local supervisor's focused proof script used dead legacy receipt-path
  aliases

### Pipeline Test Run Terminal Decision And Review-Binding Hardening

- `phase_a_executor.py` now recognizes terminal `Decision: STALE|ERROR|SYNTHETIC`
  bridge outputs, prefers the last non-synthetic rendered decision, and fails
  closed when the final reviewer turn ends in one of those terminal outcomes
- `commit_executor.py` now reuses a clear connector issue comment only when the
  continuation record already proves that review request was made for the
  current head SHA, so an older clear comment cannot suppress a required
  current-head review
- `mu/tests/tools/test_executor_dispatch.py` now locks both regressions:
  terminal final bridge decisions fail closed, and stale clear issue comments
  without current-head request binding still trigger a fresh `@codex review`
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Thirtieth live stop honestly: head `0335fe6` passed required CI,
  received a fresh current-head connector review, and the remaining stop was
  these two fail-closed gaps

### Pipeline Test Run Final-Decision Parsing

- `phase_a_executor.py` now takes the last valid `Decision:` line from rendered
  bridge output, so multi-turn transcripts obey the final reviewer turn instead
  of the first reader turn
- `mu/tests/tools/test_executor_dispatch.py` now locks that regression with a
  rendered multi-turn decision fixture where `REQUEST_CHANGES` is followed by
  final `GO`
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Twenty-Ninth live stop honestly: head `a6fb234` passed required
  CI and received a fresh current-head connector review, and the remaining stop
  was the Phase A final-decision parser defect surfaced by that review

### Pipeline Test Run CI Timing Hardening

- `mu/tests/tools/test_executor_dispatch.py` now gives the Phase A
  bridge-turn-budget watchdog regression a wider timing margin, so it still
  proves that the configured bridge-turn budget overrides the smaller stale
  watchdog threshold without flaking on Linux CI process-startup overhead
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Twenty-Eighth live stop honestly: commit `cd33a25` cleared
  supervisor, local commit, pre-push, push, PR reuse, and CI registration, and
  then stopped only because the required `test` workflow exposed that timing
  race while `green-gate` still passed

### Pipeline Test Run Step 15 Review-Thread Truth

- `commit_executor.py` now restores `handoff_sha` before resuming the
  post-commit helper, so bounded continuation checkpointing still works after a
  restart instead of silently no-oping on resumed Steps 11-14
- `commit_executor.py` Step 12 push now uses `git push --no-verify` because the
  executor already ran `pre-push-fast` explicitly in Step 11 for the same head,
  eliminating the duplicate hook rerun during automated pushes
- `mu/tests/tools/test_executor_dispatch.py` now proves resumed post-commit
  state keeps its continuation binding, that non-connector bot reviews cannot
  satisfy current-head freshness, and that the resumed push path uses
  `--no-verify`
- `bridge_adapters.py` stale-timeout cleanup now waits for tracked descendants
  to disappear before returning, while `mu/tests/tools/test_agent_bridge_supervisor.py`
  keeps the separate fast stop-after-envelope contract green
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Twenty-Fourth live stop honestly: the code slice still closes the
  Step 15 review-thread follow-up on `664be57`, but the latest automated rerun
  failed earlier because the bounded supervisor packet did not expose the exact
  implementer-path and no-manual-fallback proof surfaces
- the active proof surface for the rerun now explicitly includes
  `mu/tools/executors/phase_b_implementer.py`, `CLAUDE.md`,
  `mu/tools/checks/check_control_surface_invariants.py`, and
  `mu/tools/agents/templates/meta_bridge_task.txt` so the commit-local
  supervisor can verify those obligations directly within budget
- `CLAUDE.md` now makes the Step 11/Step 12 executor exception explicit: after
  `pre-push-fast` passes on the same local HEAD, automated Step 12 may use
  `git push --no-verify` only to avoid rerunning the same hook
- `mu/tests/tools/test_agent_bridge_supervisor.py` now marks the direct
  `_kill_process_group()` regression with `# ANTICHEAT_OK`, so `pre-push-fast`
  treats that private-helper proof as an explicit allowed exception instead of a
  policy violation
- `commit_executor.py` now checks for an already-valid current-head no-issues
  connector issue comment before posting a fresh `@codex review`, and
  `mu/tests/tools/test_executor_dispatch.py` now proves Step 15 does not
  invalidate its own clear issue-comment outcome

### Pipeline Test Run Post-Commit Checkpointing

- `commit_executor.py` now checkpoints post-commit continuation after
  `run_pre_push_script`, `git_push`, `ensure_pr`, and `wait_ci`, and skips any
  of those steps that are already recorded in the bounded continuation state
- `mu/tests/tools/test_executor_dispatch.py` now covers the resumed
  post-commit boundary directly: if `run_pre_push_script` is already
  checkpointed, the helper must skip rerunning pre-push, attempt `git push`,
  and preserve that new progress even if a later PR step fails
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Twenty-Second live stop honestly: the boring-path run creates the
  new local commit `02fbc4b`, but repeated automated resumes wedge after
  Step 11 unless post-commit continuation becomes step-aware

### Pipeline Test Run Step 15 Commit-Bound Freshness

- `commit_executor.py` Step 15 PR review GraphQL now also requests
  `headRefOid`, asserts the PR head stays on the expected commit while waiting,
  and rejects connector issue-comment clearance if the head drifts
- `mu/tests/tools/test_executor_dispatch.py` now covers commit-bound
  issue-comment acceptance, fail-closed PR-head drift, and the post-commit
  current-head paths that depend on `headRefOid`
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Twenty-First live stop honestly: the boring-path run reaches a
  fresh current-head connector review on `02b41d2`, and the remaining stop is
  the commit-bound Step 15 freshness gap

### Pipeline Test Run Current-Head Review Hardening

- `commit_executor.py` now pins Step 15 freshness, no-issues issue-comment
  clearance, and request-acknowledgement detection to the real
  `chatgpt-codex-connector` identity instead of any generic bot account
- `commit_executor.py` PR review GraphQL now requests `reviewThreads.isOutdated`,
  and tracker-note repair is limited to the active `## Ra` section so archived
  tracker history cannot be rewritten during closeout
- `phase_a_executor.py` now honors the configured bridge-turn budget before its
  stale watchdog fails a live reviewer turn closed
- `bridge_adapters.py` now keys zero-output detection to explicit stdout
  progress instead of inferred raw-file shape, while still failing closed on
  stderr-only hangs
- `reports/control_plane/pipeline_test_run_2026-03-25.md` and `TASKS.md` now
  record the Twentieth live stop honestly: the pipeline now receives a fresh
  current-head connector review and the remaining stop is the review's concrete
  control-plane findings, not review latency

## 2026-03-26

### Pipeline Smoke Truth Sync

- `reports/control_plane/pipeline_test_run_2026-03-25.md` now records the first
  live post-merge routing stop and defines a canonical rollout order for the
  boring-path smoke
- `TASKS.md` now makes `[PIPELINE-TEST-RUN]` the immediate next bounded
  control-plane proof item and explicitly sequences `[COMMIT-EXECUTOR-E2E]`
  after it with refreshed blocker wording
- No runtime/substrate or host-semantics delta

### Pipeline Continuation Hardening

- `commit_executor.py` now persists a bounded post-commit continuation record keyed to the exact handoff, target branch, and local commit, so reruns after step-11+ failures continue honestly without a separate resume flag
- Final merge clearance now waits for a current-head `chatgpt-codex-connector` review before evaluating `reviewDecision` and unresolved review threads
- `commit_executor.py` now also fails closed when the Step 15 PR review GraphQL query times out, returning a structured `ensure_review_clear_and_merge` error instead of crashing the mechanical pipeline
- `meta_bridge_supervisor.py` now rejects stderr-only authoritative envelopes during recovery parsing
- `mu/tools/executors/executor_dispatch.py` now also acts as the thin modular entrypoint for `phase-a`, `phase-b`, `pre-commit-supervisor`, `commit`, and `post-merge-supervisor`
- `mu/tests/tools/test_executor_dispatch.py` now carries a behavioral regression that forces the timed-out review-query path through `_run_post_commit_pipeline()`
- Control-plane packets and TASKS tracker truth updated to reflect bounded continuation, the structured review-timeout follow-on, the modular operator surface, and the remaining simple-route pipeline smoke target
- **L4_ENABLER** wave targeting G8. No runtime/substrate or host-semantics delta.

## 2026-03-19

### Wave W6A: Stage0 VM Trusted Path Optimization

- **Two-function trusted path pattern:** `_stage0_vm_step_trusted` (dispatch body) + `stage0_vm_step` (validate + delegate) in Python; mirrored in JS with `_stage0VmStepTrusted` export
- **Parameterized bounded helper:** `_run_bounded_impl` eliminates loop duplication across match/subst/step dispatch
- **Source-lock gate tests:** 12 tests in `tests/l4_gates/test_stage0_vm_trusted_path_gate.py` — exhaustive grep for trusted function call sites
- **Bundle validation contract:** Callers constructing custom vmConfig MUST call `validateBundle()` before passing to `_stepKernelWithVM`
- Host-semantics delta: 0 (refactor-only, no new host capabilities)
- Total inventory: 309 -> 313 (+4: 2 Python trusted functions, 2 JS trusted path helpers)
- **L4_STRUCTURAL** wave targeting G8. PR #635 merged. Bridge: 2 rounds GO.

## 2026-03-15

### Wave 1: Internal Canonical Step Record

- Retired `_stepKernelCoreNonMeta` from JS kernel.js (deleted)
- `runAlgorithmWithBridge` migrated to `_stepKernelCore` — uses `canonical.output` (already denormalized), removed redundant `denormalize()` call
- `stepKernel(returnMeta=false)` now compatibility shim over `_stepKernelCore` — re-normalizes output for legacy `denormalize()` round-trip, preserves `stalled:false` on max-steps (NB4 public debt deferred)
- NB4/NB7 contained internally: canonical `_stepKernelCore` has correct stall semantics and terminal extraction. Public non-meta adapter preserves legacy behavior.
- Source-lock tests updated for new pipeline.js structure
- **L4_STRUCTURAL** wave. Founder canonical machine direction. Bridge: 1 round GO.

### JS Kernel Cleanup (NB10)

- `_assertVmMatchResult()` added to `_stepKernelWithVM` in kernel.js — fail-closed on undefined `.root` from VM match result (parity with Python KeyError). `null` accepted (valid Mu).
- NB4 (max-steps stall) and NB7 (terminal extraction) documented as DESIGN-GATED — attempted fixes broke 27 parity tests due to caller dependency on current non-meta semantics.
- Total inventory: 310 -> 311 (+1 JS assertion function).
- **L4_STRUCTURAL** wave. Bridge: 2 rounds.

### Agent Execution Capability

- Updated 5 agent prompts (adversary, verifier, expert, structural-proof, grounding) with "Execution Verification" sections
- Added `Bash` to `tools` in all prompt frontmatter
- Updated SDK orchestrator (`run_review.py`) + all individual runners + `agent_runner_common.py`: all agents now consistently have `Bash` tool (infrastructure already granted it; declarations now match reality). Execution behavior guided by prompt instructions, not tool restrictions
- Updated all individual runners and `agent_runner_common.py` defaults
- Regenerated all 9 native subagents via `sync_native_agents.sh`
- Added "Execution-Aware Review" section to `AgentRunbook.v0.md`
- **L4_ENABLER** wave. Agents can now run targeted repro commands during review.

### S1-C: Kernel + Bridge Execution via Stage0 VM

- **Compiled:** kernel.v1 (7 projections) and bootstrap_structural.v1 (5 projections) into Stage0 bundles
- **Wired:** `_step_kernel_with_vm()` now executes ALL 33 projections via Stage0 VM
- **Eliminated:** `_apply_projection_trusted` removed from step_kernel_mu path
- **JS parity:** kernel.js updated with same all-VM execution
- Total inventory: 308 -> 310 (+2 new bundle loaders)
- **L4_STRUCTURAL** wave targeting G8.

### S1-B: VM Cutover Flip (Founder GO)

- **Python:** `_STAGE0_VM_CUTOVER = True`, `_STAGE0_SHADOW_ENABLED = False` in step_mu.py
- **JavaScript:** `_STAGE0_VM_CUTOVER = true`, `_STAGE0_SHADOW_ENABLED = false` in kernel.js
- VM path is now primary for match.v2/subst.v2 in step_kernel_mu; host path (_step_trusted) still used by engine_pipeline and projection_runner
- Shadow mode disabled (dead code under cutover=True, retained for rollback)
- Updated: test_stage0_vm_cutover.py source-lock, test_l4_current_state_truth.py flag assertions, test_performance_canary_gate.py hash_stall monkeypatch, stage0_vm.js header
- P7-d deferred items #1-6 all RESOLVED
- **L4_STRUCTURAL** wave targeting G8. Founder GO 2026-03-15.

### N15: Compiler/Loader Provenance Verification

- `_verify_bundle_provenance()` in `step_mu.py`: verifies compiled bundle source_digest against SEED_CHECKSUMS registry at load time
- `verifyBundleProvenance()` in `main.js`: JS parity implementation
- 5 gate tests in `test_stage0_vm_cutover.py::TestBundleProvenance` (pass, reject wrong digest, missing, unknown)
- Theater allowlist: 4 new entries for no-raise provenance tests
- Total inventory: 306 → 308 (+2 provenance functions), INFRA_CEILING: 123 → 125
- N2/N15 deferred items marked RESOLVED
- **L4_STRUCTURAL** wave targeting G8. Python + JS parity. Fail-closed on mismatch.

### MT2: isinstance Marker-Truth

- 29 unmarked `isinstance` calls in `step_mu.py` annotated with `# AST_OK:infra — type guard`
- INFRA_CEILING/INFRA_CURRENT: 94 → 123 in STATUS.md
- `test_debt_enforcement.py` infra count assertion: 94 → 123
- D4 wave4b (step_mu.py isinstance) + D2 wave4c (projection_runner.py isinstance) marked RESOLVED
- **L4_STRUCTURAL** (annotation-only, FOUNDER_OVERRIDE). No behavioral changes. No phase/debt change.

### S1-A VM Cutover Evidence Package

- **D1:** Performance profiling suite (`test_stage0_vm_performance.py`) — 9 Tier 1 diagnostic + 5 Tier 2 integration workloads (including cutover-mode benchmarks)
- **D2:** Cutover=True path tests (`test_stage0_vm_cutover.py`) — 15 new tests: 10 branch-level (TestCutoverTruePath) + 5 integration-level (TestCutoverIntegration) with no-monolithic-host-path negative control
- **D3:** JS VM bridge parity (`test_js_vm_bridge_parity.py`) — 8 cross-substrate tests (match.v2 + subst.v2 compiled bundle parity)
- **D4:** CONDITIONAL GO memo (`reports/l4_wave_indicators/s1a-vm-evidence-go-nogo.md`) — founder-grade evidence for cutover decision
- Theater allowlist: 5 new entries for observational performance tests
- **L4_ENABLER** wave targeting G8 (Irreducible Primitive Consensus). No runtime changes. No phase/debt change.

## 2026-03-05

### Docs Truth Sync (PR #480)

- README.md: test counts (~5,500+ across 260+), CRITICAL_TEST_FILES (44), projections (143 across 17 seeds), seed table (+5 missing seeds), metabolization status → COMPLETE
- STATUS.md: Python test count (~5,556), Tier 2/3 counts corrected, green gate selection semantics documented, tests/structural (45) and tests/tools (27) counts, CRITICAL_TEST_FILES (44)
- L4ExitChecklist.v0.md: G1 pass condition scoped to Python canonical substrate, G1 proof command fixed, muHash JS label discrepancy documented
- Boot1LoopContract.v0.md: status → COMPLETE (shadow-merge implemented 2026-02-19)
- HemisphereExecutionChecklist.v0.md: KERNEL_RESERVED_FIELDS 24→25 (_boundary_request)
- MAINTENANCE wave. No phase/debt change. Merge commit `3d19180`.

### W3-CRASH Runtime Crash Guards + Collector Hardening (PR #477)

- F-10: `denormalize_from_match` typed-dict and legacy-dict loops now have 3-layer guards (structural, kv shape, kv_tail shape); malformed kv nodes skipped instead of crashing (JS parity)
- F-11: `_match_inner` and `_stage0_match` return NO_MATCH for empty var-name `{"var": ""}` instead of raising ValueError
- F-12: `bindings_to_dict` rejects non-string binding names with diagnostic ValueError (type + repr)
- F-13: `_iter_normalized_dict_pairs` cap raised from hardcoded 100 to `MAX_MU_WIDTH` (1000); JS `iterNormalizedDictPairs` updated to match
- Enforcer: `net_host_semantic_delta` aligned to ratchet-derived delta (runs `check_host_semantics_ratchet.py --json`)
- Collector hardening (#1-6): zero-division guard on speedup ratio, `subprocess.TimeoutExpired` fail-closed on 3 probe functions, `get_changed_files` raises `CollectorError` on git failure, dead code removed (`RUNTIME_DIRS`, `COMMENT_ONLY_PATTERNS`, `get_diff_text`, `is_comment_line`), top-level `import os` replaces inline `__import__("os")`, docstring corrected (timing metrics are environment-dependent, not deterministic)
- 25 gate tests in `test_w3_crash_guards_gate.py` + 6 collector regression tests in `test_l4_governance_contract.py`
- Merge commit `735dfea`. No phase/debt change.

## 2026-03-04

### W2 Enforcer/Theater Hardening (PRs #472, #473)

- PR #472: `is_comment_only_runtime_diff` now accepts `old_ref` parameter (was hardcoded `HEAD`, broke range-based enforcement)
- PR #472: founder override bypass requires explicit wave binding (`override_wave_bound=True`); unbound stale overrides fail-closed
- PR #472: `L4ExecutionContract.v2.md` updated with condition 6 (wave-binding requirement)
- PR #472: `check_test_theater_js.sh` default target changed from single file to `mu/host/js/` directory scan with THEATER_OK suppression
- PR #473: boundary gate malformed-seed tests relocated temp files from `mu/utilities/` to `os.tmpdir()` (eliminates parallel race with `test_seed_counts.py`)
- PR #473: `_derive_old_ref_from_range` normalizes empty endpoints to HEAD (`rev...` → `rev...HEAD`, `..rev` → `HEAD..rev`)
- PR #473: 3 regression tests for empty-endpoint normalization

## 2026-03-03

### W1-GATE: Gate Blindness Remediation (PR #468)

- Green gate now includes parity canary (`test_parity_canary`) for cross-substrate coverage
- JS linters (`contraband_js.sh`, `ast_police_js.sh`) scan full `mu/host/js/` directory by default
- `pytest.fail` replaces `pytest.skip` for missing parity vectors (fail-closed)
- `new Date()` removed from `pipeline.js` (determinism fix)
- Governance fix: root canonical files counted as governed (coverage 28%→31%)
- `FOUNDER_SESSION_BOOTSTRAP.md` tracked and registered

### W2 Docs Truth Alignment (unbound patch)

- NorthStarSemantics.v0.md §B.1: corrected non-linear binding hash from `mu_hash_control_cached` to `mu_hash_cached` (Wave 25 revert was undocumented)
- STATUS.md: JS debt count corrected 19→16 (dashboard grep-token inflation documented)
- STATUS.md: AST_OK:infra references corrected 42→65, ceiling 64→65
- STATUS.md: all LOC/test counts updated (Py ~6250 LOC / ~5458 tests, JS ~4200 core + ~470 tests)
- NorthStarSemantics.v0.md: removed hardcoded "37 tests" gate count (actual is 43; now non-numeric)
- 5 runtime-file findings (F-06, F-31, F-32, F-33, F-34) deferred as POLICY_BOUND (require L4_STRUCTURAL wave)

## 2026-02-17

### Denormalization KeyError Hardening (PR #315)

- Fixed legacy linked-list denormalization paths in `match_mu.py` that used `current["tail"]` (crashes with KeyError on malformed inner nodes missing "tail" key)
- Changed to `.get("tail")` matching the type-tagged paths and JS behavior (2 lines, lines 699 and 726)
- Added 2 regression tests in `test_normalization_roundtrip.py`
- Red-team finding; classify_mu already protects the dict path, but the list path was directly exploitable

### Canonical Docs Drift Sync

- STATUS.md: INFRA_CURRENT 45→42 (reduced by PR #314 archival work)
- STATUS.md: Infra ceiling line corrected (was "38 (current 38)", now "48 (current 42)")
- STATUS.md + README.md: Test count 3,235→3,690
- README.md: Test files 90+→180+
- CHANGELOG.md: Added missing PR #315 entry

## 2026-02-16

### Roadmap Relocation (Visibility + Governance Sync)

- Moved `ROADMAP.md` from `roadmap/ROADMAP.md` to repo root `ROADMAP.md`
- Moved roadmap spec folder from `roadmap/` to root `roadmap/`
- Updated roadmap links across canonical docs (`STATUS.md`, `TASKS.md`, `README.md`) and active specs/tests
- Updated doc governance config:
  - `ROADMAP.md` added to root canonical docs
  - roadmap special-folder path changed to `roadmap/`
  - `docs_registered_subfolders` no longer lists `roadmap`
- Updated pre-commit docs-change detection to include `roadmap/` and `ROADMAP.md`
- Fixed stale archived bytecode doc path references (`archive/archive/docs/bytecode` → `archive/docs/bytecode`)

## 2026-02-15

### Round 24D: Convergence Execution (tools/scripts/tests -> mu/)

- **Physical move**: `tools/`, `scripts/`, `tests/` moved under `mu/` via `git mv` (~340 files)
- **Root symlinks**: `tools -> mu/tools`, `scripts -> mu/scripts`, `tests -> mu/tests` for backward compat (removal planned for 24E)
- **Shell scripts**: 8 scripts converted from `dirname`-based repo root to `git rev-parse --show-toplevel`
- **Python paths**: `.resolve()` removed from 25 REPO_ROOT computations (prevents symlink resolution from breaking parent chains)
- **Git-path configs updated**: `enforce_tracker_sync.sh`, `pre-commit-doc-check`, `docs_registry.json`, `run_review.py`, `run_ci_review.py` — all now use `mu/` prefix for git-reported paths
- **Root layout guard**: Made index-aware (reads staging area, not just HEAD); `tests`/`tools`/`scripts` removed from ALLOWED_ROOT_DIRS
- **Symlink `..` traversal**: Fixed `os.path.join` + `..` patterns that break with symlinks (normalize before use)
- **Tracker sync exclusions**: `mu/tools/`, `mu/scripts/`, `mu/tests/` excluded from core-change detection
- No phase/debt/runtime change

## 2026-02-14

### Documentation Drift Sync (Governance + Schemas)

- Synced Boot1 prerequisite status in governance docs:
  - `_run_engine` reservation (P2) marked resolved (Round 20B)
  - `_tail_call` reservation (P3) marked resolved (Round 20C)
- Updated schema-doc path references to canonical `mu/docs/schemas/*` locations:
  - CLI schema contract examples
  - CLI quickstart schema links
  - world_trace schema markdown/json `schema_doc` alignment
- Corrected stale `rcx_engine.v1.json` projection count in root README (7 → 11)
- Updated STATUS proof block to use `seed_police` authoritative totals (15 seeds, 102 projection IDs, 0 collisions)
- Regenerated `mu/docs/README.md` index to remove stale listing drift

## 2026-02-12

### JS Engine-Hemisphere Parity (L3 Mandatory)

- **4 core functions ported to JS** — `runEnginePipeline()`, `hashTraceForRecurrence()`, `runHemisphereRouting()`, `runEngineWithRouting()` mirror Python implementations in `eval_step.js`
- **rcx_engine.v1.json + recurrence.v2.json loaded in JS** — 9 seeds now verified at startup (was 8); `seedProjectionMap` for boundary `run_algorithm` operations
- **4 JSON API actions added** — `run_engine_pipeline`, `hash_trace`, `run_hemisphere_routing`, `run_engine_with_routing` for cross-substrate testing
- **6 cross-substrate parity tests** — 3 fast (hash_trace, overcap, routing validation) + 3 slow (engine pipeline, hemisphere routing, full pipeline E2E); 36 total parity tests pass
- **Pre-existing parity gap fixed** — `_state_hash` and `_check_hash` added to JS `ALGORITHM_RUNTIME_ALLOWED_UNDERSCORE_FIELDS` (recurrence.v2 fields present in Python but missing from JS)
- **JS debt 13→15** — `runAlgorithmWithBridge` + `runEnginePipeline` added to `@host_iteration` tracking
- **Constants and helpers** — `isTerminalShape()`, `isEngineTerminal()`, `runSubAlgorithm()`, `setsEqual()`, `defaultHemispheres()`, hemisphere/terminal key sets
- **Inline JS tests** — `isEngineTerminal`, `isTerminalShape`, `hashTraceForRecurrence` (simple, cycle, overcap), `defaultHemispheres`/`setsEqual`

## 2026-02-11

### Engine → Hemisphere Integration

- **`run_engine_with_routing()`** — Chains `run_engine_pipeline()` → `run_hemisphere_routing()` with fail-closed input/output validation
- **`hash_trace_for_recurrence` cycle guard** — `id(current)` visited set + 10000 iteration cap, `raise ValueError` (fail-closed)
- **`_default_hemispheres()`** — Canonical empty hemisphere state, single source of truth
- **10 integration tests** — 8 fast (wiring, input/output validation, cycle guard, default consistency) + 2 slow (manual chain equivalence, Paxos closure → r_a E2E proof)
- **Paxos livelock → closure → r_a** proven end-to-end through the full engine + hemisphere pipeline

### CI Green Gate Optimization (28 min → 2 min)

- **Hypothesis fuzzers auto-marked** — `pytest_collection_modifyitems` in `conftest.py` detects `item.obj.is_hypothesis_test` and applies `fuzzer` marker (452 tests deselected from green gate)
- **Slow tests excluded from green gate** — 168 meta-circular, hemisphere, paxos e2e, and engine pipeline tests marked `@pytest.mark.slow`
- **Green gate runs ~2,500 core tests in ~50s on CI** — Total wall time ~2 min (down from ~28 min)
- **4-tier test structure:** audit_fast (local), audit_all (pre-push), CI green gate (push/PR), CI nightly (ci_full)
- **Nightly branch** — `HYPOTHESIS_PROFILE=ci_full` runs everything including fuzzers and slow tests
- **pytest-timeout added to test extras** — `pyproject.toml` now declares `pytest-timeout` for `--timeout=300` in nightly/audit_all
- **Fragile grounding test fixed** — `test_green_gate_check_order` used `}` boundary detection that broke on `${VAR:-}` parameter expansions

### Static Speed Enforcer

- **Created `tools/check_test_speed.sh`** — grep-based static analysis catches test files importing slow kernel functions without `@pytest.mark.slow`
- **Pre-commit integration** — `tools/pre-commit-doc-check` section 4b enforces speed marking on staged test files (~instant)
- **7 unmarked test files fixed** — `test_structural_trace`, `test_self_hosting_v0`, `test_gate4_runtime_hardening`, `test_bootstrap_primitives`, `test_recurrence_parity`, `test_execution_path_verification`, `test_match_bridge_invariants`
- **Slow function set** — `run_mu`, `run_mu_structural`, `run_algorithm_meta_circular`, `run_engine_pipeline`, `run_hemisphere_routing`
- **Whitelist** — `# SPEED_OK: reason` for files that import but don't call slow functions

## 2026-02-10

### Content-Addressed Mu Level 1 IMPLEMENTED: mu_equal Eliminated (5→4 Bootstrap Primitives)

- **`mu_hash_cached()` added to `mu_type.py`** — SHA-256 with canonical-JSON-keyed cache for O(1) amortized equality
- **`mu_equal` eliminated as bootstrap primitive** — All 8 production call sites replaced with `mu_hash_cached()`:
  - `eval_seed.py`: 2 binding conflict detection sites
  - `step_mu.py`: 5 stall detection sites
  - `projection_runner.py`: 1 stall detection site
- **JS parity: `muHashCached()` added to `eval_step.js`** — Map-based cache, 6 JS call sites updated, `muEqual()` delegates to hash comparison
- **`mu_equal` retained as convenience wrapper** — Delegates to `mu_hash_cached(a) == mu_hash_cached(b)`. Marked DEMOTED PRIMITIVE (kept for ~30 test call sites + JS parity).
- **Bootstrap primitive count: 5 → 4** — eval_step, max_steps, stack_guard, projection_loader
- **Paxos end-to-end pipeline test created** — `tests/test_paxos_end_to_end.py` (6 tests): paxos livelock → trace → hash → recurrence.v2 → healer → consensus
- **Design docs updated**: BootstrapPrimitives.v0.md, ContentAddressedMu.md (Level 1 IMPLEMENTED), STATUS.md
- All 1991+ tests pass, JS tests pass, L3 parity intact

### Content-Addressed Mu Design + Recurrence v2 Hash Acceleration

- **Created `roadmap/ContentAddressedMu.md`** — Design doc for Content-Addressed Mu values (hash-identity as substrate property)
- **Key insight: mu_equal elimination (5→4 bootstrap primitives)** — With content-addressing, `mu_equal` is subsumed by non-linear pattern matching on hash strings. `mu_hash` moves from runtime infrastructure to boundary scaffolding (like JSON parsing)
- **Created `mu/closures/recurrence.v2.json`** — 9 hash-accelerated projections for closure detection
  - Pre-computes SHA-256 hashes at boundary; compares 64-char hash strings (O(1)) instead of deep structural match (O(depth))
  - Reduces Paxos 15-step trace from ~6,300 kernel steps to ~420 (theoretical estimate)
- **Created `mu/docs/core/recurrence_v2_design.md`** — Design spec for hash-accelerated closure detection
- **Converted `hash_trace_for_recurrence()` to iterative** — Avoids Python recursion limit on long traces (max_steps=10,000 > Python limit ~1,000)
- **Updated `mu/programs/paxos_demo.v1.json`** — Dependency changed from recurrence.v1 to recurrence.v2
- **Added Content-Addressed Mu to TASKS.md VECTOR** — Promotion criteria: Level 1 promotes to NEXT when recurrence.v2 production tests validate Level 0
- **INFRA_CURRENT: 37→38** — New AST_OK:infra marker for iterative hash_trace_for_recurrence
- Agent review: 3 iterative cycles (8, 12, 16 turns). Final: verifier APPROVE, structural-proof PROVEN

### Seed Integrity Verification Parity + Adversarial Hardening

- **JS substrate now verifies all 7 seeds at load time** — SHA256 checksum, structure validation, projection ID ordering
- Closes L3 parity gap where Python verified seeds but JS loaded blindly
- Python `validate_projection_ids` now enforces exact ordered equality (security-critical for first-match-wins routing)
- JS `classifyLegacyLinkedList` cycle detection activated
- Handler duplication factored in JS substrate
- Deprecated `get_seeds_dir` removed from Python
- 63 hemisphere adversarial tests added

## 2026-02-09

### Mu Hemispheres v0: Native Structural Routing

- **Created `mu/programs/hemispheres.v1.json`** — 8 projections for hemisphere routing (North Star #7)
- Routing state machine: init → classify → add → unwrap (4 kernel steps per decision)
- Three automatic routes: null→r_null, closure→r_a, default→lobes
- Entry schema: `{state: <value>, closure_flag: <bool>, origin: "engine"}`
- Linear-only patterns — runs through core kernel, no bridge needed
- All intermediate state uses `hemi_*` prefix (no underscore fields, passes domain validation)
- **Cross-substrate parity verified**: Python and JS produce identical results
- 27 Python tests in `tests/test_hemisphere_routing.py`
- 7 parity tests in `tests/structural/test_hemisphere_parity.py`
- 6 parity vectors in `tests/fixtures/hemisphere_vectors.json`
- JS JSON API: `run_hemisphere` action in `mu/host/js/eval_step.js`
- Seed registered in `seed_integrity.py` (checksum, projection IDs, location)
- **Answers semantic question**: Yes, routing decisions CAN be expressed purely as Mu projections

### Gate 5 CLOSED: Meta-Circular Parity Verified

- **Gates 1-5 ALL COMPLETE** — hemisphere implementation unblocked
- 56 exit criteria tests pass: 9 gate5 parity + 17 execution path + 30 JS parity
- Structural execution is default; bootstrap is explicit fallback only
- Cross-substrate parity intact (Python + JS, all 47 core projections)
- Updated consistency tests to handle all-gates-complete state

### B-Structural Non-Linear Match

- `match_mu()` now uses match.v2 + bridge projections directly via `projection_runner`
- Non-linear pattern conflict detection: `apply_mu({a:{var:x}, b:{var:x}}, {a:1, b:2})` → NO_MATCH
- `projection_runner.make_projection_runner()` extended with `terminal_field` parameter
- `load_match_with_bridge_projections()` loads and caches 13 combined projections (8 match.v2 + 5 bridge)
- Fail-closed guard: `step_mu()`/`run_mu()` reject non-linear patterns with ValueError
- 18 structural invariant tests + non-linear Hypothesis strategies

### 9-Agent Rigorous Tooling Hardening (PR #219)

- `--rigorous` now overrides depth to "all" (runs all 9 agents, was only running 6)
- Reasoning validation + skeptic always run, even on compliance failures
- `validate_agent_reasoning.py` regex fixed for `### CHECKED` markdown format
- 5 fuzzer test files from agent findings #1017-#1021 (88 property-based tests)
- Shared Hypothesis strategies extracted to `tests/strategies.py`
- Iteration guards in `match_mu.py` (bindings_to_dict, denormalize_from_match)

### Gate 5 Compliance/Severity Split (PR #221)

- JS Gate 5 parity: `runStructural()` routes through `stepKernel(allProjectionsWithBridge)`
- Prototype pollution hardened in JS substrate
- Compliance severity split for agent validation tooling

## 2026-02-08

### Gate 5 Runtime Parity Fix (PR #221)

- `run_mu_structural()` now executes through `step_kernel_mu(..., kernel_mode="bridge")`
- JS parity fix: `runStructural()` routes through `stepKernel(allProjectionsWithBridge)`

## 2026-02-07

### Gate 4: Structural Runtime Cutover + Doc/Parity Sync

- `run_algorithm_meta_circular()` now defaults to structural execution (`step_kernel_mu(..., kernel_mode="bridge", validation_mode="algorithm_runtime")`)
- Bootstrap algorithm execution remains explicit fallback only (`execution_mode="bootstrap"`)
- Promoted recurrence/exhaustion seed metadata to `execution_layer: META_CIRCULAR`
- Updated seed integrity checksums for `recurrence.v1.json` and `exhaustion.v1.json`
- Fixed JS bridge JSON API runtime loop to unwrap kernel result correctly and preserve Python/JS parity
- Synced canonical tracker docs and roadmap timeline to Gate 4 COMPLETE / Gate 5 IN_PROGRESS
- Hardened docs consistency test to use canonical layer lines and tolerate markdown-format marker variants

## 2026-02-06

### Tooling: Canonical Pre-Commit Gate Consolidated

- Removed legacy script: `tools/pre-commit-check.sh`
- Standardized on `tools/pre-commit-doc-check` as the single pre-commit gate
- Added targeted staged-file checks to `tools/pre-commit-doc-check`:
  - `py_compile` for staged Python files
  - bare `except:` detection in staged `rcx_pi/*` files
  - `ast_police.py` on staged `rcx_pi/*` files
  - `seed_police.sh` when staged `mu/*.json` files are present
- Updated docs and grounding tests to reference only the canonical hook path

## 2026-02-03

### rcx_engine.v1.json Test Coverage: 6 Projections Now Tested

**Addressed grounding agent finding:** rcx_engine.v1.json had 6 untested projections.

**Created:**
- `tests/fixtures/rcx_engine_vectors.json` - 7 test vectors covering all engine phases
- `tests/test_rcx_engine_parity.py` - 15 tests verifying engine projection behavior

**Tests cover:**
- `engine.init` - Initialize with default config
- `engine.init_config` - Initialize with custom config
- `engine.trace_done` - Trace complete triggers recurrence
- `engine.recurrence_done` - Recurrence result triggers exhaustion
- `engine.exhaustion_done` - Exhaustion result produces final output
- `engine.unwrap` - Extract final engine result

**Note:** rcx_engine.v1.json has `status: "design_only"` - projections are tested but not yet integrated into production execution.

---

### Agent Validator: Now Verifies TRUTH, Not Just FORMAT

**Problem discovered:** The agent validator only checked FORMAT (FINDING/FILE/LINES/CODE blocks exist) but never verified if cited code actually appears at the claimed location. Agents could produce perfectly formatted fabrications.

**Fix applied:**
- `tools/validate_agent_compliance.py` now reads actual files and compares CODE
- New `--verify-code` flag checks if CODE matches FILE:LINE (anti-fabrication)
- New `--strict` flag enables all verifications (recommended for CI)
- Similarity matching with 80% threshold for formatting differences
- Clear "FABRICATION DETECTED" errors with details

**Agent prompts updated:**
- All 9 agents now warned: "Your citations will be MACHINE-VERIFIED"
- Agents must use Read tool and paste EXACTLY from output
- structural-proof agent must write tests to `tests/agent_verification/`
- grounding agent must write tests to `tests/structural/`

**Hook updated:**
- `.claude/hooks/validate-agent-compliance.sh` now runs with `--strict`
- Fabricated citations are blocked with clear error message

---

### Bootstrap-Structural Bridge: Wiring Verified

**Structural matching with bridge WORKS.** Execution path tests prove bridge projections fire:
- `bridge.var.check_existing` intercepts variable patterns
- `bridge.lookup.not_found` adds new bindings
- `bridge.lookup.found_same` handles non-linear match (same value)
- `bridge.lookup.found_different` detects binding conflicts

**Algorithm execution wiring clarified:**
- `run_algorithm_meta_circular()` uses Python match/substitute for practical execution
- Python match/substitute ALREADY handle non-linear patterns correctly
- The bridge PROVES this CAN be structural (capability demonstration)
- For TRUE meta-circular algorithm execution, algorithm projections would need to work with normalized format

**What's needed for TRUE meta-circular algorithm execution:**
1. Algorithm projections (recurrence.v1, exhaustion.v1) work with linked-list format internally
2. Structural match/subst normalizes everything to linked-list format
3. To wire algorithms through structural match/subst, either:
   - Rewrite algorithm projections to expect fully normalized state, OR
   - Create a normalization-free structural matcher for algorithm use

---

### Execution Path Verification: Tests Verify What Actually Runs (FIXED)

**Problem identified and FIXED:** Tests had verified BEHAVIOR but not EXECUTION PATH. All tests passed because Python's `eval_seed.match()` provides binding conflict detection, but we claimed bootstrap_structural projections were providing it. This was "test theater."

**Solution implemented:**
- Created `tests/test_execution_path_verification.py` with 9 tests
- Tests use tracing to prove WHICH projections fire
- Tests FAIL if bridge projections don't execute (even if behavior is correct)
- Fixed wiring: bridge projections now come BEFORE match.v2 in combined kernel

**Agent guardrails updated:**
- Added "Execution Path Verification" section to `mu/docs/agents/AgentGuardrails.v0.md`
- Agents must now verify execution path, not just behavior
- Claims like "runs through X" require tests that fail if X isn't used

**match.v3 cleanup:**
- Removed all references to match.v3.json (file was incorrectly created)
- We use match.v2.json + bootstrap_structural.v1.json directly
- Updated all tests, docs, and seed_integrity.py

---

### Cleanup: Removed Stale substrates/js/ Directory

**Removed:** `substrates/js/eval_step.js` (stale duplicate)

The canonical JS substrate location is now `mu/host/js/eval_step.js`. The old `substrates/js/eval_step.js` was left behind after the mu/ folder reorganization (2026-02-02) and was 478 bytes behind the canonical version. All tests and documentation already reference the correct path.

---

## 2026-02-02

### Step 7: Bootstrap-Structural Bridge IMPLEMENTED

**Core implementation complete.** Non-linear pattern support via binding conflict detection as structural projections.

**Files created:**
- `mu/bridge/bootstrap_structural.v1.json` - 5 bridge projections for binding lookup
- `tests/test_bootstrap_structural_bridge.py` - 31 tests covering all 22 design vectors

**Architecture note:** We use match.v2 + bootstrap_structural.v1 directly (loaded at runtime)
rather than a combined match.v3 file. This keeps the bridge modular.

**How it works:**
- When pattern has `{"var": "x"}`, bridge checks if `x` is already bound
- If not bound: add new binding (same as match.v2)
- If bound with same value: continue (non-linear pattern OK)
- If bound with different value: NO_MATCH (binding conflict detected)

**Test coverage:**
- Linear parity tests (5): verify bridge matches match.v2 for linear patterns
- Non-linear detection tests (8): verify binding conflict detection works
- Edge cases (4): null values, empty collections, type mismatches
- Security vectors (3): reserved field handling, ordering verification
- Cross-substrate parity (3): unicode, float, deep nesting

**Still pending (Gates 6-7):**
- Update recurrence.v1/exhaustion.v1 to declare META_CIRCULAR
- Port bridge to JavaScript for L3 parity

**Files updated:**
- `rcx_pi/selfhost/seed_integrity.py` - Added checksums for new seeds
- `tools/seed_police.sh` - Added bridge.* to allowed prefixes, v3 version handling
- `mu/docs/core/BootstrapStructuralBridge.v0.md` - Updated status to IMPLEMENTED

---

### Bootstrap-Structural Bridge: Promoted to NEXT (Step 7)

**Promoted from VECTOR** after 9-agent verification review confirmed all fixes applied correctly.

**Final verdicts (verification round):**
| Agent | Verdict |
|-------|---------|
| Verifier | APPROVE |
| Adversary | SECURE |
| Expert | MINIMAL |
| Structural-proof | STRUCTURALLY_SOUND |
| Grounding | ADEQUATELY_GROUNDED |
| Fuzzer | NEEDS_MORE (non-blocking) |
| Translator | MATCHES_INTENT |
| Visualizer | ARCHITECTURALLY_ALIGNED |
| Advisor | READY_FOR_PROMOTION |

**Files updated:**
- `TASKS.md` - Added Step 7 to NEXT section with full implementation plan
- `STATUS.md` - Updated next milestone to Step 7 implementation

**Implementation plan:** 7 gates defined by Advisor agent, ~12 projections total.
See `TASKS.md` Step 7 for details.

---

### Bootstrap-Structural Bridge: 9-Agent Review Complete

**Review completed** for `mu/docs/core/BootstrapStructuralBridge.v0.md` with all 9 agents:
- Verifier: APPROVE (all 15 North Star invariants pass)
- Adversary: NEEDS HARDENING → FIXED
- Expert: MINIMAL
- Structural-proof: DESIGN SOUND
- Grounding: PARTIALLY_GROUNDED → FIXED
- Fuzzer: DESIGN COMPLETE
- Translator: MATCHES_INTENT
- Visualizer: 3 DIAGRAMS
- Advisor: PROMOTE TO NEXT

**Security hardening applied:**
- KERNEL_RESERVED_FIELDS updated from 20 to 24 fields (both Python and JS)
- Added: `_lookup_name`, `_lookup_value`, `_lookup_bindings`, `_original_bindings`
- Test vector table expanded from 6 to 22 vectors

**Files changed:**
- `rcx_pi/selfhost/step_mu.py` - Added 4 bridge reserved fields
- `mu/host/js/eval_step.js` - Added 4 bridge reserved fields (L3 parity)
- `substrates/js/eval_step.js` - Added 4 bridge reserved fields (L3 parity)
- `tests/test_security_boundary_fuzzer.py` - Updated reserved field count (20→24)
- `tests/test_kernel_security_fuzzer.py` - Updated reserved field count (20→24)
- `tests/test_js_parity_automated.py` - Updated reserved field count (20→24)
- `tests/structural/test_step_mu_kernel_integration.py` - Updated expected reserved fields set
- `mu/docs/core/BootstrapStructuralBridge.v0.md` - Expanded test vectors, updated checklist
- `TASKS.md` - Marked 9-agent review complete, design ready for NEXT

---

### mu/ Folder Reorganization

**Problem:** Seeds were all in flat `seeds/` folder. Architecture wasn't visible from file structure. Closure detection seeds (enginenews, exhaust) had confusing names.

**Solution:** Created `mu/` folder structure that makes architecture visible:
- `mu/substrate/` - The VM: kernel.v1, match.v1, match.v2, subst.v1, subst.v2
- `mu/closures/` - Closure detection: recurrence.v1 (renamed from enginenews), exhaustion.v1 (renamed from exhaust)
- `mu/programs/` - Applications: rcx_engine.v1 (new, orchestrates closures)
- `mu/utilities/` - Helpers: classify.v1, eval.v1
- `mu/host/js/` - JavaScript bootstrap: eval_step.js (moved from substrates/js/)
- `mu/host/python/` - Python bootstrap (symlink to rcx_pi/selfhost/)

**Files Changed:**
- All seeds copied to appropriate mu/ subfolders
- `mu/closures/recurrence.v1.json` - renamed from enginenews, projection IDs updated (recurrence.*)
- `mu/closures/exhaustion.v1.json` - renamed from exhaust, projection IDs updated (exhaustion.*)
- `mu/programs/rcx_engine.v1.json` - new main program (6 projections)
- `mu/host/js/eval_step.js` - updated to use mu/ paths, renamed to use recurrence/exhaustion
- `rcx_pi/selfhost/seed_integrity.py` - added new checksums and get_seed_path() helper
- `tests/fixtures/recurrence_vectors.json` - renamed from enginenews_vectors.json
- `STATUS.md` - updated key files section

**Backwards Compatibility:**
- Legacy `seeds/` folder still works
- Python imports unchanged (rcx_pi.selfhost via symlink)
- `get_seed_path()` helper finds seeds in mu/ or falls back to seeds/

---

### Architectural Gap: match.v2 / Non-Linear Pattern Incompatibility

**Problem (discovered in 9-agent review):** match.v2.json states "Linear patterns only (no conflict detection)", but enginenews.v1.json and exhaust.v1.json rely on non-linear patterns (same variable twice for equality). These seeds work via bootstrap (eval_seed) but CANNOT run through the meta-circular kernel.

**Impact:** Seeds could not be declared META_CIRCULAR. Tests passed via bootstrap, hiding architectural incompatibility.

**Solution:**
- Added North Star #14 (execution layer declaration) and #15 (true self-hosting path)
- Added Cross-Seed Compatibility Check to AgentGuardrails.v0.md
- Updated enginenews.v1.json and exhaust.v1.json with `"execution_layer": "BOOTSTRAP"`
- Created VECTOR item for bootstrap_structural bridge (non-linear pattern support)
- Created design doc `mu/docs/core/BootstrapStructuralBridge.v0.md`

**Files:**
- `TASKS.md` - Added North Star #14, #15; added bootstrap_structural to VECTOR
- `mu/docs/agents/AgentGuardrails.v0.md` - Added Cross-Seed Compatibility Check section
- `seeds/enginenews.v1.json` - Added execution_layer, requires_patterns, incompatible_with
- `seeds/exhaust.v1.json` - Added execution_layer, requires_patterns, incompatible_with
- `mu/docs/core/BootstrapStructuralBridge.v0.md` - Design doc for non-linear pattern support

**Lesson Learned:** 9-agent review verified correctness but not architectural fit. New guardrails require verifying execution path matches claims, not just that tests pass.

---

### Step 6: Operator Exhaustion (Rule 3.1) - COMPLETE

**Problem:** Need to detect when an operator has been applied continuously since τ was logged without making progress (Rule 3.1 from RCXEngineNew.pdf).

**Solution:**
- Created `seeds/exhaust.v1.json` with 11 projections
- Three-phase state machine: find_tau → scan → check_frozen → terminal
- Non-linear patterns for equality detection (binding conflict detection)
- First-match-wins ordering (scan_same before scan_different)
- Frozen list as Mu linked-list, NOT Python set

**Projections (exhaust.v1.json):**
- `exhaust.init_null`, `exhaust.init` - Entry points
- `exhaust.find_match`, `exhaust.find_continue`, `exhaust.find_not_found` - Find τ phase
- `exhaust.scan_same`, `exhaust.scan_different`, `exhaust.scan_end` - Scan phase
- `exhaust.frozen_found`, `exhaust.frozen_check_tail`, `exhaust.do_freeze` - Freeze phase

**Testing:**
- 17 parity tests in `tests/test_exhaustion_parity.py`
- 10 fuzzer tests in `tests/test_exhaustion_fuzzer.py`
- 6 test vectors in `tests/fixtures/exhaustion_vectors.json`
- 6 cross-substrate tests (Python and JS produce identical results)

**Security:**
- KERNEL_RESERVED_FIELDS updated to 20 (12 kernel + 4 EngineNews + 4 exhaustion)
- Both Python and JavaScript have identical reserved fields
- Automated parity test at `test_js_parity_automated.py::test_python_js_constants_match`

**Files:**
- `seeds/exhaust.v1.json` - 11 projections
- `tests/test_exhaustion_parity.py` - 17 tests
- `tests/test_exhaustion_fuzzer.py` - 10 tests
- `tests/fixtures/exhaustion_vectors.json` - 6 vectors
- `substrates/js/eval_step.js` - Updated with exhaust.v1.json loading
- `rcx_pi/selfhost/seed_integrity.py` - Added exhaust.v1.json checksum
- `mu/docs/core/OperatorExhaustion.v0.md` - Design doc updated to IMPLEMENTED

## 2026-02-01

### Agent Guardrails (Anti-Hallucination Infrastructure)

**Problem:** LLMs can hallucinate plausible-sounding file paths and code snippets. Previous agent outputs weren't verified for evidence.

**Solution:**
- Created `mu/docs/agents/AgentGuardrails.v0.md` - spec requiring FILE:LINE + code evidence
- Created `tools/validate_agent_compliance.py` - regex-based output validator
- Created `tests/tools/test_validate_agent_compliance.py` - 43 tests for validator
- Created `.claude/hooks/validate-agent-compliance.sh` - automatic SubagentStop hook
- Updated all 9 agent prompts with MANDATORY verification protocol section

**Evidence Format (required for all findings):**
```
FINDING: [description]
FILE: /absolute/path
LINES: start-end
CODE:
    [paste from Read tool output]
VERIFIED: Yes
```

**Validator Features:**
- Line ending normalization (handles Windows/Mac/Unix)
- CODE block validation (accepts tabs OR 2+ spaces)
- Hallucination word detection (13 words blocked)
- STATUS.md check (must be read in first 50 lines)

**Files:**
- `mu/docs/agents/AgentGuardrails.v0.md` - specification
- `tools/validate_agent_compliance.py` - validator script
- `tests/tools/test_validate_agent_compliance.py` - 43 tests
- `.claude/hooks/validate-agent-compliance.sh` - automatic hook
- `.claude/settings.json` - hook configuration
- `tools/agents/archive_pre_guardrails/` - archived old prompts

**Agent Model Updates:**
- Expert upgraded from Sonnet to Opus
- Visualizer upgraded from Haiku to Sonnet
- All agents now use Opus (4) or Sonnet (5) - no Haiku

### Additional Fuzzer Tests (9-agent findings)

- Created `tests/structural/test_entropy_budget_enforcement.py` - EntropyBudget.md grounding
- Created `tests/test_denormalize_type_confusion_fuzzer.py` - type confusion attacks
- Created `tests/test_normalize_malformed_fuzzer.py` - malformed structure handling

### Git Tracking

- `.claude/` directory now tracked (agents, hooks, settings.json) - was previously gitignored
- Enables reproducible agent setup across machines

## 2026-01-31

### Cross-Substrate Parity Verification (9-agent Round 3 Fix)

**Problem (Grounding finding):** Previous JS parity tests were "theater" - they just
parsed strings like "0 failed" from stdout. No test actually ran the same input through
both Python and JavaScript and compared the outputs.

**Fixes:**

- **JS JSON API Mode** (`substrates/js/eval_step.js`)
  - Added `--json-api` command line option for machine-readable output
  - Actions: `run_vector`, `run_all_vectors`, `run_enginenews`, `get_constants`
  - Outputs JSON on single line for easy parsing by Python tests
  - Fixed EngineNews e2e test expectations: stall IS a closure (fixed point)

- **Actual Cross-Substrate Comparison** (`tests/test_js_parity_automated.py`)
  - Added `_normalize_for_cross_substrate()` - handles int/float equivalence (JS doesn't distinguish)
  - Added `_cross_substrate_equal()` - compares normalized outputs
  - New `test_actual_cross_substrate_comparison` - runs SAME 20 parity vectors through BOTH substrates
  - New `test_python_js_constants_match` - verifies MAX_DEPTH=300 and KERNEL_RESERVED_FIELDS match

- **Git Tracking** (`.gitignore`)
  - `substrates/js/eval_step.js` now tracked in git (was previously gitignored)
  - Required for CI to run JS parity tests

**Test Results:**
- 13 JS parity tests: PASSED (including actual comparison)
- 2025 functional tests: PASSED
- Cross-substrate parity is now ACTUALLY VERIFIED, not just claimed

**Known Limitation (documented, not a bug):**
- JavaScript doesn't distinguish between integers and floats (0 === 0.0)
- Cross-substrate comparison normalizes all numbers to float for comparison
- Semantically equivalent; only representation differs

## 2026-01-30

### Step 5: EngineNews Structural Closure Detection (COMPLETE)

**Implementation:**
- Created `seeds/enginenews.v1.json` with 9 projections for Rule 2.2 (Closure-on-Second-Demand)
- Projections: init, end_of_trace, check_state_stall, check_state_maxsteps, check_state,
  found_in_seen, not_in_head, not_found, unwrap
- Non-linear patterns for state equality (same variable `{"var": "state"}` twice)
- Seen-set is Mu linked-list, NOT Python set
- All closure detection logic is in projections (DATA), not Python code

**Key Design Decision: Non-linear Patterns**
- `enginenews.found_in_seen` uses `{"var": "state"}` in both `_state` and `_check_list.head`
- eval_seed.match() binding conflict detection (lines 331-336, 351-355) enforces equality
- This is bootstrap primitive (like Forth's NEXT), not semantic debt
- Both Python and JS substrates handle binding conflicts identically

**Tests:**
- `tests/test_recurrence_parity.py` - 24 parity tests including:
  - TestRecurrenceProjections: seed structure validation
  - TestRecurrenceParity: parity vector tests
  - TestRecurrenceIntegration: integration with run_mu_structural
  - TestRecurrenceSpecCompliance: Rule 2.2 grounding tests
  - TestRecurrenceClosureObjectStructure: exact Omega(tau) structure
  - TestRecurrenceExactProjectionCount: 9 projections exactly
- `tests/test_recurrence_fuzzer.py` - Property-based fuzzer tests:
  - TestRecurrenceDeterminism: same input -> same output
  - TestRecurrenceClosureSemantics: Rule 2.2 semantics
  - TestRecurrenceEdgeCases: numeric, string, null states
  - TestRecurrenceTypeDistinctness: 0 vs false vs null
  - TestRecurrenceTraceFormats: stall, max_steps entries
  - TestRecurrenceComplexStates: nested state equality
- `tests/fixtures/recurrence_vectors.json` - 22 parity vectors

**7-Agent Review (Second Pass):**
| Agent | Verdict | Summary |
|-------|---------|---------|
| Verifier | APPROVE | All 12 North Star invariants maintained |
| Adversary | SECURE | Non-linear pattern concern RESOLVED |
| Expert | MINIMAL | Code appropriately sized |
| Structural-proof | PROVEN | All 4 structural claims verified |
| Grounding | GROUNDED | All claims have executable tests |
| Fuzzer | DESIGN COMPLETE | Comprehensive fuzzer code provided |
| Advisor | RESOLVED | Architecture is sound |

**Documentation:**
- Updated `mu/docs/core/EngineNewsStructural.v0.md` - marked IMPLEMENTED
- Updated `mu/docs/core/SelfHosting.v0.md` - added EngineNews section
- Updated `mu/docs/core/BootstrapPrimitives.v0.md` - added binding conflict note
- Updated `STATUS.md` - Step 5 DONE
- Updated `TASKS.md` - all checkboxes marked complete

### Second 7-Agent Adversarial Review (Complete)

**Verdicts:**
- Verifier: CONDITIONAL_APPROVE (all 12 invariants maintained)
- Adversary: SECURE (11/11 attacks blocked, defensive cache copy verified)
- Expert: COULD_SIMPLIFY (2 trivial import issues in conftest.py)
- Structural-proof: CLAIMS_HONEST (L2 PARTIAL proven with concrete evidence)
- Grounding: GROUNDED (all 4 claims have executable tests)
- Fuzzer: GAPS_EXIST (4 boundary gaps: depth=100, width=900-1000, cache at scale, mixed)
- Advisor: ON_TRACK (Step 5 needs concrete success criteria)

### Security Fixes
- **Cache Mutation Vulnerability** (Adversary finding - CLOSED)
  - `projection_loader.py`: Returns `list(cache[0])` defensive copy
  - `step_mu.py`: Returns `list(_combined_kernel_cache)` defensive copy
  - New test: `test_mutation_does_not_affect_cache()` in test_projection_loader.py
  - Updated caching tests to verify content equality, not object identity

### Code Quality
- **Duplicate Code Consolidated** (Expert finding - CLOSED)
  - `run_until_done()` moved to `tests/conftest.py` as shared utility
  - `test_phase7c_integration.py` now imports from conftest
  - `test_parity_python.py` now imports from conftest
  - Removed ~70 lines of duplicate code

### Testing
- **Dict kv-pair Regression Tests** (Grounding finding - CLOSED)
  - Added `TestDictKvPairFormat` class (4 tests)
  - Tests exact structural format: `{"head": key, "tail": {"head": value, "tail": null}}`
  - Tests sorted key order, nested preservation

- **Malformed Linked List Tests** (Fuzzer finding - CLOSED)
  - Added `TestMalformedLinkedListEdgeCases` class (9 tests)
  - Tests head-only, tail-only, malformed tail types
  - Tests circular reference detection
  - Tests deeply nested and wide dict handling

### Documentation
- **CRITICAL: EngineNews Must Be Structural**
  - Updated TASKS.md Step 5 with concrete success criteria
  - EngineNews rules MUST be Mu projections, NOT Python code
  - Closure detection must be pattern matching on traces
  - This ensures emergence is structural, not "Python did it"
  - Added `enginenews.v1.json` requirements (≥4 projections)

- **STATUS.md**: Added second 7-agent review verdicts table
- **TASKS.md**: Updated Step 5 with structural requirements and success criteria

### Test Count
- 913 tests pass in fast audit
- 1669 tests pass in full suite (2 expected idempotency failures from uncommitted changes)

## 2026-01-29

### Security Hardening (7-agent review)
- **Deprecation Enforcement** (HIGH priority fix)
  - Added `filterwarnings = ["error::DeprecationWarning:rcx_pi.*"]` to pyproject.toml
  - New code using deprecated Kernel class will now FAIL tests (not just warn)
  - Removed `TestKernelIntegration` class (4 tests) - used deprecated Kernel
  - Coverage already exists via test_step_mu_parity.py, test_kernel_projections.py

- **Step Budget Test Coverage** (coverage gap fix)
  - Created `tests/structural/test_step_budget.py` (18 tests)
  - Tests: basics, limits, reset, thread safety, no-deprecation verification
  - Grounds the claim that step budget functions are ACTIVE (not deprecated)

- **Archive Protection** (MEDIUM priority fix)
  - Added `tests/archive/conftest.py` with `pytest_ignore_collect` hook
  - `pytest tests/archive/` now collects 0 tests (was 134)
  - Prevents accidental execution of deprecated tests

- **CI Contraband/AST Police** (MEDIUM priority fix)
  - Added contraband.sh and ast_police.py to `scripts/green_gate.sh`
  - CI now runs [PY 1/4] syntax, [PY 2/4] contraband, [PY 3/4] AST, [PY 4/4] tests
  - Catches host smuggling before merge (was only in local audit_all.sh)

- **Audit Claims Grounding Tests** (grounding agent recommendation)
  - Created `tests/structural/test_audit_claims_grounding.py` (18 tests)
  - Tests verify: archive blocking, deprecation enforcement, audit script structure
  - Tests verify: lambda guardrails exist, step budget coverage exists
  - Fully grounds all audit infrastructure claims

### Architecture Cleanup
- **kernel.py Clarification** (7-agent review)
  - Added architecture comment block explaining two distinct concerns:
    1. ACTIVE: Step budget functions (get_step_budget, etc.) - used by self-hosting
    2. LEGACY: Kernel class - NOT used by self-hosting, only for testing
  - Added deprecation warning to `Kernel` class and `create_kernel()` factory
  - Moved `test_kernel_v0.py` to `tests/archive/legacy/`
  - Created `tests/structural/test_lambda_calculus_guardrails.py` with 11 guardrail tests
  - Updated mu/docs/core/MetaCircularKernel.v0.md with deprecation note and max_steps clarification

- **Documentation: kernel.v1.json as Canonical Kernel**
  - Updated README.md: Core modules table now lists kernel.v1.json as "THE canonical kernel"
  - Updated mu/docs/core/SelfHosting.v0.md: kernel.py noted as "not canonical; see kernel.v1.json"
  - Updated mu/docs/core/RCXKernel.v0.md: Added status column marking kernel.v1.json as canonical
  - Updated mu/docs/audit/MetaCircularReadiness.v1.md: Current status references kernel.v1.json

- **Audit Stack Cleanup**
  - Updated tools/audit_fast.sh: Removed archived test_kernel_v0.py from explicit test list
  - tests/conftest.py already has `"archive"` in collect_ignore (no change needed)
  - Lambda calculus guardrails auto-included via tests/structural/ in audit_fast.sh

### Testing
- **Lambda Calculus Guardrail Tests Migrated** (11 tests)
  - Migrated from test_eval_seed_v0.py to dedicated structural test file
  - Tests prove: no closures, no self-application, no Y-combinator, no higher-order matching
  - These are NORTH STAR invariant enforcement tests

### Documentation
- **STATUS.md**: Fixed @host_recursion count (3 → 2)
- **Added tests for `is_kernel_intermediate()`** (12 tests)
  - Documents key finding: `{"mode": "subst"}` (value) vs `{"subst": ...}` (key)
  - Proves mu_equal stall detection works correctly for unbound variables

### L2 Grounding & Boundary Validation
- **Docstring False Positive Fix**
  - Fixed eval_seed.py:70 docstring being counted as debt by debt_dashboard.sh
  - Was matching `@host_` pattern in docstring text

- **L2 Cursor Grounding Tests** (7 tests)
  - Created `tests/structural/test_l2_cursor_grounding.py`
  - Proves `_remaining` is structural (head/tail), not arithmetic index
  - Tests kernel.wrap creates _remaining from _projs linked list
  - Tests kernel.try consumes head, kernel.match_fail advances to tail

- **Boundary Validation Fuzzer** (27 tests)
  - Created `tests/test_boundary_validation_fuzzer.py`
  - Tests assert_seed_pure with valid/invalid inputs (lambdas, functions, builtins)
  - Tests validate_type_tag whitelist enforcement (list/dict only)
  - Tests get_var_name validation (empty names, non-var sites)

- **Kernel Bridge Fuzzer** (26 tests)
  - Created `tests/test_kernel_bridge_fuzzer.py`
  - Tests list_to_linked (preserves length, order, produces valid Mu)
  - Tests normalize_projection (pattern/body normalization)
  - Integration tests for projection list conversion

- **SelfHosting.v0.md Update**
  - Documented legacy Kernel class deletion (~350 lines removed)
  - Clarified kernel.py now only contains step budget infrastructure

## 2026-01-28

### Testing
- **Fuzzer Configuration Fully Standardized** (3x 9-agent review)
  - Fixed `deadline=None` in test_apply_mu_fuzzer.py (10 tests → `deadline=5000` or `deadline=10000`)
  - Standardized `max_depth=3` default across ALL 6 fuzzer generators:
    - test_bootstrap_fuzzer.py, test_selfhost_fuzzer.py, test_type_tags_fuzzer.py
    - test_apply_mu_fuzzer.py, test_phase8b_fuzzer.py, test_phase7_readiness_fuzzer.py
  - Fixed 29 call site overrides: `max_depth=4` → `max_depth=3` across 4 files
  - Fixed docstring bug in test_apply_mu_fuzzer.py ("default 5" → "default 3")
  - Documentation claims now match reality (STATUS.md is single source of truth)
  - Prevents tests from hanging on pathological inputs
  - All 772 core tests pass

### Self-Hosting
- **Phase 7d-1: Wire step_mu to Structural Kernel** (L2 PARTIAL)
  - `step_mu()` delegates to `step_kernel_mu()` which uses structural kernel
  - Added helpers: `list_to_linked()`, `normalize_projection()`, `load_combined_kernel_projections()`
  - Kernel uses linked-list cursor for projection SELECTION (structural)
  - Projection EXECUTION still uses Python for-loop in `step_kernel_mu`
  - Behavioral change: unbound variables now stall instead of raising KeyError

- **Honest Assessment (7-agent review)**
  - structural-proof agent found: execution loop still Python (lines 229-261)
  - Added `@host_iteration` decorator to `step_kernel_mu()` (honest debt tracking)
  - Debt: 15 → 15 (moved location, not eliminated)
  - L2 PARTIAL: selection structural, execution Python
  - True L2 requires Phase 8 recursive kernel design
  - 7d-2/7d-3 PAUSED pending Phase 8

- **Phase 7a: Kernel Projections Seed**
  - Created `seeds/kernel.v1.json` with 7 kernel projections
  - Projections: kernel.wrap, kernel.stall, kernel.try, kernel.match_success, kernel.match_fail, kernel.subst_success, kernel.unwrap
  - 30 manual trace tests pass (success, failure, empty, fallthrough)
  - Tests in `tests/test_kernel_projections.py`

- **Phase 7b: Match/Subst Context Passthrough**
  - Created `seeds/match.v2.json` with `_match_ctx` passthrough + match.fail catch-all
  - Created `seeds/subst.v2.json` with `_subst_ctx` passthrough
  - Context enables kernel to preserve state across mode transitions

- **Phase 7c: Integration Testing**
  - 20 integration tests: kernel → match → subst → kernel cycles
  - Tests in `tests/test_phase7c_integration.py`
  - Context preservation verified through full cycles
  - Security: domain data can't forge `_mode` (underscore prefix)

### Tests
- **v2 Parity Tests**
  - Created `tests/test_match_v2_parity.py` (19 tests)
  - Created `tests/test_subst_v2_parity.py` (18 tests)
  - 37 tests verify v2 seeds preserve v1 behavior
  - Tests: seed structure compatibility, functional parity, context design

### Debt Tracking
- **Comprehensive Debt Audit**
  - Found and marked 4 @host_iteration markers (step_mu, run_mu, eval_seed.step, projection_runner)
  - Added `# @host_iteration` comment marker for nested function debt
  - Updated `debt_dashboard.sh` to count both decorator and comment markers
  - Debt: 15 (12 tracked + 3 AST_OK)

- **Debt Target Revision**
  - Original target was 9, revised to 12 per structural-proof agent
  - run_mu outer loop stays as L3 boundary (scaffolding, not semantic debt)
  - 7d-1 moved debt from step_mu to step_kernel_mu (net: 15 → 15)
  - True debt reduction (15 → 12) deferred to Phase 8

### Docs
- **Doc Consistency Fixes**
  - All design docs now reference STATUS.md for debt numbers (no hardcoded values)
  - `mu/docs/core/SelfHosting.v0.md`: Removed hardcoded debt breakdown
  - `mu/docs/core/MetaCircularKernel.v0.md`: Updated status VECTOR → NEXT
  - `mu/docs/core/DebtCategories.v0.md`: Removed outdated DEBT_THRESHOLD values

### Security
- **Kernel Projection Order Validation**
  - Added `validate_kernel_projections_first()` call in step_mu() production path
  - Domain projections can no longer run before kernel projections
  - Tests in `tests/structural/test_projection_order_security.py`

### Process
- **7 Agent Review Complete**
  - verifier: APPROVE WITH DOC FIXES
  - adversary: AT_RISK (security concerns documented)
  - expert: MINIMAL (code is clean)
  - structural-proof: PARTIALLY PROVEN (debt 15→9 unrealistic, revised to 15→12)
  - grounding: GROUNDED (all claims backed by tests)
  - fuzzer: GAPS (3 property tests recommended before 7d)
  - advisor: PROCEED NOW (foundation strong)

### Tooling
- **Pre-commit Hook Improvements**
  - Added debt ceiling check to `tools/pre-commit-doc-check`
  - Hook now warns if debt exceeds THRESHOLD from STATUS.md
  - Updated `CLAUDE.md` with clearer workflow documentation
  - Added "Development Workflow" section to `STATUS.md`
  - Two pre-commit scripts documented: `pre-commit-check.sh` (full) vs `pre-commit-doc-check` (hook)

## 2026-01-27

### Agents
- **Advisor Agent** - New strategic advisor for when stuck on design decisions
  - Created `tools/agents/advisor_prompt.md` and `.claude/agents/advisor.md`
  - Provides options, trade-off analysis, creative solutions
  - Verdict types: OPTIONS_PROVIDED / RECOMMENDATION / NEEDS_MORE_CONTEXT
  - Advisor PROPOSES, other agents VALIDATE

- **Agent Documentation Completion**
  - Created 4 missing prompt files in `tools/agents/` (now all 10 agents tracked in git):
    - `grounding_prompt.md`, `fuzzer_prompt.md`, `translator_prompt.md`, `visualizer_prompt.md`
  - All agents now have "STATUS.md wins" override rule
  - structural-proof has exec/non-exec modes (Mode A: run, Mode B: CI verification)

- **Archived**: `tools/verification_checklist.md` → `archive/docs/verification_checklist_v0.md`
  - Superseded by `tools/agents/verifier_prompt.md` (verifier agent)

### Design
- **Phase 7 Design: Meta-Circular Kernel** (PR #168)
  - Created `mu/docs/core/MetaCircularKernel.v0.md` (VECTOR status)
  - Defines how kernel loop becomes structural (projections select projections)
  - Key design: linked-list cursor eliminates arithmetic (head/tail destructuring)
  - Structural-proof agent verified cursor approach is SOUND and STRUCTURAL
  - v0.2 revision addresses agent-identified gaps:
    - Context preservation via `_match_ctx` / `_subst_ctx` fields
    - Structural NO_MATCH: `{"_mode": "match_done", "_status": "no_match"}`
    - Namespace protection: `_` prefix for kernel-internal fields
    - Simplified from 11 to 7 kernel projections
  - Total projections: 7 kernel + 32 existing = 39 for fully self-hosted kernel

### Tooling
- **STATUS.md: Single Source of Truth for Project Phase**
  - Created `STATUS.md` as canonical source for current phase and self-hosting level
  - All agents now read STATUS.md before assessments (MANDATORY)
  - Self-hosting levels: L1 (Algorithmic), L2 (Operational), L3 (Full Bootstrap)
  - Agent Enforcement Guide table: what applies NOW vs LATER
  - When advancing phases: update ONE file, not 8+ agent files

- **Agent Semantic Phase Scope**
  - Updated all 8 agent `.md` files with semantic scope (L1/L2/L3, not phase numbers)
  - Agents reference STATUS.md for current level, not hardcoded version
  - Distinguishes scaffolding debt (acceptable at current L) from semantic debt (must fix)
  - Updated `mu/docs/agents/AgentRig.v0.md` with semantic Phase Scope table
  - Prevents phase drift: agents adapt automatically when STATUS.md updates

### Tests
- **Kernel Loop Fuzzer Tests** (PR #167)
  - 11 property-based tests for apply_mu, step_mu, run_mu
  - TestApplyMuDeterminism: 3 tests (determinism, var pattern, literal match)
  - TestApplyMuParity: 1 test (apply_mu == apply_projection)
  - TestStepMuDeterminism: 3 tests (determinism, empty projections, stall idempotent)
  - TestStepMuParity: 2 tests (step_mu == step, first-match-wins)
  - TestRunMuDeterminism: 2 tests (determinism, immediate stall)
  - 3000+ random examples stress-test kernel loop stability
  - Closes fuzzer gap identified by agents before Phase 7

### Tooling
- **Comprehensive Debt Tracking** (PR #155)
  - Marked ~289 LOC of previously unmarked semantic debt with `@host_*` decorators
  - match_mu.py: 7 decorators (3 `@host_recursion`, 4 `@host_builtin`)
  - subst_mu.py: 2 decorators (`@host_builtin`)
  - Updated DEBT_THRESHOLD: 14 → 23 (17 tracked + 5 AST_OK + 1 review)
  - Updated dashboard ceiling: 9 → 17
  - All semantic debt now fully tracked (was ~289 LOC unmarked)

### Tests
- **Head/Tail Collision Tests** (PR #155)
  - `TestMatchParityHeadTailCollision`: 5 tests verifying dicts with head/tail keys
  - Ensures user data like `{"head": "x", "tail": "y"}` isn't misclassified as linked list

- **Empty Collection Tests** (PR #155)
  - `TestMatchParityEmptyCollections`: 5 tests documenting known difference
  - Documents: `{}` and `[]` both normalize to `null` (intentional structural equivalence)
  - Tests explicitly mark this as "DOCUMENTED DIFFERENCE" vs parity

### Docs
- **Design Decisions Documented** (PR #155)
  - `mu/docs/core/DebtCategories.v0.md`: Added "Known Design Decisions" section
  - Empty collection normalization explained with rationale
  - Head/tail collision handling documented

### Process
- All 6 agents reviewed: verifier, adversary, expert, structural-proof, grounding, fuzzer
- Debt now at ceiling (23/23) with clear path to L2

### Security
- **Seed Integrity Verification** (PR #157)
  - `rcx_pi/selfhost/seed_integrity.py`: SHA256 checksum verification
  - Validates seed structure on load (meta, projections keys required)
  - Verifies expected projection IDs present and wrap is last
  - `match_mu.py` and `subst_mu.py` now use `load_verified_seed()`
  - 27 tests in `tests/test_seed_integrity.py`
  - Closes adversary finding: seeds were loaded without integrity verification

### Self-Hosting
- **Phase 6a: Lookup as Mu Projections** (PR #158)
  - Added `subst.lookup.found` and `subst.lookup.next` projections to subst.v1.json
  - Lookup is now structural: pattern matching with non-linear vars
  - `subst.var` now transitions to `phase: lookup` instead of creating marker
  - `subst.lookup.found`: name matches current binding → return value
  - `subst.lookup.next`: name doesn't match → continue with rest
  - Unbound variables stall (lookup_bindings becomes null, no projection matches)
  - Removed 2 `@host_builtin` decorators from subst_mu.py
  - DEBT_THRESHOLD: 23 → 21 (ratchet tightened)
  - 37 subst parity tests pass

- **Phase 6b: Classification as Mu Projections**
  - Created `seeds/classify.v1.json` with 6 projections for linked list classification
  - Created `rcx_pi/selfhost/classify_mu.py` for projection-based classification
  - `denormalize_from_match()` now uses `classify_linked_list()` instead of `is_dict_linked_list()`
  - `classify.nested_not_kv`: detects when "key" position has head/tail (not a string)
  - `classify.kv_continue`: element is valid kv-pair → continue scanning
  - `classify.not_kv`: element is not kv-pair → classify as list
  - Python pre-check validates: no cycles, all keys are strings (projections can't verify types)
  - Removed 2 `@host_builtin` decorators from match_mu.py
  - DEBT_THRESHOLD: 21 → 19 (ratchet tightened)
  - 26 tests in `tests/test_classify_mu.py`

- **Phase 6c: Normalization as Iterative + Type Tags**
  - `normalize_for_match()`: converted from recursive to iterative using explicit stack
  - `denormalize_from_match()`: converted from recursive to iterative using explicit stack
  - Removed 2 `@host_recursion` decorators from match_mu.py
  - Removed 2 `# AST_OK: bootstrap` comments (recursive comprehensions eliminated)
  - isinstance() checks at Python↔Mu boundary remain as scaffolding (not semantic debt)
  - **Type Tags** resolve list/dict ambiguity (previously `[["a", 1]]` and `{"a": 1}` normalized identically):
    - Lists get `_type: "list"`, dicts get `_type: "dict"` at root node
    - `VALID_TYPE_TAGS` whitelist + `validate_type_tag()` for security
    - New projections: `match.typed.descend`, `subst.typed.{descend,sibling,ascend}`
    - `classify_linked_list()` fast-path for type-tagged structures
  - 24 new property-based fuzzer tests (`tests/test_type_tags_fuzzer.py`)
  - All 1020 self-hosting tests pass
  - Agent review: verifier=APPROVE, adversary=HARDENED, structural-proof=PROVEN

## 2026-01-26

### Runtime
- **Thread-Safe Step Budget** (PR #149)
  - `_ProjectionStepBudget` uses `threading.local()` for thread isolation
  - Each thread gets independent budget tracking for concurrent execution
  - `get_step_budget()` and `reset_step_budget()` API

- **Cycle Detection** (PR #149)
  - `normalize_for_match()` detects circular references (raises ValueError)
  - `denormalize_from_match()` detects circular references (raises ValueError)
  - `is_dict_linked_list()` returns False on cycles instead of infinite loop

- **Resource Exhaustion Guardrails** (PR #149)
  - Global projection step budget: MAX_PROJECTION_STEPS = 50,000
  - Mu depth limit: MAX_MU_DEPTH = 300
  - Mu width limit: MAX_MU_WIDTH = 1,000
  - Empty variable name rejection in match_mu/subst_mu

### Tests
- **Comprehensive Fuzzer Tests** (PR #149)
  - `tests/test_selfhost_fuzzer.py`: 53 tests, 10,000+ random examples
  - `TestMatchMuParity`: match_mu == eval_seed.match (1,000 examples)
  - `TestSubstMuParity`: subst_mu == eval_seed.substitute (1,200 examples)
  - `TestHostileUnicodeHandling`: emoji, RTL, zero-width, homoglyphs
  - `TestNearLimitStress`: width 900-1000, depth 190-200
  - All Hypothesis tests use deadline=5000 (prevents infinite hangs)

- **Adversary Tests** (PR #149)
  - `test_nested_calls_exhaust_budget`: verifies budget limits cascading calls
  - `test_budget_thread_isolation`: verifies no cross-thread contamination
  - `test_circular_in_is_dict_linked_list_returns_false`: cycle safety
  - `test_nested_circular_in_normalize_raises`: nested cycle detection

### Process
- All 6 agents approved: verifier, adversary, expert, structural-proof, grounding, fuzzer
- Coverage rated ROBUST by fuzzer agent

## 2026-01-25

### Tooling
- **Rule Motif Observability v0** (PR #108)
  - `rules --print-rule-motifs` CLI command
  - `rule_motifs_v0()` pure helper returning all 8 rule motifs
  - `emit_rule_loaded_events()` generates v2 JSONL (`rule.loaded` events)
  - `RULE_IDS` canonical list for anti-drift testing
  - 11 subprocess CLI tests

- **Rule Motif Validation Gate v0** (PR #111)
  - `rules --check-rule-motifs` CLI command
  - `rules --check-rule-motifs-from <path>` for custom validation
  - `validate_rule_motifs_v0()` pure helper with validation rules:
    - Structure, id uniqueness, variable binding, host leakage, canonicalization
  - 16 subprocess CLI tests (positive + negative cases)

- **Trace Canon Helper v1** (PR #66)
  - `canon_jsonl()` function for JSONL serialization
  - 7 tests in `test_trace_canon_v1.py`
  - v2 event support (accepts both v1 and v2 events)

### Runtime
- **Second Independent Encounter v0** (NEXT #16)
  - Stall memory tracking: `_stall_memory` maps pattern_id → value_hash
  - Closure signal detection: `_check_second_independent_encounter()`
  - Memory clearing on `execution.fixed`: `_clear_stall_memory_for_value()`
  - Public API: `closure_evidence`, `has_closure` properties
  - `stall()` and `consume_stall()` now return bool (closure detected)
  - 15 tests in `test_second_independent_encounter.py`
  - All 8 pathological scenarios from IndependentEncounter.v0.md tested

### Docs
- Updated `docs/RuleAsMotif.v0.md` to reflect implementation status
- Updated `docs/cli_quickstart.md` with rules commands
- Updated `mu/docs/execution/IndependentEncounter.v0.md` to IMPLEMENTED status

## Unreleased

- Schema-triplet canonicalization: added `rcx_pi/cli_schema_run.py` as the single source of truth and updated CLI smoke + tests to route schema checks through the canonical runner (PRs #59–#62).

## 2026-01-24

### Runtime
- **v2 Execution Semantics (RCX_EXECUTION_V0=1)**
  - ExecutionEngine with stall/fix/fixed state machine
  - Public consume API: `consume_stall`, `consume_fix`, `consume_fixed`
  - Public getter: `current_value_hash` for post-condition assertions
  - `value_hash()` for deterministic value references
  - Record Mode v0: execution → trace for stall/fix events

### Tooling
- **Anti-theater guardrails**
  - `--print-exec-summary` CLI flag for v2 execution summary
  - `execution_summary_v2()` pure helper (derives state from events only)
  - `tools/audit_exec_summary.sh` non-test reality anchor
  - `test_cli_print_exec_summary_end_to_end` subprocess CLI test

### Docs
- `docs/TraceReadingPrimer.v0.md` - Human-readable trace guide
- `docs/Flags.md` - Flag discipline contract
- `archive/docs/MinimalNativeExecutionPrimitive.v0.md` - Boundary question answered
- Removed `NEXT_STEPS.md` (redundant with TASKS.md)

### Tests
- v2 replay validation (`validate_v2_execution_sequence`)
- Record→Replay gate end-to-end determinism test
- Closure-as-termination fixture family (stall_at_end, stall_then_fix_then_end)

### Process
- TASKS.md is now the single canonical task tracker
- All v2 work gated by feature flags (default OFF)

Format:
- Date (YYYY-MM-DD)
- Category: Docs / Schemas / Runtime / Tests / Tooling
- Notes: Must distinguish "frozen contract" vs "future target"

## 2026-01-12

### Tooling
- Kernel step-003/004: stabilize world_trace_cli invocation (script + module); tests now 216 passed, 1 skipped.
- Verified repo green gate (212 passed, 1 skipped).
- Freeze tag created on dev: `rcx-freeze-verified-2026-01-12` → `18c2dad`.
- Quarantine cleanup / ignore rules for accidental CLI-arg files.
- Added world trace CLI (Python).
- Added core MU freezer utility (`rcx_pi_rust/scripts/freeze_core_mu.py`).

## 2026-01-03

### Docs
- Frozen external CLI + JSON contracts in `docs/RCX_OMEGA_CONTRACTS.md`.
  - Notes: This freeze reflects CURRENT runtime behavior. Any future targets (e.g., `kind=omega_summary`) are explicitly marked as future and are NOT required today.

### Schemas
- Published optional JSON Schemas under `schemas/rcx-omega/`:
  - `trace.v1.schema.json`
  - `omega_summary.v1.schema.json`
- Policy: `kind` and `schema_version` are OPTIONAL and MUST remain opt-in + environment-gated. Default runtime output remains byte-for-byte identical.

### Process
- Added staging → stable promotion checklist in `docs/STAGING_TO_STABLE.md`.

### Runtime
- No runtime changes in this entry.

## 2026-01-03

### Runtime
- Added env-gated OPTIONAL schema fields to JSON producers:
  - Set `RCX_OMEGA_ADD_SCHEMA_FIELDS=1` to inject `schema_version` (and `kind` if absent).
  - Default output remains unchanged when the env var is not set.

### Docs
- Updated `docs/RCX_OMEGA_CONTRACTS.md` with a “Runtime Reality Notes” section to reflect current behavior:
  - `kind` may be omitted or may use legacy values (e.g., `omega`).
  - `kind=omega_summary` remains a FUTURE target, not a frozen requirement.
  - `schema_version` is OPTIONAL and opt-in only.

### Tests
- Verified green gate: `python3 -m pytest -q`

## 2026-01-23

### Tests
- Enforced **orbit artifact idempotence** for tracked files.
  - Re-running `scripts/build_orbit_artifacts.sh` no longer dirties the working tree.
- Formalized **orbit provenance semantics**:
  - Provenance entries validated against emitted state transitions.
  - Supports both legacy (`from` / `to`) and current (`pattern` / `template`) schemas.
  - State entries may be strings or structured objects (e.g. `{"i": 0, "mu": "ping"}`).

### Tooling
- Added Graphviz SVG normalization to strip version-specific metadata.
  - SVG fixtures are now stable across Graphviz versions.
- Added `scripts/merge_pr_clean.sh` helper for repositories with auto-merge disabled.
  - Rebase head onto base, safe force-push, gate wait, manual merge, post-merge sync.
  - Convenience script only; repository policy unchanged.

### Process
- Confirmed layered-growth rule enforcement:
  - Kernel remains frozen.
  - All new behavior implemented via tools, fixtures, or validation layers.
- Green gate verified after each change sequence.

Notes:
- No kernel or runtime semantics were modified.
- All changes live strictly outside the frozen RCX-π core.
