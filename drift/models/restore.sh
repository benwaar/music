#!/usr/bin/env bash
set -euo pipefail

# Restore drift M4 production checkpoint from GitHub release.
# Works in both the music (snapshot) and drift (dev) repos.

REPO="benwaar/music"
TAG="drift-models-v1"
FILE="m4_conditional_epoch10.pt"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="$SCRIPT_DIR/$FILE"

if [ -f "$TARGET" ]; then
  echo "Already present: $TARGET"
  exit 0
fi

echo "Downloading $FILE from $REPO release $TAG..."
gh release download "$TAG" \
  --repo "$REPO" \
  --pattern "$FILE" \
  --dir "$SCRIPT_DIR"

echo "Restored: $TARGET ($(du -h "$TARGET" | cut -f1))"
