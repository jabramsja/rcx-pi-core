# W4C: JS Trampoline _run_engine Negative Control Gap

## Status: NON-BLOCKING

## Finding

The W4C gate test `test_js_trampoline_run_engine_negative_control` proves the trampoline path works (happy-path with `boot1LoopMode:false`), but does not inject a malformed `_run_engine` payload to prove typed fail-closed validation.

## Why non-blocking

1. The source-lock test (`test_trampoline_validates_run_engine`) proves `validateReentryPayload(payload, 'trampoline _run_engine')` exists in the code.
2. Existing `test_boot1_shadow_parity.py::TestReentryPayloadValidation` tests prove `validateReentryPayload` rejects malformed payloads with typed `input.shape_mismatch`.
3. Bridge manual repro confirmed: malformed `_run_engine` through JS trampoline returns `input.shape_mismatch :: trampoline _run_engine: re-entry payload must be dict, got string`.
4. The `_run_engine` reserved-field validation at the API boundary blocks malformed payloads before they reach the engine, making it difficult to test from Python.

## Fix path

Add a JS inline test that directly calls `runEnginePipeline` with a stubbed `step` function returning malformed `_run_engine`, bypassing API-level validation.

## Discovered by

Bridge Phase B R2 review (2026-03-18, W4C implementation review).
