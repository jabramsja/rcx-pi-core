# Founder Ordered Redteam Tests Audit

Date: 2026-05-05
Status: QUEUED (packet/tracker seed only; audit not started)
Task: [NEXT-CODEX-POST-REDTEAM]
Parent directive: [FOUNDER-ORDERED-REDTEAM-WAVE-QUEUE]
Wave ID: founder-ordered-redteam-tests-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tests-audit-2026-05-05

## Purpose

Run the third founder-ordered red-team audit wave for tests after the docs audit
wave completes. This packet authorizes audit and finding classification only;
it does not authorize remediation implementation.

## Scope

Audit targets:

- `tests/` and `mu/tests/`.
- Repo-local test files outside those directories when discovered by test-file
  inventory at audit time.
- Test helper and fixture surfaces needed to prove whether a test claim is
  behavioral, source-lock-only, stale, or theater.

Output lanes:

- `reports/deferred/blocking/` for blocking findings.
- `reports/deferred/non_blocking/` for non-blocking findings.
- `TASKS.md` for the tracker status produced by the audit wave.

## Work Items

1. Inventory repo-local test files and fixtures without implementing changes.
2. Red-team tests for proof-class mismatch, source-lock-only assertions,
   private-helper coupling, skipped live paths, stale fixtures, and theater.
3. Red-team parity, L4, Stage0, docs, executor, and tooling tests for claims
   that can pass without exercising the live invariant.
4. Confirm that tests do not relist already-landed engine-state/scheduler
   work as pending work.
5. Classify every finding as blocking or non-blocking with direct file:line or
   command evidence.
6. Write finding packets to the correct deferred lane and update the matching
   `TASKS.md` tracker status.

## Constraints

- Do not implement test fixes in this audit wave.
- Do not relist the already landed engine-state/scheduler seed, fixture,
  structural-test, or scheduler-parity work as unresolved.
- Do not modify Claude-related files.
- Do not run or implement repo-code, docs, or tooling red-team waves from this
  packet except where a narrow evidence read is required to classify a tests
  finding.

## Remediation Ordering Rule

After all four founder-ordered audit waves classify findings, remediation waves
must be organized by category (`/mu`, docs, tests, tooling) and severity, with
blocking remediation before non-blocking remediation.

Any `/mu` structural blocking or non-blocking remediation wave must be ordered
last. The pipeline must hard stop before implementing any `/mu` structural
remediation wave.

## Stop Conditions

Stop after tests findings are classified and routed. Do not implement
remediation.

Stop if the audit requires Claude-related file edits.

Stop before any `/mu` structural remediation implementation, regardless of
whether the finding is blocking or non-blocking.

Stop if dispatcher/pipeline execution cannot continue without a manual
unblocker. Any unblocker must be paired with a same-wave mechanical pipeline fix
or a precise follow-up automation packet before normal execution resumes.

## Acceptance Criteria

- The tests audit reviews repo-local test and fixture surfaces discovered at
  audit execution time.
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
  `FOUNDER_OVERRIDE:founder-ordered-redteam-tests-audit-2026-05-05`.
