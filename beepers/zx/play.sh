#!/bin/bash
# play.sh — build a beeper exercise and play it in Fuse
# Usage: ./play.sh [NUM]  e.g. ./play.sh 1.1
# No arg → latest .asm

set -euo pipefail
cd "$(dirname "$0")"

FUSE_APP="/Applications/Fuse.app"

if [ ! -d "$FUSE_APP" ]; then
  echo "Fuse not found. Install with:"
  echo "  brew install --cask fredm-fuse"
  exit 1
fi

TAP="$(bash build-tap.sh "$@" | tail -1)"
TAP_ABS="$(cd "$(dirname "$TAP")" && pwd)/$(basename "$TAP")"

pkill -x Fuse 2>/dev/null && sleep 0.5
open -a "$FUSE_APP"
sleep 2
osascript -e 'tell application "Fuse" to open POSIX file "'"$TAP_ABS"'"' >/dev/null 2>&1
echo "opened in Fuse: $TAP_ABS"
