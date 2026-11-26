# WorkingRCX tmux Pane Exec Identity R3 2026-11-26

Date: 2026-11-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-tmux-pane-exec-identity-r3-2026-11-26
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 89fc74faf91f09c5bf25795a6997a40cb085327cdf800d03f5e41f203fd07853
Purpose: Resolve the BLOCKING finding in reports/deferred/blocking/tmux-pane-wrapper-shell-identity-2026-11-26.md. tmux runs each monitor pane command as $SHELL -c; every pane command in pipeline_monitor.sh is a compound cd/unset list ending in an un-exec'd bash <script>. Under macOS bash 3.2 (the founder login shell) the last command of an && list is not exec'd, so a bash -c wrapper remains as pane_pid while the watcher runs as its child; worktree_lifecycle _adopt_terminal_log_readers requires pane_pid == reader pid exactly and Holds. A/B on this machine: test_worktree_lifecycle 13 failed/133 passed under bash vs 146 passed under zsh; test_pipeline_monitor_autofollow 4 failed/55 passed vs 59 passed. Fix structurally by exec'ing the final command of all four pipeline_monitor.sh pane commands (the exec env form already used elsewhere in that script) and of the mirroring stale_live_watcher fixture, so the pane process IS the watcher under any shell. The exact identity check in worktree_lifecycle stays unchanged; adoption authority is never broadened.

## Scope

Fresh lane from exact dev fbe43a5e71fd59de07f9454b8cb9189dab346d7c. exec the final command of the four pipeline_monitor.sh pane commands and of the stale_live_watcher fixture launch command; add a regression proving pane_pid is the watcher under a non-exec-optimizing shell; resolve the blocking report.

Files and surfaces in scope:

