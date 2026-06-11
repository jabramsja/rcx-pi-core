# Monitor Default Autofollow Bus Resolver Narrow 2026-06-10 2026-06-10

Date: 2026-06-10
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: monitor-default-autofollow-bus-resolver-narrow-2026-06-10
Phase-A-Lock: LOCKED
Purpose: GOAL: Make the DEFAULT pipeline_monitor.sh monitor's PANES auto-follow the freshest active lane bus, by re-resolving the (worktree_root, bus_dir) pair on EACH pane refresh -- exactly the way the panes ALREADY re-resolve the worktree_root inside their refresh loop -- WITHOUT changing the monitor's owner-process lifecycle, its tmux session rebuild, or introducing any persistent auto-follow state. This is a deliberately NARROW re-scope of a prior wave that DIVERGED by pulling the owner/session lifecycle into scope.

## Governing request (Post-Merge Supervisor)

GOAL: Make the DEFAULT pipeline_monitor.sh monitor's PANES auto-follow the freshest active lane bus, by re-resolving the (worktree_root, bus_dir) pair on EACH pane refresh -- exactly the way the panes ALREADY re-resolve the worktree_root inside their refresh loop -- WITHOUT changing the monitor's owner-process lifecycle, its tmux session rebuild, or introducing any persistent auto-follow state. This is a deliberately NARROW re-scope of a prior wave that DIVERGED by pulling the owner/session lifecycle into scope.

CONTEXT (verified by reading the code): `tools/observability/_resolve_live_root.sh` re-resolves the freshest active worktree_root on each call but for a FIXED bus (`RCX_AGENT_BUS_DIR` / `BUS_DIR`, default `.agent_bus`); its `worktree_score` scores each linked worktree by the mtime of pipeline-activity files under that ONE bus, and it emits ONLY the resolved root (`printf '%s\n' "$BEST_ROOT"`). In `tools/observability/pipeline_monitor.sh`, `rebuild_tmux_session` bakes the fixed `BUS_DIR` into each pane command ONCE at launch and then execs a long-running pane script. **The per-refresh loop lives INSIDE those pane scripts:** `_pane_findings.sh`, `_pane_processes.sh`, and `_pane_timeline.sh` each initialize `BUS_DIR` ONCE near the top, then -- inside their `refresh_context()` (`while true`) loop -- re-resolve only the ROOT via `_resolve_live_root.sh`; the bus stays fixed for the life of the pane process. So the default monitor (`BUS_DIR=.agent_bus`, no `--lane`, `IDENTITY_LANE=default`) never follows a lane wave running under a `.agent_bus-laneN` bus. **The fix therefore belongs where the root re-resolution already lives -- inside each pane script's `refresh_context()` -- NOT in the one-shot pane command** (bridge rev2: the prior plan tried to make the launch command "dynamic per refresh," which is mechanically impossible because the command runs once).

Routed next-candidate: `monitor-default-autofollow-bus-resolver-narrow-2026-06-10`.

The actionable fix, fail-safe rule, constraints, and proof live in the structured sections below (Work items / Constraints / Stop conditions / Acceptance criteria). Where the original numbered request prose and these sections differ, **these sections are authoritative** (current bridge rev corrected the lane-selection rule, relocated the per-refresh bus rebind into the pane refresh loops, and corrected the proof scope).

## Scope (files / directories in scope)

Edit ONLY these paths:

- `tools/observability/_resolve_live_root.sh` -- add the OPT-IN pair-mode flag (WI-1).
- `tools/observability/pipeline_monitor.sh` -- add the DEFAULT-monitor autofollow SIGNAL to the pane commands in `rebuild_tmux_session` (WI-2).
- `tools/observability/_pane_findings.sh` -- per-refresh bus rebinding in `refresh_context()` + main-guard the `while true` driver (WI-2B).
- `tools/observability/_pane_processes.sh` -- per-refresh bus rebinding in `refresh_context()` + main-guard the `while true` driver (WI-2B).
- `tools/observability/_pane_timeline.sh` -- per-refresh bus rebinding in `refresh_context()` + main-guard the `while true` driver (WI-2B).
- `mu/tests/tools/test_pipeline_monitor_autofollow.py` -- the single NEW proof test (WI-4).
- `mu/tests/docs/test_growth_caps.py` -- CONDITIONAL ONLY: if the new tracked test file trips a growth cap, bump the matching `CAP_TEST_FILES` / `CAP_TOOL_SCRIPTS` by +1 with an inline comment citing this wave + FOUNDER_OVERRIDE (WI-5).

