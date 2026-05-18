# N3-Projection-Loader-Js-Binary-Decoder-Parity-2026-05-14

Date: 2026-05-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-projection-loader-js-binary-decoder-parity-2026-05-14
Class: L4_STRUCTURAL
Category: /mu structural host-debt reduction prerequisite
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-projection-loader-js-binary-decoder-parity-2026-05-14

Purpose: decide whether a narrow JavaScript decoder-parity prerequisite exists for
D010-style smaller seed-image decoding, without claiming D010 production readiness,
performing seed migration, flipping production defaults, or moving Mu semantics into
Python or JavaScript host code.

## Scope

This Phase A packet is limited to the `n3-projection-loader-js-binary-decoder-parity-2026-05-14`
candidate in the N3 autonomous host-debt reduction queue.

Phase A may inspect and cite only the minimum current code truth needed to produce a
GO/NO-GO decision and an exact Phase B write set:

- Python seed/projection loading surfaces under `mu/host/python/rcx_pi/selfhost/`
- JavaScript seed/projection loading surfaces under `mu/host/js/`
- seed registry manifest or generated seed metadata surfaces used by both substrates
- seed-image fixtures or programs under `mu/programs/` only when needed to prove the
  decoder contract boundary
- doctrine/docs explicitly governing this boundary: `mu/docs/core/L4MicroAbi.v0.md`,
  `mu/docs/core/L4ExitChecklist.v0.md`, `mu/docs/core/TypedNumericEnvelopes.v0.md`,
  and `mu/docs/core/Boot0Architecture.v0.md`
- focused parity, structural, or ratchet tests needed to prove the selected boundary

This packet itself authorizes no implementation edit. If Phase A returns GO, the
resulting locked Phase B packet must name the exact implementation write set before
any downstream code change begins.

## Work items

1. Re-open current truth only for the surfaces listed in Scope and cite exact
   file:line evidence for the Python loader, JavaScript loader, projection-loader
   boundary, seed registry/manifest source, numeric-envelope policy, and Boot0/L4
   productionization constraints.
2. Determine whether the JavaScript side lacks a mechanical decoder parity piece
   required before any later smaller seed-image pilot. Do not list already landed
   engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or
   seed-registration work as pending.
3. Classify the candidate as GO only if the work is a mechanical image-decoder parity
   prerequisite: bytes or structured image input must decode into the same seed data
   already accepted by the JSON path, with Mu program semantics still supplied by
   seeds/projections rather than host interpretation.
4. If GO, lock the exact Phase B write set, focused test matrix, parity obligations,
   host-semantics and authority-ratchet expectations, rollback path to the existing
   JSON production path, and proof limits.
5. If NO-GO, cite the smallest tracker, doctrine, or code file:line blocker and route
   the queue to the next N3 candidate without implementation.
6. Preserve same-wave control-plane mechanics: any Phase B or commit handoff must add
   or verify a detector-visible `TASKS.md` tracker note, same-wave L4 indicator
   artifact, and this packet's wave-bound `FOUNDER_OVERRIDE`.

## Constraints

- No D010 production readiness claim.
- No binary/TLV production migration.
- No production default flip from JSON seed loading to a smaller seed-image loader.
- No seed migration or integrity-chain implementation; that is reserved for the
  later `n3-projection-loader-seed-migration-integrity-chain-2026-05-14` candidate.
- No smaller-image production pilot; that is reserved for the later
  `n3-projection-loader-smaller-image-production-pilot-2026-05-14` candidate.
- No new host semantics, numeric coercion policy, object model, registry authority,
  or projection behavior in Python or JavaScript.
- No Claude files, hidden/local-memory files, Codex binary/cache files, ratchet
  baselines, unrelated deferred packets, or unrelated executor/test changes.
- No manual implementation outside the dispatcher/pipeline path.
- No broad repo investigation during this packet rewrite; downstream code truth is
  reopened only by the later Phase A execution step.

## Stop conditions

- Stop with NO-GO if the proposed decoder would interpret Mu semantics, projection
  behavior, registry authority, or numeric policy in host code instead of mechanically
  decoding an image into existing seed data.
- Stop with NO-GO if current truth shows the required JavaScript decoder parity is
  already landed, stale, or belongs to another N3 candidate.
- Stop with NO-GO if the exact Phase B write set cannot be limited to the loader,
  manifest/metadata, focused tests, and governing docs needed for decoder parity.
- Stop with NO-GO if D010 prerequisites outside JS decoder parity are needed first:
  int-range policy, NaN/Inf round-trip policy, migration strategy, checksum or
  integrity-chain policy, or production rollout mechanics.
