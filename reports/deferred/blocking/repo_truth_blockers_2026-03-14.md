# Repo Truth Blockers (Active Residue)

Extracted on 2026-03-14 from:

- `reports/codex/Archive/blockers/drift_2026-03-12_repo_redteam_blockers.md`
- `reports/codex/Archive/blockers/redteam_2026-03-14_p7a_p7d_blockers.md`

Archived as stale/resolved from the source snapshots:

- JS public-path `vmConfig` blocker is resolved in the live tree
- the older `11 markers / 269 total / 192 authority` framing is stale as written

## Active Blockers

*None — all blockers resolved as of 2026-03-14.*

## Resolved Blockers

### B1. Canonical host-debt explanation is still internally contradictory — **RESOLVED** (2026-03-14, commit 9be9e1f)

Fix: STATUS.md CURRENT updated 16→20 (all 8 AST_OK bootstrap now included). Baseline JSON `total_ast_ok_bootstrap` 4→8. `check_docs_consistency.sh` now verifies against baseline JSON instead of Python-only dashboard. All composition references fixed. 10/10 debt truth gate tests pass.

Remaining advisory: `debt_dashboard.sh` still computes Python-only totals (8 tracked + 8 AST_OK = 16). This is correct for its scope but differs from cross-substrate total (20). Not blocking — the canonical source is the baseline JSON.

### B2. The repo still does not close the true meta-circular / self-hosting gap — **RESOLVED** (2026-03-14, already honest)

STATUS.md already uses honest language: "NOT self-hosting in the traditional sense" (line 28), "SINK (research question)" (line 23), "No production reduction or elimination claims" (line 191). No overclaiming found. The blocker's own text says "the implementation status is acceptable" — the concern was only about overstating, which STATUS.md does not do.

### B3. JS serviceBoundaryEffect mutates handler result in-place during ontology emission — **RESOLVED** (2026-03-14)

- JS attached `ontology_promotion` directly to handler-returned object at pipeline.js:414. Python copies first at engine_pipeline.py:825 (`result = {**result}`).
- Found by Codex bridge review. Real parity defect.
- Fix: `result = Object.assign(Object.create(null), result)` before mutation.
- JS immutability regression test added (F-44 parity).

### B4. Missing JS F-44 immutability regression test — **RESOLVED** (2026-03-14)

- Python has `test_handler_result_not_mutated_by_emission`. JS had no equivalent.
- Added JS test proving original handler object is not mutated and injected result is a distinct object.
