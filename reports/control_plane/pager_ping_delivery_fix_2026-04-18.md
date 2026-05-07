Phase-A-Lock: PLACEHOLDER
# Phase A Plan: pager-ping-delivery-2026-04-18

wave_id: pager-ping-delivery-2026-04-18
Task: [PIPELINE-AGENT-PAGER]
Phase-A-Lock: LOCKED
Governing packet: reports/control_plane/pipeline_agent_pager_2026-04-16.md
Tracked packet entry: TASKS.md:194-200
## Status

Phase A Rev 3 (addresses bridge REQUEST_CHANGES round 2):
- Drops the prior stop-condition citation to `mu/tests/tools/test_pipeline_agent_pager.py:204-248` and `:252-302`. Those tests monkeypatch `pager_mod._dispatch_target` (lines 214, 238, 280, 291) and therefore never exercise `_dispatch_claude`. Basing a NO_OP closeout on them could miss a live claude-delivery defect.
- Re-grounds the NO_OP stop condition in a NEW integration regression test that reaches `_dispatch_claude` through the real dispatcher (patching only `pager_mod.subprocess.run`, NOT `pager_mod._dispatch_target`).
- Normalizes all acceptance pytest commands to the `PYTHONHASHSEED=0` form required by `tests/conftest.py:pytest_configure` (bare `python3 -m pytest` aborts with `RuntimeError: PYTHONHASHSEED must be '0' for deterministic tests, got None`).
Narrow, post-#796 convergence-budget live.

## 1. Scope

Files / paths in scope:
- `mu/tools/observability/pipeline_agent_pager.py`
- `mu/tests/tools/test_pipeline_agent_pager.py`
- `reports/deferred/non_blocking/` — write permitted only for the NO_OP close note under §4 (`pager_ping_delivery_2026-04-18.md` filename). Not permitted for any other reason in this wave.

## 2. Work items

Exercise the real claude-delivery path `_dispatch_pending_locked` → `_dispatch_target(target="claude", ...)` → `_dispatch_claude` in `mu/tools/observability/pipeline_agent_pager.py` (current-tree line ranges as of the 2026-05-07 docs-control-plane remediation: `_dispatch_claude` at `:1434-1481`, `_dispatch_target` at `:1496-1511`, `_dispatch_pending_locked` at `:1542-1635`) against the post-#795 / post-#796 code. Add exactly one new regression test to `mu/tests/tools/test_pipeline_agent_pager.py` that:

- Invokes `pager_mod.dispatch_pending_events(repo)` (or equivalently `pager_mod.emit_transition_event(repo, ...)` with `route="claude"`) so the real `_dispatch_pending_locked` and the real `_dispatch_target` are executed;
- Patches ONLY `pager_mod.subprocess.run` at the `_dispatch_claude` boundary (the same boundary already used by the existing direct `_dispatch_claude` contract tests at `:548-772`);
- Asserts post-dispatch state: `entry['delivered_targets']` contains `"claude"`, `entry['pending_targets']` is empty, and `run_mock.call_args.args[0]` is the deterministic claude argv (`["claude", "--resume", <session-id>, "-p", <prompt>]` when the `.agent_bus/observability/orchestrator_session_id` file exists, else `["claude", "-p", <prompt>]`).

If the new test FAILS on the current tree, a reproducible in-scope defect is confirmed — apply the minimum-complexity structural fix in `mu/tools/observability/pipeline_agent_pager.py` and make the test pass (FIX path, §5). If the new test PASSES on the current tree, no in-scope defect exists — close NO_OP with that test as the integration-path proof (NO_OP path, §5).

## 3. Constraints (NOT in scope)

No `ALLOWED_EVENT_TYPES` expansion. No new emit call sites. No mutation of runtime dirs (`mu/host/python/rcx_pi/selfhost/`). No mutation of any file outside the three paths listed in §1. The new regression test MUST NOT monkeypatch `pager_mod._dispatch_target` — monkeypatching the dispatcher is the exact pattern that masked claude-path coverage in prior tests (see `:204-248`, `:252-302` referenced in §Status) and is explicitly out of scope here. No new claim about `entry['attempts']` map semantics — the existing pager tests do not pin that map's contents and this wave does not widen that surface.

