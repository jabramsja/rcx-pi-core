# Transparent JS Live Container Provenance Implement

Date: 2026-05-13
Status: Phase B implementation complete; closeout validation passed
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: transparent-js-live-container-provenance-implementation-2026-05-13
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL implementation packet; successor to the locked L4_ENABLER routing packet.
Required detector-visible TASKS override: FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13
Purpose: Route a bounded successor implementation plan for the retained transparent JS Proxy provenance advisory. The implementation target is to thread trusted Mu-origin container provenance through live JavaScript Mu container producers so legitimate normalized/kernel/API/substitution outputs remain valid Mu while raw host records, host lists, and transparent `new Proxy({a: 1}, {})` inputs reject at public Mu boundaries without adding a host Proxy oracle.

## Scope

This packet now owns the Phase B structural implementation and closeout for the
transparent JS Proxy provenance advisory. The same-wave tracker authority sync
at `TASKS.md:320` must remain detector-visible, but the implemented scope is no
longer docs-only.

Resolved same-wave policy blocker: `TASKS.md:320` carries `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13`, making the L4_STRUCTURAL authorization detector-visible to `tools/checks/enforce_l4_execution_contract.py --staged --wave-id transparent-js-live-container-provenance-implementation-2026-05-13`.

Resolved Bridge Round 2 package blocker: `TASKS.md:320` no longer asserts that
`.scratch/phase_b_supervisor_package.json` is the current same-wave package or
authoritative changed-file count. Bridge Round 2 reproduced that the live
scratch package belonged to a different wave, so this packet binds the current
enabler evidence to tracked docs/control-plane surfaces plus the same-wave L4
indicator artifact.

Bridge Round 1 scope reconciliation: the predecessor exact successor list in
`reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`
named `types.js` plus focused tests because the predecessor had not yet
reproduced why a types-only trusted-container gate failed. Current predecessor
failure evidence shows the failed candidate broke normalized kernel/API paths
because live containers created by `normalize.js` and `bootstrap_core.js` were
outside the `types.js` provenance set. This packet therefore explicitly
overrides the predecessor exact file list for the successor implementation by
adding JS live container producer sites under the same no-host-oracle /
no-raw-host-admission constraints. No seed data, Stage0 program semantics,
scheduler, registry, Python runtime, executor, Claude, or pipeline surface is
authorized by this reconciliation.

The bounded implementation scope is:

- `mu/host/js/core/container_factory.js` for repo-internal Mu-origin container construction.
- `mu/host/js/core/types.js` for the Mu validation/provenance boundary and public `isValidMu` / hash / match admission behavior; its public `containers` export exposes only `has`.
- `mu/host/js/core/normalize.js` for live normalization-produced container provenance.
- `mu/host/js/core/bootstrap_core.js` for live kernel/API/substitution container producer provenance.
- `mu/host/js/core/seed_loader.js`, `mu/host/js/cli/main.js`, and `mu/host/js/api/json_handlers.js` for checksum/API ingress containers parsed from already-authorized JSON boundaries.
- `mu/host/js/core/stage0_vm.js` only for provenance marking on VM materialized Mu copies/templates; no Stage0 program semantics, opcode semantics, or seed bundles are changed.
- `mu/host/js/core/terminal_classification.js`, `mu/host/js/engine/kernel.js`, `mu/host/js/engine/pipeline.js`, and `mu/host/js/engine/routing.js` only for Mu container construction/copying on live engine containers they produce.
- `mu/host/js/tests/self_tests.js` for self-test helper trust construction.
- `mu/tests/l4_gates/test_d009_production_depth_gate.py` for focused L4 boundary coverage.
- `mu/tests/parity/test_js_parity_automated.py` for focused JS parity/API coverage.
- `TASKS.md` only for the same-wave tracker synchronization that carries detector-visible authorization for `transparent-js-live-container-provenance-implementation-2026-05-13`, and for post-implementation tracker/evidence synchronization after code truth proves the advisory is closed.
- `reports/l4_wave_indicators/transparent-js-live-container-provenance-implementation-2026-05-13.json`, this packet, and deferred/archive metadata only for post-implementation evidence synchronization after code truth proves the advisory is closed.

## Work Items

