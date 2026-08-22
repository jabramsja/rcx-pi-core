# PR 1219 P0IMLG Launch Source Common Dir Guard 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMLG-LAUNCH-SOURCE-COMMON-DIR-GUARD-2026-08-22]
Wave ID: pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22
Phase-A-Lock: LOCKED
Purpose: From exact merged PR #1238 authority e1ff9298c29f08f86d9ce8d1286db5d59526de9e, land only the deterministic launcher-source/target Git-common-directory identity guard proved necessary by the stopped P0IM restart-2 lane. The launcher must accept the canonical checkout and registered linked worktrees from the same repository while failing closed before config validation or artifact mutation for an identical-HEAD standalone clone, an unrelated repository, or an unresolvable Git-common-directory probe. Preserve all stopped P0IM evidence and keep P0IM nonlaunchable until this prerequisite merges.

## Scope

Add one fail-closed local repository-identity helper to launch_wave.py, call it first in both public mutation-capable entry points, and prove exact common-dir acceptance/rejection and mutation ordering in test_launch_wave.py. Advance TASKS from landed PR #1238 to P0IMLG current and fresh P0IM next without dropping unrelated work.

Files and surfaces in scope:

- mu/tools/executors/launch_wave.py (MODIFY) -- resolve the runtime launcher source SCRIPT_DIR and target repo_root with plain 'git rev-parse --git-common-dir' under a Git repository-override-scrubbed subprocess environment, normalize each result relative to its own probe cwd, require exact resolved equality, and invoke the guard before config validation and all artifact mutation in prepare_review_authority and run_wave_setup.
- mu/tests/tools/test_launch_wave.py (MODIFY) -- bind the existing temporary-repository fixture's launcher source to that repo, prove canonical and sibling linked-worktree acceptance, prove identical-commit standalone-clone rejection, prove inherited Git repository environment cannot spoof either probe, prove source/target probe failure, and prove both entry points fail before target artifact mutation or dispatcher invocation.
- TASKS.md (MODIFY THROUGH PIPELINE) -- record P0IMRB landed through PR #1238 at exact merge e1ff9298c29f08f86d9ce8d1286db5d59526de9e; make this P0IMLG wave the sole CURRENT row; make fresh P0IM restart-3 the sole immediate NEXT row but nonlaunchable until exact P0IMLG merge; preserve restart-2, every unrelated TODO, legacy-PR preservation, and fleet-cleanup obligations unchanged.
- reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json (GENERATED BEFORE REVIEW) -- same-wave candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave nonblockers only; edge cases cannot widen or delay landing.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from a fresh unique target branch/worktree/bus and a clean detached linked launcher source, all at exact PR #1238 merge e1ff9298c29f08f86d9ce8d1286db5d59526de9e and all initially sharing the canonical Git common directory. Preserve every stopped lane, branch, bus, source clone, commit, patch, and retry state as read-only evidence.
2. Implement a small fail-closed helper that runs plain 'git rev-parse --git-common-dir' independently with cwd=SCRIPT_DIR and cwd=repo_root, but only after scrubbing Git repository override variables from the subprocess environment so inherited GIT_DIR, GIT_COMMON_DIR, or GIT_WORK_TREE cannot bind either probe to an unrelated repository. Require successful bounded single-line nonblank output, anchor relative output to that probe cwd, resolve it, and require exact equality. Convert command failure, timeout, OS error, malformed output, or path-resolution error to LaunchWaveError.
3. Call the helper before WaveConfig.validate and before any candidate, TASKS, packet, routing, authority, bridge, indicator, or dispatcher action in both prepare_review_authority and run_wave_setup. Do not treat config validation as the repository-identity authority.
4. Adapt the existing wave_repo fixture so SCRIPT_DIR points to a real nested directory in the same temporary Git repository, then add focused tests for canonical target, a registered sibling linked worktree, an identical-HEAD standalone clone, inherited GIT_DIR/GIT_COMMON_DIR/GIT_WORK_TREE spoof attempts, source and target probe failure, and pre-mutation/pre-runner ordering across both entry points.
5. Update canonical queue truth without deleting, closing, reordering, or rewriting unrelated work. Route implementation, independent review, providerless commit, normal pre-push, CI, merge, exact origin/dev proof, and cleanup only through the pipeline.

## Constraints

