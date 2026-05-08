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

Current inventory refresh (2026-05-08 generated bridge closure):

- Evidence commands:
  `find reports/deferred/blocking reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' ! -name README.md -print | sort`.
- `reports/deferred/blocking/` currently contains `README.md` plus one active
  blocker packet:
  `founder_ordered_redteam_repo_code_audit_2026-05-05_blocking.md`. The packet
  remains a `/mu` structural hard stop; this inventory refresh documents status
  only and does not route or implement `/mu` structural remediation.
- The resolved mu preproduction gate-theater blocker was moved to
  `reports/archive/deferred/mu_preproduction_gate_theater_blocker_2026-05-04_closed-by-mu-preproduction-theater-ratchet-resolution-2026-05-05.md`.
  The 2026-05-05 follow-up aligns the redteam startup guard with the curated
  theater-risk ratchet; `/mu` production-forward movement is no longer blocked
  by this gate-theater finding.
- `reports/deferred/non_blocking/` currently contains `README.md` plus three
  active or partially active `/mu` structural advisory packets:
  `founder_ordered_redteam_repo_code_audit_2026-05-05_non_blocking.md`,
  `redteam_2026-03-14_repo_non_blockers.md`, and
  `repo_truth_non_blockers_2026-03-14.md`.
- The 2026-05-08 generated bridge closure archived the three active generated
  non-`/mu` bridge packets under `reports/archive/deferred/` with
  `_closed-by-deferred-non-mu-generated-bridge-closure-observability-parser-fix-2026-05-08.md`
  suffixes after bounded verification closed or staled their findings and fixed
  the live observability non-object JSON envelope parser crash.
- The truth sweep archived routed non-`/mu` deferred source packets under
  `reports/archive/deferred/` with
  `_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`
  suffixes, including stale Phase B generated packets and the closed
  `w5a_reentry_gate_coverage.md` source packet.
- The 2026-05-07 truth sweep routed then-remaining non-`/mu` work into bounded
  control-plane packets:
  `reports/control_plane/deferred-non-mu-docs-control-plane-remediation-2026-05-07_2026-05-07.md`,
  `reports/control_plane/deferred-non-mu-tooling-control-plane-remediation-2026-05-07_2026-05-07.md`,
  and
  `reports/control_plane/deferred-non-mu-tests-proof-remediation-2026-05-07_2026-05-07.md`.
- The 2026-05-06 non-blocking cleanup archived 12 closed, stale, or historical
  whole packets and extracted closed sections from 5 partial packets under
  `reports/archive/deferred/`.
- The retained-residue follow-up
  `deferred-non-blocking-retained-residue-cleanup-2026-05-06` archived one
  additional closed whole packet,
  `reports/archive/deferred/pager-deterministic-session-2026-04-18_bridge_nonblockers_closed-by-deferred-non-blocking-retained-residue-cleanup-2026-05-06.md`,
  and extracted the now-closed docs-root inventory-count section to
  `reports/archive/deferred/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers_partial-closed-by-deferred-non-blocking-retained-residue-cleanup-2026-05-06.md`.
  Bridge Round 1 then generated a same-wave retained non-blocking packet that
  was later archived by the 2026-05-07 non-blocking folder cleanup at
  `reports/archive/deferred/deferred-non-blocking-retained-residue-cleanup-2026-05-06_bridge_nonblockers_closed-by-non-blocking-folder-cleanup-2026-05-07.md`.
  The routed retained-candidate follow-up generated an active duplicate-tracker
  advisory, and the 2026-05-07 root/mu-docs audit closeout archived that
  advisory at
  `reports/archive/deferred/docs-root-mu-docs-retained-packet-cleanup-2026-05-06_bridge_nonblockers_closed-by-docs-root-mu-docs-audit-closeout-2026-05-07.md`
  and added a non-blocking L4 G8 docs DOC_ACCURACY advisory that was later
  archived by the deferred non-`/mu` truth sweep at
  `reports/archive/deferred/docs-root-mu-docs-audit-closeout-2026-05-07_non_blocking_closed-by-deferred-non-mu-deferred-lane-truth-sweep-2026-05-07.md`.
  The 2026-05-07 non-blocking folder cleanup also archived the same-wave
  `docs-root-mu-docs-audit-closeout-2026-05-07` bridge packet after closing its
  low-severity README wording finding. The 2026-05-07 deferred folder cleanup
  also archived the tests/tooling generated remediation bridge packets whose
  stale wording and evidence-command findings no longer reproduce.
- The current active non-blocking inventory is `README.md` plus three active or
  partially active retained `/mu` structural advisory packets.

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
