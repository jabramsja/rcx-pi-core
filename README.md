# RCX-π Minimal Core

This directory holds a *pure structural* RCX-π nucleus:

- `rcx_pi/core/motif.py` — Motif + μ, VOID, UNIT, Peano arithmetic (no strings, no ints in the structure).
- `rcx_pi/utils/compression.py` — depth-based structural markers for meta tags.
- `rcx_pi/reduction/pattern_matching.py` — PROJECTION, CLOSURE, ACTIVATION, VAR + PatternMatcher.
- `rcx_pi/reduction/rules_pure.py` — arithmetic + closure/activation rules, purely structural.
- `rcx_pi/engine/evaluator_pure.py` — small reducer (step/reduce).
- `rcx_pi/programs.py` — structural programs (swap, dup, rotate, etc.).
- `rcx_pi/meta.py` — structural tagging + external classifier (“value/program/mixed/struct”).

Test files:
- `test_numbers.py` — Peano + RCX-π arithmetic sanity.
- `test_combinators.py` — I, K, etc.
- `test_projection.py` — swap / projection demo.
- `test_programs.py` — higher-level structural programs.
- `test_meta.py` — meta classification checks.