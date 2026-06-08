# Growth Cap Autobump Founder Override 2026-06-08

Date: 2026-06-08
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: growth-cap-autobump-founder-override-2026-06-08
Class: L4_ENABLER
target_gate_id: G8
Phase-A-Lock: LOCKED
Purpose: Eliminate the recurring growth-cap strand where a wave that adds a new test file fails the Step-8 pre-commit growth-cap gate (mu/tests/docs/test_growth_caps.py CAP_TEST_FILES) and strands the commit, forcing a manual cap-bump recovery (just reproduced on #53/PR #1088 and earlier waves). Automate that founder-authorized recovery inside commit_executor's staging/pre-commit path: for a wave that adds a NEW test file AND carries a FOUNDER_OVERRIDE token, auto-bump CAP_TEST_FILES by exactly the cap SHORTFALL the gate would report (the minimal increment that makes the gate pass -- never the raw new-file count), record wave-id + FOUNDER_OVERRIDE provenance, and stage test_growth_caps.py so the gate passes. The bump is idempotent: on a same-wave commit retry the new file is still absent on the merge base and the trigger re-fires, but the path detects the existing same-wave provenance entry (and independently reads a zero shortfall once the cap already covers the count) and leaves CAP_TEST_FILES unchanged; a wave that adds a file while consolidating/deleting another, or that has existing cap headroom, reports zero shortfall and is NOT bumped. A wave with NO FOUNDER_OVERRIDE still fails closed exactly as today. Tooling-only; the ratchet is NOT weakened.

## Scope

L4_ENABLER, tooling-only. Files in scope:

- `mu/tools/executors/commit_executor.py` -- the staging/pre-commit path that runs BEFORE the Step-8 growth-cap gate. Add: (1) new-test-file detection (staged `mu/tests/**/test_*.py` absent on the merge base), (2) cap-shortfall computation that mirrors the gate (projected `test_*.py` count under `mu/tests` minus `BASELINE_TEST_FILES + CAP_TEST_FILES`), (3) a FOUNDER_OVERRIDE-gated, idempotent auto-bump of `CAP_TEST_FILES` in `mu/tests/docs/test_growth_caps.py` by exactly the shortfall -- guarded by a same-wave provenance check so a commit retry does not re-bump -- with a provenance comment and `git add` of test_growth_caps.py, (4) no-op (fail-closed) when no FOUNDER_OVERRIDE, and (5) a clear log line on auto-bump (and on the idempotent / zero-shortfall no-op).
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` -- the wave's regression test, added to this EXISTING test file (the wave's `evidence_command` targets `-k growth_cap` here). It MUST NOT be a new test file: a new file would trip the very CAP_TEST_FILES gate this wave fixes before the fix is active (bootstrap trap).

`mu/tests/docs/test_growth_caps.py` is READ by the auto-bump path to compute the shortfall (`BASELINE_TEST_FILES`, `CAP_TEST_FILES`, and the projected test-file count) and is WRITTEN only as the `CAP_TEST_FILES` integer bump + an appended provenance comment; its assertion logic and `BASELINE_TEST_FILES` are NOT modified by this wave.

- `reports/deferred/non_blocking/growth-cap-autobump-founder-override-2026-06-08_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. **Detect new test files.** In commit_executor's staging/pre-commit path (before the Step-8 gate), compute the set of staged/committed `mu/tests/**/test_*.py` paths that are ABSENT on the merge base (`origin/<base>`). This identifies which file(s) the wave adds (used to name them in the provenance comment) and is a PRECONDITION for the auto-bump -- it is NOT the bump magnitude.
2. **Compute the cap shortfall (not the new-file count).** Mirror the gate exactly: count the `test_*.py` files under `mu/tests` that the gate will see after staging (same `rglob("test_*.py")` measure as `_count_test_files()`), read `BASELINE_TEST_FILES` and `CAP_TEST_FILES` from test_growth_caps.py, and compute `shortfall = projected_count - (BASELINE_TEST_FILES + CAP_TEST_FILES)`. The bump amount is exactly `shortfall` when `shortfall > 0`, else zero. A wave that adds a new file while deleting/consolidating another, or that already has cap headroom, yields `shortfall <= 0` and is NOT bumped (it does not need a cap increase, so raising the cap by the raw new-file count would weaken the ratchet).
3. **Idempotency guard (same-wave provenance).** Before bumping, check whether the `CAP_TEST_FILES` provenance comment already records THIS wave (its `<wave-id>` / `FOUNDER_OVERRIDE:<wave-id>` token). If it does, the bump for this wave was already applied -> do NOTHING (no integer change, no duplicate comment). This makes a same-wave commit retry -- where the new test file is still absent on the merge base and the trigger re-fires -- leave CAP_TEST_FILES unchanged. The shortfall arithmetic in item 2 is independently idempotent (once the cap covers the count, a retry reports `shortfall <= 0`), so the two mechanisms agree: repeat execution leaves CAP_TEST_FILES unchanged.
4. **FOUNDER_OVERRIDE-gated auto-bump.** ONLY when the wave's handoff carries a FOUNDER_OVERRIDE token (the same token Gate 8 already validates) AND items 1-3 hold (>=1 genuinely-new staged test file, `shortfall > 0`, no existing same-wave provenance): bump `CAP_TEST_FILES` in `mu/tests/docs/test_growth_caps.py` by exactly the shortfall; append a provenance comment of the form `+<shortfall> for <new test file(s)> (<wave-id> wave, FOUNDER_OVERRIDE:<wave-id>)`; `git add` test_growth_caps.py to the staged set so the Step-8 growth-cap gate passes.
5. **Fail-closed when no override.** When the wave has NO FOUNDER_OVERRIDE, do NOTHING -- let the growth-cap gate strand the commit exactly as today. The auto-bump is strictly an automation of a founder-authorized action, never a silent ratchet relaxation.
6. **Log the auto-bump.** Emit a clear log line on bump, e.g. `[commit-executor] auto-bumped CAP_TEST_FILES +<shortfall> for FOUNDER_OVERRIDE wave <wave-id>`, and a distinct line on the idempotent / zero-shortfall no-op so a retry is observable.
7. **Regression test (existing file).** In `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, pin cases (a)-(e) (see Acceptance criteria), including the idempotency and zero-shortfall cases. Discoverable by `-k growth_cap` to match the wave `evidence_command`.

## Constraints

What is NOT in scope:

- Do NOT change the growth-cap test's assertion logic or `BASELINE_TEST_FILES`. The only programmatic edit to test_growth_caps.py is the exact `CAP_TEST_FILES` integer bump + provenance comment.
- Do NOT add a NEW test file for this wave. The regression test goes in the EXISTING `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (a new file would trip the very cap being fixed -- bootstrap trap).
- Do NOT touch runtime dirs: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers`. This is an L4_ENABLER; touching runtime dirs is forbidden for this class.
- No masking. The FOUNDER_OVERRIDE gate is mandatory: a non-override wave that adds a new test file MUST still fail closed.
- Keep the bump MINIMAL and exact: the cap SHORTFALL the gate would report (`projected_count - (BASELINE_TEST_FILES + CAP_TEST_FILES)`), never the raw new-file count and never a blanket increase. Do NOT bump when the shortfall is zero (headroom/consolidation) or when this wave's provenance is already recorded (retry).

## Stop conditions

- Stop when the regression test pins cases (a)-(e) -- including idempotency (repeat execution leaves CAP_TEST_FILES unchanged) and zero-shortfall (no bump) -- AND the wave `evidence_command` is green: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py -k growth_cap`.
- Stop and fail closed (do NOT proceed) if the fix would require touching any runtime dir, changing the growth-cap assertion logic / `BASELINE_TEST_FILES`, or weakening the override gate.
- Stop and re-scope if implementing the regression case requires a new test file (the bootstrap trap) -- it must live in the existing test file.
- Phase A ends when the bridge converges on this locked packet; implementation is Phase B.

## Acceptance criteria

- commit_executor detects new test files as staged `mu/tests/**/test_*.py` absent on the merge base, and computes the bump as the cap shortfall (`projected_count - (BASELINE_TEST_FILES + CAP_TEST_FILES)`), not the raw new-file count.
- (a) FOUNDER_OVERRIDE wave + new test file that pushes the count over the cap (`shortfall > 0`), no prior same-wave provenance -> `CAP_TEST_FILES` auto-bumped by EXACTLY the shortfall, provenance comment naming the wave-id recorded, `test_growth_caps.py` staged, and the Step-8 growth-cap gate passes.
- (b) NO FOUNDER_OVERRIDE + new test file (`shortfall > 0`) -> no bump; the commit still strands (fail-closed).
- (c) No new test files -> no bump.
- (d) Idempotency: FOUNDER_OVERRIDE wave + new test file, auto-bump run TWICE -> `CAP_TEST_FILES` is bumped once; the second run detects the existing same-wave provenance and leaves CAP_TEST_FILES unchanged, with no duplicate provenance comment.
- (e) Headroom/consolidation: FOUNDER_OVERRIDE wave + new test file but projected count `<=` cap limit (existing headroom, or a sibling test file deleted/consolidated in the same wave) -> `shortfall <= 0` -> no bump.
- The auto-bump is logged with the wave-id; the idempotent / zero-shortfall no-op is also logged.
- The regression test lives in `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (existing file) and every case (a)-(e) is selected by `-k growth_cap`.
- `evidence_command` green: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py -k growth_cap`.
- No runtime dirs touched; growth-cap assertion logic and `BASELINE_TEST_FILES` unchanged; `audit_fast` green.

## Grounding / Authorization

Machine-readable grounding (line-anchored so commit automation can derive the same-wave override mechanically; these tokens mirror the governing TASKS.md tracker note):

FOUNDER_OVERRIDE:growth-cap-autobump-founder-override-2026-06-08
Authorization: standing pipeline-bug-fix authorization per memory feedback_autonomous_executor_fix.md -- this control-surface L4_ENABLER automates a recurring pipeline-stranding bug recovery, so the founder's standing authorization for autonomous executor pipeline bug fixes applies; the wave-bound FOUNDER_OVERRIDE token above is the literal same-wave override.
Packet: reports/control_plane/growth_cap_autobump_founder_override_2026-06-08.md
TASKS.md authorization: the [NEXT-CODEX-POST-REDTEAM] tracker sync note (2026-06-08, growth-cap-autobump-founder-override-2026-06-08) authorizes this wave; Class L4_ENABLER, target_gate_id G8, primary_blocker_class INTEGRATION, primary_invariant_id INV_TYPED_FAIL_CLOSED_OUTCOMES.
governing packet relationship: this file IS the governing Phase A packet and matches the Packet: reference in the TASKS.md note above; Phase B converges on this packet.

Provenance and indicators:

- The literal `FOUNDER_OVERRIDE:growth-cap-autobump-founder-override-2026-06-08` token here matches the same token in the governing TASKS.md tracker note, so Gate 8 / commit automation validate the same wave-bound override the auto-bump path itself gates on (no new override is introduced by this packet).
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py -k growth_cap`.
- `indicator_artifact_ref: reports/l4_wave_indicators/growth-cap-autobump-founder-override-2026-06-08.json`; `indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id growth-cap-autobump-founder-override-2026-06-08 --output reports/l4_wave_indicators/growth-cap-autobump-founder-override-2026-06-08.json`.
- `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`. `boot0_track_id: V1`. `boot0_progress_state: HOLD`.

## Request from Post-Merge Supervisor

GOAL: eliminate the recurring growth-cap strand where a wave that adds a new test file fails the Step-8 pre-commit-doc-check growth-cap gate (test_growth_caps.py CAP_TEST_FILES) and strands the commit, forcing a manual cap-bump recovery. CONTEXT (verified, just reproduced on #53/PR #1088 and earlier waves): mu/tests/docs/test_growth_caps.py asserts the repo's test-file count <= BASELINE_TEST_FILES + CAP_TEST_FILES; a wave that introduces a new mu/tests/**/test_*.py pushes the count over the cap, so commit_executor's Step-8 pre-commit gate fails and the commit strands. The current manual recovery (done repeatedly): edit test_growth_caps.py to bump CAP_TEST_FILES by the number of new test files, append a provenance comment citing the wave + FOUNDER_OVERRIDE, stage that file, and re-run the commit. REQUIRED FIX (automate the manual recovery, gated on the EXISTING founder sign-off; do NOT weaken the ratchet): in commit_executor, in the staging/pre-commit path that runs BEFORE the Step-8 growth-cap gate, (1) detect NEW test files in the staged set -- mu/tests/**/test_*.py that are present in the staged/committed set but ABSENT on the merge base (origin/<base>); (2) ONLY when the wave's handoff carries a FOUNDER_OVERRIDE token (the same token Gate 8 already validates), auto-bump CAP_TEST_FILES in mu/tests/docs/test_growth_caps.py by exactly the count of new test files, append a provenance comment of the form '+N for <new test file(s)> (<wave-id> wave, FOUNDER_OVERRIDE:<wave-id>)', and add test_growth_caps.py to the staged set so the Step-8 gate passes; (3) when the wave has NO FOUNDER_OVERRIDE, do NOTHING -- let the growth-cap gate strand the commit exactly as today (fail-closed; the auto-bump is strictly an automation of a founder-authorized action, never a silent ratchet relaxation). Keep the bump MINIMAL and exact (count of genuinely-new test files, not a blanket increase). Log the auto-bump clearly (e.g. '[commit-executor] auto-bumped CAP_TEST_FILES +N for FOUNDER_OVERRIDE wave <wave-id>'). SCOPE: mu/tools/executors/commit_executor.py (the staging/pre-commit path) + the wave's regression test, which MUST be added to an EXISTING test file under mu/tests/tools (e.g. an existing test_commit_executor_*.py), NOT a new test file (a new file would trip the very CAP_TEST_FILES gate this wave fixes, before the fix is active -- a bootstrap trap). Do NOT change the growth-cap test's assertion logic or BASELINE; do NOT touch runtime dirs (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). HARD CONSTRAINT: no masking; the FOUNDER_OVERRIDE gate is mandatory (a non-override wave must still fail closed). PROVE: a regression test (in an existing mu/tests/tools test file) that exercises commit_executor's new-test-file detection + FOUNDER_OVERRIDE-gated auto-bump: (a) FOUNDER_OVERRIDE wave + new test file -> cap auto-bumped by the exact count + provenance recorded + test_growth_caps.py staged; (b) NO FOUNDER_OVERRIDE + new test file -> no bump (still strands); (c) no new test files -> no bump. L4_ENABLER.

Routed next-candidate:
growth-cap-autobump-founder-override-2026-06-08

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `growth-cap-autobump-founder-override-2026-06-08`
- Active packet: `reports/control_plane/growth_cap_autobump_founder_override_2026-06-08.md`
- Indicator artifact: `reports/l4_wave_indicators/growth-cap-autobump-founder-override-2026-06-08.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/growth_cap_autobump_founder_override_2026-06-08.md`
  - `reports/deferred/non_blocking/growth-cap-autobump-founder-override-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/growth-cap-autobump-founder-override-2026-06-08.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `growth-cap-autobump-founder-override-2026-06-08`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/growth-cap-autobump-founder-override-2026-06-08_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `growth-cap-autobump-founder-override-2026-06-08`
- Active packet: `reports/control_plane/growth_cap_autobump_founder_override_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ee4cd4788f92ff0841b6fd25e15cfbf6a24850f97a3768a445be794d1ff62c28`
- Indicator artifact: `reports/l4_wave_indicators/growth-cap-autobump-founder-override-2026-06-08.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/growth_cap_autobump_founder_override_2026-06-08.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/growth-cap-autobump-founder-override-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/growth_cap_autobump_founder_override_2026-06-08.md`
  - `reports/deferred/non_blocking/growth-cap-autobump-founder-override-2026-06-08_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/growth-cap-autobump-founder-override-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
