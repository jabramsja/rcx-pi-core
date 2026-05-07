# Docs-Root-Mu-Docs-Retained-Packet-Cleanup-2026-05-06

Date: 2026-05-07
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: docs-root-mu-docs-retained-packet-cleanup-2026-05-06
Parent retained cleanup wave: deferred-non-blocking-retained-residue-cleanup-2026-05-06
Class: L4_ENABLER
Category: docs/control-plane pipeline repair
Phase-A-Lock: LOCKED
Purpose: Build the first concrete Phase A plan for the retained docs-root/mu-docs bridge residue packet without widening into a repeat markdown audit or /mu structural work.
Governing packet: reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md
Authorization: TASKS.md:454 provides parent retained-lane cleanup authority for `deferred-non-blocking-retained-residue-cleanup-2026-05-06`; the 2026-05-07 tracker sync note for `docs-root-mu-docs-retained-packet-cleanup-2026-05-06` provides detector-visible same-wave L4_ENABLER authority for the routed retained candidate and its mechanical Phase B recovery hardening. Same-wave override is mechanically derivable as FOUNDER_OVERRIDE:docs-root-mu-docs-retained-packet-cleanup-2026-05-06.

Bridge Round 1 policy-bound correction: TASKS.md:435 requires every wave to have both a control-plane packet and a TASKS.md tracker entry. Direct readback found parent tracker authority for `deferred-non-blocking-retained-residue-cleanup-2026-05-06` at TASKS.md:454. The 2026-05-07 follow-on tracker sync now binds `docs-root-mu-docs-retained-packet-cleanup-2026-05-06` as the authoritative L4_ENABLER wave for this routed retained candidate and its mechanical recovery fix, while preserving the parent cleanup wave as retained-lane context only.

Bridge Round 2 policy-bound correction: TASKS.md:454 and the parent retained-residue packet authorize retained `reports/deferred/non_blocking/*.md` cleanup, archive snapshots, deferred inventory sync, TASKS tracker sync, and the same-wave L4 indicator artifact. They do not authorize edits to the older `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md` report. This packet therefore treats that historical control-plane report as an evidence/readback surface only, not a later Phase B edit surface for this retained-lane cleanup.

Manual recovery repair after Bridge Round 3 GO: `.agent_bus/recovery/recovery_status.json` records `wave_id` as `docs-root-mu-docs-retained-packet-cleanup-2026-05-06`, `step` as `pre_supervisor_l4_indicator_scope`, and `state` as `tier3_exhausted`. The diagnosed gate mismatch was that the earlier packet revision kept the parent cleanup wave in `Wave ID:` while the dispatcher routed `docs-root-mu-docs-retained-packet-cleanup-2026-05-06`; the pre-supervisor package then bound the parent wave and parent indicator instead of the routed candidate. This recovery refresh promotes the routed candidate to the authoritative `Wave ID:` and preserves the parent cleanup wave only as context. Same-wave repair also changes `mu/tools/executors/phase_b_executor.py` so `_refresh_phase_b_indicator_packet_scope` accepts exactly one matching top-level routed retained candidate when there is exactly one parent wave, and adds focused tests in `mu/tests/tools/test_phase_b_executor.py` so future retained-candidate packets cannot exhaust at the same gate.

## Scope: files/directories in scope

This Phase A rewrite edited only this governing packet:

- reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md

Phase A evidence scope was limited to the surfaces already identified by the bridge findings, TASKS grounding, and the stub packet:

- TASKS.md lines 430-456, especially TASKS.md:435 for founder-ordered wave/packet/tracker authority and TASKS.md:454 for retained deferred/non_blocking residue cleanup authority.
- reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md, the governing packet for this routed candidate with the retained-residue wave preserved as parent context.
- reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md lines 11-26, 38-43, and 45-50.
- reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md lines 69-80, 313-318, 472-487, 497-504, and 530-537.
- mu/tools/docs/generate_docs_index.py lines 132-140, only to verify the generated index target-set claim already cited by the retained packet.
- Current readback for mu/docs/README.md, only to verify the retained packet's stated generated-index output claim.

The later Phase B starts with one required retained-lane edit surface:

- reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md

The historical control-plane packet under review is not a Phase B edit surface in this retained-lane cleanup:

- reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md is evidence/readback only unless a separate tracker-backed control-plane rewrite packet authorizes that work.

Conditional Phase B edit surfaces are allowed only if the direct readback after the retained-lane edit proves the lane move is necessary:

