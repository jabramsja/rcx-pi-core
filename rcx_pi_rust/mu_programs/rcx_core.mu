# rcx_core.mu
# A tiny RCX-flavored routing skin:
#   - [null,x]      → r_a
#   - [inf,x]       → lobes
#   - [paradox,x]   → sink
#   - [ra,x]        → r_a       (explicit Ra bucket tag)
#   - [lobe,x]      → lobes     (explicit lobe tag)
#   - [sink,x]      → sink      (explicit sink tag)
#   - [shadow,x]    → sink      (shadowed / collapsed)
#   - [omega,x]     → lobes     (treat ω as exploratory lobe-region)

# rcx_core.mu
# RCX-flavored routing with a wildcard `_` in second position.

[null,_]      -> ra
[inf,_]       -> lobe
[paradox,_]   -> sink

[ra,_]        -> ra
[lobe,_]      -> lobe
[sink,_]      -> sink

[shadow,_]    -> sink
[omega,_]     -> lobe