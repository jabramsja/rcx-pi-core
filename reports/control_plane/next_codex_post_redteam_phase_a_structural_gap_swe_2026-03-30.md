# Next Codex Post-Redteam Phase A: Structural Gap Sweep — Slice 1 (Engine Pipeline)

Date: 2026-03-30
Status: Phase A (design — not yet agent-reviewed or bridge-converged)
Phase-A-Lock: UNLOCKED

## 1. Scope

### First slice target

Engine pipeline and engine-adjacent runtime surfaces. This slice focuses on
Gaps 1, 5, and 7 from the governing gap map — the engine state model, terminal
semantics, and workload corpus — because these are the most concrete,
reproducible, and structurally bounded items that can be swept and fixed without
adding new host semantics.

### Files and directories in scope

**Runtime (read + potential fix):**
- `mu/host/python/rcx_pi/selfhost/engine_pipeline.py` — Python engine loop
- `mu/host/js/engine/pipeline.js` — JS engine parity loop
- `mu/host/js/engine/routing.js` — JS engine routing
- `mu/host/js/engine/kernel.js` — JS engine kernel

**Seeds (read + potential fix):**
- `mu/programs/rcx_engine.v1.json` — engine cycle nucleus (11 projections)
- `mu/closures/fix.v1.json` — structural fix seed
- `mu/closures/exhaustion.v1.json` — exhaustion/freeze seed

**Tests (read + potential new fixtures):**
- `mu/tests/engine/` — engine test suite (18 test files)
- `tests/l4_gates/test_engine_exit_reason_gate.py` — L4 exit reason gate
- `tests/l4_gates/test_engine_terminal_event_gate.py` — L4 terminal event gate
- `tests/l4_gates/test_engine_transition_gate.py` — L4 transition gate
- `tests/engine/` — engine integration tests
- `tests/parity/` — parity tests

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
classify as DEFECT (structural gap) or DESIGN_DECISION (intentionally deferred).

### WI-2: Reproduce Gap 5 — Terminal Semantics

**Gap claim (gap map §Gap 5):** Run-level failure/restart semantics
(`hash_error`, `globalstall`, restart protocol, run-id separation) are not fully
surfaced. Engine exit reasons are narrower than the PDF specifies.

**Evidence commands:**
```bash
# Current terminal/exit reason surface
grep -n "exit_reason\|terminal\|globalstall\|hash_error\|restart" mu/host/python/rcx_pi/selfhost/engine_pipeline.py
# L4 gate coverage for terminal semantics
python3 -m pytest tests/l4_gates/test_engine_exit_reason_gate.py tests/l4_gates/test_engine_terminal_event_gate.py -v --tb=short 2>&1 | tail -30
# JS parity for terminal paths
grep -n "exit_reason\|terminal\|globalstall\|hash_error" mu/host/js/engine/pipeline.js
```

**Acceptance:** Produce a classified finding: which terminal paths are covered by
L4 gates vs. which are gap map holes still open.

### WI-3: Reproduce Gap 7 — Workload Corpus Coverage

**Gap claim (gap map §Gap 7):** The workload corpus is too small for a full-PDF
claim. Current vectors are limited to `identity_stall`, `constant_closure`,
`no_match_stall`.

**Evidence commands:**
```bash
# Count and list engine workload fixture vectors
grep -rn "identity_stall\|constant_closure\|no_match_stall\|engine.*fixture\|workload.*vector" mu/tests/engine/ tests/engine/ 2>/dev/null | head -40
# Count engine test cases
python3 -m pytest mu/tests/engine/ --collect-only 2>&1 | tail -5
# Check for any new vectors added since the gap map (2026-03-12)
git log --since="2026-03-12" --oneline -- mu/tests/engine/ tests/engine/
```

**Acceptance:** Produce an inventory of current workload vectors mapped to gap map
requirements. Identify which PDF workload paths (ω emergence, P(x) subset
closure, fork motif, operator-pool freeze, hash-error) have no coverage.

### WI-4: Cross-Substrate Parity Check

**Purpose:** Verify Python/JS engine alignment is current before any fixes.

**Evidence commands:**
```bash
node mu/host/js/eval_step.js
python3 -m pytest tests/parity/ -v --tb=short 2>&1 | tail -20
```

**Acceptance:** Both commands pass. Any parity failures become blocking findings.

### WI-5: Produce Classified Findings Report

**Purpose:** Synthesize WI-1 through WI-4 into a single classified findings
section appended to this plan (below the plan sections).

**Classification scheme:**
- `DEFECT`: structural gap that violates an existing invariant or contract
- `PROOF_GAP`: missing test/evidence for a claimed capability
- `HOST_DRIFT`: host semantics doing work that should be structural
- `DESIGN_DECISION`: gap is intentional and documented — not a defect

**Acceptance:** Each finding has: classification, file(s), evidence command output,
and a one-line fix direction. Findings are input to a future Phase B slice, not
automatic implementation in this wave.

## 3. Constraints

### NOT in scope for this slice

- **Gaps 2, 3, 4, 6, 8** from the gap map (scheduler, legality rules, closure
  family, environment flags, program boundary). These are larger and will be
  separate Phase A slices.
- **Seed implementation work** (no new `rcx_engine_supervisor.v1.json` or
  `rcx_engine_scheduler.v1.json` creation). That belongs in Phase B or later
  slices per the seed implementation packet.
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

1. All 5 work items are complete (findings classified, parity verified).
2. A blocking parity failure is discovered that requires its own wave.
3. A host semantics ratchet increase is discovered in existing code (escalate to
   founder as DEFECT before proceeding).
4. The sweep reveals that the gap map (2026-03-12) is materially outdated — more
   than 50% of Gaps 1/5/7 have been resolved since the map was written.

## 5. Acceptance Criteria

This Phase A slice is DONE when:

- [ ] Gap 1 reproduced or resolved with evidence commands and classification
- [ ] Gap 5 reproduced or resolved with evidence commands and classification
- [ ] Gap 7 reproduced or resolved with evidence commands and classification
- [ ] Cross-substrate parity verified (eval_step.js + parity tests pass)
- [ ] Classified findings section appended to this plan with per-finding evidence
- [ ] Host semantics ratchet still PASS after any fixes
- [ ] No new host capabilities introduced (bootstrap purity ratchet PASS)

## 6. Grounding

### TASKS.md authorization

- **Work item:** `[NEXT-CODEX-POST-REDTEAM]` — UNPARKED (2026-03-28, founder-authorized)
- **Location:** TASKS.md line 462
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
- `reports/codex/runtime_design/vector_2026-03-12_rcxenginenew_seed_implementation_packet_v0.md`
  — seed-first implementation plan for the engine gap closure

### Pre-conditions verified

- Merge SHA `11a0393020318924162431203cbc0f65b7e9d8e4` reachable from HEAD
- Host semantics ratchet: PASS (0 increases)
- JS parity: all 10 checks pass
- No active blocking reports in `reports/deferred/blocking/`

---

## Findings (populated after sweep execution)

_To be filled by WI-5 after WI-1 through WI-4 complete._