- reports/deferred/non_blocking/README.md, only if deferred inventory changes.
- reports/archive/deferred/, only if all three retained findings are evidence-closed without editing the out-of-scope historical control-plane packet and archiving the retained packet is the minimal truthful lane move.
- TASKS.md, only if Phase B tracker sync is required for the implemented packet/report-lane change.
- reports/deferred/README.md, only if deferred inventory changes.
- reports/l4_wave_indicators/docs-root-mu-docs-retained-packet-cleanup-2026-05-06.json, only if Phase B needs same-wave indicator evidence for the routed retained candidate.
- mu/tools/executors/phase_b_executor.py, only for the same-wave mechanical recovery repair described above.
- mu/tests/tools/test_phase_b_executor.py, only for focused indicator-scope refresh regression coverage of that recovery repair.

## Work items: concrete bounded tasks from TASKS.md current phase

1. Bind this packet to the current `[NEXT-CODEX-POST-REDTEAM]` phase using TASKS.md:435, TASKS.md:454, and the 2026-05-07 routed-candidate tracker sync note, with same-wave authorization visible in this packet.
   - Result: complete after Bridge Round 1 correction and the 2026-05-07 mechanical repair tracker sync. TASKS.md:435 requires packet/tracker authority for every founder-ordered red-team wave and requires same-wave automation or a precise follow-up packet for manual pipeline repair. TASKS.md:454 authorizes retained deferred/non_blocking residue cleanup as docs/control-plane maintenance over retained report lane markdown, archive snapshots, deferred lane README inventory sync, TASKS tracker sync, and same-wave L4 indicator artifacts, with no runtime/substrate/seed/scheduler/registry/production implementation files changed. The 2026-05-07 tracker sync binds `docs-root-mu-docs-retained-packet-cleanup-2026-05-06` as the authoritative same-wave cleanup and mechanical recovery repair without widening into `/mu` structural production work.
2. Reproduce the retained packet's three targeted DOC_ACCURACY evidence claims without rerunning the completed all-root plus mu/docs markdown audit.
   - Result: complete. All three claims reproduced from the scoped readbacks below.
3. For each retained finding, decide one of three outcomes from reproduced evidence only: close only if retained-lane wording or current truth already removes the residue, archive the retained packet only if all three findings are closed without out-of-scope historical-packet edits, or retain the finding with current file-line evidence if packet/report/index wording cannot truthfully close it.
   - Result: complete. All three findings remain active for later Phase B retained-lane disposition cleanup; none are already implemented or inactive from the cited evidence. Historical control-plane wording remains evidence only in this wave because TASKS.md:454 does not authorize editing that older report packet.
4. Remove any pending work item from Phase B if the current cited evidence proves it is already implemented or no longer active.
   - Result: complete. No already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, seed-registration, all-root markdown audit, or /mu structural work is listed as pending here.
5. Lock the smallest Phase B edit set, validation set, and readback set before implementation.
   - Result: complete. The locked Phase B sets are below. This Phase A packet rewrite does not implement the underlying cleanup.

## Phase A reproduced evidence and decisions

| ID | Retained finding | Scoped readback | Phase A decision |
| --- | --- | --- | --- |
| R1 | Acceptance-criteria residue | The retained bridge packet keeps finding 1 active at reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md:11 through 26. The historical control packet still says at reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md:472 through 487 that only the same-wave TASKS note plus three docs cleanup files were edited and that no archive move is authorized. The same packet's later scope refresh/readback lists seven staged files, including the deferred bridge packet and indicator artifact, at lines 497 through 504 and again at lines 530 through 537. | Active DOC_ACCURACY residue. TASKS.md:454 does not authorize editing the historical control-plane packet in this retained-lane cleanup, so later Phase B must either keep the retained bridge finding active with current file-line evidence or stop for separate control-plane rewrite authorization. Do not treat the stale acceptance wording as proof of unlanded implementation. |
| R2 | Routing diagnostic residue | The retained bridge packet keeps the routing diagnostic finding active at lines 31 through 43. The historical control packet preserves a stale `.agent_bus/meta/post_merge_routing.json` diagnostic as "current" at reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md:69 through 80 and repeats the old stale-dispatch output at lines 313 through 318. | Active DOC_ACCURACY residue. TASKS.md:454 does not authorize editing the historical control-plane packet in this retained-lane cleanup, so later Phase B must either keep the retained bridge finding active with current file-line evidence or stop for separate control-plane rewrite authorization. Do not rerun routing or use post_merge_routing as authority for this packet. |
| R3 | Generated-index target-set residue | The retained bridge packet keeps the mu/docs README scope finding active at lines 45 through 50. The generator code at mu/tools/docs/generate_docs_index.py:132 through 140 uses `d.glob("*.md")` for each first-level docs directory, so it indexes direct markdown files inside each first-level docs directory, not every recursive active `mu/docs/**/*.md` path. The current readback command returns only `mu/docs/README.md`. Target-locator readback inside the historical packet shows the overstated F1/proposed-edit wording at reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md:388 and 397 through 404. | Active DOC_ACCURACY residue. TASKS.md:454 does not authorize editing the historical control-plane packet in this retained-lane cleanup, so later Phase B must either keep the retained bridge finding active with current file-line evidence or stop for separate control-plane rewrite authorization. Do not edit mu/docs/README.md or mu/tools/docs/generate_docs_index.py in this wave. |

