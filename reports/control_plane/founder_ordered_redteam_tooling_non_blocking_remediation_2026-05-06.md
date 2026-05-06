# Founder Ordered Redteam Tooling Non-Blocking Remediation

Date: 2026-05-06
Status: COMPLETED (commit-ready, supervisor COMMIT_GO)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06
Phase-A-Lock: LOCKED
Class: L4_ENABLER
Category: tooling
Severity: NON-BLOCKING
Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking.md`
Queue order: non-`/mu` non-blocking remediation, after tests non-blocking remediation and before all `/mu` structural remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06
Source queue authorization: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the non-blocking tooling follow-up from the founder ordered
redteam audit output. It does not implement remediation.
## Scope

Editable implementation-wave files:

- `mu/tools/audits/audit_all.sh`: align the manual full-audit operator-facing
  wording, summary, and exit-status messaging with the non-blocking stress-test
  proof class.
- `tools/audit_all.sh`: same audit entrypoint when reached through the repo
  tooling path; edit only the canonical byte surface once if this path resolves
  to the same file as `mu/tools/audits/audit_all.sh`.
- `.github/workflows/audit_all.yml`: align the manual Audit All workflow name,
  description, and release-proof wording with the corrected audit proof class.
- `.github/workflows/fixture_gates.yml`: bound both Graphviz dependency install
  steps that currently support fixture gates.
- `TASKS.md`: limited to the `[NEXT-CODEX-POST-REDTEAM]`
  `[FOUNDER-ORDERED-REDTEAM-TOOLING-NON-BLOCKING-REMEDIATION]` entry after
  implementation, for implementation status and acceptance evidence only.

Reference-only files and docs:

- `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`
  as the governing remediation packet for this wave.
- `reports/deferred/non_blocking/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking.md`
  as the source audit packet and preserved finding evidence.
- `.github/workflows/weekly_deep_fuzz.yml` as the fail-closed scheduled
  stress/deep-fuzz reference for N1.
- `.github/workflows/green_gate.yml` as the existing bounded dependency-install
  pattern for N2.
- `TASKS.md` exact `[NEXT-CODEX-POST-REDTEAM]` lines for queue authorization
  and tracker synchronization; the queue entry authorizes the wave but does not
  prove each finding is still unlanded in current code.

- `reports/deferred/non_blocking/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work Items

1. N1 - Full Audit Advertises Comprehensive Validation While Stress Failures
   Are Non-Blocking.
   In `mu/tools/audits/audit_all.sh`, and in the `tools/audit_all.sh` path only
   if it is the same repo audit entrypoint, preserve the intended blocking
   result for required audit checks while making stress-test evidence explicit
   as optional/non-blocking. The final output and exit-status explanation must
   distinguish "required audit checks passed" from "all release/stress proof
   passed" when stress tests are skipped or fail non-blockingly.

2. N1 workflow wording.
   In `.github/workflows/audit_all.yml`, adjust the manual Audit All workflow
   label and description so it no longer advertises comprehensive fail-closed
   release validation when it invokes an audit path that preserves optional
   stress-test behavior. Keep `.github/workflows/weekly_deep_fuzz.yml`
   reference-only as the separate fail-closed scheduled stress/deep-fuzz lane.

3. N2 - Fixture Gate Graphviz Install Retains Unbounded Apt Steps.
   In `.github/workflows/fixture_gates.yml`, add bounded liveness to both
   Graphviz dependency install steps using workflow `timeout-minutes`,
   command-level `timeout`, or both, consistent with the existing bounded
   dependency pattern preserved from `.github/workflows/green_gate.yml`.

4. Tracker evidence after implementation.
   Update only the matching `TASKS.md` entry under `[NEXT-CODEX-POST-REDTEAM]`
   after code/workflow remediation has landed locally, recording implemented
   files, focused evidence, and the same-wave founder override. If scoped
   current-code inspection proves either N1 or N2 is already remediated before
   editing, remove that item from pending work and acceptance evidence instead
   of relisting stale unresolved work.

## Constraints

- This is a tooling/control-plane non-blocking remediation wave; do not make
  runtime, `/mu` structural, tests-only, docs-only, scheduler, seed,
  projection, or engine-state remediation changes.
- Do not edit Claude-related files or home-directory/persona surfaces.
- Do not widen into the blocking tooling packet, docs packet, tests packet, or
  `/mu` structural packets.
- Do not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- Do not treat the source queue override as sufficient same-wave authorization
  for this L4_ENABLER control-surface wave; use the wave-bound founder override
  recorded in this packet.
- Do not perform commit, push, PR, merge, or post-merge governance execution
  from inside the implementer wave unless a separate operator instruction
  explicitly requests that lifecycle step.

## Stop Conditions

- Stop if current scoped tooling truth proves either non-blocking finding has
  already been remediated; update the scoped tracker evidence instead of
  implementing stale work.
