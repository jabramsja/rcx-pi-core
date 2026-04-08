# Deferred Non-Blocking Findings: recovery-tier3-wiring-2026-04-01

Rebuilt 2026-04-06 after 9-round adversarial bridge review. 2 verified residuals.

## 1. TASKS.md orphan tracker sync note schema
- **Class:** POLICY_BOUND
- **Severity:** low
- **File:** TASKS.md
- **Disposition:** non_blocking
- **Detail:** Line ~458 starts with `**fix:` instead of `- Tracker sync note (...)` form. Cosmetic schema inconsistency.

## 2. Doubled FOUNDER_OVERRIDE prefixes in TASKS.md
- **Class:** POLICY_BOUND
- **Severity:** low
- **File:** TASKS.md
- **Disposition:** non_blocking
- **Detail:** 9 tracker notes carry `FOUNDER_OVERRIDE:FOUNDER_OVERRIDE:` doubled prefix at lines 112, 408-415, 433. Cosmetic, does not affect contract enforcement.

## Resolved (previously reported, now fixed)

All denylist bypass findings from bridge rounds 1-9 resolved by 8-layer hardening:
- Shell wrapper evasion, interpreter code exec, package manager bypass, quote-insertion bypass, argument-position false positives.
- Verification: 328 tests pass (75 targeted denylist tests).