Current generated-index readback used for R3:

```text
mu/docs/README.md
```

## Locked Phase B edit set

Phase B is authorized only after review / bridge convergence of this Phase A plan.

Required edits:

1. reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md
   - Update the retained finding dispositions from the reproduced evidence.
   - Because the currently reproduced residue depends on stale wording in an out-of-scope historical control-plane packet, retain the active findings with current file-line evidence unless Phase B direct readback proves a finding is already inactive without editing the historical packet.
   - If any finding would require changing reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md, stop for separate tracker-backed control-plane rewrite authorization instead of widening this retained-lane package.

Conditional edits:

- reports/deferred/non_blocking/README.md only if the bridge packet is moved out of the active non_blocking lane.
- reports/archive/deferred/ only if all three retained findings are evidence-closed without editing the out-of-scope historical control-plane packet.
- TASKS.md only if the Phase B package needs tracker sync for the implemented report-lane change.
- reports/deferred/README.md only if deferred inventory changes.
- reports/l4_wave_indicators/docs-root-mu-docs-retained-packet-cleanup-2026-05-06.json only if same-wave indicator evidence is needed for the routed retained candidate changed-file set.
- mu/tools/executors/phase_b_executor.py only for the same-wave mechanical recovery repair needed to resume after `pre_supervisor_l4_indicator_scope` exhaustion.
- mu/tests/tools/test_phase_b_executor.py only for focused regression coverage of that recovery repair.

## Locked Phase B validation and readback set

Readback required after Phase B edits. These commands include evidence-only surfaces and do not make those surfaces editable:

1. `nl -ba reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md | sed -n '60,90p;300,325p;384,406p;468,506p;526,540p'`
2. `nl -ba reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md | sed -n '1,70p'` if the bridge packet remains active.
3. `nl -ba reports/archive/deferred/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers*.md | sed -n '1,80p'` if the bridge packet is archived.
4. `nl -ba reports/deferred/non_blocking/README.md | sed -n '1,120p'` if deferred inventory changes.
5. `nl -ba TASKS.md | sed -n '430,456p'` if tracker sync changes.
6. `nl -ba mu/tools/docs/generate_docs_index.py | sed -n '132,140p'`
7. `comm -23 <(rg --files -g '*.md' mu/docs | rg -v '(^|/)(archive|archived)(/|$)' | sort) <(rg -o '\]\(([^)]*)\)' mu/docs/README.md | sed -E 's/^\]\(([^)]*)\)$/mu\/docs\/\1/' | sort)`

Validation required for later Phase B closeout:

1. `./tools/checks/check_docs_consistency.sh`
2. `./tools/session/founder_session_attest.sh closeout`
3. `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'indicator_scope_refresh'`
4. `python3 tools/checks/enforce_l4_execution_contract.py --staged`

These are later Phase B closeout validations, not authorization to run broad startup/pre-push/commit governance commands inside this Phase A packet rewrite.

## Constraints: what is NOT in scope

- Do not repeat the completed all-root plus mu/docs markdown audit unless current targeted evidence proves the prior inventory was incomplete.
- Do not inspect unrelated dirty files or examine unrelated executor/test changes during the retained docs cleanup.
- Do not create new files or write outside this governing packet except the locked retained-lane outputs, deferred inventory sync, TASKS tracker sync, same-wave indicator artifact, and the focused Phase B indicator-scope recovery repair/test paths listed above.
- Do not edit Claude-related files or Claude residue.
- Do not edit /mu structural, runtime, substrate, seed, scheduler, registry, production implementation, or hard-stopped /mu structural remediation packets.
- Do not edit README.md, mu/docs/README.md, mu/tools/docs/generate_docs_index.py, or L4DecisionCard unless Phase A proves a current doc-truth defect outside historical packet wording; if that proof appears, stop before widening into tooling or /mu structural work.
- Do not treat stale packet wording as proof that work remains unlanded. Prefer current code/doc/tool truth when it conflicts with old plan text.
- Do not perform manual pipeline repair unless it carries a same-wave mechanical fix or a precise next-wave automation packet, as required by TASKS.md:435. This packet's manual recovery repair is bounded to `mu/tools/executors/phase_b_executor.py` and `mu/tests/tools/test_phase_b_executor.py`.