- Stop with NO-GO if Python/JS parity cannot be proven with focused tests and ratchet
  evidence before any production claim.
- Stop with NO-GO if same-wave tracker, indicator, and founder-override authority
  cannot be mechanically derived before commit handoff.

## Acceptance criteria

- The packet contains Scope, Work items, Constraints, Stop conditions, Acceptance
  criteria, and Grounding / Authorization sections.
- The packet carries `FOUNDER_OVERRIDE:n3-projection-loader-js-binary-decoder-parity-2026-05-14`
  so control-surface automation can derive same-wave authorization from this
  governing packet.
- Phase A output records either GO or NO-GO with exact file:line evidence from the
  in-scope surfaces only.
- GO output locks the exact Phase B implementation write set, test commands,
  parity obligations, ratchet expectations, rollback path, and proof limits.
- GO output proves the candidate is a mechanical decoder-parity prerequisite only;
  it must not claim D010 productionization, binary/TLV migration, integrity-chain
  readiness, or a production default flip.
- NO-GO output cites the smallest blocker and routes to the next N3 candidate without
  implementation.
- Final validation for a GO path must include focused Python/JS parity evidence,
  host-semantics ratchet evidence, host-authority inventory evidence, docs
  consistency, L4 indicator collection, and strict staged L4 execution-contract
  validation for this wave id.

## Grounding / Authorization

- `TASKS.md:3-4` makes `TASKS.md` the single source of truth for authorized work.
- `TASKS.md:545-549` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked and OPEN for
  future bounded structural reduction while warning that already landed
  engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and
  seed-registration work must not be relisted as unresolved.
- `TASKS.md:553` requires every wave to have a control-plane packet plus a
  `TASKS.md` tracker entry and to proceed through the dispatcher/pipeline path.
- `TASKS.md:725` keeps D010 Binary Seed Format in `FOUNDER_DEFERRED`; `TASKS.md:747`
  says D010 productionization still requires int-range, NaN/Inf, JS decoder,
  migration, and integrity-chain work.
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:174-179`
  lists this candidate as the JS parity prerequisite for D010-style smaller
  seed-image decoding and stops the wave if the decoder becomes a new host
  semantics layer.
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:187-190`
  reserves the smaller-image production pilot until the D010 productionization
  prerequisites are satisfied.
- Governing packet for this wave:
  `reports/control_plane/n3-projection-loader-js-binary-decoder-parity-2026-05-14_2026-05-18.md`.
- Same-wave control-surface authorization:
  `FOUNDER_OVERRIDE:n3-projection-loader-js-binary-decoder-parity-2026-05-14`.

## Phase A Output

Decision: GO.

The required work is a narrow mechanical JavaScript decoder-parity prerequisite:
decode D010-style MuBinary TLV bytes into the same projection data already loaded
from JSON seeds, then stop. It does not move checksum authority, registry
authority, projection selection, production default loading, migration, rollout,
or Mu program semantics into JavaScript host code.

Current grounding:

- Python JSON seed image boundary remains
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:301-337`: it verifies raw
  seed bytes, parses JSON, validates structure, and returns seed data.
- Python path loader remains
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:345-367`: it reads the file
  and delegates to `load_verified_seed_image`.
- Python projection-loader factory remains
  `mu/host/python/rcx_pi/selfhost/projection_loader.py:48-64`: it obtains the
  canonical seed path, calls `load_verified_seed`, and returns seed projections.
- JavaScript manifest and seed-registry authority remain
  `mu/host/js/core/seed_loader.js:17-142`: the verified
  `seed_registry_manifest.v1.json` derives checksum and projection-id views.
- JavaScript JSON seed image boundary remains
  `mu/host/js/core/seed_loader.js:472-638`: it verifies JSON seed bytes through
  closed manifest views and validates projection IDs.
- JavaScript path loader remains
  `mu/host/js/core/seed_loader.js:645-659`: it resolves subdir through the
  manifest, reads the JSON file, and delegates to `loadVerifiedSeedImage` using
  the CORE view.
- D010 research format truth remains
  `mu/tests/research/test_d010_h5_projection_loader_binary.py:86-117` and
  `:166-276`: MuBinary is tag-length-value decoding for Mu values, with
  projection helper functions at `:284-305`.
- Boot0/L4 constraints remain
  `mu/docs/core/Boot0Architecture.v0.md:72-75`,
  `mu/docs/core/L4MicroAbi.v0.md:29-46`, and
  `mu/docs/core/L4ExitChecklist.v0.md:211-217`: projection loading is a
  bootstrap primitive whose binary productionization still requires separate
  int-range, NaN/Inf, migration, and integrity-chain work.

