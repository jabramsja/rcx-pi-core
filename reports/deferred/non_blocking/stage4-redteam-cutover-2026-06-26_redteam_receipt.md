# Stage 4 Red-Team Cutover Receipt - 2026-06-26

Task: [NEXT-CODEX-POST-REDTEAM]
Wave ID: stage4-redteam-cutover-2026-06-26
Status: NON_BLOCKING - no same-scope DEFECT reproduced

## Finding Classes

- DEFECT: none reproduced.
- POLICY_BOUND: none reproduced; no host numeric fallback, float tolerance, side channel, or codec shim was added.
- DOC_ACCURACY: none blocking. The remaining proof limits below are explicit.

## Direct Evidence

Current-dev grounding was read from `TASKS.md`, `STATUS.md`, `mu/docs/core/StructuralNumbers.v0.md`, `mu/docs/core/NorthStarSemantics.v0.md`, `reports/control_plane/stage4-loop-struct-2026-06-22_2026-06-22.md`, and `reports/control_plane/queue-truth-after-stage4-cutover-2026-06-26_2026-06-26.md`.

Focused Python matcher probe:

```bash
PYTHONPATH=mu/host/python python3 - <<'PY'
from rcx_pi.selfhost.eval_seed import _stage0_match, NO_MATCH
# Probed: var/literal/nested host int and float -> NO_MATCH;
# var/nested/structural pattern StructuralNumbers one -> binding success.
PY
```

Result: host int and float leaves returned `NO_MATCH`; `{"_num": {"xH": None}}` matched and bound structurally.

Focused JavaScript matcher probe:

```bash
node - <<'JS'
const { stage0Match, NO_MATCH } = require('./mu/host/js/core/bootstrap_core');
// Probed the same vectors as Python against stage0Match.
JS
```

Result: host number leaves returned `NO_MATCH`; `{"_num": {"xH": null}}` matched and bound structurally with the same terminal shape as Python.

Source trace:

- Python `_stage0_match` rejects non-bool `int`/`float` pattern or input leaves before variable binding and scans variable-bound candidate structure for nested numeric leaves.
- JavaScript `stage0Match` rejects `typeof ... === "number"` pattern or input leaves before variable binding and scans variable-bound candidate structure for nested numeric leaves.
- Engine-loop `max_steps` remains an execution watchdog at the public boundary, but the matcher-visible `_run_engine.max_steps` state is built through the StructuralNumbers ADD projection table in both Python and JavaScript.
- `run_trace` explicit `max_steps` input accepts only StructuralNumbers numerals and rejects malformed, cyclic, dirty, or over-cap numerals before structural reduction.

## Proof Limits

- This receipt proves current live Python/JS matcher-domain behavior for the probed vectors and relies on the required wave gates for broader corpus coverage.
- The workload parity helper still contains a generic int/float normalizer for cross-substrate terminal metadata; it is not the proof basis for the matcher-domain host-numeric rejection claim.
- Bool and string leaves intentionally remain on the non-numeric content-hash path per `StructuralNumbers.v0.md` section 9.7; this red-team did not advance bool/string structuralization.

## Queue Result

No same-scope runtime repair was required. The active queue may advance to pipeline hardening, including the #1139/#1140 conflict-refresh packets, while later mathematical structure items remain ordered after that hardening lane.
