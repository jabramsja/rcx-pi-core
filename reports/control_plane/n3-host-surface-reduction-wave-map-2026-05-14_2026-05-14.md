# N3-Host-Surface-Reduction-Wave-Map-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-host-surface-reduction-wave-map-2026-05-14
Class: L4_ENABLER
Category: control-plane host-surface reduction map
Phase-A-Lock: LOCKED
Purpose: Create a planning-only control-plane wave map for reducing the N3 broad host-surface boundary one bounded slice at a time after PR #950 / PR #949 closeout. This packet does not implement runtime changes and does not claim N3 closure.

## Scope

Files/directories in current staged package:

- `TASKS.md`
- `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`
- `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`

Evidence surfaces in scope for this packet's Phase A plan:

- `TASKS.md:503-518`, especially the open `[NEXT-CODEX-POST-REDTEAM]` queue, the founder-ordered dispatcher/pipeline directive, the already-landed engine-state/scheduler warning, and the landed predecessor N3 structural-slice route.
- This packet's stub content and the bridge reviewer evidence that the prior file had only title, Scope, and Request headings.
- The governing surfaces named by the supervisor for future source-grounded waves: `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`, `reports/deferred/non_blocking/README.md`, `reports/control_plane/broad_host_surface_reduction_boundary_2026-05-13.md`, `reports/control_plane/broad_host_surface_next_structural_slice_2026-05-13.md`, `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md`, `reports/control_plane/js-stage0-mucopy-lax-export-confinement-2026-05-14_2026-05-14.md`, `mu/docs/core/L4MicroAbi.v0.md`, `mu/docs/core/L4ExitChecklist.v0.md`, `mu/docs/core/Boot0Architecture.v0.md`, `mu/docs/core/L3SubstrateArchitecture.v0.md`, and current host-authority / host-semantics ratchet outputs.

This wave's output is the control-plane map below, backed by the same-wave `TASKS.md` tracker note and L4 indicator artifact named above. Future implementation waves must re-read their own source truth before locking write sets.

## Work items

1. Replace the stub packet with a real Phase A control-plane plan.
   - Goal: satisfy the bridge request for concrete plan sections and bounded work items.
   - Planning content write set: this packet.
   - Proof class: L4_ENABLER / control-plane planning.
   - Validation: targeted `rg` / `wc` section proof against this packet.
   - Proof limit: this proves packet shape and authorization text only, not N3 runtime reduction.

2. Bind this packet to same-wave tracker and indicator evidence.
   - Goal: keep the packet, `TASKS.md` tracker note, and collected L4 indicator artifact aligned on the same staged wave scope.
   - Write set: `TASKS.md`, this packet, and `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`.
   - Proof class: POLICY_BOUND L4_ENABLER authorization and indicator repair.
   - Authorization surface: same-wave `TASKS.md` tracker-sync note carrying the wave id, indicator artifact, and `FOUNDER_OVERRIDE` token.
   - Validation: `rg -n "n3-host-surface-reduction-wave-map-2026-05-14|FOUNDER_OVERRIDE:n3-host-surface-reduction-wave-map-2026-05-14" TASKS.md reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`.
   - Proof limit: the command shows tracker and packet authority for this staged package; it does not prove N3 runtime reduction.

3. Record the bounded future-wave queue for N3 host-surface reduction.
   - Goal: organize future dispatcher waves so each wave reduces or locks one narrow boundary instead of treating N3 as one broad implementation blob.
   - Planning content write set: this packet; same-wave tracker and indicator evidence remain part of the staged package.
   - Required fields for each future entry: goal, evidence surfaces, proposed write set, proof class, validations, stop conditions, and proof limits.
   - Proof limit: candidate entries are not claims that the items remain unlanded; future waves must remove or reclassify any item already proved closed by current code truth.

Future wave entries to evaluate against source/docs before implementation:

