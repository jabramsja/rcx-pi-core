# N3 Pipeline Continuation Scope Isolation Root Fix

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15
Class: L4_ENABLER
Category: pipeline hardening for /mu structural host-debt reduction
Target gate: G8
Phase-A-Lock: LOCKED

FOUNDER_OVERRIDE:n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15

## Grounding / Authorization

- Governing Packet: `reports/control_plane/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.md`.
- TASKS.md tracker authorization: `TASKS.md:348` carries the
  `[NEXT-CODEX-POST-REDTEAM]` tracker sync note for
  `n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15`, binds the
  packet path, marks `Status: ROUTED - PHASE A AUTHORIZED`, classifies the wave
  as `L4_ENABLER`, and sets `target_gate_id: G8`.
- Tracker sync note reference: `TASKS.md:348` records the same-wave evidence
  command, evidence delta, primary blocker class, invariant id, indicator
  artifact reference, and indicator collection command for this wave.
- Authorization: wave-bound
  `FOUNDER_OVERRIDE:n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15`.

## Purpose

Mechanize the executor/recovery fixes required by the N3 `rcx_load` lock wave
before continuing into the implementation wave. This wave does not reduce core
host semantics directly; it removes pipeline debt that forced manual staging,
manual dirty-work isolation, and dropped-stash recovery while `/mu` structural
implementation candidates were present in the same worktree.

## Scope

This wave may stage exactly these files:

- `TASKS.md`
- `reports/control_plane/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.md`
- `reports/deferred/non_blocking/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15_bridge_nonblockers.md`
- `reports/l4_wave_indicators/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.json`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/executors/phase_a_executor.py`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tools/executors/recovery_gate.py`
- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
- `mu/tests/tools/test_executor_dispatch.py`
- `mu/tests/tools/test_phase_b_executor.py`
- `mu/tests/tools/test_recovery_gate.py`

## Work Items

Concrete bounded tasks authorized by the current `[NEXT-CODEX-POST-REDTEAM]`
tracker phase in `TASKS.md:348`:

- Make Phase A bridge decision extraction accept completed `round-N`
  raw-envelope aliases while preserving stale-turn rejection.
- Make Phase B parse exact-stage packet scope and remove stale out-of-scope
  staged files before a control-plane lock package reaches commit handoff.
- Make commit supervisor review identify dirty files outside the current
  commit package as fenced files rather than treating them as package members.
- Isolate dirty out-of-scope work around Step 11 pre-push and restore it after
  pre-push completes.
- Restrict post-merge cleanup to executor-owned `phase_b:` branch-switch stash
  markers, preserving manual or commit-executor isolation stashes that merely
  mention the wave id.
- Allow stable `.scratch` symlinks whose targets stay inside `.scratch` while
  preserving escape rejection.

## Constraints

Out of scope:

- Runtime, substrate, seed, loader, ABI-doc, parity, projection, registry,
  checksum, and migration semantics.
- Any change that makes Python or JavaScript host code smarter as a semantic
  authority layer.
- Any ratchet-baseline update.
- Any Claude-related file.
- Any claim that N3 host-debt reduction is complete.

The current dirty seed-loader implementation candidate files are intentionally
outside this wave and must remain for the successor
`n3-rcx-load-seed-image-boundary-adapter-implementation` wave.

## Verified Breakage This Wave Repairs

- Phase B previously allowed stale staged runtime files into a control-plane
  `L4_ENABLER` lock package until the staged L4 verifier rejected runtime file
  scope. The repair adds exact-stage scope parsing and unstaging for packet
  sections that say the wave may stage exactly listed files.
- Phase A bridge decision extraction rejected a valid completed reviewer raw
  envelope whose raw `turn_id` was `round-1` while the rendered turn id used
  the `--r1-` form. The repair accepts the exact round alias while retaining
  stale-turn rejection.
- Recovery hybrid scratch baselining rejected stable pytest current symlinks
  under `.scratch` even when the symlink target stayed inside `.scratch`. The
  repair allows stable in-scratch symlinks and still rejects escapes.
