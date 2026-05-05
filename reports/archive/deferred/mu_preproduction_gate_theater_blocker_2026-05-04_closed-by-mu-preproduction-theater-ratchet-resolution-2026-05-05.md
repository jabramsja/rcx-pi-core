# Mu Preproduction Gate Theater Blocker

Date: 2026-05-04
Status: RESOLVED (2026-05-05)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: mu-preproduction-redteam-2026-05-04
Class: L4_ENABLER
Severity: BLOCKER (resolved)
Production-forward movement: UNBLOCKED for this gate

## Archive / Closeout Status

- Archived on 2026-05-05 after the bounded
  `mu-preproduction-theater-ratchet-resolution-2026-05-05` follow-up and
  `TASKS.md` tracker note recorded the gate-theater finding as resolved.
- Current enforcement is `python3 tools/checks/check_theater_risk_ratchet.py`,
  which fails on new, expired, or `real` theater risk while allowing current
  non-expired curated `heuristic_false_positive` entries.
- This packet is retained as historical evidence. It is not an active
  `reports/deferred/blocking/` item.

## Finding

DEFECT: the red-team startup gate previously completed successfully while the
L4 gate test integrity classifier reported `theater_risk` methods. That
violated the mu preproduction red-team stop condition for a test/tool that
claims production gate coverage but can pass without enforcing the claimed
invariant.

The first Phase B repair made the redteam startup guard run
`check_gate_behavioral_pairs.py --fail-on-theater`, which correctly reproduced
the raw strict failure but still blocked on 85 findings that were already
curated classifier false positives.

The bounded 2026-05-05 follow-up resolves this blocker by aligning the redteam
startup guard with the curated anti-theater ratchet. The guard now runs
`python3 tools/checks/check_theater_risk_ratchet.py`, which still invokes the
classifier and fails on new, expired, or `real` theater risk, but does not fail
solely because current findings are non-expired curated false positives.

## Direct Evidence

- `tools/session/founder_session_guard.sh:102-113` and the tracked mirror
  `mu/tools/session/founder_session_guard.sh:102-113` define the redteam
  mode-specific command set. The 2026-05-05 repair changes that command to
  `python3 tools/checks/check_theater_risk_ratchet.py`.
- `tools/checks/check_gate_behavioral_pairs.py:10-15` documents
  `--fail-on-theater` as the mode that exits non-zero when theater is found.
- `tools/checks/check_gate_behavioral_pairs.py:277-280` leaves
  `fail_on_theater` false unless that flag is supplied, while proof-class
  mismatch enforcement is on by default.
- `tools/checks/check_gate_behavioral_pairs.py:298-308` only converts
  reported theater methods into exit code `1` inside the `if fail_on_theater`
  branch.
- Mirror check: `shasum tools/checks/check_gate_behavioral_pairs.py
  mu/tools/checks/check_gate_behavioral_pairs.py` produced the same SHA1
  (`726a4b0a1da2e0ed20c46602f9b04ae02997e4a4`) for both root and `mu/`
  copies.
- Original command evidence, default gate path:
  `./tools/session/founder_session_guard.sh redteam --run` completed
  successfully, including `python3 tools/checks/check_gate_behavioral_pairs.py`,
  even though that tool reported `theater_risk: 85 (5.4%)`.
- Command evidence, strict reproduction:
  `python3 tools/checks/check_gate_behavioral_pairs.py --fail-on-theater`
  exited `1` and reported `FAIL: 85 theater_risk method(s) found`.
- Command evidence, curated ratchet:
  `python3 tools/checks/check_theater_risk_ratchet.py --json` exited `0` with
  `current_count: 85`, `allowlist_count: 85`, empty `new`, empty `expired`,
  empty `real`, empty `removals`, and `passed: true`.
- Triage evidence:
  `jq '.entries | length, (group_by(.classification) | map({classification:
  .[0].classification, count: length})), ([.[] | .expires_on] | min),
  ([.[] | .expires_on] | max)' tools/checks/theater_allowlist.json` reported
  85 entries, all `heuristic_false_positive`, with expiry range
  `2026-06-01` through `2026-06-17`.
- Metadata repair evidence:
  `jq '{schema_version, generated_at, total_theater_risk,
  entries_length:(.entries|length)}' tools/checks/theater_allowlist.json`
  showed stale metadata before this wave (`total_theater_risk: 84`,
  `entries_length: 85`). The ratchet now validates that
  `total_theater_risk` equals the entries length, and both root and `mu/`
  allowlist metadata are corrected to 85.

## Why This No Longer Blocks Production

The red-team startup command is treated as a production-preparation gate. After
the 2026-05-05 follow-up, that gate is fail-closed for new unallowlisted
theater risk, expired allowlist entries, or entries classified as `real`. The
current 85 raw classifier findings are all non-expired curated
`heuristic_false_positive` entries, so this specific production-forward blocker
is resolved.

## Required Follow-Up

No follow-up remains for this blocker. Future raw classifier additions, expired
entries, or any allowlist entry classified as `real` must fail the ratchet and
block production-forward movement again until fixed or dispositioned with fresh
evidence.

## Scope Note

This packet does not relist the already-landed PR #701 Phase A artifacts or the
landed engine-state/scheduler reduction slice. The blocker was limited to the
mu preproduction red-team gate-theater enforcement gap and is now archived as
resolved historical evidence.
