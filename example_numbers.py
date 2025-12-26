# rcx_pi/demos/example_numbers.py
from rcx_pi import μ,VOID,UNIT
from rcx_pi.engine.evaluator_pure import Evaluator

def num(n):
    x=VOID
    for _ in range(n): x=μ(x)
    return x

E=Evaluator()

a=num(3)      # 3 = succ(succ(succ(0)))
b=num(2)

expr = a.add(b)          # → structural add motif
print("RAW:",expr)
print("REDUCED:",E.reduce(expr))