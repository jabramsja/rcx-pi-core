# Wave Packet: except-narrow-hotfix-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

**HOTFIX for P1 safety regression landed in PR #789.**

PR #789 (`bot-findings-false-positive-fix-2026-04-17`, merged as `e67fd6fd`)
replaced the except block at `commit_executor.py:2103` to auto-defer bot
findings on ANY of 5 exception types from `_wait_for_bot_review_freshness`.

The bot posted a P1 on the PR (review `COMMENTED` state, NOT
`CHANGES_REQUESTED`, so commit_executor's step 15 merged past it):

> "In `mu/tools/executors/commit_executor.py`, this `except` now funnels
> `CalledProcessError`/`JSONDecodeError`/`ValueError` into the same
> auto-defer-and-continue path as `TimeoutError`. Those non-timeout errors
> include cases like `_assert_expected_pr_head` failing when the PR head
> changes, or GitHub query/request failures, so the function can `return
> None` and let merge continue without re-validating the current head/review
> state after remediation. This is a regression from the prior safe behavior
> (`bot_findings_pending`) and can merge unreviewed or newly changed code;
> auto-defer should be limited to true review-wait timeouts."

The bot is correct. This hotfix splits the except block.

## Scope

Control-surface / tooling + tests. 2 file edits + 1 wave packet.

**Files (3 total):**

- `mu/tools/executors/commit_executor.py` — split the except block at lines
  2103-2153. First branch `except TimeoutError as exc:` keeps the
  auto-defer path (the legitimate false-positive case). Second branch
  `except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
  json.JSONDecodeError, ValueError) as exc:` bails to `bot_findings_pending`
  with `review_wait_failure_class` tag so downstream recovery can
  distinguish state-uncertainty failures from timeouts.
- `mu/tests/tools/test_executor_dispatch.py` — add
  `test_35b_non_timeout_exceptions_still_bail_safely` verifying: (a)
  TimeoutError-only auto-defer branch exists, (b) separate non-timeout
  branch catches exactly the 4 remaining exception types, (c) the
  non-timeout branch does NOT call `_auto_defer_bot_findings`, (d)
  `review_wait_failure_class` tag is preserved.
- `reports/control_plane/except_narrow_hotfix_2026-04-17.md` — this packet.

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel,
projection, seed, runtime, or any `*.js` file.

## Separately-discovered gap (NOT fixed in this wave)

**Why did commit_executor's step 15 merge PR #789 despite the P1 review?**

The P1 was posted as a PR-level review with `state: COMMENTED` (not
`CHANGES_REQUESTED`) via `/pulls/789/reviews`. commit_executor's step 15
review detection apparently does not treat `COMMENTED` reviews with P1/P2
badges as blocking. This let the P1 merge unaddressed despite bot-remediation
being available.

This gap is DIFFERENT from the hotfix in this wave — this wave fixes the
safety regression. A follow-up wave should widen step 15's review detection
to recognize P1/P2 badges in COMMENTED reviews. Will file as a new blocking
deferred after this hotfix lands.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_executor_dispatch.py`
- **Evidence delta:**
  1. Splits the except block in `_attempt_bot_finding_remediation` at
     `commit_executor.py:2103` into TimeoutError-only (auto-defer) + other
     exceptions (bail-out with state-uncertainty tag).
  2. Adds `test_35b_non_timeout_exceptions_still_bail_safely` verifying the
     split via source-level assertions and regex — catches the P1 regression
     class mechanically.
  3. 330/330 tests in `test_executor_dispatch.py` pass (329 pre-existing +
     1 new).
- **Indicator artifact:** `reports/l4_wave_indicators/except-narrow-hotfix-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:except-narrow-hotfix-2026-04-17
  (founder flagged the bot comment in-session and asked "don't know if
  executor will catch it" — executor did NOT catch it, so this hotfix
  addresses the real P1 immediately while tracking the step-15 detection
  gap for a separate wave.)

## Verification Plan

1. Pre-push-fast: ratchet sweep + L4_ENABLER contract. Expected PASS.
2. Step 8b pytest on test_executor_dispatch.py: 330/330 must pass.

## Stop Conditions

- Abort if pre-push-fast fails.
- Abort if any pre-existing test regresses.

## Closeout

On merge, commit_executor step 16 cleans up worktree + branch. 3 remaining
pipeline-hardening deferreds stay open; 1 new to file:
- `recovery_gate_tier3_unactionable_exhaust_2026-04-17.md`
- `commit_executor_step16_cascade_block_2026-04-17.md`
- `pipeline_monitor_watcher_staleness_2026-04-17.md`
- `hybrid_recovery_inert_structural_gaps_2026-04-17.md` (3 sub-gaps)
- NEW (to file after this hotfix): `commit_executor_step15_commented_review_detection_2026-04-17.md`
