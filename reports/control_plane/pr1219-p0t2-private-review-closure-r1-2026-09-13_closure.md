<!-- DOC_STATUS: REFERENCE -->
# Exact P0T2 landed private-review durability evidence

Date: 2026-09-13. Task: `[ROLES-ALL-CODEX-PR1219-P0T2-PRIVATE-REVIEW-DURABILITY]`.
Wave: `pr1219-p0t2-private-review-closure-r1-2026-09-13`. Class: `MAINTENANCE`.
Status: **CURRENT / LOCAL EVIDENCE; native review and landing pending**.
The [locked native packet](pr1219-p0t2-private-review-closure-r1-2026-09-13_2026-09-13.md)
governs this existing slot. Its 2026-09-13 TASKS tracker note is the sole
authority for the packet's L4 fields.

The retained findings have landed protections and fresh passing focused tests.
This wave documents that evidence and reconciles the queue; implementation
credit belongs to these ancestor merges:

| Landed implementation | Exact merge | Credit |
| --- | --- | --- |
| PR #1291 | `fdfc58d52c717785a5696a8c3d36f9c934ee0030` | Prepared review authority binds candidate bytes, modes and index blobs during recovery. |
| PR #1294 | `cdf2e02507cde0a3f1909ed00177ab1c474155a9` | Private actors have durable pre-invocation ownership and sealed-success continuation. |
| PR #1295 | `e8bb22ee251c5bf81f7ca6d98651fd507e508257` | Reentry-private review, findings and runtime context survive correction and retry errors. |

## Exact retained requirements and current source

Read-only PRIMARY evidence is under
`reports/archive/control_plane/p0t1-terminal-identity-r2-evidence-2026-09-13/`.
`p0t2_existing_landed_overlap.json` retains the original P0L round-2 reviewer
findings 5/6: a private mutation could escape before the first pending-review
save, and successful reentry remediation followed by retry failure could erase
that pending state. Its unmerged/look-ahead wording is dated evidence.
`p0t2_final_landed_overlap.json` refreshes the comparison on PR #1301's actual
merge. Neither archival file was copied into this candidate or used as launch,
checkpoint, receipt or review authority.

The PRIMARY-only historical
`reports/control_plane/roles-all-codex-pr1219-p0c-private-attr-postfix-resume-2026-08-20_wave_config.json`
supplies the subsumed P0C requirement: after a successful private-attribute
bridge correction, retain the owed extra review across interruption, replay no
completed edit, and advance only on fresh GO. Its original example uses GO R1,
REQUEST_CHANGES R2 and `max_bridge_rounds=2`. P0C stays
`SUBSUMED_BY_P0T2 / SUPERSEDED_NOT_COMPLETE`, not a separate launch or merge.
Historical model selections and launch instructions are not current authority.

All source references below are at comparison commit
`8e7c32a1438c21d47337ad16c77e9cec4bcb5ab6`.

| Retained obligation | Current landed guard and caller in `mu/tools/executors/phase_b_executor.py` |
| --- | --- |
| Finding 5: own the private mutation before it can escape. | `_owned_implementer`, line 10504, builds the exact identity/context and owed-review checkpoint. Its `IN_FLIGHT` transition is saved at line 10550 before yielding to the actor at line 10559. The actual initial/reentry private invocation uses `_owned_implementer(kind="private")` at line 11055 with `_private_attr_pending_review_step(reentry=...)`, defined at line 10929. |
| Finding 5 / P0C: seal success before fallible bookkeeping, retain review, and never replay the completed actor. | The success outcome is selected at line 10567 and saved at line 10574 before finalization. `_finalize_implementer_success`, line 3369, completes bookkeeping and, on private recovery, prepares and seals the owed review. Public resume at line 9975 finalizes and returns `continue_phase_b` with the checkpoint digest; prepared recovery at line 11517 consumes the owed review. Ambiguous `IN_FLIGHT` fails closed at line 9942; it does not automatically complete a crashed actor. |
| Finding 6: remediation/retry errors must not erase owed reentry review. | `_save_private_attr_pending_review_state`, line 10943, carries ownership, `reentry_findings`, decisions, runtime pre-push context and review artifact paths. The actual reentry gate-error branch, lines 13577-13579, calls `_clear_state` then returns the error. `_clear_state`, line 3833, preserves reentry-private checkpoints unless terminal success is explicitly supplied; this error path uses the default false. `_has_reentry_private_attr_checkpoint`, line 14543, recognizes explicit and nested correction authority. The correction's gate retry at line 10998 also returns errors without discarding that state. |
| Preserve PR #1291 prepared review authority and P0C's fresh-verdict requirement. | `_private_attr_index_snapshot`, line 7774, binds index blob OIDs, content hashes, modes and matching worktree bytes. `_private_attr_prepared_authority`, line 7870, combines that with invocation/candidate identity; `_validate_private_attr_prepared_state`, line 7888, rejects changed authority. `_run_private_attr_remediation_bridge_review`, line 11083, retains the extra private-review budget and routes the fresh verdict; old GO does not satisfy the owed review. Prepared reentry recovery at line 11517 consumes the owed private review before continuing. |

