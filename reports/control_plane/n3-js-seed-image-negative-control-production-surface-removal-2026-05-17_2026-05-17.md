# N3-Js-Seed-Image-Negative-Control-Production-Surface-Removal-2026-05-17

Date: 2026-05-17
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-js-seed-image-negative-control-production-surface-removal-2026-05-17
Class: L4_STRUCTURAL
Phase-A-Lock: LOCKED
Decision: GO, subject to the stop conditions below.
Question: Can JS negative-control coverage be preserved while removing `TEST_ONLY_NEGATIVE_CONTROL`, `negativeControlView`, and arbitrary synthetic checksum/projection registry maps from the production `mu/host/js/core/seed_loader.js` export and live runtime surface?

## Scope

This packet rewrite write set:
- `reports/control_plane/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17_2026-05-17.md`

Phase B candidate implementation scope, if this GO plan is accepted:
- `mu/host/js/core/seed_loader.js` - production JS seed-image loader surface to narrow.
- `mu/host/js/cli/main.js` - production CLI load path reference; write only if the removal requires call-site adjustment.
- `mu/tests/` - focused seed-image negative-control, parity, and L4 gate tests only; exact test files must be locked from current code before edits.
- `TASKS.md` - same-wave tracker entry only, required before implementation or commit handoff.
- `reports/l4_wave_indicators/` - same-wave L4 indicator artifact only if Phase B proceeds.

Read-only grounding scope before Phase B edits:
- `reports/control_plane/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_2026-05-17.md`
- `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`
- `reports/deferred/non_blocking/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_bridge_nonblockers.md`

## Work items

1. Before implementation, verify current code truth for the supervisor evidence: `mu/host/js/core/seed_loader.js` still exposes `SEED_IMAGE_VERIFICATION_MODES.TEST_ONLY_NEGATIVE_CONTROL`, still accepts `negativeControlView`, and still dereferences caller-supplied checksum/projection registry data from that negative-control path.
2. Verify production paths still use manifest-derived authority through the `CORE` load path in `mu/host/js/core/seed_loader.js` and the `CLI` load path in `mu/host/js/cli/main.js`.
3. Add the missing same-wave `TASKS.md` tracker entry for `n3-js-seed-image-negative-control-production-surface-removal-2026-05-17` before any Phase B implementation or commit handoff; `TASKS.md:548` requires every wave to have both a control-plane packet and a tracker entry.
4. If the residual production surface is still present, remove production reachability for `TEST_ONLY_NEGATIVE_CONTROL`, `negativeControlView`, and arbitrary caller-supplied checksum/projection registry maps from `mu/host/js/core/seed_loader.js`.
5. Preserve JS negative-control coverage by using one bounded structural path: move synthetic-registry controls into detector-visible test-only harness code outside production runtime exports, replace them with mutation-based controls that exercise production `CORE`/`CLI` modes, or introduce a test-only helper outside the production host runtime surface.
6. Run focused seed-loader/parity/L4 validation and the relevant ratchets before closeout. Validation must prove checksum-before-parse, invalid UTF-8 rejection, numeric-domain rejection, manifest-root trust before seed parse, malformed projection fail-closed behavior, and Python/JS parity remain intact.
7. If evidence proves coverage cannot be preserved without this production export/path, stop as NO-GO and route the smallest successor packet with file:line evidence.

## Constraints

- Do not broaden this packet rewrite beyond `reports/control_plane/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17_2026-05-17.md`.
- Do not start Phase B implementation in this turn.
- Do not make Python or JavaScript smarter by adding host-only semantics, lambda/arrow adapter theater, dynamic callable hiding, optional overload/sentinel tricks, detector evasion, or new bootstrap primitives.
- Do not claim D010/binary productionization, N3 closure, L4 closure, or ratchet baseline changes from this wave.
- Do not change seed JSON, checksum files, manifest data, or Python seed-loader behavior unless Phase A stops and routes a separate seed-data/parity wave with evidence.
- Do not add new production host authority sites or move synthetic registry authority into another production export.
- Do not weaken existing checksum, UTF-8, numeric-domain, manifest-root, malformed-projection, or parity fail-closed coverage to make the removal easier.
- Do not use docs-only wording as a substitute for removing the production-surface residual if code truth shows the residual is still present.

