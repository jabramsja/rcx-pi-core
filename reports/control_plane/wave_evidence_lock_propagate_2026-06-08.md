# Wave Evidence Lock Propagate

Date: 2026-06-08
Status: Phase A (design -- not yet agent-reviewed or bridge-converged)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: wave-evidence-lock-propagate-2026-06-08
Phase-A-Lock: UNLOCKED
Purpose: Fix the #52 fail-closed P2 (PR #1082 bot finding, deferred to #54): the wave_evidence runner _run_wave_evidence_with_restore in mu/tools/agents/meta_bridge_supervisor.py acquires _MetaBridgeLock and, on lock contention, its `except Exception` caught the lock MetaBridgeError and returned (1, msg) -> a failed wave_evidence gate -> NEEDS_PHASE_B, so a concurrent supervisor run that should wait+retry (via run_meta_bridge_package's wait_for_lock_seconds loop) was falsely routed back to Phase B. Change ALREADY APPLIED + VERIFIED (2 files): (1) _run_wave_evidence_with_restore now re-raises MetaBridgeError (lock contention) so it propagates to the retry loop, while still catching other exceptions as a gate failure (_run_wave_evidence_with_restore_unlocked handles its own errors and never raises, so the only MetaBridgeError here is the lock); (2) test_evidence_restore_is_guarded_by_supervisor_lock now asserts the MetaBridgeError PROPAGATES (pytest.raises) + the evidence command did not run, instead of a gate failure. Verified: 152 supervisor tests + audit_fast green. L4_ENABLER: pipeline tooling only; no runtime/substrate dir; no host_semantics.

## Scope

wave-evidence-lock-propagate (L4_ENABLER): #52's _run_wave_evidence_with_restore converted lock contention (_MetaBridgeLock MetaBridgeError) into a failed wave_evidence gate -> false NEEDS_PHASE_B; now it re-raises the lock MetaBridgeError so run_meta_bridge_package's wait_for_lock_seconds retry loop waits + retries (the bot's prescribed fix). Other evidence/restore errors still become a gate failure. Test updated to assert propagation. Scope = 2 files: meta_bridge_supervisor.py + test_meta_bridge_supervisor.py. Verified 152 supervisor tests + audit_fast green. (Resolves the PR #1082 deferred P2.)

## Request from Post-Merge Supervisor

Fix the #52 fail-closed P2 (PR #1082 bot finding, deferred to #54): the wave_evidence runner _run_wave_evidence_with_restore in mu/tools/agents/meta_bridge_supervisor.py acquires _MetaBridgeLock and, on lock contention, its `except Exception` caught the lock MetaBridgeError and returned (1, msg) -> a failed wave_evidence gate -> NEEDS_PHASE_B, so a concurrent supervisor run that should wait+retry (via run_meta_bridge_package's wait_for_lock_seconds loop) was falsely routed back to Phase B. Change ALREADY APPLIED + VERIFIED (2 files): (1) _run_wave_evidence_with_restore now re-raises MetaBridgeError (lock contention) so it propagates to the retry loop, while still catching other exceptions as a gate failure (_run_wave_evidence_with_restore_unlocked handles its own errors and never raises, so the only MetaBridgeError here is the lock); (2) test_evidence_restore_is_guarded_by_supervisor_lock now asserts the MetaBridgeError PROPAGATES (pytest.raises) + the evidence command did not run, instead of a gate failure. Verified: 152 supervisor tests + audit_fast green. L4_ENABLER: pipeline tooling only; no runtime/substrate dir; no host_semantics.

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `wave-evidence-lock-propagate-2026-06-08`
- Active packet: `reports/control_plane/wave_evidence_lock_propagate_2026-06-08.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `c10ebbb126df5c762209f24a1d4829c72739c89aec52c02a77ea86dbe4617b34`
- Indicator artifact: `reports/l4_wave_indicators/wave-evidence-lock-propagate-2026-06-08.json`
- Evidence command: `grep -q 'wait_for_lock_seconds retry loop can' mu/tools/agents/meta_bridge_supervisor.py && grep -q 'Lock contention must PROPAGATE' mu/tests/tools/test_meta_bridge_supervisor.py`.
- Evidence delta: Re-raises the lock MetaBridgeError from _run_wave_evidence_with_restore so concurrent supervisor runs wait+retry (run_meta_bridge_package's wait_for_lock_seconds) instead of being falsely routed to NEEDS_PHASE_B; other evidence/restore errors still become a gate failure. Updated test_evidence_restore_is_guarded_by_supervisor_lock to assert propagation + that the evidence command did not run. Verified: 152 supervisor tests + audit_fast green. (Structural grep evidence_command because the supervisor's own wave_evidence runs it during this commit and a pytest of the supervisor suite would re-enter -- same non-self-referential pattern as #52.).
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/wave-evidence-lock-propagate-2026-06-08.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tests/tools/test_meta_bridge_supervisor.py`
  - `mu/tools/agents/meta_bridge_supervisor.py`
  - `reports/control_plane/wave_evidence_lock_propagate_2026-06-08.md`
  - `reports/l4_wave_indicators/wave-evidence-lock-propagate-2026-06-08.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
