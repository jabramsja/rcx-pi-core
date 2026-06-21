# NEXT-CODEX-POST-REDTEAM - propagate wave founder_override into the routing record so the growth-cap auto-bump and Gate 8 see it (deterministic recovery hardening)

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-routing-record-founder-override-propagation-2026-06-21
Phase-A-Lock: LOCKED
Purpose: STRUCTURAL recovery/pipeline hardening (founder-directed: always harden the pipeline when it breaks so the same manual fix is never needed again). VERIFIED ROOT CAUSE: a gate-authoring wave that adds a new governed test file and DECLARES a FOUNDER_OVERRIDE (in its WaveConfig and tracker note) still STRANDS at the commit-executor Step-5e growth-cap auto-bump. The auto-bump `_maybe_autobump_growth_cap_for_founder_override` fail-closes 'no_founder_override' because the commit flow derives an EMPTY founder_override_token: it reads the routing record (`_extract_founder_override_from_routing_record`) and TASKS.md, but `launch_wave.setup_routing_record` never passes `config.founder_override` to `build_and_write_routing_record`, so the routing record has no founder_override field, and the TASKS.md note is unreliable (the commit-retry state restore before Step-5e can revert the FOUNDER_OVERRIDE line written at Step 3). Net: the override the wave DECLARED never reaches the auto-bump, so every gate-authoring wave (Stage0, StructuralNumbers gate waves) strands and requires a manual cap bump. FIX (deterministic, single-source): thread `founder_override` through `build_post_merge_routing_record` + `build_and_write_routing_record` (executor_common) and pass `config.founder_override` from `launch_wave.setup_routing_record`, so the routing record durably carries the override from launch time. The commit flow already reads `record.founder_override` via `_extract_founder_override_from_routing_record`, so NO commit_executor change is needed. Result: a gate-authoring wave with a declared FOUNDER_OVERRIDE auto-bumps its growth cap and commits without a manual intervention, even across commit-retries.

## Scope

Thread founder_override through the routing-record builder so a wave's declared FOUNDER_OVERRIDE is durable in the routing record and reaches the commit-executor Step-5e growth-cap auto-bump. Tooling only (executor_common + launch_wave + an existing test file); no runtime dirs; no new test file. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/tools/executors/executor_common.py (MODIFY) -- add an optional `founder_override: pipeline-routing-record-founder-override-propagation-2026-06-21` parameter to `build_post_merge_routing_record` and `build_and_write_routing_record`; when non-empty, set a `founder_override` key in the routing-record dict it builds/writes. Default empty preserves current behavior.
- mu/tools/executors/launch_wave.py (MODIFY) -- in `setup_routing_record`, pass `founder_override=config.founder_override` to `build_and_write_routing_record` (config.founder_override already defaults to wave_id).
- mu/tests/tools/test_launch_wave.py (MODIFY -- existing file, do NOT create a new test file) -- add a regression asserting the written routing record carries the wave's founder_override and that `_extract_founder_override_from_routing_record` returns it.
- reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-21 tracker sync note for wave `pipeline-routing-record-founder-override-propagation-2026-06-21` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pipeline-routing-record-founder-override-propagation-2026-06-21_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read the current `build_post_merge_routing_record` + `build_and_write_routing_record` (executor_common) and `setup_routing_record` (launch_wave) and `_extract_founder_override_from_routing_record` (commit_executor) to confirm the routing-record dict shape and the field name the extractor reads (`founder_override` / `founder_override_token`).
2. Add the optional `founder_override` parameter to the routing-record builder(s) and write the matching field the extractor reads; keep the default empty so existing callers and records are unchanged.
3. Pass `config.founder_override` from `setup_routing_record` to the builder.
4. Add the regression to the EXISTING mu/tests/tools/test_launch_wave.py (no new test file): a launch writes a routing record carrying founder_override, and the commit-flow extractor returns it.
5. Run the evidence_command; confirm the launch_wave + dispatch test suites pass; emit the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- L4_ENABLER: do NOT touch runtime dirs (mu/host/**, rcx_pi/selfhost/**). Tooling + tests only.
- Do NOT create a new test file (it would itself trip the growth cap the fix addresses, before the fix lands); add the regression to the existing mu/tests/tools/test_launch_wave.py.
- Backward-compatible: the new parameter is optional and defaults to empty; routing records without founder_override and all existing callers keep working unchanged.
- Do NOT change commit_executor (the extractor already reads the routing-record field); keep the diff minimal and bounded to the named files.

## Stop conditions

- Stop done when the evidence_command passes (routing record carries founder_override + the extractor returns it) and the indicator is collected.
- Halt as POLICY_BOUND if the extractor reads a field name that cannot be written without a broader change; surface the exact field-name mismatch rather than widening scope.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_launch_wave.py`

## Acceptance criteria

- The routing record written by the launcher carries the wave's founder_override; `_extract_founder_override_from_routing_record` returns it.
- A declared FOUNDER_OVERRIDE now reaches the Step-5e growth-cap auto-bump (token non-empty) -- proven by the regression.
- Optional parameter, default empty; existing routing-record callers/tests unchanged; no runtime dirs touched; no new test file.
- evidence_command clean; indicator emitted.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-routing-record-founder-override-propagation-2026-06-21`.
- Governing packet: this file, `reports/control_plane/pipeline-routing-record-founder-override-propagation-2026-06-21_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `pipeline-routing-record-founder-override-propagation-2026-06-21` is canonical for this packet's L4 fields.
- Authorization: Founder-directed 2026-06-21 (verbatim: 'if pipeline breaks, you can do manual fix, but must always find the structural fix for either pipeline, recovery, builders ... so you do not have the same problem again, and waste time and tokens'). This is the LANDED structural fix for the growth-cap auto-bump strand that recurs on every gate-authoring wave (filing != fixing). Auto-authorized structural pipeline fix (feedback_manual_then_structural_autonomy).

FOUNDER_OVERRIDE:pipeline-routing-record-founder-override-propagation-2026-06-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-routing-record-founder-override-propagation-2026-06-21`
- Active packet: `reports/control_plane/pipeline-routing-record-founder-override-propagation-2026-06-21_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pipeline-routing-record-founder-override-propagation-2026-06-21_2026-06-21.md`
  - `reports/deferred/non_blocking/pipeline-routing-record-founder-override-propagation-2026-06-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pipeline-routing-record-founder-override-propagation-2026-06-21`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pipeline-routing-record-founder-override-propagation-2026-06-21_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-routing-record-founder-override-propagation-2026-06-21 --output reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-routing-record-founder-override-propagation-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-routing-record-founder-override-propagation-2026-06-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-routing-record-founder-override-propagation-2026-06-21`
- Active packet: `reports/control_plane/pipeline-routing-record-founder-override-propagation-2026-06-21_2026-06-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `66aa239a48327be71c080d206f2f17a10f219d38f7e0a7843bc5da4e76a4ce61`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-routing-record-founder-override-propagation-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pipeline-routing-record-founder-override-propagation-2026-06-21_2026-06-21.md`
  - `reports/deferred/non_blocking/pipeline-routing-record-founder-override-propagation-2026-06-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-routing-record-founder-override-propagation-2026-06-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
