# Tiny paradox-flavored Mu program
# We don't “solve” the liar paradox; we tag it structurally.

# If someone asserts contradictory truth values about LIAR,
# we rewrite it into an explicit PARADOX marker.

[LIAR,SAYS_TRUE]   -> rewrite [PARADOX,LIAR]
[LIAR,SAYS_FALSE]  -> rewrite [PARADOX,LIAR]

# Once tagged as [PARADOX,LIAR], we explicitly push it into the sink.
[PARADOX,LIAR]     -> sink

# Ambiguous/non-crisp cases get parked in the lobe.
[LIAR,UNKNOWN]     -> lobe