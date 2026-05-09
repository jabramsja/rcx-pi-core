# Deferred Active Mu Structural Nonblocking Cleanup

Date: 2026-05-09
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-active-mu-structural-nonblocking-cleanup-2026-05-09
Wave Class: L4_ENABLER
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:deferred-active-mu-structural-nonblocking-cleanup-2026-05-09

Purpose: Use the full dispatcher pipeline for a bounded cleanup of the active
deferred non-blocking `/mu` structural lane after PR #915 and PR #916, without
reusing the parent queue-controller packet whose Wave ID is
`deferred-mu-structural-residue-reconciliation-2026-05-09`.

## Scope

Files and directories in scope for the wave:

1. `reports/control_plane/deferred_active_mu_structural_nonblocking_cleanup__2026-05-09.md`
   as the same-wave governing packet.
2. `TASKS.md` only for detector-visible same-wave tracker grounding required
   before Phase B dispatch or commit automation.
3. `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` only as
   the parent `[NEXT-CODEX-POST-REDTEAM]` queue-controller reference. Do not use
   it as this wave's tracked packet because its explicit Wave ID is different.
4. `reports/deferred/non_blocking/README.md` and the active non-README markdown
   packets in `reports/deferred/non_blocking/`.
5. `reports/archive/deferred/` only for archive moves or closure snapshots for
   deferred non-blocking packets proven closed by PR #915, PR #916, or current
   code/report truth during the implementation phase.
6. `mu/tools/executors/executor_common.py`,
   `mu/tools/executors/executor_dispatch.py`, and focused tests only to preserve
   or correct the same-wave tracked-packet Wave ID guard. Builder and dispatcher
   must reject a selected tracked packet whose explicit Wave ID conflicts with
   the routed candidate before Phase A or chained Phase B can run.

## Work items

1. Treat this file, not
   `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`, as the
   tracked packet for
   `deferred-active-mu-structural-nonblocking-cleanup-2026-05-09`.
2. Before Phase B dispatch, ensure `TASKS.md` contains a detector-visible
   same-wave tracker entry for this wave and this packet. If the entry is
   missing, stop before implementation.
3. Inventory the active non-README deferred non-blocking packets at execution
   time and verify each one against current code/report truth with file:line or
   command evidence.
4. Remove from pending work any packet or section proven closed by PR #915,
   PR #916, current code truth, or current tracker truth. Archive closed packets
   or closure snapshots under `reports/archive/deferred/` and update the
   non-blocking README inventory to match the final filesystem state.
5. Do not relist already implemented founder-ordered `/mu` structural
   non-blocking proof-class work as unresolved. `TASKS.md` records
   `founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`
   as implemented/local evidence and separately tracker-synced.
6. If queue-grounding bridge residue can be closed by updating the active queue
   grounding, make only that bounded docs/control-plane update and archive the
   closed bridge packet.
7. Leave genuinely open `/mu` structural advisories active with current evidence
   and an explicit next-wave packet/task if implementation is warranted.
8. Preserve the same-wave dispatcher/builder Wave ID guard and run focused guard
   evidence. Pipeline-tool edits are limited to the guard and its tests.

## Constraints

- This Phase A rewrite does not authorize implementation work by hand. Subsequent
  work must route through the dispatcher pipeline.
- Do not edit Claude-related files or Claude home-directory surfaces.
- Do not edit Python/JS runtime, seed, Stage0, scheduler, registry, parity, or
  production `/mu` code in this cleanup wave.
- Do not widen JS runtime parity, host authority, host semantics, or bootstrap
  semantics from this cleanup packet.
- Do not reopen closed Phase A, deferred-sweep, mu-preproduction, audit, or
  remediation work unless current evidence proves a listed item is still
  unresolved.
- Do not treat `TASKS.md` authorization as proof that every historical listed
  packet remains unlanded. Current code/report truth and current tracker truth
  control closure decisions.
- Do not create new files outside the archive/readme/control-plane outputs named
  in Scope unless a stop condition routes the work to a separate bounded packet.

## Stop conditions

Stop before Phase B implementation or commit automation if any of these occurs:

1. `TASKS.md` lacks a same-wave tracker entry naming
   `deferred-active-mu-structural-nonblocking-cleanup-2026-05-09` and this
   packet.
2. Dispatcher or builder selects a tracked packet whose explicit Wave ID differs
   from the routed candidate.
3. The next proposed edit touches Claude-related files, Python/JS runtime, seed,
   Stage0, scheduler, registry, parity, production `/mu` code, or other out-of-
   scope surfaces.
4. A packet can only be resolved by new `/mu` structural implementation. Leave it
   active with current evidence and route a separate bounded packet/task.
5. A supposedly pending item is proven already implemented or closed. Remove it
   from pending work and acceptance criteria instead of relisting it.
6. A manual pipeline repair is needed beyond the same-wave Wave ID guard and
   focused regression scope. Stop and write a precise follow-up automation
   packet.
7. Current evidence cannot verify whether an active deferred packet is open or
   closed. Leave it active with the missing-evidence gap stated explicitly.

## Acceptance criteria

This wave is acceptable only when:

1. This packet has concrete Phase A sections for Scope, Work items, Constraints,
   Stop conditions, Acceptance criteria, and Grounding / Authorization.
2. This packet carries the wave-bound authorization line
   `FOUNDER_OVERRIDE:deferred-active-mu-structural-nonblocking-cleanup-2026-05-09`.
3. Before Phase B dispatch, `TASKS.md` carries a same-wave tracker entry for this
   wave and packet, satisfying the queue directive that every wave requires both
   a control-plane packet and a tracker entry.
4. The parent queue-controller packet remains a reference only; no routing or
   acceptance evidence treats
   `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` as this
   wave's tracked packet.
