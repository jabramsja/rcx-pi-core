# Mu-Preproduction-Theater-Ratchet-Resolution-2026-05-05

Date: 2026-05-05
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Parent queue: [NEXT-CODEX-POST-REDTEAM]
Wave ID: mu-preproduction-theater-ratchet-resolution-2026-05-05
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Target gate: G8
Authorization: TASKS.md:395-402 authorizes the founder-unparked parent queue and the immediate `[MU-PREPRODUCTION-REDTEAM]` blocked work order; this packet is the governing packet for the bounded follow-up wave.
Governing packet: reports/control_plane/mu-preproduction-theater-ratchet-resolution-2026-05-05_2026-05-05.md
Parent governing packet: reports/control_plane/mu_preproduction_redteam_2026-05-04.md
Blocker: reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md
FOUNDER_OVERRIDE:mu-preproduction-theater-ratchet-resolution-2026-05-05

## Phase B Implementation Result

The 85 raw strict-gate `theater_risk` findings are not real undispositioned
test defects in current code truth. They are all current, non-expired curated
classifier false positives covered by the theater-risk ratchet.

Direct evidence before code changes:

- `python3 tools/checks/check_gate_behavioral_pairs.py --fail-on-theater`
  exited `1` and reported `FAIL: 85 theater_risk method(s) found`.
- `python3 tools/checks/check_theater_risk_ratchet.py --json` exited `0` with
  `current_count: 85`, `allowlist_count: 85`, empty `new`, empty `expired`,
  empty `real`, empty `removals`, and `passed: true`.
- `jq '.entries | length, (group_by(.classification) | map({classification:
  .[0].classification, count: length})), ([.[] | .expires_on] | min),
  ([.[] | .expires_on] | max)' tools/checks/theater_allowlist.json` reported
  85 entries, all `heuristic_false_positive`, with expiry range
  `2026-06-01` through `2026-06-17`.
- `jq '{schema_version, generated_at, total_theater_risk,
  entries_length:(.entries|length)}' tools/checks/theater_allowlist.json`
  showed stale metadata before this wave: `total_theater_risk: 84` while
  `entries_length: 85`.

Implemented result:

- Redteam startup now runs `python3 tools/checks/check_theater_risk_ratchet.py`
  instead of the raw strict `check_gate_behavioral_pairs.py --fail-on-theater`
  path.
- The ratchet now rejects stale `total_theater_risk` metadata when it does not
  equal the allowlist entry count.
- Root and `mu/` surfaces are synchronized through the repo's root symlinked
  tool/test paths and covered by focused mirror tests.
- The active blocker packet is resolved. Production-forward movement is
  unblocked for this gate-theater blocker, without claiming L4 structural
  runtime movement.

Validation result:

- `PYTHONHASHSEED=0 python3 -m pytest
  mu/tests/tools/test_check_theater_risk_ratchet.py
  mu/tests/tools/test_check_gate_behavioral_pairs.py -q` passed (`52 passed`).
- `python3 tools/checks/check_theater_risk_ratchet.py --json` passed with
  `current_count: 85`, `allowlist_count: 85`, and `passed: true`.
- `python3 mu/tools/checks/check_theater_risk_ratchet.py --json` passed with
  the same counts and result.
- `./tools/session/founder_session_guard.sh redteam` dry-run now prints
  `python3 tools/checks/check_theater_risk_ratchet.py` in the redteam
  mode-specific command set.
- `./tools/checks/check_docs_consistency.sh` passed.
- `python3 tools/checks/enforce_l4_execution_contract.py --files ...`
  passed as `L4_ENABLER` when bound to the parent
  `mu-preproduction-redteam-2026-05-04` tracker note and existing parent
  indicator artifact. This follow-up does not create a new L4 indicator file.

## Purpose

Resolve the active mu preproduction gate-theater blocker without hiding real test
defects. The current blocker is not the already-landed parent-queue Phase A
structural gap sweep or the already-landed engine-state/scheduler reduction. It
is the strict redteam gate behavior recorded by TASKS.md:402: production-forward
movement remains blocked while the 85 strict-gate `theater_risk` findings are
unresolved or undispositioned.

The wave must decide from current code truth whether the correct production gate
is to fix real tests, improve classifier behavior, or align redteam startup with
the curated theater-risk ratchet that fails on new, expired, or real theater risk
while allowing only evidence-backed curated false positives.

## Scope

Files and directories in scope:

