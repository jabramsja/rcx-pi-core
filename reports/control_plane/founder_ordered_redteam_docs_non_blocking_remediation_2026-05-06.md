# Founder Ordered Redteam Docs Non-Blocking Remediation

Date: 2026-05-06
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: docs
Severity: NON-BLOCKING
Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`
Queue order: non-`/mu` non-blocking remediation, after non-`/mu` blockers and before `/mu` structural remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06
Source authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet governs and now records the docs/report drift follow-up from the
founder ordered redteam audit output. The locked Phase A plan is preserved
below; the Phase B closeout records the bounded implementation evidence.

## Phase B Implementation Closeout

Implementation status: COMPLETE.

Changed surfaces stayed inside the bounded doc/report/tracker list. No runtime,
tooling, executor, dispatcher, fixture, test, `/mu` structural, or
Claude-related files were edited.

Finding disposition:

- N1 corrected `README.md` root current-state wording: bounded production
  reduction is described as active Stage0 VM cutover evidence while full L4
  completion remains SINK and full bootstrap-primitive elimination still needs
  separate productionization gates.
- N2 corrected the stale `TASKS.md` Post-D008 operating-mode wording so bounded
  production reduction is acknowledged without claiming full primitive
  elimination.
- N3 narrowed `CHANGELOG.md` so it is a selected historical changelog, not the
  complete live recent-landed-wave source.
- N4 corrected root/core seed-count wording against
  `tests/structural/test_seed_counts.py`: 21 registered seed files and 194
  registered projections remain the current executable registry truth, while
  governed docs avoid duplicating forbidden hardcoded projection totals where
  the doc-freshness gate requires source references.
- N5 corrected `roadmap/MANIFEST.md` by replacing the Gates 6-8 `PARKED` status
  row with canonical-source pointers to `STATUS.md` and `TASKS.md`.
- N6 corrected active-lane ambiguity by updating
  `reports/deferred/non_blocking/README.md` and the three listed resolved
  packets with explicit historical-retention / non-active-advisory markers.

Post-edit validation:

- `./tools/checks/check_docs_consistency.sh` exited 0. Result: all checks passed;
  docs are consistent. It still emitted the pre-existing freshness warning that
  `STATUS.md` was last updated on 2026-04-08.
- `python3 tools/docs/docs_sync_report.py --check` exited 0. Result:
  unclassified markdown files 0, unregistered docs subfolders 0, tracker section
  placement violations 0.
- `PYTHONHASHSEED=0 python3 -m pytest -q tests/structural/test_seed_counts.py tests/docs/test_l4_current_state_truth.py tests/docs/test_manifest_discoverability.py`
  exited 0. Result: 191 passed.
- Focused registry read exited 0 with `MU_SEEDS_total 21`,
  `EXPECTED_COUNTS_total_files 21`, and `EXPECTED_COUNTS_projection_total 194`.
- Focused JSON seed literal read exited 0 with `float_literal_count 0`.

Issue encountered and resolved:

- The first post-edit docs consistency run failed because the root README
  duplicated a hardcoded projection total that the doc-freshness gate forbids in
  governed docs. The README was corrected to point exact projection totals to
  `tests/structural/test_seed_counts.py`, and the next docs consistency run
  passed.

## Source Findings

### N1 - Root README Presents Stage0 Production Cutover As Still Future

Classification: NON-BLOCKING DOC_ACCURACY

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`:

- Lines 38-40: `README.md:16` says bounded L4 reduction landed only through
  shadow-mode cutover and that production flip still requires performance
  evidence plus founder GO.
- Lines 41-52: `STATUS.md:52`, `STATUS.md:59`, `TASKS.md:436`,
  `TASKS.md:519`, `mu/host/python/rcx_pi/selfhost/step_mu.py:1031`,
  `mu/host/js/engine/kernel.js:20`, and `mu/host/js/engine/kernel.js:24`
  record active Stage0 VM cutover / all 33 projections via Stage0 VM.
- Lines 56-62 preserve the direct evidence commands for those file ranges.

### N2 - TASKS Active L4 Tracker Contradicts Its Own Production-Reduction Truth

Classification: NON-BLOCKING DOC_ACCURACY

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`:

- Lines 81-89: `TASKS.md:519` says bounded production reduction has occurred,
  while `TASKS.md:545` still says "No production reduction claims"; `STATUS.md:52`,
  `STATUS.md:59`, `STATUS.md:132`,
  `mu/host/python/rcx_pi/selfhost/step_mu.py:1031`, and
  `mu/host/js/engine/kernel.js:20` provide direct current-state evidence.
- Lines 93-98 preserve the direct evidence commands for those file ranges.

### N3 - CHANGELOG Is No Longer A Reliable Recent-Landed-Waves Source

Classification: NON-BLOCKING DOC_ACCURACY

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`:

