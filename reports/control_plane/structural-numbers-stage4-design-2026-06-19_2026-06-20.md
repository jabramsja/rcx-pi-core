# NEXT-CODEX-POST-REDTEAM - StructuralNumbers Stage 4 design: integer-first matcher cutover (design-only)

Date: 2026-06-20
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: structural-numbers-stage4-design-2026-06-19
Phase-A-Lock: LOCKED
Purpose: StructuralNumbers Stage 4 DESIGN (design-only, docs): produce a bounded, reviewable design for the integer-first matcher cutover described in StructuralNumbers.v0.md section 8 stage 4, now that Stage 3 (foundation, codec, add, compare, multiply, subtract, gcd, rationals) has landed. The design must specify: (1) how to replace the host scalar type-dispatch in the Stage0 matcher (the _stage0_match isinstance dispatch in Python and the stage0Match typeof dispatch in JS) with structural matching over the landed binary-positional numerals, integer-first with no host floats; (2) how this clears the residual host_builtin scalar marker as a real reduction (net host-semantics decrease, not delta-0); (3) the correction owed to NorthStarSemantics.v0.md section B (the stale zero-canonicalization claim) under structural numbers; (4) cross-substrate parity preservation (Python and JS produce identical structural matches, no json.dumps vs JSON.stringify float leak); and (5) an explicit reconciliation with the blocked Stage0 content-addressed-mu typedispatch reduction lane, whose blocking report states Python needs an input-side raw-list fail-close to preserve behavior and parity while the current P7W4 fence forbids the analogous list token. The design states how the Stage 4 cutover and that Stage0 reduction relate (whether the cutover subsumes, supersedes, sequences-after, or must coexist with the Stage0 work) without resolving or touching the Stage0 lane in this wave. This wave produces design content only: no runtime, substrate, seed, registry, projection, or JS production change, and it does NOT implement the cutover (that is the next sequential STAGE4-INT-FIRST-CUTOVER wave).

## Scope

Docs-only Stage 4 design spec for the integer-first Stage0 matcher cutover. No runtime, substrate, seed, projection, or JS production file changes. Uses TASKS.md as tracker-sync authority.

Files and surfaces in scope:

- StructuralNumbers.v0.md (MODIFY, preferred) -- add a bounded Stage 4 design section, OR a new mu/docs/core design doc (only with CAP_CORE_DOCS bump + MANIFEST row).
- reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json (GENERATED) -- indicator artifact from the configured collection command.
- TASKS.md -- tracker-sync authority. The 2026-06-20 tracker sync note for wave `structural-numbers-stage4-design-2026-06-19` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Re-read StructuralNumbers.v0.md (especially section 8 staging and section 4 alternatives) and the landed StructuralNumbers gates to ground the design in what already exists.
2. Read the Stage0 matcher dispatch in the Python eval_seed _stage0_match and the JS bootstrap_core stage0Match to specify exactly what scalar type-dispatch is being replaced.
3. Read the blocked Stage0 lane's deferred blocking contradiction report and the P7W4 structural-reduction gate to state the precise reconciliation between the Stage 4 cutover and the Stage0 raw-list fail-close contradiction.
4. Author the bounded Stage 4 design covering the five required points (matcher cutover, host_builtin clear, NorthStar section B correction, cross-substrate parity, Stage0-lane reconciliation).
5. Keep the design bounded and design-only; do not implement the cutover or touch any runtime, seed, projection, or JS production file.
6. Run the configured doc-governance evidence command and collect the L4 indicator artifact.

## Constraints

- Use the pipeline launcher and dispatcher Phase A and Phase B path; no manual implementation or commit path.
- Design-only: no change to runtime (eval_seed), substrate, seeds, projections, JS production (bootstrap_core), or test logic in this wave.
- Do not implement the Stage 4 cutover; that is the next sequential STAGE4-INT-FIRST-CUTOVER wave.
- Do not touch, rebase, or resolve the blocked Stage0 typedispatch-reduction lane or any dirty WIP lane; only reconcile it in the design narrative.
- Prefer extending StructuralNumbers.v0.md so no new core-doc growth cap or MANIFEST row is needed; if a new core doc is genuinely clearer, bump CAP_CORE_DOCS and add the MANIFEST row in the same wave.
- Keep doc-governance green (DOC_STATUS header, doc contracts, manifest discoverability, no hardcoded counts, no line-number citations).

## Stop conditions

- Stop done when the doc-governance evidence command passes and the indicator artifact is collected.
- Halt as POLICY_BOUND if the design concludes the integer-first cutover cannot preserve cross-substrate parity or clear host_builtin without adding a host primitive -- record the finding rather than weakening the boundary.
- If authoring the design would require touching runtime, substrate, seed, or JS production files, re-scope to design narrative rather than relaxing the design-only boundary.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-stage4-design-2026-06-19 --output reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`

## Acceptance criteria

- A bounded Stage 4 design exists (extension of StructuralNumbers.v0.md or a new core doc with cap+MANIFEST) covering all five required points.
- The design specifies the exact scalar type-dispatch being replaced in both substrates and how structural matching over the landed numerals replaces it integer-first.
- The design states the host_builtin scalar-marker clear as a real net reduction and the NorthStarSemantics section B correction.
- The design explicitly reconciles the Stage 4 cutover with the blocked Stage0 typedispatch-reduction lane and its P7W4 raw-list contradiction.
- Doc-governance is green: the configured doc-contracts, manifest-discoverability, doc-freshness, and STATUS grounding tests pass.
- reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json is collected.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `structural-numbers-stage4-design-2026-06-19`.
- Governing packet: this file, `reports/control_plane/structural-numbers-stage4-design-2026-06-19_2026-06-20.md`.
- TASKS.md authority: the 2026-06-20 tracker sync note for wave `structural-numbers-stage4-design-2026-06-19` is canonical for this packet's L4 fields.
- Authorization: StructuralNumbers program continuation: Stage 4 design is the queued next sequential StructuralNumbers wave after Stage 3 (gcd and rationals) landed. Numbers as Mu, not host semantics. Design-only; the cutover follows in a separate wave.

FOUNDER_OVERRIDE:structural-numbers-stage4-design-2026-06-19

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `structural-numbers-stage4-design-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-stage4-design-2026-06-19_2026-06-20.md`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/docs/core/StructuralNumbers.v0.md`
  - `reports/control_plane/structural-numbers-stage4-design-2026-06-19_2026-06-20.md`
  - `reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-stage4-design-2026-06-19 --output reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-stage4-design-2026-06-19 --output reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-stage4-design-2026-06-19_2026-06-20.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: structural-numbers-stage4-design-2026-06-19.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `structural-numbers-stage4-design-2026-06-19`
- Active packet: `reports/control_plane/structural-numbers-stage4-design-2026-06-19_2026-06-20.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `8dd40e1ed5c2040f9c8e005ae836adc884f299361b379daa77bb839f7cb68deb`
- Indicator artifact: `reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id structural-numbers-stage4-design-2026-06-19 --output reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/structural-numbers-stage4-design-2026-06-19_2026-06-20.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`
- Current staged files:
  - `TASKS.md`
  - `mu/docs/core/StructuralNumbers.v0.md`
  - `reports/control_plane/structural-numbers-stage4-design-2026-06-19_2026-06-20.md`
  - `reports/l4_wave_indicators/structural-numbers-stage4-design-2026-06-19.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
