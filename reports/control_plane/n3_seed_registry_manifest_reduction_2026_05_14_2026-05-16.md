# N3 Seed Registry Manifest Reduction 2026 05 14 2026-05-16

Date: 2026-05-16
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-seed-registry-manifest-reduction-2026-05-14
Wave Class: L4_STRUCTURAL
Phase-A-Lock: LOCKED
FOUNDER_OVERRIDE:n3-seed-registry-manifest-reduction-2026-05-14

## Purpose

Replace the routing stub with a real Phase A plan for the founder-ordered N3 /mu structural registry-manifest reduction. The target is narrow: reduce duplicated Python/JavaScript per-seed registry authority by moving static seed registry truth toward canonical /mu manifest data, or return NO-GO with a direct file:line blocker before implementation.

This packet is not an implementation pass. It authorizes a bounded successor to inspect current code truth, produce a GO/NO-GO decision, and, only if GO remains valid, implement the minimal parity-preserving registry-manifest reduction.

## Scope

Governing packet:
- `reports/control_plane/n3_seed_registry_manifest_reduction_2026_05_14_2026-05-16.md`

Phase A grounding and authorization scope:
- `TASKS.md:358` for the immediately preceding N3 JSON seed-image boundary runtime retry context and its structural artifact references.
- `TASKS.md:359` for `n3-seed-registry-authority-source-lock-2026-05-14`.
- `TASKS.md:360` for `n3-seed-dependency-registry-source-lock-2026-05-15`.

Potential successor implementation scope, subject to current code truth and Phase B review:
- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
- `mu/host/js/core/seed_loader.js`
- `mu/host/js/cli/main.js`
- Canonical /mu manifest/data surface: `mu/seed_registry_manifest.v1.json`
- Focused parity/source-lock tests already named by the current N3 TASKS context: `mu/tests/engine/test_seed_integrity.py`, `mu/tests/parity/test_seed_loading_parity.py`, `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`, and `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py`.

No other files or directories are in scope unless Phase B reproduces a direct file:line blocker requiring an explicitly named same-wave mechanical root fix.

## Work items

1. Re-verify current implementation truth before code changes. Use the TASKS-backed N3 registry/source-lock context as authorization, but do not assume any listed registry item is still unlanded until current code proves it.

2. Identify the duplicated static seed registry authority that still lives in Python and JavaScript host code, if any. The review must distinguish static metadata duplication from legitimate substrate mechanics such as byte reads, checksum verification, JSON parse, shape validation, and generic dependency checks.

3. Define the canonical /mu manifest data contract for any reducible static seed truth. The manifest may carry only static seed metadata needed for lookup by filename, seed byte verification, current seed structure validation, ordered projection IDs from manifest data, seed subdirectory resolution from manifest data, and generic dependency checks.

4. Preserve checksum-before-parse and root-trust ordering. If the successor cannot prove manifest bytes/root trust before host parsing, the correct Phase B result is NO-GO.

5. Keep Python and JavaScript parity strict. Any reduction must remove or demote mirrored duplicated registry authority in both substrates together, or stop as NO-GO.

6. Update only focused tests that prove the bounded manifest reduction and parity/source-lock behavior. Do not use broad baseline-only cleanup as evidence of progress.

7. If pipeline execution breaks, diagnose with direct evidence and include either a same-wave mechanical root fix within the exact failure class or a precise follow-up automation packet. Do not hide pipeline defects behind packet wording.

## Constraints

- Do not make Python or JavaScript smarter.
- Do not add host-only semantics, lambdas, JS arrow adapter theater, dynamic callable hiding, optional overload/sentinel tricks, baseline-only cleanup, or detector evasion.
- Do not keep duplicated host registries as the real source of truth while calling the result a manifest.
- Do not weaken checksum-before-parse or seed integrity controls without a manifest root proof.
- Do not claim `projection_loader` elimination, N3 closure, D010/binary productionization, or full bootstrap productionization.
- Do not edit Stage0, scheduler, Proxy provenance, Claude surfaces, unrelated pipeline machinery, or unrelated docs unless a reproduced same-wave pipeline failure names an exact mechanical root fix.
- Do not add new host-authority sites except for a proven one-to-one structural split that is detector-visible, parity-preserving, and accepted by the host-authority inventory ratchet.
- Do not use this packet as proof that any successor implementation is already complete.

## Stop conditions

