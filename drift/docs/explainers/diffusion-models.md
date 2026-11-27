# Diffusion Models — Forward Noise, Reverse Denoising, Why It Works

A diffusion model is a generative model built on a simple idea: if you know how to add noise, you can learn to remove it. Train a network to undo noising, and you get a generator for free.

---

## The forward process — destroying data

Start with a clean Mel-spectrogram `x_0` — a real chip-tune. Over `T` steps, gradually add Gaussian noise until nothing of the original survives.

At step `t`, the noisy version is:

```
x_t = sqrt(α_t) * x_0 + sqrt(1 - α_t) * ε
```

Breaking that down:

| Term | What it is |
|------|-----------|
| `x_0` | The original clean spectrogram |
| `x_t` | The noisy version at step `t` |
| `α_t` | How much of the original survives (starts near 1, decays toward 0) |
| `ε` | A sample of pure Gaussian noise |
| `sqrt(α_t)` | The signal weight — fades as `t` increases |
| `sqrt(1 - α_t)` | The noise weight — grows as `t` increases |

At `t = 0`, `α_0 ≈ 1` — you have the clean original.
At `t = T`, `α_T ≈ 0` — pure noise, the original is gone.

In between, it's a weighted blend: mostly signal early, mostly noise late.

This is the **forward process**. It's not learned — it's a fixed mathematical recipe. You can compute any `x_t` directly from `x_0` without stepping through all the intermediate steps.

Think of it like slowly dissolving a photograph in acid. At first you can still see the image. Midway through, shapes are still visible. By the end, there's nothing left.

---

## The reverse process — learning to denoise

The forward process destroys data. The reverse process reconstructs it.

A neural network `ε_θ` is trained to predict the noise `ε` that was added to get from `x_0` to `x_t`. Given a noisy spectrogram and the timestep `t`, the network guesses what the noise looked like.

The reverse step is then:

```
x_{t-1} ≈ x_t − (some fraction) * ε_θ(x_t, t)
```

Subtract the predicted noise, get a slightly cleaner version. Repeat T times. Arrive at `x_0`.

The network doesn't reconstruct the whole image at once — it just removes a little noise each step. Each step is a small, manageable prediction task.

> **Analogy:** Imagine unblurring a photo one layer at a time. Each pass removes a bit more blur. No single pass has to solve the whole puzzle — it just has to make things slightly clearer. By step T, the accumulation of small corrections has recovered the original.

---

## Training — what the model learns

Training is straightforward:

1. Take a clean spectrogram `x_0` from the dataset.
2. Sample a random timestep `t` and a noise sample `ε`.
3. Compute `x_t` (the forward formula above — one step, no loop needed).
4. Ask the network to predict `ε` from `x_t` and `t`.
5. Minimise the mean squared error between predicted and actual noise.

```
Loss = MSE(ε_θ(x_t, t), ε)
```

That's it. The model learns: *given a noisy spectrogram at timestep t, what noise was added?*

No adversarial training (unlike GANs). No complex encoder-decoder loss (unlike VAEs). Just regression — predict the noise.

---

## Generation — starting from nothing

Once trained, generation works in reverse:

1. Sample `x_T` from pure Gaussian noise (no data, just randomness).
2. Run the reverse process: at each step `t = T, T-1, ..., 1`, predict and subtract the noise.
3. At `t = 0`, the result is a generated spectrogram.

The model has never seen this particular noise sample before. But it's learned the general shape of "what chip-tune spectrograms look like", so it guides any starting noise toward something plausible.

---

## Why this works

The key insight is **decomposition**. A diffusion model never has to generate an entire coherent image in one shot — that's an extremely hard problem. Instead, it only has to answer: *"given this slightly noisy image, what small correction gets it closer to real?"*

Each denoising step is a local, tractable task. The model sees the whole noisy image and makes a small nudge. Over T steps, those small nudges accumulate into a full generation.

Compare this to:

- **GANs**: generator must produce a full image in one forward pass, competing against a discriminator. Training is unstable.
- **VAEs**: encoder compresses data into a latent space; decoder reconstructs it. The compression is lossy — blurry outputs.
- **Diffusion**: no compression, no adversarial game. Just many small denoising steps. Each step is easy; the composition of steps is powerful.

Another reason it works: the network sees `t` as an input, so it knows how noisy the image is. At high `t` (very noisy), it makes coarse corrections — getting the broad structure right. At low `t` (almost clean), it refines fine details. The same network handles all noise levels, just conditioned on `t`.

---

## Spectrograms as images — our use case

In drift, we're treating Mel-spectrograms as greyscale images.

A 128 × 256 spectrogram — 128 frequency bins, 256 time steps — is a 2D tensor of the same shape as a small image. The diffusion model has no idea it's looking at audio. It sees a grid of intensity values and learns to denoise it.

This is the payoff of the Mel-spectrogram representation: we get to use all the image-based techniques (U-Net backbones, attention, diffusion) directly on audio, without any audio-specific architecture.

The model will learn:

- Spectrograms have **horizontal structure** (notes held over time → bright bands).
- Spectrograms have **vertical structure** (chords → multiple bright bins at the same time step).
- Spectrograms have **harmonic structure** (a note plus its overtones appear at predictable frequency ratios).

None of this is explicitly programmed. It falls out of training on real chip-tune spectrograms.

---

## Summary

- **Forward process**: add Gaussian noise over T steps. Fixed formula. No learning.
- **Reverse process**: a neural network predicts and removes noise, one step at a time.
- **Training**: minimise MSE between predicted and actual noise. Simple regression.
- **Generation**: start from pure noise, run the reverse process T times.
- **Why it works**: small denoising steps are tractable; their accumulation generates coherent structure.
- **In drift**: spectrograms are treated as greyscale images. The model learns chip-tune structure from data.
