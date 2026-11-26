# WorkingRCX landing handoff · November 25, 2026

Checked from PRIMARY on November 25 EST (November 26 UTC). PRIMARY and live GitHub `dev` both point to `fbe43a5e`, the October 21 merge of PR #1345. **Throughput R7 stopped in Phase B. The first decision is what must stay fixed during its two validation runs.** This is a dated handoff for the existing owners in [TASKS.md](../../TASKS.md). [Last landed PR](https://github.com/jabramsja/rcx-pi-core/pull/1345)

## First decision and landing work

1. **Owner 40 — resolve the R7 validation hold.** In round 1, the ten-module gate passed 5,279 tests, but the catalog hash changed and the sweep stopped after 698 tests (exit 2). In round 2, the captured catalog bytes changed **only** in `fetched_at`. The gate stopped after 1,170 tests (exit 2), before the sweep started. The writer is unknown. Round 4 returned `QUESTION` and the launcher exited 1 at 03:27:59 UTC on October 29. The locked plan requires byte-for-byte continuity. The founder must either establish a supported way for both runs to use the same raw catalog, or authorize a new plan defining which metadata may change and how every other change is rejected. [Round 2 byte comparison](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/workingrcx-pipeline-throughput-r7-2026-10-29-phase-b/bridge-round2-catalog-diff.json>) · [Staged blocker report](../../.scratch/worktrees/pipeline-throughput-r7-20261029/reports/deferred/blocking/workingrcx-pipeline-throughput-r7-2026-10-29_bridge_blockers.md) · [Launcher result](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/pipeline-throughput-r7-20261029-launch.json>)
2. **Protect the latest R7 candidate and finish delivery.** All 26 staged paths match the lifecycle inventory by file hash and index entry. The staged patch hash also matches. The inventory records zero local commits and zero paths covered by `dev`. WD snapshot `92969ded` covers admission, depends on R6 source `2eeba4a1`, and predates these changes. Preserve the final candidate, raw index and review evidence, then verify them by restoring into an empty directory. Once the catalog decision is recorded, the native pipeline still owes the full gate and identical sweep on that candidate, independent review, final checks, commit, CI on that commit, merge and PRIMARY sync. R7 has no PR. [Useful-work inventory](../../.git/rcx_worktree_lifecycle/8f0dd9297bc3618eabaa4314ca21e7b435544ae3caa79c96c4b56441375264d4/attempt-1/useful-work.json) · [Lifecycle decision](../../.git/rcx_worktree_lifecycle/8f0dd9297bc3618eabaa4314ca21e7b435544ae3caa79c96c4b56441375264d4/completion.json)
3. **Owner 38 — land deduplicated retention before retiring folders.** Carry the useful retention R4 changes from `f2eebf43` onto the landed base. For a worktree retirement, the existing producer writes a tree archive, Git administration archive, history bundle and recovery repository. Its replacement must verify recovery of the original paths, Git objects, index and working files from the UUID-selected WD store. Then admit a fresh native plan for the **six named completed archives**, protect every other source, and verify the six outcomes. The 24 adjacent legacy payloads have a separate snapshot (`31428e84`). Programs that read them at their original paths need a verified mapping before removing those copies. [Current producer](../../mu/tools/executors/workingrcx_fleet_apply.py) · [Six-archive plan](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/folder-first-six-protection-plan-20261027.json>) · [Payload inventory](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/folder-first-six-legacy-payload-followup-20261027.json>)

## The four open PRs

GitHub reported conflicts against `dev` for **all four**. CI and review counts below are for the listed heads. The path counts cover the original changes from each merge base.

