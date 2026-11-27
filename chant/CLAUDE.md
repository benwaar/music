# chant — Text-to-Chiptune via LoRA Fine-Tuning

Describe a chip-tune in words, generate note tables that beepers can play.
Research project — one milestone at a time, document as you go.

## Project layout

```
_data/            # symlink to drift/_data — not committed
chant/            # Python package
  schema.py       #   canonical note table schema
  caption.py      #   text caption generator
  build_dataset.py #  parse all files → train/val JSONL
  build_training.py # tokenise dataset → prompt/completion pairs
  tokeniser.py    #   encode/decode note sequences ↔ token strings
  train.py        #   LoRA fine-tuning pipeline (load, attach, train, save)
  generate.py     #   inference — text prompt → NoteTable
  validate.py     #   structural validation of generated sequences
  evaluate.py     #   batch evaluation + metrics report
  metrics.py      #   musical coherence metrics (entropy, rhythm, balance)
  compare.py      #   conditioned vs unconditioned comparison
  render.py       #   NoteEvents → MIDI → chant-host → WAV
  parsers/        #   format-specific parsers (SID, AY, MOD, XM, VGM)
models/           # committed model artifacts
  lora_adapter/   #   trained LoRA adapter (6.5MB, SmolLM2-360M base)
synth/            # Rust offline MIDI host (chant-host binary)
  Cargo.toml      #   depends on eno-state-zx from crates.io
  src/main.rs     #   MIDI → Z80 periods → beeper engine → WAV
tests/            # unit + integration tests
explainers/       # docs per milestone (the teaching part)
docs/             # data survey, technical notes
```

## Quick start

```bash
bash setup.sh                    # pyenv, venv, deps, ollama models, drift data symlink
python -m chant.build_dataset    # parse corpus → _data/dataset/train.jsonl + val.jsonl
python -m chant.build_training   # tokenise → _data/dataset/training/ + HuggingFace Dataset
python -m chant.train            # LoRA fine-tune → _data/chant_checkpoints/lora_adapter/
python -m chant.generate "A slow 4-channel MOD"  # generate from text prompt
python -m chant.train --quality-gate              # validate checkpoint quality
python -m chant.evaluate                          # batch eval → JSON report
python -m chant.compare --num-samples 10          # conditioned vs unconditioned
python -m chant.render "A slow MOD" -o out.wav    # generate + render to WAV
python -m pytest                 # 308 tests
```

## Tech stack

- Python 3.11+ (pyenv)
- PyTorch (LoRA fine-tuning)
- Ollama (local model inference — llama3.2:1b base, smollm2:1.7b for fast iteration)
- Depends on: drift (chip-tune archive), eno-state-zx (beeper synth crate, crates.io)

## Milestones

See [NEXT.md](NEXT.md) for current progress.

- **M1** — Dataset: text-to-note-table pairs (complete — 2,684 tracks, 5 formats)
- **M2** — LoRA adapter for text-conditioned sequence generation (planned — start with Phase A)
- **M3** — Evaluation pipeline
- **M4** — Playback and demo

## Working conventions

- No committed data. `_data/` is a symlink to drift's archive.
- No model checkpoints in the repo. Save to `_data/checkpoints/` locally.
- One explainer doc per milestone gate — see [explainers/](explainers/).
- Tests live alongside the module they test.
- Conventional commits. AI attribution on every commit.
- Study mode: every milestone updates code, tests, AND docs.
- **Parallel agents for independent work.** NEXT.md marks steps that can run as parallel sonnet agents. Dispatch them simultaneously, then integrate/test/commit from the coordinator. Each agent writes to its own files — no overlap.