(`tools` is a symlink to `mu/tools`; the three `_pane_*.sh` scripts above are real files under `tools/observability/`. None of these paths is a runtime dir.)

L4 class: L4_ENABLER, tooling-only (control-surface observability). No runtime dir is in scope.

## Work items (concrete, bounded)

- **WI-1 -- resolver opt-in pair mode.** Extend `_resolve_live_root.sh` with an OPT-IN flag that emits the freshest active `(worktree_root, bus_dir)` PAIR across `.agent_bus` plus every `.agent_bus-laneN` bus present in any linked worktree, REUSING the existing `worktree_score` activity-file scoring AS-IS (no new liveness sources, no new scoring inputs, no new state). The existing no-flag invocation behavior stays UNCHANGED for all current callers (prints only the resolved root for the fixed bus).

- **WI-2 -- default-monitor autofollow signal (in `rebuild_tmux_session`).** In `pipeline_monitor.sh rebuild_tmux_session`, for the DEFAULT monitor ONLY (no `--lane`, `IDENTITY_LANE=default`, `BUS_DIR=.agent_bus`), add a single STATIC opt-in signal env var (`RCX_OBS_AUTOFOLLOW_BUS=1`) to the pane-2/3/4 commands, alongside the existing `BUS_DIR=.agent_bus`/`RCX_AGENT_BUS_DIR=.agent_bus` seed and the existing `RCX_OBS_*` vars. This signal is a launch-time FLAG (an ephemeral env var, exactly like the existing `RCX_PIPELINE_MONITOR_LANE` / `RCX_OBS_ROOT_HELPER` vars already passed in those commands) -- it is NOT a persisted target/state file, and `rebuild_tmux_session` does NOT itself resolve the bus per refresh (a pane command runs ONCE). It only ENABLES the per-refresh re-resolution that WI-2B performs inside the pane scripts. Pinned monitors (launched with an explicit `--lane` or `--bus-dir`) do NOT receive the signal: their pane commands keep the fixed bus and behave exactly as today.

- **WI-2B -- pane-script refresh-loop bus rebinding (the per-refresh fix the bridge finding requires).** In EACH of the three pane scripts -- `_pane_findings.sh`, `_pane_processes.sh`, `_pane_timeline.sh` -- extend the existing `refresh_context()` (the function already called on every `while true` iteration, which ALREADY re-resolves the root) so that, WHEN `RCX_OBS_AUTOFOLLOW_BUS=1` is set, it resolves the freshest `(root, bus)` PAIR via the WI-1 opt-in helper (the same co-located `_resolve_live_root.sh` the pane already uses for root resolution, invoked with the WI-1 opt-in flag) and rebinds the in-loop EFFECTIVE bus -- i.e. updates the `BUS_DIR` value used to build `RAW_DIR`/`BUS` and re-exports `BUS_DIR`/`RCX_AGENT_BUS_DIR` for child helpers -- using the helper's root AND bus together so the pair stays consistent. When the signal is UNSET (pinned monitors, or default-off), `refresh_context()` keeps today's behavior EXACTLY: root via the no-flag `resolve_repo_root()`, bus fixed at the top-of-script value. **Fail-safe (no masking):** if the opt-in helper emits empty or invalid output (not `.agent_bus` or `.agent_bus-<id>`), keep the CURRENT bus -- never blank it, never error the pane, never weaken the existing bus-path validation. The top-of-script initial `BUS_DIR` init + path validation stay AS-IS. Guard the trailing `while true` driver behind a main-guard (`[[ "${BASH_SOURCE[0]}" == "$0" ]]`) so `refresh_context()` can be invoked in isolation by the WI-4 test WITHOUT changing the runtime behavior of `bash _pane_*.sh` (the guard only prevents the infinite loop from running on `source`).

