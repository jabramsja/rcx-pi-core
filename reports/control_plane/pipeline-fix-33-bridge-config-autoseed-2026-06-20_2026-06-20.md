# NEXT-CODEX-POST-REDTEAM - PIPELINE-FIX-33: launch_wave setup_bridge_config auto-seeds bridge_config on a fresh worktree

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-fix-33-bridge-config-autoseed-2026-06-20
Phase-A-Lock: LOCKED
Purpose: PIPELINE-FIX-33 structural pipeline hardening: make the launcher self-seed its bridge_config so launching a wave on a fresh worktree needs NO manual pre-seed step. Today launch_wave setup_bridge_config returns a graceful no-op when bridge_config.json is absent (the fresh-namespaced-bus case), so the orchestrator must manually call ensure_bridge_config_path then sync_bridge_config_agents_from_defaults before launching, every wave. That manual pre-seed is recurring toil and a footgun (forget it and the wave bus runs without the configured implementer/reviewer adapters). The fix: have setup_bridge_config first call ensure_bridge_config_path (the existing seeder, which copies the canonical default bridge_config into a fresh namespaced bus when a trusted source exists) BEFORE the present/absent branch, then run the existing validate + sync path. This is a tooling-only enabler: no runtime, substrate, seed, projection, or JS change. The existing fail-closed behavior MUST be preserved exactly -- a present-but- malformed bridge_config still raises LaunchWaveError, and when no trusted seed source exists the genuine graceful no-op still applies.

## Scope

Tooling-only fix to launch_wave setup_bridge_config plus its test. No runtime, substrate, seed, projection, or JS change. Uses TASKS.md as tracker-sync authority.

Files and surfaces in scope:

- mu/tools/executors/launch_wave.py (MODIFY) -- setup_bridge_config seeds a fresh bus via ensure_bridge_config_path before the present/absent branch, then validates + syncs; preserve fail-closed-on-malformed and genuine-no-source no-op.
- mu/tests/tools/test_launch_wave.py (MODIFY) -- add cases: fresh-worktree auto-seed+sync; present-but-malformed still raises; genuine-no-source no-op.
- reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `pipeline-fix-33-bridge-config-autoseed-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Read setup_bridge_config in launch_wave.py and ensure_bridge_config_path in executor_common.py to ground the fix in the existing seeder and the present/absent/malformed branches.
2. Modify setup_bridge_config to call ensure_bridge_config_path(repo_root, bus_dir) first so a fresh namespaced bus is seeded from the canonical default when a trusted source exists, then run the existing validate-and-sync path unchanged.
3. Preserve the fail-closed contract: a present-but-malformed bridge_config still raises LaunchWaveError; when no trusted seed source exists, the genuine graceful no-op still applies.
4. Add tests in test_launch_wave.py covering the fresh-worktree auto-seed-and-sync path, the present-but-malformed raise, and the genuine-no-source no-op.
5. Run the evidence command and collect the L4 indicator artifact.

## Constraints

- Use the pipeline launcher and dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Tooling-only: no change to runtime (eval_seed), substrate, seeds, projections, or JS production.
- Only ADD seeding for the absent-on-fresh-worktree case; do NOT weaken the present-but-malformed fail-closed or the genuine-no-source no-op.
- Do not change ensure_bridge_config_path or sync_bridge_config_agents_from_defaults semantics; only call the existing seeder earlier in setup_bridge_config.
- Keep the bounded re-run recovery contract: a second run over a healthy config remains a no-op-equivalent.

## Stop conditions

- Stop done when the evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if auto-seeding cannot be done without weakening the existing fail-closed-on-malformed behavior.
- If the fix would require touching runtime, substrate, or seed files, re-scope rather than relaxing the tooling-only boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`

## Acceptance criteria

- setup_bridge_config seeds a fresh namespaced bus from the canonical default then syncs, returning the path with the configured agents present.
- A wave launched on a fresh worktree no longer needs a manual ensure_bridge_config_path plus sync pre-seed.
- A present-but-malformed bridge_config still raises LaunchWaveError; the genuine-no-source case still no-ops.
- test_launch_wave.py covers all three cases and passes.
- net host semantics delta stays 0 and the indicator artifact is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-fix-33-bridge-config-autoseed-2026-06-20`.
- Governing packet: this file, `reports/control_plane/pipeline-fix-33-bridge-config-autoseed-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `pipeline-fix-33-bridge-config-autoseed-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder standing directive 2026-06-20: when a manual pipeline step recurs, land the structural fix so it never recurs. This removes the per-wave manual bridge_config pre-seed before launch_wave --launch (the unfixed #33 gap). Runs in parallel with the Stage 4 design wave (non-overlapping file ownership).

FOUNDER_OVERRIDE:pipeline-fix-33-bridge-config-autoseed-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-fix-33-bridge-config-autoseed-2026-06-20`
- Active packet: `reports/control_plane/pipeline-fix-33-bridge-config-autoseed-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pipeline-fix-33-bridge-config-autoseed-2026-06-20_2026-06-20.md`
  - `reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-fix-33-bridge-config-autoseed-2026-06-20 --output reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-33-bridge-config-autoseed-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-fix-33-bridge-config-autoseed-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-fix-33-bridge-config-autoseed-2026-06-20`
- Active packet: `reports/control_plane/pipeline-fix-33-bridge-config-autoseed-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `84ff60e7207a2d7963109a0fca3ff6e310f370696df2dfadf868b54df878e183`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-33-bridge-config-autoseed-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pipeline-fix-33-bridge-config-autoseed-2026-06-20_2026-06-20.md`
  - `reports/l4_wave_indicators/pipeline-fix-33-bridge-config-autoseed-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
