# Deferred Non-Blocking Findings: commit-pipeline-automation-plan-2026-03-25

**Source:** bridge rounds plus manual corrective cleanup on 2026-03-25
**Status:** No active unresolved items remain in this packet after the manual corrective patch. It is retained as provenance until the next live rerun regenerates it mechanically.

## Resolved 2026-03-25

### 1. executor_dispatch dead local `ROUTING_RECORD_PATH` constant

- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** `mu/tools/executors/executor_dispatch.py`
- **Disposition:** non_blocking
- **Resolution:** Removed. Dispatcher now uses only the shared routing-record loader path logic.

### 2. phase_b_implementer unused executor-config import

- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** `mu/tools/executors/phase_b_implementer.py`
- **Disposition:** non_blocking
- **Resolution:** Removed the unused `load_executor_config` import binding.

### 3. supervision_poll review-artifact drift

- **Class:** DEFECT
- **Severity:** medium
- **File:** `mu/tools/executors/supervision_poll.py`
- **Disposition:** non_blocking
- **Resolution:** The poller now supports explicit status/stdout/stderr artifact binding and repo-safe state-file fallback instead of always choosing the newest global `.scratch` review artifacts by mtime.

### 4. Mar 25 control-plane packet scope undercount

- **Class:** DOC_ACCURACY
- **Severity:** low
- **File:** `reports/control_plane/commit_pipeline_automation_plan_2026-03-25.md`
- **Disposition:** non_blocking
- **Resolution:** The packet now reflects the 41-file staged scope and includes `mu/tools/checks/check_closeout_attestation.py`.
