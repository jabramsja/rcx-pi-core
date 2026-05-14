# N3-Rcx-Load-Projection-Loader-Production-Test-Surface-Lock-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Purpose: Produce the bounded production/parity test-surface lock required before
any future `rcx_load` / `projection_loader` production-boundary adapter
implementation.

FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14

## Scope

This packet is a Phase A control-plane lock attempt for the N3 `rcx_load` /
`projection_loader` production-boundary adapter prerequisite. It does not
implement production loader behavior.

Write/staged scope for this Phase B reconciliation:
- `TASKS.md` same-wave tracker sync note for
  `n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14`
- `reports/control_plane/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14_2026-05-14.md`
- `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`

No runtime, test, seed, production loader, or Claude-related file is in scope.

Read/grounding scope used for the lock decision:
- `TASKS.md:342` predecessor tracker line for
  `n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14`.
- Governing predecessor packet
  `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md`,
  especially lines 55-70, 118-134, 154-162, and 255-263.
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
  active N3 section.
- `mu/docs/core/L4MicroAbi.v0.md` `rcx_load` rows and production-unchanged
  warnings.
- `mu/docs/core/L4ExitChecklist.v0.md` D010 / productionization
  prerequisites.
- `mu/docs/core/Boot0Architecture.v0.md` projection-loader primitive section.
- Current production loader paths as read-only grounding:
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py`,
  `mu/host/python/rcx_pi/selfhost/projection_loader.py`,
  `mu/host/js/core/seed_loader.js`, and `mu/host/js/cli/main.js`.
- Candidate focused test surfaces under `mu/tests/`. `tests/` is a symlink to
  `mu/tests/`, so the canonical paths below use `mu/tests/...`.

## Decision

Outcome: NO-GO for production loader implementation and NO-GO for a current
test-only Phase B prerequisite write set from this packet.

The production/parity test-surface route is real and bounded. The original
single-packet bridge attempt could not make the same-wave L4_ENABLER
authorization detector-visible, but the current staged Phase B package now
includes the required `TASKS.md` tracker sync note and same-wave
`reports/l4_wave_indicators/` artifact. Current staged validation reports
`Wave class: L4_ENABLER`, `Changed files: 3`, `Runtime files: 0`,
`Control-plane files: 0`, and `L4 Execution Contract v2: L4_ENABLER compliant`.

Therefore this packet records the no-production-implementation boundary and the
future test-surface route, not production loader behavior. The current package
contains only detector-visible control-plane authorization and packet
reconciliation. A separate future bounded test-only/control-plane wave may
write these files:
- `mu/tests/engine/test_seed_integrity.py`
- `mu/tests/structural/test_projection_loader.py`
- `mu/tests/parity/test_seed_loading_parity.py`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
- `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`

That future test-only wave may not touch:
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- `mu/host/python/rcx_pi/selfhost/projection_loader.py`
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/cli/main.js`
- production seed files or seed-format migration tooling

## Work Items

1. Reproduced the predecessor route and proof gap. `TASKS.md:342` records the
   predecessor as `[NEXT-CODEX-POST-REDTEAM]`, Class `L4_ENABLER`, with Phase B
   converged on
   `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md`,
   three wave-owned files, no test files, and package-bound L4 authority
   pending pre-commit supervisor validation. The initial packet did not claim
   `TASKS.md` already had a same-wave target tracker entry for the current wave;
   this Phase B reconciliation now accounts for the staged same-wave tracker
   note separately.
2. Line-cited the predecessor stop. The predecessor says a bounded successor
   adapter shape is plausible, but it could not lock the candidate because no
   production L4/parity test surface was in scope
   (`...production-boundary-next-slice...md:55-70`). It preserves
   stop-before-implementation conditions
   (`...production-boundary-next-slice...md:118-134`), requires the next Phase A
   packet to open and cite production/parity tests
   (`...production-boundary-next-slice...md:154-162`), and names the no-go gap as
   missing focused production L4/parity tests rather than missing production
   files (`...production-boundary-next-slice...md:255-263`).
