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

Current active inventory (synced 2026-03-30):

- `non_blocking/redteam_2026-03-09_wave1.md`
- `non_blocking/redteam_2026-03-09_wave2.md`
- `non_blocking/redteam_2026-03-09_wave3.md`
- `non_blocking/redteam_2026-03-09_wave4a.md`
- `non_blocking/redteam_2026-03-10_wave4e.md`
- `non_blocking/redteam_2026-03-14_repo_non_blockers.md`
- `non_blocking/repo_truth_non_blockers_2026-03-14.md`
- `non_blocking/native_agent_test_findings_2026-03-11.md`
- `non_blocking/wave-i-non-blocking-findings_2026-03-09.md`
- `non_blocking/hook_soft_gate_residue.md`
- `non_blocking/w5a_reentry_gate_coverage.md`
- `non_blocking/commit_pipeline_automation_plan_2026-03-22_bridge_nonblockers.md`
- `non_blocking/commit_pipeline_bridge_r1_findings_2026-03-23.md`
- `non_blocking/commit_pipeline_hardening_2026-03-23.md`
- `non_blocking/deferred-cleanup-2026-03-29_bridge_nonblockers.md`
- `non_blocking/deferred-nonpipeline-fixes-2026-03-29_bridge_nonblockers.md`
