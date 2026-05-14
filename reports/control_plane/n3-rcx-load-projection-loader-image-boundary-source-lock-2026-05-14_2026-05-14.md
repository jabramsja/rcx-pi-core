# N3-Rcx-Load-Projection-Loader-Image-Boundary-Source-Lock-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14
Class: L4_ENABLER
Target gate: G8
Phase-A-Lock: LOCKED
Purpose: Source-lock the selected N3 `rcx_load` / `projection_loader`
image-boundary successor as a control-plane enabler, bind the same-wave tracker
and indicator artifact, and leave production loader semantics unchanged.

FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14

## Scope

This implemented source-lock completes the selected N3 `rcx_load` /
`projection_loader` image boundary as a control-plane plan only. It did not
implement, migrate, or reduce the production loader.

Completed source-lock write scope:
- `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md`
- `TASKS.md` same-wave tracker sync note for `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14`
- `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`

Read-only grounding scope for the completed source-lock wave:
- `TASKS.md` lines for `[NEXT-CODEX-POST-REDTEAM]`
- `reports/control_plane/n3-active-boundary-grounding-route-lock-2026-05-14_2026-05-14.md:98-109`
- `reports/control_plane/n3-active-boundary-grounding-route-lock-2026-05-14_2026-05-14.md:207-220`
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175`
- `mu/docs/core/L4MicroAbi.v0.md:29-46`
- `mu/docs/core/L4MicroAbi.v0.md:120-124`
- `mu/docs/core/L4MicroAbi.v0.md:157-165`
- `mu/docs/core/L4ExitChecklist.v0.md:183-188`
- `mu/docs/core/L4ExitChecklist.v0.md:207-216`
- `mu/docs/core/Boot0Architecture.v0.md:64-80`
- `mu/tests/research/test_d010_h5_projection_loader_binary.py:1-66`
- `mu/tests/research/test_d010_h5_projection_loader_binary.py:500-653`

Production source truth opened by this Phase B:
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py:588-636`
- `mu/host/python/rcx_pi/selfhost/projection_loader.py:48-64`
- `mu/host/js/core/seed_loader.js:186-242`
- `mu/host/js/cli/main.js:245-252`

No runtime, seed, scheduler, registry, parity-semantics, host-oracle, Claude,
hidden/local-memory, or Codex-local binary/cache file was writable in this
L4_ENABLER source-lock wave.

- Generated same-wave Phase B/commit bridge findings packet, now closed by the
  DOC_ACCURACY closeout wave:
  - original active path:
    `reports/deferred/non_blocking/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers.md`
  - archived closed path:
    `reports/archive/deferred/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers_closed-by-n3-source-lock-doc-accuracy-closeout-2026-05-14.md`
  - No unrelated deferred report was authorized by this source-lock wave.

## Boundary / Production Truth Lock

Selected boundary:
- The predecessor route-lock selects exactly the `rcx_load` /
  `projection_loader` image-boundary source-lock successor and excludes all
  Micro-ABI work, all bootstrap primitives, engine-pipeline module work, Stage0
  follow-ons, and baseline/doc-only cleanup.

Current production truth:
- Python production loading remains JSON loader truth: `load_verified_seed()`
  reads raw seed bytes, verifies the current JSON checksum, parses
  `content.decode("utf-8")` with `json.loads(...)`, rejects non-finite JSON
  constants through `parse_constant`, validates seed structure and projection
  IDs, and returns the seed.
- Python `projection_loader` currently delegates to `load_verified_seed()` and
  uses JSON round-trips only for cache deep-copying; it does not decode a binary
  seed image.
- JavaScript production seed loading remains UTF-8 JSON loader truth through
  `fs.readFileSync(..., "utf8")`, SHA verification, `JSON.parse(...)`,
  projection ID validation, and Mu copy/validation in the JS loader paths.
- Therefore the production path unchanged claim is source-locked for this wave:
  live production binary-loader reduction is not authorized here.

D010 research classification:
- `mu/tests/research/test_d010_h5_projection_loader_binary.py` remains research
  / parsing-component reducibility evidence only. It demonstrates a custom TLV
  parsing component and engine-level parity for research fixtures, but does not
  authorize production seed migration, JS binary decoder parity, I/O changes,
  SHA/integrity-chain changes, validation-chain changes, or live production
  loader reduction.

Future productionization requirement:
- Any later production binary-loader reduction requires a separate
  L4_STRUCTURAL wave covering int-range policy, NaN/Inf policy, JS TLV decoder
  parity, seed migration tooling, and integrity-chain policy. This wave must
  not claim that D010 makes the live production loader binary-ready.

