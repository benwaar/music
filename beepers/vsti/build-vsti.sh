#!/bin/bash
# build-vsti.sh — build the openDAW VSTi (WASM Z80 + AudioWorklet)
# Usage: ./build-vsti.sh [--skip-wasm]

set -euo pipefail
cd "$(dirname "$0")/vsti"

SKIP_WASM=false
[[ "${1:-}" == "--skip-wasm" ]] && SKIP_WASM=true

mkdir -p dist

# 1. Build Z80 WASM core
if [ "$SKIP_WASM" = false ]; then
  echo "building z80-core → wasm..."
  cargo build --release --target wasm32-unknown-unknown --manifest-path src/z80-core/Cargo.toml

  WASM_IN="src/z80-core/target/wasm32-unknown-unknown/release/z80_core.wasm"
  if command -v wasm-opt &>/dev/null; then
    wasm-opt -Oz "$WASM_IN" -o dist/z80-core.wasm
    echo "optimised: dist/z80-core.wasm ($(wc -c < dist/z80-core.wasm | tr -d ' ') bytes)"
  else
    cp "$WASM_IN" dist/z80-core.wasm
    echo "copied: dist/z80-core.wasm (install wasm-opt for smaller builds)"
  fi
fi

# 2. Bundle AudioWorklet processor
echo "bundling worklet..."
npx esbuild src/worklet/chip-synth-processor.ts \
  --bundle --outfile=dist/chip-synth-processor.js \
  --format=esm --target=esnext

# 3. Bundle host-side node
echo "bundling host..."
npx esbuild src/host/beeper-node.ts \
  --bundle --outfile=dist/beeper-node.js \
  --format=esm --target=esnext --external:*.wasm

echo "done → vsti/dist/"
ls -lh dist/