1. Tracker authority sync: keep the same-wave `TASKS.md:320` tracker note carrying `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13` before strict L4 validation, pre-commit supervisor validation, or commit automation for this wave.
2. Reproduce the predecessor evidence from tracked code and tracked packet truth only: use `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md` plus current `mu/host/js/core/{types.js,normalize.js,bootstrap_core.js}` behavior to identify the live JS container producers that fail when provenance is confined to `types.js`. Ignored `.scratch/` and `.agent_bus/` artifacts are non-canonical debug aids, not successor-wave authority.
3. Before runtime/test edits, remove any already-landed current-code behavior from pending work and acceptance criteria rather than re-listing it as unresolved. `TASKS.md:543` authorizes the retained route; it does not prove each implementation item remains unlanded.
4. In `mu/host/js/core/types.js`, define or preserve a trusted Mu-origin container provenance mechanism that can distinguish Mu-constructed containers from raw host records/lists without using a host Proxy detector or admitting raw host objects structurally.
5. In `mu/host/js/core/normalize.js`, thread trusted provenance through normalization-created arrays/records so valid normalized Mu containers remain accepted by `isValidMu`, hashing, and matching.
6. In `mu/host/js/core/bootstrap_core.js`, thread trusted provenance through live kernel/API/substitution container producers so runtime-created Mu containers remain valid without widening raw host admission.
7. Add focused tests in `mu/tests/l4_gates/test_d009_production_depth_gate.py` and `mu/tests/parity/test_js_parity_automated.py` proving both halves of the boundary: trusted constructor/normalization/substitution outputs are valid Mu, and raw host records/lists plus transparent Proxy wrappers reject before public `isValidMu`, hash, or match semantics can treat them as portable Mu.
8. After implementation evidence passes, update only the wave-owned tracker/evidence surfaces listed in Scope: `TASKS.md`, the L4 indicator artifact, this packet if closeout metadata is needed, and the active deferred advisory/archive state only if code truth proves closure.

## Constraints

- Do not use `util.types.isProxy`, `node:util`, any equivalent host Proxy detector, or any host-object oracle.
- Do not make raw JavaScript host records, arrays/lists, Proxy-wrapped records/lists, class instances, custom-prototype objects, accessor-bearing objects, hidden-key objects, or other host artifacts portable by exported serialization/canonicalization/copy helpers or public structural admission. Authorized checksum/API parse-tree ingress may construct fresh Mu containers from parsed JSON data only inside the scoped boundary modules.
- Do not relax public `isValidMu`, hash, match, CLI, or JSON API boundaries to accept raw host objects/lists.
- Do not touch seed data, Stage0 program semantics, scheduler, registry, projection data, Python runtime, Claude files, or pipeline executor tooling.
- Do not edit deferred advisory files unless the Phase B implementation actually closes the transparent Proxy advisory with current code evidence.
- Do not treat the retained predecessor route as proof that every candidate work item is still unlanded; before Phase B edits, use current code truth inside the scoped files to remove any already-implemented item from pending work and acceptance.
- Do not claim packet-local `FOUNDER_OVERRIDE` text satisfies `enforce_l4_execution_contract.py`; same-wave authorization is detector-visible only when the `TASKS.md:320` tracker authority for this wave contains `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13` or an explicit standing authorization line for this wave.
- Do not run, claim, or automate strict staged L4 validation for this wave as passing if the bridge-reviewed TASKS authorization regex exits 1.

## Stop Conditions

- Stop for founder decision if the only viable implementation requires a host Proxy oracle, `node:util`, `util.types.isProxy`, or any equivalent host-object detection capability.
- Stop for founder decision if the only viable implementation makes raw JS host records/lists portable by serialization, canonicalization, copying, or structural admission.
- Stop before runtime implementation if bridge review does not converge on this Phase A packet or the dispatcher does not route Phase B from this packet.
- Stop and split the wave if the implementation requires files outside the Phase B Scope or requires a same-wave mechanical pipeline repair.
- Stop deferred-advisory closeout if tests prove runtime behavior changed but do not prove the active transparent Proxy advisory is actually closed.
- Stop before strict staged L4 validation, pre-commit supervisor validation, or commit automation if the `TASKS.md` tracker note for `transparent-js-live-container-provenance-implementation-2026-05-13` loses `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13` and lacks an explicit standing authorization line for this wave.

## Acceptance Criteria

- This packet contains complete sections for Scope, Work Items, Constraints, Stop Conditions, Acceptance Criteria, Grounding / Authorization, and Closeout Evidence.
- This packet does not claim packet-local `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13` text is detector-visible to `enforce_l4_execution_contract.py`.
- This packet records the bridge blocker resolution: `TASKS.md:320` carries detector-visible same-wave authorization through `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13`.
- This packet records the Bridge Round 2 package-reference resolution:
  `TASKS.md:320` does not bind tracker truth to mutable `.scratch/` package
  state or stale changed-file counts.
