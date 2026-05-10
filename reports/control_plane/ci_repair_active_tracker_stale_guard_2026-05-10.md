# CI Repair Active Tracker Stale Guard

Date: 2026-05-10
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: ci-repair-active-tracker-stale-guard-2026-05-10
Class: L4_ENABLER
Category: tooling/control-plane
Severity: NON-BLOCKING pipeline repair
Founder override: FOUNDER_OVERRIDE:ci-repair-active-tracker-stale-guard-2026-05-10
Source authorization: founder direction to pair manual pipeline cleanup with a mechanical/automated fix

## Scope

Close the stale active CI repair tracker entry and harden the stale tracker
checker so a completed slashed active task label cannot remain open just
because it lacks `PR #...` text.

Files in scope:

- `TASKS.md`
- `mu/tools/checks/check_stale_next_items.sh`
- `mu/tools/hooks/pre-push-fast`
- `reports/control_plane/ci_repair_active_tracker_stale_guard_2026-05-10.md`
- `reports/l4_wave_indicators/ci-repair-active-tracker-stale-guard-2026-05-10.json`

## Root-Cause Evidence

- `TASKS.md:318` still listed
  `[CI-REPAIR/weekly-deep-fuzz-stage0-negzero-fix-2026-05-10]` as active
  after the CI repair branch had merged.
- `git log --oneline --decorate --all --grep='weekly-deep-fuzz\|negzero\|negative-zero\|CI REPAIR' -n 20`
  showed merge commit `80a96b48 Merge pull request #918 from
  jabramsja/jabramsja/weekly-deep-fuzz-stage0-negzero-fix-2026-05-10`.
- `gh pr list --state all --search "weekly-deep-fuzz-stage0-negzero-fix-2026-05-10 OR negzero OR negative-zero" --json number,state,title,mergedAt,headRefName,url --limit 20`
  reported PR #918 as `MERGED`, merged at `2026-05-10T17:37:42Z`.
- Before this repair, the stale checker only examined `NEXT` PR-number text,
  so an active slashed wave label in `NOW` was invisible when the line did not
  contain `PR #...`.
- Reproduction after the guard change and before applying `--fix`:
  `bash tools/checks/check_stale_next_items.sh` exited `1` and reported
  `branch jabramsja/weekly-deep-fuzz-stage0-negzero-fix-2026-05-10 merged as PR #918 but active item not marked Landed`.

## Mechanical Fix

- Extend `mu/tools/checks/check_stale_next_items.sh` from NEXT-only PR checks
  to active-section checks covering `NOW` and `NEXT`.
- Keep existing PR-number detection for `NEXT`.
- Add slashed active task label detection such as
  `[CI-REPAIR/<wave-id>]`, resolve same-name and contributor-prefixed merged
  PR head refs, and fail closed when a merged branch remains active.
- Extend `--fix` so stale slashed active task entries are marked `Landed`.
- Update `pre-push-fast` messages so the hook truth matches the active-section
  scope it now enforces.
- Clear the already-merged CI repair `NOW` entry in `TASKS.md`.
- Bot-remediation follow-up: remove the hardcoded head owner from the stale-wave
  lookup so the guard applies to forks/contributor-prefixed head refs too.

## Evidence

- `bash tools/checks/check_stale_next_items.sh` exited `1` before `--fix` and
  identified PR #918 as the stale active entry.
- `bash tools/checks/check_stale_next_items.sh --fix` exited `0`, marked one
  stale active item as `Landed`, then re-ran and reported all active references
  clean.
- `bash -n tools/checks/check_stale_next_items.sh mu/tools/checks/check_stale_next_items.sh`
  exited `0`.
- PR #925 automated review reported a P2 owner-specific lookup at
  `mu/tools/checks/check_stale_next_items.sh:114`; the follow-up changes the
  lookup to check plain wave branches and contributor-prefixed merged PR head
  refs.

## Stop Boundary

This repair does not implement any new `/mu` production wave. It only closes
the stale active tracker line and hardens the mechanical checker that guards
future active tracker cleanup.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `ci-repair-active-tracker-stale-guard-2026-05-10`
- Active packet: `reports/control_plane/ci_repair_active_tracker_stale_guard_2026-05-10.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c1e23432cccf40885641aa9ccfc924ae54068237a8a3545e05e8b107e578469f`
- Indicator artifact: `reports/l4_wave_indicators/ci-repair-active-tracker-stale-guard-2026-05-10.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id ci-repair-active-tracker-stale-guard-2026-05-10 --output reports/l4_wave_indicators/ci-repair-active-tracker-stale-guard-2026-05-10.json`.
- Evidence delta: (1) Routed commit handoff scopes 4 wave-owned file(s). (2) No wave-owned pytest module was staged in this ad hoc handoff, so indicator collection is the mechanical evidence surface. (3) Indicator artifact binds the wave to reports/l4_wave_indicators/ci-repair-active-tracker-stale-guard-2026-05-10.json..
- Evidence handles:
  - `docs_status_tasks`: `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/docs/test_status_tasks_consistency.py -q --tb=short`
  - `indicator`: `reports/l4_wave_indicators/ci-repair-active-tracker-stale-guard-2026-05-10.json`
  - `stale_active_check`: `bash tools/checks/check_stale_next_items.sh`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/checks/check_stale_next_items.sh`
  - `reports/control_plane/ci_repair_active_tracker_stale_guard_2026-05-10.md`
  - `reports/l4_wave_indicators/ci-repair-active-tracker-stale-guard-2026-05-10.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
