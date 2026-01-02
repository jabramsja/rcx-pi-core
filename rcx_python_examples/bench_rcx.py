#!/usr/bin/env python3
"""
Lightweight benchmark harness for the current RCX-π core.

This is intentionally **aligned with the new API**:

    - Numbers: num, add, motif_to_int, zero
    - Lists: list_from_py, py_from_list
    - Programs: swap_ends_xyz_closure + PureEvaluator.run
    - Evaluator: new_evaluator()

It does *not* use ev.reduce(), because the pure structural reducer
has not been implemented yet. Think of this as a smoke-benchmark for
the “motif + evaluator + list program” pipeline.
"""

from __future__ import annotations

import time
import statistics as stats

import rcx_pi


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def bench_add(iterations: int) -> float:
    """
    Benchmark Peano addition using rcx_pi.add over Motif numbers.

    We repeatedly compute add(num(2), num(3)) and discard the result.
    Returns elapsed seconds.
    """
    num = rcx_pi.num
    add = rcx_pi.add

    a = num(2)
    b = num(3)

    start = time.perf_counter()
    for _ in range(iterations):
        _ = add(a, b)
    end = time.perf_counter()

    return end - start


def bench_swap_ends(iterations: int, list_len: int) -> float:
    """
    Benchmark list program swap_ends_xyz_closure via PureEvaluator.run.

    We build a fixed list [0,1,2,...,list_len-1] as a Motif,
    then repeatedly apply swap_ends_xyz_closure and discard the result.
    """
    list_from_py = rcx_pi.list_from_py
    py_from_list = rcx_pi.py_from_list
    new_evaluator = rcx_pi.new_evaluator
    swap_ends = rcx_pi.swap_ends_xyz_closure

    xs = list_from_py(list(range(list_len)))
    ev = new_evaluator()
    prog = swap_ends()

    # Sanity check once before timing
    out = ev.run(prog, xs)
    out_list = py_from_list(out)
    if out_list is None:
        raise RuntimeError("swap_ends did not produce a pure motif list")

    if out_list[0] != list_len - 1 or out_list[-1] != 0:
        raise RuntimeError(
            f"swap_ends sanity check failed: expected ends swapped, got {out_list}")

    start = time.perf_counter()
    cur = xs
    for _ in range(iterations):
        cur = ev.run(prog, cur)
    end = time.perf_counter()

    # Optional: keep cur alive so the loop doesn't get optimized away.
    _ = py_from_list(cur)

    return end - start


def run_bench(fn, *, repeats: int = 5, **kwargs) -> None:
    """
    Run a benchmark function several times and print aggregate stats.
    """
    times = []
    for i in range(repeats):
        t = fn(**kwargs)
        times.append(t)
        print(f"  run {i + 1}: {t:.6f}s")

    mean = stats.mean(times)
    stdev = stats.pstdev(times) if len(times) > 1 else 0.0
    print(f"  mean: {mean:.6f}s  (σ={stdev:.6f}s)\n")


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="RCX-π micro-benchmarks (current API)")
    parser.add_argument(
        "--repeats",
        type=int,
        default=5,
        help="Number of times to repeat each benchmark (default: 5)",
    )
    parser.add_argument(
        "--iters-add",
        type=int,
        default=50_000,
        help="Iterations for the Peano add benchmark (default: 50k)",
    )
    parser.add_argument(
        "--iters-swap",
        type=int,
        default=10_000,
        help="Iterations for the swap_ends benchmark (default: 10k)",
    )
    parser.add_argument(
        "--list-len",
        type=int,
        default=8,
        help="Length of list for swap_ends benchmark (default: 8)",
    )

    args = parser.parse_args()

    print("RCX-π current-core benchmarks\n")

    print(f"[add] Peano add(num(2), num(3)) x {args.iters_add}")
    run_bench(bench_add, repeats=args.repeats, iterations=args.iters_add)

    print(f"[swap_ends] list length {args.list_len} x {args.iters_swap}")
    run_bench(
        bench_swap_ends,
        repeats=args.repeats,
        iterations=args.iters_swap,
        list_len=args.list_len,
    )


if __name__ == "__main__":
    main()
