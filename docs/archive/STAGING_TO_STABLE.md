# Staging → Stable Promotion (RCX-Ω)

This is the operational checklist for promoting RCX-Ω behavior from “staging” to “stable”.

## Definitions
- **Stable**: External contracts are frozen. Changes require intentional versioning and test updates.
- **Staging**: May change without version bumps; used for experimentation.

## Promotion Criteria (must all be true)
1. Pytest is green on clean checkout (no local-only artifacts).
2. CLI surfaces are documented (see RCX_OMEGA_CONTRACTS.md).
3. JSON schema docs exist and are versioned (see schemas/rcx-omega/).
4. Deprecation policy is defined (see below).
5. Changelog entry created for the promotion.

## Deprecation Policy
- Deprecations must be announced in release notes.
- Deprecations must remain supported for at least one MINOR release.
- Removals require a MAJOR release.

## Release Steps
1. Tag current behavior as stable baseline (git tag).
2. Cut a release note:
   - “Contracts frozen”
   - “Schemas published”
   - “No runtime output changes yet” (if applicable)
3. (Optional next) Introduce `schema_version` + `kind` as OPTIONAL fields in producers.
4. Add/update tests to accept the new optional fields (only after step 3 is implemented).

## Guardrails
- Do not change analyze markers:
  - `== Ω analyze ==`
  - `classification:`
  - `converged:`

