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
    color: #60a5fa;
  }
  section.title-slide a {
    color: rgba(255,255,255,0.5);
    font-size: 0.6em;
    text-decoration: none;
  }
  section:not(.title-slide) h2 {
    color: #1a1a2e;
    border-bottom: 2px solid #60a5fa;
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
    background: #e8f0fe;
    font-size: 0.85em;
  }
---

<!-- _class: title-slide -->
<!-- _paginate: false -->

![bg left:30% contain](logo.svg)

# Beepers

**1-bit sound synthesis from first principles**

The foundation layer — how sound works at the lowest level, and why it matters for everything above.

---

## What this is

A hands-on study of ZX Spectrum beeper engines. Five engines, built from scratch in Z80 assembly, each teaching a core synthesis concept.

No sound chip. No DAC (digital-to-analogue converter). One speaker bit. Toggle it fast enough and you get music.

| Engine | Concept | What you learn |
|--------|---------|---------------|
| **Oscillator** | Toggle at a rate | Frequency, period, pitch |
| **Pulse width** | Asymmetric toggle | Timbre, fake volume from 1 bit |
| **Noise & SFX** | Random toggle | Percussion, sweep, pitch bending |
| **Synthesis** | Combine techniques | Envelopes, vibrato, accent, mixing |
| **Digital audio** | Sample playback | PCM (pulse code modulation), PWM (pulse width modulation), output capture |

---

## Duty cycle — timbre from timing

A duty cycle is the ratio of "on" time to total cycle time. With one speaker bit, you can only be on or off — but *how long* you stay on before toggling off changes the sound completely.

- **50% duty** — on and off for equal time. A pure square wave. Hollow, buzzy tone.
- **25% duty** — on for a quarter, off for three quarters. Thinner, nasal — classic NES lead sound.
- **12.5% duty** — barely on at all. Sharp, reedy, almost like a plucked string.

The pitch stays the same (same total cycle length). Only the *shape* changes — and that shape is what gives a sound its character. Musicians call this **timbre**.

This is how a 1-bit speaker fakes volume and tonal variety. You can't change how loud the speaker is (it's either on or off), but you can change the proportion of on-vs-off within each cycle. A narrow pulse sounds quieter and thinner. A wide pulse sounds louder and fuller.

Every sound chip uses duty cycles — the Spectrum beeper just makes the mechanism obvious because there's nothing else to hide behind.

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
- **Chant** — describe a tune in English, LLM generates note tables for beepers
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

You don't need ML to understand beepers. But understanding beepers makes the ML in the other three concrete — you know exactly what the models are learning to detect, describe, or generate.

---

## Also produces: a VSTi (virtual instrument plugin)

The same beeper engines, ported to Rust with faithful integer T-state simulation.

- Same algorithm, same tone tables, same frequencies — proven with spectrogram comparison
- No floats in the timing path — toggles at exact same T-state as the Z80
- Current: 1-channel tone engine complete, D major scale sounds identical
- Future: VST3/CLAP (audio plugin formats) via nih-plug, WASM (WebAssembly — runs in the browser at near-native speed) for openDAW
- Long-term: a collection of faithful chip VSTis (AY-3-8912, SID, Game Boy, NES, OPL, Amiga)

---

## Status

- Engine 1 exercises 1.1–1.10 complete (1-channel tone engine)
- Rust port complete with integer T-state simulation
- Spectrogram comparison proves engines match (see `docs/compare/spectrogram.png`)
- Next: 2-channel interleave (exercises 1.11–1.15), then Engine 2 (pulse width)

Learning docs, concept maps, and a `/learn` skill drive the exercises — each step introduces new Z80 concepts alongside the audio work.

*The hard part isn't the code. It's understanding what sound is when you only have one bit.*

