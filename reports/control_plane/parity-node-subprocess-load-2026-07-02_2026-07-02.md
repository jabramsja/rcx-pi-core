# Make node-subprocess parity tests reliable under -n auto parallel load

Date: 2026-07-02
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: parity-node-subprocess-load-2026-07-02
Phase-A-Lock: LOCKED
Purpose: FOUNDER-DIRECTED STRUCTURAL FIX (2026-07-02): cross-substrate tests that spawn a `node` subprocess FLAKE under the nightly's and audit_fast's `-n auto --dist worksteal` parallel run, causing the nightly (slow_tests.yml) to be RED since 2026-06-26 AND blocking every commit's Step-11 pre-push. ROOT CAUSE (evidence, not conjecture): each xdist worker spawns a CPU-heavy `node` subprocess whose `subprocess.run(..., timeout=N)` is calibrated for a SERIAL run (~13-60s standalone); under N-worker CPU over-subscription the node process is starved and exceeds its timeout -> `subprocess.TimeoutExpired` -> the test FAILS in parallel while PASSING serially. VERIFIED: `test_js_parity_automated.py::TestAPIMaxStepsGuard::test_max_steps_at_cap_accepted[run_engine_pipeline]/[run_engine_with_routing]` fail at pre-push under `-n auto` (helper `_run_node_json` subprocess timeout=30 exceeded) yet the whole `TestAPIMaxStepsGuard` class passes 8/8 in 20.59s serially; the paxos cross-substrate tests in `test_boot1_shadow_parity.py` (subprocess timeout=120) time out the same way under parallel load. CORRECTION THIS ROUND (bridge finding [high], VERIFIED against current code -- a DEFECT in the prior packet's mechanism, not just its enumeration): the prior packet put the lock in a NEW `mu/tests/parity/conftest.py` and enumerated only the 11 `mu/tests/parity/` node-spawners. But (a) `mu/tests/parity/conftest.py` DOES NOT EXIST (`ls` confirmed), and a conftest placed there is inherited ONLY by tests collected under `mu/tests/parity/`; and (b) the over-subscription domain is the ENTIRE pytest session, not the parity subdir. The nightly runs `pytest -m "slow and not l4_expensive" ... -n auto --dist worksteal --timeout=300` AND `pytest -m l4_expensive ... -n auto --dist worksteal --timeout=900` REPO-WIDE (slow_tests.yml, NO path filter), which co-schedules ~109 OTHER node-spawning test files (`grep -rlnE '\[[[:space:]]*"node"|node -e' mu/tests/ tests/ | grep -v mu/tests/parity/ | wc -l` = 109 on dev HEAD; the reviewer measured 113 -- the exact count drifts with the tree, the magnitude >100 is the point) in the SAME `-n auto` session -- including `mu/tests/structural/test_hemisphere_parity.py` (the IDENTICAL `node mu/host/js/eval_step.js` spawn at lines 44/139/168, `@pytest.mark.slow`, whose lines 27-29 document the SAME CPU-starvation root cause), `mu/tests/l4_gates/test_metabolize_cycle_gate.py` (eval_step.js, `@pytest.mark.slow`+`@pytest.mark.l4_expensive` at L185-186), and the seven `mu/tests/l4_gates/test_structural_numbers_*_js_parity.py` (drive `bootstrap_core.js` via node; `@pytest.mark.l4_expensive`+`@pytest.mark.slow`). None of these inherit a `mu/tests/parity/conftest.py` fixture, so they would spawn UNLOCKED competing node processes; the prior packet's central invariant "at most ONE node at a time across ALL xdist workers" is FALSE and the primary acceptance criterion (nightly no longer flakes) is NOT met -- while the NARROW parity-only evidence_command still goes green (a false-green). STRUCTURAL FIX (this round): install the cross-worker node serializer at a SESSION-WIDE conftest surface that EVERY node-spawning test inherits -- the repo-root `conftest.py` ("shared across mirrored test trees"; equivalently `mu/tests/conftest.py`, the tightest conftest above `mu/tests/{parity,structural,l4_gates,...}`; `tests/ -> mu/tests` is a symlink, so `tests/**` collection inherits the same files). A session-scoped autouse fixture intercepts node subprocess spawns process-wide at the `subprocess.Popen` chokepoint (all of `run`/`call`/`check_output`/`check_call` -- and `from subprocess import run` callers -- funnel through `Popen`): whenever the resolved executable basename is `node`, it acquires an exclusive POSIX `fcntl.flock` on a stable shared lock file for that process's lifetime and releases it in a `finally` (including on `TimeoutExpired`/exception). Because `-n auto` runs each worker as a SEPARATE OS process that imports the conftest, every worker's node spawn contends on the SAME flock -> at most one node runs at a time across ALL workers, session-wide, for helper-based AND inline AND `node -e` spawns in ANY directory, with NO per-file routing. This is the STRUCTURAL REDUCTION: ONE choke point that a test cannot bypass by forgetting to route (the exact gap that produced this finding), instead of hand-wiring ~120 spawn sites. Dist-mode-agnostic: `fcntl.flock` is a per-open-file cross-process lock, independent of `--dist worksteal`/`load`/`loadgroup`. REJECTED PRIMARY (bridge finding, VERIFIED): `@pytest.mark.xdist_group("node_subprocess")` is INERT under `--dist worksteal` -- xdist reads the group mark ONLY when `--dist loadgroup` (`remote.py` guards the group-suffix logic; `remote.py` sets `loadgroup = dist == "loadgroup"`), and every targeted env uses worksteal (audit_fast.sh, audit_all.sh, slow_tests.yml). COMPLEMENT (dist-mode-agnostic): for genuinely-slow node runs (paxos boot1, timeout=120) raise the specific per-call `subprocess.run(..., timeout=N)` values to a documented load-tolerant headroom -- a safety margin, NOT a substitute for removing over-subscription. Do NOT change any test's ASSERTIONS or the substrate; the tests are correct (they pass serially) -- only their PARALLEL SCHEDULING/timeout is hardened. `filelock` is NOT an installed dependency; use the Python stdlib `fcntl.flock`, available on the POSIX CI/dev targets (Linux nightly + macOS dev). This is the structural fix for the recurring nightly-RED and pre-push-strand class.