3. Line-cited the doctrine and deferred N3 sources classifying this as a
   production-boundary adapter test-surface lock, not N3 closure and not D010
   production readiness. N3 remains active as a broad host-surface boundary
   (`repo_truth_non_blockers_2026-03-14.md:31-54`,
   `repo_truth_non_blockers_2026-03-14.md:161-175`). `rcx_load` is a Boot0
   loader ABI with deterministic, fail-closed, content-addressed, no-hidden
   channel invariants (`L4MicroAbi.v0.md:29-46`) and maps to
   `projection_loader` plus JSON parsing (`L4MicroAbi.v0.md:120-124`).
4. Inventoried the smallest current-code test surfaces that actually exercise
   loader behavior. The inventory below cites imports, code paths, and
   assertions rather than inferring from filenames.
5. Selected the explicit no-go path above because this packet is a
   production-boundary test-surface lock only. The earlier detector-visible
   authorization gap is now historical pre-refresh evidence: the staged package
   contains the same-wave `TASKS.md` tracker note and indicator artifact, but it
   still authorizes neither production loader edits nor a test-only
   implementation write set.
6. Recorded focused validation commands, ratchets, rollback expectations, and
   proof limits before any future code changes.

## Candidate Test-Surface Inventory

| Surface | Exercised code paths and assertions | Proof role |
|---------|-------------------------------------|------------|
| `mu/tests/engine/test_seed_integrity.py` | Imports `compute_checksum`, `verify_checksum`, `validate_seed_structure`, `validate_projection_ids`, `load_verified_seed`, `verify_all_seeds`, and `get_seed_path` from production `seed_integrity.py` (`test_seed_integrity.py:15-25`). It asserts valid checksums and tamper/unknown-seed failure (`test_seed_integrity.py:61-100`), structure validation for missing or malformed `meta`, `projections`, and projection fields (`test_seed_integrity.py:108-186`), projection-ID fail-closed behavior (`test_seed_integrity.py:194-252`), verified production loads and unknown verified-load rejection (`test_seed_integrity.py:260-321`), all known seed verification (`test_seed_integrity.py:329-341`), and `match_mu` / `subst_mu` / `classify_mu` verified loader integration (`test_seed_integrity.py:349-387`). | Python production loader boundary; `rcx_load` checksum/structure/projection-ID semantics; failure-mode coverage. |
| `mu/tests/structural/test_projection_loader.py` | Imports production `make_projection_loader()` and `get_seed_path()` (`test_projection_loader.py:15-16`). It asserts factory shape and loaded projection lists (`test_projection_loader.py:22-48`), defensive cache-copy behavior and cache reset (`test_projection_loader.py:54-113`), expected projection counts and unknown seed rejection (`test_projection_loader.py:119-143`), and projection ID structure/uniqueness (`test_projection_loader.py:146-192`). | Python `projection_loader.py` wrapper/caching boundary; adapter cache rollback guard; failure-mode coverage for unknown seed names. |
| `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py` | Calls production JS `loadVerifiedSeed` from `mu/host/js/core/seed_loader.js` and asserts `rcx_engine.v1.json` loads with 11 projections (`test_boundary_dispatch_authority_gate.py:141-153`). It writes temp malformed seeds and calls production `seed_loader.js` directly, asserting null, array, and scalar projection entries reject with the expected indexed type errors (`test_boundary_dispatch_authority_gate.py:658-733`). It source-locks `mu/host/js/cli/main.js` `validateSeedStructure` guard ordering before the `'id' in proj` check (`test_boundary_dispatch_authority_gate.py:734-755`) and anti-theater-locks that the malformed-projection class requires production `seed_loader.js` instead of inline simulation (`test_boundary_dispatch_authority_gate.py:764-788`). It also checks Python algorithm seed allowlist parity against JS `seedProjectionMap` keys (`test_boundary_dispatch_authority_gate.py:968-985`). | JS production loader boundary; JS CLI seed-loading path; failure-mode coverage; anti-theater binding to production code; parity source lock. |
| `mu/tests/parity/test_seed_loading_parity.py` | Declares the parity proof limits: checksum and projection-ID parity, not semantic behavior or disk-content proof (`test_seed_loading_parity.py:1-18`). It reads JS source registries and checks JS seeds are a Python subset, shared checksums match, and JS seed count is locked (`test_seed_loading_parity.py:87-120`). It checks order-sensitive projection IDs match between substrates (`test_seed_loading_parity.py:125-160`), `MU_SEED_LOCATIONS` covers checksummed seeds (`test_seed_loading_parity.py:165-182`), JS `loadVerifiedSeed` rejects an unregistered seed while Python `verify_checksum` rejects unknown seeds (`test_seed_loading_parity.py:189-221`), and core JS loader registries are a strict subset of CLI registries with matching checksums and IDs (`test_seed_loading_parity.py:248-283`). | Cross-substrate seed registry parity; JS core-vs-CLI parity; fail-closed unknown-seed parity. |
| `mu/tests/parity/test_parity_python.py` | Loads `kernel.v1.json`, `match.v2.json`, and `subst.v2.json` through production `load_verified_seed(get_seed_path(...))` (`test_parity_python.py:51-57`) and runs shared parity vectors through the kernel, asserting direct output equality and structural equality (`test_parity_python.py:83-124`). Security vectors assert kernel-reserved field rejection (`test_parity_python.py:127-152`). | Python L4 execution semantics after `rcx_load` seed loading; parity-vector baseline; security rejection semantics. |
| `mu/tests/parity/test_js_parity_automated.py` | Runs `node mu/host/js/eval_step.js` and asserts JS parity, security, recurrence, structural-trace, and core markers report zero failures (`test_js_parity_automated.py:101-153`). It runs the same parity vectors through Python and JavaScript kernels and compares actual outputs or mutual rejection (`test_js_parity_automated.py:258-338`). | JavaScript L4 execution semantics after CLI/main seed loading; cross-substrate behavioral parity proof. |
| `mu/tests/research/test_d010_h5_projection_loader_binary.py` | Header says the file is a research analog only, proves JSON parsing-component reducibility, does not change production code, and leaves production `seed_integrity.py` / `main.js` unchanged (`test_d010_h5_projection_loader_binary.py:1-16`). It explicitly excludes production seed migration, binary seed generation tooling, JS binary decoder, I/O/SHA reducibility, and validation reducibility (`test_d010_h5_projection_loader_binary.py:48-62`). Its engine parity and boundary tests compare research-decoded projections against `step_kernel_mu`, primitive count, and seed type round-trips (`test_d010_h5_projection_loader_binary.py:500-653`). | Research-only D010 evidence; not a sole production proof and not production readiness. |

