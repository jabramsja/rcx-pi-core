# Executor Surfaces Plan

Date: 2026-03-22
Status: Complete (all 6 slices implemented, PRs #659-#661)
Phase-A-Lock: LOCKED
Purpose: decision-complete design for repo-local executor automation surfaces

## Goal

Replace Claude-as-workflow-engine with repo-local executor scripts that the
post-merge supervisor's routing decisions dispatch into. Claude becomes a
fallback/escalation surface, not the workflow owner.

## Current Truth

- Pre-commit supervisor: live, standing gate (META-BRIDGE-S1, PR #641-#655)
- Post-merge supervisor: live, routing gate (META-BRIDGE-S2, PR #657)
- Post-merge routing tested: `ROUTE_PHASE_A` emitted for rollout step 4
- Rollout step 4 is "Introduce real repo-local executors"
- Claude currently acts manually on routing decisions
- `/wave` and `/bridge` skills are Claude-owned thin wrappers
- Claude memory (16 files, 35KB) + CLAUDE.md (601 lines) consume excessive
  context before any work begins

## What This Plan Covers

Rollout step 4: four repo-local executor scripts that act on post-merge
supervisor routing decisions. Each executor is a standalone Python script
under `mu/tools/executors/`.

## What This Plan Does NOT Cover

- CLAUDE.md/memory slimming (rollout step 6 — deferred until executors exist)
- Structural queue unparking (rollout step 7)
- Post-merge or pre-commit supervisor changes (already complete)
- Runtime/kernel/substrate changes

---

## A. Authority Model

### Post-merge supervisor (unchanged)

- Read-only investigative authority
- Full filesystem + command + web access for verification
- NO implementation, commit, push, or merge authority
- Emits routing decisions only; executors act on them
- Uses `--sandbox danger-full-access` (prompt-enforced read-only)

### Executors

| Executor | Authority | Mutating? |
|----------|-----------|-----------|
| `dialectic_executor` | Read-only + conversation | No (produces narrowed scope proposal, not code) |
| `phase_a_executor` | Read + write plan packets, TASKS.md, rollout packet, deferred non-blockers | Yes (plan packets, tracker sync, `reports/deferred/non_blocking/`) |
| `phase_b_executor` | Read + write implementation code, deferred non-blockers | Yes (code, tests, docs, `reports/deferred/non_blocking/`) |
| `commit_executor` | Full commit pipeline authority | Yes (stage, commit, push, PR, CI, merge) |

### Founder-only (never automated)

- Promoting items from VECTOR or SINK to NEXT
- Unparking the structural queue
- Overriding rollout order
- Policy decisions flagged by `STOP_FOR_FOUNDER`
- Deciding lane satisfaction

---

## B. Executor Surfaces

### 1. `dialectic_executor.py`

**Purpose:** Narrow an unbounded next-step proposal into something bounded
enough for Phase A planning.

**Invoked by:** `CONTINUE_DIALECTIC` routing token

**What it does:**
1. Reads the post-merge routing record from `.agent_bus/meta/post_merge_routing.json`
2. Reads the relevant rollout packet and TASKS.md context
3. Sends the unbounded proposal + repo context to Codex for dialectic narrowing
4. Codex proposes a bounded scope with explicit files, constraints, and stop conditions
5. Writes the narrowed proposal to `.agent_bus/executors/dialectic_result.json`
6. Triggers a new post-merge supervisor run with the narrowed proposal

**Mutating:** No — produces a proposal record, not code or plan changes.

**Backend:** Strongest available (Opus/GPT-5.4 via config).

### 2. `phase_a_executor.py`

**Purpose:** Create a decision-complete plan packet through the design +
agent review + bridge convergence loop.

**Invoked by:** `ROUTE_PHASE_A` routing token

**What it does:**
1. Reads the post-merge routing record
2. Creates or refines a plan packet in `reports/control_plane/`
3. Runs SDK agent review (`run_review.py --depth full`)
4. Sends plan + agent findings to bridge (`--no-diff`)
5. Fixes blockers, defers non-blockers
6. Loops bridge until only non-blockers remain
7. Sets `Phase-A-Lock: LOCKED` in the plan packet
8. Stages and commits the plan packet (so it becomes git-tracked)
9. Updates TASKS.md to reference the new tracked plan packet
10. Updates the rollout packet if the new plan is the canonical next item
11. Triggers a new post-merge supervisor run with a post-merge package
    that references the now-tracked plan packet

**Phase A re-entry contract (bridge R1 fix):**

The post-merge supervisor's Gate 3 requires `rollout_packet_path` to be a
git-tracked file matching the task's `Tracked packet:` reference. When Phase A
creates a NEW plan packet:
1. Phase A executor commits the plan packet (makes it git-tracked)
2. Phase A executor updates TASKS.md with a new NEXT entry for the plan
3. Phase A executor commits tracker sync
4. Only THEN does it build the post-merge package (now the plan IS tracked)
5. The post-merge supervisor sees the tracked plan and can route to Phase B

**Branch/merge discipline (bridge R2 fix):**

Phase A executor follows the same branch/merge flow as any implementation:
1. Creates a feature branch from dev (`git checkout -b jabramsja/<plan-name>`)
2. Commits plan packet + tracker sync on the feature branch
3. Pushes feature branch, creates PR targeting dev
4. Waits for CI, resolves bot comments
5. Merges via `merge_pr.sh --sweep`
6. Checks out dev, pulls
7. NOW runs post-merge supervisor on dev (HEAD is post-merge on dev)

This satisfies the post-merge supervisor's Gate 1 (must be on dev) and
Gate 3 (plan packet is now git-tracked on dev). The executor uses the
pre-commit supervisor receipt flow for the plan commit and the commit
executor for the merge pipeline.

**Mutating:** Yes — creates/edits plan packets in `reports/control_plane/`.

**Backend:** Strongest available for planning (Opus/GPT-5.4 via config).

### 3. `phase_b_executor.py`

**Purpose:** Implement a locked plan through the implementation + bridge
convergence loop.

**Invoked by:** `ROUTE_PHASE_B` routing token

**What it does:**
1. Reads the post-merge routing record and the locked plan packet
2. Implements the plan (writes code, tests, docs)
3. Runs SDK agent review (`run_review.py --depth full`)
4. Sends agent findings + diff to bridge (WITH diff)
5. Fixes blockers, defers non-blockers
6. Loops bridge until only non-blockers remain
7. Hands off to pre-commit supervisor (prepares package, runs supervisor)
8. On `NEEDS_PHASE_B` from pre-commit: re-enters bridge loop (not agents)
9. On `COMMIT_GO`: hands off to commit executor

**Mutating:** Yes — writes code, tests, docs.

**Backend:** Faster backend allowed (Sonnet/GPT-4o via config) since the plan
is already locked. Config-overridable for complex implementations.

### 4. `commit_executor.py`

**Purpose:** Execute the full commit → push → PR → CI → merge → sweep →
post-merge loop.

**Invoked by:** `COMMIT_GO` or `COMMIT_GO_HOLD_PUSH` from pre-commit supervisor

**Input contract (bridge R1+R4 fix):**

The commit executor consumes a structured handoff from ANY caller
(Phase B executor, Phase A executor, or post-merge dispatcher for
UPDATE_TRACKER_ONLY):

```json
{
  "staged_files": ["file1.py", "file2.md"],
  "commit_message": "feat: implement X\n\nCo-Authored-By: ...",
  "pr_title": "feat: implement X",
  "pr_body": "## Summary\n...\n## Test plan\n...",
  "head_branch": "jabramsja/wave-name",
  "base_branch": "dev",
  "hold_push": false,
  "pre_commit_receipt_path": ".agent_bus/meta/pre_commit_receipt.json",
  "task_id": "[TASK-ID]",
  "wave_name": "wave-name",
  "caller": "phase_b|phase_a|update_tracker_only"
}
```

**What it does:**
1. Validates handoff: receipt exists, staged files match, branch is correct
2. Runs `git commit -m <message>` (pre-commit hook verifies receipt)
3. If `hold_push`: stop and report (COMMIT_GO_HOLD_PUSH semantics)
4. Runs `git push -u origin <head_branch>` (pre-push hook runs audit_fast.sh)
5. Creates PR via `gh pr create --base dev --head <head_branch> --title <title> --body <body>`
   (uses `--body` and `--head` flags for fully non-interactive operation)
6. Waits for CI (`gh pr checks <PR#> --watch` — blocks until all checks complete)
7. Reads bot comments via `gh api` — resolves bot threads mechanically
   (same as `merge_pr.sh` existing behavior). Human-authored threads are
   left unresolved and reported as warnings. No semantic triage — the
   merge script already handles this mechanically.
8. Runs `bash mu/tools/hooks/merge_pr.sh <PR#> --sweep`
9. Post-merge verify (`git log --oneline -3`, `git status --short`)
10. Builds post-merge package and triggers post-merge supervisor

**COMMIT_GO_HOLD_PUSH semantics:** commit locally (step 2), then stop.
Do not push, PR, or merge. Report the local commit SHA and wait.

**Fail-closed merge policy (bridge R5 fix):**
- CI: `gh pr checks <PR#> --watch --required` — wait for ALL required checks.
  If any required check fails, STOP. Do not merge. Return to caller.
- Human threads: if unresolved human-authored threads exist after bot thread
  resolution, STOP. Report the thread IDs and return to caller. Do not
  merge with unresolved human threads.
- `--admin` bypass: FORBIDDEN by default. Only used when explicitly set in
  the handoff (`"admin_merge": true`). Default is `false`. Phase B and
  Phase A callers never set it. Only `update_tracker_only` may set it
  when repo protection state requires it (same policy as current
  `merge_pr.sh` usage).

**Mutating:** Yes — commits, pushes, creates PRs, merges.

**Backend:** No LLM needed — pure script orchestration (git + gh CLI).
No Codex/Claude involved.

**GitHub branch protection delegation (bridge R6 fix):**

The commit executor delegates merge to `merge_pr.sh`, which already handles
the repo's branch protection surface (required reviews, conversation
resolution, status checks, admin bypass). The executor does NOT independently
model GitHub branch protection — it trusts the merge script to enforce the
repo's protection policy. If the merge script fails, the executor reports
the failure and returns to the caller. This keeps the executor mechanical
and avoids duplicating protection logic that may change at the GitHub level.

---

## C. Backend/Model Policy

### Config-driven selection

Backend selection is config-driven, not hardcoded per executor.

**Config location:** `mu/tools/executors/executor_config.json`

**Shape:**
```json
{
  "backends": {
    "post_merge_supervisor": "codex",
    "dialectic_executor": "codex",
    "phase_a_executor": "codex",
    "phase_b_executor": "codex",
    "commit_executor": null
  },
  "model_overrides": {
    "phase_b_executor": "sonnet"
  },
  "timeouts": {
    "dialectic_executor": 600,
    "phase_a_executor": 1200,
    "phase_b_executor": 1200,
    "commit_executor": 300
  }
}
```

**Policy:**
- Post-merge supervisor + dialectic + Phase A: strongest backend (design/routing quality matters)
- Phase B: faster backend allowed (plan is locked, implementation is bounded)
- Commit executor: no LLM — pure script orchestration
- All backends configurable; defaults in config, overridable per invocation

---

## D. Input/Output and State Contracts

### State namespace

All executor runtime state lives in `.agent_bus/executors/` (untracked):
- `.agent_bus/executors/dialectic_result.json`
- `.agent_bus/executors/phase_a_state.json`
- `.agent_bus/executors/phase_b_state.json`
- `.agent_bus/executors/commit_state.json`

### What is canonical proof vs runtime state

| Artifact | Type | Location |
|----------|------|----------|
| Plan packets | Canonical (tracked) | `reports/control_plane/` |
| Routing records | Runtime (untracked) | `.agent_bus/meta/` |
| Executor state | Runtime (untracked) | `.agent_bus/executors/` |
| Bridge renders | Runtime (untracked) | `.agent_bus/rendered/` |
| Pre-commit receipts | Runtime (untracked) | `.agent_bus/meta/` |
| TASKS.md / STATUS.md | Canonical (tracked) | repo root |
| Deferred findings | Canonical (tracked) | `reports/deferred/` |

### State binding

All executor state records include `head_sha` and `state_sha` (computed via
`compute_repo_state()` from the existing supervisor). Stale records are
detected by comparing state_sha against live repo.

### Input contracts

| Executor | Primary input | Additional context |
|----------|--------------|-------------------|
| `dialectic_executor` | `post_merge_routing.json` | rollout packet, TASKS.md |
| `phase_a_executor` | `post_merge_routing.json` | rollout packet, candidate scope |
| `phase_b_executor` | `post_merge_routing.json` + locked plan packet | plan's implementation scope |
| `commit_executor` | pre-commit supervisor receipt | staged files, commit message |

---

## E. Control Flow

```
merge lands on dev
       │
       ▼
post-merge supervisor (read-only, tool-rich)
       │
       ├─ CONTINUE_DIALECTIC ──► dialectic_executor
       │                              │
       │                              ▼
       │                    narrowed proposal written
       │                              │
       │                    ◄─────────┘ (re-run post-merge supervisor)
       │
       ├─ ROUTE_PHASE_A ──► phase_a_executor
       │                         │
       │                         ▼
       │               design → agents → bridge → loop
       │                         │
       │                    Phase-A-Lock: LOCKED
       │                         │
       │                    ◄────┘ (re-run post-merge supervisor)
       │
       ├─ ROUTE_PHASE_B ──► phase_b_executor
       │                         │
       │                         ▼
       │               implement → agents → bridge → loop
       │                         │
       │                    pre-commit supervisor
       │                         │
       │                    ├─ COMMIT_GO ──► commit_executor
       │                    │                    │
       │                    │              commit → push → PR → CI → merge
       │                    │                    │
       │                    │                    ▼
       │                    │         back to post-merge supervisor
       │                    │
       │                    ├─ COMMIT_GO_HOLD_PUSH ──► commit locally, stop before push
       │                    │
       │                    ├─ NEEDS_PHASE_B ──► back to bridge loop (not agents)
       │                    │
       │                    ├─ NEEDS_PHASE_A ──► back to Phase A executor (scope changed)
       │                    │
       │                    └─ STOP_FOR_FOUNDER ──► founder
       │
       ├─ UPDATE_TRACKER_ONLY ──► dispatcher stages tracker files,
       │                           runs pre-commit supervisor (receipt flow),
       │                           then hands off to commit_executor
       │                           (caller: update_tracker_only)
       │
       ├─ STOP_FOR_FOUNDER ──► founder
       │
       └─ STOP_FOR_TRIAGE_DISCUSSION ──► founder
```

### Re-entry rules

- `NEEDS_PHASE_B` from pre-commit supervisor: re-enter Phase B bridge loop
  only (not agents, per founder feedback)
- `NEEDS_PHASE_A` from pre-commit supervisor: scope changed materially,
  re-enter Phase A executor
- `CONTINUE_DIALECTIC` after dialectic: re-run post-merge supervisor with
  narrowed proposal
- Pre-merge commit_executor failure: return to the CALLER for fix + retry:
  - `caller: phase_b` → return to Phase B executor bridge loop
  - `caller: phase_a` → return to Phase A executor
  - `caller: update_tracker_only` → emit `STOP_FOR_TRIAGE_DISCUSSION`
  NOT to post-merge supervisor (which requires a merged state).
- Post-merge executor failure (dialectic, Phase A, Phase B start): emit
  structured error, return to post-merge supervisor which routes to
  `STOP_FOR_TRIAGE_DISCUSSION`

### Bridge loop iteration limits

- Phase A bridge loop: max 15 rounds (same as the post-merge supervisor
  Phase A experience — 9 rounds was typical)
- Phase B bridge loop: max 10 rounds
- Dialectic executor: max 3 rounds of narrowing before `STOP_FOR_FOUNDER`
- If any limit is hit, executor emits `STOP_FOR_TRIAGE_DISCUSSION` with
  the round history and remaining findings

### Input validation

Every executor validates its input before acting:
1. Routing record exists and is not stale (`state_sha` matches current repo)
2. Routing record's `decision` field matches the executor's expected token
3. Referenced plan packets exist and are readable
4. Referenced rollout packet exists and is readable
If any validation fails, executor emits structured error and stops.

---

## F. Priority / Routing Discipline

### How post-merge supervisor chooses next work

1. Read the active rollout packet's canonical rollout order
2. Skip done steps and standing invariants
3. The first routable step is the canonical next item
4. If the next item has a locked plan → `ROUTE_PHASE_B`
5. If the next item has an unlocked plan or no plan → `ROUTE_PHASE_A`
6. If the next item is not bounded enough → `CONTINUE_DIALECTIC`
7. If the rollout is complete → `STOP_FOR_TRIAGE_DISCUSSION`

### Founder-stop rules

- Promoting VECTOR → NEXT: `STOP_FOR_FOUNDER`
- Promoting SINK → VECTOR or NEXT: `STOP_FOR_FOUNDER`
- Unparking structural queue: `STOP_FOR_FOUNDER`
- Overriding rollout order: `STOP_FOR_FOUNDER`
- Any ambiguity about what's next: `STOP_FOR_TRIAGE_DISCUSSION`

---

## G. Interaction with Existing Surfaces

### `/wave` and `/bridge` skills

After executor implementation, these become thin wrappers:
- `/wave plan <name>` → invokes `phase_a_executor.py`
- `/wave implement` → invokes `phase_b_executor.py`
- `/bridge review` → invokes bridge_supervisor.py (unchanged)
- `/bridge plan` → invokes `bridge_supervisor.py review --no-diff` (unchanged)

The skills remain available as manual fallback during transition (rollout
step 5). After executors are proven, the skills can be deprecated.

### Pre-commit supervisor

Unchanged. Remains the standing commit gate. The commit executor calls it
as part of the commit pipeline.

### `merge_pr.sh`

Unchanged. The commit executor calls it for merge + sweep.

### Structural queue

Remains parked. Unparking requires rollout steps 1-6 complete + founder GO.

---

## H. CLAUDE.md / Memory Optimization Relationship

### How executors reduce protocol pressure

Once executors exist:
- Phase A/B protocol no longer needs to be in Claude's memory — executors
  encode it in code
- Wave protocol XML in MEMORY.md (64 lines duplicated from CLAUDE.md) can be
  removed — the executors ARE the protocol
- CLAUDE.md can drop test classification tables, audit script details, L4
  contract field-by-field specs — executors handle those checks
- Claude memory becomes pointers: "executor exists at X, run it for Y"
  instead of "here's the entire protocol to follow manually"

### Follow-on (rollout steps 5+6 — DONE)

Steps 5+6 combined (founder-authorized 2026-03-22). Executors validated via
context optimization wave. CLAUDE.md slimmed 601→201 lines. Memory consolidated
19→6 files. Manual wave protocol archived to `reports/archive/`.
- Step 4: executors (this plan) — DONE
- Step 5: transition + validation — DONE (combined with step 6)
- Step 6: CLAUDE.md/memory pointer layer — DONE
- Step 7: unpark structural queue — READY

---

## I. Future Implementation Proof

### Required tests per executor

| Executor | Unit tests | Integration tests | Failure-mode tests |
|----------|-----------|-------------------|-------------------|
| `dialectic_executor` | Schema validation, state binding | End-to-end with mocked Codex | Timeout, adapter failure, stale state |
| `phase_a_executor` | Plan creation, agent invocation, bridge loop | Full Phase A cycle with mocked bridge | Agent failure, bridge failure, lock failure |
| `phase_b_executor` | Code write, agent invocation, bridge loop | Full Phase B cycle with mocked bridge | Implementation failure, pre-commit rejection, re-entry |
| `commit_executor` | Stage, commit, push, PR, merge | Full commit pipeline with mocked git/gh | Hook failure, CI failure, merge conflict, bot threads |

### End-to-end control flow tests

- Post-merge → dialectic → post-merge (re-routing after narrowing)
- Post-merge → Phase A → post-merge → Phase B → pre-commit → commit → post-merge
- Pre-commit NEEDS_PHASE_B → bridge loop re-entry (not agents)
- Executor failure → post-merge → STOP_FOR_TRIAGE_DISCUSSION

### Honest proof criteria

Implementation is proven when:
1. All executor scripts exist under `mu/tools/executors/`
2. Each executor has unit + integration + failure-mode tests
3. The full control flow loop completes end-to-end with mocked backends
4. `/wave` and `/bridge` skills can dispatch to executors
5. Post-merge supervisor routing record is consumed by executors
6. Pre-commit supervisor receipt flow works through commit executor

---

## Implementation Slices (for future Phase B)

### Slice 1: config + dispatcher foundation (bridge R1 fix — must come first)

- Config file (`executor_config.json`) with backend/timeout defaults
- Dispatcher script (`executor_dispatch.py`) that reads routing record and
  invokes the correct executor
- Shared utilities: routing record validation, state binding, error reporting
- Direct-invocation CLI contract for each executor (even before wrappers)
- Tests: dispatcher routing, config loading, input validation
- Proves: the shared foundation works before any executor is built on it

### Slice 2: commit_executor (lowest risk, mechanical)

- No LLM needed — pure git/gh orchestration
- Reuses `merge_pr.sh`
- Consumes structured handoff from Phase B executor
- Non-interactive `gh pr create` with `--body` flag
- Tests: mock git/gh commands, handoff validation
- Proves: the commit pipeline can be scripted end-to-end

### Slice 3: phase_b_executor (medium risk, core loop)

- Implements the Phase B bridge convergence loop
- Reuses `bridge_supervisor.py` and `run_review.py`
- Tests: mock bridge + agent responses
- Proves: bridge loop can run without Claude-in-the-loop

### Slice 4: phase_a_executor (medium risk, planning + re-entry)

- Creates plan packets and runs Phase A convergence
- Commits plan + tracker sync (needs pre-commit receipt flow)
- Re-entry contract for post-merge supervisor
- Reuses `bridge_supervisor.py --no-diff` and `run_review.py`
- Tests: mock bridge + agent responses, plan tracking, re-entry
- Proves: plan creation + lock + commit + re-entry cycle works

### Slice 5: dialectic_executor (highest risk, least defined)

- Narrowing requires flexible reasoning
- May need special Codex prompt engineering
- Tests: mock Codex narrowing responses
- Proves: scope narrowing can be structured

### Slice 6: /wave skill wrapper update + end-to-end integration

- `/wave` skill dispatches to executors
- End-to-end integration tests for full control flow
- Deprecation path for manual Claude workflow

---

## Invariants

1. Post-merge supervisor never executes Phase A/B — only routes
2. Executors never modify supervisor routing decisions
3. Pre-commit supervisor remains the standing commit gate
4. Structural queue awaiting separate founder GO to unpark (rollout steps 1-6 complete)
5. CLAUDE.md/memory slimmed to pointer layer (step 6 done, 2026-03-22)
6. Founder-only: VECTOR/SINK promotion, queue unparking, rollout override
7. All executor state is runtime (untracked) and state-bound
8. Config-driven backend selection, not hardcoded
9. Executor failures route to STOP_FOR_TRIAGE_DISCUSSION, not silent swallow

---

## Tracked Packet References

- **This packet:** `reports/control_plane/executor_surfaces_plan_2026-03-22.md`
- **Parent rollout:** `reports/control_plane/meta_bridge_rollout_2026-03-20.md`
- **Pre-commit supervisor:** `mu/tools/agents/meta_bridge_supervisor.py` (pre-commit mode)
- **Post-merge supervisor:** `mu/tools/agents/meta_bridge_supervisor.py` (post-merge mode)
- **Post-merge plan:** `reports/control_plane/post_merge_supervisor_plan_2026-03-21.md`
- **Parked queue:** `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
