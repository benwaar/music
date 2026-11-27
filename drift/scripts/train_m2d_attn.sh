#!/usr/bin/env bash
# M2d experiment: train with self-attention at level 2 for 10 epochs.
# Compare autocorrelation against baseline (bottleneck-only attention).
#
# Run overnight — ~2 hours on MPS.
#
# Usage:
#   bash scripts/train_m2d_attn.sh

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate
mkdir -p _data/checkpoints_attn _data/generated/m2d_attn

echo "=== M2d: Training with attention at level 2 ==="
echo "  10 epochs, save every 5, checkpoints to _data/checkpoints_attn/"
echo ""

caffeinate -dims python -m drift.train \
    --data _data/segments \
    --epochs 10 \
    --batch-size 16 \
    --save-every 5 \
    --checkpoint-dir _data/checkpoints_attn \
    --attn-levels 2

echo ""
echo "=== Generating samples from attention model ==="

python scripts/generate.py \
    --checkpoint _data/checkpoints_attn/epoch_0010.pt \
    --n 10 \
    --output _data/generated/m2d_attn

echo ""
echo "=== Comparing autocorrelation: baseline vs attention ==="

python scripts/analyse_repetition.py \
    --checkpoint _data/checkpoints_attn/epoch_0010.pt \
    --n-real 50 \
    --n-gen 10 \
    --output _data/eval/repetition_attn.json \
    --plot docs/images/m2d-autocorrelation-attn.png

echo ""
echo "=== Done. Compare:"
echo "  Baseline: _data/eval/repetition.json"
echo "  Attention: _data/eval/repetition_attn.json"
