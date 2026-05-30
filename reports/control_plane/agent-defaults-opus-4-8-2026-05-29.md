# Agent-Defaults-Opus-4-8-2026-05-29

Date: 2026-05-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [agent-defaults-opus-4-8-2026-05-29]
Wave ID: agent-defaults-opus-4-8-2026-05-29
Wave class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Governing packet: reports/control_plane/agent-defaults-opus-4-8-2026-05-29.md
FOUNDER_OVERRIDE:agent-defaults-opus-4-8-2026-05-29

## Purpose

Switch the DEFAULT pipeline implementer AND reviewer to Claude Opus 4.8 at
`max` effort, persistently for all future sessions, AND make the
config-alignment test structural so future provider/model/effort changes are
config-only (no test rewrite).

The role-switch control surface already exists (`role_agents` +
`bridge_agent_defaults` in `executor_config.json`, materialized into
`backends`/`bridge_reviewers` at load time, with model/effort injected into
adapter commands by `bridge_adapters._apply_agent_defaults`). This wave
COMPLETES that mechanism for the opus-4-8 default — it does NOT introduce a new
parallel mechanism. Work within the existing surfaces only.

## Scope (in)

- `mu/tools/executors/executor_config.json` — authoritative tracked defaults
  (`role_agents`, `bridge_agent_defaults.claude`).
- `mu/tools/executors/executor_common.py` — `DEFAULT_EXECUTOR_CONFIG` and
  `DEFAULT_AGENT_DISPLAY_NAMES` (keep in sync with live config; the alignment
  test asserts defaults == live).
- `mu/tests/tools/test_executor_config_alignment.py` — de-brittle: replace
  literal value pins with structural invariants. PRESERVE the defaults==live
  sync guards.
- `TASKS.md` — tracker note (commit_executor inserts).
- This packet.
- `reports/l4_wave_indicators/agent-defaults-opus-4-8-2026-05-29.json` — L4
  indicator (collector produces; force-add at commit).

## Scope (out)

- Runtime/substrate dirs (`rcx_pi/selfhost/`, `mu/host/`) — L4_ENABLER must not
  touch runtime.
- Branch-protection / workflow.
- Gitignored `.agent_bus/bridge_config.json` — its hardcoded cmd is OVERRIDDEN
  by the tracked `bridge_agent_defaults` at load time, so it needs no edit.
- `~/.claude/*` and `~/.codex/*` — out of repo. (The go-live removal of the
  `RCX_BRIDGE_REVIEWER_OVERRIDE=codex` session shadow in `~/.claude/settings.json`
  is a SEPARATE post-merge step, NOT part of this wave.)

## Work Items

### C4 — Flip defaults to Claude Opus 4.8 max

- `role_agents.implementer` → `claude`
- `role_agents.reviewer` → `claude`
- `bridge_agent_defaults.claude` → `{"display_name":"Claude Opus 4.8 max",
  "model":"claude-opus-4-8", "effort":"max"}`
- Leave `bridge_agent_defaults.codex` UNCHANGED (so codex remains a one-line
  swap-back target).
- `DEFAULT_AGENT_DISPLAY_NAMES["claude"]` → `"Claude Opus 4.8 max"`.
- Do NOT hand-edit `backends` / `bridge_reviewers` static blocks —
  `_materialize_role_agents` overwrites them from `role_agents` on every load.

### C3 — De-brittle the alignment test

Replace literal value pins (which hard-code `codex`/`codex` + `claude-opus-4-7`)
with structural invariants so future changes are config-only:

- PRESERVE: `bridge_agent_defaults` (and `role_agents`) in
  `DEFAULT_EXECUTOR_CONFIG` must equal the live `executor_config.json` values
  (the existing sync guards).
- `role_agents` keys are exactly `{implementer, reviewer}`, each value in
  `{claude, codex}`.
- `bridge_agent_defaults` has both providers; each carries its required keys
  (claude: `display_name`/`model`/`effort`; codex:
  `display_name`/`model`/`reasoning_effort`).
- Drop hard-coded model-string and display-string equality assertions.

## Constraints

- Existing surfaces only — no new parallel ownership mechanism.
- L4_ENABLER: must not touch runtime/substrate dirs.
- No `--no-verify`, no manual git ops — full pipeline path.
- If the plan diverges in bridge review, NARROW (drop claims), do not expand.

## Stop Conditions

