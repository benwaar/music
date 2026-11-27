# Explainers

Documentation for each concept and milestone in chant.

## M1 — Dataset: text-to-note-table pairs

### 1. Data Survey

See [../docs/m1-data-survey.md](../docs/m1-data-survey.md) — what's in drift's chip-tune archive, how much, and what metadata each format carries.

### 2. Note Table Schema

See [note-table-schema.md](note-table-schema.md) — the canonical data structure all parsers output. Three dataclasses: `TrackMetadata`, `NoteEvent`, `NoteTable`.

### 3. Parsers

Five parsers extract metadata from drift's chip-tune archive:
- **SID** — fixed-offset binary header, Latin-1 encoding, MOS6581/8580 chip detection
- **AY** — relative-pointer header, falls back to dirname/filename for blank fields
- **MOD** — title + 31 instrument names + magic tag for channel count
- **XM** — header with module name, tracker, channels, instruments, BPM
- **VGM/VGZ** — GD3 UTF-16LE tags, gzip decompression, chip clock detection

### 4. Dataset

See [m1-dataset.md](m1-dataset.md) — how captions are generated, the JSONL output format, train/val split, and corpus stats (2,684 tracks).

## M2 — LoRA adapter for text-conditioned sequence generation

### 5. LoRA Fine-Tuning

See [lora-training.md](lora-training.md) — what LoRA is, how it attaches to SmolLM2-360M, the training format (prompt/completion with label masking), the training loop, and checkpoint handling. Includes analogies for C and TypeScript developers.

### 6. Libraries Reference

See [libraries.md](libraries.md) — every library function used in the project, organised by package.

### 7. Python Concepts

See [python-concepts.md](python-concepts.md) — Python patterns that would be unfamiliar to C or TypeScript developers: dataclasses, gradient tracking, context managers, generator functions, label masking.

### 8. Inference Pipeline

`chant/generate.py` — load trained adapter, generate note sequences from text prompts, decode to NoteTable. Supports single generation (`generate_sequence`) and batch (`generate_batch`). CLI: `python -m chant.generate "description"` or `--from-val N` for held-out examples.

### 9. Validation Suite

`chant/validate.py` — structural checks on generated output: pitch range (20–20,000 Hz), duration (>0, ≤30s), channel (0–31), variety (not all identical). `validate_token_string` parses and validates in one call. `compare_conditioned_vs_unconditioned` measures diversity metrics for conditioned vs random generation.

## M3 — Evaluation pipeline

### 10. Musical Coherence Metrics

`chant/metrics.py` — four measures that go beyond structural validity to assess musical quality: pitch entropy (Shannon entropy of pitch distribution), rhythm regularity (coefficient of variation of durations), channel balance (normalised entropy of channel usage), repetition score (fraction of consecutive identical events).

### 11. Batch Evaluation

`chant/evaluate.py` — run the trained model across all held-out val examples, validate each, compute musical coherence metrics, aggregate into an `EvaluationReport` saved as JSON. CLI: `python -m chant.evaluate`.

### 12. Conditioned vs Unconditioned Comparison

`chant/compare.py` — generate sequences with real captions and a generic prompt, compare diversity metrics, report whether conditioning helps. CLI: `python -m chant.compare`.

### 13. Audio Rendering (MIDI Pipeline)

`chant/render.py` — convert NoteEvents to a standard MIDI file (raw bytes, no library deps). Includes CC messages for waveform (CC 70), volume (CC 7), and duty cycle (CC 71) metadata — ignored by the current 1-bit engine but preserved for future multi-engine support. The MIDI file is passed to `synth/chant-host`, a Rust binary that reads MIDI via `midly`, maps Hz→Z80 periods, and renders through the `eno-state-zx` crate's beeper engine. Pipeline: `NoteEvents → MIDI → chant-host → eno-state-zx → WAV`. CLI: `python -m chant.render "description" -o output.wav`.

### 14. Post-Generation Fixups

`chant/generate.py:_fixup_events()` — clamps generated event fields to valid ranges after decode. Currently handles channel numbers that exceed hardware limits (wraps via modulo). The model occasionally generates channel 32 from 1-indexed training data — clamping is correct behaviour, not lossy.

### 15. Quality Gate Results

Two rounds of evaluation on the 66-example val set. Baseline: 68.2% pass rate. After channel clamp + repetition penalty (1.1): 80.3%. Conditioning produces longer sequences with more channels but doesn't yet improve pitch diversity. 4/5 val examples render to playable beeper WAV audio.
