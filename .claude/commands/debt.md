# /debt — RCX Debt Dashboard + Truth Check

Shows current host debt state and verifies STATUS.md matches reality.

## Steps

1. Run `bash tools/util/debt_dashboard.sh` — show current debt counts by category.

2. Run `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` — get tracked marker breakdown.

3. Run `python3 tools/checks/check_host_authority_inventory_ratchet.py` — get authority inventory.

4. Read STATUS.md debt section (lines around "THRESHOLD", "CURRENT", "FLOOR") — extract claimed values.

5. Run `PYTHONHASHSEED=0 python3 -m pytest mu/tests/docs/test_debt_truth_gate.py -q` — verify gate test passes.

6. Cross-check: Do the claimed values in STATUS.md match what the tools report?

## Output Format

```
DEBT STATUS
Tracked markers: <n>/<threshold> (<breakdown>)
Authority sites: <n>/<baseline>
Total inventory: <n>/<baseline>
STATUS.md truth: <consistent/DRIFT DETECTED>
Truth gate: <pass/fail>
```

If any drift detected, show exactly what STATUS.md claims vs what tools report, with line numbers.
