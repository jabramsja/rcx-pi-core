# Pipeline Pager Receiver Exact Source Authority 2026-07-27

Date: 2026-07-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-pager-receiver-exact-source-authority-2026-07-27
Phase-A-Lock: LOCKED
Purpose: Make the canonical session pager receiver an exact by-path, fail-closed authority so earlier target-control roots, retained site paths, or cached modules cannot shadow the receiver used by pipeline paging.

## Scope

Narrow L4 pager source-authority prerequisite only: one pager production file, its existing test module, and builder-generated tracker, packet, and indicator artifacts.

Files and surfaces in scope:

- mu/tools/observability/pipeline_agent_pager.py (MODIFY) -- replace bare receiver import with lazy exact-by-path loading, canonical path validation, cache replacement, circular-import-safe module publication, and partial-module cleanup.
- mu/tests/tools/test_pipeline_agent_pager.py (MODIFY) -- prove exact authority against path and cache collisions, exercise the real receiver circular link, and cover missing, symlinked, non-regular, and retry cases.
- TASKS.md (GENERATED UPDATE) -- launcher-built tracker-sync authority for this wave.
- reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md (GENERATED) -- launcher-built Phase A packet.
- reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json (GENERATED) -- L4 indicator artifact.
- TASKS.md -- tracker-sync authority. The 2026-07-27 tracker sync note for wave `pipeline-pager-receiver-exact-source-authority-2026-07-27` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce bare-import receiver shadowing from earlier target-control and retained-site paths before changing code.
2. Add one lazy exact-by-path loader rooted at the pager module's canonical sibling session directory.
3. Reject a symlinked session directory and any missing, symlinked, non-regular, unreadable, or out-of-tools-root receiver file before executing receiver bytes.
4. Replace any preexisting bare-name cache entry, publish the exact candidate before execution for the intentional receiver-to-pager circular import, and remove a partial candidate on every execution error.
5. Validate that the loaded receiver class is callable and return only that exact class to the existing paging flow.
6. Add hermetic collision, cache, invalid-shape, retry, and real-repo circular-link regressions without changing pager behavior outside receiver source selection.
7. Run the exact evidence command and let Phase B, pre-commit supervisor, and commit executor own staging, commit, PR, CI, merge, and cleanup.

## Constraints

- Exactly the two named production and test files plus builder-generated TASKS.md, packet, and indicator artifacts are in scope; the external launcher config remains outside the worktree and must not be staged.
- Keep receiver loading lazy so importing pipeline_agent_pager on non-POSIX bootstrap paths does not eagerly import receiver dependencies.
- Do not widen launcher or dispatcher path manifests, reorder global sys.path, trust importlib bare-name resolution, retain a wrong cache entry, or add a fallback receiver source.
- Do not change provider routing, pager wake policy, detached drain semantics, circuit-breaker behavior, role/model defaults, runtime, substrate, seeds, parity, or docs outside generated wave artifacts.
- Do not follow symlinks or accept missing, non-regular, unreadable, or out-of-root receiver authority.
- Do not cite code line numbers inside the packet; identify source sites by file and symbol so launcher line-reference lint remains green.
- Do not hand-author packets, tracker notes, handoffs, receipts, commits, pushes, PRs, or merges.

## Stop conditions

- Halt as NEEDS_RESCOPING before editing a third production or test file.
- Halt fail closed before receiver execution if canonical receiver identity cannot be proven.
- Halt if exact loading breaks the intentional receiver-to-pager circular link, poisons sys.modules after an error, or requires eager receiver import.
- Halt if the repair would require changing provider routing or paging policy; route that as a separate wave instead of widening this prerequisite.
- Stop done only after the exact evidence command is green and commit, PR, CI, merge, and cleanup complete through the pipeline.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`

## Acceptance criteria

- Earlier same-name receiver modules under executor, observability, agent, check, or retained-site paths never execute; the canonical session receiver class is returned.
- A wrong preexisting sys.modules cache entry is replaced rather than trusted.
- The real repository receiver loads successfully and its imported pager reference is the active pipeline_agent_pager module.
- An execution error removes the partial candidate so a corrected receiver can load on a fresh retry.
- Missing, symlinked, non-regular, unreadable, or out-of-root receiver paths stop fail closed.
- The existing pager test module remains green and the staged scope contains only the two named code/test files plus TASKS.md, the generated packet, and the generated indicator.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-pager-receiver-exact-source-authority-2026-07-27`.
- Governing packet: this file, `reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md`.
- TASKS.md authority: the 2026-07-27 tracker sync note for wave `pipeline-pager-receiver-exact-source-authority-2026-07-27` is canonical for this packet's L4 fields.
- Authorization: Founder-directed permanent pipeline repair: waves must use the pipeline, and pager receiver authority must remain exact after target-worktree source selection rather than being redirectable by path order or cache state.

FOUNDER_OVERRIDE:pipeline-pager-receiver-exact-source-authority-2026-07-27

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-pager-receiver-exact-source-authority-2026-07-27`
- Active packet: `reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md`
  - `reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-pager-receiver-exact-source-authority-2026-07-27 --output reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/observability/pipeline_agent_pager.py`, `reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md`, `reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-pager-receiver-exact-source-authority-2026-07-27.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-pager-receiver-exact-source-authority-2026-07-27`
- Active packet: `reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `28b425486fce91f332b2fadee94b3781f168e6c715b0197d67412d46225ca7b4`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/observability/pipeline_agent_pager.py`, `reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md`, `reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pipeline-pager-receiver-exact-source-authority-2026-07-27_2026-07-27.md`
  - `reports/l4_wave_indicators/pipeline-pager-receiver-exact-source-authority-2026-07-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
