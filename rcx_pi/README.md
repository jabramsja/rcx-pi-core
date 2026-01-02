## RCX Spec Architecture

- Base specs (`core`, `paradox_1over0`, `godel_liar`) describe *native worlds*
- Composite specs (`rcx_triad`, `rcx_triad_plus`) describe *selection lenses*
- `rcx_triad_router` must satisfy **100% coverage** of composite specs
- New Mu seeds:
  - go into base worlds *only if native*
  - otherwise go into `triad_plus_routes.py`

Never embed new semantics directly into base worlds.