# WorkingRCX Bridge Envelope Identity 2026-11-28

Date: 2026-11-28
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]
Wave ID: workingrcx-bridge-envelope-identity-2026-11-28
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 7b8489df4e3ca856fbfaa24aa5c893181ab696702c2645d241f296b5bf34033b
Purpose: Stop Phase B's private-attribute post-review seal from refusing every approved review. The reviewer writes its own turn id into its envelope, in an invented format, and the bridge stores agent envelopes verbatim; the seal requires the stored envelope's turn id to equal the bridge's turn id, so it can never pass. On 2026-11-28 workingrcx-lane-completion-monitor-pairing-r2-2026-11-28 lost a candidate that had passed every review, including the private-attribute review, with 'Recovered reviewer job/turn/decision identity mismatch'. All five canonical reviewer turns of that wave carried a self-written turn id.

## Scope

Fresh lane from exact dev 48b93eac8a102be9abccd2d56adaca4f3c404fd5. Make the bridge bind every stored agent envelope to its turn's canonical identity at the point it stores the parsed envelope, with regressions; carry the as-filed blocking report as a closure record and the founder tracker checkpoint verbatim.

Files and surfaces in scope:

- mu/tools/agents/bridge_supervisor.py (MODIFY) -- ONLY the point in the bridge's turn flow between parsing an agent's envelope and storing it, plus one public helper that binds the identity. Envelope parsing rules, prompts, adapters, decisions, refusal handling and the meta bridge stay unchanged.
- mu/tests/tools/test_agent_bridge_supervisor.py (MODIFY) -- regressions, using public functions and the bridge's normal turn flow only.
- reports/archive/deferred/bridge-envelope-identity-private-attr-seal-2026-11-28_closed-by-workingrcx-bridge-envelope-identity-2026-11-28.md (ADD) -- the as-filed blocking report carried before launch as a closure record; update only its disposition and resolution lines.
- TASKS.md (MODIFY) -- body equals the preserved PRIMARY checkpoint (sha256 b3c3c902361c51a27a19ea7d5d46eb3687e58b74a21ace97dc8032c18ae6fd57) plus only this wave's tracker note.
- reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md, reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json, reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md (wave-owned artifacts).
- reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md
- TASKS.md -- tracker-sync authority. The 2026-11-28 tracker sync note for wave `workingrcx-bridge-envelope-identity-2026-11-28` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Start from exact dev 48b93eac8a102be9abccd2d56adaca4f3c404fd5 in a fresh lane and bus .agent_bus-bridge-envelope-identity-20261128; comparison_commit is that SHA.
2. IDENTITY BINDING: add a public helper in bridge_supervisor that takes a parsed agent envelope and its turn's canonical job_id, turn_id and agent_role. It refuses an envelope whose job_id is present and names a different job, and otherwise returns the envelope with those three fields set to the canonical values. Call it at every place the bridge stores an agent's parsed envelope for a turn, before storing, so the stored and the returned envelope are the same bound object. A refused envelope records the turn exactly as an unparseable envelope does today. Raw output files are never rewritten.
3. REGRESSIONS in mu/tests/tools/test_agent_bridge_supervisor.py, using only public functions and the bridge's normal turn flow, with no private-attribute access: a reviewer envelope carrying a self-written turn id (for example '<job>-reviewer-r1') is stored and returned with the canonical turn id and role, and the stored row's envelope turn id equals the row's turn id; an envelope naming another job is refused; an envelope that already carries the canonical identity is unchanged; the raw output file stays byte-identical.
4. Complete the closure record reports/archive/deferred/bridge-envelope-identity-private-attr-seal-2026-11-28_closed-by-workingrcx-bridge-envelope-identity-2026-11-28.md: disposition and resolution lines only. In the resolution, state that relaunching the lane-completion fix with workingrcx-lane-completion-monitor-pairing-r2-2026-11-28's preserved candidate is the next step.
5. Verify TASKS.md equals the preserved PRIMARY checkpoint plus only this wave's tracker note.
6. Run the declared gate and the identical sweep. After ANY code change, including re-entry repairs, re-run both on the final candidate before writing evidence; record source and test hashes as taken at evidence time, never as final hashes of executor-generated files.
7. Run the full local pre-push gate and show it passes.

## Constraints

