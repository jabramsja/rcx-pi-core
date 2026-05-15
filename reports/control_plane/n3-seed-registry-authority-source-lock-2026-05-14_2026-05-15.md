# N3-Seed-Registry-Authority-Source-Lock-2026-05-14

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-seed-registry-authority-source-lock-2026-05-14
Class: L4_ENABLER
Phase-A-Lock: LOCKED
Governing packet: reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md

FOUNDER_OVERRIDE:n3-seed-registry-authority-source-lock-2026-05-14

## Scope

This Phase A packet is a dispatcher/pipeline-owned plan for the next N3
seed-registry authority source-lock decision after the rcx_load seed-image
boundary closeout.

Files/directories in scope for this Phase A control-surface packet:

- Edit-only packet surface:
  `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md`.
- Read-only authorization evidence: `TASKS.md` line 68 and lines 531-539.
- Read-only governing N3/source-lock planning inputs:
  - `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
    lines 150-164.
  - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
    lines 161-175.
  - `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md`.
  - `mu/docs/core/Why_RCX_PI_VM_EXISTS.md`.
  - `mu/docs/core/SelfHosting.v0.md`.
  - `mu/docs/core/MetaCircularKernel.v0.md`.
  - `mu/docs/core/StructuralPurity.v0.md`.
  - `mu/docs/core/Boot0Architecture.v0.md`.
  - `mu/docs/core/L4MicroAbi.v0.md`.
  - `mu/docs/core/L4ExitChecklist.v0.md`.
- Read-only authority-inventory directories for the successor decision:
  - `mu/host/python/`.
  - `mu/host/js/`.
  - `mu/programs/`.
  - `mu/tests/`.

The work within that explicit file/directory scope is limited to:

- Build the next implementation decision from the cited N3 queue and seed-image
  authority materials, not from broad repository discovery.
- Source-lock duplicated host registry authority across Python and JavaScript
  for checksums, seed locations, expected projection IDs, and seed
  dependencies.
- Produce either a bounded next implementation packet with exact file:line
  evidence and a locked write set, or a NO-GO with direct file:line blocker
  evidence.
- Preserve Python/JS parity and structural VM direction: Python and JavaScript
  may own bootstrap servicing, validation, orchestration, and evidence
  collection, but must not become the semantic authority for Mu behavior.
- Keep this packet as a planning/control-surface artifact only. It authorizes a
  later source-lock test packet; it does not authorize runtime, seed, registry,
  projection, or generated artifact edits.

Out of scope for this packet:

- Runtime behavior edits.
- Seed JSON, checksum registry, projection-ID registry, seed dependency
  registry, generated seed artifact, scheduler, Stage0, production `/mu`,
  host-oracle, Claude-related, or unrelated control-plane edits.
- TASKS.md synchronization in this rewrite. The later implementation handoff
  must add or mechanically derive same-wave TASKS synchronization before strict
  closeout.

## Work items

1. Re-ground the N3 item from the already-cited governing sources:
   - `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:150-164`
     identifies this wave's goal as duplicated Python/JS host registry authority
     for checksums, locations, expected projection IDs, and seed dependencies,
     and requires an exact next packet or NO-GO.
   - `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175`
     keeps N3 as architectural boundary residue and requires future reductions
     to narrow bootstrap assumptions rather than move semantics into hosts.
   - `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md:169-195`
     allows source-lock-only or other detector-visible prerequisites when a
     broader loader split is not yet the honest next runtime step.
   - Doctrine evidence keeps the direction fixed: `Why_RCX_PI_VM_EXISTS.md:91-103`
     says host languages would smuggle evaluation/control assumptions;
     `SelfHosting.v0.md:82` says L4 still requires eliminating remaining host
     bootstrap; `MetaCircularKernel.v0.md:70-75` requires structural kernel
     selection instead of Python iteration as proof; `StructuralPurity.v0.md:42-51`
     says everything flowing through the kernel must be Mu; `Boot0Architecture.v0.md:60-80`
     treats projection loading as Boot0 trusted substrate; `L4MicroAbi.v0.md:29-45`
     defines the target rcx_load boundary; and `L4ExitChecklist.v0.md:115-130`
     classifies projection_loader as content-addressed production truth with
     binary-format reduction unproven.
2. Inventory duplicated host registry authority, grouped by authority class:
   checksum authority, seed location authority, expected projection ID
   authority, and seed dependency authority.
3. Classify each authority group as duplicate authority that can be
   mechanically source-locked, bootstrap servicing that must remain
   substrate-local, Mu semantic authority that must not move into either host,
   or already landed/currently satisfied and removed from pending work.
4. Select the smallest honest next step:
   - GO for a bounded test-only dependency source-lock successor, because
     checksum, location, and projection-ID source-lock coverage is already
     present, while dependency parity remains a weaker string-presence check.
   - Do not authorize runtime/source-data reduction here, because that would
     require seed or registry edits beyond this packet's locked write set.
5. Draft the successor packet requirements with exact write set, read-only
   evidence set, focused tests, Python/JS parity proof, ratchet expectations,
   and same-wave TASKS tracker/override requirements before commit.

## Authority Inventory

Checksum authority:

- Python authority: `mu/host/python/rcx_pi/selfhost/seed_integrity.py:25-92`
  defines `SEED_CHECKSUMS`, and `seed_integrity.py:462-485` rejects unknown or
  mismatched seed bytes.
- JS CLI authority: `mu/host/js/cli/main.js:24-42` defines
  `SEED_CHECKSUMS`, and `main.js:162-168` rejects unknown or mismatched seed
  bytes.
- JS core authority: `mu/host/js/core/seed_loader.js:17-25` defines
  `CORE_SEED_CHECKSUMS`, and `seed_loader.js:190-203` verifies hash before
  parsing for known seeds.
- Current source-lock coverage: `mu/tests/parity/test_seed_loading_parity.py:130-163`
  proves JS checksum entries are a Python subset and match for shared seeds.
  `test_seed_loading_parity.py:344-379` proves JS core checksum/projection maps
  are a subset of JS CLI and have matching keys.
- Classification: duplicate host authority, already source-locked for the
  current shared JS surfaces. Do not relist checksum parity as pending work in
  the successor unless current code evidence changes.

Seed location authority:

- Python authority: `mu/host/python/rcx_pi/selfhost/seed_integrity.py:364-393`
  defines `MU_SEED_LOCATIONS`, and `seed_integrity.py:644-674` resolves seed
  paths from that map.
- JS authority: `mu/host/js/core/seed_loader.js:131-154` defines
  `SEED_SUBDIRS`, `seed_loader.js:162-168` rejects unknown subdir lookups, and
  `seed_loader.js:186-188` builds the file path from `subdir` plus `seedName`.
- Current source-lock coverage: `mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py:562-588`
  proves JS `SEED_SUBDIRS` keys and values match Python `MU_SEED_LOCATIONS`.
  `mu/tests/parity/test_seed_loading_parity.py:208-225` proves Python locations
  cover every checksum seed and use valid mu/ subdirectories.
- Classification: duplicate host authority, already source-locked for exact
  Python/JS location parity. Do not relist location parity as pending work.

Expected projection ID authority:

- Python authority: `mu/host/python/rcx_pi/selfhost/seed_integrity.py:105-361`
  defines `EXPECTED_PROJECTION_IDS`, and `seed_integrity.py:544-580` enforces
  exact ordered ID equality.
- JS CLI authority: `mu/host/js/cli/main.js:44-160` defines
  `EXPECTED_PROJECTION_IDS`, and `main.js:189-200` enforces exact ordered ID
  equality.
- JS core authority: `mu/host/js/core/seed_loader.js:27-99` defines
  `CORE_SEED_PROJECTION_IDS`, and `seed_loader.js:227-240` rejects registry
  asymmetry or ID-order mismatch.
- Current source-lock coverage: `mu/tests/parity/test_seed_loading_parity.py:168-203`
  proves JS projection ID entries are a Python subset and match exactly for
  shared seeds. `test_seed_loading_parity.py:344-379` proves JS core
  projection IDs are a JS CLI subset and the core checksum/projection key sets
  match.
- Classification: duplicate host authority, already source-locked for current
  shared JS surfaces. Do not relist projection-ID parity as pending work.

Seed dependency authority:

- Python authority: `mu/host/python/rcx_pi/selfhost/seed_integrity.py:396-428`
  defines `SEED_DEPENDENCIES`, and `seed_integrity.py:431-449` checks loaded
  seed prerequisite satisfaction.
- JS authority: `mu/host/js/core/seed_loader.js:101-110` defines
  `SEED_DEPENDENCIES`, `seed_loader.js:117-129` checks loaded seed prerequisite
  satisfaction, and `seed_loader.js:249` exports the map.
- Current registry consistency coverage: `mu/tests/engine/test_seed_registry_consistency.py:73-120`
  proves Python dependency referential integrity, no self-dependencies, and
  acyclicity.
- Current parity coverage gap: `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py:290-309`
  only verifies that JS source text contains each Python dependency string. It
  does not parse the exported JS map, reject extra JS dependencies, reject
  missing JS keys with exact set evidence, or compare ordered dependency lists.
- Mu semantic evidence: program seed metadata also carries human dependency
  prose, for example `mu/programs/rcx_engine.v1.json:10-15`,
  `mu/programs/hemispheres.v1.json:10-13`,
  `mu/programs/metabolization.v1.json:10-13`,
  `mu/programs/metabolize_cycle.v1.json:10-14`, and
  `mu/programs/paxos_demo.v1.json:7`. That metadata is not currently a clean
  machine-readable dependency registry for all host-enforced dependencies, and
  this packet must not rewrite seed JSON or checksums to make it one.
- Classification: duplicate Python/JS host authority that can be mechanically
  source-locked with test-only parity evidence. Canonicalizing dependency truth
  into Mu seed metadata would be a separate seed-schema/checksum wave and is not
  selected here.

Bootstrap servicing that must remain substrate-local:

- Python loader servicing stays in `load_verified_seed()`, which reads bytes,
  verifies checksums, parses JSON, validates structure, and validates projection
  IDs at `mu/host/python/rcx_pi/selfhost/seed_integrity.py:593-636`.
- JS core loader servicing stays in `loadVerifiedSeed()`, which resolves paths,
  reads files, verifies checksums, parses JSON, checks projection-entry shapes,
  and validates projection IDs at `mu/host/js/core/seed_loader.js:186-242`.
- JS CLI loader servicing stays in `loadVerifiedSeed()` and startup seed loading
  at `mu/host/js/cli/main.js:245-272`.
- Classification: bootstrap servicing. Do not move Mu semantic decisions into
  these functions and do not treat loader implementation edits as source-lock
  progress for this successor.

Already landed/currently satisfied and removed from pending work:

- Engine-state/scheduler seed, fixture, structural-test, scheduler-parity, and
  seed-registration work is already landed per `TASKS.md:531-535` and must not
  be relisted as unresolved.
- Checksum, seed-location, expected projection-ID, JS core subset, and OPROMO
  fully locked-set parity are already guarded by current tests:
  `mu/tests/parity/test_seed_loading_parity.py:130-225`,
  `mu/tests/parity/test_seed_loading_parity.py:344-379`, and
  `mu/tests/l4_gates/test_ontology_promotion_runtime_gate.py:562-588`,
  `:646-725`.

## Phase A Result: GO Successor

GO: create a bounded test-only successor implementation packet for exact seed
dependency source-lock.

Successor wave:

- Proposed wave id:
  `n3-seed-dependency-registry-source-lock-2026-05-15`.
- Proposed class: `L4_ENABLER`.
- Proposed packet:
  `reports/control_plane/n3-seed-dependency-registry-source-lock-2026-05-15.md`.
- Purpose: replace weak dependency string-presence parity with an exact
  Python/JS exported-map comparison, without editing runtime loaders, seed JSON,
  checksum maps, projection-ID maps, seed-location maps, dependency registries,
  Stage0, scheduler, generated artifacts, or production semantics.

Exact successor write set:

- `reports/control_plane/n3-seed-dependency-registry-source-lock-2026-05-15.md`
  for the successor packet.
- `TASKS.md` same-wave tracker note for
  `n3-seed-dependency-registry-source-lock-2026-05-15`.
- `mu/tests/parity/test_seed_loading_parity.py` to add the exact exported
  Python/JS `SEED_DEPENDENCIES` parity proof.
- `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py` only if Phase B chooses to
  replace the existing string-presence dependency check with the same exact
  exported-map helper, rather than leaving the weaker legacy check in place.
- `reports/l4_wave_indicators/n3-seed-dependency-registry-source-lock-2026-05-15.json`
  for same-wave L4 evidence.
- Same-wave generated deferred non-blocking bridge findings packet, if commit
  automation produces one.

Exact successor read-only evidence set:

- This packet.
- `TASKS.md:68`, `TASKS.md:531-539`.
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md:150-164`.
- `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md:161-175`.
- `reports/control_plane/n3-seed-image-authority-inventory-split-prereq-2026-05-15.md:169-195`.
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py:396-449`.
- `mu/host/js/core/seed_loader.js:101-129`, `:249`.
- `mu/tests/engine/test_seed_registry_consistency.py:73-120`.
- `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py:290-309`.
- `mu/programs/rcx_engine.v1.json:10-15`.
- `mu/programs/hemispheres.v1.json:10-13`.
- `mu/programs/metabolization.v1.json:10-13`.
- `mu/programs/metabolize_cycle.v1.json:10-14`.
- `mu/programs/paxos_demo.v1.json:7`.

Focused successor implementation requirements:

- Add a Python parity helper that imports Python `SEED_DEPENDENCIES` and obtains
  the JS exported `SEED_DEPENDENCIES` from `mu/host/js/core/seed_loader.js` via a
  Node subprocess or another existing test-local JS execution helper.
- Compare exact key sets and exact dependency lists. The test must fail on:
  missing JS dependency keys, extra JS dependency keys, missing dependency
  targets, extra dependency targets, order drift if order remains semantically
  documented as list order, and non-array JS dependency values.
- Preserve Python-only registry-integrity tests for referential integrity and
  acyclicity.
- Preserve existing checksum, location, projection-ID, JS core subset, and
  OPROMO fully locked-set source-lock tests as already-satisfied coverage.
- Do not derive dependency truth from `mu/programs/*.json` prose in this
  successor. If machine-readable seed metadata becomes the desired canonical
  source, stop and route a separate seed-schema/checksum packet.

Focused successor validation commands:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py mu/tests/engine/test_seed_registry_consistency.py mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py --tb=short
```

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short
```

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
```

```bash
python3 tools/checks/check_host_authority_inventory_ratchet.py
```

```bash
./tools/checks/check_docs_consistency.sh
```

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-seed-dependency-registry-source-lock-2026-05-15
```

Same-wave authorization proof before successor commit:

- Add a detector-visible `TASKS.md` tracker line for
  `n3-seed-dependency-registry-source-lock-2026-05-15`, or carry a mechanically
  accepted same-wave override token for that exact wave.

## Constraints

- Do not implement runtime behavior in this packet.
- Do not edit seed JSON, checksum registries, projection registries, seed
  dependency registries, generated seed artifacts, Stage0 bundles, scheduler
  files, production `/mu` runtime, host-oracle files, Claude-related files, or
  unrelated control-plane surfaces in this packet.
- Do not add bootstrap primitives.
- Do not add host semantic fallbacks.
- Do not move Mu semantic authority into Python or JavaScript.
- Do not count baseline cleanup, stale prose cleanup, or documentation-only
  wording as structural progress.
- Do not relist work as unresolved if direct current-code evidence proves it is
  already implemented; remove already-landed items from pending work and
  acceptance criteria.
- Do not widen into Claude-related files, Stage0 changes, scheduler work,
  host-oracle work, or unrelated executor/test cleanup.
- This rewrite is restricted to
  `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md`.
  TASKS.md synchronization is required before a later implementation/commit
  handoff, but is not authorized in this rewrite.

## Stop conditions

- Stop with NO-GO if Phase A evidence cannot identify duplicated Python/JS
  registry authority with direct file:line support.
- Stop with NO-GO if the proposed fix would require seed JSON/checksum/
  projection/dependency registry edits before a later packet locks that exact
  write set.
- Stop with NO-GO if source-locking would add host-only semantics or make
  Python/JavaScript decide Mu behavior that belongs in Mu seeds/projections.
- Stop with NO-GO if Python and JavaScript cannot be kept parity-aligned for the
  selected source-lock check.
- Stop before implementation if the host semantics ratchet or host authority
  inventory ratchet would increase.
- Stop before commit/closeout if the wave lacks detector-visible same-wave
  authorization through a TASKS tracker entry or a mechanically accepted
  same-wave override token.
- Stop the successor and route a separate seed-schema/checksum packet if exact
  dependency source-lock requires changing `mu/programs/*.json`, checksum maps,
  projection registries, or host dependency registries.

## Acceptance criteria

- The packet is no longer a stub: it contains Scope, Work items, Constraints,
  Stop conditions, Acceptance criteria, Grounding/Authorization, Proof limits,
  and Validations sections.
- The Scope section explicitly lists the edit-only packet file, read-only TASKS
  authorization evidence, read-only governing packet/docs evidence, and
  read-only successor authority-inventory directories.
- The packet carries same-wave authorization text that commit automation can
  detect: FOUNDER_OVERRIDE:n3-seed-registry-authority-source-lock-2026-05-14.
- Grounding cites `TASKS.md:68` for the rule that authorization lives in
  TASKS.md, and `TASKS.md:531-539` for the active
  `[NEXT-CODEX-POST-REDTEAM]` founder-authorized queue and every-wave
  packet/tracker requirement.
- Phase A produces exactly one successor implementation packet selection with
  direct file:line evidence, exact write set, parity checks, ratchet
  expectations, and same-wave TASKS synchronization requirements.
- Pending work and acceptance criteria exclude anything already proven landed
  by current code evidence.
- No runtime, seed, scheduler, registry, projection, Stage0, production `/mu`,
  host-oracle, Claude-related, or unrelated control-plane implementation edits
  are authorized by this packet.

## Grounding/Authorization

- `TASKS.md:68` states that current state lives in STATUS.md and authorization
  lives in TASKS.md.
- `TASKS.md:531-535` marks `[NEXT-CODEX-POST-REDTEAM]` UNPARKED,
  founder-authorized, and still OPEN for future bounded work not proven by the
  landed engine-state/scheduler slice.
- `TASKS.md:536-539` gives the immediate pre-production work order and requires
  founder-ordered waves to proceed through dispatcher/pipeline, with every wave
  carrying a control-plane packet plus TASKS.md tracker entry.
- Targeted lookup evidence for this exact wave id before this rewrite:
  `rg -n "n3-seed-registry-authority-source-lock-2026-05-14" TASKS.md`
  exits 1, so TASKS.md does not yet contain a detector-visible same-wave
  tracker note for this packet.
- This packet therefore carries a packet-local same-wave override token for the
  Phase A control-surface packet rewrite:
  FOUNDER_OVERRIDE:n3-seed-registry-authority-source-lock-2026-05-14.
- A later Phase B/commit handoff must add or mechanically derive
  detector-visible TASKS synchronization for its same wave before strict L4
  closeout.

## Proof limits

- This packet proves only that the Phase A plan found the smallest honest next
  source-lock successor. It does not prove that successor implementation is
  landed.
- Source-lock tests prove registry equality/invariant checks, not runtime
  semantic reduction. Runtime behavior parity still belongs to focused runtime
  parity tests.
- The selected successor is test-only and dependency-focused. It does not
  reduce the number of host registry literals, migrate canonical dependency
  truth into Mu seed metadata, or close N3 broad host-surface residue.
- Program seed metadata lines in `mu/programs/*.json` are treated as current
  semantic/prose evidence only. They are not a clean machine-readable canonical
  dependency registry in this packet.
- Passing packet-structure checks does not prove Python/JS registry parity, host
  semantics safety, authority inventory stability, or docs consistency for the
  successor implementation.

## Validations

Packet-structure validation for this rewrite:

```bash
wc -l reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md
```

```bash
rg -n "^(## (Scope|Work items|Constraints|Stop conditions|Acceptance criteria|Grounding/Authorization|Proof limits|Validations)|FOUNDER_OVERRIDE:|Authorization: standing pipeline-bug-fix authorization)" reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md
```

Required validation set for the successor implementation packet:

- Focused dependency source-lock:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py mu/tests/engine/test_seed_registry_consistency.py mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py --tb=short`.
- Shared substrate parity:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short`
  when registry behavior touches shared substrate parity.
- Host semantics ratchet:
  `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`.
- Host authority inventory ratchet:
  `python3 tools/checks/check_host_authority_inventory_ratchet.py`.
- Docs consistency: `./tools/checks/check_docs_consistency.sh`.
- Strict staged L4 for the successor wave id:
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-seed-dependency-registry-source-lock-2026-05-15`.
- Same-wave authorization proof before commit: a detector-visible TASKS.md
  tracker line or mechanically accepted override for
  `n3-seed-dependency-registry-source-lock-2026-05-15`.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-seed-registry-authority-source-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-registry-authority-source-lock-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md`
  - `reports/l4_wave_indicators/n3-seed-registry-authority-source-lock-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-seed-registry-authority-source-lock-2026-05-14`
- Active packet: `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `2d02a9882b4948f0c20a18f713cdbb3235b0175270bb01d33710d8e432363951`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-registry-authority-source-lock-2026-05-14.json`
- Evidence command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id n3-seed-registry-authority-source-lock-2026-05-14 --output reports/l4_wave_indicators/n3-seed-registry-authority-source-lock-2026-05-14.json`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md. (2) Commit handoff carries 3 wave-owned file(s) with pre-commit supervisor receipt pending for the current staged package. (3) No test files were present in the wave-owned diff, so indicator collection is the mechanical evidence surface..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-seed-registry-authority-source-lock-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md`
  - `reports/l4_wave_indicators/n3-seed-registry-authority-source-lock-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
