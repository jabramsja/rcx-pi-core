# N3-Post-Pr1018-Host-Surface-Selection-2026-05-22

Date: 2026-05-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-post-pr1018-host-surface-selection-2026-05-22
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: Reconcile the current post-PR #1018 N3 host-surface queue against source-grounded tracker and packet evidence, then select exactly one bounded structural-reduction target or close with NO-GO when no current target is authorized.

## Scope

This packet is a control-plane selection closeout plus same-wave mechanical pipeline repair only.

- Phase A selection rewrite target: `reports/control_plane/n3-post-pr1018-host-surface-selection-2026-05-22_2026-05-22.md`.
- Bridge Round 1 authority-binding repair targets: `TASKS.md` tracker sync note and `reports/l4_wave_indicators/n3-post-pr1018-host-surface-selection-2026-05-22.json`.
- Bridge Round 2 / recovery mechanical pipeline guard targets: `mu/tools/executors/phase_b_executor.py`, `mu/tools/executors/tracker_sync_note.py`, `mu/tests/tools/test_phase_b_executor.py`, and `mu/tests/tools/test_tracker_sync_note_generation.py`.
- Allowed decision evidence: `TASKS.md:627-631`, `TASKS.md:635`, `TASKS.md:643-652`, `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:110-113`, `reports/control_plane/n3-active-residue-closeout-or-next-map-2026-05-14.md:151-177`, `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md:4`, `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md:137-139`, and `.agent_bus/meta/post_merge_package.json`.
- Runtime, `/mu` semantic implementation, substrate implementation, ratchet baselines, generated packages, commit/push/PR surfaces, and Claude files are out of scope. Test scope is limited to the same-wave pipeline guard tests named above. Indicator scope is limited to the same-wave L4 indicator artifact needed for detector-visible tracker binding.
- Phase B implementation write set: none. No successor implementation work is created by this packet.