- Lines 116-121: `CHANGELOG.md:3` says all notable changes are documented in
  the file; `CHANGELOG.md:5` starts the newest visible section at
  `2026-04-04`; `git log --oneline --since='2026-04-04' --max-count=20`
  showed May 5 merges through PR #876 and related founder-ordered red-team
  queue work; `TASKS.md:236` through `TASKS.md:239` and `TASKS.md:419` record
  current tracker notes.
- Lines 125-129 preserve the direct evidence commands.

### N4 - Active Seed/Projection Count Claims Lag The Registered Seed Corpus

Classification: NON-BLOCKING DOC_ACCURACY

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`:

- Lines 145-157: `README.md:23`, `mu/docs/core/Boot0Architecture.v0.md:337`,
  `mu/docs/core/TypedNumericEnvelopes.v0.md:251`,
  `mu/docs/core/TypedNumericEnvelopes.v0.md:313`, and
  `tests/structural/test_seed_counts.py:26` through
  `tests/structural/test_seed_counts.py:78` disagree on seed/projection counts.
- Lines 158-160 preserve narrow AST output:
  `MU_SEEDS_total 21`, `EXPECTED_COUNTS_total_files 21`, and
  `EXPECTED_COUNTS_projection_total 194`.
- Lines 164-184 preserve the direct evidence commands and AST read.

### N5 - Roadmap Manifest Still Marks Gates 6-8 As Parked In A Status Column

Classification: NON-BLOCKING DOC_ACCURACY

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`:

- Lines 201-207: `roadmap/MANIFEST.md:45` through `roadmap/MANIFEST.md:48`
  mark gates 6-8 `PARKED`; `STATUS.md:142` through `STATUS.md:147` records
  Gate 8 as PASS, caveated; `roadmap/MANIFEST.md:56` through
  `roadmap/MANIFEST.md:60` says roadmap docs should point to canonical sources
  and should not track current state.
- Lines 211-214 preserve the direct evidence commands.

### N6 - Active Non-Blocking Lane Retains Resolved Packets Without A Clear Historical Header

