# N3 JS Seed Image Boundary Manifest Authority Narrowing - 2026-05-17

Date: 2026-05-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17
Phase-A-Lock: LOCKED
Packet Class: L4_ENABLER control-surface Phase A packet
Candidate Phase B Class: L4_STRUCTURAL only if Phase A returns GO
Target Gate: G8
Workload Target: host_debt_reduction
FOUNDER_OVERRIDE:n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17
Authorization: standing pipeline-bug-fix authorization for this control-surface L4_ENABLER Phase A packet; the packet-local override above exists so commit automation can derive same-wave authority while TASKS.md lacks the exact wave id.

## Scope

Files and directories in scope for this Phase A packet:
- `reports/control_plane/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_2026-05-17.md`
- `TASKS.md` only for targeted `[NEXT-CODEX-POST-REDTEAM]` authorization lines and the absence/presence of this exact wave id
- Reviewer-cited seed boundary surfaces for Phase A evidence only:
  - `mu/host/js/core/seed_loader.js`
  - `mu/host/js/cli/main.js`
  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/engine/test_seed_integrity.py`
- Governing predecessor packet references named by the post-merge supervisor:
  - `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
  - `reports/control_plane/n3_seed_registry_manifest_reduction_2026_05_14_2026-05-16.md`
- Validation-only surfaces if Phase A returns GO:
  - `tools/checks/enforce_l4_execution_contract.py`
  - `mu/tools/checks/check_host_semantics_ratchet.py`
  - `tools/checks/check_host_authority_inventory_ratchet.py`
  - `tools/checks/check_docs_consistency.sh`

Directories and domains out of scope unless Phase A stops and routes a successor:
- Seed corpus data and checksum data edits under `mu/seeds/` or `mu/seed_registry_manifest.v1.json`
- Runtime semantics outside the JS seed-image byte-boundary path
- Stage0, scheduler, engine pipeline, bridge executor, production `/mu`, host oracle, and Claude surfaces
- Ratchet baseline changes, generated bridge-residue cleanup, or unrelated deferred-lane cleanup

## Work Items

1. Confirm tracker grounding for this Phase A route from current TASKS evidence without broad repository investigation.
   - TASKS.md:347 records the prior `n3-rcx-load-seed-image-boundary-adapter-lock-2026-05-14` N3 seed-image boundary packet as `[NEXT-CODEX-POST-REDTEAM]`.
   - TASKS.md:358 records the landed N3 JSON seed-image boundary runtime retry with structural artifacts including `mu/host/python/rcx_pi/selfhost/seed_integrity.py`, `mu/host/js/core/seed_loader.js`, `mu/host/js/cli/main.js`, `mu/tests/engine/test_seed_integrity.py`, `mu/tests/parity/test_seed_loading_parity.py`, and `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`.
   - TASKS.md:362 records the landed `n3-seed-registry-manifest-reduction-2026-05-14` manifest-reduction predecessor and its governing packet `reports/control_plane/n3_seed_registry_manifest_reduction_2026_05_14_2026-05-16.md`.
   - TASKS.md:363 records the immediately adjacent `n3-projection-loader-numeric-domain-policy-2026-05-14` seed-loader numeric-domain policy wave.
   - TASKS.md:364 records the same-day JS seed parity argv transport CI repair and explicitly says production Python/JS seed loaders are unchanged.

2. Produce a Phase A GO/NO-GO decision for the exact question: can arbitrary caller-supplied JavaScript `checksumRegistry` and `projectionIdRegistry` authority at the seed-image byte boundary be removed, demoted, or confined to a test-only negative-control surface without widening host authority?

3. If Phase A returns GO, lock the smallest exact Phase B write set before implementation:
   - `mu/host/js/core/seed_loader.js`
   - `mu/host/js/cli/main.js` only if the production call surface must change with the loader API
   - `mu/tests/parity/test_seed_loading_parity.py`
   - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
   - `mu/tests/engine/test_seed_integrity.py` only if parity with Python seed-boundary assertions must be refreshed
   - this packet, only for Phase A lock/decision text

4. If Phase A returns NO-GO, record the smallest evidence-backed successor route instead of implementing:
   - test-only custom registries remain required negative controls, or
   - a manifest-derived closed verification view cannot be introduced without losing fail-closed coverage, or
   - current code truth already proves the candidate is landed and no pending implementation work remains.

