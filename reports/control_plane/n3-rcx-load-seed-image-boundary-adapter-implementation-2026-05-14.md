# N3 rcx_load Seed Image Boundary Adapter Implementation

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14
Class: L4_ENABLER
Category: control/evidence closeout for rejected /mu runtime candidate
Target gate: G8
Phase-A-Lock: LOCKED

FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14

## Grounding / Authorization

This packet began as the N3 implementation packet authorized by the current
`[NEXT-CODEX-POST-REDTEAM]` lane in `TASKS.md`. The commit-bound re-entry
package is now a control/evidence closeout for the rejected runtime candidate,
not an accepted executable `/mu` implementation.

Targeted `TASKS.md` grounding:

- `TASKS.md:347` is the detector-visible predecessor lock entry for
  `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14` under
  `[NEXT-CODEX-POST-REDTEAM]`; it binds the control-plane lock packet that
  routes this follow-on implementation slice.
- `TASKS.md:331` and `TASKS.md:539` are the current landed N3
  broad-host-surface lineage entries for
  `broad-host-surface-next-structural-slice-2026-05-13` under
  `[NEXT-CODEX-POST-REDTEAM]`; they preserve the N3 lane lineage but do not
  prove that every listed implementation item below is still unlanded.
- Targeted lookup for
  `n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14` in
  `TASKS.md` found no same-wave implementation tracker note before this packet
  rewrite. Phase B added the same-wave tracker note before this package was
  staged for handoff, and re-entry classifies that package as `L4_ENABLER`
  control/evidence because no runtime/substrate delta is accepted.

Governing packet references:

- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md`
- `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
- this packet:
  `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`

Same-wave authorization line for control-surface L4 handling and commit
automation:

`FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14`

## Purpose

Record the Phase B result for the first production `rcx_load(image_bytes)`
boundary-narrowing slice after the control-plane lock wave. The runtime
candidate was rejected, so this package closes the control/evidence surfaces and
routes the smaller prerequisite instead of claiming implementation completion.

This packet does not accept the current dirty implementation candidate as-is.
The live candidate contains host-overload and adapter-theater patterns that
must be revised, replaced, or rejected with a smaller prerequisite. The
successful implementation must narrow the `projection_loader` bootstrap
boundary by separating filesystem reads from deterministic seed-image
verification while preserving Mu as the semantic authority.

## Scope

Allowed implementation write set:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/cli/main.js`
- `mu/tests/engine/test_seed_integrity.py`
- `mu/tests/structural/test_projection_loader.py`
- `mu/tests/parity/test_seed_loading_parity.py`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
- `mu/docs/core/L4MicroAbi.v0.md`
- `mu/tools/executors/phase_b_executor.py` same-wave pipeline root fix only
- `mu/tests/tools/test_phase_b_executor.py` focused pipeline root-fix regression only
- `mu/tools/executors/commit_executor.py` same-wave commit-handoff root fix only
- `mu/tests/tools/test_commit_executor_receipt.py` focused commit-handoff root-fix regression only
- `TASKS.md` same-wave tracker note
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
- `reports/archive/deferred/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14_bridge_nonblockers_closed-by-n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
- `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json`
- same-wave generated deferred non-blocking bridge findings packet, if any

Read-only grounding:

- `TASKS.md:347` for the predecessor N3 seed-image boundary adapter lock
  authority.
- `TASKS.md:331` and `TASKS.md:539` for the landed N3 broad-host-surface
  current-lane lineage.
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14.md`
- `reports/control_plane/n3-rcx-load-projection-loader-production-adapter-test-prereq-2026-05-14_2026-05-14.md`
- `mu/docs/core/Why_RCX_PI_VM_EXISTS.md`
- `mu/docs/core/SelfHosting.v0.md`
- `mu/docs/core/MetaCircularKernel.v0.md`
- `mu/docs/core/StructuralPurity.v0.md`
- `mu/docs/core/BootstrapPrimitives.v0.md`
- `mu/docs/core/L3SubstrateArchitecture.v0.md`
- `mu/docs/core/Boot0Architecture.v0.md`
- current startup output from `codex-rcx-preflight parity`

Out of scope:

- any seed JSON edit
- any registry/checksum/projection-ID authority expansion
- any binary/TLV seed image migration
- any D010 production-readiness claim
- any host-oracle, runner, recovery, bridge, hook, Codex-local, Claude-local, or
  hidden-memory edit; pipeline executor edits are allowed only for the same-wave
  handoff-root-fix block below
- any ratchet-baseline update used as the proof of structural progress

## Current Live Evidence

Startup in `parity` mode reproduced the current bad candidate state before this
packet was authored:

- `codex-rcx-preflight parity` reported pager/autoping health: tmux monitor
  active, dashboard reachable at `http://127.0.0.1:8099/api/state`, Codex pager
  target reachable at `http://127.0.0.1:8765/api/threads`, and Codex autoping
  active with pid `28731`.
