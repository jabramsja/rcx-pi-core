# bot-remediation adapter timeout auto-defers all-deferrable findings (reuses the existing P0/P1 + critical-path guards) instead of unconditionally stranding

Date: 2026-06-29
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: bot-remediation-timeout-autodefers-2026-06-29
Phase-A-Lock: LOCKED
Purpose: Fix the bot-remediation timeout strand (2026-06-20 learning: bot_remediation=claude is slow → the 600s adapter timeout strands a wave whose bot findings are all non-blocking). ROOT (verified on dev, commit_executor.py `_attempt_bot_finding_remediation`): the `except _bridge_adapters.BridgeAdapterError` block (~line 8924, which catches the remediation-adapter TIMEOUT/error) returns `status='bot_findings_pending'` UNCONDITIONALLY — it does NOT classify the findings. The ADJACENT no-change path (~line 8939) DOES classify: it routes to recovery (bot_findings_pending) only if there are P0/P1 findings OR critical-path findings (`_CRITICAL_PATH_PREFIXES`), and otherwise AUTO-DEFERS the non-blocking (P2+) findings via `_auto_defer_bot_findings` (+ stage/amend/re-mint-receipt). So an adapter TIMEOUT on a wave whose findings are all P2+/non-critical strands, even though the SAME findings via the no-change path would auto-defer + commit. FIX: factor the no-change path's classification+auto-defer logic (the P0/P1 check + the critical-path check + the `_auto_defer_bot_findings` call + the stage/amend/re-mint-receipt block, ~lines 8940-9044) into a SHARED helper, and call it from BOTH the no-change path AND the `except BridgeAdapterError` (timeout/error) path. So on a remediation timeout: if there are NO P0/P1 findings AND no critical-path findings, AUTO-DEFER (commit proceeds); P0/P1 OR critical-path findings STILL route to recovery (bot_findings_pending) exactly as today. REUSE the EXISTING P0/P1 + `_CRITICAL_PATH_PREFIXES` guards verbatim — do NOT introduce a new classification, do NOT use the bridge severity rule (the bot uses P-levels). This is strictly safer (a strand becomes a guarded auto-defer; the blocking guards are unchanged). Add regressions in the EXISTING mu/tests/tools/test_commit_executor*.py: (1) remediation adapter raises BridgeAdapterError (timeout) with only P2 findings -> auto-defers (status NOT bot_findings_pending); (2) timeout with a P0/P1 finding -> bot_findings_pending; (3) timeout with a critical-path finding (e.g. mu/tools/executors/) -> bot_findings_pending. No host semantics. Do NOT add a new test file.

## Scope

Fix the bot-remediation timeout strand (2026-06-20 learning: bot_remediation=claude is slow → the 600s adapter timeout strands a wave whose bot findings are all non-blocking). ROOT (verified on dev, commit_executor.py `_attempt_bot_finding_remediation`): the `except _bridge_adapters.BridgeAdapterError` block (~line 8924, which catches the remediation-adapter TIMEOUT/error) returns `status='bot_findings_pending'` UNCONDITIONALLY — it does NOT classify the findings. The ADJACENT no-change path (~line 8939) DOES classify: it routes to recovery (bot_findings_pending) only if there are P0/P1 findings OR critical-path findings (`_CRITICAL_PATH_PREFIXES`), and otherwise AUTO-DEFERS the non-blocking (P2+) findings via `_auto_defer_bot_findings` (+ stage/amend/re-mint-receipt). So an adapter TIMEOUT on a wave whose findings are all P2+/non-critical strands, even though the SAME findings via the no-change path would auto-defer + commit. FIX: factor the no-change path's classification+auto-defer logic (the P0/P1 check + the critical-path check + the `_auto_defer_bot_findings` call + the stage/amend/re-mint-receipt block, ~lines 8940-9044) into a SHARED helper, and call it from BOTH the no-change path AND the `except BridgeAdapterError` (timeout/error) path. So on a remediation timeout: if there are NO P0/P1 findings AND no critical-path findings, AUTO-DEFER (commit proceeds); P0/P1 OR critical-path findings STILL route to recovery (bot_findings_pending) exactly as today. REUSE the EXISTING P0/P1 + `_CRITICAL_PATH_PREFIXES` guards verbatim — do NOT introduce a new classification, do NOT use the bridge severity rule (the bot uses P-levels). This is strictly safer (a strand becomes a guarded auto-defer; the blocking guards are unchanged). Add regressions in the EXISTING mu/tests/tools/test_commit_executor*.py: (1) remediation adapter raises BridgeAdapterError (timeout) with only P2 findings -> auto-defers (status NOT bot_findings_pending); (2) timeout with a P0/P1 finding -> bot_findings_pending; (3) timeout with a critical-path finding (e.g. mu/tools/executors/) -> bot_findings_pending. No host semantics. Do NOT add a new test file.

