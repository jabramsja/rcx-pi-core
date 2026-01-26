# RCX-Ω Stable Baseline: Release/Tag Checklist

Purpose: Promote a known-green behavior set to a “stable baseline” WITHOUT changing runtime output.

## Preconditions (must be true)
- Pytest is green on a clean checkout.
- `docs/RCX_OMEGA_CONTRACTS.md` accurately reflects CURRENT runtime behavior.
- Schemas exist and are OPTIONAL-only (no new requirements).
- No CLI marker strings changed:
  - analyze ALWAYS includes `== Ω analyze ==`
  - omega-summary analysis includes `classification:`
  - trace analysis includes `converged:`

## Steps (operator checklist)
1) Verify tests:
   - `python3 -m pytest -q`
2) Verify docs match reality:
   - Confirm `docs/RCX_OMEGA_CONTRACTS.md` does NOT require `kind` or `schema_version`.
   - Confirm any mention of `kind=omega_summary` is labeled FUTURE TARGET, not a requirement.
3) Create a baseline tag (example convention):
   - `rcx-omega-stable-baseline-YYYYMMDD`
4) Create release notes (minimal):
   - “Contracts frozen”
   - “Schemas published (optional)”
   - “No runtime changes”
5) Archive the release artifact if applicable (optional but recommended).

## Postconditions
- A tag/release exists that corresponds to a known-green commit.
- The frozen contract doc matches that commit’s runtime behavior.

