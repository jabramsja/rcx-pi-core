# Next Codex Post-Redteam Phase A: Structural Gap Sweep — Slice 1 (Engine Pipeline)

Date: 2026-03-30
Status: Phase A (design — bridge-converged)
Phase-A-Lock: LOCKED

## 2026-05-03 Current-Truth Note

This packet is now a historical Phase A findings/evidence record, not a current
pending-work list. `TASKS.md:392-397` is the active tracker authority for
`[NEXT-CODEX-POST-REDTEAM]`: PR #701 landed this Phase A sweep packet/evidence
only, and the later `post-redteam-engine-state-scheduler-reduction-2026-04-30`
slice landed the engine-state/scheduler seed, fixture, structural-test,
scheduler-parity, and seed-registration items listed in `TASKS.md:396`.

The F-1/F-2 findings below remain useful as historical closure evidence for why
that downstream slice existed, but they must not be relisted as unresolved.
F-3/F-4 remain historical findings only until a separate bounded packet proves
new current code truth.

## 1. Scope

### First slice target

Engine pipeline, scheduler boundary, and engine-adjacent runtime surfaces. This
slice focuses on Gaps 1, 2, 5, and 7 from the governing gap map — the formal
engine state model, the scheduler/operator-pool boundary, terminal semantics,
and workload corpus. Gaps 1 and 2 are sequenced first because both governing
packets (gap map §Recommended Next Design Slice, seed implementation packet
§Why This Packet Exists) specify that the next slice must lock formal engine
state plus the scheduler boundary before other gap work proceeds. Gaps 5 and 7
are included because they are concrete, reproducible, and structurally bounded
items that can be swept alongside the state/scheduler investigation without
adding new host semantics.

### Files and directories in scope

