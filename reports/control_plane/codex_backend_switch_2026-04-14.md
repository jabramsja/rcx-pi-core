# Codex Backend Switch For Pipeline Implementers

Date: 2026-04-14
Task: [PIPELINE-RECOVERY]
Wave class: L4_ENABLER
Target gate: G8
Governing packet: This file

## Authorization

TASKS.md lists `[PIPELINE-RECOVERY]` as **IN PROGRESS** with the lane
"control-surface (pipeline hardening)". The current control-surface problem is
operational: Phase A / Phase B implementation still defaults to Claude-owned
surfaces in the executor defaults and operator-facing truth surfaces, while this
session's live dirty diff is already switching those defaults to Codex. The
packet below formalizes that change as a narrow follow-on instead of attempting
to resume under the already-landed `anti_drift` packet.

Repo evidence for the operational constraint exists in the control layer:

1. `mu/tools/executors/commit_executor.py` already classifies issue-comment
   review failures caused by usage exhaustion (`usage_limit` handling).
2. `mu/tools/executors/phase_b_executor.py` already routes implementer backend
   selection through executor config.
3. The current dirty worktree changes the default implementer backend from
   `claude` to `codex` in executor config / defaults and updates operator-facing
   truth surfaces to match.

This is a pipeline-hardening follow-on under `[PIPELINE-RECOVERY]`, not a new
anti-drift bot-findings wave.

## Scope

Narrow the current dirty worktree to one honest wave:

1. Switch Phase A / Phase B implementer defaults from Claude to Codex in the
   executor control layer.
2. Update the associated tests so the default-backend truth matches runtime
   behavior.
3. Update generated handoff metadata so it no longer claims "Claude" when the
   implementer path is now Codex.

This packet is intentionally about backend-routing truth only. It is **not**
the startup-hardening wave and it is **not** the standalone commit-executor
recovery wave.

## Files In Scope

### Included in this wave

1. `mu/tools/executors/executor_common.py`
2. `mu/tools/executors/executor_config.json`
3. `mu/tools/executors/phase_a_executor.py`
4. `mu/tools/executors/phase_b_executor.py`
5. `mu/tests/tools/test_executor_dispatch.py`
6. `mu/tests/tools/test_phase_b_executor.py`
7. `reports/control_plane/codex_backend_switch_2026-04-14.md`

### Explicitly excluded from this wave

These files are currently dirty but belong to a separate Codex startup /
preflight hardening wave, not to the backend switch:

1. `.claude/skills/preflight/SKILL.md`
2. `AGENTS.md`
3. `FOUNDER_SESSION_BOOTSTRAP.md`
4. `mu/tools/session/founder_session_guard.sh`
5. `mu/tools/session/check_codex_startup_state.py`
6. `mu/tools/session/founder_learning_snapshot.py`
7. `mu/tests/tools/test_codex_startup_state.py`
8. `mu/tools/observability/_pane_processes.sh`
9. `mu/tools/observability/pipeline_dashboard_web.py`

### Separate active-but-unpacketed item

1. `reports/control_plane/standalone_recovery_2026-04-13.md`

That report is a different `[PIPELINE-RECOVERY]` follow-on about standalone
`commit_executor.py --standalone` recovery wiring. Do not bundle it into the
backend switch commit.

## Work Items

**A. Default backend switch in executor truth**

- Update executor defaults so `phase_b_executor` defaults to `codex` in both the
  Python default config and the tracked JSON config.
- Keep bridge-reviewer defaults untouched unless the current dirty diff proves
  they already match Codex and require no further change.

**B. Phase A / Phase B implementer routing coherence**

- Update the Phase A implementer invocation so the blocking-finding fix path no
  longer hardcodes either Claude or Codex and instead honors the configured
  Phase A implementer backend, with Codex remaining the default.
- Update Phase B generated handoff metadata so commit messages and operator truth
  no longer claim Claude authorship for a Codex implementer path.

**C. Test alignment**

- Update executor tests that currently assert the old Claude default so they
  assert the new Codex default.
- Keep the assertions about valid backend override behavior for both `claude`
  and `codex`; this wave changes defaults, not supported backend vocabulary.

## Constraints

- No runtime / substrate file changes under `mu/host/`.
- No startup-hook, founder-bootstrap, preflight, or memory-snapshot changes in
  this wave.
- No changes to `.claude` surfaces in this wave.
- No standalone recovery wiring in `commit_executor.py` in this wave.
- No opportunistic packet bundling just because the worktree is already dirty.

## Dirty-Worktree Split Rule

Before any Phase B rerun or commit packaging:

1. Treat the files in "Included in this wave" as the only files allowed into the
   backend-switch candidate.
2. Treat the "Explicitly excluded" startup-hardening files as a separate future
   wave, even if they remain locally dirty.
3. Do not rely on the landed `anti_drift` packet for authority; it does not own
   `phase_a_executor.py`, `phase_b_executor.py`, executor default config, or the
   observability labels.

## Stop Conditions

1. The executor default backend truth is consistently Codex across config,
   control-layer defaults, tests, and generated handoff metadata.
2. No Claude-specific implementer identity remains in the Phase A / Phase B
   paths touched by this wave.
3. The candidate diff can be described honestly by this packet alone.
4. The startup-hardening and observability files are clearly excluded from the
   packet-owned file set.

## Acceptance Criteria

1. `mu/tools/executors/executor_common.py` and
   `mu/tools/executors/executor_config.json` agree on the default
   `phase_b_executor` backend.
2. The targeted executor tests that assert default backend behavior pass with
   `codex` as the default.
3. The Phase A blocking-finding rewrite path preserves explicit backend
   overrides instead of forcing Codex during implementer retries.
4. The final candidate can be staged from only the "Included in this wave" file
   list without pulling in startup-hardening surfaces.