- **WI-3 -- fail-safe lane-selection rule (FIXED; no tunable margin, no state file): UNIQUE STRICT-MAX across ALL candidate buses.** Score every candidate bus = `.agent_bus` plus each `.agent_bus-laneN` present in any linked worktree, using the existing `worktree_score`. Determine the single highest score across that whole set. Emit a lane's `(root, bus)` ONLY when the unique strict maximum is held by a `.agent_bus-laneN` bus -- that is, exactly one bus has the top score AND its score is strictly greater than EVERY other candidate, including `.agent_bus`, with no other bus tying it. In EVERY other case return `.agent_bus` with the current root (existing default behavior): when `.agent_bus` holds the maximum (greatest-or-equal), when the top score is TIED among two or more buses (no unique strict max), when any input is missing/unreadable, or on any error. This is a single unique-strict-max-or-default rule. It deliberately resolves the multi-lane case: when two (or more) `.agent_bus-laneN` buses are simultaneously above `.agent_bus`, the freshest one (the unique strict max) is followed -- only a tie AT THE TOP falls back to `.agent_bus`. (Bridge rev1: replaces the prior "exactly one bus strictly greater than `.agent_bus`" wording, which wrongly fell back to default whenever two lanes both beat default and thus contradicted the freshest-active-lane goal.)

- **WI-4 -- single proof test.** Add ONE new test at exactly `mu/tests/tools/test_pipeline_monitor_autofollow.py`, run under `PYTHONHASHSEED=0`, covering the WI-1/WI-3 resolver opt-in pair mode, the WI-2 default/pinned signal wiring, AND the WI-2B pane-script per-refresh bus rebinding (the actual rebind the bridge finding required). Exact cases in Acceptance criteria.

- **WI-5 -- conditional growth-cap bump.** If this new tracked test file (or any new tracked tool/test file) trips `mu/tests/docs/test_growth_caps.py`, bump the matching `CAP_TEST_FILES` / `CAP_TOOL_SCRIPTS` by +1 with an inline comment citing this wave and FOUNDER_OVERRIDE. (The three pane scripts are EDITED, not added, so they should not trip `CAP_TOOL_SCRIPTS`; only the one new test file is expected to matter.) Do nothing here if no cap trips.

## Constraints (NOT in scope)

- **EXPLICITLY OUT OF SCOPE (caused the prior divergence -- do NOT touch):** the owner-loop process lifecycle (`cmd_owner_loop` / `ensure_owner_running` / owner replacement / `stop_wrong_root_owner_processes`); any tmux session rebuild triggered by a bus change; any persistent auto-follow state or target file; any new "pair-mode" / "autofollow target" / "ensure-session" helper or function; the pane-1 live-log watcher (`/tmp/rcx_log_watcher.sh` / `write_log_watcher`) and its tail loop; and the pinned `--lane` / `--bus-dir` monitors. The owner process and tmux session lifecycle stay EXACTLY as-is; ONLY the per-refresh bus binding of the DEFAULT monitor's panes 2-4 becomes dynamic.
- The `RCX_OBS_AUTOFOLLOW_BUS` signal is an EPHEMERAL launch-time env var (like the existing `RCX_PIPELINE_MONITOR_LANE` / `RCX_OBS_ROOT_HELPER`), NOT a persistent auto-follow state/target file. No file is written to track the followed bus.
- Runtime behavior of `bash _pane_*.sh` MUST be unchanged for pinned/default-off monitors, and the added main-guard must NOT change behavior when the script is run normally (`$0 == BASH_SOURCE`) -- it only suppresses the infinite loop when the script is `source`d by the test.
- MUST NOT touch any runtime dir: `mu/host`, `mu/substrate`, `mu/closures`, `mu/bridge`, `mu/programs`, `rcx_pi/selfhost`, `mu/tools/compilers`.
- Keep the existing no-flag `_resolve_live_root.sh` behavior UNCHANGED for all current callers (prints only the resolved root for the fixed bus).
- No new liveness sources, scoring inputs, state files, or tunable margin -- reuse `worktree_score` as-is.
- No masking: no retry / skip / xfail; do not weaken any existing test or any existing bus-path validation.

## Stop conditions

