# Simple rewrite demo: PING → PONG, then PONG goes to r_a.

# Rewrite bare PING into PONG
PING            -> rewrite(PONG)

# Optionally, a structured example:
#   [PING,PING] → [PONG,PING]  (just to show structured rewrite)
[PING,PING]     -> rewrite([PONG,PING])

# Once something is literally PONG, send it to r_a
PONG            -> ra

# Anything that looks obviously contradictory (toy example)
[PARADOX,X]     -> sink