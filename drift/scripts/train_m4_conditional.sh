#!/usr/bin/env bash
# Train M4 conditional model in supervised chunks — train, sample each chip, review, repeat.
#
# 15k unbalanced loop dataset, base_ch=64, 8s, num_classes=4, CFG dropout 0.1.
# Each chunk trains ~2 epochs (~1.5 hours on MPS with 15k samples), then:
#   1. Rebuilds metadata (first run only)
#   2. Generates 2 samples per chip type with DDIM-50
#   3. Opens spectrograms + plays audio
#   4. Asks "Continue?" — hit Enter for yes, n to stop
#
# Resumes automatically from the latest checkpoint.
#
# Usage:
#   bash scripts/train_m4_conditional.sh          # 2-epoch chunks, 20 total
#   bash scripts/train_m4_conditional.sh 30       # 30 epochs total

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

CHUNK=2
TOTAL=${1:-20}
BATCH_SIZE=4           # 8s + base_ch=64 = big model, small batch
DATA=_data/segments_loops
CKPT_DIR=_data/checkpoints_m4_conditional
GEN_DIR=_data/generated/m4_conditional
BASE_CH=64
DURATION=8
NUM_CLASSES=4
CFG_DROPOUT=0.1
CHIPS=(ay sid vgm modarchive)

mkdir -p "$CKPT_DIR" "$GEN_DIR"

# Step 1: Rebuild metadata if needed (unbalanced).
meta="$DATA/metadata.json"
total_files=$(python -c "
import json
with open('$meta') as f: m = json.load(f)
total = sum(len(v) for v in m['splits'].values())
print(total)
")
if [ "$total_files" -lt 10000 ]; then
    echo "--- Rebuilding metadata (unbalanced, ~15k files) ---"
    python scripts/rebuild_metadata.py --data "$DATA"
    echo ""
fi

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
m = UNet(base_ch=$BASE_CH, num_classes=$NUM_CLASSES)
n = sum(p.numel() for p in m.parameters())
print(f'Model: base_ch=$BASE_CH, num_classes=$NUM_CLASSES, {n:,} params')
"

while [ "$completed" -lt "$TOTAL" ]; do
    target=$((completed + CHUNK))
    if [ "$target" -gt "$TOTAL" ]; then
        target=$TOTAL
    fi

    echo ""
    echo "============================================================"
    echo "  M4: Training epochs $((completed + 1)) – $target of $TOTAL"
    echo "  (base_ch=$BASE_CH, ${DURATION}s, num_classes=$NUM_CLASSES, batch=$BATCH_SIZE)"
    echo "  Start: $(date '+%H:%M')"
    echo "============================================================"
    echo ""

    caffeinate -dims python -m drift.train \
        --data "$DATA" \
        --duration "$DURATION" \
        --base-ch "$BASE_CH" \
        --num-classes "$NUM_CLASSES" \
        --cfg-dropout "$CFG_DROPOUT" \
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

    # Generate samples — one per chip type, DDIM-50 eta=1.0.
    echo ""
    echo "--- Generating samples from epoch $completed (per chip type) ---"
    sample_dir="$GEN_DIR/epoch_${completed}"
    mkdir -p "$sample_dir"

    for chip in "${CHIPS[@]}"; do
        python scripts/generate.py \
            --checkpoint "$ckpt" \
            --sampler ddim --steps 50 --eta 1.0 \
            --chip "$chip" --guidance-scale 3.0 \
            --n 2 --seed 42 \
            --output "$sample_dir/$chip"
    done

    # Show first sample from each chip type.
    for chip in "${CHIPS[@]}"; do
        [ -f "$sample_dir/$chip/sample_000.png" ] && open "$sample_dir/$chip/sample_000.png"
    done
    # Play one sample.
    AFPLAY_PID=""
    if [ -f "$sample_dir/ay/sample_000.wav" ]; then
        afplay "$sample_dir/ay/sample_000.wav" &
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
    echo "  Epoch $completed / $TOTAL  ($(date '+%H:%M'))"
    echo "  Checkpoint: $ckpt"
    echo "  Samples:    $sample_dir/{ay,sid,vgm,modarchive}/"
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
echo "Compare chip types:"
echo "  open $GEN_DIR/epoch_${completed}/{ay,sid,vgm,modarchive}/sample_000.png"
