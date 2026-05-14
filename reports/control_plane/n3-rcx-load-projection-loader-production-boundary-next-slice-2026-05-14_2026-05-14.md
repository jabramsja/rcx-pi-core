# N3-Rcx-Load-Projection-Loader-Production-Boundary-Next-Slice-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Convert the routed N3 `rcx_load` / `projection_loader` successor into a
grounded Phase A decision after the source-lock wave. The grounded outcome is a
no-go for production implementation from this packet because the scoped evidence
does not include a production proof/test surface capable of locking an exact
production-boundary adapter write set.

FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14

## Scope

Writable control-surface repair scope for this Phase B rewrite:
- `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md`
- `TASKS.md`
- `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`

Read-only grounding scope opened for this decision:
- `TASKS.md:340`
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:31-54`
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175`
- `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md:18-20`
- `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md:67-98`
- `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md:141-150`
- `mu/docs/core/L4MicroAbi.v0.md:29-46`
- `mu/docs/core/L4MicroAbi.v0.md:120-124`
- `mu/docs/core/L4MicroAbi.v0.md:157-165`
- `mu/docs/core/L4ExitChecklist.v0.md:115-128`
- `mu/docs/core/L4ExitChecklist.v0.md:183-188`
- `mu/docs/core/L4ExitChecklist.v0.md:199-216`
- `mu/docs/core/L4ExitChecklist.v0.md:226-232`
- `mu/docs/core/Boot0Architecture.v0.md:64-80`
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py:588-636`
- `mu/host/python/rcx_pi/selfhost/projection_loader.py:48-64`
- `mu/host/js/core/seed_loader.js:186-242`
- `mu/host/js/cli/main.js:245-252`
- `mu/tests/research/test_d010_h5_projection_loader_binary.py:1-66`
- `mu/tests/research/test_d010_h5_projection_loader_binary.py:500-653`

This packet does not authorize production loader changes, binary seed-image
migration, new host-only semantics, a Python/JS parity split, or N3 closure.

## Decision

Outcome: no-go for a Phase B production-boundary implementation lock in this
packet.

The preferred bounded successor shape remains architecturally plausible: a
future adapter/gate could narrow `rcx_load` / `projection_loader` by separating
file I/O from deterministic seed-image bytes verification and JSON parsing in
both Python and JavaScript, without moving to the full binary TLV seed format.
That candidate cannot be locked here because the current scoped write/test set
does not contain a production L4/parity test surface for such an adapter.

Required next packet: create a bounded Phase A production-boundary adapter
test-surface lock for `rcx_load` / `projection_loader`. That packet must first
ground and authorize the focused production/parity test files needed to prove
the adapter in both substrates, then choose either:
- one exact production adapter write set with focused tests, parity checks,
  host-semantics ratchet, authority-inventory ratchet, and rollback path; or
- a narrower no-go packet naming the next missing prerequisite.

N3 remains active.

## Work Items

1. Reproduced the current authorization baseline from `TASKS.md:340`: the
   predecessor `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14`
   Phase B converged, carried package-bound L4 authority pending pre-commit
   supervisor validation, and is the immediate source-lock predecessor for this
   successor.
2. Opened every scoped grounding file named by the locked plan and recorded
   line-cited facts distinguishing source-lock evidence, production-path
   evidence, D010 research-only evidence, and architectural prerequisites.
3. Chose exactly one Phase A successor outcome: no-go / next-wave packet. The
   preferred production-boundary adapter slice is not locked because the scoped
   evidence cannot prove an exact production and test write set without widening
   beyond this packet.
4. Did not lock a future Phase B production write set. The missing prerequisite
   is a source-grounded production/parity test surface for any adapter that
   changes `/mu` loader behavior.
5. Kept pending work truthful against current code: current production remains
   JSON loader truth in both Python and JavaScript, and D010 remains
   research-only parsing-component reducibility evidence rather than production
   readiness.
6. Preserved dispatcher-owned Phase A / Phase B routing. This packet is a
   control-plane no-go / next-wave packet only; manual production repair is not
   authorized here.

## Constraints

- Do not implement production loader changes in this Phase A rewrite.
- Do not inspect unrelated dirty files, `git diff`, `git status`, or unrelated
  executor/test changes for this packet repair.
- Do not widen beyond the scoped grounding paths from this packet.
- Do not claim N3 closure.
- Do not implement broad binary-loader migration in one wave.
- Do not add Python-only or JS-only semantic debt. If `/mu` production is
  touched later, prefer Mu-programmed behavior or narrower bootstrap
  assumptions over smarter host loaders.
- Do not treat candidate-space examples as pre-approved implementation scope.
- Do not touch Claude-related files.
- Do not use `mu/tests/research/test_d010_h5_projection_loader_binary.py` as a
  production readiness gate. It is research-only evidence under the cited docs
  and test header.
- Visible operator summaries for this wave must end with:
  `Questions? Concerns? Thoughts? -- Think hard`

## Stop Conditions

Triggered stop condition:
- The scoped grounding cannot prove one bounded production-boundary slice with
  exact production and test write sets. The production files are in scope, but
  the only focused test file in scope is explicitly research-only.

Additional stop-before-implementation conditions preserved for the next packet:
- Stop if a candidate requires broad binary-loader migration, seed migration,
  new host-only semantics, a Python/JS parity split, or D010 productionization
  prerequisites that cannot be line-cited and satisfied.
- Stop if current code truth proves the candidate is already landed, obsolete,
  or narrower than the packet wording implies.
- Stop if focused parity, host-semantics ratchet, authority-inventory ratchet,
  or rollback expectations cannot be stated before code changes.
- Stop if same-wave control-surface authority is missing or cannot be made
  detector-visible before commit automation.
- Stop if the packet attempts to close N3 from a baseline-only cleanup or from
  research-only D010 evidence.

## Acceptance Criteria

This Phase A no-go / next-wave packet is acceptable when:
- It contains concrete `Scope`, `Work Items`, `Constraints`, `Stop Conditions`,
  `Acceptance Criteria`, and `Grounding / Authorization` sections.
- It cites the predecessor source-lock authority at `TASKS.md:340` and records
  the same-wave successor tracker note at `TASKS.md:341` so the
  `FOUNDER_OVERRIDE` is detector-visible.
- It includes a same-wave
  `FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14`
  line for control-surface L4_ENABLER automation.
- It preserves the stop-before-implementation boundary and does not authorize
  production code edits by this rewrite.
- It requires the next Phase A grounding pass to remove any already-landed item
  from pending work and acceptance criteria instead of relisting it as
  unresolved.
- It leaves N3 active unless future evidence independently proves closure.

A future Phase B implementation packet may lock only after:
- The next Phase A packet opens and line-cites the production/parity test
  surfaces that are outside this packet's scoped write set.
- Exactly one production-boundary adapter slice is chosen, or a narrower no-go /
  next-wave packet is produced.
- The exact write set, focused tests, parity checks, host-semantics ratchet,
  authority-inventory ratchet, rollback path, and proof limits are recorded.
- D010 remains classified as research-only unless the future packet separately
  satisfies the D010 productionization prerequisites.

## Grounding / Authorization

Source-lock authorization:
- `TASKS.md:340` records
  `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14` as a
  converged Phase B package with package-bound L4 authority pending pre-commit
  supervisor validation. That is the immediate predecessor authority for this
  successor packet.
- `TASKS.md:342` now records this same-wave production-boundary successor
  no-go packet, binding the control-plane packet, indicator artifact, and
  `FOUNDER_OVERRIDE` to one detector-visible L4_ENABLER wave id without
  authorizing production loader edits.
- The predecessor packet states that the implemented source-lock completed the
  selected N3 `rcx_load` / `projection_loader` image boundary as a
  control-plane plan only and did not implement, migrate, or reduce the
  production loader
  (`reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md:18-20`).
- The predecessor packet locks current production truth as Python/JS JSON seed
  loading and explicitly says live production binary-loader reduction was not
  authorized there
  (`reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md:67-80`).
- The predecessor packet classifies D010 as research-only and leaves N3 open
  (`reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md:82-98`).

Active N3 boundary:
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:31-54`
  and `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175`
  keep N3 active as a broad host-surface boundary and require future reductions
  to route through separate bounded packets with file scope, validation, and no
  semantic authority moved into Python or JavaScript host code.

