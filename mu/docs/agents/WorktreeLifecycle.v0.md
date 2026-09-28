<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-09-27
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/tools/test_worktree_lifecycle.py, mu/tests/tools/test_workingrcx_fleet_apply.py, mu/tests/tools/test_commit_executor_post_merge_cleanup.py, mu/tests/tools/test_pipeline_monitor_autofollow.py, mu/tests/tools/test_launch_wave.py, mu/tests/tools/test_recovery_gate.py
-->
# Native worktree lifecycle

The cleanup task is `FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION`. A merged PR,
backup, census or HOLD count does not complete it. Runtime semantics are outside
this control-plane contract.

## Ownership and terminal completion

`worktree_lifecycle.py` registers an exact linked worktree, its filesystem and
Git directory identity, wave, bus and native process owners under the surviving
common Git directory's `rcx_worktree_lifecycle/`. PRIMARY cannot be registered
for retirement. Launcher refusal, dispatcher failure/stop and post-merge cleanup
retain a terminal request there. Normal Phase A/B handoffs retain registration
until the downstream native owner finishes.

Post-merge cleanup preserves branches and held stashes. A providerless child
performs at most three durable completion attempts. Live native owners must
exit first. Each attempt repeats native/process/file checks and uses the
existing preservation transaction and fresh terminal mutation boundary. An
interrupted claim or started mutation is escalated; it is never replayed.
Recorded completion verifies source absence, destination bytes and the full
semantic index on re-read.
The native launcher uses a single dispatch. The optional dispatcher's `--loop`
cleanup fence still needs to read the commit payload nested in executor stdout;
that finding remains deferred under row40 in `TASKS.md`. Generated bridge
nonblocker reports are optional and may be removed by a native GO.

Native commit closeout publishes the actual result, handoff and available
config/routing/package/receipt bytes in the common directory before retirement.
Those copies preserve evidence; they grant no replay authority. Missing or failed
closeout retains the source and its correction owner. Ordinary post-merge
verification records the fetched merge without first modifying the base owner.
Synchronization loads the exact landed dependencies in a fresh interpreter and
coordinates PRIMARY plus the exact separately checked-out base owner through
the existing identity-bound, locked transaction API. The base owner is bound
before PRIMARY sync and rechecked under the shared lock before recovery,
preparation and fast-forward. Native ownership, process/open-file and content
checks retain live, uncertain, changed or divergent owners individually.

`primary_worktree_sync` retains PRIMARY's outcome and adds `base_worktree_sync`
and `all_owners_current`. Each owner reports actual ahead/behind counts and
CURRENT, CURRENT_WITH_HELD_WIP or HOLD; a base with no checkout reports
NOT_CHECKED_OUT. PRIMARY success cannot conceal a stale base checkout. These
local holds do not revert a merged PR or release a useful-work owner. Foreign
journals remain with their recorded owners. Replacement coverage uses an
actually synchronized surviving checkout.
The recorded R3 recovery enabler carries transaction R2 as its original plan
owner and cannot fabricate a new plan or restart consumed operations.

The child writes its log and receipts in the common directory and uses surviving
PRIMARY as its cwd. Escalation uses the existing Codex pager at an identity-bound
surviving root. Pager errors have their own durable receipt. It never writes a
pager event into a retired source.

The generated raw-log watcher uses native lifecycle registration and terminal
identity, including the exact bus, HEAD and filesystem identity, plus registered
owner exit to release its own follower. Log text, age and PID absence alone do
not prove terminal state. A live registered owner continues to display output.
The default monitor resolves the selected carrier's root and bus together on
each refresh. Log selection, terminal probes and heartbeat attachment all use
that same pair, including named-bus carriers. The implicit tee-log path is
derived from the selected root on each refresh, so a previous carrier's recent
tee cannot hide the new carrier's active output. `RCX_PIPELINE_LIVE_LOG` retains
its explicit log override. Explicit lane or bus pins retain
their fixed bus; a terminal record on a different bus cannot release the reader.
The watcher moves its cwd to the surviving common-directory owner, checks
terminal state before selection and attachment (including heartbeat and cold
restart), and leaves the last output visible or renders a finite snapshot.
It stops only its own tail; it never exempts readers from the generic retirement
guard. An open writer still holds native completion. The same three-attempt
budget and all historical claims remain unchanged; reader release grants no
retry or retirement authority.

