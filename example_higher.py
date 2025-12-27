# example_higher.py
"""
Demo: higher-level Peano helpers on top of RCX-π core.
"""

from rcx_pi import μ, VOID
from rcx_pi.higher import (
    num,
    motif_to_int,
    peano_list,
    peano_factorial,
    peano_sum,
    peano_map_increment,
)
from rcx_pi.pretty import pretty_motif
from rcx_pi.engine.evaluator_pure import PureEvaluator


if __name__ == "__main__":
    ev = PureEvaluator()

    print("=== RCX-π higher-level helpers ===")

    # 1) factorial
    n = 5
    fact_m = peano_factorial(n, ev)
    print(f"{n}! as motif:   {fact_m}")
    print(f"{n}! as int:     {motif_to_int(fact_m)}")
    print()

    # 2) sum
    data = [2, 5, 7]
    sum_m = peano_sum(data, ev)
    print(f"sum({data}) motif: {sum_m}")
    print(f"sum({data}) int:   {motif_to_int(sum_m)}")
    print()

    # 3) map increment
    mapped = peano_map_increment(data, delta=1, ev=ev)
    print(f"map (+1) over {data}:")
    print("  raw motif:    ", mapped)
    print("  pretty motif: ", pretty_motif(mapped))
    print()