# N3 rcx_load Seed Image Boundary Adapter Lock

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14
Class: L4_ENABLER
Category: /mu structural host-debt reduction lock
Target gate: G8
Phase-A-Lock: LOCKED

FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14

## Purpose

Lock the control-plane boundary for the N3 `rcx_load` seed-image adapter slice
without accepting implementation files in this `L4_ENABLER` package.

The accepted repo truth for this lock package is the staged package plus `HEAD`,
not unstaged working-tree implementation candidates. The completed Phase A R3
reviewer proved that `HEAD` still lacks the byte-oriented seed-image adapter
symbols cited by the previous packet rewrite. Those unstaged candidates remain
outside this package and must be carried, revised, or replaced by a separate
`L4_STRUCTURAL` implementation wave with its own tracker note, wave ID,
indicator artifact, and package-bound L4 command.

## Scope

This lock package may stage exactly these same-wave files:

- `TASKS.md`
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md`
- `reports/deferred/non_blocking/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14_bridge_nonblockers.md`
- `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.json`

Read-only grounding for this packet:

- `TASKS.md:348`
- `.agent_bus/raw/phase-a-r3-4d9970bb/phase-a-r3-4d9970bb--r1-reviewer-2fd3ea86.txt`
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/cli/main.js`
- `mu/docs/core/L4MicroAbi.v0.md`

Out of scope for this lock package:

- Any `mu/` runtime, substrate, test, or ABI-doc edit.
- Any pipeline executor, recovery, bridge, commit, or hook edit.
- Any seed, registry, checksum, migration, binary-loader, ratchet-baseline,
  host-oracle, or Claude-related edit.
- Any claim that current unstaged implementation candidates are accepted repo
  truth.
- Any N3 closure, L4 completion, projection-loader elimination, or production
  binary-loader readiness claim.

## Work Items

1. Preserve the lock package as a control-plane-only `L4_ENABLER` package with
   the four staged files named above and no staged `mu/` implementation files.
2. Record the current accepted code truth for the successor implementation wave:
   `HEAD` exposes path-coupled seed loading in Python and JavaScript and does
   not expose the byte-oriented adapter symbols from the unstaged candidates.
3. Keep byte-adapter introduction, review, acceptance, cleanup, and proof in a
   later `L4_STRUCTURAL` implementation package. That package must decide
   whether to reuse, revise, or replace the current unstaged candidate edits.
4. Bind this package to the same-wave TASKS tracker note, indicator artifact,
   deferred packet, and same-wave `FOUNDER_OVERRIDE`.
5. Validate this exact staged package with:

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14
```

## Current Accepted Code Truth

The Phase A R3 completed reviewer reproduced the package-bound distinction:

- The staged package contains only `TASKS.md`, this packet, the same-wave
  deferred packet, and the same-wave L4 indicator artifact.
- `HEAD:mu/host/python/rcx_pi/selfhost/seed_integrity.py` exposes
  `def load_verified_seed(seed_path: Path, verify: bool = True)` and lacks
  `load_verified_seed_image` / `seed_image_bytes`.
- `HEAD:mu/host/js/core/seed_loader.js` exports `loadVerifiedSeed` and lacks
  `loadVerifiedSeedImage` / `seedImageBytes`.
- `HEAD:mu/host/js/cli/main.js` exposes `function loadVerifiedSeed(seedPath,
  seedName)` and lacks `loadVerifiedSeedImage` / `seedImageBytes`.
- `HEAD:mu/docs/core/L4MicroAbi.v0.md` names the current implementation as
  `seed_integrity.py:load_verified_seed()` plus `projection_loader.py`.

This packet therefore keeps byte-adapter implementation as successor work. It
does not delete that work from the queue merely because unstaged local candidate
edits exist.

## Constraints

- Do not make Python or JavaScript smarter as the objective. The successor
  implementation must reduce host-boundary debt by narrowing the loader boundary
  toward `rcx_load(image_bytes)`.
- Do not stage or accept any runtime/test/doc implementation candidate in this
  `L4_ENABLER` package.
- Do not add any fallback, dynamic seed lookup, host object-model semantics,
  relaxed validation, or one-substrate behavior.
- Do not change seed registries, checksums, projection IDs, seed locations, seed
  files, binary image formats, migration tools, or integrity-chain policy.
- Do not use unstaged working-tree state as accepted repo truth.
- Do not update host-semantics or authority-inventory baselines as proof.

## Stop Conditions

- Stop before acceptance if any `mu/` runtime, substrate, test, or ABI-doc file
  is staged with this lock package.
- Stop if the package-bound L4 command above exits nonzero.
- Stop if the packet, tracker, handoff, or bridge response claims
  control-plane-only staging without a fresh staged-name-list proof and a
  passing same-wave L4 command.
- Stop if accepting this lock package would also accept implementation, test,
  ABI-doc, pipeline executor, recovery, bridge, or hook changes.
- Stop if a proposed remediation needs files outside the four staged lock
  surfaces listed in Scope.

## Acceptance Criteria

- Phase A accepts this packet as a real plan, not a stub.
- The staged package contains exactly the four files named in Scope.
- No `mu/` runtime, substrate, test, or ABI-doc file is staged.
- The same-wave L4 command exits 0 for this exact wave ID.
- The packet explicitly names the generated deferred packet path in Scope.
- The packet distinguishes accepted repo truth from unstaged implementation
  candidates.
- The successor implementation wave remains separate and must carry its own
  `L4_STRUCTURAL` tracker note, indicator artifact, proof commands, and package
  binding.

## Grounding / Authorization

- `TASKS.md:348` authorizes this `[NEXT-CODEX-POST-REDTEAM]`
  `L4_ENABLER` lock wave, binds the
  `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14` wave ID, records
  that no runtime code is edited by this lock wave, and carries the same-wave
  `FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`.
- The completed R3 reviewer artifact
  `.agent_bus/raw/phase-a-r3-4d9970bb/phase-a-r3-4d9970bb--r1-reviewer-2fd3ea86.txt`
  supplies the blocking evidence this rewrite answers: prior text treated
  unstaged implementation candidates as accepted current code and carried stale
  package-composition/L4-failure claims.
- The current staged package proof is:
  `git diff --cached --name-only` lists only `TASKS.md`, this packet, the
  same-wave deferred packet, and the same-wave indicator artifact.
- The current same-wave L4 proof is:
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`
  exits 0 with `Wave class: L4_ENABLER`, `Changed files: 4`,
  `Runtime files: 0`, and `L4_ENABLER compliant`.

Same-wave authorization line for detector-visible L4_ENABLER handling:

`FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md`
  - `reports/deferred/non_blocking/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `f0764bbff2b037dbebe5cedda19dcd454f37864d307d2554647bce75c7266741`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14 --output reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md. (2) Commit handoff carries 4 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md`
  - `reports/deferred/non_blocking/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