N3 status:
- N3 remains open. This wave identifies and source-locks one bounded successor
  surface only; it does not close broad N3 host-surface residue.

## Work Items

1. Completed this successor control-plane packet as the bounded Phase A source-lock for `rcx_load` / `projection_loader` image-boundary scope selected by the predecessor route-lock.
2. Added the detector-visible same-wave `TASKS.md` tracker sync note for `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14` before commit-supervisor and L4 contract enforcement.
3. Collected the L4 indicator artifact at `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`.
4. Source-locked the production truth as JSON loader truth for this wave. The packet keeps D010 binary-format evidence classified as research / parsing-component reducibility only.
5. Stated that live production binary-loader reduction is not authorized in this wave. Later productionization requires a separate L4_STRUCTURAL wave for int-range policy, NaN/Inf policy, JS TLV decoder parity, seed migration tooling, and integrity-chain policy.
6. Preserved the open N3 status. This wave identified one bounded successor surface and did not claim broad N3 closure.
7. Routed execution through dispatcher -> Phase A -> Phase B -> commit executor. Completed tracker, indicator, commit-path, and sweep evidence is recorded as source-lock history, not queued as unresolved work in this packet.

## Constraints

Not in scope:
- No binary loader implementation.
- No seed migration.
- No ratchet baseline update.
- No production `/mu` runtime, seed, scheduler, registry, parity-semantics, or host-oracle edit.
- No Python-only or JS-only semantic widening.
- No Claude file, hidden/local memory, Codex-local binary/cache, or operator-home edit.
- No claim that N3 is closed.
- No claim that D010 makes the live production loader binary-ready.
- No live production loader reduction unless current code truth and validations actually prove it in a later authorized wave.

Pipeline repair constraint:
- If manual pipeline repair is needed, the same wave must add a mechanical/automated fix in dispatcher, builder, recovery, commit, pre-commit, or another appropriate pipeline surface, or it must leave a precise next-wave automation packet with evidence.

## Stop Conditions

These stop conditions governed source-lock implementation and remain the
boundary for this packet:

1. Implementation had to stop if it could not add a same-wave `TASKS.md` tracker note containing either `FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14` or an explicit standing pipeline-bug-fix authorization line.
2. Grounding evidence shows the selected `rcx_load` / `projection_loader` source-lock is not the currently selected N3 successor.
3. Current code truth, when opened by the source-lock implementation wave, proves the production loader boundary has already changed materially from the JSON production truth assumed by this packet.
4. Completing the work would require implementing a binary loader, migrating seeds, changing integrity-chain policy, adding a JS TLV decoder, changing int-range policy, changing NaN/Inf policy, or editing production runtime semantics.
5. Any required validation fails for reasons that cannot be corrected within the control-plane source-lock scope.
6. The wave starts to rely on D010 research evidence as production readiness evidence instead of parsing-component reducibility evidence.
7. The necessary write set expands beyond this packet, `TASKS.md`, and the same-wave L4 indicator artifact without a new bridge-reviewed packet.

## Acceptance Criteria

Completed source-lock acceptance state:

1. This packet contains the bounded Phase A sections for scope, work items, constraints, stop conditions, acceptance criteria, and grounding / authorization.
2. The packet distinguishes production JSON loader truth from D010 binary-format research evidence.
3. The packet states that production binary-loader reduction requires later L4_STRUCTURAL productionization work for int-range policy, NaN/Inf policy, JS TLV decoder parity, seed migration tooling, and integrity-chain policy.
4. `TASKS.md` contains a same-wave tracker sync note for `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14`.
5. The same-wave tracker or this packet contains detector-visible authorization for the wave id.
6. `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json` exists after the indicator collection step.
7. No runtime, seed, scheduler, registry, parity-semantics, host-oracle, Claude, hidden/local-memory, or Codex-local binary/cache file is edited by this L4_ENABLER source-lock wave.
8. The wave does not claim N3 closure, binary loader production readiness, or live production loader reduction.
9. Required closeout commands are recorded with results before GO/NO-GO.

Required validation commands recorded for source-lock closeout:

```bash
find reports/deferred/blocking reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' | sort
rg -n "rcx_load|projection_loader|binary format|D010|production path unchanged|FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14" TASKS.md reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md mu/docs/core/L4MicroAbi.v0.md mu/docs/core/L4ExitChecklist.v0.md mu/docs/core/Boot0Architecture.v0.md
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
./tools/checks/check_docs_consistency.sh
python3 tools/metrics/collect_l4_wave_indicators.py --wave-id n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14 --output reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14
```

## Grounding / Authorization