## 4. Stop conditions

STOP if root cause implicates any file outside §1.

STOP + close NO_OP if the new integration regression test described in §2 PASSES on the current tree AND a direct code read of the three ranges `mu/tools/observability/pipeline_agent_pager.py:1434-1481` (`_dispatch_claude`), `:1496-1511` (`_dispatch_target`), `:1542-1635` (`_dispatch_pending_locked`) confirms on current code that: (a) `_dispatch_target` routes `target == "claude"` to `_dispatch_claude`; (b) `_dispatch_claude` returns `acknowledged=True` with `ack["target"] == "claude"` on subprocess returncode 0 after building the `--resume <session-id>` / plain `-p` argv; (c) `_dispatch_pending_locked` records `entry['delivered_targets']['claude']` and clears `entry['pending_targets']` on a successful claude ack. The existing direct `_dispatch_claude` adapter tests pin argv construction and returncode handling; the new integration test at `mu/tests/tools/test_pipeline_agent_pager.py:1829-1867` closes the `_dispatch_pending_locked → _dispatch_target` integration gap that the dropped stop-condition citation failed to cover.

## 5. Acceptance criteria

Either:
- (Fix path) The new integration regression test in `mu/tests/tools/test_pipeline_agent_pager.py` FAILS on the pre-fix tree and PASSES on the post-fix tree, and `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py` exits 0 on the post-fix tree; OR
- (NO_OP path) The new integration regression test in `mu/tests/tools/test_pipeline_agent_pager.py` PASSES on the unchanged `mu/tools/observability/pipeline_agent_pager.py` tree. The NO_OP close note is archived at `reports/archive/deferred/pager_ping_delivery_2026-04-18_closed-by-deferred-report-truth-cleanup-2026-05-02.md` and contains: (a) the new test's function name and `mu/tests/tools/test_pipeline_agent_pager.py` file:line range; (b) the exact `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py::<test_name>` command run and its "1 passed" output; (c) the observed `entry['delivered_targets']`, `entry['pending_targets']`, and `run_mock.call_args.args[0]` values from that test; (d) a one-line statement that no in-scope defect was reproduced against `_dispatch_pending_locked → _dispatch_target → _dispatch_claude` on the current tree. `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_agent_pager.py` must exit 0 on the final tree. All pytest invocations in this acceptance section satisfy the repo's `tests/conftest.py:pytest_configure` deterministic-seed policy; bare `python3 -m pytest` invocations are NOT acceptable as proof, because they abort at configure-time with `RuntimeError: PYTHONHASHSEED must be '0' for deterministic tests, got None`.

## 6. Grounding / Authorization

TASKS.md:194-200 authorizes `[PIPELINE-AGENT-PAGER]` (QUEUED 2026-04-16, founder-directed post-merge follow-up) with `FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup` for the pager-slice family, governed by `reports/control_plane/pipeline_agent_pager_2026-04-16.md`.

Class: MAINTENANCE (per TASKS.md:198 "MAINTENANCE wave" wording in the 2026-04-17 fold-in). If the §2 regression test reveals a defect and a pager fix is applied, the commit handoff reclassifies per `.claude/rules/l4-contract.md`; the Phase A default against the NO_OP stop condition is MAINTENANCE.
target_gate_id: G8.
no_op_proof: no runtime files changed; the pager source is observability tooling at `mu/tools/observability/` (outside `mu/host/python/rcx_pi/selfhost` runtime dir) and the in-scope test addition lives under `mu/tests/tools/` which is non-runtime.
defer_reason_code: TOOLING_FOLLOWUP.
primary_blocker_class: INTEGRATION.
primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION.
indicator_artifact_ref: reports/l4_wave_indicators/pager-ping-delivery-2026-04-18.json.
indicator_collection_command: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pager-ping-delivery-2026-04-18 --output reports/l4_wave_indicators/pager-ping-delivery-2026-04-18.json.
bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
boot0_track_id: V1.
boot0_progress_state: HOLD.
FOUNDER_OVERRIDE:pipeline-agent-pager-2026-04-17-followup.
