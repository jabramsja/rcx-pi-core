# Renew-Theater-Allowlist-Expired-Entries-2026-06-16

Date: 2026-06-16
Status: Phase B (locked, implementing)
Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: renew-theater-allowlist-expired-entries-2026-06-16
Phase-A-Lock: LOCKED
Purpose: Renew the 9 expired founder-owned entries in mu/tools/checks/theater_allowlist.json by bumping their expires_on from 2026-06-15 to 2026-07-15. These 9 (4 target_wave n15-provenance, 5 target_wave s1a-vm-evidence; all owner=founder, classification heuristic_false_positive) expired by date and made check_theater_risk_ratchet.py FAIL (9 expired), which fails pre-push-fast and the CI green-gate DEV-WIDE for every wave. The entries are documented classifier false-positives: the n15-provenance tests verify no-raise behavior (the AST classifier does not count no-exception-is-pass as an assertion); the s1a-vm-evidence tests are intentionally observational performance profiling. Data-only change to the allowlist JSON: EXACTLY 9 expires_on value bumps (2026-06-15 -> 2026-07-15), no entries added or removed, no other field changed, no runtime/test/seed change. This extends the founder's existing acceptance by one month, matching the 2026-06-02 renewal precedent (75 entries renewed then).

## Scope

Renew 9 expired founder-owned theater_allowlist entries (2026-06-15 -> 2026-07-15); unblocks the dev-wide green-gate / pre-push theater ratchet.

## Request from Post-Merge Supervisor

Renew the 9 expired founder-owned entries in mu/tools/checks/theater_allowlist.json by bumping their expires_on from 2026-06-15 to 2026-07-15. These 9 (4 target_wave n15-provenance, 5 target_wave s1a-vm-evidence; all owner=founder, classification heuristic_false_positive) expired by date and made check_theater_risk_ratchet.py FAIL (9 expired), which fails pre-push-fast and the CI green-gate DEV-WIDE for every wave. The entries are documented classifier false-positives: the n15-provenance tests verify no-raise behavior (the AST classifier does not count no-exception-is-pass as an assertion); the s1a-vm-evidence tests are intentionally observational performance profiling. Data-only change to the allowlist JSON: EXACTLY 9 expires_on value bumps (2026-06-15 -> 2026-07-15), no entries added or removed, no other field changed, no runtime/test/seed change. This extends the founder's existing acceptance by one month, matching the 2026-06-02 renewal precedent (75 entries renewed then).

<!-- L4_FIELDS_FROM_TRACKER:start -->
**L4 fields (auto-derived from the canonical TASKS.md tracker note -- single source of truth; do not hand-edit):**

- `primary_blocker_class`: INTEGRATION.
- `primary_invariant_id`: INV_STRUCTURAL_FORWARD_MOTION.
- `indicator_artifact_ref`: reports/l4_wave_indicators/renew-theater-allowlist-expired-entries-2026-06-16.json.
- `indicator_collection_command`: python3 tools/metrics/collect_l4_wave_indicators.py --wave-id renew-theater-allowlist-expired-entries-2026-06-16 --output reports/l4_wave_indicators/renew-theater-allowlist-expired-entries-2026-06-16.json.
- `target_gate_id`: G8.
- `evidence_command`: `python3 tools/checks/check_theater_risk_ratchet.py`.
- `evidence_delta`: mu/tools/checks/theater_allowlist.json staged diff is EXACTLY 9 expires_on value bumps 2026-06-15 -> 2026-07-15 (4 n15-provenance + 5 s1a-vm-evidence, all owner=founder, classification heuristic_false_positive); no entries added/removed, no other field changed. check_theater_risk_ratchet.py now exits 0 (PASS: no expired) instead of FAIL: 9 expired, so pre-push-fast and the CI green-gate pass again..
- `bootstrap_endgame_policy`: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP.
- `boot0_track_id`: V1.
- `boot0_progress_state`: HOLD.
- `founder_override`: renew-theater-allowlist-expired-entries-2026-06-16.
<!-- L4_FIELDS_FROM_TRACKER:end -->

<!-- COMMIT_PATH_TRUTH_REFRESH:start -->
## Commit Path Truth Refresh

- Refresh wave: `renew-theater-allowlist-expired-entries-2026-06-16`
- Active packet: `reports/control_plane/renew-theater-allowlist-expired-entries-2026-06-16_2026-06-16.md`
- Commit status: `pre_commit_supervisor_pending`
- Tracker note sha256: `b6896e2ba42591a219c085ead56386c540d37abd147f66bfb273440d5cb352b8`
- Indicator artifact: `reports/l4_wave_indicators/renew-theater-allowlist-expired-entries-2026-06-16.json`
- Evidence command: `python3 tools/checks/check_theater_risk_ratchet.py`.
- Evidence delta: mu/tools/checks/theater_allowlist.json staged diff is EXACTLY 9 expires_on value bumps 2026-06-15 -> 2026-07-15 (4 n15-provenance + 5 s1a-vm-evidence, all owner=founder, classification heuristic_false_positive); no entries added/removed, no other field changed. check_theater_risk_ratchet.py now exits 0 (PASS: no expired) instead of FAIL: 9 expired, so pre-push-fast and the CI green-gate pass again..
- Evidence handles:
  - `indicator`: `reports/l4_wave_indicators/renew-theater-allowlist-expired-entries-2026-06-16.json`
- Current staged files:
  - `TASKS.md`
  - `mu/tools/checks/theater_allowlist.json`
  - `reports/control_plane/renew-theater-allowlist-expired-entries-2026-06-16_2026-06-16.md`
  - `reports/l4_wave_indicators/renew-theater-allowlist-expired-entries-2026-06-16.json`
<!-- COMMIT_PATH_TRUTH_REFRESH:end -->
