# Deferred Consolidation Phase B Fail-Closed Hardening 2026-04-02

Date: 2026-04-02
Lane: control-surface
Parent task: `[DEFERRED-CONSOLIDATION]`
Status: implemented locally; replay proof still pending

## Why This Wave Exists

A live replay of the deferred E5/E6 pipeline reached Phase B bridge review and surfaced two real fail-closed defects in `mu/tools/executors/phase_b_executor.py` that the E5/E6 observability wave could not honestly fix:

1. High/critical `POLICY_BOUND` or `DOC_ACCURACY` findings on governance/doc paths were downgraded to non-blocking before the severity floor ran.
2. `_stage_files()` retried with `git add -f`, which could force-stage ignored files.

Both defects sit on the control surface, not in the wave-owned observability file.

## Scope

Files in scope:

- `mu/tools/executors/phase_b_executor.py`
- `mu/tests/tools/test_phase_b_executor.py`

Files explicitly out of scope:

- `mu/tools/observability/_pane_prci.sh`
- `reports/control_plane/deferred_consolidation_e5_e6_2026_04_02_2026-04-02.md`
- dispatcher, recovery, commit, or bridge supervisor code outside the two scoped files

## Defects And Fixes

### 1. Severity floor bypass on governance/doc paths

Reproduced with:

```bash
python3 - <<'PY'
from mu.tools.executors.phase_b_executor import _classify_findings
findings = [{
    "title": "critical governance downgrade",
    "class": "POLICY_BOUND",
    "severity": "critical",
    "file": "reports/control_plane/example.md",
    "status": "new",
}]
print(_classify_findings(findings))
PY
```

Before this wave, the finding above was classified as non-blocking because the governance/doc-path downgrade ran before the critical/high severity floor.

Fix:

- move the critical/high severity floor ahead of governance downgrades and ahead of generic disposition handling
- keep governance/doc-path downgrades only for findings below the severity floor

### 2. Ignored-file staging bypass through `git add -f`

Reproduced with:

```bash
python3 - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
from mu.tools.executors.phase_b_executor import _stage_files
with TemporaryDirectory() as td:
    repo = Path(td)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    (repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (repo / "ignored.txt").write_text("x", encoding="utf-8")
    print(_stage_files(repo, ["ignored.txt"]))
    print(subprocess.run(["git", "status", "--short"], cwd=repo, text=True, capture_output=True, check=True).stdout)
PY
```

Before this wave, `_stage_files()` returned success and staged the ignored file through the `git add -f` fallback.

Fix:

- remove the `git add -f` retry
- fail closed when normal staging fails

## Test Coverage Added

- governance/doc-path downgrades remain non-blocking only below the severity floor
- high/critical governance/doc findings stay blocking
- `_stage_files()` stages normal files
- `_stage_files()` rejects ignored files instead of force-adding them
- stale rendered bridge output still falls back to job-scoped raw reviewer envelopes

## Validation

- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_phase_b_executor.py -q --tb=short -k 'GovernanceDowngrade or TestStageFiles or stale_render_still_uses_job_raw_reviewer_findings'`
- `PYTHONHASHSEED=0 python3 -m pytest mu/tests/tools/test_phase_b_executor.py -q --tb=short`

## Invariant Tuple

- debt before/after: unchanged
- host semantics before/after: unchanged
- runtime/substrate delta: none; executor/control-surface only

## Next Step

Replay the deferred E5/E6 wave from a fresh clean worktree on top of this hardening slice and confirm:

1. Phase A still converges through stub -> same-file rewrite -> SDK review
2. Phase B bridge review consumes real reviewer findings
3. the E5/E6 wave reaches commit or the next honest blocker without these Phase B fail-closed gaps