- Exact candidate allowlist; halt NEEDS_RESCOPING if any other path is required.
- Do not change phase_b_executor or its private-attribute seal: its identity check stays exactly as strict. The fix makes the stored envelope honest; it never loosens a consumer.
- Tests add no private-attribute access; check_private_attr_access must stay clean for the changed test file.
- Phase B runs this lane's own bridge for every review, so once the binding is implemented, this wave's later reviews already store canonical identity. That is expected and is not a scope change.
- Evidence contract: the wave evidence_command must remain valid after final staging and must not depend on any intermediate (pre-review) candidate-authority receipt; native candidate-authority checks stay in force.
- Never add a non-README file under reports/deferred/blocking/; record any blocking finding of this wave in the packet and the evidence record instead.
- The carried TASKS.md is a verbatim founder tracker publication. Its historical observation lines are records, not claims of this wave; findings against their historical wording are non-blocking DOC_ACCURACY, deferred to the non-blocker report, and never rewritten here.
- No file:line citations in the packet, tracker note or reports.
- Founder usage-stop policy at TASKS.md top applies: stop immediately, preserving files, index and journals, if any observed Codex account window is at or above 70% used.
- Founder authorization (immutable): the 2026-11-25 landing handoff (finish owner 40 delivery) and the 2026-11-26 standing instruction to execute the recommended option autonomously; directive #5 (any issue gets a structural fix).
- This wave's launcher output is written outside the lane worktree.
- Untracked, git-ignored copies of the Claude configuration (.codex/ and .agents/) can appear in the lane from the Codex desktop import sync; never stage, edit or depend on them.
- This wave runs with the native phase_a bridge turn-budget override (RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY=phase_a, 1500s) applied from the launch environment; tracked executor timeouts are unchanged.
- Tests outside this wave's allowlist that fail in CI but pass locally on the same head are owner-40 findings filed separately; do not edit them in this wave.

## Stop conditions

- Halt before launch if origin/dev is not 48b93eac8a102be9abccd2d56adaca4f3c404fd5.
- Halt as NEEDS_RESCOPING if the change requires any path outside the allowlist.
- Halt if the carried TASKS.md is not the preserved PRIMARY checkpoint (sha256 b3c3c902361c51a27a19ea7d5d46eb3687e58b74a21ace97dc8032c18ae6fd57) plus only this wave's tracker note.
- Halt on the founder usage-stop threshold.
- Halt before launch if the lane contains any non-README file under reports/deferred/blocking/.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal --max-worker-restart=0 --maxfail=0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_agent_bridge_supervisor.py --tb=short --durations=20 && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-bridge-envelope-identity-2026-11-28 --wave-class L4_ENABLER`

## Acceptance criteria

- The only production semantic delta: every agent envelope the bridge stores and returns for a turn carries that turn's canonical job_id, turn_id and agent_role, and an envelope whose job_id names a different job is refused exactly as an unparseable envelope is.
- Regressions prove, through public functions only: a self-written turn id is stored and returned as the canonical one and matches the row; an envelope naming another job is refused; a canonical envelope is unchanged; the raw output stays byte-identical; the changed test file passes check_private_attr_access.
- TASKS.md equals the preserved PRIMARY checkpoint plus only this wave's tracker note; the closure record lives under reports/archive/deferred/ and no non-README file is under reports/deferred/blocking/.
- Candidate authority, staged L4 enforcement (L4_ENABLER), independent review, CI and providerless commit/merge all pass.
- The wave evidence command passes unchanged both before and after supervisor preparation and final staging; the full local pre-push gate passes.

## Grounding / Authorization

- Task: [FLEET-NATIVE-LIFECYCLE-PREVENTION]; wave id `workingrcx-bridge-envelope-identity-2026-11-28`.
- Governing packet: this file, `reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md`.
- TASKS.md authority: the 2026-11-28 tracker sync note for wave `workingrcx-bridge-envelope-identity-2026-11-28` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-bridge-envelope-identity-2026-11-28

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-bridge-envelope-identity-2026-11-28`
- Active packet: `reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/archive/deferred/bridge-envelope-identity-private-attr-seal-2026-11-28_closed-by-workingrcx-bridge-envelope-identity-2026-11-28.md`
  - `reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md`
  - `reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `workingrcx-bridge-envelope-identity-2026-11-28`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-bridge-envelope-identity-2026-11-28 --output reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal --max-worker-restart=0 --maxfail=0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_agent_bridge_supervisor.py --tb=short --durations=20 && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-bridge-envelope-identity-2026-11-28 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/archive/deferred/bridge-envelope-identity-private-attr-seal-2026-11-28_closed-by-workingrcx-bridge-envelope-identity-2026-11-28.md`, `reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md`, `reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md`, `reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-bridge-envelope-identity-2026-11-28.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-bridge-envelope-identity-2026-11-28`
- Active packet: `reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `05b2702873280518dbf53b3f6223232e1cf19459eda069675b3658ad7944edad`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json`
- Evidence command: `PYTHONHASHSEED=0 RCX_CI=1 HYPOTHESIS_PROFILE=ci_fast PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -n 4 --dist worksteal --max-worker-restart=0 --maxfail=0 -p no:cacheprovider --import-mode=importlib -m 'not slow and not fuzzer' mu/tests/tools/test_agent_bridge_supervisor.py --tb=short --durations=20 && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-bridge-envelope-identity-2026-11-28 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_supervisor.py`, `reports/archive/deferred/bridge-envelope-identity-private-attr-seal-2026-11-28_closed-by-workingrcx-bridge-envelope-identity-2026-11-28.md`, `reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md`, `reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md`, `reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_supervisor.py`
  - `reports/archive/deferred/bridge-envelope-identity-private-attr-seal-2026-11-28_closed-by-workingrcx-bridge-envelope-identity-2026-11-28.md`
  - `reports/control_plane/workingrcx-bridge-envelope-identity-2026-11-28_2026-11-28.md`
  - `reports/deferred/non_blocking/workingrcx-bridge-envelope-identity-2026-11-28_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/workingrcx-bridge-envelope-identity-2026-11-28.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
