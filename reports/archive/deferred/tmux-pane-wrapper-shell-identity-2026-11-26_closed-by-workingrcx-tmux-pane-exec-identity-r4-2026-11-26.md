<!-- DOC_STATUS: REFERENCE -->
# tmux pane wrapper-shell identity breaks reader adoption under bash 3.2 — 2026-11-26

Class: DEFECT · Severity: high · Disposition: **RESOLVED LOCALLY BY R4; NATIVE DELIVERY PENDING** ·
Owner: 40 `[FLEET-NATIVE-LIFECYCLE-PREVENTION]` (existing tmux/monitor follow-ups).

Resolution wave: `workingrcx-tmux-pane-exec-identity-r4-2026-11-26`. The monitor
and autofollow test files are byte-identical to reviewed R3 commit
`ff12f6544f0b2e3bdb2820f763c2e73e6667d79b`; the lifecycle implementation and its
tests remain byte-identical to comparison commit
`fbe43a5e71fd59de07f9454b8cb9189dab346d7c`. Exact reader/pane identity and adoption
authority are unchanged.

R4 resolution evidence (2026-11-26, macOS): the full two-module pytest commands
preserved below were rerun with `PYTHONHASHSEED=0` and
`PYTHONDONTWRITEBYTECODE=1`. Under `SHELL=/bin/bash`, pytest exited 0 with
**207 passed in 439.80 seconds**; under `SHELL=/bin/zsh`, it exited 0 with
**207 passed in 437.01 seconds**. Each run covers 146 lifecycle tests and
61 monitor tests, including both non-exec-optimizing Bash regression cases.

The declared R4 chained evidence command exited 1 after pytest passed:
`python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r4-2026-11-26 --wave-class L4_ENABLER`
reported no tracked files in the empty staged change set. Native candidate
staging, indicator collection, the staged L4 rerun, independent review, pre-push,
CI and publication remain outer-executor work and are not claimed complete.

This closed source packet lives under `reports/archive/deferred/` and is indexed
under historical closures in `reports/deferred/blocking/README.md`; that blocking
directory contains only its README. The observations, impact, interim workaround
and R3 before/after evidence below are preserved unchanged as historical records.

## Observed

- Wave `workingrcx-role-model-selection-r3-2026-11-26` reached supervisor COMMIT_GO
  (local commit `212d1172`) and then failed `run_pre_push_script`: **19 failed, 13721
  passed**; native tier-3 recovery exhausted.
- The same failures reproduce on untouched dev `fbe43a5e`, so they are independent of
  that wave's content.
- Failing assertions: `test_worktree_lifecycle.py` `assert observations >= 2`
  (`0 >= 2`) and `assert 'ESCALATED' == 'COMPLETE'`, with the result reason
  "Old raw log reader lacks an exact owned pane; no new retirement claim".

## Root cause (A/B proven)

| `SHELL` for the tmux server | `mu/tests/tools/test_worktree_lifecycle.py` |
| --- | --- |
| `/bin/bash` (macOS bash 3.2.57, the founder login shell) | 13 failed, 133 passed |
| `/bin/zsh` | 146 passed |

1. tmux runs each pane command as `$SHELL -c "<cmd>"`.
2. The pane command is a compound list ending in an un-`exec`'d `bash <watcher>`.
   - Production: `pipeline_monitor.sh` `pane1_cmd`, a `cd … && unset … && VAR=… bash …`
     list started by `tmux new-session … "$pane1_cmd"`.
   - The `stale_live_watcher` fixture in `test_pipeline_monitor_autofollow.py`
     mirrors it.
3. bash 3.2 does not exec the last command of an `&&` list. A `bash -c` wrapper
   therefore remains as `pane_pid`, and the watcher runs as its child. Runtime
   evidence: pane `%0` pid 10222 is `bash -c cd … && … bash rcx_log_watcher.sh`; the
   reader is pid 10224, whose parent is 10222.
4. `worktree_lifecycle.py` `_adopt_terminal_log_readers` requires exactly one pane
   whose `pane_pid == reader pid`, and raises the Hold otherwise.
5. zsh and modern bash exec the last command, so environments that run under zsh
   (the earlier codex-orchestrated waves) passed.

## Impact

- Local pre-push fails for every Claude-orchestrated wave on this machine.
- In production, real lane completions can ESCALATE whenever the `rcx-pipeline` tmux
  server was started under bash 3.2.
