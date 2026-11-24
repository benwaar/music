# Engine 2 Research: Pulse Width / Duty Cycle Approaches

Two reference engines compared, plus techniques from the 1-bit community.

---

## Our Reference: `sp83_duty_cycle.asm` — Static Hi/Lo Pairs (Splat!, 1983)

**Author:** Incentive Software (extracted from Splat! game binary)
**Technique:** Explicit hi_period / lo_period per note frame

```asm
NEXT_FRAME:
    LD C, (HL)          ; C = high-phase period
    LD A, 0x11
    OUT (0xFE), A       ; speaker HIGH

HI_WAIT:
    LD B, 3
    DJNZ $              ; inner delay ×3
    DEC C
    JR NZ, HI_WAIT

    INC HL
    LD C, (HL)          ; C = low-phase period
    LD A, 0x01
    OUT (0xFE), A       ; speaker LOW

LO_WAIT:
    LD B, 3
    DJNZ $
    DEC C
    JR NZ, LO_WAIT
```

**How it works:**
- Each note frame is 2 bytes: (hi_period, lo_period)
- Pitch = hi_period + lo_period (total cycle time)
- Duty cycle = hi_period / (hi_period + lo_period)
- 50% duty = square wave, <50% = thin/quiet, >50% = fat/loud
- Static per frame — no envelope, no modulation within a note
- Frame counter (DE = 216) controls total playback length

**Character:** Simple, predictable. Each frame has a fixed timbre. Volume changes by changing the ratio between notes. This is the earliest and most direct approach — a true 1983 game engine.

---

## Second Reference: Squeeker Plus (utz, based on zilogat0r's Squeeker)

**Author:** utz (demoscene), based on Squeeker by zilogat0r
**Source:** github.com/utz82/ZX-Spectrum-1-Bit-Routines/squeekerplus
**Licence:** MIT
**Technique:** Accumulator overflow with duty cycle threshold + envelopes

```asm
; Per channel, inside the sound loop:
    ADD HL, BC          ; accumulator += frequency divider (16-bit)
    LD A, duty          ; load duty threshold (self-modifying)
    ADD A, H            ; compare accumulator high byte against duty
    RL C                ; carry into output mixer
    ; ... repeat for each channel, then:
    LD A, 0x0F
    ADC A, C            ; combine all 4 channels
    OUT (0xFE), A       ; output mixed signal
```

**How it works:**
- 4 channels, each with independent frequency + duty cycle
- Frequency via 16-bit accumulator overflow (ADD HL, BC) — not period counter
- Duty cycle via threshold comparison: `ADD A, H` where A = duty value
  - duty = 0x80 → 50% (square wave)
  - duty = 0x40 → 25% (thin pulse, quieter)
  - duty = 0xC0 → 75% (fat pulse, louder)
- **Duty envelopes**: between notes, the engine reads an envelope table that modifies the duty threshold over time → timbre sweeps
- 4 channels mixed into a single OUT via carry chain (RL C / ADC)

**Character:** Rich, evolving timbres. Each channel can sweep from thin to fat within a single note. The duty envelope is what makes Squeeker-family engines sound musical rather than mechanical.

---

## Key Difference

| Aspect | sp83 (ours) | Squeeker Plus (utz) |
|--------|-------------|---------------------|
| Era | 1983 (commercial game) | 2016 (demoscene) |
| Channels | 1 | 4 |
| Duty cycle control | Static per frame (2 bytes: hi, lo) | Dynamic via threshold + envelope |
| Frequency method | Period counter (DEC C, inner DJNZ) | 16-bit accumulator overflow (ADD HL, BC) |
| Timbre over time | Changes only between frames | Sweeps within a note via envelope |
| Data format | 2 bytes/frame (hi_period, lo_period) | Freq + duty + envelope pointer per channel |
| Volume control | Implicit (duty ratio) | Same mechanism, but with envelope automation |
| Complexity | ~20 instructions | ~200+ instructions (4ch + envelopes + drums) |

---

## The Two PWM Families (from utz's tutorial)

The 1-bit community recognises two fundamentally different approaches:

### 1. Period-Counter PWM (sp83 style)
- Explicit HIGH wait loop + LOW wait loop
- Duty cycle = hi_count / (hi_count + lo_count)
- Simple, direct, easy to understand
- Used in early commercial games (Splat!, and many others)
- Good bass, clean square waves

### 2. Accumulator-Threshold PWM (Squeeker style)
- 16-bit accumulator overflows at a rate determined by frequency divider
- Duty cycle controlled by comparing accumulator against a threshold
- `CP duty; SBC A,A` gives 0x00 or 0xFF depending on where in the cycle
- Allows duty cycle to change per-sample (envelopes, modulation)
- Used in demoscene engines (Squeeker, Phaser, quattropic, Pindsvin)
- Better for multi-channel mixing (each channel is a few instructions)

### Why both matter for learning

sp83 teaches the **concept** of duty cycle in the most direct way — you literally write the HIGH time and LOW time as separate bytes. It's visible, countable, and maps to the waveform.

Squeeker teaches the **technique** used by all modern 1-bit engines — accumulator + threshold. This is the same approach that Engines 1 already uses for 2ch interleave (XOR toggle), but with a duty parameter added.

---

## Additional Techniques (from utz Part 11)

**SID Sound:** Duty cycle sweep in sync with the oscillator. Each time the accumulator overflows, the duty threshold increments/decrements. Creates the classic C64-style "boing" timbre. Costs only 4 extra cycles.

**Earth Shaker:** Continuous duty modulation within the sound loop — creates chords or "phatness" depending on the modulation rate vs oscillator frequency.

**Duty Modulation:** A second oscillator controls when the duty threshold updates. Allows harmonic control (octave overtones/undertones) or complex timbral evolution.

---

## Recommendation for Engine 2 Exercises

The plan (exercises 2.1–2.14) already follows the right structure — building sp83-style period-counter PWM. For the second reference:

1. **Save a simplified Squeeker duty-cycle core** as `reference/squeeker_duty.asm`
2. **Compare side-by-side:**
   - `sp83_duty_cycle.asm` = static hi/lo pairs (concept)
   - `squeeker_duty.asm` = accumulator + threshold + envelope (technique)
3. **Key learning:** same principle (varying hi/lo ratio), different implementation (explicit periods vs threshold comparison)

The SID Sound and Duty Modulation techniques are worth mentioning in the explainer as where this leads (Engine 4 territory).

---

## Sources

- Splat! (Incentive Software, 1983) — extracted by dig from sp83.tap
- Squeeker Plus (utz, based on zilogat0r) — github.com/utz82/ZX-Spectrum-1-Bit-Routines
- utz, "How to Write a 1-Bit Music Routine" Parts 7, 11 — randomflux.info/1bit
- alfishe, "Beeper Synthesis" — github.com/alfishe/speccy-bootcamp
- Knowledge corpus: `z80-beeper/beeper_concept_duty_cycle`, `z80-beeper/beeper_engine_sp83_duty_cycle`, `z80-beeper/squeekerplus`
