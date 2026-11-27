# Prism — CLAUDE.md

## Project

Cross-modal ML study project: autoencoder/VAE on melody data with cross-modal audio→visual mapping.

## Stack

- Python 3.11+
- PyTorch
- JSON melody data in `data/melodies/`

## Conventions

- Use `pyproject.toml` for project config (not setup.py)
- Source code in `prism/` package
- Tests in `tests/` using pytest
- Type hints on all function signatures
- Functional style preferred over classes (except PyTorch nn.Module)
- Run tests: `pytest tests/`
- Run type checks: `mypy prism/`

## Structure

```
prism/           — source package
  data/          — data loading and tensor encoding
  models/        — VAE and cross-modal head
  viz/           — latent space visualisation
tests/           — pytest tests
data/            — raw melody JSONs and suno prompts
docs/            — conceptual docs extracted from eno project
```

## Key Data

- Melody JSONs: `{ title, tempo, analysis: { mood, style, energy, movement, character, imagery, rhythm }, notes: [{ note, beats }] }`
- Note format: string pitch names (C4, F#4, Bb5, Rest) with beat duration floats
- 35 labelled files, 7 bare test fixtures excluded
