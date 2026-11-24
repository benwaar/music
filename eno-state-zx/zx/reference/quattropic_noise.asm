; quattropic_noise.asm — noise channel from quattropic (utz, 2015)
;
; Source: github.com/utz82/ZX-Spectrum-1-Bit-Routines/quattropic
; Licence: MIT
;
; Technique: RLC H inside a pulse-interleave loop converts one tone
; channel into noise. The other channels keep playing tones.
;
; This is the same RLC H trick as noise_drum.asm, but inline —
; noise plays simultaneously with up to 3 tone channels.
;
; Extracted and simplified from quattropic's noiseCore for study.
; Original has 4 channels; this shows 2ch (1 noise + 1 tone).
;
; Key insight: the duty cycle threshold (cp #80) gives fake volume
; control over the noise — lower threshold = quieter noise.
;
; Entry: standalone demo — noise + tone together, loops forever.

    ORG     0x8000

; Frequency dividers — DE must be ~0x2174 for convincing noise
NOISE_FREQ  EQU 0x2174      ; magic value for noise (utz's recommendation)
TONE_FREQ   EQU 0x0600      ; tone channel frequency (a mid-range note)
NOISE_DUTY  EQU 0x80        ; duty threshold for noise (controls "volume")
TONE_DUTY   EQU 0x80        ; duty threshold for tone (50% = square wave)
DURATION    EQU 0x40        ; frames per note

START:
    DI

    ; --- Initialise ---
    LD      HL, 0           ; noise accumulator
    LD      DE, NOISE_FREQ  ; noise frequency divider
    LD      IX, 0           ; tone accumulator
    LD      BC, TONE_FREQ   ; tone frequency divider

    ; Outer loop: one "row" of sound
    PUSH    BC
    LD      B, DURATION
    LD      C, 0            ; inner timer (256 iterations per frame)
    POP     BC
    ; (simplified: just loop forever)

PLAY_LOOP:
    ; --- Channel 1: NOISE ---
    ADD     HL, DE          ; accumulator += freq divider
    RLC     H               ; ← the noise magic: rotates H, breaks periodicity
    LD      A, H
    CP      NOISE_DUTY      ; compare against duty threshold
    SBC     A, A            ; A = 0x00 or 0xFF
    AND     0x10            ; mask to EAR bit
    OUT     (0xFE), A

    ; --- Channel 2: TONE (normal, no RLC) ---
    ADD     IX, BC          ; accumulator += freq divider
    LD      A, IXH
    CP      TONE_DUTY       ; compare against duty threshold
    SBC     A, A            ; A = 0x00 or 0xFF
    AND     0x10            ; mask to EAR bit
    OUT     (0xFE), A

    ; --- Loop forever (demo) ---
    JP      PLAY_LOOP