## Fresh Phase B-local evidence

The unchanged public regressions were rerun once for this class-reconciliation
reentry, including all parametrizations:

```bash
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_phase_b_executor.py --tb=short -k 'test_inflight_implementer_public_resume_keeps_one_owner or test_implementer_success_sealed_before_collection or test_reentry_private_public_resume_preserves_owed_review_and_guard or test_reentry_private_failed_correction_preserves_authority_without_replay or test_reentry_private_finalizer_failure_retains_sealed_success or test_reentry_private_gate_rerun_preserves_correction_context or test_reentry_private_question_retains_context_and_refuses_correction'
```

Reentry result: **exit 0; 28 passed, 1184 deselected in 53.70s**. The earlier
implementation pass recorded 28 passed, 1184 deselected in 53.35s. Existing fixtures used
ordinary external OS temporary directories; no repository scratch log, temp
override or Hypothesis store was introduced.

| Existing test in `mu/tests/tools/test_phase_b_executor.py` | Cases | Observed coverage |
| --- | --- | --- |
| `test_inflight_implementer_public_resume_keeps_one_owner`, line 522 | 5 | Includes private/reentry-private interruption after actor mutation; forced public resume preserves checkpoint/candidate bytes and actor counts, returning `ambiguous_outcome`. |
| `test_implementer_success_sealed_before_collection`, line 538 | 5 | Post-success collection interruption; public resume finalizes with a bound checkpoint digest and unchanged actor counts. |
| `test_reentry_private_public_resume_preserves_owed_review_and_guard`, line 7343 | 10 | Five interruption boundaries with runtime context false/true; one edit, owed reviews and findings retained; runtime scope guard still prevents inappropriate commit readiness. |
| `test_reentry_private_failed_correction_preserves_authority_without_replay`, line 7381 | 2 | Actor interruption/failed correction retain authority and refuse ambiguous replay. |
| `test_reentry_private_finalizer_failure_retains_sealed_success`, line 7400 | 1 | A finalizer error preserves sealed success; later continuation keeps the edit count at one. |
| `test_reentry_private_gate_rerun_preserves_correction_context`, line 7418 | 4 | Normal, actor interruption, sealed-success and explicit-failure gate retry boundaries preserve nested correction/findings/runtime context. |
| `test_reentry_private_question_retains_context_and_refuses_correction`, line 7465 | 1 | Repeated QUESTION retains the same state and findings/runtime context, with no corrective actor or supervisor. |

These are public Phase B regressions with controlled actors/faults and real
checkpoint/file I/O. Source ordering proves the pre-invocation save; the
interruption regression faults inside the actor after its edit. The exact
historical inline scripts, including successful remediation followed by a
second failing gate and the old P0C `max_bridge_rounds=2` transcript, were **not
independently replayed**. The source guards and current public regression
coverage support this bounded closure; they are not an exhaustive crash,
process-lifecycle or broader private-review proof.

## Base, native authority and predecessor evidence

Fresh read-only inspection found carrier HEAD, PRIMARY HEAD, `origin/dev`,
remote `refs/heads/dev` (`git ls-remote`) and the current candidate spec's
`comparison_commit` all equal PR #1301 merge
`8e7c32a1438c21d47337ad16c77e9cec4bcb5ab6`. Its parents are PR #1300 merge
`3ed23cf38edc47eb13e23e5471016f810467b79f` and final head
`0fe48c3a1754d396fb9ef70683b8dd8c4f83ef3f`. Each credited PR #1291/#1294/#1295
merge passed `git merge-base --is-ancestor <merge> <comparison>` with exit 0.
The separate local `dev` ref was not claimed synchronized.

The initial implementation entry recorded only the seeded TASKS change and
native untracked packet. At this class-reconciliation reentry, all five required
paths were already staged and no unstaged drift was present. Both source/test
files still matched the merge byte-for-byte:

| Unchanged file | Git blob | SHA256 |
| --- | --- | --- |
| `mu/tools/executors/phase_b_executor.py` | `893155cd733e2757eddca3c2a59246884260108c` | `e17eaf65beaf78d233546a7731d586d0ba9ee8de25c1c1245ef2fc19d0790944` |
| `mu/tests/tools/test_phase_b_executor.py` | `96a034cb59a93add5b66f388f2dce47430734b62` | `4eb1413e473bd412ba5ddaac4007184cd85dd44da18429bd9ef9e09c336810d9` |

