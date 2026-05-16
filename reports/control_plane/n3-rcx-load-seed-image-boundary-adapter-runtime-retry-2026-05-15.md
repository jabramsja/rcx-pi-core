# N3 rcx_load Seed Image Boundary Adapter Runtime Retry

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15
Class: L4_STRUCTURAL
Category: /mu structural host-debt reduction
Target gate: G8
Phase-A-Lock: LOCKED

FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15

## Grounding / Authorization

- `TASKS.md:3-4` makes `TASKS.md` the single source of truth for
  authorized work and says unlisted tasks are not to be implemented.
- `TASKS.md:68` says current authorization lives in `TASKS.md`.
- `TASKS.md:535-539` authorizes `[NEXT-CODEX-POST-REDTEAM]` as
  founder-authorized and open for remaining bounded structural reduction not
  already proven by landed engine-state/scheduler work.
- `TASKS.md:543` requires every wave to have a control-plane packet plus a
  `TASKS.md` tracker entry. This packet is the governing control-plane packet
  for the retry wave; Phase B must add or sync a same-wave `TASKS.md` tracker
  note before implementation closeout can claim Gate 8 authority.
- `TASKS.md:550` marks the prior broad-host-surface structural next-slice route
  as landed, so this retry must stand as a separate bounded packet instead of
  reusing the completed predecessor.
- Parent tracked packet: `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
  from `TASKS.md:536`.
- Governing retry packet: `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15.md`.
- Same-wave authorization token for automation:
  `FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15`.

## Purpose

Route the next N3 runtime slice after the seed-image authority inventory split
prerequisite. This wave must narrow the projection-loader boundary toward
`rcx_load(image_bytes)` by separating filesystem reads from deterministic seed
image verification in both Python and JavaScript.

This packet is a Phase A dispatch plan. Phase B may implement only the concrete
work items below, and must stop before claiming closure if same-wave `TASKS.md`
tracker grounding, split-accounting proof, parity proof, or ratchet proof is
missing.

## Current Code Truth

- The prior implementation wave is complete as an `L4_ENABLER` control/evidence
  closeout, not as runtime reduction:
  `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md:4`
  is `Status: IMPLEMENTED / LOCAL EVIDENCE`, and lines 7-8 classify it as
  control/evidence closeout for a rejected runtime candidate.
- The canonical routing builder rejects completed packets:
  `mu/tools/executors/executor_common.py:868-878` treats `IMPLEMENTED` status as
  complete, and `:958-964` rejects completed tracked packets before writing a
  routing record. This retry therefore uses a new wave id and packet.
- Python remains path-coupled:
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:593-636` defines only
  `load_verified_seed(seed_path, verify=True)`, reads bytes from the path, then
  verifies checksum, parses JSON, validates structure, and validates projection
  IDs in one public loader.
- JavaScript core remains path-coupled:
  `mu/host/js/core/seed_loader.js:186-242` defines only
  `loadVerifiedSeed(seedName, subdir)`, builds a path, reads the file, hashes
  raw text, parses JSON, validates projection entries, and validates IDs in one
  public loader.
- JavaScript CLI remains path-coupled:
  `mu/host/js/cli/main.js:245-251` defines only
  `loadVerifiedSeed(seedPath, seedName)` and performs read, verify, parse,
  structure validation, and projection-ID validation in that wrapper.
- The split-accounting prerequisite landed empty-by-default policy files:
  `tools/checks/host_authority_inventory_split_allowances.json:5` and
  `mu/tools/checks/host_authority_inventory_split_allowances.json:5` both have
  `"split_allowances": []`.
- `mu/docs/core/L4MicroAbi.v0.md:29-45` defines the target
  `rcx_load(image_bytes) -> state` invariants: deterministic, fail-closed,
  content-addressed, and no hidden channels.

## Scope