- `tools/session/founder_session_guard.sh`
- `mu/tools/session/founder_session_guard.sh`
- `tools/checks/check_gate_behavioral_pairs.py`
- `mu/tools/checks/check_gate_behavioral_pairs.py`
- `tools/checks/check_theater_risk_ratchet.py`
- the `mu/` mirror of the theater-risk ratchet when current code truth shows one
  exists or is required for parity with the root tool surface
- theater-risk ratchet allowlist or metadata surfaces read by the ratchet, only
  if current code truth shows their contents are stale or incomplete
- focused tests for the gate checker, theater-risk ratchet, redteam startup guard
  command set, and any root/`mu` mirror synchronization touched by this wave
- `TASKS.md`, limited to the current `[NEXT-CODEX-POST-REDTEAM]` /
  `[MU-PREPRODUCTION-REDTEAM]` tracker state
- `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`
- deferred blocker/index text needed to keep the active blocker lane truthful
- this packet

## Work Items

1. Reproduce and triage the 85 strict-gate `theater_risk` findings against
   current code truth before changing gate behavior.
2. Classify each actionable finding as a real test defect, a classifier defect,
   a curated classifier false positive, or a stale ratchet/allowlist metadata
   problem. Do not add allowlist entries or remove findings without triage
   evidence.
3. If any finding is real, fix the bounded test or classifier defect when it is
   in scope; otherwise route it with file:line or command evidence and keep
   production-forward movement blocked.
4. If all current findings are evidence-backed curated false positives, align the
   redteam startup/preflight production gate with the curated ratchet semantics:
   fail on new, expired, or real theater risk; do not fail solely on allowlisted
   curated false positives.
5. Keep root and `mu/` mirror surfaces synchronized for every touched checker,
   ratchet, guard, and test path.
6. Update only the tracker, blocker, deferred index text, and ratchet metadata
   directly supported by code-truth evidence from this wave.
7. If the wave reveals a manual pipeline repair that is necessary to complete
   the bounded gate fix, mechanize it in recovery, builder, or automation only if
   the repair is narrow. If it is not narrow, stop and write a concrete follow-up
   packet with command and file evidence instead of broadening this wave.
8. Do not relist the already-landed PR #701 Phase A artifacts or the landed
   engine-state/scheduler reduction slice as unresolved work.

## Constraints

- Do not inspect or modify unrelated executor, test, runtime, or documentation
  files.
- Do not treat this packet as authorization for a broad `/mu` preproduction
  red-team rerun.
- Do not move production forward while real or undispositioned theater-risk
  findings remain.
- Do not silence the raw checker, delete theater findings, or add allowlist
  entries just to make the blocker green.
- Do not make the curated ratchet less strict for new, expired, or real
  theater-risk findings.
- Do not claim L4 structural runtime movement; this is a control-surface
  `L4_ENABLER` gate-repair wave unless a later packet authorizes runtime
  structural delta with evidence.
- Do not reopen or reimplement already-landed `[NEXT-CODEX-POST-REDTEAM]` seed,
  fixture, structural-test, scheduler, or scheduler-parity work recorded as
  landed in TASKS.md:399.
- Do not create new report files unless a non-narrow manual pipeline repair
  forces a follow-up packet; this Phase A rewrite itself authorizes no new file.

## Stop Conditions

Stop and report immediately if:

1. Any strict-gate `theater_risk` finding proves to be a real test defect that
   cannot be fixed within the bounded checker, ratchet, guard, or focused-test
   scope.
2. Triage cannot prove whether the 85 findings are real defects or curated false
   positives with file:line or command evidence.
3. The proposed gate alignment would allow new, expired, or real theater risk to
   pass.
4. Root and `mu/` mirror behavior diverges for a touched checker, ratchet, guard,
   or test surface and cannot be reconciled within this wave.
5. Required pipeline repair extends beyond a narrow recovery, builder, or
   automation fix.
6. Acceptance would require modifying unrelated runtime, seed, scheduler,
   executor, or broad documentation surfaces.

## Acceptance Criteria

- The 85 strict-gate `theater_risk` findings are either fixed, routed as real
  blockers with evidence, or proven by current code truth to be curated false
  positives already covered by the theater-risk ratchet.
- The redteam startup/preflight gate and curated ratchet enforce the same
  production-forward policy: fail on new, expired, or real theater risk; allow
  only evidence-backed curated false positives.
- Root and `mu/` mirror files touched by the wave are behaviorally synchronized
  and covered by focused tests.
