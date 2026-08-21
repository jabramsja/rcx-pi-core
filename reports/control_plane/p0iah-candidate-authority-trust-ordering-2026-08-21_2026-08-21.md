# PR 1219 P0IAH Candidate Authority Trust And Ordering Hardening 2026-08-21

Date: 2026-08-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-P0IAH-CANDIDATE-AUTHORITY-TRUST-ORDERING-HARDENING]
Wave ID: p0iah-candidate-authority-trust-ordering-2026-08-21
Phase-A-Lock: LOCKED
Purpose: Immediately after P0IA and before P0IM, close the remaining explicit P0IA authority gaps and the launch-owned branch-identity loss exposed at P0IA commit without widening into lifecycle, commit-executor, dispatcher, collector semantics, model bootstrap, carry-forward, or unrelated hardening: bind the mutable bus-local authority spec and receipt back to trusted launch inputs, reject outside-scope candidate state before any target-lane collector can execute, and propagate the already-authorized fresh lane branch into the Phase B commit handoff.

## Scope

Strict successor to exact P0IA PR #1223 merge 0ccf8d18cb5149926e62d75a1b392120db9cfd32 (which includes P0IC4R/P0IC4S PR #1225 at 8fd5c898c8f18232e42a84356e29fd7150df1b99 and the complete 60-row queue) and strict predecessor to P0IM. Candidate scope is only the existing P0IA authority/launcher/Phase B seams, their focused tests, TASKS queue reconciliation, and exact same-wave generated artifacts. The external root WaveConfig is never candidate content.

Files and surfaces in scope:

- mu/tools/executors/candidate_authority.py (MODIFY) -- add trusted-spec receipt verification and a read-only pre-mutation scope guard; recompute and compare the evidence fields required by the P0IA packet.
- mu/tools/executors/launch_wave.py (MODIFY) -- bind the normalized authority spec identity, immutable launch inputs, and explicit authorized target branch into routed authority used by Phase B; preserve configs without pre-review authority.
- mu/tools/executors/phase_b_executor.py (MODIFY) -- require the launch-bound spec, run read-only scope rejection before any target-lane collector, run full candidate authority after the last indicator/packet mutation and before every reviewer entry, and carry the launch-owned fresh/restart branch into the commit handoff instead of re-deriving the stale canonical wave branch.
- mu/tests/tools/test_candidate_authority.py (MODIFY) -- prove receipt/spec tampering and plan/wave/phase/round or evidence mismatch fail closed against caller-owned expectations.
- mu/tests/tools/test_launch_wave.py (MODIFY) -- prove deterministic launch-bound spec and target-branch identity are present for opted-in fresh/restart lanes and absent-compatible for legacy configs.
- mu/tests/tools/test_phase_b_executor.py (MODIFY) -- prove a modified out-of-allowlist collector is rejected before execution, every review path consumes the trusted final receipt, and the Phase B handoff preserves the validated launch-owned target branch when the canonical wave branch already exists.
- TASKS.md (MODIFY THROUGH PIPELINE ONLY) -- mark P0IC4R/P0IC4S landed via PR #1225 at 8fd5c898c8f18232e42a84356e29fd7150df1b99, mark P0IA landed via PR #1223 at 0ccf8d18cb5149926e62d75a1b392120db9cfd32, make P0IAH the sole first NEXT, keep P0IM nonlaunchable until P0IAH lands, retain every existing TODO, and preserve exactly 60 sequential unique PROGRAM QUEUE rows.
- reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md (GENERATED) -- governing same-wave packet.
- reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json (GENERATED BEFORE REVIEW) -- current-candidate indicator.
- reports/deferred/non_blocking/p0iah-candidate-authority-trust-ordering-2026-08-21_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave deferrals that cannot widen or delay this hardening packet.
- TASKS.md -- tracker-sync authority. The 2026-08-21 tracker sync note for wave `p0iah-candidate-authority-trust-ordering-2026-08-21` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start a fresh unique lane and bus from literal P0IA merge 0ccf8d18cb5149926e62d75a1b392120db9cfd32 only; PR #1223 merged at 2026-08-21T16:06:49Z and origin/dev resolved exactly to that commit before setup.
2. Persist a deterministic digest plus normalized wave, comparison commit, allowlist, plan, indicator, and authority requirement from the launch-owned spec into the routed authority input. Phase B must reject a missing or mismatched spec before candidate code, collector code, or reviewer entry can rely on it.
3. Persist the validated fresh/restart target branch from launch into routing and Phase B commit handoff authority. A preserved canonical branch collision must select the explicit noncolliding restart descendant and must never trigger deletion, overwrite, implicit rename, or re-derivation from wave_id at commit time.
4. Verify each receipt against the trusted spec and caller-owned phase/review round rather than receipt-owned fields. Recompute the actual plan hash, inventory hashes, staged index/diff hashes, indicator hash, and staged L4 result; reject tampering or mismatch before review.
5. Add a side-effect-free pre-collector guard that inventories worktree, untracked, and staged index state against the literal base and exact allowlist. Invoke it before the existing target-lane collector or packet mutation, then retain the full post-mutation authority transaction immediately before each SDK, ordinary bridge, private-attribute, and re-entry reviewer subprocess.
6. Reconcile TASKS through the implementer only: mark row 4 P0IC4R plus its nested P0IC4S repair LANDED with exact PR #1225/8fd5c898c8f18232e42a84356e29fd7150df1b99 evidence; mark row 5 P0IA LANDED with exact PR #1223/0ccf8d18cb5149926e62d75a1b392120db9cfd32 evidence; make row 6 P0IAH the sole first NEXT; keep row 7 P0IM QUEUED and nonlaunchable until P0IAH lands; preserve every other item in relative order. The resulting queue has rows 0 through 59, deterministic carry-forward at row 19, the Phase A line-reference guard at row 20, PIPELINE-FIX-61 at row 21, and MU-OPTIMIZATION-LAST at row 59.
7. Route implementation, review, pager, staging, providerless commit, push, PR, CI, merge, and cleanup through the normal all-Codex pipeline. Do not launch P0IM until deterministic P0IAH merge evidence exists.

