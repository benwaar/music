# Next Steps

## Now: Data Pipeline (Phase 1)

- [ ] Create `prism/` package with `__init__.py`
- [ ] `prism/data/loader.py` — load all melody JSONs from `data/melodies/`
- [ ] `prism/data/encoder.py` — encode note sequences as tensors
  - Pitch: map note names to MIDI integers (C4=60, Rest=-1)
  - Duration: float beats
  - Result: `(N, 2)` tensor per melody (pitch, duration)
- [ ] `prism/data/labels.py` — encode analysis fields as label vectors
- [ ] `prism/data/dataset.py` — PyTorch Dataset with padding/truncation
- [ ] Tests for each module
- [ ] `pyproject.toml` with torch, pytest, mypy dependencies
