# rcx_pi/worlds_compare_demo.py

from rcx_pi.worlds_probe import compare_worlds


def main():
    # You can tweak this seed set as you invent more worlds
    seeds = [
        "[null,a]",
        "[inf,a]",
        "[paradox,a]",
        "[omega,[a,b]]",
        "[a,a]",
        "[dog,cat]",
    ]

    result = compare_worlds("rcx_core", "vars_demo", seeds, max_steps=20)

    print("=== world comparison ===")
    print(f"world_a: {result['world_a']}")
    print(f"world_b: {result['world_b']}")
    print("\nDiffs:")
    for d in result["diffs"]:
        print(
            f"  {d['mu']:<16} | A={d['route_a']!s:<5} | "
            f"B={d['route_b']!s:<5} | same={d['same']}"
        )


if __name__ == "__main__":
    main()
