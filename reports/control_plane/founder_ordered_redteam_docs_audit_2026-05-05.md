# Founder Ordered Redteam Docs Audit

Date: 2026-05-05
Status: QUEUED (packet/tracker seed only; audit not started)
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
