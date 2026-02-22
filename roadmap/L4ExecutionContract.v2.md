<!-- DOC_STATUS: REFERENCE -->
<!-- DOC_SCOPE: L4 execution wave classification v2 — 3-class model with no-stagnation enforcement -->

# L4 Execution Contract v2

> **Current State**: See [`STATUS.md`](../STATUS.md) for L4 gate snapshot.
> **Authorization**: See [`TASKS.md`](../TASKS.md) for wave tracker sync notes.
> **Scope**: This document defines DESIGN only — wave classification policy, anti-stagnation rules, and enforcement mechanics.

**Supersedes:** [`L4ExecutionContract.v1.md`](L4ExecutionContract.v1.md) (2-class model).

## Purpose

Prevent indefinite L3 stagnation by requiring recurring L4 structural production.
Every wave must be machine-classifiable, auditable, and subject to anti-stagnation quotas.

## Wave Classes (Strict Enum)

### L4_STRUCTURAL — Runtime/Substrate Structural Production

**Required:**
- MUST touch ≥1 file in runtime/substrate directories
- MUST have non-comment executable delta in runtime files
- MUST include changed file under `tests/l4_gates/` (or `mu/tests/l4_gates/`) AND `evidence_command` referencing gate test target (AND rule — both required)
- MUST include `host_semantics_delta_before` and `host_semantics_delta_after` in tracker note
- MUST include `structural_artifact_ref` in tracker note
- MUST include `post_gate_contract_sweep` referencing at least one non-gate test domain (`tests/engine/`, `tests/structural/`, etc.). Gate pass alone is insufficient; cross-contract sweep is mandatory.

**Runtime/substrate directories:**
`mu/host/`, `mu/substrate/`, `mu/closures/`, `mu/bridge/`, `mu/programs/`, `rcx_pi/selfhost/`, `tools/compilers/`

### L4_ENABLER — Tooling/Governance Prerequisite

**Required:**
- MUST NOT touch runtime/substrate directories
- MUST include `target_gate_id`, `evidence_command`, `evidence_delta`
- Must produce concrete prerequisite artifact for a specific gate

**Cannot:** claim `host_semantics_delta` without runtime file changes.

### MAINTENANCE — No L4 Progress

**Required:**
- MUST NOT touch runtime/substrate directories
- MUST include `no_op_proof` and `defer_reason_code` in tracker note
- MUST include `target_gate_id`

**Cannot:** advance L-level or gate completion status.

## Anti-Stagnation Rules

1. **Rolling structural quota:** In every rolling window of the last 3 class-marked waves, ≥1 must be `L4_STRUCTURAL`. Violation fails the checker.

2. **Consecutive MAINTENANCE cap:** Max 1 consecutive MAINTENANCE without an L4_STRUCTURAL or L4_ENABLER wave.

3. **NO_OP throttling:** Same `target_gate_id` cannot use `no_op_proof` twice in the last 3 class-marked waves. Only bypass: `FOUNDER_OVERRIDE:<id>` token.

4. **Fail-closed on missing marker:** If runtime/core files are changed and no wave class marker exists, the checker fails (not skips).

5. **Legacy alias lock:** `L4_CLASS_A` is accepted for historical parsing only. New tracker notes using `L4_CLASS_A` must fail.

6. **Blocker classification:** Every class-marked wave must declare `primary_blocker_class: DESIGN|INTEGRATION|PERFORMANCE` identifying the dominant blocker type for the target gate.

7. **Post-gate contract sweep (L4_STRUCTURAL only):** Gate pass alone is insufficient. `post_gate_contract_sweep` must reference at least one non-gate test domain (e.g., `tests/engine/`, `tests/structural/`). Sweep commands that only reference `tests/l4_gates/` are rejected.

8. **Primary invariant ID (all classes):** Every class-marked wave must declare `primary_invariant_id` from the enum: `INV_BOUND_HOST_TERMINATION`, `INV_TERMINAL_SCHEMA_LOCK`, `INV_CROSS_SUBSTRATE_PARITY`, `INV_STRUCTURAL_FORWARD_MOTION`, `INV_TYPED_FAIL_CLOSED_OUTCOMES`. Unknown values fail.

9. **Progress proof (STRUCTURAL + ENABLER):** Both `progress_proof_before` and `progress_proof_after` are required for L4_STRUCTURAL and L4_ENABLER waves. Values must not be identical (anti-theater). MAINTENANCE is exempt.

10. **Non-structural adjacency cap:** The two most recent class-marked waves cannot both be non-L4_STRUCTURAL. At least one must be L4_STRUCTURAL. Founder override on the current wave grants bypass.

## Founder Override

Format: `FOUNDER_OVERRIDE:<id>` in tracker note (e.g., `FOUNDER_OVERRIDE:2026-02-20-boot1-exception`).

- Grants one explicit exception to any single anti-stagnation rule.
- Checker logs the override with explicit message.
- Replay protection: duplicate override ID in the active window must fail.
- No silent bypass.

## Tracker Sync Note Schema

Required fields by class (machine-parseable `key: value` format):

| Field | L4_STRUCTURAL | L4_ENABLER | MAINTENANCE |
|-------|:---:|:---:|:---:|
| `wave_id` | required | required | required |
| `class` | required | required | required |
| `target_gate_id` (G1-G8) | required | required | required |
| `evidence_command` | required | required | — |
| `evidence_delta` | required | required | — |
| `host_semantics_delta_before` | required | — | — |
| `host_semantics_delta_after` | required | — | — |
| `structural_artifact_ref` | required | — | — |
| `post_gate_contract_sweep` | required | — | — |
| `primary_blocker_class` | required | required | required |
| `primary_invariant_id` | required | required | required |
| `progress_proof_before` | required | required | — |
| `progress_proof_after` | required | required | — |
| `no_op_proof` | — | — | required |
| `defer_reason_code` | — | — | required |
| `founder_override` | optional | optional | optional |

## Enforcement

Machine enforcement via `tools/checks/enforce_l4_execution_contract.py`:

| Mode | Usage | Where |
|------|-------|-------|
| `--staged` | Check staged files | Local (audit_fast, pre-commit) |
| `--range A...B` | Check commit range | CI (green_gate.yml, ci.yml), pre-push |
| `--files f1 f2` | Check explicit file list | Unit tests |

Empty scope policy: if `--wave-id` is provided and staged/range resolves empty, checker fails (cannot certify an empty scope). Without `--wave-id`, empty staged/range is a non-blocking skip with an explicit message.

## References

- [`STATUS.md`](../STATUS.md) — Current L4 status and gate snapshot
- [`TASKS.md`](../TASKS.md) — Wave tracker sync notes
- [`CLAUDE.md`](../CLAUDE.md) — Concise 3-class mirror (L4 Execution Contract section)
- [`L4ExecutionContract.v1.md`](L4ExecutionContract.v1.md) — Superseded 2-class model (historical)
