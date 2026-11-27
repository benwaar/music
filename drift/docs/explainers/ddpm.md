# DDPM — The Maths in Plain Terms

The [diffusion models explainer](diffusion-models.md) covers the core idea: add noise forward, learn to reverse it. This document goes deeper — into the specific algorithm published in "Denoising Diffusion Probabilistic Models" (Ho et al., 2020) and how it maps to our actual code in `drift/`.

If you've read the theory and want to understand what the code is doing and why, start here.

---

## The forward process — one formula, no loop

The forward process corrupts a clean spectrogram `x_0` by adding noise. The DDPM formulation has a useful property: **you can compute the noisy version at any step `t` directly from `x_0`, without stepping through all the intermediate steps**.

The formula is:

```
x_t = sqrt(ᾱ_t) * x_0 + sqrt(1 - ᾱ_t) * ε
```

where `ε ~ N(0, I)` is pure Gaussian noise and `ᾱ_t` (alpha-bar) is the cumulative product of all the `α` values up to step `t`.

### Beta schedule — our values

The noise schedule in `drift/scheduler.py` is linear:

```python
betas = torch.linspace(1e-4, 0.02, 1000)  # β_1 to β_T
alphas = 1.0 - betas                        # α_t = 1 - β_t
alpha_cumprod = torch.cumprod(alphas, dim=0)  # ᾱ_t = Π α_s for s=1..t
```

Breaking down the chain:

| Symbol | Formula | What it means |
|--------|---------|---------------|
| `β_t` | linearly from 0.0001 to 0.02 | noise variance added at step `t` — small at first, larger later |
| `α_t` | `1 - β_t` | signal fraction surviving at step `t` alone |
| `ᾱ_t` | `α_1 × α_2 × ... × α_t` | total signal fraction surviving from step 0 to `t` |

At `t = 1`, `ᾱ_t ≈ 0.9999` — almost nothing destroyed. At `t = 1000`, `ᾱ_t ≈ 0.0` — pure noise.

The scheduler also precomputes the square-root terms it will need repeatedly:

```python
self.register_buffer("sqrt_alpha_cumprod", torch.sqrt(alpha_cumprod))
self.register_buffer("sqrt_one_minus_alpha_cumprod", torch.sqrt(1.0 - alpha_cumprod))
```

> **Coming from C:** `register_buffer` is like putting these arrays in the struct. They're not trainable parameters (no gradient) — they're constants that need to move with the model (same device, same dtype). See [python-concepts.md](python-concepts.md) for a fuller explanation.

> **Coming from JS/TS:** Think of `register_buffer` as `Object.freeze`ing a typed array that's attached to the class. It travels with the model when you call `.to(device)` but isn't part of the optimiser's parameter list.

### Calling it — one line

The closed-form forward step (`scheduler.py:41–45`):

```python
def add_noise(self, x_0, t, noise):
    sqrt_ac = self._gather(self.sqrt_alpha_cumprod, t)
    sqrt_one_minus_ac = self._gather(self.sqrt_one_minus_alpha_cumprod, t)
    return sqrt_ac * x_0 + sqrt_one_minus_ac * noise
```

`_gather` indexes the precomputed table by `t` and reshapes to `(B, 1, 1, 1)` so it broadcasts correctly against the `(B, 1, H, W)` spectrogram tensor.

> **Coming from C:** Broadcasting means "expand dimensions automatically so shapes align". `sqrt_ac` has shape `(B, 1, 1, 1)` and `x_0` has shape `(B, 1, 128, 176)`. The multiply broadcasts `sqrt_ac` across the H and W dimensions — no manual loop or memcpy.

---

## The reverse process — predict noise, compute mean, add variance

The forward process is fixed math. The reverse process is learned.

At each step, a trained network predicts the noise that was added, and the scheduler computes a step backward:

### Mean formula

Given the noisy spectrogram `x_t` at step `t`, the predicted mean for `x_{t-1}` is:

```
μ_θ(x_t, t) = (1 / sqrt(α_t)) * (x_t - β_t / sqrt(1 - ᾱ_t) * ε_θ(x_t, t))
```

