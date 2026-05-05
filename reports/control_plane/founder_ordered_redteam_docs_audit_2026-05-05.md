# Founder Ordered Redteam Docs Audit

Date: 2026-05-05
Status: COMPLETED (commit-ready, pre-commit supervisor pending)
Task: [NEXT-CODEX-POST-REDTEAM]
Parent directive: [FOUNDER-ORDERED-REDTEAM-WAVE-QUEUE]
Wave ID: founder-ordered-redteam-docs-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-docs-audit-2026-05-05

## Purpose

Run the second founder-ordered red-team audit wave for every discovered
repo-local `.md` document after the repo-code audit wave completes. This packet
authorizes audit and finding classification only; it does not authorize
remediation implementation.

## Scope

Audit targets:

- Every repo-local `.md` document discovered by the audit wave's file inventory
  at execution time.
- Active docs, indexes, manifests, report packets, deferred finding packets,
  roadmap docs, and markdown under `mu/docs/`.
- Archived markdown only as historical evidence; findings must distinguish
  active doc drift from historical archive content.

Output lanes:

- `reports/deferred/blocking/` for blocking findings.
- `reports/deferred/non_blocking/` for non-blocking findings.
- `TASKS.md` for the tracker status produced by the audit wave.

- `reports/deferred/non_blocking/founder-ordered-redteam-docs-audit-2026-05-05_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. Discover repo-local `.md` files at audit time without editing them.
2. Red-team active docs for stale current-state claims, stale tracker links,
   missing report placement, and proof-class mismatch.
3. Red-team report packets and deferred finding packets for stale active lane
   status, unresolved blocker truth, and references to already-landed work.
4. Red-team markdown under `mu/docs/` for current L4, Stage0, parity, or
   production claims that conflict with code truth.
5. Classify every finding as blocking or non-blocking with direct file:line or
   command evidence.
6. Write finding packets to the correct deferred lane and update the matching
   `TASKS.md` tracker status.

## Constraints

- Do not implement docs fixes in this audit wave.
- Do not relist the already landed engine-state/scheduler seed, fixture,
  structural-test, or scheduler-parity work as unresolved.
- Do not treat archive content as live drift unless an active surface points to
  it as current truth.
- Do not modify Claude-related files.
- Do not run or implement repo-code, tests, or tooling red-team waves from this
  packet except where a narrow evidence read is required to classify a docs
  finding.

## Remediation Ordering Rule

After all four founder-ordered audit waves classify findings, remediation waves
must be organized by category (`/mu`, docs, tests, tooling) and severity, with
blocking remediation before non-blocking remediation.

Any `/mu` structural blocking or non-blocking remediation wave must be ordered
last. The pipeline must hard stop before implementing any `/mu` structural
remediation wave.

## Stop Conditions

Stop after docs findings are classified and routed. Do not implement
remediation.

Stop if the audit requires Claude-related file edits.

Stop before any `/mu` structural remediation implementation, regardless of
whether the finding is blocking or non-blocking.

Stop if dispatcher/pipeline execution cannot continue without a manual
unblocker. Any unblocker must be paired with a same-wave mechanical pipeline fix
or a precise follow-up automation packet before normal execution resumes.

## Acceptance Criteria

- The docs audit discovers and reviews every repo-local `.md` file at audit
  execution time.
- Every finding is classified as blocking or non-blocking.
- Blocking and non-blocking findings are routed to the corresponding deferred
  lanes with evidence.
- The tracker status in `TASKS.md` records the packet path, wave id, class, and
  founder override.
- No audit remediation, downstream implementation edit, or Claude-related file
  edit is performed by this audit wave.
- Already landed engine-state/scheduler seed, fixture, structural-test, and
  scheduler-parity work is not relisted as unresolved.

## Grounding / Authorization

- Parent task: `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]`.
- Parent packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- Seed packet: `reports/control_plane/founder_ordered_redteam_wave_packet_seed_2026_05_0_2026-05-05.md`.
- Parent directive token:
  `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- Wave-bound authorization:
  `FOUNDER_OVERRIDE:founder-ordered-redteam-docs-audit-2026-05-05`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-docs-audit-2026-05-05`
- Active packet: `reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-docs-audit-2026-05-05.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md`
  - `reports/deferred/blocking/founder_ordered_redteam_docs_audit_2026-05-05_blocking.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-docs-audit-2026-05-05_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-docs-audit-2026-05-05.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `founder-ordered-redteam-docs-audit-2026-05-05`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/founder-ordered-redteam-docs-audit-2026-05-05_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-docs-audit-2026-05-05`
- Active packet: `reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `74e3280e2ddfe16adffeeddc4f05cb1afe827eced07fc314418126d93941ba58`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-docs-audit-2026-05-05.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id founder-ordered-redteam-docs-audit-2026-05-05 --output reports/l4_wave_indicators/founder-ordered-redteam-docs-audit-2026-05-05.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md. (2) Commit handoff carries 6 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-docs-audit-2026-05-05.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md`
  - `reports/deferred/blocking/founder_ordered_redteam_docs_audit_2026-05-05_blocking.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-docs-audit-2026-05-05_bridge_nonblockers.md`
  - `reports/deferred/non_blocking/founder_ordered_redteam_docs_audit_2026-05-05_non_blocking.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-docs-audit-2026-05-05.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
