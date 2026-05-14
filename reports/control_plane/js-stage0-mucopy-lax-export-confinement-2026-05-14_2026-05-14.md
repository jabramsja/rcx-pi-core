# Js-Stage0-Mucopy-Lax-Export-Confinement-2026-05-14

Date: 2026-05-14
Status: IMPLEMENTED / PR #949 MERGED
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: js-stage0-mucopy-lax-export-confinement-2026-05-14
Class: L4_STRUCTURAL
target_gate_id: G8
workload_target: host_debt_reduction
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:js-stage0-mucopy-lax-export-confinement-2026-05-14
Authorization: same-wave packet-local Phase A authorization for js-stage0-mucopy-lax-export-confinement-2026-05-14, grounded in TASKS.md:332 and the governing N3 source-boundary packet selection below.
Purpose: Record the selected N3 successor slice and its completed Phase B outcome: a bounded JS Stage0 public export confinement that prevents externally reachable `muCopy` from entering lax `rejectNonMu=false` mode, while preserving private/internal lax copying needed by VM-owned bundle/capture template materialization.

Phase B / PR #949 completion truth (2026-05-14): PR #949 completed and merged this implementation, with closure provenance recorded by remediation commit `05942b62` in the follow-up bridge closeout packet. Historical Phase A planning text below is retained as provenance only; it no longer means this packet is a packet-rewrite-only turn or that implementation edits remain pending.

## Scope

Historical Phase A packet rewrite scope:

- `reports/control_plane/js-stage0-mucopy-lax-export-confinement-2026-05-14_2026-05-14.md` only.

Read-only grounding scope used for this Phase A repair:

- `TASKS.md:332`.
- `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md:74` through `:148`.
- `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md:149` through `:182`.
- `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md:187` through `:224`.

Completed Phase B implementation write set from PR #949:

