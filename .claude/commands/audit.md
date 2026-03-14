# /audit — RCX Smart Audit Runner

Run tests at the appropriate tier. Accepts an argument for tier selection.

## Usage
- `/audit fast` — Core tests only (~3 min). Use during iteration.
- `/audit full` — Core + fuzzer + slow (~5-8 min). Use before push.
- `/audit gate <file>` — Run specific gate test file. Use for targeted validation.
- `/audit parity` — Cross-substrate parity tests only. Use after JS/Python changes.
- `/audit ratchets` — Run both ratchets + debt truth gate. Use after debt changes.

## Steps

### `/audit fast`
Run `./tools/audit_fast.sh` and report results. If any failures, investigate and fix — do NOT dismiss as pre-existing.

### `/audit full`
Run `./tools/audit_all.sh` and report results. This is REQUIRED before push.

### `/audit gate <file>`
Run `PYTHONHASHSEED=0 python3 -m pytest mu/tests/l4_gates/<file> -v --timeout=60`.
If no file specified, list available gate test files: `ls mu/tests/l4_gates/test_*.py`

### `/audit parity`
Run in sequence:
1. `node mu/host/js/eval_step.js` — JS self-tests
2. `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/ -x -q --timeout=120` — cross-substrate tests

### `/audit ratchets`
Run:
1. `python3 mu/tools/checks/check_host_semantics_ratchet.py`
2. `python3 tools/checks/check_host_authority_inventory_ratchet.py`
3. `PYTHONHASHSEED=0 python3 -m pytest mu/tests/docs/test_debt_truth_gate.py -q`
4. `PYTHONHASHSEED=0 python3 -m pytest mu/tests/structural/test_status_md_grounding.py -q`

## Output
Report pass/fail count, any failures with file:line, and suggested fixes. Never dismiss failures.
