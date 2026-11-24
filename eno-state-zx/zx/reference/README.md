# Beepers — Reference Beeper Engines

Minimal, standalone Z80 beeper engines extracted and rebuilt from real games via the Rosetta POC pipeline. Each file is a complete, assembler-ready source — pasmo-compatible, ORG 0x8000, no dependencies.

These are the output of: binary → dig scan → extract → analyse → rewrite. The originals live in game ROMs; these are clean reconstructions that prove we understood the algorithm.

## Catalogue

| File | Channels | Technique | Source | Size |
|------|----------|-----------|--------|------|
| `1ch_tone.asm` | 1 | Single period counter + note table | Hand-written (simplest possible) | 79 bytes |
| `2ch_interleave.asm` | 2 | Dual-tone pulse interleave (XOR toggle) | mm83 title music | 344 bytes |
| `sp83_duty_cycle.asm` | 1 | Variable duty cycle (2 bytes/frame: hi+lo period) | Splat! 1983 (sp83) | 474 bytes |
| `noise_drum.asm` | 1 | PRNG-driven toggle (el cheapo by Shiru) | Hand-written | 37 bytes |
| `sweep_sfx.asm` | 1 | Period decrements each cycle → rising pitch | Hand-written | 44 bytes |

## How to build

```bash
# Assemble to raw binary
pasmo --bin reference/2ch_interleave.asm output.bin

# Wrap in TAP with autorun loader
python3 -I tap.py output.bin output.tap
```

## Adding new engines

As dig scans more games (see `PREDICTIONS.md`), add each distinct engine type here:
- `3ch_interleave.asm` — when we find a 3-channel variant
- `pwm_tone.asm` — pulse width modulation with envelope (attack/decay)
- `lfo_vibrato.asm` — low-frequency oscillator nudging period once per 50Hz frame

Each file should be the minimal standalone version — just the engine + note/data table, no screen setup, no game code.