Supported inspection and bounded completion commands:

```sh
python3 mu/tools/executors/worktree_lifecycle.py --record <exact-common-dir-record>
python3 mu/tools/executors/worktree_lifecycle.py --record <exact-common-dir-record> --complete
```

Each retained completion records an executable inspection command, the exact
evidence path and the owner action needed to resolve it. Inspection grants no
new mutation authority.

The second command cannot reset the attempt budget or reapply a completed or
interrupted mutation. Escalated owners require their recorded next action and
fresh reviewed action authority. A later native commit gets a separate exact
HEAD completion record linked from its predecessor; prior claims and budgets
stay unchanged. If a committed stopped lane later merges at the same HEAD, a
native merged/success request must supply the exact merge SHA. Fresh base fetch
and ancestry checks bind an immutable successor to that landed merge and the
finished pre-mutation useful-work or failed commit-closeout escalation. A failed
closeout may precede the merge or retain that same merge SHA after a post-merge
failure. Its successor verifies the commit owner and saved failed result, and
hashes the original closeout alongside the terminal, completion and attempt
evidence. It requires a newly published successful closeout in its own record;
the predecessor's failed closeout remains immutable and cannot authorize
retirement. Repeated failed-closeout continuations retain the full predecessor
chain and consume only the remaining attempts from the original three-attempt
budget. Exhaustion cannot be reset by another successful request. Interrupted or
started target preparation cannot acquire this successor. Repeated requests
follow the same successor, including after source retirement; inspecting the
old completion still returns its unchanged historical outcome.

A live dispatcher defers its commit children's completion worker until its
terminal handoff. A sequential successful commit child at the same HEAD may
therefore bind the previous failed closeout before `completion.json` exists,
provided no completion attempt has started. That successor hashes the actual
failed closeout and immutable terminal identity, verifies landed merge authority,
and requires its own successful closeout. An unattempted deferred predecessor
consumes zero completion attempts; any earlier consumed attempts remain charged
through the full predecessor chain. The live dispatcher still owns the worker,
and retirement still requires every registered owner to exit. Completion through
an older deferred record follows its verified successor without starting a late
attempt or changing the sealed failure evidence. Any claim or preparation under
an unfinished predecessor rejects this admission, including interrupted mutations.

Abrupt termination before a terminal request
leaves the original registration as incomplete evidence; registration alone
does not authorize retirement.

## Fleet inventory and useful work

Fresh census supports `--comparison-commit <exact-local-dev-commit>`. It records
HEAD ancestry, local branch/history references, staged and unstaged patch
hashes, path/blob identities, and content hashes without changing targets.
Standalone clones include local history outside HEAD. Inspection failures stay
unknown. Identical bytes and covered history establish conservative dev
coverage; differing bytes require native landing review.

Native completion passes its recorded coverage inventory to the existing
preservation admission check under the preparation lock. Changed index/content
between inventory and admission causes a HOLD before target preparation or
retirement. The next attempt uses the remaining original budget and records a
native landing owner if the fresh inventory requires it; the earlier coverage
receipt stays unchanged. Preserved bytes alone cannot authorize completion.

The PR1306 transaction also binds admission through every archive, native stash,
fast-forward and terminal move. A later index-only edit keeps an explicit
unresolved landing owner in both the apply outcome and lifecycle result.

Detached linked worktrees are inventoried from their exact HEAD and index,
including detached-only commits and staged/unstaged/untracked changes. They
have no symbolic local branch reference; ordinary automatic completion holds
them until fresh explicit retirement authority. Their
useful changes still receive the same native landing ownership as named lanes.
Native completion rechecks the terminal detached identity before inventory and
records the exact wave, empty branch, HEAD, source and inventory path in its
landing owner. It escalates after that observation without target preparation,
even when the inventory establishes coverage. Re-reading completion preserves
that owner and the original receipt; changed HEAD or branch cannot inherit it.

