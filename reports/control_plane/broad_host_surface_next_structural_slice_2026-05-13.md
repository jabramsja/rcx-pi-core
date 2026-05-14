# Broad Host-Surface Next Structural Slice

Date: 2026-05-13
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: broad-host-surface-next-structural-slice-2026-05-13
Class: L4_ENABLER
Category: /mu structural host-surface reduction
Phase-A-Lock: LOCKED
Parent waves:
- broad-host-surface-reduction-boundary-2026-05-13
- broad-host-surface-next-boundary-slice-2026-05-13
FOUNDER_OVERRIDE:broad-host-surface-next-structural-slice-2026-05-13

## Scope

This packet routes the still-active N3 broad host-surface deferred non-blocker
after PR #944, PR #945, and PR #946. The previous structural slices closed
specific JS acceptance-boundary gaps, and the bridge DOC_ACCURACY closeout
removed generated residue, but the retained N3 advisory remains active:

- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
- `reports/deferred/non_blocking/README.md`
- `reports/deferred/README.md`

This packet authorizes only a dispatcher-first Phase A selection pass followed
by Phase B implementation if Phase A locks one exact bounded source slice. It
does not authorize manual runtime implementation outside the dispatcher.
Because this initial route changes only tracker/control-plane truth, it is
classified as `L4_ENABLER`. If Phase B locks and stages runtime or substrate
changes under this same wave, Phase B must reclassify the staged package as
`L4_STRUCTURAL` and satisfy the stricter runtime/test contract.

## Grounding / Authorization

Direct active-source evidence:

- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:150`
  names N3 as "P7-d is execution-path progress, not broad host-surface
  reduction."
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:152`
  through `:164` keeps N3 as a retained architectural boundary, requires a
  separate bounded control-plane packet before implementation, and forbids
  moving more semantic authority into Python or JavaScript host code.
- `reports/deferred/non_blocking/README.md:341` through `:349` records that
  the active non-blocking lane contains only the README plus
  `repo_truth_non_blockers_2026-03-14.md`, with N3 as the only open work inside
  that packet.
- `reports/deferred/README.md:22` through `:56` records the current active
  deferred inventory and the retained N3 advisory.

Recent predecessor truth:

- PR #944 merged `broad-host-surface-reduction-boundary-2026-05-13`, which
  closed one bounded JS invalid-state acceptance slice but did not close N3.
- PR #945 merged `broad-host-surface-next-boundary-slice-2026-05-13`, which
  closed one bounded exported JS Stage0 `muCopy(..., rejectNonMu=true)` host
  trap fail-closed slice but did not close N3.
- PR #946 merged `broad-host-surface-next-bridge-doc-accuracy-closeout-2026-05-13`,
  which archived generated bridge DOC_ACCURACY residue only and did not close
  N3.

