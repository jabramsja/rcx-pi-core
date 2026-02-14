# mu/mu_programs/

Active `.mu` world fixtures used by tools, tests, and the program descriptor CLI.

These files are the **canonical source** for `.mu` programs referenced by active
code paths. They were seeded from `rcx_pi_rust/mu_programs/` during Round 21C
decoupling (2026-02-14).

## Files

| File | Description |
|------|-------------|
| `rcx_core.mu` | Core RCX world (12 routing rules) |
| `pingpong.mu` | Pure rewrite cycle (ping/pong) |
| `paradox_1over0.mu` | Paradox routing world |
| `vars_demo.mu` | Variable binding demo with pattern precedence |

## Governance

- `rcx_pi_rust/mu_programs/` is ARCHIVE-bound (LegacySurfaceDecisionRecord.v0.md)
- Active code should reference `mu/mu_programs/` (this directory), not `rcx_pi_rust/mu_programs/`
- New `.mu` fixtures should be added here, not to `rcx_pi_rust/mu_programs/`
- `mu/programs/` (sibling) contains JSON seed programs — distinct from `.mu` world files
