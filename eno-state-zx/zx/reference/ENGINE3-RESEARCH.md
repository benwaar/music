# Engine 3 Research: Noise & SFX Approaches

Two reference engines compared, plus techniques from the 1-bit community.

---

## Our Reference: `noise_drum.asm` — PRNG Burst

**Author:** Based on Shiru's "el cheapo" PRNG
**Technique:** Linear congruential generator drives speaker toggles

```
ADD HL, DE    ; HL += 0x2157 (wraps 16-bit)
RLC H         ; rotate high byte left
AND 0x10      ; extract bit 4 → speaker
OUT (0xFE), A
```

**How it works:**
- PRNG runs in a tight loop, outputting a pseudo-random bit to the speaker
- PITCH delay between outputs controls noise frequency (hi-hat vs kick)
- BURST_LEN controls hit duration (40=click, 80=hit, 160=sustained)
- Gap loop adds silence between hits
- Standalone — does NOT mix with tone channels

**Character:** Broadband noise burst. Convincing percussion but interrupts any melody.

---

## Second Reference: quattropic `noiseCore` — In-Loop Noise Channel

**Author:** utz (2015), from ZX-Spectrum-1-Bit-Routines
**Technique:** RLC H inside a 4-channel pulse-interleave engine

```
; Inside the main sound loop, channel 1 becomes noise:
ADD HL, DE    ; accumulator step (DE = 0x2174 for noise)
RLC H         ; ← this single instruction converts tone → noise
LD A, H
CP duty       ; duty threshold comparison
SBC A, A      ; → 0x00 or 0xFF
AND 0x10
OUT (0xFE), A
```

**How it works:**
- Same `RLC H` trick as noise_drum, but embedded in the multi-channel sound loop
- Channel 1 plays noise while channels 2–4 continue playing tones
- The duty cycle threshold provides **fake volume control** for the noise
- Frequency divider DE must be a specific value (~0x2174) for convincing noise
- Switching between `noiseCore` and `regularCore` is data-driven (flag byte per row)

**Character:** Noise mixed with up to 3 tone channels simultaneously. No interruption.

---

## Key Difference

| Aspect | noise_drum (ours) | quattropic (utz) |
|--------|-------------------|-------------------|
| Mixing | Standalone — pauses music | Inline — noise + tones play together |
| PRNG | LCG: `ADD HL,DE; RLC H` | Same `RLC H` trick, inside interleave loop |
| Pitch control | Delay loop between outputs | Frequency divider value (limited) |
| Volume control | None (burst is full volume) | Duty cycle threshold fakes volume |
| Channels during noise | 0 (music stops) | 3 tone + 1 noise |
| Complexity | Simple, 20 lines | Complex, part of 4ch engine |
| Use case | Sound effects, drum breaks | Background percussion under melody |

---

## Third Technique: Interrupting Click Drum (utz tutorial Part 6)

**Technique:** Read bytes from ROM as pseudo-random data

```
; HL points into ROM (or any data area)
drumloop:
  LD A, (HL)     ; read byte from ROM
  AND 0x10       ; extract bit 4
  OUT (0xFE), A  ; output to speaker
  INC HL         ; next byte
  DJNZ drumloop  ; B = drum length
```

**How it works:**
- Uses ROM contents as a source of "random" data
- Very short bursts (a few hundred T-states) squeezed between tone frames
- Music pauses briefly but resumes so fast the listener doesn't notice
- Different ROM addresses produce different timbres
- Cheapest possible drum — 5 instructions

**Character:** Quick percussive click. Used in many commercial games.

---

## Recommendation for Engine 3 Exercises

Our plan already has the right structure. For the second reference comparison:

1. **Save quattropic's noise technique** as `reference/quattropic_noise.asm` — extracted just the noise core
2. **Compare side-by-side:**
   - `noise_drum.asm` = standalone PRNG burst (our approach)
   - `quattropic_noise.asm` = inline noise channel (utz's approach)
3. **Key learning:** same `RLC H` trick, but the difference is WHERE it runs — standalone vs inside the multi-channel loop

The interrupting click drum is worth mentioning in the explainer as the simplest possible technique (read ROM bytes as noise), but it's too primitive for a full reference engine.

---

## Sources

- Shiru's "el cheapo" PRNG — used in numerous beeper engines
- utz, quattropic (2015) — github.com/utz82/ZX-Spectrum-1-Bit-Routines
- utz, "How to Write a 1-Bit Music Routine" Parts 6, 11 — randomflux.info/1bit
- Knowledge corpus: `z80-beeper/beeper_engine_noise_drum`, `z80-beeper/quattropic_1-2`
