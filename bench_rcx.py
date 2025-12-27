# bench_rcx.py
"""
Simple command-line benchmark for RCX-π.

Right now this benchmarks:
  - `k` nested successors reduced to normal form.

You can extend this to benchmark closures, projections, etc.
"""

from __future__ import annotations
import argparse

from rcx_pi import μ, VOID
from rcx_pi.bench import benchmark_reduce


def build_succ_chain(k: int):
    """Build a Peano motif with k successors over VOID."""
    m = VOID
    for _ in range(k):
        m = m.succ()
    return m


def main():
    parser = argparse.ArgumentParser(description="Benchmark RCX-π reductions.")
    parser.add_argument(
        "--succ-depth",
        type=int,
        default=12,
        help="Number of successors to build over VOID.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=20,
        help="Number of reduction repetitions.",
    )
    args = parser.parse_args()

    def builder():
        return build_succ_chain(args.succ_depth)

    stats = benchmark_reduce(builder, repeats=args.repeats)

    print("=== RCX-π benchmark ===")
    print(f"succ depth: {args.succ_depth}")
    print(f"repeats:    {stats['repeats']}")
    print(f"total:      {stats['total_s']:.6f} s")
    print(f"avg:        {stats['avg_s']:.6f} s")
    print(f"min:        {stats['min_s']:.6f} s")
    print(f"max:        {stats['max_s']:.6f} s")


if __name__ == "__main__":
    main()