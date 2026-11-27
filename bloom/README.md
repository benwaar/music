# Bloom

Chiptune → full production using GANs. Take a 1-bit beeper track and blow it up to a modern multi-track arrangement.

## What

Audio domain translation via spectrogram-based GANs. Treat spectrograms as images and learn to map from the chiptune domain to the full-production domain — the audio equivalent of pixel art → photorealistic rendering.

## Why

Part of an ML/AI study programme. Bloom covers:

- **GAN** — generator/discriminator training, mode collapse, Wasserstein loss
- **Domain translation** — CycleGAN (unpaired) and pix2pix (paired) architectures
- **Style transfer** — learning what makes a domain sound the way it does
- **Spectrogram manipulation** — builds on signal-hunt's audio-as-image foundation

## Approach

**CycleGAN (unpaired)** is the practical starting point:
- Collect a set of chiptune spectrograms (beepers can generate these)
- Collect a set of modern production spectrograms (any music library)
- No matching pairs needed — the model learns the domain mapping

**pix2pix (paired)** if we can build matching data:
- Same melody rendered as chiptune (via beepers) and as full production
- Cleaner results, harder data collection

## Connection to Beepers

Beepers (Eno State ZX) is the perfect source — a 1-bit ZX Spectrum synth that produces chiptune audio from first principles. It generates the input domain data directly.

## Stack

- Python, PyTorch
- Spectrogram processing: librosa / torchaudio
- GAN architectures: CycleGAN, pix2pix
- Audio reconstruction: Griffin-Lim or neural vocoder

## Applications in Finance

The same techniques apply directly to banking and fund management:

- **Synthetic data generation** — GANs producing realistic transaction tables for testing, training, and compliance (CTGAN, CTAB-GAN)
- **Stress testing** — generate realistic extreme market scenarios that haven't occurred historically
- **Data augmentation** — rare events like fraud and defaults are hard to train on; GANs create more examples
- **Domain adaptation** — model trained on one market or region translated to another, same CycleGAN concept with different domains

## Sibling Projects

| Project | ML Domain |
|---------|-----------|
| signal-hunt | CNN, RNN, audio classification |
| drift | Diffusion models, U-Net |
| chant | LoRA fine-tuning |
| prism | Autoencoder/VAE, cross-modal learning |
| beepers | 1-bit synthesis (source material for bloom) |
