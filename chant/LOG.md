# Log

Completed work — what was built, key decisions, results.

## M1 — Dataset (complete)

Parsed drift's chip-tune archive into text-caption + note-table pairs.

- **5 parsers:** SID, AY, MOD, XM, VGM/VGZ — each extracts metadata from a different 80s/90s tracker format
- **2,684 tracks** with captions describing instrument, waveform, pitch, rhythm
- **Output:** `_data/dataset/train.jsonl` + `val.jsonl` (90/10 split)
- **Schema:** `NoteEvent(pitch_hz, duration_ms, channel, waveform, volume)` → `NoteTable(metadata, events)`

## M2 — LoRA adapter (complete)

Fine-tuned SmolLM2-360M with LoRA to generate note token sequences from text captions.

### Phase A — Note event extraction

Extended M1's metadata-only parsers to extract actual note sequences from MOD and XM pattern data.

- MOD: 4-byte packed notes (sample, period, effect) → pitch lookup table
- XM: variable-width compressed notes with flags → semitone table
- **659 MOD/XM tracks** with ~2.3M note events
- Enriched captions with pitch range, note count, tempo, dominant channel

### Phase B — Tokenisation

Designed a 671-token vocabulary for note sequences:

| Token | Meaning | Range |
|-------|---------|-------|
| N{midi} | Pitch | N0–N127 |
| D{ms} | Duration (10ms quant) | D10–D5000 |
| C{n} | Channel | C0–C31 |
| V{level} | Volume (8 levels) | V0–V7 |

- Fully reversible: `encode(NoteTable) → str → decode() → NoteTable`
- 588 train + 66 val prompt/completion pairs
- BPE expansion ratio: ~2.4x (each note token ≈ 2.4 BPE tokens)

### Phase C — LoRA fine-tuning

| Setting | Value |
|---------|-------|
| Base model | SmolLM2-360M (362M params, Llama arch) |
| LoRA rank | 8, alpha 16, targeting q_proj + v_proj |
| Trainable params | 819,200 (0.23% of total) |
| Training | 3 epochs, batch 1, 2048 BPE max, CPU-only |
| Time | ~35 minutes on laptop CPU |
| Final loss | 0.035 (best: 0.017) |

**Quality gate:** 10/10 parseable, 8/10 fully valid (2 had channel > 31).

**Key decision:** Per-epoch checkpointing with `--resume` flag after training crashed twice mid-run.

### Phase D — Inference + validation

- `generate.py` — text prompt → model.generate() → decode → NoteTable
- `validate.py` — structural checks (pitch, duration, channel, variety) + conditioned-vs-unconditioned comparison metrics
- End-to-end verified: caption → generate → decode → validate → valid
- **182 tests**, all passing

### Observations

Model generates valid token format but limited pitch diversity — repetitive patterns (e.g. N72 repeating across events). Expected with 588 training examples and a 360M param base. More data, data augmentation, or a larger base model would improve variety.

## M3 — Evaluation pipeline (complete)

Batch evaluation, musical coherence metrics, conditioned-vs-unconditioned comparison, audio rendering via MIDI pipeline, and two rounds of quality improvements.

### Phase A — Metrics + evaluation

Four modules built in parallel:

- **evaluate.py** — batch eval across val set. Generates per-sample, aggregates pass rate, pitch/duration/channel distributions, failure breakdown, and musical coherence metrics. Saves JSON report.
- **metrics.py** — four musical coherence measures:
  - `pitch_entropy` — Shannon entropy of pitch distribution (bits)
  - `rhythm_regularity` — coefficient of variation of durations
  - `channel_balance` — normalised entropy of channel usage (0–1)
  - `repetition_score` — fraction of consecutive identical events
- **compare.py** — generates conditioned (real caption) and unconditioned (generic prompt) sequences side by side, compares diversity metrics, reports win counts
- Metrics integrated into evaluate.py report

### Phase B — Audio rendering (MIDI pipeline)

Replaced the placeholder JSON render protocol with a standard MIDI pipeline:

- **render.py** — converts NoteEvents to MIDI file (raw bytes, no external deps), including CC metadata for waveform/volume/duty cycle. Calls `chant-host` binary to render.
- **synth/chant-host** — Rust binary using `eno-state-zx` crate (v0.1.2 from crates.io). Reads MIDI, maps Hz→Z80 periods, renders through the 1-bit beeper engine, writes WAV.
- Pipeline: `NoteEvents → MIDI → chant-host → eno-state-zx → WAV`
- The VSTi plugin stays standard (MIDI in, audio out) — no custom protocols added

**Key decision:** MIDI as the interchange format between Python and Rust. The VSTi stays a standard instrument; the offline host is a separate binary in this repo that depends on the published crate.

### Phase C — Quality improvements

Two rounds of evaluation with targeted fixes:

**Round 1 (baseline):** 68.2% pass rate (45/66)
- 12 failures: channel 32 out of range (tokeniser artefact from 1-indexed training data)
- 9 failures: all events identical (model stuck in single-note loops)

**Fixes applied:**
- Channel clamp: `_fixup_events()` in generate.py wraps channels via modulo → eliminated all 12 channel failures
- Repetition penalty: `repetition_penalty=1.1` in model.generate() → reduces single-note loops without causing early EOS

**Quality gate progression:**

| Metric | Round 1 | Round 2 (penalty=1.2) | Round 3 (penalty=1.1) |
|--------|---------|----------------------|----------------------|
| Pass rate | 68.2% (45/66) | 80.3% (53/66) | **92.4% (61/66)** |
| Channel errors | 12 | 0 | 0 |
| Identical events | 9 | 7 | 2 |
| Empty sequences | 0 | 5 | 3 |
| Duration errors | 0 | 1 | 0 |

### Phase D — Comparison + listen test

**Conditioned vs unconditioned (20 samples):** Conditioning produces longer sequences (38.4 vs 25.4 events) and uses more channels (5.55 vs 4.30) but doesn't yet improve pitch/duration diversity. Win rate: 12%.

**Listen test (5 val → WAV):** 4/5 rendered real beeper audio (2.6–13.4s). One empty (model generated no valid notes for that prompt).

### Stats

- **308 tests**, all passing
- 4 evaluation modules, 1 Rust binary (10 Rust tests), 7 Python test files
