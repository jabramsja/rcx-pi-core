# mu_programs/vars_demo.mu
# variable demo with precedence: specific patterns first
[omega,_] -> lobe

[null,$x]    -> ra
[paradox,$x] -> sink
[inf,$x]     -> lobe
[$x,$x]      -> lobe
[$x,$y]      -> rewrite([$y,$x])
