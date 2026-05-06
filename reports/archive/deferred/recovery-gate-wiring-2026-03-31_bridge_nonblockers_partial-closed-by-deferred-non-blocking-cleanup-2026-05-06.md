# Archived Closed Sections: recovery-gate-wiring-2026-03-31

Date archived: 2026-05-06
Source packet: `reports/deferred/non_blocking/recovery-gate-wiring-2026-03-31_bridge_nonblockers.md`
Reason: deferred non-blocking cleanup moved sections already marked resolved
out of the active advisory lane.

## Closed Sections

- ~~Missing wave_name makes stale-state recovery delete checkpoint~~ (fixed:
  empty wave_id now returns noop)
- ~~Report packet claims no new files~~ (fixed: updated packet text)

## Evidence

- Source packet before cleanup marked the sections under `Resolved in this wave`.
- Current active packet retains only the persisting surface-mode timeout finding.