- STOP and treat as out-of-scope if correctly following the active lane appears to require an owner-loop or tmux-session lifecycle change (the panes re-resolving the bus inside their own refresh loop is sufficient for the display to follow).
- STOP if making `refresh_context()` invokable in isolation would require more than guarding the `while true` driver behind a main-guard (e.g. a structural rewrite of the pane scripts) -- that exceeds the narrow scope.
- STOP if the fix would require a new liveness source, new scoring input, a state/target file, or a tunable margin.
- STOP if any runtime dir would be touched (would reclassify the wave out of L4_ENABLER tooling-only).
- STOP if a current no-flag caller of `_resolve_live_root.sh` would change behavior, or if a pinned/default-off pane's runtime behavior would change.
- Phase A ends at a bridge-converged plan; do NOT implement the fix in this Phase A turn.

## Acceptance criteria

The single proof file `mu/tests/tools/test_pipeline_monitor_autofollow.py` passes under `PYTHONHASHSEED=0` and asserts ALL of the following.

**Resolver opt-in pair mode** -- drive `_resolve_live_root.sh` opt-in flag via subprocess over a synthetic temporary git repo with linked worktrees:

- A1: one `.agent_bus-laneN` bus with a STRICTLY-greater `worktree_score` than `.agent_bus` -> emits that lane's `(root, bus)`.
- A2: **two `.agent_bus-laneN` buses BOTH strictly greater than `.agent_bus`, one of them the unique strict maximum -> emits the unique-strict-max lane's `(root, bus)`** (the freshest active lane; directly exercises the WI-3 multi-lane rule).
- A3: two lane buses TIED at the top above `.agent_bus` (no unique strict max) -> emits `.agent_bus` with the current/default root.
- A4: `.agent_bus` greatest-or-equal -> emits `.agent_bus` with the current/default root.
- A5: a single lane TIED with `.agent_bus` -> emits `.agent_bus` with the current/default root.
- A6: missing / unreadable / absent lane bus -> emits `.agent_bus` with the current/default root.
- A7: the no-flag invocation prints ONLY the resolved root for the fixed bus (legacy caller behavior unchanged).

**Default-monitor autofollow wiring** -- exercise `pipeline_monitor.sh rebuild_tmux_session` with `tmux` stubbed (a recording shim on `PATH`; NO real tmux), capturing the pane command strings:

- B1: for the DEFAULT monitor (no `--lane`, `IDENTITY_LANE=default`, `BUS_DIR=.agent_bus`), each captured pane-2/3/4 command sets the autofollow signal `RCX_OBS_AUTOFOLLOW_BUS=1` and still seeds `BUS_DIR=.agent_bus`/`RCX_AGENT_BUS_DIR=.agent_bus` -- proving WI-2 ENABLES autofollow without trying to bake a dynamic bus into the one-shot command.
- B2: for a PINNED monitor (explicit `--lane` or `--bus-dir`), NO captured pane command sets `RCX_OBS_AUTOFOLLOW_BUS`; each retains its explicit fixed bus -- proving pinned monitors remain unchanged.

