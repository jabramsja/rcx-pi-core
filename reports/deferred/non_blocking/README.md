# Deferred Non-Blocking

Use this folder for active founder-facing advisory audits and unresolved
non-blocking residue that still matters, but does not currently block runtime
integrity or truthful promotion claims.

Generated `*_bridge_nonblockers.md` records should remain here only when they
still carry a current, file-line-grounded advisory finding. A retained advisory
file does not reopen a parent task that `TASKS.md` marks closed, and it does not
relist landed work as unresolved unless the file itself records current evidence.

Status convention:

- Active advisory packets must carry an unresolved `Status:` value and current
  file-line-grounded evidence.
- Resolved packets belong under `reports/archive/deferred/` unless a narrow
  retained section still carries an active advisory.

Archived source snapshots for extracted non-blocking residue live in:

- `reports/archive/deferred/`
- `reports/codex/Archive/non_blockers/`

2026-05-04 sweep note:

- `deferred-findings-fix-sweep-2026-05-04` moved code-closed/stale generated
  advisory packets out of this active lane. The remaining markdown files are
  active advisories or retained follow-ups with current evidence targets.

2026-05-05 repo-code audit note:

- `founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md` records
  the non-blocking proof-class mismatch from
  `founder-ordered-redteam-repo-code-audit-2026-05-05`: JS ontology evidence
  collection source-locks/registers `evidence_walker.v1.json` but still drains
  runtime traces with host code.

2026-05-06 cleanup note:

- Evidence command:
  `find reports/deferred/non_blocking -maxdepth 1 -type f -name "*.md" -print | sort`.
- Inventory after the first 2026-05-06 cleanup: 30 markdown files, including
  this README and 29 active or partially active advisory packets.
- Whole-file archives moved 12 closed, stale, or historical packets to
  `reports/archive/deferred/` with `closed-by-deferred-non-blocking-cleanup-2026-05-06`,
  `historical-by-deferred-non-blocking-cleanup-2026-05-06`, or source-wave
  closure suffixes.
- Partial splits moved closed sections from:
  `recovery-gate-wiring-2026-03-31_bridge_nonblockers.md`,
  `pipeline-recovery-phase1-2026-03-31_bridge_nonblockers.md`,
  `redteam_2026-03-14_repo_non_blockers.md`,
  `repo_truth_non_blockers_2026-03-14.md`, and
  `plan-learning-store-enforcement-2026-04-08-2026-04-08_bridge_nonblockers.md`.
- `hook_soft_gate_residue.md` and the Claude-referencing resolved sections
  retained in `redteam_2026-03-14_repo_non_blockers.md` and
  `repo_truth_non_blockers_2026-03-14.md` were not extracted because they are
  Claude-related residue outside this cleanup authorization.

2026-05-06 retained-residue cleanup note:

- Evidence command:
  `find reports/deferred/non_blocking -maxdepth 1 -type f -name "*.md" -print | sort | nl -ba`.
- Current post-bridge inventory after retained-residue cleanup and the routed
  docs-root/mu-docs retained-candidate follow-up: 32 markdown
  files, including this README and 31 active or partially active advisory
  packets.
- Whole-file archive:
  `reports/archive/deferred/pager-deterministic-session-2026-04-18_bridge_nonblockers_closed-by-deferred-non-blocking-retained-residue-cleanup-2026-05-06.md`.
- Partial closed-section extraction:
  `reports/archive/deferred/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers_partial-closed-by-deferred-non-blocking-retained-residue-cleanup-2026-05-06.md`.
- Bridge Round 1 generated and retained
  `deferred-non-blocking-retained-residue-cleanup-2026-05-06_bridge_nonblockers.md`
  as this wave's active non-blocking follow-up packet.
- The routed retained-candidate follow-up generated and retained
  `docs-root-mu-docs-retained-packet-cleanup-2026-05-06_bridge_nonblockers.md`
  as the active advisory packet for post-Bridge findings in that routed cleanup.
- Claude-related retained residue was left untouched.
