# RCX-π Core v1

This directory (`WorkingRCX/`) is a **minimal RCX-π core**:

- A single structural type: `Motif` (built with `μ(...)`)
- Peano arithmetic as pure structure (`VOID` = 0, successors, add, mult)
- Structural “programs” via **projection / closure / activation** motifs
- A tiny meta layer that classifies motifs as value / program / mixed / struct
- A single runner `run_all.py` that exercises the whole core

If `run_all.py` is green, RCX-π Core v1 is intact.

---

## How to run everything

From `WorkingRCX/`:

```bash
python3 run_all.py