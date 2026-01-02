# rcx_pi/worlds_score_demo.py

from pprint import pprint
from rcx_pi.worlds_probe import score_world, spec_from_world


def main():
    seeds = [
        "[null,a]",
        "[inf,a]",
        "[paradox,a]",
        "[omega,[a,b]]",
        "[a,a]",
        "[dog,cat]",
    ]

    # Treat rcx_core as the "gold" world for this seed set
    desired_routes = spec_from_world("rcx_core", seeds, max_steps=20)

    print("=== desired spec (derived from rcx_core) ===")
    pprint(desired_routes)

    print("\n=== score rcx_core against its own spec ===")
    core_score = score_world("rcx_core", seeds, desired_routes, max_steps=20)
    pprint(core_score)

    print("\n=== score vars_demo against rcx_core spec ===")
    vars_score = score_world("vars_demo", seeds, desired_routes, max_steps=20)
    pprint(vars_score)


if __name__ == "__main__":
    main()
