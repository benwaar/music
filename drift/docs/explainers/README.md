# Explainers

Standalone docs that explain the concepts behind each milestone. Each one is written for someone with a C or JS/TS background who hasn't done ML before.

---

## M0 — Natural noise baseline

- [Natural Noise](natural-noise.md) — Why real-world noise has structure, what that means for diffusion models, and how it connects to the art project.

## M1 — Spectrogram dataset

- [Diffusion models](diffusion-models.md) — The forward process (add noise), the reverse process (denoise), why it works.
- [Noise schedules](noise-schedules.md) — Linear vs cosine, how the schedule affects generation quality.

## M2 — DDPM baseline

- [DDPM](ddpm.md) — The maths in plain terms: forward process, reverse process, loss function, and why 1000 steps.
  - Forward process closed-form trick (no loop needed for training)
  - U-Net with time conditioning — why 1000 steps is the paper default
  - Griffin-Lim for spectrogram → audio

## M2b — Training loss curve and quality metric

- [Training metrics](training-metrics.md) — Loss curves, mean spectral distance, and what they tell us about model convergence.
  - Why loss plateaus don't mean the model stopped improving
  - Nearest-neighbour MSD — measuring generation quality with a single number
  - C and JS/TS analogies (PID controllers, Lighthouse scores, Hamming distance)

## M2c — Real-world noise as starting point

- [Partial denoising](partial-denoising.md) — img2img for audio: how partial denoising preserves input structure.
  - Strength parameter: 0.3 (preserve input) → 1.0 (pure generation)
  - 3×3 experiment grid: road/rain/machine × 3 strengths
  - Cross-source MSD: measuring whether noise sources steer the output

## M2d — Repetition and looping

- [Repetition analysis](repetition.md) — Autocorrelation as a repetition metric, three experiments (attention, longer context, loop filtering), and why data windowing mattered more than architecture.
  - Why 4s windows can't contain a loop repeat (4-bar loop at 120 BPM = 8s)
  - Loop detection with FFT-accelerated autocorrelation (`drift/loops.py`)
  - 8s + loop filter + base_ch=64: autocorrelation gap from 0.222 → 0.029
  - Overfitting on small datasets — epoch 20 sweet spot, static by epoch 40
  - The lesson: the model can't learn what the data doesn't show

## M3 — Improved sampling (DDIM)

- [DDIM](ddim.md) — Faster sampling without retraining: deterministic reverse process, timestep subsequences, η control.
  - Why DDPM's noise is optional — SDE vs ODE formulation
  - Timestep subsequence: 50 steps instead of 1000
  - η parameter: deterministic (0) vs stochastic (1.0) — and why 1.0 wins on our model
  - Listen test: DDIM-50 η=1.0 is 23× faster *and* more consistent than DDPM-1000
  - x_0 clamping to prevent prediction overshoot at large step sizes

## M4 — Conditional generation

- [Chip types](chip-types.md) — The four sound chips in the dataset: AY, SID, SN76489, MOD/XM. Hardware constraints, sonic character, spectrogram signatures, and energy profiles.
  - Why each chip's spectrograms look different (and how to tell them apart)
  - Energy distribution table across frequency bands
  - Why unbalanced training data is fine with classifier-free guidance
  - Hardware lineage: from fixed-function oscillators to sample playback
- [Classifier-free guidance](classifier-free-guidance.md) — How dropping labels during training enables guided generation, and the trade-off between musicality and chip identity.
  - Class embedding added to time embedding — the model sees "timestep + chip type"
  - CFG dropout: 10% of labels replaced with an unconditional token during training
  - Dual forward pass at inference: amplify the chip-specific direction
  - Guidance scale sweep: 1.0 (musical, chips alike) → 7.0 (very distinct, quality drops)
  - The model learned "music" at epoch 10 before learning chip identity
- [Conditioning signals](conditioning-signals.md) — What signals can steer audio generation: chip type (implemented), tempo, energy, key, images, and text. What makes sense for drift's creative workflow.

## M5 — Real-world noise generation

Retested the `--from-noise` pipeline from M2c with the 8s conditional model (epoch 10, base_ch=64). Real-world recordings steer generation: different noise sources produce measurably different outputs. Road noise creates bass-heavy repetitive loops. Rain creates broadband varied textures. The model preserves the input's frequency profile almost perfectly (r=0.99).

Key finding: noise source dominates chip conditioning — when starting from a recording, the input texture matters more than the chip type label. Chip separation drops from 0.08 MSD (Gaussian) to 0.01–0.02 (noise starts).

- [Non-Gaussian starting points](non-gaussian-starting-points.md) — why starting from recordings instead of random noise steers the output
- [Comparison grid](images/m5-noise-strength-grid.png) — noise source × strength
- [Chip conditioning grid](images/m5-noise-chip-grid.png) — noise source × chip type

## M5 — Non-Gaussian starting points

- [Non-Gaussian starting points](non-gaussian-starting-points.md) — Why starting diffusion from real-world recordings instead of Gaussian noise steers the output, and what M5 measured.
  - Cross-source MSD 0.24–0.26: noise sources produce measurably different outputs at all strengths
  - Gaussian vs noise MSD: rain (0.85) steers most, machine (0.54) least
  - Frequency correlation 0.98–0.99: model preserves noise source frequency profile almost perfectly
  - Autocorrelation: road (0.85) → highly repetitive loops, rain (0.53) → varied textures
  - Chip conditioning weakens with noise starts (cross-chip MSD 0.01–0.02 vs 0.08 for Gaussian)

## M7 — Eyes and ears

- Shared structure *(planned)* — Why images and spectrograms are interchangeable as 2D tensors.

## M8 — Cross-feed

- Non-Gaussian starting points revisited *(planned)* — Images as diffusion seeds.

---

## Reference

- [Libraries](libraries.md) — torch.nn, librosa, tqdm, and other library functions used across M2.
- [Python concepts](python-concepts.md) — `@dataclass`, `register_buffer`, `torch.no_grad()`, and other patterns new in M2.

---

See also: [natural-noise-to-drift.md](../natural-noise-to-drift.md) — the bridge document connecting the art project to this one.
