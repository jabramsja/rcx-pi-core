# example_rcx.py

from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.programs import swap_xy_closure, activate
from rcx_pi.listutils import list_from_py


def main():
    ev = PureEvaluator()

    # Build a simple pair [2, 5] or ["x", "y"], whatever you like
    pair = list_from_py([2, 5])

    swap_cl = swap_xy_closure()
    result = activate(ev, swap_cl, pair)

    print("Input pair  :", pair)
    print("Swapped pair:", result)


if __name__ == "__main__":
    main()