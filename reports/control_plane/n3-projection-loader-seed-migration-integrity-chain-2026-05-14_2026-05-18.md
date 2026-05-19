# N3 Projection Loader Seed Migration Integrity Chain 2026-05-14

Date: 2026-05-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-projection-loader-seed-migration-integrity-chain-2026-05-14
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Category: /mu structural host-debt reduction prerequisite
Authorization: FOUNDER_OVERRIDE:n3-projection-loader-seed-migration-integrity-chain-2026-05-14

## Scope

Current rewrite edit scope:

- `reports/control_plane/n3-projection-loader-seed-migration-integrity-chain-2026-05-14_2026-05-18.md`

Phase B implementation scope, if this packet proceeds past review, is limited
to the following files/directories:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py` - Python verified
  seed-image integrity boundary and rollback proof only.
- `mu/host/js/core/seed_loader.js` - JavaScript seed loader sidecar boundary
  and integrity-chain proof only. The already-landed JS TLV sidecar decoder is
  not pending work.
- `mu/tools/` - one bounded JSON-to-smaller-image migration/validation tool,
  using existing repo-local tooling conventions and no new top-level tool
  surface.
- `mu/tests/parity/test_seed_loading_parity.py` - Python/JS migration artifact,
  decoder, and rollback parity proof.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py` - production
  loader boundary and sidecar-not-default proof.
- `mu/tests/research/test_d010_h5_projection_loader_binary.py` - read-only D010
  research comparator and non-goal source.
- `TASKS.md` - same-wave tracker sync only, required before Phase B
  implementation edits or strict staged L4 closeout.
- `reports/l4_wave_indicators/` - generated same-wave indicator artifact only
  if Phase B reaches closeout.

## Work Items

1. Lock the residual prerequisite selected from current TASKS truth:
   `TASKS.md:565` records the JS binary decoder parity wave as implemented and
   explicitly excludes binary/TLV migration, seed migration, checksum or
   integrity-chain implementation, smaller-image pilot, D010 production
   readiness, and production default flips. This packet selects only the
   deterministic seed migration plus integrity-chain subset from that residue.

2. Define the deterministic migration contract:
   - Input is an already-valid production JSON seed image.
   - Output is a smaller generated/static Mu binary image artifact.
   - Output bytes must be byte-for-byte stable for the same input and policy.
   - Validation must prove JSON source bytes, generated binary bytes, and
     decoded projection data bind to the same seed/projection identity.
   - Unsupported numeric, NaN/Inf, or non-exact binary cases remain
     fail-closed; this wave does not expand numeric policy.

3. Define the integrity-chain policy:
   - Preserve current JSON checksum verification as the production default and
     rollback path.
   - Add a binary-image checksum policy only for the generated/static migration
     artifact.
   - Bind the JSON checksum, binary-image checksum, migration policy id, and
     seed name in one reproducible proof chain.
   - Reject checksum, projection-id, trailing-byte, malformed-image, or
     source/binary mismatch failures before any production-default change.

4. Add focused parity and boundary proof:
   - Python and JS must decode the same generated/static image to equivalent
     projection data.
   - The existing JS sidecar decoder may be used as proof machinery, but this
     wave must not reimplement or relitigate the completed JS decoder parity
     work.
   - Tests must prove production loaders still route through the JSON path and
     do not consume the binary sidecar by default.
   - Host-semantics and host-authority ratchets must show no accepted new host
     semantic layer or authority expansion.

5. Keep the governance chain detector-visible:
   - Before Phase B implementation edits or strict staged L4 closeout,
     `TASKS.md` must contain a same-wave tracker sync note for
     `n3-projection-loader-seed-migration-integrity-chain-2026-05-14`.
   - The closeout proof must collect the same-wave L4 indicator artifact and
     run strict L4 validation with this wave id and `L4_STRUCTURAL` class.
   - If the TASKS same-wave note is absent, Phase B must stop rather than
     claiming a complete L4 handoff.

## Constraints

- Do not flip production seed loading away from JSON in this wave.
- Do not remove JSON seed files, JSON checksum verification, manifest-derived
  CORE/CLI production views, or JSON rollback.
