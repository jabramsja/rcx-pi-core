# Deferred: Post-Merge Supervisor Phase A Non-Blockers

**Source:** SDK agent review (5 agents, --depth full) + 9 bridge rounds (2026-03-21)
**Classification:** NON-BLOCKING (design hardening and pre-existing issues)

## Pre-Existing: Envelope Injection via Regex First-Match

**Source:** Adversary agent (Phase A review)
**File:** `mu/tools/agents/meta_bridge_supervisor.py:785`
**Issue:** `META_ENVELOPE_RE` uses `re.search()` which returns the FIRST match.
If Codex includes an example `BEGIN_META_ENVELOPE` block in its preamble text
(reasoning, quoting the template), that example block is parsed as the real
decision instead of the actual decision block.
**Impact:** Pre-existing in the pre-commit supervisor. Not introduced by the
post-merge design. Affects both modes.
**Recommended fix:** Parse the LAST match instead of the first, or require the
envelope at the end of output with no trailing content.
**Classification:** Pre-existing, not blocking post-merge implementation.

## Design-Level: Sandbox Trust Boundary

**Source:** Adversary agent (Phase A review)
**File:** `reports/control_plane/post_merge_supervisor_plan_2026-03-21.md:49`
**Issue:** `--sandbox danger-full-access` with prompt-enforced read-only is
not a security boundary. The design documents this honestly as "prompt-enforced,
not sandbox-enforced; this is an acknowledged trust boundary, not a security
boundary." No implementation change needed — the constraint model is the same
as the pre-commit supervisor.
**Classification:** Acknowledged limitation, not blocking.

## Design-Level: Ignore Prefix Tuple Consolidation

**Source:** Expert agent (Phase A review), corrected by structural-proof (Phase B review)
**File:** `mu/tools/agents/meta_bridge_supervisor.py:40-58`
**Issue:** Two near-duplicate constants: `DIRTY_STATE_IGNORE_PREFIXES` (line 40)
and `STATE_IGNORE_PREFIXES` (line 51). They contain the same prefixes but in
different ordering. Should be consolidated into a single
`TRANSIENT_PATH_PREFIXES` constant with a canonical ordering.
**Classification:** Code quality improvement. Can land in the post-merge
implementation wave or as a separate follow-on.

## Pre-Existing: TASKS Authorization Prose-Match

**Source:** Bridge R4 (Phase B implementation review)
**File:** `mu/tools/agents/meta_bridge_supervisor.py:check_tasks_authorization`
**Issue:** `check_tasks_authorization` uses regex to find bracketed task IDs in
NOW/NEXT text. A prose mention of `[TASK-ID]` anywhere in those sections
passes the check, even if it's not a task bullet. Both pre-commit and
post-merge modes are affected.
**Impact:** Pre-existing in the pre-commit supervisor. Not introduced by
post-merge implementation.
**Recommended fix:** Parse TASKS.md bullet structure and match only on
task-entry-level `**[ID]**` patterns at line start.
**Classification:** Pre-existing, separate follow-on.

## Phase B Bridge Non-Blockers (R1-R5)

### Gate 5: Shell Variable Resolution Edge Case

**Source:** Bridge R4-R5 (persisting)
**File:** `mu/tools/agents/meta_bridge_supervisor.py:check_pre_commit_gate`
**Issue:** Gate 5 cannot resolve `$SCRIPT_DIR` from shell text. An exec target
like `/tmp/malicious/hooks/pre-commit-doc-check` passes if the canonical hook
file also exists in the repo. Static text analysis cannot evaluate shell
variable expansion.
**Mitigation:** Gate 5 is SOFT (Codex-informed, not blocking). The actual
enforcement is the pre-commit hook itself at commit time. Gate 5 is
defense-in-depth for post-merge routing context.
**Classification:** Trust-boundary limitation. Hardening requires shell
execution or symlink resolution beyond static analysis.

### Gate 1: Same-SHA Feature Branch Edge Case

**Source:** Bridge R5
**File:** `mu/tools/agents/meta_bridge_supervisor.py:check_merge_verification`
**Issue:** If a feature branch points to the same SHA as `refs/heads/dev`,
Gate 1 passes even though the branch name is not `dev`. This is technically
correct (the state IS dev's state) but doesn't enforce the branch-name
invariant strictly.
**Classification:** Low-risk edge case. Post-merge supervisor is manually
invoked; the operator knows what branch they're on.

### Test Count Discrepancy

**Source:** Bridge R3-R5 (persisting)
**Issue:** Codex measures 40 tests in `mu/tests/tools/test_meta_bridge_supervisor.py`,
package claims 55. The 55 count includes `test_pre_commit_receipt.py` (15 tests)
in the same pytest invocation. The targeted file alone has 40 pre-existing +
15 new = 55 tests when both files are included.
**Classification:** Evidence presentation issue, not a code defect.

## Pre-Existing: merge_pr.sh --admin Bypass

**Source:** Bridge Phase B R1 for executor surfaces (2026-03-22)
**File:** `mu/tools/hooks/merge_pr.sh:162`
**Issue:** merge_pr.sh uses `gh pr merge --admin` unconditionally. The executor
plan documents a fail-closed policy (admin forbidden by default), but the
existing merge script doesn't implement that policy. The commit executor
delegates to merge_pr.sh as-is.
**Classification:** Pre-existing in merge_pr.sh. Not introduced by executor
implementation. Hardening of merge_pr.sh to support non-admin merge is a
separate follow-on.

## Executor Slice 1+2 Phase B Bridge Non-Blockers (2026-03-22)

### UPDATE_TRACKER_ONLY Handoff Path — RESOLVED (2026-03-25)

**Source:** Bridge Phase B R2 for executor surfaces
**Issue:** The dispatcher returned `needs_handoff` for commit_executor when
UPDATE_TRACKER_ONLY routed to it.
**Resolution:** Dispatcher now passes `--routing-record` to commit_executor,
which internally prepares the handoff via `prepare_handoff_from_routing_record()`.
For UPDATE_TRACKER_ONLY, defaults to `files_to_stage: ["TASKS.md"]` and
`caller: "update_tracker_only"`. Resolved in wave `commit_pipeline_automation_plan_2026-03-25`.

### Post-Merge Supervisor Trigger After Merge

**Source:** Bridge Phase B R1+R2 for executor surfaces
**Issue:** commit_executor verifies dev checkout but does not trigger the
post-merge supervisor. The full loop (merge → post-merge → route → executor)
requires the post-merge supervisor to be invoked from the commit executor.
This is integration scope (Slice 6).
**Classification:** Not blocked for Slice 1+2 proof.

### Commit State Persistence / Resume

**Source:** Bridge Phase B R2 for executor surfaces
**Issue:** If commit_executor fails mid-pipeline (e.g., CI timeout), there is
no persisted state to resume from. The executor must be re-run from scratch.
**Classification:** Quality improvement. Not blocked for Slice 1+2 proof.
