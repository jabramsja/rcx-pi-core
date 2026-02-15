########################################
# RCX WORLD ROUTING DEMO
########################################

# Uppercase NEWS
[NEWS,STABLE]   -> ra
[NEWS,UNSTABLE] -> lobe
[NEWS,PARADOX]  -> sink
[NEWS,UNKNOWN]  -> sink

# Lowercase news aliases
[news,stable]   -> ra
[news,unstable] -> lobe
[news,paradox]  -> sink
[news,unknown]  -> sink