- `python3 tools/checks/check_host_authority_inventory_ratchet.py` failed
  because `mu/host/js/cli/main.js::loadVerifiedSeedImage` is a new total and
  authority site at line 244/245 with `JSON.parse`.
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py -q`
  failed because the test expected a named JS core adapter while
  `mu/host/js/core/seed_loader.js` still used the arrow/overload candidate.
- `./tools/session/founder_session_attest.sh parity` passed, so this is a
  package/candidate defect, not a founder-protocol proof-class failure.

Direct file evidence from the live dirty candidate:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py:588-600` adds a sentinel
  overload to `load_verified_seed(...)`; `:653-659` defines
  `load_verified_seed_image` as a Python `lambda`.
- `mu/host/js/core/seed_loader.js:180-190` defines
  `loadVerifiedSeedImage` as a JS arrow adapter and overloads
  `loadVerifiedSeed(seedName, subdir, seedImageBytes = null)`.
- `mu/host/js/cli/main.js:245-256` adds a named `loadVerifiedSeedImage` that
  owns `JSON.parse`, creating a new authority site rejected by the inventory
  ratchet.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py:810-821`
  currently expects named adapters, while the core JS candidate still contains
  the arrow adapter shape above.

Doctrine evidence:

- `StructuralPurity.v0.md` says to program in RCX/Mu, not about RCX; its bad
  examples include Python lambdas in seed/semantic paths and host-language
  matching/control smuggling.
- `BootstrapPrimitives.v0.md` permits `projection_loader` only as a minimal,
  mechanical bootstrap primitive: JSON parse, integrity verification, schema
  validation, and no semantic branching/string manipulation/control choices.
- `L3SubstrateArchitecture.v0.md` says Python and JS must expose the same four
  bootstrap primitives and warns that `=>` in seed values is contraband.
- `L4MicroAbi.v0.md` defines the target `rcx_load(image_bytes) -> state` as
  deterministic, fail-closed, content-addressed, and hidden-channel-free.
- `Boot0Architecture.v0.md` lists `projection_loader` as stable bootstrap
  semantics whose host substrate may shrink over time; the semantics are not
  permission to make Python or JavaScript smarter.

## Required Direction

Phase B must choose the smallest implementation that narrows the live
filesystem-coupled loader boundary toward a deterministic seed-image boundary.

Required shape:

1. Keep all semantic authority in Mu seeds and projection order. The host loader
   may only read bytes, verify registered integrity, parse current JSON seed
   bytes, validate current seed structure, and validate expected projection IDs.
2. Separate file I/O from seed-image verification. Path-based loading may exist
   only as an outer filesystem wrapper that reads bytes and delegates to the
   seed-image boundary.
3. Use named production functions, not Python lambdas and not JS arrow adapter
   theater.
4. Do not use optional byte/path overloads such as Python sentinel parameters or
   JS `seedImageBytes = null` in the semantic loader path.
5. Preserve Python/JS parity: accepted inputs, rejected inputs, checksum-before
   parse behavior for known seeds, unknown-seed behavior, projection type
   guards, and projection-ID ordering must match where the substrates claim the
   same boundary.
6. Prefer preserving the existing authority-site count and identity where
   possible. If moving authority to a newly named byte-boundary function is the
   only honest implementation, Phase B must prove it is a same-count authority
   relocation, not an authority expansion, and must include a narrower
   alternative analysis before asking bridge/commit review to accept any
   accounting update.

Acceptable outcomes:

- `GO`: implementation narrows the boundary, removes the lambda/arrow/overload
  defects, passes the focused tests and ratchets, and records exact proof
  limits.
- `NO-GO`: current code truth proves the implementation would require adding
  host semantics, broad API churn, or ratchet accounting that needs a smaller
  prerequisite. The NO-GO must route the smallest next packet with exact
  file:line evidence.

## Constraints / Hard No-Go

Do not accept or stage an implementation that includes any of these:

- Python `lambda` adapter for `load_verified_seed_image`.
- JS arrow adapter for the production seed-image boundary.
- Optional path/byte overload in the semantic loader function.
- Host-side dynamic fallback, unregistered seed fallback, environment/network
  input, dynamic code generation, or hidden I/O channel.
- One-substrate implementation or one-substrate proof.
- New semantic branching, arithmetic, string manipulation, or control policy in
  the loader beyond the existing bootstrap primitive duties.
- New seed registry/checksum/projection-ID authority unless it is static,
  parity-locked, and explicitly required by the focused tests.
- A host-semantics ratchet increase.
- An authority-inventory increase. A same-count authority relocation is allowed
  only if Phase B proves the old authority site was removed, the new site is the
  byte-boundary replacement, and no narrower no-relocation alternative exists.
- Ratchet-baseline changes used to hide an increase.
- Any claim that this wave eliminates `projection_loader`, closes N3, completes
  L4, or productionizes binary/TLV seed images.

## Stop Conditions

Stop before commit readiness and route a `NO-GO` or smaller prerequisite packet
if any of these occur:

- Targeted current-code truth proves a listed work item is already implemented;
  remove it from pending work items and acceptance criteria instead of
  re-listing it as unresolved.
- Phase B cannot add a detector-visible same-wave `TASKS.md` tracker note for
  `n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14`.
- The smallest parity-preserving byte-boundary implementation requires new host
  semantics, dynamic fallback, seed authority expansion, registry/checksum
  expansion, or one-substrate behavior.
- The host-authority inventory cannot pass without more than a same-count
  relocation, or the bridge does not explicitly accept a documented same-count
  relocation with paired removed/new sites.
- Required focused tests, parity tests, host-semantics ratchet,
  host-authority inventory, staged L4 contract, or docs consistency cannot pass
  within the authorized write set.

## Work Items

1. Re-open the current dirty candidate and reject the lambda/arrow/overload
   shapes above before editing.
2. Implement the seed-image boundary in Python and JS with parity-preserving
   fail-closed behavior and no extra host semantic authority.
3. Keep filesystem wrappers thin: read bytes, pass seed name and bytes to the
   seed-image boundary, and return the verified seed.
4. Update production-boundary tests so they prove behavior, not adapter naming
   theater. Include source-lock checks only as support for behavior and ratchet
   evidence.
5. Update `L4MicroAbi.v0.md` only to describe the exact production truth after
   implementation, without overclaiming D010 or L4 completion.
6. Add the same-wave `TASKS.md` tracker note and collect the same-wave L4
   indicator artifact before commit automation.

## Required Validation

Phase B / commit handoff must run and record:

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
./tools/checks/check_js_debt.sh
```

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
```

```bash
python3 tools/checks/check_host_authority_inventory_ratchet.py
```

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14
```

