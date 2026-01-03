# RCX-π Core — Minimal Structural Runtime v1

This is the **minimal working implementation of RCX-π**, built entirely from a
single recursive motif structure `μ(...)`.  
Everything—numbers, pairs, triples, programs, projections, activation closures—
is represented as pure nested structure instead of syntax or bytecode.

RCX-π = *Computation without instructions.*  
Only shape. Only structure. The program **is** the data.

---

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