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

2. **Consecutive MAINTENANCE cap:** Max 1 consecutive MAINTENANCE without an L4_STRUCTURAL or L4_ENABLER wave. Bypass is allowed only when the current MAINTENANCE note declares both `unblocks_wave_id` and `unblocks_runtime_blocker`, with runtime blocker provenance (`primary_blocker_class` must be `INTEGRATION` or `PERFORMANCE`, and blocker token must be runtime/invariant form such as `RT-*` or `INV_*`).

3. **NO_OP throttling:** Same `target_gate_id` cannot use `no_op_proof` twice in the last 3 class-marked waves. Only bypass: `FOUNDER_OVERRIDE:<id>` token.

4. **Fail-closed on missing marker:** If runtime/core files are changed and no wave class marker exists, the checker fails (not skips).

5. **Legacy alias lock:** `L4_CLASS_A` is accepted for historical parsing only. New tracker notes using `L4_CLASS_A` must fail.

6. **Blocker classification:** Every class-marked wave must declare `primary_blocker_class: DESIGN|INTEGRATION|PERFORMANCE` identifying the dominant blocker type for the target gate.

7. **Post-gate contract sweep (L4_STRUCTURAL only):** Gate pass alone is insufficient. `post_gate_contract_sweep` must reference at least one non-gate test domain (e.g., `tests/engine/`, `tests/structural/`). Sweep commands that only reference `tests/l4_gates/` are rejected.

8. **Primary invariant ID (all classes):** Every class-marked wave must declare `primary_invariant_id` from the enum: `INV_BOUND_HOST_TERMINATION`, `INV_TERMINAL_SCHEMA_LOCK`, `INV_CROSS_SUBSTRATE_PARITY`, `INV_STRUCTURAL_FORWARD_MOTION`, `INV_TYPED_FAIL_CLOSED_OUTCOMES`. Unknown values fail.

9. **Progress proof (STRUCTURAL + ENABLER):** Both `progress_proof_before` and `progress_proof_after` are required for L4_STRUCTURAL and L4_ENABLER waves. Values must not be identical (anti-theater). MAINTENANCE is exempt.

10. **Non-structural adjacency cap:** The two most recent class-marked waves cannot both be non-L4_STRUCTURAL. At least one must be L4_STRUCTURAL. Founder override on the current wave grants bypass.

11. **Indicator artifact (all classes):** Every class-marked wave must include `indicator_artifact_ref` pointing to a JSON artifact in `reports/l4_wave_indicators/<wave_id>.json` and `indicator_collection_command` referencing the canonical collector `tools/metrics/collect_l4_wave_indicators.py`. Artifact must be committed as part of the wave. CLI-level validation checks artifact is in changed files and JSON is valid.

12. **Indicator artifact JSON schema:** Required keys: `repeat_run_speedup_ratio` (float), `parity_diff_count` (int), `net_host_semantic_delta` (int), `step_growth_slope` (float). Boolean values are explicitly rejected (Python `bool` is subclass of `int`).

13. **Bootstrap endgame policy lock (all classes):** Every class-marked wave must declare `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`. This resolves the documented design split between "eliminate bootstrap" and "irreducible bootstrap forever" — the canonical policy is minimal substrate-independent bootstrap. See `L4DecisionCard.v0.md` and `BootstrapStructuralBridge.v0.md` for architectural context.

14. **Boot0 track binding (all classes):** Every class-marked wave must declare `boot0_track_id` from the enum: `N1a`, `N1b`, `N2`, `N3`, `N4`, `N5`, `N6a`, `N6b`, `V1`, `V2`, `V3`, `V4`, `V5` (from `Hex0_Boot0_Checklist.md`). Must also declare `boot0_progress_state` from: `ADVANCE`, `HOLD`, `DEFER`. Unknown values fail.

15. **Indicator provenance (all classes):** Indicator artifact JSON must include provenance keys: `repeat_run_raw_seconds` (array of 2 positive numbers), `step_growth_points` (array of ≥2 objects with strictly increasing `step` and `elapsed_seconds`), `parity_diff_source` (non-empty string), `collection_timestamp_utc` (non-empty string), `collector_version` (non-empty string). Derivation checks: `repeat_run_speedup_ratio` must equal `round(raw[0] / raw[1], 6)`, `step_growth_slope` must be consistent with `step_growth_points`. Boolean values rejected for all numeric fields.

