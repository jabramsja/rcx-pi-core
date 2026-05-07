# Partial Closed Deferred Non-Blocking Snapshot: docs-root-mu-docs-redteam-cleanup-2026-05-06

Source file:
`reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md`

Closed by:
`deferred-non-blocking-retained-residue-cleanup-2026-05-06`

Reason:
The active non-blocking lane count drift section was closed by the same cleanup
that archived
`pager-deterministic-session-2026-04-18_bridge_nonblockers.md`. The final
inventory readback now matches `reports/deferred/README.md` and
`reports/deferred/non_blocking/README.md`.

Current evidence:

- Before the move, `find reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' | sort | nl -ba`
  listed `README.md` plus 30 retained packets.
- `reports/deferred/README.md:37` through `reports/deferred/README.md:42`
  and `reports/deferred/non_blocking/README.md:37` through
  `reports/deferred/non_blocking/README.md:40` describe the active lane as 30
  markdown files, including README plus 29 active or partially active packets.
- After moving the closed pager packet to archive, the same inventory command
  lists 30 markdown files including README.

Archived closed section:

## Deferred lane inventory count is stale after adding a non_blocking report

- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** reports/deferred/README.md
- **Disposition:** non_blocking
- **Evidence:** `find reports/deferred/non_blocking -maxdepth 1 -type f -name '*.md' -print | wc -l; nl -ba reports/deferred/README.md | sed -n '22,45p'`
