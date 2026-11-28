<!-- DOC_STATUS: REFERENCE -->
# Private-attribute seal refuses every approved review: the reviewer writes its own turn id — 2026-11-28

Class: DEFECT · Severity: high · Disposition: **RESOLVED BY `workingrcx-bridge-envelope-identity-2026-11-28`
(this record lands with that wave's fix)** · Owner: 40
`[FLEET-NATIVE-LIFECYCLE-PREVENTION]`.

Resolution: `workingrcx-bridge-envelope-identity-2026-11-28` binds identity at the single storage point. In the
bridge supervisor's turn flow, `execute_agent_turn` passes every parsed agent envelope through the public
`bind_envelope_identity` helper before storing it, so the stored and the returned envelope are one bound object
carrying the turn's canonical `job_id`, `turn_id` and `agent_role`. An envelope whose `job_id` is present and names
a different job is refused, and its turn is recorded exactly as an unparseable envelope's turn is. Raw output files
stay verbatim, and `phase_b_executor`'s private-attribute seal is unchanged and exactly as strict. Regressions cover
a self-written reviewer turn id, an envelope naming another job, an already-canonical envelope and byte-identical raw
output, through public functions and the bridge's normal turn flow only. Next step: relaunch the lane-completion fix
with `workingrcx-lane-completion-monitor-pairing-r2-2026-11-28`'s preserved candidate.

Classification evidence:

- It affects an executor surface: Phase B's private-attribute post-review seal, and the bridge supervisor's
  envelope storage that feeds it.
- The failure is terminal: Phase B returns `status: error` at step `private_attr_post_review_seal`, the
  dispatcher stops, and no recovery runs. It stays silent until a wave's staged tests trigger the private-attribute
  gate. The first wave to hit it lost a candidate that had passed every review.

## Observed

Wave `workingrcx-lane-completion-monitor-pairing-r2-2026-11-28`:
1. Its re-entry review approved the repairs for the supervisor's three findings.
2. The private-attribute gate then ran a remediation pass, and the private-attribute review
   (`phase-b-reentry-private-attr-r4-1b436cb9`) approved it with four low findings.
3. Phase B then stopped with "Recovered reviewer job/turn/decision identity mismatch".

Nothing was committed. The lane is preserved on the recovery volume as
`lane-completion-monitor-pairing-r2-terminal-lane-20261128`, with SHA256SUMS verified.

## Root cause (verified from the lane's bridge.db, read-only)

The reviewer writes its own `turn_id` into its envelope, in an invented format. All five canonical reviewer
turns of that wave show it, for example:

- the bridge turn `phase-b-r1-4030065c--r1-reviewer-20e25c43` carries envelope turn id
  `phase-b-r1-4030065c-reviewer-r1`;
- the bridge turn `phase-b-reentry-private-attr-r4-1b436cb9--r1-reviewer-cfcd64bb` carries
  `phase-b-reentry-private-attr-r4-1b436cb9-reviewer-r1`.

The bridge parses the agent's envelope and stores it verbatim (`parse_envelope`, then `update_turn_complete`). No
step in `mu/tools/agents` compares its identity fields. Only the private-attribute recovery reader,
`_read_recovered_private_attr_envelope` in `phase_b_executor`, requires the envelope's `turn_id` to equal the
turn's. So that seal can never pass while reviewers write their own ids. Every other field matched: the job id,
the reviewer role, the GO decision and the turn-id format.

## Required fix

1. **Bind identity at the single storage point.** After the bridge parses an agent's envelope and before storing
   it:
   - refuse an envelope whose `job_id` names a different job, the same way an unparseable envelope is refused;
   - otherwise store and return the envelope with the turn's canonical `job_id`, `turn_id` and `agent_role`.
   - Raw output files stay verbatim.
2. **Regressions:**
   - a reviewer envelope with a self-written turn id is stored and returned with the canonical id;
   - an envelope naming another job is refused;
   - an already-canonical envelope is unchanged.
3. Afterwards, relaunch the lane-completion fix, carrying R2's preserved, reviewed candidate.
