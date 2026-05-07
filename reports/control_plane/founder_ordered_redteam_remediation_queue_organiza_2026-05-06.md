# Founder Ordered Redteam Remediation Queue Organization

Date: 2026-05-06
Status: Phase B (implementation-complete, bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-remediation-queue-organization-2026-05-05
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: Prepare the smallest bounded Phase A plan for the routed next candidate, then retry the round-trip proof.

## Scope

This Phase A rewrite edits only this governing packet:

- `reports/control_plane/founder_ordered_redteam_remediation_queue_organiza_2026-05-06.md`

The downstream queue-organization wave authorized by this packet is planning/tracker organization only. Its write scope is limited to:

- `reports/control_plane/` remediation control-plane packets for the queued follow-up waves.
- `TASKS.md` tracker entries for each queued remediation wave.

The downstream wave's read-only source scope is limited to the authorized queue and audit-output evidence:

- `TASKS.md` entry `[NEXT-CODEX-POST-REDTEAM]`, especially lines 412-426 as reproduced for this Phase A rewrite.
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
- `reports/deferred/blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`
- `reports/deferred/blocking/founder_ordered_redteam_docs_audit_2026-05-05_blocking.md`
- `reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_blocking_closed-by-deferred-folder-cleanup-2026-05-07.md`
- `reports/archive/deferred/founder_ordered_redteam_tooling_audit_2026-05-05_blocking_closed-by-deferred-folder-cleanup-2026-05-07.md`
- `reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`
- `reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`
- `reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.md`
- `reports/archive/deferred/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.md`

Queue organization categories are `/mu`, docs, tests, and tooling. Blocking remediation waves are ordered before non-blocking remediation waves except for the explicit `/mu` structural exception: any `/mu` structural blocking or non-blocking remediation wave is ordered last and is a hard stop before implementation.

## Work Items

1. Reconstruct the remediation candidate inventory from the audit-output packets without implementing any remediation. Preserve each source finding's file:line or command-output evidence in the generated packet for that remediation wave.

2. Create or update the non-`/mu` blocking remediation wave packets first, with matching `TASKS.md` tracker entries:
   - Tests: 1 blocking tests fail-closed defect from `reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_blocking_closed-by-deferred-folder-cleanup-2026-05-07.md`.
   - Tooling/control-plane: 2 blocking tooling/control-plane defects from `reports/archive/deferred/founder_ordered_redteam_tooling_audit_2026-05-05_blocking_closed-by-deferred-folder-cleanup-2026-05-07.md`.
   - Docs: no blocking docs wave is expected from the current TASKS inventory because TASKS.md line 423 records 0 blocking docs findings.

3. Create or update the non-`/mu` non-blocking remediation wave packets next, with matching `TASKS.md` tracker entries:
   - Docs: 6 non-blocking DOC_ACCURACY doc/report drift findings from `reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`.
   - Tests: 2 non-blocking test-integrity/proof-class findings from `reports/archive/deferred/founder_ordered_redteam_tests_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06.md`.
   - Tooling: 2 non-blocking CI/audit-tooling findings from `reports/archive/deferred/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking_closed-by-founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.md`.

4. Create or update `/mu` structural remediation wave packets last, with matching `TASKS.md` tracker entries and an explicit hard stop before implementation:
   - Repo-code blocking: 1 blocking repo-code defect from `reports/deferred/blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`.
   - Repo-code non-blocking: 1 non-blocking proof-class mismatch from `reports/deferred/non_blocking/founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`.
   - Treat Python/JS substrate sync, `/mu` Stage0, and other structural `/mu` items as `/mu` structural unless their source packet proves a narrower non-`/mu` scope.

5. For every generated or updated remediation wave packet, include:
   - Task: `[NEXT-CODEX-POST-REDTEAM]`.
   - A deterministic wave ID.
   - Category and severity.
   - Source audit packet path.
   - Source finding evidence with file:line or command-output references.
   - Stop conditions and acceptance criteria specific to that remediation wave.
   - A tracker-update note for the matching `TASKS.md` entry.

6. Preserve current code truth guardrails from TASKS.md line 416. Do not relist the already landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.

7. Route the queue-organization work through the full dispatcher pipeline: post-merge supervisor -> Phase A -> Phase B -> commit executor. After this Phase A packet is accepted, retry the round-trip proof using this packet as the governing Phase A source.

8. If a manual pipeline repair is required to complete the queue-organization wave, add a same-wave mechanical/automated fix in dispatcher, builder, recovery, commit, pre-commit, or another appropriate pipeline surface, or add a precise follow-up automation packet before resuming.

## Constraints

- Do not implement remediation for repo-code, docs, tests, tooling, or `/mu` in this wave.
- Do not edit implementation files under `mu/`, `tools/`, `scripts/`, runtime hosts, tests, or docs outside the control-plane packet and `TASKS.md` tracker scope.
- Do not edit Claude-related files.
- Do not treat TASKS.md authorization as proof that every listed finding is still unlanded. If source evidence or current code truth proves a candidate is already implemented, remove that candidate from pending work items and acceptance criteria instead of relisting it as unresolved.
- Do not widen source review beyond the authorized queue packet, the cited audit-output packets, and the exact `[NEXT-CODEX-POST-REDTEAM]` TASKS entry unless a stop condition fires.
- Do not collapse blocking and non-blocking lanes into a single remediation wave.
- Do not dispatch any `/mu` structural remediation implementation from this queue-organization wave.

## Stop Conditions

- Stop if any required source audit-output packet is missing, unreadable, or lacks enough evidence to preserve file:line or command-output references in a remediation packet.
- Stop if a candidate's category or severity cannot be derived from the source packet without inference.
- Stop if queue organization would require editing implementation, tests, runtime, tool, or doc content outside `reports/control_plane/` packets and `TASKS.md`.
- Stop if any Claude-related file would need to be edited.
- Stop before implementing any `/mu` structural blocking or non-blocking remediation wave, even after the queue packet and tracker entry are created.
- Stop if the dispatcher/pipeline cannot represent the work without a manual repair; resume only after adding the same-wave mechanical/automated fix or precise follow-up automation packet required by TASKS.md line 420.

## Acceptance Criteria

- This Phase A packet contains concrete Scope, Work Items, Constraints, Stop Conditions, Acceptance Criteria, and Grounding / Authorization sections.
- Phase-A-Lock is `LOCKED` for bridge retry, with the queue order and hard-stop behavior stated explicitly.
- The downstream queue-organization wave creates or updates one control-plane packet and one `TASKS.md` tracker entry for each remediation wave that remains pending after source evidence review.
- Generated remediation waves are grouped by category and severity, with non-`/mu` blocking waves before non-blocking waves and any `/mu` structural blocking or non-blocking wave last.
- Every generated remediation packet preserves source finding evidence with file:line or command-output references.
- Already landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and seed-registration items are not relisted as unresolved.
- No remediation implementation is performed by this wave.
- No Claude-related file is edited.
- Any manual pipeline repair is paired with a same-wave mechanical/automated fix or a precise follow-up automation packet before the dispatcher resumes.

## Grounding / Authorization

- TASKS.md line 412 marks `[NEXT-CODEX-POST-REDTEAM]` as `UNPARKED` and founder-authorized.
- TASKS.md line 413 names the tracked packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- TASKS.md lines 414-420 authorize the founder-ordered wave queue, require the dispatcher/pipeline route, require control-plane packets plus `TASKS.md` tracker entries, require category/severity ordering, require blocking before non-blocking, and require `/mu` structural waves to be last with a hard stop before implementation.
- TASKS.md line 420 provides the parent queue override: `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- TASKS.md lines 422-425 identify the completed audit waves, their packet paths, their blocking/non-blocking output packet paths, and their current finding counts.
- TASKS.md line 426 authorizes manual pipeline repair only as a bounded unblocker paired with a same-wave mechanical/automated fix or a precise follow-up automation packet.
- Wave-bound same-wave authorization for this L4_ENABLER control-surface packet: `FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-remediation-queue-organization-2026-05-05`
- Active packet: `reports/control_plane/founder_ordered_redteam_remediation_queue_organiza_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-remediation-queue-organization-2026-05-05.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_remediation_queue_organiza_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-remediation-queue-organization-2026-05-05.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-remediation-queue-organization-2026-05-05`
- Active packet: `reports/control_plane/founder_ordered_redteam_remediation_queue_organiza_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `672c6ebf7968c261416aadfd8fde5c6f484170ab0117dfd350686dcfc9dfce4f`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-remediation-queue-organization-2026-05-05.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id founder-ordered-redteam-remediation-queue-organization-2026-05-05 --output reports/l4_wave_indicators/founder-ordered-redteam-remediation-queue-organization-2026-05-05.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_remediation_queue_organiza_2026-05-06.md. (2) Commit handoff carries 10 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-remediation-queue-organization-2026-05-05.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_mu_structural_non_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_remediation_queue_organiza_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tests_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tests_non_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tooling_blocking_remediation_2026-05-06.md`
  - `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-remediation-queue-organization-2026-05-05.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