- `reports/deferred/non_blocking/n3-post-pr1018-host-surface-selection-2026-05-22_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Re-ground `[NEXT-CODEX-POST-REDTEAM]` on current tracker truth:
   - `TASKS.md:627-631` keeps the queue open only for future bounded packets and states the engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and seed-registration slice is already landed.
   - `TASKS.md:635` requires dispatcher/pipeline routing, a control-plane packet plus tracker authority for every wave, and same-wave mechanical pipeline repair only with an automated guard or precise follow-up packet.

2. Reconcile the current N3 tracker segment before naming any target:
   - `TASKS.md:643` marks `FOUNDER-ORDERED-REDTEAM-MU-STRUCTURAL-NEXT-SLICE` as landed.
   - `TASKS.md:644` marks `N3-PROJECTION-LOADER-JS-BINARY-DECODER-PARITY` as implemented/local evidence.
   - `TASKS.md:645` is a Phase A source-lock prerequisite and tracker-authority note; it excludes runtime behavior changes and does not itself lock a bounded Phase B implementation write set.
   - `TASKS.md:646-647` mark the JS kernel marker-truth alignment and JS debt-summary truth sync as implemented/local evidence.
   - `TASKS.md:648-649` record the kernel-driver Mu fuel loop implementation evidence and residual follow-up split, not a fresh pending target.
   - `TASKS.md:650` is superseded by the later local-evidence design entry at `TASKS.md:651` and the explicit post-continuation NO-GO at `TASKS.md:652`.
   - `TASKS.md:651` marks the kernel-driver Mu-driver boundary design as implemented/local evidence.
   - `TASKS.md:652` marks the post-continuation marker-reduction decision as NO-GO/local evidence.

3. Exclude stale or closed candidates:
   - Do not relist engine-state/scheduler seed work as unresolved.
   - Do not carry forward the concrete projection-loader UTF-8 item: `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md:4` records `IMPLEMENTED / LOCAL EVIDENCE`, and `:137-139` records the current malformed UTF-8 error taxonomy behavior.
   - Treat the map-only categories in `reports/control_plane/n3-active-residue-closeout-or-next-map-2026-05-14.md:151-177` as selection context only, not direct implementation authority.

4. Record the Phase A outcome:
   - Selected target: none.
   - Target gate: none selected.
   - Locked Phase B write set: empty.
   - Parity proof, focused tests, ratchet expectations, rollback/default path, and acceptance criteria for implementation: not applicable because no bounded implementation target remains authorized by the allowed evidence.
   - Follow-on Phase B: blocked and not authorized by this packet.

5. Bridge Round 1 authority-binding repair:
   - Add the detector-visible same-wave `TASKS.md` tracker sync note required by `TASKS.md:635`.
   - Add the same-wave L4 indicator artifact required by `tools/checks/enforce_l4_execution_contract.py` for strict `--wave-id` binding.
   - Keep this repair control-plane only; it does not reopen runtime, `/mu`, semantic, marker, ratchet-baseline, generated-package, commit/push/PR, or Claude scope.

6. Bridge Round 2 / recovery mechanical pipeline guard:
   - Normalize locked-packet `Target gate: none selected` placeholders before Phase B package governance chooses a tracker-note gate, preserving the existing `G8` fallback for closeout/control-plane waves.
   - Reject invalid tracker-note target gates in `tracker_sync_note.py` before rendering, so `target_gate_id: none` cannot be emitted into `TASKS.md`.
   - Add focused tests proving the placeholder normalization, `G8` fallback, and renderer-side invalid-gate rejection.
   - Keep this repair in pipeline executor/test surfaces only; it does not alter `/mu` runtime semantics or reopen an implementation target.

## Constraints

- This rewrite writes only the selection packet, the Bridge Round 1 authority-binding tracker and L4 indicator surfaces, and the Bridge Round 2 / recovery pipeline guard files named in `Scope`.
- This packet does not authorize runtime, `/mu` semantic implementation, substrate implementation, ratchet-baseline edits, indicator-baseline edits beyond the same-wave artifact, generated-package edits, Claude-file edits, commit/push/PR commands, or new dispatcher/executor launches outside resumed same-wave pipeline recovery.
- Do not inspect downstream implementation files merely to decide whether a stub-listed candidate is already landed; this closeout relies only on the allowed evidence listed in `Scope`.
- Do not reopen items marked landed, implemented, local-evidence, archived, superseded by later local evidence, or explicit NO-GO unless current file truth in the allowed evidence set proves the item remains unresolved.
- Do not use host semantic shortcuts, helper authority moves, baseline-only cleanup, or marker-only deletion to make any future gate green.
- Do not treat `.agent_bus/meta/post_merge_package.json` empty `next_candidates` after PR #1018 as implementation authority; it is routing evidence supporting the bounded NO-GO decision.

## Stop conditions

- Stop with NO-GO because the allowed evidence does not identify a current authorized bounded N3 host-surface implementation target.
- Stop because the apparent concrete candidates in `TASKS.md:643-652` are landed, implemented/local-evidence, superseded by later local evidence, or explicit NO-GO, while the remaining source-lock prerequisite does not provide a locked Phase B implementation write set.
- Stop before Phase B because no exact implementation write set, tests, parity proof, ratchet expectations, rollback path, and implementation acceptance criteria can be locked from the allowed evidence.
- Stop if target selection would require reading downstream implementation files outside the allowed evidence set.
- Stop semantic work immediately if a dispatcher/pipeline failure appears; only same-wave mechanical pipeline repair with an automated/structural guard is authorized by the standing pipeline bug-fix rule.

## Acceptance criteria

- This packet contains concrete `Scope`, `Work Items`, `Constraints`, `Stop Conditions`, `Acceptance Criteria`, and `Grounding / Authorization` sections.
- The grounding section cites `TASKS.md` authorization, the current N3 tracker segment, governing packet references, `.agent_bus/meta/post_merge_package.json`, and a wave-bound override line.
- Pending implementation work excludes engine-state/scheduler seed work, projection-loader UTF-8 work, and any N3 entry marked landed, implemented, local-evidence, superseded by later local evidence, archived, or NO-GO in the allowed evidence.
- Phase A outcome is NO-GO/closeout: no current bounded N3 target is selected, no successor implementation work is created, and the Phase B write set is empty.
- Phase B remains blocked unless a future packet and detector-visible same-wave tracker authority lock an exact write set, tests, parity proof, ratchet expectations, rollback path, and acceptance criteria.
- Bridge Round 1 tracker authority is detector-visible in `TASKS.md` and bound to the same-wave L4 indicator artifact without widening semantic implementation scope.
- Bridge Round 2 / recovery proof shows the packet `none selected` target-gate placeholder no longer renders `target_gate_id: none`, and tracker note rendering rejects invalid non-`G1`-through-`G8` gates before `TASKS.md` mutation.
- Any same-wave pipeline repair remains limited to a mechanical dispatcher/pipeline defect, includes an automated/structural guard or precise follow-up automation packet, and does not authorize semantic `/mu` fixes.
- Reviewer reproduction should find the required section headings and authorization terms with:
  `rg -n "^(##[[:space:]]+)?(Scope|Work items|Work Items|Constraints|Stop conditions|Acceptance criteria|Grounding|Authorization)|FOUNDER_OVERRIDE|standing pipeline|Authorization:" reports/control_plane/n3-post-pr1018-host-surface-selection-2026-05-22_2026-05-22.md`

## Grounding / Authorization

- `TASKS.md:627-631`: `[NEXT-CODEX-POST-REDTEAM]` remains open only for future bounded work; the engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and seed-registration slice is already landed and must not be relisted as unresolved.
- `TASKS.md:635`: founder directive requires dispatcher/pipeline execution, packet plus tracker authority for every wave, and only bounded same-wave mechanical pipeline repair with an automated guard or precise follow-up automation packet.
- `TASKS.md:643-652`: current N3 tracker segment is status-bearing. It excludes the landed broad structural slice, implemented/local-evidence projection-loader binary decoder parity, implemented/local-evidence JS marker/debt-sync entries, completed kernel-driver implementation/design entries, and explicit post-continuation marker-reduction NO-GO from pending work. The Phase A source-lock prerequisite at `TASKS.md:645` lacks a locked implementation write set in the allowed evidence and is not direct Phase B authority.
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md:110-113`: any new structural reduction beyond listed queue state requires a separate bounded control-plane packet plus detector-visible `TASKS.md` tracker authority and does not authorize direct unpacketed `/mu` implementation.
- `reports/control_plane/n3-active-residue-closeout-or-next-map-2026-05-14.md:151-177`: retained N3 map-only categories are selection context, not automatic implementation authority.
- `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md:4` and `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md:137-139`: the concrete UTF-8 projection-loader taxonomy item is implemented/local evidence and excluded from pending work.
- `.agent_bus/meta/post_merge_package.json`: post-PR #1018 routing evidence reports `"deferred_items": []`, `"next_candidates": []`, and `"blocker_report_paths": []`; this is routing evidence for bounded NO-GO/closeout, not direct implementation authority.

