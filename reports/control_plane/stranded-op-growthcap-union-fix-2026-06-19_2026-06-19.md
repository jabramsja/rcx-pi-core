# NEXT-CODEX-POST-REDTEAM - stranded-op growth-cap conflict resolver union-fix (max-of-totals undercounts)

Date: 2026-06-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stranded-op-growthcap-union-fix-2026-06-19
Phase-A-Lock: LOCKED
Purpose: Fix a CONFIRMED first-use bug in the stranded-PR-landing op (commit_executor.land_stranded_pr, landed PR #1119). Its bring-current step resolves the mu/tests/docs/test_growth_caps.py merge conflict by taking the MAX of each CAP_* value (CAP_TEST_FILES / CAP_TOOL_SCRIPTS), which UNDERCOUNTS when the PR branch AND the base branch each added DISTINCT new test/tool files.

REPRODUCED 2026-06-19 landing PR #1107: head cap=143 (includes test_claude_pager_receiver.py), origin/dev cap=145 (includes the structural-numbers / launch_wave / land_stranded tests but NOT the pager test). After merging dev, the worktree has BOTH sets of new files -> 336 test files, but max(143,145)=145 -> limit = baseline 190 + 145 = 335 -> the pre-commit-doc-check growth-cap gate fails `assert 336 <= 335` -> `git commit --no-edit` exits 1 -> the op aborts and FAILS CLOSED (correct refusal, but the PR can never land). 'max value + union comments' is internally inconsistent: the unioned increment comments enumerate MORE files than either side's value.

FIX (commit_executor.py): change the bring-current growth-cap conflict resolution used by land_stranded_pr (and/or its conflict helper) so each resolved CAP_* covers the ACTUAL merged file count, NOT max(totals). PREFER REUSING the existing `_maybe_autobump_growth_cap_for_founder_override` helper (already mutates+stages test_growth_caps.py and is FOUNDER_OVERRIDE-aware) post-merge to bump each cap to cover the merged tree; OR compute base + count(union of the '+N for <file>' increment comment lines, deduped by filename). KEEP the union of the inline increment comment lines. Do NOT take max-of-totals. Fail closed (raise + surface) if the cap still cannot be made to cover the merged count.

TESTS (mu/tests/tools/test_land_stranded_pr.py, FAST + hermetic -- temp git repos, mock gh/merge, no network): UPDATE the existing growth-cap-conflict test to the corrected union behavior, and ADD a regression proving that a merge where BOTH sides added a distinct test file (and a distinct tool script) resolves each CAP_* to base+union (covering the merged count) so the resulting commit PASSES the growth-cap gate (the max-of-totals path would fail it). Mark NOTHING slow.

If this wave itself adds a test/tool file that needs a cap bump, bump CAP_TEST_FILES / CAP_TOOL_SCRIPTS with an inline 'FOUNDER_OVERRIDE:stranded-op-growthcap-union-fix-2026-06-19' comment.

FORBIDDEN: NO --admin / force-merge / manual thread-resolution; NO new transactional/snapshot/rollback machinery (reuse the existing growth-cap autobump + conflict helpers); NO runtime/substrate change (mu/host/python/rcx_pi/selfhost, mu/host/js/core, mu/closures, mu/substrate); NO seed registration. Additive pipeline-control fix + its unit test.

## Scope

Pipeline-control fix: edit mu/tools/executors/commit_executor.py (bring-current growth-cap conflict resolution in land_stranded_pr / its helper -> cover actual merged count via the existing growth-cap autobump or base+union-of-increments, not max-of-totals) + update/add tests in mu/tests/tools/test_land_stranded_pr.py. Includes TASKS.md tracker-sync authority for this wave. No runtime/substrate change.

Files and surfaces in scope:

- TASKS.md -- tracker-sync authority. The 2026-06-19 tracker sync note for wave `stranded-op-growthcap-union-fix-2026-06-19` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Correct the bring-current growth-cap conflict resolution so each resolved `CAP_*` COVERS the actual merged file count, not `max(head, origin)`. The bug is the `cap_value[name] = max(cap_value[name], value)` rule in `_merge_growth_cap_block`, reached via `_resolve_growth_caps_conflict` -> `_try_auto_resolve_pr_conflict` -> `land_stranded_pr` bring-current. PREFER reusing the existing `_maybe_autobump_growth_cap_for_founder_override` helper (it already mutates + stages `test_growth_caps.py` and is FOUNDER_OVERRIDE-aware) post-merge to bump each cap to cover the merged tree; OR compute `base + count(union of the '+N for <file>' increment-comment lines, deduped by filename)`. KEEP the existing UNION of inline increment-comment annotations. Do NOT take max-of-totals. Fail closed (raise + surface) if the cap still cannot be made to cover the merged count.
2. Preserve the two-layer fail-closed gate inside `_resolve_growth_caps_conflict` / `_try_auto_resolve_pr_conflict`: the filename-subset gate AND the per-block "CAP_* / comment / blank only" content guard must still abort (return `False` WITHOUT modifying the file) on any non-mechanical, malformed, nested, or dangling-marker conflict block.
3. Update the existing growth-cap-conflict test in `mu/tests/tools/test_land_stranded_pr.py` from the old max-of-totals expectation to the corrected base+union behavior.
4. Add a regression test in the same file proving that a merge where BOTH sides add a distinct test file (and a distinct tool script) resolves each `CAP_*` to base+union (covering the merged count), so the resulting bring-current commit PASSES the `pre-commit-doc-check` growth-cap gate -- the max-of-totals path would instead fail it (the confirmed `assert 336 <= 335` from landing #1107). FAST + hermetic only (temp git repos, mocked gh/merge, no network); mark NOTHING slow.
5. If THIS wave's own added test/tool file pushes the repo past a cap, bump `CAP_TEST_FILES` / `CAP_TOOL_SCRIPTS` in `mu/tests/docs/test_growth_caps.py` with an inline `# FOUNDER_OVERRIDE:stranded-op-growthcap-union-fix-2026-06-19` annotation.

## Constraints

Out of scope -- NOT to be touched or added:

- NO runtime/substrate change: `mu/host/python/rcx_pi/selfhost`, `mu/host/js/core`, `mu/closures`, `mu/substrate` stay untouched (L4_ENABLER MUST NOT touch runtime dirs).
- NO `--admin` / force-merge / manual PR-thread resolution.
- NO new transactional / snapshot / rollback machinery -- reuse the existing growth-cap autobump (`_maybe_autobump_growth_cap_for_founder_override`) and conflict helpers (`_merge_growth_cap_block`, `_resolve_growth_caps_conflict`).
- NO seed registration.
- NO new host capability / host-semantics delta (the ratchet must stay flat).
- NO marking any new or updated test `slow`.
- Surfaces limited to `mu/tools/executors/commit_executor.py` (conflict-resolution fix) + `mu/tests/tools/test_land_stranded_pr.py` (test update/add), plus the TASKS.md tracker-sync note and -- only if this wave's own files trip a cap -- `mu/tests/docs/test_growth_caps.py`.

## Stop conditions

- STOP and surface to the founder if covering the merged file count cannot be achieved without taking max-of-totals OR without adding new rollback/snapshot machinery (both forbidden).
- STOP if the fix would require editing any runtime/substrate file -- that is out of scope and a founder decision.
- STOP if the regression cannot be made FAST + hermetic (no network, mocked gh/merge); do NOT mark it `slow` to get around the speed gate.
- STOP (do NOT commit) if the evidence_command fails after the fix, or if `check_host_semantics_ratchet.py` reports any host-semantics delta.
- Preserve existing fail-closed behavior: if a real (non-mechanical) `test_growth_caps.py` conflict appears, the resolver must still abort the merge rather than guess.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_land_stranded_pr.py`

## Acceptance criteria

- `land_stranded_pr` bring-current resolves the `mu/tests/docs/test_growth_caps.py` conflict to a `CAP_*` value that COVERS the actual merged file count (base + union of both sides' added files), not `max(totals)`, so a stranded PR that adds a file the base lacks no longer fails the growth-cap gate at the bring-current commit.
- Regression test passes: a both-sides-add-distinct-files merge resolves each `CAP_*` to base+union -> the bring-current commit PASSES the `pre-commit-doc-check` growth-cap gate. The same scenario under the old max-of-totals logic would fail it (the confirmed `336 > 335` from landing #1107, where `max(143,145)=145` dropped #1107's pager test file).
- The updated existing growth-cap-conflict test and the new regression both pass; the UNION of inline increment-comment annotations is preserved and is no longer inconsistent with the resolved cap value.
- The two-layer fail-closed gate is intact: a non-mechanical / malformed / nested / dangling-marker conflict block still returns `False` and aborts the merge WITHOUT modifying the file.
- evidence_command passes: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_land_stranded_pr.py --tb=short && python3 mu/tools/checks/check_host_semantics_ratchet.py`.
- No host-semantics delta (ratchet flat / `net_host_delta` 0); no runtime/substrate file changed; no test marked `slow`.
- #1107 (the confirmed repro) becomes landable via the op.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `stranded-op-growthcap-union-fix-2026-06-19`.
- Governing packet: this file, `reports/control_plane/stranded-op-growthcap-union-fix-2026-06-19_2026-06-19.md`.
- TASKS.md authority: the 2026-06-19 tracker sync note for wave `stranded-op-growthcap-union-fix-2026-06-19` is canonical for this packet's L4 fields.
- Authorization: Pipeline-hardening fix for a confirmed first-use bug in the founder-chosen stranded-PR-landing op; standing pipeline-hardening authorization per feedback_manual_then_structural_autonomy + CLAUDE.md rule_13 (always harden the pipeline when it breaks).

FOUNDER_OVERRIDE:stranded-op-growthcap-union-fix-2026-06-19

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `stranded-op-growthcap-union-fix-2026-06-19`
- Active packet: `reports/control_plane/stranded-op-growthcap-union-fix-2026-06-19_2026-06-19.md`
- Indicator artifact: `reports/l4_wave_indicators/stranded-op-growthcap-union-fix-2026-06-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_land_stranded_pr.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/stranded-op-growthcap-union-fix-2026-06-19_2026-06-19.md`
  - `reports/l4_wave_indicators/stranded-op-growthcap-union-fix-2026-06-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/stranded-op-growthcap-union-fix-2026-06-19.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id stranded-op-growthcap-union-fix-2026-06-19 --output reports/l4_wave_indicators/stranded-op-growthcap-union-fix-2026-06-19.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_land_stranded_pr.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/stranded-op-growthcap-union-fix-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: stranded-op-growthcap-union-fix-2026-06-19.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `stranded-op-growthcap-union-fix-2026-06-19`
- Active packet: `reports/control_plane/stranded-op-growthcap-union-fix-2026-06-19_2026-06-19.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c3f3aa3e6c64413bfb5e31b562852abc4b5dc326c1f48fe45975703128c6441c`
- Indicator artifact: `reports/l4_wave_indicators/stranded-op-growthcap-union-fix-2026-06-19.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_land_stranded_pr.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/stranded-op-growthcap-union-fix-2026-06-19_2026-06-19.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/stranded-op-growthcap-union-fix-2026-06-19.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_land_stranded_pr.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/stranded-op-growthcap-union-fix-2026-06-19_2026-06-19.md`
  - `reports/l4_wave_indicators/stranded-op-growthcap-union-fix-2026-06-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