**Pane-script per-refresh bus rebinding** -- for EACH of the three pane scripts (`_pane_findings.sh`, `_pane_processes.sh`, `_pane_timeline.sh`), drive `refresh_context()` in isolation: source the script from a synthetic temp dir that ALSO contains a stub `_resolve_live_root.sh` (so `$SCRIPT_DIR`'s helper is the stub) over a synthetic temp git repo, seed a valid `BUS_DIR=.agent_bus`, let the main-guard suppress the `while true` driver, call `refresh_context` once, and inspect the resulting bus binding (`RAW_DIR` for findings/timeline, `BUS` for processes):

- B3: signal SET (`RCX_OBS_AUTOFOLLOW_BUS=1`) and the stub opt-in helper reports a `.agent_bus-laneN` bus as the unique strict max -> `refresh_context` rebinds the effective bus to that lane bus (`RAW_DIR`/`BUS` now under `.agent_bus-laneN`) and re-exports `BUS_DIR`/`RCX_AGENT_BUS_DIR` -- the actual per-refresh rebind the bridge finding required, proven for all three panes.
- B4: signal UNSET -> `refresh_context` keeps the fixed `.agent_bus` binding regardless of helper output -- proving pinned/default-off panes never drift off `.agent_bus`.
- B5: signal SET but the stub helper emits empty/invalid output -> `refresh_context` keeps the current bus (pane not blanked, not errored) -- proving the fail-safe with no masking.

**Gate:** the tracker `evidence_command` is green and no out-of-scope surface changed:

- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pipeline_monitor_autofollow.py`
- No runtime dir touched; no existing test weakened; no existing bus-path validation weakened; no owner/session lifecycle change; pane-1 watcher untouched; no new state/target file; existing no-flag `_resolve_live_root.sh` callers unaffected; pinned monitors unchanged.

## Grounding / Authorization

- **TASKS.md authorization:** TASKS.md tracker sync note (2026-06-10) for `[NEXT-CODEX-POST-REDTEAM]`, wave `monitor-default-autofollow-bus-resolver-narrow-2026-06-10` -- Class `L4_ENABLER`, `target_gate_id: G8`, Packet `reports/control_plane/monitor_default_autofollow_bus_resolver_narrow_2026-06-10_2026-06-10.md`, `evidence_command: PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_pipeline_monitor_autofollow.py`.
- **Governing packet:** this file (the routed next-candidate `monitor-default-autofollow-bus-resolver-narrow-2026-06-10`).
- **Same-wave override (mechanically derivable by commit automation):**
  FOUNDER_OVERRIDE:monitor-default-autofollow-bus-resolver-narrow-2026-06-10
- **Authorization:** wave-bound founder override above, carried in the canonical TASKS.md tracker sync note for this wave; standing control-plane / pipeline-tooling fix authorization for this L4_ENABLER. Mechanical-gate bypass / force-merge are NOT authorized here.

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/monitor-default-autofollow-bus-resolver-narrow-2026-06-10.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id monitor-default-autofollow-bus-resolver-narrow-2026-06-10 --output reports/l4_wave_indicators/monitor-default-autofollow-bus-resolver-narrow-2026-06-10.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_pipeline_monitor_autofollow.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/monitor_default_autofollow_bus_resolver_narrow_2026-06-10_2026-06-10.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: monitor-default-autofollow-bus-resolver-narrow-2026-06-10.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `monitor-default-autofollow-bus-resolver-narrow-2026-06-10`
- Active packet: `reports/control_plane/monitor_default_autofollow_bus_resolver_narrow_2026-06-10_2026-06-10.md`
- Indicator artifact: `reports/l4_wave_indicators/monitor-default-autofollow-bus-resolver-narrow-2026-06-10.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/_pane_findings.sh`
  - `mu/tools/observability/_pane_processes.sh`
  - `mu/tools/observability/_pane_timeline.sh`
  - `mu/tools/observability/_resolve_live_root.sh`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/monitor_default_autofollow_bus_resolver_narrow_2026-06-10_2026-06-10.md`
  - `reports/l4_wave_indicators/monitor-default-autofollow-bus-resolver-narrow-2026-06-10.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `monitor-default-autofollow-bus-resolver-narrow-2026-06-10`
- Active packet: `reports/control_plane/monitor_default_autofollow_bus_resolver_narrow_2026-06-10_2026-06-10.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `5baa96d04052c8b160ebcbd2fb9e8a534484950b0f0b624e0bed92d237283fa9`
- Indicator artifact: `reports/l4_wave_indicators/monitor-default-autofollow-bus-resolver-narrow-2026-06-10.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/docs/test_growth_caps.py mu/tests/tools/test_pipeline_monitor_autofollow.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/monitor_default_autofollow_bus_resolver_narrow_2026-06-10_2026-06-10.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/monitor-default-autofollow-bus-resolver-narrow-2026-06-10.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/_pane_findings.sh`
  - `mu/tools/observability/_pane_processes.sh`
  - `mu/tools/observability/_pane_timeline.sh`
  - `mu/tools/observability/_resolve_live_root.sh`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/monitor_default_autofollow_bus_resolver_narrow_2026-06-10_2026-06-10.md`
  - `reports/l4_wave_indicators/monitor-default-autofollow-bus-resolver-narrow-2026-06-10.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