- N3 active-boundary grounding / route lock.
  - Goal: prove which N3 host-surface residue is still active after PR #949 / PR #950 and predecessor N3 packets, or stop with N3 left active and a narrower next packet.
  - Evidence surfaces: deferred N3 source packet, non-blocking README inventory, prior broad host-surface control packets, L4 doctrine docs, and current ratchet outputs.
  - Proposed write set: one future control-plane packet, required `TASKS.md` tracker entry, and normal indicator artifact; no runtime files unless a later locked packet authorizes them.
  - Proof class: L4_ENABLER governance/source-lock.
  - Validations: targeted `rg` over deferred inventory plus docs consistency, indicator collection, and strict L4 execution-contract validation for that future wave id.
  - Stop conditions: conflicting active-lane truth, no source-grounded boundary, or evidence that the candidate was already closed.
  - Proof limits: does not reduce runtime host surface by itself and cannot close all N3.

- Micro-ABI public boundary narrowing around `rcx_load`, `rcx_step`, and `rcx_run`.
  - Goal: evaluate whether public host ingress can be narrowed without moving Mu semantic authority into Python or JS.
  - Evidence surfaces: `L4MicroAbi.v0.md`, `L4ExitChecklist.v0.md`, Boot0/L3 doctrine, source-boundary packet, and host authority / semantics ratchets.
  - Proposed write set: future Phase A must lock exact Python/JS API files and focused tests before any implementation.
  - Proof class: likely L4_STRUCTURAL if runtime/API code changes are needed; L4_ENABLER if limited to governance/source-lock.
  - Validations: focused API tests, parity where behavior is semantic, host-semantics ratchet, host-authority inventory ratchet, docs consistency, and strict L4 validation.
  - Stop conditions: narrowing changes observable Mu semantics, requires host-only semantic fallback, or cannot be mirrored/parity-proved.
  - Proof limits: a narrow API slice cannot prove full Micro-ABI completion or N3 closure.

- `projection_loader` JSON-to-smaller-image productionization planning.
  - Goal: decide whether JSON host object exposure can be reduced through a smaller structural image path.
  - Evidence surfaces: N3 deferred source, L3/Boot0 doctrine, current loader/source-boundary packet, and ratchet outputs.
  - Proposed write set: future packet first; later code write set only after exact loader/tests are source-locked.
  - Proof class: L4_ENABLER for planning, L4_STRUCTURAL for later runtime reduction.
  - Validations: focused loader tests, parity if semantic, ratchets, docs consistency, and strict L4 validation.
  - Stop conditions: no source-proof that this reduces host surface, or any design that expands host JSON semantics.
  - Proof limits: planning does not prove production readiness.

- `stack_guard` structural depth budget productionization parity.
  - Goal: convert any remaining structural-depth budget work into a bounded parity-preserving production slice.
  - Evidence surfaces: governing packets, L4 docs, source files selected by future Phase A, and ratchet outputs.
  - Proposed write set: exact runtime/test files to be locked by future packet; no write set is authorized here.
  - Proof class: L4_STRUCTURAL only after source-lock.
  - Validations: focused depth-budget tests, parity, host-semantics ratchet, host-authority ratchet, docs consistency, strict L4 validation.
  - Stop conditions: behavior cannot be parity-proved or would add host-only enforcement semantics.
  - Proof limits: one depth-budget slice cannot close broader host-surface debt.

- `max_steps` / fuel threading production pilot.
  - Goal: evaluate whether execution fuel can be threaded as structural control without increasing host semantic authority.
  - Evidence surfaces: L4 execution doctrine, Boot0/L3 docs, current execution boundary packets, and ratchet outputs.
  - Proposed write set: future packet must lock exact executor/runtime/test surfaces before code changes.
  - Proof class: L4_STRUCTURAL if code changes; L4_ENABLER if only governance.
  - Validations: focused fuel tests, parity where semantic, L4 execution-contract validation, ratchets, and docs consistency.
  - Stop conditions: fuel handling becomes a host oracle, changes Mu program meaning, or cannot be mirrored.
  - Proof limits: fuel threading is not full scheduler or runtime self-hosting proof.

