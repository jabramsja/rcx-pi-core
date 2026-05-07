# Deferred Non-Blocking Findings: docs-root-mu-docs-redteam-cleanup-2026-05-06

Wave: docs-root-mu-docs-redteam-cleanup-2026-05-06
Class: L4_ENABLER
Target Gate: G8
Status: DEFERRED_NON_BLOCKING
Retained by `deferred-non-blocking-retained-residue-cleanup-2026-05-06` with
3 active finding(s). Closed inventory-count section archived to
`reports/archive/deferred/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers_partial-closed-by-deferred-non-blocking-retained-residue-cleanup-2026-05-06.md`.

## 1. Control-plane packet acceptance criteria omits staged deferred report and indicator artifact
- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md
- **Disposition:** non_blocking
- **Evidence:** `git show :reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md | nl -ba | sed -n '467,484p'; git diff --cached --name-only | nl -ba`

## Current Truth Note (2026-05-06)

- Finding 1 remains active: current packet lines
  `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md:472`
  through
  `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md:486`
  still describe a narrower edited-file set and no archive move while the same
  packet's commit refresh lists the deferred packet and indicator artifact at
  lines 530 through 537.
- Former finding 2 is closed by this retained-residue cleanup: the final active
  lane inventory is reproduced with
  `find reports/deferred/non_blocking -maxdepth 1 -type f -name "*.md" | sort | nl -ba`
  and matches the deferred lane indexes.
- Finding 2 below remains active: current packet lines 69 through 80 and 313
  through 318 preserve stale routing-diagnostic output as packet evidence.
- Finding 3 below remains active: `mu/tools/docs/generate_docs_index.py:132`
  through `mu/tools/docs/generate_docs_index.py:140` only index one markdown
  directory level, and the current `comm -23 ...` readback still returns
  `mu/docs/README.md`.

## 2. Routing diagnostic evidence remains stale in the staged packet
- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md
- **Disposition:** non_blocking
- **Evidence:** `git rev-parse --short HEAD; nl -ba .agent_bus/meta/post_merge_routing.json | sed -n '1,18p'; git show :reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md | nl -ba | sed -n '65,80p;310,315p'`

## 3. mu/docs README edit scope overstates the generated index target set
- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md
- **Disposition:** non_blocking
- **Evidence:** `nl -ba mu/tools/docs/generate_docs_index.py | sed -n '120,155p'; comm -23 <(rg --files -g '*.md' mu/docs | rg -v '(^|/)(archive|archived)(/|$)' | sort) <(rg -o '\]\(([^)]*)\)' mu/docs/README.md | sed -E 's/^\]\(([^)]*)\)$/mu\/docs\/\1/' | sort)`
