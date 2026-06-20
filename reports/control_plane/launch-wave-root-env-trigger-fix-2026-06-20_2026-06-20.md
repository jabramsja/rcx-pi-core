# Launch Wave Root Env Trigger Fix 2026-06-20

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: launch-wave-root-env-trigger-fix-2026-06-20
Phase-A-Lock: LOCKED
Purpose: Fix launch_wave dispatcher child environment selection so RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT alone scopes inherited overrides but does not create an env-bearing runner call when no role or pager override is present.

## Scope

Pipeline launcher/control-plane test fix only. Do not touch runtime, substrate, seed, scheduler, registry, projection, StructuralNumbers, autoping watcher behavior, pager route semantics, role agent config defaults, or tmux scripts.

Files and surfaces in scope:

- mu/tools/executors/launch_wave.py (MODIFY) -- separate trigger override keys from the root-only scoping key while preserving child-env scrubbing.
- mu/tests/tools/test_launch_wave.py (MODIFY) -- add or adjust focused regression coverage for omitted pins under RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT-only parent env.
- reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md (GENERATED) -- launcher-created control packet.
- reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_wave_config.json (GENERATED) -- launcher-created wave config control artifact binding this wave id and indicator collection command.
- reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `launch-wave-root-env-trigger-fix-2026-06-20` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Update dispatcher_child_environment trigger logic so it ignores RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT when deciding whether a child env is needed.
2. Keep RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT in the scrubbed key set when a child env is needed for actual role or pager override keys.
3. Extend launch_wave tests so omitted pins plus a root-only parent env preserve runner kwargs as cwd-only.
4. Run the configured evidence command and collect the indicator artifact.

## Constraints

- Use launch_wave.py and executor_dispatch for this wave.
- Do not change role_agents, bridge_agent_defaults, pager route defaults, orchestrator mode, or model config.
- Do not change autoping watcher code in this wave.
- Do not touch runtime, substrate, seed, registry, projection, JavaScript parity, or StructuralNumbers files.
- Do not relax private-attribute test-integrity checks.

## Stop conditions

- Stop done when the focused launch_wave tests pass, private-attr checker passes for the touched test file, host semantics ratchet passes, the indicator artifact is collected, and commit/push/PR are handled through the commit executor.
- Halt as NEEDS_RESCOPING if the fix requires redesigning role-agent config resolution or pager routing rather than launch_wave child-env trigger selection.
- Halt as POLICY_BOUND if a proposed fix weakens private-attribute test-integrity checks or bypasses pre-push validation.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`

## Acceptance criteria

- With no implementer/reviewer/pager pins and only RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT inherited, run_wave_setup(..., launch=True) calls the runner with cwd only.
- With actual inherited role or pager override env keys, launch_wave still creates a sanitized child env and removes stale parent override keys.
- No private launch_wave module attributes are accessed from tests.
- No runtime/substrate/seed/parity files are touched.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `launch-wave-root-env-trigger-fix-2026-06-20`.
- Governing packet: this file, `reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `launch-wave-root-env-trigger-fix-2026-06-20` is canonical for this packet's L4 fields.
- Authorization: Founder-directed autonomous pipeline hardening: when the docs queue and autoping waves exposed the launch_wave root-only env trigger failure, split the repair into a deterministic structural pipeline wave instead of manually smuggling it through unrelated packets.

FOUNDER_OVERRIDE:launch-wave-root-env-trigger-fix-2026-06-20

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `launch-wave-root-env-trigger-fix-2026-06-20`
- Active packet: `reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md`
  - `reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id launch-wave-root-env-trigger-fix-2026-06-20 --output reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: launch-wave-root-env-trigger-fix-2026-06-20.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `launch-wave-root-env-trigger-fix-2026-06-20`
- Active packet: `reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5f3a3783aefd2c4e2fb87bc2ccef510ce007e4e76d6dd434bb362a845a9e99a2`
- Indicator artifact: `reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_2026-06-20.md`
  - `reports/control_plane/launch-wave-root-env-trigger-fix-2026-06-20_wave_config.json`
  - `reports/l4_wave_indicators/launch-wave-root-env-trigger-fix-2026-06-20.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