Files and surfaces in scope:

- `mu/tools/executors/commit_executor.py` -- PRIMARY surface. `_attempt_bot_finding_remediation` (def ~line 8816). Two adjacent regions: (a) the `except _bridge_adapters.BridgeAdapterError` block (~lines 8924-8932) that catches the remediation-adapter TIMEOUT/error and currently returns `status='bot_findings_pending'` UNCONDITIONALLY (no classification); (b) the no-change path (~lines 8939-9024) that DOES classify -- P0/P1 blocking-findings check (`"P0"/"P1"` in `body`/`severity`, ~8942-8961), critical-path check (`_CRITICAL_PATH_PREFIXES` path-prefix match, defined function-locally at ~8965, ~8965-8985), then `_auto_defer_bot_findings(...)` + stage/amend/re-mint-receipt + `return None` success (~8986-9024). The classify+auto-defer logic in (b) is extracted into a shared helper that (a) also calls; the normal-remediation branch (adapter PRODUCED changes, ~line 9026+) is untouched.
- `mu/tests/tools/test_commit_executor_receipt.py` -- EXISTING regression test file (already houses the bot-remediation + auto-defer coverage, e.g. `test_auto_defer_amend_mints_fresh_receipt_for_staged_report`, `test_bot_remediation_commit_carries_active_lane_bus_env`). The three regressions are added here; the named evidence-target test `test_bot_remediation_timeout_autodefers_deferrable` lives here (first file in the evidence_command grep). NO new test file is created.
- TASKS.md -- tracker-sync authority. The 2026-06-29 tracker sync note for wave `bot-remediation-timeout-autodefers-2026-06-29` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/bot-remediation-timeout-autodefers-2026-06-29_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Factor the no-change path's classification + auto-defer logic (`_attempt_bot_finding_remediation`, ~lines 8939-9024) into a SHARED helper. That logic is, in order: the P0/P1 blocking-findings check (`"P0"/"P1"` in `f.get("body","")` or `f.get("severity","")`, ~8942-8961), the critical-path check (`_CRITICAL_PATH_PREFIXES` path-prefix match, ~8965-8985), and the `_auto_defer_bot_findings(...)` call + stage/amend/re-mint-receipt block + `return None` success (~8986-9024). The helper returns exactly what the no-change path returns today: a `bot_findings_pending` response dict when P0/P1 OR critical-path findings exist; `None` (auto-deferred, commit proceeds) otherwise. The function-local `_CRITICAL_PATH_PREFIXES` tuple (currently defined inside the no-change branch at ~8965) moves into the shared helper (or module scope) so both call sites resolve to ONE definition. Reuse the existing guards VERBATIM -- no new classification, no bridge severity rule.
2. Call the shared helper from BOTH sites: (a) replace the inlined block in the no-change path with the helper (behavior-preserving), and (b) call it from the `except _bridge_adapters.BridgeAdapterError` block (~8924-8932) that currently returns `bot_findings_pending` unconditionally. On a remediation TIMEOUT/adapter error: NO P0/P1 AND no critical-path findings -> auto-defer (helper returns `None`, commit proceeds); P0/P1 OR critical-path findings -> `bot_findings_pending` (route to recovery), exactly as the no-change path already does and exactly as the timeout path already does for those classes.
3. Add three regressions to the EXISTING `mu/tests/tools/test_commit_executor_receipt.py` (NO new test file), each driving `_attempt_bot_finding_remediation` so the remediation adapter raises `BridgeAdapterError` (timeout):
   - (a) `test_bot_remediation_timeout_autodefers_deferrable` (the named evidence-target test the evidence_command greps for): timeout with only P2/non-critical findings -> auto-defers (returns success / status is NOT `bot_findings_pending`).
   - (b) timeout with a P0/P1 finding -> `bot_findings_pending`.
   - (c) timeout with a critical-path finding (path under one of `_CRITICAL_PATH_PREFIXES`, e.g. `mu/tools/executors/`) -> `bot_findings_pending`.
4. Confirm the change is pure control-plane: no host semantics, no edits under runtime dirs, no new file. Re-run the FULL `mu/tests/tools/test_commit_executor_receipt.py` (not just the three new cases) because the extracted block is the same code the existing no-change auto-defer tests exercise (e.g. `test_auto_defer_amend_mints_fresh_receipt_for_staged_report`); the shared-helper refactor must leave those green (blast radius).

## Constraints