The current carrier is `WorkingRCX-pr1219-p0t2-private-review-closure-r1-20260913`,
branch `jabramsja/pr1219-p0t2-private-review-closure-r1-2026-09-13`, with bus
`.agent_bus-pr1219-p0t2-private-review-closure-r1-20260913`. Its fresh routing
record was created at `2026-09-13T20:04:02+00:00` and binds this exact wave,
packet, comparison and five required paths plus the optional same-wave
nonblocker. Current Phase A reviewer
`phase-a-r1-18cf2827--r1-reviewer-4112c147` returned GO; its reader was synthetic,
not a second independent review. The selected implementer/reviewer/pager are
Codex with the bus's `gpt-6-astra`/`max` configuration; commit is providerless.
No new launch, receipt/counter reset or predecessor self-handoff replay occurred
inside this implementer.

The PRIMARY-only `terminal_closeout_observation.json` in the archive above
records PR #1301 merged at `2026-09-13T19:35:02Z`, native `commit_succeeded` at
`19:38:37.739153Z`, pane `%46` exit 0, absent owners and retired worktree/branch.
Fresh worktree inspection found no registered predecessor R2 carrier, and
`ps` found none of its recorded owner PIDs (28979, 29341, 5073, 78125).

Historical final CI is credited **only to head
`0fe48c3a1754d396fb9ef70683b8dd8c4f83ef3f`**: seven checks SUCCESS; green-gate
run `34777230279`, job `103777456749`, completed `19:33:41Z`, with 11689 passed,
22 skipped, 6 warnings in 702.90s and separate 1/515/149 passing gates. The
initial 1960-test result in 340.59s belongs to the initial three-file
reconstruction, before later same-PR routing/QUESTION and timeout-fixture
follow-ups. It is not evidence that every final follow-up had that local run.
Neither historical result is this wave's CI or a fresh GitHub review clearance;
the predecessor's final review request returned no clearance within 59s before
native clean-head/CI merge policy proceeded.

## Queue, preservation and remaining native work

The canonical same-wave TASKS note now declares **MAINTENANCE**, with
`no_op_proof` for the five documentation/governance paths and a
`defer_reason_code`. The packet header derives that class from TASKS, matching
the launch-bound candidate specification, selector metadata and this report.
The inherited supervisor package had declared L4_ENABLER because the packet
lacked a class header and the top-level routing record omitted `wave_class`.
The landed `_resolve_phase_b_wave_class` in `mu/tools/executors/phase_b_executor.py`,
line 5987, reads the explicit header first; `_refresh_phase_b_package_governance`,
line 6000, reloads it before native packaging. These are existing source paths,
not new implementation in this maintenance wave. The outer Phase B owner must
regenerate the package, tracker-derived evidence and affected native reviews;
the inherited package is not claimed revalidated by this implementer.

TASKS header, Binding order, Parallelism rule, task bodies and native tracker
notes agree: P0T1 row 34 **LANDED PR #1301**; the exact rich P0T2 row 35 remains
**CURRENT until native landing**; P0T3 is immediately NEXT, then P0T4, P0R2,
P1-P5 and every later recorded identity, with Mu production before optimization.
Row 35 retains inline `Task: [NEXT-CODEX-POST-REDTEAM]`, exact Wave ID,
`Class: MAINTENANCE`, `Category: PROGRAM QUEUE` and the canonical open packet.
Native selector execution belongs to the outer executor; this implementer did
not run or change the selector.

Held TASKS stash `8271020746511cb9a7917f584dc23766660072de` was present; it and
all older stashes/stopped carriers remain untouched. Open stopped PR #1284/#1298
retain their recorded disposition. Consumed fleet outcomes remain 1 MOVED,
3 INCOMPLETE and 407 prior HOLDs, without replay. The late P0T1 bootstrap-exception
review remains deferred/nonblocking under P0T1; observed post-retirement Claude
pager fallback stays with existing P0R2. P0T3 fast-root capture, P0T4's semantic
checker matrix, findings 15-17 and broader private-review variants are excluded.

Invariant tuple: tracked debt **5 -> 5**, net host semantic delta **0**,
runtime/substrate delta **0**, supported by the documentation-only diff and
unchanged ledger/source bytes; no fresh ratchet run or Mu/L4 completion is
claimed. The native Phase B owner still collects the same-wave indicator and
derives packet fields from TASKS, then performs candidate/review/staging gates.
Independent reviews, supervisors, pre-push, current-wave CI, merge and PRIMARY
fast-forward are outer-executor work, not completed Phase B-local validation.