## Locked Phase B Write Set

Implementation files:

- `mu/host/js/core/seed_loader.js`
- `mu/tests/parity/test_seed_loading_parity.py`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`

Control-surface files:

- `TASKS.md`
- `reports/control_plane/n3-projection-loader-js-binary-decoder-parity-2026-05-14_2026-05-18.md`
- `reports/l4_wave_indicators/n3-projection-loader-js-binary-decoder-parity-2026-05-14.json`

Explicit non-write set:

- No seed registry manifest or generated seed metadata changes.
- No seed file migration.
- No checksum or integrity-chain policy change.
- No production default flip away from the JSON seed loader.
- No ratchet baseline changes.
- No Claude, hidden/local-memory, Codex binary/cache, dispatcher, executor,
  commit, push, or PR files.

## Phase B Implementation Contract

- Add a JavaScript sidecar decoder for the D010 MuBinary TLV tags.
- Export sidecar decoder entry points only; do not call them from the production
  JSON path loader.
- Decode binary seed projection images into a projection array containing
  `id`, `pattern`, and `body` fields.
- Materialize INT64 values only when the decoded value is exactly representable
  as the current JavaScript `Number` data model, including the D010 research
  fixture values `2**53` and `-(2**53)`; fail closed on non-exact INT64 values
  rather than silently rounding or introducing a new numeric envelope.
- Preserve the current integer-only seed-image numeric policy for decoded seed
  projection images; reject binary FLOAT64/non-finite seed projection data,
  including integer-valued FLOAT64 values, instead of creating a new numeric
  policy.
- Preserve existing JSON checksum/projection-id verification as the production
  rollback path.

## Phase B Validation Matrix

Phase B-local commands:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py::TestProjectionLoaderBinaryDecoderParity --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py::TestProductionLoaderBoundaryParity --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestJsSeedLoaderBinaryDecoderSidecarLock::test_binary_decoder_sidecar_not_production_loader --tb=short
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
./tools/checks/check_docs_consistency.sh
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-projection-loader-js-binary-decoder-parity-2026-05-14 --output reports/l4_wave_indicators/n3-projection-loader-js-binary-decoder-parity-2026-05-14.json
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-projection-loader-js-binary-decoder-parity-2026-05-14 --wave-class L4_STRUCTURAL
```

Parity obligations:

- JS golden TLV values that are exactly representable in the current JS `Number`
  data model match the Python D010 research decoder, including D010's
  `2**53` / `-(2**53)` large-integer fixture.
- A D010-style binary projection image produced by the Python research encoder
  decodes in JS to the current JSON seed projection data.
- Non-exact INT64 values fail closed instead of silently rounding; full INT64
  range policy remains a separate D010 productionization prerequisite.
- Wrong top-level binary image shape, trailing bytes, non-string dict keys, and
  seed-image FLOAT64 numerics fail closed, while valid Mu string keys such as
  `__proto__` remain data keys rather than JavaScript prototype edits.
- Source lock proves the binary sidecar is not invoked by `loadVerifiedSeed` or
  `loadVerifiedSeedImage`.

Ratchet expectations:

- Host-semantics ratchet: no marker increase.
- Host-authority inventory: no unaccepted new total-inventory or authority-site
  increase.
- L4 execution contract: same-wave tracker note, same-wave indicator artifact,
  and `FOUNDER_OVERRIDE:n3-projection-loader-js-binary-decoder-parity-2026-05-14`
  are detector-visible.

Rollback path:

- Continue using `loadVerifiedSeed` / `loadVerifiedSeedImage` JSON production
  paths. Removing the exported sidecar decoder and focused parity tests returns
  production behavior to the previous JSON-only surface because no production
  caller is redirected.

## Proof Limits

This wave proves only JavaScript mechanical decoder parity for D010-style TLV
projection images whose INT64 values are exactly representable in the current
JSON-compatible JavaScript `Number` data model. It does not prove full INT64
range policy, D010 production readiness, binary/TLV seed migration, checksum or
integrity-chain readiness, smaller-image production pilot readiness, full L4
completion, or a production default flip.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-projection-loader-js-binary-decoder-parity-2026-05-14`
- Active packet: `reports/control_plane/n3-projection-loader-js-binary-decoder-parity-2026-05-14_2026-05-18.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-projection-loader-js-binary-decoder-parity-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/seed_loader.js`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `reports/control_plane/n3-projection-loader-js-binary-decoder-parity-2026-05-14_2026-05-18.md`
  - `reports/deferred/non_blocking/n3-projection-loader-js-binary-decoder-parity-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-projection-loader-js-binary-decoder-parity-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
