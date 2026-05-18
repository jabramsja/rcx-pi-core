# N3 Projection Loader JS UTF-8 Decode Error Taxonomy 2026-05-18

Date: 2026-05-18
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18
Phase-A-Lock: LOCKED
Class: L4_STRUCTURAL
Category: /mu structural host-debt reduction prerequisite
Authorization: FOUNDER_OVERRIDE:n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18

## Scope

This wave is the next bounded N3 projection-loader reduction after the JS
MuBinary sidecar decoder landed. It is limited to replacing the JS MuBinary
sidecar decoder's native host `TypeError` escape for malformed UTF-8 string
payloads with the existing Mu decoder taxonomy, `MuBinaryDecodeError`.

Files in Phase A / Phase B scope:

- `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md`
  as the governing packet and Phase A lock surface.
- `mu/host/js/core/seed_loader.js` for the JS sidecar MuBinary decoder malformed
  UTF-8 payload taxonomy only.
- `mu/tests/parity/test_seed_loading_parity.py` for focused parity /
  negative-control coverage of malformed UTF-8 binary string payloads.
- `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py` for the
  same-wave L4 changed-test contract and production-boundary sidecar lock.
- `reports/l4_wave_indicators/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.json`
  as the same-wave L4 indicator artifact generated during validation.

The production JSON seed loader remains the default and rollback path.

## Work Items

- Lock Phase A for the `[NEXT-CODEX-POST-REDTEAM]` bounded structural queue
  item. `TASKS.md:548-552` keeps the task unparked, founder-authorized, and
  open for remaining bounded structural reduction work; it does not prove every
  historical item is still pending.
- Preserve current code truth from the prior N3 binary decoder parity wave:
  the sidecar decoder already exists. This wave must not relist sidecar decoder
  creation, engine-state/scheduler seeds, fixtures, structural tests, scheduler
  parity, or seed-registration work as unresolved.
- Before Phase B dispatch, ensure the same-wave control-plane packet and
  required `TASKS.md` tracker entry are mechanically bound to this wave id,
  task id, class, category, scope, and authorization. `TASKS.md:556` requires
  every wave to have both a control-plane packet and a `TASKS.md` tracker entry.
- Implement the narrow JS sidecar decoder taxonomy reduction: malformed UTF-8
  string payloads must still fail closed, but the public sidecar decoder error
  type must be `MuBinaryDecodeError`, not host `TypeError`.
- Add or extend focused parity / negative-control coverage proving the malformed
  UTF-8 binary string payload returns `MuBinaryDecodeError`.
- Collect the same-wave L4 indicator and run the focused validation set before
  closeout.

## Constraints

- Do not widen production seed loading, add production binary/TLV loading, flip
  defaults, migrate seed storage, or change checksum / integrity-chain policy.
- Do not add a new host semantic layer. The fix must narrow host leakage through
  the existing Mu decoder taxonomy.
- Do not edit Python runtime/substrate code unless Phase A proves a
  parity-contract requirement. Python research decoder behavior may be cited as
  contrast, but this wave should not make Python smarter.
- Do not edit ratchet baselines, seed registry manifests, projection order, CLI
  manifest views, Claude files, dispatcher/commit/push surfaces, or unrelated
  docs.
- Existing `TypeError` behavior for invalid caller-provided byte container shape
  remains out of scope unless Phase A proves it is part of the same MuBinary
  payload taxonomy.
- Do not treat `TASKS.md` authorization as proof that every listed work item is
  unlanded; current code truth wins over stale packet wording.

## Stop Conditions

- Stop if Phase A cannot bind the exact write set and proof limits.
- Stop if the fix would require a new host semantic layer, production binary
  loading, seed migration, registry authority, or ratchet-baseline change.
- Stop if the malformed UTF-8 failure cannot be reproduced locally before the
  implementation change.
