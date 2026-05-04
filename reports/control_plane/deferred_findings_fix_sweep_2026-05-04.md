# Deferred Findings Fix Sweep

Date: 2026-05-04
Status: ACTIVE (ready for Phase B dispatch)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-findings-fix-sweep-2026-05-04
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Target gate: G8
FOUNDER_OVERRIDE:deferred-findings-fix-sweep-2026-05-04

## Purpose

Fix or explicitly route the blocker and non-blocker findings that remain in the
report surfaces before any production-forward runtime work continues.

This packet is the immediate pre-production cleanup gate before the full `/mu`
runtime red-team packet.

## Scope

Required inventory surfaces:

- `reports/deferred/blocking/`
- `reports/deferred/non_blocking/`
- `reports/l4_wave_indicators/`
- `reports/control_plane/`
- `TASKS.md`

Allowed write surfaces:

- the report surfaces above
- existing archive/resolved destinations for stale or closed findings:
  `reports/deferred/archive/`, `reports/deferred/resolved/`,
  `reports/control_plane/archive/`, and `reports/archive/deferred/`
- `TASKS.md`
- code, test, tooling, or doc files named by an active finding, only when the
  fix is bounded and directly resolves that finding

If a finding requires broad runtime, substrate, seed, parity, or production
semantics work, split it into the `/mu` red-team packet or a narrower structural
implementation packet instead of hiding it in this cleanup wave.

## Work Items

1. Inventory blocker and non-blocker findings in the required surfaces.
2. Classify every finding against current code, tests, or direct command output
   as fixed-by-code, stale/historical, active blocker, active non-blocker, or
   needs split authorization.
3. Fix active blockers first when the code/test/doc surface is bounded and named
   by the finding.
4. Fix non-blockers when the repair is bounded; otherwise leave them in
   `reports/deferred/non_blocking/` with concrete evidence and a next packet.
5. Move stale or closed findings out of active folders after code-truth
   verification, using the existing archive/resolved destination that matches the
   source lane.
6. Update report indexes, TASKS, and packet truth so closed parent lanes do not
   get reopened by stale generated advisory text.
7. If manual intervention is needed for pipeline/recovery/builder behavior,
   mechanize the repair in this wave when bounded or add an explicit follow-up
   packet with file:line or command evidence.

## Constraints

- Do not mark a finding closed from report prose alone; use current code, tests,
  or direct command evidence.
- Do not leave stale or code-closed findings in active blocking/non-blocking
  folders after they have been proven closed; archive or resolve them.
- Do not move a blocker into non-blocking just to clear the blocking lane.
- Do not widen this wave into a full `/mu` runtime red-team; that is owned by
  `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`.
- Do not move production forward while active blockers remain unresolved.

## Stop Conditions

Stop and split the work if:

1. A finding requires broad runtime or parity semantics beyond a bounded repair.
2. A blocker cannot be reproduced or dismissed with direct file:line or command
   evidence.
3. The correct fix needs a builder/recovery mechanism not yet represented by a
   bounded work item.
4. The wave would need to edit outside the allowed surfaces without a finding
   naming that file.

## Acceptance Criteria

- `reports/deferred/blocking/` contains only active blockers with current
  evidence, or only its README when no active blockers remain.
- `reports/deferred/non_blocking/` contains only active advisories or follow-ups
  with concrete evidence; stale or code-closed items have been moved to an
  archive/resolved destination.
- Blocker/non-blocker references in `reports/l4_wave_indicators/` and
  `reports/control_plane/` are either fixed, routed, or moved/marked historical
  with code-truth evidence.
- `TASKS.md` points to the next required packet after this sweep.
- Validation includes `git diff --check`, docs consistency, stale NEXT checks,
  and an L4 execution-contract check for the changed files.

## Follow-On

After this packet lands, run `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`
before any production-forward movement.
