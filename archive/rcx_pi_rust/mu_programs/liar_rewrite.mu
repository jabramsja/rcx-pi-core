# Liar paradox rewrite program
# [LIAR,SAYS_TRUE]   => rewrite [LIAR,SAYS_FALSE]
# [LIAR,SAYS_FALSE]  => rewrite [LIAR,SAYS_TRUE]
# [LIAR,UNKNOWN]     => lobe      (unstable but not fatal)
# [LIAR,PARADOX]     => sink      (explicit paradox marker)

[LIAR,SAYS_TRUE]   => rewrite [LIAR,SAYS_FALSE]
[LIAR,SAYS_FALSE]  => rewrite [LIAR,SAYS_TRUE]
[LIAR,UNKNOWN]     => lobe
[LIAR,PARADOX]     => sink