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

Current inventory refresh (2026-05-05):

- Evidence command: `rg --files reports/deferred/blocking reports/deferred/non_blocking | sort | nl -ba`.
- `reports/deferred/blocking/` contains `README.md` plus the active repo-code
  blocker packet
  `founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`.
- The resolved mu preproduction gate-theater blocker was moved to
  `reports/archive/deferred/mu_preproduction_gate_theater_blocker_2026-05-04_closed-by-mu-preproduction-theater-ratchet-resolution-2026-05-05.md`.
  The 2026-05-05 follow-up aligns the redteam startup guard with the curated
  theater-risk ratchet; `/mu` production-forward movement is no longer blocked
  by this gate-theater finding.
- `reports/deferred/non_blocking/` currently contains 33 markdown files:
  `README.md` plus 32 retained advisory/follow-up records with concrete
  evidence targets, including
  `founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`,
  reproduced with
  `find reports/deferred/non_blocking -maxdepth 1 -type f -name "*.md" -print | sort | nl -ba`.
- The deferred findings sweep archived 6 stale, self-closed, or code-closed
  generated advisory packets under `reports/archive/deferred/` with
  `closed-by-deferred-findings-fix-sweep-2026-05-04` filenames.

Closed-parent exclusions for this index:

- The current `TASKS.md` NEXT code-truth reconciliation note marks
  `[PIPELINE-AGENT-PAGER]`, `[PARALLEL-PIPELINE]`, and
  `[DEFERRED-CONSOLIDATION]` as closed by code and says old in-progress prose is
  historical unless the current section marks the item open.
- The current `TASKS.md` `[NEXT-CODEX-POST-REDTEAM]` entry keeps that queue open
  only for future bounded structural work and excludes the landed PR #701 Phase A
  artifacts plus the landed
  `post-redteam-engine-state-scheduler-reduction-2026-04-30` seed, fixture,
  structural-test, scheduler-parity, and seed-registration items from unresolved
  work.
- The current `TASKS.md` `[PARALLEL-PIPELINE]` closed tracker entry records bus
  namespacing, monitor identity, Tier 2 transient-kill retry, and agent-team work
  as landed or satisfied.

Historical/generated advisory records retained in `non_blocking/` therefore do
not relist PR #701, the engine-state/scheduler slice, `PIPELINE-AGENT-PAGER`,
`PARALLEL-PIPELINE`, or `DEFERRED-CONSOLIDATION` as active unresolved work.

Mu preproduction blocker note (2026-05-05):

- `reports/archive/deferred/mu_preproduction_gate_theater_blocker_2026-05-04_closed-by-mu-preproduction-theater-ratchet-resolution-2026-05-05.md`
  was opened by the mu preproduction red-team stop condition, resolved by the
  bounded ratchet follow-up, and archived by this closeout. The raw strict
  checker still reports 85 `theater_risk` methods, but
  `check_theater_risk_ratchet.py` proves they are all current, non-expired
  curated false positives and will fail on new, expired, or `real` findings. It
  is not part of the earlier deferred-findings sweep inventory and does not
  reopen archived or landed parent-queue work.
