# Fresh WorkingRCX Fleet Census R3 and Codex Astra Defaults

Date: 2026-09-11
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [FLEET-CLEANUP-CENSUS-R3]
Wave ID: workingrcx-fleet-census-r3-2026-09-11
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 82a2a969740437d31c0dc57ceace3f6e3340a983e22db37030a343eb248e9fe1
Purpose: Land the queued fresh read-only WorkingRCX fleet census so preservation-first classification can start, and persist the founder's already-active Codex gpt-6-astra/max selection without inserting another wave.

## Scope

Fresh read-only fleet enumeration and focused tests; three Codex default fields, their existing fallback and regression expectation; exact census and generated governance artifacts only.

Files and surfaces in scope:

- mu/tools/executors/workingrcx_fleet_census.py and mu/tests/tools/test_workingrcx_fleet_census.py
- mu/tools/executors/executor_config.json and executor_common.py: only Codex display_name/model/reasoning_effort defaults; test_bridge_config_model_sync.py: matching expected defaults
- reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json, TASKS.md, CHANGELOG.md and this wave's builder-generated packet/indicator and optional nonblocker artifact
- TASKS.md -- tracker-sync authority. The 2026-09-11 tracker sync note for wave `workingrcx-fleet-census-r3-2026-09-11` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Implement a small read-only CLI with --fleet-root, --anchor-repo and --output. Enumerate direct case-insensitive WorkingRCX* sibling entries plus paths returned by the anchor's git worktree list --porcelain -z; union duplicate paths while retaining provenance. Do not perform an additional recursive filesystem census.
2. Record action-time paths, entry kind, registration/inspection status and available Git root/common-dir/HEAD/branch plus dirty-status/count evidence using read-only Git with optional locks disabled. Distinguish standalone repositories, linked worktrees, non-repositories, missing entries and uncertainty without treating inspection failures as clean. Preserve path data without silent lossy decoding, but do not copy file contents or bulk dirty-file listings. Every row is UNCLASSIFIED. A failed top-level enumeration must not claim complete coverage; per-target inspection errors remain explicit records.
3. Write only the declared new census artifact. Record observation timing and that this is an observation, not a coherent deletion-safety snapshot or authorization. Do not fetch, inspect processes/GitHub, decide safety, or mutate any enumerated target. Fresh metadata observations are allowed; importing old census reports, code or findings is not.
4. Set bridge_agent_defaults.codex to display_name 'Codex GPT-6 Astra max', model 'gpt-6-astra', reasoning_effort 'max' in the registry and its existing executor_common fallback. Update only the matching committed-default regression expectation/name. Preserve all-Codex role routing and every other provider/default.
5. Test the public CLI/data behavior on temporary fixtures for union coverage, a dirty repository, non-repository/missing entries and explicit inspection failure. Run the declared tests and fresh census in this new carrier. Update TASKS/CHANGELOG honestly: R4 landed, census pending until merge, classification immediate next; keep all preserved attempts noncomplete and maintain existing downstream order.

## Constraints

- Use this fresh carrier from the verified exact R4 merge. Do not resume, copy, adopt, delete, or modify fleet census R1/R2 or any stopped native-stub/retry carrier, bus, packet, staged bytes or report.
- No fleet archive/delete/cleanup, PR disposition, remote ref changes, pipeline redesign, generalized path/locking protocol, runtime or Mu changes. No hypothetical hardening or new precursor queue slots.
- Only the committed R3 census may feed the already-queued classification; only its landed decision plan may feed apply. All later terminal mutations remain subject to execute_terminal_mutation_once with fresh fetch and behind(origin/dev)=0 inside the exact mutation callback.
- Keep all model-bearing roles Codex gpt-6-astra/max; do not modify historical reviews, provider menu entries for other providers, Claude-owned surfaces or R4's already-locked candidate.

## Stop conditions