- Before any strict same-wave L4 validation, pre-commit supervisor validation, commit automation, or Phase B runtime/test implementation can be accepted, the `TASKS.md:320` tracker note for `transparent-js-live-container-provenance-implementation-2026-05-13` must continue to contain `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13` or an explicit `Authorization: standing pipeline-bug-fix authorization ...` line for this wave.
- Phase B preserves rejection of transparent `new Proxy({a: 1}, {})`, raw host records, and raw host lists at public `isValidMu`, hash, and match boundaries.
- Phase B preserves acceptance of trusted Mu-origin constructor, normalization, kernel/API, and substitution container outputs.
- Phase B keeps the JavaScript CLI and JSON API startup paths working.
- Phase B adds focused regression coverage in `mu/tests/l4_gates/test_d009_production_depth_gate.py` and `mu/tests/parity/test_js_parity_automated.py`.
- The wave passes these exact validation commands before commit, with runtime/test commands required after any routed Phase B implementation:
  - `node mu/host/js/eval_step.js`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_d009_production_depth_gate.py --tb=short -p no:cacheprovider`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short -p no:cacheprovider`
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `rg -n 'transparent-js-live-container-provenance-implementation-2026-05-13.*FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13|Authorization: standing pipeline-bug-fix authorization.*transparent-js-live-container-provenance-implementation-2026-05-13' TASKS.md`
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id transparent-js-live-container-provenance-implementation-2026-05-13`
  - `./tools/checks/check_docs_consistency.sh`
- Closeout updates `TASKS.md` and the L4 indicator artifact for implementation evidence only after implementation evidence passes, and updates active deferred advisory/archive state only because code truth proves closure.

## Grounding / Authorization

- `TASKS.md:543` is the current queue authority for this successor work. It retains `transparent-js-proxy-provenance-boundary-2026-05-09` under `[NEXT-CODEX-POST-REDTEAM]`, classifies it as `L4_ENABLER`, names category `/mu` structural boundary policy, binds the predecessor packet `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`, and keeps host-oracle/runtime implementation hard-stopped behind a successor packet.
- This file is that successor packet for `transparent-js-live-container-provenance-implementation-2026-05-13`; it does not claim that `TASKS.md:543` proves all listed implementation items remain unlanded.
- Same-wave tracker state for this packet is `TASKS.md:320`. It names `transparent-js-live-container-provenance-implementation-2026-05-13` and now carries `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13`, making authorization detector-visible for `tools/checks/enforce_l4_execution_contract.py --staged --wave-id transparent-js-live-container-provenance-implementation-2026-05-13`.
- Bridge-reviewed authorization reproduction: `rg -n 'transparent-js-live-container-provenance-implementation-2026-05-13.*FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13|Authorization: standing pipeline-bug-fix authorization.*transparent-js-live-container-provenance-implementation-2026-05-13' TASKS.md` should match `TASKS.md:320`.
- Required detector-visible TASKS authorization text for this wave is present: `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13`.
- Governing predecessor route: `reports/control_plane/transparent_js_proxy_provenance_boundary_2026-05-09.md`.
- Predecessor failure evidence for Phase B planning must be reproduced from tracked packet/code truth before runtime edits. Ignored `.agent_bus/` and `.scratch/` paths may explain prior operator context but are not durable authority for this successor packet.
- Required founder override token for the TASKS sync: `FOUNDER_OVERRIDE:transparent-js-live-container-provenance-implementation-2026-05-13`.

## Closeout Evidence

- Direct transparent Proxy probe exits 0 with transparent record/list Proxy values rejected at public JS Mu boundaries and trusted Mu-origin records accepted.
- Commit executor supervisor Step 6 initially rejected the raw WeakSet export because `_TRUSTED_MU_CONTAINERS.add(proxy)` made transparent Proxy roots pass `isValidMu` and `muHash`; the next supervisor pass rejected the global-symbol WeakSet export because `types[Symbol.for('rcx.mu.internalProvenance')].add(proxy)` had the same effect; the next supervisor pass rejected the exported recursive `containers.json` copy helper because it laundered raw records/lists and transparent Proxy wrappers into valid/hashable Mu containers; the next supervisor rejection proved public `containers.record(Object.entries(proxy))` and `containers.list(proxyArray)` were still laundering paths; the final supervisor rejection found `normalizeProjection` and `deriveEngineExitReason` still constructing plain compound records inside scoped producer paths. The repaired implementation confines constructors to repo-internal `container_factory.js`, exposes public `types.js` `containers` as `["has"]` only, converts the remaining scoped producers to factory-backed records, exposes no global-symbol/raw WeakSet/string-named trust mutator, `.add()` capability, exported `list`/`record` constructor, or recursive host-object/Proxy copy helper, and requires provenance on every compound node.
- `node mu/host/js/eval_step.js` exits 0 and reports `All tests passed: true`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_d009_production_depth_gate.py --tb=short` exits 0 with `44 passed`.
- `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short -p no:cacheprovider` exits 0 with `307 passed in 484.69s (0:08:04)`.
- Focused JS parity repairs for empty-var matching, JSON recurrence input, and JS security parity exit 0 after trusting only explicitly Mu-origin compound test values.
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` exits 0 with `"passed": true`.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` exits 0 with no new total-inventory or authority-subset sites detected; the current inventory is one JS total site below baseline and the authority subset remains flat.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id transparent-js-live-container-provenance-implementation-2026-05-13` exits 0 and reports `L4_STRUCTURAL compliant`.
- `python3 tools/checks/enforce_l4_execution_contract.py --staged` exits 0 and reports `L4_STRUCTURAL compliant`.
- `./tools/checks/check_docs_consistency.sh` exits 0 and reports `All checks passed. Docs are consistent.`
- The active transparent Proxy deferred advisory is closed by this implementation and archived at `reports/archive/deferred/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-transparent-js-live-container-provenance-implementation-2026-05-13.md`.
