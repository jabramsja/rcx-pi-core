# Archived Closed Sections: redteam_2026-03-14_repo_non_blockers

Date archived: 2026-05-06
Source packet: `reports/deferred/non_blocking/redteam_2026-03-14_repo_non_blockers.md`
Reason: deferred non-blocking cleanup moved resolved sections out of the active
advisory lane.

## Archived N2: Stage0 Compiled-Bundle Integrity

Original status: `RESOLVED` on 2026-03-15.

Closed-truth evidence:

- `mu/host/python/rcx_pi/selfhost/step_mu.py:777` defines
  `_verify_bundle_provenance`.
- `mu/host/python/rcx_pi/selfhost/step_mu.py:788` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:803` compare bundle
  `source_digest` against `SEED_CHECKSUMS` and fail closed on mismatch.
- `mu/host/js/cli/main.js:284` through `mu/host/js/cli/main.js:304` performs
  the parallel JS provenance check on kernel, bridge, match, and subst bundles.
- `tests/l4_gates/test_stage0_vm_cutover.py:473` through
  `tests/l4_gates/test_stage0_vm_cutover.py:506` proves pass, wrong-digest
  rejection, missing-digest acceptance, and unknown-seed acceptance.