- Stop if remediation requires files outside the editable implementation-wave
  scope listed above.
- Stop if remediation requires runtime, tests-only, docs-only, or `/mu`
  structural changes outside the tooling category.
- Stop if remediation would require commit, push, PR, merge, post-merge
  governance execution, or broad pipeline dispatch from inside the implementer
  wave.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- `audit_all.sh` operator-facing wording, success summary, and exit-status
  explanation no longer imply fail-closed release/stress proof when stress
  tests remain explicitly non-blocking.
- `.github/workflows/audit_all.yml` no longer advertises the manual Audit All
  workflow as comprehensive fail-closed release validation while calling an
  audit path with optional/non-blocking stress evidence.
- `.github/workflows/fixture_gates.yml` bounds both Graphviz dependency install
  steps with step-level timeout, command-level timeout, or equivalent bounded
  liveness.
- Focused static or command evidence demonstrates the proof-class correction
  and the bounded fixture-gate install behavior.
- Already landed engine-state/scheduler seed, fixture, structural-test,
  scheduler-parity, and seed-registration work is not relisted as unresolved.
- The matching `TASKS.md` entry is updated after implementation with
  implementation status, evidence, and
  `FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06`.

## Grounding / Authorization

- Governing task: `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]`, exact current entry
  for `[FOUNDER-ORDERED-REDTEAM-TOOLING-NON-BLOCKING-REMEDIATION]`.
- Governing packet: `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`.
- Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking.md`.
- TASKS queue authorization: `FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05`.
- Same-wave L4_ENABLER authorization:
  FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.
- TASKS.md authorizes this queued wave, but TASKS.md does not prove every
  listed item remains unlanded; the implementation wave must prefer scoped
  current code truth over stale packet wording when they conflict.

## Source Findings

### N1 - Full Audit Advertises Comprehensive Validation While Stress Failures Are Non-Blocking

Classification: NON-BLOCKING PROOF-CLASS MISMATCH

Surfaces: `audit_all.sh`, manual Audit All workflow, stress-test proof class.

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking.md`:

- Lines 47-55: `mu/tools/audits/audit_all.sh:28` through
  `mu/tools/audits/audit_all.sh:31` describe the full audit as comprehensive
  CI/pre-push validation, while `mu/tools/audits/audit_all.sh:95` through
  `mu/tools/audits/audit_all.sh:102` run `tests/stress/` as optional and
  convert stress-test failure into `Note: Stress tests skipped or failed
  (non-blocking)`.
- Lines 56-59: `.github/workflows/audit_all.yml:3` through
  `.github/workflows/audit_all.yml:6` present the workflow as manual deep
  validation before important releases; `.github/workflows/audit_all.yml:39`
  through `.github/workflows/audit_all.yml:43` execute `tools/audit_all.sh`.
- Lines 60-62: `.github/workflows/weekly_deep_fuzz.yml:47` through
  `.github/workflows/weekly_deep_fuzz.yml:58` separately run deep fuzz and
  stress tests under the weekly schedule with normal fail-closed shell behavior.

### N2 - Fixture Gate Graphviz Install Retains Unbounded Apt Steps

Classification: NON-BLOCKING DEFECT

Surfaces: GitHub fixture gates, CI liveness, stale tooling workaround residue.

Source evidence preserved from
`reports/deferred/non_blocking/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking.md`:

- Lines 84-90: `.github/workflows/fixture_gates.yml:54` through
  `.github/workflows/fixture_gates.yml:60` and
  `.github/workflows/fixture_gates.yml:66` through
  `.github/workflows/fixture_gates.yml:71` run Graphviz installs as
  `sudo apt-get update && sudo apt-get install -y graphviz` without a
  step-level timeout or bounded `timeout` wrapper.
- Lines 95-103 preserve direct scoped-search output showing
  `.github/workflows/green_gate.yml` has `timeout-minutes` and bounded
  `timeout 120s` system dependency steps, while
  `.github/workflows/fixture_gates.yml:60` and
  `.github/workflows/fixture_gates.yml:71` retain the unbounded apt commands.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `.github/workflows/audit_all.yml`
  - `.github/workflows/fixture_gates.yml`
  - `TASKS.md`
  - `mu/tools/audits/audit_all.sh`
  - `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06`
- Active packet: `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8dd997e68a37bd621dddf4df3f2e9233d9d5e16a3e1dd626dba0a036969fd188`
- Indicator artifact: `reports/l4_wave_indicators/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06 --output reports/l4_wave_indicators/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md. (2) Commit handoff carries 7 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.json`
- Current staged files:
  - `.github/workflows/audit_all.yml`
  - `.github/workflows/fixture_gates.yml`
  - `TASKS.md`
  - `mu/tools/audits/audit_all.sh`
  - `reports/control_plane/founder_ordered_redteam_tooling_non_blocking_remediation_2026-05-06.md`
  - `reports/deferred/non_blocking/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