In code (`scheduler.py:58–62`):

```python
sqrt_recip_alpha = self._gather(self.sqrt_recip_alpha, t_tensor)
betas = self._gather(self.betas, t_tensor)
sqrt_omc = self._gather(self.sqrt_one_minus_alpha_cumprod, t_tensor)

mean = sqrt_recip_alpha * (x_t - betas / sqrt_omc * noise_pred)
```

Read it as: "un-scale the noise the network predicted, subtract it from `x_t`, scale back up".

### Variance

The posterior variance is:

```
σ²_t = β_t × (1 - ᾱ_{t-1}) / (1 - ᾱ_t)
```

Precomputed in the scheduler constructor:

```python
alpha_cumprod_prev = torch.cat([torch.ones(1), alpha_cumprod[:-1]])
posterior_variance = betas * (1.0 - alpha_cumprod_prev) / (1.0 - alpha_cumprod)
```

`alpha_cumprod_prev` is `ᾱ_{t-1}` — the cumulative product *one step earlier*. The `cat` prepends a `1.0` so that at `t=0`, `ᾱ_{t-1} = 1.0` (convention: no noise before the process starts).

### No noise on the final step

At `t = 0`, we're reconstructing the clean spectrogram. Adding variance noise here would corrupt the final output. The code masks it out (`scheduler.py:65–68`):

```python
is_final = (t_tensor == 0).reshape(-1, 1, 1, 1).float()
var = self._gather(self.posterior_variance, t_tensor)
noise = torch.randn_like(x_t)
return mean + (1.0 - is_final) * torch.sqrt(var) * noise
```

When `t = 0`, `is_final = 1.0`, so `(1 - is_final) = 0.0` — the noise term vanishes.

> **Coming from C:** This is a branchless mask instead of an `if` statement. Both approaches work; the mask is friendlier to GPU execution because it avoids divergent branches across a batch.

---

## Training — the simple loop

Training is elegant: for each batch, sample a random timestep, corrupt the spectrogram to that step in one shot, ask the network to predict the noise, compute MSE loss.

The key insight is that the closed-form forward process means **no inner loop**. You don't step through `t-1` intermediate states — you jump straight to `x_t` from `x_0`.

From `train.py:108–145`:

```python
def train_step(model, scheduler, batch, device):
    specs, _labels = batch
    specs = specs.to(device)
    specs = pad_to_target(specs, TARGET_WIDTH)   # 173 → 176

    t = scheduler.sample_timesteps(batch_size).to(device)  # random t per sample
    noise = torch.randn_like(specs)                         # ε ~ N(0, I)

    noisy = scheduler.add_noise(specs, t, noise)  # x_t in one step
    noise_pred = model(noisy, t)                  # ε_θ(x_t, t)

    return F.mse_loss(noise_pred, noise)          # MSE(predicted ε, actual ε)
```

Five lines of logic. The training target is the noise itself — not the clean spectrogram, not a latent encoding. Just: "what noise did we add?"

The outer loop wraps this with `loss.backward()` and `optimiser.step()`:

```python
for batch in batch_bar:
    loss = train_step(model, scheduler, batch, device)
    optimiser.zero_grad()
    loss.backward()
    optimiser.step()
    ema.update(model)
```

> **Coming from C:** `loss.backward()` is PyTorch's automatic differentiation — it walks the computation graph backward from the scalar loss and accumulates gradients into each parameter's `.grad` field. `optimiser.step()` then applies the gradient updates. `optimiser.zero_grad()` clears the accumulated gradients before the next batch (they accumulate by default — a footgun).

---

## The U-Net backbone

The model predicts noise — a tensor of the same shape as the input. U-Nets are standard for this because their skip connections preserve spatial detail at every resolution.

### Why U-Net

A plain encoder-decoder compresses to a bottleneck and then expands. Information lost in compression can't come back. Skip connections short-circuit that: they copy the encoder output at each scale and concatenate it with the decoder at the matching scale. Fine detail from the encoder is available to the decoder without having to reconstruct it.