- Engine pipeline thin-core / module extraction governance.
  - Goal: separate governance for semantics-neutral module extraction from any later runtime behavior change.
  - Evidence surfaces: prior JS engine pipeline governance route, broad host-surface packets, L3/Boot0 doctrine, and current ratchet outputs.
  - Proposed write set: governance packet and structural tests first; later extraction packet only after dependency direction and no-semantics-delta proof are locked.
  - Proof class: L4_ENABLER for governance; possible L4_STRUCTURAL for later extraction.
  - Validations: structural module-boundary tests, docs consistency, ratchets, and strict L4 validation.
  - Stop conditions: extraction changes behavior, introduces module cycles, or moves seed/program authority into host core.
  - Proof limits: module shape proof is not semantic host-surface elimination.

- Terminal / hemisphere / ontology authority source-lock.
  - Goal: keep terminal, hemisphere, and ontology authority seed-derived rather than core Python/JS authority.
  - Evidence surfaces: N3 source boundary packet, L3/Boot0 doctrine, seed/projection docs selected by future Phase A, and ratchets.
  - Proposed write set: future source-lock packet plus focused structural tests if current source truth shows missing coverage.
  - Proof class: L4_ENABLER governance/source-lock unless code changes are locked later.
  - Validations: targeted source-boundary checks, docs consistency, ratchets, and strict L4 validation.
  - Stop conditions: evidence shows the authority is already locked, or the proposed fix would add host semantics.
  - Proof limits: source-lock proof does not prove runtime reduction unless paired with a later structural slice.

- Stage0 trusted/public export surface follow-ons.
  - Goal: evaluate only remaining public/trusted export host authority after current source truth, without relisting closed Stage0 or Mu-copy work.
  - Evidence surfaces: Stage0 export confinement packet, L4 docs, current ratchets, and future source inspection.
  - Proposed write set: no code write set until a future Phase A proves remaining public host authority.
  - Proof class: L4_ENABLER if closed by source-lock; L4_STRUCTURAL only if a remaining runtime export is proved.
  - Validations: focused export probes/tests, parity when semantic, host-authority inventory ratchet, host-semantics ratchet, docs consistency, strict L4 validation.
  - Stop conditions: source truth finds no remaining public host authority, or the only work is stale wording cleanup.
  - Proof limits: follow-on export proof cannot claim all N3 is closed.

## Constraints

- Do not edit runtime, Stage0, seed, scheduler, registry, parity, production `/mu`, host-oracle, or Claude-related files in this wave.
- Keep the wave-owned write set limited to `TASKS.md`, this packet, and the same-wave L4 indicator artifact.
- Do not implement runtime, Stage0, seed, scheduler, registry, parity, production `/mu`, host-oracle, or Claude-related changes.
- Do not add semantic host debt, host-only object-model behavior, or Python/JS semantic authority.
- Do not move Mu semantic authority out of Mu programs/seeds/projections and into Python or JS host code.
- Do not claim N3 closure from this packet or from any single bounded future slice.
- Do not relist already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work from `TASKS.md:507` as unresolved.
- Do not treat the stricken landed predecessor at `TASKS.md:518` as pending implementation.
- Do not use baseline-only cleanup as a substitute for real reduction.

## Stop conditions

- Stop if satisfying a request requires writing outside the current wave-owned package of `TASKS.md`, this packet, and the same-wave L4 indicator artifact.
- Stop if a future candidate cannot be grounded in current file/doc/source truth when that candidate's own Phase A runs.
- Stop if current code truth proves a candidate already landed; remove it from pending work and acceptance criteria instead of preserving stale wording.
- Stop if a candidate requires runtime changes before Phase A locks exact write set, focused tests, parity obligations, ratchet expectations, and stop conditions.
- Stop if a candidate would add host-only semantics, widen host authority, or move Mu semantic authority into Python/JS.
- Stop if the only available proof would self-reference the packet instead of independent TASKS/governing-source evidence.

## Acceptance criteria