5. Preserve the predecessor manifest wave boundary: host code may verify manifest bytes/root trust, parse current JSON, validate shape, look up seed metadata by filename, verify seed bytes, validate current seed structure, validate ordered projection IDs from manifest data, resolve seed subdirectories from manifest data, and check dependencies generically. Do not add semantic host interpretation beyond that accepted mechanical behavior.

## Constraints

- Do not make Python or JavaScript smarter.
- Do not add host-only semantics, lambda or arrow adapter theater, dynamic callable hiding, optional overload or sentinel tricks, detector evasion, new bootstrap primitives, D010 or binary productionization claims, N3 closure claims, or ratchet baseline changes.
- Do not edit seed JSON, checksum data, manifest data, or generated registry truth unless Phase A stops and routes a separate seed-data wave.
- Do not weaken checksum-before-parse, invalid UTF-8 rejection, numeric-domain rejection, manifest-root trust before seed parse, malformed projection fail-closed tests, or Python/JS parity.
- Do not add a new host authority site unless the Phase A GO packet proves an accepted, detector-visible structural split with exact validation.
- Do not use TASKS.md lineage as proof that any specific work item is still unlanded. Current code truth wins over stale packet wording if Phase A verification finds a conflict.
- Do not inspect or modify unrelated dirty files, git diffs, executor changes, generated bridge packets, or unrelated tests for this packet rewrite.

## Stop Conditions

Stop Phase A with NO-GO and route the narrowest successor if any of the following are true:
- The only arbitrary JS registry path is test-only negative-control coverage and removing it would weaken required fail-closed assertions.
- The production JS seed-image byte boundary already rejects caller-provided registry authority or already derives verification views exclusively from the manifest.
- Narrowing the JS API would require Python behavior changes, seed-data edits, manifest schema changes, ratchet baseline changes, or new host semantics.
- Focused evidence cannot distinguish production authority from test harness authority without inspecting implementation files beyond the reviewer-cited surfaces.
- The packet cannot be grounded to current TASKS authorization or a same-wave automation override before Phase B.

Stop Phase B before implementation if the final Phase A GO packet does not lock:
- exact write set,
- exact tests,
- same-wave TASKS tracker requirement,
- L4 indicator artifact requirement,
- no-new-host-authority proof requirement.

## Acceptance Criteria

Phase A acceptance:
- The packet contains explicit `Scope`, `Work Items`, `Constraints`, `Stop Conditions`, `Acceptance Criteria`, and `Grounding / Authorization` sections.
- The packet names the exact files/directories in scope and the exact out-of-scope domains.
- The packet records that `rg -n "n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17" TASKS.md` currently has no same-wave hit, and therefore Phase B must not proceed until either TASKS gains detector-visible same-wave tracker authority or the packet-local `FOUNDER_OVERRIDE`/authorization line is accepted by the commit path for this L4_ENABLER control-surface packet.
- The packet includes `FOUNDER_OVERRIDE:n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17` and the explicit standing pipeline-bug-fix authorization line above.
- The final Phase A result is either GO with a locked smallest write set and validation set, or NO-GO with file:line evidence and a narrow successor route.

Phase B acceptance if Phase A returns GO:
- Production JS seed-image verification no longer depends on arbitrary caller-provided `checksumRegistry` or `projectionIdRegistry` authority at the byte boundary, or those inputs are demoted to a detector-visible test-only negative-control surface.
- Any replacement authority is manifest-derived, closed over the trusted manifest view, and no broader than the predecessor manifest wave's accepted mechanical behavior.
- Python/JS parity remains explicit and checksum-before-parse is preserved.
- Invalid UTF-8, numeric-domain rejection, manifest-root trust before seed parse, and malformed projection fail-closed behavior remain covered.
- Focused seed loader/parity/L4 tests pass:
  - `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/engine/test_seed_integrity.py mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py mu/tests/parity/test_seed_loading_parity.py`