- PRECONDITION (satisfied): `TASKS.md` now contains the current-task
  authorization block for `[agent-defaults-opus-4-8-2026-05-29]` at
  TASKS.md:553-556 (the `[AGENT-DEFAULTS-OPUS-4-8]` OPEN block + tracker sync
  note); `rg -n "agent-defaults-opus-4-8-2026-05-29" TASKS.md` returns matches.
  TASKS.md:67-69 says authorization lives in TASKS.md, and it now does.
- Both C3 and C4 are required deliverables (see Acceptance Criteria); there is
  no drop-C3 fallback. If bridge review diverges, NARROW the C3 assertions
  (assert fewer structural invariants) rather than dropping any work item —
  never ship a variant that contradicts the Acceptance Criteria.
- Do NOT add reviewer-shadow visibility/warning work to this wave (that is a
  separate hardening wave).

## Acceptance Criteria

- Before non-packet implementation, `rg -n
  "agent-defaults-opus-4-8-2026-05-29" TASKS.md` returns the TASKS.md
  current-task authorization block for this wave.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_config_alignment.py`
  passes with `role_agents` = claude/claude and
  `bridge_agent_defaults.claude.model` = `claude-opus-4-8`.
- The defaults==live sync guard still passes (defaults updated in lockstep).
- De-brittleness demonstrated: changing provider/model/effort in the live config
  to another valid combination does not require editing the test.
- `pre-push-fast` (audit_fast + L4 contract) passes.

## Grounding / Authorization

TASKS.md authorization rule: TASKS.md:67-69 states that roadmap/docs define
sequence and design only, current state lives in STATUS.md, and authorization
lives in TASKS.md. Therefore this wave requires a TASKS.md current-task block
for `[agent-defaults-opus-4-8-2026-05-29]` before implementation.

Current TASKS.md evidence: the targeted lookup now returns matches:

`rg -n "agent-defaults-opus-4-8-2026-05-29" TASKS.md` → lines 554 (tracked
packet) and 556 (tracker sync note). The full current-task authorization block
spans TASKS.md:553-556: the `[AGENT-DEFAULTS-OPUS-4-8]` **OPEN** header (553),
the tracked-packet pointer (554), the lane (555), and the tracker sync note
(556).

TASKS.md now contains the current-task authorization block, so this packet's
implementation-authorization precondition is satisfied.

Governing packet: `reports/control_plane/agent-defaults-opus-4-8-2026-05-29.md`.

Founder directive (verbatim): "we want to make sure that all reviewers and
implementers are claude opus 4.8 max ... As well as making it easy to change for
the future"; "the idea is that it should be easy to choose which agent is the
implementer, and which one is the reviewer ... including allowing model and
effort change. Try to work within what we already have"; "you can also use the
builders that are provided to help."

This consciously overrides the standing "all reviewers = Codex" rule for the
DEFAULT, by explicit founder instruction, scoped Persistent (all sessions).

NOTE (not in scope for this wave): a session-level
`RCX_BRIDGE_REVIEWER_OVERRIDE=codex` currently lives in
`~/.claude/settings.json` and silently shadows the reviewer role for all
sessions (env-first precedence in `resolve_role_agent`). Removing it is the
post-merge go-live step so that THIS switch wave is itself codex-reviewed; it is
intentionally excluded here.

FOUNDER_OVERRIDE:agent-defaults-opus-4-8-2026-05-29 — clears non-structural
adjacency / rolling-window caps for this L4_ENABLER. Standing autonomous-fix
authorization applies if the pipeline breaks (manual unblock + root structural
fix).

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `agent-defaults-opus-4-8-2026-05-29`
- Active packet: `reports/control_plane/agent-defaults-opus-4-8-2026-05-29.md`
- Indicator artifact: `reports/l4_wave_indicators/agent-defaults-opus-4-8-2026-05-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_config_alignment.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/agent-defaults-opus-4-8-2026-05-29.md`
  - `reports/l4_wave_indicators/agent-defaults-opus-4-8-2026-05-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `agent-defaults-opus-4-8-2026-05-29`
- Active packet: `reports/control_plane/agent-defaults-opus-4-8-2026-05-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7a7281628da4f053aef02a70e2e27c065f643400b51e68d7dc75f683b9655898`
- Indicator artifact: `reports/l4_wave_indicators/agent-defaults-opus-4-8-2026-05-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/agent-defaults-opus-4-8-2026-05-29.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/agent-defaults-opus-4-8-2026-05-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_config_alignment.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/agent-defaults-opus-4-8-2026-05-29.md`
  - `reports/l4_wave_indicators/agent-defaults-opus-4-8-2026-05-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
