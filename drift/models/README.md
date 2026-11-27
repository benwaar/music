# Drift Model Checkpoints

Production checkpoint for the M4 conditional diffusion model.

## Files

| File | Model | Size | What it does |
|------|-------|------|-------------|
| `m4_conditional_epoch10.pt` | M4 conditional DDPM | 182 MB | 4-class chip-type conditional generation (SID, AY, SN76489, MOD) |

## Usage

```python
import torch
from drift.unet import UNet
from drift.sampler import DDIMSampler

checkpoint = torch.load("drift/models/m4_conditional_epoch10.pt", map_location="cpu")
```

## Restoring from GitHub release

If this file is not present (e.g. after a fresh clone), restore it:

```bash
bash drift/models/restore.sh
```

## Training from scratch

If you prefer to retrain (~18 hours on Apple Silicon MPS):

```bash
bash drift/scripts/setup.sh
bash drift/scripts/train_m4_conditional.sh
```
