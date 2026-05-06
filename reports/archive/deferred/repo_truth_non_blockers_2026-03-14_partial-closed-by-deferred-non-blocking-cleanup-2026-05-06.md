# Archived Closed Sections: repo_truth_non_blockers_2026-03-14

Date archived: 2026-05-06
Source packet: `reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md`
Reason: deferred non-blocking cleanup moved resolved sections out of the active
advisory lane.

## Archived Resolved Sections

- N4. JS locked seed registries still lack a direct subset/diff gate
- N6. Historical report drift still requires date discipline
- N7. Wave indicator artifacts remain thin for deep replay
- N9. `debt_dashboard.sh` scope differs from ratchet scope
- N12. JS `_ALGORITHM_SEED_ALLOWLIST` uses `Object.freeze(Set)`
- N13. `reports/codex/` exempt from docs governance
- N15. Stage0 `source_digest` format-only validation
- N16. `check_gate_behavioral_pairs.py`: module-level test functions unclassified
- N17. `check_gate_behavioral_pairs.py`: positional args accepted silently
- N19. Three-scope debt counting mismatch

## Evidence

- N4: current seed-registry checks cover checksum/projection/status registry
  consistency in `tests/engine/test_seed_registry_consistency.py:39` through
  `tests/engine/test_seed_registry_consistency.py:58`, mirrored under
  `mu/tests/engine/test_seed_registry_consistency.py`.
- N9 and N19: `tools/util/debt_dashboard.sh:220` emits the current scope
  reconciliation section.
- N12: `mu/host/js/engine/pipeline.js:254` uses a null-prototype object for
  `_ALGORITHM_SEED_ALLOWLIST`.
- N13: `tools/session/founder_session_attest.sh:118` through
  `tools/session/founder_session_attest.sh:122` keeps `reports/codex/` as an
  advisory, founder-approved governance exemption rather than a hard failure.
- N15: `mu/host/python/rcx_pi/selfhost/step_mu.py:777` through
  `mu/host/python/rcx_pi/selfhost/step_mu.py:803`,
  `mu/host/js/cli/main.js:284` through `mu/host/js/cli/main.js:304`, and
  `tests/l4_gates/test_stage0_vm_cutover.py:473` through
  `tests/l4_gates/test_stage0_vm_cutover.py:506` prove provenance verification.
- N16 and N17: `tools/checks/check_gate_behavioral_pairs.py:169` scans
  module-level test functions, and `tools/checks/check_gate_behavioral_pairs.py:265`
  rejects positional arguments fail-closed.
