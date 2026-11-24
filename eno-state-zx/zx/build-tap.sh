#!/bin/bash
# build-tap.sh — assemble beeper.asm and wrap it in a TAP with BASIC loader

set -euo pipefail
cd "$(dirname "$0")"

LOCAL_PASMO="../_tools/pasmo/pasmo"
if [ -x "$LOCAL_PASMO" ]; then
  PASMO="$LOCAL_PASMO"
elif command -v pasmo &>/dev/null; then
  PASMO="pasmo"
else
  echo "error: pasmo not found (install via 'brew install pasmo' or run: cd _tools/pasmo && ./configure && make)"
  exit 1
fi

ASM="beeper.asm"
BIN="beeper.bin"
TAP="beeper.tap"

[ -f "$ASM" ] || { echo "error: $ASM not found"; exit 1; }

# convert screen.jpg → screen.scr if needed (cauldron png2scr pattern)
if [ -f "screen.jpg" ] && { [ ! -f "screen.scr" ] || [ "screen.jpg" -nt "screen.scr" ]; }; then
  python3 -I ../tools/png2scr.py screen.jpg screen.scr
  echo "converted: screen.jpg → screen.scr ($(wc -c < screen.scr | tr -d ' ') bytes)"
fi

"$PASMO" --bin "$ASM" "$BIN" 2>&1 | grep -v "^WARNING" || true
echo "assembled: $ASM → $BIN ($(wc -c < "$BIN" | tr -d ' ') bytes)"

python3 -I ../tools/tap.py "$BIN" "$TAP"

echo "$TAP"
