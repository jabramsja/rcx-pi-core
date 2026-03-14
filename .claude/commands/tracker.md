# /tracker — RCX Wave Tracker Note Generator

Generates L4 execution contract tracker sync notes with required fields auto-populated.

## Usage
- `/tracker generate <wave-id> <class>` — Generate a tracker sync note
  - `<class>`: L4_STRUCTURAL, L4_ENABLER, or MAINTENANCE

## Steps

1. **Collect current baselines:**
   - `python3 mu/tools/checks/check_host_semantics_ratchet.py --json` → tracked markers
   - `python3 tools/checks/check_host_authority_inventory_ratchet.py` → authority/total inventory
   - `git diff --stat origin/dev...HEAD` → changed files

2. **Determine required fields based on class:**

   **All classes require:**
   - `wave_id`, `Class`, `target_gate_id`, `primary_blocker_class`, `primary_invariant_id`
   - `indicator_artifact_ref`, `indicator_collection_command`
   - `bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP`
   - `boot0_track_id`, `boot0_progress_state`

   **L4_STRUCTURAL additionally requires:**
   - `host_semantics_delta` (before/after from ratchet)
   - `structural_artifact_ref` (runtime files changed)
   - `evidence_command` (test command)
   - `evidence_delta` (what new evidence this wave produces)
   - `progress_proof_before` / `progress_proof_after` (must differ)
   - `post_gate_contract_sweep`

   **MAINTENANCE requires:**
   - `no_op_proof`, `defer_reason_code`

3. **Generate the note** in TASKS.md tracker sync note format.

4. **Generate the indicator artifact** at `reports/l4_wave_indicators/<wave-id>.json`:
   ```
   python3 mu/tools/metrics/collect_l4_wave_indicators.py --wave-id <wave-id> --range origin/dev...HEAD --output reports/l4_wave_indicators/<wave-id>.json
   ```

5. **Present** the note for founder review before appending to TASKS.md.

## Output
The complete tracker sync note ready to paste into TASKS.md, plus the indicator artifact path.