**Runtime (read + potential fix):**
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py` — Python engine loop
- `mu/host/python/rcx_pi/selfhost/step_mu.py` — Python terminal classification authority (`classify_terminal_kind`)
- `mu/host/js/engine/pipeline.js` — JS engine parity loop
- `mu/host/js/engine/routing.js` — JS engine routing
- `mu/host/js/engine/kernel.js` — JS engine kernel
- `mu/host/js/core/terminal_classification.js` — JS terminal classification authority (`deriveEngineExitReason`, `classifyTerminalKind`)

**Seeds (read + potential fix):**
- `mu/programs/rcx_engine.v1.json` — engine cycle nucleus (11 projections)
- `mu/closures/fix.v1.json` — structural fix seed
- `mu/closures/exhaustion.v1.json` — exhaustion/freeze seed

**Tests (read + potential new fixtures):**
- `mu/tests/engine/` — engine test suite (17 test files)
- `tests/l4_gates/test_engine_exit_reason_gate.py` — L4 exit reason gate
- `tests/l4_gates/test_engine_terminal_event_gate.py` — L4 terminal event gate
- `tests/l4_gates/test_engine_transition_gate.py` — L4 transition gate
- `tests/l4_gates/test_terminal_classification_parity_gate.py` — L4 terminal classification parity gate
- `tests/l4_gates/test_terminal_semantics_displacement_gate.py` — L4 terminal semantics displacement gate
- `tests/engine/` — engine integration tests
- `tests/parity/` — parity tests
- `tests/parity/test_rcx_engine_workload_contract_parity.py` — canonical workload contract parity test
- `mu/tests/fixtures/rcx_engine_workload_contract.json` — canonical workload vector manifest (3 vectors)

**Docs (read-only, for gap verification):**
- `reports/codex/runtime_design/vector_2026-03-12_rcxenginenew_full_spec_gap_map.md`
- `reports/codex/runtime_design/vector_2026-03-12_rcxenginenew_seed_implementation_packet_v0.md`
- `mu/docs/core/RCXEngine.v0.md`
- `mu/docs/core/EngineNewsStructural.v0.md`
- `mu/docs/core/EngineNewFixContract.v0.md`
- `mu/docs/core/OperatorExhaustion.v0.md`

## 2. Work Items

### WI-1: Reproduce Gap 1 — Engine State Model

**Gap claim (gap map §Gap 1):** The PDF kernel's formal state model (`G=(V,E)`,
bookkeeping maps `Ω`, `Λ`, `Ξ`, rank `ρ`, `NextID(G)`) is not the canonical
runtime authority. No `RCXEngineState.v1` seed/schema artifact exists.

**Evidence commands:**
```bash
# Check if any engine state schema artifact exists
ls mu/programs/rcx_engine_state* mu/substrate/engine_state* 2>/dev/null
# Check engine_pipeline.py for state model enforcement
grep -n "engine.state\|EngineState\|graph_state\|formal_state" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
# Check what the engine entry ABI actually accepts
grep -n "def run_engine\|def _engine_step\|def run_trace" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
```

**Acceptance:** Finding is CONFIRMED or RESOLVED with evidence. If confirmed,
classify as DEFECT (structural gap) or POLICY_BOUND (intentionally deferred —
escalate to founder for decision).

### WI-2: Reproduce Gap 2 — Scheduler/Operator-Pool Boundary

**Gap claim (gap map §Gap 2):** The PDF includes a strong scheduler model
(`seedOps`, Godel-coded unary maps, finite operator pool per step, strict
lexicographic order, identity-map safeguard, promotion/freeze across the operator
pool). No executable scheduler artifact or loadable seed/program for scheduler
semantics exists.

**Sequencing rationale:** The gap map §Recommended Next Design Slice says "lock
the formal engine state + scheduler boundary first" because "almost every
remaining PDF feature depends on operator identity and run state." The seed
implementation packet §Why This Packet Exists repeats this: "lock formal engine
state + scheduler boundary first." This work item characterizes the scheduler
gap as a Phase A finding; actual seed creation (`rcx_engine_scheduler.v1.json`)
is structural reduction work and belongs in Phase C per the governing queue
(Phase B is host/boundary unification, not seed implementation).

**Evidence commands:**
```bash
# Check if any scheduler seed/program artifact exists
ls mu/programs/rcx_engine_scheduler* mu/programs/rcx_engine_supervisor* 2>/dev/null
# Check for scheduler/operator-pool logic in engine pipeline
grep -n "scheduler\|operator.pool\|seedOps\|lexicographic\|operator.*order" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
# Inspect the run_algorithm boundary chokepoint — the seed implementation packet
# (§356-363) names this as the scheduler-entry surface ("reuse the existing
# generic run_algorithm boundary operation; widen the authorized seed list only
# enough to admit the new scheduler").
# Python: allowlist + dispatch handler + dispatch map
grep -n "_ALGORITHM_SEED_ALLOWLIST\|_boundary_op_run_algorithm\|_BOUNDARY_DISPATCH\|run_algorithm" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
# JS parity: allowlist + dispatch handler + dispatch map
grep -n "_ALGORITHM_SEED_ALLOWLIST\|boundaryOpRunAlgorithm\|BOUNDARY_DISPATCH\|run_algorithm" mu/host/js/engine/pipeline.js
# Check JS parity for scheduler surface beyond run_algorithm
grep -n "scheduler\|operator.pool\|seedOps\|lexicographic" mu/host/js/engine/pipeline.js mu/host/js/engine/routing.js
# Check exhaustion seed for operator-pool freeze surface
grep -n "operator\|frozen\|freeze\|pool" mu/closures/exhaustion.v1.json
# Check if any scheduler-related test artifacts exist
ls mu/tests/structural/test_rcx_enginenew_scheduler* mu/tests/fixtures/rcx_enginenew_scheduler* 2>/dev/null
# Seed-path truth vs bootstrap-fallback validation — the seed implementation
# packet (§115-121) states: _run_sub_algorithm() iterates the seed,
# run_algorithm_meta_circular() uses structural mode by default, and bootstrap
# fallback is explicit debug-only behavior. The exit criteria (§446-451) require
# that the seed path is real and bootstrap fallback is not the only passing path.
# Python: verify _run_sub_algorithm is the execution path after dispatch
grep -n "_run_sub_algorithm\|run_algorithm_meta_circular" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
# Python: check for structural-mode defaulting and debug-only fallback paths
grep -n "structural_mode\|debug_only\|fallback\|bootstrap.*mode\|mode.*structural" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
# JS: verify runSubAlgorithm is the execution path after dispatch
grep -n "runSubAlgorithm\|runAlgorithmMetaCircular" mu/host/js/engine/pipeline.js
# JS: check for structural-mode defaulting and debug-only fallback paths
grep -n "structural_mode\|structuralMode\|debug_only\|debugOnly\|fallback\|bootstrap.*mode" mu/host/js/engine/pipeline.js
```

**Acceptance:** Produce a classified finding characterizing: (a) what scheduler
semantics currently live in host code vs. seed code, (b) what
`run_algorithm`/`_ALGORITHM_SEED_ALLOWLIST` chokepoint currently enforces as the
scheduler-entry boundary (Python `engine_pipeline.py:726-750`, JS
`pipeline.js:253-279`), (c) what operator-identity model exists (if any),
(d) what the gap is between current state and the PDF scheduler model,
(e) whether `_run_sub_algorithm` (Python) / `runSubAlgorithm` (JS) is the actual
post-dispatch execution path and whether it runs the seed or a host fallback,
(f) whether `run_algorithm_meta_circular` uses structural mode by default and
whether bootstrap fallback is debug-only as stated by the seed implementation
packet (§115-121). Classify as DEFECT (structural gap requiring seed-first
implementation) or POLICY_BOUND (intentionally deferred — escalate to founder
for decision).

### WI-3: Reproduce Gap 5 — Terminal Semantics

**Gap claim (gap map §Gap 5):** Run-level failure/restart semantics
(`hash_error`, `globalstall`, restart protocol, run-id separation) are not fully
surfaced. Engine exit reasons are narrower than the PDF specifies.

**Canonical terminal-semantics authority surfaces:**
- Python: `mu/host/python/rcx_pi/selfhost/step_mu.py` — `classify_terminal_kind`
- JS: `mu/host/js/core/terminal_classification.js` — `deriveEngineExitReason`, `classifyTerminalKind`
- Engine pipeline wrappers: `engine_pipeline.py` (Python), `pipeline.js` (JS)

**Evidence commands:**
```bash
# Terminal classification authority — Python
grep -n "classify_terminal_kind\|derive_engine_exit_reason\|exit_reason\|terminal" mu/host/python/rcx_pi/selfhost/step_mu.py
# Terminal classification authority — JS
grep -n "deriveEngineExitReason\|classifyTerminalKind\|exit_reason\|terminal" mu/host/js/core/terminal_classification.js
# Outer pipeline terminal/exit surface (wrapper, not authority)
grep -n "exit_reason\|terminal\|globalstall\|hash_error\|restart" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
# JS pipeline terminal surface
grep -n "exit_reason\|terminal\|globalstall\|hash_error" mu/host/js/engine/pipeline.js
# L4 gate coverage for terminal semantics (exit reason + terminal event gates)
PYTHONHASHSEED=0 python3 -m pytest tests/l4_gates/test_engine_exit_reason_gate.py tests/l4_gates/test_engine_terminal_event_gate.py -v --tb=short 2>&1 | tail -30
# Dedicated terminal classification and displacement gates
PYTHONHASHSEED=0 python3 -m pytest tests/l4_gates/test_terminal_classification_parity_gate.py tests/l4_gates/test_terminal_semantics_displacement_gate.py -v --tb=short 2>&1 | tail -30
```

**Acceptance:** Produce a classified finding: which terminal paths are covered by
L4 gates (including the dedicated terminal-classification parity gate and
terminal-semantics displacement gate) vs. which are gap map holes still open.
Characterize whether terminal authority lives in the structural classification
functions (`classify_terminal_kind` / `classifyTerminalKind`) or in host wrapper
code.

### WI-4: Reproduce Gap 7 — Workload Corpus Coverage

**Gap claim (gap map §Gap 7):** The workload corpus is too small for a full-PDF
claim. Current vectors are limited to `identity_stall`, `constant_closure`,
`no_match_stall`.

**Evidence commands:**
```bash
# Read the canonical workload vector manifest (source of truth)
python3 -c "import json; d=json.load(open('mu/tests/fixtures/rcx_engine_workload_contract.json')); [print(v['id'], '-', v['description']) for v in d['vectors']]"
# Verify parity test loads from the canonical manifest
grep -n "VECTORS_PATH\|rcx_engine_workload_contract" tests/parity/test_rcx_engine_workload_contract_parity.py
# Run the canonical workload parity test to confirm current coverage
PYTHONHASHSEED=0 python3 -m pytest tests/parity/test_rcx_engine_workload_contract_parity.py -v --tb=short 2>&1 | tail -20
# Count engine test cases across all engine test dirs
PYTHONHASHSEED=0 python3 -m pytest mu/tests/engine/ --collect-only 2>&1 | tail -5
# Check for any new vectors added since the gap map (2026-03-12)
git log --since="2026-03-12" --oneline -- mu/tests/fixtures/rcx_engine_workload_contract.json mu/tests/engine/ tests/engine/
# Research-integrity evidence shape — the seed implementation packet (§83-94,
# §466-473) requires widened EngineNew claims to survive negative controls,
# ablation/removal tests, and parity on the seed path. A given-for-free ledger
# must enumerate what the host implicitly provides.
# Check for negative control tests in engine/research test dirs
grep -rn "negative.control\|negative_control\|stall.*expected\|non.convergence\|null.emergence" mu/tests/engine/ mu/tests/research/ tests/engine/ 2>/dev/null | head -20
# Check for ablation/removal test cases
grep -rn "ablation\|removal\|remove.*seed\|without.*operator" mu/tests/engine/ mu/tests/research/ tests/engine/ 2>/dev/null | head -20
# Check for given-for-free ledger artifacts
ls mu/docs/core/*given_for_free* mu/docs/core/*host_implicit* mu/tests/fixtures/*given_for_free* 2>/dev/null
grep -rn "given.for.free\|host.implicit\|implicitly.provided" mu/docs/core/ mu/tests/fixtures/ 2>/dev/null | head -10
# Verify whether workload vectors have paired negative controls
python3 -c "import json; d=json.load(open('mu/tests/fixtures/rcx_engine_workload_contract.json')); [print(v['id'], '- has_negative:', v.get('negative_control', 'MISSING')) for v in d['vectors']]"
```

**Acceptance:** Produce an inventory of current workload vectors from the
canonical manifest (`mu/tests/fixtures/rcx_engine_workload_contract.json`)
mapped to gap map requirements. Identify which PDF workload paths (ω emergence,
P(x) subset closure, fork motif, operator-pool freeze, hash-error) have no
coverage. Additionally, characterize the research-integrity evidence shape
required by the seed implementation packet (§83-94, §466-473): (a) whether
negative controls exist for current workload vectors, (b) whether
ablation/removal test cases exist that verify behavior changes when a component
is removed, (c) whether a given-for-free ledger enumerates host-implicit
provisions. Classify missing research-integrity artifacts as DEFECT (structural
gap — widened claims cannot survive without negative controls per the packet's
own validity conditions §83-94).

### WI-5: Cross-Substrate Parity Check and Ratchet Verification

**Purpose:** Verify Python/JS engine alignment is current before any fixes, and
confirm host-authority inventory has not regressed.

**Evidence commands:**
```bash
# JS parity (all 10 seed checks)
node mu/host/js/eval_step.js
# Engine-scoped parity tests only (17 tests, not the full 931-test parity suite)
PYTHONHASHSEED=0 python3 -m pytest tests/parity/test_rcx_engine_parity.py tests/parity/test_rcx_engine_workload_contract_parity.py -v --tb=short 2>&1 | tail -20
# Host-authority inventory ratchet (hard constraint proof)
python3 tools/checks/check_host_authority_inventory_ratchet.py
# Host-semantics ratchet (hard constraint — §3 requires no increase)
python3 tools/checks/check_host_semantics_ratchet.py
# Bootstrap-purity ratchet (hard constraint — §3 requires no new host capabilities)
python3 tools/checks/check_bootstrap_purity_ratchet.py
```

**Scope note:** This slice covers engine-pipeline gaps only, so the parity gate
is scoped to the two engine-specific parity test files (17 tests), not the full
`tests/parity/` tree (931 tests). Repo-wide parity is validated by CI and
`audit_all.sh`, not by this slice.

**Acceptance:** All five commands pass. Any engine parity failure,
host-authority inventory increase, host-semantics ratchet increase, or
bootstrap-purity ratchet failure becomes a blocking finding.

### WI-6: Produce Classified Findings Report

**Purpose:** Synthesize WI-1 through WI-5 into a single classified findings
section appended to this plan (below the plan sections).

**Classification scheme (CLAUDE.md behavioral rule 4):**
- `DEFECT`: structural gap that violates an existing invariant or contract,
  including missing test/evidence for a claimed capability and host semantics
  doing work that should be structural
- `POLICY_BOUND`: gap is intentional or requires a founder decision before
  proceeding — escalate per CLAUDE.md rule 5
- `DOC_ACCURACY`: documentation states something inconsistent with code truth

**Acceptance:** Each finding has: classification, file(s), evidence command output,
and a one-line fix direction. Findings are input to downstream queue phases
(Phase B for host/boundary unification, Phase C for structural reduction into
Mu), not automatic implementation in this wave.

## 3. Constraints

### NOT in scope for this slice

- **Gaps 3, 4, 6, 8** from the gap map (legality rules, closure family,
  environment flags, program boundary). These are larger and will be separate
  Phase A slices.
- **Seed implementation work** (no new `rcx_engine_supervisor.v1.json` or
  `rcx_engine_scheduler.v1.json` creation). This slice characterizes gaps as
  findings; actual seed creation is structural reduction work and belongs in
  Phase C per the governing queue (Phase B is host/boundary unification).
- **New host semantics.** Any fix must reduce or tighten, not add host power.
  Enforced by `check_bootstrap_purity_ratchet.py` and `check_host_semantics_ratchet.py`.
- **Phase B or commit flow.** This slice produces findings + bounded fixes only.
  Phase B is a separate executor invocation.
- **Docs-only changes** unless a doc contract is broken by a code fix.

### Hard constraints

- Host semantics ratchet must not increase (currently PASS, 0 increases).
- Host authority inventory must not increase (currently 312/312 total, 217/217 authority).
- L3 parity must remain intact (JS `eval_step.js` all 10 checks pass).
- All fixes must be structural reductions or parity-preserving boundary tightening
  per CLAUDE.md rule 11.

## 4. Stop Conditions

Stop this slice when ANY of the following is true:

1. All 6 work items are complete (findings classified, parity verified).
2. A blocking parity failure is discovered that requires its own wave.
3. A host semantics ratchet increase is discovered in existing code (escalate to
   founder as DEFECT before proceeding).
4. A host-authority inventory increase is discovered (escalate to founder as
   DEFECT before proceeding). Proof command:
   `python3 tools/checks/check_host_authority_inventory_ratchet.py`.
5. The sweep reveals that the gap map (2026-03-12) is materially outdated — more
   than 50% of Gaps 1/2/5/7 have been resolved since the map was written.

## 5. Acceptance Criteria

This Phase A slice is DONE when:

- [ ] Gap 1 reproduced or resolved with evidence commands and classification
- [ ] Gap 2 reproduced or resolved with evidence commands and classification
- [ ] Gap 5 reproduced or resolved with evidence commands and classification
- [ ] Gap 7 reproduced or resolved with evidence commands and classification
- [ ] Cross-substrate parity verified (eval_step.js + engine-scoped parity tests pass)
- [ ] Classified findings section appended to this plan with per-finding evidence
- [ ] Host semantics ratchet still PASS after any fixes
- [ ] Host authority inventory still PASS after any fixes (312/312 total, 217/217 authority)
- [ ] No new host capabilities introduced (bootstrap purity ratchet PASS)

## 6. Grounding

### TASKS.md authorization

- **Work item:** `[NEXT-CODEX-POST-REDTEAM]` — UNPARKED (2026-03-28, founder-authorized)
- **Location:** TASKS.md line 463
- **Current phase:** Phase A — structural gap sweep
- **Lane:** structural (post-control-surface)
- **Tracked packet:** `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`

### Governing packet

- **Queue:** `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
  - Status: ACTIVE (unparked 2026-03-28)
  - Phase-A-Lock: UNLOCKED
  - Phase A goal: "find and fix real Mu / Stage0 / runtime structure gaps,
    behavioral errors, proof gaps, and hidden host-side drift"
  - Operating note: "treat new defects as red-team findings first, not as
    automatic implementation work"

### Supporting input packets

- `reports/codex/runtime_design/vector_2026-03-12_rcxenginenew_full_spec_gap_map.md`
  — 8 identified gaps between current runtime and full PDF spec
  — §Recommended Next Design Slice: "lock the formal engine state + scheduler
    boundary first"
- `reports/codex/runtime_design/vector_2026-03-12_rcxenginenew_seed_implementation_packet_v0.md`
  — seed-first implementation plan for the engine gap closure
  — §Why This Packet Exists: "lock formal engine state + scheduler boundary first"
  — §Promotion Criteria: "founder agrees that the first slice is supervisor +
    scheduler, not another recurrence/fix refinement"

### Sequencing alignment

Both governing design packets specify that the first slice must address formal
engine state (Gap 1) and scheduler boundary (Gap 2) together, because nearly all
remaining PDF features depend on operator identity and run state. This plan
includes both gaps in Slice 1 as Phase A findings (characterization and
classification), with actual seed implementation deferred to Phase C (structural
reduction into Mu) per the governing queue's phase sequence.

### Pre-conditions verified

- Merge SHA `11a0393020318924162431203cbc0f65b7e9d8e4` reachable from HEAD
- Host semantics ratchet: PASS (0 increases)
- JS parity: all 10 checks pass
- No active blocking reports in `reports/deferred/blocking/`

---

## Bridge Review History

### R1 (bridge job phase-a-r1-d9c6ac64)

**Decision:** REQUEST_CHANGES (reviewer: codex gpt-5.4 xhigh)

**Findings addressed:**

1. **DEFECT (high, blocking):** Slice 1 was mis-sequenced by excluding Gap 2
   (scheduler boundary). Both governing packets say the first slice must lock
   formal engine state + scheduler boundary first.
   **Resolution:** Added Gap 2 to slice scope, added WI-2 for scheduler boundary
   characterization, updated constraints/acceptance/stop conditions accordingly.

2. **DEFECT (high, blocking):** WI-3 evidence commands searched test directories
   instead of the canonical workload manifest at
   `mu/tests/fixtures/rcx_engine_workload_contract.json`.
   **Resolution:** Rewrote WI-4 (formerly WI-3) evidence commands to read the
   canonical manifest first, run the parity test, and check git history on the
   manifest file. Added both canonical files to §1 scope.

3. **DOC_ACCURACY (low, non-blocking):** TASKS.md line reference off by one
   (462 → 463).
   **Resolution:** Fixed to line 463.

### R2 (bridge job phase-a-r1-b3d2046b)

**Decision:** REQUEST_CHANGES (reviewer: codex gpt-5.4 xhigh)

**Findings addressed:**

1. **DEFECT (high, blocking):** Pytest evidence commands are non-executable as
   written because they omit `PYTHONHASHSEED=0`. The repo test harness aborts
   with `RuntimeError: PYTHONHASHSEED must be '0' for deterministic tests`.
   Reproduced on WI-3, WI-4, and WI-5 commands.
   **Resolution:** Prefixed `PYTHONHASHSEED=0` to every `python3 -m pytest`
   command in WI-3, WI-4, and WI-5 evidence blocks.

2. **DEFECT (medium, blocking):** WI-3 under-scopes Gap 5 by omitting the
   canonical terminal-semantics authority surfaces. Terminal classification
   authority lives in `step_mu.py` (`classify_terminal_kind`) and
   `terminal_classification.js` (`deriveEngineExitReason`,
   `classifyTerminalKind`), not in the outer pipeline wrappers. The dedicated
   gates `test_terminal_classification_parity_gate.py` and
   `test_terminal_semantics_displacement_gate.py` were also missing.
   **Resolution:** Added `step_mu.py` and `terminal_classification.js` to §1
   Runtime scope. Added both dedicated terminal gates to §1 Tests scope. Rewrote
   WI-3 evidence commands to grep canonical terminal authority surfaces first,
   then pipeline wrappers, and to run dedicated terminal gates alongside the
   exit-reason/terminal-event gates. Updated WI-3 acceptance to require
   characterizing whether terminal authority lives in structural classification
   functions vs. host wrapper code.

### R3 (bridge job phase-a-r2-717043ad)

**Decision:** REQUEST_CHANGES (reviewer: codex gpt-5.4 xhigh)

**Findings addressed:**

1. **DEFECT (medium, blocking):** WI-5 uses repo-wide parity (`tests/parity/`,
   931 tests) as a slice gate, so the engine-only Phase A slice is no longer
   bounded. Unrelated parity failures on non-engine surfaces would be treated as
   blocking findings for this engine-scoped slice.
   **Resolution:** Scoped WI-5 evidence commands to the two engine-specific
   parity test files (`test_rcx_engine_parity.py` and
   `test_rcx_engine_workload_contract_parity.py`, 17 tests). Added scope note
   explaining that repo-wide parity is validated by CI/audit_all, not this slice.
   Renamed WI-5 to "Cross-Substrate Parity Check and Ratchet Verification."

2. **DEFECT (medium, blocking):** Host-authority inventory is declared a hard
   constraint (§3) but has no stop-condition escalation path (§4) and no
   acceptance-proof criterion (§5). The slice could claim DONE without proving
   one of its own stated invariants.
   **Resolution:** Added stop condition #4 (escalate host-authority inventory
   increase to founder as DEFECT). Added acceptance criterion for host-authority
   inventory PASS (312/312 total, 217/217 authority). Added
   `check_host_authority_inventory_ratchet.py` to WI-5 evidence commands.

3. **DOC_ACCURACY (low, non-blocking):** R2 bridge history header used job ID
   `phase-a-r1-b3d2046b` where the `r1` prefix is inconsistent with the plan's
   "R2" round label.
   **Resolution:** Prefixed job IDs in bridge history headers with "bridge job"
   to clarify that the ID is from the bridge system's internal naming, distinct
   from the plan's round numbering.

### R4 (bridge job phase-a-r3-6e662ce6)

**Decision:** REQUEST_CHANGES (reviewer: codex gpt-5.4 xhigh)

**Findings addressed:**

1. **DEFECT (high, blocking):** WI-2 misses the actual scheduler-entry boundary
   chokepoint (`run_algorithm` allowlist/dispatch). The governing seed
   implementation packet (§107-119, §356-363) names the existing `run_algorithm`
   boundary and its allowlist as the intended scheduler-entry surface. Live code
   already implements this chokepoint in Python (`engine_pipeline.py:726-750`,
   `_ALGORITHM_SEED_ALLOWLIST` + `_boundary_op_run_algorithm` +
   `_BOUNDARY_DISPATCH`) and JS (`pipeline.js:253-279`,
   `_ALGORITHM_SEED_ALLOWLIST` + `boundaryOpRunAlgorithm` +
   `BOUNDARY_DISPATCH`). WI-2 evidence commands grepped for
   `scheduler|operator.pool|seedOps|lexicographic` but never inspected the
   `run_algorithm` dispatch path.
   **Resolution:** Added evidence commands to WI-2 that grep for
   `_ALGORITHM_SEED_ALLOWLIST`, `_boundary_op_run_algorithm`/
   `boundaryOpRunAlgorithm`, `_BOUNDARY_DISPATCH`/`BOUNDARY_DISPATCH`, and
   `run_algorithm` in both Python and JS. Added inline comment citing the seed
   implementation packet rationale (§356-363). Updated WI-2 acceptance to require
   characterizing the `run_algorithm`/`_ALGORITHM_SEED_ALLOWLIST` chokepoint as
   the scheduler-entry boundary, with specific file:line references.

2. **DEFECT (medium, blocking):** WI-6 findings taxonomy (`PROOF_GAP`,
   `HOST_DRIFT`, `DESIGN_DECISION`) diverges from the repo's canonical
   `DEFECT` / `POLICY_BOUND` / `DOC_ACCURACY` contract (CLAUDE.md behavioral
   rule 4). The `DESIGN_DECISION` label specifically can hide founder-decision
   escalation items that should be classified as `POLICY_BOUND` (which triggers
   founder escalation per CLAUDE.md rule 5).
   **Resolution:** Replaced WI-6 classification scheme with the canonical
   taxonomy from CLAUDE.md rule 4: `DEFECT`, `POLICY_BOUND`, `DOC_ACCURACY`.
   Mapped removed categories: `PROOF_GAP` and `HOST_DRIFT` → `DEFECT` (both are
   structural gaps); `DESIGN_DECISION` → `POLICY_BOUND` (requires founder
   decision). Updated WI-1 and WI-2 acceptance sections to use `POLICY_BOUND`
   instead of `DESIGN_DECISION`.

### R5 (bridge job phase-a-r4-7125da3a)

**Decision:** REQUEST_CHANGES (reviewer: codex gpt-5.4 xhigh)

**Findings addressed:**

1. **DEFECT (medium, blocking):** WI-5 omits the host-semantics and
   bootstrap-purity ratchets that the plan itself requires after any bounded fix.
   WI-5 evidence commands only scheduled three checks (`eval_step.js`, engine
   parity tests, `check_host_authority_inventory_ratchet.py`), but §3 Hard
   Constraints names `check_bootstrap_purity_ratchet.py` and
   `check_host_semantics_ratchet.py` as enforcement, and §5 Acceptance Criteria
   requires both "Host semantics ratchet still PASS" and "bootstrap purity
   ratchet PASS." Without these two commands in the evidence block, the slice
   could claim DONE without proving its own stated invariants.
   **Resolution:** Added `check_host_semantics_ratchet.py` and
   `check_bootstrap_purity_ratchet.py` to WI-5 evidence commands. Updated WI-5
   acceptance from "All three commands pass" to "All five commands pass" with
   explicit failure conditions for each ratchet.

### R6 (bridge job phase-a-r5-86a0dc2e)

**Decision:** REQUEST_CHANGES (reviewer: codex gpt-5.4 xhigh)

**Findings addressed:**

1. **DEFECT (high, blocking):** WI-4 under-specifies Gap 7 by omitting the
   EngineNew research-integrity evidence shape required by the seed
   implementation packet (§83-94, §466-473). WI-4 only inventoried manifest
   vectors, parity, collection count, and git history. The packet's own validity
   conditions require widened EngineNew claims to survive negative controls,
   ablation/removal tests, and a given-for-free ledger — none of which were
   checked by WI-4 evidence commands.
   **Resolution:** Added evidence commands to WI-4 that grep for negative
   control tests, ablation/removal test cases, and given-for-free ledger
   artifacts across `mu/tests/engine/`, `mu/tests/research/`, `tests/engine/`,
   `mu/docs/core/`, and `mu/tests/fixtures/`. Added a command to check whether
   workload vectors in the canonical manifest have paired negative controls.
   Updated WI-4 acceptance to require characterizing the research-integrity
   evidence shape: (a) negative control existence, (b) ablation/removal test
   existence, (c) given-for-free ledger existence. Missing research-integrity
   artifacts are classified as DEFECT per the packet's validity conditions.

2. **DEFECT (medium, blocking):** WI-2 stops at the `run_algorithm`
   allowlist/dispatch layer and omits seed-path truth versus bootstrap-fallback
   validation. The seed implementation packet (§115-121) states that
   `_run_sub_algorithm()` iterates the seed, `run_algorithm_meta_circular()`
   uses structural mode by default, and bootstrap fallback is explicit
   debug-only behavior. The exit criteria (§446-451) require that the seed path
   is real and bootstrap fallback is not the only passing path. WI-2 did not
   verify any of these post-dispatch execution properties.
   **Resolution:** Added evidence commands to WI-2 that grep for
   `_run_sub_algorithm` / `runSubAlgorithm` and `run_algorithm_meta_circular` /
   `runAlgorithmMetaCircular` in both Python and JS, plus structural-mode
   defaulting and debug-only fallback patterns. Updated WI-2 acceptance to
   require characterizing (e) whether `_run_sub_algorithm` / `runSubAlgorithm`
   is the actual post-dispatch execution path and whether it runs the seed or a
   host fallback, and (f) whether `run_algorithm_meta_circular` uses structural
   mode by default with bootstrap fallback being debug-only as stated by the
   packet (§115-121).

### R7 (bridge job phase-a-r6-06f0625f)

**Decision:** REQUEST_CHANGES (reviewer: codex gpt-5.4 xhigh)

**Findings addressed:**

1. **DEFECT (medium, blocking):** Future supervisor/scheduler seed work is
   mis-sequenced into Phase B instead of the queue's Phase C reduction lane.
   The governing queue (`post_redteam_structural_queue_2026-03-20.md`) defines
   Phase B as "host/boundary unification" (compress host semantics into
   chokepoints) and Phase C as "structural reduction into Mu" (reduce the
   narrowed host surface into Mu). Seed creation (`rcx_engine_scheduler.v1.json`,
   `rcx_engine_supervisor.v1.json`) is structural reduction, not boundary
   unification. The plan referenced "Phase B" at WI-2 sequencing rationale
   (line 92-93), WI-6 acceptance (line 266), §3 Constraints (line 276-279),
   and §6 Sequencing alignment (line 360).
   **Resolution:** Changed all four Phase B references for seed creation /
   structural reduction work to Phase C, with inline citations to the governing
   queue's phase definitions. Updated WI-6 acceptance to distinguish downstream
   phases: Phase B for host/boundary unification, Phase C for structural
   reduction into Mu.

---

## Findings (populated after sweep execution)

Sweep executed: 2026-03-30
Executor: Claude Opus 4.6 (Phase A implementer)

---

### Finding F-1: No Engine State Schema Artifact (Gap 1)

**Classification:** DEFECT (structural gap)

**Files:** `mu/programs/` (missing `rcx_engine_state*`), `mu/substrate/` (missing
`engine_state*`), `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`

**Evidence:**
```
$ ls mu/programs/rcx_engine_state* mu/substrate/engine_state* 2>/dev/null
(no output — no artifacts exist)

$ grep -n "engine.state\|EngineState\|graph_state\|formal_state" engine_pipeline.py
526:        state: previous engine state (for identity-stall detection)
780:    """Service a boundary effect request from the engine state machine.
1170:def run_engine_pipeline(  # AST_OK: infra — boundary host loop, services engine state machine
1183:    """Host loop that drives the engine state machine defined in rcx_engine.v1.json.
```

**Characterization:** CONFIRMED. The PDF kernel's formal state model (`G=(V,E)`,
bookkeeping maps `Ω`, `Λ`, `Ξ`, rank `ρ`, `NextID(G)`) has no corresponding
`RCXEngineState.v1` seed or schema artifact. The term "engine state" appears only
in comments and docstrings inside `engine_pipeline.py` (lines 526, 780, 1170,
1183, 1206, 1321). The engine entry ABI (`run_engine_pipeline` at line 1170,
`run_engine_with_routing` at line 1530) accepts raw projections and input values
with no formal state type enforcement. The `rcx_engine.v1.json` seed (11
projections) defines an engine *cycle* (init → trace → hash → fix → recurrence →
exhaustion → unwrap) but not an engine *state model* with graph topology,
bookkeeping maps, or rank invariants.

**Fix direction:** Phase C structural reduction — create `rcx_engine_state.v1.json`
seed that encodes the formal state model as projections, making the state model
a loadable Mu artifact rather than implicit host-side convention.

---

### Finding F-2: No Scheduler Seed or Operator-Pool Artifact (Gap 2)

**Classification:** DEFECT (structural gap)

**Files:** `mu/programs/` (missing `rcx_engine_scheduler*`,
`rcx_engine_supervisor*`), `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
(lines 726–750), `mu/host/js/engine/pipeline.js` (lines 253–279),
`mu/closures/exhaustion.v1.json`

**Evidence:**
```
$ ls mu/programs/rcx_engine_scheduler* mu/programs/rcx_engine_supervisor* 2>/dev/null
(no output — no artifacts exist)

$ grep -n "scheduler|operator.pool|seedOps|lexicographic|operator.*order" engine_pipeline.py
(no output — no scheduler terms in Python engine pipeline)

$ grep -n "scheduler|operator.pool|seedOps|lexicographic" pipeline.js routing.js
(no output — no scheduler terms in JS)

$ ls mu/tests/structural/test_rcx_enginenew_scheduler* mu/tests/fixtures/rcx_enginenew_scheduler*
(no output — no scheduler test artifacts exist)
```

**Scheduler-entry boundary characterization (run_algorithm chokepoint):**

The `run_algorithm` boundary dispatch is the existing scheduler-entry surface:

- **Python** (`engine_pipeline.py:726–750`): `_ALGORITHM_SEED_ALLOWLIST` is a
  frozen set of 4 authorized seeds (`recurrence.v1.json`, `recurrence.v2.json`,
  `exhaustion.v1.json`, `fix.v1.json`). `_boundary_op_run_algorithm` (line 736)
  validates the request, checks the allowlist, loads the seed, and calls
  `_run_sub_algorithm` (line 750).
- **JS** (`pipeline.js:253–279`): `_ALGORITHM_SEED_ALLOWLIST` is a frozen object
  with the same 4 seeds. `boundaryOpRunAlgorithm` (line 260) performs identical
  validation and calls `runSubAlgorithm` (line 278).
- Both substrates have parity on the dispatch map: `_BOUNDARY_DISPATCH` /
  `BOUNDARY_DISPATCH` maps `run_algorithm` → the handler function.

**Post-dispatch execution path (seed-path truth):**

- **Python** (`step_mu.py:1824`): `_run_sub_algorithm` iterates the seed via
  `run_algorithm_meta_circular` (line 1844), which defaults to
  `execution_mode="structural"` (line 1391) and uses `step_kernel_mu` with
  `kernel_mode="bridge"` (line 1426). Bootstrap fallback requires explicit
  `execution_mode="bootstrap"` AND `allow_bootstrap_fallback=True` (line 1433) —
  it is disabled by default with a SECURITY error.
- **JS** (`pipeline.js:152`): `runSubAlgorithm` iterates the seed via
  `runAlgorithmWithBridge` (line 156), which runs through `_stepKernelCore`
  (line 135). No bootstrap fallback path exists in JS at all.

**Seed-path truth verdict:** The seed path is real and is the default execution
path in both substrates. Bootstrap fallback is explicit debug-only in Python and
absent in JS. This satisfies the seed implementation packet (§115-121) exit
criteria (§446-451).

**Operator-identity model:** The `exhaustion.v1.json` seed contains extensive
operator/frozen/freeze/pool semantics (operator extraction, frozen-list
management, freeze detection). However, no scheduler artifact governs operator
*ordering* (seedOps, Godel-coded unary maps, lexicographic order) or operator
*identity* across the full engine cycle. The operator-pool model lives entirely
in the exhaustion seed's projection patterns, not in a standalone scheduler.

**Characterization:** CONFIRMED. The PDF scheduler model (seedOps, Godel-coded
unary maps, finite operator pool per step, strict lexicographic order,
identity-map safeguard, promotion/freeze) has no executable artifact. The
existing `run_algorithm` chokepoint provides a security boundary (allowlist +
dispatch) but not scheduling semantics. Operator identity is partially modeled
in `exhaustion.v1.json` but without cross-cycle ordering or promotion logic.

**Fix direction:** Phase C structural reduction — create
`rcx_engine_scheduler.v1.json` seed encoding operator ordering, pool management,
and promotion/freeze lifecycle. The `run_algorithm` allowlist would be widened to
admit the scheduler seed per the seed implementation packet (§356-363).

---

### Finding F-3: Terminal Semantics — Partial Coverage (Gap 5)

**Classification:** DEFECT (structural gap — partial) + partially RESOLVED

**Files:** `mu/host/python/rcx_pi/selfhost/step_mu.py` (lines 42–43, 150–190),
`mu/host/js/core/terminal_classification.js` (lines 60–66, 122–235),
`mu/host/python/rcx_pi/selfhost/engine_pipeline.py`,
`mu/host/js/engine/pipeline.js`

**Evidence — Terminal authority surface:**

Terminal classification authority lives in *structural* classification functions,
not host wrapper code:

- **Python** (`step_mu.py:161`): `classify_terminal_kind` dispatches to
  `terminal_classify.v1.json` seed projections via `eval_step()` (line 169).
  Key sets are seed-derived (line 64, `_load_tc_key_sets`). Terminal kinds:
  `kernel_done`, `recurrence_terminal`, `exhaustion_terminal`, `engine_terminal`,
  `non_terminal`.
- **JS** (`terminal_classification.js:219`): `classifyTerminalKind` mirrors
  Python exactly. `deriveEngineExitReason` (line 268) delegates to
  `terminal_classify.v1.json` seed projections. Key sets are seed-derived
  (line 66).

This is a Wave 25 structural displacement achievement — terminal semantics were
moved from hardcoded host sets to seed-derived classification.

**Evidence — L4 gate coverage:**

All 4 terminal-related L4 gates pass:
- `test_engine_exit_reason_gate.py`: 17 passed (exit reasons: closure,
  exhaustion, stall, completed — 4 reasons, both substrates, cross-substrate
  parity)
- `test_engine_terminal_event_gate.py`: 12 passed (terminal event emission,
  exactly-one-terminal invariant, boot1/trampoline parity)
- `test_terminal_classification_parity_gate.py`: 45 passed (seed-derived key
  sets, no hardcoded frozensets, prefilter short-circuit, cache integrity)
- `test_terminal_semantics_displacement_gate.py`: 51 passed (classify parity,
  exit reason parity, seed-derived key set cardinality/correctness)

**Gap map holes still open:**
- `hash_error`: No exit reason or terminal path for hash-error events. The
  engine pipeline handles hash computation inline but `hash_error` is not a
  recognized `engine_exit_reason` value.
- `globalstall`: Not surfaced as a terminal classification or exit reason. The
  engine detects identity stall (hash-based) but does not distinguish
  single-projection stall from global (all-operator) stall.
- `restart protocol / run-id separation`: No restart terminal or run-id tracking
  in either substrate. The engine is single-run; restart semantics are not modeled.

**Characterization:** PARTIALLY RESOLVED. Core terminal classification (5 kinds,
4 exit reasons) is structurally displaced into `terminal_classify.v1.json` with
full L4 gate coverage and cross-substrate parity (125 tests across 4 gates, all
passing). The remaining PDF terminal paths (`hash_error`, `globalstall`, restart
protocol) have no coverage and no structural representation.

**Fix direction:** Phase C structural reduction — extend `terminal_classify.v1.json`
with projections for `hash_error` and `globalstall` terminal kinds. Restart
protocol requires design work (new Phase A slice, Gap 3/6 scope).

---

### Finding F-4: Workload Corpus — 3 Vectors, No Research Integrity Artifacts (Gap 7)

**Classification:** DEFECT (structural gap)

**Files:** `mu/tests/fixtures/rcx_engine_workload_contract.json`,
`tests/parity/test_rcx_engine_workload_contract_parity.py`

**Evidence — Current manifest:**
```
$ python3 -c "... rcx_engine_workload_contract.json ..."
workload.identity_stall - Identity projection stalls immediately; engine produces terminal with stall=true
workload.constant_closure - Constant projection converges to fixed point; engine detects closure and stall
workload.no_match_stall - No-match projection stalls on input; engine detects closure from stall
```

3 vectors. Parity test passes (Python/JS agree on all 3).

**Evidence — Missing PDF workload paths:**
- `ω emergence` (omega emergence): no vector
- `P(x) subset closure`: no vector
- `fork motif`: no vector
- `operator-pool freeze`: no vector (exhaustion seed exists but no workload
  vector exercises it through the engine pipeline)
- `hash-error`: no vector

**Evidence — Research integrity (seed implementation packet §83-94, §466-473):**

```
$ python3 -c "... has_negative ..."
workload.identity_stall - has_negative: MISSING
workload.constant_closure - has_negative: MISSING
workload.no_match_stall - has_negative: MISSING
```

- **Negative controls:** MISSING. No `negative_control` field on any vector.
  One research negative control exists (`mu/tests/research/test_d007_h3_negative_control.py`)
  but it is for hypothesis falsification, not workload contract vectors.
- **Ablation/removal tests:** MISSING. No ablation or removal test cases found
  in `mu/tests/engine/`, `mu/tests/research/`, or `tests/engine/`.
- **Given-for-free ledger:** MISSING. No `given_for_free` or `host_implicit`
  artifacts found in `mu/docs/core/` or `mu/tests/fixtures/`.

**Post-gap-map activity:** 2 commits since 2026-03-12 touched engine test dirs
(P7-c three-way parity harness, Wave 20 fuzz test) but did not add new workload
vectors to the manifest.

**Engine test collection:** 639 tests collected across `mu/tests/engine/` — the
testing surface is broad, but the *canonical workload contract* manifest that
maps to PDF workload paths has only 3 vectors.

**Characterization:** CONFIRMED. The workload corpus is too small for full-PDF
claims. The 3 existing vectors cover basic stall/closure paths only. 5 PDF
workload paths have no coverage. Research-integrity artifacts required by the
seed implementation packet (§83-94) — negative controls, ablation tests,
given-for-free ledger — do not exist. Per the packet's validity conditions
(§466-473), widened EngineNew claims cannot survive without these artifacts.

**Fix direction:** Phase C structural reduction — expand
`rcx_engine_workload_contract.json` with vectors for ω emergence, P(x) subset
closure, fork motif, operator-pool freeze, and hash-error. Add `negative_control`
field to each vector. Create ablation test fixtures. Create
`host_given_for_free_ledger.json` enumerating implicit host provisions.

---

### Finding F-5: Cross-Substrate Parity and Ratchets — ALL PASS

**Classification:** No finding (all gates pass)

**Evidence:**
```
$ node mu/host/js/eval_step.js
All tests passed: true
(12 seeds verified, 10 test suites, 20 parity vectors, 3 security vectors)

$ PYTHONHASHSEED=0 python3 -m pytest tests/parity/test_rcx_engine_parity.py \
    tests/parity/test_rcx_engine_workload_contract_parity.py -v --tb=short
17 passed in 2.88s

$ python3 tools/checks/check_host_authority_inventory_ratchet.py
Current: 312 total (181 Python + 131 JS), 217 authority (120 Python + 97 JS)
Baseline: 312 total, 217 authority
PASS: No new total-inventory or authority-subset sites detected.

$ python3 tools/checks/check_host_semantics_ratchet.py
PASS: No host-semantics footprint increase detected.

$ python3 tools/checks/check_bootstrap_purity_ratchet.py
PASS: Bootstrap purity ratchet OK — no new host capabilities
```

**Characterization:** All 5 checks pass. Engine parity is intact across
substrates. No ratchet regressions. No blocking finding.

---

### Summary Table

| ID | Gap | Classification | Status | Downstream Phase |
|----|-----|---------------|--------|-----------------|
| F-1 | Gap 1: Engine State Model | DEFECT | HISTORICAL — downstream engine-state slice landed per `TASKS.md:396`; do not relist as unresolved | Closed for the landed slice only |
| F-2 | Gap 2: Scheduler Boundary | DEFECT | HISTORICAL — downstream scheduler slice landed per `TASKS.md:396`; do not relist as unresolved | Closed for the landed slice only |
| F-3 | Gap 5: Terminal Semantics | DEFECT (partial) | PARTIALLY RESOLVED — 5 terminal kinds + 4 exit reasons displaced to seed with 125 L4 gate tests passing; hash_error/globalstall/restart still open | Phase C (extend terminal_classify.v1.json) |
| F-4 | Gap 7: Workload Corpus | DEFECT | CONFIRMED — 3 of 8+ needed vectors; no negative controls, no ablation tests, no given-for-free ledger | Phase C (structural reduction) |
| F-5 | Parity + Ratchets | — | ALL PASS — no regression | N/A |

### Stop Condition Evaluation

- **Condition 1 (all 6 WIs complete):** YES — all findings classified, parity verified.
- **Condition 2 (blocking parity failure):** NO — all parity checks pass.
- **Condition 3 (host semantics ratchet increase):** NO — PASS, 0 increases.
- **Condition 4 (host authority inventory increase):** NO — PASS, 312/312 total, 217/217 authority.
- **Condition 5 (gap map >50% outdated):** NO — 3 of 4 gaps fully confirmed, 1 partially resolved. The gap map (2026-03-12) is materially current.