16. **Collector fail-closed policy:** The canonical indicator collector (`tools/metrics/collect_l4_wave_indicators.py`) must exit non-zero if any probe command fails (non-zero exit code) or if parity-diff output cannot be parsed. Silent coercion of failures to zero/default values is prohibited. Collector version ≥2.1.0 enforces this.

17. **RCX-first semantic destination binding (L4_STRUCTURAL):** Every L4_STRUCTURAL wave must declare `workload_target` (enum) to bind runtime changes to an RCX semantic objective, not generic process churn. Valid values: `ontology_promotion`, `rcx_engine_cycle`, `seed_auto_execution`, `execution_layer_truth`, `recurrence_exhaustion`, `host_debt_reduction`.

18. **Workload target proof binding (L4_STRUCTURAL):** When a `workload_target` has registered evidence files in `WORKLOAD_TARGET_EVIDENCE`, the enforcer checks: (a) contract test files exist on disk (hard fail if missing), (b) at least one evidence file appears in the wave's changed files or is referenced in gate scripts (`audit_fast.sh`, `audit_all.sh`, `green_gate.sh`), (c) `evidence_command` references at least one evidence test module name. Targets with empty evidence lists are exempt (proof binding not yet established).

19. **Debt-removal integrity (marker-touch structural waves):** If an `L4_STRUCTURAL` wave changes runtime `@host_*` markers in diff scope, the checker runs `check_host_semantics_ratchet.py --json` and enforces: (a) strict total host-semantics decrease (`current_total < baseline_total`), and (b) zero per-category increases across both substrates (no category swaps such as recursion→iteration or builtin→iteration).

20. **Baseline split-wave requirement (marker-touch structural waves):** If an `L4_STRUCTURAL` wave changes runtime `@host_*` markers, it MUST NOT modify `tools/checks/host_semantics_baseline.json` (or the `mu/`-prefixed equivalent) in the same wave. Baseline updates are bookkeeping and must run as a separate `MAINTENANCE` wave after structural proof is captured.

21. **Semantic marker-removal proof (Rule A4):** For marker-touch `L4_STRUCTURAL` waves, each removed function-level marker must be backed by construct removal in the same function body (deterministic textual extraction): removing `@host_recursion` requires no self-call (A4.1), removing `@host_iteration` requires no loop constructs (A4.2), and removing `@host_builtin` requires no host-builtin call patterns (A4.3). Marker-only removals (marker deleted while construct remains) fail (A4.4).

## Founder Override

Format: `FOUNDER_OVERRIDE:<id>` in tracker note (e.g., `FOUNDER_OVERRIDE:2026-02-20-boot1-exception`).

- Grants one explicit exception to any single anti-stagnation rule.
- Checker logs the override with explicit message.
- Replay protection: duplicate override ID in the active window must fail.
- No silent bypass.

### Comment-Only Runtime Edit Bypass

When ALL of the following conditions hold, `FOUNDER_OVERRIDE` bypasses the fail-closed gate for runtime file changes without a wave class:

1. Tracker note contains valid `FOUNDER_OVERRIDE:<id>`.
2. Runtime diff is **comment/docstring/marker-only** — zero executable delta (verified by AST-aware diff classifier).
3. Tracker note includes `no_op_proof` (explains why the change is non-functional).
4. Tracker note includes `target_gate_id` (which gate the work relates to).
5. Override ID has not been replayed (existing replay protection).
6. Override note is **explicitly wave-bound** — resolved via `--wave-id` (CLI) or equivalent bound-note context. Unbound top-note overrides (stale notes[0] from a prior wave) are fail-closed.

If any condition fails, the checker emits the specific rejection reason and returns FAIL. The classifier handles: Python `#` comments, Python docstring interiors (via `ast` module), inline comment additions (executable portion unchanged), JS `//`/`*`/`/* */` comment lines.

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
| `workload_target` | required (enum) | — | — |
| `no_op_proof` | — | — | required |
| `defer_reason_code` | — | — | required |
| `unblocks_wave_id` | — | — | required for consecutive MAINTENANCE bypass |
| `unblocks_runtime_blocker` | — | — | required for consecutive MAINTENANCE bypass |
| `indicator_artifact_ref` | required | required | required |
| `indicator_collection_command` | required | required | required |
| `bootstrap_endgame_policy` | required | required | required |
| `boot0_track_id` | required | required | required |
| `boot0_progress_state` | required | required | required |
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
