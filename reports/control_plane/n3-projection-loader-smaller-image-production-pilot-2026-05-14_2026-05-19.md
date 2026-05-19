# N3 Projection Loader Smaller Image Production Pilot 2026-05-14

Date: 2026-05-19
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-projection-loader-smaller-image-production-pilot-2026-05-14
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL candidate for /mu structural host-debt reduction
Category: /mu projection-loader host-semantics narrowing
Authorization: FOUNDER_OVERRIDE:n3-projection-loader-smaller-image-production-pilot-2026-05-14

Purpose: route the next ordered N3 projection-loader slice through the
dispatcher pipeline. This packet authorizes Phase A to decide whether the
smaller seed-image production pilot is now ready after the numeric-domain,
JavaScript decoder-parity, and seed-migration integrity-chain prerequisites
landed. It does not authorize hand runtime edits or a production default flip.
Phase A authority comes from the detector-visible `[NEXT-CODEX-POST-REDTEAM]`
tracker entry for the governing N3 ordered plan plus the ordered queue entry
for this wave; a same-wave `TASKS.md` tracker note for this exact wave remains
required before Phase B runtime/test edits or strict staged L4 closeout.

## Scope

This packet is the governing control-plane packet for:

- `n3-projection-loader-smaller-image-production-pilot-2026-05-14`

Phase A may inspect only the current code and evidence needed to return a
source-grounded GO/NO-GO decision and, on GO, an exact Phase B write set.

Candidate Phase B scope, if Phase A returns GO, is limited to:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py` - Python seed-image
  boundary, JSON rollback, and fail-closed opt-in smaller-image boundary until
  a Mu-native sidecar adapter exists.
- `mu/host/js/core/seed_loader.js` - JavaScript seed-image boundary, JSON
  rollback, and opt-in smaller-image loading adapter only.
- `mu/tools/util/seed_binary_migration.py` - existing deterministic
  JSON-to-smaller-image generation and proof-chain utility only if pilot
  validation needs a bounded production adapter or fixture-generation guard.
- `mu/tests/parity/test_seed_loading_parity.py` - JavaScript pilot coverage,
  Python fail-closed boundary coverage, and Python/JavaScript rollback parity.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py` - production
  boundary proof that the pilot remains opt-in and does not make host code the
  semantic authority.
- `TASKS.md` - read-only Phase A authorization evidence from the current
  `[NEXT-CODEX-POST-REDTEAM]` tracker and same-wave tracker sync only if Phase B
  proceeds; same-wave sync is required before Phase B runtime/test edits or
  strict staged L4 closeout.
- `reports/l4_wave_indicators/` - generated same-wave indicator artifact only
  if Phase B reaches closeout.

No other runtime, substrate, seed, registry, Stage0, scheduler, dispatcher,
commit, push, ratchet baseline, local Codex, Claude, or report file is in scope
without a new packet or explicit founder authorization.

## Work Items

1. Re-open current code truth before implementation. Phase A must cite exact
   file:line evidence for the prerequisite chain and for any retained blocker:
   numeric-domain policy, JavaScript binary decoder parity, seed migration,
   integrity-chain validation, JSON rollback, and sidecar-not-default
   production boundary.
2. Verify the ordered queue prerequisite from
   `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:187-191`:
   this pilot may proceed only after waves 5-7 satisfy the D010
   productionization prerequisites and must stop on any missing int-range,
   non-finite numeric, JavaScript decoder, migration, or integrity-chain
   prerequisite.
3. Determine whether a production pilot can be narrower than a default flip.
   A GO decision must define an opt-in smaller-image adapter or fixture-backed
   production pilot whose rollback remains the existing JSON seed loading path.
4. Program in Mu, not in host semantics. Any candidate implementation must
   mechanically load or validate a generated/static smaller image already bound
   to Mu seed/projection identity. Python and JavaScript may enforce boundary
   checks, but must not infer projection meaning, registry authority, numeric
   policy, or seed semantics beyond the existing Mu image/proof data.
5. If GO, lock exact Phase B files, expected test commands, parity obligations,
   host-semantics and host-authority ratchet expectations, rollback path,
   generated/static artifact policy, and proof limits before implementation.
6. If NO-GO, cite the smallest missing prerequisite or current-code blocker and
   route the next N3 candidate without implementation.
7. Preserve same-wave pipeline discipline. Phase A is authorized by
   `TASKS.md:347` plus the ordered queue entry at
   `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:187-191`.
   The exact same-wave lookup
   `rg -n "n3-projection-loader-smaller-image-production-pilot-2026-05-14" TASKS.md`
   currently exits 1, so Phase B, if reached, must add a detector-visible
   same-wave `TASKS.md` tracker note before runtime/test edits or strict staged
   L4 closeout, collect the same-wave L4 indicator artifact, run strict staged
   L4 validation with this wave id, and proceed through the commit executor.

## Constraints

- Use the dispatcher pipeline: routing record -> Phase A -> Phase B -> review
  -> commit executor. Do not hand-edit runtime from this packet.
- Do not flip production seed loading from JSON to the smaller image by
  default.
- Do not remove JSON seed files, JSON checksum verification, manifest-derived
  CORE/CLI production views, or JSON rollback.
- Do not claim full D010 production readiness, broad N3 closure, or full L4
  exit from this bounded pilot.
