# Clear Stale Omitted L4 Decls 2026-06-09 2026-06-10

Date: 2026-06-10
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: clear-stale-omitted-l4-decls-2026-06-09
Phase-A-Lock: LOCKED
Purpose: GOAL: Fix commit_executor's L4-field reconciler (_conform_out_of_block_l4_decls) leaving a STALE out-of-block packet declaration of an L4-block field when the canonical tracker note OMITS that field. The reconciler's contract is that the tracker note is the single source and any out-of-block declaration of an L4-block field is conformed to the note; but for a field the note omits (empty note value), the per-field loop does "if not clean_value: continue" and skips conforming, so a stale packet line (e.g. a leftover "founder_override: old-token") survives even though the note no longer declares that field. This is the deferred P2 from PR #1090's bot review.

## Scope

In-scope files (explicit list):

- `mu/tools/executors/commit_executor.py` -- source under change: the L4-field reconciler `_conform_out_of_block_l4_decls` and the finite field set `_L4_FIELDS_FROM_TRACKER` it iterates.
- `mu/tests/tools/test_phase_a_executor.py` -- regression test for the reconciler; this is the wave `evidence_command` target (`PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`).
- `reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md` -- this Phase A plan / governing packet.

Behavioral scope: make `_conform_out_of_block_l4_decls` CLEAR a stale out-of-block declaration of an L4-block field the tracker note OMITS (e.g. `founder_override`) -- conform-to-absence -- instead of skipping via the empty-value `continue` and leaving the stale value. Strictly limited to the finite L4 field set `_L4_FIELDS_FROM_TRACKER`; non-L4 content untouched; the machine-owned block region byte-identical; idempotent. Deferred PR #1090 bot P2. Tooling-only L4_ENABLER; no runtime dirs.

- `reports/deferred/non_blocking/clear-stale-omitted-l4-decls-2026-06-09_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. In `mu/tools/executors/commit_executor.py`, change `_conform_out_of_block_l4_decls` so that when the tracker note OMITS an L4-block field (empty note value) AND the packet declares that field OUT OF BLOCK, the stale out-of-block declaration is CLEARED/removed (conform-to-absence) instead of skipped by the existing `if not clean_value: continue`.
2. Preserve the existing conform-to-value behavior for every field the note DOES declare (non-empty note value).
3. Keep the operation strictly bounded to the finite L4 field set `_L4_FIELDS_FROM_TRACKER` -- no non-L4 / human-authored packet line may be removed or rewritten.
4. Keep the machine-owned block region (between `<!-- L4_FIELDS_FROM_TRACKER:start -->` and `<!-- L4_FIELDS_FROM_TRACKER:end -->`) byte-identical; only out-of-block stale declarations are affected.
5. Keep the reconciler idempotent (a second pass over already-conformed text is a no-op).
6. Add a regression test in `mu/tests/tools/test_phase_a_executor.py` covering the `founder_override` omitted-but-stale case (packet has an out-of-block `founder_override: clear-stale-omitted-l4-decls-2026-06-09` line + a note that omits `founder_override` -> the stale line is cleared), plus assertions that note-declared fields and non-L4 content are unaffected and that the operation is idempotent.

Pending-status note: the single blocking finding is a DOC_ACCURACY mismatch -- the auto-derived L4 fields (`primary_invariant_id`, `evidence_command`, `evidence_delta`) had drifted from the canonical tracker note (TASKS.md line 514) and are reconciled to it in this rewrite. The finding does not prove any planned work item already landed, so the six Phase B work items above are retained as the plan of record. Per the rewrite constraints, downstream implementation files were not inspected to re-decide this.

## Constraints

What is NOT in scope:

- MUST NOT touch any runtime dir: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers` (L4_ENABLER rule).
- MUST NOT delete or rewrite arbitrary non-L4 / human-authored packet content -- only out-of-block declarations of fields in `_L4_FIELDS_FROM_TRACKER`.
- MUST NOT change conform-to-value behavior for fields the note DOES declare.
- MUST NOT alter the machine-owned `L4_FIELDS_FROM_TRACKER` block region (keep byte-identical).
- No masking: no retry/skip/xfail; do not weaken or delete existing reconciler tests.
- This turn rewrites the Phase A packet only; it does NOT implement the fix (that is Phase B).

## Stop conditions

- STOP (done) when `_conform_out_of_block_l4_decls` clears stale out-of-block declarations of note-omitted L4 fields, preserves note-declared fields and non-L4 content, keeps the block byte-identical and the operation idempotent, and the `evidence_command` passes.
- STOP and escalate as POLICY_BOUND if conform-to-absence cannot be achieved without touching a runtime dir, deleting non-L4 content, or mutating the machine-owned block region.
- STOP and escalate if the fix would require weakening/skipping any existing reconciler test.
- Do NOT proceed to Phase B implementation in this packet-rewrite turn.

## Acceptance criteria