Residual classification and apply support `--wave-id <fresh-owner>`. They bind
the census, complete classification and useful-work ledger to distinct bounded
operation IDs. `--protect <exact-path>` retains additional live or preserved
candidates. Each present direct repository with recorded unlanded history or
WIP has a native landing stub in the wave's useful-work JSON, with source
branch/head, local commits, changed paths
and patch hashes. Stopped Mu remains protected for its later owner.

Legacy preservation still requires safe fast-forward. Fresh explicit retirement
supports exact detached and divergent checkouts, standalone clones with no
other registered owners, and native archives with their original successful
move receipts. Their landing owners must reconcile actual useful work.
Archival never counts as integration.

Only committed foreground `workingrcx_fleet_apply.py --residual --wave-id ...`
plan/apply/verify may act on the fleet after native merge and PRIMARY sync. Use
the plan's exact classification hash, authority commit, batch and destination.
Each operation is consumed once. Prior R1/R2 and September 13 plans, receipts
and operation roots remain immutable.

The observed macOS retirement failure on a `0555` source root has a bounded
native permission transition. After independent archive/index/history recovery
and consumed-once admission, retirement opens the exact directory without
following links and matches its device, inode and original mode. A durable
restoration-intent record precedes temporarily adding only owner-write (`0755`).
The same descriptor restores `0555` after rename, including exceptions before
or after the move. Child modes/bytes, ownership and ACLs are not edited. Full
destination and original admin manifests must still match before exact Git
registration removal. Public verification checks original archived permissions,
destination content/modes, raw index/history and restoration evidence. An
interrupted restoration leaves an INCOMPLETE owner and independent original-mode
recovery; it grants no retry and cannot be reported as retirement.

The read-only-source wave binds PR1319 predecessor indices 2, 7, 8, 9, 14 and 17
to their exact original paths. Census `--readonly-predecessor-plan` records
current identity, permissions, idle-owner checks and independent recovery.
Indices 7–9 additionally verify the unchanged consumed permission-failure claim,
receipt, source/admin manifests and recovery. Index 2 permits only its carrier's
landed HEAD advancement with the original inode, branch and admin identity.
R3 additionally names exactly the stopped read-only-source R1 and R2 carriers
through `--readonly-stopped-manifest` and `--readonly-stopped-r2-manifest`.
Their separate manifests bind the preserved packets and terminal receipts, staged
candidate blobs, raw indices, original HEAD/admin and spent lifecycle records.
R1 stopped before review; R2 passed review and tests but stopped on a
root-authored evidence probe that rejected the native commit-ready status.
Each requires its own recorded terminal state and manifest binding.
Census proves standalone recovery without altering
those inputs, including disabling Git diff's automatic index stat-cache refresh
as well as optional locks. APPLY recreates durable recovery and verifies the same bindings
before relocation. A changed file, raw index, receipt, owner or live process
holds that source independently of eligible peers. Both uncommitted action
plans are preserved evidence and grant no action authority. The governing
packet remains unchanged by implementation; the declared evidence probe uses
the existing launcher lifecycle projection in memory before strict validation.
Indices 14 and 17 retain prior explicit protection and useful-work owners;
this packet supplies no individual release justification. All unlisted sources,
locks, PRIMARY, separate dev, stopped Mu, preservation parent and active carrier
remain held. Fresh operations inherit all prior useful-work ledgers and exact
intent coverage without closing them or resetting exhausted lifecycle attempts.

### Explicit historical-source retirement

Census and classification accept `--retirement` with a fresh residual wave.
The actual September 23 retirement wave binds exact predecessor
`a76ccb9b238b45474946b93a5f3d3be1b07a8b93`. Non-ancestry is a history relationship,
not missing-code evidence. Coverage records comparison blobs and exact reverse
binary-patch checks against independently materialized dev files. Unmatched
hunks retain review ownership; inherited owners and HELD journal intent are not
closed by current-checkout equality. Work remains under the existing cleanup
task, with no speculative wave per folder. Stopped Mu, PRIMARY, the active
carrier, base checkouts and canonical preservation roots remain protected.