## Current Production Boundary

Python:
- `load_verified_seed()` is still marked `BOOTSTRAP_PRIMITIVE:
  projection_loader`, reads seed bytes, verifies checksums, parses UTF-8 JSON
  while rejecting non-finite numeric literals, validates seed structure and
  projection IDs, and returns the parsed seed
  (`seed_integrity.py:588-636`).
- `get_seed_path()` still routes seed names through the canonical
  `MU_SEED_LOCATIONS` map and rejects unknown seed names
  (`seed_integrity.py:644-674`).
- `make_projection_loader()` still delegates to `get_seed_path()` and
  `load_verified_seed()`, caches `seed["projections"]`, and returns defensive
  JSON round-trip copies (`projection_loader.py:48-64`).

JavaScript:
- `mu/host/js/core/seed_loader.js` `loadVerifiedSeed(seedName, subdir)` reads
  seed text from disk, hashes before parse for known seeds, parses with
  `muCopy(JSON.parse(raw), true, ...)`, rejects malformed projection entries,
  rejects unknown seeds, validates projection IDs, and returns the seed
  (`seed_loader.js:186-242`).
- `mu/host/js/cli/main.js` verifies checksums (`main.js:162-169`), validates
  seed structure and projection fields (`main.js:171-187`), validates projection
  IDs (`main.js:189-201`), loads verified seed JSON (`main.js:245-252`), and
  eagerly loads the startup seed set (`main.js:261-272`). The stable
  `eval_step.js` entrypoint delegates to `cli/main.js` when run as a program
  (`eval_step.js:1-15`).

## Constraints

- Do not implement production loader behavior in this packet.
- Do not claim N3 closure or D010 production readiness.
- Do not perform broad binary-loader migration, seed migration, or production
  seed-format migration.
- Do not add Python-only or JavaScript-only semantic debt.
- Do not move Mu semantic authority into Python or JavaScript host loaders.
- Do not use a research-only D010 artifact as the sole production proof.
- Do not touch Claude-related files.
- Do not widen this bridge-remediation turn beyond the three staged
  control-plane/accounting files named above.