## Stop conditions

- Stop if the three retained finding claims cannot be reproduced from the cited lines and commands without widening beyond the scoped files.
- Stop if resolving a finding requires /mu structural, runtime, substrate, seed, scheduler, registry, production implementation, or Claude-related edits.
- Stop if resolving a finding requires a full markdown audit rather than the targeted docs/control-plane residue cleanup authorized here.
- Stop if the evidence proves an item is already implemented or inactive; remove it from pending Phase B work instead of relisting it as unresolved.
- Stop if a finding is still active but cannot be closed by historical packet/report/index wording; retain it with current file-line evidence rather than forcing archive.
- Stop before Phase B implementation until this Phase A plan is reviewed and bridge-converged.

## Acceptance criteria

- This packet contains explicit Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization sections.
- The in-scope files/directories and out-of-scope boundaries are mechanically readable from this packet.
- Same-wave authorization is mechanically derivable through FOUNDER_OVERRIDE:docs-root-mu-docs-retained-packet-cleanup-2026-05-06, TASKS.md:454 parent cleanup authority, the 2026-05-07 routed-candidate tracker sync note, the authoritative `Wave ID:` header, and the explicit Authorization line above.
- Phase A work items are limited to the three retained low-severity DOC_ACCURACY findings cited by the stub packet and do not relist already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.
- A later Phase B may proceed only after direct readback either reproduces each retained finding or records why current truth removes it from pending work.
- A later Phase B edit set is limited to retained-lane surfaces authorized by TASKS.md:454; the older docs-root/mu-docs control-plane report is evidence/readback only in this cleanup wave.
- A later Phase B closeout must include direct readback of changed/archived packet lines, deferred inventory readback if inventory changes, `./tools/checks/check_docs_consistency.sh`, and `./tools/session/founder_session_attest.sh closeout`.

## Grounding / Authorization: TASKS.md authorization + governing packet refs

- TASKS.md:430-431 keeps `[NEXT-CODEX-POST-REDTEAM]` open only for future bounded work not already proven by the landed engine-state/scheduler slice and warns not to relist those landed items as unresolved.
- TASKS.md:435 is the founder-ordered red-team wave queue directive: every wave requires a control-plane packet plus a TASKS.md tracker entry; remediation is ordered by category and severity; manual pipeline repair requires same-wave mechanical automation or a precise follow-up packet.
- TASKS.md:453 binds the earlier docs-root/mu-docs redteam cleanup packet to `[NEXT-CODEX-POST-REDTEAM]`, `docs-root-mu-docs-redteam-cleanup-2026-05-06`, and same-wave control-plane authority while excluding Claude-related edits and /mu structural/runtime/substrate/seed/scheduler/registry/production implementation.
- TASKS.md:454 authorizes the retained deferred/non_blocking residue cleanup lane as docs/control-plane maintenance over retained report lane markdown, archive snapshots, deferred lane README inventory sync, TASKS tracker sync, and same-wave L4 indicator artifacts, with no runtime/substrate/seed/scheduler/registry/production implementation files changed.
- TASKS.md 2026-05-07 tracker sync note binds the routed retained candidate `docs-root-mu-docs-retained-packet-cleanup-2026-05-06` as L4_ENABLER for the focused Phase B indicator-scope recovery repair and retained-lane inventory sync.
- Governing packet for this routed retained candidate with TASKS.md:454 parent cleanup authority: reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md.
- Parent retained-residue governing packet: reports/control_plane/deferred_non_blocking_retained_residue_cleanup_2026-05-06.md.
- Historical docs-root/mu-docs cleanup packet under review: reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md.
- Retained bridge packet under review: reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md.

Routed next-candidate:
docs-root-mu-docs-retained-packet-cleanup-2026-05-06

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `docs-root-mu-docs-retained-packet-cleanup-2026-05-06`
- Active packet: `reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md`
- Indicator artifact: `reports/l4_wave_indicators/docs-root-mu-docs-retained-packet-cleanup-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md`
  - `reports/deferred/README.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-root-mu-docs-retained-packet-cleanup-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `docs-root-mu-docs-retained-packet-cleanup-2026-05-06`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `docs-root-mu-docs-retained-packet-cleanup-2026-05-06`
- Active packet: `reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `944a94517913fce84ae5c8d2d50ef8044eae2d5e1d3a9e7a6b49f1d3c013ff9b`
- Indicator artifact: `reports/l4_wave_indicators/docs-root-mu-docs-retained-packet-cleanup-2026-05-06.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_b_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/docs-root-mu-docs-retained-packet-cleanup-2026-05-06.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_2026-05-07.md`
  - `reports/deferred/README.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/docs-root-mu-docs-retained-packet-cleanup-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
