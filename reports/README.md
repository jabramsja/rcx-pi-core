# Reports Tree

Active top-level lanes:

- `reports/archive/`: canonical archive for completed, stale, or superseded report artifacts
- `reports/codex/`: active Codex design packets, synthesis work, and audit support material
- `reports/control_plane/`: tracked founder-facing control-plane packets referenced by TASKS.md
- `reports/deferred/`: active founder-facing blocker and advisory lanes, split into `blocking/` and `non_blocking/`
- `reports/l4_wave_indicators/`: canonical wave evidence/provenance artifacts

Root cleanup status:

- the root `reports/` folder now contains only real active directories
- historical frontage paths were removed once their remaining references were
  repointed to canonical deferred or archive locations

Deferred lane rules:

- active founder-facing blocker audits live in `reports/deferred/blocking/`
- active founder-facing advisory/non-blocking audits live in `reports/deferred/non_blocking/`
- do not add compatibility symlinks under `reports/deferred/`; repoint tracker
  references to the canonical file paths instead
- once a deferred source packet is routed into a bounded control-plane packet,
  archive the source snapshot under `reports/archive/deferred/` and track the
  active work from the routed packet and `TASKS.md`

Codex lane rules:

- active blocker/non-blocker residue was migrated out of `reports/codex/` and into
  `reports/deferred/`
- `reports/codex/blockers/` and `reports/codex/non_blockers/` are now redirect
  lanes with README guidance only
- archived Codex blocker/non-blocker snapshots live under
  `reports/codex/Archive/blockers/` and `reports/codex/Archive/non_blockers/`
