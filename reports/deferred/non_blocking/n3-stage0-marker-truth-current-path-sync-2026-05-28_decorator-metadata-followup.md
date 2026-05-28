# N3 Stage0 Decorator Metadata Follow-Up

Date: 2026-05-28
Status: DEFERRED
Severity: non-blocking
Source wave: n3-stage0-marker-truth-current-path-sync-2026-05-28
Task: [NEXT-CODEX-POST-REDTEAM]
Class needed: L4_STRUCTURAL
FOUNDER_OVERRIDE:n3-stage0-marker-truth-current-path-sync-2026-05-28

## Rationale

The Phase B implementation corrected the non-executable current-path wording in
`eval_seed.py` and added focused L4 evidence proving:

- `step_kernel_mu` cutover does not call `_stage0_match`,
  `_step_trusted`, or `_apply_projection_trusted`.
- `run_engine_pipeline` still reaches `_stage0_match` through
  `_step_trusted` and `_apply_projection_trusted`.

A direct rewrite of the executable `@host_builtin(...)` metadata string on
`_stage0_match` is not valid under the locked `L4_ENABLER` packet: staged L4
contract validation classifies that decorator argument rewrite as executable
runtime diff. The current wave therefore retains the executable marker string
and adds an inline comment plus surrounding current-path comments. A follow-up
packet must either reclassify this as `L4_STRUCTURAL` marker-metadata cleanup or
provide a mechanical contract path for metadata-string-only marker wording
changes without runtime behavior movement.

## Required Follow-Up Scope

- `mu/host/python/rcx_pi/selfhost/eval_seed.py` only, unless the Phase A packet
  proves additional marker-source tests need synchronized wording.
- Correct the executable `@host_builtin(...)` text for `_stage0_match` so it no
  longer says "Sole production path".
- Preserve `_stage0_match` as `@host_builtin` unless a separate current-path
  proof shows the engine/bootstrap trusted-helper path no longer reaches it.
- Preserve host-semantics ratchet counts unless runtime code actually removes
  the engine/bootstrap trusted-helper path.

## Non-Goals

- No Stage0 VM, `step_kernel_mu`, `run_engine_pipeline`, `_step_trusted`,
  `_apply_projection_trusted`, seed, scheduler, registry, loader, JS parity,
  binary/checksum/integrity, dispatcher, commit, push, PR, or Claude-surface
  changes are authorized by this deferred note.