- mu/tools/observability/pipeline_monitor.sh (MODIFY) -- only the four pane command constructions; each ends with an exec (exec env ... form) of its final script; no other behavior change.
- mu/tests/tools/test_pipeline_monitor_autofollow.py (MODIFY) -- the stale_live_watcher fixture launch command execs its final bash; plus a regression asserting the reader pane's pane_pid process is the watcher (not a sh/bash -c wrapper) when the private tmux server's default-shell is a non-exec-optimizing bash.
- mu/tests/tools/test_worktree_lifecycle.py (MODIFY only if strictly required; none expected) -- the exact identity assertions must stay unchanged.
- reports/deferred/blocking/tmux-pane-wrapper-shell-identity-2026-11-26.md (MODIFY) -- record resolution and move to the historical closures per reports/deferred/blocking/README.md.
- reports/deferred/blocking/README.md (MODIFY) -- move the entry to historical closures.
- TASKS.md (MODIFY) -- body equals the preserved PRIMARY 2026-11-25 checkpoint (sha256 8a26d505ce137ce5303adfa4084f3c13ebd40be2b76357bb1c643122167ccff0) plus only this wave's tracker note.
- reports/control_plane/workingrcx-landing-handoff-2026-11-25.md (ADD) -- byte-identical carry of the founder landing handoff (sha256 b8df7b196504ee75c2304893fc103d97861497b2ec488ff043109c5a172ec7c6).
- reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md, reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json, reports/deferred/non_blocking/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_bridge_nonblockers.md (wave-owned artifacts).
- reports/deferred/non_blocking/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-11-26 tracker sync note for wave `workingrcx-tmux-pane-exec-identity-r3-2026-11-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from exact dev fbe43a5e71fd59de07f9454b8cb9189dab346d7c; comparison_commit is that SHA.
2. Reproduce first: run test_worktree_lifecycle and test_pipeline_monitor_autofollow with SHELL=/bin/bash and record the failure counts.
3. Change each pane command so its final command is exec'd; preserve every existing variable, quoting and unset step.
4. Change the fixture launch command identically and add the non-exec-optimizing-shell regression.
5. Show both test files pass under SHELL=/bin/bash and SHELL=/bin/zsh.
6. Close the blocking report truthfully with the before/after counts.

## Constraints

- Exact candidate allowlist; halt NEEDS_RESCOPING if any other path is required.
- Do not change worktree_lifecycle adoption logic or relax the exact pane_pid == reader pid identity check; never broaden adoption authority.
- Do not touch any path of the preserved throughput R7 candidate (owner 40 delivery) or of the role/model selection wave.
- No file:line citations in packet, tracker note or reports.
- Founder usage-stop policy at TASKS.md top applies: stop immediately, preserving files/index/journals, if any observed Codex account window is at or above 70% used.
- This wave is the next native publication, so it carries the founder 2026-11-25 tracker checkpoint (TASKS.md) and landing handoff verbatim, as the handoff requires. Their historical observation lines are records, not claims of this wave; findings against their historical wording are non-blocking DOC_ACCURACY, deferred, and never rewritten here.
- Founder authorization (immutable): founder directive 2026-04-11 -- a failing test that blocks must be taken care of, pre-existing or not -- and the 2026-11-26 standing instruction to execute the recommended option autonomously; this wave is the recommended structural fix recorded in reports/deferred/blocking/tmux-pane-wrapper-shell-identity-2026-11-26.md.
- Supersession: workingrcx-tmux-pane-exec-identity-2026-11-26 stopped at Phase A R1 with a bridge fail-closed on two differing reviewer envelopes (both GO) after the orchestrator carried the blocker report into the lane mid-review; no implementation, commit or PR. R2 starts with the blocker report, tracker checkpoint and handoff all carried before launch.
- Supersession: workingrcx-tmux-pane-exec-identity-r2-2026-11-26 stopped at Phase A R1 when the codex reviewer's max-effort design turn exceeded the 600s phase_a bridge turn budget (adapter timeout; no command was running; no implementation, commit or PR). R3 runs with the phase_a bridge turn budget raised to 1500s for this launch through the native recovery env override (RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY=phase_a); tracked executor_config.json is unchanged.

## Stop conditions

- Halt before launch if origin/dev is not fbe43a5e71fd59de07f9454b8cb9189dab346d7c.
- Halt as NEEDS_RESCOPING if the fix requires changing worktree_lifecycle identity logic or any path outside the allowlist.
- Halt on the founder usage-stop threshold.

## Validation gates

- evidence_command: `SHELL=/bin/bash PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r3-2026-11-26 --wave-class L4_ENABLER`

## Acceptance criteria

- All four pipeline_monitor.sh pane commands and the fixture launch command exec their final command; no other monitor behavior changes.
- test_worktree_lifecycle and test_pipeline_monitor_autofollow pass under SHELL=/bin/bash and SHELL=/bin/zsh on macOS; the new regression fails on the pre-fix command form and passes after.
- The exact reader/pane identity assertions are unchanged.
- The local pre-push gate passes with no SHELL override; independent review, CI and providerless commit/merge pass.
- TASKS.md equals the preserved PRIMARY checkpoint plus only this wave's tracker note, and the handoff report is byte-identical to its preserved copy.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-tmux-pane-exec-identity-r3-2026-11-26`.
- Governing packet: this file, `reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md`.
- TASKS.md authority: the 2026-11-26 tracker sync note for wave `workingrcx-tmux-pane-exec-identity-r3-2026-11-26` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-tmux-pane-exec-identity-r3-2026-11-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-tmux-pane-exec-identity-r3-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`
  - `reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md`
  - `reports/deferred/blocking/README.md`
  - `reports/deferred/blocking/tmux-pane-wrapper-shell-identity-2026-11-26.md`
  - `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-tmux-pane-exec-identity-r3-2026-11-26 --output reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `SHELL=/bin/bash PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r3-2026-11-26 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`, `reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md`, `reports/deferred/blocking/README.md`, `reports/deferred/blocking/tmux-pane-wrapper-shell-identity-2026-11-26.md`, `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-tmux-pane-exec-identity-r3-2026-11-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-tmux-pane-exec-identity-r3-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c6e98b5b4c14f1b699375d89eab87e85df4bf7a142849279f2f45e6e4bde90dc`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json`
- Evidence command: `SHELL=/bin/bash PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r3-2026-11-26 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`, `reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md`, `reports/deferred/blocking/README.md`, `reports/deferred/blocking/tmux-pane-wrapper-shell-identity-2026-11-26.md`, `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`
  - `reports/control_plane/workingrcx-tmux-pane-exec-identity-r3-2026-11-26_2026-11-26.md`
  - `reports/deferred/blocking/README.md`
  - `reports/deferred/blocking/tmux-pane-wrapper-shell-identity-2026-11-26.md`
  - `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r3-2026-11-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
