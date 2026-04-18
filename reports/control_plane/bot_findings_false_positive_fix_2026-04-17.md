# Wave Packet: bot-findings-false-positive-fix-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Close `reports/deferred/blocking/commit_executor_bot_findings_false_positive_2026-04-17.md`.

**Observed pattern (verified across PR #783 and PR #788 in session 2026-04-17):**
After commit_executor's step 15 pushes a bot-remediation commit and CI passes
on that commit, it requests a fresh bot review. The bot typically does not
respond within the 58-second wait window. `_wait_for_bot_review_freshness`
raises `TimeoutError`. The except block at `commit_executor.py:2103-2117`
bails out with `bot_findings_pending` — even though the remediation commit
was successful and CI green. Human operator has to manually
`bash mu/tools/hooks/merge_pr.sh <PR> --sweep` to unblock.

This wave lets the except block auto-defer the findings instead of bailing,
per policy `feedback_bot_comments_not_gates.md` ("Bot comments are signal,
not gates. Auto-defer, don't block next wave.").

## Scope

Control-surface / tooling + tests only. 3 file edits + 1 archive rename + 1
wave packet.

**Files (4 total):**

- `mu/tools/executors/commit_executor.py` — replace the except block at
  lines 2103-2117. On `TimeoutError` (or related) from
  `_wait_for_bot_review_freshness`, log the timeout, call
  `_auto_defer_bot_findings` (which writes
  `reports/deferred/non_blocking/pr<N>_bot_auto_deferred_<wave>.md` and
  resolves the GraphQL bot review threads), then return `None` (success path
  — caller proceeds to merge). If `_auto_defer_bot_findings` itself raises,
  fall back to `bot_findings_pending` with `review_wait_timeout: True` tag
  so downstream recovery can distinguish this sub-class.
- `mu/tests/tools/test_executor_dispatch.py` — add
  `test_35a_review_wait_timeout_triggers_auto_defer_before_bot_findings_pending`
  next to the existing `test_35_unresolved_bot_thread_returns_bot_findings`.
  Source-level test verifying (a) auto-defer call site exists in except
  block, (b) fall-back path with `review_wait_timeout` tag preserved. Matches
  the source-level pattern used by tests 34, 35, 36, 37.
- `reports/deferred/blocking/commit_executor_bot_findings_false_positive_2026-04-17.md`
  → archived as
  `reports/deferred/archive/commit_executor_bot_findings_false_positive_2026-04-17_CLOSED_by_PR_PENDING.md`
  (PR number resolved at commit time; convention accepts `_PR_PENDING` suffix
  when commit_executor lacks auto-rename).
- `reports/control_plane/bot_findings_false_positive_fix_2026-04-17.md` —
  this packet.

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel,
projection, seed, runtime, or any `*.js` file.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8 (enables reliable pipeline autonomy without manual
  `merge_pr.sh` intervention for bot-timeout false-positive cases)
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`
- **Evidence delta:**
  1. Replaces the except block at `commit_executor.py:2103-2117` with an
     auto-defer-first path: `_auto_defer_bot_findings` is invoked on
     `TimeoutError`/related exceptions from `_wait_for_bot_review_freshness`.
     On auto-defer success, returns `None` (merge proceeds). On auto-defer
     failure, falls back to `bot_findings_pending` with `review_wait_timeout`
     tag for recovery-gate classification.
  2. Adds `test_35a_review_wait_timeout_triggers_auto_defer_before_bot_findings_pending`
     in `test_executor_dispatch.py::TestPRAndReview` verifying the new except
     block shape at source level.
  3. Archives the closed blocking deferred
     `commit_executor_bot_findings_false_positive_2026-04-17.md` with
     `_CLOSED_by_PR_PENDING` suffix.
- **Indicator artifact:** `reports/l4_wave_indicators/bot-findings-false-positive-fix-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:bot-findings-false-positive-fix-2026-04-17
  (founder authorized in-session via "go ahead" directing the session's
  next Wave D to pick up the bot-findings-false-positive deferred as the
  highest-leverage fix — eliminating the manual `merge_pr.sh` pattern that
  forced intervention on PRs #783 and #788.)

## Verification Plan

1. Pre-push-fast: ratchet sweep + L4 contract enforcement. L4_ENABLER passes.
2. Step 8b targeted pytest on `test_executor_dispatch.py` — 329 tests (328
   pre-existing + 1 new) must PASS.

## Stop Conditions

- Abort if any pre-existing test_executor_dispatch.py test regresses.
- Abort if L4 contract rejects the classification.

## Live-Fire Test — This Wave Itself

This wave's own commit_executor run may encounter the SAME bot-review-timeout
pattern on its own PR. If so, the IN-FLIGHT wave will experience the OLD
behavior (bail-out to bot_findings_pending) because the fix hasn't landed
yet at the time phase_b/commit_executor runs. After merge, the NEXT wave
will be the first to benefit from auto-defer.

Observable: if this wave's commit_executor exits `bot_findings_pending` due
to review-wait-timeout, it's the same pattern we're fixing. The next wave
(e.g., recovery_gate_tier3_unactionable_exhaust fix) should land
autonomously without manual `merge_pr.sh`.

## Closeout

On merge, commit_executor step 16 runs post-merge cleanup. 3 remaining
pipeline-hardening deferreds stay open:
- `recovery_gate_tier3_unactionable_exhaust_2026-04-17.md`
- `commit_executor_step16_cascade_block_2026-04-17.md`
- `pipeline_monitor_watcher_staleness_2026-04-17.md`
- `hybrid_recovery_inert_structural_gaps_2026-04-17.md` (3 sub-gaps)
