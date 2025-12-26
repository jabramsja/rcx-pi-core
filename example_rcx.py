# rcx_pi/demos/example_rcx.py
from rcx_pi import μ,VOID,UNIT
from rcx_pi.engine.evaluator_pure import Evaluator
from rcx_pi.reduction.pattern_matching import PROJECTION,CLOSURE,VAR

x=μ(VAR,VOID)                # variable
proj=μ(PROJECTION,x,x)       # identity projection
closure=μ(CLOSURE,proj)

E=Evaluator()
value = μ(μ())               # number 1

print("Apply closure:",E.reduce(μ(CLOSURE,proj)))    # still closure
print("Activation:  ",E.reduce(μ(μ(μ(μ(μ(μ())))),closure,value)))