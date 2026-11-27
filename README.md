# Music & Sound AI Lab

**[View the site](https://benwaar.github.io/music/)**

Hands-on machine learning music and sound AI projects.

## Development Ethos

These projects are about:
- understanding algorithms by building them
- seeing how different approaches *think*
- learning by stripping problems down to their **nuts and bolts**

Everything is inspectable and hackable.

---

## Projects

| # | Project | What it builds | Depends on | Status |
|---|---------|---------------|------------|--------|
| 1 | [Signal Hunt](signal-hunt/) | Audio AI: sound classification → piano notes → chords and progressions | — | done |
| 2 | [Beepers](beepers/) | 1-bit beeper synth: Z80 ASM → Rust → VST3/CLAP plugin + MCP knowledge server | — | done |
| 3 | [Drift](drift/) | Chip-tune generation via denoising diffusion on Mel spectrograms | Signal Hunt | done |
| 4 | [Chant](chant/) | Text-to-chiptune via LoRA fine-tuning of a small language model | Drift, Signal Hunt, Beepers | done |
| 5 | [Prism](prism/) | Cross-modal VAE — melody ↔ visual mapping inspired by chromesthesia | — | planning |
| 6 | [Bloom](bloom/) | Chiptune → full production via GAN domain translation | Beepers | planning |


---

## Signal Hunt

Deep Learning: CNNs and transfer learning for predictive modeling.

`audio classification` · `CNN` · `transfer learning` · `Mel spectrograms` · `CNN-RNN` · `ONNX` · `WASM inference`

Turn raw audio into Mel spectrograms, then build up from sound classification through piano note detection, chord recognition, and chord progressions. The trained model also runs in a live browser demo, with real-time inference and no server required.

**Highlights:** 89.5% piano note accuracy · 96.2% chord-name accuracy · browser demo with ~12 ms end-to-end inference

[Project folder](signal-hunt/) · [Project log](signal-hunt/LOG.md) · [Full documentation](signal-hunt/DOCS.md)

---

## Beepers

[![crates.io](https://img.shields.io/crates/v/eno-state-zx.svg)](https://crates.io/crates/eno-state-zx)
[![docs.rs](https://docs.rs/eno-state-zx/badge.svg)](https://docs.rs/eno-state-zx)

1-bit beeper synth and knowledge engineering stack.

`Z80 assembly` · `Rust` · `VST3/CLAP` · `1-bit audio` · `beeper engines` · `MCP server` · `FAISS` · `ONNX embeddings`

Learn how the ZX Spectrum beeper works by building engines from scratch in Z80 ASM, then port each to Rust as a playable VST3/CLAP synth plugin (Eno State ZX). Plus a full knowledge engineering stack — Rust MCP server with keyword and ONNX semantic search, FAISS embeddings, and a curated Z80/Spectrum/WASM corpus.

**Highlights:** 4 engines (tone, pulse width, noise, synthesis) · 14 Rust tests · MCP knowledge server · ONNX semantic search

[Project folder](beepers/) · [Explainers](beepers/explainers/) · [Z80 exercises](beepers/zx/) · [Knowledge MCP](beepers/knowledge-mcp/)

---

## Drift

Generating chip-tune music from noise using diffusion models.

`diffusion` · `U-Net` · `DDPM` · `DDIM` · `Mel spectrograms` · `conditional generation` · `noise schedules`

Train a denoising diffusion model on 54,000 chip-tune spectrogram segments across four chip architectures (SID, AY, SN76489, MOD). Start from pure noise and denoise step by step into playable audio. M5 replaces random noise with real-world recordings as seeds.

**Highlights:** 54k segments · 4 chip types · M0–M7 complete · melody extraction pipeline

[Project folder](drift/) · [Explainers](drift/docs/explainers/) · [Plan](drift/PLAN.md)

---

## Chant

Text-to-chiptune via LoRA fine-tuning.

`LoRA` · `SmolLM2` · `custom tokeniser` · `Rust synth` · `text-conditioned generation`

Describe a chip-tune in plain English and a fine-tuned language model generates note sequences that beepers can play. 0.23% of parameters retrained, trains in 35 minutes on CPU. Custom 671-token vocabulary for note events.

**Highlights:** 2,684 tracks · 308 tests · 671 custom tokens · 92.4% quality gate · Rust MIDI host

[Project folder](chant/) · [Explainers](chant/explainers/) · [Plan](chant/PLAN.md)

---

## Prism

Cross-modal learning — melody ↔ visual mapping inspired by chromesthesia.

`VAE` · `cross-modal` · `latent spaces` · `representation learning` · `chromesthesia`

Train a Variational Autoencoder to compress melodies into a meaningful latent space, then map that space to visual parameters (colour, energy, motion). Inspired by chromesthesia — hearing colour, seeing sound.

**Status:** Planning — schema and inspiration docs ready.

[Project folder](prism/) · [Inspiration docs](prism/docs/inspiration/)

---

## Bloom

Chiptune → full production via GAN domain translation.

`GAN` · `CycleGAN` · `pix2pix` · `domain translation` · `style transfer`

Treat spectrograms as images and learn to map from the 1-bit beeper domain to modern multi-track arrangements — the audio equivalent of pixel art to photorealistic rendering.

**Status:** Planning — architecture research complete.

[Project folder](bloom/)

---

# Eno State 

Songs for games and films, the odd punk song and an occasional ballard.

**Lyrics by David Benoy**

Featured in the [Aerythen CLI Punk Universe](https://aerythen.com/).

### Listen & Stream

* **Linktree:** [All Links](https://linktr.ee/enostate)
* **Universal Link:** [Song.link](https://song.link/jtmzgwknhjt8g)
* **Spotify:** [Playlist / Track](https://open.spotify.com/playlist/3NZB6jhJ4FjMazS8HllwPH?si=XzlZ6ex1SJWiKl1pOG74TQ)
* **Amazon Music:** [Album Release](https://music.amazon.co.uk/albums/B0HKLG8Z49?marketplaceId=A1F83G8C2ARO7P&musicTerritory=GB&ref=dm_sh_RQPvr9uAS5PsdV0dZp0nVt6hE&trackAsin=B0HKKXCDFR)

---

## License

Source code is licensed under the MIT License.

Aerythen and Eno State the associated song lyrics, artwork, the game names and branding are © 2026 David Benoy. All rights reserved.