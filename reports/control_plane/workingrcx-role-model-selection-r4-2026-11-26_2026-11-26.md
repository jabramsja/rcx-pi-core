# WorkingRCX Role and Model Selection R4 2026-11-26

Date: 2026-11-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [WORKINGRCX-ROLE-MODEL-SELECTION-2026-11-26]
Wave ID: workingrcx-role-model-selection-r4-2026-11-26
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: b1f6ed55c92dcca60e7827eaf72a297e4ea718a30d0d539be2fb7b8594e15ad1
Purpose: R4 is the corrected-config relaunch of workingrcx-role-model-selection-r3-2026-11-26 on the tmux-fixed base (PR #1347). Founder live directive 2026-11-26: Claude becomes the orchestrator, every implementer moves to the best Claude model, and every reviewer stays on the best Codex model. This wave lands ONLY the committed implementer-side role and Claude model authority so every later wave launched off dev inherits it: role_agents.implementer codex -> claude with the derived implementer backends exactly as set_roles.py and executor_common.apply_role_agents materialize them; committed bridge_agent_defaults.claude and the DEFAULT claude fallback entry -> model claude-opus-5-5, effort max, display_name 'Claude Opus 5.5 max'; and the opt-in, committed-only bridge_agent_defaults.fable entry -> model claude-fable-5-2, effort high, display_name 'Claude Fable 5.2 high'. It also carries, verbatim, the founder's PRIMARY tracker checkpoint (TASKS.md, updated 2026-11-26) as the next native publication. Deliberately OUT of scope and owned by a successor wave after owner 40 lands throughput R7: the Codex reviewer model upgrade gpt-6-astra -> gpt-6.2-astra (the commit executor local quota review hard-requires gpt-6-astra/max), the committed pager route flip (route pins live in test files R7 also edits), the Codex fallback entry, and the set_roles model/effort switch flags. This wave runs on the predecessor all-Codex gpt-6-astra/max authority and its receipts must say so.

## Scope

Fresh lane from exact dev b6544dfcbfe8047e1cd9fbf93ba1be0be494661f. Change only committed implementer role, committed Claude/Fable menu authority and the matching DEFAULT claude fallback entry, update the committed-value model-sync assertions, and carry the founder tracker checkpoint and handoff verbatim. No hunk of the preserved throughput R7 candidate is touched.

Files and surfaces in scope:

- mu/tools/executors/executor_config.json (MODIFY) -- via set_roles.py --implementer claude --reviewer codex plus bridge_agent_defaults.claude and bridge_agent_defaults.fable model/effort/display updates; no other key changes.
- mu/tools/executors/executor_common.py (MODIFY) -- ONLY the DEFAULT_EXECUTOR_CONFIG bridge_agent_defaults.claude fallback entry, set identical to the committed claude entry; no other line. This block does not overlap the preserved R7 candidate's executor_common hunks (imports, the insertion after ExecutorCommonError, copy_launch_wave_override_authority, apply_recovery_config_env_overrides).
- mu/tests/tools/test_bridge_config_model_sync.py (MODIFY) -- update only the committed role_agents/backends assertions for implementer=claude and the committed Claude/Fable menu assertions; keep the committed and fallback Codex gpt-6-astra/max assertions, bridge_reviewers codex, and the committed pager route codex assertion unchanged.
- mu/tests/tools/test_set_roles.py and mu/tests/tools/test_candidate_authority.py (MODIFY only if strictly required by the change; none expected).
- TASKS.md (MODIFY) -- body equals the preserved PRIMARY 2026-11-26 checkpoint (sha256 2539aeaab6a2dcb2dc99364cfeb3d1dda826f1c90c0e4a89bad456e332b7633d) plus only this wave's tracker note.
- reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md, reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json, reports/deferred/non_blocking/workingrcx-role-model-selection-r4-2026-11-26_bridge_nonblockers.md (wave-owned artifacts).
- mu/tests/tools/test_pipeline_agent_pager.py (MODIFY) -- update only the committed role-selection pin (the committed codex role and pager defaults test) to the founder 2026-11-26 selection {implementer: claude, reviewer: codex}; keep its committed pager route assertion unchanged.
- mu/tests/tools/test_executor_dispatch.py (MODIFY) -- in the resume supervisor package (11 fields) test only, derive the expected reader agent from the committed role configuration instead of the provider literal; no other line. This region does not overlap the preserved R7 candidate's hunks in that file.
- reports/deferred/non_blocking/workingrcx-role-model-selection-r4-2026-11-26_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-11-26 tracker sync note for wave `workingrcx-role-model-selection-r4-2026-11-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Start from exact dev b6544dfcbfe8047e1cd9fbf93ba1be0be494661f in a fresh lane and bus .agent_bus-role-model-selection-r4-20261126; comparison_commit is that SHA.
2. Run python3 mu/tools/executors/set_roles.py --implementer claude --reviewer codex --repo-root . and keep the derived backends and bridge_reviewers exactly as executor_common.apply_role_agents materializes them.
3. Set committed bridge_agent_defaults.claude to model claude-opus-5-5, effort max, display_name 'Claude Opus 5.5 max'; set committed bridge_agent_defaults.fable to model claude-fable-5-2, effort high, display_name 'Claude Fable 5.2 high'; leave committed bridge_agent_defaults.codex exactly gpt-6-astra/max.
4. Set the DEFAULT_EXECUTOR_CONFIG bridge_agent_defaults.claude fallback entry in executor_common to model claude-opus-5-5, effort max, display_name 'Claude Opus 5.5 max', byte-for-byte equal to the committed entry; leave the DEFAULT codex entry and every other DEFAULT key unchanged.
5. Run the A2 superset alignment gate (test_executor_config_alignment) UNMODIFIED and show it passes; update the committed-value assertions in test_bridge_config_model_sync as scoped, and prove with the existing sync helper (fixture-based) that a synced bridge config resolves the claude command to --model claude-opus-5-5 --effort max and the fable command to --model claude-fable-5-2 --effort high.
6. Verify TASKS.md equals the preserved PRIMARY copy (sha256 2539aeaab6a2dcb2dc99364cfeb3d1dda826f1c90c0e4a89bad456e332b7633d) plus only this wave's tracker note.
7. Record truthfully that this wave ran on the predecessor all-Codex gpt-6-astra/max authority.
8. Update mu/tests/tools/test_pipeline_agent_pager.py committed role-selection pin to the new selection and keep its pager-route assertion.
9. In mu/tests/tools/test_executor_dispatch.py, make the 11-field resume-package test derive its expected reader agent from the committed role configuration (no provider literal), so it holds across future founder role switches.
10. Run the full local pre-push gate with no SHELL override and show it passes.

## Constraints

- Exact candidate allowlist; halt NEEDS_RESCOPING if any other path is required.
- Do not touch commit_executor, recovery_gate, launch_wave, phase_b_executor, executor_dispatch, validation_execution, meta_bridge_client, meta_bridge_supervisor, AgentRunbook, CHANGELOG, or any other path of the preserved throughput R7 candidate; owner 40 owns them. In executor_common touch only the DEFAULT claude fallback entry, which no R7 hunk overlaps.
- Evidence contract: the wave evidence_command must remain valid after final staging and must not depend on any intermediate (pre-review) candidate-authority receipt; native candidate-authority checks at reviewer entry and commit readiness remain fully in force and are not weakened.
- Do not weaken, skip or rewrite the A2 superset alignment gate; it must pass unmodified.
- Do not change the reviewer role, bridge_reviewers, the committed or DEFAULT Codex model authority, the pager route, providerless commit execution, or the bridge example.
- The carried TASKS.md is a verbatim founder tracker publication. Its historical observation lines are records, not claims of this wave; findings against their historical wording are non-blocking DOC_ACCURACY, deferred to the non-blocker report, and never rewritten here.
- No file:line citations in packet, tracker note or reports.
- Founder usage-stop policy at TASKS.md top applies: stop immediately, preserving files/index/journals, if any observed Codex account window is at or above 70% used.
- Supersession: workingrcx-role-model-selection-2026-11-26 stopped at Phase A R1 (valid blocking alignment DEFECT; no implementation, commit or PR); its lane holds no unique content and is left for owner 38 deduplicated retention.
- Founder authorization (immutable): live directive 2026-11-26 in the Claude session -- change orchestrator to Claude when ready, all implementers to whatever Claude version is best, all reviewers to whatever Codex model is best, and always execute the recommended option autonomously -- and the 2026-11-25 landing handoff, which PR #1347 published with the tracker. The orchestrator selected Claude Opus 5.5 max for implementers (Fable 5.2 high as an opt-in menu entry) and gpt-6.2-astra max as the reviewer target, landing the reviewer upgrade after owner 40 because of the hardcoded gpt-6-astra local-review requirement and the R7 file overlap.
- Supersession: workingrcx-role-model-selection-r2-2026-11-26 stopped at Phase B R4 QUESTION on the intermediate-receipt evidence dependency only (no commit or PR); its lane holds no unique content and is left for owner 38 deduplicated retention.
- Never hardcode a provider in a test whose purpose is not the founder selection itself (directive: roles are a runtime switch); pins whose purpose IS the committed founder selection are updated, not deleted.
- Supersession: workingrcx-role-model-selection-r3-2026-11-26 reached supervisor COMMIT_GO (local commit 212d1172, never pushed) and failed only the local pre-push gate: 17 tmux reader-identity failures (fixed on this base by PR #1347) and two committed-config pins this R4 adds to scope; its lane is preserved for owner 38 deduplicated retention.
- R4 runs with the native phase_a bridge turn-budget override (RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY=phase_a, 1500s) applied from the launch environment; tracked executor timeouts are unchanged.
- Tests outside this wave's allowlist that fail in CI but pass locally on the same head are owner-40 findings filed separately; do not edit them in this wave.

## Stop conditions

- Halt before launch if origin/dev is not b6544dfcbfe8047e1cd9fbf93ba1be0be494661f.
- Halt as NEEDS_RESCOPING if the role/model change requires any path outside the allowlist (for example commit_executor or a pager-route test) or any executor_common change beyond the DEFAULT claude fallback entry.
- Halt if set_roles.py derivation changes the reviewer role, bridge_reviewers, or the providerless commit_executor backend.
- Halt if the carried TASKS.md cannot be verified byte-identical to the preserved PRIMARY copy.
- Halt on the founder usage-stop threshold.
- Halt before launch if the lane contains any non-README file under reports/deferred/blocking/.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_pipeline_agent_pager.py mu/tests/tools/test_executor_dispatch.py --tb=short && python3 -m json.tool mu/tools/executors/executor_config.json >/dev/null && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-role-model-selection-r4-2026-11-26 --wave-class L4_ENABLER`

## Acceptance criteria

- The only production semantic delta is the committed implementer role (codex -> claude with derived implementer backends), the committed Claude/Fable menu authority (claude-opus-5-5/max; claude-fable-5-2/high) and the matching DEFAULT claude fallback entry.
- test_executor_config_alignment passes UNMODIFIED: every DEFAULT bridge_agent_defaults agent is present in the committed menu with an identical entry (A2 superset alignment preserved, not weakened).
- Focused tests prove committed role_agents == {implementer: claude, reviewer: codex}, derived backends accordingly, bridge_reviewers unchanged codex, committed and fallback Codex still exactly gpt-6-astra/max, pager route unchanged, and the bridge config sync resolves the claude and fable commands to the new model and effort.
- TASKS.md equals the preserved PRIMARY checkpoint plus only this wave's tracker note.
- Candidate authority, staged L4 enforcement (L4_ENABLER), independent review, CI and providerless commit/merge all pass; receipts truthfully record the predecessor all-Codex gpt-6-astra/max authority.
- After merge, refreshed dev reports set_roles --show implementer=claude reviewer=codex, and a fresh lane's synced bridge config invokes the Claude implementer with --model claude-opus-5-5 --effort max.
- The wave evidence command passes unchanged both before and after supervisor preparation and final staging.
- mu/tests/tools/test_pipeline_agent_pager.py and mu/tests/tools/test_executor_dispatch.py pass; the full local pre-push gate passes with no SHELL override.

## Grounding / Authorization

- Task: [WORKINGRCX-ROLE-MODEL-SELECTION-2026-11-26]; wave id `workingrcx-role-model-selection-r4-2026-11-26`.
- Governing packet: this file, `reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md`.
- TASKS.md authority: the 2026-11-26 tracker sync note for wave `workingrcx-role-model-selection-r4-2026-11-26` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-role-model-selection-r4-2026-11-26

## Phase B implementation evidence

The 2026-11-26 R4 tracker sync note in TASKS.md remains the canonical source for
this packet's L4 fields. This section records implementation evidence without
changing the locked scope or transferring earlier-wave approval.

- The lane HEAD and origin/dev both resolved to
  `b6544dfcbfe8047e1cd9fbf93ba1be0be494661f` before implementation.
- `set_roles.py --implementer claude --reviewer codex --repo-root .` materialized
  Claude for phase_a_executor, phase_b_executor and bot_remediation. The reviewer
  role, review backends, bridge_reviewers, pager route and providerless
  commit_executor backend remain unchanged.
- The committed Claude entry and DEFAULT Claude fallback both select
  `claude-opus-5-5`, effort `max`, display name `Claude Opus 5.5 max`. The
  committed-only opt-in Fable entry selects `claude-fable-5-2`, effort `high`,
  display name `Claude Fable 5.2 high`. Committed and DEFAULT Codex remain
  `gpt-6-astra` / `max`.
- Only the DEFAULT Claude entry changed in executor_common.py. The A2 alignment
  test, set_roles tests, candidate-authority tests, bridge example and all
  protected R7 production files remain unchanged. The dispatcher test edit is
  confined to the reader expectation in the eleven-field resume-package test.
- The existing sync helper is exercised against temporary bridge fixtures seeded
  with the committed menu, asserting the exact model, effort and display name for
  both Claude and Fable. This proves command construction, not live provider
  availability.
- Removing only the R4 tracker note and its inserted separator from TASKS.md
  reproduces the preserved PRIMARY checkpoint SHA-256
  `2539aeaab6a2dcb2dc99364cfeb3d1dda826f1c90c0e4a89bad456e332b7633d`.
  The founder's historical observations are untouched. The landing handoff
  already exists on the PR #1347 base and is unchanged.

### Actual execution authority

This wave was launched and implemented under the predecessor all-Codex
`gpt-6-astra` / `max` authority. The initial committed configuration selected
Codex for both roles; the Phase A bridge record identifies Codex reader/reviewer,
the Phase B mutation context retains reader `codex`, and the active bus Codex
adapter specifies `-m gpt-6-astra` with `model_reasoning_effort="max"`.
The new committed Claude selection applies to subsequent configuration loads;
it is not a claim that this implementer ran on Claude.

### Phase B-local validation

The locked evidence command is unchanged and contains no intermediate
candidate-authority receipt dependency. It completed with exit 0:

- Focused pytest: **1131 passed in 200.94s**, including the unmodified A2
  superset-alignment gate, role-switch regressions, both committed Claude/Fable
  command-sync cases, pager selection and the resume supervisor package.
- `python3 -m json.tool mu/tools/executors/executor_config.json`: exit 0.
- Staged L4 enforcement for this wave and `L4_ENABLER`: exit 0,
  **9 changed files, 0 runtime files, 2 control-plane files; compliant**.

The canonical indicator collection command from the tracker note completed with
exit 0. Its artifact records comparison commit
`b6544dfcbfe8047e1cd9fbf93ba1be0be494661f`, net host-semantics delta 0 and parity
marker count 3. These are repository/probe indicators, not runtime or model-speed
improvement claims. Exact-delta inspection verified that the production changes
are limited to the approved role/model fields and DEFAULT Claude entry; all
changed paths are in the candidate allowlist. The checkpoint checksum was
verified again after recording these results in the R4 note.

Full local pre-push without a SHELL override, independent review, supervisor
preparation, final candidate authority, CI, commit, push, merge and fresh-dev
verification remain outer-executor obligations. This implementer does not run
those commands or claim those outcomes.

The two Phase A DOC_ACCURACY findings and preserved historical wording are
accounted for in
`reports/deferred/non_blocking/workingrcx-role-model-selection-r4-2026-11-26_bridge_nonblockers.md`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-role-model-selection-r4-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md`
  - `reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-role-model-selection-r4-2026-11-26 --output reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_pipeline_agent_pager.py mu/tests/tools/test_executor_dispatch.py --tb=short && python3 -m json.tool mu/tools/executors/executor_config.json >/dev/null && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-role-model-selection-r4-2026-11-26 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/executors/executor_common.py`, `mu/tools/executors/executor_config.json`, `reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md`, `reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-role-model-selection-r4-2026-11-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-role-model-selection-r4-2026-11-26`
- Active packet: `reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `d598c7eed99c1932e0a4b1f5b515483f90a709d33db0060e1cb844e9cec414e7`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_bridge_config_model_sync.py mu/tests/tools/test_set_roles.py mu/tests/tools/test_executor_config_alignment.py mu/tests/tools/test_pipeline_agent_pager.py mu/tests/tools/test_executor_dispatch.py --tb=short && python3 -m json.tool mu/tools/executors/executor_config.json >/dev/null && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-role-model-selection-r4-2026-11-26 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tests/tools/test_executor_dispatch.py`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/executors/executor_common.py`, `mu/tools/executors/executor_config.json`, `reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md`, `reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_executor_dispatch.py`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `reports/control_plane/workingrcx-role-model-selection-r4-2026-11-26_2026-11-26.md`
  - `reports/l4_wave_indicators/workingrcx-role-model-selection-r4-2026-11-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
