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
- **Phase B retained-lane decision:** active; retain with current file-line evidence. The historical control-plane packet is evidence/readback only for this retained-lane cleanup.
- **Evidence:** `nl -ba reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md | sed -n '468,506p;526,540p'; nl -ba reports/deferred/non_blocking/docs-root-mu-docs-redteam-cleanup-2026-05-06_bridge_nonblockers.md | sed -n '11,26p'`

## Phase B Retained-Lane Disposition (2026-05-07)

- Direct readback keeps all three findings in this retained packet active as
  low-severity DOC_ACCURACY advisories. The historical control-plane packet is
  not an edit surface for this retained-lane cleanup, so no finding is closed by
  rewriting that older packet.
- Finding 1 remains active: the historical packet still says at
  `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md:472`
  through
  `reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md:487`
  that only the same-wave tracker note plus three docs cleanup files were edited
  and that no archive move is authorized. The same packet later lists the
  deferred bridge packet and same-wave indicator artifact at lines 497 through
  504 and lines 530 through 537.
- Former finding 2 is closed by this retained-residue cleanup: the final active
  lane inventory is reproduced with
  `find reports/deferred/non_blocking -maxdepth 1 -type f -name "*.md" | sort | nl -ba`
  and matches the deferred lane indexes.
- Finding 2 below remains active: the historical packet preserves the stale
  routing diagnostic as report evidence at lines 69 through 80 and repeats the
  stale-dispatch output at lines 313 through 318. This retained packet does not
  rerun routing and does not use `.agent_bus/meta/post_merge_routing.json` as
  current authority.
- Finding 3 below remains active: `mu/tools/docs/generate_docs_index.py:132`
  through `mu/tools/docs/generate_docs_index.py:140` index only direct markdown
  files inside each first-level docs directory, and the current `comm -23 ...`
  readback returns `mu/docs/README.md`. The historical packet's proposed edit
  wording at lines 388 and 397 through 404 remains evidence only; this wave does
  not edit `mu/docs/README.md` or `mu/tools/docs/generate_docs_index.py`.
- Lane action: keep this packet active in `reports/deferred/non_blocking/`.
  Because the packet remains active, no archive move or inventory removal is
  performed for these three retained findings.

## 2. Routing diagnostic evidence remains stale in the staged packet
- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md
- **Disposition:** non_blocking
- **Phase B retained-lane decision:** active; retain with current file-line evidence. Do not rerun routing or use post-merge routing state as authority for this packet.
- **Evidence:** `nl -ba reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md | sed -n '60,90p;300,325p'`

## 3. mu/docs README edit scope overstates the generated index target set
- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md
- **Disposition:** non_blocking
- **Phase B retained-lane decision:** active; retain with current file-line evidence. Do not edit `mu/docs/README.md` or `mu/tools/docs/generate_docs_index.py` in this wave.
- **Evidence:** `nl -ba reports/control_plane/docs-root-mu-docs-redteam-cleanup-2026-05-06_2026-05-06.md | sed -n '384,406p'; nl -ba mu/tools/docs/generate_docs_index.py | sed -n '132,140p'; comm -23 <(rg --files -g '*.md' mu/docs | rg -v '(^|/)(archive|archived)(/|$)' | sort) <(rg -o '\]\(([^)]*)\)' mu/docs/README.md | sed -E 's/^\]\(([^)]*)\)$/mu\/docs\/\1/' | sort)`
