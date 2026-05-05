# Mu Preproduction Gate Theater Blocker

Date: 2026-05-04
Status: ACTIVE BLOCKER
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: mu-preproduction-redteam-2026-05-04
Class: L4_ENABLER
Severity: BLOCKER
Production-forward movement: BLOCKED

## Finding

DEFECT: the red-team startup gate previously completed successfully while the
L4 gate test integrity classifier reported `theater_risk` methods. That
violated the mu preproduction red-team stop condition for a test/tool that
claims production gate coverage but can pass without enforcing the claimed
invariant.

Phase B has now mechanized the bounded gate fix by making the redteam startup
guard run `check_gate_behavioral_pairs.py --fail-on-theater`. Production-forward
movement remains blocked because the strict gate is expected to fail while the
85 reported `theater_risk` methods remain unresolved or undispositioned.

## Direct Evidence

- `tools/session/founder_session_guard.sh:102-113` and the tracked mirror
  `mu/tools/session/founder_session_guard.sh:102-113` define the redteam
  mode-specific command set. The Phase B repair changes that command to
  `python3 tools/checks/check_gate_behavioral_pairs.py --fail-on-theater`.
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

## Why This Blocks Production

The red-team startup command is treated as a production-preparation gate. After
the Phase B repair, that gate is fail-closed for reported theater risk. A green
redteam startup can no longer mask known theater-risk methods, but the strict
gate will remain red until the 85 reported methods are resolved or explicitly
dispositioned as classifier false positives.

## Required Follow-Up

The remaining follow-up is to decide whether every reported `theater_risk`
method is a real test defect or a classifier false positive. Production-forward
movement must remain blocked until the enforced gate behavior is green for the
right reason.

## Scope Note

This packet does not relist the already-landed PR #701 Phase A artifacts or the
landed engine-state/scheduler reduction slice. The blocker is limited to the
current mu preproduction red-team gate-theater enforcement gap.
