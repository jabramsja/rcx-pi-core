# Founder Ordered Redteam Docs Audit - Non-Blocking Findings

Date: 2026-05-05
Status: CLASSIFIED - NON-BLOCKING
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-docs-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-docs-audit-2026-05-05

This packet records non-blocking docs-audit findings only. The audit wave did
not implement remediation.

## Scope Executed

- Markdown inventory command: `find . -path ./.git -prune -o -path ./node_modules -prune -o -name '*.md' -type f -print | LC_ALL=C sort | wc -l`
- Inventory result: 2310 repo-local markdown files discovered at audit time.
- Active/generated non-archive markdown: 2027.
- Archive/historical markdown: 283.
- Active docs, report packets, deferred finding packets, roadmap docs, and
  `mu/docs/` markdown were scanned for stale current-state, stale lane, stale
  tracker, and proof-class claims.
- Archived markdown was treated as historical evidence only.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## N1 - Root README Presents Stage0 Production Cutover As Still Future

Classification: NON-BLOCKING DOC_ACCURACY

Surfaces: root founder-facing current status, L4/Stage0 production truth,
remediation ordering.

Evidence:

- `README.md:16` says bounded L4 reduction landed only "through shadow-mode
  cutover (PR #581)" and that "Production flip requires performance evidence +
  founder GO."
- `STATUS.md:52` says VM cutover is ACTIVE and all 33 projections run via
  Stage0 VM.
- `STATUS.md:59` says `_STAGE0_VM_CUTOVER = True`.
- `TASKS.md:436` records `[S1-SCHED]` COMPLETE with all 33 projections via
  Stage0 VM.
- `TASKS.md:519` records that bounded production reduction has occurred with
  VM cutover active and 33 projections on Stage0 VM.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1031` sets
  `_STAGE0_VM_CUTOVER = True` with founder GO dated 2026-03-15.
- `mu/host/js/engine/kernel.js:20` sets `_STAGE0_VM_CUTOVER = true`, and
  `mu/host/js/engine/kernel.js:24` states the kernel step runs all projections
  via Stage0 VM.

Direct evidence commands:

```text
nl -ba README.md | sed -n '1,25p'
nl -ba STATUS.md | sed -n '48,62p'
nl -ba TASKS.md | sed -n '432,520p'
nl -ba mu/host/python/rcx_pi/selfhost/step_mu.py | sed -n '1026,1048p'
nl -ba mu/host/js/engine/kernel.js | sed -n '16,32p'
```

Why this is non-blocking:

- The finding is DOC_ACCURACY-only: it records stale root current-state wording,
  not a runtime failure, security issue, test regression, hard invariant
  violation, pipeline skip, or wrong output.
- `STATUS.md`, `TASKS.md`, and both substrate flags still provide live code truth
  for current operators.
- Remediation is not authorized in this audit wave.

## N2 - TASKS Active L4 Tracker Contradicts Its Own Production-Reduction Truth

Classification: NON-BLOCKING DOC_ACCURACY

Surfaces: canonical task tracker, L4 production-claim boundary.

Evidence:

- `TASKS.md:519` says bounded production reduction has occurred and explicitly
  names S1-B/S1-C: VM cutover active, 33 projections on Stage0 VM.
- `TASKS.md:545` still says "No production reduction claims" in the active SINK
  L4 operating-mode prose.
- `STATUS.md:52`, `STATUS.md:59`, and `STATUS.md:132` all record VM cutover
  active / all 33 projections via Stage0 VM.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:1031` and
  `mu/host/js/engine/kernel.js:20` are the direct substrate evidence that the
  cutover flag is active in both runtimes.

Direct evidence commands:

```text
nl -ba TASKS.md | sed -n '516,546p'
nl -ba STATUS.md | sed -n '48,62p;128,134p'
nl -ba mu/host/python/rcx_pi/selfhost/step_mu.py | sed -n '1029,1032p'
nl -ba mu/host/js/engine/kernel.js | sed -n '18,24p'
```

Why this is non-blocking:

- The finding is DOC_ACCURACY-only: it records stale tracker wording about the
  Stage0 production-reduction boundary, not a runtime failure, security issue,
  test regression, hard invariant violation, pipeline skip, or wrong output.
- This does not relist already-landed engine-state/scheduler work as unresolved.
- Remediation is not authorized in this audit wave.

## N3 - CHANGELOG Is No Longer A Reliable Recent-Landed-Waves Source

Classification: NON-BLOCKING DOC_ACCURACY

Surfaces: root volatile-state source, recent chronology.

Evidence:

- `CHANGELOG.md:3` says all notable changes to RCX are documented in the file.
- `CHANGELOG.md:5` starts the newest visible section at `2026-04-04`.
- `git log --oneline --since='2026-04-04' --max-count=20` shows May 5 merges
  through PR #876 and related founder-ordered red-team queue work.
- `TASKS.md:236` through `TASKS.md:239` record May 1 / May 5 tracker notes, and
  `TASKS.md:419` records the completed founder-ordered repo-code audit.

Direct evidence commands:

```text
nl -ba CHANGELOG.md | sed -n '1,80p'
git log --oneline --since='2026-04-04' --max-count=20
nl -ba TASKS.md | sed -n '232,240p;417,420p'
```

Why this is non-blocking:

- `STATUS.md`, `TASKS.md`, and git history still provide live current truth.
- The risk is operator drift from a stale root chronology source, not a direct
  runtime or promotion-proof defect.

## N4 - Active Seed/Projection Count Claims Lag The Registered Seed Corpus

Classification: NON-BLOCKING DOC_ACCURACY

Surfaces: root README, active `mu/docs/` design specs, seed-count grounding.

Evidence:

- `README.md:23` says there are approximately 163 projections across 19 seed
  files and points to `test_seed_counts.py` for exact counts.
- `mu/docs/core/Boot0Architecture.v0.md:337` says all seed files total 19.
- `mu/docs/core/TypedNumericEnvelopes.v0.md:251` says all 14 seed files use
  integer literals only; `mu/docs/core/TypedNumericEnvelopes.v0.md:313` says
  Option B touches all 14 seeds.
- `tests/structural/test_seed_counts.py:26` through
  `tests/structural/test_seed_counts.py:40` registers 21 seed files in
  `MU_SEEDS`.
- `tests/structural/test_seed_counts.py:54` through
  `tests/structural/test_seed_counts.py:78` starts the current
  `EXPECTED_COUNTS` registry, including the landed engine-state/scheduler and
  terminal/evidence utility seeds.
- A narrow AST read of `tests/structural/test_seed_counts.py` reported:
  `MU_SEEDS_total 21`, `EXPECTED_COUNTS_total_files 21`, and
  `EXPECTED_COUNTS_projection_total 194`.

Direct evidence commands:

```text
nl -ba README.md | sed -n '20,25p'
nl -ba mu/docs/core/Boot0Architecture.v0.md | sed -n '335,390p'
nl -ba mu/docs/core/TypedNumericEnvelopes.v0.md | sed -n '249,314p'
nl -ba tests/structural/test_seed_counts.py | sed -n '24,78p'
python3 - <<'PY'
import ast
from pathlib import Path
src = Path('tests/structural/test_seed_counts.py').read_text()
mod = ast.parse(src)
vals = {}
for node in mod.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {'MU_SEEDS','EXPECTED_COUNTS'}:
                vals[target.id] = ast.literal_eval(node.value)
print('MU_SEEDS_total', sum(len(v) for v in vals['MU_SEEDS'].values()))
print('EXPECTED_COUNTS_total_files', len(vals['EXPECTED_COUNTS']))
print('EXPECTED_COUNTS_projection_total', sum(vals['EXPECTED_COUNTS'].values()))
PY
```

Why this is non-blocking:

- The executable registry is current and enforced by structural tests; this is
  stale descriptive count text.
- This finding records the count drift caused by already-landed seed work
  without relisting that landed work as unresolved.

## N5 - Roadmap Manifest Still Marks Gates 6-8 As Parked In A Status Column

Classification: NON-BLOCKING DOC_ACCURACY

Surfaces: roadmap manifest, L4 gate status summary.

Evidence:

- `roadmap/MANIFEST.md:45` through `roadmap/MANIFEST.md:48` includes a `Status`
  table where gates 6-8 are marked `PARKED`.
- `STATUS.md:142` through `STATUS.md:147` records Gate 8 as PASS
  (classification gate, caveated).
- `roadmap/MANIFEST.md:56` through `roadmap/MANIFEST.md:60` says roadmap docs
  should point to canonical sources and should not track current state, so this
  is a manifest wording drift rather than a source-of-truth conflict.

Direct evidence commands:

```text
nl -ba roadmap/MANIFEST.md | sed -n '40,60p'
nl -ba STATUS.md | sed -n '142,148p'
```

Why this is non-blocking:

- The manifest itself defers current state to `STATUS.md` and `TASKS.md`.
- The stale row can mislead readers, but canonical status remains available and
  test-backed elsewhere.

## N6 - Active Non-Blocking Lane Retains Resolved Packets Without A Clear Historical Header

Classification: NON-BLOCKING DOC_ACCURACY

Surfaces: deferred finding lane status, active advisory retention rules.

Evidence:

- `reports/deferred/non_blocking/README.md:3` through
  `reports/deferred/non_blocking/README.md:11` says this folder holds active
  founder-facing advisory audits and unresolved residue, while generated records
  may also be retained as historical advisory evidence after parent closure.
- `reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md:6`
  says `Status: RESOLVED`.
- `reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md:6`
  says `Status: RESOLVED_IN_FOLLOWUP`, while lines 9 through 21 still present
  the original findings as `Disposition: non_blocking`.
- `reports/deferred/non_blocking/handoff-current-state-reconciliation-2026-05-05_bridge_nonblockers.md:6`
  says `Status: RESOLVED_DEFERRED_NON_BLOCKING`.

Direct evidence commands:

```text
nl -ba reports/deferred/non_blocking/README.md | sed -n '1,30p'
nl -ba reports/deferred/non_blocking/codex-autoping-active-ping-cleanup-hardening-2026-05-05_bridge_nonblockers.md | sed -n '1,20p'
nl -ba reports/deferred/non_blocking/codex-autoping-window-watchdog-selfheal-2026-05-01_bridge_nonblockers.md | sed -n '1,30p'
nl -ba reports/deferred/non_blocking/handoff-current-state-reconciliation-2026-05-05_bridge_nonblockers.md | sed -n '1,20p'
```

Why this is non-blocking:

- The lane README explicitly allows retained historical advisory evidence.
- The issue is unclear active-vs-historical labeling for resolved records, not
  an unresolved blocker or runtime defect.
