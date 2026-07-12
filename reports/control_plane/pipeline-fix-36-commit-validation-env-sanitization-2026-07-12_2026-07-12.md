# Pipeline Fix 36 Commit Validation Environment Sanitization

Date: 2026-07-12
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [PIPELINE-FIX-36]
Wave ID: pipeline-fix-36-commit-validation-env-sanitization-2026-07-12
Phase-A-Lock: LOCKED
Purpose: Prevent launch-role, pager, and one-shot recovery overrides from contaminating commit-owned validation subprocesses while preserving active bus authority and all unrelated process environment.

## Scope

Allowed write scope:
- TASKS.md
- mu/tools/executors/commit_executor.py
- mu/tests/tools/test_commit_executor_receipt.py
- reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md
- reports/deferred/non_blocking/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_bridge_nonblockers.md
- reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json

Files and surfaces in scope:

- TASKS.md (MODIFY) -- builder-owned tracker authority only.
- mu/tools/executors/commit_executor.py (MODIFY) -- add and wire the bounded validation-subprocess environment sanitizer.
- mu/tests/tools/test_commit_executor_receipt.py (MODIFY) -- prove exact key removal, preservation, and all commit-owned validation call sites through public seams.
- reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md (GENERATED) -- governing packet.
- reports/deferred/non_blocking/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_bridge_nonblockers.md (CREATE ONLY IF NEEDED) -- durable lower-severity dispositions.
- reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json (GENERATED) -- same-wave indicator.
- TASKS.md -- tracker-sync authority. The 2026-07-12 tracker sync note for wave `pipeline-fix-36-commit-validation-env-sanitization-2026-07-12` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the exact contaminated parent environment that stranded FIX35: role/pager pins select claude while Tier 2 recovery selects phase_b_executor timeout 27000.
2. Add one commit-owned validation environment helper that copies the current environment, removes exactly RCX_IMPLEMENTER_AGENT_OVERRIDE, RCX_REVIEWER_AGENT_OVERRIDE, RCX_BRIDGE_REVIEWER_OVERRIDE, RCX_ROLE_AGENT_OVERRIDE_REPO_ROOT, RCX_PIPELINE_AGENT_PAGER_ROUTE_OVERRIDE, RCX_RECOVERY_TIMEOUT_OVERRIDE, RCX_RECOVERY_TIMEOUT_KEY, RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_OVERRIDE, RCX_RECOVERY_BRIDGE_TURN_TIMEOUT_KEY, and RCX_RECOVERY_STALE_TIMEOUT_OVERRIDE, and preserves RCX_AGENT_BUS_DIR plus unrelated variables.
3. Wire that helper into targeted pytest, every test-integrity child, bot-remediation pre-push, and normal Step 11 pre-push. Do not globally alter _run or the environment for git, adapter, receipt, push, merge, pager, or supervisor subprocesses.
4. Add public-seam tests for exact removal, lane-bus preservation, unrelated-key preservation, no mutation of os.environ, and explicit env use at every required validation call site.
5. Run the focused receipt tests plus the four tests that failed under FIX35, compile commit_executor, strict staged L4, host-semantics ratchet, and diff check. Leave commit, push, PR, merge, and cleanup to the pipeline.
6. Require normal commit Step 11 to run the full pre-push-fast suite from the contaminated pipeline parent and report zero failures before publication.

## Constraints

- Builders only. Do not manually edit tracked files, commits, pushes, PRs, merges, receipts, or conflicts.
- Sanitize only commit-owned validation children. Do not globally scrub the dispatcher or executor environment because role, pager, recovery, bus, and receipt authority remain necessary for live pipeline execution.
- Preserve RCX_AGENT_BUS_DIR, PATH, credentials, pytest worker bounds, locale, and every unrelated variable byte-for-byte.
- Do not weaken, skip, xfail, deselect, or rewrite the four existing failing tests. They are read/test-only and outside the writable scope.
- Do not use git push --no-verify as a bypass; the existing commit executor may use its documented post-Step-11 push mechanism only after Step 11 passes.
- Do not add runtime, substrate, seed, parity, host, or Claude-owned semantics.
- The packet and TASKS note must carry FOUNDER_OVERRIDE:pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.

## Stop conditions

- Halt if reproduction does not show inherited launch/recovery keys changing the four tests, or if a proposed fix changes committed executor defaults instead of isolating validation children.
- Halt if RCX_AGENT_BUS_DIR or unrelated variables are removed or changed, if any non-validation subprocess environment changes, or if scope expands beyond the exact allowed files.
- Halt if focused tests select zero cases, any validation fails, Codex Phase B review is not GO, COMMIT_GO is absent, or full Step 11 pre-push is not green.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`

## Acceptance criteria

- A contaminated parent with all five launch-role/pager keys and all five one-shot recovery override keys produces a validation child env containing none of them.
- The validation child env preserves RCX_AGENT_BUS_DIR and arbitrary unrelated sentinel variables exactly, without mutating os.environ.
- Targeted pytest, test-integrity children, bot-remediation pre-push, and normal Step 11 pre-push all receive the sanitized env explicitly; git, adapter, receipt, push, merge, pager, and supervisor paths remain unchanged.
- The four exact FIX35 failures pass under their intended seeded/committed authority, focused receipt tests pass, compile/L4/host-ratchet/diff checks pass, and normal full pre-push reports zero failures.
- The wave lands through Codex Phase B GO and receipt-authorized commit executor without bypasses.

## Grounding / Authorization

- Task: [PIPELINE-FIX-36]; wave id `pipeline-fix-36-commit-validation-env-sanitization-2026-07-12`.
- Governing packet: this file, `reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md`.
- TASKS.md authority: the 2026-07-12 tracker sync note for wave `pipeline-fix-36-commit-validation-env-sanitization-2026-07-12` is canonical for this packet's L4 fields.
- Authorization: Founder-authorized structural repair for the reproduced commit validation environment leak that stranded FIX35 after COMMIT_GO.

FOUNDER_OVERRIDE:pipeline-fix-36-commit-validation-env-sanitization-2026-07-12

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-fix-36-commit-validation-env-sanitization-2026-07-12`
- Active packet: `reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md`
  - `reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-fix-36-commit-validation-env-sanitization-2026-07-12 --output reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md`, `reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-fix-36-commit-validation-env-sanitization-2026-07-12`
- Active packet: `reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `86278f41573b7fba6d00b40eecb1f9b8e1b12d53ca6584e1819b43fb5d173eb0`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_receipt.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_receipt.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md`, `reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_receipt.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12_2026-07-12.md`
  - `reports/l4_wave_indicators/pipeline-fix-36-commit-validation-env-sanitization-2026-07-12.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
