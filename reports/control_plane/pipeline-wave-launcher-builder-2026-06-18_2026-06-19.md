# Pipeline-Wave-Launcher-Builder-2026-06-18 2026-06-19

Date: 2026-06-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-wave-launcher-builder-2026-06-18
Phase-A-Lock: LOCKED
Purpose: Structural fix (ALWAYS USE BUILDERS): build mu/tools/executors/launch_wave.py + test that mechanizes the full dispatcher-wave setup from one config (reusing the existing builders), with a SIMPLE sequential design (NO transactional/rollback -- partial writes are recoverable), the standard fences (packet-integrity, line-ref lint, asterisk-free title, run_mu # SPEED_OK), fail-closed precondition + 3-guard verification, optional dispatcher launch. Eliminates the per-wave hand-written setup script. L4_ENABLER, tooling-only. Re-scoped after a transactional-design divergence.

## Scope

Files and directories in scope (additive, tooling-only):

- `mu/tools/executors/launch_wave.py` (NEW) -- the wave-launcher builder named in the tracker note's `structural_artifact_ref`. From one wave-config it mechanizes the full per-wave setup by reusing the existing setup builders.
- `mu/tests/tools/test_launch_wave.py` (NEW) -- focused regression test for the builder (the new test file behind the `CAP_TEST_FILES` 143->144 bump).
- `mu/tests/docs/test_growth_caps.py` -- bump the additive growth caps to admit exactly the two new files: `CAP_TEST_FILES` 143->144 and `CAP_TOOL_SCRIPTS` 53->54. No other count change.
- `TASKS.md` -- tracker-sync authority. The 2026-06-19 tracker sync note for wave `pipeline-wave-launcher-builder-2026-06-18` (Class L4_ENABLER, target_gate_id G8) is the single source of truth for this packet's L4 fields; the packet derives from it and does not restate state beyond it.

This wave touches no runtime/substrate dir; out-of-scope dirs are listed under Constraints.

- `reports/deferred/non_blocking/pipeline-wave-launcher-builder-2026-06-18_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

Concrete bounded tasks for this wave (from the TASKS.md tracker note for this wave id):

1. Create `mu/tools/executors/launch_wave.py` that, from one wave-config input, runs the full dispatcher-wave setup as a SIMPLE sequential chain over the existing builders: create_plan_draft (Phase A packet) -> TASKS.md tracker-sync note -> routing record -> bridge_config sync -> fail-closed precondition -> 3-guard verification -> optional dispatcher launch (off by default). No transactional/rollback layer; instead the chain is idempotent under the bounded re-run recovery contract in Work item 2, so a partial run is recovered by re-running the same config.
2. Define and implement the bounded re-run recovery contract -- this is the concrete meaning of "recoverable by re-running," and it is the sanctioned alternative to (not a reintroduction of) transactional rollback. Re-running launch_wave.py with the SAME wave-config is idempotent and convergent: each of the four artifact-producing steps detects its own prior output and leaves exactly one canonical copy -- (a) create_plan_draft rewrites the wave's packet in place at its deterministic path (one packet, never a duplicate), (b) the TASKS.md tracker-sync note is keyed by wave id and is NOT re-appended when a note for this wave id already exists (no duplicate note, honoring the known tracker-note bleed-forward hazard), (c) the routing record is upserted by wave id (no duplicate candidate), (d) bridge_config sync is a converging sync (a second run is a no-op-equivalent). The two verification steps (fail-closed precondition, 3-guard verify) and the optional launch persist no artifact, so they need no dedup and are safe to re-run. Bounded scope: the contract covers exactly these steps for the SAME wave-config and makes NO claim about concurrent runs or a changed config. Outcome: a re-run after any partial prior run converges to the single complete setup with no orphaned or doubled artifact.
3. Bake the standard packet fences into the generated draft path: packet-integrity (bare `FOUNDER_OVERRIDE:pipeline-wave-launcher-builder-2026-06-18` line plus Scope-mentions-TASKS.md), line-ref lint (no line numbers in packets), asterisk-free title, and the `run_mu` `# SPEED_OK` annotation.
4. Add `mu/tests/tools/test_launch_wave.py` covering the sequential setup, the fail-closed precondition, the 3-guard verify, the baked-in fences, and the bounded re-run recovery contract from Work item 2: simulate a partial setup (run the chain but abort after a subset of the artifact-producing steps), re-run the same wave-config, and assert convergence to exactly one canonical copy of each artifact (no duplicate packet, no duplicate TASKS.md tracker-sync note for the wave id, no duplicate routing record) with all setup steps completed.
5. Bump the growth caps in `mu/tests/docs/test_growth_caps.py`: `CAP_TEST_FILES` 143->144 and `CAP_TOOL_SCRIPTS` 53->54, matching exactly the two new files.

## Constraints

Explicitly NOT in scope:

- No transactional / rollback / two-phase-commit design. The wave was re-scoped to SIMPLE sequential after a transactional-design divergence; transactional behavior is out of scope.
- No runtime / substrate / seed changes. As an L4_ENABLER, this MUST NOT touch runtime dirs (`mu/host/`, `rcx_pi/selfhost/`, seed corpora).
- No host capability added. `check_host_semantics_ratchet.py` net_host_delta must stay 0.
- No L3 parity / JS work; `mu/host/js/eval_step.js` is untouched.
- Does not replace the dispatcher, Phase B, or commit executor. launch_wave.py only SETS UP and OPTIONALLY launches a wave.
- No edits to existing wave packets or unrelated executors beyond the two-file growth-cap bump.

## Stop conditions

- Halt and re-scope if the design drifts back toward transactional/rollback semantics (the prior divergence).
- Halt if the implementation would require touching any runtime dir or adding a host primitive -- that would invalidate the L4_ENABLER classification; re-classify before proceeding.
- Halt if `check_host_semantics_ratchet.py` reports net_host_delta != 0.
- Halt if the evidence_command goes red. Do not commit on a red gate.
- Phase A boundary: work for THIS turn ends at the rewritten packet. Do NOT implement launch_wave.py in Phase A; implementation is Phase B via the executor.

## Acceptance criteria

- `mu/tools/executors/launch_wave.py` exists and sets up a complete wave (the seven setup steps in Work item 1) from one config, reusing the existing builders.
- `mu/tests/tools/test_launch_wave.py` exists and passes.
- Re-run recovery is specified AND accepted: the bounded contract in Work item 2 is exercised by `test_launch_wave.py`, which simulates a partial setup and then re-runs the same wave-config and asserts convergence to exactly one canonical copy of each artifact (no duplicate packet, no duplicate TASKS.md tracker-sync note for the wave id, no duplicate routing record) with all setup steps completed. No transactional/rollback layer is introduced.
- evidence_command is green: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_launch_wave.py --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- `check_host_semantics_ratchet.py` confirms net_host_delta 0 (tooling-only, additive).
- Growth-cap test is green with `CAP_TEST_FILES` at 144 and `CAP_TOOL_SCRIPTS` at 54.
- Packets generated by the builder carry the baked-in fences (packet-integrity bare-`FOUNDER_OVERRIDE` plus Scope-mentions-TASKS.md, line-ref lint, asterisk-free title, `run_mu` `# SPEED_OK`).
- The L4 indicator is collected via the tracker note's `indicator_collection_command` into its `indicator_artifact_ref`.

## Request from Post-Merge Supervisor

Structural fix (ALWAYS USE BUILDERS): build mu/tools/executors/launch_wave.py + test that mechanizes the full dispatcher-wave setup from one config (reusing the existing builders), with a SIMPLE sequential design (NO transactional/rollback -- partial writes are recoverable), the standard fences (packet-integrity, line-ref lint, asterisk-free title, run_mu # SPEED_OK), fail-closed precondition + 3-guard verification, optional dispatcher launch. Eliminates the per-wave hand-written setup script. L4_ENABLER, tooling-only. Re-scoped after a transactional-design divergence.

Routed next-candidate:
pipeline-wave-launcher-builder-2026-06-18

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-wave-launcher-builder-2026-06-18.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-wave-launcher-builder-2026-06-18 --output reports/l4_wave_indicators/pipeline-wave-launcher-builder-2026-06-18.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-wave-launcher-builder-2026-06-18_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-wave-launcher-builder-2026-06-18.
<!-- L4_FIELDS_FROM_TRACKER:end -->

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-wave-launcher-builder-2026-06-18`.
- TASKS.md authority: the 2026-06-19 tracker sync note for this wave id in TASKS.md (Class L4_ENABLER, target_gate_id G8, structural_artifact_ref `mu/tools/executors/launch_wave.py`) is the canonical source for this packet's L4 fields; the auto-derived block above is generated from it.
- Governing packet: this file, `reports/control_plane/pipeline-wave-launcher-builder-2026-06-18_2026-06-19.md`.
- Authorization: standing pipeline-bug-fix authorization for pipeline control-surface builders (founder directive ALWAYS USE BUILDERS; pipeline-first parallel builders, 2026-06-09), plus the wave-bound founder override below.

`FOUNDER_OVERRIDE:pipeline-wave-launcher-builder-2026-06-18`

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-wave-launcher-builder-2026-06-18`
- Active packet: `reports/control_plane/pipeline-wave-launcher-builder-2026-06-18_2026-06-19.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-wave-launcher-builder-2026-06-18.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pipeline-wave-launcher-builder-2026-06-18_2026-06-19.md`
  - `reports/deferred/non_blocking/pipeline-wave-launcher-builder-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-wave-launcher-builder-2026-06-18.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pipeline-wave-launcher-builder-2026-06-18`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pipeline-wave-launcher-builder-2026-06-18_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-wave-launcher-builder-2026-06-18`
- Active packet: `reports/control_plane/pipeline-wave-launcher-builder-2026-06-18_2026-06-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `dce4ea3486e78f6b8034fc3e951d7cc915630f3bfacba8688f72901164b5973d`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-wave-launcher-builder-2026-06-18.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-wave-launcher-builder-2026-06-18_2026-06-19.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-wave-launcher-builder-2026-06-18.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pipeline-wave-launcher-builder-2026-06-18_2026-06-19.md`
  - `reports/deferred/non_blocking/pipeline-wave-launcher-builder-2026-06-18_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-wave-launcher-builder-2026-06-18.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
