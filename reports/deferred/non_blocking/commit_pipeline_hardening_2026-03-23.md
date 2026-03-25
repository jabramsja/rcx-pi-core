# Commit Pipeline Hardening (Non-Blocking)

Date: 2026-03-23
Status: OPEN
Source: Bridge R1 findings #1-11 from commit-pipeline-impl-r1
Wave: commit-pipeline-automation (BOOTSTRAP_PHASE_B_EXCEPTION)

## Context

Claude implementer (via phase_b_executor mechanical path) implemented the locked 15-step commit pipeline state machine. Bridge R1 found 12 findings. #12 (test schema mismatch) was fixed by the implementer. #1-11 are non-blocking hardening items deferred for a follow-on wave.

## OPEN Items

1. Phase B accepts invalid routing tokens and unlocked plans (validate_inputs non-fatal) — phase_b_executor.py:380
2. Closeout attestation authorizes GO with no behavioral validation proof — check_closeout_attestation.py:174
3. Gate 10 never supplies validation results to attestation generator — meta_bridge_supervisor.py:783
4. Phase B sweeps unrelated dirty-worktree files into handoff — phase_b_executor.py:199
5. Commit executor reports success when post-merge tree is dirty — commit_executor.py:784
6. Streaming adapter timeouts still orphan child processes — bridge_adapters.py:255
7. INV-2 control-surface checker spoofable by dummy if-branches — check_control_surface_invariants.py:150
8. executor_config.json not in control-surface detection set — check_control_surface_invariants.py:34
9. Phase B staging helper omits '--' separator — phase_b_executor.py:221
10. force_add_files denylist is case-sensitive on macOS — commit_executor.py:147
11. Missing indicator collector treated as success — commit_executor.py:373
