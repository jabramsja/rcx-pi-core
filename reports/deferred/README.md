# Deferred Reports

This lane now holds only unresolved residue and active deferred-lane audit
packets.

Layout:

- `blocking/`: active blocker reports that still matter for repo truth or research integrity
- `non_blocking/`: active advisory residue that is still open but does not block
- new deferred reports should live in `blocking/` or `non_blocking/`
- do not add compatibility symlinks here; update tracker references to the
  canonical file path instead

Archive rule:

- if a whole report is resolved, stale, or mainly historical, its source snapshot
  lives in `reports/archive/deferred/`
- the active copy in this lane should contain only still-open residue

Current active inventory (audited 2026-03-31):

Redteam residue (March 2026):
- `non_blocking/redteam_2026-03-09_wave2.md` — branch-prefix coupling, wrapper staleness (low)
- `non_blocking/redteam_2026-03-09_wave3.md` — Hypothesis suppressions/decorators (fuzzer hygiene wave)
- `non_blocking/redteam_2026-03-09_wave4a.md` — Stage0 design decisions, kernel duplication
- `non_blocking/redteam_2026-03-14_repo_non_blockers.md` — Stage0 hostile-leaf gap (design)
- `non_blocking/repo_truth_non_blockers_2026-03-14.md` — VM cutover/JS bridge evidence (future waves)
- `non_blocking/wave-i-non-blocking-findings_2026-03-09.md` — _match_inner duplication (perf risk)

Runtime/gate residue:
- `non_blocking/hook_soft_gate_residue.md` — soft-gate annoyance (quote-split, false positives)
- `non_blocking/w5a_reentry_gate_coverage.md` — gate test missing re-entry exercise

Pipeline/control-surface residue:
- `non_blocking/commit_pipeline_automation_plan_2026-03-22_bridge_nonblockers.md` — 33 doc/comment stale-state items
- `non_blocking/commit_pipeline_bridge_r1_findings_2026-03-23.md` — Phase B validation non-fatal, attestation gaps
- `non_blocking/commit_pipeline_hardening_2026-03-23.md` — 11 hardening items (validators, denylist, timeouts)
- `non_blocking/deferred-cleanup-2026-03-29_bridge_nonblockers.md` — jq bug, PR validation, escape injection (low)
- `non_blocking/deferred-nonpipeline-fixes-2026-03-29_bridge_nonblockers.md` — OSC escapes, doc mismatches (low)
- `non_blocking/next-codex-post-redteam-phase-a-structural-gap-swe-2026-03-30_bridge_nonblockers.md` — retry coverage, timeout parser, self-referential meta-finding

Archived (2026-03-31):
- `redteam_2026-03-09_wave1.md` → `reports/archive/deferred/` (all resolved/design-locked)
- `redteam_2026-03-10_wave4e.md` → `reports/archive/deferred/` (collected_at fixed, JS-only intentional)
- `native_agent_test_findings_2026-03-11.md` → `reports/archive/deferred/` (markers added, architecture mitigations)
