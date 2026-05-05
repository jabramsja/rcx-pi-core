# Founder Ordered Redteam Tooling Audit

Date: 2026-05-05
Status: QUEUED (packet/tracker seed only; audit not started)
Task: [NEXT-CODEX-POST-REDTEAM]
Parent directive: [FOUNDER-ORDERED-REDTEAM-WAVE-QUEUE]
Wave ID: founder-ordered-redteam-tooling-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-audit-2026-05-05

## Purpose

Run the fourth founder-ordered red-team audit wave for tooling after the tests
audit wave completes. This packet authorizes audit and finding classification
only; it does not authorize remediation implementation.

## Scope

Audit targets:

- `tools/`, `scripts/`, and root developer/audit command surfaces.
- `mu/tools/` executors, checks, agents, hooks, observability, metrics,
  compilers, and pipeline tooling.
- CI and automation configuration that governs validation, routing, or
  production-readiness checks.
- Test and docs evidence only where needed to prove or disprove a tooling
  claim.

Output lanes:

- `reports/deferred/blocking/` for blocking findings.
- `reports/deferred/non_blocking/` for non-blocking findings.
- `TASKS.md` for the tracker status produced by the audit wave.

## Work Items

1. Inventory repo-local tooling and automation surfaces without implementing
   changes.
2. Red-team dispatcher, builder, recovery, commit, pre-commit, observability,
   and check tooling for fail-open paths, stale package truth, and manual
   workaround residue.
3. Red-team validation and CI tooling for proof-class mismatch, theater, and
   stale current-state claims.
4. Confirm tooling does not relist already-landed engine-state/scheduler work
   as pending work.
5. Classify every finding as blocking or non-blocking with direct file:line or
   command evidence.
6. Write finding packets to the correct deferred lane and update the matching
   `TASKS.md` tracker status.

## Constraints

- Do not implement tooling fixes in this audit wave.
- Do not relist the already landed engine-state/scheduler seed, fixture,
  structural-test, or scheduler-parity work as unresolved.
- Do not modify Claude-related files.
- Do not run or implement repo-code, docs, or tests red-team waves from this
  packet except where a narrow evidence read is required to classify a tooling
  finding.

## Remediation Ordering Rule

After all four founder-ordered audit waves classify findings, remediation waves
must be organized by category (`/mu`, docs, tests, tooling) and severity, with
blocking remediation before non-blocking remediation.

Any `/mu` structural blocking or non-blocking remediation wave must be ordered
last. The pipeline must hard stop before implementing any `/mu` structural
remediation wave.

## Stop Conditions

Stop after tooling findings are classified and routed. Do not implement
remediation.

Stop if the audit requires Claude-related file edits.

Stop before any `/mu` structural remediation implementation, regardless of
whether the finding is blocking or non-blocking.

Stop if dispatcher/pipeline execution cannot continue without a manual
unblocker. Any unblocker must be paired with a same-wave mechanical pipeline fix
or a precise follow-up automation packet before normal execution resumes.

## Acceptance Criteria

- The tooling audit reviews repo-local tooling and automation surfaces
  discovered at audit execution time.
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
  `FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-audit-2026-05-05`.
