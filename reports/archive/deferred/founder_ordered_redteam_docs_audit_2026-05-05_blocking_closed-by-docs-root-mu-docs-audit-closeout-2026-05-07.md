# Founder Ordered Redteam Docs Audit - Blocking Findings

Date: 2026-05-05
Status: CLASSIFIED - NO BLOCKING FINDINGS
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: founder-ordered-redteam-docs-audit-2026-05-05
Class: L4_ENABLER
Target gate: G8
Governing packet: `reports/control_plane/founder_ordered_redteam_docs_audit_2026-05-05.md`
Founder override: FOUNDER_OVERRIDE:founder-ordered-redteam-docs-audit-2026-05-05

This packet records the docs-audit blocking lane. The audit wave did not
implement remediation.

## Scope Executed

- Markdown inventory command: `find . -path ./.git -prune -o -path ./node_modules -prune -o -name '*.md' -type f -print | LC_ALL=C sort | wc -l`
- Inventory result: 2310 repo-local markdown files discovered at audit time.
- Archive split command: `find . -path ./.git -prune -o -path ./node_modules -prune -o -name '*.md' -type f -print | sed 's#^./##' | awk '/(^|\/)archive\// || /(^|\/)Archive\// {archive++} !/(^|\/)archive\// && !/(^|\/)Archive\// {active++} END{print "active_or_generated_non_archive", active; print "archive_historical", archive}'`
- Archive split result: `active_or_generated_non_archive 2027`; `archive_historical 283`.
- Generated `.agent_bus/` and `.scratch/` markdown was inventoried and scanned as
  generated operational evidence, not governing doc truth, unless an active
  surface pointed to it as current.
- Archived markdown was treated as historical evidence only.

Already landed engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration work was not relisted as unresolved.

## Blocking Findings

None.

Bridge Round 1 reclassified the prior DOC_ACCURACY-only B1/B2 entries as
non-blocking because the shared disposition contract routes "Documentation
accuracy without behavioral impact" to NON_BLOCKING and because Phase B keeps
low/medium governance DOC_ACCURACY findings non-blocking. Those findings are
now recorded in the non-blocking docs-audit packet.

Direct classification evidence:

```text
nl -ba mu/tools/executors/executor_common.py | sed -n '129,144p'
nl -ba mu/tools/executors/phase_b_executor.py | sed -n '177,216p'
```
