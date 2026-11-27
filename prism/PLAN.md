# Prism — ML Roadmap

## Phase 1: Data Pipeline

- [ ] Load melody JSONs into structured Python objects
- [ ] Encode note sequences as tensors (pitch as integer, duration as float)
- [ ] Encode semantic labels (mood, energy, movement, etc.) as multi-hot or embedding vectors
- [ ] Pad/truncate sequences to fixed length
- [ ] Train/val split
- [ ] PyTorch Dataset and DataLoader

## Phase 2: Melody VAE

- [ ] Encoder: sequence → latent vector (RNN or 1D-CNN backbone)
- [ ] Decoder: latent vector → reconstructed sequence
- [ ] VAE loss: reconstruction + KL divergence
- [ ] Train on melody data (augment with transposition, tempo shift)
- [ ] Visualise latent space (t-SNE / UMAP coloured by mood, genre, energy)
- [ ] Interpolation: walk between two melodies in latent space, decode intermediates

## Phase 3: Cross-Modal Head

- [ ] Define visual parameter space (colour hue/saturation/brightness, energy, motion, texture)
- [ ] Train a mapping network: melody latent → visual parameters
- [ ] Supervised signal: use the analysis labels as proxy targets
- [ ] Evaluate: do similar melodies map to similar visual outputs?

## Phase 4: Exploration

- [ ] Interactive latent space explorer (plotly or streamlit)
- [ ] Generate novel melodies by sampling latent space
- [ ] Reverse direction: visual parameters → latent → melody
- [ ] Compare perceptual dialect profiles (Rothko vs Neural Abstraction mappings)

## Data Augmentation Ideas

- Transpose melodies up/down by N semitones (preserves structure, multiplies data)
- Tempo scaling (stretch/compress beat durations)
- Sequence reversal (retrograde)
- Note-level dropout (random rest insertion)
