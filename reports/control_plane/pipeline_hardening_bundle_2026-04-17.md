# Wave Packet: pipeline-hardening-bundle-2026-04-17

## Status: Phase B (locked, implementing)

## Goal

Close one of the four hybrid-recovery inertness gaps discovered in PR #787's
phase_b run — the MISSING_BRIDGE_CONFIG chicken-and-egg — with a deterministic
Tier 1 classifier + fixer in `recovery_gate.py`. File a consolidated deferred
blocking doc for the remaining 3 gaps (files_in_scope whitelist, phase_b
stderr swallow, recovery trigger conditions) so they're tracked for
subsequent small waves.

**Background:** PR #786 enabled `hybrid_recovery_enabled: true` and switched
implementers to Claude Opus 4.7 max. PR #787 was the first live-fire test.
Observed that the recovery agent escalated instead of delegating because (a)
recovery itself couldn't bootstrap when `bridge_config.json` was missing, (b)
scope whitelist was too narrow to repair the failing files, (c) phase_b
swallowed claude's real stop_reason, (d) recovery trigger conditions were too
narrow. This wave fixes (a) and files (b)(c)(d) as blocking deferreds.

## Scope

Control-surface / pipeline tooling + tests + deferred docs. 4 files.

**Files (4 total):**

- `mu/tools/executors/recovery_gate.py` — adds `FailureClass.MISSING_BRIDGE_CONFIG`
  (Tier 1), classifier pattern matching "bridge config not found", deterministic
  `fix_missing_bridge_config()` function that walks from worktree `.git` pointer
  to main repo and copies `bridge_config.json`, and registers the fixer in
  `_TIER1_FIXES`. No LLM involvement — pure deterministic file copy.
- `mu/tests/tools/test_recovery_gate.py` — adds 3 classifier tests (stderr +
  error field + tier mapping) and 4 fixer tests (noop-when-present,
  noop-when-not-worktree, happy-path-copy, error-when-main-has-no-config) in
  new `TestFixMissingBridgeConfig` class. Also updates existing
  `test_all_classes_mapped_and_tier1_tier4_correct` to include the new class
  in the expected Tier 1 set.
- `reports/deferred/blocking/hybrid_recovery_inert_structural_gaps_2026-04-17.md`
  — NEW deferred doc consolidating the 3 remaining hybrid-inertness gaps with
  root causes, evidence, structural fix candidates, and acceptance criteria.
- `reports/control_plane/pipeline_hardening_bundle_2026-04-17.md` — this
  packet.

**Files NOT touched:** any `mu/host/**`, `rcx_pi/selfhost/**`, kernel,
projection, seed, runtime, or any `*.js` file.

## L4 Contract Fields

- **Class:** L4_ENABLER
- **Target gate:** G8 (enables hybrid recovery to eventually self-heal the
  pipeline-infra failure classes that currently require human intervention)
- **Primary blocker class:** INTEGRATION
- **Primary invariant:** INV_STRUCTURAL_FORWARD_MOTION
- **Evidence command:** `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_recovery_gate.py`
- **Evidence delta:**
  1. Adds `FailureClass.MISSING_BRIDGE_CONFIG` as Tier 1 classifier at
     `recovery_gate.py` matching "bridge config not found" in stderr / error /
     detail / message / combined text.
  2. Implements `fix_missing_bridge_config()` — deterministic, no LLM,
     mirrors the pattern of `fix_stale_bridge_lock` + `commit_executor.py`
     step-15 auto-heal. Walks the linked worktree's `.git` pointer file to
     locate the main repo, copies `.agent_bus/bridge_config.json` from main
     into worktree.
  3. Adds 7 regression tests (3 classifier + 4 fixer branches). Existing
     tier-mapping test updated.
  4. Files consolidated blocking deferred for the 3 remaining hybrid-inertness
     gaps (whitelist, phase_b stderr, recovery trigger) with root causes,
     evidence, and acceptance criteria for follow-up waves.
- **Indicator artifact:** `reports/l4_wave_indicators/pipeline-hardening-bundle-2026-04-17.json`
- **Bootstrap endgame policy:** SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP
- **Boot0 track:** V1 / HOLD
- **Founder override:** FOUNDER_OVERRIDE:pipeline-hardening-bundle-2026-04-17
  (founder authorized in-session via "all of these may be good for a very
  soon wave" + "put that in the next wave" directing that the hybrid-inertness
  gaps be addressed as the wave after PR #787 merges.)

## Verification Plan

1. Pre-push-fast: ratchet sweep + `enforce_l4_execution_contract.py` on
   L4_ENABLER class. Expected PASS.
2. Step 8b targeted pytest on `test_recovery_gate.py` — 847 tests (840
   pre-existing + 7 new) must PASS.
3. No Phase B bridge review (standalone commit_executor path).

## Stop Conditions

- Abort if any pre-existing recovery_gate test regresses.
- Abort if tier-mapping assertion changes semantic (e.g., unexpected class
  demotion).

## Live-Fire Value

Before this wave:
- Phase B running in a fresh worktree without `bridge_config.json` fails at
  implementer invocation. Recovery tier-3 tries to help but can't —
  bridge_config is also required for the recovery agent itself. Tier 3
  exhausts in <50ms per iteration. Manual intervention (`cp` from main
  repo) required.

After this wave:
- Phase B (or any executor) failing with "Bridge config not found at" is
  classified as Tier 1 MISSING_BRIDGE_CONFIG. Deterministic fixer copies the
  config from main repo into the worktree. Retry proceeds normally. Zero
  LLM tokens consumed. Zero human intervention required.

## Closeout

On merge, commit_executor step 16 runs post-merge cleanup. The deferred doc
`hybrid_recovery_inert_structural_gaps_2026-04-17.md` remains open for the
3 follow-up waves (one per gap, ~30-100 LOC each). The original 4 hardening
deferreds from PR #785 continue to track their individual fix waves.
