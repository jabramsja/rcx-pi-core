Phase-A-Lock: LOCKED
# Phase A Plan: pager-deterministic-session-2026-04-18
## Status

Phase A plan, Rev 2 after bridge REQUEST_CHANGES on Rev 1.

Rev 1 was rejected because its only determinism mechanism
(`claude --resume <id>`) was gated on a session-id file that is absent in
the current repo state, and the orchestrator-side writer that would populate
it was explicitly deferred. The result: Rev 1 could land while leaving
`_dispatch_claude`'s live `-c` / `--continue` behavior unchanged, so the bot
P1 finding on PR #794 would remain live on merge.

Rev 2 restructures the wave so live behavior changes on merge without
depending on a deferred writer: the `-c` / `--continue` branch is removed
from `_dispatch_claude` entirely, and dispatch falls back to plain `-p`
(deterministic, single-shot) when no session-id is registered. Awaiting
bridge review GO.

## Context

PR #794 (merged `7e2c8f48`) landed `pipeline_agent_pager.route: "claude"` +
`claude_continue: true` in `mu/tools/executors/executor_config.json:22-26`.
At `mu/tools/observability/pipeline_agent_pager.py:650-697`, `_dispatch_claude`
reads the `claude_continue` flag from config and, when true, builds argv
unconditionally as:

```
claude -c -p <prompt>
```

`claude -c` / `--continue` loads "the most recent conversation in the current
directory." That is non-deterministic: `executor_config.json:5-7` also routes
`phase_a_executor`, `phase_b_executor`, and `bot_remediation` to `claude`.
While the pipeline is actively running any of those Claude subprocesses, the
pager's `--continue` can attach to a pipeline subprocess's conversation
instead of the orchestrator conversation that should receive the ping.
PR #794's bot P1 finding identifies this divert risk.

This wave removes `-c` / `--continue` from the pager's dispatch path
entirely, so dispatch is deterministic on merge regardless of whether an
orchestrator session id has been registered.

## 1. Scope

In-scope files / directories (exhaustive):

- `mu/tools/observability/pipeline_agent_pager.py` — specifically
  `_dispatch_claude` (lines 650-697) and any new helper(s) it calls for
  reading the orchestrator session-id file.
- `mu/tools/executors/executor_config.json` — `pipeline_agent_pager` block
  at lines 22-26, for the `claude_continue` key cleanup (see W5).