```bash
./tools/checks/check_docs_consistency.sh
```

If authority inventory cannot pass without an accounting update for a same-count
rename, Phase B must stop before commit readiness unless the bridge explicitly
accepts the relocation as narrower than the old path-coupled authority and the
packet records the paired removed/new sites.

## Acceptance Criteria

- Runtime implementation is pipeline-owned; no manual runtime patch is accepted
  as completion for this packet.
- Python and JS expose the same seed-image boundary semantics.
- Filesystem loaders are outer wrappers and do not parse, validate, or own
  semantic authority beyond delegating bytes to the boundary.
- Known-seed tampering fails before JSON parse in both substrates.
- Unknown, malformed, non-finite numeric, malformed projection, and projection
  ID/order cases retain fail-closed behavior with parity where the substrates
  claim parity.
- Focused production tests and parity tests pass.
- Host-semantics ratchet passes with no increase.
- Host-authority inventory passes, or the wave NO-GOs before commit readiness
  with a smaller mechanization/accounting prerequisite.
- The staged L4 contract passes for this exact wave ID.
- The final packet and tracker note state proof limits: this is a JSON
  seed-image boundary narrowing, not projection-loader elimination, D010
  productionization, N3 closure, or L4 completion.

## Pipeline Requirement

Launch this work through:

```bash
python3 mu/tools/executors/executor_dispatch.py --routing-record .agent_bus/meta/post_merge_routing.json --loop --max-waves 1 --json
```

Manual runtime implementation from the operator session is out of scope. If the
pipeline breaks, diagnose the root cause with direct evidence. Manual unblock is
allowed only as a bounded operator-visible repair, and the same wave or a
follow-up wave must mechanize the root fix in dispatcher, builder, recovery,
commit, pre-commit, pager/autoping, or another appropriate pipeline surface so
the same failure does not require another manual repair.

