#!/bin/bash
# serve.sh — local dev server for VSTi harness
# AudioWorklet requires HTTPS or localhost, plain file:// won't work

set -euo pipefail
cd "$(dirname "$0")/vsti"

PORT="${1:-8080}"

echo "serving vsti/ at http://localhost:$PORT"
echo "open http://localhost:$PORT/harness.html"
python3 -m http.server "$PORT"