After observed identity drift, renew through a complete native retirement
census and a distinct wave. Classification requires
`--retirement-predecessor <exact-comparison-commit>` for actual-fleet successors;
it binds that predecessor, wave, raw census hash and canonical fleet/anchor.
Every recorded useful-work comparison must use that predecessor. The original
September 23 wave remains readable with its original authority and cannot be
rebound through renewal. A supplied JSON binding grants no live action rights.
Planning checks the binding and derives both useful-work ledgers exactly from
classification. The fresh plan pins their hashes; foreground apply and verify
require committed bytes, index and mode for the complete authority, including
the coverage ledger. Native merge, ancestor checks and synchronized PRIMARY
remain mandatory before any public apply.

The September 27 observation found device `16777231` where the September 26
census recorded `16777229`; matching inodes and modes did not authorize a
substitution. The first old public batch was consumed as 12 independently
verified HOLDs, with zero retirements or registration change. Retain that batch,
its receipts and every old artifact unchanged; do not spend remaining stale
batches. A fresh full census supplies current identities and fresh operation
IDs derived from its new classification hash and wave. Current identity checks
remain read-only evidence; any later device/inode/mode, HEAD, index, ownership
or source drift still holds the affected target at action time. A retained
carrier can receive new conditional retirement authority without replaying its
ESCALATED completion. Inherited landing owners and protected WIP remain open.

The fresh plan admits `RETIRE_WORKTREE`, `RETIRE_CLONE` and `RETIRE_ARCHIVE`.
It preserves raw source bytes, symlink targets, modes, index/admin bytes,
index-only blobs, refs, reflog history, declared stashes and journal directories.
A history bundle is verified and imported in an empty standalone recovery Git
directory. Git's read-only `rev-list --single-worktree --objects --indexed-objects` traversal also
enumerates cache-tree objects and their descendants that neither history nor
staged blobs necessarily retain. A separate `index-objects.pack` carries that
closure into recovery; object identities, original raw index bytes (including
shared indices), and strict standalone `fsck --full --strict` must agree without
alternates. Neither source nor preserved index is refreshed or normalized to
make recovery pass. The original index and objects are checked independently
before source removal. Source preparation never fetches, merges,
checks out or synthesizes a branch in the historical source.

Fresh classification can also name individual absent registrations with repeated
`--missing-registration <exact-source-path>` arguments. Each must resolve to one
canonical common-dir `worktrees/<admin>/gitdir` pointer and one matching Git
registration. `RETIRE_MISSING_REGISTRATION` binds the original admin inode,
HEAD/ref bytes, raw index and full admin manifest, reflogs, indexed-object closure
and HEAD history. Symbolic owners also retain exact loose/packed-ref storage
and branch-reflog archives; original HEAD and branch reflogs are restored in
the independent recovery repository. An absent source is never classified clean: its unstaged and
untracked bytes remain unknown. Every such source retains a useful-work owner;
staged differences require exact comparison to dev and historical receipts,
without treating a byte difference as proof of missing production behavior.

The admin-only action uses the same independent bundle/index-object recovery,
strict fsck, process/lock/native-owner checks and consumed-once PRIMARY boundary.
It preserves the raw admin archive and symbolic or detached HEAD in standalone
recovery before `git worktree remove <exact-absent-source>`. It creates no
worktree snapshot or replacement checkout and makes no directory-loss recovery
claim. Source reappearance, changed pointers/index/history, ambiguous owners or
failed recovery hold that individual target. Verification rereads recovery,
the original consumed claim, exact registration delta and admin absence.

The September 27 missing-registration wave may additionally name only the
enumerated historical sources with `--historical-source <exact-path>`; these
remain subject to the existing present-source preservation and liveness checks.
The canonical `WorkingRCX-preservation` parent remains protected. The exact
unregistered empty `WorkingRCX-worktrees` container uses
`RETIRE_EMPTY_CONTAINER`: its device/inode/mode, empty contents and registration
absence are checked again within the same terminal boundary. It requires no Git
history synthesis. No wildcard release, force/prune, original journal rewrite,
spent operation replay or lifecycle-budget reset is permitted.

`bind_terminal_retirement_identity` binds that source and preservation to
surviving PRIMARY. `execute_terminal_retirement_once` retains the existing
shared lock, fresh fetch, PRIMARY behind-zero check and durable consumed claim.
Active-checkout and PR callers retain their ordinary symbolic-branch and
never-behind contract. Identity, original owners, liveness, source bytes,
independent recovery and refs are rechecked under the terminal lock.

