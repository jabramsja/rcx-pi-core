---
description: "L4 execution contract classes, requirements, and anti-stagnation rules"
globs: ["roadmap/*", "tools/checks/enforce_l4*", "tools/checks/check_host*"]
---

**Canonical policy:** `roadmap/L4ExecutionContract.v2.md`. Machine-enforced by `tools/checks/enforce_l4_execution_contract.py`.

| Class | Meaning | Key Requirements |
|-------|---------|-----------------|
| `L4_STRUCTURAL` | Runtime/substrate production | MUST touch runtime dirs + `tests/l4_gates/` + `host_semantics_delta` + `evidence_command` + `post_gate_contract_sweep` |
| `L4_ENABLER` | Tooling prerequisite for gate | MUST NOT touch runtime dirs. Requires `target_gate_id` + `evidence_command` + `evidence_delta` |
| `MAINTENANCE` | No L4 progress | MUST NOT touch runtime dirs. Requires `no_op_proof` + `defer_reason_code`. Max 1 consecutive. |

**All classes require:** `primary_blocker_class` + `primary_invariant_id` + `indicator_artifact_ref` + `indicator_collection_command` + `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP` + `boot0_track_id` + `boot0_progress_state`.

**Semantic policy lock:** `mu/docs/core/NorthStarSemantics.v0.md` is canonical for undefined-as-structure, zero canonicalization, bounded non-closure, and routing tie-break policies.

**Anti-stagnation:** Rolling structural quota (>=1 STRUCTURAL per 3 waves). Non-structural adjacency cap. Founder override: `FOUNDER_OVERRIDE:<id>`.

**Related policies (read on demand):**
- L4 Parity-Floor: fix L3 gaps only if they invalidate L4 gate evidence
- L4 Momentum Guardrails: evidence-or-NO-OP per wave, ratio cap, SINK expiry
- Codex→Claude Prompt Contract: every multi-wave prompt requires: Preflight gate, Primary uncertainty, Allowed/forbidden scope, Evidence delta, Stop conditions, Validation gates, Push/merge block. Governance ratio cap: no more than 1 governance/docs-only wave without an evidence wave. WIP cap: max 2 concurrent NEXT workstreams.
