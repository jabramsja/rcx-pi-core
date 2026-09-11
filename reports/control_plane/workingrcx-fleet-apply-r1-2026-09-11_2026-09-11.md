# Bounded Recoverable WorkingRCX Fleet Cleanup Apply

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY]
Wave ID: workingrcx-fleet-apply-r1-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: ea17c44f45bc596b13606100ab57b878dba94744167f76f432c5243943d34fd4
Purpose: Execute the already-queued fleet cleanup for the exact four conditional candidates in the landed classification, preserving all other obligations. Build and land the bounded apply tool first, then use that landed tool for the real actions.

## Scope

One small bounded apply CLI, disposable focused tests, exact action plan and generated governance/tracker artifacts. No general fleet manager or new pipeline repair.

Files and surfaces in scope:

- mu/tools/executors/workingrcx_fleet_apply.py and mu/tests/tools/test_workingrcx_fleet_apply.py
- reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json
- TASKS.md, CHANGELOG.md and this builder's generated packet/indicator/optional nonblocker report
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `workingrcx-fleet-apply-r1-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Consume only the exact landed classification and its pinned raw SHA-256 supplied in this stub. Preserve the complete 411-row accounting and fixed four conditional candidate identities. Do not re-census the fleet, promote any of the 407 HOLDs, or touch any unlisted target. Fresh inspection is restricted to the four named targets and the existing common repository/operation evidence needed for their action. Landed classification: reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json, SHA-256 19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf, merge 23197ef9079ec47a022611dcc90fa848cbf4ee9f. Exact conditional source identities: [{"path":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-pr1219-p0imrp-receipt-model-provenance-activation-20260822","HEAD":"a6ee535a702875a62bb9170365d0b969320a9e32","branch":"refs/heads/jabramsja/pr1219-p0imrp-receipt-model-provenance-activation-2026-08-22","common_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git","git_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git/worktrees/WorkingRCX-pr1219-p0imrp-receipt-model-provenance-activation-20260822"},{"path":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-pr1219-p0imrpas-north-star-numbering-repair-20260822","HEAD":"ff2e0304432b1405cf1584f44e26535e1291fc29","branch":"refs/heads/jabramsja/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22","common_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git","git_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git/worktrees/WorkingRCX-pr1219-p0imrpas-north-star-numbering-repair-20260822"},{"path":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/workingrcx_pager_route_codex_20260701","HEAD":"ba51ce3e32043fcc529a258ad967c0630a644425","branch":"refs/heads/jabramsja/pager-route-codex-default-2026-07-01","common_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git","git_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git/worktrees/workingrcx_pager_route_codex_20260701"},{"path":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/workingrcx_setrolesdefault_20260628","HEAD":"13849e8aeea5d501078811f8b2b504cd72ff4f8e","branch":"refs/heads/jabramsja/set-roles-syncs-default-no-drift-2026-06-28","common_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git","git_dir":"/Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/.git/worktrees/workingrcx_setrolesdefault_20260628"}].
2. Implement separate non-mutating plan/validation and explicit apply modes. The repeated evidence_command must use only disposable tests and deterministic plan validation; it must never perform real fleet actions. No real target mutation before this tool passes the pipeline and lands. Provide the exact postmerge command for the foreground operator to execute once using the landed tool, with local receipts and recoverable destinations outside any source target.
3. Prefer recoverable relocation of each entire eligible linked worktree into a new unique preservation subdirectory over deletion. Preserve ignored/untracked evidence, symlink bytes, branch/history and any queue-relevant evidence, with verifiable before/after accounting. Do not discard caches/evidence or use force/remove/reset/stash/prune. If safe preservation or the supported Git worktree move cannot be proved for a target, record HOLD for that target, continue other valid candidates, and do not widen the wave.
4. Before any action reconcile exact source path, recorded HEAD, symbolic branch, Git/common directory and registration. Prove idle and not currently protected under TASKS or native active-owner/process evidence. Check action-time tracked/untracked/ignored state without executing target-owned filters or hooks. Drift, unmerged work, unreadable content, uncertain liveness or newly protected state is HOLD, not permission to adapt or retry destructively.
5. Use the existing supported safe never-behind preparation without losing WIP. Preserve proof of the recorded HEAD/history and evidence across any strictly fast-forward-only preparation. Then bind the exact prepared TARGET identity with bind_terminal_target_identity and place each actual terminal move/archive/removal action itself inside execute_terminal_mutation_once; that invocation must freshly fetch and prove behind(origin/dev)=0. Never bind the carrier in place of the target, use diagnostic readiness as authority, bypass the one-shot lock, or edit existing terminal boundary code. Any inability to satisfy the existing API is an explicit target HOLD.
6. Write durable local action outcomes and preservation locations; verify completed moves and retain source identities/history. Re-running an already consumed or ambiguous operation must not silently perform a second action. Repeated read-only plan output should reproduce/verify its owned output without overwriting unrelated files. Do not upload private preserved file contents or model transcripts to GitHub.
7. Focused tests use isolated disposable Git repositories outside the live fleet and outside arbitrary new .scratch descendants, disable automatic maintenance and inherited Git configuration, and cover the actual four-candidate flow, source/hash/identity mismatch, dirty/active/HOLD exclusion, fresh one-shot callback use, recoverable evidence preservation and explicit incomplete outcomes. Use the repository's installed Git capabilities without assuming an unsupported global option. Do not build a speculative compatibility matrix.
8. Keep TASKS/CHANGELOG synchronized: classification #1288 landed; apply pending until its code is merged AND each live outcome is recorded; preserve all 407 HOLDs and every existing later obligation. After the bounded action attempt, recovery R2, fresh R3C6-R2 and the retained PR1219/Mu queue continue unchanged. Do not mark the entire fleet clean or create new prerequisite waves for ineligible targets.

## Constraints

- Only the fresh carrier from the exact classification merge is implementation authority. Every stopped census/native-stub/retry carrier, bus, receipt and report remains unchanged; no copying or adopting stopped implementations.
- No changes to existing census/classification production code or tests, launch/dispatcher/recovery/commit executor code, model defaults, Claude-owned files, runtime or Mu. Reuse the existing terminal API; do not redesign it.
- No real fleet mutation during Phase A, implementation, review, tests or repeated evidence commands. Only the reviewed merged tool may execute the finite postmerge operation. Its exact destinations must be new, explicit and recoverable; no overwrite, broad glob, deletion, pruning, branch deletion or stale PR disposition.
- All selected local model-bearing roles remain Codex gpt-6-astra/max. Only the native pipeline refines the packet, implements, stages, reviews, commits, pushes and merges.
- Per-target HOLD preserves safety without blocking other valid targets or adding an unrequested wave. Keep changes narrow to the actual bounded cleanup, not hypothetical edge cases.

## Stop conditions

- Stop on wrong predecessor/source hash, malformed or incomplete source report, a broadened candidate set, or implementation outside the closed allowlist.
- Stop any action on protected, active, dirty, drifted or uncertain identity; report that target HOLD. No forced fast-forward, evidence overwrite, repeated terminal grant or mutation outside the existing callback boundary.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_apply.py --classification reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json --classification-sha256 19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf --classification-commit 23197ef9079ec47a022611dcc90fa848cbf4ee9f --plan-output reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-apply-r1-2026-09-11 --wave-class L4_ENABLER`

