#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== drift setup ==="

# --- Python venv ---
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

source .venv/bin/activate
echo "Python: $(python --version) ($(which python))"

echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "Dependencies installed"

# --- System deps (brew) ---
echo ""
BREW_DEPS=(p7zip ffmpeg libopenmpt libsidplayfp game-music-emu cmake pkg-config autoconf automake libtool)
for dep in "${BREW_DEPS[@]}"; do
  if brew list "$dep" &>/dev/null; then
    echo "$dep already installed"
  else
    echo "Installing $dep..."
    brew install "$dep"
  fi
done

# --- Local tool builds (sidplayfp, vgm2wav) ---
echo ""
echo "--- Building local tools ---"
bash scripts/build_tools.sh

# Verify renderers — scripts find _tools/bin/ automatically
echo ""
echo "--- Renderer check ---"
TOOLS_BIN="$(pwd)/_tools/bin"
for cmd in openmpt123 sidplayfp vgmplay ffmpeg; do
  if [ -f "$TOOLS_BIN/$cmd" ]; then
    echo "  $cmd: $TOOLS_BIN/$cmd"
  elif command -v "$cmd" &>/dev/null; then
    echo "  $cmd: $(which $cmd)"
  else
    echo "  $cmd: NOT FOUND — rendering will fail for this format"
  fi
done

# Re-activate venv (build_tools.sh runs in a subshell and may clobber it)
source .venv/bin/activate
PYTHON="$(pwd)/.venv/bin/python"

# --- Data downloads ---
echo ""
echo "--- HVSC SID files ---"
"$PYTHON" scripts/download_hvsc.py

echo ""
echo "--- AY (ZX Spectrum) files ---"
"$PYTHON" scripts/download_ay.py

echo ""
echo "--- VGM (SN76489 / SMS) files ---"
"$PYTHON" scripts/download_vgm.py

echo ""
echo "--- MOD/XM tracker modules ---"
"$PYTHON" scripts/download_modarchive.py

echo ""
echo "=== setup complete ==="
find _data -type f | wc -l | xargs echo "Total files:"
