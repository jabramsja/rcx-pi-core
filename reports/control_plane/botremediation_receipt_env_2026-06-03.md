# Botremediation Receipt Env 2026-06-03

Date: 2026-06-03
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: botremediation-receipt-env-2026-06-03
Phase-A-Lock: LOCKED
Purpose: Fix commit_executor's Step-15 bot-finding remediation so its commit on a NON-DEFAULT (lane) agent-bus does NOT fail the pre-commit receipt check with 'No pre-commit receipt found'. READ FIRST: in mu/tools/executors/commit_executor.py -- `_attempt_bot_finding_remediation` (the Step-15 remediation flow), `_mint_bot_remediation_receipt` (mints the type-B receipt), `_commit_subprocess_env` (builds the commit subprocess env that carries the active-bus authority RCX_AGENT_BUS_DIR from the `_active_bus_dir()` ContextVar, and returns None when no bus ContextVar is active), and how Step 9's normal commit passes `env=_commit_subprocess_env(...)` (step9_env) to its git commit; and in mu/tools/agents/meta_bridge_supervisor.py -- `verify_pre_commit_receipt` (resolves the receipt path via bus_dir and returns 'No pre-commit receipt found' when the receipt FILE is absent at that path), and in mu/tools/agents/verify_pre_commit_receipt.py how the hook reads bus_dir from the RCX_AGENT_BUS_DIR env. ROOT CAUSE (pinned via code 2026-06-03): `_mint_bot_remediation_receipt` writes the receipt to the ACTIVE bus meta dir (agent_bus_path(repo_root, _active_bus_dir(), 'meta')/pre_commit_receipt.json) -- for a lane wave that is .agent_bus-laneN/meta/pre_commit_receipt.json. But the Step-15 remediation `git commit -m <msg>` invocation AND the `git commit --amend --no-edit` invocation in `_attempt_bot_finding_remediation` call `_run([...])` WITHOUT env=, so the commit's pre-commit hook inherits os.environ -- which does NOT carry RCX_AGENT_BUS_DIR (the bus authority lives ONLY in the `_active_bus_dir()` ContextVar). The hook's verify_pre_commit_receipt then resolves the DEFAULT .agent_bus bus, where no receipt exists, and returns 'No pre-commit receipt found' -- failing the remediation commit even though the receipt was correctly minted to the lane bus. The FIRST commit (Step 9) does NOT hit this because it passes env=step9_env (=_commit_subprocess_env(...)), which injects RCX_AGENT_BUS_DIR from the ContextVar so the hook resolves the lane bus. PRECISE, BOUNDED FIX: in `_attempt_bot_finding_remediation`, pass `env=_commit_subprocess_env()` to the bot-remediation `git commit -m <msg>` invocation AND the `git commit --amend --no-edit` invocation, exactly mirroring how Step 9 passes step9_env -- so the remediation commit's pre-commit hook resolves the SAME (active/lane) bus that `_mint_bot_remediation_receipt` wrote the receipt to. Do NOT change `_mint_bot_remediation_receipt`, `_commit_subprocess_env`, `verify_pre_commit_receipt`, or any other commit/step. `_commit_subprocess_env()` returns None when no bus ContextVar is active (default-bus / non-lane runs), so env=None preserves today's behavior for the default bus -- NO regression. ADD A REGRESSION TEST to the EXISTING mu/tests/tools/test_commit_executor_receipt.py (do NOT create a new test file -- growth cap): assert that when a lane bus is the active `_active_bus_dir()`, the Step-15 bot-remediation git commit is invoked with an env that carries RCX_AGENT_BUS_DIR set to the lane bus (mock _run / _active_bus_dir / the bridge adapter as needed; assert the git-commit _run call's env equals the _commit_subprocess_env() result, i.e. carries RCX_AGENT_BUS_DIR); and that with NO active bus ContextVar the env passed is None (unchanged default-bus behavior, no regression).

## Scope

One bounded commit_executor robustness fix (L4_ENABLER, no runtime dir): in `_attempt_bot_finding_remediation`, pass `env=_commit_subprocess_env()` to the Step-15 bot-remediation `git commit -m <msg>` and `git commit --amend --no-edit` invocations (mirroring Step 9's step9_env), so the remediation commit's pre-commit hook resolves the SAME active/lane bus that `_mint_bot_remediation_receipt` wrote the receipt to -- fixing the 'No pre-commit receipt found' failure that strands a lane wave at Step 15 (the receipt is minted to .agent_bus-laneN/meta but the env-less commit's hook resolves the default .agent_bus). `_commit_subprocess_env()` returns None for the default/non-lane bus so there is NO regression. This unblocks the Step-15 bot-remediation path for ALL lane waves (incl. #24). Touch only `_attempt_bot_finding_remediation`; do not change the mint, the env helper, or verify_pre_commit_receipt. Regression test added to the EXISTING test_commit_executor_receipt.py (lane bus -> commit env carries RCX_AGENT_BUS_DIR; no bus -> env None). Validation gate: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`. Cite code by function name only; no file:line in the packet.

- `reports/deferred/non_blocking/botremediation-receipt-env-2026-06-03_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete, bounded tasks for the current phase (TASKS.md `[NEXT-CODEX-POST-REDTEAM]`, wave `botremediation-receipt-env-2026-06-03`):

1. In `_attempt_bot_finding_remediation` (`mu/tools/executors/commit_executor.py`): pass `env=_commit_subprocess_env()` to the Step-15 bot-remediation `git commit -m <msg>` `_run(...)` invocation, mirroring how Step 9 passes `env=step9_env` to its commit.
2. In the same function: pass `env=_commit_subprocess_env()` to the `git commit --amend --no-edit` `_run(...)` invocation.
3. Add a regression test to the EXISTING `mu/tests/tools/test_commit_executor_receipt.py` (no new file -- growth cap):
   - Lane-bus case: with a lane bus active as `_active_bus_dir()`, assert the Step-15 bot-remediation git-commit `_run` call is invoked with `env` equal to `_commit_subprocess_env()` (i.e. carrying `RCX_AGENT_BUS_DIR` set to the lane bus). Mock `_run` / `_active_bus_dir` / the bridge adapter as needed.
   - Default-bus case: with no active bus ContextVar, assert the env passed is `None` (unchanged default-bus behavior, no regression).

Mechanism (pinned in Purpose / Request, restated for the implementer): `_mint_bot_remediation_receipt` writes the receipt to the active bus meta dir (lane -> `.agent_bus-laneN/meta/pre_commit_receipt.json`); the env-less remediation commit's pre-commit hook inherits `os.environ` (no `RCX_AGENT_BUS_DIR`), so `verify_pre_commit_receipt` resolves the DEFAULT `.agent_bus` and reports 'No pre-commit receipt found'. Passing `env=_commit_subprocess_env()` makes the hook resolve the same active/lane bus the receipt was minted to.

## Constraints (NOT in scope)

- Do NOT modify `_mint_bot_remediation_receipt`, `_commit_subprocess_env`, `verify_pre_commit_receipt`, Step 9, or any other commit/step. Touch only `_attempt_bot_finding_remediation`.
- Do NOT create a new test file -- extend the existing `mu/tests/tools/test_commit_executor_receipt.py` (growth cap).
- Do NOT touch runtime/substrate dirs (`mu/host/...`, `rcx_pi/selfhost/...`). This is an `L4_ENABLER`: tooling-only, no runtime dir.
- Do NOT change default/non-lane bus behavior -- `_commit_subprocess_env()` returns `None` with no active bus ContextVar; env stays `None` (no regression).
- Do NOT widen the diff to other lane/bus call sites, other executors, or the hook.
- No `file:line` citations in this packet; cite code by function name only (doc-governance).

## Stop conditions

- Implementation stops once both `env=_commit_subprocess_env()` pass-throughs and the regression test are in place and the validation gate is green.
- HALT and re-open diagnosis (do NOT widen the patch) if the fix appears to require editing `_commit_subprocess_env`, `_mint_bot_remediation_receipt`, `verify_pre_commit_receipt`, or Step 9 -- that would mean the root cause is mis-pinned.
- HALT and escalate if the regression test cannot assert the commit env without a new test file or mocking beyond `_run` / `_active_bus_dir` / the bridge adapter.
- Phase A stops at the locked, bridge-converged plan; do NOT begin implementation until Phase A is locked. Do NOT commit/push/merge until the validation gate passes and the pre-commit supervisor receipt is minted to the active bus.

## Acceptance criteria

- `_attempt_bot_finding_remediation`'s Step-15 `git commit -m <msg>` and `git commit --amend --no-edit` `_run` calls both pass `env=_commit_subprocess_env()`.
- Lane bus: the remediation commit's pre-commit hook resolves the lane bus and finds the minted receipt -- the Step-15 'No pre-commit receipt found' strand (observed on PR #1069 / #24) no longer occurs.
- Default/non-lane bus: env resolves to `None`; behavior unchanged (no regression).
- Regression test in the EXISTING `test_commit_executor_receipt.py` asserts both cases (lane -> env carries `RCX_AGENT_BUS_DIR` == `_commit_subprocess_env()`; no bus -> env `None`).
- Validation gate green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Diff limited to `_attempt_bot_finding_remediation` plus the existing test file; no runtime dirs, no new files.

## Grounding / Authorization

- TASKS.md authorization: `[NEXT-CODEX-POST-REDTEAM]` -- tracker sync note (2026-06-03, `botremediation-receipt-env-2026-06-03`). Class: **L4_ENABLER**. target_gate_id: **G8**.
- FOUNDER_OVERRIDE:botremediation-receipt-env-2026-06-03 -- wave-bound override carried verbatim from the TASKS.md tracker sync note so commit automation derives the same-wave override mechanically.
- Authorization: standing pipeline-bug-fix authorization (per memory `feedback_autonomous_executor_fix.md` / `feedback_manual_then_structural_autonomy.md`) for this control-surface commit_executor robustness fix, combined with the wave-bound FOUNDER_OVERRIDE above for the non-structural adjacency / rolling-structural-quota clearance an `L4_ENABLER` requires.
- Governing packet: `reports/control_plane/botremediation_receipt_env_2026-06-03.md` (this file).
- L4_ENABLER contract bindings (from the TASKS.md tracker sync note for this wave):
  - evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`
  - evidence_delta: `_attempt_bot_finding_remediation` passes `env=_commit_subprocess_env()` to its Step-15 `git commit -m` and `git commit --amend` invocations so the remediation commit's pre-commit hook resolves the same active/lane bus that `_mint_bot_remediation_receipt` wrote the receipt to; the lane-wave 'No pre-commit receipt found' Step-15 strand is fixed; default/non-lane env stays `None`; regression test added to the existing `test_commit_executor_receipt.py`.
  - primary_blocker_class: INTEGRATION
  - primary_invariant_id: INV_TYPED_FAIL_CLOSED_OUTCOMES
  - indicator_artifact_ref: `reports/l4_wave_indicators/botremediation-receipt-env-2026-06-03.json`
  - indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id botremediation-receipt-env-2026-06-03 --output reports/l4_wave_indicators/botremediation-receipt-env-2026-06-03.json`
  - bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
  - boot0_track_id: V1
  - boot0_progress_state: HOLD

## Request from Post-Merge Supervisor

Fix commit_executor's Step-15 bot-finding remediation so its commit on a NON-DEFAULT (lane) agent-bus does NOT fail the pre-commit receipt check with 'No pre-commit receipt found'. READ FIRST: in mu/tools/executors/commit_executor.py -- `_attempt_bot_finding_remediation` (the Step-15 remediation flow), `_mint_bot_remediation_receipt` (mints the type-B receipt), `_commit_subprocess_env` (builds the commit subprocess env that carries the active-bus authority RCX_AGENT_BUS_DIR from the `_active_bus_dir()` ContextVar, and returns None when no bus ContextVar is active), and how Step 9's normal commit passes `env=_commit_subprocess_env(...)` (step9_env) to its git commit; and in mu/tools/agents/meta_bridge_supervisor.py -- `verify_pre_commit_receipt` (resolves the receipt path via bus_dir and returns 'No pre-commit receipt found' when the receipt FILE is absent at that path), and in mu/tools/agents/verify_pre_commit_receipt.py how the hook reads bus_dir from the RCX_AGENT_BUS_DIR env. ROOT CAUSE (pinned via code 2026-06-03): `_mint_bot_remediation_receipt` writes the receipt to the ACTIVE bus meta dir (agent_bus_path(repo_root, _active_bus_dir(), 'meta')/pre_commit_receipt.json) -- for a lane wave that is .agent_bus-laneN/meta/pre_commit_receipt.json. But the Step-15 remediation `git commit -m <msg>` invocation AND the `git commit --amend --no-edit` invocation in `_attempt_bot_finding_remediation` call `_run([...])` WITHOUT env=, so the commit's pre-commit hook inherits os.environ -- which does NOT carry RCX_AGENT_BUS_DIR (the bus authority lives ONLY in the `_active_bus_dir()` ContextVar). The hook's verify_pre_commit_receipt then resolves the DEFAULT .agent_bus bus, where no receipt exists, and returns 'No pre-commit receipt found' -- failing the remediation commit even though the receipt was correctly minted to the lane bus. The FIRST commit (Step 9) does NOT hit this because it passes env=step9_env (=_commit_subprocess_env(...)), which injects RCX_AGENT_BUS_DIR from the ContextVar so the hook resolves the lane bus. PRECISE, BOUNDED FIX: in `_attempt_bot_finding_remediation`, pass `env=_commit_subprocess_env()` to the bot-remediation `git commit -m <msg>` invocation AND the `git commit --amend --no-edit` invocation, exactly mirroring how Step 9 passes step9_env -- so the remediation commit's pre-commit hook resolves the SAME (active/lane) bus that `_mint_bot_remediation_receipt` wrote the receipt to. Do NOT change `_mint_bot_remediation_receipt`, `_commit_subprocess_env`, `verify_pre_commit_receipt`, or any other commit/step. `_commit_subprocess_env()` returns None when no bus ContextVar is active (default-bus / non-lane runs), so env=None preserves today's behavior for the default bus -- NO regression. ADD A REGRESSION TEST to the EXISTING mu/tests/tools/test_commit_executor_receipt.py (do NOT create a new test file -- growth cap): assert that when a lane bus is the active `_active_bus_dir()`, the Step-15 bot-remediation git commit is invoked with an env that carries RCX_AGENT_BUS_DIR set to the lane bus (mock _run / _active_bus_dir / the bridge adapter as needed; assert the git-commit _run call's env equals the _commit_subprocess_env() result, i.e. carries RCX_AGENT_BUS_DIR); and that with NO active bus ContextVar the env passed is None (unchanged default-bus behavior, no regression).

Routed next-candidate:
botremediation-receipt-env-2026-06-03

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `botremediation-receipt-env-2026-06-03`
- Active packet: `reports/control_plane/botremediation_receipt_env_2026-06-03.md`
- Indicator artifact: `reports/l4_wave_indicators/botremediation-receipt-env-2026-06-03.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/botremediation_receipt_env_2026-06-03.md`
  - `reports/deferred/non_blocking/botremediation-receipt-env-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/botremediation-receipt-env-2026-06-03.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `botremediation-receipt-env-2026-06-03`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/botremediation-receipt-env-2026-06-03_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `botremediation-receipt-env-2026-06-03`
- Active packet: `reports/control_plane/botremediation_receipt_env_2026-06-03.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `515a62c05695cc8e3f4e1f3a023f005cbca0c4116a59f6706c5bab6178aad7ca`
- Indicator artifact: `reports/l4_wave_indicators/botremediation-receipt-env-2026-06-03.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/botremediation_receipt_env_2026-06-03.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/botremediation-receipt-env-2026-06-03.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/botremediation_receipt_env_2026-06-03.md`
  - `reports/deferred/non_blocking/botremediation-receipt-env-2026-06-03_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/botremediation-receipt-env-2026-06-03.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
