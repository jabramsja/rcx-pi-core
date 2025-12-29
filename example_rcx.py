from rcx_pi.engine.evaluator_pure import PureEvaluator
from rcx_pi.programs import swap_ends_xyz_closure, activate
from rcx_pi.listutils import list_from_py, py_from_list

if __name__ == "__main__":
    ev = PureEvaluator()

    # Example: swap ends of a list [2, 5] -> [5, 2]
    swap_cl = swap_ends_xyz_closure()
    pair = list_from_py([2, 5])

    result_motif = activate(ev, swap_cl, pair)
    result_py = py_from_list(result_motif)

    print("Input:  [2, 5]")
    print("Output:", result_py)