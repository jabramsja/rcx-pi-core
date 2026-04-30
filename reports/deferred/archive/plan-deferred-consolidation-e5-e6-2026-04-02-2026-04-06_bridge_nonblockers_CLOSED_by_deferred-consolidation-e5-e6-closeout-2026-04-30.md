# Deferred Non-Blocking Findings: plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06

Wave: plan-deferred-consolidation-e5-e6-2026-04-02-2026-04-06
Closed by: deferred-consolidation-e5-e6-closeout-2026-04-30
Class: L4_ENABLER
Target Gate: G8
Status: CLOSED

## 1. Pane comment sanitizer leaves C1 control characters in displayed bot text

- **Class:** DEFECT
- **Severity:** low
- **File:** `mu/tools/observability/_pane_prci.sh`
- **Disposition:** closed
- **Original evidence:** `PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY' ... _run_pane_once(..., 'safe \u009b31mred\u009b0m tail') ... print(repr(stdout)); print('contains_u009b=', '\u009b' in stdout)`
- **Closeout evidence:** `sanitize_pane_text()` now strips C1 controls (`U+0080..U+009F`) in addition to ESC/C0/DEL controls, and `mu/tests/tools/test_pane_prci_observability.py::test_displayed_bot_comment_text_strips_c1_controls` proves displayed bot text no longer contains `U+009B`.
- **Validation:** `PYTHONHASHSEED=0 python3 -m pytest -q mu/tests/tools/test_pane_prci_observability.py` -> `9 passed`.
