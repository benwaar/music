# Eno State ZX

A 1-bit ZX Spectrum beeper synth. Four engines built from Z80 assembly first principles, then ported to Rust as a VST3/CLAP plugin.

Same algorithms, same tone tables, same sound — the integer T-state simulation matches the real hardware.

## Engines

| # | Engine | What it does | Status |
|---|--------|-------------|--------|
| 1 | Tone | 1ch + 2ch interleave, detuned unison | done (Z80 + Rust + plugin) |
| 2 | Pulse Width | Duty cycle, fake volume, timbre control | in progress |
| 3 | Noise & SFX | PRNG percussion, pitch sweeps | planned |
| 4 | Synthesis | Envelopes, vibrato, accent | planned |

## Quick start

```bash
./setup.sh                    # install deps (pasmo, Rust, Python venv)
source .venv/bin/activate     # activate Python env

# Z80 assembly
cd zx && ./play.sh 1.1       # build + play in Fuse emulator

# Rust CLI
cd vsti && cargo test         # 14 tests
cargo run -- --demo           # render D major scale to WAV

# VST3/CLAP plugin
cargo xtask bundle eno-state-zx --features plugin
# → target/bundled/eno-state-zx.vst3
# → target/bundled/eno-state-zx.clap

# Headless test
./tools/test_plugin.py        # loads plugin, sends MIDI, renders WAV → PASS
```

## For learners

The Z80 exercises in `zx/` build each engine step by step — from a bare speaker toggle to a multi-channel synth. Reference engines in `zx/reference/` are the answer key.

- [LEARN-ASM.md](explainers/LEARN-ASM.md) — Z80 assembly quick reference
- [LEARN-AUDIO.md](explainers/LEARN-AUDIO.md) — audio and sound design concepts
- [LEARN-RUST.md](explainers/LEARN-RUST.md) — Rust quick reference
- [COMPARE-ENGINES.md](explainers/COMPARE-ENGINES.md) — Z80 vs Rust with spectrogram proof

## Knowledge corpus

The `knowledge-mcp/` directory contains an MCP server for searching Z80/Spectrum reference material (instructions, ROM routines, beeper engine techniques). See [knowledge-mcp/README.md](knowledge-mcp/README.md).

Build the corpus: `cd knowledge && ./setup.sh`

## Part of Eno State

Eno State ZX is the first in a series of synth plugins faithfully emulating classic chip sound generation.
