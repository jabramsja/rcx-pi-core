# RCX Project Status

**This is the single source of truth for project phase. Agents MUST read this file.**

> **Document Architecture**: See [`roadmap/MANIFEST.md`](roadmap/MANIFEST.md) for reading order and linking rules across STATUS.md, TASKS.md, and roadmap docs.

---

## Current Phase

```
PHASE: 8c
NAME: Structural Selection Parity (L1-L3 COMPLETE)
```

## Projection-Based Architecture Levels

| Level | Description | Status |
|-------|-------------|--------|
| **L1: Algorithmic** | match/subst algorithms EXPRESSED as Mu projections | DONE (Python executes projections) |
| **L2: Operational** | kernel state machine EXPRESSED as Mu projections | FULL (decision: accept for-loop as bootstrap primitive) |
| **L3: Substrate Portability** | Same projections on Python and JavaScript substrates | COMPLETE |
| **L4: True Self-Hosting** | Bootstrap primitives eliminated or substrate-independent | SINK (full completion research; bounded reduction active) |

**Terminology Honesty:**
- "Projection-based" means the ALGORITHM is expressed as Mu projections (data)
- Python's `eval_step()` EXECUTES those projections (like Forth's NEXT executes threaded code)
- The "kernel" in L2 refers to `kernel.v1.json` (7 projections), NOT the deprecated `Kernel` class

## What This Means

- **L1 Algorithmic DONE**: `match_mu()` and `subst_mu()` are expressed as Mu projections. Python's `eval_step()` executes them.
- **L2 Operational FULL**: Projection SELECTION is structural (linked-list cursor in kernel.v1). Projection EXECUTION is Python (`for` loop in `step_kernel_mu`) — accepted as bootstrap primitive per Phase 8 decision.
- **Python's role**: `eval_step()` is a bootstrap primitive (like Forth's NEXT). Irreducible in current architecture.

## L2 Completion Criteria

- [x] Kernel state machine is 7 Mu projections (`kernel.v1.json`)
- [x] Match v2 with context passthrough (8 projections, `_match_ctx`)
- [x] Subst v2 with context passthrough (13 projections, `_subst_ctx`)
- [x] Projection selection uses linked-list cursor (`_remaining` field)
- [x] `step_kernel_mu()` wired to use structural kernel
- [x] Security hardening (27 reserved fields, deep validation)
- [ ] Python for-loop still drives kernel execution (accepted as bootstrap primitive)

## L3/L4 Architecture Details

**For full L3 architecture, seed categories, JS debt tracking, contraband patterns, L4 research status, P7 reduction chain, and cross-substrate testing strategy:**

See [`mu/docs/core/L3SubstrateArchitecture.v0.md`](mu/docs/core/L3SubstrateArchitecture.v0.md)

**L4 current state:** full L4 completion remains in SINK, but bounded reduction work is active. VM cutover is ACTIVE. P7 Meta-Circular Reduction Chain complete (all 33 projections via Stage0 VM). The current autonomous execution order is tracked in `TASKS.md` under the active Codex queue; this file does not duplicate that queue. See architecture doc for full chain details.

**Key facts (summary):**
- 22 registered seeds; 17 in the JS CLI verification view, including the guarded finite-prefix program shared by Python and JavaScript
- 4 bootstrap primitives: eval_step, max_steps, stack_guard, projection_loader (mu_equal DEMOTED)
- JS substrate: ~6,488 LOC core, 16 modules at `mu/host/js/`
- Python substrate: ~8,430 LOC, ~7,525 tests
- VM cutover ACTIVE (`_STAGE0_VM_CUTOVER = True`, all 33 projections via Stage0 VM)
- G8 PASS (classification gate, caveated, 2026-03-03)