- Do not broaden numeric policy, add typed numeric envelopes, accept NaN/Inf,
  or reopen the integer-only corpus policy without founder authorization.
- Do not add a new host semantic interpretation layer in Python or JavaScript.
- Do not move registry authority, projection semantics, scheduler behavior,
  Stage0 behavior, or Mu program meaning into host code.
- Do not edit ratchet baselines as proof.
- Do not touch Claude-related files or local Codex binary/cache surfaces.

## Stop Conditions

- Stop with NO-GO if any prerequisite from the ordered queue remains missing:
  int-range policy, non-finite numeric rejection, JavaScript decoder parity,
  deterministic migration, or integrity-chain proof.
- Stop with NO-GO if current code truth already makes the proposed pilot
  obsolete; record the evidence and route the next bounded N3 candidate.
- Stop with NO-GO if the pilot requires a production default flip or JSON
  rollback removal.
- Stop with NO-GO if JavaScript cannot prove the positive pilot path, Python
  cannot prove fail-closed sidecar handling without new host capability, or
  Python and JavaScript cannot prove equivalent JSON rollback behavior.
- Stop with NO-GO if implementation would require seed registry redesign,
  full D010 productionization, broad public Micro-ABI redesign, host-oracle
  changes, Stage0/scheduler changes, ratchet baseline edits, or Claude-related
  edits.
- Stop before Phase B runtime/test edits if the exact write set cannot remain
  within the candidate scope above.
- Stop before Phase B runtime/test edits and before strict staged L4 closeout if
  `TASKS.md` lacks a detector-visible same-wave tracker note for
  `n3-projection-loader-smaller-image-production-pilot-2026-05-14`.

## Acceptance Criteria

- Phase A returns GO or NO-GO with exact file:line evidence from the scoped
  surfaces.
- GO output locks the exact Phase B implementation write set, focused test
  matrix, parity obligations, rollback path, ratchet expectations, generated
  artifact policy, and proof limits.
- Any production pilot remains opt-in or gated; JSON seed loading remains the
  default and rollback path unless a later founder-authorized packet explicitly
  changes that default.
- JavaScript proves positive smaller-image pilot behavior, Python proves
  explicit fail-closed sidecar handling without new host capability, and Python
  and JavaScript prove equivalent JSON rollback behavior.
- Host-semantics and host-authority ratchets report no unaccepted increase.
- Phase A authorization cites detector-visible `TASKS.md` authority for the
  governing N3 ordered plan and the ordered queue entry for this exact wave.
- Before Phase B runtime/test edits or strict staged L4 closeout, same-wave
  tracker authority is detector-visible in `TASKS.md`, the L4 wave indicator is
  collected, and strict staged L4 validation uses:
  `--wave-id n3-projection-loader-smaller-image-production-pilot-2026-05-14`
  with `--wave-class L4_STRUCTURAL`.
- The commit path uses the receipt/commit builders and the commit executor
  rather than manual commit/push/PR steps.

## Grounding / Authorization

- `TASKS.md:347` is the detector-visible `[NEXT-CODEX-POST-REDTEAM]` tracker
  authority for `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
  and carries
  `FOUNDER_OVERRIDE:n3-autonomous-host-debt-reduction-plan-2026-05-14`.
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:187-191`
  is the ordered queue entry for
  `n3-projection-loader-smaller-image-production-pilot-2026-05-14` and defines
  the prerequisite stop condition; together with `TASKS.md:347`, it authorizes
  Phase A for this packet.
- `TASKS.md:364`, `TASKS.md:371`, and `TASKS.md:374` record the prerequisite
  N3 projection-loader waves under `[NEXT-CODEX-POST-REDTEAM]`; they are
  tracker evidence for predecessor handoffs, not proof that any current-code
  item remains unlanded.
- `rg -n "n3-projection-loader-smaller-image-production-pilot-2026-05-14" TASKS.md`
  currently exits 1, so the packet does not claim an existing same-wave
  `TASKS.md` tracker note. Phase B must add that note before runtime/test edits
  or strict staged L4 closeout.
- `mu/tools/util/seed_binary_migration.py:2-7` states the current tool
  generates deterministic smaller MuBinary sidecar artifacts while preserving
  JSON rollback.
- `mu/tools/util/seed_binary_migration.py:321-371` builds the proof chain by
  binding seed name, JSON checksum, binary checksum, migration policy,
  projection ids, size proof, and smaller-than-JSON proof.
- `mu/tools/util/seed_binary_migration.py:375-390` generates deterministic
  smaller binary sidecar bytes from an already-verified JSON seed image.
- `mu/host/js/core/seed_loader.js:522-580` mirrors the migration proof-chain
  verification fields in JavaScript.
- `reports/control_plane/n3-projection-loader-numeric-domain-policy-2026-05-14_2026-05-17.md`
  records the numeric-domain prerequisite as implemented with local evidence.
- `reports/control_plane/n3-projection-loader-js-binary-decoder-parity-2026-05-14_2026-05-18.md`
  records the JavaScript decoder-parity prerequisite as implemented with local
  evidence.
- `reports/control_plane/n3-projection-loader-seed-migration-integrity-chain-2026-05-14_2026-05-18.md`
  records the seed migration and integrity-chain prerequisite as implemented
  with local evidence.
- Same-wave control-surface authorization:
  `FOUNDER_OVERRIDE:n3-projection-loader-smaller-image-production-pilot-2026-05-14`.
