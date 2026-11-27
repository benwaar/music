#!/usr/bin/env bash
# 8s loop PoC — filter looping segments, train 10 epochs, compare autocorrelation.
#
# Usage: bash scripts/train_8s_loop_poc.sh

set -euo pipefail

echo "=== 8s Loop PoC ==="
echo ""

# 1. Create filtered dataset (symlinks to looping 8s segments)
echo "Step 1: Creating filtered loop dataset..."
python -c "
import json
from pathlib import Path

data = json.loads(Path('_data/eval/loop_filter.json').read_text())
out_root = Path('_data/segments_loops')

for entry in data['files']:
    src = Path(entry['path'])
    chip = src.parent.name
    dst_dir = out_root / chip
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    if not dst.exists():
        dst.symlink_to(src.resolve())

total = sum(1 for _ in out_root.rglob('*_8s.wav'))
print(f'  Linked {total} looping segments into {out_root}/')
"

# 2. Build metadata for the filtered dataset
echo ""
echo "Step 2: Building dataset metadata..."
python -c "
from pathlib import Path
from drift.dataset import build_metadata
build_metadata(Path('_data/segments_loops'))
print('  Metadata built.')
"

# 3. Train 10 epochs
echo ""
echo "Step 3: Training 10 epochs on 8s loop-filtered data..."
python -m drift.train \
    --data _data/segments_loops \
    --duration 8 \
    --epochs 10 \
    --batch-size 8 \
    --save-every 5 \
    --checkpoint-dir _data/checkpoints_8s_loop

# 4. Generate samples and run autocorrelation analysis
echo ""
echo "Step 4: Autocorrelation analysis..."
python scripts/analyse_repetition.py \
    --data _data/segments_loops \
    --duration 8 \
    --checkpoint _data/checkpoints_8s_loop/epoch_0010.pt \
    --n-real 50 --n-gen 20 \
    --output _data/eval/repetition_8s_loop.json \
    --plot docs/images/m2d-autocorrelation-8s-loop.png

echo ""
echo "=== Compare ==="
echo ""
python -c "
import json
from pathlib import Path

baseline = json.loads(Path('_data/eval/repetition.json').read_text())
try:
    poc = json.loads(Path('_data/eval/repetition_8s_loop.json').read_text())
except FileNotFoundError:
    print('No 8s results found.')
    exit(1)

print(f'  Real (4s):      {baseline[\"real\"][\"mean_strength\"]:.3f}')
print(f'  Baseline (4s):  {baseline[\"generated\"][\"mean_strength\"]:.3f}')
print(f'  Real (8s loop): {poc[\"real\"][\"mean_strength\"]:.3f}')
print(f'  8s loop model:  {poc[\"generated\"][\"mean_strength\"]:.3f}')
gap_baseline = baseline['real']['mean_strength'] - baseline['generated']['mean_strength']
gap_8s = poc['real']['mean_strength'] - poc['generated']['mean_strength']
print(f'')
print(f'  Gap (4s baseline): {gap_baseline:.3f}')
print(f'  Gap (8s loop):     {gap_8s:.3f}')
if gap_8s < gap_baseline:
    print(f'  → 8s loop model is CLOSER to real. Improvement: {gap_baseline - gap_8s:.3f}')
else:
    print(f'  → No improvement. 8s loop model gap is wider.')
"