- REUSE the existing P0/P1 + `_CRITICAL_PATH_PREFIXES` guards VERBATIM. Do NOT introduce a new or second classification rule. The bot uses P-levels -- do NOT use the bridge severity rule here.
- The shared helper is an EXTRACTION, not a behavior change for the no-change path: its disposition for every finding set must be identical after the refactor (P0/P1 -> pending, critical-path -> pending, otherwise auto-defer + commit). Only the `except BridgeAdapterError` (timeout/error) path's behavior changes -- it gains the same classification it currently lacks.
- Do NOT change the normal-remediation branch (adapter PRODUCED changes, ~line 9026+), the recovery agent path, or the stage/amend/re-mint-receipt mechanics. Out of scope: any unrelated remediation/dispatcher refactor.
- Do NOT create a new test file. The three regressions go in the EXISTING `mu/tests/tools/test_commit_executor_receipt.py`.
- No host semantics and no runtime-dir edits. Class is L4_ENABLER: scope is limited to `mu/tools/executors/commit_executor.py` control-plane code plus its tests; `mu/host/`, `rcx_pi/selfhost/`, seeds, and projection surfaces are OUT of scope.

## Stop conditions

- STOP and escalate if the timeout/error path cannot reuse the no-change classifier without duplicating it. Re-scope; do NOT clone the P0/P1 + critical-path + auto-defer logic into a second definition -- a divergent classifier is exactly the kind of finding the bridge rejects.
- STOP and escalate if the shared helper would require touching a runtime dir or adding host semantics -- that would violate the L4_ENABLER class for this wave.
- STOP and treat as a TRUE blocker (not a fixture update) if extracting the shared helper changes the no-change path's disposition for any finding set -- e.g. a P0/P1 or critical-path finding newly auto-defers, or an all-P2/non-critical set newly strands. The extraction must be behavior-preserving for the no-change path.
- STOP if the full `mu/tests/tools/test_commit_executor_receipt.py` run regresses outside the three new cases in a way that signals a real behavior change to the no-change auto-defer / stage / amend / re-mint-receipt path (blast radius), rather than an expected update.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`

## Acceptance criteria

- evidence_command passes (currently FAILS -- the named test is absent): `grep -q 'def test_bot_remediation_timeout_autodefers_deferrable' mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py 2>/dev/null || grep -rq 'def test_bot_remediation_timeout_autodefers_deferrable' mu/tests/tools/`.
- The `except _bridge_adapters.BridgeAdapterError` (timeout/error) path and the no-change path produce the SAME disposition for the same findings: NO P0/P1 AND no critical-path -> auto-defer + commit (status NOT `bot_findings_pending`); P0/P1 OR critical-path -> `bot_findings_pending` (recovery). A remediation timeout on all-deferrable (P2+/non-critical) findings no longer strands the wave.
- All three regressions exist in `mu/tests/tools/test_commit_executor_receipt.py` and pass: (a) `test_bot_remediation_timeout_autodefers_deferrable` -- P2-only timeout auto-defers (status NOT `bot_findings_pending`); (b) P0/P1 timeout -> `bot_findings_pending`; (c) critical-path timeout (e.g. `mu/tools/executors/`) -> `bot_findings_pending`.
- Full-file green (blast radius): `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py` is green (the whole file, to cover the no-change auto-defer / stage / amend / re-mint-receipt path the shared helper now also serves).
- `python3 -m py_compile mu/tools/executors/commit_executor.py` is clean; `git diff --check` is clean.
- Exactly ONE classification + auto-defer definition exists (no divergent/duplicate); both the no-change path and the timeout/error path resolve to the shared helper.
- No host semantics, no runtime-dir edits, no new test file (L4_ENABLER constraints upheld).

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `bot-remediation-timeout-autodefers-2026-06-29`.
- Governing packet: this file, `reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md`.
- TASKS.md authority: the 2026-06-29 tracker sync note for wave `bot-remediation-timeout-autodefers-2026-06-29` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:bot-remediation-timeout-autodefers-2026-06-29

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `bot-remediation-timeout-autodefers-2026-06-29`
- Active packet: `reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md`
- Indicator artifact: `reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md`
  - `reports/deferred/non_blocking/bot-remediation-timeout-autodefers-2026-06-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `bot-remediation-timeout-autodefers-2026-06-29`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/bot-remediation-timeout-autodefers-2026-06-29_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id bot-remediation-timeout-autodefers-2026-06-29 --output reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md`, `reports/deferred/non_blocking/bot-remediation-timeout-autodefers-2026-06-29_bridge_nonblockers.md`, `reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: bot-remediation-timeout-autodefers-2026-06-29.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `bot-remediation-timeout-autodefers-2026-06-29`
- Active packet: `reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `01f3a6cd5ca8ffc55221894d3a9eb046b0485c3b4ea3bf19e66f0f00f5c7cfa6`
- Indicator artifact: `reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md`, `reports/deferred/non_blocking/bot-remediation-timeout-autodefers-2026-06-29_bridge_nonblockers.md`, `reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/bot-remediation-timeout-autodefers-2026-06-29_2026-06-29.md`
  - `reports/deferred/non_blocking/bot-remediation-timeout-autodefers-2026-06-29_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/bot-remediation-timeout-autodefers-2026-06-29.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