FOUNDER_OVERRIDE:n3-post-pr1018-host-surface-selection-2026-05-22

Authorization: standing pipeline-bug-fix authorization applies only to same-wave mechanical dispatcher/pipeline defects that block this packet/tracker path; it does not authorize runtime, `/mu` semantic, marker, ratchet-baseline, indicator, generated-package, commit/push/PR, or Claude-file changes.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-post-pr1018-host-surface-selection-2026-05-22`
- Active packet: `reports/control_plane/n3-post-pr1018-host-surface-selection-2026-05-22_2026-05-22.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-post-pr1018-host-surface-selection-2026-05-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_tracker_sync_note_generation.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/tracker_sync_note.py`
  - `reports/control_plane/n3-post-pr1018-host-surface-selection-2026-05-22_2026-05-22.md`
  - `reports/deferred/non_blocking/n3-post-pr1018-host-surface-selection-2026-05-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-post-pr1018-host-surface-selection-2026-05-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-post-pr1018-host-surface-selection-2026-05-22`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-post-pr1018-host-surface-selection-2026-05-22_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-post-pr1018-host-surface-selection-2026-05-22`
- Active packet: `reports/control_plane/n3-post-pr1018-host-surface-selection-2026-05-22_2026-05-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `58cf0ef57b446c16a8f6bf6badf862cdaab4aee69ba0a170874ad34fac83d7ac`
- Indicator artifact: `reports/l4_wave_indicators/n3-post-pr1018-host-surface-selection-2026-05-22.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_tracker_sync_note_generation.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-post-pr1018-host-surface-selection-2026-05-22_2026-05-22.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-post-pr1018-host-surface-selection-2026-05-22.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_tracker_sync_note_generation.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/tracker_sync_note.py`
  - `reports/control_plane/n3-post-pr1018-host-surface-selection-2026-05-22_2026-05-22.md`
  - `reports/deferred/non_blocking/n3-post-pr1018-host-surface-selection-2026-05-22_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-post-pr1018-host-surface-selection-2026-05-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
