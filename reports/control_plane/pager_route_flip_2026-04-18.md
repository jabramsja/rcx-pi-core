# Phase A Plan: pager-route-flip-2026-04-18

## Status

Phase A plan (rewritten 2026-04-18 after a third bridge review
REQUEST_CHANGES). The three blocking findings addressed by this rewrite:

- **DOC_ACCURACY (FOUNDER_OVERRIDE token).** The previous rewrite
  invented a new `FOUNDER_OVERRIDE:pager-route-flip-2026-04-18` token
  specific to this sub-wave. No repo-tracked evidence authorizes a
  second override token for this pager slice. TASKS.md:195 and the
  locked parent packet
  `reports/control_plane/pipeline_agent_pager_2026-04-16.md:29-35`
  both authorize exactly one bounded override for this slice:
  `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup`, used
  "to bypass the non-structural adjacency and rolling-window caps
  while committing this MAINTENANCE wave." This rewrite removes the
  invented token and uses only the tracked one from the parent lane.

- **DEFECT (L4 class mismatch).** The previous rewrite reclassified
  the route flip as `L4_ENABLER`, but the governing parent packet is
  locked at `Wave class: MAINTENANCE`
  (`reports/control_plane/pipeline_agent_pager_2026-04-16.md:8`) and
  TASKS.md:195 explicitly names the tracked override as applying to
  "this MAINTENANCE wave." No tracked re-authorization exists to
  promote this bounded sub-wave out of MAINTENANCE. This rewrite sets
  the L4 classification to `MAINTENANCE`, adds the required
  `no_op_proof` and `defer_reason_code` fields, and restates AC6 in
  MAINTENANCE terms (tracked override clears the non-structural
  adjacency and rolling-window caps for this MAINTENANCE landing).

- **DEFECT (growth-cap contingency).** The previous rewrite marked
  docs-governance changes out of scope and forbade any change outside
  three paths. The locked parent packet keeps
  `mu/tests/docs/test_growth_caps.py` in scope (line 94) and
  explicitly permits the narrow growth-cap acknowledgement edit at
  lines 359-363 if this packet's additions push the repo over the
  docs growth-cap gate, with parent-packet constraint #12 (line 388)
  forbidding any docs-governance edit beyond that file. If the gate
  trips under the previous rewrite's wording, the implementer would
  have to violate either the plan or the parent packet. This rewrite
  admits `mu/tests/docs/test_growth_caps.py` as a conditional
  fourth path, admitted only if the growth-cap gate blocks the
  commit path, and only to acknowledge the pager additions actually
  produced by this wave. No other docs-governance edits are admitted.

## Goal

Flip two values in `mu/tools/executors/executor_config.json` at lines
22-26:
- `"route": "notify-only"` → `"route": "claude"`
- `"claude_continue": false` → `"claude_continue": true`

This activates the already-implemented `_dispatch_claude` path at
`mu/tools/observability/pipeline_agent_pager.py:650-697`. At runtime,
the pager subprocess command for the 6 currently allowed event types
(`ALLOWED_EVENT_TYPES` at `pipeline_agent_pager.py:48-55`:
`phase_b_reviewer_started`, `recovery_started`, `recovery_state_changed`,
`recovery_failed`, `pipeline_hard_fail`, `commit_ready`) changes from
`[claude, "-p", <prompt>]` to `[claude, "-c", "-p", <prompt>]`. The
`-c` flag is a documented Claude CLI feature (resume the repo's most
recent Claude conversation) — it is a property of the `claude` CLI,
**not implemented by this wave**. This wave only flips the
command-shape selector and proves the flip in-diff.

Without the flip, the 6 allowed pager events are emitted through the
`notify-only` path and do not reach the orchestrator Claude session
as in-session turns.

This wave is a route-flip prerequisite under the `[PIPELINE-AGENT-PAGER]`
lane. It does NOT, by itself, deliver the founder's full quoted
multi-wave transition-paging scope. See Acceptance and Closeout for the
explicit residual partition.

## Grounding / Authorization