- Ratchet and governance checks pass before commit handoff:
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `./tools/checks/check_docs_consistency.sh`
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17`
- If implementation proceeds, the same wave records a TASKS tracker note and L4 indicator artifact before commit automation or bridge review treats the packet as converged.

## Grounding / Authorization

Direct packet evidence:
- Target packet before this rewrite was a stub: it had only `## Scope` at line 10 and `## Request from Post-Merge Supervisor` at line 14, with no concrete work items, stop conditions, acceptance criteria, or grounding/authorization section.
- The prior packet already named the Phase A purpose and the post-merge supervisor's evidence requirements, including the JS custom-registry candidate at `mu/host/js/core/seed_loader.js:209-216`, `seed_loader.js:226-230`, and `seed_loader.js:356-367`.

TASKS.md targeted authorization evidence:
- `TASKS.md:347` authorizes prior N3 seed-image boundary work under `[NEXT-CODEX-POST-REDTEAM]`.
- `TASKS.md:358` records the N3 JSON seed-image boundary runtime retry as L4_STRUCTURAL host-debt reduction with the current seed loader/parity/l4 test surfaces.
- `TASKS.md:362` records the manifest-reduction predecessor as L4_STRUCTURAL host-debt reduction and points to `reports/control_plane/n3_seed_registry_manifest_reduction_2026_05_14_2026-05-16.md`.
- `TASKS.md:363` records the adjacent projection-loader numeric-domain policy wave against `mu/host/js/core/seed_loader.js`, `mu/host/python/rcx_pi/selfhost/seed_integrity.py`, and the seed loader tests.
- `TASKS.md:364` records a same-day control-surface CI repair and explicitly says production Python/JS seed loaders are unchanged.

Same-wave authority status:
- Direct targeted search for `n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17` in `TASKS.md` currently has no hit. This packet rewrite cannot edit `TASKS.md` by user constraint, so it makes the missing same-wave tracker authority explicit and adds the packet-local `FOUNDER_OVERRIDE` plus authorization line required for control-surface L4_ENABLER routing.
- Phase B must add detector-visible same-wave TASKS tracker authority and an L4 indicator artifact if implementation proceeds.

Governing packet refs:
- This file is the governing Phase A packet for `n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17`.
- Predecessor direction comes from `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md` and `reports/control_plane/n3_seed_registry_manifest_reduction_2026_05_14_2026-05-16.md`.

## Phase A Decision

Decision: GO.

Scoped code truth distinguished production authority from test harness authority. Before Phase B edits, `mu/host/js/core/seed_loader.js` exposed `loadVerifiedSeedImage` with caller-supplied `checksumRegistry` and `projectionIdRegistry` inputs, and the production wrappers in `mu/host/js/core/seed_loader.js` and `mu/host/js/cli/main.js` passed manifest-derived maps through that public byte-boundary call. The candidate is therefore not already landed, and narrowing can proceed without Python behavior changes, seed-data edits, manifest schema changes, ratchet baseline changes, or host-only semantic expansion.

Locked Phase B write set:
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/cli/main.js`
- `mu/tests/parity/test_seed_loading_parity.py`
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
- `reports/control_plane/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_2026-05-17.md`
- `TASKS.md` only for detector-visible same-wave tracker authority
- `reports/l4_wave_indicators/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17.json`

Locked validation set:
- `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/engine/test_seed_integrity.py mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py mu/tests/parity/test_seed_loading_parity.py`
- `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
- `python3 tools/checks/check_host_authority_inventory_ratchet.py`
- `./tools/checks/check_docs_consistency.sh`
- `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17`

Same-wave TASKS tracker requirement: Phase B must add a detector-visible tracker note for `n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17` before commit handoff.

L4 indicator artifact requirement: Phase B must write `reports/l4_wave_indicators/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17.json` with the same wave id before commit handoff.

No-new-host-authority proof requirement: production JS seed-image verification must close over manifest-derived CLI/core verification modes. Any synthetic checksum/projection maps must be reachable only through the detector-visible `SEED_IMAGE_VERIFICATION_MODES.TEST_ONLY_NEGATIVE_CONTROL` test surface and must not be used by `mu/host/js/core/seed_loader.js` path loading or `mu/host/js/cli/main.js` path loading.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17`
- Active packet: `reports/control_plane/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_2026-05-17.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/cli/main.js`
  - `mu/host/js/core/seed_loader.js`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `reports/control_plane/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_2026-05-17.md`
  - `reports/deferred/non_blocking/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
