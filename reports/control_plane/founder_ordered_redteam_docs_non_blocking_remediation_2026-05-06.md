# Founder Ordered Redteam Docs Non-Blocking Remediation

Date: 2026-05-06
Status: QUEUED - NON-BLOCKING REMEDIATION PACKET
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-docs-non-blocking-remediation-2026-05-06
Class: L4_ENABLER
Category: docs
Severity: NON-BLOCKING
Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`
Queue order: non-`/mu` non-blocking remediation, after non-`/mu` blockers and before `/mu` structural remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the docs/report drift follow-up from the founder ordered
redteam audit output. It does not implement remediation.

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

## Remediation Scope For Future Wave

- Reconcile the six DOC_ACCURACY drift findings against current source truth.
- Update only the minimum canonical docs/report surfaces needed to remove stale
  current-state or active-lane ambiguity.
- Preserve the audit classification: these are non-blocking doc/report accuracy
  findings, not runtime or test failures.

## Stop Conditions

- Stop if any listed doc/report candidate is already current by code or tracker
  truth; update the tracker instead of relisting stale work.
- Stop if a candidate requires implementation, test, runtime, tooling, or `/mu`
  structural changes rather than doc/report truth sync.
- Stop if remediation would require edits outside the documented doc/report
  surfaces and matching tracker/control-plane updates.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- The six DOC_ACCURACY findings are either corrected in their canonical surfaces
  or explicitly closed as already current with evidence.
- Current-state claims distinguish active truth from historical/archive
  evidence.
- Seed/projection count text does not relist already landed
  engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or
  seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Tracker Update Note

Add or update the `[FOUNDER-ORDERED-REDTEAM-DOCS-NON-BLOCKING-REMEDIATION]`
entry under `[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID,
category `docs`, severity `non-blocking`, source audit packet path, and the
acceptance evidence once implemented.
