# drift — Diffusion Chip-Tune Generator

Chip-tune generation via denoising diffusion on Mel-spectrograms.
Research project — one milestone at a time, document as you go.

## Project layout

```
_data/          # local only — not committed, reproduced via scripts
  hvsc/         # HVSC SID files
  vgm/          # VGM/VGZ files (AY, SN76489, YM2612)
  modarchive/   # MOD/XM tracker modules
_tools/         # local only — not committed, built via scripts/build_tools.sh
  bin/          # sidplayfp, vgm2wav — added to PATH by setup.sh
  src/          # cloned source repos used during build
scripts/        # data acquisition + tool builds — one script per source
drift/          # Python package — dataset, model, training
```

## Data & tools

`_data/` and `_tools/` are gitignored. To reproduce on a fresh clone:

```bash
bash scripts/setup.sh    # venv, brew deps, build tools, download data — one command
```

Or step by step:

```bash
pip install -r requirements.txt
bash scripts/build_tools.sh               # builds sidplayfp + vgm2wav into _tools/bin/
python scripts/download_hvsc.py           # HVSC update pack — ~600 SID files
python scripts/download_ay.py             # Modland AY Emul — ZX Spectrum .emul files
python scripts/download_vgm.py            # archive.org — 280 SN76489 VGM files
python scripts/download_modarchive.py     # Mod Archive — 500 MOD/XM files
```

Each script is idempotent — safe to re-run, skips already-downloaded files.

## Milestones

See [PLAN.md](PLAN.md). Study complete through M7. M0–M7 done (M7 = test example, real captures left as personal exercise). M8+ available for future work.

## CLI

```bash
python -m drift generate --chip ay --bars 8 --steps 50
python -m drift generate --from-noise road.wav --extract-melody --voice triangle
```

## Production checkpoint

`_data/checkpoints_m4_conditional/epoch_0010.pt` — 8s, base_ch=64, 4-class conditional, epoch 10.

## Key findings

- Noise source seeds generation at s=1.0 (full denoise from structured starting tensor)
- Melody extraction (peak freq → pentatonic → triangle wave) produces musical output
- The model finds contours, not finished audio — extraction + re-rendering is the creative pipeline

## Tech stack

- Python 3.11+
- PyTorch (diffusion model + U-Net)
- librosa / torchaudio (Mel-spectrograms)
- sidplayfp, vgm2wav (built from source into `_tools/bin/` via `scripts/build_tools.sh`)
- openmpt123 (chip rendering — MOD/XM → .wav, via brew libopenmpt)

## Working conventions

- No committed data. Scripts fetch everything from public sources.
- No model checkpoints in the repo. Save to `_data/checkpoints/` locally.
- One explainer doc per milestone gate (see PLAN.md).
- Tests live alongside the module they test.
- Conventional commits. AI attribution on every commit.