- `mu/host/js/core/stage0_vm.js`
- `mu/tests/l4_gates/test_stage0_vm.py`
- `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
- Generated control-plane packet/tracker/indicator surfaces required by the dispatcher and commit executor for this same wave.

The Phase B slice is limited to the exported JS Stage0 copy boundary. It may not widen to unrelated runtime, seed, scheduler, registry, production `/mu`, host-oracle, or Claude-related work.

## Work items

The list below is the historical Phase A implementation plan. PR #949 completed
this Phase B package; these items are retained to preserve the accepted write set,
proof limits, and validation contract.

1. Re-check current code truth before implementation, limited to the locked Phase B write set, to confirm that the public exported JS Stage0 `muCopy` lax path is still open. If it is already closed, stop and record no-slice closure evidence instead of inventing adjacent work.
2. In `mu/host/js/core/stage0_vm.js`, split, wrap, or otherwise confine the public export so externally reachable `muCopy` cannot call the helper in lax `rejectNonMu=false` mode.
3. Preserve the private/internal lax copy path only where the VM already owns the bundle/capture template materialization context. This is a host-surface reduction, not a change to Mu semantics.
4. Keep legitimate strict parse-tree ingress intact. The governing packet records checked ingress using `muCopy(..., true, ...)` from seed/API fixture paths; this wave must not require edits to `seed_loader.js` or `cli/main.js`.
5. In `mu/tests/l4_gates/test_stage0_vm.py`, replace the public lax-completion expectation for hostile proxy/revoked-proxy cases with a fail-closed exported-boundary expectation, while keeping the existing strict `rejectNonMu=true` host-trap proof.
6. In `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`, source-lock the JS Stage0 VM public copy export so future edits cannot re-expose lax public copy, a new public trust mutator, or a public copy/constructor laundering path.
7. Do not relist predecessor work as pending. The strict `muCopy(..., rejectNonMu=true)` host-trap repair and predecessor dispatcher/package repair remain predecessor evidence only, as represented by `TASKS.md:328`, `TASKS.md:329`, `TASKS.md:331`, and the governing packet.
8. Validate the accepted Phase B package with the focused tests and ratchets listed under Acceptance criteria, then bind the package to same-wave control-plane/tracker/indicator evidence through the dispatcher/commit executor surfaces.

## Constraints

The constraints below governed the historical Phase A-to-Phase B implementation
handoff. After PR #949, the only active follow-up work is the bounded
docs/control-plane bridge closeout tracked by
`js-stage0-mucopy-bridge-nonblocker-closeout-2026-05-14`.

- Historical Phase A packet-rewrite guard: before Phase B acceptance, this packet did not authorize implementation edits. That guard is now provenance only after PR #949 completion.
- Do not edit files outside the locked Phase B write set unless a dispatcher/commit-executor generated control-plane, tracker, or indicator surface is required for this same wave after implementation.
- Do not edit Claude-related files, Claude home files, `.claude/`, or Claude-specific run surfaces.
- Do not add semantic host debt, host-only oracles, public trust mutators, public constructor laundering paths, or new Python/JavaScript authority sites.
- Do not move Mu semantic decisions into Python or JavaScript host code. The intended change shrinks public JS host-boundary accessibility only.
- Do not change Stage0 opcode semantics, seed semantics, kernel dispatch, scheduler behavior, registry behavior, or Python runtime behavior.
- Do not update ratchet baselines as proof for this slice.
- Do not claim this slice closes the retained N3 broad host-surface advisory. At most, it closes one public JS host-copy boundary.

## Stop conditions

- Stop if current code truth proves the public exported JS Stage0 lax `muCopy` boundary is already closed.
- Stop if a viable fix requires edits outside the locked Phase B write set, except for same-wave generated control-plane/tracker/indicator surfaces.
- Stop if preserving strict checksum/API fixture ingress would require editing `seed_loader.js`, `cli/main.js`, or other source files outside the locked write set.
- Stop if the fix would add host-only semantics, new host authority, a host oracle, public trust mutation, or public constructor/copy laundering.
- Stop if Python/JS parity for semantically shared Stage0 VM stepping cannot be preserved.
- Stop if the needed change would alter Stage0 opcode semantics, seed semantics, kernel dispatch, scheduler behavior, registry behavior, production `/mu` scope, or any unrelated retained deferred advisory.

## Acceptance criteria

The criteria below describe the accepted Phase B contract and the completed PR
#949 implementation truth; they are not current pending work for this packet.

- This packet is no longer a request echo and contains detector-visible `Scope`, `Work items`, `Constraints`, `Stop conditions`, `Acceptance criteria`, and `Grounding / Authorization` sections.
- The packet carries a same-wave authorization marker: `FOUNDER_OVERRIDE:js-stage0-mucopy-lax-export-confinement-2026-05-14`.
- Historical pending work was exactly one bounded `/mu` structural host-surface reduction candidate: JS Stage0 exported `muCopy` lax-mode confinement. That candidate is complete in PR #949.
- The locked Phase B write set is limited to `mu/host/js/core/stage0_vm.js`, `mu/tests/l4_gates/test_stage0_vm.py`, `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`, and same-wave generated control-plane/tracker/indicator surfaces required by the dispatcher/commit executor.
- The exported JS Stage0 copy surface fails closed for externally reachable lax use and cannot be used to copy raw host/proxy values through public `rejectNonMu=false` access.
- Private/internal lax copying needed by VM-owned bundle/capture template materialization still works without adding public trust/copy authority.
- Existing strict `muCopy(..., true, ...)` checksum/API parse-tree ingress remains valid without widening the write set.
- Focused validation for implementation included the Phase B contract below:

```bash
PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/l4_gates/test_stage0_vm.py::TestCapturePathProvenance mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py::TestJsSourceLock --tb=short -p no:cacheprovider
node mu/host/js/eval_step.js
python3 mu/tools/checks/check_host_semantics_ratchet.py --json
python3 tools/checks/check_host_authority_inventory_ratchet.py
./tools/checks/check_docs_consistency.sh
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id js-stage0-mucopy-lax-export-confinement-2026-05-14
python3 tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD --wave-id js-stage0-mucopy-lax-export-confinement-2026-05-14
```

- Host-semantics ratchet must not increase, host-authority inventory must not add total-inventory or authority-subset sites, and no ratchet baseline update may be used as evidence for this wave.
- The final implementation evidence must state proof limits: this slice reduces one JS public host-copy boundary only and does not prove full N3 closure.

## Grounding / Authorization

- Governing packet for this wave after this rewrite:
  `reports/control_plane/js-stage0-mucopy-lax-export-confinement-2026-05-14_2026-05-14.md`
- Task: `[NEXT-CODEX-POST-REDTEAM]`
- Wave ID: `js-stage0-mucopy-lax-export-confinement-2026-05-14`
- Same-wave packet marker:
  `FOUNDER_OVERRIDE:js-stage0-mucopy-lax-export-confinement-2026-05-14`
- Phase B / PR #949 completion: `TASKS.md:333` records the commit-ready Phase B
  handoff for this wave, including the two focused L4 gate test files and the
  same-wave indicator artifact. The follow-up bridge closeout packet records the
  source-lock finding as already closed by merged PR #949 remediation commit
  `05942b62`; the only remaining closeout residue was DOC_ACCURACY wording in
  this packet.
- TASKS authorization: `TASKS.md:332` records the predecessor `broad-host-surface-n3-source-boundary-slice-2026-05-14` L4_ENABLER package for `[NEXT-CODEX-POST-REDTEAM]`, with same-wave `FOUNDER_OVERRIDE:broad-host-surface-n3-source-boundary-slice-2026-05-14`, and points to `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md` as the converged source-boundary packet.
- Governing predecessor selection: `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md:74` through `:83` selects **JS Stage0 exported `muCopy` lax-mode confinement** and records the source/test evidence for the public lax export.
- Governing predecessor write set and expected artifacts: `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md:95` through `:112` locks the proposed Phase B files and expected structural test surfaces.
- Governing predecessor validation, parity, and proof limits: `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md:114` through `:148` lists focused validation, ratchet obligations, and the limit that this candidate reduces one JS public host-copy boundary without closing N3.
- Governing predecessor constraints and stops: `reports/control_plane/broad-host-surface-n3-source-boundary-slice-2026-05-14_2026-05-14.md:149` through `:182` forbid Claude edits, host-oracle work, semantic host debt, already-landed predecessor relisting, and write-set widening without stopping.
- This rewrite did not inspect downstream implementation files beyond the cited governing evidence. Phase B must prefer current code truth over this packet if the locked-write-set re-check proves the selected public lax export is already closed.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Completed Phase B Indicator Scope Reconciliation

- Refresh wave: `js-stage0-mucopy-lax-export-confinement-2026-05-14`
- Active packet: `reports/control_plane/js-stage0-mucopy-lax-export-confinement-2026-05-14_2026-05-14.md`
- Indicator artifact: `reports/l4_wave_indicators/js-stage0-mucopy-lax-export-confinement-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- PR #949 staged files at Phase B handoff:
  - `TASKS.md`
  - `mu/host/js/core/stage0_vm.js`
  - `mu/tests/l4_gates/test_stage0_vm.py`
  - `mu/tests/l4_gates/test_stage0_vm_trusted_path_gate.py`
  - `reports/control_plane/js-stage0-mucopy-lax-export-confinement-2026-05-14_2026-05-14.md`
  - `reports/deferred/non_blocking/js-stage0-mucopy-lax-export-confinement-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/js-stage0-mucopy-lax-export-confinement-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
