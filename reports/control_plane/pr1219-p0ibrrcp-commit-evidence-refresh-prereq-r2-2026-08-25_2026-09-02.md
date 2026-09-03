# PR 1219 P0IBRRCP Commit Evidence Refresh Prerequisite R2

Date: 2026-09-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IBRRCP-COMMIT-EVIDENCE-REFRESH-PREREQ-R2]
Wave ID: pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 87a1a3d3a837e3edaf76130ed0c3fe20b6bb907cf224614d9be1005119d76a97
Purpose: Land only the still-occurring commit-time evidence-command overwrite blocker on exact PR #1265 merge authority: when an L4_ENABLER locked packet explicitly declares an evidence command and the current same-wave tracker/handoff command matches it exactly, preserve that command through both commit packet-truth refresh passes. Keep packet-absent and non-L4-ENABLER behavior unchanged.

## Scope

Fresh two-file commit-control atom from exact PR #1265 merge: preserve an already matching explicit L4_ENABLER evidence command across both commit packet-truth refresh passes, add compact focused regressions, and advance the exact TASKS baton to Phase-B evidence-handoff R2.

Files and surfaces in scope:

- Exact permitted path 1: TASKS.md for PR #1265 landed/current/next and preserved later queue synchronization only.
- Exact permitted path 2: mu/tools/executors/commit_executor.py inside commit packet-truth evidence refresh only.
- Exact permitted path 3: mu/tests/tools/test_commit_executor_receipt.py for compact matched, mismatch, repeated-refresh, packet-absent, and class-isolation regressions only.
- Exact permitted path 4: reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md for the Phase-A-authored canonical packet.
- Exact permitted path 5: reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json for Phase-B-generated L4 governance.
- Exact permitted path 6, conditional only on real findings: reports/deferred/non_blocking/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_bridge_nonblockers.md.
- TASKS.md -- tracker-sync authority. The 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub; preserve commit-evidence R1 unchanged as noncomplete evidence and use only ad1bbebb current code as implementation authority.
2. Within refresh_commit_path_packet_truth for effective L4_ENABLER only, resolve one unique explicit evidence_command from the already validated active same-wave locked packet and compare it exactly with the incoming current same-wave tracker/handoff command before any refresh mutation.
3. When packet and tracker/handoff authority match, preserve the exact decoded command through both _refresh_tracker_note_test_evidence call sites, TASKS tracker replacement, active packet truth rendering, and refreshed handoff persistence. Packet text alone must never independently authorize a command.
4. On missing uniqueness or explicit mismatch, return a deterministic commit packet-truth refresh error before replacing TASKS, rendering or persisting packet truth, or persisting a refreshed handoff.
5. When no explicit command exists, retain current staged-test derivation unchanged. Keep L4_STRUCTURAL, MAINTENANCE, and every non-L4-ENABLER class on their current path.
6. Add compact focused regressions for exact matched preservation across both passes and serialized outputs, repeated-refresh idempotence, mismatch mutation boundary, packet-absent legacy behavior, and non-L4-ENABLER isolation.
7. Use this stub's exact generic one-file evidence command so R2 can self-land without depending on the new preservation seam to change its own bytes.
8. Synchronize TASKS without loss: record reviewer-causality R4 landed through PR #1265 at ad1bbebbdb67dd8edd2ab2dec646173fc0cd2bfd; make R2 the sole CURRENT baton; make fresh Phase-B evidence-handoff R2 the immediate NEXT baton; retain fresh routing R4, R3C5/R3C6, exact PR1219 closure, PR census, never-behind, PR disposition, preservation-first fleet cleanup, and Mu production in their serialized order.
9. Retain a concise tracker note that the R4 pre-push load-sensitive five-second adapter test was operator-waived only after two broad runs passed 9043/9044 other tests and the exact failed test passed focused; do not absorb or fix that test in this wave.
10. Land normally through Phase B, providerless commit, PR, CI, merge, and cleanup, then builder-launch fresh Phase-B evidence-handoff R2 from the exact merge.