- Stop if current code already proves the malformed UTF-8 case returns
  `MuBinaryDecodeError`; remove that item from pending work and acceptance
  instead of re-listing it as unresolved.
- Stop if a broader binary/TLV migration or D010 production-readiness decision
  is needed; that belongs in a later bounded packet.

## Acceptance Criteria

- Phase A locks the exact source write set and proof limits before Phase B.
- The packet cites `TASKS.md:548-552` for current `[NEXT-CODEX-POST-REDTEAM]`
  authorization and `TASKS.md:556` for the packet-plus-tracker requirement.
- The same-wave `FOUNDER_OVERRIDE:n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18`
  remains present so commit automation can derive wave-bound authority.
- Malformed UTF-8 binary string payloads remain rejected and surface as
  `MuBinaryDecodeError` from the JS MuBinary sidecar decoder.
- Production JSON seed loading remains the default / rollback path and the
  sidecar decoder remains out of production loader authority.
- Focused validation passes:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py::TestProjectionLoaderBinaryDecoderParity --tb=short`
- Production boundary lock passes:
  `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py::TestJsSeedLoaderBinaryDecoderSidecarLock::test_binary_decoder_sidecar_not_production_loader --tb=short`
- Ratchets pass:
  `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  `python3 tools/checks/check_host_authority_inventory_ratchet.py`
- L4 contract passes after staging:
  `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18 --wave-class L4_STRUCTURAL`

## Grounding / Authorization

- `TASKS.md:548-552` authorizes the current `[NEXT-CODEX-POST-REDTEAM]` queue:
  it is unparked, founder-authorized, and open for remaining bounded structural
  reduction after already-landed structural slices. The same lines warn that
  already-landed engine-state/scheduler seed, fixture, structural-test,
  scheduler-parity, and seed-registration work must not be relisted as
  unresolved.
- `TASKS.md:556` governs execution for the active founder-ordered redteam wave
  queue: proceed through dispatcher/pipeline, organize remediation by category
  and severity, put `/mu` structural remediation last, hard stop before
  implementation where required, and ensure every wave has both a control-plane
  packet and a `TASKS.md` tracker entry.
- `reports/control_plane/n3-active-residue-closeout-or-next-map-2026-05-14.md:155-161`
  retains only the projection-loader / JS binary decoder error-taxonomy surface
  from generated N3 bridge residue and requires a successor packet to lock exact
  write set, parity proof, ratchets, rollback path, and proof limits.
- `reports/deferred/non_blocking/n3-projection-loader-js-binary-decoder-parity-2026-05-14_bridge_nonblockers.md:16-21`
  records the active deferred finding: malformed binary UTF-8 currently fails
  closed as `TypeError` rather than `MuBinaryDecodeError`.
- Current packet authority is this file:
  `reports/control_plane/n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18.md`.
- Same-wave override:
  `Authorization: FOUNDER_OVERRIDE:n3-projection-loader-js-utf8-decode-error-taxonomy-2026-05-18`.
- Phase A evidence identified the pre-implementation JS source surface at
  `mu/host/js/core/seed_loader.js:330-337` and recorded the reproduced malformed
  UTF-8 failure:
  `node -e "const {decodeMuBinaryValue}=require('./mu/host/js/core/seed_loader'); try { decodeMuBinaryValue(Buffer.from([0x05,0,0,0,1,0xff])); console.log(JSON.stringify({ok:true})); } catch (e) { console.log(JSON.stringify({ok:false, name:e.name, error:e.message})); }"`
  prints `{"ok":false,"name":"TypeError","error":"The encoded data was not valid for encoding utf-8"}`.
- Phase B implementation evidence identifies the current JS source surface at
  `mu/host/js/core/seed_loader.js:330-344`; the same malformed UTF-8 probe now
  prints `{"ok":false,"name":"MuBinaryDecodeError","error":"Malformed UTF-8 string at offset 0: The encoded data was not valid for encoding utf-8"}`.
