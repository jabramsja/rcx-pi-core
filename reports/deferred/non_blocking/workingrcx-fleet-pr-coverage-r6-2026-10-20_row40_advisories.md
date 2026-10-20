<!-- DOC_STATUS: REFERENCE -->
# PR1330 / PR1338 R6: standing obligations

Date: 2026-10-20. Standing owner: [FLEET-NATIVE-LIFECYCLE-PREVENTION], existing
row40. Coverage remains with [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION], row38.
Canonical ownership and preserved history live in TASKS.md. This required
delivery is separate from optional native `_bridge_nonblockers.md` output;
empty bridge findings may clear that optional file without resolving this work.

Comparison: actual PR1339 merge `ca6c3a93c176fc1da6b6bb6f0169edebf8c1a654`.
PR1334 actually merged at `b75972546901e3a09e08047f1a10c7684bf875bd`.
Exact whole-file and range hashes, native predicates and new local run receipts
are in `reports/control_plane/workingrcx-fleet-pr-coverage-r6-2026-10-20_implementation_evidence.json`
and the same-wave `_coverage.json`. Mechanical binding is not independent
semantic approval, and preserved old approval hashes do not approve R6.

## Original PR1330 topic 1: demonstrated partial-output preservation

PR1330's missing optional report was identified in its still-unresolved review
thread `discussion_r4177312840`. This standing delivery records both original
topics without claiming to resolve that provider thread or close the PR.

Actual PR1334/current-dev `mu/tools/executors/commit_executor.py:4915-4932`
retains available stdout and stderr from `TimeoutExpired`, decodes byte streams
with `backslashreplace`, preserves long streams, prefixes the finite deadline
diagnostic and returns exit -1 / passed=False plus command/deadline metadata.
The original exact lifecycle selector remains 600 seconds, fleet 900 seconds,
ordinary selectors 240 seconds; mixed budgets sum with the caller floor.
Later Phase B's 600-second selector is an additional policy, not new R6 code.

`mu/tests/tools/test_commit_executor_post_merge_cleanup.py:270-320` covers
None, long byte/text, mixed invalid UTF-8, stdout-only and stderr-only streams.
Its public Step8b boundary controls at lines342-423 retain complete streams
through JSON transport, actual command/deadline diagnostics and fail-closed
outcomes while preventing commit/landing. This is demonstrated landed behavior
within those boundaries. It does not prove arbitrary process termination,
general recovery suppression or a fresh R6 execution of this test module.

## Original PR1330 topic 2: unchanged undersized-retry suppression remains OPEN

The separate recovery policy in `mu/tools/executors/recovery_gate.py:8895-8951`
keeps non-fleet caller deadlines; its delegate bounds the validator to 300
seconds at lines9148-9162. The verify/retry branches at lines9989-10055 can feed
a failed verification into another bounded iteration, or request retry after
applied work. Neither diagnostic hashes nor these branches establish general
suppression keyed by unchanged source, selectors and effective deadline.

Bounded acceptance for a separately authorized row40 repair: bind source/index,
exact command/selectors, effective finite budget and retained failure output.
An unchanged failed or undersized combination must HOLD without a second
identical invocation. A materially changed combination may enter only the
existing bounded path, with a newly recorded result. Public-boundary controls
must distinguish suppression from changed-input admission and preserve real
failures, empty collection, timeouts, prior receipts and consumed budgets.
No timeout inflation, rearm or exhausted replay is authorized by R6. The
historical R4 foreign-proof refusal and R19 timeout causes remain qualified;
this source reading does not establish their causes.

## PR1338 fixture lineage and its limits

Actual PR1339 retains the R5 selectors import, five-second foreign-child
readiness, positive release setup outside dispatcher error handling, distinct
owner proof injection, two-consumer diagnostic assertion and all three real
setup failure controls: readiness-timeout, early-exit and missing-owner.
Current `mu/tests/tools/test_phase_b_executor.py:726-770` asserts visible errors,
child reaping, closed stdout, observer restoration, zero actor calls and
unchanged protected files/index. Lines773-934 preserve all 23 consumer cases.

R3 subsequently changed the observation boundary at lines126-215 and829-835:
only the unchanged positive consumer retains fresh coherent OS observation;
every adverse callback restores the original observer before injection. This
explains the source difference from R5 without weakening the foreign-proof
negative assertion. PR1339's historical Linux failures remain preserved and
their original reaping/refusal causes are not retrospectively proved by a later
pass. R6 changes none of this executable source.

## Independent standing owners and required native stages

- Main actually synchronized to PR1339 and the previous lifecycle completed.
  The linked dev checkout's ownership synchronization remains HOLD under row40.
  Preserve transaction `df98e6b2f6a74d1699909ce0ae3a1e5c` and stash
  `4afaa4e7f9749e0c47f83c14ff94f06244fc5e70`; do not replay a stash or reset Main.
- Native pytest runner/R19 work remains preserved and unmerged, with its failed
  full-gate/timeout evidence and distinct import, scheduler, cancellation and
  owed source-bound validation obligations. R6 coverage does not land it.
- Retention integration, deduplication, usable capacity, verified preservation
  and empty-store restoration retain their own admission and review. Folder
  registration and physical/useful-work followups require their own current
  native authority. There is no physical archive purge or source retirement.
- Mu/Coinduction, paused PR1325, productivity, bisimulation, scheduler,
  stream-runtime and self-hosting obligations retain existing owners and order;
  Hemisphere's closed milestone, Phase8c and host debt are unchanged.
- Row40 retains native no-change CI retry prevention, late-review automation,
  coverage admission, xdist prerequisites, runner enforcement, false-idle
  attribution and monitor verification. Dead-pane product repair remains
  conditional on native reproduction. PR1339's shared watcher fixture landing
  does not complete all monitor or recovery obligations.
- Original1325/1329/1335/1336/1337 remain independently OPEN/owned at admission.
  PR1330 and PR1338 also remain OPEN until actual native disposition verifies.
  Retain every original branch, raw commit/tree closure, snapshot and failure.
- For R6, native outer owns tracker restoration, measured indicators, applicable
  generated growth-cap transition or exact no-op, actual indexed L4 and standing
  file handoff, independent review/precommit_inventory, full prepush, current-head
  CI, protected merge, separate Main sync and lane release. Only then may the
  operator use public lifecycle plan/apply/verify with the actual authority
  commit. No approval or closure is inferred from preservation or this report.

These independent obligations remain visible without making every unrelated
item a prerequisite for otherwise ready row38 coverage. The standing report
must survive native empty-findings cleanup and be included with these exact
bytes in the actual staged handoff; implementer validation records the former,
while the outer executor must record the latter.

Admission startup guard exited1 with three failures (docs registry/placement
and Codex-local binary/cache drift); attestation exited0. Neither is a fresh
all-green startup claim. R6 changes no local binary/cache/hooks/Claude surfaces,
backup implementation, production code or fixtures.
