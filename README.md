# RCX-π Core — Minimal Structural Runtime v1

This is the **minimal working implementation of RCX-π**, built entirely from a
single recursive motif structure `μ(...)`.  
Everything—numbers, pairs, triples, programs, projections, activation closures—
is represented as pure nested structure instead of syntax or bytecode.

RCX-π = *Computation without instructions.*  
Only shape. Only structure. The program **is** the data.

---

## World tracing (stable entrypoint)

Use the stable wrapper script (no PYTHONPATH required):

  ./scripts/world_trace.sh --help
  ./scripts/world_trace.sh --max-steps 50 --json --pretty < world.json

This delegates to: python3 -m rcx_pi.worlds.world_trace_cli


## 🌱 Core Components

| Module | Purpose |
|-------|---------|
| `core/motif.py` | Defines the `Motif` object and constructor `μ(...)` |
| `rules_pure.py` | Pure rewrite rules (no semantics baked in) |
| `engine/evaluator_pure.py` | Structural evaluator + reduction engine |
| `programs.py` | Reusable structural closures (swap, dup, rotate, etc.) |
| `utils.py` | Peano helpers: `num(n)`, `motif_to_int`, decode to tuples |
| `run_all.py` | Runs **all demos + tests** in one command |

If `run_all.py` finishes without red errors — **RCX-π Core is healthy.**

---

## 🔒 Green Gate (Canonical Health Check)

The **only supported correctness gate** for this repository is:

```bash
scripts/green_gate.sh

If scripts/green_gate.sh finishes without red errors — RCX-π Core is healthy.

## JSON diff / inspection

Use `scripts/json_diff.sh` to compare JSON outputs semantically (object key order ignored; arrays remain order-sensitive).

Examples:
- Compare full docs (ignoring optional schema metadata):
  - `scripts/json_diff.sh a.json b.json --ignore kind,schema_version`
- Compare only the frozen minimum field:
  - `scripts/json_diff.sh a.json b.json --only result`

## Rule precedence visualization

Use `scripts/rule_precedence.sh` to inspect a `.mu` world file and list rule-like lines in **textual order** (earlier lines first).
This is a tooling inspector only; it does not change runtime semantics.

Examples:
- Show the first 25 rules detected:
  - `scripts/rule_precedence.sh rcx_pi_rust/mu_programs/rcx_core.mu --top 25`
- Emit a stable JSON summary:
  - `scripts/rule_precedence.sh rcx_pi_rust/mu_programs/rcx_core.mu --json`

## CLI Quickstart
See `docs/cli_quickstart.md` for the umbrella `rcx` command and the JSON-emitting tools.

<!-- protection smoke: 2026-01-13T23:02:14Z -->


# smoke: 2026-01-13T23:26:27Z
