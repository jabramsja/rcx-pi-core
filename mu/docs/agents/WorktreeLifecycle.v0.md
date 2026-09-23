<!--
DOC_STATUS
TYPE: REFERENCE
LAST_VERIFIED: 2026-09-22
OWNER: RCX Core Team
FOR_CURRENT_STATE: See STATUS.md and TASKS.md
GROUNDING_TESTS: mu/tests/tools/test_worktree_lifecycle.py, mu/tests/tools/test_commit_executor_post_merge_cleanup.py, mu/tests/tools/test_launch_wave.py, mu/tests/tools/test_recovery_gate.py
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
closeout retains the source and its correction owner. Post-merge PRIMARY sync
loads the exact landed dependencies in a fresh interpreter before calling the
existing identity-bound, locked transaction API. Foreign journals remain with
their recorded owners. Replacement coverage uses an actually synchronized
surviving checkout; a dirty stale local dev checkout remains explicitly stale.
The recorded R3 recovery enabler carries transaction R2 as its original plan
owner and cannot fabricate a new plan or restart consumed operations.

The child writes its log and receipts in the common directory and uses surviving
PRIMARY as its cwd. Escalation uses the existing Codex pager at an identity-bound
surviving root. Pager errors have their own durable receipt. It never writes a
pager event into a retired source.

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
have no symbolic local branch reference and remain held for retirement. Their
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

Standalone clones and divergent branches remain individually held
where canonical registration, comparison objects or safe fast-forward cannot
be proved. Their explicit landing owners must reconcile actual useful work.
Archival never counts as integration.

Only committed foreground `workingrcx_fleet_apply.py --residual --wave-id ...`
plan/apply/verify may act on the fleet after native merge and PRIMARY sync. Use
the plan's exact classification hash, authority commit, batch and destination.
Each operation is consumed once. Prior R1/R2 and September 13 plans, receipts
and operation roots remain immutable.

## Safety and preservation

Native control state comes from direct lane buses. Saved pytest repositories
under scratch retain their status/lock bytes as evidence. Available flock plus
coherent dead-owner metadata is historical evidence; separate whole-tree
process and open-file checks remain mandatory. Recovery finish records must
match their actual producer schema, including inactive state, cleared child
command, finish timestamp and consistent outcome. Live or ambiguous owners
remain protected.

Only the captured Spotlight `mdworker_shared` executable can qualify for a
read-only indexing exception. Every reported process must include its command
and at least one complete descriptor. The entire `lsof` field stream must be
newline-terminated and complete before any reader qualifies, for exits 0 and 1.
Every descriptor must be numeric, read-only and regular, match the current
inode/device/path, and have stable content. Writers, cwd/root descriptors,
unknown readers and incomplete `lsof` results remain HOLDs, including trailing
process records with no descriptor. Symlink aliases, unreadable entries,
nested mounts and special files (including retained FIFOs) require exact
external preservation resolution.

Tracked deletions retain explicit absent-path intent in admission, the native
journal and stash evidence, even for a tracked generated report. Missing stash
keys cannot substitute for that intent or for any present admitted content.
No generated report is restored as a documentation requirement.

The shared WIP sync transaction handles staged deletions by using a whole-index
stash only when its declared paths own all tracked WIP. This avoids Git's
index-only pathspec validation while retaining staged/unstaged intent. Ordinary
path-filtered stashes use literal paths. Untracked/ignored evidence and existing
held stashes retain their original safeguards.

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
