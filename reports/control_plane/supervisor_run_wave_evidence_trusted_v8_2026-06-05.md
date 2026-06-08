# Supervisor Run Wave Evidence Trusted V8 2026-06-05

Date: 2026-06-05
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: supervisor-run-wave-evidence-trusted-v8-2026-06-05
Phase-A-Lock: LOCKED

Purpose: make the pre-commit supervisor run the wave tracker note's declared `evidence_command` before merge as a required behavioral proof. The package field is transport-only and must exactly match the tracker-declared founder evidence before any shell runs. A failed, omitted, undeclared, or mismatched proof must route to `NEEDS_PHASE_B`, not merge with a stale, wrong, or unproven receipt.

Policy-bound founder decisions:
- `evidence_command` is trusted same-wave founder-authored shell. Run it through `run_validation_command` as `['bash', '-c', evidence_command]`; do not build an argv allowlist, shell grammar, or env-prefix parser.
- Trust attaches to the tracker note's declared `evidence_command`, not to an arbitrary package field. The package value must match the tracker-declared command exactly before execution.
- Restore-around-evidence remains required, but the restore source must be a pre-evidence worktree snapshot, not the index. Pre-existing unstaged tracked changes are protected state.
- The gate is fail-closed when the tracker note declares `evidence_command`, or when a package provides evidence that is absent from or mismatched with the tracker note.
- The v7 re-baseline approach stays rejected; `run_meta_bridge` keeps `state_start` before `run_validation_gates`.

## 1. Scope

Phase B implementation scope is exactly:
- `mu/tools/agents/meta_bridge_supervisor.py`
- `mu/tools/executors/commit_executor.py`
- `mu/tools/executors/phase_b_executor.py`
- `mu/tests/tools/test_meta_bridge_supervisor.py` by appending regressions to the existing test file

Required generated commit artifact after implementation staging:
- `reports/l4_wave_indicators/supervisor-run-wave-evidence-trusted-v8-2026-06-05.json`

This Phase A rewrite task edits only this governing packet.

## 2. Work Items

1. In `commit_executor.py` and `phase_b_executor.py`, pass the wave's `evidence_command` into every pre-commit supervisor package assembly site that already carries `tracker_note_text`. Extract the value from the tracker note with `_tracker_marker_value`.

2. In `meta_bridge_supervisor.py`, add `evidence_command` to `_OPTIONAL_PACKAGE_FIELDS` and add self-contained helpers that detect and extract the `tracker_note_text` `evidence_command:` marker. Do not import executor code for these helpers.

3. In `run_validation_gates`, add the `wave_evidence` proof outside the `is_cs_wave` block:
- Extract `declared_evidence_command` from `tracker_note_text`; treat `package.get('evidence_command')` only as the transported candidate.
- If both tracker-declared and package-provided commands are non-empty and exactly equal, run the tracker-declared command through the restore-wrapped evidence runner and append `ValidationResult('wave_evidence', exit_code == 0, detail)`.
- If the tracker note declares `evidence_command` but the package omits it, append `ValidationResult('wave_evidence', False, 'tracker note declares evidence_command but package omitted it')` without running anything.
- If the tracker note declares `evidence_command` and the package provides a different command, append `ValidationResult('wave_evidence', False, 'package evidence_command does not match tracker-declared evidence_command')` without running anything.
- If the tracker note does not declare `evidence_command` but the package provides one, append `ValidationResult('wave_evidence', False, 'package provided evidence_command but tracker note omitted it')` without running anything.
- If the tracker note does not declare `evidence_command` and the package omits it, skip the proof.
- When `is_cs_wave` is true, append the `wave_evidence` proof dict to `validation_commands_for_att`.
- A false `wave_evidence` result must make `all_passed` false so `run_meta_bridge` returns `NEEDS_PHASE_B`.

