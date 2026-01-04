#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT/docs/latex/src"
BUILD_DIR="$ROOT/docs/latex/build"

mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# Copy sources into build dir (keeps build artifacts out of src)
cp -f "$SRC_DIR/wrapper.tex" .
for f in "$SRC_DIR"/*.tex; do
  [ -f "$f" ] || continue
  bn="$(basename "$f")"
  [ "$bn" = "wrapper.tex" ] && continue
  cp -f "$f" .
done

# Prefer XeLaTeX for Unicode (π, etc), fallback to pdfLaTeX.
if command -v latexmk >/dev/null 2>&1; then
  if command -v xelatex >/dev/null 2>&1; then
    latexmk -xelatex -interaction=nonstopmode -halt-on-error wrapper.tex
  else
    latexmk -pdf -interaction=nonstopmode -halt-on-error wrapper.tex
  fi
else
  if command -v xelatex >/dev/null 2>&1; then
    xelatex -interaction=nonstopmode -halt-on-error wrapper.tex
    xelatex -interaction=nonstopmode -halt-on-error wrapper.tex
  else
    pdflatex -interaction=nonstopmode -halt-on-error wrapper.tex
    pdflatex -interaction=nonstopmode -halt-on-error wrapper.tex
  fi
fi

echo "Built: $BUILD_DIR/wrapper.pdf"
ls -lh "$BUILD_DIR/wrapper.pdf" || true
