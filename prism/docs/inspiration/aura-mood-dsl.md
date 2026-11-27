# Project Plan: Stage 2 Aura — Mood DSL Engine

## Summary
Build a single structured **Mood DSL** describing experiential and physical intent as the single source of truth.

> **One YAML Spec → Dual Audio & Visual Projections**

State modification flows through three operational layers:
* **Mood:** Affective intent (e.g., "increase tension").
* **Composition:** Structural parameters (e.g., "raise pitch register").
* **Direct/Physical Control:** Real-time overrides (e.g., "transpose +3 semitones", "cap hand span to 6ths").

---

## Technical & Architectural Progression

### Phase 1 — DSL Vocabulary & Biomechanical Constraints
Define a minimal YAML schema mapping emotional state and physical performance envelopes.
* **Mood Parameters:** `valence`, `energy`, `tension`, `density`, `stability`, `warmth`, `motion`.
* **Biomechanical Constraints:** `target_level` (1–10), `max_hand_span` (semitones), `leap_tolerance`, `rhythmic_grid`, `polyphony_limit`.

### Phase 2 — Trajectory & Performance Timeline
Model evolving state using time-series keyframes for ramps, peaks, and releases.
* **Execution:** Dynamically adjust energy, tension, and physical density across timeline blocks while enforcing biomechanical friction limits.

### Phase 3 — Unified Composition & Master Schema
Extend the master YAML to couple emotional intent with explicit audio, visual, and performance primitives.
* **Audio Scope:** Register, timbre character, harmonic stability, motif arrays.
* **Visual Scope:** Motion vector, field turbulence, structural density, particle velocity.
* **Biomechanical Scope:** Physical leap limits, finger speed bounds, hand-independence friction.

### Phase 4 — Audio Projection Engine
Compile the YAML state into sound parameters and WAV/DSP output.
* **Mapping Mechanics:** Tension drives dissonance/instability; energy drives amplitude/activity; physical difficulty drives note density, rapid arpeggiation, and complex voice placement.

### Phase 5 — Visual Projection Engine (WebGL/GLSL)
Render the **same YAML state** into GPU visual shaders.
* **Mapping Mechanics:** Tension drives field turbulence; energy drives particle movement; physical execution friction translates into visual pulse rate, geometric deformation, and line density.

### Phase 6 — Multi-Layered Control Model
Process state edits across three distinct abstraction tiers:
* **Mood Layer:** Prompt-based emotional shifts ("make it darker").
* **Composition Layer:** Structural changes ("thin out left-hand texture").
* **Direct Control Layer:** Immediate, non-LLM param updates (MIDI CC, filter cutoffs, key transposition).

### Phase 7 — Physical MIDI Interface & Motif Capture
Integrate hardware (e.g., MPK Mini) to manipulate state and inject musical material.
* **Continuous Control:** Assign knobs to mood parameters, wheels to texture/pitch, pads to timeline transitions.
* **Motif Engine:** Capture played phrases into the YAML spec (`notes`, `rhythm`, `character`). The LLM or DSP compiler transforms, harmonizes, or simplifies these motifs while enforcing player level bounds.

### Phase 8 — LLM Compiler & State Iteration
The LLM modifies versioned YAML files (`mood-v01.yaml`, `mood-v02.yaml`) rather than raw audio or video streams, ensuring deterministic compilation and structural consistency.

---

## Core System Architecture

```text
                     MASTER YAML SPEC (One State)
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
     LLM Compiler           MIDI Controller           UI / Prompts
          │                       │                       │
          │               ┌───────┴───────┐               │
          │             Mood           Melody             │
          │               │               │               │
          └───────────────┴───────────────┴───────────────┘
                                  │
                                  ▼
                            UPDATED YAML
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
            AUDIO ENGINE                    VISUAL ENGINE
        (DSP / Python / Rust)              (WebGL / GLSL)
                  │                               │
                  └───────────────┬───────────────┘
                                  ▼
                    Synchronized Audio-Visual World
```

## Appendix — Multimodal AI & Audio Synthesis

### Acoustic Analysis & AI Perception

Multimodal AI models process audio by transforming raw waveforms (e.g., 44.1kHz sample arrays) via Fast Fourier Transform (FFT) into **2D Spectrograms** (Time vs. Frequency vs. Amplitude).

```text

Frequency
  high │   .  .     . .  .
       │ .. ..   .. .. ..
       │ .....  ........
   low │...................
       └────────────────────
            Time →

```

### Bi-Directional Signal Flow
* **Generative Pipeline:** `Intent Spec → YAML Bounds → DSP Synthesis → WAV Numbers → Speaker`
* **Perceptual Pipeline:** `Sound → Microphone → Waveform Numbers → Spectrogram Image → Shared Multimodal Space`

Understanding this mapping allows the LLM compiler to translate qualitative human feedback ("make the low end punchier", "reduce left-hand friction") into precise DSP filter coefficients, harmonic overtone adjustments, and finger-placement limits.