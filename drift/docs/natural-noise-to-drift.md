# Natural Noise → Drift — Eyes and Ears

Two projects, one idea: nature is noise, and the interesting thing is what a system finds in it. Natural Noise explores this visually — photographs pushed through filters until only the system's interpretation remains. Drift explores it with audio — field recordings denoised into chip-tune melodies. Both operate on 2D tensors of intensity. This means we can cross-feed between them: a photograph can seed a melody, a spectrogram can seed a visual piece, and a single place can produce art for both eyes and ears from the same moment.

---

## The shared idea

Nature already *is* noise. Grass, rain, traffic, wind — complex signals with hidden structure. The interesting thing isn't the scene itself, but what a system *finds* in it when forced to decide what matters and what to discard.

The art project explored this with eyes. Drift explores it with ears.

| | Natural Noise (visual) | Drift (audio) |
|---|---|---|
| **Input** | Photograph (grass, sky, water) | Field recording (road, rain, machine) |
| **Transform** | Greyscale → sigmoid → band → colour map | Audio → Mel-spectrogram → normalise → diffusion model |
| **Noise source** | Perlin noise as synthetic texture | Gaussian noise as diffusion starting point |
| **Question** | What does the filter see in this field? | What does the model hear in this road? |
| **Output** | Topographic colour fields — the filter's interpretation | Chip-tune melody — the model's interpretation |
| **The art** | The filter's bias *is* the artwork | The model's bias (trained on chip-tunes) *is* the composition |

---

## Experiment 1 — Same place, two senses

Stand somewhere. A field, a roadside, a rainy window.

1. **Photograph** the scene
2. **Record** 30 seconds of ambient sound
3. Run the photo through Natural Noise → get a visual piece
4. Run the recording through Drift → get a chip-tune

The visual and the melody come from the same moment, the same place — but through different senses and different systems. Do they feel related? Does the road that produced dark, banded topography also produce a heavier, more rhythmic tune? Does the rain that made soft, diffuse colour fields also make something gentler?

The answer might be no. That's interesting too — it tells you something about what each system latches onto.

---

## Experiment 2 — Cross-feeding between eyes and ears

Both systems operate on the same thing: 2D arrays of intensity values. A Mel-spectrogram is just an image (frequency × time). A Natural Noise output is just an image (x × y). They're the same shape of data. This means we can feed one into the other.

### Visual → Audio: art becomes the seed for a melody

Take the banded colour field from a grass photo. Resize to spectrogram dimensions (e.g. 128×256). Greyscale it. Feed that directly into Drift as the starting "noise" instead of Gaussian noise. The diffusion model denoises it into a chip-tune — but the frequency structure of the visual piece steers where the melody goes. Dark bands become bass, bright islands become treble.

This is the beautiful one. You photograph a field, process it into art, then the art *becomes the seed for a melody*. The visual and the audio are causally linked — not just from the same place, but one literally produces the other.

### Photo → Audio: raw photograph as starting spectrogram

Skip the art processing entirely. Take the grass photo itself, resize to spectrogram dimensions, normalise to [-1, 1]. The model denoises it. The vertical axis becomes frequency, the horizontal becomes time. Texture in the photo becomes timbre in the tune.

### Audio → Visual: spectrogram as Natural Noise input

Run a field recording through Mel-spectrogram conversion. Feed that image into the Natural Noise banding process instead of a photograph. The sigmoid + band + colour map reveals the structure in the sound visually — a different view than a raw spectrogram.

### The full loop

Photograph → Natural Noise art → Drift spectrogram seed → chip-tune → Mel-spectrogram → Natural Noise art.

The output visual won't look like the input visual. The distance between them is a measure of what was lost, transformed, and invented across two domain crossings and two systems. That gap *is* the piece.

---

## Why this matters beyond art

Both projects are about the same underlying operation: **denoising structured signals**. The visual version is hand-tuned (sigmoid, banding, colour palette). The audio version learns it (U-Net trained on spectrograms). Drift formalises what Natural Noise did intuitively — and the diffusion framework explains *why* the source noise steers the output.

The techniques transfer directly. Spectrograms are 2D tensors with a time axis — structurally identical to financial time series. The same denoising intuition applies: what does the model find when you feed it market noise instead of Gaussian noise?

Eyes → ears → numbers. Same question each time.
