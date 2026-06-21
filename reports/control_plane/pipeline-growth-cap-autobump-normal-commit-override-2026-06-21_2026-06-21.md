# NEXT-CODEX-POST-REDTEAM - growth-cap auto-bump uses the effective tracker-note-inclusive FOUNDER_OVERRIDE on the normal commit path so a declared override auto-bumps instead of stranding

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-growth-cap-autobump-normal-commit-override-2026-06-21
Phase-A-Lock: LOCKED
Purpose: STRUCTURAL pipeline hardening (founder-directed: guarantee the manual cap bump is never needed again on the normal commit path). CORRECTED ROOT CAUSE (code truth supersedes the original packet wording): the originally-asserted defect does NOT exist at the variable the original packet named. The Step-5e growth-cap auto-bump `_maybe_autobump_growth_cap_for_founder_override` is invoked with `founder_override_token`, and inside `_run_commit_pipeline_impl` that variable is resolved at Step 1 via `_resolve_control_surface_founder_override_token` from the handoff's `tracker_note_text` + `tracked_packet` + `embedded_handoff` -- i.e. it is ALREADY tracker-note + control-surface inclusive -- and is passed UNCHANGED to the Step-5e call (it is not reassigned between Step 1 and Step 5e). The original packet's proposed change -- "pass `effective_founder_override_token` to Step 5e" -- is INVALID: `effective_founder_override_token` is a LOCAL variable of the handoff-builder function (an earlier function, not `_run_commit_pipeline_impl`) and is NOT in scope at the Step-5e call site. The original "only filled in the `decision == UPDATE_TRACKER_ONLY` branch" premise is also false at the call site; the UPDATE_TRACKER_ONLY-gated assignments live in the handoff-builder region, not where Step 5e resolves its token. NET EFFECT: on the normal commit path the auto-bump already receives the declared FOUNDER_OVERRIDE whenever `_resolve_control_surface_founder_override_token` yields it; no `commit_executor.py` change is warranted. This wave is therefore re-scoped to VERIFY-AND-LOCK that call-site contract with a regression in an existing commit-executor test file, run against UNMODIFIED `commit_executor.py`. This complements #1141 (routing-record propagation, UPDATE_TRACKER_ONLY path); the normal commit path is covered by the Step-1 control-surface resolution.

## Scope

Verify and lock (regression-only) that the Step-5e growth-cap auto-bump already receives the tracker-note-inclusive FOUNDER_OVERRIDE on the normal commit path. Existing test file + indicator + tracker-sync only; NO `commit_executor.py` change; no runtime dirs; no new test file. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/tests/tools/test_commit_executor_post_merge_cleanup.py (MODIFY -- existing file; this is the CANONICAL home for growth-cap auto-bump tests: it already holds the `_init_growth_cap_repo` / `_growth_cap_source` / `_read_growth_cap_values` fixtures and the sibling `test_growth_cap_autobump_*` cases. Add the regression HERE, reusing those fixtures. Do NOT create a new test file, and do NOT place it in a file the evidence_command does not run -- the packet pins both the placement and the evidence_command to THIS file so they cannot diverge) -- add a regression that drives a NORMAL (non-UPDATE_TRACKER_ONLY) commit whose tracker note declares the wave's FOUNDER_OVERRIDE through `_run_commit_pipeline_impl` (exercising the Step-1 -> Step-5e token RESOLUTION, not merely calling the auto-bump function directly with an explicit `founder_override_token=` the way the existing sibling unit tests do) and asserts the Step-5e auto-bump (`_maybe_autobump_growth_cap_for_founder_override`) receives a NON-EMPTY token (cap bumps) instead of stranding; plus the fail-closed case (no declared override -> empty token -> no bump). The test must run against UNMODIFIED `commit_executor.py`. The evidence_command runs this whole file (no `-k` filter), so it covers the existing `test_growth_cap_autobump_*` siblings plus the new call-site regression; name the new test with `autobump`, `growth`, or `cap` so it stays discoverable alongside them.
- reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-21 tracker sync note for wave `pipeline-growth-cap-autobump-normal-commit-override-2026-06-21` carries this packet's L4 fields and is canonical: its `evidence_command` already names `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (matching this packet), and it carries the standard pre-commit-supervisor-refresh `progress_proof_before` / `progress_proof_after` / `evidence_delta` boilerplate shared by the sibling notes. Code truth (Purpose, above) governs: the verified call-site contract -- Step-5e already receives the Step-1-resolved tracker-note-inclusive `founder_override_token` with NO `commit_executor.py` change -- is proven by the passing regression test added in this wave (the executable evidence_command), not by note prose. No note-prose rewrite is required; the original packet's pre-correction description of the note (documented and superseded in Purpose, above) does not match the canonical note.

OUT of scope (verified already-correct -- do NOT modify):

- mu/tools/executors/commit_executor.py -- `_run_commit_pipeline_impl` already resolves `founder_override_token` from the tracker note + tracked packet + embedded handoff (via `_resolve_control_surface_founder_override_token`) at Step 1 and passes that same token to the Step-5e auto-bump. No change. The auto-bump function, the resolver, and the handoff-builder's `effective_founder_override_token` / UPDATE_TRACKER_ONLY logic are all unchanged.

## Work items

