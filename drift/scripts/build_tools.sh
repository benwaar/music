#!/usr/bin/env bash
set -euo pipefail
#
# Build local tool binaries into _tools/bin/.
#
# Clones, builds, and installs chip-rendering tools that aren't available
# as brew bottles. Idempotent — skips tools that are already built.
#
# Tools built:
#   vgmplay     — VGM/VGZ → wav (from ValleyBell/vgmplay-libvgm, -w flag)
#   sidplayfp   — SID → wav     (from libsidplayfp/sidplayfp)
#
# Prerequisites (installed by setup.sh):
#   cmake, pkg-config, libsidplayfp, zlib (all via brew)
#
# Usage:
#   bash scripts/build_tools.sh

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

TOOLS_DIR="$ROOT/_tools"
BIN_DIR="$TOOLS_DIR/bin"
SRC_DIR="$TOOLS_DIR/src"

mkdir -p "$BIN_DIR" "$SRC_DIR"

# ---------------------------------------------------------------------------
# vgm2wav — from vgmplay-libvgm (requires libvgm built first)
# ---------------------------------------------------------------------------
if [ -f "$BIN_DIR/vgm2wav" ]; then
  echo "vgm2wav already built"
else
  echo "Building vgm2wav..."
  VGMPLAY_SRC="$SRC_DIR/vgmplay-libvgm"
  LOCAL_PREFIX="$TOOLS_DIR/local"
  mkdir -p "$LOCAL_PREFIX"

  if [ ! -d "$VGMPLAY_SRC" ]; then
    git clone --depth 1 https://github.com/ValleyBell/vgmplay-libvgm.git "$VGMPLAY_SRC"
  fi

  cd "$VGMPLAY_SRC"
  git submodule update --init --recursive

  # Build libvgm first
  echo "  Building libvgm..."
  mkdir -p libvgm/build && cd libvgm/build
  cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$LOCAL_PREFIX"
  make -j"$(sysctl -n hw.ncpu)"
  make install
  cd "$VGMPLAY_SRC"

  # Now build vgmplay with libvgm from our local prefix
  echo "  Building vgmplay..."
  mkdir -p build && cd build
  cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$LOCAL_PREFIX"
  make -j"$(sysctl -n hw.ncpu)" vgmplay

  cp vgmplay "$BIN_DIR/"
  echo "Installed: $BIN_DIR/vgmplay"
  cd "$ROOT"
fi

# ---------------------------------------------------------------------------
# sidplayfp — CLI player/renderer using libsidplayfp
# ---------------------------------------------------------------------------
if [ -f "$BIN_DIR/sidplayfp" ]; then
  echo "sidplayfp already built"
else
  echo "Building sidplayfp..."
  SIDPLAY_SRC="$SRC_DIR/sidplayfp"

  if [ ! -d "$SIDPLAY_SRC" ]; then
    git clone --depth 1 https://github.com/libsidplayfp/sidplayfp.git "$SIDPLAY_SRC"
  fi

  cd "$SIDPLAY_SRC"
  export PATH="/opt/homebrew/opt/libtool/libexec/gnubin:$PATH"
  autoreconf -ivf 2>/dev/null || {
    echo "autoreconf not found — installing autotools..."
    brew install autoconf automake libtool
    export PATH="/opt/homebrew/opt/libtool/libexec/gnubin:$PATH"
    autoreconf -ivf
  }

  PKG_CONFIG_PATH="$(brew --prefix libsidplayfp)/lib/pkgconfig:${PKG_CONFIG_PATH:-}" \
    ./configure --prefix="$TOOLS_DIR/local"

  make -j"$(sysctl -n hw.ncpu)"
  cp src/sidplayfp "$BIN_DIR/"
  echo "Installed: $BIN_DIR/sidplayfp"
  cd "$ROOT"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "=== _tools/bin/ ==="
ls -1 "$BIN_DIR"