- A packet with an out-of-block `founder_override: clear-stale-omitted-l4-decls-2026-06-09` line plus a tracker note that omits `founder_override` has the stale line CLEARED (conform-to-absence).
- Fields the note DOES declare remain conformed-to-value (existing behavior preserved).
- Non-L4 human-authored content is unchanged.
- The machine-owned block region (`L4_FIELDS_FROM_TRACKER:start` .. `:end`) is byte-identical before/after.
- The reconciler is idempotent (running it twice equals running it once).
- Behavior strictly limited to the finite `_L4_FIELDS_FROM_TRACKER` set.
- `evidence_command` is green: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`.
- No runtime dir touched; no masking; `git diff --check` clean.

## Grounding / Authorization

- TASKS.md authorization: tracker sync note (2026-06-10, `clear-stale-omitted-l4-decls-2026-06-09`), task `[NEXT-CODEX-POST-REDTEAM]` -- "clear stale omitted optional L4 declarations in packet reconciler." Class: L4_ENABLER. target_gate_id: G8. `primary_blocker_class: INTEGRATION`. `primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION`.
- Governing packet: `reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md` (this file). Origin: deferred P2 from PR #1090's bot review.
- Indicator artifact: `reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json`, collected by `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id clear-stale-omitted-l4-decls-2026-06-09 --output reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json`.
- FOUNDER_OVERRIDE:clear-stale-omitted-l4-decls-2026-06-09
- Authorization: standing pipeline-bug-fix authorization per memory `feedback_autonomous_executor_fix.md`; the wave-bound `FOUNDER_OVERRIDE:clear-stale-omitted-l4-decls-2026-06-09` token above lets commit automation derive the same-wave override mechanically (commit-gate + pre-push adjacency-cap clearance). The lower-case `founder_override` inside the auto-derived `L4_FIELDS_FROM_TRACKER` block below is machine-generated and must not be hand-edited; this section carries the canonical upper-case token.

## Request from Post-Merge Supervisor

GOAL: Fix commit_executor's L4-field reconciler (_conform_out_of_block_l4_decls) leaving a STALE out-of-block packet declaration of an L4-block field when the canonical tracker note OMITS that field. The reconciler's contract is that the tracker note is the single source and any out-of-block declaration of an L4-block field is conformed to the note; but for a field the note omits (empty note value), the per-field loop does "if not clean_value: continue" and skips conforming, so a stale packet line (e.g. a leftover "founder_override: old-token") survives even though the note no longer declares that field. This is the deferred P2 from PR #1090's bot review.

CONTEXT (verified on dev): _conform_out_of_block_l4_decls iterates the finite L4 field set (_L4_FIELDS_FROM_TRACKER). For each field it looks up clean_value = the note's value for that field; when the note omits the field, clean_value is empty and the loop skips ALL out-of-block rewrites for it. The docstring states this skip is deliberate ("a field the note does not declare is left as authored ... deleting human-authored content is out of scope"). The bot P2 establishes that for an L4-block field the note OMITS (notably the optional founder_override, which many L4_ENABLER notes omit), an out-of-block packet declaration of that field is drift the supervisor and bot will flag, because they read the note as truth -- so it should be CLEARED, not preserved.

REQUIRED FIX (narrow): when the tracker note OMITS an L4-block field (empty note value) AND the packet declares that field OUT OF BLOCK, CLEAR/remove the stale out-of-block declaration (conform-to-absence) instead of skipping it. Scope strictly to the FINITE L4 field set (_L4_FIELDS_FROM_TRACKER): an out-of-block declaration of a note-omitted L4-block field is by definition stale drift relative to the single-source note. This must NOT touch any non-L4 human-authored packet content, must keep the existing conform-to-value behavior for fields the note DOES declare, must keep the machine-owned block region byte-identical, and must stay idempotent. Add a regression test (in the reconciler's existing test file) covering the founder_override omitted-but-stale case (a packet with a stale "founder_override: old-token" line out of block plus a note that omits founder_override -> the stale line is cleared) plus assertions that note-declared fields and non-L4 content are unaffected, and that the operation is idempotent.

This is an L4_ENABLER tooling-only change (commit_executor.py plus its tests): MUST NOT touch any runtime dir (mu/host, mu/substrate, mu/closures, mu/bridge, mu/programs, rcx_pi/selfhost, mu/tools/compilers). No masking (no retry/skip/xfail; do not weaken existing reconciler tests). Scope strictly to the finite L4 field set; do not delete arbitrary human-authored packet content.

Routed next-candidate:
clear-stale-omitted-l4-decls-2026-06-09

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id clear-stale-omitted-l4-decls-2026-06-09 --output reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: clear-stale-omitted-l4-decls-2026-06-09.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `clear-stale-omitted-l4-decls-2026-06-09`
- Active packet: `reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md`
- Indicator artifact: `reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md`
  - `reports/deferred/non_blocking/clear-stale-omitted-l4-decls-2026-06-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `clear-stale-omitted-l4-decls-2026-06-09`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/clear-stale-omitted-l4-decls-2026-06-09_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `clear-stale-omitted-l4-decls-2026-06-09`
- Active packet: `reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `4aea0a667b47d428a0359566909f1e084e27b3d7f51319fc4a57a3e272755903`
- Indicator artifact: `reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_phase_a_executor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_phase_a_executor.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/clear_stale_omitted_l4_decls_2026-06-09_2026-06-10.md`
  - `reports/deferred/non_blocking/clear-stale-omitted-l4-decls-2026-06-09_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/clear-stale-omitted-l4-decls-2026-06-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
