# P0IMRPAS North Star Numbering Repair 2026-08-22

Date: 2026-08-22
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PR1219-P0IMRPAS-NORTH-STAR-NUMBERING-REPAIR]
Wave ID: pr1219-p0imrpas-north-star-numbering-repair-2026-08-22
Phase-A-Lock: LOCKED
Purpose: Carry the already-reviewed P0IMRPA commit 7e95e66d8e26a6b01977b08459be06955ef28807 through a fresh pipeline branch and repair only the accidental TASKS North Star heading gap that blocked pre-push. Restore the invariant numbering from 1-12,14,15,16 to the exact continuous sequence 1-15 without reopening P0IMRPA implementation, changing PROGRAM QUEUE rows, or absorbing any successor or nonblocking work.

## Scope

Fresh nested repair branch at exact committed P0IMRPA head 7e95e66d. Modify only three North Star heading numbers in TASKS.md, permit launch_wave.py to add the canonical same-wave tracker note and governance artifacts, and land the combined two-commit history through the normal pipeline. Preserve the failed P0IMRPA lane/bus and all other queue/TODO content unchanged.

Files and surfaces in scope:

- TASKS.md (MODIFY THROUGH PIPELINE) -- change only North Star heading 14 to 13, heading 15 to 14, and heading 16 to 15, plus the canonical launcher-generated P0IMRPAS tracker note; preserve all PROGRAM QUEUE rows, labels, states, order, prose, and every other TODO.
- reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md (GENERATED) -- sole governing same-wave repair packet.
- reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json (GENERATED BEFORE REVIEW) -- exact same-wave current-candidate indicator.
- reports/deferred/non_blocking/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_bridge_nonblockers.md (GENERATED ONLY IF NEEDED) -- exact same-wave reviewer deferrals; nonblockers and edge cases cannot widen or delay this repair.
- TASKS.md -- tracker-sync authority. The 2026-08-22 tracker sync note for wave `pr1219-p0imrpas-north-star-numbering-repair-2026-08-22` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from a fresh clean worktree and canonical branch whose HEAD and comparison commit are exact P0IMRPA commit 7e95e66d8e26a6b01977b08459be06955ef28807; retain that commit unchanged as the repair commit's parent.
2. Change only the three shifted North Star heading numbers so the section is the exact continuous sequence 1 through 15. Do not rewrite the invariant text or modify any other TASKS content except the canonical launcher-generated tracker note.
3. Prove the exact formerly failing North Star invariant, staged L4 contract, and cached diff check, then leave broad pre-push, push, PR creation, CI, merge, exact dev verification, and cleanup to the normal pipeline.
4. Treat P0IMRPAS as a nested landing repair for P0IMRPA, not a new numbered PROGRAM QUEUE item. After combined merge, the existing fresh P0IMRP activation row remains the next serialized owner.

## Constraints

- Exact P0IMRPA commit 7e95e66d8e26a6b01977b08459be06955ef28807 is the comparison base and direct parent authority. The fresh target branch must be jabramsja/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22 and its unique worktree/bus must be clean before launch.
- Use the trusted detached predecessor launcher source at exact P0IMQR merge 14f3bc4acc828e49ba3d8c6c251bc8e899f97837. Do not resume or mutate the exhausted P0IMRPA continuation, target worktree, bus, branch, commit, receipt, handoff, packet residue, or recovery state.
- The comparison-relative candidate allowlist is only TASKS.md, the generated same-wave repair packet, the generated same-wave indicator, and the optional exact same-wave deferred nonblocker report. This external WaveConfig is excluded.
- Do not modify, restage, reconstruct, or re-review P0IMRPA production/test files. Do not change PROGRAM QUEUE numbering, labels, order, status, prose, or dependencies; do not add a numbered P0IMRPAS row.
- All model-bearing roles and pager routing use Codex. Commit execution remains providerless. No manual candidate edit, index mutation, commit, push, PR mutation, merge, or gate bypass is authorized. Nonblockers and edge cases cannot delay landing.

## Stop conditions

- Halt before implementation if the fresh target HEAD or comparison commit differs from exact 7e95e66d8e26a6b01977b08459be06955ef28807, if that commit is not descended directly from exact P0IMQR merge 14f3bc4acc828e49ba3d8c6c251bc8e899f97837, or if the branch/bus/worktree identity is not fresh and canonical.
- Halt as NEEDS_RESCOPING if any production/test code, predecessor packet, PROGRAM QUEUE content, or non-governance file must change, or if the North Star failure cannot be repaired solely by the three heading renumbers.
- Halt if any path outside the literal allowlist enters the comparison-relative candidate, if P0IMRPA commit 7e95e66d is rewritten or omitted, or if any actor proposes bypassing pre-push, review, CI, or merge authority.
- Do not release fresh P0IMRP until deterministic combined P0IMRPA/P0IMRPAS PR merge, exact merge SHA, origin/dev equality, and cleanup evidence exist.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrpas-north-star-numbering-repair-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`

## Acceptance criteria

- TASKS North Star contains exactly fifteen continuously numbered top-level invariants 1 through 15, with invariant text unchanged relative to P0IMRPA commit 7e95e66d except the three heading numbers.
- The comparison-relative staged set contains exactly TASKS.md, the generated P0IMRPAS packet, the generated P0IMRPAS indicator, and only if required the exact P0IMRPAS deferred nonblocker report.
- Every PROGRAM QUEUE row, label, state, order, prose, and dependency is byte-identical to P0IMRPA commit 7e95e66d; P0IMRPAS appears only in its canonical tracker note and governing same-wave artifacts.
- The repair branch retains exact P0IMRPA commit 7e95e66d as an ancestor; no P0IMRPA production/test file differs from that commit in the repair delta.
- The focused North Star invariant, staged L4 gate, diff check, normal pre-push, independent review, providerless commit, CI, merge, exact origin/dev proof, and cleanup all pass before fresh P0IMRP activation is released.

## Grounding / Authorization

- Task: [PR1219-P0IMRPAS-NORTH-STAR-NUMBERING-REPAIR]; wave id `pr1219-p0imrpas-north-star-numbering-repair-2026-08-22`.
- Governing packet: this file, `reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md`.
- TASKS.md authority: the 2026-08-22 tracker sync note for wave `pr1219-p0imrpas-north-star-numbering-repair-2026-08-22` is canonical for this packet's L4 fields.
- Authorization: Founder authorized autonomous narrow repair packets whenever a wave stops converging and made landing valuable changes onto dev the primary goal. P0IMRPA has one deterministic pre-push numbering blocker after successful review and commit; P0IMRPAS is the minimum combined-history repair and leaves the failed lane preserved.

FOUNDER_OVERRIDE:pr1219-p0imrpas-north-star-numbering-repair-2026-08-22

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0imrpas-north-star-numbering-repair-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrpas-north-star-numbering-repair-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrpas-north-star-numbering-repair-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0imrpas-north-star-numbering-repair-2026-08-22`
- Active packet: `reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ea1e7923c01d1b6d9a74e0bdab55e5675e9dc12f6ad6b4c7c201e3f6cd79acb5`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0imrpas-north-star-numbering-repair-2026-08-22 --output reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. scope_refs: `TASKS.md`, `reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md`, `reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22_2026-08-22.md`
  - `reports/l4_wave_indicators/pr1219-p0imrpas-north-star-numbering-repair-2026-08-22.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