## Scope

Serialize EVERY `node` subprocess spawn in the pytest SESSION (not just `mu/tests/parity/`) behind a CROSS-WORKER FILE LOCK, installed at a session-wide conftest surface so it is inherited by all node-spawning tests by construction. Dist-mode-agnostic (POSIX `fcntl.flock`), unlike the inert `@pytest.mark.xdist_group` (a no-op unless `--dist loadgroup`, which no targeted env uses). Complement: raise the genuinely-slow node-run `subprocess.run(..., timeout=N)` values to documented load-tolerant headroom. No assertion changes, no xfail/skip/retry masking, no runtime substrate, no new third-party dependency.

Files and surfaces in scope:

- `conftest.py` (repo root -- PRIMARY session-wide surface; already the "Repo-root pytest fixtures shared across mirrored test trees" file). Add a session-scoped autouse fixture that installs the cross-worker node serializer for the whole run. Equivalent alternative: `mu/tests/conftest.py` (tightest conftest that still covers every current node-spawning dir -- `parity/`, `structural/`, `l4_gates/`, `tools/`, ...). All current node-spawning tests live under `mu/tests/**`, and `tests/ -> mu/tests` is a symlink, so a single edit at either surface reaches both mirrored collection paths -- NO second edit needed. Root `conftest.py` is chosen as PRIMARY because it also covers any node-spawning test placed outside `mu/tests/` in future.
- Node-run timeout headroom (complement): the genuinely-slow node-run `subprocess.run(..., timeout=N)` calls -- notably paxos boot1 (`mu/tests/parity/test_boot1_shadow_parity.py`, timeout=120) and any other call that legitimately needs margin -- raised to a documented load-tolerant value with an inline comment per raised call.
- `TASKS.md` -- tracker-sync authority. The 2026-07-02 tracker sync note (line 671) for wave `parity-node-subprocess-load-2026-07-02` is the single source of truth for this packet's L4 fields; the packet derives from it. Read-only here (L4 fields are not hand-edited from this packet).

