# How AI "Hears" Audio, "Sees" Images

---

## The short version

Multimodal AI models (like GPT-4o, Gemini) can process audio — speech, music, environmental sounds. They don't "hear" like humans do. Instead, audio is transformed into numerical representations that the model reasons about, similar to how images are converted into visual features before interpretation.

---

## How it works

### 1. Audio becomes numbers (just like our WAV files)

Sound enters as a waveform — the same list of numbers we've been writing. 44,100 samples per second, each one describing speaker position. This is the raw input.

### 2. Numbers become a spectrogram

The raw waveform is transformed (usually via FFT — Fast Fourier Transform) into a **spectrogram**: a 2D image where:

- X axis = time
- Y axis = frequency (low notes at bottom, high at top)
- Brightness = how loud that frequency is at that moment

```
Frequency
  high │  .  .     . .  .
       │ .. ..   .. .. ..
       │ .....  ........
  low  │...................
       └────────────────────
              Time →
```

This is the key insight: **audio becomes an image**. The model can then use the same visual processing it uses for photos.

### 3. The spectrogram feeds into the model

The model processes this "image" through layers that learn patterns:

- Speech patterns (phonemes, words, accents)
- Musical patterns (chords, rhythm, instruments)
- Environmental sounds (sirens, birdsong, typing)

### 4. Shared representation

The clever bit: the model learns a **shared internal language** across text, images, and audio. This is why you can ask:

- "Describe the mood of this music" (audio → text)
- "What instrument is playing?" (audio → text)
- "Generate code to recreate this sound" (audio → code)
- "Does this match the sheet music?" (audio + image → reasoning)

---

## What AI can and can't do with audio

### Can do well:
- Transcribe speech (multiple languages, accents)
- Identify instruments and musical keys
- Describe the "character" of a sound (bright, warm, harsh)
- Reason about acoustic properties (reverb, distortion, clipping)
- Relate sounds to DSP concepts (filtering, frequency content)

### Can't do (or does poorly):
- Hear in real-time (processes chunks, not a continuous stream)
- Distinguish very similar timbres (two similar violins)
- Precise pitch detection to the cent (use software tools for this)
- Generate audio directly (produces text/code that *describes* audio)

---

## Why this matters for our project

We're writing raw waveform numbers → WAV files. An AI model does the reverse:

```
Our project:         Idea → Numbers → WAV → Speaker → Sound
AI understanding:    Sound → Microphone → Numbers → Spectrogram → Meaning
```

Same numbers, opposite direction. Understanding one helps understand the other.

The spectrogram step is interesting — it's basically asking "which frequencies are present at each moment?" That's exactly what our waveforms define:

- Sine at 440Hz → one bright dot at 440 on the spectrogram
- Square at 440Hz → dots at 440, 1320, 2200... (harmonics — the overtones that make it buzzy)
- Sawtooth → even more harmonic dots (why it sounds brassy/rich)

---

## Cross-Modal Translation: Dialect Swapping

Because the underlying intermediate state of a sound or image can be represented as a neutral abstract syntax tree (AST), we can decompile media from one perceptual dialect and re-compile it through another:

```
[ Visual Seed / Audio Input ] ──► (Decompile) ──► [ Neutral AST ]
                                                        │
         ┌──────────────────────────────────────────────┼──────────────────────────────────────────────┐
         ▼                                              ▼                                              ▼
[ Profile: colorblind_impasto ]                [ Profile: rothko_chromatic ]                 [ Profile: me.json ]
 High value contrast & isolated                 Soft plum fields & radiant                   Warm autumn earth sub-drone &
 primary cobalt pops.                           hovering coral light glazes.                 cold electric cyan transient flashes.
```

Through this pipeline, Eno acts as a cognitive compiler: taking an artwork shaped by a color-blind painter or a machine vision model, extracting its structural intent, and rendering it directly inside your personal synesthetic dialect.

---

## The training data question

These models weren't trained by ingesting "all audio on the internet." Training uses a mixture of:

- Licensed datasets
- Data created by human annotators
- Publicly available data where appropriate

