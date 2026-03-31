# Wave 1B: Pipeline Cleanup (MEDIUM + LOW)

**Status:** QUEUED (run after Wave 1A merges)
**Task:** NEXT-CODEX-POST-REDTEAM deferred cleanup
**Surface:** `mu/tools/executors/`, `mu/tools/agents/`, `mu/tools/checks/`, `mu/tools/observability/`, `mu/tools/hooks/`
**Classification:** MAINTENANCE (hardening, no runtime dirs)
**Scope:** 18 items — Clusters C (6 wiring) + D (4 executor) + E (8 observability)
**Source:** `reports/deferred/non_blocking/wave1_pipeline_consolidated_2026-03-31.md`

---

## Cluster C — Control Surface Wiring (6 items)

### C1. [MEDIUM] Wire closeout attestation into pre-commit hook or commit_executor
### C2. [MEDIUM] Wire control surface invariant checker into pipeline
### C3. [MEDIUM] INV-2 checker spoofable by dummy if-branches — structural validation
### C4. [MEDIUM] Bridge adapter hardcoded review mode audit
### C5. [MEDIUM] meta_bridge_client envelope schema validation
### C6. [LOW] Add executor_config.json to control-surface detection set

## Cluster D — Executor Logic (4 items)

### D1. [MEDIUM] Dialectic executor max_rounds — implement or remove dead config
### D2. [MEDIUM] Phase B re-entry refresh propagate deferred packet paths
### D3. [MEDIUM] Phase B classification logs to stderr not stdout
### D4. [MEDIUM] Dispatcher retry surface regression tests

## Cluster E — Observability / Hooks (8 items)

### E1. [P2] BRIDGE_ZERO_OUTPUT_TIMEOUT_S 1200→450s
### E2. [LOW] Zero-output watchdog timing mismatch
### E3. [LOW] Timeout override parser reject NaN/Inf
### E4. [LOW] Dashboard pre-commit vs post-merge classification
### E5. [LOW] jq last(3) dead logic + terminal escape sanitization
### E6. [LOW] PR number numeric validation in gh API path
### E7. [LOW] Hook test vacuous-pass guards
### E8. [LOW] Phase B executor gitignore comment fix

---

## Acceptance Criteria

- [ ] All C/D/E items addressed or explicitly deferred with rationale
- [ ] All existing tests pass (`audit_fast.sh`)
