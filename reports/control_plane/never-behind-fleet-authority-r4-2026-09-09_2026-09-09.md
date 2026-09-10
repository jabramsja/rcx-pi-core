# Never-Behind Fleet Authority R4

Date: 2026-09-09
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEVER-BEHIND-FLEET-AUTHORITY]
Wave ID: never-behind-fleet-authority-r4-2026-09-09
Phase-A-Lock: LOCKED
Native-Stub-Packet-Contract: required=true; producer=launch_wave.py; version=1
Native-Stub-Packet-Contract-Digest: 43d28fddfb042325a0ff47b80ab83626a42894b9305816a55072f91f9294bab4
Purpose: Correct only the two R3 pre-commit blockers on top of the preserved green implementation: avoid creating an invalid transaction for a dual-classified path, and make terminal readiness a single-use mutation-under-lock operation rather than a reusable GO result.

## Scope

Seed the exact preserved R3 executor/test bytes, make two bounded corrections in those files, synchronize TASKS, and generate same-wave governance artifacts; no other code, PR, or fleet surface is in scope.

Files and surfaces in scope:

- TASKS.md — record #1278 landed, R1-R3 stopped with preservation evidence, R4 current, and retain the exact serial queue
- mu/tools/executors/commit_executor.py — seed R3 blob d63c38be1b7a39e98405fce278fdfb6e785519ad and correct only dual classification plus terminal action atomicity
- mu/tests/tools/test_commit_executor_post_merge_cleanup.py — seed R3 blob ef337c6d63500ba9a9589cc38173b48065d38e1d and add focused regressions for the two corrections
- reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md — required builder-generated locked packet
- reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json — required same-wave L4 indicator
- reports/deferred/non_blocking/never-behind-fleet-authority-r4-2026-09-09_bridge_nonblockers.md — optional and absent unless a genuine nonblocking review finding is recorded
- TASKS.md -- tracker-sync authority. The 2026-09-09 tracker sync note for wave `never-behind-fleet-authority-r4-2026-09-09` is the single source of truth for this packet's L4 fields; the packet derives from it.

## Work items

1. Use this JSON only as the operator stub and launch through launch_wave.py. Start source, target, and comparison at exact #1278 merge ea690246e953b71236329f6b01c3bc8999477c7f. Never hand-edit the generated packet.
2. Treat R1, R2, and R3 as stopped immutable evidence. R3 is preserved read-only at /Users/jeffabrams/Desktop/RCX_X/RCXStack/RCXStackminimal/WorkingRCX-preservation/never-behind-fleet-authority-r3-precommit-needs-phase-a-20260909 with packet SHA-256 3daa238f2273c951c1916c897015c9fb5cdbe19d8228187dfaa0b1e3b74cb42a and full staged-diff SHA-256 028a28e5ada9162de3b2e47602fcafd1fe00319f3087138ed39302fc2350832d.
3. Verify R3 has no unstaged candidate delta and its staged executor/test blobs are d63c38be1b7a39e98405fce278fdfb6e785519ad and ef337c6d63500ba9a9589cc38173b48065d38e1d. Mechanically seed those exact two files into R4, then make only the two authorized corrections; preserve all other reviewed R3 behavior.
4. Before allocating or publishing a primary-sync transaction, detect any path that Git simultaneously reports as tracked dirty and untracked, such as a staged deletion followed by a recreated file. Safe-skip that unsupported dual-classified state with exact path evidence and the existing behind-dev signal, leaving HEAD, bytes, index intent, stash list, and transaction directory unchanged. Do not implement broader support for this synthetic-only state.
5. Replace reusable terminal authorization with a one-shot API that receives the exact target identity and terminal-action callback, takes the common-dir lock, freshly fetches origin/dev, revalidates common-dir/worktree/branch/HEAD identity and behind count, invokes the callback at most once only while the same lock is still held and behind is zero, and returns the action outcome after releasing the lock. A diagnostic readiness observation may remain only if explicitly marked non-authoritative and unusable for mutation.
6. Add focused regressions proving the staged-delete/recreated-file case safe-skips before transaction creation and is retryable without permanent journal HOLD; proving a dev advance after an earlier diagnostic observation prevents the callback; proving a competing common-dir lock cannot enter during the callback; and proving stale identity, callback failure, or retry never causes multiple callback invocations. Retain and rerun all existing 70 tests.
7. Synchronize TASKS without loss: preserve #1278 and all four PR evidence holds; record R1 stopped pre-implementation, R2 stopped on inventory wording, and R3 stopped at pre-commit with exact preservation path/hashes and two blockers; make R4 CURRENT; after landing make PR-DISPOSITION-EXECUTION sole NEXT and require its terminal operations plus fleet apply to use the one-shot callback; retain the full later queue and Mu production.
8. The required changed set is exactly TASKS.md, executor, tests, R4 packet, and R4 indicator. The sixth allowlisted nonblocker report is optional and appears only for a genuine nonblocking finding. Land through independent Codex review, providerless commit, PR, required CI/review, merge, governed post-merge sync, and cleanup; perform no old-PR disposition or fleet action.

## Constraints