- **Primary authorization — TASKS.md `[PIPELINE-AGENT-PAGER]`,
  lines 191-197.** QUEUED (2026-04-16, founder-directed post-merge
  follow-up). Verbatim from TASKS.md:
  > Shared pipeline transition pager: authoritative executor-side
  > transition emission plus Codex App Server / Claude Code adapters
  > so important pipeline changes can wake agents without continuous
  > model watching.
  >
  > **Priority:** first queued post-merge follow-up once the active
  > [PIPELINE-RECOVERY] hybrid recovery wave lands.
  >
  > **Tracked packet:** `reports/control_plane/pipeline_agent_pager_2026-04-16.md`
  >
  > **Lane:** control-surface (agent automation / observability).
  The active hybrid recovery wave referenced by the priority condition
  has landed (precedent below: PR #786 flipped `enabled: true` and
  `hybrid_recovery_enabled: true`), so the queued follow-up is now
  eligible. The present wave is the minimal route-flip sub-wave
  under that tracked packet's scope.

- **`[PIPELINE-RECOVERY]` is NOT cited as authorization for this wave.**
  TASKS.md:212-224 routes that label to recovery-tier work anchored to
  `mu/docs/agents/PipelineRecovery.v0.md` (design) and
  `mu/tools/executors/recovery_gate.py` (file), with tracked packet
  `reports/control_plane/hybrid_recovery_agent_2026-04-16.md`. The
  pager-route flip touches none of those surfaces and is not governed
  by that tracked packet.

