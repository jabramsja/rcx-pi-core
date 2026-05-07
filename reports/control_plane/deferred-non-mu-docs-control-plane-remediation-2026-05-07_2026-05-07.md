# Deferred-Non-Mu Docs Control-Plane Remediation 2026-05-07

Date: 2026-05-07
Status: Routed - Phase A required before implementation
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-non-mu-docs-control-plane-remediation-2026-05-07
Class: L4_ENABLER
Category: docs/control-plane
Phase-A-Lock: UNLOCKED
Source authorization: FOUNDER_OVERRIDE:deferred-non-mu-deferred-lane-truth-sweep-2026-05-07
Governing source packet: reports/control_plane/deferred-non-mu-deferred-lane-truth-sweep-2026-05-07_2026-05-07.md

## Scope

This routed packet groups non-`/mu` DOC_ACCURACY and control-plane wording
findings discovered in active deferred source packets and routed by
`deferred-non-mu-deferred-lane-truth-sweep-2026-05-07`.

In scope for a future implementation wave:

- Active docs/control-plane packet wording that overclaims, omits current
  evidence, or carries stale staged/proof phrasing.
- Deferred-source snapshots archived under `reports/archive/deferred/` with
  `closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07` suffixes.
- Root/report/control-plane docs only when directly cited by the archived source
  packets.

Out of scope:

- `/mu` structural runtime, seed, scheduler, Stage0, parity, or production
  implementation.
- Claude-related residue, including `CLAUDE.md`, `.claude/`, or `~/.claude/`.
- Any already-landed engine-state/scheduler seed, fixture, structural-test,
  scheduler-parity, or seed-registration item excluded by `TASKS.md:433`.

## Source Findings

- `deferred-report-truth-cleanup-2026-05-02_bridge_nonblockers.md`: pager
  tracker/archive/control-packet stale line-range and validation-summary wording.
- `docs-root-mu-docs-audit-closeout-2026-05-07_non_blocking.md`: active L4 G8
  docs retain pre-S1 no-production-reduction wording.
- `docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`:
  historical packet acceptance criteria, routing diagnostic, and `mu/docs`
  generated-index target-set wording.
- `hybrid-recovery-agent-2026-04-16_bridge_nonblockers.md`: PipelineRecovery
  taxonomy/table and hybrid-recovery packet status/scope wording.
- `learning-store-warming-2026-04-12-2026-04-13_bridge_nonblockers.md`:
  proof-command and packet-state wording.
- `mu-preproduction-redteam-2026-05-04_bridge_nonblockers.md`: repaired
  theater-risk guard described in stale present-tense stop-result prose.
- `pager-lifecycle-event-coverage-2026-04-23_bridge_nonblockers.md` and
  `pipeline-agent-pager-2026-04-16_bridge_nonblockers.md`: pager tracker/control
  packet validation proof wording.
- `parallel-pipeline-bus-namespacing-2026-04-29_bridge_nonblockers.md`:
  bus-path wording in control-plane/tooling comments and help text.
- `post-merge-verify-fetch-fix-2026-04-11_bridge_nonblockers.md`:
  Phase B/commit-owned validation boundary and fetch-fix claim wording.
- `recovery-gate-pr-conflicting-2026-04-20_bridge_nonblockers.md`:
  checked-out-branch invariant documentation drift.
- `supervisor-prompt-override-2026-04-20_bridge_nonblockers.md`: override
  validator guarantee overclaims in prompt/control-plane text.
- `tier3-short-circuit-2026-04-17_bridge_nonblockers.md`: short-circuit packet
  scope and live contract wording.
- `wave1a-pipeline-validation-2026-03-31_bridge_nonblockers.md`: stale Wave 1A
  packet/source-report state and scope wording.

## Work Items

1. Re-open each archived source packet and reproduce only the cited doc/control
   evidence needed for the specific wording claim.
2. Patch the narrowest current docs/control-plane surfaces that still carry
   stale or overbroad claims.
3. Do not rewrite historical archive snapshots except to add a clear archive
   header if a validation gate requires it.
4. Update the relevant report/deferred indexes only if the active inventory
   changes.
5. Record command, exit status, and short evidence summary for every closed
   routed finding.

## Stop Conditions

- Any fix requires `/mu` structural implementation.
- Any fix requires editing Claude-related residue.
- Current direct evidence no longer reproduces the archived source claim and no
  bounded doc patch is justified.
- The work would require broad documentation cleanup outside the cited surfaces.

## Acceptance Criteria

- Every closed source finding is tied to direct file-line evidence.
- No already-landed engine-state/scheduler work appears as pending.
- No Claude-related files are edited.
- The implementation wave records validation command, exit status, and evidence
  summary for each changed surface.

## Grounding / Authorization

Routed by `deferred-non-mu-deferred-lane-truth-sweep-2026-05-07` under
`FOUNDER_OVERRIDE:deferred-non-mu-deferred-lane-truth-sweep-2026-05-07`.
