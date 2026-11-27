# Next — M7 Eyes and Ears

## Status: COMPLETE (study edition)

M7 proven with a generic test capture from archive.org. The pipeline works end-to-end: ambient audio → diffusion → chip-tune + melody extraction. Real field recordings (photo + audio from 3 locations) left as a personal exercise.

## Test example

**Source:** CC BY-NC-ND stream recording from archive.org ([aporee_73794_86247](https://archive.org/details/aporee_73794_86247))

**Script:** `python scripts/download_test_capture.py` — downloads MP3, trims to 30s mono WAV.

**Pipeline:**
```bash
python -m drift generate --from-noise _data/captures/test/audio.wav \
    --extract-melody --voice triangle --n 1 --seed 42 \
    --output _data/generated/m7_test
```

**Committed outputs:** `docs/examples/m7_test/`
- `stream_spectrogram.png` — Mel spectrogram of generated output
- `stream_chiptune.wav` — raw diffusion output (8s)
- `stream_melody.wav` — melody-extracted triangle wave

## Personal exercise — expand with real captures

When ready, record 3 paired captures (photograph + 30s audio) from real locations:

Save to:
```
_data/captures/
  roadside/
    photo.jpg
    audio.wav       # or .m4a — script will convert
  field/
    photo.jpg
    audio.wav
  rain/
    photo.jpg
    audio.wav
```

Then run per location:
```bash
python -m drift generate --from-noise _data/captures/roadside/audio.wav \
    --extract-melody --voice triangle --n 4 --seed 42 \
    --output _data/generated/m7/roadside
```

## Production checkpoint

Same as M5/M6:
```
_data/checkpoints_m4_conditional/epoch_0010.pt
```