Classification: NON-BLOCKING DOC_ACCURACY

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`:

- Lines 230-240: `reports/deferred/non_blocking/README.md:3` through
  `reports/deferred/non_blocking/README.md:11` describe the active advisory
  lane and historical retention; resolved packets at
  `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md:6`,
  `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md:6`,
  lines 9 through 21 of that same packet, and
  `reports/deferred/non_blocking/handoff-current-state-reconciliation-2026-05-05_bridge_nonblockers.md:6`
  retain resolved status without a clear historical header.
- Lines 244-249 preserve the direct evidence commands.

## Scope: Files And Directories In Scope

This Phase A packet rewrite may edit only this file:

- `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`

The future remediation wave is bounded to the following editable doc/report and
tracker surfaces. No directory-wide edit authority is implied beyond the listed
files:

- Repo root docs:
  - `README.md`
  - `STATUS.md`
  - `TASKS.md`
  - `CHANGELOG.md`
- Roadmap docs:
  - `roadmap/MANIFEST.md`
- Core docs:
  - `mu/docs/core/Boot0Architecture.v0.md`
  - `mu/docs/core/TypedNumericEnvelopes.v0.md`
- Deferred non-blocking report lane:
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/handoff-current-state-reconciliation-2026-05-05_bridge_nonblockers.md`
- Control-plane packet/tracker closure surfaces:
  - `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
  - `TASKS.md`

The future remediation wave may read only the following non-doc evidence paths
when needed to verify current truth, and must not edit them:

- `mu/host/python/rcx_pi/selfhost/step_mu.py`
- `mu/host/js/engine/kernel.js`
- `tests/structural/test_seed_counts.py`

## Work Items: Bounded Tasks From Current Phase

1. N1 root current-state wording: reconcile `README.md` Stage0 production
   cutover language against current `STATUS.md`, `TASKS.md`, and read-only
   runtime evidence, or close the item as already current if current file truth
   proves no stale claim remains.
2. N2 TASKS production-reduction wording: reconcile the active L4 tracker
   wording in `TASKS.md` so current production-reduction truth is not
   contradicted by stale "No production reduction claims" language, or close it
   with exact evidence if already current.
3. N3 CHANGELOG chronology: either update `CHANGELOG.md` so its current-source
   claim covers the recent landed waves or narrow its wording so it no longer
   claims to be the complete recent-landed-wave source.
4. N4 seed/projection count text: reconcile count claims in `README.md`,
   `mu/docs/core/Boot0Architecture.v0.md`, and
   `mu/docs/core/TypedNumericEnvelopes.v0.md` against the registered seed corpus
   evidence in `tests/structural/test_seed_counts.py`; do not relist already
   landed engine-state/scheduler seed, fixture, structural-test,
   scheduler-parity, or seed-registration work as unresolved.
5. N5 roadmap status wording: reconcile `roadmap/MANIFEST.md` Gates 6-8 parked
   status wording with the manifest's own canonical-source rule and current
   `STATUS.md` gate truth.
6. N6 active non-blocking lane labeling: update
   `reports/deferred/non_blocking/README.md` and only the three listed resolved
   packets as needed so active advisory entries and historical/resolved
   retention are mechanically distinguishable.
7. Tracker/control-plane closeout: update the matching
   `[FOUNDER-ORDERED-REDTEAM-DOCS-NON-BLOCKING-REMEDIATION]` entry under
   `[NEXT-CODEX-POST-REDTEAM]` with implementation status and evidence once the
   remediation wave executes.

## Constraints: Not In Scope

- No implementation, runtime, tooling, executor, dispatcher, test, fixture, or
  `/mu` structural remediation.
- No edits to `mu/host/python/rcx_pi/selfhost/step_mu.py`,
  `mu/host/js/engine/kernel.js`, or `tests/structural/test_seed_counts.py`;
  those paths are evidence-only for this docs/report wave.
- No edits outside the bounded file list above.
- No directory-wide rewrites, broad report-lane cleanup, archive migration, or
  formatting churn.
- No Claude-related file edits.
- No relisting of already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.

## Stop Conditions

- Stop if any listed doc/report candidate is already current by code, test, or
  tracker truth; record the evidence and remove that item from pending work and
  acceptance status instead of preserving stale unresolved wording.
- Stop if a candidate requires implementation, test, runtime, tooling, executor,
  dispatcher, fixture, or `/mu` structural changes rather than doc/report truth
  sync.
- Stop if remediation would require edits outside the bounded file list in this
  packet.
- Stop if any Claude-related file would need to be edited.
- Stop if current code/test truth contradicts the source audit packet; use
  current truth and record the conflict instead of carrying stale packet claims
  forward.

## Acceptance Criteria

- Each of the six DOC_ACCURACY findings is either corrected in its bounded
  canonical surface or explicitly closed as already current with exact evidence.
- Current-state claims distinguish active truth from historical/archive evidence
  in the root docs, roadmap manifest, changelog, TASKS tracker, and deferred
  non-blocking report lane.
- Seed/projection count text matches current registered seed corpus evidence
  and does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The deferred non-blocking lane clearly separates active advisory packets from
  resolved historical retained packets.
- The matching `TASKS.md` entry is updated with implementation status,
  evidence, and any items closed as already current.

## Grounding / Authorization

- Current task authorization: `TASKS.md:430` defines the organized remediation
  packet queue created by
  `founder-ordered-redteam-remediation-queue-organization-2026-05-05`.
- Current wave authorization: `TASKS.md:433` queues
  `[FOUNDER-ORDERED-REDTEAM-DOCS-NON-BLOCKING-REMEDIATION]`, wave ID
  `founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`, class
  `L4_ENABLER`, category `docs`, severity `non-blocking`, this packet path, the
  source audit packet path, and the six finding categories.
- Same-wave control-surface authorization:
  FOUNDER_OVERRIDE:founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06
- Source queue authorization:
  FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05
- Governing packet:
  `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
- Source audit packet:
  `reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `CHANGELOG.md`
  - `README.md`
  - `TASKS.md`
  - `mu/docs/core/Boot0Architecture.v0.md`
  - `mu/docs/core/TypedNumericEnvelopes.v0.md`
  - `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/handoff-current-state-reconciliation-2026-05-05_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06.json`
  - `roadmap/MANIFEST.md`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `7cd8203cc67b96ab88400661f777b9d8cd28db4852399021b4bc002416d7f228`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06 --output reports/l4_wave_indicators/founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md. (2) Commit handoff carries 12 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06.json`
- Current staged files:
  - `CHANGELOG.md`
  - `README.md`
  - `TASKS.md`
  - `mu/docs/core/Boot0Architecture.v0.md`
  - `mu/docs/core/TypedNumericEnvelopes.v0.md`
  - `reports/control_plane/founder_ordered_redteam_docs_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/README.md`
  - `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/handoff-current-state-reconciliation-2026-05-05_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06.json`
  - `roadmap/MANIFEST.md`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