The action renames the exact source into its fresh operation directory, then
uses `git worktree remove` on the single absent registered source. It never
uses force or prune or deletes branch/stash history. A clone is preserved by
rename without a canonical registration removal. `RETIRED` requires the exact
registration delta and verified recoverability. `MOVED` remains archival only.
The raw snapshot retains its original `.git` bytes; inspect its independent
Git recovery with `git --git-dir <operation/row/recovery.git> --work-tree
<operation/row/worktree> ...`. Original administration is also retained in
`gitdir-before.tar`; the snapshot is not silently rewritten into a new checkout.

The captured dangling direct-bus `bridge_config.json` adapter links are retained
verbatim while their destinations remain absent. Captured FIFOs under the saved
`test_metadata_rejects_fifo_wit0` pytest directories are archived as FIFO
metadata, never opened for payload. Whole-tree liveness/open-file checks still
apply. Unknown links, other special files, live owners and ambiguous journals
hold individually. Relocated lock metadata may retain its original `lock_path`
only when the fresh authority binds the original consumed native move receipt,
terminal claim and exact archived record bytes. An arbitrary old path is not
historical ownership evidence. Both lock and status PID reuse require immutable
receipt-bound records and repeated OS process-creation observations proving the
current process began after preservation. Missing, conflicting or ambiguous
creation identity remains a HOLD. No process is terminated by reconciliation;
actual flock, whole-tree process and open-file fences still apply.

The observed PREPARED original sync owner requires unchanged path, HEAD, inode,
history and marker, no published or marker-matched stash, and no transition
beyond PREPARED. A device transition requires an explicit fresh reviewed
`prepared_owner_bindings` plan entry: journal path/hash, original owner and
transaction, original identity, exact current identity, and new wave/predecessor/
census authority. Action-time identity checks still require the current device;
the old journal and device remain immutable evidence. Its journal remains
unchanged and unresolved; the fresh retirement mapping grants no recovery replay.

Native fleet and completed lifecycle archives retain their original receipts,
landing owners and spent operation/attempt budgets. An immutable separate
retirement mapping permits lifecycle inspection to verify the new recovery and
report retired registration without recreating the old destination or changing
the original completion receipt. Public `--verify` independently rereads the
archives, recovered index/history, consumed terminal claim, original owners,
source absence and exact registration outcomes. Foreground apply/verify after
landing and PRIMARY synchronization remains required; Phase B reports no live
retirement or completed useful-work integration.

Earlier HOLD and INCOMPLETE operations are also indexed by their original
source identity. Their landing owners and preservation hashes remain in the
fresh census, useful-work ledger, plan and recovery proof, even when current
source changes are already covered. Retirement verifies those original receipts
and preserved artifacts without resolving or relabeling their obligations.

## Safety and preservation

Native control state comes from direct lane buses. Saved pytest repositories
under scratch retain their status/lock bytes as evidence. Available flock plus
coherent dead-owner metadata is historical evidence; separate whole-tree
process and open-file checks remain mandatory. Recovery finish records must
match their actual producer schema, including inactive state, cleared child
command, finish timestamp and consistent outcome. Live or ambiguous owners
remain protected.

The shared preservation admission also recognizes abandoned recovery owners in
the observed `tier3_delegate_scope_validation`, `tier3_waiting_on_agent` and
`tier2_fixing` producer schemas. A complete, coherent direct-bus record must
retain its original invocation, task, wave, timestamps and attempt counters.
Its positive owner PID and any recorded child must be absent; native locks,
whole-tree process references and open files must independently pass the
existing checks. Unknown fields, contradictory child/command/state evidence,
missing identity, changed bytes or uncertain probes remain individual HOLDs.
Neither elapsed age nor `active:true` nor a missing PID grants permission.

Admission records the original status and hash, lock observations, manifest
binding and fresh process/open-file evidence in the action's `process_checks`.
It never finishes the original invocation, edits its status/log/claims, resets
attempts, or declares its useful work landed. Preservation archives and the
transaction checks retain those bytes through sync and relocation. Native
completion uses the same admission, still requires useful-work coverage and
registered-owner exit, and retains its original finite completion budget.