Stop and return NO-GO with direct file:line evidence if:
- Current code truth shows no duplicated static seed registry authority remains to reduce.
- A proposed manifest still leaves Python or JavaScript host registry maps as the authoritative source.
- The manifest cannot be verified from trusted bytes/root before parse.
- The change would move seed semantics into host code rather than into canonical /mu data.
- Python and JavaScript would diverge in seed lookup, dependency ordering, projection ID/order validation, checksum ordering, or error semantics.
- The work requires broad runtime refactors, production binary/D010 migration, projection_loader elimination, N3 closure claims, or unrelated control-plane cleanup.
- Host semantics or host-authority ratchets increase without an exact, reviewed, same-wave structural split allowance.
- Any blocking reviewer finding proves a listed work item is already implemented; remove that item from pending work and acceptance criteria instead of re-listing it as unresolved.

## Acceptance criteria

Phase A acceptance for this packet:
- The packet is no longer a stub and contains Scope, Work items, Constraints, Stop conditions, Acceptance criteria, and Grounding / Authorization sections.
- The scope names the governing packet, the exact TASKS grounding lines, and the bounded potential successor files/directories.
- The packet contains detector-visible same-wave authorization via `FOUNDER_OVERRIDE:n3-seed-registry-manifest-reduction-2026-05-14`.
- The packet does not claim implementation completion, N3 closure, projection_loader elimination, D010 productionization, or broad bootstrap productionization.

Successor Phase B acceptance, if this plan is implemented later:
- Current code truth is reproduced before edits and stale packet wording is discarded where it conflicts with code.
- Static seed registry truth is read from canonical /mu manifest data, not duplicated Python/JavaScript host maps.
- Host code remains mechanical: verify manifest bytes/root trust, parse current JSON, validate shape, look up seed metadata by filename, verify seed bytes, validate current seed structure, validate ordered projection IDs from manifest data, resolve seed subdirectories from manifest data, and check dependencies generically.
- Python and JavaScript preserve identical seed loading semantics and parity tests cover the reduced registry authority.
- Integrity/source-lock tests prove checksum-before-parse and manifest-root ordering.
- Host semantics and host-authority inventory checks do not regress, except for an explicit accepted one-to-one structural split.
- Final output includes exact validation commands/results and a direct GO or NO-GO rationale.

## Grounding / Authorization

- `TASKS.md:358` records the preceding N3 JSON seed-image boundary runtime retry and names the seed loader/integrity surfaces that remain the relevant substrate context.
- `TASKS.md:359` records `n3-seed-registry-authority-source-lock-2026-05-14` under `[NEXT-CODEX-POST-REDTEAM]`, with `FOUNDER_OVERRIDE:n3-seed-registry-authority-source-lock-2026-05-14`.
- `TASKS.md:360` records `n3-seed-dependency-registry-source-lock-2026-05-15` under `[NEXT-CODEX-POST-REDTEAM]`, with standing pipeline-bug-fix authorization text and `FOUNDER_OVERRIDE:n3-seed-dependency-registry-source-lock-2026-05-15`.
- This packet is the governing packet for `n3-seed-registry-manifest-reduction-2026-05-14` and provides the wave-bound override line `FOUNDER_OVERRIDE:n3-seed-registry-manifest-reduction-2026-05-14` for same-wave control-surface authorization.
- Before any successor implementation is committed, TASKS must carry a same-wave tracker note or the commit automation must mechanically derive the same-wave override from this packet according to the control-surface authorization rule.

## Required Human-Facing Footer

Questions? Concerns? Thoughts? -- Think hard

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `n3-seed-registry-manifest-reduction-2026-05-14`
- Active packet: `reports/control_plane/n3_seed_registry_manifest_reduction_2026_05_14_2026-05-16.md`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-registry-manifest-reduction-2026-05-14.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Current staged files:
  - `TASKS.md`
  - `mu/host/js/cli/main.js`
  - `mu/host/js/core/seed_loader.js`
  - `mu/host/python/rcx_pi/selfhost/engine_pipeline.py`
  - `mu/host/python/rcx_pi/selfhost/seed_integrity.py`
  - `mu/seed_registry_manifest.v1.json`
  - `mu/tests/engine/test_seed_integrity.py`
  - `mu/tests/l4_gates/test_boundary_dispatch_authority_gate.py`
  - `mu/tests/l4_gates/test_evidence_walker_gate.py`
  - `mu/tests/l4_gates/test_wave11_hardening_gate.py`
  - `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `mu/tests/structural/test_engine_pipeline_discipline.py`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tests/tools/test_l4_execution_contract_enforcement.py`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tests/tools/test_phase_b_executor.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/agents/templates/meta_bridge_task.txt`
  - `mu/tools/checks/enforce_l4_execution_contract.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/n3_seed_registry_manifest_reduction_2026_05_14_2026-05-16.md`
  - `reports/deferred/non_blocking/n3-seed-registry-manifest-reduction-2026-05-14_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/n3-seed-registry-manifest-reduction-2026-05-14.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->
