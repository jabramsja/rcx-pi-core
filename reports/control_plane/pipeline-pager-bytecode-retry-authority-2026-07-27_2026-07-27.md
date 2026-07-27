# Pipeline Pager Bytecode Retry Authority 2026-07-27

Date: 2026-07-27
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-pager-bytecode-retry-authority-2026-07-27
Phase-A-Lock: LOCKED
Purpose: Close the actionable Codex P2 on PR #1216 by making canonical pager receiver retries execute the exact bytes opened from the authorized source file rather than timestamp-and-size-matching stale bytecode.

## Scope

Immediate two-file follow-up to the current unresolved Codex P2 on PR #1216, plus only builder-generated tracker, packet, and indicator artifacts.

Files and surfaces in scope:

- mu/tools/observability/pipeline_agent_pager.py (MODIFY) -- read the canonical receiver through a no-follow descriptor and compile/execute the captured source bytes directly while preserving lazy loading, circular-import publication, and partial-module cleanup.
- mu/tests/tools/test_pipeline_agent_pager.py (MODIFY) -- seed a real stale pyc with identical source size and mtime, prove repaired bytes win, and prove a path swap after source capture cannot redirect execution.
- TASKS.md (GENERATED UPDATE) -- launcher-built tracker-sync authority for this wave.
- reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md (GENERATED) -- launcher-built Phase A packet.
- reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json (GENERATED) -- L4 indicator artifact.
- TASKS.md -- tracker-sync authority. The 2026-07-27 tracker sync note for wave `pipeline-pager-bytecode-retry-authority-2026-07-27` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Reproduce the unresolved PR #1216 P2 with a failing receiver import that seeds bytecode, then rewrite corrected source with exactly the same byte size and mtime.
2. Open the already validated canonical receiver with no-follow semantics, verify the opened descriptor is a regular file, and capture its bytes once.
3. Compile the captured bytes directly and execute that code object in the exact candidate module instead of asking SourceFileLoader to select source or bytecode.
4. Preserve wrong-cache replacement, circular-import-safe publication, callable-class validation, and cleanup of a partially executed candidate.
5. Add a deterministic source-path swap control after byte capture so execution remains bound to the opened bytes.
6. Run the exact evidence command and let Phase B, pre-commit supervisor, and commit executor own staging, commit, PR, CI, merge, and cleanup.

## Constraints

- Exactly the two named production and test files plus builder-generated TASKS.md, packet, and indicator artifacts are in scope; the external launcher config remains outside the worktree and must not be staged.
- Do not delete pyc files as the fix, weaken canonical path checks, follow symlinks, fall back to a different receiver, reorder sys.path, or trust a preexisting module cache entry.
- Keep loading lazy and preserve the intentional receiver-to-pager circular link and existing pager delivery behavior.
- Do not modify provider routing, pager wake policy, drain semantics, circuit-breaker behavior, executor review policy, role/model defaults, runtime, substrate, seeds, parity, or docs outside generated wave artifacts.
- Do not cite code line numbers inside the packet; identify source sites by file and symbol so launcher line-reference lint remains green.
- Do not hand-author packets, tracker notes, handoffs, receipts, commits, pushes, PRs, or merges.

## Stop conditions

- Halt as NEEDS_RESCOPING before editing a third production or test file.
- Halt fail closed before receiver execution if the opened canonical source identity or regular-file shape cannot be proven.
- Halt if direct source execution breaks the real receiver circular import, leaves partial sys.modules state, or changes pager delivery semantics.
- Route late bot-review durability as a separate commit-executor/merge-hook wave rather than widening this P2 repair.
- Stop done only after the exact evidence command is green and commit, PR, CI, merge, thread disposition, and cleanup complete through the pipeline.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`

## Acceptance criteria

- A real stale timestamp-based pyc exists for failing receiver code before the corrected source is written.
- Corrected source with identical byte size and mtime loads the corrected receiver class and never replays the old runtime error.
- Replacing the source path after bytes are captured but before compilation cannot redirect the executed receiver class.
- Wrong module-cache replacement, real repository circular loading, invalid canonical-path rejection, and partial-module retry behavior remain green.
- The full pager test module remains green and the staged scope contains only the two named code/test files plus TASKS.md, the generated packet, and the generated indicator.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-pager-bytecode-retry-authority-2026-07-27`.
- Governing packet: this file, `reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md`.
- TASKS.md authority: the 2026-07-27 tracker sync note for wave `pipeline-pager-bytecode-retry-authority-2026-07-27` is canonical for this packet's L4 fields.
- Authorization: Founder-directed permanent pipeline repair: actionable Codex review findings must be reproduced and structurally closed before dependent waves continue.

FOUNDER_OVERRIDE:pipeline-pager-bytecode-retry-authority-2026-07-27

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-pager-bytecode-retry-authority-2026-07-27`
- Active packet: `reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md`
  - `reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-pager-bytecode-retry-authority-2026-07-27 --output reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/observability/pipeline_agent_pager.py`, `reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md`, `reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-pager-bytecode-retry-authority-2026-07-27.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-pager-bytecode-retry-authority-2026-07-27`
- Active packet: `reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `ec5e15d3d112f0f1a47203775be07e6da1fccfe550612264dc722844d177c595`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_pipeline_agent_pager.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_pipeline_agent_pager.py`, `mu/tools/observability/pipeline_agent_pager.py`, `reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md`, `reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_pipeline_agent_pager.py`
  - `mu/tools/observability/pipeline_agent_pager.py`
  - `reports/control_plane/pipeline-pager-bytecode-retry-authority-2026-07-27_2026-07-27.md`
  - `reports/l4_wave_indicators/pipeline-pager-bytecode-retry-authority-2026-07-27.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
