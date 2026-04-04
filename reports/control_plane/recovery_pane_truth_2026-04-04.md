# Recovery Pane Truth

Date: 2026-04-04
Status: Local proof complete; routed closeout pending
Task: [PIPELINE-RECOVERY/recovery-pane-truth-2026-04-04]
Wave ID: recovery-pane-truth-2026-04-04

## Scope

Fix the stale recovery-pane behavior exposed during live routed commit work:

1. when recovery fires, fails, and a later retry eventually succeeds, stop
   presenting the old exhausted recovery record as the current truth
2. stop treating junk one-character recovery reasons like `R` as meaningful
   operator text
3. phrase inactive recovery state in plain English so the founder can tell at a
   glance whether recovery is still running or is only historical
4. keep the web recovery snapshot aligned with the same plain-English fallback

No runtime/substrate semantics change. This is control-surface recovery
observability only.

## Changed surfaces

- `mu/tools/executors/recovery_gate.py`
- `mu/tools/executors/executor_dispatch.py`
- `mu/tools/observability/pipeline_dashboard.py`
- `mu/tools/observability/pipeline_dashboard_web.py`
- `mu/tests/tools/test_recovery_gate.py`
- `mu/tests/tools/test_executor_dispatch.py`

## Proof points

1. `recovery_gate.py` now exposes
   `clear_stale_recovery_status_on_success()`, which marks an inactive matching
   recovery record as `resolved_by_later_success` when the later retry actually
   works.
2. `executor_dispatch.py` now calls that helper whenever a routed wave ends in
   `success` or `held`, so recovery status does not stay frozen on an older
   exhausted tuple after the pipeline has already recovered.
3. `pipeline_dashboard.py` now treats one- and two-character recovery reasons
   as noise, so garbage like `R` falls through to the actual human-readable
   detail.
4. `pipeline_dashboard.py` now renders inactive recovery in past-tense plain
   English:
   - `No recovery is running now.`
   - `Recovery sent work back to: Commit`
   - `Outcome: a later success cleared the earlier issue`
5. `pipeline_dashboard_web.py` uses the same junk-reason suppression, so web
   snapshot consumers see the same plain-English note instead of the raw junk
   token.
6. Live proof on the worktree:
   - the merged recovery wave’s stale Tier 3 record was rewritten in place via
     `clear_stale_recovery_status_on_success(...)`
   - one-shot `pipeline_status.sh` then rendered the record as historical only
   - after restarting the tmux monitor, pane `%3` showed the same
     plain-English cleared state instead of the old exhausted wording

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_recovery_gate.py mu/tests/tools/test_executor_dispatch.py -q --tb=short`
- `bash mu/tools/observability/pipeline_status.sh`
- tmux live check:
  `tmux capture-pane -p -S -40 -t %3 | tail -n 25`

## Invariant tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; control-surface observability only
