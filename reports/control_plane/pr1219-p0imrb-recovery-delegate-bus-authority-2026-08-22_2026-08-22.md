# PR 1219 P0IMRB Recovery Delegate Bus Authority 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMRB-RECOVERY-DELEGATE-BUS-AUTHORITY-2026-08-22]
Wave ID: pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22
Phase-A-Lock: LOCKED
Purpose: From exact merged PR #1237 authority ab0b58db13f8dc97b73acf17f3720380ae6e3630, repair only the demonstrated recovery delegate bus-authority omission. A Tier-3 delegate implementer launched for a namespaced pipeline lane must receive that active namespaced bus and therefore resolve the same launch-frozen model authority as the diagnosis leg, rather than silently reading the canonical default bus. Preserve the stopped P0IM restart-2 lane unchanged, queue the launch source/common-dir guard as the sole immediate successor, and keep P0IM nonlaunchable until both prerequisites merge.

## Scope

Pass only the already-bound active bus from recovery_gate into phase_b_implementer.invoke_implementer and prove propagation with focused positive and default-path controls. Advance TASKS from landed PR #1237 through the immutable stopped P0IM restart-2 evidence to this current prerequisite, the launch common-dir guard next, and P0IM behind both exact merges.

Files and surfaces in scope:

- mu/tools/executors/recovery_gate.py (MODIFY) -- in _run_delegate_implementer_action, pass bus_dir=_active_bus_dir() to phase_b_implementer.invoke_implementer without changing backend, model_override, timeout, prompt, classifier, retry, scope-audit, or recovery policy.
- mu/tests/tools/test_recovery_gate.py (MODIFY) -- prove that run_recovery_loop(..., bus_dir=<namespaced bus>) reaches the reused fake implementer with that exact active bus; retain and, if needed, explicitly assert the existing default None behavior when no override is supplied. Do not mock away the run_recovery_loop context binding.
- TASKS.md (MODIFY THROUGH PIPELINE) -- record PR #1237 as landed at exact merge ab0b58db13f8dc97b73acf17f3720380ae6e3630; record P0IM restart-2 as PRESERVED_RESCOPED_NOT_COMPLETE with the unrelated-source common-dir commit failure and wrong-bus recovery-delegate evidence; make this P0IMRB wave the sole CURRENT row, P0IMLG the sole immediate NEXT row, and P0IM nonlaunchable behind both exact merges while retaining every unrelated TODO and preservation obligation.
- reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json (GENERATED BEFORE REVIEW) -- same-wave candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave nonblockers only; edge cases cannot widen or delay landing.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from a fresh unique target branch/worktree/bus and a clean detached linked launcher source, all at exact PR #1237 merge ab0b58db13f8dc97b73acf17f3720380ae6e3630 and all sharing the canonical Git common directory. Preserve the standalone source clone and stopped P0IM restart-2 lane as read-only evidence.
2. Thread _active_bus_dir() into the existing invoke_implementer keyword arguments. Do not reload, reinterpret, copy, or rewrite bridge configuration and do not add a new authority source.
3. Extend the existing FakeHybridImplementerModule call capture or an equally focused existing fixture so one namespaced run_recovery_loop invocation asserts the exact bus_dir passed to invoke_implementer. Preserve the established no-override behavior and all planning-agent resolution paths.
4. Update canonical queue truth without deleting, closing, reordering, or rewriting unrelated work. Route implementation, independent review, providerless commit, normal pre-push, CI, merge, exact origin/dev proof, and cleanup only through the pipeline.

## Constraints

- Exact PR #1237 merge ab0b58db13f8dc97b73acf17f3720380ae6e3630 is the hard dependency and must equal launcher-source HEAD, target HEAD before implementation, comparison_commit, and origin/dev immediately before launch.
- The comparison-relative candidate allowlist is only TASKS.md, recovery_gate.py, test_recovery_gate.py, the exact same-wave packet/indicator, and only if generated the exact same-wave deferred report. This external WaveConfig and bus-local receipts are excluded from candidate content.
- Do not modify phase_b_implementer.py, executor_common.py, executor_config.json, launch_wave.py, commit_executor.py, executor_dispatch.py, bridge adapters/client/config, candidate authority, model defaults, role/provider mappings, timeouts, hooks, observability, runtime, substrate, seeds, registry, JS files, or unrelated tests/docs.
- Do not introduce bridge-config copying, fallback authority, a new bus resolver, model overrides, or permissive error handling. The active recovery ContextVar is the sole authority to forward.
- This is Python control-plane authority only and requires no JS mirror. All model-bearing roles and pager use Codex on predecessor gpt-5.5/xhigh; commit remains providerless. Nonblockers and edge cases cannot delay landing.

## Stop conditions

- Halt before launch unless origin/dev, clean detached linked launcher source, fresh target HEAD, and comparison_commit all equal exact ab0b58db13f8dc97b73acf17f3720380ae6e3630; source and target share the canonical Git common directory; identities are unique; roles/pager are Codex; and commit is providerless.
- Halt as NEEDS_RESCOPING if the fix requires any functional file beyond recovery_gate.py and test_recovery_gate.py, changes recovery classification/delegation/retry policy, changes model or role authority, or modifies bridge/adapter/commit/launch/runtime behavior.
- Halt as DEFECT if a namespaced recovery delegate receives None, the canonical/default bus, or a different bus; if the no-override path stops preserving default semantics; or if planning and implementation legs acquire divergent authority.
- Halt if TASKS removes or rewrites any unrelated TODO/preservation item, treats restart-2 as resumable/pushed/landed, releases P0IM before both prerequisites merge, closes any legacy PR before unique-delta landing, or treats HOLD as cleanup authority.
- Do not claim this blocker complete or launch P0IMLG until deterministic PR merge, exact merge SHA, origin/dev equality, and pipeline cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`

## Acceptance criteria

- _run_delegate_implementer_action passes bus_dir=_active_bus_dir() into phase_b_implementer.invoke_implementer while preserving every existing invocation argument and behavior.
- A focused test drives run_recovery_loop with a namespaced bus and proves the reused implementer receives that exact bus; the no-override path retains None/default-bus semantics.
- No model/default/config/role/provider/bridge/commit/launch/runtime/substrate semantic delta enters the candidate, and host-semantics plus host-authority inventories remain unchanged.
- TASKS records PR #1237 landed, restart-2 immutable and not complete, P0IMRB current, P0IMLG next, and P0IM behind both exact merges while preserving all unrelated queue and historical obligations.
- Focused tests, exact live candidate receipt verification, staged L4 enforcement, cached diff check, independent review, providerless commit, normal pre-push, required CI, merge, exact dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMRB-RECOVERY-DELEGATE-BUS-AUTHORITY-2026-08-22]; wave id `pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder prioritized landing, explicitly authorized narrower packets when convergence requires them, and asked that deterministic launch-wave safeguards become pipeline waves rather than manual fixes. The stopped P0IM restart-2 proves this missing bus argument is an active model-authority blocker, so this two-functional-file prerequisite is the minimum safe first successor before the separately queued launch guard and fresh P0IM.

FOUNDER_OVERRIDE:pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `0e3d6e669a380237ef7bbcb7242892ade542089e12c6c3e0ac35fc5bc9e595b6`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrb-recovery-delegate-bus-authority-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
