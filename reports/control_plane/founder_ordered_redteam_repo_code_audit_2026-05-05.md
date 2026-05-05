# Founder Ordered Redteam Repo Code Audit

Date: 2026-05-05
Status: QUEUED (packet/tracker seed only; audit not started)
Task: [NEXT-CODEX-POST-REDTEAM]
Parent directive: [FOUNDER-ORDERED-REDTEAM-WAVE-QUEUE]
Wave ID: founder-ordered-redteam-repo-code-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-repo-code-audit-2026-05-05

## Purpose

Run the first founder-ordered red-team audit wave for repo code after the
packet/tracker seed wave completes. This packet authorizes audit and finding
classification only; it does not authorize remediation implementation.

## Scope

Audit targets:

- Python/JavaScript substrate sync surfaces under `mu/host/python/` and
  `mu/host/js/`.
- Stage0, lowering, runtime, and execution-boundary paths under `mu/`.
- Structural `/mu` seed, registry, bridge, program, projection, and runtime
  wiring that carries current production, parity, Stage0, or L4 claims.
- Direct evidence surfaces needed to classify repo-code findings, including
  targeted tests, docs, and tooling only when they are required to prove or
  disprove a code claim.

Output lanes:

- `reports/deferred/blocking/` for blocking findings.
- `reports/deferred/non_blocking/` for non-blocking findings.
- `TASKS.md` for the tracker status produced by the audit wave.

## Work Items

1. Inventory repo-code targets in the scope above without implementing changes.
2. Red-team Python/JS substrate sync for parity, host-authority drift, and
   proof-class mismatch.
3. Red-team `/mu` Stage0, lowering, runtime, and execution-boundary paths for
   structural gaps, hidden host semantics, and fail-open behavior.
4. Red-team other structural `/mu` code surfaces for current-state claims that
   are not backed by executable proof.
5. Classify every finding as blocking or non-blocking with direct file:line or
   command evidence.
6. Write finding packets to the correct deferred lane and update the matching
   `TASKS.md` tracker status.

## Constraints

- Do not implement repo-code fixes in this audit wave.
- Do not relist the already landed engine-state/scheduler seed, fixture,
  structural-test, or scheduler-parity work as unresolved.
- Do not treat old control-surface packets as current code truth when live code
  proves a slice has already landed.
- Do not modify Claude-related files.
- Do not run or implement docs, tests, or tooling red-team waves from this
  packet except where a narrow evidence read is required to classify a
  repo-code finding.

## Remediation Ordering Rule

After all four founder-ordered audit waves classify findings, remediation waves
must be organized by category (`/mu`, docs, tests, tooling) and severity, with
blocking remediation before non-blocking remediation.

Any `/mu` structural blocking or non-blocking remediation wave must be ordered
last. The pipeline must hard stop before implementing any `/mu` structural
remediation wave.

## Stop Conditions

Stop after repo-code findings are classified and routed. Do not implement
remediation.

Stop if the audit requires Claude-related file edits.

Stop before any `/mu` structural remediation implementation, regardless of
whether the finding is blocking or non-blocking.

Stop if dispatcher/pipeline execution cannot continue without a manual
unblocker. Any unblocker must be paired with a same-wave mechanical pipeline fix
or a precise follow-up automation packet before normal execution resumes.

## Acceptance Criteria

- The repo-code audit targets Python/JS substrate sync, `/mu` Stage0, and other
  structural `/mu` surfaces.
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
  `FOUNDER_OVERRIDE:founder-ordered-redteam-repo-code-audit-2026-05-05`.
