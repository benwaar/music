#!/usr/bin/env bash
# setup.sh — install/check all dependencies for beepers
# Run once on a new machine, or after cloning.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[32m'
YELLOW='\033[33m'
RED='\033[31m'
RESET='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]${RESET} $1"; }
warn() { echo -e "  ${YELLOW}[SKIP]${RESET} $1"; }
fail() { echo -e "  ${RED}[MISSING]${RESET} $1"; ERRORS=$((ERRORS+1)); }
step() { echo -e "\n${BOLD}==> $1${RESET}"; }
inst() { echo -e "  ${DIM}installing $1...${RESET}"; }

ERRORS=0

# ─── Platform ───────────────────────────────────────────────────

step "Platform"

if [[ "$OSTYPE" == darwin* ]]; then
  ok "macOS"
  if ! command -v brew &>/dev/null; then
    fail "Homebrew — install from https://brew.sh"
  else
    ok "Homebrew"
  fi
elif [[ "$OSTYPE" == linux* ]]; then
  ok "Linux"
else
  warn "Untested platform: $OSTYPE"
fi

# ─── TAP target (Z80 assembly) ──────────────────────────────────

step "TAP target — Z80 assembly tools"

# pasmo (Z80 assembler)
if [ -x "_tools/pasmo/pasmo" ]; then
  ok "pasmo (local)"
elif command -v pasmo &>/dev/null; then
  ok "pasmo $(pasmo --version 2>&1 | head -1 || echo '')"
else
  if [ -f "_tools/pasmo/configure" ]; then
    inst "pasmo (building from source)"
    (cd _tools/pasmo && ./configure && make) >/dev/null 2>&1
    ok "pasmo (built)"
  elif command -v brew &>/dev/null; then
    inst "pasmo"
    brew install pasmo
    ok "pasmo (installed)"
  else
    fail "pasmo — run: cd _tools/pasmo && ./configure && make"
  fi
fi

# python3 + venv + requirements
PYTHON_VERSION="3.14.0"
VENV_DIR=".venv"

if command -v pyenv &>/dev/null; then
  ok "pyenv"
  if pyenv versions --bare 2>/dev/null | grep -q "^${PYTHON_VERSION}$"; then
    ok "python ${PYTHON_VERSION} (pyenv)"
  else
    inst "python ${PYTHON_VERSION} via pyenv"
    pyenv install "${PYTHON_VERSION}"
    ok "python ${PYTHON_VERSION} (installed)"
  fi
else
  if command -v python3 &>/dev/null; then
    ok "python3 $(python3 --version 2>&1 | awk '{print $2}') (no pyenv — using system)"
  else
    fail "python3 — install pyenv (brew install pyenv) or python3"
  fi
fi

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  inst "venv at ${VENV_DIR}"
  python3 -m venv "$VENV_DIR"
  ok "venv created"
else
  ok "venv exists"
fi

# Install requirements
source "${VENV_DIR}/bin/activate"
if pip install -q -r requirements.txt 2>/dev/null; then
  ok "requirements installed ($(pip list --format=freeze | wc -l | tr -d ' ') packages)"
else
  fail "pip install -r requirements.txt"
fi

# Fuse (ZX Spectrum emulator)
if [ -d "/Applications/Fuse.app" ]; then
  ok "Fuse for macOS"
elif command -v fuse &>/dev/null; then
  ok "fuse (CLI)"
else
  if command -v brew &>/dev/null; then
    inst "Fuse"
    brew install --cask fredm-fuse
    ok "Fuse (installed)"
  else
    warn "Fuse not found — install manually for play.sh (not required for build)"
  fi
fi

# ─── VSTi target (WASM + AudioWorklet) ──────────────────────────

step "VSTi target — Rust tools"

# Rust
if command -v rustc &>/dev/null; then
  ok "rustc $(rustc --version | awk '{print $2}')"
else
  fail "rustc — install from https://rustup.rs"
fi

# wasm32 target
if rustup target list --installed 2>/dev/null | grep -q wasm32-unknown-unknown; then
  ok "wasm32-unknown-unknown target"
else
  if command -v rustup &>/dev/null; then
    inst "wasm32-unknown-unknown"
    rustup target add wasm32-unknown-unknown
    ok "wasm32-unknown-unknown (installed)"
  else
    fail "wasm32-unknown-unknown — rustup target add wasm32-unknown-unknown"
  fi
fi

# wasm-opt (binaryen — optional, smaller WASM)
if command -v wasm-opt &>/dev/null; then
  ok "wasm-opt"
else
  if command -v brew &>/dev/null; then
    inst "binaryen"
    brew install binaryen
    ok "wasm-opt (installed)"
  else
    warn "wasm-opt not found — install binaryen for smaller WASM builds (optional)"
  fi
fi

# ─── Optional: MCP (Claude only) ────────────────────────────────

step "Optional — knowledge-corpus MCP"

if [ -x "knowledge-mcp/target/release/knowledge-mcp" ]; then
  ok "knowledge-mcp binary (local)"
  echo -e "  ${DIM}MCP available — restart Claude Code to activate${RESET}"
else
  if command -v cargo &>/dev/null && [ -f "knowledge-mcp/Cargo.toml" ]; then
    inst "knowledge-mcp (building — may take a minute)"
    (cd knowledge-mcp && cargo build --release) >/dev/null 2>&1
    ok "knowledge-mcp (built)"
  else
    warn "knowledge-mcp not found (only needed for Claude sessions, not builds)"
  fi
fi

# ─── Summary ────────────────────────────────────────────────────

step "Summary"

if [ "$ERRORS" -gt 0 ]; then
  echo -e "  ${RED}${ERRORS} missing requirement(s). Fix and re-run.${RESET}"
  exit 1
else
  echo -e "  ${GREEN}All good.${RESET}"
  echo ""
  echo -e "  ${DIM}Activate: source .venv/bin/activate${RESET}"
  echo -e "  ${DIM}Build:    cd zx && ./build-tap.sh 1.1${RESET}"
  echo -e "  ${DIM}Play:     cd zx && ./play.sh 1.1${RESET}"
  echo -e "  ${DIM}VSTi:     cd vsti && cargo xtask bundle eno-state-zx --features plugin${RESET}"
  echo -e "  ${DIM}Test:     ./tools/test_plugin.py${RESET}"
  echo ""
fi
