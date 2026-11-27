# Libraries — M2 Reference

Functions and modules introduced in M2. Each entry explains what it does and shows the one-liner from our code. For deeper context on the Python patterns surrounding these, see [python-concepts.md](python-concepts.md).

---

## torch.nn modules

### GroupNorm

Normalises activations within groups of channels. A middle ground between BatchNorm (normalises across the batch) and LayerNorm (normalises across all features).

```python
self.norm1 = nn.GroupNorm(8, in_ch)  # 8 groups, in_ch channels — unet.py:39
```

**Why not BatchNorm?** BatchNorm depends on batch statistics, which become unreliable at small batch sizes (batch size 1 breaks it completely). GroupNorm is batch-size-independent — it computes stats within channel groups for each sample independently.

**Why not LayerNorm?** LayerNorm over a 2D feature map treats all spatial positions and channels equally, which discards useful channel-structure. GroupNorm preserves channel grouping, which aligns with how convolutional features work.

---

### SiLU

Sigmoid Linear Unit: `SiLU(x) = x * sigmoid(x)`. A smooth activation function.

```python
nn.SiLU()  # used in TimeEmbed.mlp — unet.py:26
```

Also callable as a function (`F.silu`), used when there's no learnable state to store:

```python
h = self.conv1(F.silu(self.norm1(x)))  # unet.py:47
```

**vs ReLU:** ReLU is `max(0, x)` — simple and cheap but has a "dead neuron" problem (gradient is zero for all negative inputs). SiLU is smooth everywhere, which tends to train better for deeper networks. The difference is small for simple models; it's become the community default for diffusion model residual blocks.

---

### Conv2d

2D convolution — applies a learned filter across spatial dimensions.

```python
self.conv1 = nn.Conv2d(in_ch, out_ch, 3, padding=1)  # unet.py:41
```

Arguments: `(in_channels, out_channels, kernel_size, padding)`. `padding=1` with `kernel_size=3` preserves spatial dimensions (same-padding).

For downsampling we use stride instead of a pooling layer:

```python
self.conv = nn.Conv2d(ch, ch, 3, stride=2, padding=1)  # unet.py:81
```

Strided conv is learnable — the model can decide what to discard during downsampling rather than using a fixed pooling rule.

---

### Linear

Fully connected layer: `y = xW^T + b`.

```python
self.time_proj = nn.Linear(time_dim, out_ch)  # unet.py:42
```

Used here to project the time embedding vector (1D, size `time_dim`) into the channel dimension of the current ResBlock so it can be broadcast across the spatial map.

---

### ModuleList

A list of `nn.Module` instances that PyTorch tracks for parameter registration.

```python
self.down0 = nn.ModuleList([ResBlock(...), ResBlock(...)])  # unet.py:108
```

**Why not a plain Python list?** PyTorch's parameter tracking only follows attributes assigned directly or placed in `nn.Module` containers (`ModuleList`, `ModuleDict`, `Sequential`). A plain Python list would make those submodules invisible to `model.parameters()` — they'd never get gradients.

> **Coming from C:** Think of `ModuleList` as a tagged union array where the tag ensures the runtime knows to recurse into each element during gradient computation.

> **Coming from JS/TS:** It's like registering child components in a framework so the parent's lifecycle hooks propagate down. A plain `Array` wouldn't trigger that propagation.

---

## torch.nn.functional

### F.pad

Zero-pads a tensor along specified dimensions.

```python
return F.pad(x, (0, pad_amount))  # train.py:46
```

Pad spec is `(left, right)` for the last dimension, `(left, right, top, bottom)` for the last two, and so on — **dimensions are specified last-first**. `(0, pad_amount)` means: no padding on the left, `pad_amount` on the right of the last dimension.

> **Coming from C:** Equivalent to `memmove` + zero-fill — shift the data left, fill the gap on the right. The tensor is a new allocation; the original is unchanged.

> **Coming from JS/TS:** Opposite of CSS padding order (TRBL). `F.pad` starts from the innermost dimension. `(0, 3)` pads the last dim. `(0, 3, 0, 2)` pads last dim then second-to-last.

---

### F.mse_loss

Mean squared error: `mean((predicted - target)²)`.

```python
return F.mse_loss(noise_pred, noise)  # train.py:145
```

The training objective for DDPM: minimise the difference between the noise the model predicted and the actual Gaussian noise added in the forward process.

---

### F.silu

Functional (stateless) version of SiLU. Use when you don't need to store it as a module attribute:

```python
h = self.conv1(F.silu(self.norm1(x)))  # unet.py:47
```

---

### F.interpolate

Resizes a tensor using a specified interpolation mode.

```python
return self.conv(F.interpolate(x, scale_factor=2, mode="nearest"))  # unet.py:93
```

`scale_factor=2` doubles the spatial dimensions. `mode="nearest"` copies the value of the nearest pixel — fast and no blending artefacts. The convolution following it smooths out the blockiness.

