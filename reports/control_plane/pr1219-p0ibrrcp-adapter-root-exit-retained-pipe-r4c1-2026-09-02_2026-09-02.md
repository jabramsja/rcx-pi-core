# PR 1219 P0IBRRCP Adapter Root Exit Retained Pipe R4C1

Date: 2026-09-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [ROLES-ALL-CODEX-PR1219-ROOT-EXIT-R4C]
Wave ID: pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 3968032877b4f9682655a1acd3db2ba429bf375d91319470e87092edc935ee43
Purpose: Close only the reproduced case where a normal adapter-root exit leaves one same-session child holding inherited stdout and stderr until the absolute timeout: cancel root-timeout authority, invoke the existing process-group cleanup, and finish the existing reader-drain path.

## Scope

Land one missing post-normal-root call to existing same-session cleanup in buffered and streaming adapter execution, with one synchronized retained-pipe regression, then advance to envelope-validation R3.

Files and surfaces in scope:

- Exact permitted path 1: TASKS.md for same-wave tracker and queue synchronization only.
- Exact permitted path 2: mu/tools/agents/bridge_adapters.py for the missing post-normal-root existing-cleanup invocation in buffered and streaming paths only.
- Exact permitted path 3: mu/tests/tools/test_agent_bridge_supervisor.py for the synchronized reproduced retained-pipe regression and existing controls only.
- Exact permitted path 4: reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md for the Phase-A-authored canonical packet.
- Exact permitted path 5: reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json for Phase-B-generated L4 governance.
- Exact permitted path 6, conditional only on real findings: reports/deferred/non_blocking/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_bridge_nonblockers.md.
- TASKS.md -- tracker-sync authority. The 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Have Phase A author the canonical bounded packet from this operator stub; preserve the stopped broad R4C source and bus as noncomplete evidence only.
2. In both existing adapter execution paths, after proc.wait reports a normal root exit, cancel the applicable root/zero-output/stale timeout authority and invoke the unchanged _kill_process_group(proc, wait_for_exit=True) before the existing reader joins and output classification.
3. Add one parametrized buffered/streaming real-process regression whose synchronized child inherits stdout and stderr, whose root flushes fixed output and exits zero, and which proves the call returns that output without the absolute-timeout error and the named child is no longer live non-zombie.
4. Synchronize TASKS with PR #1262 landed, broad R4C preserved as Phase-A nonconvergent, R4C1 current, and exact bridge-envelope-validation R3 next; retain the urgent PR/fleet/Mu order.
5. Land normally through Phase B, providerless commit, PR, CI, review, merge, and cleanup, then advance exactly to envelope-validation R3.

## Constraints

- Reuse _kill_process_group unchanged; do not add process-group enumeration, a new cleanup protocol, a cleanup budget, an EOF signaling abstraction, a cleanup-error class, or synthetic cleanup-failure handling.
- The only new behavioral authority is the missing invocation after reproduced zero-status root completion; do not change timeout, stale, nonzero-exit, provider-terminal, envelope, raw-output, or reader semantics.
- Unavailable membership probes, over-budget probes, killpg failure injection, delayed reaping variants, incomplete-EOF injection, and broad process-tree closure are non-occurring edge cases outside this atom and cannot be promoted to blockers; P0T3 retains broad lifecycle ownership.
- Do not copy, resume, mutate, or import either preserved adapter-finality R3 or broad R4C candidate; their evidence may ground the fresh implementation only.
- Do not absorb envelope validation, open-PR disposition, never-behind application, fleet cleanup, or Mu production.
- Every model-bearing role is Codex gpt-5.6-sol ultra; commit remains providerless; do not edit Claude-owned files or hand-author the canonical packet.

## Stop conditions

- Stop only if the unchanged existing process-group cleanup cannot close the exact synchronized retained-pipe reproduction from the two adapter call sites or if a required edit falls outside the six explicit paths.
- A reviewer demand for the explicitly excluded synthetic failure matrix is a nonblocking deferred edge, not authorization to widen or rewrite this packet.
- If one packet-only correction fails to converge, preserve the attempt; do not enter another same-packet rewrite loop.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`

## Acceptance criteria

- One synchronized parametrized test reproduces the same zero-status root plus one named same-session retained-pipe child in buffered and streaming modes, and both calls return the fixed stdout/stderr content before the one-second absolute timeout instead of raising the old timeout error.
- The named reproduced child is not live non-zombie after each call, while clean no-child normal exit and the existing true live-root timeout, stale, and nonzero controls remain green.
- The production delta reuses the unchanged cleanup helper after normal root completion and changes no provider, envelope, watcher policy, reader protocol, or broad lifecycle surface.
- The full focused bridge-supervisor test file passes and only the six explicit paths are present in the wave-owned package.
- TASKS records the broad R4C attempt as preserved/noncomplete, selects only R4C1 as current, selects exact wave pr1219-p0ibrrcp-bridge-envelope-validation-prereq-r3-2026-08-25 and task [ROLES-ALL-CODEX-PR1219-P0IBRRCP-BRIDGE-ENVELOPE-VALIDATION-PREREQ-R3] as immediate successor, and retains PR census, never-behind, PR disposition, fleet cleanup, and Mu production.

## Grounding / Authorization

- Task: [ROLES-ALL-CODEX-PR1219-ROOT-EXIT-R4C]; wave id `pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02`.
- Governing packet: this file, `reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md`.
- TASKS.md authority: the 2026-09-02 tracker sync note for wave `pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02 --output reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02`
- Active packet: `reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f6cf976787374bad592f4202737870c853740d70d9c8b6713b53f5736cd6212f`
- Indicator artifact: `reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_agent_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_agent_bridge_supervisor.py`, `mu/tools/agents/bridge_adapters.py`, `reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md`, `reports/deferred/non_blocking/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_bridge_nonblockers.md`, `reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_agent_bridge_supervisor.py`
  - `mu/tools/agents/bridge_adapters.py`
  - `reports/control_plane/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_2026-09-02.md`
  - `reports/deferred/non_blocking/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pr1219-p0ibrrcp-adapter-root-exit-retained-pipe-r4c1-2026-09-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
