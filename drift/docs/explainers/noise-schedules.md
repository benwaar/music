# Noise Schedules — Linear vs Cosine, and Why It Matters

The forward process adds noise over T steps. But how much noise at each step? That's the **noise schedule** — and getting it right makes the difference between a model that generates coherent structure and one that collapses into mush.

---

## What a noise schedule is

At each step `t`, a small amount of noise is added, controlled by `β_t` (beta). The full schedule is the sequence:

```
β_1, β_2, ..., β_T
```

Each `β_t ∈ (0, 1)` is a variance — how much Gaussian noise gets mixed in at that step. Small `β_t` means gentle noising. Large `β_t` means aggressive noising.

From `β_t`, the complementary value `α_t = 1 - β_t` gives the "how much signal survives" fraction at each individual step.

The thing that actually determines how noisy `x_t` is — relative to the original `x_0` — is the **cumulative product**:

```
ᾱ_t = α_1 × α_2 × ... × α_t = Π_{s=1}^{t} α_s
```

This is the key number. It combines all the individual steps into a single signal-to-noise ratio:

```
x_t = sqrt(ᾱ_t) * x_0 + sqrt(1 - ᾱ_t) * ε
```

When `ᾱ_t ≈ 1`, the spectrogram is almost clean. When `ᾱ_t ≈ 0`, it's pure noise.

The schedule shapes how `ᾱ_t` falls from 1 to 0 across the T steps.

---

## Linear schedule — the simple approach

The original DDPM paper (Ho et al., 2020) used a **linear schedule**: `β_t` increases linearly from a small `β_min` to a larger `β_max`.

Typical values: `β_1 = 0.0001`, `β_T = 0.02`, `T = 1000`.

```
β_t = β_min + (β_max − β_min) × (t / T)
```

The `ᾱ_t` curve drops steeply at first and then levels off.

| Step | ᾱ_t (approx) | What you see |
|------|-------------|--------------|
| t = 0 | 1.0 | Clean spectrogram |
| t = 250 (T/4) | ~0.1 | Almost all structure lost |
| t = 500 (T/2) | ~0.01 | Mostly noise |
| t = 750 (3T/4) | ~0.001 | Indistinguishable from noise |
| t = 1000 (T) | ~0.0 | Pure noise |

The problem: **most of the information is destroyed in the first quarter of the steps**. Steps 250–1000 are all working with near-pure noise, where there's almost no signal left to guide the model.

This wastes most of the model's capacity. Half the steps are spent refining noise that barely differs from step to step. The model uses expensive computation to distinguish "nearly pure noise" from "also nearly pure noise".

> **Analogy:** Imagine shredding a document — but you do all the shredding in the first few seconds and spend the remaining time just shaking the confetti.

---

## Cosine schedule — preserving information longer

Nichol & Dhariwal (2021) proposed a **cosine schedule** to fix this. Instead of specifying `β_t` directly, they define `ᾱ_t` to follow a cosine curve:

```
ᾱ_t = cos²( (t/T + s) / (1 + s) × π/2 )
```

where `s ≈ 0.008` is a small offset to prevent `β_t` from being too small near `t = 0`.

The `ᾱ_t` curve now drops smoothly and slowly at first, then falls steeply in the middle, then levels off again at the end.

| Step | ᾱ_t (approx) | What you see |
|------|-------------|--------------|
| t = 0 | 1.0 | Clean spectrogram |
| t = 250 (T/4) | ~0.85 | Lightly noisy — structure still clear |
| t = 500 (T/2) | ~0.5 | Visibly noisy — broad shapes intact |
| t = 750 (3T/4) | ~0.15 | Heavily noisy — only faint structure |
| t = 1000 (T) | ~0.0 | Pure noise |

The information is distributed more evenly across the full T steps. At the quarter mark, the spectrogram still looks like a spectrogram. At the halfway mark, you can still see broad frequency patterns.

---

## Why the schedule matters

The schedule controls **what the model spends its capacity on**.

The network is trained on `(x_t, t)` pairs sampled uniformly from `t = 1` to `T`. With a linear schedule, most of those pairs are near-pure-noise — uninformative, hard to distinguish. The model spends most of its training budget learning to distinguish "noise level 97%" from "noise level 98%", which contributes little to the final generation quality.

With a cosine schedule, the model sees more pairs where real signal is still visible. It learns to reconstruct structure at moderate noise levels — which is exactly the regime that matters most for generation quality. The steps where `ᾱ_t ≈ 0.5` are where the model makes the biggest decisions about coarse structure.

Two failure modes from a bad schedule:

- **Too aggressive** (too much noise too fast): the model never learns to preserve structure because it rarely sees training examples with intact structure. Outputs look blurry or structureless.
- **Too gentle** (too little noise overall): the model doesn't fully reach pure noise at `t = T`. Generation fails because the starting point at inference isn't the pure noise the model expects.

---

## What a spectrogram looks like at each stage

Under the cosine schedule, the destruction is gradual and interpretable:

- **t = 0**: Sharp horizontal bands (sustained notes), vertical chord stacks, clean silence gaps. Recognisable chip-tune.
- **t = T/4**: The broad frequency structure survives — bass vs treble bands still visible. Individual notes beginning to blur.
- **t = T/2**: Frequency structure is hazy but detectable. The spectrogram still looks audio-shaped — you can see regions of higher and lower energy. Individual notes gone.
- **t = 3T/4**: Almost noise. A faint bias toward the original frequency distribution might still be visible, but no structure.
- **t = T**: Pure Gaussian noise. Flat spectrum, no pattern.

Under a linear schedule, the `t = T/4` and `t = T/2` descriptions would swap — at the halfway mark, you'd already be looking at what the cosine schedule shows at `3T/4`.

---

## Practical implication for drift

Mel-spectrograms have strong frequency structure. Chip-tunes have:

- **Bass lines**: concentrated energy in the bottom frequency bins.
- **Lead melodies**: narrow bands at specific pitches.
- **Harmonic stacking**: a note and its overtones appear at predictable frequency ratios (2×, 3×, 4× the fundamental).
- **Rhythmic silence**: gaps between notes visible as dark columns.

This structure lives at multiple scales. Broad frequency bands are coarse structure; individual note onsets are fine structure.

The cosine schedule preserves coarse structure deeper into the diffusion process. At the halfway mark, the model still has frequency band information to work from. This is important for spectrograms — knowing "this is a bass-heavy piece" is a strong prior that should survive well into the noising process.

A linear schedule destroys those bands too early, forcing the model to reconstruct them from scratch at generation time. The cosine schedule keeps them alive longer, giving the reverse process a clearer target at each step.

**Default recommendation for drift**: use the cosine schedule. It's the community standard since 2021 and is particularly well-suited to structured 2D data like spectrograms.

---

## Summary

- **β_t** is the noise variance added at step `t`. The full sequence is the schedule.
- **ᾱ_t** (cumulative product) is what determines total noise level at step `t`.
- **Linear schedule**: `β_t` increases linearly. Destroys signal too fast — most steps operate on near-pure noise.
- **Cosine schedule**: `ᾱ_t` follows a cosine curve. Information preserved longer, more evenly distributed across steps.
- **Why it matters**: the schedule controls what the model trains on. Good schedule = more informative training pairs = better generation.
- **For drift**: cosine schedule preferred — chip-tune spectrograms have rich frequency structure that benefits from surviving deeper into the forward process.
