# Codex Startup Hardening

Date: 2026-04-14
Status: Phase B follow-up (PostToolUse startup audit mechanization)
Task: [CODEX-STARTUP-HARDENING]
Phase-A-Lock: LOCKED
Phase: B
Wave class: L4_ENABLER
Target gate: G8
Governing packet: This file
## Grounding / Authorization

This packet is grounded by the current task authorization in
`TASKS.md:182-184`:

1. shared-learning snapshot
2. Codex startup drift audit
3. tmux/web observability enforcement
4. binary-vs-text-surface documentation for checksum / re-sign behavior

Additional founder-approved governance adjacency (2026-04-15): if this wave's
new startup-state test and startup session tools exceed the repo growth-cap
gate, the wave may update `tests/docs/test_growth_caps.py` only far enough to
cover those wave-owned additions before rerunning Phase B.

Additional founder-approved governance adjacency (2026-04-15): if the
post-merge sweep on the prerequisite control-surface split exposes a
Phase-B-maintenance metadata parser defect that prevents this packet's own
markdown-bulleted `unblocks_*` tokens from propagating truthfully into the
tracker note, this wave may update `mu/tools/executors/phase_b_executor.py`
and `mu/tests/tools/test_phase_b_executor.py` only far enough to parse those
tokens without markdown quote residue before rerunning Phase B.

Additional founder-approved governance adjacency (2026-04-15): if the active
dirty wave still carries a hardcoded `commit_executor.py` bot-remediation
adapter after the Codex backend switch, this wave may update
`mu/tools/executors/executor_common.py`,
`mu/tools/executors/executor_config.json`,
`mu/tools/executors/commit_executor.py`, and
`mu/tests/tools/test_executor_config_alignment.py` only far enough to bind bot
remediation to the same config-backed Codex backend authority before rerunning
Phase B.

This packet is the governing plan for that bounded startup wave. Reviewer
findings are controlling for this rewrite:

1. `tools/session/founder_session_guard.sh:19-20,196-199` defines dry-run as
   print-only and reserves command execution for `--run`.
2. Tracker cleanup work is not currently authorized by `TASKS.md:182-184` and
   is removed from this phase.
3. The startup-state verification surface must include the live mirrored test
   suite at `tests/tools/test_codex_startup_state.py` alongside
   `mu/tests/tools/test_codex_startup_state.py`, because both execute in the
   current repo.

## Wave Class Justification

This L4_ENABLER follow-on is the bounded Phase B/parser hardening pass required
after the Codex implementer/backend switch landed. The active landing surface
changes executor behavior in `mu/tools/executors/phase_b_executor.py` plus its
regression coverage, so the truthful classification is enabler work rather than
bookkeeping-only maintenance. It preserves the same forward-motion linkage:

FOUNDER_OVERRIDE:codex-startup-hardening-2026-04-16-followup (founder approved
this non-structural pipeline-hardening follow-up while founder AFK; required to
bypass the current non-structural adjacency and rolling structural quota until a
new structural wave lands.)

- `unblocks_wave_id: wave-codex-backend-switch-2026-04-14`
- `unblocks_runtime_blocker: INV_STRUCTURAL_FORWARD_MOTION`

## Scope

Edit targets for this phase are limited to the startup contract and startup
orchestration surfaces needed to deliver the four authorized items. Adjacent
tmux observability support is in scope only where it is required to make the
startup-state audit's pane-body enforcement truthful rather than cosmetic:

1. founder-facing startup docs:
   - `.claude/skills/preflight/SKILL.md`
   - `AGENTS.md`
   - `FOUNDER_SESSION_BOOTSTRAP.md`
2. startup contract / tracker surfaces:
   - `TASKS.md`
3. repo-native startup tooling:
   - `tools/session/founder_session_guard.sh`
   - `tools/session/check_codex_startup_state.py`
   - `tools/session/founder_learning_snapshot.py`
4. adjacent tmux observability support:
   - `tools/observability/pipeline_monitor.sh`
5. targeted startup-audit tests:
   - `tests/tools/test_codex_startup_state.py`
   - `mu/tests/tools/test_codex_startup_state.py`
   - `tests/tools/test_recovery_gate.py`
   - `mu/tests/tools/test_recovery_gate.py`
6. adjacent docs governance enforcer:
   - `tests/docs/test_growth_caps.py`
7. adjacent Phase B maintenance-token parsing hardening:
   - `tools/executors/phase_b_executor.py`
   - `tests/tools/test_phase_b_executor.py`
8. adjacent commit-executor remediation backend parity:
   - `tools/executors/executor_common.py`
   - `tools/executors/executor_config.json`
   - `tools/executors/commit_executor.py`
   - `tests/tools/test_executor_config_alignment.py`
9. governing packet:
   - `reports/control_plane/codex_startup_hardening_2026-04-14.md`

Repo path note: in this repo, `tools/` and `tests/` are symlinked to
`mu/tools/` and `mu/tests/`. Implementation must keep the shared underlying
startup files aligned with both surfaced paths.