For spectrograms, this matters: fine-grained pitch and rhythm structure that gets compressed in the bottleneck can still flow through the skip path.

### Time conditioning

The model needs to know `t` — how noisy the input is. Without it, the same network would be trying to predict noise at `t = 1` (barely noisy) and `t = 999` (almost pure noise) identically. That's impossible.

Time conditioning is via sinusoidal embeddings (`unet.py:12–18`):

```python
def sinusoidal_embedding(t, dim):
    half = dim // 2
    freqs = torch.exp(-math.log(10000) * torch.arange(half) / (half - 1))
    args = t[:, None].float() * freqs[None]
    return torch.cat([args.sin(), args.cos()], dim=-1)
```

This is identical to the positional encoding used in Transformer models. Each timestep `t` maps to a unique fixed vector of sines and cosines. The MLP in `TimeEmbed` then projects it into the model's embedding dimension.

Each ResBlock injects the time embedding into its intermediate activations (`unet.py:48`):

```python
h = h + self.time_proj(F.silu(t_emb))[:, :, None, None]
```

The `[:, :, None, None]` reshapes the time vector from `(B, C)` to `(B, C, 1, 1)` so it broadcasts over the spatial dimensions — every position in the feature map receives the same time signal.

> **Coming from JS/TS:** The `[:, :, None, None]` syntax is NumPy/PyTorch's way of inserting new axes. Equivalent to `.reshape(B, C, 1, 1)` but more idiomatic when the batch and channel dims are already in place.

### Architecture summary

Our U-Net (`unet.py:96–177`):

```
Input: (B, 1, 128, 176) — one-channel spectrogram

input_conv → (B, 32, 128, 176)

Down stage 0: 2× ResBlock(32→32) → Downsample → (B, 32, 64, 88)
Down stage 1: 2× ResBlock(32→64) → Downsample → (B, 64, 32, 44)
Down stage 2: 2× ResBlock(64→128) → Downsample → (B, 128, 16, 22)

Bottleneck: ResBlock → SelfAttention → ResBlock at (B, 128, 16, 22)

Up stage 2: Upsample + skip-cat → 2× ResBlock(256→128) → (B, 128, 32, 44)
Up stage 1: Upsample + skip-cat → 2× ResBlock(192→64) → (B, 64, 64, 88)
Up stage 0: Upsample + skip-cat → 2× ResBlock(96→32) → (B, 32, 128, 176)

out_norm → out_conv → (B, 1, 128, 176) — predicted noise
```

Self-attention lives only at the bottleneck (`16 × 22 = 352` positions). Attention at full resolution would be `128 × 176 = 22,528` positions — quadratic in sequence length, expensive. At the bottleneck it's tractable and handles global structure: relationships between distant frequency bands.

The skip concatenations double the channel count at each up stage — that's why the first ResBlock in each up stage takes `2×` channels (`ch[2]*2`, `ch[2]+ch[1]`, `ch[1]+ch[0]`).

### Parameter count — why small matters

With `base_ch = 32`, the model has approximately **1.5M parameters**. This is intentional:

- Small enough to train for several epochs on a laptop CPU in a reasonable time.
- Large enough to learn basic spectrogram structure.
- Easy to reason about: every layer fits in your head.

The research principle here: understand a small model deeply before scaling. A 1.5M parameter model that generates recognisable pitch structure is more educational than a 100M parameter model that you run once and treat as a black box.

---

## Why 1000 steps

The DDPM paper uses T = 1000. This is a quality/speed tradeoff.

**More steps → better quality** — each denoising step removes only a tiny amount of noise. Small steps mean each individual prediction task is easy: the model only has to distinguish "noise level 52.3%" from "noise level 52.1%". The accumulated corrections sum to a coherent output.

**Fewer steps → faster, but harder** — with 100 steps, each step must handle 10× more denoising. The model's predictions need to be more accurate at each step, or errors accumulate. Quality drops.

**1000 is the DDPM paper's baseline** — it's a known good starting point with well-understood training dynamics. The loss curves are stable, the schedule is calibrated for it, and the prior art provides comparison points.

