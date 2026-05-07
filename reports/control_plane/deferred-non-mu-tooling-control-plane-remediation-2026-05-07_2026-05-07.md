# Deferred-Non-Mu Tooling Control-Plane Remediation 2026-05-07

Date: 2026-05-07
Status: Routed - Phase A required before implementation
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: deferred-non-mu-tooling-control-plane-remediation-2026-05-07
Class: L4_ENABLER
Category: tooling/control-plane
Phase-A-Lock: UNLOCKED
Source authorization: FOUNDER_OVERRIDE:deferred-non-mu-deferred-lane-truth-sweep-2026-05-07
Governing source packet: reports/control_plane/deferred-non-mu-deferred-lane-truth-sweep-2026-05-07_2026-05-07.md

## Scope

This routed packet groups still-open non-`/mu` tooling, dispatcher, Phase B,
commit, recovery, and observability findings from the deferred lane truth sweep.
It is a future implementation packet, not an implementation in the truth-sweep
wave.

In scope for a future implementation wave:

- Pipeline/control-plane tooling defects in executor, recovery, bridge,
  observability, and runner surfaces cited by the archived source packets.
- Same-wave mechanical fixes when manual pipeline repair is needed.
- Focused regression tests that prove the specific tooling/control-plane fix.

Out of scope:

- `/mu` structural runtime, seed, scheduler, Stage0, parity, or production
  implementation.
- Claude-related residue, including `CLAUDE.md`, `.claude/`, or `~/.claude/`.
- Commit, push, PR, merge, or pre-push execution from inside Phase B implementer
  validation.

## Source Findings

- `learning-store-warming-2026-04-12-2026-04-13_bridge_nonblockers.md`:
  learning-store import fallback can disable agent-memory helpers.
- `meta-bridge-taskid-path-safety-2026-04-03_bridge_nonblockers.md`:
  `lock_plan()` header/body status handling and zero-match envelope proof gaps.
- `mu-preproduction-redteam-2026-05-04_bridge_nonblockers.md`: Phase B can still
  continue implementer work after final REQUEST_CHANGES/NO_GO review budget.
- `pipeline-recovery-phase1-2026-03-31_bridge_nonblockers.md`: tmux/web timeline
  parsing, Phase B re-entry timeline coverage, stale raw review selection, and
  notification quoting.
- `plan-learning-store-enforcement-2026-04-08-2026-04-08_bridge_nonblockers.md`:
  recovery command filtering, lock-timeout persistence wording/code boundary,
  and dangerous command containment.
- `post-commit-roundtrip-2026-04-04_bridge_nonblockers.md`: commit-only retry
  path still invokes commit executor without the structured `--json` surface.
- `post-merge-verify-fetch-fix-2026-04-11_bridge_nonblockers.md`: ff-only merge
  dispatch proof and related commit/dispatch boundaries.
- `recovery-gate-wiring-2026-03-31_bridge_nonblockers.md`: surface-mode
  forwarding timeout gap.
- `supervisor-prompt-override-2026-04-20_bridge_nonblockers.md`: override
  validation contract mismatch between supervisor prompts and L4 validator.
- `tier-2-auto-retry-tier-3-llm-recovery-loop-2026-03-31_bridge_nonblockers.md`:
  Tier 2/Tier 3 recovery containment, logging, timeout accounting, and
  non-canonical generated packet residue.
- `tier3-short-circuit-2026-04-17_bridge_nonblockers.md`: short-circuit behavior
  broader than packet wording.
- `wave1a-pipeline-validation-2026-03-31_bridge_nonblockers.md`: observability
  dashboard attribute escaping and findings-pane inline Python interpolation.
- `hook_soft_gate_residue.md`: non-Claude validator strictness residue in
  `tools/runners/validate_agent_compliance.py`.

## Work Items

1. Reproduce each selected source claim against current code before patching.
2. Split the implementation further if dispatcher/Phase B/commit, recovery, and
   observability fixes cannot be changed safely in one bounded wave.
3. Pair any manual pipeline repair with a same-wave mechanical fix or leave a
   precise follow-up automation packet before closeout.
4. Add or update focused tests for each tooling behavior change.
5. Keep archive snapshots as provenance; do not treat stale generated wording as
   current active work after the fix lands.

## Stop Conditions

- Any fix requires `/mu` structural implementation.
- Any fix requires editing Claude-related residue.
- Any fix would need commit/push/PR/merge execution from a Phase B implementer.
- A source claim cannot be reproduced directly and no bounded current defect
  remains.
- The work spans too many tooling surfaces for one bounded wave.

## Acceptance Criteria

- Every changed behavior is proven by focused tests or direct command evidence.
- Manual pipeline repair, if any, is paired with same-wave automation or a
  precise follow-up automation packet.
- No Claude-related files are edited.
- No `/mu` structural remediation is implemented.
- Validation records include command, exit status, and short evidence summary.

## Grounding / Authorization

Routed by `deferred-non-mu-deferred-lane-truth-sweep-2026-05-07` under
`FOUNDER_OVERRIDE:deferred-non-mu-deferred-lane-truth-sweep-2026-05-07`.