Architectural prerequisites:
- `mu/docs/core/L4MicroAbi.v0.md:29-46` defines `rcx_load(image_bytes) -> state`
  with deterministic, fail-closed, content-addressed, no-hidden-channel
  invariants and maps current implementation to `load_verified_seed()` plus
  `projection_loader.py`.
- `mu/docs/core/L4MicroAbi.v0.md:120-124` maps `rcx_load` to Boot0
  `projection_loader` plus JSON parsing.
- `mu/docs/core/L4MicroAbi.v0.md:157-165` classifies the binary-format path as
  reducible while warning that production completion claims require separate
  productionization evidence.
- `mu/docs/core/L4ExitChecklist.v0.md:115-128` requires the loader to validate
  JSON seeds and SHA256 checksums with no I/O beyond the seed directory.
- `mu/docs/core/L4ExitChecklist.v0.md:183-188` classifies
  `projection_loader` as `REDUCIBLE_WITH binary format` through D010, while
  stating that production `projection_loader` is unchanged and I/O, integrity,
  and validation are out of scope.
- `mu/docs/core/L4ExitChecklist.v0.md:199-216` locks the rule that production
  reduction claims require separate productionization gates and lists the D010
  prerequisites: int-range policy, NaN/Inf policy, JS TLV decoder, seed
  migration tooling, and binary-format integrity-chain policy.
