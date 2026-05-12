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

Current inventory refresh (2026-05-12 Stage0 cleanup bridge doc accuracy closeout):

- Evidence command:
  `find reports/deferred/blocking reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' -print | sort`.
- Current active deferred files:

```text
reports/deferred/blocking/README.md
reports/deferred/non_blocking/README.md
reports/deferred/non_blocking/founder-ordered-redteam-mu-structural-blocking-remediation-2026-05-06_bridge_nonblockers.md
reports/deferred/non_blocking/repo_truth_non_blockers_2026-03-14.md
```

- `reports/deferred/blocking/` currently contains `README.md` only; no active
  blocking deferred packets remain.
- `reports/deferred/non_blocking/` currently contains `README.md` plus two
  active or partially active retained `/mu` structural advisory packets.
- The generated same-wave DOC_ACCURACY bridge residue for
  `stage0-capture-provenance-deferred-cleanup-2026-05-12` is closed and archived
  at
  `reports/archive/deferred/stage0-capture-provenance-deferred-cleanup-2026-05-12_bridge_nonblockers_closed-by-stage0-cleanup-bridge-doc-accuracy-closeout-2026-05-12.md`.
- Retained `/mu` structural advisories remain active and are not implemented by
  this inventory refresh: transparent JS Proxy provenance, N1 VM coverage
  bookkeeping, N3 broad host-surface boundary, and N5 JS pipeline governance.

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
