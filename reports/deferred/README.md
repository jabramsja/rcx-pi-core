# Deferred Reports

This lane holds active deferred-lane audit packets and retained generated
advisory records. Retained records for already-closed parent tasks are historical
unless the current `TASKS.md` NEXT section also marks that parent task open.

Layout:

- `blocking/`: active blocker reports that still matter for repo truth or research integrity
- `non_blocking/`: active advisory residue that is still open but does not block
- new deferred reports should live in `blocking/` or `non_blocking/`
- do not add compatibility symlinks here; update tracker references to the
  canonical file path instead

Archive rule:

- if a whole report is resolved, stale, or mainly historical, its source snapshot
  lives in `reports/archive/deferred/`
- if archive movement is outside the authorized wave scope, the retained active
  copy must be clearly marked historical or closed-parent advisory

Current inventory refresh (2026-05-04):

- Evidence command: `rg --files reports/deferred/blocking reports/deferred/non_blocking | sort | nl -ba`.
- `reports/deferred/blocking/` contains `README.md` plus one active blocker:
  `mu_preproduction_gate_theater_blocker_2026-05-04.md`. `/mu`
  production-forward movement is blocked until the strict theater-risk gate is
  green for the right reason.
- `reports/deferred/non_blocking/` currently contains 29 markdown files:
  `README.md` plus 28 active advisory/follow-up records with concrete evidence
  targets.
- The deferred findings sweep archived 6 stale, self-closed, or code-closed
  generated advisory packets under `reports/archive/deferred/` with
  `closed-by-deferred-findings-fix-sweep-2026-05-04` filenames.

Closed-parent exclusions for this index:

- `TASKS.md:277-283` marks `[PIPELINE-AGENT-PAGER]`,
  `[PARALLEL-PIPELINE]`, and `[DEFERRED-CONSOLIDATION]` as closed by code and
  says old in-progress prose is historical unless the current section marks the
  item open.
- `TASKS.md:385-397` records `[DEFERRED-CONSOLIDATION]` as closed by code,
  keeps `[NEXT-CODEX-POST-REDTEAM]` open only for future bounded structural
  work, and excludes the landed PR #701 Phase A artifacts plus the landed
  `post-redteam-engine-state-scheduler-reduction-2026-04-30` seed, fixture,
  structural-test, scheduler-parity, and seed-registration items from unresolved
  work.
- `TASKS.md:399-403` records `[PARALLEL-PIPELINE]` as closed, with bus
  namespacing, monitor identity, Tier 2 transient-kill retry, and agent-team
  work landed or satisfied.

Historical/generated advisory records retained in `non_blocking/` therefore do
not relist PR #701, the engine-state/scheduler slice, `PIPELINE-AGENT-PAGER`,
`PARALLEL-PIPELINE`, or `DEFERRED-CONSOLIDATION` as active unresolved work.

Mu preproduction blocker note (2026-05-04):

- `reports/deferred/blocking/mu_preproduction_gate_theater_blocker_2026-05-04.md`
  was opened by the mu preproduction red-team stop condition. Phase B now
  enforces `--fail-on-theater` from the redteam startup guard; the packet
  remains active while the 85 strict-gate theater-risk findings are unresolved.
  It is not part of the earlier deferred-findings sweep inventory and does not
  reopen archived or landed parent-queue work.
