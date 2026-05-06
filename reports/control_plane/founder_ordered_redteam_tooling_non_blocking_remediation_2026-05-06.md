# Founder Ordered Redteam Tooling Non-Blocking Remediation

Date: 2026-05-06
Status: QUEUED - NON-BLOCKING REMEDIATION PACKET
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06
Class: L4_ENABLER
Category: tooling
Severity: NON-BLOCKING
Source audit packet: `reports/deferred/non_blocking/founder_ordered_redteam_tooling_audit_2026-05-05_non_blocking.md`
Queue order: non-`/mu` non-blocking remediation, after tests non-blocking remediation and before all `/mu` structural remediation.
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-remediation-queue-organization-2026-05-05

This packet queues the non-blocking tooling follow-up from the founder ordered
redteam audit output. It does not implement remediation.

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

## Remediation Scope For Future Wave

- Align the manual full-audit label and behavior so operators can distinguish
  comprehensive fail-closed validation from non-blocking stress evidence.
- Bound fixture-gate Graphviz install liveness with a workflow timeout or
  command-level timeout consistent with existing bounded dependency patterns.
- Preserve the audit classification: these are non-blocking tooling proof-class
  and CI liveness findings, not runtime remediation.

## Stop Conditions

- Stop if current tooling truth proves either non-blocking finding has already
  been remediated; update the tracker instead of implementing stale work.
- Stop if remediation requires runtime, tests-only, docs-only, or `/mu`
  structural changes outside the tooling category.
- Stop if remediation would require commit, push, PR, or merge governance
  execution from inside the implementer wave.
- Stop if any Claude-related file would need to be edited.

## Acceptance Criteria

- Manual full-audit wording and exit behavior no longer imply fail-closed
  release proof for stress tests that remain explicitly non-blocking.
- Fixture-gate Graphviz dependency installs have bounded liveness.
- Focused command or static evidence demonstrates the proof-class correction
  and the bounded install behavior.
- The wave does not relist already landed engine-state/scheduler seed, fixture,
  structural-test, scheduler-parity, or seed-registration work as unresolved.
- The matching `TASKS.md` entry is updated with implementation and evidence
  status.

## Tracker Update Note

Add or update the `[FOUNDER-ORDERED-REDTEAM-TOOLING-NON-BLOCKING-REMEDIATION]`
entry under `[NEXT-CODEX-POST-REDTEAM]` with this packet path, this wave ID,
category `tooling`, severity `non-blocking`, source audit packet path, and the
acceptance evidence once implemented.
