# Prism

Cross-modal ML — learning shared representations between audio and visual, inspired by chromesthesia.

## What

Prism trains a Variational Autoencoder (VAE) on labelled melody data to learn a meaningful latent space of musical sequences. A cross-modal head then maps that latent space to visual parameters (colour, energy, motion), creating a bridge between audio structure and visual perception.

The name comes from a prism splitting light — here we split audio through a visual lens.

## Why

Part of an ML/AI study programme ([study index](../music/docs/index.html)). Prism covers study areas not yet explored:

- **Autoencoder / VAE** — learning compressed representations, reconstruction loss, KL divergence
- **Embedding spaces** — latent space structure, interpolation, clustering
- **Cross-modal learning** — mapping between audio and visual domains in a shared space
- **Representation learning** — what makes a good learned feature vs a hand-crafted one

## Inspiration

Inspired by Brian Eno's **generative processes** and grounded in **chromesthesia** — the synesthetic perception where auditory stimuli spontaneously evoke visual colours and shapes.

Traditional creative software treats audio and visuals as distinct domains linked only after production. Prism instead explores them as **simultaneous render targets of a single underlying state** — the same idea, approached through ML. Because high-dimensional latent vector spaces naturally map acoustic concepts (timbre, harmonics, attack) to mathematical neighbours in visual and qualitative domains, a learned embedding can act as a cross-modal bridge: melody in, visual parameters out, or the reverse.

See [docs/inspiration/](docs/inspiration/) for the full chromesthesia vision, perceptual dialect profiles, and mood parameter schemas.

## Data

Melody schema and 2 examples in [data/melodies/](data/melodies/). Full training data will be generated at scale when ML work begins. See [SCHEMA.md](data/melodies/SCHEMA.md) for the format.

Each melody has a note sequence (pitch + duration) and semantic labels across 7 dimensions: mood, style, energy, movement, character, imagery, rhythm.

## Stack

- Python, PyTorch
- Melody data: JSON → tensor encoding
- Visualisation: matplotlib / plotly for latent space exploration

## Applications in Finance

The same techniques apply directly to banking and fund management:

- **Fraud detection** — VAE learns "normal" transaction patterns, flags anomalies as high reconstruction error
- **Customer segmentation** — latent space clustering of behaviour across products and channels
- **Synthetic data** — sample the VAE to generate realistic but privacy-safe transaction data (GDPR/compliance)
- **Cross-modal mapping** — shared embeddings between text (reports, filings) and numerical data (positions, risk metrics)

## Sibling Projects

| Project | ML Domain |
|---------|-----------|
| signal-hunt | CNN, RNN, transfer learning, audio classification |
| drift | Diffusion models, U-Net, noise schedules |
| chant | LoRA fine-tuning, text-conditioned generation |
| beepers | 1-bit synthesis (Z80 → Rust VST3) |
