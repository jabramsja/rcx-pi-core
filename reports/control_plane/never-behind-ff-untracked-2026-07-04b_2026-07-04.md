# Change Step 15b to fast-forward a clean-ancestor primary that has non-colliding untracked files instead of skipping (CODE change required, not test-only)

Date: 2026-07-04
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: never-behind-ff-untracked-2026-07-04b
Phase-A-Lock: LOCKED
Purpose: FOUNDER TOP PRIORITY, 3rd attempt (2 prior waves failed to make the intended CODE change). The founder primary (WorkingRCX) is 0-ahead + a clean ANCESTOR of dev (pure fast-forward possible) but Step 15b _sync_primary_worktree_to_base SKIPS the ff because the primary has untracked scratch files (reports/handoffs), writing behind_dev.json reason=dirty_primary_worktree -> the primary is PERMANENTLY behind dev. THIS SKIP IS THE BUG and must be CHANGED. The current skip-on-untracked-PRESENCE is TOO CONSERVATIVE: `git merge --ff-only` does NOT clobber untracked files -- git ABORTS the ff ONLY if an untracked file would be OVERWRITTEN (a real collision); non-colliding untracked scratch is SAFE to fast-forward over (git leaves it untouched). So attempting the ff PRESERVES never-clobber (git's own collision-abort) while achieving never-behind. Do NOT defend or re-assert the current skip behavior -- CHANGE it.

## Scope

mu/tools/executors/commit_executor.py (_sync_primary_worktree_to_base, Step 15b) -- REQUIRED CODE CHANGE -- plus a regression in mu/tests/tools/test_commit_executor_post_merge_cleanup.py that asserts the NEW ff-success behavior. The wave is INCOMPLETE if commit_executor.py is not modified. No runtime/substrate files; L4_ENABLER.

Files and surfaces in scope:

- TASKS.md -- tracker-sync authority. The 2026-07-04 tracker sync note for wave `never-behind-ff-untracked-2026-07-04b` is the single source of truth for this packet's L4 fields; the packet derives from it.

- `reports/deferred/non_blocking/never-behind-ff-untracked-2026-07-04b_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. **Change the untracked-only branch of `_sync_primary_worktree_to_base`** (`mu/tools/executors/commit_executor.py`). Today, when the primary is a clean ancestor of `origin/{base_branch}` and its only dirty paths are untracked (the `if not tracked_wip_paths:` case), the helper returns `_behind_dev_dirty_skip(...)` — it writes `behind_dev.json` and never attempts the ff. Change that branch to ATTEMPT `git merge --ff-only --no-overwrite-ignore origin/{base_branch}` (the same invocation the tracked-WIP and clean paths already use). No stash is needed — untracked files are never stashed and ride through a fast-forward untouched.
   - On ff **success**: set `synced=True`, `skipped=False`, record `new_sha`, clear the `behind_dev` signal, and log the sync. Non-colliding untracked founder scratch (reports/handoffs) is left byte-identical on disk.
   - On ff **failure** (a real collision — an untracked/ignored path that `origin/{base_branch}` would overwrite): fall back to the existing `_behind_dev_dirty_skip(...)` safe skip + `behind_dev` signal. Never clobber founder WIP; git's own collision-abort plus `--no-overwrite-ignore` preserves never-clobber.
2. **Add a greppable `FIX-NEVERBEHIND-FF-UNTRACKED` marker comment** at the changed site so the CODE change is mechanically detectable and a test-only / no-op wave cannot masquerade as complete (the exact gap that let the 2 prior attempts land empty).
3. **Add a hermetic ff-SUCCESS regression** to `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`: a clean-ancestor primary that is behind `origin/dev` and holds ONLY non-colliding untracked files (e.g. `HANDOFF_FOR_CODEX.md`) is fast-forwarded — assert `synced is True`, HEAD advanced to `origin/dev` (post-sync `behind_count == 0`), the untracked files still present and byte-identical, and no `behind_dev.json` written. (`_advance_origin_dev` / `_advance_origin_dev_add_file` helpers already exist for a non-colliding origin advance.)
4. **Reconcile the now-contradicting existing test** `test_sync_primary_writes_behind_dev_with_untracked_files_present`. Its origin advance (`_advance_origin_dev`, which touches only `seed.txt`) does NOT collide with its untracked `HANDOFF_FOR_CODEX.md` / `scratch_deferred_note.md`, so under the new behavior that case fast-forwards. Update it to assert the ff-SUCCESS outcome (or supersede it with the new hermetic test); leaving it asserting `synced is False` / `behind_dev_signal_written is True` would make the wave's own `evidence_command` RED.
5. **Regenerate the wave indicator artifact** via the note's `indicator_collection_command` so `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json` matches the landed diff.

## Constraints

What is NOT in scope for this wave:

- **L4_ENABLER — no runtime/substrate edits.** Do NOT touch `mu/host/python/rcx_pi/selfhost/`, `mu/host/js/`, or any L4 runtime dir. No L3-parity surface is involved (no projection or semantic change). `mu/tools/executors/` is tooling.
- **Do NOT touch the tracked-dirty stash-preserve path** (landed as `never-behind-dev-stash-preserve-2026-07-04`, dev `793fc5d3`). This wave changes ONLY the untracked-only branch (`if not tracked_wip_paths:`).
- **Do NOT weaken never-clobber.** Keep `--ff-only` and `--no-overwrite-ignore`. A real untracked/ignored collision MUST still abort to a safe skip; `test_sync_primary_skips_when_ff_would_overwrite_ignored_founder_wip` must stay GREEN.
- **Do NOT alter the other guards/paths:** GUARD-A (base-branch skip), GUARD-C (divergent-local-commit skip), GUARD-D (lock), the already-current clear, or the PULL-ONLY contract (no push/checkout/force/reset added to the helper).
- **Do NOT change any L4 field.** `evidence_command`, `target_gate_id` (G8), Class (`L4_ENABLER`), and all L4 fields are owned by the 2026-07-04 TASKS.md tracker note; the packet derives from it.
- **Pipeline-only.** No manual git operations; commit through `commit_executor.py`.
- **Docs-only / test-only completion is DISALLOWED** (see Purpose): the wave is INCOMPLETE unless `commit_executor.py` is modified.

## Stop conditions

- **STOP if the fix would require host-only semantics or a runtime/substrate edit** — escalate; the wave must stay `L4_ENABLER` tooling.
- **STOP if never-clobber cannot be preserved** — if `git merge --ff-only --no-overwrite-ignore` cannot be shown to abort on a real untracked/ignored collision, do not land a change that risks clobbering founder WIP.
- **STOP if the `evidence_command` can only pass by reverting the `commit_executor.py` change** — a green run over a test-only / no-op diff is the exact trap the 2 prior attempts fell into; that is a FAIL, not a pass.
- **STOP if the `commit_executor.py` diff is empty at commit handoff** — hard stop for this wave.
- **STOP and request the founder decision** on any POLICY_BOUND conflict (e.g., a gate that can only be satisfied by touching a forbidden surface).

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

All must hold at commit handoff. Criteria 1–2 are the mechanical proof-of-CODE-change that closes the no-op / test-only gap the 2 prior attempts fell through.

1. **CODE change present (not test-only, not no-op).** `grep -n "FIX-NEVERBEHIND-FF-UNTRACKED" mu/tools/executors/commit_executor.py` returns a hit at the changed site, AND the wave's committed diff for `mu/tools/executors/commit_executor.py` (against the wave merge-base with `origin/dev`) is NON-EMPTY and modifies `_sync_primary_worktree_to_base`. An empty `commit_executor.py` diff FAILS the wave regardless of test results.
2. **Behavior change proven by a hermetic ff-SUCCESS test.** The new test in `test_commit_executor_post_merge_cleanup.py` drives a clean-ancestor primary behind `origin/dev` holding ONLY non-colliding untracked files and asserts `outcome["synced"] is True`, HEAD fast-forwarded to `origin/dev` (post-sync `behind_count == 0`), untracked files present and byte-identical, and `behind_dev.json` NOT written (cleared).
3. **Contradicting existing test reconciled.** `test_sync_primary_writes_behind_dev_with_untracked_files_present` no longer asserts an untracked-only skip (`synced is False` / `behind_dev_signal_written is True`); it asserts the new ff-SUCCESS behavior or is superseded by the new hermetic test.
4. **Never-clobber preserved.** `test_sync_primary_skips_when_ff_would_overwrite_ignored_founder_wip` stays GREEN — a real collision still aborts the ff to a safe skip that preserves founder WIP.
5. **Evidence gate green WITH the code change in place.** `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_commit_executor_post_merge_cleanup.py -p no:xdist -q` passes and `python3 -m py_compile mu/tools/executors/commit_executor.py` succeeds.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `never-behind-ff-untracked-2026-07-04b`.
- Governing packet: this file, `reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md`.
- TASKS.md authority: the 2026-07-04 tracker sync note for wave `never-behind-ff-untracked-2026-07-04b` is canonical for this packet's L4 fields.
- Authorization: Founder TOP-PRIORITY 3rd attempt 2026-07-04: prior waves did not make the code change; this one mandates the commit_executor.py behavior change (attempt-ff on non-colliding untracked). FOUNDER_OVERRIDE:never-behind-ff-untracked-2026-07-04b.

FOUNDER_OVERRIDE:never-behind-ff-untracked-2026-07-04b

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `never-behind-ff-untracked-2026-07-04b`
- Active packet: `reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-ff-untracked-2026-07-04b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `never-behind-ff-untracked-2026-07-04b`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/never-behind-ff-untracked-2026-07-04b_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id never-behind-ff-untracked-2026-07-04b --output reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-ff-untracked-2026-07-04b_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: never-behind-ff-untracked-2026-07-04b.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `never-behind-ff-untracked-2026-07-04b`
- Active packet: `reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `58ebd9c813b5452b7b3499f880c929b992b6652373eedab2a5b9623ec729399a`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md`, `reports/deferred/non_blocking/never-behind-ff-untracked-2026-07-04b_bridge_nonblockers.md`, `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-ff-untracked-2026-07-04b_2026-07-04.md`
  - `reports/deferred/non_blocking/never-behind-ff-untracked-2026-07-04b_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/never-behind-ff-untracked-2026-07-04b.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