- **Founder in-session directive 2026-04-18 (verbatim, multi-wave
  scope).**
  > "remember, after this wave, before the next wave, turn on full
  > pager pings and hybrid recovery. You will need to be aware if you
  > are not receiving pings, or getting errors, and fix those as well."

  > "if you had a ping for this, i wouldn't have to tell you..it's
  > fail closed with a question..you would have gotten that ping..
  > otherwise you'd be waiting for who knows how long".

  > "you should be getting pings for phase A (reviewer/implementer
  > transitions), then output for converged/No_go...transition to
  > Phase B, pings for implementer/reviewer transitions...any
  > failing (shouldn't fail silently..should ping you), and also any
  > recovery agent routing".

  This directive describes the steady-state post-completion behavior
  of the entire `[PIPELINE-AGENT-PAGER]` lane. It is NOT a one-wave
  deliverable. The route flip in this packet is a strict prerequisite
  for any of the listed pings to reach the orchestrator session as
  in-session turns; the listed events that are not yet emitted (Phase A
  reviewer/implementer transitions, converged/NO_GO output emission,
  Phase B implementer transitions, fail-closed pings beyond
  `pipeline_hard_fail`) require new executor-side emit call sites and
  widening of `ALLOWED_EVENT_TYPES` and remain owned by the parent
  `[PIPELINE-AGENT-PAGER]` tracked packet
  `reports/control_plane/pipeline_agent_pager_2026-04-16.md` as
  follow-up sub-waves after this one.

- **Precedent for session-level authorization + config-flip pattern.**
  `reports/control_plane/enable_pager_and_hybrid_recovery_2026-04-17.md`
  landed as PR #786 using the same config-flip pattern with in-session
  founder directive + `FOUNDER_OVERRIDE` tracker-note capture. That
  wave flipped `enabled: true` (from false) and
  `hybrid_recovery_enabled: true`. The present wave is the natural
  continuation along the same `[PIPELINE-AGENT-PAGER]` lane — finish
  the pager route now that the pager is `enabled: true`.

`FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup` — the
tracked pager-slice override authorized in TASKS.md:195 ("use
`FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup` to bypass
the non-structural adjacency and rolling-window caps while committing
this MAINTENANCE wave") and recorded in the parent packet's Grounding
section
`reports/control_plane/pipeline_agent_pager_2026-04-16.md:29-35`.
This route-flip sub-wave operates inside that same MAINTENANCE
classification and inherits the same bounded override. No new or
second override token is introduced by this wave.

## Scope

Implementer stages three unconditional paths, and one conditional
fourth path admitted ONLY if the docs growth-cap gate blocks the
commit:

1. `mu/tools/executors/executor_config.json` — two value edits on the
   `pipeline_agent_pager` object (`route` and `claude_continue`).
2. `mu/tests/tools/test_pipeline_agent_pager.py` — one new test added
   adjacent to `test_claude_ack_requires_zero_exit` (currently at
   lines 550-574). The new test asserts that when
   `claude_continue: True` is passed to `_dispatch_claude`, the
   captured `subprocess.run` call receives `"-c"` ahead of `"-p"`
   in the command list. Existing tests in that file are **not
   modified**. Repo-local verification: grep shows the file currently
   contains `claude_continue` at line 24 (helper default `False`)
   and line 556 (`{"pipeline_agent_pager": {"claude_continue": False}}`)
   only — there is no existing assertion on the `-c` branch.
3. `reports/control_plane/pager_route_flip_2026-04-18.md` — this
   plan packet (added via `git add` at `commit_executor.py` Step 4,
   standard for every wave).
4. `mu/tests/docs/test_growth_caps.py` — **conditional, admitted
   only if the growth-cap gate blocks the commit path.** This is the
   same narrow adjacency already authorized in the parent packet
   (`reports/control_plane/pipeline_agent_pager_2026-04-16.md:94`
   keeps this file in scope; lines 359-363 permit it "only far
   enough to acknowledge those two wave-owned additions"; line 388
   forbids widening docs-governance edits beyond this single file).
   For this route-flip sub-wave, the only wave-owned additions
   capable of tripping the growth-cap gate are (a) the single new
   test function added to `test_pipeline_agent_pager.py` in W3 and
   (b) this plan packet itself. Any acknowledgement edit to
   `test_growth_caps.py` is bounded to those two additions. If the
   growth-cap gate does not trip, no edit to this file is staged.

**NOT in scope (owned by the parent `[PIPELINE-AGENT-PAGER]` tracked
packet `reports/control_plane/pipeline_agent_pager_2026-04-16.md`):**

- No code edits to `pipeline_agent_pager.py` (`_dispatch_claude` at
  lines 650-697 is already implemented — see lines 660-661 for the
  `if continue_flag: command.append("-c")` construction this wave
  activates).
- No widening of `ALLOWED_EVENT_TYPES` (currently the 6 events at
  `pipeline_agent_pager.py:48-55`). The founder's quoted scope
  explicitly names categories not in the current allow-list:
  - Phase A reviewer/implementer transitions
    (no `phase_a_reviewer_started` / `phase_a_implementer_started` in
    `ALLOWED_EVENT_TYPES`).
  - Converged/NO_GO output emission
    (no `phase_a_converged` / `phase_a_no_go` in `ALLOWED_EVENT_TYPES`).
  - Phase B implementer transitions
    (only `phase_b_reviewer_started` is allowed; no
    `phase_b_implementer_started`).
  - Any-failure pings beyond `pipeline_hard_fail`
    (e.g. per-step or per-gate failure events).
  These are all owned by the parent tracked packet and explicitly
  outside this wave.
- No new executor-side emit call sites — same parent tracked packet.
- No Codex App Server / Claude Code adapter parity changes — same
  parent tracked packet.
- No TASKS.md edits. TASKS.md:191-197 already authorizes this lane
  under `[PIPELINE-AGENT-PAGER]`; no new Session note is added by this
  wave.
- No changes to `enabled`, `hybrid_recovery_enabled`, or timeouts.
- No runtime directory edits (`mu/host/**`, `rcx_pi/**`).
- No docs-governance edits outside `mu/tests/docs/test_growth_caps.py`
  (no DOC_STATUS, DOC_CONTRACTS, STATUS.md, CHANGELOG.md edits). This
  mirrors parent packet constraint #12 at line 388.

## Constraints

- No runtime directory edits (`mu/host/**`, `rcx_pi/**`).
- Test edits in `mu/tests/tools/test_pipeline_agent_pager.py` are
  strictly bounded to the single added test described in W3.
  Existing tests in that file are not modified; no other
  `mu/tests/tools/` test files are touched.
- No hook edits.
- Docs-governance edits bounded to `mu/tests/docs/test_growth_caps.py`
  only (matching parent packet constraint #12 at
  `reports/control_plane/pipeline_agent_pager_2026-04-16.md:388`), and
  only staged if the growth-cap gate blocks the commit path, and only
  far enough to acknowledge this wave's two additions (the new pager
  test function and this plan packet). No other docs-governance files
  (DOC_STATUS, DOC_CONTRACTS, STATUS.md, CHANGELOG.md) are modified.
  TASKS.md is not modified (TASKS.md:191-197 already authorizes this
  lane).
- No edits to `mu/tools/observability/pipeline_agent_pager.py`,
  `mu/tools/executors/recovery_gate.py`, or any executor-side emit
  call site — all such work is owned by the parent tracked packet.

## L4 Classification

This sub-wave inherits the parent packet's locked classification at
`reports/control_plane/pipeline_agent_pager_2026-04-16.md:8`
(`Wave class: MAINTENANCE`). TASKS.md:195 names the same slice as
"this MAINTENANCE wave" when granting the tracked override. No
repo-tracked evidence re-authorizes promotion out of MAINTENANCE for
this sub-wave.

| Field | Value |
|-------|-------|
| class | `MAINTENANCE` |
| target_gate_id | G8 (pipeline self-repair / recovery effectiveness; pager observability is a G8 capability — inherited from parent packet header) |
| primary_blocker_class | INTEGRATION |
| primary_invariant_id | INV_STRUCTURAL_FORWARD_MOTION |
| bootstrap_endgame_policy | SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP |
| boot0_track_id | V1 |
| boot0_progress_state | HOLD |
| indicator_artifact_ref | `mu/tools/executors/executor_config.json` `pipeline_agent_pager` block (lines 22-26) — post-merge, `route: "claude"` + `claude_continue: true` |
| indicator_collection_command | `python3 -c "import json; c=json.load(open('mu/tools/executors/executor_config.json'))['pipeline_agent_pager']; assert c['route']=='claude', c; assert c['claude_continue']==True, c; print('OK')"` |
| no_op_proof | This wave advances no L4 gate by itself. It flips two control-surface config values (`route`, `claude_continue`) so that the already-landed `_dispatch_claude` path at `mu/tools/observability/pipeline_agent_pager.py:650-697` is reachable for the 6 currently allowed event types. No runtime dirs are touched (`mu/host/**`, `rcx_pi/**` unmodified). No new gate evidence is produced. Verified by `indicator_collection_command` above + the unit test added in W3. |
| defer_reason_code | `PREREQUISITE_FOR_LATER_L4_EVIDENCE` — this config flip is the prerequisite so later `[PIPELINE-AGENT-PAGER]` sub-waves (widening `ALLOWED_EVENT_TYPES`, adding executor-side emit call sites) can be mechanically observed as they land. Without the route flip, future pager events would still be emitted through `notify-only` and would not wake the orchestrator session, making later structural waves hard to audit without continuous model watching. |
| MAINTENANCE runtime-dirs check | This wave touches NO runtime dirs — only the control-surface config JSON, the matching test file in `mu/tests/tools/`, this plan packet, and (conditionally) `mu/tests/docs/test_growth_caps.py` if the growth-cap gate trips. `mu/host/**` and `rcx_pi/**` are unmodified. |
| MAINTENANCE consecutive-cadence | The parent packet is MAINTENANCE. The tracked override `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup` (TASKS.md:195) expressly bypasses "the non-structural adjacency and rolling-window caps while committing this MAINTENANCE wave." No second override is introduced for this sub-wave. |
| evidence_command (context) | `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py && python3 -c "import json; c=json.load(open('mu/tools/executors/executor_config.json'))['pipeline_agent_pager']; assert c['route']=='claude', c; assert c['claude_continue']==True, c; print('OK')"` (MAINTENANCE does not require `evidence_command`; shown here for reviewer convenience). |
| evidence_delta (context) | (a) `mu/tools/executors/executor_config.json` `pipeline_agent_pager.route` flipped `"notify-only"` → `"claude"`; (b) `pipeline_agent_pager.claude_continue` flipped `false` → `true`; (c) `enabled: true` unchanged; (d) `mu/tests/tools/test_pipeline_agent_pager.py` gains one new test asserting `"-c"` appears in the `subprocess.run` command list when `_dispatch_claude` is invoked with `claude_continue: True` — in-diff proof of the command-shape change; (e) at runtime, `_dispatch_claude` at `pipeline_agent_pager.py:650-697` constructs `[claude, "-c", "-p", <prompt>]` for the 6 currently allowed event types only (the founder's broader directive scope remains owned by the parent `[PIPELINE-AGENT-PAGER]` tracked packet). MAINTENANCE does not require `evidence_delta`; shown here for reviewer convenience. |

## Work items

**W1 — flip `pipeline_agent_pager.route`.** In
`mu/tools/executors/executor_config.json` at the current line 24:
```
  "route": "notify-only"
```
becomes:
```
  "route": "claude"
```

**W2 — flip `pipeline_agent_pager.claude_continue`.** In
`mu/tools/executors/executor_config.json` at the current line 25:
```
  "claude_continue": false
```
becomes:
```
  "claude_continue": true
```

**W3 — add one unit test proving the `-c` branch.** In
`mu/tests/tools/test_pipeline_agent_pager.py`, add a new test
adjacent to `test_claude_ack_requires_zero_exit` (currently at lines
550-574). The new test:

- Builds a `_build_event_record` with `route="claude"`.
- Sets `config = {"pipeline_agent_pager": {"claude_continue": True}}`.
- Patches `pager_mod.subprocess.run` with a return of
  `subprocess.CompletedProcess(["claude", "-c", "-p"], 0, "ok", "")`
  and captures the call args.
- Calls `pager_mod._dispatch_claude(tmp_path, event, config, timeout_s=5)`.
- Asserts the captured `args[0]` (the command list passed to
  `subprocess.run`) contains `"-c"` at an index strictly less than
  the index of `"-p"` — proving that `claude_continue: True` in
  config flows into the subprocess command shape.
- Asserts `acknowledged is True` and `ack["target"] == "claude"`.

Existing tests in `test_pipeline_agent_pager.py` are not modified.

W1+W2+W3 all land in the same commit. No other file changes.

## Stop conditions

Stop (do not expand scope further) when ALL of the following hold:

1. `mu/tools/executors/executor_config.json`
   `pipeline_agent_pager.route` equals `"claude"`.
2. `mu/tools/executors/executor_config.json`
   `pipeline_agent_pager.claude_continue` equals `true`.
3. `pipeline_agent_pager.enabled` equals `true` (UNCHANGED — already was).
4. `mu/tests/tools/test_pipeline_agent_pager.py` contains one newly
   added test (and only one) asserting `"-c"` appears before `"-p"`
   in the `_dispatch_claude` `subprocess.run` command list when
   `claude_continue: True`. Existing tests in that file are
   byte-identical.
5. No file modifications outside (a) `executor_config.json`,
   (b) `test_pipeline_agent_pager.py`, (c) this plan packet, and
   (d) — **only if the growth-cap gate blocks the commit path** —
   `mu/tests/docs/test_growth_caps.py`, edited only far enough to
   acknowledge this wave's two additions (the new pager test
   function and this plan packet). If the growth-cap gate does not
   trip, path (d) stays unmodified and staged modifications total
   three paths.
6. `commit_executor.py` Step 11 `pre-push-fast` passes.

## Acceptance criteria

This wave's success is the route-flip prerequisite ONLY. It does NOT
assert that the founder's quoted multi-wave transition-paging directive
is fully delivered. Residual scope is partitioned in AC8 and Closeout.

- **AC1:** `python3 -c "import json; c=json.load(open('mu/tools/executors/executor_config.json'))['pipeline_agent_pager']; print(c)"`
  outputs `{'enabled': True, 'route': 'claude', 'claude_continue': True}`.
- **AC2:** `git diff --cached mu/tools/executors/executor_config.json`
  shows EXACTLY two value changes: `"route"` and `"claude_continue"`.
  No other JSON keys modified.
- **AC3:** `git diff --cached mu/tests/tools/test_pipeline_agent_pager.py`
  is a **pure addition** of one new test function that asserts the
  `-c` branch command shape. No lines removed; no existing test
  functions modified.
- **AC4:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short
  mu/tests/tools/test_pipeline_agent_pager.py` exits 0. The new
  test is present in the collected set and passes.
- **AC5:** No changes outside
  `mu/tools/executors/executor_config.json`,
  `mu/tests/tools/test_pipeline_agent_pager.py`, this plan packet,
  and — **only if the growth-cap gate blocks the commit path** —
  a narrow acknowledgement edit to
  `mu/tests/docs/test_growth_caps.py` covering this wave's two
  additions (the new pager test function and this plan packet). No
  other docs-governance files are modified. If the growth-cap gate
  does not trip, the final staged diff spans exactly three paths.
- **AC6:** `commit_executor.py` Step 11 `pre-push-fast` passes. This
  wave is classified `MAINTENANCE` (inherited from the parent
  packet's locked `Wave class: MAINTENANCE`). The tracked override
  `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup`
  (TASKS.md:195) clears the non-structural adjacency and
  rolling-window caps for this MAINTENANCE landing — verbatim:
  "bypass the non-structural adjacency and rolling-window caps while
  committing this MAINTENANCE wave." MAINTENANCE-specific
  `no_op_proof` and `defer_reason_code` fields are present in the
  L4 Classification table and must appear in the commit tracker note
  (enforced by `tools/checks/enforce_l4_execution_contract.py`).
- **AC7:** Commit tracker note cites:
  - wave_class: `MAINTENANCE`
  - `no_op_proof` and `defer_reason_code` (as rendered in the L4
    Classification table above),
  - the parent `[PIPELINE-AGENT-PAGER]` lane (TASKS.md:191-197) with
    tracked packet
    `reports/control_plane/pipeline_agent_pager_2026-04-16.md`, and
  - `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup` (the
    tracked pager-slice override — no new or second override token
    is introduced by this wave).
  The tracker note does NOT cite `[PIPELINE-RECOVERY]` as
  authorization (that label governs recovery-tier work, not pager
  work).
- **AC8 (scope-honesty disclaimer, addresses bridge Finding 1).**
  This wave's "done" state explicitly does NOT assert that the
  founder's full quoted transition-paging scope is delivered.
  Specifically, on merge of this wave, the following founder-named
  surfaces are still NOT pinging the orchestrator session, and remain
  owned by the parent `[PIPELINE-AGENT-PAGER]` tracked packet
  `reports/control_plane/pipeline_agent_pager_2026-04-16.md`:
  - Phase A reviewer/implementer transitions
    (no `phase_a_*` events in `ALLOWED_EVENT_TYPES`).
  - Phase A converged / NO_GO output emission to the orchestrator.
  - Phase B implementer transitions
    (only `phase_b_reviewer_started` is allowed; no
    `phase_b_implementer_started`).
  - Any-failure pings beyond `pipeline_hard_fail`.
  Any post-merge audit that finds these surfaces still silent is
  expected behavior of this wave's bounded scope, not a regression.
  Closure of those surfaces is the next sub-wave under
  `[PIPELINE-AGENT-PAGER]`.

## Closeout

On merge:

1. The 6 currently allowed pager events (`phase_b_reviewer_started`,
   `recovery_started`, `recovery_state_changed`, `recovery_failed`,
   `pipeline_hard_fail`, `commit_ready`) produce subprocess
   invocations of `claude -c -p <prompt>` at each transition. The
   in-diff proof of this command-shape change is the new test added
   by W3. The downstream behavior that `claude -c` resumes the repo's
   most recent Claude conversation is a property of the `claude` CLI
   itself and is outside this wave's diff.

2. **Founder's full quoted directive is NOT closed by this wave.** The
   directive's scope spans multiple sub-waves under
   `[PIPELINE-AGENT-PAGER]`. The residual deliverables that remain
   owned by the parent tracked packet
   `reports/control_plane/pipeline_agent_pager_2026-04-16.md` after
   this wave merges are, at minimum:
   - Widening `ALLOWED_EVENT_TYPES` at
     `mu/tools/observability/pipeline_agent_pager.py:48-55` to admit
     Phase A reviewer/implementer transition events, Phase A
     converged / NO_GO output events, Phase B implementer transition
     events, and any-failure events beyond `pipeline_hard_fail`.
   - Adding executor-side emit call sites that publish those events
     (Phase A executor emit on reviewer/implementer transition and on
     converged/NO_GO; Phase B executor emit on implementer
     transition; any-failure emit at gate failure points).
   - Codex App Server / Claude Code adapter parity for those new
     event types.
   None of those items are delivered by the present route flip;
   declaring this wave done does NOT close the founder's broader
   quoted scope.

3. No deferred packet is closed by this wave (it is a fresh config
   enabler on top of already-landed pager infrastructure, not a
   closure of a prior gap).
