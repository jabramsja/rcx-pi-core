# Recovery Out-of-Wave TASKS Note Auto-Fix

Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: recovery-out-of-wave-tasks-note-auto-fix-2026-05-26
Class: L4_ENABLER
Category: pipeline/control-plane recovery hardening
Target gate: G8
Phase-A-Lock: LOCKED
Founder override: FOUNDER_OVERRIDE:recovery-out-of-wave-tasks-note-auto-fix-2026-05-26

## Purpose

Mechanize the commit-recovery failure observed during
`l4-ci-runtime-test-evidence-cache-2026-05-26`: commit supervisor identified an
out-of-wave staged `TASKS.md` tracker note, Tier 3 recovery diagnosed the same
small repair three times, but recovery did not apply it. The next occurrence
must be handled by deterministic recovery-gate logic instead of manual editing
or LLM shell advice.

During this same wave, dispatcher recovery wrote a Tier 2 timeout override into
tracked `mu/tools/executors/executor_config.json`, and pre-commit supervisor
rejected that staged timeout drift as outside this packet's scope. This packet
therefore also authorizes the bounded pipeline self-repair required by founder
protocol: recovery overrides must be mechanically propagated to retrying child
executors without mutating tracked executor config defaults.

## Diagnostic Evidence

- `.agent_bus/recovery/recovery_status.json` for
  `l4-ci-runtime-test-evidence-cache-2026-05-26` ended with
  `failure_class: "needs_phase_b"`, `tier: 3`, `state: "tier3_exhausted"`,
  `current_iteration: 3`, and `recovered: false`.
- `.agent_bus/recovery/recovery_log.json` recorded the final three attempts for
  invocation
  `l4-ci-runtime-test-evidence-cache-2026-0-build-and-run-superv-needs-phase-b-0afac6c6`.
  The attempt details all identify an unrelated out-of-wave `TASKS.md` tracker
  note for `n3-js-evidence-walker-runtime-authority-parity-2026-05-22`.
- `mu/tools/executors/recovery_gate.py:317-328` currently classifies commit
  supervisor `NEEDS_PHASE_B` as generic `FailureClass.NEEDS_PHASE_B`.
- `mu/tools/executors/recovery_gate.py:157` maps generic `NEEDS_PHASE_B` to
  Tier 3, and `mu/tools/executors/recovery_gate.py:3350-3364` has no
  deterministic Tier 2 repair for the out-of-wave tracker-note case.
- `mu/tools/executors/recovery_gate.py:6511-6554` shows Tier 3 shell recovery
  can execute bounded shell commands, but this incident proved that repeated
  textual diagnosis alone did not produce the required edit.
- Pre-commit supervisor rejected the intermediate staged
  `mu/tools/executors/executor_config.json` change because this packet
  authorized recovery-gate/TASKS repairs, not tracked timeout-default drift.
- `mu/tools/executors/executor_dispatch.py` previously applied
  `RCX_RECOVERY_TIMEOUT_OVERRIDE` to in-memory config and wrote non-commit
  overrides to tracked `executor_config.json` for subprocesses that reload
  config; that write path created the out-of-wave staged file.
- `mu/tools/executors/executor_common.py` is the shared config loader used by
  Phase B and related child executors, so it is the correct place to
  materialize inherited recovery override env vars without editing disk.

## Scope

Implementation files in scope:

- `mu/tools/executors/executor_common.py`
- `mu/tools/executors/executor_dispatch.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tests/tools/test_executor_dispatch.py`
- `mu/tests/tools/test_recovery_gate.py`

Same-wave governance and generated artifacts in scope during Phase B and commit
packaging:

- `TASKS.md`
- `reports/control_plane/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_2026-05-26.md`
- `reports/l4_wave_indicators/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26.json`
- `reports/deferred/non_blocking/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_bridge_nonblockers.md`, only if Phase B or commit automation generates same-wave non-blocking findings.

## Work Items

1. Add a specific recovery classification for commit-supervisor
   `NEEDS_PHASE_B` payloads whose reproduced evidence names an out-of-wave
   staged `TASKS.md` tracker note.
2. Route that class to a deterministic Tier 2 repair, not generic Tier 3.
3. Implement the repair by parsing `git diff --cached --unified=0 -- TASKS.md`
   and removing only added `TASKS.md` tracker-note or tracker-follow-up lines
   whose wave token is proven different from the active recovery wave.
