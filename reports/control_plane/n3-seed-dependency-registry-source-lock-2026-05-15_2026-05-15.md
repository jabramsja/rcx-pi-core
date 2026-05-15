# N3-Seed-Dependency-Registry-Source-Lock-2026-05-15

Date: 2026-05-15
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: n3-seed-dependency-registry-source-lock-2026-05-15
Class: L4_ENABLER
Category: /mu structural parity/source-lock
Phase-A-Lock: LOCKED
Governing Packet: reports/control_plane/n3-seed-dependency-registry-source-lock-2026-05-15_2026-05-15.md
Authorization: FOUNDER_OVERRIDE:n3-seed-dependency-registry-source-lock-2026-05-15

## Scope

This Phase A packet bounds the successor wave that replaces weak seed-dependency string-presence parity with exact Python/JS exported-map source-lock coverage. It is a planning/control-plane packet; implementation must remain downstream of Phase A review and bridge convergence.

Files and directories in scope for the downstream wave:

- `reports/control_plane/n3-seed-dependency-registry-source-lock-2026-05-15_2026-05-15.md`: governing Phase A packet.
- `TASKS.md`: same-wave tracker/authorization line only, if Phase B proceeds and automation requires TASKS-visible grounding.
- `mu/tests/parity/test_seed_loading_parity.py`: primary parity/source-lock test surface.
- `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py`: optional only if replacing an existing weak dependency source-lock check with the same exact helper.
- `reports/l4_wave_indicators/n3-seed-dependency-registry-source-lock-2026-05-15.json`: same-wave indicator artifact.
- Same-wave generated deferred non-blocker only if the standard automation produces one.

Read-only source scope:

- `mu/host/python/rcx_pi/selfhost/seed_integrity.py`: read-only source for the Python exported `SEED_DEPENDENCIES` map.
- `mu/host/js/core/seed_loader.js` for the exported JavaScript `SEED_DEPENDENCIES` map.

## Work Items

1. Keep this packet as the standalone Phase A authority surface for `n3-seed-dependency-registry-source-lock-2026-05-15`, with detector-visible same-wave authorization in the packet.
2. Before implementation or commit automation proceeds, add or mechanically satisfy same-wave TASKS grounding for this wave if the pipeline still requires TASKS-visible tracker authority.
3. Add a test-local Python parity helper that imports Python `SEED_DEPENDENCIES` and obtains JavaScript `SEED_DEPENDENCIES` from `mu/host/js/core/seed_loader.js` through Node or an existing test-local JS helper.
4. Compare exact dependency map key sets and exact dependency lists across Python and JavaScript.
5. Fail the source-lock check on missing keys, extra keys, missing dependency targets, extra dependency targets, order drift where list order remains semantic, and non-array JavaScript dependency values.
6. Preserve existing Python-only referential-integrity and acyclicity coverage.
7. Preserve existing checksum, seed-location, projection-ID, JavaScript-core-subset, and OPROMO locked-set source-lock coverage.
8. Record same-wave indicator metadata and run the required validation commands before commit/PR handoff.
9. Do not relist engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as pending; TASKS.md records those as already landed code truth.

## Constraints

- Do not implement runtime, Stage0, scheduler, seed, registry, checksum, projection, location-map, generated-artifact, or production `/mu` semantic changes in this wave.
- Do not edit runtime loaders, `mu/programs/*.json`, seed JSON, checksum maps, projection registries, seed-location maps, host dependency registries, Stage0, scheduler, or production semantics to make the test pass.
- Do not derive dependency truth from `mu/programs/*.json` prose.
- Do not make Python, JavaScript, or bootstrap host code smarter as a substitute for exact source-lock parity.
- Do not add lambda-driven or AST-theater host semantics.
- Do not widen into Claude-related files, unrelated dirty files, unrelated executor/test changes, or broad repo cleanup.
- This Phase A rewrite does not solve the underlying implementation; it only replaces the stub packet with a bounded plan.

## Stop Conditions