Same-wave authorization line for detector-visible L4 handling:

`FOUNDER_OVERRIDE:n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14`

## Phase B Runtime Candidate Rejection (2026-05-15)

Runtime status: rejected before runtime commit readiness.

Commit-bound package status: `COMMIT_GO` as an `L4_ENABLER` control/evidence
closeout with no accepted runtime/substrate delta.

The current candidate cannot be safely accepted, and the smallest honest
production byte-boundary implementation cannot satisfy this packet's authority
inventory stop condition within the authorized write set.

Direct candidate defects reproduced in this Phase B pass:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py:596-600` overloads
  `load_verified_seed(...)` with a `seed_image_bytes` sentinel argument, and
  `mu/host/python/rcx_pi/selfhost/seed_integrity.py:653-659` exports
  `load_verified_seed_image` as a lambda.
- `mu/host/js/core/seed_loader.js:180-190` exports
  `loadVerifiedSeedImage` as an arrow adapter and overloads
  `loadVerifiedSeed(seedName, subdir, seedImageBytes = null)`.
- `mu/host/js/cli/main.js:245-256` adds `loadVerifiedSeedImage` as a new
  `JSON.parse` authority site.

Ratchet blocker:

- `python3 tools/checks/check_host_authority_inventory_ratchet.py` fails on the
  live candidate with a new total and authority site:
  `mu/host/js/cli/main.js::loadVerifiedSeedImage`.
- The inventory checker records every Python `FunctionDef` as a total site and
  every top-level JS `function`, arrow-with-block, or `const ... = function`
  as a total site. The current baseline contains only
  `rcx_pi/selfhost/seed_integrity.py::load_verified_seed`,
  `mu/host/js/core/seed_loader.js::loadVerifiedSeed`, and
  `mu/host/js/cli/main.js::loadVerifiedSeed` for these loader boundaries.
  Therefore replacing the lambda/arrow/overload candidate with real named
  `load_verified_seed_image` / `loadVerifiedSeedImage` production functions
  creates new inventory keys before any semantic behavior is considered.

Why this is not a same-count relocation:

- The existing path loaders must remain public compatibility wrappers for
  current Python and JS callers.
- Adding a separate named byte-boundary function while retaining those wrappers
  is an additional total inventory site on each substrate, not a pure rename of
  the existing path-coupled authority site.
- Hiding the adapter behind an unscanned assignment, object method, dynamic
  callable, lambda, or optional overload would make the ratchet pass by
  avoiding the detector rather than by reducing authority. That violates this
  packet's hard no-go rules.

Phase B runtime disposition:

- The forbidden runtime/test/doc candidate was rejected from the staged
  snapshot rather than accepted with lambda, arrow, overload, or hidden adapter
  shapes.
- A same-wave `TASKS.md` tracker note and L4 indicator artifact were added.
- No executable runtime delta is accepted by this wave. The commit-bound package
  is therefore classified as `L4_ENABLER` control/evidence, not
  `L4_STRUCTURAL`, and it makes no seed-image boundary implementation claim.

Validation evidence from this Phase B pass after rejecting the dirty candidate:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/engine/test_seed_integrity.py \
  mu/tests/structural/test_projection_loader.py \
  mu/tests/parity/test_seed_loading_parity.py \
  mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestJsSeedLoaderMalformedProjection \
  mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestF2ProductionBindingLock
```

Result: passed with `94 passed in 0.66s`.

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/parity/test_parity_python.py \
  mu/tests/parity/test_js_parity_automated.py::TestJSTestSuitePasses \
  mu/tests/parity/test_js_parity_automated.py::TestCrossSubstrateParity
```

Result: passed with `34 passed in 12.20s`.

```bash
node mu/host/js/eval_step.js
```

Result: passed with `All tests passed: true`.

```bash
./tools/checks/check_js_debt.sh
```

Result: passed.

```bash
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
```

Result: passed with `passed: true` and no increases.

```bash
python3 tools/checks/check_host_authority_inventory_ratchet.py
```

Result: passed with `311 total (181 Python + 130 JS)` against baseline
`312 total (181 Python + 131 JS)`, and `217 authority` unchanged.

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14
```

Historical result before re-entry reconciliation: failed as expected while the
packet still declared `L4_STRUCTURAL` despite having no runtime/substrate files
and no changed L4 gate file after the forbidden runtime candidate was rejected.

