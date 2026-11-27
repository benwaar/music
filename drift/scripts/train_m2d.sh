#!/usr/bin/env bash
# Train M2d attention experiment in supervised chunks — train, sample, review, repeat.
#
# Each chunk trains for ~5 epochs (~1 hour on MPS), then:
#   1. Generates 3 samples
#   2. Opens the spectrogram + plays the audio
#   3. Asks "Continue?" — hit Enter for yes, n to stop
#
# Resumes automatically from the latest checkpoint.
#
# Usage:
#   bash scripts/train_m2d.sh            # 5-epoch chunks, 10 total
#   bash scripts/train_m2d.sh 20         # 5-epoch chunks, 20 total

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate
mkdir -p _data/checkpoints_attn _data/generated/m2d_attn

CHUNK=5                 # epochs per chunk (~1 hour on MPS)
TOTAL=${1:-10}
BATCH_SIZE=16
DATA=_data/segments
CKPT_DIR=_data/checkpoints_attn
GEN_DIR=_data/generated/m2d_attn
ATTN_LEVELS=2

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

while [ "$completed" -lt "$TOTAL" ]; do
    target=$((completed + CHUNK))
    if [ "$target" -gt "$TOTAL" ]; then
        target=$TOTAL
    fi

    echo ""
    echo "============================================================"
    echo "  M2d: Training epochs $((completed + 1)) – $target of $TOTAL"
    echo "  (self-attention at level $ATTN_LEVELS)"
    echo "============================================================"
    echo ""

    caffeinate -dims python -m drift.train \
        --data "$DATA" \
        --epochs "$target" \
        --batch-size "$BATCH_SIZE" \
        --save-every "$CHUNK" \
        --checkpoint-dir "$CKPT_DIR" \
        --attn-levels "$ATTN_LEVELS" \
        $resume_flag

    completed=$target
    ckpt="$CKPT_DIR/epoch_$(printf '%04d' $completed).pt"

    if [ ! -f "$ckpt" ]; then
        echo "ERROR: Expected checkpoint $ckpt not found."
        exit 1
    fi

    # Next chunk resumes from this checkpoint.
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

    # Stop audio if still playing.
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