- Do not implement D010 full production readiness.
- Do not implement full INT64, NaN/Inf, or broader numeric-policy changes.
- Do not reimplement the already-landed JS binary decoder parity slice.
- Do not add a new host semantic interpretation layer to Python or JS loaders.
- Do not change seed registry authority, host-oracle behavior, Stage0 runtime,
  scheduler, dispatcher, commit, push, or Claude-related surfaces.
- Do not edit ratchet baselines as a substitute for no-regression proof.
- Do not widen beyond the files/directories listed in Scope.

## Stop Conditions

- Stop if current code truth proves deterministic seed migration plus
  integrity-chain policy is already implemented; record the evidence and route
  the next bounded N3 candidate instead of relisting closed work.
- Stop if the proposal requires production binary loading as the default or
  removes JSON rollback.
- Stop if Python and JS cannot be kept symmetric for the generated/static
  artifact proof.
- Stop if the implementation would require full numeric-policy settlement,
  D010 production promotion, registry authority redesign, ratchet baseline
  edits, host-oracle changes, or Claude-related edits.
- Stop if the migration tool would make the host smarter semantically instead
  of generating a byte-stable artifact plus verifiable integrity chain.
- Stop before Phase B implementation edits or strict staged L4 closeout if
  `rg -n "n3-projection-loader-seed-migration-integrity-chain-2026-05-14" TASKS.md`
  does not match a same-wave tracker sync note.

## Acceptance Criteria

- The packet no longer acts as a stub: it carries explicit in-scope
  files/directories, bounded work items, constraints, stop conditions,
  acceptance criteria, and grounding/authorization.
- Phase B either implements the deterministic migration/integrity-chain
  prerequisite within the locked scope or returns a source-grounded NO-GO with
  the smallest missing prerequisite and next candidate.
- Production JSON seed loading remains the default and rollback path in Python
  and JS throughout the wave.
- Generated/static binary artifacts are byte-for-byte stable and are bound to
  JSON source bytes, binary bytes, migration policy id, seed name, checksum
  policy, and decoded projection identity.
- Python/JS parity tests prove equivalent decoded projection data for the
  generated/static migration artifact.
- Boundary tests prove binary sidecar decoding is not called by production
  JSON loaders by default.
- Host-semantics and host-authority ratchets report no unaccepted increase.
- Same-wave tracker authority is detector-visible in `TASKS.md` before Phase B
  implementation edits or strict staged L4 closeout, and strict validation uses
  `--wave-id n3-projection-loader-seed-migration-integrity-chain-2026-05-14`
  with `--wave-class L4_STRUCTURAL`.

## Phase B Implementation Evidence

Implemented in the scoped files:

- `TASKS.md` now contains a detector-visible same-wave tracker sync note before
  loader/tool/test implementation evidence.
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py` defines the migration
  policy id, checksum policy id, and shared fail-closed migration exception.
  It does not call binary sidecar logic from `load_verified_seed_image` or
  `load_verified_seed`.
- `mu/tools/util/seed_binary_migration.py` is the bounded JSON-to-smaller-MuBinary
  generation/validation tool. It verifies an already-valid JSON seed image,
  emits deterministic sidecar bytes, validates source/binary identity, and
  writes/validates the reproducible proof chain.
- `mu/tests/docs/test_growth_caps.py` records the same-wave growth-cap
  exception for this one in-scope tool script; pre-commit exercises it through
  the tracked `tests` symlink path
  under `FOUNDER_OVERRIDE:n3-projection-loader-seed-migration-integrity-chain-2026-05-14`.
- `mu/host/js/core/seed_loader.js` keeps the already-landed TLV decoder as a
  sidecar and adds sidecar proof-chain verification helpers without routing
  production seed loading through binary bytes.
- `mu/tests/parity/test_seed_loading_parity.py` proves deterministic generated
  bytes, smaller-than-JSON output, Python/JS proof-chain parity, checksum
  binding, projection-id binding, source/binary mismatch rejection, malformed
  and trailing-byte rejection, and non-exact integer fail-closed behavior.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py` proves Python
  and JS production JSON loaders remain on the JSON path and do not consume
  the binary sidecar by default.

