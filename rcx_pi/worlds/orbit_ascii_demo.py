from __future__ import annotations

import sys
from rcx_pi.worlds_bridge import orbit_with_world_parsed


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "usage: python3 -m rcx_pi.orbit_ascii_demo WORLD SEED [MAX_STEPS]")
        print("example: python3 -m rcx_pi.orbit_ascii_demo pingpong ping 12")
        sys.exit(1)

    world = sys.argv[1]
    seed = sys.argv[2]
    max_steps = int(sys.argv[3]) if len(sys.argv) >= 4 else 20

    code, raw, parsed = orbit_with_world_parsed(world, seed, max_steps)
    if code != 0:
        # Bubble up Rust-side error output so it’s visible.
        print(raw)
        sys.exit(code)

    states = parsed.get("states", [])
    kind = parsed.get("kind")
    period = parsed.get("period")
    classification_raw = parsed.get("classification_raw", "")

    print(f"[ω-orbit] world={world} seed={seed} max_steps={max_steps}\n")

    if not states:
        print("(no states returned)")
        print()
    else:
        width = max(1, len(str(len(states) - 1)))
        for idx, s in enumerate(states):
            print(f"{idx:>{width}}: {s}")
        print()

    print(f"[ω-class] kind={kind} period={period}")
    print(f"[ω-raw]   {classification_raw}")


if __name__ == "__main__":
    main()
