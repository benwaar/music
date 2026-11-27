#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Requires: npx (Node/npm) — installs @marp-team/marp-cli on first run
npx --yes @marp-team/marp-cli \
  --html \
  --output "$SCRIPT_DIR/presentation.html" \
  "$SCRIPT_DIR/presentation.md"

echo "Built: $SCRIPT_DIR/presentation.html"
