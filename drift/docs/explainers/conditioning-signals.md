# Conditioning Signals for Audio Generation

What can you tell a generative model to steer its output? In drift, we condition on chip type. But there are other signals that could shape generation — some we could add, some need architectural changes.

---

## What we condition on now

**Chip type** (4 classes: AY, SID, VGM, modarchive). Implemented as a class embedding added to the timestep embedding. Each chip has a distinct sonic character — different frequency distributions, overtone structure, noise characteristics. See [chip-types.md](chip-types.md).

The conditioning is weak at the quality sweet spot (guidance scale 3.0). The model learned shared musical structure before chip-specific identity.

---

## Signals we could add without architectural changes

These use the same class-embedding mechanism — an integer label mapped to a learnable vector, added to the time embedding. Just more `nn.Embedding` tables.

**Tempo bucket.** Slow / medium / fast. Detectable from onset density in the spectrogram. Would help the model separate rhythmic patterns — a slow ballad looks very different from a fast arpeggio section. Easy to extract: count onsets per second in the training data, bucket into 3–5 ranges.

**Energy level.** Quiet / medium / loud. Based on RMS energy of the segment. A simple proxy for "intro section" vs "chorus." Already computable from the spectrograms — average Mel energy across time.

**Loop position.** Intro / body / outro. If the segment came from the first 10% of a track vs the middle vs the last 10%. Chip-tunes often have structurally different intros (fade in, single voice) vs body (full voices, dense).

Each of these adds one more integer to the conditioning vector and one more `nn.Embedding` table. Multi-label CFG needs one dropout mask per signal — drop each independently so the model learns unconditional, chip-only, tempo-only, chip+tempo, etc.

---

## Signals that need more work

**Key / pitch centre.** What key is the piece in? Useful for steering harmony, but hard to extract reliably from chip-tune spectrograms (many chip voices are noise or pulse waves, not pitched). Would need a pitch detection preprocessing step — `crepe` or similar. Worth exploring but not blocking.

**Time signature.** 4/4 vs 3/4 vs 6/8. Visible in the spectrogram's onset pattern but hard to label automatically. Most chip-tunes are 4/4 anyway, so low diversity.

**Continuous conditioning (tempo as BPM, not a bucket).** Requires replacing `nn.Embedding` with a continuous projection — similar to the timestep sinusoidal embedding. More expressive but harder to train with CFG (you can't "drop" a continuous value to unconditional the same way you drop a class label — you'd use a mask or a learned null vector instead).

---

## Signals from outside the audio

**Text prompts.** "Upbeat, fast, SID-style bass line." Needs a text encoder (CLIP or similar) — a much larger architectural change. This is what AudioLDM and MusicGen do. Out of scope for drift, but it's where the field is heading.

**Images.** Already partially supported via `--from-image`. The image steers the spectrogram's frequency structure through partial denoising, not through a conditioning embedding. This is drift's unique angle — the cross-feed with the Natural Noise art project (M7–M8).

**Other audio.** Style transfer — "make this sound like a SID chip." Needs an audio encoder to extract a style vector. Related to vocoder approaches like RAVE or EnCodec.

---

## What makes sense for drift

The creative workflow is: generate a batch, listen, tweak, curate. More conditioning signals = more knobs to tweak. But each one needs:

1. **Reliable labels** in the training data (automated extraction or manual annotation)
2. **Enough diversity** in the dataset to learn from (if 95% of data is 4/4, time signature conditioning won't learn much)
3. **Perceptible effect** on the output (if the listener can't tell the difference, the knob is useless)

For the next iteration, **tempo bucket** and **energy level** are the low-hanging fruit — easy to extract, likely to produce audible differences, and reuse the existing embedding machinery.