4. Fail closed if `TASKS.md` has unstaged changes, the active wave id cannot be
   resolved, the staged diff cannot prove candidate line numbers, or any
   candidate line lacks an explicit out-of-wave token.
5. Preserve same-wave tracker notes, non-tracker edits, and unrelated files.
6. Restage only `TASKS.md` after a successful deterministic repair.
7. Add tests covering classification, successful removal/restage, same-wave
   preservation, and fail-closed behavior for unstaged `TASKS.md` changes.
8. Mechanize the same-wave dispatcher recovery failure by keeping tracked
   `executor_config.json` read-only during Tier 2 timeout recovery.
9. Materialize recovery timeout, bridge-turn-timeout, and stale-implementer
   overrides through the shared config loader so child executors that reload
   config receive the retry parameters through inherited env.
10. Preserve the no-leak invariant by clearing one-shot recovery override env
    vars at dispatcher retry-scope exit.

## Constraints

- Do not edit production runtime, substrate, seed, scheduler, registry,
  projection, JS parity, or Mu semantic files in this wave.
- Do not use `run_review.py`.
- Do not use destructive git commands such as reset, checkout, restore, clean,
  or stash inside the repair.
- Do not remove a line unless the staged diff proves it is an added
  `TASKS.md` tracker-note or tracker-follow-up line and the line carries an
  explicit wave token different from the active recovery wave.
- Do not remove same-wave tracker notes.
- Do not modify branch protection, workflow files, green-gate selectors, or test
  markers.
- Do not stage or persist `mu/tools/executors/executor_config.json` timeout
  default changes as part of recovery.
- Do not hand-author commit handoff or receipt JSON. Route through dispatcher,
  Phase B, adversarial review, pre-commit supervisor, and commit executor.

## Acceptance Criteria

Focused validation must pass:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py::TestOutOfWaveTasksTrackerNoteRecovery --tb=short
```

Broader control-surface validation must pass:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py --tb=short
```

Dispatcher recovery override validation must pass:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k 'recovery_override or apply_overrides or chained_phase_b_live_timeout_attribution_and_cap or tier2_recovery_retries_with_adjustment' --tb=short
```

Contract validation must pass after Phase B stages the same-wave package:

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id recovery-out-of-wave-tasks-note-auto-fix-2026-05-26 --wave-class L4_ENABLER
```

Commit packaging must go through the normal dispatcher path and produce a
pre-commit supervisor `COMMIT_GO` receipt before commit.

## Proof Limits

This wave mechanizes one precise recovery case: out-of-wave staged `TASKS.md`
tracker-note lines that commit supervisor reports as a package-scope blocker. It
does not claim to solve all `NEEDS_PHASE_B` cases, all tracker-note drift, or
all commit-supervisor package mismatches.

## Grounding / Authorization

- Founder instruction in this session explicitly required automatic,
  non-interactive waves through dispatcher/Phase B/pre-commit executor and
  explicitly prohibited `run_review.py`.
- Founder instruction in this session explicitly allowed bounded structural
  manual recovery only when the failure is then structurally automated so it
  does not recur.
- The merged #1023 wave required bounded manual removal of out-of-wave
  `TASKS.md` tracker-note additions after Tier 3 recovery exhausted; this packet
  is the required mechanization of that failure mode.
- The current same-wave dispatcher retry failure required bounded manual
  intervention only to stop the bad loop and remove the out-of-scope staged
  timeout default; this packet is expanded to mechanize that pipeline failure
  before resuming Phase B.

Human-facing output footer: `Questions? Concerns? Thoughts? -- Think hard`

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `recovery-out-of-wave-tasks-note-auto-fix-2026-05-26`
- Active packet: `reports/control_plane/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_2026-05-26.md`
- Indicator artifact: `reports/l4_wave_indicators/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_2026-05-26.md`
  - `reports/deferred/non_blocking/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `recovery-out-of-wave-tasks-note-auto-fix-2026-05-26`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `recovery-out-of-wave-tasks-note-auto-fix-2026-05-26`
- Active packet: `reports/control_plane/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_2026-05-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5b3e11a57a02fc7fab4907df37d12454180dc6edfa097dd6f467f00fc23359dc`
- Indicator artifact: `reports/l4_wave_indicators/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_2026-05-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_2026-05-26.md`
  - `reports/deferred/non_blocking/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/recovery-out-of-wave-tasks-note-auto-fix-2026-05-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