- Commit supervisor review did not fence unrelated dirty files from the
  commit-bound package. The repair sends `fenced_files` for dirty paths outside
  the current commit package.
- Commit continuation reached local commit `762f6bcb75afac046d70e82074f92111a8fc5010`
  and then `pre-push-fast` scanned dirty out-of-scope implementation work,
  failing on `mu/host/python/rcx_pi/selfhost/seed_integrity.py` line 654. The
  repair stashes/restores dirty out-of-scope work around Step 11 pre-push.
- Commit executor restart on the already-created target branch still ran the
  local/remote branch-collision probe before recognizing that it was already on
  the handoff target. A timed-out `git ls-remote --heads origin <target>` then
  failed Step 2 before any commit work could continue. The repair skips the
  branch-collision probe when `HEAD` is already on the target branch.
- Post-merge cleanup reported `stashes_dropped: 1` for PR #963 and removed the
  manual temporary isolation stash because the old cleanup predicate dropped
  any stash whose description mentioned the wave id. The repair drops only
  executor-owned `phase_b:` branch-switch stash markers and preserves manual
  or commit-executor isolation stashes.

## Required Evidence

Focused local evidence before routing:

```bash
python3 -m py_compile mu/tools/executors/commit_executor.py mu/tools/executors/phase_a_executor.py mu/tools/executors/phase_b_executor.py mu/tools/executors/recovery_gate.py
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py -k 'pre_push_dirty_isolation or fences_unstaged_out_of_scope_dirty_files or commit_packet_truth_refresh_rebinds_packet_and_handoff_before_supervisor' --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_post_merge_cleanup.py -k 'matching_stashes or manual_wave_named_stash or no_matching_stashes or empty_wave_id' --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_executor_dispatch.py -k 'extract_bridge_decision_accepts_completed_round_alias_after_stale or extract_bridge_decision_ignores_stale_turn_before_completed_go or already_on_target_skips_collision_probe_timeout' --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py -k 'exact_stage_scope or BridgeFixScopeReconciliation or checkout_state_fence_excludes_dirty_baseline_from_wave_scope' --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_recovery_gate.py -k 'preexisting_scratch_symlink' --tb=short
```

Phase B and commit executor must still collect the same-wave L4 indicator and
run the normal pre-commit/pre-push pipeline.

## Stop Conditions

- Stop if any runtime, substrate, seed-loader, ABI-doc, or parity implementation
  file is staged in this wave.
- Stop if exact-stage scope cannot keep this wave's commit-bound package limited
  to the files listed above.
- Stop if pre-push dirty isolation cannot restore the worktree after pre-push.
- Stop if stash cleanup would still drop non-`phase_b:` operator or
  commit-executor isolation stashes that merely mention the wave id.
- Stop if the repair requires bypassing pre-push, CI, bot review, or merge
  cleanup.

## Acceptance Criteria

- The routed package is an `L4_ENABLER` control-surface repair, not a runtime
  implementation.
- Focused tests prove the exact failures above.
- The pipeline can push and merge this wave while dirty seed-loader
  implementation candidates remain outside the commit package.
- After merge, the successor implementation wave can proceed without a manual
  pre-push stash and without losing out-of-scope work.

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15`
- Active packet: `reports/control_plane/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.md`
  - `reports/l4_wave_indicators/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15`
- Active packet: `reports/control_plane/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `6581fe865b062e14c019dbbc90a2ff5e2acf2cac45ace064ef0ca8f55e18c7fe`
- Indicator artifact: `reports/l4_wave_indicators/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py mu/tests/tools/test_commit_executor_receipt.py mu/tests/tools/test_executor_dispatch.py mu/tests/tools/test_phase_b_executor.py mu/tests/tools/test_recovery_gate.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.md. (2) Final pytest gate covered 5 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_a_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.md`
  - `reports/l4_wave_indicators/n3-pipeline-continuation-scope-isolation-root-fix-2026-05-15.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