Observed startup inputs may be read by the audit or snapshot, but are not edit
targets in this phase:

1. optional `.claude/rules/learning.md` (when present)
2. `.claude/hooks/capture-learning.sh`
3. `.agent_bus/recovery/learned_patterns.json`
4. `~/.codex/models_cache.json`
5. local Codex hooks and rules surfaces
6. tmux session `rcx-pipeline`
7. dashboard endpoint `http://127.0.0.1:8099/api/state`

## Work Items

**A. Binary-vs-text-surface documentation**

- Update founder-facing startup docs so only byte-level Codex binary edits are
  treated as checksum / signature / interactive-launch validation events.
- State explicitly that `models_cache.json`, hooks, and local rules are text
  surfaces and must not be conflated with Mach-O patch drift.

**B. Shared-learning snapshot**

- Add or refine `tools/session/founder_learning_snapshot.py` so startup
  reporting names the active shared learning surfaces used across Codex,
  Claude, and the pipeline:
  - `.claude/hooks/capture-learning.sh`
  - `.agent_bus/recovery/learned_patterns.json`
  - `.claude/rules/learning.md` when present
- Make the output explicit that Codex is reusing shared learning surfaces,
  not creating a second repo-local learning store.

**C. Codex startup drift audit with observability enforcement**

- Add or refine `tools/session/check_codex_startup_state.py` to verify:
  - binary guard state and contradiction drift
  - session-start hook canaries
  - prompt-hook disabled or anchored state
  - local `default.rules` does not reopen manual git write / fetch paths
    through blanket interpreter execution allows, multiline allow blocks, or
    equivalent broad command prefixes
  - `~/.codex/models_cache.json` no longer carries stale friendly-persona
    canaries
  - tmux session `rcx-pipeline` and dashboard health at
    `http://127.0.0.1:8099/api/state`
- When this audit is executed, it may recover tmux/web observability and must
  fail closed if recovery cannot be established.
- Keep the tmux monitor honest enough for that audit to be meaningful: pane 1
  must prefer recent non-empty live logs or raw reviewer transcripts over blank
  bridge placeholder files.
- Keep the scoped verification surface aligned with both live mirrored
  startup-state suites plus the monitor-selector regression surface:
  - `tests/tools/test_codex_startup_state.py`
  - `mu/tests/tools/test_codex_startup_state.py`
  - `tests/tools/test_recovery_gate.py`
  - `mu/tests/tools/test_recovery_gate.py`

**D. Founder-guard integration**

- Update `tools/session/founder_session_guard.sh` so dry-run render mode
  remains print-only, consistent with
  `tools/session/founder_session_guard.sh:19-20,196-199`.
- Include the learning snapshot and startup-state audit in the rendered command
  list, but execute them only when the guard is run with `--run`.
- Do not wire mutating observability recovery into a non-run invocation.

**E. Growth-cap governance alignment**

- Keep the docs growth-cap enforcer honest for this wave's bounded startup
  additions only.
- If the new startup-state test or the new startup session tools push repo
  counts over the current cap, update `tests/docs/test_growth_caps.py` with the
  smallest founder-approved cap increase that matches those wave-owned files.
- Do not widen this into unrelated doc/test/tool cap cleanup.

**F. Commit-executor remediation backend parity**

- If the active dirty wave still carries a hardcoded bot-remediation adapter in
  `tools/executors/commit_executor.py`, align that path to the Codex backend
  authority already declared in `tools/executors/executor_config.json`.
- Limit this adjacency to `tools/executors/executor_common.py`,
  `tools/executors/executor_config.json`,
  `tools/executors/commit_executor.py`, and
  `tests/tools/test_executor_config_alignment.py` only far enough to remove the
  hardcoded adapter and lock the binding with regression coverage.

**G. PostToolUse shared-learning verification audit**

- Fold the stale PR #811 startup residue into this startup-state audit instead
  of leaving it as an open local-hook cleanup.
- Verify the Codex-local `~/.codex/hooks/post_tool_use_rcx_verify.py` source as
  an observed startup surface: target repo anchor, shared-learning canaries,
  `PostToolUse` output contract, and safe main-guard execution.
- Verify `~/.codex/hooks.json` routes `PostToolUse` for Bash/Read/Grep/Edit/
  Write/MultiEdit to the verification hook.
- Preserve the current try-wrapped `if __name__ == "__main__": raise
  SystemExit(main())` entrypoint shape as valid; the startup audit should prove
  the live hook contract, not a narrower source formatting preference.

## Constraints

1. Do not add tracker-truth cleanup, `pr711-landed-marker` cleanup, or
   `[PIPELINE-RECOVERY]` text repairs to this phase. `TASKS.md` is in scope
   only for the active `[CODEX-STARTUP-HARDENING]` authorization/tracker
   surface, not for unrelated tracker cleanup outside the current
   `TASKS.md:182-184` authorization.
2. Do not collapse guard render mode into execution mode. Any command that may
   recover tmux or dashboard state must stay behind `--run`.
