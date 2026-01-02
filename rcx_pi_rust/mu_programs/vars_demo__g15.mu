# mu_programs/vars_demo.mu
# variable demo with precedence: specific patterns first

[null,$x]    -> ra
[paradox,$x] -> sink
[$x,$x]      -> lobe
[$x,$y]      -> rewrite([$y,$x])