- Stop if the exact predecessor merge is not established or the candidate would reuse a preserved census attempt.
- Stop on a requested target mutation, out-of-allowlist implementation, hidden enumeration failure, or attempt to claim cleanup/safety from the census.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py mu/tests/tools/test_bridge_config_model_sync.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_census.py --fleet-root /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal --anchor-repo . --output reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-census-r3-2026-09-11 --wave-class L4_ENABLER`

## Acceptance criteria

- The declared tests pass and a fresh parseable census artifact covers both required enumeration sources, retains unknown/error records, and labels every result UNCLASSIFIED.
- No enumerated directory, Git index/ref, preserved packet/evidence or GitHub PR is modified by census execution; only the declared output is written.
- The Codex registry and existing fallback agree on gpt-6-astra/max and their committed-default regression passes without changing other provider settings.
- Generated packet, candidate authority, indicator, TASKS and CHANGELOG agree; after this wave lands, fleet classification remains immediate next with no extra precursor.

## Grounding / Authorization

- Task: [FLEET-CLEANUP-CENSUS-R3]; wave id `workingrcx-fleet-census-r3-2026-09-11`.
- Governing packet: this file, `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md`.
- TASKS.md authority: the 2026-09-11 tracker sync note for wave `workingrcx-fleet-census-r3-2026-09-11` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:workingrcx-fleet-census-r3-2026-09-11

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

<!-- PHASE_B_INDICATOR_SCOPE_AUTHORITY:BROAD_PACKAGE_SNAPSHOT -->

- Refresh wave: `workingrcx-fleet-census-r3-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_workingrcx_fleet_census.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/executors/workingrcx_fleet_census.py`
  - `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id workingrcx-fleet-census-r3-2026-09-11 --output reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py mu/tests/tools/test_bridge_config_model_sync.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_census.py --fleet-root /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal --anchor-repo . --output reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-census-r3-2026-09-11 --wave-class L4_ENABLER`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tests/tools/test_workingrcx_fleet_census.py`, `mu/tools/executors/executor_common.py`, `mu/tools/executors/executor_config.json`, `mu/tools/executors/workingrcx_fleet_census.py`, `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json`, `reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json`, `mu/tests/docs/test_growth_caps.py`.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: workingrcx-fleet-census-r3-2026-09-11.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:start -->
## Commit-Time Generated Governance Authorization

- Refresh wave: `workingrcx-fleet-census-r3-2026-09-11`
- Step-5e provenance: `bumped`
- Purpose: commit automation may bind the exact same-wave growth-cap governance file after Phase B review; first bumps require staged-index proof, while already-recorded reuse requires clean HEAD/index proof.
- Authorized generated governance path(s):
  - `mu/tests/docs/test_growth_caps.py`
- Scope binding: the path above is in scope only as the Step-5e same-wave growth-cap governance mutation or exact clean same-wave continuation evidence.
- Pre-review boundary: this block does not add the path to the locked Phase B/pre-review candidate allowlist and cannot authorize arbitrary implementation files.
- Acceptance binding: unsupported, malformed, outside-repo, dirty, wrong-wave, worktree-only, index/HEAD-mismatched, or provenance-free generated governance paths fail before supervisor.
<!-- COMMIT_GENERATED_GOVERNANCE_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `workingrcx-fleet-census-r3-2026-09-11`
- Active packet: `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `3c54c6fe5fc21b9f07efdd1cd4d14cd8b680ed189dadcd84ad349ebfbb5a455a`
- Indicator artifact: `reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_workingrcx_fleet_census.py mu/tests/tools/test_bridge_config_model_sync.py --tb=short && PYTHONDONTWRITEBYTECODE=1 python3 mu/tools/executors/workingrcx_fleet_census.py --fleet-root /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal --anchor-repo . --output reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json && python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-fleet-census-r3-2026-09-11 --wave-class L4_ENABLER`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md. (2) Final pytest gate covered 3 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `CHANGELOG.md`, `TASKS.md`, `mu/tests/tools/test_bridge_config_model_sync.py`, `mu/tests/tools/test_workingrcx_fleet_census.py`, `mu/tools/executors/executor_common.py`, `mu/tools/executors/executor_config.json`, `mu/tools/executors/workingrcx_fleet_census.py`, `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md`, `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json`, `reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json`, `mu/tests/docs/test_growth_caps.py`.
- Commit-generated governance paths:
  - `mu/tests/docs/test_growth_caps.py`
- Evidence handles:
  - `commit_time_generated_governance`: `mu/tests/docs/test_growth_caps.py`
  - `indicator`: `reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json`
- Current staged files:
  - `CHANGELOG.md`
  - `TASKS.md`
  - `mu/tests/docs/test_growth_caps.py`
  - `mu/tests/tools/test_bridge_config_model_sync.py`
  - `mu/tests/tools/test_workingrcx_fleet_census.py`
  - `mu/tools/executors/executor_common.py`
  - `mu/tools/executors/executor_config.json`
  - `mu/tools/executors/workingrcx_fleet_census.py`
  - `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_2026-09-11.md`
  - `reports/control_plane/workingrcx-fleet-census-r3-2026-09-11_census.json`
  - `reports/l4_wave_indicators/workingrcx-fleet-census-r3-2026-09-11.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