- A new orchestrator-session-id file contract documented in
  `pipeline_agent_pager.py` as a module-level comment or docstring
  (proposed path: `.agent_bus/observability/orchestrator_session_id`; the
  implementer may choose an equivalent path under `.agent_bus/` provided it
  is documented in the commit and consistent between future writer and this
  wave's reader). No file is created by this wave; only the read path is
  authored.
- Test surface for `_dispatch_claude`: the existing test module
  `mu/tests/tools/test_pipeline_agent_pager.py` (confirmed present; its
  fixture at line 556 already constructs config with
  `"claude_continue": False`, so W5's config change does not regress that
  test). Extend this module; do not create a new file.
- `mu/tools/executors/executor_common.py` line 50 — iff W5 deletes the
  `claude_continue` key entirely, the default fixture here must drop the
  key too. If W5 only flips the value to `false`, this file is untouched.
- Governing packet: this file
  (`reports/control_plane/pager_deterministic_session_2026-04-18.md`).

Out-of-scope files explicitly excluded in §3 below.

## 2. Work items

Concrete, bounded tasks authorized by TASKS.md `[PIPELINE-AGENT-PAGER]`
(lines 192-200) + `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup`:

W1. **Orchestrator session-id file contract.** Document the file path the
    pager reads for a targeted orchestrator session id, as a short
    module-level comment or docstring in `pipeline_agent_pager.py` (single
    source of truth for the path). The file is read-only from the pager's
    perspective in this wave; a separate follow-on wave will add the
    orchestrator-side writer. The pager MUST tolerate the file being
    absent indefinitely (see W2 fallback and W3 hardening).

W2. **Deterministic dispatch in `_dispatch_claude`.** Modify
    `_dispatch_claude` at `pipeline_agent_pager.py:650-697` so that argv
    construction has exactly two branches and `-c` / `--continue` is not
    present in either:

    - If the orchestrator-session-id file exists and contains a non-empty
      session id (after W3's validation), build argv as
      `[claude_bin, "--resume", <id>, "-p", <prompt>]`.
    - Otherwise build argv as `[claude_bin, "-p", <prompt>]` — plain
      single-shot invocation, deterministic by construction. This branch is
      the active branch in the current repo state (session-id file absent)
      and is a deliberate behavioral change from post-PR-#794's
      `claude -c -p <prompt>`.

    The `if continue_flag: command.append("-c")` block at
    `pipeline_agent_pager.py:660-661` MUST be deleted, not guarded. The
    `continue_flag` read at line 658 MUST also be deleted if it has no
    remaining callers inside `_dispatch_claude`. Grep `pipeline_agent_pager.py`
    after the edit to confirm no lingering references to `claude_continue`
    or `continue_flag` inside the module's dispatch path.

W3. **Session-id read hardening.** The read path must tolerate: missing
    file, empty file, whitespace-only file, and a single trailing newline
    (strip it). On any of those it treats the session id as absent and
    takes W2's plain-`-p` branch rather than raising. Session ids that
    contain internal whitespace or newlines are also treated as absent
    (malformed); the pager logs a single fallback note through the existing
    pager error surface and continues. The pager MUST NOT crash the
    orchestrator because of a malformed session-id file.

W4. **Tests.** Extend `mu/tests/tools/test_pipeline_agent_pager.py` with
    unit tests for `_dispatch_claude` covering:

    - Session-id file present, non-empty, no internal whitespace → argv is
      exactly `[<claude_bin>, "--resume", <id>, "-p", <prompt>]`. Assert
      `"-c"` and `"--continue"` are NOT in the argv.
    - Session-id file absent → argv is exactly
      `[<claude_bin>, "-p", <prompt>]`. Assert `"-c"`, `"--continue"`, and
      `"--resume"` are NOT in the argv. This test pins the behavioral
      change in the current-repo-state path.
    - Session-id file present but empty / whitespace-only / with internal
      whitespace → falls back to the absent-file branch (plain `-p`).
    - Session-id file with a trailing newline around a valid id → id is
      stripped and `--resume <id>` is used.

    Tests MUST patch `subprocess.run` (or equivalent) and assert on the
    argv list constructed. They MUST NOT invoke a real `claude` binary.
    They MUST run in <1s and MUST NOT be marked `@pytest.mark.slow` (the
    existing test module already follows this pattern).

W5. **Config cleanup for `claude_continue`.** The `claude_continue` key in
    `executor_config.json:22-26` becomes dead after W2 deletes the only
    reader. The implementer selects one of the two bounded options:

    - **Option W5a (minimum churn):** flip the value from `true` to
      `false` in `executor_config.json:25`. Leave the key in place as an
      explicitly-unused slot. The fixture default at
      `executor_common.py:50` is already `False` and is untouched. The
      test fixture at `test_pipeline_agent_pager.py:556` already constructs
      `"claude_continue": False` and is untouched.
    - **Option W5b (full removal):** delete the `claude_continue` key from
      `executor_config.json:25`. Delete the key from
      `executor_common.py:50`'s default fixture. Delete or update the
      fixture at `test_pipeline_agent_pager.py:556` so no test references
      a removed key.

    Either option is acceptable. The implementer chooses based on which
    diff is smaller and which keeps `git grep claude_continue` honest. In
    either case, no production code path reads the key after this wave.

## 3. Constraints (NOT in scope)

- No changes to pager routing targets other than `_dispatch_claude` (e.g.,
  `_dispatch_codex`, `_dispatch_notify_only`, `_dispatch_target` routing
  table).
- No changes to `executor_config.json` keys outside the `pipeline_agent_pager`
  block (backends, bridge_reviewers, timeouts, hybrid_recovery_enabled, etc.).
- No change to the PR #794 route decision (`route: "claude"`). This wave
  hardens how the Claude route targets the orchestrator; it does NOT revert
  to codex or notify-only.
- No orchestrator-side writer for the session-id file in this wave. The
  writer is a separate, explicitly-deferred follow-up. This deferral is
  safe because W2's absent-file branch is deterministic (plain `-p`): the
  wave lands a real, observable change in live behavior on merge without
  depending on any writer ever being authored. When the writer does land
  in a follow-on wave, the `--resume <id>` branch activates and restores
  conversation-targeted wake-up semantics.
- No modifications to other Claude subprocesses (`phase_a_executor`,
  `phase_b_executor`, `bot_remediation`) — they remain on their existing
  invocation paths. This wave does not audit or alter their `--continue`
  behavior, if any.
- No L3 parity work: `mu/tools/observability/pipeline_agent_pager.py` is
  host-side Python pipeline tooling, not substrate runtime. No JS mirror
  (`mu/host/js/eval_step.js`) edit is required or permitted by this wave.
- No doc-governance rewrites; a short code-level docstring/comment on the
  session-id file path is sufficient.
- No changes to `tests/docs/`, `tests/l4_gates/`, seeds, or ratchet tables.
- No widening to other bot findings on PR #794 beyond the P1 determinism
  finding.
- No restoration of conversational wake-up semantics in this wave. The
  trade-off is explicit: pings to `claude -p <prompt>` begin a fresh
  conversation that is not attached to the interactive orchestrator. The
  wake-up UX regression is accepted as the cost of making dispatch
  deterministic in the current repo state; the follow-on writer wave
  restores the wake-up path via `--resume`.

## 4. Stop conditions

Phase B MUST stop and return to Phase A for re-plan if any of the following
holds after initial diagnosis:

S1. The proposed orchestrator-session-id file path collides with an
    existing file under `.agent_bus/observability/` (namespace conflict).
S2. `_dispatch_claude` cannot be made to never-emit-`-c` without modifying
    upstream callers or a separate dispatch helper beyond the pager module
    (scope breach — the deletion is supposed to be purely local to
    `_dispatch_claude`).
S3. Tests cannot be authored without importing real `claude` binary
    behavior (e.g., no seam to mock `subprocess.run`) — indicates a
    structural refactor beyond this wave's scope.
S4. The existing test module `mu/tests/tools/test_pipeline_agent_pager.py`
    requires non-trivial refactor (moving fixtures, reorganizing classes)
    to accommodate W4 — that refactor is a separate MAINTENANCE item.
S5. W5's `claude_continue` removal surfaces a third reader of the key not
    listed in §1 — stop and decide whether removal widens scope.

Normal completion stop: work items W1-W5 land, tests green at audit tier 1,
`git grep` shows `_dispatch_claude` no longer emits `-c` / `--continue`, and
bot P1 on PR #794 can be dispositioned as addressed.

## 5. Acceptance criteria

A1. After this wave merges, `_dispatch_claude` in
    `mu/tools/observability/pipeline_agent_pager.py` NEVER emits `-c` or
    `--continue` in argv, in any branch. Verified by code inspection
    (`git grep -n '"-c"' mu/tools/observability/pipeline_agent_pager.py`
    returns no hit inside `_dispatch_claude`'s body) AND by W4's unit
    tests asserting absence of those flags in constructed argv.

A2. With the orchestrator-session-id file present and containing a valid
    non-empty id, the pager's argv is exactly
    `[<claude_bin>, "--resume", <id>, "-p", <prompt>]`. Verified by a
    W4 unit test asserting on the argv list passed to `subprocess.run`.

A3. With the orchestrator-session-id file absent (the current repo
    state), the pager's argv is exactly
    `[<claude_bin>, "-p", <prompt>]`. This is a deliberate behavioral
    change from post-PR-#794 behavior (which was
    `[<claude_bin>, "-c", "-p", <prompt>]`). The change is verified by a
    W4 unit test that asserts the argv list and asserts absence of `"-c"`,
    `"--continue"`, and `"--resume"` in it. This criterion is the direct
    remediation of PR #794's bot P1 finding: the live behavior on merge
    is non-`--continue` regardless of any follow-on writer.

A4. Malformed / empty / whitespace-only session-id file does not raise;
    pager falls back to A3's plain-`-p` branch. Verified by W4 unit tests.

A5. `claude_continue` is no longer read by any production code path. For
    W5a: the key's value in `executor_config.json:25` is `false` and
    `pipeline_agent_pager.py`'s `_dispatch_claude` contains no reference
    to it. For W5b: the key is absent from `executor_config.json`,
    `executor_common.py`'s default fixture, and any remaining test
    fixtures. Verified by `git grep claude_continue` after the edit.

A6. `./tools/audit_fast.sh` passes (tier 1). New tests are not marked
    `@pytest.mark.slow` (argv-construction tests with mocked
    `subprocess.run`, <1s each, consistent with the existing
    `test_pipeline_agent_pager.py` patterns).

A7. `pre-push-fast` (tier 2 pre-push hook) passes — standard for all
    commits.

A8. No file under `mu/host/js/`, `tests/docs/`, `tests/l4_gates/`, or any
    runtime substrate directory is touched. Verified by
    `git diff --name-only` on the wave's HEAD.

A9. Tracker note in `TASKS.md` for `[PIPELINE-AGENT-PAGER]` is updated on
    closure (not in this Phase A file) to record the determinism fix,
    cross-reference the resulting PR, mark PR #794's bot P1 as addressed,
    and flag the orchestrator-session-id writer as the next follow-on.

## 6. Grounding / Authorization

- **TASKS.md authorization:** `[PIPELINE-AGENT-PAGER]` QUEUED entry at
  `TASKS.md:192-200`, specifically the 2026-04-18 follow-up note at
  line 199 that names this wave and records
  `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup`.
- **Tracked packet (governing):** this file,
  `reports/control_plane/pager_deterministic_session_2026-04-18.md`
  (referenced at `TASKS.md:200`).
- **Prior-wave packet (prerequisite merged):** PR #794 commit `7e2c8f48`
  landed `route: "claude"` + `claude_continue: true`; this wave addresses
  the bot P1 finding on that PR by removing `-c` / `--continue` from the
  pager's dispatch path entirely.
- **Lane:** control-surface (agent automation / observability), matching
  the parent task's lane at `TASKS.md:198`.
- **L4 class (proposed):** `MAINTENANCE` — fixes a determinism defect in
  host-side pipeline tooling, no runtime/substrate change, no new L4 gate
  evidence. Final class is set by the commit executor / L4 contract check;
  flagged here so the bridge reviewer can challenge if a different class
  is appropriate. Running under
  `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup`.
- **Parity note:** no L3 Python/JS parity implication — the pager is
  host-only pipeline observability tooling, not a substrate projection.
- **Rev 2 trigger:** bridge REQUEST_CHANGES against Rev 1 observed that
  Rev 1 deferred the only deterministic-dispatch mechanism (`--resume`
  gated on an absent session-id file, writer out of scope). Rev 2
  eliminates that gap by removing `-c` from the fallback, so the wave
  changes live behavior on merge even with the writer still deferred.