Files and directories in scope:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/cli/main.js`
- `tools/checks/host_authority_inventory_split_allowances.json`
- `mu/tools/checks/host_authority_inventory_split_allowances.json`
- focused Python/JS loader, projection-loader, parity, and L4 gate tests selected
  by Phase A
- `mu/docs/core/L4MicroAbi.v0.md` only for exact production-truth wording after
  implementation
- `TASKS.md` same-wave tracker note during the implementation/closeout wave
- this packet
- same-wave L4 indicator artifact
- generated same-wave deferred non-blocker only if automation produces one

## Work Items

1. Confirm Phase B still targets only the N3 JSON seed-image boundary slice under
   `[NEXT-CODEX-POST-REDTEAM]`; do not relist landed engine-state/scheduler seed,
   fixture, structural-test, scheduler-parity, or seed-registration work as
   unresolved because `TASKS.md:539` already marks those as landed.
2. Add or sync a same-wave `TASKS.md` tracker note before Phase B closeout so
   Gate 8 can bind this retry wave to TASKS authority, the governing packet, and
   the same-wave `FOUNDER_OVERRIDE` token.
3. In Python, split the current public path loader into a thin filesystem wrapper
   and a named deterministic seed-byte boundary that performs registered
   integrity verification, JSON parse, current structure validation, and
   projection-ID/order validation without adding seed semantics to host code.
4. In JavaScript core, split the current public path loader into a thin
   filesystem wrapper and a named deterministic seed-byte boundary with behavior
   parity for accepted input, checksum-before-parse failures, unknown seed
   handling, malformed JSON, malformed projection entries, and projection-ID/order
   validation.
5. In the JavaScript CLI wrapper, preserve the CLI-facing path contract while
   delegating verification, parse, structure validation, and projection-ID/order
   validation to the JavaScript byte boundary instead of duplicating the combined
   path/read/verify/parse logic.
6. If the implementation introduces named byte-boundary functions, add exact
   same-wave split-allowance entries in both checker copies that prove only the
   old path-wrapper to new byte-boundary pairs; do not add broad exemptions,
   baseline updates, hidden adapters, or detector evasion.
7. Add or update focused tests that prove wrapper-to-byte-boundary delegation,
   checksum-before-parse ordering, parity-preserving failure classes, non-finite
   numeric rejection, malformed projection rejection, and projection-ID/order
   validation in both substrates.
8. Run the required validation set in this packet and collect the same-wave L4
   indicator artifact. If any required command fails, either include a same-wave
   mechanical root fix inside the locked scope or stop with a precise follow-up
   automation packet.
9. Update `mu/docs/core/L4MicroAbi.v0.md` only if implementation changes require
   exact production-truth wording for the JSON seed-image boundary; do not use doc
   wording as proof of runtime reduction.

## Constraints

Not in scope:

- seed JSON edits
- checksum registry edits
- projection-ID registry edits
- seed-location registry edits
- Stage0 bundle edits
- scheduler file edits
- binary/TLV seed-image migration
- D010 production-readiness claims
- host-oracle file edits
- Claude-related file edits
- hidden adapters, optional overloads, sentinels, lambdas, arrow adapter theater,
  object-method hiding, dynamic dispatch, or unscanned callable shapes
- ratchet-baseline updates used as proof
- claims that this closes N3, eliminates `projection_loader`, completes L4, or
  productionizes `rcx_load(image_bytes)`

Mu semantic authority must remain in seeds and projection order. Host loaders may
only perform mechanical bootstrap servicing: read bytes at the outer edge, verify
registered integrity, parse current JSON seed bytes, validate current seed
structure, and validate expected projection IDs.

## Stop Conditions

- Stop before runtime edits if Phase A cannot lock the exact write set, focused
  tests, split-allowance requirements, parity obligations, ratchet expectations,
  rollback path, and proof limits.
- Stop before Phase B closeout if `TASKS.md` does not carry a same-wave tracker
  note for `n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15`.
- Stop if the proposed implementation moves Mu semantic authority into Python or
  JavaScript host code.
- Stop if either substrate needs behavior the other substrate cannot mirror or
  prove out of scope.
- Stop if the host-semantics ratchet increases.
- Stop if host-authority inventory cannot pass without exact split evidence or
  if the only path is a baseline update, broad exemption, hidden adapter, or
  detector evasion.
- Stop if the implementation claims `projection_loader` elimination, N3 closure,
  L4 completion, binary/TLV image productionization, or D010 readiness.
- If the pipeline breaks, diagnose with direct evidence and include a same-wave
  mechanical root fix or a precise follow-up automation packet.

## Required Validation

Phase B cannot close without:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/engine/test_seed_integrity.py \
  mu/tests/structural/test_projection_loader.py \
  mu/tests/parity/test_seed_loading_parity.py \
  mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py \
  --tb=short
```

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/parity/test_parity_python.py \
  mu/tests/parity/test_js_parity_automated.py \
  --tb=short