| PR | Head | Paths | CI | Work to reconcile |
| --- | --- | ---: | --- | --- |
| [#1335 · pytest R1](https://github.com/jabramsja/rcx-pi-core/pull/1335) | `4f6ab974` | 7 | 7 passed | One open thread on inherited fail-fast options. Include the private R1 commit and distinct staged/working tests in the donor review. |
| [#1336 · pytest R3](https://github.com/jabramsja/rcx-pi-core/pull/1336) | `4e8aca8a` | 9 | `green-gate` failed | One open thread on serial fallback when pytest-xdist is unavailable. |
| [#1337 · pytest R6](https://github.com/jabramsja/rcx-pi-core/pull/1337) | `ccabe0e8` | 15 | `green-gate` failed | One open thread on verifying owned child processes after normal pytest exit. |
| [#1325 · Mu guarded prefix R8](https://github.com/jabramsja/rcx-pi-core/pull/1325) | `01cc58b3` | 25 | `green-gate` failed | No open review threads. Compare all original changes with landed Mu R10 and the continuation repair. |

For each PR, record what landed on `dev`, what was superseded and why, and which useful hunks still need a native wave. Resolve each outstanding finding against the actual replacement, then use the native disposition path and verify the remote result. One throughput merge cannot establish coverage for all three runner PRs.

## What is on disk

From PRIMARY, `../RCX-Recovery-Access/rcx-recovery where` locates the repository by volume UUID. The WD evidence links in this handoff use its adjacent `reviews/autonomous-landing-20261011/` directory.

The UUID-resolved **RCX Recovery** volume has **331 restic snapshots**. The October migration records 86 fleet folders and 17 ordinary sibling worktrees retired to verified storage. It preserved their contents. Useful historical work still needs comparison with `dev`, including the fix35 provider-error and fix37 staged-discard repairs in snapshot `8971db37`. Restore selected paths into an empty review directory on the WD. Keep active development in PRIMARY. [Recovery manifest](../../../RCX-Recovery-Access/manifest.json) · [Historical donor review](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/historical-selected-recovery-review-note-20261027.txt>)

On the WD, `du -sk` measured **44.9 GiB in `reviews/`** and **30.2 GiB in the deduplicated `repository/`**. The largest directory under the October 11 review lane holds the legacy payloads for the first six archives, about 3.5 GiB including its restored copies. How much space can be reclaimed depends on which copies can be restored and which files are unique or still referenced by receipts.

Git registers **77 worktrees**. The 76 present are PRIMARY, 65 under `.scratch/worktrees`, seven lifecycle archives and three in the sibling preservation directory. One locked `/private/tmp` registration has no directory. Against remote `dev`, 16 registered heads match, 51 are strictly behind and 10 diverge. The separate linked local `dev` is at `146ca495`, 38 commits behind. Reconcile it through its native owner with its evidence protected.

Of the 66 sources in the October 27 inventory, six were proposed for retirement, seven had no observed tracked changes, three held retention code, 29 had selected changes reviewed, and **21 held useful unmerged work**. Seven throughput registrations (R1–R7) have since been added. Include all seven in the next census. For each source, check the index, working files, private history, ignored/untracked files and live ownership before retirement. [66-source disposition map](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/folder-disposition-queue-map-v16-20261027.json>)

## Return to Mu

**The first production wave is the coinduction continuation repair.** PR #1327 delivered the bounded finite-prefix implementation. The outstanding proof is that the retained JS continuation stays bound to its state, with matching Python/JS behavior through the real evaluator. Bind the structural repair to the then-current landed base and use it for #1325 coverage. Follow with owner 41 (evaluator self-application and fixpoint), owner 42 (Stage5 ordinal and Stage0 bool/str evidence), then owner 43 (optimization). The October 22 assessment also flags incorrect projection IDs in traces on both substrates. Keep that limitation visible wherever a production claim relies on trace attribution. [Mu R10 merge](https://github.com/jabramsja/rcx-pi-core/pull/1327) · [Structural repair draft](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/continuation-binding-wave-launch-preparation-20261017-v32.json>) · [Trace assessment](../deferred/blocking/rcx-runtime-candid-assessment-2026-10-22.md)

Runner lifetime, monitor verification, timeout/retry handling, review of locked failure criteria, and linked-worktree synchronization retain their existing owners. Keep parked pipeline work off the Mu critical path unless a specific issue blocks the next wave.

The checkpoint, working to-do and rows 38/40 were updated in the local PRIMARY checkout on `jabramsja/workspace-2026-06-04`. Carry this handoff with the tracker in the next native publication. The tracker writer preserved 268 IDs, all 44 ordered owners and the earlier notes. [Tracker synchronization receipt](</Volumes/RCX Recovery/WorkingRCX-Recovery/reviews/autonomous-landing-20261011/PRIMARY-workingrcx-landing-handoff-20261125-tracker-sync.json>)

## Verification in PRIMARY

The five documentation, tracker and debt/status test files ran together from the repo root. The command exited **0** and printed **`136 passed in 8.98s`**.

```bash
env PYTHONHASHSEED=0 python3 -m pytest -q \
  mu/tests/docs/test_doc_freshness.py \
  mu/tests/docs/test_status_tasks_consistency.py \
  mu/tests/docs/test_l4_current_state_truth.py \
  mu/tests/docs/test_debt_truth_gate.py \
  mu/tests/structural/test_status_md_grounding.py
```

An initial combined invocation mixed the `tests/` symlink with its `mu/tests/` target. It exited **1** during collection with `ValueError: Plugin already registered under a different name` for `docs/conftest.py`. The command above uses the canonical path throughout.

| Command | Exit | Observed result |
| --- | ---: | --- |
| `./tools/checks/check_docs_consistency.sh` | 1 | Its pytest groups printed `42 passed`, `50 passed`, and `8 passed`. The docs registry step failed. |
| `python3 tools/docs/docs_sync_report.py --check` | 1 | `Unclassified markdown files: 6054`, `Unregistered docs subfolders: 0`, `Tracker section placement violations: 7`. All seven placement paths are lifecycle copies under `.git`. |
| `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` | 0 | `"passed": true`, with empty `increases` and `decreases` lists. The five tracked markers match baseline. |
| `python3 tools/checks/check_host_authority_inventory_ratchet.py` | 0 | `PASS: No unaccepted new total-inventory or authority-subset sites detected.` The scan counted 309 total sites and 212 authority sites. |
| `python3 tools/checks/enforce_l4_execution_contract.py --staged` | 0 | `No staged files — skipping enforcement.` |

These checks cover the PRIMARY handoff. R7's separate Phase B hold remains open. Docs-mode startup also reported local Codex binary and model-cache drift.
