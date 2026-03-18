# JS Trampoline _run_engine Validation Gap

## Status: NON-BLOCKING (out of W4A scope — JS changes deferred)

## Finding

Python trampoline now validates `_run_engine` reentry payloads via `_validate_reentry_payload(payload, "trampoline _run_engine")`. The JS trampoline (`pipeline.js`) lacks equivalent validation for `_run_engine` in the trampoline path. Malformed `_run_engine` output from engine projections would run until `engine.exhausted` instead of failing with a typed shape error.

## Why deferred

W4A scope is explicitly "No JS pipeline changes (audit only)." The Python validation was added because W4A's extraction created a new `reentry` branch in the trampoline that needed validation. The JS code was not refactored — its trampoline never had `_run_engine` detection.

## Fix path

Mirror the Python pattern: add `validateReentryPayload(payload, 'trampoline _run_engine')` in the JS trampoline's re-entry handling. Update hardening gate to require 4 JS calls.

## Discovered by

Bridge R3 review (2026-03-18, W4A implementation review).