- The failure context given to tier-3 recovery is the trailing
  "git push --no-verify" hint line (known extractor defect). The delegate then edited
  out-of-scope fixtures on an unrelated zombie-state hypothesis. Those edits are
  preserved, not landed, under
  `reviews/autonomous-landing-20261011/role-model-selection-r3-recovery-delegate-edits-20261126/`
  on the WD.

## Required fix (structural; no broadened adoption authority)

- `exec` the final command of every monitor pane command, in production
  (`pipeline_monitor.sh` pane commands) and in the mirroring fixture. The pane process
  then **is** the watcher under any shell, and the exact `pane_pid == reader pid`
  identity check stays as strict as today.
- Add a regression that pins the tmux server's `default-shell` to a non-exec-optimizing
  bash, so the property is exercised on every platform.
- Do not relax `_adopt_terminal_log_readers` to accept ancestor matches.

## Interim unblock (manual, once, documented)

Launch the stranded wave's native same-config continuation with `SHELL=/bin/zsh`. The
full gate still runs unchanged; only the shell that tmux uses differs. This is an
environment setting, not a gate bypass, and it ends when the fix above lands.

## R3 implementation evidence (2026-11-26)

Wave: `workingrcx-tmux-pane-exec-identity-r3-2026-11-26`.
comparison_commit: `fbe43a5e71fd59de07f9454b8cb9189dab346d7c`.
Both HEAD and origin/dev matched that commit before implementation.

Before any code edits, the exact two-module bash reproduction exited 1 with
**17 failed, 188 passed in 422.99 seconds**: `test_worktree_lifecycle.py` had
13 failures and 133 passes; `test_pipeline_monitor_autofollow.py` had 4 failures
and 55 passes.

```bash
SHELL=/bin/bash PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short
```

The new regression pins a private tmux server's default-shell to Bash and
installs an EXIT trap through BASH_ENV, preventing last-command exec optimization
even on newer Bash versions. An un-exec'd control proves the wrapper remains.
Each real production pane command then runs a small script that independently
records its own PID; that PID must equal pane_pid and the observed process must
be Bash executing the script directly. Both default and pinned monitor modes
cover all four command constructions.

```bash
SHELL=/bin/zsh PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_pipeline_monitor_autofollow.py -k test_monitor_pane_pids_are_scripts_under_non_exec_bash --tb=short
```

Against the original command form, this regression exited 1 with **2 failed,
59 deselected in 1.68 seconds**. Both failures showed a `bash -c` pane process
whose PID differed from the reader script's PID. After the fix, the identical
command exited 0 with **2 passed, 59 deselected in 2.30 seconds**.

The implementation adds only `exec env` to the four production pane command
constructions and to the mirroring stale_live_watcher launch. All existing
variables, quoting, directory changes and unsets are preserved.
`worktree_lifecycle.py` and `test_worktree_lifecycle.py` remain byte-identical to
the comparison commit; exact reader/pane identity and adoption authority are
unchanged.

The full post-fix bash run passed **207 tests in 435.22 seconds** (pytest exit 0):
146 lifecycle tests and 61 monitor tests, including the two new regression cases.
The declared chained evidence command then exited 1 at the staged L4 check:

```bash
python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id workingrcx-tmux-pane-exec-identity-r3-2026-11-26 --wave-class L4_ENABLER
```

```text
ERROR: --wave-id 'workingrcx-tmux-pane-exec-identity-r3-2026-11-26' provided but no tracked files found (--staged). Cannot verify wave against empty change set.
```

The full post-fix zsh run exited 0 with **207 passed in 433.70 seconds**:

```bash
SHELL=/bin/zsh PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider mu/tests/tools/test_worktree_lifecycle.py mu/tests/tools/test_pipeline_monitor_autofollow.py --tb=short
```

| Snapshot | Lifecycle module | Monitor module | Combined |
| --- | --- | --- | --- |
| Before fix, bash | 13 failed, 133 passed | 4 failed, 55 passed | 17 failed, 188 passed |
| After fix, bash | 146 passed | 61 passed | 207 passed |
| After fix, zsh | 146 passed | 61 passed | 207 passed |

Final staging, indicator generation, independent review, pre-push without a SHELL
override, CI and publication belong to the outer executor
and are not claimed complete by this Phase B implementation. The staged L4
check must be rerun after that executor materializes the candidate and indicator;
the empty-index failure is retained rather than bypassed or reported as a pass.
