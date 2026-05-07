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

2026-05-07 root/mu-docs audit closeout note:

- Evidence command:
  `find reports/deferred/non_blocking -maxdepth 1 -type f -name "*.md" -print | sort | nl -ba`.
- Current inventory after retained-residue cleanup, the routed
  docs-root/mu-docs retained-candidate follow-up,
  `docs-root-mu-docs-audit-closeout-2026-05-07`, and the 2026-05-07
	  deferred folder cleanup: 28 markdown files, including this README and 27
	  active or partially active advisory packets.
- Whole-file archive:
  `reports/archive/deferred/pager-deterministic-session-2026-04-18_bridge_nonblockers_closed-by-deferred-non-blocking-retained-residue-cleanup-2026-05-06.md`.
- Partial closed-section extraction:
  `reports/archive/deferred/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers_partial-closed-by-deferred-non-blocking-retained-residue-cleanup-2026-05-06.md`.
- Bridge Round 1 generated
  `deferred-non-blocking-retained-residue-cleanup-2026-05-06_bridge_nonblockers.md`;
  the 2026-05-07 non-blocking folder cleanup archived it to
  `reports/archive/deferred/deferred-non-blocking-retained-residue-cleanup-2026-05-06_bridge_nonblockers_closed-by-non-blocking-folder-cleanup-2026-05-07.md`
  after confirming the only finding targeted an archive-only closure snapshot.
- The routed retained-candidate follow-up generated a duplicate-tracker advisory;
  `docs-root-mu-docs-audit-closeout-2026-05-07` resolved the duplicate
  same-wave tracker note and moved that advisory to
  `reports/archive/deferred/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_bridge_nonblockers_closed-by-docs-root-mu-docs-audit-closeout-2026-05-07.md`.
- `docs-root-mu-docs-audit-closeout-2026-05-07_non_blocking.md` remains active
  with one DOC_ACCURACY advisory for stale pre-S1 no-production-reduction
  wording in active L4 G8 docs.
- The generated `docs-root-mu-docs-audit-closeout-2026-05-07` bridge packet was
  archived to
  `reports/archive/deferred/docs-root-mu-docs-audit-closeout-2026-05-07_bridge_nonblockers_closed-by-non-blocking-folder-cleanup-2026-05-07.md`
  after the active README wording finding was closed and the TASKS line-citation
  finding no longer reproduced against current tracker lines.
- The 2026-05-07 deferred folder cleanup archived the generated tests/tooling
  remediation bridge packets after patching their stale implemented-status,
  standalone receipt wording, and audit-wrapper syntax-check findings:
  `reports/archive/deferred/founder-ordered-redteam-tests-non-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-deferred-folder-cleanup-2026-05-07.md`,
  `reports/archive/deferred/founder-ordered-redteam-tooling-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-deferred-folder-cleanup-2026-05-07.md`,
  and
  `reports/archive/deferred/founder-ordered-redteam-tooling-non-blocking-remediation-2026-05-06_bridge_nonblockers_closed-by-deferred-folder-cleanup-2026-05-07.md`.
- Claude-related retained residue was left untouched.

2026-05-07 deferred non-`/mu` truth sweep note:

- Evidence command:
  `find reports/deferred/blocking reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' ! -name README.md -print | sort`.
- Current non-blocking inventory after routing/archive cleanup: `README.md` plus
  three active `/mu` structural advisory packets:
  `founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`,
  `redteam_2026-03-14_repo_non_blockers.md`, and
  `repo_truth_non_blockers_2026-03-14.md`.
- Routed non-`/mu` source packets were moved to `reports/archive/deferred/` with
  same-wave `routed-by` suffixes, and remaining work is tracked by the bounded
  control-plane packets for docs/control-plane, tooling/control-plane, and
  tests/proof-integrity remediation.
- `w5a_reentry_gate_coverage.md` was archived as closed by current direct test
  evidence in `mu/tests/l4_gates/test_boot1_step_monotonicity_gate.py`.
- Claude-related files were not edited.
