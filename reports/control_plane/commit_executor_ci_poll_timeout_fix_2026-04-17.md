# Wave Packet: commit-executor-ci-poll-timeout-fix-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Close `reports/deferred/blocking/commit_executor_step15_ci_poll_timeout_2026-04-17.md`.

`commit_executor.py`'s fallback CI-poll at step 15 uses a hardcoded 300s timeout
budget. On observation (PR #783, 2026-04-17), green-gate takes up to 5m7s = 307s
after a bot-remediation push — exceeding the 300s budget and causing the
executor to false-positive classify "CI failed after remediation round 1" when
CI actually passes shortly after. This cascades into Tier 3 recovery exhaust
and an unmergeable PR despite all checks green.

This wave adopts **structural fix candidate 1** (bump polling budget from
300 → 900s at all 3 call sites). Candidate 2 (authoritative state fallback)
and candidate 3 (externalize to config) are deferred as follow-up waves —
candidate 1 is the minimal structural fix that closes the immediate failure
mode, matches the observed wall-time max with 3× headroom, and requires zero
new config keys.

## Scope

Control-surface / tooling-tests only. 2 file edits + 1 archive move + 1 wave
packet.

**Files (4 total):**

- `mu/tools/executors/commit_executor.py` — bump the `_poll_ci_checks_fallback`
  default timeout from `300` → `900` at the function signature (line 1616) AND
  at both call sites (line 2077 in the first remediation round's CI-wait and
  line 2923 in the second remediation round's CI-wait). No other signature or
  control-flow changes.
- `mu/tests/tools/test_commit_executor_receipt.py` — add regression test
  `test_ci_poll_fallback_tolerates_green_gate_wall_time_over_5_minutes` that
  patches `time.time()` / `time.monotonic()` so the test clock advances from
  `t=0` through `t=400` while the polling loop runs. Assert that the fallback
  does NOT time out at 400s (previously would have at 300s) and returns the
  "CI passed" result when `gh pr view --json statusCheckRollup` shows all
  checks passing at t≥350s. A second test case
  `test_ci_poll_fallback_still_times_out_at_new_budget` patches the clock to
  advance past 900s without CI completion, and asserts the fallback correctly
  returns False.
- `reports/deferred/blocking/commit_executor_step15_ci_poll_timeout_2026-04-17.md`
  → archived as
  `reports/deferred/archive/commit_executor_step15_ci_poll_timeout_2026-04-17_CLOSED_by_PR<N>.md`
  (the closing PR number is determined at commit time by `commit_executor`).
- `reports/control_plane/commit_executor_ci_poll_timeout_fix_2026-04-17.md` —
  this packet.

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel, projection,
seed, runtime, or any file outside `mu/tools/executors/commit_executor.py` +
`mu/tests/tools/test_commit_executor_receipt.py` + the above reports entries.

## Implementation Guidance

Read `mu/tools/executors/commit_executor.py:1610-1680` for the
`_poll_ci_checks_fallback` function and its 300s default. Read lines `2070-2085`
and `2915-2930` for the two call sites. Bump each literal `300` in those three
locations to `900`. Leave the log message format alone (it already prints
`{timeout}s` so it will naturally render "900s").

For the regression test, model after existing patterns in
`mu/tests/tools/test_commit_executor_receipt.py`: use `monkeypatch` to patch
`commit_mod.time.monotonic` with a controllable clock, patch `subprocess.run`
on the gh call to return canned output. The test file has existing monkeypatch
fixtures that can be reused.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8 (enables reliable commit-push-merge pipeline for future
  hardening + evidence waves)
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`
- **Evidence delta:**
  1. Bumps `_poll_ci_checks_fallback` default timeout at `commit_executor.py:1616`
     from `300` to `900` and propagates to the 2 call sites at `:2077` and
     `:2923`. Closes the observed green-gate > 300s false-positive timeout
     documented in PR #783 wave cascade.
  2. Adds regression test in `test_commit_executor_receipt.py` that simulates
     green-gate wall time of 400s (past old 300s budget) and asserts the
     fallback does not incorrectly time out. Adds a companion test asserting
     the new 900s budget DOES time out when CI genuinely stalls beyond that.
  3. Archives the closed blocking deferred
     `commit_executor_step15_ci_poll_timeout_2026-04-17.md` with the
     `_CLOSED_by_PR<N>` suffix.
- **Indicator artifact:** `reports/l4_wave_indicators/commit-executor-ci-poll-timeout-fix-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:commit-executor-ci-poll-timeout-fix-2026-04-17
  (founder authorized this wave in-session via "yep" confirming it as the
  next substantive wave + the first live-fire test of the just-enabled
  pipeline_agent_pager + hybrid_recovery + claude-as-implementer chain
  landed in PR #786.)

## Verification Plan

1. Pre-push-fast runs ratchet sweep + `enforce_l4_execution_contract.py` on
   L4_ENABLER class. Expected PASS (no runtime paths touched).
2. Step 8b targeted pytest runs
   `test_commit_executor_receipt.py` — new regression tests must PASS.
3. Phase B bridge review (Codex as reviewer) should converge on "no blocking
   findings" since scope is narrow (3 literal bumps + 2 new test cases).

## Stop Conditions

- Abort if `enforce_l4_execution_contract.py` rejects the L4_ENABLER
  classification.
- Abort if targeted pytest fails (new tests must pass, existing tests must
  not regress).
- Abort if Phase B bridge review returns blocking findings on the structural
  approach (if reviewer prefers candidate 2/3 over candidate 1, defer to next
  wave — do not re-architect in-line).

## Live-Fire Observations for This Wave

Because PR #786 just enabled pipeline_agent_pager + hybrid_recovery + switched
implementers to Claude Opus 4.7 max, this wave is the first live test:

- **Phase B implementer invocation** should appear in phase_b scratch logs with
  the claude adapter (`--model claude-opus-4-7 --effort max`), not the codex
  adapter.
- **Pager events** should emit to `.agent_bus/observability/pipeline_agent_events.jsonl`
  at `phase_b_reviewer_started` and `commit_ready` boundaries (and any
  `recovery_*` events if Tier 3 fires).
- **Hybrid recovery delegation** path at `recovery_gate.py:2939` should be
  available (no longer short-circuited at `:2950-2956`).

## Closeout

On merge, commit_executor step 16 runs post-merge cleanup. The next wave can
pick up any of the remaining 3 hardening deferreds (bot-findings false
positive, tier-3 unactionable exhaust, step 16 cascade-block).
