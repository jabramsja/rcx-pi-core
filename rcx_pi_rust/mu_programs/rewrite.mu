# Simple rewrite demo for RCX-π
# These rules use the new `rewrite` action.

PING        -> rewrite PONG
[PING,PING] -> lobe
[PING,OTHER] -> sink