**Why not transposed convolution?** Transposed conv (sometimes called "deconv") is learnable but can produce checkerboard artefacts. Nearest-neighbour upsample + conv is a common alternative that avoids them.

---

### F.scaled_dot_product_attention

Computes attention efficiently: `softmax(QK^T / sqrt(d)) V`.

```python
out = F.scaled_dot_product_attention(q, k, v)  # unet.py:69
```

Available from PyTorch 2.0. Uses FlashAttention under the hood when available — faster and more memory-efficient than the manual implementation. The code falls back to manual attention for older PyTorch versions:

```python
if hasattr(F, "scaled_dot_product_attention"):
    out = F.scaled_dot_product_attention(q, k, v)
else:
    scale = q.shape[-1] ** -0.5
    attn = torch.softmax((q @ k.transpose(-2, -1)) * scale, dim=-1)
    out = attn @ v
```

---

## torch.optim

### Adam

Adaptive gradient descent optimiser. Maintains per-parameter learning rate estimates based on first and second moment history.

```python
optimiser = torch.optim.Adam(model.parameters(), lr=2e-4)  # train.py:202
```

`lr=2e-4` (0.0002) is the learning rate from the DDPM paper — a well-tested default for diffusion model training.

**Why Adam over plain SGD?** SGD with momentum works well but is sensitive to learning rate tuning. Adam's per-parameter adaptation handles the varying gradient scales across different layers (early layers see small gradients from backpropagation; the output layer sees larger ones). Less tuning needed to get training started.

---

## tqdm

### tqdm progress bars

Wraps any iterable and prints a live progress bar.

```python
batch_bar = tqdm(loader, desc=f"Epoch {epoch}/{config.epochs}", leave=False)
# train.py:212
```