```bash
./tools/checks/check_docs_consistency.sh
```

Result: passed; docs are consistent.

Smallest next prerequisite:

- Route a smaller authority-inventory/accounting design packet before this
  runtime implementation resumes. That prerequisite must decide whether the
  seed-image boundary may add public wrapper inventory sites, or must first
  mechanize an explicit same-wave relocation model for path-wrapper-to-byte
  boundary splits. It must not update a ratchet baseline merely to hide an
  authority increase.

## Phase B Re-entry Reconciliation (2026-05-15)

Status: `COMMIT_GO` for `L4_ENABLER` control/evidence closeout.

Re-entry fixed the package contradiction where the supervisor package and
`TASKS.md` tracker were already `L4_ENABLER`, while this governing packet still
declared `L4_STRUCTURAL` and package-level `NO-GO`. The reconciled package now
states the runtime candidate rejection as the substantive result and the
commit-bound docs/control-plane package as the L4 enabler closeout.

Current commit-bound truth:

- No runtime, substrate, seed, projection, registry, checksum, or L4 Micro-ABI
  file is changed by this package. The only executable-code delta is a
  Phase B executor control-plane repair plus focused executor tests so the
  pipeline can commit this package without recreating closed active deferred
  state.
- The active generated bridge non-blocker is closed by archiving the original
  generated packet at
  `reports/archive/deferred/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14_bridge_nonblockers_closed-by-n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
  and staging deletion of the old active-lane path.
- The runtime proof limit remains: this wave records a rejected JSON seed-image
  boundary candidate and a smaller authority-inventory/accounting prerequisite;
  it does not implement `rcx_load(image_bytes)`, eliminate `projection_loader`,
  close N3, complete L4, or make a D010 production-readiness claim.

## Same-Wave Pipeline Root Fix (2026-05-15)

Root-cause evidence: after bridge round 3 returned `COMMIT_GO`, Phase B handoff
failed in `prepare_commit_handoff(...)` because commit handoff validation saw
the same generated bridge packet as both active deferred and archived closed for
this wave. Direct stderr named the conflicting paths:

- `reports/deferred/non_blocking/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14_bridge_nonblockers.md`
- `reports/archive/deferred/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14_bridge_nonblockers_closed-by-n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`

A retry after closed-archive retention exposed the remaining mechanical cause:
the active deferred packet was staged as a deletion, but Phase B still listed it
as an active supervisor/handoff `deferred_items` entry because deferred-item
collection only inspected path names in `changed_files`. Index evidence before
this repair showed `D` for the active-lane packet in
`git diff --cached --name-status`, while `git ls-files --stage` returned no
entry for that path.

Re-entry review then exposed the second half of the same handoff-root class:
branch rebind correctly treated the active deferred deletion as scoped dirt via
`scope_items`, but `_restore_scope_snapshot(...)` restored it as an unstaged
worktree deletion. A later bridge finding showed the attempted repair was too
broad because `_stage_handoff_paths(...)` could stage arbitrary deleted
`scope_items` paths that were never in `files_to_stage`, turning context scope
into commit authority.

Mechanical repair:

- `mu/tools/executors/phase_b_executor.py` now retains later non-blocking review
  notes inside the same-wave closed archive when that archive already exists,
  clears the active generated packet path, omits the active deletion from
  commit `files_to_stage`, and carries the staged deletion in handoff scope.
- Phase B supervisor/handoff deferred-item collection now consults the git index
  and omits active-lane deferred packets that are staged deletions, while leaving
  those deletions in the commit-bound file set.
- `mu/tools/executors/commit_executor.py` now treats a same-wave active deferred
  packet staged as a deletion as closed for the active/archive collision check,
  includes handoff `scope_items` in branch-rebind dirty-scope matching, captures
  staged deletion state during branch-rebind snapshot/restore, and keeps
  `_stage_handoff_paths(...)` staging authority limited to `files_to_stage` and
  `force_files`. `scope_items` can preserve an already staged deletion through
  branch rebind, but cannot create a new staged deletion.
- `mu/tests/tools/test_phase_b_executor.py::TestDeferredPacketFiling` covers the
  closed-archive path, idempotent post-closure note replacement, and the
  staged-deletion deferred-item regression.
- `mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd`
  covers the commit handoff validator path that failed after pre-commit returned
  `COMMIT_GO`.
- `mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds` covers the
  branch-rebind snapshot/restore/stage path that previously dropped a scoped
  staged deletion before commit staging and the scope-only deletion case that
  previously let context paths become commit authority.

Focused evidence:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestDeferredPacketFiling --tb=short
```