For the September 23 orphan-owner wave, the committed `*_apply_plan.json` and
`*_orphan_owner_evidence.json` bind the exact source identities, inherited useful
work and consumed predecessor mappings. The foreground owner must first verify
native landing and supported PRIMARY synchronization, then run each new
operation's public `--apply` once and its matching `--verify`, using the exact
classification SHA256, landed authority commit, batch and operation root from
that plan. TASKS row38 carries the expanded commands. Record each actual
MOVED/HOLD/INCOMPLETE outcome, source absence, preserved index/bytes/history,
directory and behind-dev counts, and remaining landing owners. A recorded
individual hold permits eligible peers to continue; an interrupted or consumed
operation must never be replayed. Update the existing tracker and continue the
production queue. The old reader diagnosis, source84/source196 journals,
dangling bus links, FIFO and stopped Mu remain with their existing owners.

Only the captured Spotlight `mdworker_shared` executable can qualify for a
read-only indexing exception. Every reported process must include its command
and at least one complete descriptor. The entire `lsof` field stream must be
newline-terminated and complete before any reader qualifies, for exits 0 and 1.
Every descriptor must be numeric, read-only and regular, match the current
inode/device/path, and have stable content. Writers, cwd/root descriptors,
unknown readers and incomplete `lsof` results remain HOLDs, including trailing
process records with no descriptor. Symlink aliases, unreadable entries,
nested mounts and unsupported special files require exact external preservation
resolution. Only fresh explicit retirement admits the captured dangling adapter
links and saved pytest FIFOs described above.

Tracked deletions retain explicit absent-path intent in admission, the native
journal and stash evidence, even for a tracked generated report. Missing stash
keys cannot substitute for that intent or for any present admitted content.
No generated report is restored as a documentation requirement.

Inventory takes the union of HEAD-to-index and index-to-worktree changes.
An AD path (staged addition, deleted worktree file) is retained even when its
net HEAD-to-worktree diff is empty. Deletion intent in either component also
retains a transient deferred report in journal/stash preparation. Snapshots
bind the added index blob separately from the absent worktree path. Exact
non-overlap restoration reproduces both components; overlap keeps that same
intent in the verified HELD stash while the checkout takes the landed bytes.
The captured Source84 regression uses its original blob and report path in
disposable repositories through shared fleet admission. It grants no recovery
or replay authority over Source84's old PREPARED journal or source196's HELD
journal and useful hunks.

The shared WIP sync transaction handles staged deletions with a whole-index
stash only when its declared paths own all tracked WIP, avoiding Git's index-only
pathspec validation. For AD, `stash push` also resurrects the absent blob without
a pathspec. The transaction constructs a standard two-parent stash from the
original index and the actual unstaged binary patch applied to a temporary index.
It verifies both fingerprints and rechecks HEAD, index and WIP before storing
the predeclared marker, then isolates only the declared paths with `git restore`.
AD isolation and restoration touch only the index, preserving the absent
worktree path and its original parent directories without a create/delete cycle.
The existing PREPARED recovery handles interruption before or after isolation.
Ordinary path-filtered stashes use literal paths. Untracked/ignored evidence and
existing held stashes retain their original safeguards.

Stash equality uses Git's regular-file mode representation (0644 or 0755),
alongside exact base, index, size and content hash. Admission and archives keep
the original filesystem permissions, including 0600. Native restoration accepts
only exact restored index/content and the corresponding Git-created mode before
restoring those saved permissions. Full transaction verification then compares
the original filesystem modes; arbitrary permission drift remains a HOLD.

The residual validator compares untracked evidence to the same derived prepared
transaction state. This admits the exact native producer's bound behind-dev
signal removal, while unrelated file, index, stash or permission drift still
fails. Marker filenames alone grant no exception.

## Recovery and late supervisor continuation

Step 8 retains the failing hook command, exit or timeout outcome, and bounded
stdout and stderr. Each stream keeps up to 6,000 characters, including assertion
context when noisy prefixes or trailers require truncation. Recovery records
the latest shell iteration's last four command results in its durable attempt
log before the next diagnosis. Each result includes the bounded command text,
full command SHA256, position, outcome, exit code, block/timeout reason and both
output streams; omitted command counts remain explicit.

