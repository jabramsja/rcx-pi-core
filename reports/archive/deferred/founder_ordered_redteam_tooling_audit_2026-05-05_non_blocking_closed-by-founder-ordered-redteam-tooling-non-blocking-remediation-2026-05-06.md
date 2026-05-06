# Founder Ordered Redteam Tooling Audit - Non-Blocking Findings

Date: 2026-05-06
Status: CLASSIFIED - NON-BLOCKING
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-tooling-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_tooling_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-tooling-audit-2026-05-05

This packet records non-blocking tooling-audit findings only. The audit wave
did not implement remediation.

## Scope Executed

- Explicit tracked target inventory command:
  `git ls-files tools scripts mu/tools dev.sh doctor.sh pyproject.toml .github/CODEOWNERS .github/pull_request_template.md .github/workflows/agent-review.yml .github/workflows/audit_all.yml .github/workflows/ci.yml .github/workflows/fixture_gates.yml .github/workflows/green_gate.yml .github/workflows/pr_verification_reminder.yml .github/workflows/slow_tests.yml .github/workflows/weekly_deep_fuzz.yml`
- Inventory result: 158 tracked entries: 143 tracked `mu/tools` entries,
  `dev.sh`, `doctor.sh`, the tracked `tools` symlink, the tracked `scripts`
  symlink, `pyproject.toml`, 2 listed `.github` files, and 8 listed workflows.
- `tools` is a tracked symlink to `mu/tools`, so it was treated as the same byte
  surface as explicit `mu/tools`, not as a separate implementation.
- `scripts` is a tracked symlink to `mu/scripts`; the symlink target has 23
  tracked entries reachable through the explicit `scripts/` path and was
  inspected as the scripts surface without counting the symlink as a separate
  implementation.
- Root command surfaces were included: `dev.sh:34` through `dev.sh:42`
  dispatch the fast/full audit entrypoints, and `doctor.sh:24` through
  `doctor.sh:103` verify developer environment dependencies and CLI presence.
- Scoped search for already-landed engine-state/scheduler residue produced no
  matches for `rcx_engine_state`, `rcx_engine_scheduler`,
  `post-redteam-engine-state`, `scheduler-parity`, `engine-state`, or
  `scheduler` in the explicit target set.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## N1 - Full Audit Advertises Comprehensive Validation While Stress Failures Are Non-Blocking

Classification: NON-BLOCKING PROOF-CLASS MISMATCH

Surfaces: `audit_all.sh`, manual Audit All workflow, stress-test proof class.

Evidence:

- `mu/tools/audits/audit_all.sh:28` through
  `mu/tools/audits/audit_all.sh:31` describe the full audit as comprehensive
  CI/pre-push validation that runs all 3,155+ tests including fuzzer and slow
  tests, semantic purity, contraband detection, AST police, anti-cheat scans,
  and fixture validation.
- `mu/tools/audits/audit_all.sh:95` through
  `mu/tools/audits/audit_all.sh:102` run `tests/stress/` as optional and
  convert any stress-test failure into a note:
  `pytest -q tests/stress/ --timeout=300 2>/dev/null || echo "Note: Stress tests skipped or failed (non-blocking)"`.
- `.github/workflows/audit_all.yml:3` through
  `.github/workflows/audit_all.yml:6` present the workflow as manual deep
  validation before important releases, and `.github/workflows/audit_all.yml:39`
  through `.github/workflows/audit_all.yml:43` execute `tools/audit_all.sh`.
- `.github/workflows/weekly_deep_fuzz.yml:47` through
  `.github/workflows/weekly_deep_fuzz.yml:58` separately run deep fuzz and
  stress tests under the weekly schedule with normal fail-closed shell behavior.

Why this is non-blocking:

- The repository has a separate weekly deep-fuzz workflow that runs stress tests
  fail-closed, and the audit script itself explicitly labels stress as
  non-CI-blocking.
- The mismatch is a proof-class/current-state issue for the manual "full audit"
  label: a failed stress suite does not make `audit_all.sh` fail even though
  the surrounding wording can lead operators to treat it as complete release
  evidence.

Remediation is not authorized in this audit wave.

## N2 - Fixture Gate Graphviz Install Retains Unbounded Apt Steps

Classification: NON-BLOCKING DEFECT

Surfaces: GitHub fixture gates, CI liveness, stale tooling workaround residue.

Evidence:

- `.github/workflows/fixture_gates.yml:54` through
  `.github/workflows/fixture_gates.yml:60` run the `orbit-svg` Graphviz install
  as `sudo apt-get update && sudo apt-get install -y graphviz` without a
  step-level timeout or bounded `timeout` wrapper.
- `.github/workflows/fixture_gates.yml:66` through
  `.github/workflows/fixture_gates.yml:71` repeat the same unbounded install
  pattern for the `orbit-index` job.
- Direct scoped search shows `fixture_gates.yml` has the unbounded apt commands
  and no `timeout-minutes`, while `green_gate.yml` has both a 30-minute job
  timeout and a 3-minute bounded system dependency step:

```text
$ rg -n "timeout-minutes|sudo apt-get update|sudo apt-get install|timeout 120s" .github/workflows/fixture_gates.yml .github/workflows/green_gate.yml
.github/workflows/green_gate.yml:24:    timeout-minutes: 30
.github/workflows/green_gate.yml:52:        timeout-minutes: 3
.github/workflows/green_gate.yml:59:          timeout 120s sudo apt-get update
.github/workflows/green_gate.yml:60:          timeout 120s sudo apt-get install -y ripgrep
.github/workflows/fixture_gates.yml:60:        run: sudo apt-get update && sudo apt-get install -y graphviz
.github/workflows/fixture_gates.yml:71:        run: sudo apt-get update && sudo apt-get install -y graphviz
```

Why this is non-blocking:

- This is a CI liveness and stale-workaround risk, not a path that lets a bad
  fixture pass.
- The current `green_gate.yml` system dependency install has already been
  bounded, so this finding is scoped to the fixture workflow's Graphviz jobs.

Remediation is not authorized in this audit wave.
