# Partial Denoising — img2img for Audio

How do you make a diffusion model transform a recording instead of generating from scratch? The same way Stable Diffusion does img2img: start partway through the denoising process.

## The idea

Normal generation starts from pure Gaussian noise (timestep 1000) and denoises all the way to timestep 0. The model decides everything — structure, rhythm, frequency content.

Partial denoising starts from a real recording:

1. Convert the recording to a Mel-spectrogram
2. Add diffusion noise up to timestep `t = strength × 1000`
3. Denoise from `t` back to 0

At **strength 0.3**, we add noise to step 300 — 70% of the input's structure survives. The model fills in details but keeps the recording's character.

At **strength 0.7**, we add noise to step 700 — the model takes over most of the output, with only faint traces of the input.

```python
# In the sampler: add noise to the input, then denoise from there
start_step = int(strength * scheduler.num_steps)
t = torch.full((n_samples,), start_step - 1, device=device, dtype=torch.long)
noise = torch.randn_like(x_0)
x = scheduler.add_noise(x_0, t, noise)

for t in range(start_step - 1, -1, -1):
    noise_pred = model(x, t_batch)
    x = scheduler.step(x, t_batch, noise_pred)
```

### Coming from C

Think of it like a lossy compression chain. At strength 0.3, you're compressing the input at a low ratio — most of the original data survives. At strength 1.0, you've compressed it to nothing (random noise) and the decompressor (model) reconstructs from scratch. The "quality" parameter is how many bits of the original you keep.

### Coming from JS/TS

Think of it like CSS transforms applied in sequence. At strength 0.3, you're applying a mild blur then sharpening — the original layout is recognisable. At strength 1.0, you've blurred it to a uniform grey and the sharpening step creates a new image from the model's training data.

## The experiment

We tested 3 real-world noise sources (road, rain, machine) at 3 strength levels (0.3, 0.5, 0.7):

![Strength grid](../images/m2c-strength-grid.png)

**What the spectrograms show:**

- **Road (s=0.3)**: concentrated low-frequency energy — the road's bass rumble is preserved
- **Rain (s=0.3)**: bright broadband energy across high frequencies — rain's white-noise character shows through
- **Machine (s=0.3)**: vertical banding — the rhythmic pulse of the machine survives
- **All sources (s=0.7)**: outputs converge — the model dominates, noise source barely visible

## Measuring steering

We measured cross-source distance: how different are the outputs when you change the noise source but keep the strength fixed?

| Strength | road–rain | road–machine | rain–machine | Average |
|----------|-----------|-------------|-------------|---------|
| 0.3      | 0.156     | 0.149       | 0.203       | 0.170   |
| 0.5      | 0.131     | 0.142       | 0.177       | 0.150   |
| 0.7      | 0.186     | 0.216       | 0.222       | 0.208   |

The distances are small but non-zero at all strengths. Rain-vs-machine is consistently the largest gap — they have the most different frequency profiles (broadband white noise vs rhythmic low-frequency hum).

**Strength 0.7 shows the highest divergence** — somewhat counterintuitive. At low strength (0.3), the model barely transforms the input, so outputs are close to their respective inputs and thus different. At medium strength (0.5), the model starts homogenising. At high strength (0.7), the random noise added at step 700 amplifies small differences in the surviving input structure.

## What this means for the project

For the GO/NO-GO gate:

- **Criterion #4** (noise source audibly steers the output): **Partially met.** The spectrograms show visible differences. The listen test is the real arbiter — the MSD differences are small (~0.15–0.21) relative to the overall spectrogram range.

The technique works mechanically. Whether the steering is *audible* depends on the listener and the audio quality — which M2a showed is limited by the small model, not the vocoder.

## Running the experiment

```bash
# Full grid (3 sources × 3 strengths × 2 samples each)
python scripts/experiment_m2c.py

# Single test at a specific strength
python scripts/generate.py \
    --checkpoint _data/checkpoints/epoch_0050.pt \
    --from-noise _data/noise/rain.wav \
    --strength 0.5 \
    --n 3
```
