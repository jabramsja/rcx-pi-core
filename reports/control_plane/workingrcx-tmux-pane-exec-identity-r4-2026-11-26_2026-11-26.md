# WorkingRCX tmux Pane Exec Identity R4 2026-11-26

Date: 2026-11-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-tmux-pane-exec-identity-r4-2026-11-26
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: fb5ce5198d1a95254e3cb5b417bc024a48c052f421d306e41e440b2d9041f8de
Purpose: Land the reviewed structural fix for the BLOCKING tmux pane wrapper-shell identity finding, whose closure record is carried at reports/archive/deferred/tmux-pane-wrapper-shell-identity-2026-11-26_closed-by-workingrcx-tmux-pane-exec-identity-r4-2026-11-26.md. tmux runs each monitor pane command as $SHELL -c; every pane command in pipeline_monitor.sh was a compound cd/unset list ending in an un-exec'd bash <script>. Under macOS bash 3.2 (the founder login shell) the last command of an && list is not exec'd, so a bash -c wrapper remains as pane_pid while the watcher runs as its child; worktree_lifecycle _adopt_terminal_log_readers requires pane_pid == reader pid exactly and Holds. A/B on this machine: test_worktree_lifecycle 13 failed/133 passed under bash vs 146 passed under zsh; test_pipeline_monitor_autofollow 4 failed/55 passed vs 59 passed. The fix execs the final command of all four pipeline_monitor.sh pane commands (the exec env form already used elsewhere in that script) and of the mirroring stale_live_watcher fixture, so the pane process IS the watcher under any shell. It was reviewed in R3 and is carried byte-identical from R3 commit ff12f6544f0b2e3bdb2820f763c2e73e6667d79b. The exact identity check in worktree_lifecycle stays unchanged; adoption authority is never broadened.

## Scope

Fresh lane from exact dev fbe43a5e71fd59de07f9454b8cb9189dab346d7c: carry the reviewed R3 exec fix (four pipeline_monitor.sh pane commands, the stale_live_watcher fixture launch command and the non-exec-optimizing-shell regression) byte-identical from R3 commit ff12f6544f0b2e3bdb2820f763c2e73e6667d79b; verify under bash and zsh; record the blocker closure under reports/archive/deferred/ and index it under the blocking README's historical closures.

Files and surfaces in scope:

