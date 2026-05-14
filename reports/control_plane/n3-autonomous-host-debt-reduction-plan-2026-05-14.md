# N3 Autonomous Host-Debt Reduction Plan

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-autonomous-host-debt-reduction-plan-2026-05-14
Class: L4_ENABLER
Category: /mu structural host-debt reduction plan
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-autonomous-host-debt-reduction-plan-2026-05-14

Purpose: convert the current N3 broad host-surface residue into an autonomous,
dispatcher-first wave queue that narrows or moves host semantics out of the
core one bounded `/mu` structural slice at a time. This planning packet does
not authorize runtime implementation edits by itself.

## Scope

This wave may edit only:

- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- the same-wave `TASKS.md` tracker note if Phase A / Phase B stages this plan
- the same-wave L4 indicator artifact if Phase A / Phase B stages this plan
- the packet-owned routing record under `.agent_bus/meta/` via the canonical
  routing-record builder

Runtime, seed, scheduler, registry, parity, production `/mu`, host-oracle,
Claude-related, hidden/local-memory, Codex binary/cache, and ratchet-baseline
files are out of scope for this planning wave.

- `reports/deferred/non_blocking/n3-autonomous-host-debt-reduction-plan-2026-05-14_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Current Evidence

- Full Codex redteam preflight on 2026-05-14 passed: clean worktree, staged L4
  contract skipped because no files were staged, host-semantics ratchet passed
  with no increases/decreases, host-authority inventory passed with `311 total`
  current sites and `217 authority` current/baseline sites, docs consistency
  passed, redteam gate tests passed, founder attestation passed, JS self-test
  passed.
- Codex startup state reported pager and autoping health: pager target reachable
  at `http://127.0.0.1:8765/api/threads`, autoping active for thread
  `019e27ec-868d-7990-ba8b-945d35775522`, tmux monitor active, and dashboard
  reachable at `http://127.0.0.1:8099/api/state`.
- Direct autoping state inspection after preflight recorded
  `status: idle_unchanged_state`, watcher pid `28731`, bridge reviewer `GO`,
  commit executor success acknowledged, and no intervention performed.
- Direct dashboard probe returned HTTP `200`; direct pager endpoint probe
  returned HTTP `400` with body `Connection header did not include 'upgrade'`,
  matching a reachable websocket endpoint rather than a dead listener.
- Current routing record is stale for new work: `.agent_bus/meta/post_merge_routing.json`
  still names `commit-executor-index-lock-classifier-precedence-2026-05-14`,
  which already merged as PR #961. This packet owns the next routing-record
  rebuild before dispatcher launch.

Architectural source truth:

- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175`
  keeps N3 active and says future reductions must route through bounded packets
  that program in Mu or narrow bootstrap assumptions, not move semantic
  authority into Python or JavaScript host code.
- `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md:51-123`
  already lists broad successor categories, but it predates the latest
  `rcx_load` production-adapter test prerequisite landing and does not itself
  launch the next production-boundary reduction wave.
- `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md:217-250`
  records the just-landed test-only prerequisite: Python/JS loader tests now
  bind current JSON `rcx_load` / `projection_loader` behavior, while production
  loader files remain unchanged.
- `mu/docs/core/L4MicroAbi.v0.md:29-46` defines `rcx_load(image_bytes) -> state`
  with deterministic, fail-closed, content-addressed, no-hidden-channel
  invariants.
- `mu/docs/core/L4ExitChecklist.v0.md:209-216` says production reduction claims
  require separate gates and lists the D010 productionization prerequisites for
  `projection_loader`.
- `mu/docs/core/Boot0Architecture.v0.md:64-80` keeps `projection_loader` as a
  Boot0 primitive that currently loads JSON, with a possible future smaller
  substrate.

## Work Items

1. Lock this packet as the queue controller for follow-on N3 host-debt
   reduction waves.
2. Rebuild `.agent_bus/meta/post_merge_routing.json` with the canonical
   routing-record builder so dispatcher freshness is tied to current HEAD and
   this packet.
3. Route this packet through `executor_dispatch.py`, not a manual Phase A /
   Phase B shortcut.
4. After this packet is locked, route the first actionable production-boundary
   wave:
   `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`.
5. Keep every runtime implementation wave bounded to one exact file set,
   focused tests, parity obligations, ratchets, rollback path, and proof
   limits before code changes.
6. If the pipeline breaks, repair manually only as a bounded unblocker and pair
   the repair with a same-wave mechanical fix in dispatcher, builder, recovery,
   commit, pre-commit, pager/autoping, or an explicit next-wave automation
   packet.

## Canonical rollout order

1. Phase A locks this queue-controller packet without runtime implementation
   edits.
2. Phase B stages only this packet, the same-wave tracker note, the same-wave
   L4 indicator artifact, and the packet-owned routing record.
3. Phase B rebuilds `.agent_bus/meta/post_merge_routing.json` through the
   canonical routing-record builder and proves dispatcher freshness against
   current `HEAD` and current repo state.
4. Commit/pre-push execution remains executor-owned; this Phase B packet does
   not run commit or pre-push governance commands.
5. After this queue-controller packet lands, route
   `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14` as the first
   actionable N3 production-boundary lock wave.

## Wave Queue

Each wave below must re-open current code truth before implementation. A listed
candidate is not proof that the work remains unlanded.

1. `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`
   - Goal: lock the exact production adapter slice after PR #960 test coverage.
   - Hypothesis: the current path-based loader can be narrowed toward the
     documented `rcx_load(image_bytes)` ABI by separating file I/O from seed
     image bytes verification, parse, and projection validation in both
     substrates.
   - Evidence surfaces: #960 packet and tests, `seed_integrity.py`,
     `projection_loader.py`, `seed_loader.js`, `cli/main.js`, `L4MicroAbi`,
     `L4ExitChecklist`, Boot0 docs.
   - Output: exact write set or NO-GO with the smallest missing prerequisite.
   - Stop: any plan that adds host-only semantic fallback, one-substrate
     behavior, broad binary migration, or D010 production-readiness overclaim.

2. `n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14`
   - Goal: implement the adapter only if wave 1 locks it.
   - Expected direction: expose a deterministic seed-image boundary that accepts
     verified bytes as the core loader input while keeping disk reads at the
     outer bootstrap edge.
   - Proof: focused #960 loader tests, parity tests, JS self-test, ratchets,
     docs consistency, strict staged/range L4 checks.
   - Stop: any host-authority inventory increase without explicit bridge
     acceptance and a narrower alternative analysis.

3. `n3-seed-registry-authority-source-lock-2026-05-14`
   - Goal: identify duplicated Python/JS host registry authority for checksums,
     locations, expected projection IDs, and seed dependencies.
   - Hypothesis: some registry truth can be moved into canonical `/mu` data or
     generated from canonical seed metadata, reducing hand-maintained host
     semantic authority.
   - Output: exact next implementation packet or NO-GO with line-cited blocker.

4. `n3-seed-registry-manifest-reduction-2026-05-14`
   - Goal: reduce duplicated host registry maps only after wave 3 locks the
     canonical data source and parity tests.
   - Proof: Python/JS registry parity, seed police, checksum/projection-ID
     failure controls, ratchets.
   - Stop: any manifest design that makes host loaders interpret new semantic
     rules instead of consuming static canonical data.

5. `n3-projection-loader-numeric-domain-policy-2026-05-14`
   - Goal: lock production seed-image numeric policy before binary or smaller
     image work.
   - Hypothesis: current production seeds can be constrained more tightly than
     D010 research floats/NaN/Inf without changing Mu program semantics.
   - Proof: corpus scan, Python/JS loader rejection parity, docs update if the
     policy is adopted.

6. `n3-projection-loader-js-binary-decoder-parity-2026-05-14`
   - Goal: build or reject the JS parity prerequisite for D010-style smaller
     seed-image decoding.
   - Scope: research/prerequisite until a later production packet promotes it.
   - Stop: if the decoder becomes a new host semantics layer rather than a
     mechanical image decoder.

7. `n3-projection-loader-seed-migration-integrity-chain-2026-05-14`
   - Goal: define deterministic JSON-to-smaller-image migration and integrity
     chain policy.
   - Proof: byte-for-byte stable artifacts, checksum policy, rollback to JSON
     production path, no production default flip.

8. `n3-projection-loader-smaller-image-production-pilot-2026-05-14`
   - Goal: pilot a smaller seed-image loader in production only after waves 5-7
     satisfy the D010 productionization prerequisites.
   - Stop: any missing int-range, non-finite numeric, JS decoder, migration, or
     integrity-chain prerequisite.

9. `n3-max-steps-structural-fuel-production-lock-2026-05-14`
   - Goal: move remaining `max_steps` / fuel control toward structural budget
     data without changing program meaning.
   - Proof: Python/JS parity, exhaustion/fuel tests, no host oracle.

10. `n3-stack-guard-depth-budget-production-lock-2026-05-14`
    - Goal: evaluate production depth budget as structural input while preserving
      crash protection as a host safety boundary.
    - Proof: hostile-depth negative controls in both substrates.

11. `n3-micro-abi-public-boundary-narrowing-2026-05-14`
    - Goal: narrow public `rcx_load`, `rcx_step`, and `rcx_run` ingress/egress so
      the public ABI exposes less host object-model behavior.
    - Proof: API tests, cross-substrate parity, no-hidden-channel checks.

12. `n3-engine-pipeline-thin-core-source-lock-2026-05-14`
    - Goal: separate semantics-neutral orchestration from seed/program authority
      in engine pipeline surfaces before any extraction.
    - Proof: module-dependency guard, seed-derived authority checks, no behavior
      delta.

13. `n3-terminal-hemisphere-ontology-authority-lock-2026-05-14`
    - Goal: ensure terminal, hemisphere, and ontology authority remains
      seed-derived rather than Python/JS host-derived.
    - Proof: source-lock and focused runtime parity only if current code truth
      finds a missing live proof.

14. `n3-active-residue-closeout-or-next-map-2026-05-14`
    - Goal: after the above waves, either close N3 with code/proof evidence or
      leave a smaller live residue map that names only unreduced host surfaces.
    - Stop: baseline cleanup, doc-only cleanup, or one bounded slice cannot close
      broad N3.

## Constraints

- Use the dispatcher pipeline for every wave: routing record -> Phase A ->
  Phase B -> pre-commit supervisor -> commit executor.
- Do not make Python or JavaScript "smarter" as the objective. Any host edit
  must narrow, isolate, fail-close, or move authority toward Mu data.
- Do not add new bootstrap primitives.
- Do not use D010 research evidence as production readiness evidence.
- Do not claim N3 closure from planning, tests-only work, baseline cleanup, or
  one bounded implementation.
- Do not update ratchet baselines as proof of reduction.
- Do not modify Claude-related files.
- Do not bypass pager/autoping/pipeline surfaces when they are healthy.

## Stop Conditions

- Stop a wave before code changes if exact write set, tests, parity obligations,
  ratchets, rollback path, and proof limits are not detector-visible.
- Stop if a proposed fix moves Mu semantic authority into host code.
- Stop if a production wave requires broad migration that cannot be split.
- Stop if Python/JS behavior cannot be mirrored or explicitly proved out of
  scope.
- Stop if a candidate is already closed by current code truth; record the
  evidence and route the next candidate.
- Stop if the pipeline breaks and no same-wave or next-wave mechanical repair is
  recorded.

## Acceptance Criteria

- This packet is reviewed and locked by Phase A before implementation waves
  start.
- The routing record is rebuilt through the canonical builder and dispatcher
  freshness passes.
- The first actionable wave after this plan is the `rcx_load` seed-image
  boundary adapter lock, not another broad queue-only packet.
- Every implementation wave changes only its Phase-A-locked files and records
  focused validation results.
- Host-semantics ratchet never increases.
- Host-authority inventory adds no total-inventory or authority-subset sites
  unless a bridge-reviewed packet explicitly proves no narrower reduction exists
  and records the follow-up removal path.
- Pager/autoping remain checked before long-running dispatch and after any
  pipeline hard fail.

## Grounding / Authorization

Task authority:

- `TASKS.md:514-518` is the governing tracker authority for this wave.
  `TASKS.md:514` marks `[NEXT-CODEX-POST-REDTEAM]` as **UNPARKED** and
  founder-authorized, `TASKS.md:515` names the tracked packet as
  `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`,
  `TASKS.md:516` preserves the Phase A -> Phase B -> Phase C -> Phase D
  sequence, and `TASKS.md:517-518` keeps the queue open only for future
  bounded work not already proven by landed engine-state/scheduler seed,
  fixture, structural-test, scheduler-parity, or seed-registration work.
- `[NEXT-CODEX-POST-REDTEAM]` is therefore the active founder-authorized
  structural lane for the current N3 host-surface reduction sequence, governed
  by the tracked packet
  `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`.
- This wave is plan/control-plane only: `L4_ENABLER`, not runtime reduction.

Pipeline authority:

- `FOUNDER_SESSION_BOOTSTRAP.md` requires dispatcher/executor routing where
  supported and requires manual pipeline repairs to be paired with mechanical
  automation or a precise next-wave automation packet.
- This packet therefore creates the route for dispatcher-owned Phase A lock
  review followed by bounded Phase B implementation.

## Phase B Implementation Record

Phase B keeps this packet control-plane only. The implemented state is:

- This packet is the N3 queue controller for follow-on host-debt reduction
  waves until the first production-boundary successor is routed.
- The packet-owned routing record under `.agent_bus/meta/` must be rebuilt by
  the canonical routing-record builder, bound to current `HEAD`, current repo
  state, this wave id, `[NEXT-CODEX-POST-REDTEAM]`, and this packet path.
- Dispatcher freshness is the local proof that the rebuilt record is usable by
  `executor_dispatch.py`; this Phase B implementer does not launch commit or
  pre-push governance surfaces.
- The first actionable successor after this queue-controller packet remains
  `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`.
- Runtime, seed, scheduler, registry, parity, production `/mu`, host-oracle,
  Claude-related, hidden/local-memory, Codex binary/cache, and ratchet-baseline
  files remain out of scope for this packet.

Phase B-local validation surfaces:

- `python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-autonomous-host-debt-reduction-plan-2026-05-14 --output reports/l4_wave_indicators/n3-autonomous-host-debt-reduction-plan-2026-05-14.json`
- canonical `build_and_write_routing_record(...)` invocation from
  `mu.tools.executors.executor_common`
- dispatcher freshness check via
  `mu.tools.executors.executor_dispatch.validate_routing_record_freshness(...)`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-autonomous-host-debt-reduction-plan-2026-05-14`
- `./tools/checks/check_docs_consistency.sh`

Same-wave marker:

`FOUNDER_OVERRIDE:n3-autonomous-host-debt-reduction-plan-2026-05-14`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-autonomous-host-debt-reduction-plan-2026-05-14`
- Active packet: `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-autonomous-host-debt-reduction-plan-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
  - `reports/deferred/non_blocking/n3-autonomous-host-debt-reduction-plan-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-autonomous-host-debt-reduction-plan-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-autonomous-host-debt-reduction-plan-2026-05-14`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-autonomous-host-debt-reduction-plan-2026-05-14_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-autonomous-host-debt-reduction-plan-2026-05-14`
- Active packet: `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `82fc20ea05e2fd1ba49a506309772a5898b8b927e18a67dc3c855f3517e514f5`
- Indicator artifact: `reports/l4_wave_indicators/n3-autonomous-host-debt-reduction-plan-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-autonomous-host-debt-reduction-plan-2026-05-14 --output reports/l4_wave_indicators/n3-autonomous-host-debt-reduction-plan-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-autonomous-host-debt-reduction-plan-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
  - `reports/deferred/non_blocking/n3-autonomous-host-debt-reduction-plan-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-autonomous-host-debt-reduction-plan-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
