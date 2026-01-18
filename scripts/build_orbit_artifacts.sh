#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

ENGINE_RUN_FIXTURE="docs/fixtures/engine_run_from_snapshot_rcx_core_v1.json"
DOT_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.dot"
SVG_FIXTURE="docs/fixtures/orbit_from_engine_run_rcx_core_v1.svg"
INDEX_HTML="docs/fixtures/index.html"

GEN_DOT="./scripts/orbit_engine_run_to_dot.py"

[[ -f "$ENGINE_RUN_FIXTURE" ]] || { echo "missing engine-run fixture: $ENGINE_RUN_FIXTURE" >&2; exit 1; }
[[ -x "$GEN_DOT" ]] || { echo "missing generator (not executable): $GEN_DOT" >&2; exit 1; }

echo "== 1/4) engine_run -> orbit.dot =="
python3 "$GEN_DOT" "$ENGINE_RUN_FIXTURE" "$DOT_FIXTURE" >/dev/null
echo "OK: wrote $DOT_FIXTURE"

echo "== 2/4) orbit.dot -> orbit.svg (requires graphviz dot) =="
if ! command -v dot >/dev/null 2>&1; then
  echo "missing graphviz 'dot' binary. Install graphviz and re-run." >&2
  exit 1
fi
dot -Tsvg "$DOT_FIXTURE" > "$SVG_FIXTURE"
echo "OK: wrote $SVG_FIXTURE"

echo "== 3/4) write docs/fixtures/index.html =="
python3 - "$ENGINE_RUN_FIXTURE" "$DOT_FIXTURE" "$SVG_FIXTURE" "$INDEX_HTML" <<'PY'
import sys
from pathlib import Path

engine_run, dotp, svgp, outp = map(Path, sys.argv[1:5])

html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RCX Orbit Artifacts (v1)</title>
  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; }}
    .meta {{ color: #444; margin-bottom: 16px; }}
    .box {{ border: 1px solid #ddd; border-radius: 10px; padding: 14px; margin: 14px 0; }}
    .links a {{ margin-right: 12px; }}
    .svgwrap {{ overflow: auto; border: 1px solid #eee; border-radius: 10px; padding: 10px; background: #fafafa; }}
    .hint {{ color: #666; font-size: 0.95rem; }}
    code {{ background: #f2f2f2; padding: 2px 6px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>RCX Orbit Artifacts (v1)</h1>
  <div class="meta">
    Deterministic chain: <code>engine_run.v1</code> → <code>orbit.dot</code> → <code>orbit.svg</code>
  </div>

  <div class="box links">
    <strong>Fixtures</strong><br/>
    <a href="{engine_run.name}">{engine_run.name}</a>
    <a href="{dotp.name}">{dotp.name}</a>
    <a href="{svgp.name}">{svgp.name}</a>
  </div>

  <div class="box">
    <strong>Orbit (SVG)</strong>
    <div class="hint">If this looks huge, zoom your browser or open the SVG directly.</div>
    <div class="svgwrap">
      <object type="image/svg+xml" data="{svgp.name}" width="100%" height="600"></object>
    </div>
  </div>

  <div class="box">
    <strong>Build</strong>
    <div class="hint">From repo root:</div>
    <pre><code>./scripts/build_orbit_artifacts.sh</code></pre>
  </div>
</body>
</html>
"""
outp.write_text(html, encoding="utf-8")
print(f"OK: wrote {outp}")
PY

echo "== 4/4) done =="
echo "OK: artifacts updated:"
echo "  - $DOT_FIXTURE"
echo "  - $SVG_FIXTURE"
echo "  - $INDEX_HTML"