## Constraints

- Halt before launch unless PR #1223 is MERGED at 2026-08-21T16:06:49Z with merge SHA 0ccf8d18cb5149926e62d75a1b392120db9cfd32, origin/dev equals that SHA, and the P0IA feature worktree plus local and remote branches are absent.
- The exact candidate allowlist contains only TASKS.md; candidate_authority.py; launch_wave.py; phase_b_executor.py; their three focused test files; the same-wave packet and indicator; and the optional exact same-wave deferred report.
- Do not modify executor_dispatch.py, commit_executor.py, recovery_gate.py, bridge supervisor/client, collector semantics, runtime, substrate, role/model defaults, P0IM, P0IB, lifecycle/checker/process work, deterministic carry-forward implementation, or the Phase A line-reference guard implementation. Use their existing explicit target_branch contract rather than widening them.
- The already-deferred unsafe direct-API wave_id receipt-path issue remains nonblocking unless it becomes inseparable from the exact trusted-spec binding; do not widen for it.
- No manual patching of the candidate, staging, index editing, commit, push, merge, direct PR mutation, or reuse of the P0IA lane/bus is authorized.

## Stop conditions

- Halt before launch if P0IA merge authority is missing, dev is not exactly at that merge, the lane/bus is not fresh and unique, any model-bearing role or pager is not Codex, or commit execution is provider-backed.
- Halt reviewer entry if the launch-bound spec identity, pre-collector scope proof, final receipt, exact comparison inventory, same-wave indicator, or staged L4 result is absent, stale, malformed, self-derived, or mismatched.
- Halt as NEEDS_RESCOPING if closure requires dispatcher, commit, recovery, supervisor/client, collector-semantics, runtime/substrate, role/model, P0IB, or lifecycle/checker/process changes.
- Do not release P0IM before deterministic P0IAH merge evidence exists.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_b_executor.py`

## Acceptance criteria

- A bus spec or receipt changed after launch cannot authorize itself: wave/base/allowlist/plan/indicator/phase/round and evidence are checked against launch/caller-owned truth and real candidate state.
- Plan hash, phase, review round, literal and staged inventories, index tree, staged binary diff, indicator hash, and staged L4 evidence tampering each fail closed in focused tests.
- Any worktree, untracked, rename-old-path, or staged-index path outside the exact allowlist is rejected before the target-lane collector can execute; the full authority transaction is rerun after the last authorized mutation before reviewer Popen.
- Legacy non-opted-in configs remain compatible, while pre_review_authority=true waves cannot silently lose or replace their launch-owned spec.
- A fresh or restart branch explicitly authorized at launch survives Phase B handoff and commit validation even when the canonical wave branch exists; no manual branch deletion, rename, checkout, or candidate carry-forward is required.
- Candidate TASKS contains exactly 60 sequential unique rows 0 through 59 with P0IC4R/P0IC4S and P0IA LANDED, P0IAH row 6 as the sole first NEXT, P0IM row 7 QUEUED/nonlaunchable until P0IAH lands, deterministic carry-forward row 19, the Phase A line-reference guard row 20, PIPELINE-FIX-61 row 21, and every pre-existing TODO retained in relative order.
- Focused tests, staged L4 enforcement, independent review, providerless commit, CI, merge, exact origin/dev proof, and cleanup all pass without widening the packet.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-P0IAH-CANDIDATE-AUTHORITY-TRUST-ORDERING-HARDENING]; wave id `p0iah-candidate-authority-trust-ordering-2026-08-21`.
- Governing packet: this file, `reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md`.
- TASKS.md authority: the 2026-08-21 tracker sync note for wave `p0iah-candidate-authority-trust-ordering-2026-08-21` is canonical for this packet's L4 fields.
- Authorization: Founder authorized narrower packets when a wave stops converging, required all TODOs to remain synchronized in TASKS, prioritized landing over unrelated edge cases, and prohibited manual candidate Git operations.

FOUNDER_OVERRIDE:p0iah-candidate-authority-trust-ordering-2026-08-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `p0iah-candidate-authority-trust-ordering-2026-08-21`
- Active packet: `reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md`
- Indicator artifact: `reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_candidate_authority.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/candidate_authority.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md`
  - `reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id p0iah-candidate-authority-trust-ordering-2026-08-21 --output reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_b_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md. (2) Final pytest gate covered 10 pytest selector(s) across 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/candidate_authority.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md`, `reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: p0iah-candidate-authority-trust-ordering-2026-08-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `p0iah-candidate-authority-trust-ordering-2026-08-21`
- Active packet: `reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4f7666f17546e60747f5de1e2a5cfd2ee7f65c1f286d1e2be2e646ed4c1e8212`
- Indicator artifact: `reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_candidate_authority.py mu/tests/tools/test_launch_wave.py mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md. (2) Final pytest gate covered 10 pytest selector(s) across 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_candidate_authority.py`, `mu/tests/tools/test_launch_wave.py`, `mu/tests/tools/test_phase_b_executor.py`, `mu/tools/executors/candidate_authority.py`, `mu/tools/executors/launch_wave.py`, `mu/tools/executors/phase_b_executor.py`, `reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md`, `reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_candidate_authority.py`
  - `mu/tests/tools/test_launch_wave.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/candidate_authority.py`
  - `mu/tools/executors/launch_wave.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/p0iah-candidate-authority-trust-ordering-2026-08-21_2026-08-21.md`
  - `reports/l4_wave_indicators/p0iah-candidate-authority-trust-ordering-2026-08-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