`desc` sets the label. `leave=False` clears the bar when the epoch completes (so completed epochs don't stack up). `set_postfix` updates the right-side annotation:

```python
batch_bar.set_postfix(loss=f"{loss.item():.4f}")
```

For the sampling loop, steps are counted rather than batches:

```python
for t in tqdm(range(scheduler.num_steps - 1, -1, -1), desc="Sampling"):
# sampler.py:36
```

---

## librosa

### librosa.db_to_power

Converts decibels back to linear power: `power = 10^(db / 10)`.

```python
s_power = librosa.db_to_power(spec_db)  # vocoder.py:33
```

The dataset stores spectrograms in dB (human-perceptual scale). Griffin-Lim works on power (linear) values. This converts between them.

---

### librosa.griffinlim

Iterative phase estimation from a magnitude spectrogram.

```python
waveform = librosa.griffinlim(
    s_linear, n_iter=64, hop_length=hop_length, n_fft=n_fft
)  # vocoder.py:37–39
```

`n_iter=64` runs 64 forward-backward passes to converge the phase estimate. More iterations = cleaner audio, slower conversion. 64 is a reasonable tradeoff for a listen test.

---

### librosa.feature.inverse.mel_to_stft

Inverts the Mel filterbank to recover a linear-frequency STFT magnitude.

```python
s_linear = librosa.feature.inverse.mel_to_stft(
    s_power, sr=sr, n_fft=n_fft
)  # vocoder.py:34–36
```

The Mel scale is perceptual — it compresses high frequencies. The U-Net outputs a Mel spectrogram. This step converts it back to a linear-frequency magnitude spectrum that STFT operations expect. It uses a pseudo-inverse of the Mel filterbank matrix — not exact, but a good approximation.

---

## matplotlib

### imshow

Displays a 2D array as an image.

```python
plt.imshow(spec[0, 0].cpu().numpy(), origin="lower", aspect="auto")
# scripts/generate.py
```

`origin="lower"` flips the y-axis so low frequencies are at the bottom (natural for spectrograms). `aspect="auto"` lets matplotlib stretch the image to fill the axes rather than enforcing square pixels.

---

### savefig

Saves the current figure to disk.

```python
plt.savefig(img_path, dpi=150, bbox_inches="tight")
# scripts/generate.py
```

`bbox_inches="tight"` removes excess whitespace around the figure. `dpi=150` gives a reasonably sharp PNG without being massive.

---

## M2b additions

### torch.no_grad (evaluation context)

Disables gradient tracking for forward-only evaluation. Used in `evaluate_loss.py` to compute loss across checkpoints without building the computation graph.

```python
with torch.no_grad():
    loss = train_step(model, scheduler, batch, device)
# scripts/evaluate_loss.py — forward pass only, no backprop
```

**Why it matters:** Without this, PyTorch still builds the gradient graph for every forward pass, consuming ~2× the memory and taking longer. For evaluation we never call `.backward()`, so the graph is wasted.

---

### matplotlib.pyplot.annotate

Adds text annotations with arrows pointing to specific data points.

```python
ax.annotate(
    f"Improved {pct:.1f}%",
    xy=(epochs[-1], msd[-1]),           # arrow target
    xytext=(-100, 30),                  # text offset (points)
    textcoords="offset points",
    arrowprops={"arrowstyle": "->"},
)
# scripts/evaluate_quality.py — labels the improvement on the quality curve
```

`textcoords="offset points"` means the text position is relative to the data point, in display units (not data units). Keeps annotations readable regardless of axis scale.

---

## M3 additions

### torch.Tensor.clamp

Restricts tensor values to a range. Used in DDIM to prevent x_0 predictions from overshooting.

```python
x_0_pred = x_0_pred.clamp(-3.0, 3.0)  # scheduler.py:149
```

With large step sizes, the predicted clean image can have extreme values (±10 or more) that compound through subsequent steps. Clamping to ±3.0 (roughly 3 standard deviations of the training data range) keeps the denoising process stable without losing meaningful signal.

> **Coming from C:** Same as `fmin(fmax(x, -3.0), 3.0)` but applied element-wise across the entire tensor. In-place variant `.clamp_()` exists but the non-in-place version is preferred here for clarity.

> **Coming from JS/TS:** `Math.min(Math.max(x, -3), 3)` — but vectorised. No loop, no map.

---

### torch.Tensor.flip

Reverses a tensor along a dimension.

```python
timesteps = timesteps.flip(0)  # scheduler.py:103
```

The DDIM timestep subsequence is computed in ascending order `[19, 39, ..., 999]` then flipped to descending `[999, ..., 39, 19]` for the reverse process. `.flip(0)` reverses along dimension 0 (the only dimension for a 1D tensor).

---

### torch.zeros_like

Creates a tensor of zeros with the same shape, dtype, and device as the input.

```python
noise = torch.randn_like(x_t) if self.eta > 0.0 else torch.zeros_like(x_t)
# scheduler.py:157
```

When η = 0, DDIM is deterministic — no noise should be added. `torch.zeros_like` provides a zero tensor that multiplies out cleanly in the formula. This avoids a branch in the arithmetic (`sigma * 0 = 0` regardless of other terms).

---

## M5 additions

### numpy.corrcoef

Computes the Pearson correlation coefficient matrix between two or more 1D arrays.

```python
correlation = float(np.corrcoef(input_energy, output_energy)[0, 1])
# scripts/analyse_m5.py — frequency profile correlation between input noise and generated output
```

`np.corrcoef(a, b)` returns a 2×2 matrix; `[0, 1]` picks the off-diagonal element — the correlation between `a` and `b`. A value near 1.0 means the two arrays have the same shape (even if their scales differ).

Used in M5 to measure how well the model preserves the input noise's frequency profile. Result: r≈0.99 — the output tracks the input's energy distribution almost perfectly, explaining why noise source dominates chip conditioning.

> **Coming from C:** Equivalent to computing `cov(a,b) / (std(a) * std(b))` element-by-element. The matrix form handles multiple inputs at once.

> **Coming from JS/TS:** No stdlib equivalent. Think of it as a similarity score between two arrays normalised to the range [-1, 1]. 1.0 = identical shape, 0 = unrelated, -1 = inverse.

---

## M4 additions

### nn.Embedding

A lookup table mapping integer indices to dense vectors.

```python
self.class_emb = nn.Embedding(num_classes + 1, t_dim)  # unet.py:124
```

`num_classes + 1` entries: one per chip type (AY=0, SID=1, VGM=2, modarchive=3) plus an unconditional token (index 4) used during classifier-free guidance. Each entry is a learnable vector of size `t_dim`.

At forward time, the index selects a row from the table:

```python
t_emb = t_emb + self.class_emb(class_label)  # unet.py:166
```

The class embedding is added to the time embedding, so every layer in the U-Net sees both "what timestep" and "what chip type."

> **Coming from C:** It's an array of float vectors indexed by an integer. `class_emb[3]` returns the 4th row. The difference is that the contents are learnable parameters — gradient descent adjusts them during training.

> **Coming from JS/TS:** Think of it as a `Map<number, Float32Array>` where the values are updated by the optimiser. Conceptually similar to a lookup in an embedding table for word2vec or similar NLP models.

---

### torch.where

Element-wise conditional selection between two tensors.

```python
labels = torch.where(drop_mask, torch.full_like(labels, num_classes), labels)
# train.py:155
```

Where `drop_mask` is true, replace the label with the unconditional token (`num_classes`). Otherwise keep the original label. This implements CFG dropout — randomly masking 10% of labels during training.

> **Coming from C:** `for (int i = 0; i < n; i++) out[i] = mask[i] ? a[i] : b[i];` — but vectorised.

> **Coming from JS/TS:** `mask.map((m, i) => m ? a[i] : b[i])` — ternary selection across arrays.