- Stop and route a separate seed-schema/checksum packet if exact dependency source-lock requires changing `mu/programs/*.json`, checksum maps, projection registries, seed-location maps, host dependency registries, runtime loaders, seed JSON, Stage0, scheduler, generated artifacts, or production `/mu` semantics.
- Stop if JavaScript `SEED_DEPENDENCIES` cannot be read through Node or an existing test-local helper without changing production loader semantics.
- Stop if current code truth proves a listed work item is already implemented; remove it from pending work and acceptance criteria instead of relisting it as unresolved.
- Stop before commit if same-wave TASKS authorization is neither detector-visible nor mechanically accepted by the L4 execution contract path.
- Stop and route a precise follow-up automation packet if pipeline execution fails for a recoverable control-plane reason that would otherwise require repeated manual recovery.

## Acceptance Criteria

- The packet contains standalone `Scope`, `Work Items`, `Constraints`, `Stop Conditions`, `Acceptance Criteria`, and `Grounding / Authorization` sections.
- Same-wave authorization is detector-visible in this packet as `FOUNDER_OVERRIDE:n3-seed-dependency-registry-source-lock-2026-05-15`.
- The downstream parity test imports Python `SEED_DEPENDENCIES`, reads JavaScript `SEED_DEPENDENCIES` from `mu/host/js/core/seed_loader.js`, and compares the exported maps exactly.
- The source-lock fails on missing or extra map keys, missing or extra dependency targets, dependency-list order drift where order is semantic, and non-array JavaScript dependency values.
- Existing Python referential-integrity and acyclicity tests remain in force.
- Existing checksum, seed-location, projection-ID, JavaScript-core-subset, and OPROMO locked-set source-lock coverage remains in force.
- No prohibited runtime, seed JSON, registry, Stage0, scheduler, generated artifact, or production semantic surface is changed by this wave.
- Required validations for the downstream implementation pass:
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_seed_loading_parity.py mu/tests/engine/test_seed_registry_consistency.py mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py --tb=short`
  - `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/parity/test_js_parity_automated.py --tb=short`
  - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json`
  - `python3 tools/checks/check_host_authority_inventory_ratchet.py`
  - `./tools/checks/check_docs_consistency.sh`
  - `python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id n3-seed-dependency-registry-source-lock-2026-05-15`

## Grounding / Authorization

- TASKS.md lines 532-536 ground `[NEXT-CODEX-POST-REDTEAM]` as founder-authorized and OPEN, with remaining structural reduction requiring separate bounded packets; the same lines warn not to relist already landed engine-state/scheduler seed, fixture, structural-test, scheduler-parity, or seed-registration work as unresolved.
- TASKS.md line 540 grounds the founder-ordered queue directive: every wave requires a control-plane packet plus a `TASKS.md` tracker entry, and manual pipeline repair must be paired with same-wave mechanical repair or a precise follow-up automation packet.
- The inherited source route is the merged N3 seed-registry authority packet evidence cited by the supervisor request: `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md:221-318` and `reports/control_plane/n3-seed-registry-authority-source-lock-2026-05-14_2026-05-15.md:356-450`.
- This file is the governing Phase A packet for `n3-seed-dependency-registry-source-lock-2026-05-15`.
- Same-wave L4_ENABLER authorization for detector use: FOUNDER_OVERRIDE:n3-seed-dependency-registry-source-lock-2026-05-15.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `n3-seed-dependency-registry-source-lock-2026-05-15`
- Active packet: `reports/control_plane/n3-seed-dependency-registry-source-lock-2026-05-15_2026-05-15.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `44623d0c3655688480d748574d8491a913eabebfd2677c417bd1d4a2be4917ec`
- Indicator artifact: `reports/l4_wave_indicators/n3-seed-dependency-registry-source-lock-2026-05-15.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py mu/tests/parity/test_seed_loading_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/n3-seed-dependency-registry-source-lock-2026-05-15_2026-05-15.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/n3-seed-dependency-registry-source-lock-2026-05-15.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/l4_gates/test_wave_j_arch_gaps_gate.py`
  - `mu/tests/parity/test_seed_loading_parity.py`
  - `reports/control_plane/n3-seed-dependency-registry-source-lock-2026-05-15_2026-05-15.md`
  - `reports/l4_wave_indicators/n3-seed-dependency-registry-source-lock-2026-05-15.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