5. Every active non-README packet in `reports/deferred/non_blocking/` is either
   archived as closed with current evidence or left active with current evidence
   and an explicit next-wave packet/task for any warranted implementation.
6. `reports/deferred/non_blocking/README.md` matches the final active/archive
   filesystem state.
7. Already implemented or tracker-synced founder-ordered `/mu` structural
   non-blocking proof-class work is not relisted as unresolved.
8. Focused dispatcher/builder Wave ID guard evidence passes, and the closeout
   evidence also includes docs consistency, docs sync, stale NEXT checking, L4
   execution-contract validation, host-semantics ratchet, host-authority
   inventory ratchet, and founder closeout attestation.

## Grounding / Authorization

- `TASKS.md:445-453` authorizes `[NEXT-CODEX-POST-REDTEAM]` as UNPARKED,
  records the current phase as open only for separate bounded packets not already
  proven by landed work, and states that every founder-ordered wave requires a
  control-plane packet plus a `TASKS.md` tracker entry.
- `TASKS.md:453` authorizes autonomous dispatcher/pipeline progression through
  the founder-ordered red-team wave queue and allows manual pipeline repair only
  as a same-wave mechanical unblocker or precise follow-up automation packet.
- `TASKS.md:467` records the prior
  `founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06`
  wave as implemented/local evidence; `TASKS.md:469` records its same-wave
  tracker sync. This cleanup must not relist that proof-class decision as
  unresolved pending work.
- `TASKS.md:468` records the parent queue-controller bridge authority binding
  for `deferred-mu-structural-residue-reconciliation-2026-05-09`, using
  `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` as that
  packet. That packet is not this wave's tracked packet because it declares a
  different Wave ID.
- Parent governing reference:
  `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`, whose
  header declares Wave ID `deferred-mu-structural-residue-reconciliation-2026-05-09`
  and whose Scope/Work items/Constraints govern the broader queue only.
- Same-wave governing packet:
  `reports/control_plane/deferred_active_mu_structural_nonblocking_cleanup__2026-05-09.md`.
- FOUNDER_OVERRIDE:deferred-active-mu-structural-nonblocking-cleanup-2026-05-09

## Phase B Implementation Evidence

Execution inventory command:
`find reports/deferred/non_blocking -maxdepth 1 -type f -name "*.md" -print | sort | nl -ba`.

Current active inventory after cleanup:

1. `reports/deferred/non_blocking/README.md`
2. `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
3. `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
4. `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`

Archived during this wave:

1. `reports/archive/deferred/deferred-mu-structural-residue-reconciliation-2026-05-09_bridge_nonblockers_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
   - Closed by updating the parent queue grounding in
     `reports/control_plane/post_redteam_structural_queue_2026-03-20.md` to name
     the later same-task routed control-plane entries as references only.
2. `reports/archive/deferred/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
   - Closed by current tracker/control-packet truth for the implemented
     intentionally Python-only `evidence_walker.v1` proof-class outcome.
3. `reports/archive/deferred/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
   - Closed by PR #915 and `TASKS.md` tracker truth; the source proof-class
     mismatch is not active pending work.

Retained active advisories:

- Transparent JavaScript Proxy rejection remains active because closure requires
  a structural Mu provenance rule or explicit host-oracle authorization.
- Stage0 `capture_path` capture-table hardening remains active because closure
  requires separate `/mu` structural design and implementation.
- The repo-truth structural advisory packet remains active pending a separate
  bounded triage packet that splits coverage-proof, JS bridge evidence,
  pipeline governance, and Stage0 capture questions.

Dispatcher/builder guard status:

- `mu/tools/executors/executor_common.py` reads an explicit tracked-packet
  Wave ID and rejects post-merge routing-record construction when it conflicts
  with `wave_name`.
- `mu/tools/executors/executor_dispatch.py` rejects a selected tracked packet
  with a conflicting explicit Wave ID before Phase A dispatch and before
  chained Phase B.
- Focused tests live in `mu/tests/tools/test_executor_dispatch.py`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `deferred-active-mu-structural-nonblocking-cleanup-2026-05-09`
- Active packet: `reports/control_plane/deferred_active_mu_structural_nonblocking_cleanup__2026-05-09.md`
- Indicator artifact: `reports/l4_wave_indicators/deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/archive/deferred/deferred-mu-structural-residue-reconciliation-2026-05-09_bridge_nonblockers_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
  - `reports/archive/deferred/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
  - `reports/archive/deferred/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
  - `reports/control_plane/deferred_active_mu_structural_nonblocking_cleanup__2026-05-09.md`
  - `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/deferred-mu-structural-residue-reconciliation-2026-05-09_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/l4_wave_indicators/deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `deferred-active-mu-structural-nonblocking-cleanup-2026-05-09`
- Active packet: `reports/control_plane/deferred_active_mu_structural_nonblocking_cleanup__2026-05-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `57e249e4f4dc4299aea01a2fd2489029da8b904a53df7755eb42ebcc87f46e9e`
- Indicator artifact: `reports/l4_wave_indicators/deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/deferred_active_mu_structural_nonblocking_cleanup__2026-05-09.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_dispatch.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/archive/deferred/deferred-mu-structural-residue-reconciliation-2026-05-09_bridge_nonblockers_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
  - `reports/archive/deferred/founder-ordered-redteam-mu-structural-non-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
  - `reports/archive/deferred/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking_closed-by-deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.md`
  - `reports/control_plane/deferred_active_mu_structural_nonblocking_cleanup__2026-05-09.md`
  - `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/deferred-mu-structural-residue-reconciliation-2026-05-09_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/l4_wave_indicators/deferred-active-mu-structural-nonblocking-cleanup-2026-05-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