- Exact PR #1238 merge e1ff9298c29f08f86d9ce8d1286db5d59526de9e is the hard dependency and must equal launcher-source HEAD, target HEAD before implementation, comparison_commit, and origin/dev immediately before launch; source and target must share the canonical Git common directory at launch.
- Use plain 'git rev-parse --git-common-dir'. Do not use '--path-format=absolute' because the installed Apple Git 2.24.3 does not implement that option. Resolve relative output against each individual probe cwd after repository-override environment scrubbing; cwd alone is not authoritative when GIT_DIR, GIT_COMMON_DIR, or GIT_WORK_TREE is inherited.
- The comparison-relative candidate allowlist is only TASKS.md, launch_wave.py, test_launch_wave.py, the exact same-wave packet/indicator, and only if generated the exact same-wave deferred report. This external WaveConfig and bus-local receipts are excluded from candidate content.
- Do not add HEAD, branch-name, remote-URL, clean-worktree, lexical-parent, inode, object-database, or worktree-registration policy. Exact resolved Git common-directory equality is the complete functional scope of this active blocker.
- Do not modify executor_common.py, executor_config.json, recovery_gate.py, phase_b_implementer.py, commit_executor.py, executor_dispatch.py, bridge adapters/client/config, candidate authority, model defaults, role/provider mappings, timeouts, hooks, observability, runtime, substrate, seeds, registry, JS files, or unrelated tests/docs.
- This is Python control-plane launch authority only and requires no JS mirror. All model-bearing roles and pager use Codex on predecessor gpt-5.5/xhigh; commit remains providerless. Nonblockers and edge cases cannot delay landing.

## Stop conditions

- Halt before launch unless origin/dev, clean detached linked launcher source, fresh target HEAD, and comparison_commit all equal exact e1ff9298c29f08f86d9ce8d1286db5d59526de9e; source and target share the canonical Git common directory; identities are unique; roles/pager are Codex; and commit is providerless.
- Halt as NEEDS_RESCOPING if the fix requires a functional file beyond launch_wave.py and test_launch_wave.py, changes repository identity policy beyond exact resolved common-dir equality, or changes models, roles, recovery, commit, bridge, runtime, substrate, or JS behavior.
- Halt as DEFECT if canonical checkout or registered linked-worktree targets are rejected; if a standalone clone, unrelated repo, inherited Git repository override spoof, failed/timeout/malformed probe, or differing common directory is accepted; or if rejection occurs only after candidate or bus artifact mutation.
- Halt if TASKS removes or rewrites any unrelated TODO/preservation item, treats restart-2 as resumable/pushed/landed, releases P0IM before exact P0IMLG merge, closes any legacy PR before unique-delta landing, or treats HOLD as cleanup authority.
- Do not claim this blocker complete or launch fresh P0IM restart-3 until deterministic PR merge, exact merge SHA, origin/dev equality, and pipeline cleanup evidence exist.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`

## Acceptance criteria

- A launcher-local helper obtains source and target common directories with bounded plain Git probes under a subprocess environment that removes Git repository override variables including GIT_DIR, GIT_COMMON_DIR, and GIT_WORK_TREE, rejects any command/output/resolution uncertainty, normalizes relative results against their respective cwd, and requires exact resolved equality.
- prepare_review_authority and run_wave_setup call the guard before WaveConfig.validate and before all target or bus artifact mutation; a mismatch cannot invoke the dispatcher runner.
- Focused tests prove canonical-to-canonical and canonical-to-registered-linked-worktree acceptance, identical-commit standalone-clone rejection, inherited Git repository override spoof rejection or neutralization for both probes, source- and target-probe failure rejection, and unchanged target artifacts on rejection for both public entry points.
- No model/default/config/role/provider/recovery/commit/bridge/runtime/substrate semantic delta enters the candidate, and host-semantics plus host-authority inventories remain unchanged.
- TASKS records P0IMRB landed through PR #1238, P0IMLG current, and fresh P0IM restart-3 gated behind this exact merge while preserving every unrelated queue and historical obligation.
- Focused tests, exact live candidate receipt verification, staged L4 enforcement, cached diff check, independent review, providerless commit, normal pre-push, required CI, merge, exact dev proof, and cleanup all pass.

## Grounding / Authorization

- Task: [PR1219-P0IMLG-LAUNCH-SOURCE-COMMON-DIR-GUARD-2026-08-22]; wave id `pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder prioritized landing, explicitly authorized narrower packets when convergence requires them, and asked that deterministic launch-wave safeguards become pipeline waves rather than manual fixes. The stopped P0IM restart-2 proves unrelated launcher-source Git identity is an active commit-stage blocker; this two-functional-file prerequisite is the minimum safe final precursor before fresh P0IM restart-3.

FOUNDER_OVERRIDE:pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `a75c192b02117e1ed317e45d2b68e513c5cfb69d9153bed7889d3072941f62c7`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_launch_wave.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_launch_wave.py`, `mu/tools/executors/launch_wave.py`, `reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tools/executors/launch_wave.py`
  - `reports/control_plane/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imlg-launch-source-common-dir-guard-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