- Future production Phase B may not touch production loader files unless a prior
  detector-visible test-only/control-plane prerequisite wave proves the exact
  test surface, parity proof, ratchets, rollback path, and proof limits.

## Stop Conditions

Historical pre-refresh stop conditions:
- Same-wave control-surface authorization was initially present only as a packet
  token and was not detector-visible to the staged L4 checker because `TASKS.md`
  had no same-wave tracker sync note and the staged package contained no
  same-wave indicator artifact.
- That gap is now resolved for the current staged package by `TASKS.md` plus
  `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`.

Remaining stop conditions:
- Production implementation remains stopped. This packet authorizes neither
  production loader edits nor a test-only Phase B implementation.

Stop conditions not triggered for the future prerequisite route:
- Exact Python and JavaScript production/parity test files are named above.
- The future test-only path does not require broad binary-loader migration, seed
  migration, new host-only semantics, or a Python/JavaScript parity split.
- D010 productionization prerequisites are line-cited and remain out of scope.
- Current code truth shows existing partial test surfaces, but no already landed
  production adapter implementation.
- Focused parity checks, host-semantics ratchet, authority-inventory ratchet,
  rollback expectations, and proof limits are recorded below.
- The selected proof is not research-only D010 evidence or baseline-only cleanup
  evidence.

## Future Validation Commands

The future detector-visible test-only/control-plane Phase B must run these
before any later production loader implementation packet is allowed:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/engine/test_seed_integrity.py \
  mu/tests/structural/test_projection_loader.py \
  mu/tests/parity/test_seed_loading_parity.py \
  mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestJsSeedLoaderMalformedProjection \
  mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestF2ProductionBindingLock
```

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/parity/test_parity_python.py \
  mu/tests/parity/test_js_parity_automated.py::TestJSTestSuitePasses \
  mu/tests/parity/test_js_parity_automated.py::TestCrossSubstrateParity
```

```bash
node mu/host/js/eval_step.js
```

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged
```

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
```

```bash
python3 tools/checks/check_host_authority_inventory_ratchet.py
```

If that future test-only wave creates a staged package, it must preserve the
same-wave control-surface authorization in a detector-visible tracker/indicator
handoff and must not use commit, push, or merge bypasses.

## Rollback Expectations

- Current control-plane package rollback: remove only this packet, the
  same-wave `TASKS.md` tracker note, and the same-wave indicator artifact from
  the staged package. No runtime, test, seed, or Claude-related file is part of
  this wave.
- Future tracker/indicator authorization rollback: revert only the same-wave
  tracker note and indicator artifact created by that later authorized
  control-surface wave.
- Future test-only prerequisite rollback: revert only the touched test files and
  successor control-plane packet. Production loader files remain untouched.
- Later production-adapter rollback, if authorized by a separate packet: restore
  current JSON loader behavior in both Python and JavaScript, keep checksum and
  projection-ID registries fail-closed, and re-run the future validation command
  set above.
- Rollback must not remove D010 proof-class warnings or convert research-only
  evidence into production readiness.

## Proof Limits

- This packet proves a bounded test-surface route exists and that the current
  staged package is detector-visible as `L4_ENABLER`. It does not lock or
  implement production loader behavior, test-only changes, binary TLV loading,
  or seed migration.
- Existing tests prove current JSON loader behavior and parity surfaces only to
  the cited assertions. They do not prove a binary TLV production loader, seed
  migration tooling, binary-format integrity chain, or full L4 completion.
- `mu/tests/research/test_d010_h5_projection_loader_binary.py` remains
  research-only. `L4ExitChecklist.v0.md:205-216` requires separate
  productionization gates for any "reduced in production" claim, including JS
  TLV decoder parity, seed migration tooling, binary integrity-chain policy,
  int-range policy, and NaN/Inf policy.
- N3 remains active. The active deferred source says future broad host-surface
  reduction must be routed through separate bounded packets and must not move
  more semantic authority into Python or JavaScript host code
  (`repo_truth_non_blockers_2026-03-14.md:161-175`).

## Acceptance Criteria

- The packet contains concrete Phase A sections for Scope, Work Items,
  Constraints, Stop Conditions, Acceptance Criteria, and Grounding /
  Authorization.
- The packet cites the same-wave control-surface authorization required for
  automation:
  `FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14`.
