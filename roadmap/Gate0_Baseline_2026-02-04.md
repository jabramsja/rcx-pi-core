# Gate 0 Baseline Freeze (2026-02-04)

> **Current State**: See [`STATUS.md`](../STATUS.md)
> **Authorization**: See [`TASKS.md`](../TASKS.md)
> **Scope**: This document records the BASELINE SNAPSHOT only. It is a point-in-time record, not current state.

## Purpose
Lock current behavior before Gate 2 normalization refactor begins.

## Baseline Test Results

| Test File | Tests | Result |
|-----------|-------|--------|
| `tests/test_recurrence_parity.py` | 28 | PASS |
| `tests/test_exhaustion_parity.py` | 17 | PASS |
| `tests/test_meta_circular_gate6.py` | 19 | PASS |
| `tests/test_execution_path_verification.py` | 15 | PASS |
| `tests/test_js_parity_automated.py` | 19 | PASS |
| **Total** | **98** | **ALL PASS** |

## Seed Checksums (Frozen)

From `rcx_pi/selfhost/seed_integrity.py`:

| Seed | Checksum (SHA256) |
|------|-------------------|
| match.v1.json | `9614ec7e802005dc3322dc7af474abf4f137a506efc57f52781157210e76e190` |
| subst.v1.json | `d8626f8ffddda711124205a761dd64d6781ebec53567e74a11f2ce8cf0ce75df` |
| classify.v1.json | `2008556c09105d0dc46f19e38382870a60ced7d88549dbd989f5d613d5db1968` |
| kernel.v1.json | `813cae10f2a7f19bd494e56e5c8cf2feaf92f32ae6988d626bca21ee01811daa` |
| match.v2.json | `55a6b58a6c8fe31d4c3a8c704603d453fc04c1a757a45fcf7f6570afa1fe27b1` |
| subst.v2.json | `e64695b966c497b22d710779ad7c1c9a2a5158734392714c10dffb77f6c39621` |
| recurrence.v1.json | `3d4b07523eac31c9495c6601b5e4c11eabbd35235619173aabc0f28d33ce34a6` |
| exhaustion.v1.json | `44dc13783f1b0481a1e8961ab7e0717d511dcc09ade5af4078e5750f83d5d749` |
| rcx_engine.v1.json | `dfc3c8fcd4545687b614b9ee8d80d687a29d72e36c69f148615061d0341b0456` |
| bootstrap_structural.v1.json | `edb9908eeaee4518b49f72bb17274aa490388555cebe9e363f5785d7e44014db` |

## Exit Criteria

| Criterion | Status |
|-----------|--------|
| All baseline tests pass on current main | ✓ |
| Checksums match current seeds | ✓ |

## Commit Reference
Baseline frozen at commit: `df07625` (Gate 1 completion)

## Next Gate
Gate 2: Normalization Adapters
- Add adapter functions for raw → normalized conversion
- Add round-trip tests
