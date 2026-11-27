#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== chant setup ==="

# --- Python (pyenv) ---
REQUIRED_PY="3.11"
if ! command -v pyenv &>/dev/null; then
  echo "ERROR: pyenv not found. Install it: https://github.com/pyenv/pyenv"
  exit 1
fi

CURRENT_PY="$(pyenv version-name)"
if [[ "$CURRENT_PY" != "$REQUIRED_PY"* ]]; then
  echo "ERROR: Python $REQUIRED_PY required (got $CURRENT_PY). Run: pyenv install 3.11 && pyenv local 3.11"
  exit 1
fi
echo "Python: $CURRENT_PY (pyenv)"

# --- Venv ---
if [ ! -d .venv ]; then
  echo "Creating virtual environment..."
  python -m venv .venv
fi

source .venv/bin/activate
echo "Venv: $(which python)"

echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "Dependencies installed"

# --- Ollama ---
echo ""
echo "--- Ollama ---"
if ! command -v ollama &>/dev/null; then
  echo "ERROR: ollama not found. Install it: https://ollama.com"
  exit 1
fi
echo "ollama: $(which ollama)"

MODELS=("llama3.2:1b" "smollm2:1.7b")
for model in "${MODELS[@]}"; do
  if ollama list | grep -q "$(echo "$model" | cut -d: -f1)"; then
    echo "  $model: already pulled"
  else
    echo "  Pulling $model..."
    ollama pull "$model"
  fi
done

# --- Data (symlink from drift) ---
echo ""
echo "--- Data ---"
DRIFT_DATA="../drift/_data"
if [ -L _data ]; then
  echo "_data: symlinked → $(readlink _data)"
elif [ -d _data ]; then
  echo "_data: exists (not a symlink)"
elif [ -d "$DRIFT_DATA" ]; then
  ln -s "$DRIFT_DATA" _data
  echo "_data: symlinked → $DRIFT_DATA"
else
  echo "NOTE: drift/_data not found yet at $DRIFT_DATA — symlink will be created next run (drift setup can run in parallel)"
fi

# --- HuggingFace model weights (for LoRA training) ---
# --- Synth host (Rust) ---
echo ""
echo "--- Synth host ---"
if command -v cargo &>/dev/null; then
  if [ -f synth/Cargo.toml ]; then
    echo "Building chant-host (eno-state-zx offline renderer)..."
    (cd synth && cargo build --release --quiet)
    echo "  chant-host: synth/target/release/chant-host"
  fi
else
  echo "NOTE: cargo not found — skipping chant-host build. Install Rust: https://rustup.rs"
fi

echo ""
echo "--- HuggingFace model weights ---"
HF_MODEL="HuggingFaceTB/SmolLM2-360M"
HF_CACHE="${HF_HOME:-$HOME/.cache/huggingface}/hub"
MODEL_SLUG="models--$(echo "$HF_MODEL" | tr '/' '--')"
if [ -d "$HF_CACHE/$MODEL_SLUG" ]; then
  echo "  $HF_MODEL: already cached"
else
  echo "  Downloading $HF_MODEL (LoRA base model, ~720MB)..."
  python -c "from huggingface_hub import snapshot_download; snapshot_download('$HF_MODEL')"
fi

echo ""
echo "=== setup complete ==="