- `mu/docs/core/L4ExitChecklist.v0.md:226-232` says JSON dependency is
  reducible by D010, but production seeds remain JSON and no migration is
  planned in that classification evidence.
- `mu/docs/core/Boot0Architecture.v0.md:64-80` keeps `projection_loader` as a
  Boot0 primitive that currently loads JSON, with stable semantics and a future
  possible smaller substrate.

Production-path evidence:
- Python `load_verified_seed()` is still the `projection_loader` bootstrap
  primitive, reads seed bytes from a path, verifies checksum, parses UTF-8 JSON
  with `json.loads(...)`, validates structure and projection IDs, and returns
  the seed (`mu/host/python/rcx_pi/selfhost/seed_integrity.py:588-636`).
- Python `make_projection_loader()` still gets a seed path, delegates to
  `load_verified_seed(seed_path)`, caches `seed["projections"]`, and returns
  JSON round-trip deep copies
  (`mu/host/python/rcx_pi/selfhost/projection_loader.py:48-64`).
- JS core `loadVerifiedSeed(seedName, subdir)` still reads UTF-8 seed text from
  disk, verifies known seed checksums before parsing, parses JSON through
  `muCopy(JSON.parse(raw), true, ...)`, validates projection entries and IDs,
  and returns the seed (`mu/host/js/core/seed_loader.js:186-242`).
- JS CLI `loadVerifiedSeed(seedPath, seedName)` still reads UTF-8 seed text,
  verifies checksum, parses JSON through Stage0 `muCopy`, validates structure
  and projection IDs, and returns the seed (`mu/host/js/cli/main.js:245-252`).

D010 research-only evidence:
- The D010 test header states that the file is a research analog only, proves
  JSON parsing-component reducibility, does not change production code, and
  leaves production `seed_integrity.py` / `main.js` unchanged
  (`mu/tests/research/test_d010_h5_projection_loader_binary.py:1-16`).
- The same header says I/O, integrity, and validation are out of scope; the
  explicit non-goals include production seed migration, binary seed generation
  tooling, JS cross-substrate binary decoder, I/O/SHA reducibility, and seed
  validation reducibility
  (`mu/tests/research/test_d010_h5_projection_loader_binary.py:48-62`).
- D010 engine parity and boundary tests exercise research-decoded projections
  against `step_kernel_mu`, primitive count, and seed type round-trips
  (`mu/tests/research/test_d010_h5_projection_loader_binary.py:500-653`), but
  those tests do not provide a production adapter/parity gate for changing the
  live Python and JS loaders.

No-go evidence gap:
- The scoped production files are enough to identify the current JSON loader
  boundary, but not enough to lock a future production implementation because
  this packet does not authorize a focused production L4/parity test file.
- The only scoped test file is explicitly research-only. Using it as the sole
  production proof would violate the D010 proof-class boundary cited above.
- Therefore this packet must stop before Phase B production implementation and
  leave the next bounded Phase A task to ground and authorize the missing
  production/parity test surface.

Same-wave authorization line for detector-visible control-surface L4_ENABLER handling:

`FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14`

Same-wave tracker/indicator binding:
- `TASKS.md:341`
- `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `40d674be0c86dd1875957ba6d69e4bef46253ece9466792b70fa568a43365fe5`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14 --output reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14_2026-05-14.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-production-boundary-next-slice-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