The cost: 1000 forward passes through the U-Net at generation time. For a 1.5M parameter model on CPU, that's slow — roughly 5–10 minutes per sample. For training, this doesn't matter (training only needs one forward pass per batch, not 1000 reverse steps).

M3 will address this with DDIM (Song et al., 2020): a deterministic variant that achieves the same generation quality in ~50 steps by reformulating the reverse process as an ODE. Same trained model, different sampler — no retraining required.

---

## Griffin-Lim — spectrograms back to audio

The model generates **Mel spectrograms**, not audio. To hear the output, the spectrogram must be inverted to a waveform.

### The phase problem

A Mel spectrogram discards phase. It captures *how much energy* is at each frequency at each time, but not *where in the cycle* those frequencies are. Phase information is needed to reconstruct a waveform from a spectrum.

Griffin-Lim (Griffin & Lim, 1984) solves this iteratively. Starting from a random phase estimate, it:

1. Computes a waveform from the magnitude + phase guess.
2. Takes the STFT of that waveform to get a new (complex) spectrum.
3. Replaces the magnitude with the target magnitude (from the model output), keeps the new phase estimate.
4. Repeats.

After `n_iter` iterations (we use 64), the phase estimate converges and the waveform is consistent with the target magnitude spectrum.

From `vocoder.py:25–40`:

```python
def mel_to_audio(spec_db, sr, n_fft, hop_length, n_mels, n_iter=64):
    s_power = librosa.db_to_power(spec_db)          # dB → linear power
    s_linear = librosa.feature.inverse.mel_to_stft(  # Mel → STFT magnitude
        s_power, sr=sr, n_fft=n_fft
    )
    waveform = librosa.griffinlim(
        s_linear, n_iter=n_iter, hop_length=hop_length, n_fft=n_fft
    )
    return waveform.astype(np.float32)
```

### Quality — good enough for a listen test

Griffin-Lim produces audio that is audible and structurally correct, but not clean. Artefacts are common: a slight metallic quality, smearing of transients, occasional phase noise.

For M2, this is fine. The goal is to determine whether the model has learned anything useful — does the output have pitch structure? Rhythmic patterns? Or just filtered noise? Griffin-Lim is good enough to answer those questions.

Better alternatives exist: WaveGlow and HiFi-GAN are neural vocoders trained to predict phase from magnitude. They produce significantly higher quality audio. M5 may revisit this — for now, Griffin-Lim lets us hear the model without adding another trained component to the stack.

> **Why not just train on waveforms directly?** Waveforms are 1D signals at 22,050 samples/second — a 4-second clip is 88,200 samples. That's a very long sequence for a model to generate coherently. Spectrograms compress time: a 4-second clip is 173 frames × 128 frequency bins. All the image-based techniques (U-Net, attention, diffusion) work naturally on that 2D grid. Waveform generation is a different and harder problem.

---

## Summary

| Piece | What it does | File |
|-------|-------------|------|
| `DDPMScheduler` | Precomputes schedule tables; `add_noise` → forward process; `step` → one reverse step | `drift/scheduler.py` |
| `UNet` | Predicts noise from noisy spectrogram + timestep | `drift/unet.py` |
| `train_step` | One training iteration: sample `t`, corrupt `x_0`, predict noise, MSE loss | `drift/train.py` |
| `generate` | 1000-step reverse loop: start from Gaussian noise, step to `x_0` | `drift/sampler.py` |
| `mel_to_audio` | Griffin-Lim: Mel spectrogram → waveform | `drift/vocoder.py` |

- **Forward process**: closed-form, no loop, one line. `add_noise(x_0, t, ε)` → `x_t`.
- **Reverse process**: 1000 steps of predict-noise, compute-mean, add-variance. No noise at `t = 0`.
- **Training target**: the noise itself (`ε`). MSE between predicted and actual.
- **U-Net**: skip connections preserve spatial detail; time embedding conditions every layer on `t`.
- **1000 steps**: DDPM default — good quality, slow generation. M3 will fix the speed with DDIM.
- **Griffin-Lim**: iterative phase estimation. Audible, not clean. Good enough to hear what the model learned.