- This packet contains the required Phase A sections: Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization.
- Work items are bounded and distinguish this packet rewrite from future implementation waves.
- Every future-wave entry above includes goal, evidence surfaces, proposed write set, proof class, validations, stop conditions, and proof limits.
- The packet carries a wave-bound local override token for `n3-host-surface-reduction-wave-map-2026-05-14`.
- `TASKS.md` contains the same-wave tracker-sync note for `n3-host-surface-reduction-wave-map-2026-05-14`.
- The packet records the same staged scope as `TASKS.md`: `TASKS.md`, this packet, and `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`.
- Targeted section proof passes:
  - `rg -n "^(#|##) |Work items|Constraints|Stop conditions|Acceptance criteria|Grounding|Authorization|FOUNDER_OVERRIDE" reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md && wc -l reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`
- Targeted authorization proof returns this packet's same-wave override:
  - `rg -n "FOUNDER_OVERRIDE:n3-host-surface-reduction-wave-map-2026-05-14" reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`

## Grounding / Authorization

TASKS grounding:

- `TASKS.md:503` marks `[NEXT-CODEX-POST-REDTEAM]` as UNPARKED and founder-authorized.
- `TASKS.md:506` keeps the current phase OPEN for remaining structural reduction that requires separate bounded packets.
- `TASKS.md:507` warns not to relist already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.
- `TASKS.md:511` requires autonomous dispatcher/pipeline routing, control-plane packets, tracker entries for waves, and paired mechanical automation for manual pipeline repairs.
- `TASKS.md:517` records the broad-host-surface bridge DOC_ACCURACY closeout as implemented and local-evidence backed.
- `TASKS.md:518` records the predecessor broad-host-surface next structural slice as landed; this packet therefore maps successor work without treating that predecessor as pending.

Governing packet refs for future source-grounded work:

- `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md` is the governing packet for this planning wave.
- Future implementation or source-lock waves must independently cite the relevant governing surfaces named in Scope before locking write sets.

Bridge / pre-commit disposition:

- Bridge Round 1 found that the prior authorization text did not clearly separate planning-packet authority from the normal strict `TASKS.md` tracker requirement.
- The current staged package now includes the same-wave `TASKS.md` tracker note and the L4 indicator artifact, so this packet describes the tracker, indicator, and packet as one three-file staged scope.
- Pre-commit supervisor receipt remains pending for this staged package; the packet does not claim N3 runtime reduction or final closeout.

Same-wave tracker sync note:

- Tracker sync note (2026-05-14, n3-host-surface-reduction-wave-map-2026-05-14): **NEXT-CODEX-POST-REDTEAM - N3 host-surface reduction wave-map control-plane packet.** Class: L4_ENABLER. Category: control-plane host-surface reduction map. target_gate_id: G8. Packet: `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`. evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-host-surface-reduction-wave-map-2026-05-14 --output reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`. evidence_delta: (1) Phase B converged on the locked plan at `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface. progress_proof_before: Phase B had not yet emitted a commit-ready handoff with a canonical tracker note, so downstream governance could not bind the wave cleanly to its indicator artifact. progress_proof_after: Phase B refreshed the pre-commit supervisor package for `n3-host-surface-reduction-wave-map-2026-05-14` with 3 wave-owned file(s), bridge rounds=2, package-bound L4 authority pending pre-commit supervisor validation. FOUNDER_OVERRIDE:n3-host-surface-reduction-wave-map-2026-05-14. primary_blocker_class: INTEGRATION. primary_invariant_id: INV_STRUCTURAL_FORWARD_MOTION. indicator_artifact_ref: `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`. indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-host-surface-reduction-wave-map-2026-05-14 --output reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`. bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. boot0_track_id: V1. boot0_progress_state: HOLD.

Authorization: wave-bound L4_ENABLER tracker authority for the current staged package.

FOUNDER_OVERRIDE:n3-host-surface-reduction-wave-map-2026-05-14

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-host-surface-reduction-wave-map-2026-05-14`
- Active packet: `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-host-surface-reduction-wave-map-2026-05-14`
- Active packet: `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ab140b4cbc7d6b1eabffe13a141d8437eb9cb4a214221b83af69f26deae0d9f9`
- Indicator artifact: `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-host-surface-reduction-wave-map-2026-05-14 --output reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-host-surface-reduction-wave-map-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-host-surface-reduction-wave-map-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