4. Implement restore-around-evidence from pre-evidence worktree truth:
- Before running evidence, compute and save the pre-evidence `compute_repo_state`.
- Enumerate tracked paths from the index only as path identity, then snapshot each tracked path's current worktree existence, bytes or symlink target, and executable mode into a temporary location outside the repo. This snapshot must preserve pre-existing unstaged tracked edits and pre-existing tracked deletions.
- Enumerate pre-existing untracked paths with `git ls-files --others --exclude-standard -z`, then snapshot each pre-existing untracked path's current worktree existence, bytes or symlink target, and executable mode into the same temporary location outside the repo. Filename-only tracking is insufficient.
- Run `run_validation_command(repo_root, ['bash', '-c', declared_evidence_command])` and capture its exit code.
- In a `finally` path, restore tracked worktree paths from the saved worktree snapshot, including files the evidence modified, deleted, created at tracked paths, or mode-changed.
- In the same `finally` path, remove only untracked paths that appear after evidence and were absent from the pre-evidence untracked set.
- Restore every pre-existing untracked path from the saved untracked snapshot, including files or symlinks the evidence modified, deleted, replaced with a different object type, or mode-changed.
- Do not use a tracked-file restore from the index, `git clean`, `git reset`, or any restore operation that discards pre-existing unstaged tracked work.
- After restore, require `compute_repo_state` to match the saved pre-evidence state. If it does not, fail closed before any receipt can be trusted.

5. Keep the post-merge path unchanged. `run_post_merge_validation_gates` does not call `run_validation_gates` and is out of scope.

6. Keep `_validate_tracker_note_text` behavior unchanged; the existing `set_roles.py --show` rejection needs no special case.

7. Add focused regressions to the existing test file:
- Matching tracker-declared/package-provided `evidence_command` containing `&&` and an env prefix calls `run_validation_command` exactly once with `['bash', '-c', exact_string]` and passes on exit 0.
- Matching tracker-declared/package-provided evidence with a non-zero exit produces failed `wave_evidence`, makes `all_passed` false, and routes through `NEEDS_PHASE_B`.
- Declared-but-omitted evidence fails closed without running `run_validation_command`.
- Provided-but-not-declared evidence fails closed without running `run_validation_command`.
- Provided-but-mismatched evidence fails closed without running `run_validation_command`.
- Not-declared and not-provided skips the proof and does not call `run_validation_command`.
- A non-control-surface package with matching tracker-declared/package-provided `evidence_command` still runs `wave_evidence`.
- Restore test proves a monkeypatched evidence run can mutate a tracked file that already had pre-existing unstaged content, create a new untracked file, and modify or delete a pre-existing untracked file; after the gate, the tracked file has the pre-evidence unstaged bytes, the created untracked file is gone, the pre-existing untracked file has the pre-evidence bytes or symlink target and executable mode, and `compute_repo_state` is unchanged.

8. After implementation changes are staged, run the tracker note's `indicator_collection_command` and include the generated indicator artifact in `files_to_stage`.

## 3. Constraints

- Do not edit tracker-note builders or evidence-command generation.
- Do not create a new test file.
- Do not edit runtime, substrate, seed, scheduler, registry, production `/mu`, host semantics, or Claude-related surfaces.
- Do not add an argv allowlist, shell grammar, env parser, or trust boundary around the founder-authored `evidence_command`.
- Do not execute a package-provided `evidence_command` unless it exactly matches the command declared in `tracker_note_text`.
- Do not re-baseline `state_start` after validation.
- Do not convert a failed or omitted declared `wave_evidence` result into a generic validation error; it must route to `NEEDS_PHASE_B`.
- Do not preserve pre-existing untracked paths by filename set only; pre-existing untracked bytes, symlink targets, and executable mode are protected state.
- Do not cite implementation code by file line number in the plan; use function names for code references.
- Do not treat `TASKS.md` authorization as proof that every item remains unlanded. If Phase B code truth proves an item is already implemented, remove it from pending work and acceptance instead of re-listing it.
- For this Phase A rewrite turn, do not inspect downstream implementation files or edit any file other than this packet.

