# BOOTSTRAP COMPLETE (Historical)

Bootstrap phase completed as of 2026-01-14T00:19:50Z.

This document records:
- founding constraints
- invariants
- initial architecture decisions

It is no longer a live roadmap.
Ongoing work must follow:
- CI_POLICY.md
- TASKS.md
- NEXT_STEPS.md (if present)

Kernel remains frozen.
Layered growth only.

---
RCX-π / RCX Stack — Bootstrap Guide

This file exists so that future AI sessions can quickly understand the repository without needing past conversation context.

Repository layout:
- rcx_pi/               Python RCX-π engine (Motif VM, evaluator, registry)
- rcx_pi_rust/          Rust RCX-π runtime (Mu, buckets, rules, REPL)
- worlds_json/          JSON world format for Rust <-> Python sync
- README_BOOTSTRAP.md   This onboarding guide (main file for new AI)

Rust RCX-π (rcx_pi_rust):
- Runs minimal Mu routing system: r_a (stable), lobes (potential), sink (paradox)
- Pattern rules may send to buckets or Rewrite(Mu)
- If no rule matches, fallback classifier:
    Sym(x) -> r_a
    [x,x]  -> lobes
    [x,y]  -> sink
- Worlds live at rcx_pi_rust/mu_programs/*.mu

Run REPL:
cd rcx_pi_rust
cargo run --example repl

Useful REPL commands:
:load-world NAME
:save-world NAME
:rules
:why MU
:orbit MU n
:omega MU n
:export-json NAME
:import-json NAME
:doc-world NAME
:save-state NAME
:load-state NAME
:reset
:q

Example worlds:
- rcx_core.mu   core tags null/inf/paradox/shadow/omega
- pingpong.mu   ping ↔ pong rewrite for orbit cycles
- vars_demo.mu  $x,$y variable patterns
- news.mu       small classification demo

Orbit demo:
cargo run --example orbit_cli -- pingpong ping 12

State snapshot demo:
cargo run --example state_demo

Python RCX-π (rcx_pi):
- Motif VM (numbers, lists, evaluator, registry)
- modules:
  rcx_pi/api.py
  rcx_pi/program_registry.py
  rcx_pi/worlds_json.py
  rcx_pi/worlds_bridge.py

World conversion:
MU -> JSON:
python3 -m rcx_pi.worlds_json to-json rcx_pi_rust/mu_programs/rcx_core.mu worlds_json/rcx_core.json
JSON -> MU:
python3 -m rcx_pi.worlds_json to-mu worlds_json/rcx_core.json rcx_pi_rust/mu_programs/rcx_core.mu

How to brief a new AI session:
"I am working on RCX-π. Repo contains rcx_pi (Python) and rcx_pi_rust (Rust). Worlds are stored in .mu and JSON. Mu terms route into r_a, lobes, sink. REPL supports rules, orbits, snapshots. Read README_BOOTSTRAP.md first."
Then paste any file(s) that AI must edit.

Roadmap:
short-term: serialization, auto-doc
mid-term: visual orbit exploration, rule mutation tools
long-term: self-hosting/meta-circular RCX core

Remember:
RCX-π is the minimal organism spine. We will build higher RCX layers on top.

## Local Git hooks (recommended)

This repo includes non-blocking helper hooks under `.githooks/`.

Enable them locally (per-machine):

    git config core.hooksPath .githooks

These hooks are reminders only (they do not block commits).

## JSON fixtures (golden outputs)

We keep small “golden” JSON outputs under `docs/fixtures/` for quick diffs and schema stability:

- `docs/fixtures/orbit_pingpong_v1.json`
- `docs/fixtures/engine_rcx_core_v1.json`

Regenerate locally:

    (cd rcx_pi_rust && cargo build --examples)
    (cd rcx_pi_rust && cargo run --example orbit_json_cli -- pingpong ping 12 > ../docs/fixtures/orbit_pingpong_v1.json)
    (cd rcx_pi_rust && cargo run --example engine_json_cli -- rcx_core "[null,a]" "[inf,a]" "[paradox,a]" "[omega,[a,b]]" > ../docs/fixtures/engine_rcx_core_v1.json)

## Snapshot JSON (golden outputs)

We keep a replayable snapshot fixture under docs/fixtures:

- docs/fixtures/snapshot_rcx_core_v1.json (rcx.snapshot.v1)

Regenerate:

    (cd rcx_pi_rust && cargo build --examples)
    (cd rcx_pi_rust && cargo run --example snapshot_json_cli -- rcx_core "[null,a]" "[inf,a]" "[paradox,a]" "[omega,[a,b]]" > ../docs/fixtures/snapshot_rcx_core_v1.json)

Roundtrip proof (write -> wipe -> restore -> same behavior):

    (cd rcx_pi_rust && cargo run --example snapshot_roundtrip_cli)