Result: passed with `15 passed in 1.30s`.

Additional focused root-fix evidence:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_validate_handoff_rejects_same_wave_active_packet_when_closed_archive_staged mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_validate_handoff_rejects_same_wave_active_packet_with_archive_without_deferred_items mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_build_handoff_accepts_same_wave_staged_deletion_with_closed_archive --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_phase_b_executor.py::TestDeferredPacketFiling::test_commit_handoff_stage_files_omit_closed_active_staged_deletion mu/tests/tools/test_phase_b_executor.py::TestDeferredPacketFiling::test_commit_handoff_stage_files_scope_staged_deletion_for_branch_rebind --tb=short
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_stage_handoff_paths_does_not_stage_scope_only_deletion mu/tests/tools/test_commit_executor_receipt.py::TestWaveIdBounds::test_stage_handoff_paths_restages_scoped_deletion_after_rebind_restore --tb=short
```

Result: passed with `3 passed in 0.44s`, `2 passed in 0.67s`, and `2 passed in
1.13s`.

## Commit Executor Retry Root Fix (2026-05-15)

Root-cause evidence after PR #970 reached the commit/push/CI path:

- `.agent_bus/executors/phase_b_handoff.json` still listed the old active
  generated packet in `files_to_stage` and `scope_items`, while also listing the
  closed archive in `files_to_stage` and `force_add_files`.
- `git log --name-status -2 -- <active-packet> <closed-archive>` shows commit
  `09579ac4` deleted the active packet and added the archive.
- `git ls-files --stage -- <active-packet> <closed-archive>` now returns only
  the closed archive index entry. The active generated packet is absent from the
  worktree and index.
- The retry validator only excluded active paths while they were currently
  staged deletions. After the deletion commit, the same stale handoff path was no
  longer a staged deletion, so validation reconstructed a false active/archive
  collision from handoff text instead of repo truth.

Mechanical repair:

- `mu/tools/executors/commit_executor.py` now treats a same-wave active deferred
  packet as closed for the active/archive collision check when the path is absent
  from both the worktree and Git index.
- The existing staged-deletion allowance remains intact, so uncommitted closeout
  still passes only when the active packet deletion is staged.
- The validator still rejects handoffs that list an active packet and closed
  archive when no repo root is provided or when the active packet remains live in
  repo truth.
- `mu/tests/tools/test_commit_executor_receipt.py` adds a committed-deletion
  regression that reproduces the retry state: stale handoff text lists both
  active and archive paths, while the repo has already committed deletion of the
  active packet and retained only the archive.

Focused retry-root evidence:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_build_handoff_accepts_same_wave_staged_deletion_with_closed_archive \
  mu/tests/tools/test_commit_executor_receipt.py::TestReceiptChainEndToEnd::test_validate_handoff_accepts_same_wave_committed_deletion_with_closed_archive \
  --tb=short
```

Result: passed with `2 passed in 0.93s`.

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_commit_executor_receipt.py --tb=short
```

Result: passed with `131 passed in 32.31s`.

```bash
python3 -m py_compile mu/tools/executors/commit_executor.py
git diff --check
./tools/checks/check_docs_consistency.sh
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
```

Result: passed. Host-semantics ratchet reported no increases; host-authority
inventory remained `311 total` / `217 authority`, with no new total-inventory or
authority-subset sites detected.

Current staged L4 evidence after the retry-root fix:

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14
```

Result: passed as `L4_ENABLER` compliant with 5 changed files, 0 runtime files,
and only control-plane/tooling evidence paths in scope.

Retry-root staged files:

- `TASKS.md`
- `mu/tests/tools/test_commit_executor_receipt.py`
- `mu/tools/executors/commit_executor.py`
- `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
- `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json`

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/archive/deferred/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14_bridge_nonblockers_closed-by-n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
  - `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
  - `reports/deferred/non_blocking/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14`
- Active packet: `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `9dfb21ba9105f9cc6d811cdd0596893719de8daa4299b33623aeddf7235b2140`
- Indicator artifact: `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Routed commit handoff scopes 5 wave-owned file(s). (2) Evidence gate exercises 1 wave-owned test module(s). (3) Indicator artifact binds the wave to reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.md`
  - `reports/l4_wave_indicators/n3-rcx-load-seed-image-boundary-adapter-implementation-2026-05-14.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