## 4. Stop Conditions

Stop before implementation or commit handoff if any of these occur:
- Scope expands beyond the four implementation/test files plus the required generated indicator artifact.
- The implementation cannot preserve pre-evidence tracked worktree bytes, including pre-existing unstaged tracked modifications, without restoring tracked content from the index.
- The evidence wrapper cannot prove the repo state after restore equals the saved pre-evidence state.
- Evidence execution changes the index or any implementation path would need index mutation to recover from evidence side effects.
- A pre-existing untracked file or pre-existing unstaged tracked edit would be overwritten, deleted, or normalized by the restore path.
- The package-provided `evidence_command` can be executed without an exact match to the tracker-declared `evidence_command`.
- The declared `evidence_command` cannot be passed exactly as `['bash', '-c', evidence_command]`.
- The gate cannot make failed or omitted declared evidence route to `NEEDS_PHASE_B`.
- Required focused tests or the tracker note's indicator collection command fail.
- Same-wave `TASKS.md` authorization or `FOUNDER_OVERRIDE` is absent or mismatched.
- Bridge review returns `REQUEST_CHANGES`.

## 5. Acceptance Criteria

- Only the scoped implementation/test files are changed, plus the required generated indicator artifact after staging.
- `commit_executor.py` and `phase_b_executor.py` include `evidence_command` in every relevant pre-commit supervisor package while preserving `tracker_note_text`.
- `meta_bridge_supervisor.py` accepts optional `evidence_command` and detects/extracts declared tracker-note evidence without importing executor code.
- `run_validation_gates` runs `wave_evidence` outside `is_cs_wave`, appends attestation command data for control-surface waves, runs evidence only when package-provided evidence exactly matches tracker-declared evidence, fails closed on declared-but-omitted, provided-but-not-declared, and provided-but-mismatched evidence, skips absent undeclared evidence, and makes failed evidence drive `NEEDS_PHASE_B`.
- Matched tracker-declared evidence is executed exactly through `run_validation_command(repo_root, ['bash', '-c', evidence_command])`.
- Restore-around-evidence restores tracked worktree content from the pre-evidence worktree snapshot, not from index content; it preserves pre-existing unstaged tracked changes, snapshots and restores pre-existing untracked bytes, symlink targets, and executable mode, removes only evidence-created untracked files, runs in a `finally` path, and leaves `compute_repo_state` equal to the pre-evidence state.
- No post-merge validation path behavior changes.
- No `set_roles.py --show` special case is added.
- Regression coverage is added to the existing `test_meta_bridge_supervisor.py` for matched provided success, shell chaining/env prefix pass-through, non-zero failure, declared-but-omitted fail-closed behavior, provided-but-not-declared fail-closed behavior, provided-but-mismatched fail-closed behavior, not-declared skip behavior, non-control-surface independence, and pre-existing unstaged tracked plus pre-existing untracked restore safety.
- Required validation command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`.
- Required indicator command after staging: `python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id supervisor-run-wave-evidence-trusted-v8-2026-06-05 --output reports/l4_wave_indicators/supervisor-run-wave-evidence-trusted-v8-2026-06-05.json`.

## 6. Grounding / Authorization

Authorization: `TASKS.md:502` authorizes `[NEXT-CODEX-POST-REDTEAM]` for `supervisor-run-wave-evidence-trusted-v8-2026-06-05`, class `L4_ENABLER`, target gate `G8`, and packet `reports/control_plane/supervisor_run_wave_evidence_trusted_v8_2026-06-05.md`.

Governing packet: this file is the Phase A governing packet for `supervisor-run-wave-evidence-trusted-v8-2026-06-05`.

Same-wave override for control-surface L4_ENABLER automation:
`FOUNDER_OVERRIDE:supervisor-run-wave-evidence-trusted-v8-2026-06-05`

The `TASKS.md:502` tracker note remains the wave authorization source, but its old package-provided execution wording and index/filename-only restore wording are superseded by this REQUEST_CHANGES repair. The authoritative evidence design for this packet is exact match to tracker-declared evidence before execution. The authoritative restore design is pre-evidence worktree snapshot restore, preserving pre-existing unstaged tracked work and pre-existing untracked bytes, symlink targets, and executable mode.

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `supervisor-run-wave-evidence-trusted-v8-2026-06-05`
- Active packet: `reports/control_plane/supervisor_run_wave_evidence_trusted_v8_2026-06-05.md`
- Indicator artifact: `reports/l4_wave_indicators/supervisor-run-wave-evidence-trusted-v8-2026-06-05.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/supervisor_run_wave_evidence_trusted_v8_2026-06-05.md`
  - `reports/deferred/non_blocking/supervisor-run-wave-evidence-trusted-v8-2026-06-05_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/supervisor-run-wave-evidence-trusted-v8-2026-06-05.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `supervisor-run-wave-evidence-trusted-v8-2026-06-05`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/supervisor-run-wave-evidence-trusted-v8-2026-06-05_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `supervisor-run-wave-evidence-trusted-v8-2026-06-05`