3. Do not widen into `reports/control_plane/standalone_recovery_2026-04-13.md`,
   recovery-gate work, or runtime/substrate changes under `mu/host/`. The only
   adjacent executor allowances are the bounded `phase_b_executor.py`
   maintenance-token parsing fix authorized above, the pane-1 monitor selector
   fix required to make startup tmux enforcement truthful, and the bounded
   `commit_executor.py` / `executor_config.json` bot-remediation backend parity
   fix authorized above.
4. Do not edit Claude-owned shared-learning source files in this phase; they are
   inputs to the snapshot, not targets of the wave.
5. Do not introduce a separate repo-local Codex learning store.
6. Do not widen docs governance edits beyond `tests/docs/test_growth_caps.py`.

## Stop Conditions

1. Founder-facing startup docs accurately distinguish binary patch drift from
   text-surface drift.
2. The shared-learning snapshot reports the shared knowledge surfaces Codex is
   expected to inherit.
3. The startup-state audit covers Codex-local drift plus tmux/web
   observability state in one executed entrypoint.
4. The founder session guard renders the snapshot/audit commands in dry-run
   output and executes them only with `--run`.
5. The phase remains bounded to the four startup items authorized in
   `TASKS.md:182-184` plus the bounded commit-executor bot-remediation backend
   parity adjacency explicitly authorized in this packet.
6. Any `check_codex_startup_state.py` change remains scoped for verification
   against both mirrored startup-state test files that currently execute in the
   repo.
7. The live startup-contract scope is accurately reflected in the packet,
   including `.claude/skills/preflight/SKILL.md` and the active
   `[CODEX-STARTUP-HARDENING]` entry in `TASKS.md`.
8. The tmux monitor no longer satisfies pane 1 with a zero-byte bridge
   placeholder file when recent raw reviewer output exists.
9. The growth-cap enforcer either remains within cap or explicitly records the
   founder-approved allowance for the one new startup-state test and two new
   startup session tools introduced by this wave.
10. This packet's markdown-bulleted `unblocks_*` metadata propagates into the
    generated tracker note without trailing markdown quote residue.

## Acceptance Criteria

1. The packet no longer claims that guard render mode executes the learning
   snapshot or startup-state audit; execution is explicitly limited to `--run`.
2. Pending work in this packet is limited to the four authorized startup items
   named in `TASKS.md:182-183` plus the bounded commit-executor
   bot-remediation backend parity allowance documented here.
3. No tracker-cleanup work remains in scope, work items, constraints, stop
   conditions, or acceptance criteria.
4. The plan makes tmux/web observability enforcement part of the executed
   startup-state audit rather than a dry-run side effect.
5. The plan keeps Claude-owned shared-learning files as observed inputs and
   does not treat them as edit targets for this wave.
6. The scoped startup-state verification surface explicitly includes both
   `tests/tools/test_codex_startup_state.py` and
   `mu/tests/tools/test_codex_startup_state.py`.
7. The packet scope explicitly covers `.claude/skills/preflight/SKILL.md` and
   the active `[CODEX-STARTUP-HARDENING]` `TASKS.md` entry without reintroducing
   unrelated tracker cleanup.
8. The executed tmux audit can only pass after pane 1 resolves to recent
   non-empty live content instead of a blank bridge `stderr` placeholder.
9. `tests/docs/test_growth_caps.py` acknowledges only the startup-hardening
   wave's one new test file and two new session tools, with no unrelated cap
   widening.
10. The packet's markdown-bulleted `unblocks_wave_id` and
    `unblocks_runtime_blocker` lines parse into Phase B tracker-note metadata
    without trailing backticks or dropped values.
11. The startup-state audit verifies the live PostToolUse verification hook and
    hooks.json matcher coverage without editing Codex-local hook files.

## Re-entry Findings

The last bounded meta review returned `NEEDS_PHASE_B` because the staged
governance truth did not match the current package: this packet still
advertised `Status: ACTIVE (post-review cleanup pending rerun)` / `Phase: A`,
its prior re-entry note still told the pipeline to stop and rerun Phase B, and
`TASKS.md` underreported bridge convergence. Those were staged governance-drift
defects, not new code-surface blockers. The current staged follow-up package at
`.scratch/manual_followup_supervisor_package.json` carries this packet alongside
the parser/test fix slice, so it reports `current_judgment: COMMIT_GO`,
`bridge_status.rounds: 3`, `bridge_status.reentry: true`, and 3 changed files.
This packet revision syncs the staged control-plane truth to that follow-up
package so the next bounded meta review can mint a fresh handoff/receipt from
the synchronized staged state and proceed to commit executor.

## Learning Context

Known pipeline patterns and fixes:
- [test_failure] phase_b: [phase-b] Bridge heartbeat: job=phase-b-r1-573fdfad pid=28206 child_pid → recovery_loop (success:0)
- [test_failure] commit: pre-commit-doc-check failed: [commit-executor] Step 1: inputs validated → recovery_loop (success:0)

## Instructions

1. Read the plan carefully.
2. Implement ALL specified changes.
3. Run only the Phase B-local validation commands listed in the plan.
4. Report your results.
