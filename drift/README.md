# drift — Diffusion Chip-Tune Generator

Generate new 8-bit chip-tunes using a denoising diffusion model operating on spectrograms.
Start from pure noise — Gaussian or real-world — and iteratively denoise into authentic chip music.

Ddrift covers **generative modelling via diffusion** — a fundamentally different approach to generation than the sequence models, RL agents, and classifiers built elsewhere.

### ML skills this teaches (not covered by other projects)

| Skill | What's new | Where it transfers |
|-------|-----------|-------------------|
| **Diffusion process** | Forward (corrupt) + reverse (denoise). Learning to undo noise. | Image generation, protein folding, any domain where you model a distribution |
| **Noise schedules** | Linear vs cosine. How the corruption rate shapes what the model learns. | Hyperparameter design for any iterative refinement process |
| **DDIM fast sampling** | Deterministic sampling, ODE connection. 1000 steps → 50 with same quality. | Inference optimisation — trading compute for quality at deploy time |
| **Classifier-free guidance** | Conditional generation without a separate classifier. Drop labels during training, scale at inference. | Any conditional generation task (text-to-image, text-to-audio, guided search) |
| **Non-Gaussian starting points** | What happens when you denoise from real-world noise instead of mathematical noise? | Extends the natural-noise art project into audio with formal diffusion theory |

### Why audio → finance

Spectrograms are 2D tensors with a time axis — structurally identical to how we'd represent financial time series (price, volume, volatility across instruments over time). The diffusion techniques learned here — denoising structured signals, conditional generation, fast sampling — transfer directly to scenario generation, synthetic market data, and anomaly detection in financial datasets. Audio is a forgiving domain to learn in: you can *hear* when the model is wrong.

---

## Training

Download the dataset first (`bash scripts/setup.sh`), then:

```bash
python -m drift.train --data _data/segments --epochs 50 --batch-size 16
```

Checkpoints are saved to `_data/checkpoints/` every 10 epochs and at the final epoch. The trainer auto-detects MPS (Apple Silicon), CUDA, or CPU.

Options:

| Flag | Default | Description |
|------|---------|-------------|
| `--data` | `_data/segments` | Path to segments directory |
| `--epochs` | 50 | Training epochs |
| `--batch-size` | 16 | Batch size |
| `--lr` | 2e-4 | Learning rate |
| `--device` | `auto` | `auto` \| `cpu` \| `cuda` \| `mps` |
| `--checkpoint-dir` | `_data/checkpoints` | Where to save checkpoints |
| `--save-every` | 10 | Save checkpoint every N epochs |

## Generation

```bash
python scripts/generate.py --checkpoint _data/checkpoints/epoch_0050.pt --n 5
```

Generates 5 Mel spectrograms, converts each to audio via Griffin-Lim, and saves `.wav` files and spectrogram images to `_data/generated/`.

## CLI (M6)

```bash
python -m drift generate [OPTIONS]
```

**Basic generation:**
```bash
python -m drift generate --chip ay --bars 8 --steps 50
python -m drift generate --chip sid --bars 16
```

**From a noise recording (M5 — real-world noise steers the output):**
```bash
python -m drift generate --from-noise road.wav --steps 50
python -m drift generate --from-noise rain.wav --chip vgm --guidance-scale 3.0
```

**With melody extraction (extracts melodic contour from noise, re-renders on a chip voice):**
```bash
python -m drift generate --from-noise road.wav --extract-melody --voice triangle
python -m drift generate --from-noise road.wav --extract-melody --voice triangle --scale minor_pentatonic
```

Each sample produces a `.wav` + `.png` spectrogram. With `--extract-melody`, also a `_melody.wav`.

**Key flags:**

| Flag | Description |
|------|-------------|
| `--chip {ay,sid,vgm,modarchive}` | Chip type conditioning |
| `--bars N` | Duration in bars (4/4 at 120 BPM) |
| `--from-noise FILE` | Use a recording as generation seed instead of Gaussian noise |
| `--strength 0.0–1.0` | Denoising strength (`1.0` recommended for noise inputs) |
| `--steps N` | DDIM steps (default 50) |
| `--guidance-scale F` | Classifier-free guidance scale |
| `--extract-melody` | Extract melodic contour and re-render on a chip voice |
| `--voice {square,triangle,pulse}` | Chip voice for melody extraction |
| `--scale {pentatonic,minor_pentatonic,major}` | Scale quantisation |
| `--n N` | Number of samples to generate |
| `--seed N` | Reproducible generation |

---

## The idea

Diffusion models learn to reverse noise. During training, you gradually corrupt real
spectrograms with Gaussian noise over many steps, then train a U-Net to predict the
noise at each step. At generation time, you start from pure static and denoise step by
step until a coherent spectrogram emerges.

### The natural noise question

Standard diffusion starts from Gaussian noise — mathematically structured randomness.
But what happens when you start from *real-world* noise? Road noise, rain, crowd hum,
machine drone — these have their own frequency structure (low rumble, harmonics, rhythmic
patterns). The diffusion model should pull chip-tune structure out of whatever frequencies
are already there — the source noise *steers* the output.

This extends a prior art project (natural noise) into audio, with the formal diffusion
framework to understand *why* it works. Different noise sources → different tunes.
Record the road → get a tune unique to that journey.