1. Re-confirm the call-site contract by reading the named surfaces (no line numbers): in `_run_commit_pipeline_impl`, confirm `founder_override_token` is resolved at Step 1 via `_resolve_control_surface_founder_override_token` (from `tracker_note_text` + `tracked_packet` + `embedded_handoff`), is not reassigned before Step 5e, and is the exact variable passed to `_maybe_autobump_growth_cap_for_founder_override`. Confirm `effective_founder_override_token` belongs to the handoff-builder function and is NOT in scope at Step 5e.
2. Add the regression to `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (the existing home of the growth-cap auto-bump fixtures + sibling tests; no new test file), reusing `_init_growth_cap_repo`: a normal (non-UPDATE_TRACKER_ONLY) commit whose tracker note declares the wave's FOUNDER_OVERRIDE, driven through `_run_commit_pipeline_impl`, makes the Step-5e auto-bump receive a non-empty token (cap bumps); and an undeclared override yields an empty token (no bump). Unlike the existing sibling unit tests (which call the auto-bump function directly with an explicit `founder_override_token=`), this regression must exercise the pipeline's Step-1 -> Step-5e token resolution. Assert against UNMODIFIED `commit_executor.py`.
3. Run the evidence_command; confirm the growth-cap/auto-bump regression passes against unmodified code; emit the indicator.
4. Confirm the wave's TASKS.md note matches code truth: its `evidence_command` already names `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (matching this packet) and it carries the canonical L4 fields with the standard pre-commit-supervisor-refresh proof boilerplate. The verified contract (Step-5e already receives the Step-1-resolved tracker-note-inclusive `founder_override_token`; NO `commit_executor.py` change) is proven by the passing regression test from Work item 2 -- executable evidence, not note prose -- so no note-prose rewrite is required; this packet's prose is reconciled to that code truth.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- L4_ENABLER: do NOT touch runtime dirs (mu/host/**, rcx_pi/selfhost/**). Test + indicator + tracker-sync only.
- Do NOT modify `commit_executor.py`. Code truth shows the normal-path auto-bump already receives the tracker-note-inclusive `founder_override_token`; the originally-proposed swap to `effective_founder_override_token` targets a variable that is out of scope at the Step-5e call site.
- Do NOT create a new test file (it would itself trip the growth cap); add the regression to the existing `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`. (Adding to an existing file means this wave does not trip the cap it concerns, and keeping it in the file the evidence_command runs prevents the placement/command divergence.)
- Do NOT alter `_maybe_autobump_growth_cap_for_founder_override`, `_resolve_control_surface_founder_override_token`, the handoff-builder, or the UPDATE_TRACKER_ONLY branch.
- Preserve the existing fail-closed behavior when NO override is declared (an undeclared override must still strand, not auto-bump) -- the regression asserts this, it does not change it.

## Stop conditions

- Stop done when the regression PASSES against UNMODIFIED `commit_executor.py` (proving the normal-path auto-bump already receives the tracker-note-inclusive declared FOUNDER_OVERRIDE, and an undeclared override yields no bump) and the indicator is collected.
- HALT as POLICY_BOUND if the regression FAILS against unmodified code: that would mean the real gap is inside `_resolve_control_surface_founder_override_token`'s gating, NOT the Step-5e call-site variable. There is no correct in-scope variable to swap to (`effective_founder_override_token` is out of scope), so do NOT blind-swap variables or widen the change -- surface the exact resolver-gating constraint for re-derivation and bridge re-review.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py` -- this is the file that holds the growth-cap auto-bump tests + fixtures, so running the whole file (no `-k` filter) covers the existing `test_growth_cap_autobump_*` siblings plus the new call-site regression. The packet evidence_command, the test placement, and the TASKS note's `evidence_command` all name the SAME file (see Work item 4 / Acceptance criteria).

## Acceptance criteria

- A regression in `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (driven through `_run_commit_pipeline_impl`, not a direct function call) PASSES against UNMODIFIED `commit_executor.py`, proving the Step-5e auto-bump already receives the Step-1-resolved tracker-note-inclusive `founder_override_token` on the normal (non-UPDATE_TRACKER_ONLY) commit path (non-empty token -> cap bumps).
- The fail-closed case holds (undeclared override -> empty token -> no bump).
- No `commit_executor.py` change; the auto-bump function, the control-surface resolver, the handoff-builder, and the UPDATE_TRACKER_ONLY branch are all unchanged; no runtime dirs; no new test file.
- The wave's TASKS.md note matches code truth: its `evidence_command` names `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (matching this packet) and it carries the canonical L4 fields. The verified contract -- Step-5e already receives the Step-1-resolved tracker-note-inclusive `founder_override_token` with NO `commit_executor.py` change -- is proven by the passing regression test, and this packet's prose is reconciled to that code truth.
- evidence_command clean; indicator emitted.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-growth-cap-autobump-normal-commit-override-2026-06-21`.
- Governing packet: this file, `reports/control_plane/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `pipeline-growth-cap-autobump-normal-commit-override-2026-06-21` carries this packet's L4 fields. Its `evidence_command` names `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` (matching this packet) and it carries the canonical L4 fields with standard proof boilerplate; the verified call-site contract (Purpose) governs and is proven by the passing regression test (see Work item 4 / Acceptance criteria).
- Authorization: Founder-directed 2026-06-21 (guarantee the manual growth-cap bump is never needed again -- it was the one manual step this session, on Stage0-c). Auto-authorized structural pipeline fix (feedback_manual_then_structural_autonomy).

FOUNDER_OVERRIDE:pipeline-growth-cap-autobump-normal-commit-override-2026-06-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-growth-cap-autobump-normal-commit-override-2026-06-21`
- Active packet: `reports/control_plane/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `reports/control_plane/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21_2026-06-21.md`
  - `reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-growth-cap-autobump-normal-commit-override-2026-06-21 --output reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-growth-cap-autobump-normal-commit-override-2026-06-21`
- Active packet: `reports/control_plane/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21_2026-06-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6d084097bbb761bd9ddb65620e4807b9ee7fc6b7cb5137bacefb0c3d918c720a`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `reports/control_plane/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21_2026-06-21.md`
  - `reports/l4_wave_indicators/pipeline-growth-cap-autobump-normal-commit-override-2026-06-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
