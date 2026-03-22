# Control-Plane Lane

Purpose: hold tracked founder-facing control-plane packets that canonical
trackers such as `TASKS.md` are allowed to reference directly.

This lane is for:

- active meta-bridge rollout packets
- tracked wave-orchestration/control-plane sequencing
- parked post-redteam queue packets once they become canonical execution
  references

This lane is not for:

- implementation transcripts
- raw `.scratch/` drafts
- advisory Codex synthesis that is still exploratory rather than canonical
- blocker or non-blocker residue (`reports/deferred/` owns that)
- wave evidence/provenance artifacts (`reports/l4_wave_indicators/` owns that)

Relationship to other lanes:

- `reports/codex/` remains the advisory/working Codex design lane
- `.scratch/` remains disposable local drafting space
- promote only the small subset of packets that `TASKS.md` or other canonical
  trackers must point at directly

Current tracked packets:

- `meta_bridge_rollout_2026-03-20.md`
- `post_merge_supervisor_plan_2026-03-21.md`
- `post_redteam_structural_queue_2026-03-20.md`
