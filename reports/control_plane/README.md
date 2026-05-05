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

Canonical packet references:

- `reports/control_plane/archive/meta_bridge_rollout_2026-03-20.md`
- `reports/archive/control_plane/post_merge_supervisor_plan_2026-03-21.md`
- `reports/archive/control_plane/executor_surfaces_plan_2026-03-22.md`
- `reports/control_plane/post_redteam_structural_queue_2026-03-20.md`
- `reports/control_plane/deferred_findings_fix_sweep_2026-05-04.md`
- `reports/control_plane/mu_preproduction_redteam_2026-05-04.md`

Index truth note (2026-05-04):

- This README is a lane-placement guide, not an exhaustive active-work tracker.
- Current open/closed task truth comes from `TASKS.md`.
- Historical packets in this folder may retain pre-implementation scope,
  acceptance, or commit-ready evidence, but those packets do not reopen work that
  `TASKS.md` marks closed or relist landed work as unresolved.
- The active pre-production sequence is governed by the deferred findings sweep
  packet first, then the `/mu` preproduction red-team packet.