The next planner receives those diagnostics separately from the original
failure identity. A nonzero shell exit contributes evidence but never marks
recovery successful. The existing finite iteration budget, command/path/edit
guards, verification and outer retry/receipt ownership still apply. A correct
edit without a separate verification command requests the original gate retry;
it does not certify that gate as passed.

Native growth-cap settlement derives all three counts from the projected Git
index: tests, tools and `mu/docs/**/*.md`. It adds only the actual shortfall to
the immutable HEAD caps and appends canonical same-wave provenance. The
committed algorithm v2 producer derives the lifecycle helper/test/doc delta
for the current wave; an older candidate's numeric caps or override comments
cannot supply that authority. Untracked files do not
grant cap authority. Retry requires the exact whole-file HEAD preimage or
generated postimage in both index and worktree; manual provenance, surplus
caps and unrelated edits remain rejected. A committed same-wave bump cannot
be applied again.

Retained native pytest scratch is immutable recovery evidence. A pre-existing
dangling link is admissible when its resolved missing target remains inside
scratch. Its exact link text, realpath and surrounding manifest/inventory are
still bound to the checkpoint; new, deleted, changed or escaping aliases and
Git-control drift fail closed. Unreadable and special targets remain rejected.
The recovery delegate returns code edits and the native validator owns test
execution. Its explicit `--basetemp` binds new fixtures to that invocation's
temporary directory, including when inherited pytest options request a
different location. This does not exempt a new repository scratch subtree or
delete retained evidence.

Common-directory recovery selects the recorded worktree owner before
reconciliation. A foreign pending journal is retained byte-for-byte, including
its stash, while eligible peers can synchronize. The original owner still has
to pass filesystem identity, branch, HEAD, snapshot and stash checks.

After merge and PRIMARY synchronization, the committed native command can
recover a retained owner's PREPARED or HOLD journal, including a stash created
before its object ID was published:

```sh
python3 mu/tools/executors/worktree_lifecycle.py --record <exact-transaction-manifest> --recover-sync --authority-commit <landed-repair-commit>
```

This convenience command delegates to `workingrcx_fleet_apply.py --recover-sync`
in a fresh interpreter. It shares the existing fleet recovery claim/result
rather than creating another recovery authority. It verifies all eight landed
dependencies plus the lifecycle consumer, committed/index bytes and modes,
PRIMARY, idle owner and journal identity before claiming one recovery attempt.
The common-directory claim/result survives the source. Interrupted attempts
cannot replay. A completed result rechecks retained transaction state on read.
Only the native transaction may retire its own temporary stash after verified
restoration; overlapping WIP remains held. Historical fleet intents, receipts
and original preservation evidence are unchanged. Subsequent fleet actions
need fresh compatible committed authority.

The launcher accepts the exact native pre-supervisor packet status and a
tracker note regenerated by the Phase B producer. The terminal receipt binds
the entire candidate, package and sealed latest-finding checkpoint, in addition
to config, contract, base and routing authority. Worktree/index equality and
the unclaimed receipt are required. Changed notes, candidate bytes, executable
modes, findings, packages and claimed receipts cannot resume.

For a new native STUB with candidate authority, the builder includes the exact
same-wave `reports/deferred/non_blocking/<wave>_bridge_nonblockers.md` path in
the candidate allowlist and immutable packet scope before locking. Phase B may
produce it when a finding is deferred and remove it on GO. Absence requires no
placeholder or restoration. Other-wave reports and unrelated source paths
still fail the candidate scope guard. Existing locked contracts cannot acquire
this additional path through a relaunch.

After a late supervisor rejection, one additional native repair cycle receives
the full newest finding. Its sealed checkpoint consumes completed implementer
ownership and carries the finite budget across restarts. Another rejection
retains the newest finding as an explicit exhausted owner, with no obsolete
implementer or checkpoint replay.

Completion evidence includes actual physical/behind counts, per-target source
absence or retained current ref, verified byte/index/history preservation,
destinations, and unresolved useful-work/PR owners. Code/test success leaves
the live cleanup obligation CURRENT until committed actions verify those facts.
