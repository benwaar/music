# Chromesthesia — Conceptual Foundations

Extracted from the original Eno project. These ideas inspire Prism's cross-modal ML work.

---

## The Core Idea

Chromesthesia is the synesthetic perception where auditory stimuli spontaneously evoke visual colours and shapes. Traditional creative software treats audio and visuals as distinct domains linked only after production through manual timelines. The chromesthetic approach instead models sound and vision as **simultaneous, parallel render targets of a single underlying generative state**.

Modern Large Language Models operate on high-dimensional latent vector spaces where acoustic concepts (timbre, harmonics, attack) inherently map to mathematical neighbours in visual and qualitative domains. They act as ideal cross-modal compilers: natural language input or visual seeds don't merely trigger sound — they compile fluidly into unified audio-visual structures.

## Four Perceptual Dialects

Rather than generic AI defaults (calm = blue, high energy = red), the chromesthetic framework introduces distinct **perceptual profiles** that translate art and sound differently:

### 1. Personal Chromesthesia
Built on individual qualia. Low-frequency acoustic warmth and tape saturation pair with autumn earth tones and terracotta. Piercing high-frequency transients trigger razor-sharp flashes of cold neon cyan, electric blue, and white.

### 2. Colour-Blind Impasto
Reverse-engineered from palette choices relying on high luminance value contrast and isolated primary strikes. Dark silhouette masses and glowing horizon halos map to heavy sub-bass drones; isolated cobalt blue and crimson accents map to high-energy transient spikes.

### 3. Rothko Chromatic
Based on colour-field philosophy and emotional envelopment. Deep, sustained resonance maps to dark plum, maroon, and charred earth fields. Transient shifts manifest as soft, glowing glazes of cadmium orange and radiant light bleeding through layers.

### 4. Neural Abstraction
Inspired by Tom White's work on how convolutional neural networks perceive images. Strips away realistic forms to isolate raw mathematical activation triggers. Hard vector edge discontinuities and feature-map gradients translate into precise DSP noise floors and sharp digital spikes.

## Cross-Modal Translation

The ultimate vision: take a piece of art created in one perceptual dialect, extract its intermediate structure into a neutral specification, and re-compile it through a different profile. Experience the structural intent of other human minds and machine vision models translated into your own synesthetic dialect.

## Brian Eno and Generative Music

Eno coined the term "Generative Music" in 1996 (the Koan software). His key insight from Discreet Music (1975) and Music for Airports (1978): use asynchronous loops of different lengths that perpetually generate new combinations without repeating. The system, not the composer, creates the moment-to-moment experience.

See [gen-music-history.md](../history/gen-music-history.md) for the full timeline from Wurfelspiel to MusicLM.

## Architecture Vision (Simplified for ML)

The original project envisioned four phases:
1. **Resonance** — text → audio (intent compilation)
2. **Aura** — unified mood → parallel audio + visual
3. **Chroma** — bi-directional visual ↔ audio remixing
4. **Cadence** — production DSP engine

Prism focuses on the ML core of phases 2 and 3: learning a **shared latent space** where melodies and visual parameters coexist, enabling cross-modal generation and translation via autoencoders/VAE.