- The packet binds to `TASKS.md:342` predecessor authorization, governing packet
  line ranges, and the current staged same-wave `TASKS.md` tracker note without
  claiming the initial single-packet bridge attempt already had that tracker
  surface.
- The selected next path is an explicit no-go for production implementation and
  current test-only implementation while recording that the historical missing
  detector-visible prerequisite evidence is now staged as a same-wave `TASKS.md`
  tracker sync note plus same-wave indicator artifact.
- Any future implementation packet has exact file paths, focused tests, parity
  checks, host-semantics ratchet, authority-inventory ratchet, rollback path,
  and proof limits recorded before code changes.
- Acceptance does not close N3, does not authorize production loader behavior,
  and does not convert D010 research evidence into production readiness.

## Grounding / Authorization

Same-wave control-surface authorization token required for automation:

`FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14`

Detector-visible authorization state:
- Current `git status --short` reports exactly three staged files:
  `TASKS.md`, this packet, and
  `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`.
- Current `rg -n "n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14|production-test-surface-lock" TASKS.md STATUS.md CHANGELOG.md reports/README.md reports/control_plane reports/l4_wave_indicators`
  finds the wave ID in the same-wave `TASKS.md` tracker note, this packet, and
  the same-wave indicator artifact. It is not required to appear in
  `STATUS.md`, `CHANGELOG.md`, or `reports/README.md` for this no-go
  prerequisite packet.
- Current `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14`
  reports `Wave class: L4_ENABLER`, `Changed files: 3`, `Runtime files: 0`,
  `Control-plane files: 0`, and `L4 Execution Contract v2: L4_ENABLER compliant`.
- Historical pre-refresh evidence showed the current wave ID only in this packet
  and the staged L4 check as `Wave class: (none)`, `Changed files: 1`,
  `Runtime files: 0`, `Control-plane files: 0`, and
  `L4 Execution Contract v2: no-class compliant`. That evidence explains why
  the tracker/indicator refresh was required, not the current staged truth.
- Because `reports/README.md:7` defines `reports/control_plane/` as tracked
  founder-facing packets referenced by `TASKS.md`, the same-wave tracker note is
  a policy-bound authorization surface rather than a production-code blocker.

Predecessor authorization:
- `TASKS.md:342` records predecessor wave
  `n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14` as
  `[NEXT-CODEX-POST-REDTEAM]`, Class `L4_ENABLER`, target gate `G8`, with Phase
  B converged on the predecessor control-plane packet, three wave-owned files,
  no test files, and package-bound L4 authority pending pre-commit supervisor
  validation.
- Predecessor packet lines 55-70 require this packet to ground focused
  production/parity tests before selecting an adapter write set or no-go.
- Predecessor packet lines 118-134 preserve stop-before-implementation
  conditions, including no broad binary-loader migration, no host-only
  semantics, no parity split, no unsatisfied D010 productionization
  prerequisites, and same-wave control-surface authority before commit
  automation.
- Predecessor packet lines 154-162 require exact write set, tests, parity
  checks, ratchets, rollback path, and proof limits before future Phase B
  implementation.
- Predecessor packet lines 255-263 identify the no-go evidence gap as missing
  focused production L4/parity tests and warn that research-only D010 evidence
  cannot be sole production proof.

Doctrine:
- `L4MicroAbi.v0.md:29-46` defines `rcx_load(image_bytes) -> state` and its
  deterministic, fail-closed, content-addressed, no-hidden-channel invariants.
- `L4MicroAbi.v0.md:157-165` says the binary-format path is a classification
  status, not production completion.
- `L4ExitChecklist.v0.md:115-128` defines the loader content-addressed
  objective and proof command class.
- `L4ExitChecklist.v0.md:205-216` locks productionization prerequisites and the
  research-evidence boundary.
- `L4ExitChecklist.v0.md:224-232` says D010 resolves JSON reducibility as
  research evidence while production seeds remain JSON.
- `Boot0Architecture.v0.md:64-76` keeps `projection_loader` as the current
  Boot0 primitive that loads JSON, with stable semantics and possible future
  format evolution.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

Questions? Concerns? Thoughts? -- Think hard

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14_2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `768edf5a2737203a597e9d79fda6d74aa1af1a6d4a838a6156a9852462cb3eeb`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14 --output reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14_2026-05-14.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-test-surface-lock-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