**L3 Parity Requirement (MANDATORY — North Star #13):**
- Any change to Python projection behavior MUST be mirrored in JavaScript
- Core L3 seeds MUST be loaded in BOTH substrates
- Run `node mu/host/js/eval_step.js` after Python changes to verify JS parity
- Run `./tools/checks/check_js_debt.sh` to verify JS debt markers match Python
- Violation of parity breaks L3 and must be fixed before merge

**Related policies:**
- L4 Execution Contract: [`roadmap/L4ExecutionContract.v2.md`](roadmap/L4ExecutionContract.v2.md)
- Semantic Policy Lock: [`mu/docs/core/NorthStarSemantics.v0.md`](mu/docs/core/NorthStarSemantics.v0.md)
- Ontology Promotion Contract: [`mu/docs/core/OntologyPromotionContract.v0.md`](mu/docs/core/OntologyPromotionContract.v0.md)
- Boot0 Architecture: [`mu/docs/core/Boot0Architecture.v0.md`](mu/docs/core/Boot0Architecture.v0.md)
- Boot1 Loop Contract: [`mu/docs/core/Boot1LoopContract.v0.md`](mu/docs/core/Boot1LoopContract.v0.md)

## Debt Status

### Three-Ledger Host Debt Truth

RCX tracks host debt at three distinct granularities. Each ledger answers a different question. All three are mechanically enforced by ratchet baselines and a gate test (`tests/docs/test_debt_truth_gate.py`).

| Ledger | Count | What It Measures | Baseline Source |
|--------|-------|------------------|-----------------|
| **Tracked markers** | 5 | Narrow official `@host_*` debt marker sites (2 Py marker + 3 JS marker) | `tools/checks/host_semantics_baseline.json` |
| **Authority sites** | 217 | Named runtime sites with host-authority signals (120 Python + 97 JavaScript) | `tools/checks/host_authority_inventory_baseline.json` |
| **Total inventory sites** | 312 | Full named host-runtime surface (181 Python + 131 JavaScript) | `tools/checks/host_authority_inventory_baseline.json` |

```
THRESHOLD: 9 (dashboard/pre-commit semantic ceiling)
CURRENT: 5 (2 Py marker + 3 JS marker — per host_semantics_baseline.json)
FLOOR: 5 (see archive/status_debt_history.md for wave-by-wave explanation)
INFRA_CEILING: 135
INFRA_CURRENT: 135
```

**Direction:** Tracked markers monotonically decrease (enforced by `check_host_semantics_ratchet.py`). `THRESHOLD` carries the dashboard/pre-commit semantic ceiling; `CURRENT`/`FLOOR` carry the canonical cross-substrate tracked-marker baseline. Authority and total inventory ratcheted against baseline (enforced by `check_host_authority_inventory_ratchet.py`).

**For marker breakdown, kernel path details, site inventory, wave-by-wave history, and infrastructure classification:**

See [`archive/status_debt_history.md`](archive/status_debt_history.md)

## Testing Tiers

```
Tier 1: Fast Audit    ./tools/audit_fast.sh         ~3 min   Core tests only (local iteration)
Tier 2: Full Audit    ./tools/audit_all.sh          ~5-8 min Core + Fuzzer + Slow (before push)
Tier 3: CI Green Gate scripts/green_gate.sh          ~2 min   Core only, no fuzzers/slow (push/PR)
Tier 4: CI Nightly    scripts/green_gate.sh ci_full  ~45 min  Everything (scheduled nightly)
```

See [`.claude/rules/test-classification.md`](.claude/rules/test-classification.md) for marker rules, hook details, and enforcement. See [`mu/docs/audit/CI_POLICY.md`](mu/docs/audit/CI_POLICY.md) for full testing strategy.

## Key Files

| File | Purpose |
|------|---------|
| `STATUS.md`, `TASKS.md` | Source of truth for phase/debt and work items |
| `mu/host/python/rcx_pi/selfhost/` | Core implementation (`rcx_pi/` is symlink) |
| `mu/host/js/eval_step.js` | JavaScript substrate (L3 parity) |
| `mu/tools/executors/` | Executor scripts (Phase A/B/commit automation) |
| `mu/docs/core/` | Design specs |
| `.claude/rules/` | Conditional rules (9 files incl. learning) |
| `mu/docs/core/L3SubstrateArchitecture.v0.md` | L3/L4 architecture details (extracted from this file) |
| `archive/status_debt_history.md` | Debt marker wave-by-wave history (extracted from this file) |

---

## Grounded References (test-enforced presence)

**Terminology Lock:** `sink` (lowercase) = runtime hemisphere bucket. `SINK` (uppercase) = governance task lane. `r_a` = runtime accumulator. `Ra` = resolved-work section. See TASKS.md and `mu/docs/core/L3SubstrateArchitecture.v0.md` for full definitions.

**Post-D008 Operating Mode:** D008 GO rendered (founder, 2026-03-01; supersedes prior DEFER). G8 PASS (classification gate). VM cutover ACTIVE. All 33 projections via Stage0 VM. See architecture doc for full chain.

**Hemisphere Metabolization Contract:** COMPLETE (E1-E5 all MET, 2026-02-20). Canonical closed milestone baseline.

**Conjecture Parking:** Non-Euclidean geometry / structural linear algebra hypotheses are PARKED (not active). See TASKS.md SINK for re-evaluation trigger.

**L3 Canonical Truth:** The evaluation rules are structural data, but execution iteration, resource bounding, and API normalization remain irreducible host-language mechanics.

---

## Gate Snapshot (Canonical)

- Gate 3: COMPLETE (2026-02-07)
- Gate 4: COMPLETE (2026-02-07 structural cutover)
- Gate 5: COMPLETE (2026-02-09 meta-circular parity verified)
- Gate 8: PASS (classification gate, caveated, 2026-03-03)

Current Recurrence Layer: META_CIRCULAR
Current Exhaustion Layer: META_CIRCULAR

**Current Algorithm Execution:**
- `run_algorithm_meta_circular()` defaults to `step_kernel_mu(kernel_mode="bridge", validation_mode="algorithm_runtime")`
- Algorithm runtime is bridge-backed meta-circular

**Bounded Coinduction capability (Mu R10, Phase B, 2026-10-02):** the registered
`coinduction_prefix.v1.json` program constructs guarded finite observation windows
and resumable open tails through the production Python/JS structural kernels.
It preserves R9's 24 shared vectors, complete outcomes, emission assertions and
canonical StructuralNumbers inputs. The execution-layer contract requires real
alternating progress and loss of the result when `co_prefix.emit` is removed.
This is finite kernel-trace evidence; it does not establish engine observer
events, infinite productivity, bisimulation or full Coinduction/L4 completion.
R10 retains R9's paired 1000-step substitution replay bound, immutable VM
snapshots and private proof identity. Data-only canonical-content pins replace
four forbidden engine imports; compiler reconstruction and per-slot content/pin
mutation controls ground those pins in actual artifacts. Public continuations
and custom configurations retain binding replay and original VM-order rejection.
Raw host integers remain outside matcher admission; resource exhaustion is not
a semantic result. See [CoinductionPrefix.v0.md](mu/docs/core/CoinductionPrefix.v0.md)
and the [current implementation evidence](reports/control_plane/mu-coinduction-guarded-prefix-r10-2026-10-02_implementation_evidence.json)
for actual local validation. Native review, measured indicators and landing
remain pending; R9 and R8/PR1325 stay preserved under the existing production owner.

---

## Historical Archives

**Current recovery coverage R10 (2026-10-21; Phase B implementation):**
Closeout repair PR1344 merged head `108e2cf3d6b85367a41f327d3bd6b76f4b0341be`
at `cb6ab69c68b80464db386ac626bf739e42653805` on 2026-10-21T02:38:33Z.
Captured PRIMARY independently records seven successful current-head CI checks
on attempt1, Main synchronization, native successor COMPLETE and launcher exit0.
Fresh public R8 recovery subsequently reached RECOVERED/MOVED, with verified
source/index/history restoration in WD snapshot `6815ad24`. R8's old launcher
exit1 and sealed ESCALATED completion remain historical. The landed R4 evidence
snapshot `ac4c8214` and source lineage `4c05a144` remain retained.

PR1341 is CLOSED_VERIFIED under consumed native operation
`1a32f9f7f8b24c399e4f79a609cbd498`, with source head `167dd035` and its branch
retained. PR1329 remains OPEN/HOLD: PR1344 changed the lifecycle production and
test blobs cited by old R8 coverage. Existing row38 owns the fresh
[R10 single-target manifest](reports/control_plane/workingrcx-fleet-pr-coverage-r10-2026-10-21_coverage.json)
for original `537fb046` against actual merged `cb6ab69c`: all 20 paths/62 hunks,
explicit supersession of the one-time Mu exception, and preserved default Mu
protection. Independent native semantic review, indexed authority and delivery
remain PLANNED; local source/command bindings and actual results belong in the
[R10 implementation evidence](reports/control_plane/workingrcx-fleet-pr-coverage-r10-2026-10-21_implementation_evidence.json).
Separate public PR1329 disposition follows verified landing and Main sync.

R9 commit `da269cfd` remains STOPPED/PRESERVED: its local 239/239 pair, review
and staged L4 preceded a 2400-second pre-push timeout, exhausted native recovery
and launcher exit1. It has no PR, CI, merge or COMPLETE. Snapshots `2c714f5e`
and `7a0895c2` preserve the committed source and later staged packet demotion.
R10's immutable runtime context `9a4d39a1` admits only initial per-invocation
pre-push 3600 seconds, baseline 2400 and unchanged commit outer 3600; physical
config `7ce64811` stays unchanged. This temporary control establishes no cause
for the slow hook and leaves the durable timeout repair with row40.

Existing row40 and Mu owners retain runner PR1335/1336/1337, PR1325 useful work,
deduplicated retention producer integration, docs-inventory boundaries, timeout
and CI pending-state automation, permanent closeout retry regression, tmux
provisioning and linked-dev/held-transaction obligations. The existing standing
reports below preserve those obligations; their earlier stage observations are
historical. Main's archived-Git/Claude-learning inventory HOLD is distinct from
the captured clean R10 lane startup. Phase 8c and all debt/runtime counts remain
unchanged; no global cleanup or full L4 completion is claimed.

**Historical landed-closeout R4 implementation (2026-10-20; before PR1344 landed):**
The exact base is PR1343 merge `609270f0b338a3121f37b1e58e9d1448356f4048`.
Captured PRIMARY records that coverage lane's closeout HOLD; original PR1329
and PR1341 disposition remains separate. Existing row40 owns ten admitted
source files for timeout observation, completion-locked publication, fresh sealed
closeout recovery, canonical tracker-note authority, and dispatcher continuation
fixtures. Local results and exact source/index/config bindings belong in the
[R4 implementation evidence](reports/control_plane/workingrcx-landed-closeout-r4-2026-10-20_implementation_evidence.json).
R3 source preservation and old approvals are not R4 landing proof. Native
generated authority, independent review, final gates and delivery remain pending.
The [required standing obligations](reports/deferred/non_blocking/workingrcx-landed-closeout-r4-2026-10-20_remaining_obligations.md)
retain original PR, runner, retention, Mu, docs namespace, execution-envelope and
operator reconciliation work. Phase 8c, all debt counts, runtime and substrates
are unchanged.

**Historical recovery coverage R8 (2026-10-20; observed before PR1343 landed):** PR1340 actually merged at
`5921cf352db0f52aa469655371e8977c3f1a0848`; original PR1330/PR1338 are
CLOSED_VERIFIED with their branches retained. Fixture PR1342 actually merged
at `9e3323108d81561e31cb5b83e72cc21b13accca2`, Main synchronized and its native
lane reached COMPLETE. Its fresh `68c65585` CI attempt1 and source-bound
3530/3530 local pair belong to R4, not to this coverage candidate.
Existing row38 now owns exactly original PR1329 (20 paths/62 hunks) and failed
R7 PR1341 (9 paths/14 hunks). Both remain OPEN at their retained source heads.
The [R8 manifest](reports/control_plane/workingrcx-fleet-pr-coverage-r8-2026-10-20_coverage.json)
and [implementation evidence](reports/control_plane/workingrcx-fleet-pr-coverage-r8-2026-10-20_implementation_evidence.json)
separate contributing merged code, historical evidence and superseded policy.
Independent native review, generated/indexed authority and all R8 landing
stages remain pending; subsequent public original-PR disposition is separate.

The removed one-time Mu release exception is superseded by default protection,
not represented as landed permission. Tmux availability P2 remains OPEN under
row40: R4 establishes stable birth identity, actual waiting/reaping and
query-failure cleanup, not provisioning or supported tmux-less operation.
R7's initial release-positive child-presence failure cause remains unproved;
its second attempt directly evidenced mutable command identity. The corrected
`167dd035` inventory does not retroactively approve `19f499d6`.
The [required standing report](reports/deferred/non_blocking/workingrcx-fleet-pr-coverage-r8-2026-10-20_row40_advisories.md)
preserves runner/R19, retention, Mu, monitor, docs-inventory and linked-dev
ownership obligations. PR1325/1335/1336/1337 remain independently OPEN.

Main's captured startup at `9e332310` has four core checks at exit0 and docs
consistency at exit1: 42/50/8 docs subchecks passed, but the inventory reported
3395 unclassified and four placement failures involving preserved Git metadata
and Claude-owned learning archives. The separate clean worktree admission
measured empty status and passing core/docs checks. This is not global startup
green; the existing row40 inventory-boundary followup remains open.

**Private tmux fixture R3 (landed PR1339, 2026-10-20):** merged at
`ca6c3a93c176fc1da6b6bb6f0169edebf8c1a654`; Main synchronized to that commit
and the prior native lifecycle completed. The test
fixtures own a private foreground tmux controller, bind its watcher identity,
and require actual reaping and fresh PID absence. Only the unchanged positive
late consumer retains coherent OS observation; adverse consumers restore the
original observer before injection. Production guards, runtime/substrate and
architectural completion claims are unchanged. Source-bound local results and
the retained historical failures are recorded in
[implementation evidence](reports/control_plane/workingrcx-private-tmux-fixture-r3-2026-10-19_implementation_evidence.json).
That report retains the original local results and their source bindings;
PR1339 CI and landing do not approve a later coverage candidate.

**Historical PR1330/PR1338 coverage R6 (Phase B, 2026-10-20; recorded before PR1340 landed):** existing row38 owns fresh
schema2 accounting for all 7 paths/14 hunks of PR1330 and 9 paths/20 hunks of
PR1338 against actual merged PR1334 and PR1339. Both original targets remain
OPEN at the admitted heads; independent native review, indexed authority,
complete landing gates and subsequent public lifecycle disposition remain
pending. Source-bound local results belong in the
[R6 implementation evidence](reports/control_plane/workingrcx-fleet-pr-coverage-r6-2026-10-20_implementation_evidence.json).
The [required standing report](reports/deferred/non_blocking/workingrcx-fleet-pr-coverage-r6-2026-10-20_row40_advisories.md)
keeps partial-output preservation distinct from unproved unchanged retry
suppression, and retains native runner/R19, retention, Mu, monitor and linked
dev ownership sync HOLD. Main synchronization does not resolve that separate
linked-checkout hold or consume the preserved transaction/stash.

- Phase history (Jan-Mar 2026): [`archive/status_history_jan_mar_2026.md`](archive/status_history_jan_mar_2026.md)
- Debt marker history: [`archive/status_debt_history.md`](archive/status_debt_history.md)
- L3/L4 architecture details: [`mu/docs/core/L3SubstrateArchitecture.v0.md`](mu/docs/core/L3SubstrateArchitecture.v0.md)

**Historical update wording, before PR1340 landed:** 2026-10-20 (R6 Phase B governance; admitted HEAD and `origin/dev` equal actual PR1339 merge `ca6c3a93c176fc1da6b6bb6f0169edebf8c1a654`. Main synchronized; this coverage candidate remains unmerged. Phase 8c/L4 bounded-reduction posture and debt counts unchanged.)
**Historical last-updated wording:** 2026-10-20 (R8 Phase B governance at actual PR1342 merge `9e3323108d81561e31cb5b83e72cc21b13accca2`; R4 landed and complete, R6 originals CLOSED_VERIFIED, R8 unmerged. Phase 8c/L4 posture and debt counts unchanged.)
**Next milestone:** First clear the ordered control-plane root-fix queue in TASKS.md if it blocks autonomous execution, then continue with **Coinduction** as the next program-structural wave. Recursive ordinals landed in PR #1160 (`b538b8d9`), W-types / inductive types landed in PR #1161 (`6a6b4217`), the nightly StructuralNumbers regression repair landed across PRs #1181-#1187, and Codex/default pager routing landed in PR #1194 (`4734ed2a`). Fixpoint follows Coinduction; Optimization remains LAST. Hemisphere Metabolization Contract remains the closed milestone baseline (E1-E5 all MET). Canonical authorization remains TASKS.md.
**Historical active-item wording, at R6 admission:** Existing row38 owns PR1330/PR1338 R6 coverage; both originals and other independently owned PR obligations remain OPEN at admission. R19/retention/Mu/monitor work and linked dev ownership sync HOLD remain separately owned.
**Historical active-item wording at R8 admission:** See `TASKS.md` PROGRAM QUEUE. Existing row38 owns fresh PR1329/PR1341 R8 coverage; independent review and native landing/disposition remain pending. Existing row40 and Mu owners retain runner, retention, monitor, prerequisite-policy, docs-inventory and linked-dev ownership holds without a new all-unfinished-work prerequisite barrier.

**Historical 2026-07-01 operational snapshot:** See `TASKS.md` PROGRAM QUEUE for the active Codex autonomous queue. Current operational merge evidence includes PR #1194 (`4734ed2a`, committed and missing-config pager fallback routes to Codex), PR #1193 (`0eb8c34c`, commit-executor draft-PR-ready hardening), PR #1192 (`f98c445c`, route/xdist hardening), PR #1191 (`c8c65c4a`, PR #1166 Codex-default preservation), PR #1190 (`5303862f`, recovery/pre-push blocker hardening), PR #1189 (`ea782dc1`, PR #1173 never-behind preservation), PR #1188 (`675f6de8`, WIP/unmerged-PR preservation), and PRs #1181-#1187 (nightly NR structural-numeral repair and verification). Original stale PRs #1173 and #1166 are closed as superseded, and GitHub reported no open PRs against `dev` during this sync. Recurring local cron/autoping/tmux was intentionally stopped after #1194 to conserve model usage; do not assume those local observer surfaces are live until explicitly restarted.

**Last updated:** 2026-10-21 (R10 Phase B coverage against landed PR1344 merge `cb6ab69c`; R10 native review/delivery and separate PR1329 disposition pending).
**Active NEXT items:** See `TASKS.md` PROGRAM QUEUE. Existing row38 owns PR1329 coverage/disposition; row40 and Mu owners retain runner, retention, Mu, regression automation and ownership holds.
