rcx_core world
==============

Purpose
-------
Core routing for RCX-π null / inf / paradox / shadow / omega tags.

Buckets
-------
[null,_]    -> ra       # null-projected items go to r_a (stable)
[inf,_]     -> lobe     # inf-tagged items go to lobes (potential)
[paradox,_] -> sink     # paradox-tagged items preserved in sink
[ra,_]      -> ra
[lobe,_]    -> lobe
[sink,_]    -> sink
[shadow,_]  -> sink     # shadow flows to sink for now
[omega,_]   -> lobe     # omega-folds treated as potential lobes

Notes
-----
- This is the canonical "Mandelbrot-bridge" world:
  null = stable, inf/omega = exploratory, paradox/shadow = tension storage.
- Behavior is deterministic and good as a baseline for other worlds.