## Acceptance criteria

- Focused tests and repeated non-mutating evidence command pass; the exact apply plan is bound to landed classification and accounts for all four conditional candidates plus 407 untouched HOLDs.
- Real actions are gated until code lands and then require fresh per-target checks and the existing one-shot callback; successful outcomes are recoverable and preserve evidence/history.
- TASKS/report/packet distinguish code landing from actual operation completion and keep recovery R2 immediately next. No hypothetical precursor wave or false fleet-wide closure.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY]; wave id `workingrcx-fleet-apply-r1-2026-09-11`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `workingrcx-fleet-apply-r1-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-apply-r1-2026-09-11

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-apply-r1-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-apply-r1-2026-09-11 --output reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_apply.py --classification reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json --classification-sha256 19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf --classification-commit 23197ef9079ec47a022611dcc90fa848cbf4ee9f --plan-output reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-apply-r1-2026-09-11 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json`, `reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json`, `mu/tests/docs/test_growth_caps.py`.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-apply-r1-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `workingrcx-fleet-apply-r1-2026-09-11`
- Step-5e provenance: `bumped`
- Purpose: commit automation may bind the exact same-wave growth-cap governance file after Phase B review; first bumps require staged-index proof, while already-recorded reuse requires clean HEAD/index proof.
- Authorized generated governance path(s):
  - `mu/tests/docs/test_growth_caps.py`
- Scope binding: the path above is in scope only as the Step-5e same-wave growth-cap governance mutation or exact clean same-wave continuation evidence.
- Pre-review boundary: this block does not add the path to the locked Phase B/pre-review candidate allowlist and cannot authorize arbitrary implementation files.
- Acceptance binding: unsupported, malformed, outside-repo, dirty, wrong-wave, worktree-only, index/HEAD-mismatched, or provenance-free generated governance paths fail before supervisor.
<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-apply-r1-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `42e9d5ba337be1e919f0973ce7e2ef7207b3748ab77f8821fb188a3e78376beb`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_apply.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_apply.py --classification reports/control_plane/workingrcx-fleet-classification-r1-2026-09-11_classification.json --classification-sha256 19d684abaa8c3062ed7429447382b7ccf1d8df65dc4913a27ad6efe0ed3335cf --classification-commit 23197ef9079ec47a022611dcc90fa848cbf4ee9f --plan-output reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-apply-r1-2026-09-11 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_workingrcx_fleet_apply.py`, `mu/tools/executors/workingrcx_fleet_apply.py`, `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json`, `reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json`, `mu/tests/docs/test_growth_caps.py`.
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_workingrcx_fleet_apply.py`
  - `mu/tools/executors/workingrcx_fleet_apply.py`
  - `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-apply-r1-2026-09-11_apply_plan.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-apply-r1-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