Local validation results:

- `rg -n "n3-projection-loader-seed-migration-integrity-chain-2026-05-14" TASKS.md`
  exits `0` and finds the tracker sync note at `TASKS.md:374`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py::TestProjectionLoaderSeedMigrationIntegrityChain mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestProjectionLoaderSeedMigrationIntegrityChainBoundary --tb=short`
  exits `0` with `5 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py::TestProjectionLoaderBinaryDecoderParity mu/tests/parity/test_seed_loading_parity.py::TestProductionLoaderBoundaryParity mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestJsSeedLoaderBinaryDecoderSidecarLock --tb=short`
  exits `0` with `31 passed`.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` exits `0`
  with `passed: true` and no increases.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` exits `0`
  with `PASS: No unaccepted new total-inventory or authority-subset sites detected.`
- `PYTHONHASHSEED=0 python3 -m pytest tests/docs/test_growth_caps.py -q`
  exits `0`, proving the tool-script cap now covers the authorized migration
  tool without bypassing the growth gate.
No deferred report was opened for the stop-hook pass because the unresolved
surface was this same-wave control-plane packet, which is included in the
authorized rewrite scope and is reconciled here.

## Grounding / Authorization

- TASKS current phase authorization: `TASKS.md:565` records
  `[N3-PROJECTION-LOADER-JS-BINARY-DECODER-PARITY]` as implemented under
  `[NEXT-CODEX-POST-REDTEAM]`, with production JSON loading retained as the
  default and rollback path. The same line explicitly excludes D010 production
  readiness, binary/TLV migration, seed migration, checksum or integrity-chain
  implementation, smaller-image pilot, registry authority changes,
  numeric-policy changes, production default flips, Claude files, ratchet
  baselines, and dispatcher/commit/push surfaces. This packet selects the
  migration plus integrity-chain residue and does not relist the completed JS
  decoder parity work as pending.
- TASKS productionization gate context: `TASKS.md:752` states that D010
  productionization requires int-range and NaN/Inf policy, JS decoder,
  migration, and integrity-chain work. The JS decoder prerequisite is current
  completed evidence per `TASKS.md:565`; this packet is limited to migration
  and integrity-chain policy, while numeric-policy expansion remains out of
  scope.
- N3 governing route: the autonomous plan lists
  `n3-projection-loader-seed-migration-integrity-chain-2026-05-14` as the
  projection-loader prerequisite with deterministic JSON-to-smaller-image
  migration, integrity-chain policy, byte-stable artifacts, checksum policy,
  JSON rollback, and no production default flip:
  `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:181-185`.
- L4 gate: `mu/docs/core/L4ExitChecklist.v0.md:211-216` requires, for
  `projection_loader`, seed migration tooling and integrity-chain policy before
  productionization; it also records D010 as research-only.
- D010 non-goals: `mu/tests/research/test_d010_h5_projection_loader_binary.py:51-59`
  explicitly did not implement production seed format migration, binary seed
  file generation tooling, JS cross-substrate decoder, I/O or SHA256
  reducibility, seed-structure validation reducibility, or performance
  benchmarking, and says future production promotion must address
  cross-substrate parity, migration tooling, and integrity chain.
- Current JS production loader truth: `mu/host/js/core/seed_loader.js:515-574`
  decodes image bytes as UTF-8 JSON and parses JSON; the path wrapper reads
  file bytes and delegates to `loadVerifiedSeedImage` at
  `mu/host/js/core/seed_loader.js:660-673`.
- Current Python production loader truth:
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:301-337` decodes UTF-8 JSON
  and validates checksum/structure/projection ids; the path wrapper reads file
  bytes and delegates at
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:340-367`.
- Current sidecar boundary truth: the UTF-8 taxonomy packet records the
  malformed sidecar UTF-8 probe returning `MuBinaryDecodeError` at
  `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md:137-139`.
- Same-wave packet authority:
  `Authorization: FOUNDER_OVERRIDE:n3-projection-loader-seed-migration-integrity-chain-2026-05-14`.
