# VSTi — Beeper Synth

Faithful Rust port of the Z80 beeper engines. Same algorithms, same tone tables, same sound.

## Quick start

```bash
cargo test              # run all tests
cargo run               # render D major scale → demo.wav
./play.sh               # build + open demo WAV
```

## Structure

```
vsti/
  Cargo.toml
  play.sh               — build + play demo
  src/
    tone_engine.rs      — 1ch tone engine (period-countdown, matches Z80)
    wav.rs              — WAV output helper
    lib.rs              — module wiring
    main.rs             — CLI
    reference/          — archived generic oscillator + plugin stub
```

## Engine mapping

Each Z80 engine gets a Rust port. Same period values, same integer countdown, same frequencies.

| ASM engine | Rust module | Status |
|---|---|---|
| Engine 1 — 1ch tone | `tone_engine.rs` | Done |
| Engine 1 — 2ch interleave | — | Next |
| Engine 2 — duty cycle | — | TODO |
| Engine 3 — noise, sweep | — | TODO |
| Engine 4 — envelope, LFO, accent | — | TODO |
| Engine 5 — PCM, PWM | — | TODO |

## How the port works

The Z80 runs at 3.5 MHz. Each inner loop iteration = 24 T-states. The Rust engine simulates this:

1. Each audio sample ≈ 79.4 T-states (3,500,000 / 44,100)
2. Accumulate T-states, decrement the period counter every 24T
3. Toggle on zero, reload — same logic as the Z80
4. Output: +1.0 or -1.0 (square wave from 1-bit speaker)

Same formula: `freq = 3,500,000 / (2 × ((period-1) × 24 + 57))`
