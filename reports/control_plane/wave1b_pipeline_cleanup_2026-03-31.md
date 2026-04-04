# Wave 1B: Pipeline Cleanup (MEDIUM + LOW)

**Status:** IN PROGRESS (observability slice landed 2026-04-02; remaining items still queued)
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

### E1. [P2] ~~BRIDGE_ZERO_OUTPUT_TIMEOUT_S 1200→450s~~ **LANDED 2026-04-02**
### E2. [LOW] ~~Zero-output watchdog timing mismatch~~ **LANDED 2026-04-02**
### E3. [LOW] ~~Timeout override parser reject NaN/Inf~~ **LANDED 2026-04-02**
### E4. [LOW] ~~Dashboard pre-commit vs post-merge classification~~ **LANDED 2026-04-02**
### E5. [LOW] jq last(3) dead logic + terminal escape sanitization
### E6. [LOW] PR number numeric validation in gh API path
### E7. [LOW] ~~Hook test vacuous-pass guards~~ **LANDED 2026-04-02**
### E8. [LOW] ~~Phase B executor gitignore comment fix~~ **LANDED 2026-04-02**

---

## Progress Notes

### 2026-04-02 — Observability hardening slice

- Landed `bridge_supervisor.py` timeout hardening so reviewer zero-output watchdog defaults to 450s, stays strictly inside the active turn budget, and rejects non-finite env overrides instead of accepting `NaN` / `Inf`.
- Landed dashboard phase detection updates so `meta_bridge_supervisor.py` is classified as `commit` in pre-commit mode and `post-merge` only when `--mode post-merge` is actually present.
- Landed rendered-transcript fallback parsing in `pipeline_dashboard.py`, `pipeline_dashboard_web.py`, and `_pane_findings.sh`, so Codex raw JSON transcripts no longer leave old reviewer rounds stuck as false `In progress...`.
- Landed the two low-risk hygiene fixes from the packet: hook-test vacuous-pass guards removed, and the stale Phase B gitignore comment corrected.
- Remaining open from Wave 1B after this slice: Cluster C items, Cluster D items, and E5-E6.
- Adjacent fix pulled in because it reproduced live in tmux: the findings pane now accepts reviewer markdown transcripts in addition to envelope JSON artifacts.

---

## Acceptance Criteria

- [ ] All C/D/E items addressed or explicitly deferred with rationale
- [ ] All existing tests pass (`audit_fast.sh`)
