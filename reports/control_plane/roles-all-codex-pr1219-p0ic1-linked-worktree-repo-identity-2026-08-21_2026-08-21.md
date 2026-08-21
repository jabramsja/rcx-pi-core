# PR 1219 P0IC1 Linked Worktree Repo Identity 2026-08-21

Date: 2026-08-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IC1-LINKED-WORKTREE-REPO-IDENTITY]
Wave ID: roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21
Phase-A-Lock: LOCKED
Purpose: Land only the deterministic meta-supervisor repository-identity defect reproduced by P0IA commit: canonical-root supervisor code must accept a package in a sibling linked worktree only when both resolve to the same Git common directory, while unrelated repositories and failed probes remain fail-closed.

## Scope

Fresh P0IC1 restart lane at exact origin/dev P0IC0 merge commit 4d69a3a437b890dadb670de7aa3ab86234e3047c. Reconstruct only the exact two-file implementation preserved by 3c05baf637b5f3bbca1a794f10014c613babe80f: the two duplicated meta-supervisor repository-identity checks and focused tests in the existing supervisor test file, plus TASKS and generated same-wave governance only.

Files and surfaces in scope:

- mu/tools/agents/meta_bridge_supervisor.py (MODIFY) -- add one fail-closed resolved Git common-dir identity helper and use it at both pre-commit and post-merge package entrypoints.
- mu/tests/tools/test_meta_bridge_supervisor.py (MODIFY) -- prove both entrypoints accept a real same-repository linked worktree and reject an unrelated repository or failed identity probe.
- TASKS.md (MODIFY THROUGH PIPELINE) -- start from the exact 56-row P0IC0 merge snapshot at 4d69a3a437b890dadb670de7aa3ab86234e3047c, mark P0IC0 landed, keep P0IC1 next, and preserve every remaining task identity, order, TODO disposition, and the launcher's same-wave tracker note.
- reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json (GENERATED) -- same-wave indicator.
- reports/deferred/non_blocking/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave reviewer deferrals; nonblockers cannot widen or delay P0IC1.
- TASKS.md -- tracker-sync authority. The 2026-08-21 tracker sync note for wave `roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Implement a local helper that runs git rev-parse --git-common-dir from an explicit directory, anchors relative output to that directory, resolves the result, and returns no authority on empty output, nonzero exit, timeout, or OS error.
2. Use exact resolved common-dir equality for both run_meta_bridge and run_post_merge_bridge repository-identity checks. Preserve WRONG_GIT_REPO and every downstream schema, receipt, gate, and review behavior.
3. Add real temporary Git-worktree tests for both entrypoints plus unrelated-repository and failed-probe negative controls in the existing supervisor test module.
4. Reconcile TASKS.md through the implementer from the fresh lane's exact predecessor file, git object 4d69a3a437b890dadb670de7aa3ab86234e3047c:TASKS.md with SHA-256 363b56f9dfb5e78adf56c52614014bf0162df25b6f0fcd5b866da99ddfac9e08, preserving the generated P0IC1 tracker note and all 56 queue identities in order.
5. Run all implementation, review, pager, staging, commit, push, PR, CI, and merge roles through Codex with providerless commit from the fresh restart lane. Do not relaunch or resume the original terminal dispatcher, bus, continuation, or candidate-local commit path.

## Constraints

- The only starting commit is origin/dev 4d69a3a437b890dadb670de7aa3ab86234e3047c in a fresh unique P0IC1 restart branch, worktree, and bus.
- The exact candidate scope contains only TASKS.md; mu/tools/agents/meta_bridge_supervisor.py; mu/tests/tools/test_meta_bridge_supervisor.py; the same-wave generated packet; the same-wave indicator; and, only if produced, the exact same-wave deferred nonblocker report. This refreshed root WaveConfig, the exact predecessor TASKS object, and immutable source commit 3c05baf637b5f3bbca1a794f10014c613babe80f are external launch inputs and never candidate content.
- Do not modify meta_bridge_client.py, commit_executor.py, executor_dispatch.py, launch_wave.py, Phase A/B, recovery, bridge adapters, role/model configuration, runtime, substrate, or growth caps.
- Do not accept lexical similarity, shared remote URL, shared object content, or any identity weaker than exact resolved Git common-dir equality. Probe failure is rejection.
- P0IC1 is a pre-P0IA bootstrap packet and shares only the declared pre-P0IA review-authority waiver. It waives no implementation review, exact scope, tests, staged L4, providerless commit, CI, or merge gate.
- Add no new test or tool file. Nonblocking findings and adjacent edge cases cannot delay P0IC1.

## Stop conditions

- Halt before launch if origin/dev is not 4d69a3a437b890dadb670de7aa3ab86234e3047c, the restart branch, lane, or bus is not fresh and unique, any model-bearing role is not Codex, or commit execution is provider-backed.
- Halt as NEEDS_RESCOPING if the fix requires a file outside the exact code/test scope, weakens unrelated-repository rejection, or absorbs P0IC2, P0IA, role/model, lifecycle, or runtime work.
- Do not release P0IC2 until exact P0IC1 PR and merge SHA evidence exists.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`

## Acceptance criteria

- Both pre-commit and post-merge supervisor entrypoints accept a package in a real sibling linked worktree when the loaded supervisor source belongs to the same Git common directory.
- Both entrypoints return exact WRONG_GIT_REPO for separately initialized repositories and for identity-probe failure.
- Ordinary same-worktree behavior, package schema validation, receipt behavior, gates, and model review remain unchanged.
- The final candidate contains no new test/tool file and no commit, recovery, role/model, runtime, substrate, or nonblocker expansion.
- The exact binary full-index diff for only mu/tools/agents/meta_bridge_supervisor.py and mu/tests/tools/test_meta_bridge_supervisor.py matches preserved commit 3c05baf637b5f3bbca1a794f10014c613babe80f with SHA-256 a5e13cc012df45d508f7db140cd3ab118e56b153b6319f1bf5f0ec966ee36dfb and total delta +253/-11.
- Focused tests, host-semantics ratchet, staged L4 contract, independent review, providerless commit, CI, and deterministic merge are green.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IC1-LINKED-WORKTREE-REPO-IDENTITY]; wave id `roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21`.
- Governing packet: this file, `reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md`.
- TASKS.md authority: the 2026-08-21 tracker sync note for wave `roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21` is canonical for this packet's L4 fields.
- Authorization: Founder directed that nonconverging recovery be split into multiple narrower packets and that active blockers, not edge cases or nonblockers, be resolved to get the waves landed.

FOUNDER_OVERRIDE:roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21`
- Active packet: `reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md`
  - `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21 --output reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_meta_bridge_supervisor.py`, `mu/tools/agents/meta_bridge_supervisor.py`, `reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md`, `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21`
- Active packet: `reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `16b9b1a19f3427d6b582e7b3716975e507336de7d23f5947922180468254a9e8`
- Indicator artifact: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_meta_bridge_supervisor.py`, `mu/tools/agents/meta_bridge_supervisor.py`, `reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md`, `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `reports/control_plane/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21_2026-08-21.md`
  - `reports/l4_wave_indicators/roles-all-codex-pr1219-p0ic1-linked-worktree-repo-identity-2026-08-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