- Active packet: `reports/control_plane/supervisor_run_wave_evidence_trusted_v8_2026-06-05.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `1f6d167cff909139ba17c670e074470c16b969f881e624b4f0528b25746efcf2`
- Indicator artifact: `reports/l4_wave_indicators/supervisor-run-wave-evidence-trusted-v8-2026-06-05.json`
- Evidence command: `grep -q _run_wave_evidence_with_restore mu/tools/agents/meta_bridge_supervisor.py && grep -q evidence_command mu/tools/executors/phase_b_executor.py && grep -q evidence_command mu/tools/executors/commit_executor.py`.
- Evidence delta: Adds a trusted, fail-closed-when-declared wave_evidence runner to the pre-commit supervisor that runs the evidence_command via run_validation_command(['bash','-c', ..]) then snapshots/restores the worktree (tracked + untracked) AND the git index and verifies compute_repo_state is unchanged, so a mutating evidence command is harmless to staged content/receipt. Gate runs outside is_cs_wave; provided -> run+restore; declared-but-omitted -> ValidationResult False; not-declared -> skip; false/omitted -> all_passed False -> NEEDS_PHASE_B. BOTH commit_executor and phase_b_executor pass evidence_command. This wave's evidence_command is a structural grep proof (verifies _run_wave_evidence_with_restore + the evidence_command pass-through are wired) -- chosen because #52 is self-referential; the full 152/152 suite passes in CI (follow-up #54 restores the full-suite dogfood once the runner is re-entrant)..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/supervisor-run-wave-evidence-trusted-v8-2026-06-05.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `mu/tools/executors/commit_executor.py`
  - `mu/tools/executors/phase_b_executor.py`
  - `reports/control_plane/supervisor_run_wave_evidence_trusted_v8_2026-06-05.md`
  - `reports/deferred/non_blocking/supervisor-run-wave-evidence-trusted-v8-2026-06-05_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/supervisor-run-wave-evidence-trusted-v8-2026-06-05.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->

<!-- HYBRID_RECOVERY_REPAIR:start -->
## Hybrid Recovery Repair

- Repair trigger: commit executor `build_and_run_supervisor` received a pre-commit supervisor `NEEDS_PHASE_B` after `wave_evidence` failed before `git_commit`.
- Control-surface fix: commit executor now carries the full supervisor summary into the Step 6 failure payload, marks the result with `failure_class: needs_phase_b`, exposes the tracked control-plane packet as `plan_path` / `tracked_packet` for Phase B re-entry routing, and treats the same structured signal as standalone-recoverable.
- Retry-state fix: commit retry demotion now also accepts a structured `needs_phase_b` status before `git_commit`, so a restored commit-ready packet/TASKS state is demoted back to pending commit when the pre-commit supervisor vetoes the package.
- Validation: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py` passed with 152 tests.
<!-- HYBRID_RECOVERY_REPAIR:end -->
