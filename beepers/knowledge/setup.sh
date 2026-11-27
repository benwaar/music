#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "=== Knowledge Corpus Setup ==="

PYTHON_BIN="${PYTHON_BIN:-$(pyenv which python3)}"
EXPECTED_PYTHON_VERSION="$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
VENV_DIR="knowledge/.venv"

# 1. Create an isolated environment and install Python dependencies
if [ -x "$VENV_DIR/bin/python" ] && [ "$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != "$EXPECTED_PYTHON_VERSION" ]; then
	echo "Rebuilding $VENV_DIR with Python $EXPECTED_PYTHON_VERSION"
	"$PYTHON_BIN" -m venv --clear "$VENV_DIR"
elif [ ! -d "$VENV_DIR" ]; then
	"$PYTHON_BIN" -m venv "$VENV_DIR"
	echo "Created $VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo "Installing dependencies..."
python -m pip install -q -r knowledge/requirements.txt

# 2. Fetch raw data from public sources
echo "Fetching raw data..."
bash knowledge/scripts/fetch_all.sh

# 3. Normalise into chunks
echo "Normalising chunks..."
python knowledge/scripts/normalise.py

# 4. Build FAISS index (optional — needs sentence-transformers + faiss-cpu)
echo "Building FAISS index..."
python knowledge/scripts/embed.py

# 5. Export ONNX model + vectors for MCP semantic search
echo "Exporting ONNX model..."
python knowledge/scripts/export_onnx.py

# 6. Build human-readable kb/
echo "Building kb/..."
python knowledge/scripts/build_kb.py

# 7. Build MCP server (Rust)
echo ""
echo "Building MCP server (Rust)..."
echo "  Note: first build is slow (~2-3 min) due to ONNX runtime + tokenizer crates."
echo "  Subsequent builds are incremental and fast."
(cd knowledge-mcp && cargo build --release 2>&1)

echo ""
echo "=== Done ==="
echo "Corpus ready: $(find knowledge/chunks -name '*.md' | wc -l | tr -d ' ') chunks"
echo ""
echo "MCP server registered in .claude/settings.local.json"
echo "Restart Claude Code to activate the knowledge-corpus MCP server."