TASKS grounding:
- `TASKS.md:508-516` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked, founder-authorized, and explicitly requires every wave to carry a control-plane packet plus a `TASKS.md` tracker entry.
- `TASKS.md:512` says already-landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and seed-registration work must not be relisted as unresolved.
- `TASKS.md:523` records the broad host-surface next structural slice as landed, so this packet is a bounded successor source-lock rather than a re-opened copy of that predecessor wave.
- Reviewer reproduction before Phase B showed the exact same-wave lookup for `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14` exited with no TASKS output. The completed source-lock wave closed that authorization gap with the same-wave tracker note and indicator artifact.

Governing packet grounding:
- `reports/control_plane/n3-active-boundary-grounding-route-lock-2026-05-14_2026-05-14.md:98-109` selects the `rcx_load` / `projection_loader` image-boundary source-lock successor.
- `reports/control_plane/n3-active-boundary-grounding-route-lock-2026-05-14_2026-05-14.md:207-220` fixes the successor write boundary as this packet, a same-wave `TASKS.md` tracker note, and the same-wave L4 indicator artifact.

Architecture / proof-class grounding:
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175` keeps N3 active as broad host-surface residue and requires bounded successor packets for future reductions.
- `mu/docs/core/L4MicroAbi.v0.md:29-46`, `mu/docs/core/L4MicroAbi.v0.md:120-124`, and `mu/docs/core/L4MicroAbi.v0.md:157-165` define `rcx_load(image_bytes) -> state`, map current production truth to JSON loading through the Boot0 projection loader path, and classify binary format as reducible while production remains unchanged.
- `mu/docs/core/L4ExitChecklist.v0.md:183-188` and `mu/docs/core/L4ExitChecklist.v0.md:207-216` classify projection_loader binary format as D010 research-only evidence and list the productionization prerequisites.
- `mu/docs/core/Boot0Architecture.v0.md:64-80` keeps projection_loader among the bootstrap primitives with stable current JSON semantics and possible future smaller substrate.
- `mu/tests/research/test_d010_h5_projection_loader_binary.py:1-66` and `mu/tests/research/test_d010_h5_projection_loader_binary.py:500-653` are research evidence only. They do not authorize production migration, a JS decoder, I/O, SHA, or validation-chain changes.

Same-wave authorization line for detector-visible control-surface L4_ENABLER handling:

`FOUNDER_OVERRIDE:n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4
  indicator before pre-commit supervisor review so the tracker note, Gate 8
  package, and governing packet described one staged source-lock scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Source-lock package files recorded by the parent handoff:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md`
  - `reports/deferred/non_blocking/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`
- Generated bridge residue status after DOC_ACCURACY closeout:
  - active path absent after archive move:
    `reports/deferred/non_blocking/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers.md`
  - archived closed record:
    `reports/archive/deferred/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers_closed-by-n3-source-lock-doc-accuracy-closeout-2026-05-14.md`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14`
- Purpose: Phase B and commit automation generated the same-wave non-blocking
  bridge findings packet as deferred follow-up instead of blocking the
  source-lock wave.
- Generated deferred packet:
  - original active path:
    `reports/deferred/non_blocking/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers.md`
  - archived closed path:
    `reports/archive/deferred/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers_closed-by-n3-source-lock-doc-accuracy-closeout-2026-05-14.md`
- Scope binding: the packet above was in scope only as a generated same-wave
  non-blocking bridge findings packet. It is no longer active deferred work.
- Acceptance binding: the DOC_ACCURACY residue is closed by the closeout wave;
  N3 broad host-surface boundary remains open in
  `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md`
- Commit status: `source_lock_completed`
- Tracker note sha256: `8f097d3963e198538b77c474ef20c073f899429e9815c966d0c9f0c7dd32800b`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14 --output reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md. (2) The source-lock commit handoff carried 4 wave-owned file(s), including tracker sync, the same-wave L4 indicator, and the generated bridge residue packet. (3) No test files were present in the wave-owned diff, so indicator collection was the mechanical evidence surface. (4) The generated bridge DOC_ACCURACY residue is closed by `n3-source-lock-doc-accuracy-closeout-2026-05-14` and archived under `reports/archive/deferred/` with the required same-wave closed-by suffix.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`
- Source-lock package files recorded by the parent handoff:
  - `TASKS.md`
  - `reports/control_plane/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_2026-05-14.md`
  - `reports/deferred/non_blocking/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14.json`
- Current closeout archive state:
  - `reports/archive/deferred/n3-rcx-load-projection-loader-image-boundary-source-lock-2026-05-14_bridge_nonblockers_closed-by-n3-source-lock-doc-accuracy-closeout-2026-05-14.md`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