Current ratchet evidence to reproduce before Phase A selection:

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/checks/check_host_authority_inventory_ratchet.py --json
./tools/checks/check_docs_consistency.sh
```

At packet creation, host authority inventory output reports `311 total
(181 Python + 130 JS)` current sites versus `312 total (181 Python + 131 JS)`
baseline sites, `217 authority` current and baseline sites, no new total or
authority sites, and one removed non-authority total site:
`mu/host/js/api/json_handlers.js::runRecurrence`. That removed site is review
evidence only. Baseline-only cleanup is not a structural reduction and must not
be used to close N3.

## Phase A Work Items

1. Reproduce current N3 deferred status and current deferred inventory from the
   files named in Scope.
2. Reproduce predecessor closure state from PR #944, PR #945, and PR #946 so
   already-closed boundary slices are not reimplemented or relisted.
3. Re-run current host-semantics, host-authority inventory, host-authority JSON,
   and docs consistency checks.
4. Inspect current source truth and select exactly one bounded host-surface
   reduction candidate, or leave N3 active with a precise next packet if no
   honest slice exists.
5. Lock the Phase B write set, focused tests, parity proof, ratchet
   expectations, and stop conditions before implementation starts.
6. Remove any candidate from pending work if source or test truth proves it
   already landed.

## Candidate Evidence Surfaces

Phase A read scope is restricted to current source, ratchet JSON, and focused
tests around these surfaces unless direct evidence requires a smaller adjacent
read:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
- `mu/host/python/rcx_pi/selfhost/stage0_vm.py`
- `mu/host/js/engine/pipeline.js`
- `mu/host/js/core/stage0_vm.js`
- `mu/host/js/core/terminal_classification.js`
- `mu/host/js/core/types.js`
- `mu/host/js/api/json_handlers.js`
- focused tests under `mu/tests/l4_gates/`, `mu/tests/parity/`, and
  `mu/tests/structural/` that directly exercise a candidate boundary.

Phase A must choose from current behavior, not from broad wording or string
matches. The selected slice must shrink or fail-close a real host-surface
boundary without adding semantic host debt.

## Constraints

- Route through the full dispatcher pipeline:
  post-merge supervisor -> Phase A -> Phase B -> commit executor.
- Do not hand-implement runtime changes before Phase A locks a bounded route.
- Do not edit Claude-related files.
- Do not add host-only semantics or make Python/JavaScript "smarter" as the
  goal. Work in Mu where possible or narrow bootstrap/host assumptions.
- Prefer paired Python/JS surfaces when the behavior is semantically shared. If
  a single-substrate slice is selected, Phase A must prove the paired substrate
  is already strict or out of scope.
- Do not update ratchet baselines as a substitute for real reduction.
- Do not archive or close N3 unless code or explicit architecture evidence
  proves the retained broader advisory is closed.
- If manual pipeline repair is required, keep it same-wave and add a
  mechanical/automated repair in dispatcher, builder, recovery, commit,
  pre-commit, or another appropriate pipeline surface, or emit a precise
  follow-up automation packet.

## Stop Conditions

- Stop if the dispatcher selects a completed or stale wrong-wave packet.
- Stop if Phase A cannot bind a focused test or parity proof to the selected
  source boundary.
- Stop if the apparent candidate is already closed by current source and tests.
- Stop if the only available action would add host-only semantics or move
  authority into Python/JavaScript.
- Stop if implementation would require changing runtime, Stage0, seed,
  scheduler, registry, or parity surfaces outside the Phase-A-locked write set.
- Stop before commit if same-wave `TASKS.md` tracker authority is not
  detector-visible for this wave id and packet.

## Acceptance Criteria

- Phase A either locks one narrow implementation slice or leaves N3 active with
  a precise next-wave task and evidence trail.
- If Phase B is routed, implementation changes only the locked files and tests.
- Host-semantics ratchet does not increase.
- Host-authority inventory adds no total-inventory or authority-subset sites.
- Any retained or narrowed N3 status is reflected in active deferred truth
  without pretending that one bounded slice equals broad host-surface closure.

## Required Validation

Minimum Phase A validation:

```bash
git status --short --branch
find reports/deferred/blocking reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' -print | sort
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 tools/checks/check_host_authority_inventory_ratchet.py --json
./tools/checks/check_docs_consistency.sh
```

Any Phase B implementation must add focused tests for the locked source surface
and rerun the relevant parity, L4, ratchet, docs, and strict staged L4 checks.

## Same-Wave Pipeline Repair

During packet routing, the post-merge package builder correctly selected this
wave but generated a request that still said to stop if the packet required
`/mu` structural work. That stop text was correct for the earlier founder hard
stop, but it contradicts this explicitly authorized, bounded non-hard-stop
successor route.

Root-cause evidence:

- Builder source:
  `mu/tools/executors/commit_executor.py` generated the request text from
  `_post_merge_request_for_queue_entry()`.
- Generated package output:
  `.agent_bus/meta/post_merge_package.json` selected
  `broad-host-surface-next-structural-slice-2026-05-13` and
  `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`,
  but the request string ended with
  `Stop if the packet requires /mu structural work or founder input.`

Mechanical repair:

- `mu/tools/executors/commit_executor.py` now preserves the hard-stop behavior
  for entries marked hard-stop, preserves the old `/mu structural` escalation
  stop for non-`/mu` entries, and uses a bounded-scope stop clause for
  authorized non-hard-stop `/mu` structural entries.
- `mu/tests/tools/test_commit_executor_post_merge_cleanup.py` now proves an
  authorized non-hard-stop `/mu` structural queue entry is routed through the
  full dispatcher request without the self-blocking `/mu structural work` stop
  clause, while the existing hard-stop test still blocks implementation.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `broad-host-surface-next-structural-slice-2026-05-13`
- Active packet: `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-next-structural-slice-2026-05-13.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/l4_wave_indicators/broad-host-surface-next-structural-slice-2026-05-13.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `broad-host-surface-next-structural-slice-2026-05-13`
- Active packet: `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `04aaeef06201749c8796b0c9afd6fd4038c8b4a7e395e1549589eca93da9d331`
- Indicator artifact: `reports/l4_wave_indicators/broad-host-surface-next-structural-slice-2026-05-13.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/broad-host-surface-next-structural-slice-2026-05-13.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  - `reports/l4_wave_indicators/broad-host-surface-next-structural-slice-2026-05-13.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