Verification targets (these are what to RUN under `-n auto --dist worksteal` to PROVE reliability -- they are NOT an enforcement enumeration; enforcement is session-wide-by-construction, so no per-file routing list exists to audit):

- Parity node-spawners: `grep -rlnE '\[[[:space:]]*"node"' mu/tests/parity/` = 11 files (incl. `test_js_parity_automated.py`, `test_boot1_shadow_parity.py`, `test_exhaustion_parity.py`, `test_hemisphere_metabolization_parity.py`, `test_rcx_engine_workload_contract_parity.py`, `test_seed_loading_parity.py`, ...). These are a SUBSET of the session's node-spawners.
- Non-parity co-runners named by the finding (proof that the domain is session-wide): `mu/tests/structural/test_hemisphere_parity.py`, `mu/tests/l4_gates/test_metabolize_cycle_gate.py`, and `mu/tests/l4_gates/test_structural_numbers_*_js_parity.py` (7 files). A parity-subdir lock would NOT reach these; the session-wide lock does.

- `reports/deferred/non_blocking/parity-node-subprocess-load-2026-07-02_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Add a session-scoped autouse node-serialization fixture to the repo-root `conftest.py` (or equivalently `mu/tests/conftest.py`): for the whole test session (installed once per xdist worker process), intercept node subprocess spawns at the `subprocess.Popen` chokepoint so that any invocation whose resolved executable basename is `node` acquires an exclusive `fcntl.flock` on a STABLE shared lock file (a fixed absolute path shared by all workers -- e.g. under the OS temp dir or `.pytest_cache/`) for that process's lifetime and releases it in a `finally` (including on `TimeoutExpired`/exception). Non-node subprocess calls pass through UNCHANGED (no behavior change for anything but node). Must be dist-mode-agnostic (correct under `--dist worksteal`; NOT reliant on `--dist loadgroup`).
2. Intercept at the single `subprocess.Popen` chokepoint so coverage is by CONSTRUCTION: `run`/`call`/`check_output`/`check_call` all funnel through `Popen`, so one wrapper covers helper-based, inline, `node -e`, and `from subprocess import run` callers. Detect `node` in BOTH list-form (`argv[0]` basename) and shell/`node -e` string form (first token). Because every test under `mu/tests/**` (and, via the symlink, `tests/**`) inherits the session fixture, NO node spawn in the session can bypass it -- and a newly-added node test is covered automatically, with zero per-file edits.
3. Do NOT add or rely on `@pytest.mark.xdist_group("node_subprocess")` for serialization (inert under `--dist worksteal`, per bridge finding); if any such marker was speculatively added in a prior attempt, remove it so the packet does not imply protection it cannot provide under the targeted dist mode.
4. Raise the genuinely-slow node-run `subprocess.run(..., timeout=N)` values (paxos boot1 timeout=120, and any other call that legitimately needs headroom) to a documented load-tolerant headroom, with an inline comment per raised call stating why. Never lower any timeout or assertion below a value that passes serially.
5. Verify no masking was introduced: grep the touched files for any new `xfail` / `skip` / retry decorator / assertion change; confirm there are none.
6. Prove reliability under the ACTUAL nightly shape, not the narrow command alone: run the evidence_command repeatedly AND run a repo-wide node-spawning slow/l4_expensive selection under `-n auto --dist worksteal` -- INCLUDING the non-parity co-runners `test_hemisphere_parity.py`, `test_metabolize_cycle_gate.py`, `test_structural_numbers_*_js_parity.py` -- green on repeated runs. The narrow parity evidence_command is NECESSARY but NOT SUFFICIENT (it can false-green while an unlocked non-parity spawner flakes the nightly -- the exact bridge finding [high]).
7. If session-wide strict-1 serialization would exceed a per-test `--timeout`: if serializing every node in the session behind a single flock makes any test's (lock-queue wait + own run) exceed its per-test `--timeout` budget (300s slow / 900s l4_expensive), replace strict-1 with a BOUNDED cross-process gate (allow K concurrent node, K sized to leave cores free -- still removes over-subscription) rather than mask with retries/xfail. Diagnose the measured serialized wall-clock before choosing K.

## Constraints

- NOT in scope: runtime substrate dirs `mu/host/**` and `rcx_pi/selfhost/**` (L4_ENABLER MUST NOT touch runtime dirs).
- NOT in scope: weakening, skipping, xfailing, retrying, or otherwise masking any assertion or test. The tests pass serially and MUST keep identical assertions and substrate semantics.
- NOT in scope: `@pytest.mark.xdist_group` / `--dist loadgroup` as the serialization mechanism -- inert under the `--dist worksteal` used by all targeted envs and the evidence_command.
- NOT in scope: scoping the lock to a `mu/tests/parity/conftest.py` (or any subdir conftest) -- it would NOT be inherited by the ~109 non-parity node-spawners that co-run in the nightly session, and would re-create the false-green this finding flags. Enforcement MUST be at a session-wide surface (root `conftest.py` / `mu/tests/conftest.py`).
- NOT in scope: per-file routing of individual node spawn sites as the enforcement mechanism -- SUPERSEDED by the single session-wide `Popen`-chokepoint interception; per-file routing is precisely what produced this finding's gap (a missed file re-introduces over-subscription).
- NOT in scope: changing the CI/audit `--dist worksteal` mode or the `-n auto` parallelism. `audit_fast.sh`, `audit_all.sh`, and `slow_tests.yml` stay as-is (worksteal is deliberately chosen for load balancing).
- NOT in scope: adding a new third-party dependency. `filelock` is not installed; use the Python stdlib `fcntl` (available on the POSIX CI/dev targets).
- NOT in scope: editing this packet's L4 fields into TASKS.md. The TASKS.md note is the authority; this packet derives from it.

## Stop conditions

- STOP and re-scope (do not proceed) if removing over-subscription would require changing runtime substrate dirs or test assertions -- that would violate L4_ENABLER and the no-masking rule.
- STOP and surface as POLICY_BOUND if a dist-mode-agnostic cross-worker gate cannot be built from the stdlib (`fcntl`) without adding a dependency.
- STOP and choose a bounded-K gate (per work item 7) if strict-1 session-wide serialization makes any node test's (lock-queue wait + own run) exceed its per-test `--timeout` budget (300s slow / 900s l4_expensive). Do NOT mask with retries; do NOT lower a serial-passing timeout.
- STOP and diagnose (do NOT paper over with retries) if the evidence_command OR the repo-wide node-spawning run still flakes after the session-wide lock + headroom -- the residual over-subscription source must be found (e.g. a node spawn form the `Popen`-chokepoint interception missed: `os.system`, a shell wrapper script, or a non-`node` argv0 that re-execs node).

## Validation gates

- evidence_command (machine-checked, canonical in TASKS.md note; NECESSARY but not SUFFICIENT -- see Acceptance criteria for the sufficient nightly-shape run): `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_js_parity_automated.py::TestAPIMaxStepsGuard -n auto --dist worksteal -q`
- L4 fields (canonical in TASKS.md note; reproduced verbatim for reference; UNCHANGED this round):
  - Class: `L4_ENABLER`
  - target_gate_id: `G8`
  - primary_blocker_class: `INTEGRATION`
  - primary_invariant_id: `INV_STRUCTURAL_FORWARD_MOTION`
  - indicator_artifact_ref: `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`
  - indicator_collection_command: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id parity-node-subprocess-load-2026-07-02 --output reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`
  - bootstrap_endgame_policy: `SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`
  - boot0_track_id: `V1`
  - boot0_progress_state: `HOLD`

## Acceptance criteria

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/parity/test_js_parity_automated.py::TestAPIMaxStepsGuard -n auto --dist worksteal -q` passes reliably (green on repeated runs), matching the TASKS.md evidence_command. (NECESSARY.)
- A repo-wide node-spawning slow/l4_expensive selection run under `-n auto --dist worksteal` -- the ACTUAL nightly shape, INCLUDING the non-parity co-runners `mu/tests/structural/test_hemisphere_parity.py`, `mu/tests/l4_gates/test_metabolize_cycle_gate.py`, and `mu/tests/l4_gates/test_structural_numbers_*_js_parity.py` alongside the 11 parity node-spawners -- passes on REPEATED runs with no `subprocess.TimeoutExpired`, and the pass is BECAUSE at most one node subprocess (or <=K, if the bounded-K fallback was needed) runs at a time via the session-wide `fcntl.flock`, not because any assertion or timeout was weakened. (SUFFICIENT for the nightly claim -- this is exactly what the parity-only command could NOT prove.)
- Enforcement is session-wide-by-construction: the serializer lives in the repo-root `conftest.py` (or `mu/tests/conftest.py`), inherited by every node-spawning test dir (`tests/ -> mu/tests`), so NO node spawn anywhere in the session runs unlocked. Verified by: `grep -rlnE '\[[[:space:]]*"node"|node -e' mu/tests/` lists the session's node-spawners, and they are covered by fixture INHERITANCE (no per-file routing to audit), plus a runtime check that the concurrent node count never exceeds the cap.
- Serialization holds specifically under `--dist worksteal`: no reliance on `@pytest.mark.xdist_group` / `--dist loadgroup` (marker removed or provably unused for scheduling).
- No new `xfail` / `skip` / retry markers and no assertion changes in the touched files (grep-clean).
- Every raised `subprocess.run(..., timeout=N)` carries an inline comment justifying the load-tolerant headroom; no timeout lowered below its serial-passing value.
- No edits under `mu/host/**` or `rcx_pi/selfhost/**`; no new third-party dependency added (`fcntl` stdlib only).
- Both nightly (slow_tests.yml) sessions -- `-m "slow and not l4_expensive"` (timeout=300) AND `-m l4_expensive` (timeout=900) -- AND the Step-11 pre-push (audit_fast) no longer flake on parallel-load timeout for this class, across parity AND non-parity node-subprocess tests (`test_hemisphere_parity.py`, `test_metabolize_cycle_gate.py`, `test_structural_numbers_*_js_parity.py`, the no-slow-marker parity runners, etc.).

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `parity-node-subprocess-load-2026-07-02`.
- Governing packet: this file, `reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md`.
- TASKS.md authority: the 2026-07-02 tracker sync note (line 671) for wave `parity-node-subprocess-load-2026-07-02` is canonical for this packet's L4 fields (reproduced in Validation gates above).
- Reconciliation (current code truth over stale note prose): the note's narrative `evidence_delta`/`progress_proof_after` describe the fix as "serialized into a shared xdist group." Bridge finding -- verified against xdist (`remote.py`, `remote.py`) and the `--dist worksteal` usage in audit_fast.sh / audit_all.sh / slow_tests.yml -- proves that mechanism is INERT under `--dist worksteal`. Per the packet-rewrite directive to prefer current code truth over stale wording, this packet's DESIGN uses a dist-mode-agnostic cross-worker `fcntl.flock` mutex instead; the machine-checked L4 fields (Class, target_gate_id, evidence_command, primary_blocker_class, primary_invariant_id, indicator_artifact_ref, indicator_collection_command, bootstrap_endgame_policy, boot0_track_id, boot0_progress_state, FOUNDER_OVERRIDE) are UNCHANGED.
- Scope-domain correction (THIS round's bridge finding [high], class DEFECT, VERIFIED against current code): the prior packet scoped the lock to a `mu/tests/parity/conftest.py` (which does NOT exist -- `ls` confirmed) and treated the 11 parity node-spawners as the enforcement domain. But the over-subscription domain is the ENTIRE `-n auto --dist worksteal` pytest session. The nightly (slow_tests.yml) runs `pytest -m "slow and not l4_expensive"` and `pytest -m l4_expensive` REPO-WIDE, co-scheduling ~109 non-parity node-spawning files (`grep -rlnE '\[[[:space:]]*"node"|node -e' mu/tests/ tests/ | grep -v mu/tests/parity/ | wc -l` = 109 on dev HEAD; reviewer measured 113) -- including `mu/tests/structural/test_hemisphere_parity.py` (identical `node eval_step.js` at 44/139/168, `@pytest.mark.slow`, documenting the SAME CPU-starvation cause at L27-29), `mu/tests/l4_gates/test_metabolize_cycle_gate.py` (eval_step.js, `slow`+`l4_expensive`), and 7x `mu/tests/l4_gates/test_structural_numbers_*_js_parity.py` (`bootstrap_core.js` via node, `l4_expensive`+`slow`). A conftest under `mu/tests/parity/` is inherited ONLY by parity collection, so these spawn UNLOCKED -> the invariant "at most ONE node across ALL xdist workers" is FALSE and the nightly can still flake while the narrow parity evidence_command false-greens. FIX: move enforcement to the session-wide root `conftest.py` / `mu/tests/conftest.py` surface (a single `subprocess.Popen`-chokepoint interception), which every node-spawning test inherits by construction. The machine-checked L4 fields and the `evidence_command` are unchanged; the nightly gap is closed by the broader-run acceptance criteria (a repo-wide node-spawning run under the nightly's own dist shape), not by widening the machine-checked evidence_command.
- Authorization: Founder-directed structural fix 2026-07-02 (recurring-strand rule): the parallel-load node-subprocess flakiness blocks the nightly AND every commit's pre-push. FOUNDER_OVERRIDE:parity-node-subprocess-load-2026-07-02.

FOUNDER_OVERRIDE:parity-node-subprocess-load-2026-07-02

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `parity-node-subprocess-load-2026-07-02`
- Active packet: `reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md`
- Indicator artifact: `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `conftest.py`
  - `mu/tests/l4_gates/test_metabolize_cycle_gate.py`
  - `mu/tests/parity/test_boot1_shadow_parity.py`
  - `reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md`
  - `reports/deferred/non_blocking/parity-node-subprocess-load-2026-07-02_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `parity-node-subprocess-load-2026-07-02`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/parity-node-subprocess-load-2026-07-02_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id parity-node-subprocess-load-2026-07-02 --output reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_metabolize_cycle_gate.py mu/tests/parity/test_boot1_shadow_parity.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `conftest.py`, `mu/tests/l4_gates/test_metabolize_cycle_gate.py`, `mu/tests/parity/test_boot1_shadow_parity.py`, `reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md`, `reports/deferred/non_blocking/parity-node-subprocess-load-2026-07-02_bridge_nonblockers.md`, `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: parity-node-subprocess-load-2026-07-02.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `parity-node-subprocess-load-2026-07-02`
- Active packet: `reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `878a193c43bb76b1ee8b149417fee5c4d87a836abf6a32e765a944f823d9398d`
- Indicator artifact: `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/l4_gates/test_metabolize_cycle_gate.py mu/tests/parity/test_boot1_shadow_parity.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md. (2) Final pytest gate covered 2 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `conftest.py`, `mu/tests/l4_gates/test_metabolize_cycle_gate.py`, `mu/tests/parity/test_boot1_shadow_parity.py`, `reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md`, `reports/deferred/non_blocking/parity-node-subprocess-load-2026-07-02_bridge_nonblockers.md`, `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`
- Current staged files:
  - `TASKS.md`
  - `conftest.py`
  - `mu/tests/l4_gates/test_metabolize_cycle_gate.py`
  - `mu/tests/parity/test_boot1_shadow_parity.py`
  - `reports/control_plane/parity-node-subprocess-load-2026-07-02_2026-07-02.md`
  - `reports/deferred/non_blocking/parity-node-subprocess-load-2026-07-02_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/parity-node-subprocess-load-2026-07-02.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
