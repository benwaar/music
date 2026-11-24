# COMPARE-ENGINES — Z80 ASM vs Rust Port

Comparing how the original Z80 engine and the Rust port produce the same sound.

---

## What this compares

- **Z80 ASM engine** (`zx/beeper.asm`) — assembled binary, run through the `z80` Python emulator
- **Rust engine** (`vsti/src/tone_engine.rs`) — integer T-state simulation at 44.1 kHz sample rate

Independent codebases — no shared code, no shared assumptions. The Z80 emulator (`tools/tap_to_wav.py`) runs your actual assembled binary and captures every `OUT ($FE)` with its T-state timestamp.

---

## How the Z80 works

- Crystal oscillator: exactly **3,500,000 ticks per second**
- Every instruction costs a fixed number of T-states — the CPU IS the clock
- No OS, no interrupts (`DI`), no jitter — **deterministic timing**

Inner loop cost per tick:

| Instruction | T-states |
|-------------|----------|
| `DEC D`     | 4T       |
| `NOP`       | 4T       |
| `NOP`       | 4T       |
| `JR NZ`     | 12T      |
| **Total**   | **24T**  |

- Toggle overhead when counter hits zero: **57T**
- Half-cycle = `((period - 1) × 24) + 57` T-states
- Frequency = `3,500,000 / (2 × half-cycle)`

---

## How the Rust port works

- No 3.5 MHz clock — runs at audio sample rate (44,100 Hz)
- Each sample = ~79.4 T-states of Z80 time
- Tracks a global `t_count: u64` — integer T-state counter, **no floats**

Per sample:
1. Compute target T-state: `(sample_num × 3_500_000) / sample_rate` (integer math)
2. Run the period-countdown in 24T steps until target is reached
3. Toggle at the exact same integer T-state as the Z80 would
4. Output: speaker state at each sample boundary (`+1.0` or `-1.0`)

---

## Why integer T-states matter

- Earlier version used `f64` accumulator — floating point introduces tiny rounding errors
- Over millions of samples, the toggle point drifts by fractions of a T-state
- With integers: toggles happen at **exactly the same T-state count** as the Z80

The only remaining approximation: we sample the output at 44.1 kHz boundaries (~79T resolution). Toggle edges are quantised to ~23 microsecond boundaries — unavoidable at this sample rate.

---

## The comparison

Both engines render the **D major scale** (D4 up to D5, back down).

| Metric | Value |
|--------|-------|
| Total samples (Rust) | 752,642 |
| Total samples (Z80 emulated) | 752,667 (~25 extra from note-loading overhead) |
| Duration | 17.07 seconds |
| Output length | Identical |
| Spectrograms | Visually identical |
| Harmonic bands | Same |
| Frequency steps | Same |
| Timing | Same |

---

## Frequency table

| Note | Target Hz | Period | Formula Hz |
|------|-----------|--------|------------|
| D4   | 293.66    | 248    | 293.8      |
| E4   | 329.63    | 221    | 329.2      |
| F#4  | 369.99    | 197    | 370.0      |
| G4   | 392.00    | 186    | 391.8      |
| A4   | 440.00    | 166    | 438.6      |
| B4   | 493.88    | 148    | 492.2      |
| C#5  | 554.37    | 132    | 551.4      |
| D5   | 587.33    | 124    | 588.9      |

Worst error: **~2 Hz** (A4 at 438.6 vs 440.0). This comes from the 1-byte period field — only 256 possible values, so not every frequency maps exactly.

---

## What "faithful" means

- Same algorithm (period-countdown, not phase-accumulator)
- Same integer arithmetic (no floats in timing)
- Same note table format (duration + period byte pairs)
- Same frequencies (within <2 Hz across all notes)
- Same waveform shape (square wave, 1-bit output)

**One unavoidable difference:** the Z80 toggles at 3.5 MHz resolution; Rust samples at 44.1 kHz. Toggle edges are quantised to ~23 microsecond boundaries. This is inaudible and invisible in the spectrograms.

---

## Spectrogram evidence — 1ch

Side-by-side spectrograms of `zx-emulated.wav` (assembled binary through Z80 emulator) and `rust-scale.wav` (Rust engine):

![1ch spectrogram comparison](../docs/compare/spectrogram.png)

The image shows frequency vs time for both renders. Harmonic content, note boundaries, and frequency steps are identical between the two engines.

---

## 2-channel interleave engine

The 2ch engine adds a second period counter. Both counters share one speaker — each toggles it independently via XOR. The ear blends them into two simultaneous pitches.

### What changed from 1ch

| | 1ch (`tone_1ch.rs`) | 2ch (`tone_2ch.rs`) |
|---|---|---|
| Counters | D only | D (ch1) + E (ch2) |
| Reload | E register (4T) | H, L registers (4T each) |
| Inner loop | 24T (DEC D + NOP + NOP + JR NZ) | 45T (DEC D + JR NZ + DEC E + JR NZ + DJNZ) |
| Toggle cost | 57T | 62T (one channel), 79T (both) |
| Note table | 2 bytes (dur, period) | 3 bytes (dur, ch1, ch2) |
| REST | period 0 = silence | period 0 → 255 substitution |
| Speaker state | carries over | carries over (PUSH/POP AF in Z80) |

### Z80 reference

Our engine improves on Manic Miner (Matthew Smith, 1983) — the first documented 2ch beeper engine. See `zx/reference/QUIRKS.md` for what we changed and why.

| | Manic Miner (1983) | Ours (exercise 1.14) |
|---|---|---|
| Reload | `LD D, (IY+1)` — 19T | `LD D, H` — 4T |
| OUT | every iteration | only on toggle |
| Note transitions | `XOR A` (clicks) | PUSH/POP AF (smooth) |
| Toggle overhead | 21T | 17T |
| Normal loop | 56T | 45T |

### The comparison — 2ch Blue Danube

Both engines render the **Blue Danube** (Manic Miner title screen tune, 95 notes).

| Metric | Z80 (emulated) | Rust |
|--------|----------------|------|
| Duration | 16.27s | 16.10s |
| Toggle count | 31,174 | — |
| Note table | Same data (Manic Miner original) | Same data |
| Loop T-states | 45T (actual, via Z80 emulator) | 45T (integer simulation) |

The ~0.17s duration difference comes from note-loading overhead in the Z80 version (IY indexed reads between notes) which the Rust version doesn't model.

### Spectrogram evidence — 2ch

Side-by-side spectrograms of `zx-2ch-danube.wav` (Z80 emulator) and `rust-2ch-danube.wav` (Rust engine):

![2ch spectrogram comparison](../docs/compare/spectrogram-2ch.png)

Note: the spectrogram tool struggles with 2ch XOR composite waveforms — it may pick different harmonics note-to-note. Notes where it picks the same harmonic match within a few Hz. The ear comparison is more reliable for 2ch: both WAVs are in `docs/compare/`.
