# Unblock the committed fleet cleanup with separate recovery-validator temporary ownership

Date: 2026-09-26
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]
Wave ID: workingrcx-fleet-validator-temp-r1-2026-09-26
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: b21abdccdf5e3cbf19c8a578dae556c077541b8f2c2b10f76880d6707b63513b
Purpose: Authorized control-surface L4_ENABLER continuation on the existing PR branch for the committed fleet cleanup. Correct only the reproduced recovery-validator TMPDIR/pytest-basetemp collision, retain the native provider-isolation probe correction, and land the already-reviewed cleanup commits through the normal native pipeline. No PR exists yet; this is the same feature branch and carrier, not a new checkout or a replacement fleet implementation.

## Scope

Nine exact paths: one recovery-validator source, its tests, the already-native-edited provider-isolation tests, existing task/changelog, preserved prior packet, and current native packet/indicator/advisory. Existing fleet implementation and action artifacts are committed ancestors and remain unchanged.

Files and surfaces in scope:

- TASKS.md -- Keep every existing obligation and the existing row38 cleanup ordering. Record actual validator repair and original cleanup authority; actual public apply/verify and useful-work ownership remain open before Mu.
- CHANGELOG.md -- Bounded source-backed validator correction and native landing evidence only.
- mu/tools/executors/recovery_gate.py -- Correct the demonstrated _run_pytest_targeted_validator temporary-directory ownership collision, retaining external owned temp/cache, explicit basetemp override, repository-write suppression and normal failure reporting.
- mu/tests/tools/test_recovery_gate.py -- Source-backed regression proving the provider guard survives pytest tmp_path initialization through the actual validator; retain current unadmitted-scratch and unchanged-retained-evidence regressions.
- mu/tests/tools/test_pipeline_agent_pager.py -- Retain the native Python-only rcx_pi provider-probe correction already in this worktree. Only directly required corrections for this observed validation; retain marker, xdist topology, detached descendant and exact environment restoration assertions.
- reports/control_plane/workingrcx-fleet-real-retirement-r1-2026-09-23_2026-09-23.md -- Preserve native prior pending-status packet as historical failed-attempt evidence. Do not rewrite its frozen contract or claim its exhausted recovery succeeded.
- reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md -- Native Phase A authors the full packet from this external STUB.
- reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json -- Native current indicator and exact proof bindings.
- reports/deferred/non_blocking/workingrcx-fleet-validator-temp-r1-2026-09-26_bridge_nonblockers.md -- Optional actual non-blocker report only.
- TASKS.md -- tracker-sync authority. The 2026-09-26 tracker sync note for wave `workingrcx-fleet-validator-temp-r1-2026-09-26` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Continue in existing PR branch jabramsja/workingrcx-fleet-real-retirement-r1-2026-09-23 in /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-fleet-real-retirement-r1-20260926, based on exact committed HEAD b914cf0d4012d0fecc4e7c3c99bac2123ff09be6. This branch has no published PR yet; do not create a new WorkingRCX sibling or reconstruct the fleet implementation. Preserve both original commits, original bus .agent_bus-fleet-real-retirement-r1-20260926, all approvals/failure receipts, spent budgets and current two-file native WIP. Read /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX/reports/archive/control_plane/fleet-real-retirement-r1-evidence-2026-09-26/validator_temp_collision_and_preserved_candidate_20260927.json.
2. Reproduce the actual failure before changing source. recovery_gate.py _run_pytest_targeted_validator passes tmp_root as pytest --basetemp while its environment mapping export the same tmp_root as TMPDIR/TMP/TEMP. conftest.py _install_provider_isolation installs provider guards through tempfile.mkdtemp under that directory; the first pytest tmp_path initialization clears basetemp and removes those guards. The failing detached-receiver test uses a safe fake provider; do not call any real provider during tests.
3. Make the smallest source correction that gives pytest's disposable basetemp separate ownership from general temporary files/provider guards. Preserve forced owned scratch outside all checkouts despite inherited PYTEST_ADDOPTS, cache isolation, deterministic environment, genuine failure reporting and finite recovery policy. Do not change root conftest or weaken guards/assertions.
4. Add a focused regression through the actual native validator, not only a mocked argv assertion. Prove the pre-fix directory relationship fails and the corrected relationship retains initialization-time evidence/guards through tmp_path. Run the existing detached receiver test through the corrected native validator as well as the normal targeted suite. Preserve existing retained-native-scratch before/after and environment suppression checks.
5. Retain the already-native-edited pager tests using rcx_pi/worlds/test_worlds_godel_liar.py instead of incidental Cargo-backed archived examples, including useful failure-output diagnostics. Foreground previously reproduced the unchanged archived child failing FileNotFoundError cargo; do not rewrite archived Rust semantics or install packages. All future subprocess launches inherit the complete existing PATH with native gh/rg prefixed; do not replace it with a narrow allowlist.
6. Native Phase A owns full packet; Phase B owns implementation/staging/review; commit executor owns commit/push/PR/CI/merge. Keep explicit positive existing-PR-branch control-surface authorization. Preserve original pending packet/failure evidence without counter reset or unchanged retry loop. Review only the new scoped delta against b914cf0d; retain original approvals for committed fleet ancestors.
7. After normal native landing and sync, the foreground owner must re-read the landed original workingrcx-fleet-real-retirement-r1-2026-09-23 classification/apply plan and execute admitted finite public apply/verify pairs exactly once. Keep all unsafe targets and genuinely missing useful-work owners explicit, then continue the existing Mu task. Do not claim a code merge is physical cleanup or useful-code integration.