- Candidate changes are a subset of the six-path allowlist. Five paths are required; the optional nonblocker path is not required and its absence is compliant.
- Start executor and test work from the exact preserved R3 blobs. Modify only what is necessary for the two pre-commit findings; do not redesign the journal, sync path, tracker system, or future cleanup workflow.
- All model-bearing roles and pager remain Codex gpt-5.6-sol ultra; commit is providerless. Phase A and Phase B agents are foreground-only and do not spawn, delegate, sleep, poll, or call wait surfaces.
- Do not mutate R1-R3, an old PR, a fleet directory, founder dirty primary before governed post-merge, Claude-owned files, executor config, recovery gate, or unrelated source. Only the R4 carrier follows normal remote lifecycle after COMMIT_GO.
- The dual-classified synthetic state is handled by a pre-transaction safe skip, not by new move/stash semantics. The existing behind-dev signal is sufficient and the path must remain retryable after the user resolves its index/worktree state.
- A readiness dictionary or earlier GO is never terminal authorization. The terminal action itself must execute at most once inside the same locked fresh-fetch and identity/behind-zero critical section.
- Do not add speculative or unrelated edge cases. Genuine nonblocking findings are recorded in the optional same-wave report and do not delay landing.

## Stop conditions

- Stop before launch unless the fresh R4 source/target/comparison equal ea690246e953b71236329f6b01c3bc8999477c7f, R3 preservation hashes and seed blobs match, all model-bearing roles are Codex gpt-5.6-sol ultra, and commit is providerless.
- Stop implementation if work needs a seventh candidate path, changes unrelated R3 behavior, performs any old-PR/fleet/founder-primary mutation, or expands dual-classified-path support beyond safe skip.
- Stop as DEFECT if the dual-classified state creates a transaction, changes HEAD/bytes/index/stashes, or leaves a permanent recovery journal rather than a precise retryable behind-dev signal.
- Stop as DEFECT if a terminal callback can run after the lock is released, without a fresh fetch/identity/behind-zero check, more than once, or from a reusable prior GO result.
- Do not stop or widen for style, a genuine nonblocking finding, a nonoccurring unrelated edge case, or compliant absence of the optional report.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_commit_executor_post_merge_cleanup.py`

## Acceptance criteria

- The five required candidate paths and no out-of-allowlist path are staged; the optional sixth path is absent unless a genuine nonblocking finding exists. The builder packet remains locked.
- R4 starts from the exact R3 executor/test blobs and preserves every existing journal, restart, WIP, ignored-file, safe-fast-forward, and readiness regression outside the two bounded corrections.
- A staged deletion plus recreated untracked file at an upstream-changed path safe-skips before transaction creation; founder bytes and staged deletion remain exact, HEAD and stash list do not change, no invalid journal persists, and a later cleanly resolved state can retry normally.
- The one-shot terminal API holds the common-dir lock continuously across fresh fetch, exact identity and behind-zero validation, and the callback; a stale diagnostic GO has no authority; the callback runs zero times on rejection and at most once on success or failure.
- The full focused module passes with the new regressions, staged L4 passes with net host semantic delta zero, candidate authority remains exact, every model-bearing role is Codex gpt-5.6-sol ultra, and commit is providerless.
- TASKS records R1-R3 stopped with exact evidence, R4 current, PR disposition sole next after landing with callback requirement, every PR/fleet/recovery/PR1219/later/Mu-production obligation retained, and no false claim that future callers are already wired.
- Independent review and pre-commit return GO/COMMIT_GO, required CI/review pass, R4 merges, governed post-merge primary sync runs, carrier cleanup completes, and no old PR or WorkingRCX fleet directory is mutated in this wave.

## Grounding / Authorization

- Task: [NEVER-BEHIND-FLEET-AUTHORITY]; wave id `never-behind-fleet-authority-r4-2026-09-09`.
- Governing packet: this file, `reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md`.
- TASKS.md authority: the 2026-09-09 tracker sync note for wave `never-behind-fleet-authority-r4-2026-09-09` is canonical for this packet's L4 fields.

FOUNDER_OVERRIDE:never-behind-fleet-authority-r4-2026-09-09

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `never-behind-fleet-authority-r4-2026-09-09`
- Active packet: `reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md`
  - `reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id never-behind-fleet-authority-r4-2026-09-09 --output reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md`, `reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json`..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: never-behind-fleet-authority-r4-2026-09-09.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `never-behind-fleet-authority-r4-2026-09-09`
- Active packet: `reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `b6cb6786ede5fb0c70f7f49838d98ea85a9403e8e9f138aef61522be17658e25`
- Indicator artifact: `reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json`
- Evidence command: `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -x --tb=short -p no:cacheprovider mu/tests/tools/test_commit_executor_post_merge_cleanup.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package. scope_refs: `TASKS.md`, `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`, `mu/tools/executors/commit_executor.py`, `reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md`, `reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json`..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_commit_executor_post_merge_cleanup.py`
  - `mu/tools/executors/commit_executor.py`
  - `reports/control_plane/never-behind-fleet-authority-r4-2026-09-09_2026-09-09.md`
  - `reports/l4_wave_indicators/never-behind-fleet-authority-r4-2026-09-09.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
