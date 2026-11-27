#!/usr/bin/env bash
# Train 8s loop PoC with bumped capacity — supervised 5-epoch chunks.
#
# base_ch=64 (~12M params) on 8s loop-filtered data.
# Each chunk: train 5 epochs, generate 3 samples, show + play, ask to continue.
#
# Usage:
#   bash scripts/train_8s_loops.sh            # 50 epochs in 5-epoch chunks
#   bash scripts/train_8s_loops.sh 30         # 30 epochs total

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate
mkdir -p _data/checkpoints_8s_loops _data/generated/8s_loops

CHUNK=5
TOTAL=${1:-50}
BATCH_SIZE=4           # 8s + base_ch=64 = 4x memory, halve batch twice
DATA=_data/segments_loops
CKPT_DIR=_data/checkpoints_8s_loops
GEN_DIR=_data/generated/8s_loops
BASE_CH=64
DURATION=8

completed=0
resume_flag=""

# Find latest checkpoint and resume from it.
latest=$(ls -1t "$CKPT_DIR"/epoch_*.pt 2>/dev/null | head -1 || true)
if [ -n "$latest" ]; then
    completed=$(python -c "import torch; print(torch.load('$latest', map_location='cpu', weights_only=False)['epoch'])")
    resume_flag="--resume $latest"
    echo "Resuming from: $latest (epoch $completed)"
fi

if [ "$completed" -ge "$TOTAL" ]; then
    echo "Already at $completed epochs (target: $TOTAL). Nothing to do."
    exit 0
fi

# Print param count at start.
python -c "
from drift.unet import UNet
m = UNet(base_ch=$BASE_CH)
n = sum(p.numel() for p in m.parameters())
print(f'Model: base_ch={$BASE_CH}, {n:,} params')
"

while [ "$completed" -lt "$TOTAL" ]; do
    target=$((completed + CHUNK))
    if [ "$target" -gt "$TOTAL" ]; then
        target=$TOTAL
    fi

    echo ""
    echo "============================================================"
    echo "  8s loops: Training epochs $((completed + 1)) – $target of $TOTAL"
    echo "  (base_ch=$BASE_CH, duration=${DURATION}s, batch=$BATCH_SIZE)"
    echo "============================================================"
    echo ""

    caffeinate -dims python -m drift.train \
        --data "$DATA" \
        --duration "$DURATION" \
        --base-ch "$BASE_CH" \
        --epochs "$target" \
        --batch-size "$BATCH_SIZE" \
        --save-every "$CHUNK" \
        --checkpoint-dir "$CKPT_DIR" \
        $resume_flag

    completed=$target
    ckpt="$CKPT_DIR/epoch_$(printf '%04d' $completed).pt"

    if [ ! -f "$ckpt" ]; then
        echo "ERROR: Expected checkpoint $ckpt not found."
        exit 1
    fi

    resume_flag="--resume $ckpt"

    # Generate samples.
    echo ""
    echo "--- Generating samples from epoch $completed ---"
    sample_dir="$GEN_DIR/epoch_${completed}"
    python scripts/generate.py \
        --checkpoint "$ckpt" \
        --n 3 \
        --output "$sample_dir"

    # Show spectrogram + play audio (macOS).
    if [ -f "$sample_dir/sample_000.png" ]; then
        open "$sample_dir/sample_000.png"
    fi
    AFPLAY_PID=""
    if [ -f "$sample_dir/sample_000.wav" ]; then
        afplay "$sample_dir/sample_000.wav" &
        AFPLAY_PID=$!
    fi

    # Done?
    if [ "$completed" -ge "$TOTAL" ]; then
        echo ""
        echo "=== Reached $TOTAL epochs. Done! ==="
        break
    fi

    # Ask to continue.
    echo ""
    echo "------------------------------------------------------------"
    echo "  Epoch $completed / $TOTAL"
    echo "  Checkpoint: $ckpt"
    echo "  Samples:    $sample_dir/"
    echo "  Next chunk: epochs $((completed + 1)) – $((completed + CHUNK))"
    echo "------------------------------------------------------------"
    echo ""
    read -rp "Continue? [Y/n] " answer

    [ -n "$AFPLAY_PID" ] && kill "$AFPLAY_PID" 2>/dev/null || true

    case "$answer" in
        [nN]*)
            echo "Stopped at epoch $completed. Run again to resume."
            exit 0
            ;;
    esac
done

echo ""
echo "Final checkpoint: $ckpt"
echo "All samples in: $GEN_DIR/"
echo ""
echo "Run autocorrelation analysis:"
echo "  python scripts/analyse_repetition.py \\"
echo "    --data $DATA --duration $DURATION \\"
echo "    --checkpoint $ckpt \\"
echo "    --n-real 50 --n-gen 20 \\"
echo "    --output _data/eval/repetition_8s_loops.json \\"
echo "    --plot docs/images/m2d-autocorrelation-8s-loops.png"