- mu/tools/observability/pipeline_monitor.sh (MODIFY) -- carried byte-identical from reviewed R3 commit ff12f6544f0b2e3bdb2820f763c2e73e6667d79b: only the four pane command constructions, each ending with an exec (exec env ... form) of its final script; no other behavior change.
- mu/tests/tools/test_pipeline_monitor_autofollow.py (MODIFY) -- carried byte-identical from R3 commit ff12f6544f0b2e3bdb2820f763c2e73e6667d79b: the stale_live_watcher fixture launch command execs its final bash, plus the regression asserting the reader pane's pane_pid process is the watcher (not a sh/bash -c wrapper) when the private tmux server's default-shell is a non-exec-optimizing bash.
- mu/tests/tools/test_worktree_lifecycle.py (MODIFY only if strictly required; none expected) -- the exact identity assertions must stay unchanged.
- reports/archive/deferred/tmux-pane-wrapper-shell-identity-2026-11-26_closed-by-workingrcx-tmux-pane-exec-identity-r4-2026-11-26.md (ADD) -- the closed source packet, carried from R3's committed copy; update only its disposition and resolution lines to name this wave and its final evidence.
- reports/deferred/blocking/README.md (MODIFY) -- add one historical-closures entry pointing at the archived closure record; no other README change.
- TASKS.md (MODIFY) -- body equals the preserved PRIMARY 2026-11-26 checkpoint (sha256 f8b55669ec7ec29c7815b7803209b54037837cc6a4e4e0db1da91787f1ebf67a) plus only this wave's tracker note.
- reports/control_plane/workingrcx-landing-handoff-2026-11-25.md (ADD) -- byte-identical carry of the founder landing handoff (sha256 b8df7b196504ee75c2304893fc103d97861497b2ec488ff043109c5a172ec7c6).
- reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md, reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json, reports/deferred/non_blocking/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_bridge_nonblockers.md (wave-owned artifacts).
- reports/deferred/non_blocking/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-11-26 tracker sync note for wave `workingrcx-tmux-pane-exec-identity-r4-2026-11-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from exact dev fbe43a5e71fd59de07f9454b8cb9189dab346d7c; comparison_commit is that SHA.
2. Verify that pipeline_monitor.sh and test_pipeline_monitor_autofollow.py in the lane are byte-identical to R3 commit ff12f6544f0b2e3bdb2820f763c2e73e6667d79b (they are carried before launch); do not re-author them unless a review finding requires a change, and record any such change in the packet.
3. Show both test files pass under SHELL=/bin/bash and SHELL=/bin/zsh; R3's closure record already holds the pre-fix counts, so re-reproducing the failure is optional.
4. Record the closure: update the carried archive record's disposition to resolved by this wave with its final evidence, and add one historical-closures line to reports/deferred/blocking/README.md.
5. Never add a non-README file under reports/deferred/blocking/: the post-merge route builder and the pre-commit supervisor package list every such file as an active blocker.

## Constraints

- Exact candidate allowlist; halt NEEDS_RESCOPING if any other path is required.
- Do not change worktree_lifecycle adoption logic or relax the exact pane_pid == reader pid identity check; never broaden adoption authority.
- Do not touch any path of the preserved throughput R7 candidate (owner 40 delivery) or of the role/model selection wave.
- No file:line citations in packet, tracker note or reports.
- Founder usage-stop policy at TASKS.md top applies: stop immediately, preserving files/index/journals, if any observed Codex account window is at or above 70% used.
- This wave is the next native publication, so it carries the founder tracker checkpoint (TASKS.md, 2026-11-25 updated 2026-11-26) and landing handoff verbatim, as the handoff requires. Their historical observation lines are records, not claims of this wave; findings against their historical wording are non-blocking DOC_ACCURACY, deferred, and never rewritten here.
- Founder authorization (immutable): founder directive 2026-04-11 -- a failing test that blocks must be taken care of, pre-existing or not -- and the 2026-11-26 standing instruction to execute the recommended option autonomously; this wave is the recommended structural fix recorded in reports/archive/deferred/tmux-pane-wrapper-shell-identity-2026-11-26_closed-by-workingrcx-tmux-pane-exec-identity-r4-2026-11-26.md.
- Supersession: workingrcx-tmux-pane-exec-identity-2026-11-26 stopped at Phase A R1 with a bridge fail-closed on two differing reviewer envelopes (both GO) after the orchestrator carried the blocker report into the lane mid-review; no implementation, commit or PR. R2 starts with the blocker report, tracker checkpoint and handoff all carried before launch.
- Supersession: workingrcx-tmux-pane-exec-identity-r2-2026-11-26 stopped at Phase A R1 when the codex reviewer's max-effort design turn exceeded the 600s phase_a bridge turn budget (adapter timeout; no command was running; no implementation, commit or PR). R3 runs with the phase_a bridge turn budget raised to 1500s for this launch through the native recovery env override (RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY=phase_a); tracked executor_config.json is unchanged.
- Supersession: workingrcx-tmux-pane-exec-identity-r3-2026-11-26 (PR #1346, head ff12f6544f0b2e3bdb2820f763c2e73e6667d79b) passed Phase A GO, Phase B round 1 convergence, supervisor COMMIT_GO, local pre-push under bash and CI (after one informed re-run of an unrelated heartbeat-timing test), but cannot merge: its route was born with its own blocking report present in the lane, which forfeits the post-commit continuation; the tier-3 recovery rewrote its Phase B handoff; and its package would publish a non-README file under reports/deferred/blocking/, which every later route and supervisor package lists as a blocker. R4 carries R3's reviewed code byte-identical and records the closure under reports/archive/deferred/. The orchestrator closes PR #1346 as superseded after R4 merges; this wave does not touch it.
- R4 runs with the same native phase_a bridge turn-budget override as R3 (RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY=phase_a, 1500s), applied by load_executor_config from the launch environment; tracked executor_config.json is unchanged.
- Tests outside this wave's allowlist that fail in CI but pass locally on the same head (for example the Phase B heartbeat observation-window test) are owner-40 findings filed separately; do not edit them in this wave.

## Stop conditions

- Halt before launch if origin/dev is not fbe43a5e71fd59de07f9454b8cb9189dab346d7c.
- Halt as NEEDS_RESCOPING if the fix requires changing worktree_lifecycle identity logic or any path outside the allowlist.
- Halt on the founder usage-stop threshold.
- Halt before launch if the lane contains any non-README file under reports/deferred/blocking/.

## Validation gates

- evidence_command: `SHELL=/bin/bash PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r4-2026-11-26 --wave-class L4_ENABLER`

## Acceptance criteria

- All four pipeline_monitor.sh pane commands and the fixture launch command exec their final command; no other monitor behavior changes.
- test_worktree_lifecycle and test_pipeline_monitor_autofollow pass under SHELL=/bin/bash and SHELL=/bin/zsh on macOS; the new regression fails on the pre-fix command form and passes after.
- The exact reader/pane identity assertions are unchanged.
- The local pre-push gate passes with no SHELL override; independent review, CI and providerless commit/merge pass.
- TASKS.md equals the preserved PRIMARY checkpoint plus only this wave's tracker note, and the handoff report is byte-identical to its preserved copy.
- pipeline_monitor.sh and test_pipeline_monitor_autofollow.py are byte-identical to R3 commit ff12f6544f0b2e3bdb2820f763c2e73e6667d79b unless a review finding required a change, which the packet records.
- The committed tree contains no non-README file under reports/deferred/blocking/; the closure record lives under reports/archive/deferred/ and is indexed under the README's historical closures.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-tmux-pane-exec-identity-r4-2026-11-26`.
- Governing packet: this file, `reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md`.
- TASKS.md authority: the 2026-11-26 tracker sync note for wave `workingrcx-tmux-pane-exec-identity-r4-2026-11-26` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-tmux-pane-exec-identity-r4-2026-11-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-tmux-pane-exec-identity-r4-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/archive/deferred/tmux-pane-wrapper-shell-identity-2026-11-26_closed-by-workingrcx-tmux-pane-exec-identity-r4-2026-11-26.md`
  - `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`
  - `reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md`
  - `reports/deferred/blocking/README.md`
  - `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-tmux-pane-exec-identity-r4-2026-11-26 --output reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `SHELL=/bin/bash PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r4-2026-11-26 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/archive/deferred/tmux-pane-wrapper-shell-identity-2026-11-26_closed-by-workingrcx-tmux-pane-exec-identity-r4-2026-11-26.md`, `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`, `reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md`, `reports/deferred/blocking/README.md`, `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-tmux-pane-exec-identity-r4-2026-11-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-tmux-pane-exec-identity-r4-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `e593beecb25fb0b22a329fda6a21c8c2b22d3021bacba68a94172527953efb93`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json`
- Evidence command: `SHELL=/bin/bash PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r4-2026-11-26 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_monitor_autofollow.py`, `mu/tools/observability/pipeline_monitor.sh`, `reports/archive/deferred/tmux-pane-wrapper-shell-identity-2026-11-26_closed-by-workingrcx-tmux-pane-exec-identity-r4-2026-11-26.md`, `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`, `reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md`, `reports/deferred/blocking/README.md`, `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_monitor_autofollow.py`
  - `mu/tools/observability/pipeline_monitor.sh`
  - `reports/archive/deferred/tmux-pane-wrapper-shell-identity-2026-11-26_closed-by-workingrcx-tmux-pane-exec-identity-r4-2026-11-26.md`
  - `reports/control_plane/workingrcx-landing-handoff-2026-11-25.md`
  - `reports/control_plane/workingrcx-tmux-pane-exec-identity-r4-2026-11-26_2026-11-26.md`
  - `reports/deferred/blocking/README.md`
  - `reports/l4_wave_indicators/workingrcx-tmux-pane-exec-identity-r4-2026-11-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
