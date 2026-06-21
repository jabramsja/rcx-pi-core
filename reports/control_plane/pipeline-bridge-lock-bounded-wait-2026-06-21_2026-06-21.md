# NEXT-CODEX-POST-REDTEAM - bridge supervisor lock bounded-wait (kernel-flock-authoritative) so parallel pipeline waves serialize instead of one failing on immediate non-blocking lock contention

Date: 2026-06-21
Status: IMPLEMENTED / LOCAL EVIDENCE
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: pipeline-bridge-lock-bounded-wait-2026-06-21
Phase-A-Lock: LOCKED
Purpose: STRUCTURAL pipeline hardening (founder-directed: fix parallel pipelines so they do not collide). VERIFIED ROOT CAUSE: `_MetaBridgeLock.__enter__` in mu/tools/agents/meta_bridge_supervisor.py acquires the meta-bridge supervisor lock with a NON-BLOCKING flock (`fcntl.flock` with `LOCK_EX | LOCK_NB`) and, on a held lock (EWOULDBLOCK), raises MetaBridgeError 'Another meta-bridge supervisor is running. Wait for it to finish' IMMEDIATELY. The message says to wait but the code never waits, so when two pipeline waves run in parallel and both reach the bridge, the second one fails instantly (observed: a 2nd concurrent wave's Phase-A bridge died with failure_class stale_bridge_lock + tier1_failed while the first wave held the lock). FIX: make the lock acquire a BOUNDED-WAIT -- retry the non-blocking flock with short backoff up to a bounded timeout so a contending wave serializes (waits for the holder to finish), and raise (fail closed) only when the timeout elapses with the flock STILL HELD. The kernel flock is the SOLE authority for who holds the lock. A dead-holder lock needs NO special handling: the kernel releases an flock automatically when the holding process dies (its fd closes), so the bounded-wait retry simply acquires it on a later attempt. The packet does NOT parse the lock-metadata PID to clear or bypass a held flock (see Round-1 review fix below). Result: parallel pipeline waves serialize gracefully on the bridge instead of one failing; a genuinely-stale (dead-holder) lock is recovered automatically via the kernel-released flock, not via metadata-driven unlinking.

## Round-1 bridge review fix (REQUEST_CHANGES, DEFECT)

Reviewer finding (high / DEFECT): a stale metadata PID is NOT sufficient authority to clear or bypass a held supervisor flock. Verified against current code: `_lock_metadata_payload` / `_write_lock_metadata` record the holder PID, but `_MetaBridgeLock.__enter__` writes that metadata only AFTER `fcntl.flock` succeeds, and `__exit__` clears the metadata while still holding the flock and retains the lockfile inode. Therefore a dead PID in the file does NOT prove that no live process holds the kernel flock -- it can be stale metadata while another process currently owns the flock. Worse, "clearing"/recreating the lockfile on that basis changes the inode, and flock mutual exclusion is per-inode (per open file description), so a live holder on the old inode and a new acquirer on a recreated inode could BOTH believe they hold the lock -- violating the single-supervisor invariant.

Resolution: REMOVE the metadata-PID stale-probe-and-clear from the design. The bounded-wait retry on the kernel flock is the complete, safe fix -- it serializes live contenders AND recovers dead-holder locks (the kernel already released them, so a retry acquires). The recorded holder metadata MAY be surfaced read-only in the timeout error for operator diagnostics, but MUST NEVER gate acquisition, clear the lock, or unlink/recreate the lockfile.

## Scope

Make the meta-bridge supervisor lock acquire BOUNDED-WAIT so parallel pipeline waves serialize instead of failing on immediate non-blocking contention. The kernel flock stays the sole authority; the design does not read the metadata PID to clear or bypass a held lock, and never changes the lockfile inode. Agent tooling + an existing test file; no runtime dirs; no new test file. TASKS.md is tracker-sync authority.

Files and surfaces in scope:

- mu/tools/agents/meta_bridge_supervisor.py (MODIFY) -- in `_MetaBridgeLock.__enter__`, replace the immediate raise on a non-blocking flock contention with a bounded-wait retry loop: repeat the non-blocking `fcntl.flock(LOCK_EX | LOCK_NB)` acquire with short backoff up to a named bounded-wait timeout, and raise the existing MetaBridgeError only when the timeout elapses with the flock STILL HELD (fail-closed preserved). Add the bounded-wait timeout (and backoff) as a named constant, reusing the existing `_read_bounded_timeout_env` helper (the same one backing `GIT_COMMAND_TIMEOUT_S` / `VALIDATION_COMMAND_TIMEOUT_S`) so the value is env-overridable and clamped. Do NOT switch to an unbounded blocking flock. Do NOT parse the metadata PID to clear/bypass the lock, and do NOT unlink/recreate the lockfile (the inode must stay stable for flock). Keep `__exit__` and the metadata write (`_lock_metadata_payload` / `_write_lock_metadata`) unchanged.
- mu/tests/tools/test_meta_bridge_supervisor.py (MODIFY -- existing file, do NOT create a new test file) -- add a regression proving (1) a lock whose flock is held by a live holder makes a second `__enter__` WAIT (bounded) and then SUCCEED once the holder releases -- and RAISE (fail-closed) if the holder never releases within the timeout; and (2) a lockfile that merely contains stale (dead-PID) metadata but is NOT flock-held is acquired IMMEDIATELY, proving acquisition depends on the free kernel flock and not on metadata PID liveness, and that the lockfile is never unlinked/recreated (inode preserved).
- reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json (GENERATED).
- TASKS.md -- tracker-sync authority. The 2026-06-21 tracker sync note for wave `pipeline-bridge-lock-bounded-wait-2026-06-21` is the single source of truth for this packet's L4 fields; the packet derives from it. NOTE: that note's prose still mentions probing the metadata PID to clear a stale lock; per current code truth and the Round-1 bridge review, that mechanism is dropped -- only the note's L4 fields and the bounded-wait/serialization outcome are binding.

- `reports/deferred/non_blocking/pipeline-bridge-lock-bounded-wait-2026-06-21_bridge_nonblockers.md`
  - Same-wave Phase B/commit generated deferred non-blocking bridge findings packet only; no unrelated deferred report is authorized by this wave.

## Work items

1. Read `_MetaBridgeLock.__enter__` / `__exit__` and `_lock_metadata_payload` / `_write_lock_metadata` to confirm the kernel flock -- not the metadata -- is the authority, and that metadata is written only after the flock is held and cleared before release. Read `_read_bounded_timeout_env` and its existing `GIT_COMMAND_TIMEOUT_S` / `VALIDATION_COMMAND_TIMEOUT_S` callers to reuse the established constant pattern.
2. Add a named bounded-wait timeout constant (and a short backoff) for the lock acquire, via `_read_bounded_timeout_env` so it is env-overridable and clamped like the other timeouts (this also lets the regression drive a small, deterministic timeout). Do not switch to an unbounded blocking flock that could hang forever.
3. Replace the immediate raise in `__enter__` with a bounded-wait retry loop around the non-blocking `fcntl.flock(LOCK_EX | LOCK_NB)`: on EWOULDBLOCK, sleep the backoff and retry until the timeout. Do NOT read the metadata PID to clear or bypass the lock; do NOT unlink/recreate the lockfile (preserve inode stability). A dead holder needs no special handling -- the kernel already released its flock, so a retry acquires it.
4. Raise the existing MetaBridgeError only when the bounded timeout elapses with the flock STILL HELD (fail-closed preserved). Optionally enrich the message with the elapsed wait and the read-only recorded holder for diagnostics -- explicitly without using it to gate acquisition or clear the lock.
5. Add the regression to the EXISTING mu/tests/tools/test_meta_bridge_supervisor.py (no new test file): live-holder contention waits-then-succeeds (and times-out-raises if never released); a lockfile with stale dead-PID metadata but no held flock is acquired immediately and the lockfile is not unlinked/recreated.
6. Run the evidence_command; confirm the lock tests pass; emit the indicator.

## Constraints

- Use the pipeline launcher + dispatcher Phase A and Phase B path; no manual implementation or commit path.
- L4_ENABLER: do NOT touch runtime dirs (mu/host/**, rcx_pi/selfhost/**). Agent tooling + tests only.
- Do NOT create a new test file; add the regression to the existing mu/tests/tools/test_meta_bridge_supervisor.py.
- BOUNDED wait only -- a named timeout constant + bounded backoff; never an unbounded blocking flock (it must not hang forever).
- The kernel flock is the SOLE authority. Do NOT parse the metadata PID to decide whether to clear or bypass the lock, and do NOT unlink, recreate, or otherwise change the lockfile inode -- flock mutual exclusion is per-inode, so an inode swap would break single-supervisor enforcement. The recorded holder metadata may be read for diagnostics only and must never influence acquisition or clearing.
- Preserve the fail-closed raise on timeout-with-flock-still-held, and keep the existing `__exit__` metadata-clear/unlock behavior and the metadata-write surfaces (`_lock_metadata_payload` / `_write_lock_metadata`) unchanged.

## Stop conditions

- Stop done when the evidence_command passes (live-holder contention waits-then-succeeds, and times-out-raises if never released; a stale-metadata lockfile with no held flock is acquired immediately) and the indicator is collected.
- Halt as POLICY_BOUND if a bounded-wait retry on the kernel flock cannot serialize contenders without reintroducing metadata-PID authority or an inode swap; surface that precisely rather than clearing locks unsafely.
- Do not commit without a real handoff artifact and gate-green evidence.

## Validation gates

- evidence_command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`

## Acceptance criteria

- A second acquire while the flock is held by a live holder waits (bounded) and succeeds after release, instead of raising immediately; if the holder never releases within the timeout, it raises (fail-closed).
- A lockfile that contains only stale (dead-PID) metadata but is NOT flock-held is acquired immediately -- acquisition depends on the free kernel flock, not on PID liveness -- and the lockfile is never unlinked or recreated (inode preserved).
- The design does not parse the metadata PID to clear or bypass a held flock (Round-1 DEFECT resolved).
- Regression in the existing test file proves the above; no runtime dirs; no new test file.
- evidence_command clean; indicator emitted.

## Grounding / Authorization

- Task: [NEXT-CODEX-POST-REDTEAM]; wave id `pipeline-bridge-lock-bounded-wait-2026-06-21`.
- Governing packet: this file, `reports/control_plane/pipeline-bridge-lock-bounded-wait-2026-06-21_2026-06-21.md`.
- TASKS.md authority: the 2026-06-21 tracker sync note for wave `pipeline-bridge-lock-bounded-wait-2026-06-21` is canonical for this packet's L4 fields (Class L4_ENABLER, target_gate_id G8, evidence_command above, indicator_artifact_ref reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json, primary_blocker_class INTEGRATION, primary_invariant_id INV_STRUCTURAL_FORWARD_MOTION, bootstrap_endgame_policy SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP, boot0_track_id V1, boot0_progress_state HOLD). The note's prose describing a metadata-PID stale-clear is superseded by current code truth and the Round-1 bridge review; the binding outcome is bounded-wait serialization with the kernel flock as the sole authority.
- Authorization: Founder-directed 2026-06-21 ('fix structurally so this does not happen again with parallel pipelines'). Structural fix for the parallel-wave bridge-lock collision (LOCK_NB immediate-fail). Auto-authorized structural pipeline fix (feedback_manual_then_structural_autonomy).

FOUNDER_OVERRIDE:pipeline-bridge-lock-bounded-wait-2026-06-21

<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:start -->
## Phase B Indicator Scope Reconciliation

- Refresh wave: `pipeline-bridge-lock-bounded-wait-2026-06-21`
- Active packet: `reports/control_plane/pipeline-bridge-lock-bounded-wait-2026-06-21_2026-06-21.md`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json`
- Purpose: Phase B mechanically collected and staged this same-wave L4 indicator before pre-commit supervisor review so the tracker note, Gate 8 package, and governing packet describe one staged scope.
- Scope binding: no indicator file other than the artifact above is in scope for this wave.
- Authorized staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `reports/control_plane/pipeline-bridge-lock-bounded-wait-2026-06-21_2026-06-21.md`
  - `reports/deferred/non_blocking/pipeline-bridge-lock-bounded-wait-2026-06-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json`
<!-- PHASE_B_INDICATOR_SCOPE_REFRESH:end -->

<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:start -->
## Same-Wave Deferred Non-Blocking Authorization

- Refresh wave: `pipeline-bridge-lock-bounded-wait-2026-06-21`
- Purpose: Phase B and commit automation may stage the same-wave non-blocking bridge findings packet as deferred follow-up instead of blocking an otherwise commit-ready wave.
- Authorized deferred packet(s):
  - `reports/deferred/non_blocking/pipeline-bridge-lock-bounded-wait-2026-06-21_bridge_nonblockers.md`
- Scope binding: the packet(s) above are in scope only as generated same-wave non-blocking bridge findings packets.
- Acceptance binding: the final touched-file set may include the packet(s) above when they are also present in `deferred_items` or current staged files.
<!-- SAME_WAVE_DEFERRED_NON_BLOCKING_AUTH:end -->

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json.
- `indicator_collection_command`: python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id pipeline-bridge-lock-bounded-wait-2026-06-21 --output reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json.
- `target_gate_id`: G8.
- `evidence_command`: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`.
- `evidence_delta`: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-bridge-lock-bounded-wait-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: pipeline-bridge-lock-bounded-wait-2026-06-21.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `pipeline-bridge-lock-bounded-wait-2026-06-21`
- Active packet: `reports/control_plane/pipeline-bridge-lock-bounded-wait-2026-06-21_2026-06-21.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `1545c75629c801fafaa15615d97f7573d9b59196f19b8ebda225fa2ee0fdc93c`
- Indicator artifact: `reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json`
- Evidence command: `PYTHONHASHSEED=0 python3 -m pytest -x --tb=short mu/tests/tools/test_meta_bridge_supervisor.py`.
- Evidence delta: (1) Phase B converged on the locked plan at reports/control_plane/pipeline-bridge-lock-bounded-wait-2026-06-21_2026-06-21.md. (2) Final pytest gate covered 1 test file(s) from the wave-owned diff. (3) Pre-commit supervisor receipt remains pending for the current staged package.
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `reports/control_plane/pipeline-bridge-lock-bounded-wait-2026-06-21_2026-06-21.md`
  - `reports/deferred/non_blocking/pipeline-bridge-lock-bounded-wait-2026-06-21_bridge_nonblockers.md`
  - `reports/l4_wave_indicators/pipeline-bridge-lock-bounded-wait-2026-06-21.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
