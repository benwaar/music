---
marp: true
theme: default
paginate: true
style: |
  section {
    font-family: 'Segoe UI', system-ui, sans-serif;
  }
  section.title-slide {
    background: #1a1a2e;
    color: #fff;
  }
  section.title-slide h1 {
    font-size: 2.6em;
    margin-bottom: 0.1em;
    color: #fff !important;
  }
  section.title-slide p {
    color: rgba(255,255,255,0.7);
  }
  section.title-slide strong {
    color: #22c55e;
  }
  section.title-slide a {
    color: rgba(255,255,255,0.5);
    font-size: 0.6em;
    text-decoration: none;
  }
  section:not(.title-slide) h2 {
    color: #1a1a2e;
    border-bottom: 2px solid #22c55e;
    padding-bottom: 0.2em;
  }
  em {
    color: #555;
  }
  table {
    font-size: 0.85em;
  }
  table th {
    background: #1a1a2e;
    color: #fff;
  }
  code {
    background: #e8fef3;
    font-size: 0.85em;
  }
---

<!-- _class: title-slide -->
<!-- _paginate: false -->

![bg left:30% contain](logo.svg)

# Signal Hunt

**Audio classification from first principles**

From raw waveforms to a piano tutor — deep learning on Mel spectrograms, built phase by phase.

---

## What this is

A hands-on study of audio classification with CNNs (convolutional neural networks — image-style pattern recognition applied to audio). Four phases, each building on the last, turning raw audio into musical understanding.

No pre-trained models. No shortcuts. Record audio, transform it, train a classifier, deploy it in a browser.

| Phase | Task | Result |
|-------|------|--------|
| **1** | Data pipeline — ingest, augment, Mel spectrograms | `(1, 128, 65)` tensors, 7 augmentations per clip |
| **2** | Sound type CNN (hum / whistle / clap) | 100% test accuracy |
| **3** | Piano note classifier, transfer learning | 89.5% test accuracy, 12 classes |
| **4** | Chord detection — name + note-set models | 96.2% / 73.1% exact-match |

---

## Mel spectrograms — turning sound into images

A Mel spectrogram is a picture of sound. It breaks audio into three dimensions a neural network can read like a photograph.

- **X-axis** — time (left to right, like a timeline)
- **Y-axis** — frequency (low notes at the bottom, high notes at the top)
- **Brightness** — how loud that frequency is at that moment

The "Mel" part matters: human ears hear the difference between 200 Hz and 400 Hz clearly, but 8,000 Hz and 8,200 Hz sound almost identical. The Mel scale spaces frequencies the way we actually hear them — more detail where it counts.

This is why audio classification works: different notes, chords, and sounds each leave a distinct visual fingerprint. A C major chord looks different from an A minor chord the same way two faces look different in a photo.

Every model in this project learns from these images — not from raw audio.

---

## How it works

Audio in. Spectrogram out. CNN classifies.

```
WAV → resample → Mel spectrogram → augment → CNN → prediction
        16 kHz     128 bins × 65 frames   ↑
                                      time shift, noise,
                                      pitch shift, gain...
```

- **Mel spectrograms** — the image representation from the previous slide, 128 frequency bins × 65 time frames
- **Transfer learning** — Phase 2 features bootstrap Phase 3
- **Two-pass chord detection** — one model names the chord, another verifies individual notes
- **Browser inference** — ONNX (Open Neural Network Exchange) Runtime via WASM (WebAssembly — runs code in the browser at near-native speed), no server needed

---

## How it connects

Four related projects exploring sound from different angles.

```
Beepers              Signal Hunt           Chant                 Drift
───────              ───────────           ─────                 ─────
Build the signals    Classify them         Describe → generate   Generate from noise
```

- **Beepers** — learn what a waveform *is* by building one from a single bit
- **Signal Hunt** — given audio, classify notes and chords (CNN on Mel spectrograms)
- **Chant** — describe a tune in English, an LLM (large language model) generates note tables for beepers
- **Drift** — diffusion model creates new chip music from noise spectrograms

---

## The signal processing bridge

The same concepts appear across all four projects.

| Concept | Where it shows up |
|---------|-------------------|
| Frequency | Period counters, Mel spectrograms, diffusion y-axis |
| Harmonics | Duty cycle shape, CNN frequency bins, learned structure |
| Noise | PRNG toggle, classifier noise floor, diffusion schedule |
| Envelope | Amplitude shaping, volume contours, intensity over time |

Understanding beepers makes the ML concrete — you know exactly what the models are learning to detect, describe, or generate.

---

## Status

- All four phases complete — pipeline through to chord detection
- Browser demo live via ONNX Runtime WASM (no server)
- Chord progression CNN-RNN (recurrent neural network — learns sequences over time) at 66.7% on 4 classes (Phase 4b)
- Full explainer docs for every concept: browser pipeline, real-time inference, Mel spectrograms

```bash
bash demo_chord.sh chord.wav --expected Cmaj
# Chord:   Amin  ✗  (expected Cmaj)
# Notes:   A4 ✓  C4 ✓  E4 ✓
# Missing: G4
```

*The hard part isn't the neural network. It's understanding what sound looks like when you turn it into an image.*