## Stop conditions

- Stop before Phase B if the same-wave `TASKS.md` tracker entry is still absent. This packet carries a wave-bound override, but the tracker entry is still required by `TASKS.md:548`.
- Stop if current code truth proves `TEST_ONLY_NEGATIVE_CONTROL`, `negativeControlView`, and caller-supplied registry maps are already removed from the production loader surface; do not relist landed work as unresolved.
- Stop as NO-GO if file:line evidence proves JS negative-control coverage cannot be preserved without a production loader export or live runtime path for synthetic registry authority.
- Stop if the only available implementation would add host-only semantics, widen JS/Python host authority, or introduce a new production registry loophole.
- Stop if preserving coverage requires seed-data, checksum, manifest, Python parity, or ratchet-baseline changes outside this packet's locked scope.
- Stop and route a precise follow-up automation packet if pipeline failure diagnosis requires a mechanical dispatcher/builder/recovery/commit/pre-commit fix that cannot be safely made in the same wave.

## Acceptance criteria

- Packet structure is detector-visible: `Scope`, `Work items`, `Constraints`, `Stop conditions`, `Acceptance criteria`, and `Grounding / Authorization` sections are present.
- Scope is an explicit file/directory list, with this rewrite limited to the packet and Phase B candidate scope locked separately.
- The packet contains a detector-visible wave-bound authorization line: `FOUNDER_OVERRIDE:n3-js-seed-image-negative-control-production-surface-removal-2026-05-17`.
- Before Phase B implementation or commit handoff, `TASKS.md` contains a same-wave tracker entry for `n3-js-seed-image-negative-control-production-surface-removal-2026-05-17`.
- If Phase B proceeds, production `mu/host/js/core/seed_loader.js` exposes only manifest-derived production seed-image verification authority; no caller-supplied checksum/projection registry map authority remains reachable from production loader exports.
- JS negative-control coverage remains present through detector-visible test-only scaffolding or mutation-based production-mode tests that do not widen the runtime surface.
- Focused validation passes for seed-loader behavior, Python/JS parity, L4 execution contract, host-semantics ratchet, host-authority inventory ratchet, and docs consistency.
- Closeout includes the changed file list, exact validation commands/results, L4 indicator artifact, invariant tuple, and an explicit GO/NO-GO rationale.

## Grounding / Authorization

TASKS grounding:
- `TASKS.md:540-548` keeps `[NEXT-CODEX-POST-REDTEAM]` unparked and open for remaining bounded structural reduction work.
- `TASKS.md:548` orders the founder red-team wave queue, requires every wave to have a control-plane packet plus a `TASKS.md` tracker entry, and carries `FOUNDER_OVERRIDE:founder-ordered-redteam-wave-queue-2026-05-05`.
- Targeted lookup for `n3-js-seed-image-negative-control-production-surface-removal-2026-05-17` in `TASKS.md` returned no same-wave match during this packet rewrite; because this turn is packet-only, adding that tracker entry is a Phase B stop condition rather than a hidden edit.

Governing packet refs:
- Current governing packet: `reports/control_plane/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17_2026-05-17.md`.
- Predecessor boundary packet cited by the supervisor: `reports/control_plane/n3-js-seed-image-boundary-manifest-authority-narrowing-2026-05-17_2026-05-17.md`.
- Host-debt reduction context cited by the supervisor: `reports/control_plane/n3-autonomous-host-debt-reduction-plan-2026-05-14.md`.

Authorization:
- FOUNDER_OVERRIDE:n3-js-seed-image-negative-control-production-surface-removal-2026-05-17
- This override is packet-local, wave-bound, and subordinate to the `TASKS.md:548` requirement that Phase B must add a same-wave tracker entry before implementation or commit handoff.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-js-seed-image-negative-control-production-surface-removal-2026-05-17`
- Active packet: `reports/control_plane/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17_2026-05-17.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/core/seed_loader.js`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `reports/control_plane/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17_2026-05-17.md`
  - `reports/deferred/non_blocking/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-js-seed-image-negative-control-production-surface-removal-2026-05-17.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
