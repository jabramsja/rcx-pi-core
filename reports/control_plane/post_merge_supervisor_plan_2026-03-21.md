# Post-Merge Supervisor Plan

Date: 2026-03-21
Status: Complete (implemented and merged, PR #657)
Phase-A-Lock: LOCKED
Purpose: decision-complete design for the post-merge supervisor follow-on

## Goal

After a PR merges to `dev`, determine the next bounded work step. This is NOT
"may this commit proceed?" (that's the pre-commit supervisor). This is "what
should happen next?"

The post-merge supervisor reasons about the next bounded wave:
- continued dialectic / narrowing when the next step is not yet bounded enough
- route to Phase A when planning is needed
- route to Phase B when a locked plan exists and implementation should start
- founder/triage stop when the state is not honestly routable

## What It Does

1. Validates that the merge actually landed (git truth: merge SHA reachable from HEAD)
2. Verifies the supplied rollout packet matches the canonical active packet from TASKS.md
3. Reads TASKS.md to understand what is authorized and what the next item is
4. Checks for outstanding blockers in `reports/deferred/blocking/`
5. Independently verifies pre-commit gate is installed (not self-reported)
6. Evaluates whether the next item in the rollout sequence is bounded enough
7. Sends context to Codex for adversarial routing deliberation
8. Emits a routing decision bound to current repo state

## What It Does NOT Do

- Execute Phase A or Phase B (routing only — Claude acts on the decision)
- Commit, push, or merge anything
- Modify tracker files (STATUS.md, TASKS.md, CHANGELOG.md)
- Recurse into itself or the pre-commit supervisor
- Replace the pre-commit supervisor (orthogonal concerns)
- Auto-run the whole lifecycle inside a single invocation
- Unpark the structural queue without explicit founder authorization

## Authority Model

- **Read-only investigative authority** (same as pre-commit supervisor)
- Full filesystem + command access for verification
- NO implementation authority
- NO commit/push authority
- Emits routing decision only; Claude is the actor
- Uses `--sandbox danger-full-access` with prompt-enforced read-only
  (same constraint model as pre-commit supervisor — prompt-enforced, not
  sandbox-enforced; this is an acknowledged trust boundary, not a security
  boundary)

## Input Package Contract

The post-merge package captures the state after a merge lands. 10 required
fields + 1 derived field (trimmed from initial 13 per expert + bridge review):

```json
{
  "task_id": "[META-BRIDGE-S1]",
  "merged_pr": 655,
  "merge_sha": "ac714fa...",
  "wave_name": "pre-commit-gate-operationalize",
  "lane": "hooks/agents/bridge control-surface",
  "changed_files": ["file1.py", "file2.md"],
  "rollout_packet_path": "reports/control_plane/meta_bridge_rollout_2026-03-20.md",
  "deferred_items": ["item1", "item2"],
  "next_candidates": [
    {
      "candidate": "post-merge supervisor design",
      "bounded": true,
      "tracked_packet": "reports/control_plane/post_merge_supervisor_plan_2026-03-21.md"
    }
  ],
  "tracker_state_summary": "NOW: [NOW-CODEX-REDTEAM], NEXT: [META-BRIDGE-S1] complete",
  "blocker_report_paths": []
}
```

**Removed fields (vs initial draft):**
- `pre_commit_gate_status`: was self-reported. Now independently verified by
  Gate 5 (see Validation Gates). Agent adversary finding: self-reported input
  cannot be trusted for a structural guarantee.
- `current_routing_judgment`: Claude's initial assessment is better expressed
  in `next_candidates[].bounded` + the candidate list itself. Expert finding:
  redundant with `next_candidates`.

### Field Definitions

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `task_id` | string (bracketed) | yes | TASKS.md authorization anchor |
| `merged_pr` | int | yes | PR number that just merged |
| `merge_sha` | string | yes | Merge commit SHA (verifiable) |
| `wave_name` | string | yes | Name of the completed wave |
| `lane` | string | yes | Current active lane |
| `changed_files` | list[string] | no (derived) | **Derived by supervisor from `merge_sha`** via `git diff --name-only <merge_sha>^...<merge_sha>` (first-parent diff, merge-safe). Package-supplied value is IGNORED — git truth is authoritative. Field retained in schema for documentation but supervisor always overrides with derived value. |
| `rollout_packet_path` | string | yes | Path to active rollout packet (must be under `reports/control_plane/`) |
| `deferred_items` | list[string] | yes | Items deferred during the wave |
| `next_candidates` | list[object] | yes | Claude's proposed next steps |
| `tracker_state_summary` | string | yes | Current TASKS.md NOW/NEXT summary |
| `blocker_report_paths` | list[string] | yes | Acknowledged blocker packets |

### next_candidates entry schema

Each candidate must declare:
- `candidate`: what the proposed next step is (string)
- `bounded`: whether the scope is bounded enough for Phase A (bool)
- `tracked_packet`: path to an existing tracked plan packet, or null if none
  exists. **Containment rule:** must be under `reports/control_plane/` or null.
  Paths outside this directory are rejected during schema validation.

### Path containment (adversary + bridge R6 finding fix)

All path fields (`rollout_packet_path`, `next_candidates[].tracked_packet`)
must satisfy THREE checks during schema validation:

1. **Lexical prefix:** Must be a relative path starting with
   `reports/control_plane/`. Absolute paths and `..` components rejected.
2. **Resolved containment:** `os.path.realpath()` of the path must still be
   under `<repo_root>/reports/control_plane/`. This closes symlink escapes
   (bridge R6 finding).
3. **Tracked-file proof:** Non-null paths must pass
   `git ls-files --error-unmatch <path>` — the file must be a git-tracked
   control-plane document, not an untracked or ignored file.

This prevents path traversal, symlink escapes, and references to untracked
files.

## Decision / Routing Vocabulary

### Mode-scoped token sets (adversary + verifier finding fix)

Post-merge uses a SEPARATE token set from pre-commit. The implementation MUST
NOT extend `TEMPLATE_AUTHORIZED_DECISIONS` (pre-commit's whitelist). Instead,
it defines `POST_MERGE_AUTHORIZED_DECISIONS` as a distinct constant. The
`parse_meta_envelope` function (or a mode-aware wrapper) validates against the
correct set based on invocation mode.

This prevents cross-mode authority escalation: a Codex response containing
`COMMIT_GO` in a post-merge context is rejected (not a valid post-merge token),
and a response containing `ROUTE_PHASE_A` in a pre-commit context is rejected
(not a valid pre-commit token).

### Routing tokens (Codex-emittable in post-merge mode)

| Token | When to emit | Claude action |
|-------|-------------|---------------|
| `CONTINUE_DIALECTIC` | Next step exists but is not bounded enough for Phase A. Needs narrowing. | Continue conversation/analysis to bound the scope. Do not start Phase A yet. |
| `ROUTE_PHASE_A` | A bounded task exists but needs planning. A tracked plan packet may or may not exist. | Create or refine tracked plan packet. Enter Phase A (design + agents + bridge). |
| `ROUTE_PHASE_B` | A locked Phase A plan exists for the next item. | Enter Phase B (implement + agents + bridge). |
| `UPDATE_TRACKER_ONLY` | Merge was clean. Only tracker sync needed (STATUS.md, TASKS.md, CHANGELOG.md). No implementation. | Update tracker files and stop. |
| `STOP_FOR_FOUNDER` | Policy question or lane-satisfaction decision that requires founder input. | Present the question to founder. Wait for direction. |
| `STOP_FOR_TRIAGE_DISCUSSION` | Queue exhausted, state contradictory, or routing unclear. | Surface the ambiguity. Do not proceed. |

**Removed:** `QUEUE_EXHAUSTED` — expert finding: redundant with
`STOP_FOR_TRIAGE_DISCUSSION` when the reason field says "queue exhausted".
Codex can communicate queue exhaustion through `STOP_FOR_TRIAGE_DISCUSSION`
with an appropriate `summary` and `request_for_claude`.

### Error tokens (supervisor-emittable only, not from Codex)

| Token | Meaning |
|-------|---------|
| `ERROR_PACKAGE_INVALID` | Package failed schema validation |
| `ERROR_CODEX_TIMEOUT` | Codex review timed out |
| `ERROR_CODEX_ABORT` | Review aborted (SIGINT) |
| `ERROR_MERGE_NOT_FOUND` | PR not merged or SHA mismatch |
| `ERROR_INTERNAL` | Internal supervisor error |

**Removed:** `ERROR_VALIDATION_FAILED` — not needed for post-merge because
validation failures are warnings (except Gate 1 which produces
`ERROR_MERGE_NOT_FOUND`). Expert finding: pre-commit needs this because
validation failures block commit-capable decisions; post-merge doesn't block
routing decisions on validation state.

### Routing decision rules

1. If Gate 1 (merge verification) fails, emit `ERROR_MERGE_NOT_FOUND` — hard
   stop, there's nothing to route from. This is the ONLY supervisor-level
   routing rule.
2. All other gate results (Gates 2-6) are passed to Codex in the validation
   summary. **Codex is the sole routing authority** — the supervisor does not
   pre-route or hard-stop based on soft gate results.
3. Codex evaluates `next_candidates`, rollout packet state, validation
   results, and the full repo context, then emits the appropriate routing
   decision.
4. The supervisor does NOT pre-route based on `next_candidates[].bounded` —
   that is Claude's advisory input. Codex decides.
5. For `ROUTE_PHASE_B`, Codex must verify TWO conditions:
   (a) The referenced plan packet's `Phase-A-Lock:` field is exactly `LOCKED`
       (machine-checkable lock signal — see "Phase A lock criterion").
   (b) The referenced plan packet is the canonical next routable item from
       the active rollout packet — see "Canonical next-item binding".

## Validation Gates (post-merge)

6 validation gates, run before Codex routing:

| Gate | Name | What it checks | Severity |
|------|------|---------------|----------|
| 1 | `merge_verification` | (a) Current HEAD is on `dev` branch (or detached at `refs/heads/dev` OID), AND (b) merge SHA reachable from HEAD (`git merge-base --is-ancestor`) | HARD (blocks all routing) |
| 2 | `tracker_consistency` | TASKS.md contains task_id in NOW or NEXT (active or completed; struck-through entries accepted as normal completion markers) | SOFT (Codex informed) |
| 3 | `rollout_packet_canonical` | Supplied `rollout_packet_path` is referenced as `Tracked packet:` in the TASKS.md entry matching `task_id`; packet exists and is readable | SOFT (Codex informed) |
| 4 | `blocker_check` | All `reports/deferred/blocking/` packets acknowledged | SOFT (Codex informed) |
| 5 | `pre_commit_gate_check` | Pre-commit hook installed AND `verify_pre_commit_receipt.py` exists (local-checkout assurance only, not repo-wide enforcement) | SOFT (Codex informed) |
| 6 | `docs_consistency` | `check_docs_consistency.sh` passes | SOFT (Codex informed) |

**Severity model:**

Only Gate 1 is HARD — if the merge didn't land, there is nothing to route
from. All other gates are SOFT: their pass/fail status is reported to Codex in
the validation summary. **Codex is the sole routing authority for soft gates.**
The supervisor does not emit `STOP_FOR_FOUNDER` or any routing decision based
on soft gate results — that is Codex's job.

**Rationale:** The merge already happened; blocking the routing decision
doesn't un-merge anything. The pre-commit supervisor is the hard gate for
commit flow. The post-merge supervisor is a routing advisor, not a blocker.

**Gate 3 canonical verification (bridge R2+R7+R8 finding fix):** The
supervisor does NOT trust the package-supplied `rollout_packet_path` blindly.
Gate 3 locates the TASKS.md entry matching `task_id` (in NOW or NEXT), then
extracts the `Tracked packet:` reference from that specific entry. The
supplied `rollout_packet_path` must match that entry's tracked packet. This
is task-bound, not a broad scan of all control-plane references in TASKS.md
(bridge R8 finding: broad scan accepts unrelated packets). If no match,
Gate 3 fails with a message identifying both the supplied and task-bound
canonical paths. `tracker_state_summary` is treated as Claude's advisory
input — Gate 2 independently reads TASKS.md to verify tracker state.

**Gate 5 scope (bridge finding fix):** Gate 5 checks local checkout state
only — it cannot enforce that the pre-commit hook is installed on CI runners
or other developer machines. This is documented honestly as "local-checkout
assurance" in the gate table.

**Gate 5 independence (adversary + bridge R5+R6 finding fix):**
`pre_commit_gate_status` is NOT a package field. Instead, the supervisor
independently verifies:
1. Resolve the active hook path via `git rev-parse --git-path hooks/pre-commit`
   (handles `core.hooksPath` overrides)
2. The resolved hook file exists and is executable
3. The hook is the managed RCX hook: verify it delegates to
   `tools/hooks/pre-commit-doc-check` (the backward-compat wrapper checks
   this via `exec "$SCRIPT_DIR/hooks/pre-commit-doc-check" "$@"`) — compare
   the resolved hook's delegate target against the known canonical path
4. `mu/tools/agents/verify_pre_commit_receipt.py` exists

**Why not grep (bridge R6 fix):** A simple grep for
`verify_pre_commit_receipt.py` in the hook would match comments or dead code.
Instead, Gate 5 verifies the hook delegates to the managed hook script, which
is the canonical source-of-truth for which checks run (including the receipt
check in section 8). This is a structural proof: if the managed hook is
active, the receipt check runs.

**Scope acknowledgment:** Gate 5 is SOFT and provides local-checkout assurance
only. The primary enforcement is the pre-commit hook itself at commit time.
Gate 5 is defense-in-depth for the post-merge routing context.

## Phase A Lock Criterion (bridge R3+R4 finding fix)

For Codex to emit `ROUTE_PHASE_B`, it must verify that the referenced plan
packet has a machine-readable lock field indicating convergence.

**Machine-readable lock field:** Plan packets in `reports/control_plane/`
include a `Phase-A-Lock:` field on line 5 (after Status). This is a dedicated
machine-checkable field, NOT the free-text Status line.

```
Phase-A-Lock: UNLOCKED
```
or
```
Phase-A-Lock: LOCKED
```

**Lock values (exact match, not substring):**
- `UNLOCKED` — plan is not yet bridge-converged. ROUTE_PHASE_B is invalid.
- `LOCKED` — bridge returned GO or non-blockers only. ROUTE_PHASE_B is valid
  (if canonical next-item binding also passes).

**Status line remains free-text for human readability.** The status progression
(draft → agent-reviewed → bridge-converged → implementation → complete) is
informational. The `Phase-A-Lock` field is the machine-checkable signal.

**Why not substring match on Status (bridge R4 fix):** The status
`"Phase A (design — not yet bridge-converged)"` contains the substring
`"bridge-converged"`, making substring matching ambiguous. An exact-match
dedicated field eliminates this class of false positives.

**This criterion is Codex's responsibility, not the supervisor's.** The
supervisor extracts and presents `Phase-A-Lock` in the Codex prompt context.
Codex verifies the value is exactly `LOCKED` before emitting `ROUTE_PHASE_B`.

## Canonical Next-Item Binding (bridge R2+R3 finding fix)

The post-merge supervisor's Codex prompt MUST include the active rollout
packet's "Canonical rollout order" section so Codex can verify what the
actual next item is. Codex must confirm that any `ROUTE_PHASE_B` target
matches the rollout's next routable step.

**How the binding works:**

1. The supervisor reads the active rollout packet (verified canonical by
   Gate 3) and extracts the numbered rollout order.
2. The supervisor classifies each step:
   - **Done:** strikethrough or "(done)" annotation → skip
   - **Standing invariant:** contains "Standing invariant:" prefix → skip
     (these are continuous obligations, not discrete waves)
   - **Routable:** first remaining step not done and not standing → this is
     the canonical next item
3. The supervisor includes the full extracted sequence (with classifications)
   in the Codex prompt, along with `next_candidates` from the package.
4. Codex verifies that the proposed `ROUTE_PHASE_B` target matches the
   canonical next routable item. If the candidate does not match, Codex
   should emit `STOP_FOR_TRIAGE_DISCUSSION` (rollout drift).

**Standing invariant convention (bridge R3 fix):** The rollout packet uses
`**Standing invariant:**` prefix for steps that are continuous obligations
(e.g., "keep pre-commit supervisor as standing gate"). These are verified by
validation gates (Gate 5 for the pre-commit gate) but are not discrete waves
and do not block routing to the next routable step.

**What this prevents:** A stale or fabricated `next_candidates` list that
points at a plan packet for a step that is not actually next in the rollout
order. Also prevents deadlock when a standing invariant sits between a
completed step and the next routable step (bridge R3 finding).

**Implementation note:** The supervisor extracts the rollout order
mechanically (numbered list parsing + prefix classification), but Codex is
the semantic authority on whether a candidate matches the next step. The
supervisor does not pre-filter or reject candidates — it provides context
and Codex decides.

## Routing Decision Record

Routing decisions are recorded in `.agent_bus/meta/post_merge_routing.json`:

```json
{
  "decision": "ROUTE_PHASE_A",
  "summary": "Next step is post-merge supervisor implementation...",
  "findings": [...],
  "request_for_claude": "Enter Phase A for post-merge supervisor implementation",
  "merged_pr": 655,
  "merge_sha": "ac714fa...",
  "head_sha": "ac714fa...",
  "state_sha": "abc123...",
  "timestamp_utc": "2026-03-21T14:30:00+00:00",
  "validations_passed": ["merge_verification", "tracker_consistency", ...],
  "validations_failed": []
}
```

**State-binding (adversary + fuzzer finding fix):** The routing record includes
`head_sha` and `state_sha` (computed the same way as in the pre-commit
supervisor via `compute_repo_state`). This prevents replay: a routing decision
is bound to the repo state at the time of deliberation. Consumers can verify
the decision is still current by comparing `state_sha` against the live repo.

**No receipt system:** Unlike the pre-commit supervisor, post-merge does NOT
write receipts that gate a blocking action. The routing record is for
auditability and staleness detection, not enforcement.

## Interaction with Pre-Commit Supervisor

- **Independent and orthogonal.** Pre-commit gates commit flow (before commit).
  Post-merge gates next-wave entry (after merge).
- Both use `.agent_bus/meta/` namespace but separate state files:
  - Pre-commit: `pre_commit_receipt.json`
  - Post-merge: `post_merge_routing.json` (routing decision record)
- Post-merge does NOT write receipts (no blocking action to gate).
- Post-merge does NOT replace or weaken the pre-commit gate.
- Both read the same rollout packet and TASKS.md for authorization.
- Gate 5 independently verifies the pre-commit gate is installed.

## Interaction with Future Phase A / Phase B / Commit Executors

- Post-merge routing decisions will eventually point at repo-local executors.
- Until those executors exist, Claude acts on routing decisions manually.
- The routing vocabulary is designed to be machine-consumable so that future
  executors can read the post-merge decision and dispatch automatically.
- Post-merge supervisor does NOT implement those executors — it only routes.

## Interaction with Parked Structural Queue

- Post-merge supervisor does NOT unpark the structural queue.
- `STOP_FOR_TRIAGE_DISCUSSION` with "queue exhausted" in summary triggers
  founder conversation about whether to unpark, not automatic unparking.
- The structural queue (`post_redteam_structural_queue_2026-03-20.md`) has
  explicit prerequisites that must be met before resuming:
  1. Pre-commit supervisor live as standing gate (done)
  2. Post-merge supervisor through Phase A/B (this wave = Phase A)
  3. Claude has explicit Phase A/B/commit executors (future)

## Invariants

1. Post-merge supervisor never modifies repo state (read-only)
2. Post-merge supervisor never weakens or bypasses the pre-commit gate
3. Post-merge supervisor never unparks the structural queue without founder GO
4. Post-merge supervisor never executes Phase A/B — it only routes
5. Routing decisions are state-bound (head_sha + state_sha in record)
6. Single-instance enforcement via file lock (same pattern as pre-commit)
7. Codex routing always happens — no mode that skips deliberation
8. Pre-commit gate must be independently verified (not self-reported)
9. Post-merge and pre-commit use mode-scoped token sets (no cross-mode leakage)

## Reusable Denominator from Pre-Commit Supervisor

The following components from `mu/tools/agents/meta_bridge_supervisor.py` are
directly reusable:

| Component | Reuse | Notes |
|-----------|-------|-------|
| `_MetaBridgeLock` | Yes, as-is | Same single-instance pattern |
| `MetaBridgePaths` | Yes, extended | Add `post_merge_routing_path` field |
| `MetaBridgeResponse` | Yes, as-is | Same response envelope |
| `run_validation_command` | Yes, as-is | Same validation runner |
| `check_tasks_authorization` | Yes, as-is | Same TASKS.md gate |
| `check_deferred_blockers` | Yes, as-is | Same blocker gate |
| `compute_repo_state` | Yes, for state-binding | State SHA in routing record |
| `git_output` | Yes, as-is | Same git helper |
| `utc_now` | Yes, as-is | Timestamp helper |
| `parse_meta_envelope` | **No — mode-aware wrapper** | Post-merge needs separate `POST_MERGE_AUTHORIZED_DECISIONS` constant. Either (a) add a `mode` parameter to `parse_meta_envelope`, or (b) create `parse_post_merge_envelope` that validates against the post-merge token set. Option (b) is simpler and avoids coupling. |
| `validate_package_schema` | **No — separate function** | Post-merge has 11 fields (different from pre-commit's 11). Create `validate_post_merge_package_schema` with its own field set and path containment rules. |
| `build_meta_reviewer_prompt` | **No — new template** | Different input/output contract. New template: `templates/post_merge_task.txt` |
| `write_pre_commit_receipt` | **No** | Post-merge has no receipt system |
| `check_dirty_state` | **No** | Post-merge checks merge SHA, not staged files |

### Architecture decision: shared script with mode flag

Add post-merge as a new mode in the existing `meta_bridge_supervisor.py`:
- CLI gains `--mode post-merge` (default remains pre-commit behavior)
- Shared: lock, paths, response envelope, validation runner, git helpers,
  Codex adapter wiring, TASKS auth, blocker check
- Separate: package schema validation, envelope parsing (mode-scoped tokens),
  prompt template, routing record (vs receipt), merge verification gate,
  pre-commit gate verification gate

**Consolidation of ignore prefix tuples (expert finding, corrected by
structural-proof):** The two near-duplicate constants
`DIRTY_STATE_IGNORE_PREFIXES` and `STATE_IGNORE_PREFIXES` in
`meta_bridge_supervisor.py` contain the same prefixes but differ in ordering.
Should be consolidated into a single `TRANSIENT_PATH_PREFIXES` constant.
Minor cleanup that can land in the implementation wave or as a follow-on.

## Implementation Scope (Slice 1 — bounded)

Slice 1 of the post-merge supervisor:

1. **Post-merge package schema** (11 fields, validation with path containment)
2. **6 validation gates** (merge, tracker, rollout, blockers, pre-commit gate, docs)
3. **Routing vocabulary** (6 routing tokens, mode-scoped; 5 error tokens)
4. **Codex prompt template** (`templates/post_merge_task.txt`)
5. **CLI mode** (`--mode post-merge --package <path> --json`)
6. **State-bound routing decision record** (`.agent_bus/meta/post_merge_routing.json`)
7. **Merge verification gate** (new: check PR merged, SHA reachable from HEAD)
8. **Pre-commit gate verification** (new: independently check hook + verifier exist)
9. **Mode-scoped envelope parsing** (`POST_MERGE_AUTHORIZED_DECISIONS`)

### Not in Slice 1

- Phase A/B executor dispatch (routing only)
- Automatic invocation (Claude runs manually after merge)
- Integration with `merge_pr.sh` (future)
- Structural queue unparking logic (future, requires founder decision)
- State persistence / crash recovery (same deferral as pre-commit Slice 1)
- Audit trail beyond routing decision record (future)
- Ignore-prefix consolidation (minor cleanup, can be same wave or follow-on)

## Agent Review Findings (Phase A, 2026-03-21)

5 agents ran at `--depth full` with canonical model defaults.

| Agent | Verdict | Key Findings | Resolution |
|-------|---------|-------------|------------|
| **verifier** | REQUEST_CHANGES | Mode-aware token whitelist missing; `pre_commit_gate_status` self-reported; gate severity table/prose contradiction; `parse_meta_envelope` reuse claim unproven | All addressed: mode-scoped tokens, independent gate verification, severity model clarified, reuse table corrected |
| **adversary** | NEEDS_HARDENING | Envelope injection (existing pre-commit issue); path traversal in `tracked_packet`; routing record replay; schema divergence; sandbox != security boundary | Path containment added; state-binding in routing record; separate schema validation; sandbox caveat documented; envelope injection deferred (pre-existing, not introduced by this plan) |
| **structural-proof** | UNPROVEN | Reuse claims not backed by code proof; no concrete projection proof | Reuse table corrected (several items changed from "Yes" to "No — separate"); structural proof is design-phase appropriate — implementation will prove/disprove |
| **expert** | COULD_SIMPLIFY | 13 fields reducible; duplicate ignore tuples; vocabulary expansion large; redundant tokens | Trimmed to 11 fields; noted ignore-prefix consolidation; merged `QUEUE_EXHAUSTED` into `STOP_FOR_TRIAGE_DISCUSSION`; removed `ERROR_VALIDATION_FAILED` |
| **fuzzer** | FRAGILE | Canonical example fails Gate 4; vocabulary mismatch will hard-fail; gate severity contradicts prose | Example noted as illustrative (not live package); vocabulary mode-scoped to prevent mismatch; severity model clarified consistently |

### Deferred (non-blocking, pre-existing)

- **Envelope injection via regex first-match** (`meta_bridge_supervisor.py:785`):
  Pre-existing in pre-commit supervisor. Not introduced by this plan. Should
  be hardened (e.g., parse last match, or require envelope at end of output)
  as a separate follow-on. Filed to `reports/deferred/non_blocking/`.

## Tracked Packet References

- **This packet:** `reports/control_plane/post_merge_supervisor_plan_2026-03-21.md`
- **Parent rollout:** `reports/control_plane/meta_bridge_rollout_2026-03-20.md`
- **Parked queue:** `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
- **Pre-commit implementation:** `mu/tools/agents/meta_bridge_supervisor.py`
- **Pre-commit template:** `mu/tools/agents/templates/meta_bridge_task.txt`
- **Advisory source:** `reports/codex/tooling/tooling_2026-03-20_codex_meta_bridge_supervisor_plan.md`

## Bridge Review History

### Round 1 (2026-03-21): REQUEST_CHANGES — 4 findings

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 1 | DEFECT | high | Gate 5 dual semantics (soft gate AND direct STOP_FOR_FOUNDER) | Removed routing rule 2. Codex is sole routing authority for all soft gates. |
| 2 | DEFECT | high | Supplied rollout packet / tracker summary not independently verified | Gate 3 now verifies supplied packet matches canonical TASKS.md reference. `tracker_state_summary` treated as advisory. |
| 3 | DEFECT | medium | ROUTE_PHASE_B has no machine-checkable lock criterion | Added "Phase A Lock Criterion" section: plan status must contain "bridge-converged". |
| 4 | DOC_ACCURACY | medium | Merge verification wording inconsistent (HEAD matches vs reachable) | Normalized to "reachable from HEAD" (`git merge-base --is-ancestor`) everywhere. |

Bridge also confirmed: shared-script mode-flag architecture acceptable for
Slice 1; 6-token routing vocabulary sufficient once Phase A/B entry criteria
explicit.

### Round 2 (2026-03-21): REQUEST_CHANGES — 1 finding

R1 fixes confirmed addressed. One remaining design gap:

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 5 | DEFECT | medium | ROUTE_PHASE_B lacks canonical binding to rollout's actual next item | Added "Canonical Next-Item Binding" section: supervisor extracts rollout order from active packet; Codex verifies candidate matches next uncompleted step. |

### Round 3 (2026-03-21): REQUEST_CHANGES — 1 finding

R2 fix confirmed, but canonical-next-item algorithm deadlocks on standing
invariant step 2 ("keep pre-commit supervisor as standing gate") because it's
not a discrete wave.

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 6 | DEFECT | high | Canonical next-item binding deadlocks on standing-gate step | Distinguished "Standing invariant:" (continuous obligation, skip) from discrete routable steps. Updated rollout packet step 2 with `**Standing invariant:**` prefix. Binding algorithm now skips standing invariants. |

### Round 4 (2026-03-21): REQUEST_CHANGES — 1 finding

R3 fix confirmed. But Phase A lock criterion uses substring match on free-text
Status line — `"not yet bridge-converged"` falsely matches `"bridge-converged"`.

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 7 | DEFECT | high | Substring-based lock criterion accepts unconverged status | Replaced with dedicated `Phase-A-Lock:` field using exact-match values `LOCKED`/`UNLOCKED`. No substring ambiguity. |

### Round 5 (2026-03-21): REQUEST_CHANGES — 1 finding

R4 fix confirmed. Gate 5 only checks file coexistence, not that the hook
actually invokes `verify_pre_commit_receipt.py`.

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 8 | DEFECT | medium | Gate 5 doesn't prove hook invokes receipt verifier | Gate 5 now: (1) resolves active hook path via `git rev-parse --git-path`, (2) checks hook is executable, (3) verifies hook delegates to managed RCX hook script, (4) checks verifier script exists. |

### Round 6 (2026-03-21): REQUEST_CHANGES — 2 findings

R5 fix confirmed but grep-based proof insufficient (comments match), and
path containment is lexical only (symlinks escape).

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 9 | DEFECT | medium | Gate 5 grep matches comments, not execution | Replaced grep with managed-hook delegate verification (structural proof that RCX hook is active) |
| 10 | DEFECT | medium | Path containment is lexical only, symlinks escape | Added resolved-path containment (`os.path.realpath`) + tracked-file proof (`git ls-files --error-unmatch`) |

### Round 7 (2026-03-21): REQUEST_CHANGES — 2 findings

R6 fixes confirmed (hook proof + path containment converged). Two remaining:

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 11 | DEFECT | medium | Gate 3 anchored to NOW only; NOW is exceptional/normally-empty | Gate 3 now searches both NOW and NEXT for canonical packet references |
| 12 | DEFECT | medium | `changed_files` is self-reported but derivable from `merge_sha` | `changed_files` now derived by supervisor via `git diff-tree` from `merge_sha`. Package value ignored. |

### Round 8 (2026-03-21): REQUEST_CHANGES — 2 findings

R7 fixes confirmed but: `git diff-tree -r` fails on merge commits (needs
first-parent diff), and Gate 3 is too broad (any control-plane packet passes).

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 13 | DEFECT | high | `git diff-tree -r` returns empty on merge commits | Changed to `git diff --name-only <sha>^...<sha>` (first-parent, merge-safe) |
| 14 | DEFECT | high | Gate 3 accepts any control-plane packet in TASKS, not task-bound | Gate 3 now matches `task_id` to specific TASKS entry and extracts `Tracked packet:` from that entry only |

### Round 9 (2026-03-21): REQUEST_CHANGES — 1 finding

R8 fixes confirmed (merge-safe diff + task-bound Gate 3). Remaining: Gate 1
doesn't anchor to `dev` branch.

| # | Class | Severity | Finding | Resolution |
|---|-------|----------|---------|------------|
| 15 | DEFECT | high | Gate 1 not anchored to canonical `dev` post-merge state | Gate 1 now requires: (a) HEAD is on `dev` or detached at `refs/heads/dev` OID, AND (b) merge SHA reachable from HEAD |

## Open Questions (resolved or remaining)

1. ~~Shared vs separate script?~~ **RESOLVED** (bridge R1): Shared with mode
   flag, but post-merge path factored behind separate helpers.
2. ~~Gate 5 semantics?~~ **RESOLVED** (bridge R1): Soft only. Codex decides.
3. Is the deferred envelope-injection hardening urgent enough to include in
   the post-merge implementation wave, or is it properly a separate follow-on?
   Current design says separate follow-on.