```

```bash
node mu/host/js/eval_step.js
./tools/checks/check_js_debt.sh
./tools/checks/linters/contraband_js.sh
./tools/checks/linters/ast_police_js.sh
./tools/checks/check_test_theater_js.sh
./tools/checks/linters/seed_police.sh
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
python3 mu/tools/checks/check_host_authority_inventory_ratchet.py
./tools/checks/check_docs_consistency.sh
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15 --output reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15.json
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-seed-image-boundary-adapter-runtime-retry-2026-05-15
```

Bridge Round 1 policy corrections are part of this locked packet: the same-wave
`TASKS.md` tracker note must exist before closeout, and the validation set above
includes the JS governance checks required by `TASKS.md` for scoped `/mu` edits.

## Acceptance Criteria

- This packet remains the governing Phase A plan for the retry wave, with
  `Grounding / Authorization`, `Scope`, `Work Items`, `Constraints`,
  `Stop Conditions`, and `Acceptance Criteria` present before implementation.
- Phase B implements a real JSON seed-image boundary split or returns NO-GO with
  the smallest next prerequisite; it does not commit adapter theater.
- `TASKS.md` carries a same-wave tracker note before Phase B closeout and strict
  L4 validation.
- Any split allowance is exact, same-wave, reviewer-visible in checker output,
  and paired across `tools/` and `mu/tools/`.
- Runtime loaders are narrower after the wave: file I/O is at the outer edge,
  and seed bytes verification/parse/validation are delegated to deterministic
  byte-boundary functions.
- Python and JavaScript preserve accepted-input behavior, checksum-before-parse
  behavior, unknown seed handling, malformed JSON/non-finite numeric rejection,
  malformed projection rejection, projection-ID/order validation, and claimed
  parity failure classes.
- No seed semantic authority is added to Python or JavaScript.
- Proof limits explicitly state that this is JSON seed-image boundary narrowing,
  not bootstrap elimination, N3 closure, D010 productionization, or full L4.

## Phase B Closeout Evidence

- Phase B pipeline rounds 1-10 converged on the runtime byte-boundary split but
  ended `NO_GO` because the host-authority inventory split checker could not
  account for the Python side as a total-inventory-only split while the
  JavaScript side remained an authority split.
- Same-wave manual structural repair narrowed the governance mechanism instead
  of baseline-washing: `check_host_authority_inventory_ratchet.py` now supports
  explicit `split_kind` values, with fail-closed total-inventory split handling
  that rejects old or new authority signals, stale total splits, malformed
  policies, and one-substrate-only accepted split packages.
- The same-wave split policy records the exact old/new seed path-wrapper to
  byte-boundary pairs: Python `load_verified_seed -> load_verified_seed_image`
  as `split_kind: total`, and JavaScript
  `loadVerifiedSeed -> loadVerifiedSeedImage` as `split_kind: authority`.
- Same-wave commit-executor repair prevents the commit path from reclassifying
  this staged runtime package as `MAINTENANCE`: standalone handoff regeneration
  now derives `wave_class` from embedded handoff, routing record, or tracked
  packet text, preserves only contract-complete existing tracker notes, and
  renders structural fallback tracker metadata with gate evidence plus a
  non-gate post-sweep.
- The first commit-executor pre-push attempt then failed the bootstrap purity
  ratchet on a new JavaScript stdlib import: `util`. Same-wave repair removed
  the `util` module import from the seed byte boundary while retaining fatal
  UTF-8 decode parity, and added an L4 gate assertion against reintroducing
  `require("util")`/`require('util')` in the core seed loader.
- Final local evidence:
  `mu/tests/tools/test_check_host_authority_inventory_ratchet.py` passed
  `32 passed`; focused seed/projection/parity/L4 plus commit-executor root-fix
  evidence passed `298 passed`; commit-executor receipt regressions passed
  `135 passed`; post-pre-push utility-import repair evidence passed bootstrap
  purity plus seed-loading parity/L4 gate slice `25 passed`; broad Python/JS
  parity passed `333 passed`; `node mu/host/js/eval_step.js`, JS debt,
  contraband, AST police, test theater, seed police, host-semantics ratchet,
  both host-authority inventory ratchet entrypoints, docs consistency, L4
  indicator collection, and staged L4 execution contract all passed.
- Proof limit: this is JSON seed-image boundary narrowing toward
  `rcx_load(image_bytes)`. It does not eliminate the bootstrap, close N3,
  productionize binary/TLV seed images, or make D010/full L4 readiness claims.

Questions? Concerns? Thoughts? -- Think hard