## Constraints

- One authoritative native writer; all selected LLM roles Codex gpt-6-astra/max, commit providerless, pager Codex. Root supplies only external STUB and bounded tracker/evidence, never full packet or source edits.
- Only nine declared paths. Existing committed fleet source, classification, plans and evidence remain intact. No runtime/host semantics changes, unrelated hardening, new numbered queue obligation or extra carrier.
- Original terminal receipts, exhausted counters, held WIP/index/journals/stashes and useful-work ownership are immutable. No reset, force, blanket cleanup, skipped tests, downgraded assertions, altered quotas, or old apply replay.
- Use normal launch_wave.py/dispatcher entry. Same existing branch and carrier; correctly scoped new authority is not a reset or reuse of the exhausted old recovery.

## Stop conditions

- Stop with exact evidence if the observed temporary-ownership fix needs writes outside the nine paths, threatens preserved work, or another live writer exists.
- Do not replay the exhausted original recovery or silently change its packet/config/receipts. Diagnose in-scope observed failures; do not add hypothetical blockers.
- Do not execute fleet retirement before exact native merge/sync and fresh checks against the landed authority.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_pipeline_agent_pager.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`

## Acceptance criteria

- The actual native validator preserves its provider guards while pytest initializes tmp_path; the captured failing detached-receiver case passes without weakening its block-marker assertion.
- Focused source-backed regression, existing scratch/retention safeguards, full declared two-file tools suite and docs pass with no runtime or provider policy relaxation.
- Original fleet commits and native pager improvement survive same-branch normal native landing. No new WorkingRCX directory or hanging PR is left by this continuation.
- TASKS and to-do stay synchronized: existing actual cleanup/apply/verify and useful-work disposition remain immediately next, then Mu; no false cleanup closure.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-APPLY-ACTION-RECONCILIATION]; wave id `workingrcx-fleet-validator-temp-r1-2026-09-26`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md`.
- TASKS.md authority: the 2026-09-26 tracker sync note for wave `workingrcx-fleet-validator-temp-r1-2026-09-26` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-validator-temp-r1-2026-09-26

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-validator-temp-r1-2026-09-26`
- Active packet: `reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-fleet-real-retirement-r1-2026-09-23_2026-09-23.md`
  - `reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-validator-temp-r1-2026-09-26 --output reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_pipeline_agent_pager.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/workingrcx-fleet-real-retirement-r1-2026-09-23_2026-09-23.md`, `reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md`, `reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-validator-temp-r1-2026-09-26.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-validator-temp-r1-2026-09-26`
- Active packet: `reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `3191ef604b68fc96ac7bef348c3510bf3716af1461b6267751d3ab6915a2b31b`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider -n 4 --dist worksteal mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_pipeline_agent_pager.py --tb=short && PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/docs --tb=short`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tests/tools/test_recovery_gate.py`, `mu/tools/executors/recovery_gate.py`, `reports/control_plane/workingrcx-fleet-real-retirement-r1-2026-09-23_2026-09-23.md`, `reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md`, `reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tests/tools/test_recovery_gate.py`
  - `mu/tools/executors/recovery_gate.py`
  - `reports/control_plane/workingrcx-fleet-real-retirement-r1-2026-09-23_2026-09-23.md`
  - `reports/control_plane/workingrcx-fleet-validator-temp-r1-2026-09-26_2026-09-26.md`
  - `reports/l4_wave_indicators/workingrcx-fleet-validator-temp-r1-2026-09-26.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