- No allowlist or metadata update is made without command or file evidence
  showing it is stale, incomplete, or otherwise required by current code truth.
- `TASKS.md`, the active blocker packet, and deferred blocker/index text are
  updated only to the extent supported by the implemented code-truth result.
- Validation includes focused gate/checker tests, the redteam startup guard path
  or its narrow equivalent, `python3 tools/checks/check_theater_risk_ratchet.py
  --json`, docs consistency for touched report/tracker surfaces, and the L4
  execution contract for changed files.
- The final result explicitly states whether production-forward movement remains
  blocked or is unblocked, with the evidence command(s) that justify that state.
- Acceptance does not require, and must not relist, the already-landed PR #701
  Phase A artifacts or the landed engine-state/scheduler reduction slice.

## Grounding / Authorization

- `TASKS.md:395` marks `[NEXT-CODEX-POST-REDTEAM]` as unparked and
  founder-authorized.
- `TASKS.md:396-399` identifies the parent structural queue, records the current
  phase as open, and states that the Phase A structural gap sweep plus the
  engine-state/scheduler reduction slice already landed. Those landed items are
  out of scope for this packet.
- `TASKS.md:400-402` defines the immediate pre-production work order and names
  `[MU-PREPRODUCTION-REDTEAM]` as Phase B stopped/blocked on gate-theater risk,
  with blocker `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`
  and parent governing packet
  `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`.
- `reports/control_plane/mu_preproduction_redteam_2026-05-04.md:118-133`
  records the Phase B stop result: strict theater reproduction exits `1`, reports
  85 `theater_risk` methods, blocks production-forward movement, and applied no
  runtime code fix in the audit packet.
- `reports/control_plane/mu_preproduction_redteam_2026-05-04.md:135-148`
  classifies the prior package repair as `L4_ENABLER`, not L4 structural runtime
  movement.
- `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md:19-22`
  records that the redteam startup guard now runs the strict
  `check_gate_behavioral_pairs.py --fail-on-theater` path and remains blocked
  while the 85 findings are unresolved or undispositioned.
- `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md:58-63`
  defines the required follow-up: decide whether every reported `theater_risk`
  method is a real defect or classifier false positive before production-forward
  movement resumes.
- Same-wave control-surface authorization is explicit:
  `FOUNDER_OVERRIDE:mu-preproduction-theater-ratchet-resolution-2026-05-05`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `mu-preproduction-theater-ratchet-resolution-2026-05-05`
- Active packet: `reports/control_plane/mu-preproduction-theater-ratchet-resolution-2026-05-05_2026-05-05.md`
- Indicator artifact: `reports/l4_wave_indicators/mu-preproduction-theater-ratchet-resolution-2026-05-05.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_check_theater_risk_ratchet.py`
  - `mu/tools/checks/check_theater_risk_ratchet.py`
  - `mu/tools/checks/theater_allowlist.json`
  - `mu/tools/session/founder_session_guard.sh`
  - `reports/control_plane/mu-preproduction-theater-ratchet-resolution-2026-05-05_2026-05-05.md`
  - `reports/deferred/README.md`
  - `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`
  - `reports/l4_wave_indicators/mu-preproduction-theater-ratchet-resolution-2026-05-05.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `mu-preproduction-theater-ratchet-resolution-2026-05-05`
- Active packet: `reports/control_plane/mu-preproduction-theater-ratchet-resolution-2026-05-05_2026-05-05.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `1bd1c10291793e65f6137cf1273bc8d940b9e80633e3a8fd5b46864fd47d7e1c`
- Indicator artifact: `reports/l4_wave_indicators/mu-preproduction-theater-ratchet-resolution-2026-05-05.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_check_theater_risk_ratchet.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/mu-preproduction-theater-ratchet-resolution-2026-05-05_2026-05-05.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/mu-preproduction-theater-ratchet-resolution-2026-05-05.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_check_theater_risk_ratchet.py`
  - `mu/tools/checks/check_theater_risk_ratchet.py`
  - `mu/tools/checks/theater_allowlist.json`
  - `mu/tools/session/founder_session_guard.sh`
  - `reports/control_plane/mu-preproduction-theater-ratchet-resolution-2026-05-05_2026-05-05.md`
  - `reports/deferred/README.md`
  - `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`
  - `reports/l4_wave_indicators/mu-preproduction-theater-ratchet-resolution-2026-05-05.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
