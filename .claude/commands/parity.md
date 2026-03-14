# /parity — RCX Cross-Substrate Parity Check

Verifies Python and JavaScript substrates produce identical results.

## Steps

1. Run `node mu/host/js/eval_step.js` — JS self-tests (must print "All tests passed: true").

2. Run `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_seed_loading_parity.py -v --timeout=60` — verify seed loading parity (checksums, projection IDs, ordering).

3. Run `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_cross_substrate_constants.py -v --timeout=60` — verify constants parity (MAX_MU_DEPTH, reserved fields, fuel defaults).

4. Run `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_step_mu_parity.py -v --timeout=60` — verify step_mu behavioral parity.

5. If all above pass and deeper check desired, run: `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/ -x -q --timeout=120` — full parity suite.

## Output Format

```
PARITY CHECK
JS self-tests: <pass/fail>
Seed loading: <pass/fail> (<n> tests)
Constants: <pass/fail> (<n> tests)
Step parity: <pass/fail> (<n> tests)
Overall: <CLEAN / DIVERGENCE DETECTED>
```

If divergence detected, identify the specific test, substrate, and divergent behavior.
