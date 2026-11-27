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
    color: #fbbf24;
  }
  section.title-slide a {
    color: rgba(255,255,255,0.5);
    font-size: 0.6em;
    text-decoration: none;
  }
  section:not(.title-slide) h2 {
    color: #1a1a2e;
    border-bottom: 2px solid #fbbf24;
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
    background: #fef8e8;
    font-size: 0.85em;
  }
---

<!-- _class: title-slide -->
<!-- _paginate: false -->

![bg left:30% contain](logo.svg)

# Chant

**Text-to-chiptune via LoRA fine-tuning**

Describe a chip-tune in plain English. A fine-tuned language model generates note sequences that beepers can play.

---

## What this is

A fine-tuning project that teaches a small language model to compose chip-tune music from text descriptions.

LoRA (Low-Rank Adaptation) — a technique that adds a thin trainable layer on top of a frozen pre-trained model. Instead of retraining 362 million parameters, we train 819,000 (0.23%). The same approach used to adapt foundation models to any specialised domain.

| Component | Detail |
|-----------|--------|
| **Base model** | SmolLM2-360M — small enough to train on a laptop CPU |
| **LoRA rank** | 8, targeting attention layers |
| **Dataset** | 2,684 chip-tune tracks with text captions |
| **Training** | ~35 minutes on CPU, 3 epochs |
| **Output** | Note tables playable by the Beepers VSTi engine |

---

## How it works

Text in. Note sequence out. Beepers plays it.

```
"bright arpeggio,        LoRA        N72 D100 C0 V7      beeper-synth
 pulse wave,         ──────────►    N76 D100 C0 V6    ──────────────►  WAV
 C major"              SmolLM2      N79 D150 C0 V7
```

- **Custom tokeniser** — 671 tokens for note events: pitch (N0–N127), duration (D10–D5000), channel (C0–C31), volume (V0–V7)
- **Fully reversible** — encode a note table to tokens, decode back to the exact same table
- **Text-conditioned** — captions describe waveform, pitch pattern, rhythm, tempo
- **Audio rendering** — output feeds directly into Beepers' Rust synthesiser

---

## What is LoRA?

LoRA (Low-Rank Adaptation) fine-tunes a model by injecting small trainable matrices alongside its frozen weights. Think of it as teaching a new accent without rewiring the whole brain.

**Why it matters:**

- Train on a laptop CPU — no GPU cluster needed
- 0.23% of parameters retrained — the rest stay frozen
- The adapter is 6.5 MB — the base model is 720 MB
- Same technique works for any domain: legal, medical, financial

**The analogy:** A LoRA adapter is to a language model what a guitar pedal is to an amplifier — it shapes the output without rebuilding the hardware.

---

## The audio-to-finance bridge

Note tables and financial event sequences are structurally identical: ordered sequences of structured records with timing, magnitude, and type fields.

| Audio | Finance |
|-------|---------|
| "rising arpeggio, pulse wave, C major" → note table | "volatile open, mean reversion midday" → event series |
| Note = (pitch, duration, waveform, duty, effects) | Event = (price, volume, instrument, direction, volatility) |
| Text-conditioned generation of musical sequences | Text-conditioned generation of market scenarios |
| Signal Hunt classifier verifies rendered output | Statistical tests verify distribution match |
| LoRA adapts model to chip-tune domain | LoRA adapts model to specific asset class |

Learn it once on audio (where you can hear mistakes), apply it to structured data.

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

Chant depends on all three: Drift's archive for training data, Signal Hunt's classifier for evaluation, and Beepers' VSTi for playback.

---

## Status

- M1 (dataset), M2 (LoRA adapter), M3 (evaluation pipeline) — all complete
- 276 tests passing
- End-to-end verified: text prompt → generate → decode → validate → render to WAV
- Model generates valid token sequences; pitch diversity limited by dataset size (588 training pairs)

```bash
python -m chant.generate "bright arpeggio, pulse wave, C major"
# → NoteTable with 12 events, renders to WAV via beeper-synth
```

*The hard part isn't the neural network. It's designing a vocabulary that captures music precisely enough for a 360M-parameter model to learn it in 35 minutes.*