No AI company has published a complete inventory of their audio training data. The result is a model that can reason about sound, but the exact source material remains opaque.

---

## Connection to DSP and this project

If you're building audio tools (like we are), multimodal AI becomes useful for:

- Describing what a generated sound "sounds like" without playing it
- Suggesting parameter tweaks ("make it warmer" → lower the high harmonics)
- Analysing recordings to extract musical structure
- Bridging the gap between musical intent and DSP parameters

The shared representation means you can work in whichever domain is most natural — describe in words, show a spectrogram, write code, or play audio — and the model maps between them.

---

# LLM Variety and Uniqueness (warning)

Generative models do not explicitly copy stored MIDI files, but monophonic melody generation operates within a tiny state space compared to image generation, leaving far less room for variance. When prompting for specific musical archetypes—like a driving 90s club synth hook—the LLM pursues the highest statistical probability for that genre, frequently converging on the exact same narrow 4-to-8-note interval sequences that made iconic tracks famous. The Parsons Code checker isn't catching the LLM "stealing," but rather serving as a fast, deterministic guardrail against this accidental statistical convergence, ensuring generated .eno assets remain provably distinct before audio synthesis.

---

# Artificial Synesthesia: How Shared Latent Space Mirrors Chromesthesia

The way a multimodal AI processes audio through a shared representation space is remarkably similar to human Chromesthesia. When an AI converts an audio waveform into a spectrogram, it literally transforms acoustic frequency into a visual image. Within its internal high-dimensional vector space, visual, auditory, and textual concepts exist in direct mathematical proximity to one another—high-frequency timbre vectors sit adjacent to bright visual vectors, while dense harmonic structures align with saturated geometric textures. The model does not experience sensory qualia, but its architectural structure functions as an algorithmic form of synesthesia. For developers with Chromesthesia, interacting with a multimodal LLM often feels natural because the model’s internal cross-modal translation—mapping a sound directly to a visual parameter or qualitative mood descriptor—mirrors the brain's innate cross-sensory neural pathways.

---

# How Machines "See" Images: Convolutional Feature Maps

When an AI model looks at an image—or an audio spectrogram—it doesn't see a single complete picture. It breaks the visual matrix down across layers of feature maps:

Low-level layers: Detect hard edges, high-contrast borders, pixel-level transients, and local gradient spikes.

High-level layers: Group those edges into abstract geometric relationships, spatial boundaries, and semantic concepts.

## Tom White & Neural Abstractions

Artist Tom White capitalized on this machine mechanics to create Neural Abstractions—prints designed not for human eyes, but specifically to trigger high-confidence classifications inside deep vision models. By stripping away realistic surface detail, his work isolates the absolute minimal vector edges and gradient spikes required to fire specific artificial neurons.

This reveals a key parallel for audio/visual compilers: computers don't require realistic representations to identify a concept—they only require its distilled mathematical activation triggers.

---

# The Four Perceptual Dialects in Eno

Perceptual Dialects: Translating Across Cognitive Lenses
Because latent vector spaces allow high-dimensional mapping across audio and visual domains, we can define runtime profiles (.json) that dictate how those cross-modal vectors compile into sound and light. Rather than relying on standard AI population defaults, Eno leverages four distinct perceptual dialects:

Personal Chromesthesia (me.json): Individual qualia. Maps low-frequency acoustic warmth and tape saturation to autumn earth tones/terracotta, and high-frequency transients to razor-thin flashes of cold neon cyan and electric blue.

Color-Blind Impasto (colorblind_impasto_v1): A value-contrast and luminance model. Maps deep silhouette masses and glowing horizon halos to sub-bass drones, using isolated cobalt blue and crimson accents for transient spikes.

Rothko Chromatic (rothko_chromatic_v1): An atmospheric color-field model. Maps sustained acoustic weight to dark plum, maroon, and charred earth fields, while transient shifts manifest as soft glazes of cadmium orange and radiant light.

Neural Abstraction (neural_abstraction_v1): A machine-vision feature-map model. Strips away form to map hard vector edge discontinuities and pixel gradient spikes into precise DSP noise floors and sharp digital spikes.

---