## Constraints

- Production/test scope is only commit_executor.py and test_commit_executor_receipt.py, plus TASKS and exact same-wave generated governance.
- Do not copy, resume, mutate, cherry-pick, or patch-transfer preserved commit-evidence R1; it is evidence only.
- Do not change phase_b_executor.py, phase_a_executor.py, executor_dispatch.py, launch_wave.py, recovery_gate.py, candidate_authority.py, bridge supervisor/adapters, receipt code, runtime, substrate, or Claude-owned files.
- Do not absorb the R4 pre-push timing flake, post-failure handoff demotion, post-merge selector alias, Phase-B evidence-handoff implementation, parser formats, receipt atomicity, pager naming, PR/fleet cleanup implementation, wording polish, or any non-occurring edge case.
- Do not weaken supervisor, literal allowlist, staged L4, commit, CI, review, or merge gates. Every model-bearing role is Codex gpt-5.6-sol ultra; commit remains providerless.
- Phase A owns the canonical packet; the operator supplies only this WaveConfig stub.

## Stop conditions

- Stop only if closure requires a production/test file outside commit_executor.py and test_commit_executor_receipt.py, or if exact ad1bbebb source authority is unavailable.
- Stop as DEFECT if a matching explicit L4_ENABLER command can still be replaced in TASKS, packet truth, or refreshed handoff during either refresh pass, or if mismatch mutates those surfaces before failing.
- Stop as DEFECT if packet-absent or non-L4-ENABLER behavior changes.
- Do not stop or widen for Phase-B, recovery, launcher, adapter, selector, cleanup, production, or deferred nonblocker work.
- If one packet-only correction fails to converge, preserve the attempt and create a narrower successor; do not enter a same-packet rewrite loop.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`

## Acceptance criteria

- Only the six explicit paths are wave-owned, with production/test changes confined to commit_executor.py and test_commit_executor_receipt.py.
- A unique explicit L4_ENABLER command equal to incoming same-wave tracker/handoff authority remains byte-identical through both refresh passes and serialized TASKS, packet, and handoff truth.
- Mismatch fails before TASKS replacement, packet rendering/persistence, or refreshed-handoff persistence; packet-absent and non-L4-ENABLER behavior remain unchanged.
- Compact focused tests and the exact one-file evidence command pass; staged L4, providerless commit, push, PR, required CI, review policy, merge, and cleanup complete through the pipeline.
- TASKS records PR #1265/ad1bbebb as landed, R2 as sole current, Phase-B evidence-handoff R2 as immediate next, and preserves every later PR1219, PR census, never-behind, PR disposition, fleet cleanup, and Mu production obligation.
- After merge, fresh Phase-B evidence-handoff R2 is builder-launched from the exact merge SHA; no preserved attempt is resumed.

## Grounding / Authorization

- Task: [PR1219-P0IBRRCP-COMMIT-EVIDENCE-REFRESH-PREREQ-R2]; wave id `pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md`.
- TASKS.md authority: the 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25

## Non-normative review clarification

This section fixes only the interpretation and regression detail for Work items 2-7 and the existing acceptance criteria; it does not replace, amend, or supersede the native contract.

For this packet, uniqueness means uniqueness of the exact decoded command value, not uniqueness of textual occurrence. An "authored declaration" is a declaration-position lowercase field named `evidence_command` (shown here without declaration punctuation) in packet-authored text outside the marker-delimited `L4_FIELDS_FROM_TRACKER` machine block and outside the marker-delimited `COMMIT_PATH_TRUTH_REFRESH` generated block. Count every declaration form already recognized and conformed by `reconcile_packet_l4_fields_block`, including plain or bold list items, compact grouped declarations, and supported inline-code declarations. Prose mentions are not declarations. The auto-derived block and the generated capitalized `Evidence command` summary label are replicas, not authored authority, and do not add votes merely because they repeat the same value.

A canonical authored occurrence has one nonempty value in the existing backtick-wrapped packet grammar. Decoding removes only that existing declaration syntax and Markdown wrapper; it does not tokenize, reorder, shell-normalize, regenerate, or otherwise alter payload bytes. Identical canonical occurrences therefore collapse to one decoded value and are legitimate. An empty, unwrapped, unterminated, ambiguous, or otherwise noncanonically decodable declaration-shaped occurrence is malformed, not absent, even when another occurrence is canonical.

The authorized comparison value is not supplied by packet text. It is the one canonical decoded value shared by the current same-wave TASKS tracker note and the incoming handoff's `tracker_note_text`; both representations must be present, canonical, singular by decoded value, and byte-identical before preservation mode is allowed. Perform this resolution before either `_refresh_tracker_note_test_evidence` call and before TASKS replacement or staging, packet rendering, writing or staging, handoff rebuilding, or refreshed-handoff persistence.

| Packet-authored state | Current same-wave TASKS / incoming handoff state | Required result |
|---|---|---|
| No authored declaration and no malformed declaration-shaped candidate | Existing authority remains otherwise valid | Use legacy staged-test derivation unchanged. A generated `L4_FIELDS_FROM_TRACKER` replica does not turn this into explicit-command preservation. |
| One or more canonical authored declarations, all decoding byte-identically to `C` | TASKS and handoff each have one canonical decoded value, and both equal `C` byte-for-byte | Treat identical occurrences as one authorized decoded value; preserve the exact bytes of `C` through both refresh passes and every serialization. |
| One unique authored decoded value `C` | TASKS or handoff authority is absent, malformed, non-unique, mutually different, or differs from `C` by any byte | Return a deterministic commit packet-truth refresh error before mutation. |
| Canonical authored declarations decode to two or more distinct values | Any | Return a deterministic conflict error before mutation. |
| Any authored declaration-shaped candidate is malformed or noncanonical | Any | Return a deterministic malformed-declaration error before mutation; never reinterpret this state as zero declarations. |

In preservation mode, every authored or generated replica, including the machine-owned block and commit-path truth-refresh block, must serialize the authorized value `C` exactly. A conflicting or malformed replica is not another authority source and must not be allowed to authorize or silently normalize a different command. Packet text alone never authorizes preservation. Each failing row must leave TASKS, the packet, its staging state, the input handoff, and any persisted handoff byte-identical to their pre-call snapshots and must return no refreshed handoff for persistence.

Work item 7's generic one-file command remains this wave's self-landing validation command; it is not sufficient as the matched-preservation regression fixture. At least one matched fixture must seed this exact non-synthesized payload into the packet-authored declaration and the byte-identical current same-wave TASKS and incoming handoff authority:

`PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py -k matched_preservation_nondefault`

The retained prefix deliberately matches the current helper's replacement pattern, while the selector makes the decoded value observably different from the synthesized one-file output. On the unfixed implementation the helper drops `-k matched_preservation_nondefault`, so the regression must fail.

Exercise and observe both existing `_refresh_tracker_note_test_evidence` passes in order, with a distinct assertion on the command emerging from each pass; a final-state-only assertion is insufficient. After each pass, and again after a repeated full refresh, assert that the literal payload above remains byte-identical in the canonical TASKS note, every authored packet declaration, the auto-derived packet block, the commit-path truth-refresh block, the returned handoff tracker note, and the persisted-and-reloaded handoff. Also assert that the selector-free synthesized payload is absent from those command fields. Add separate focused cases for zero authored declarations, identical duplicate authored declarations, distinct conflicting declarations, malformed or noncanonical declarations, TASKS/handoff disagreement, and an exact packet-versus-authority mismatch; every failure case must prove the pre-mutation boundary with byte snapshots.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `330342da069f4d5ddadb66454fde609acdc2d456f30ba843c92da5e128068f21`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25_2026-09-02.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-commit-evidence-refresh-prereq-r2-2026-08-25.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
