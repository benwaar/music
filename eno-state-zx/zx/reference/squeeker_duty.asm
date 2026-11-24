; squeeker_duty.asm — duty cycle via accumulator threshold (Squeeker family)
;
; Source: Squeeker Plus by utz (based on Squeeker by zilogat0r)
;         github.com/utz82/ZX-Spectrum-1-Bit-Routines/squeekerplus
; Licence: MIT
;
; Technique: 16-bit accumulator overflow + duty threshold comparison.
; The duty threshold controls what fraction of the waveform is HIGH.
;
; This is the modern demoscene approach — same principle as sp83's
; explicit hi/lo periods, but implemented as a threshold comparison
; on the accumulator's high byte. This allows per-sample duty changes
; (envelopes) and efficient multi-channel mixing.
;
; Simplified to 1 channel for study. Original has 4 channels.
;
; Key insight: `ADD A, H` where A = duty threshold.
;   - If H is below (0x100 - duty), no carry → speaker LOW
;   - If H is above (0x100 - duty), carry → speaker HIGH
;   - duty = 0x80 → 50% square wave
;   - duty = 0x40 → 25% thin pulse (quieter)
;   - duty = 0xC0 → 75% fat pulse (louder)
;
; Entry: standalone demo — plays a note with sweeping duty cycle.

    ORG     0x8000

NOTE_FREQ   EQU 0x0600      ; frequency divider (16-bit, higher = higher pitch)
START_DUTY  EQU 0x80        ; starting duty cycle (0x80 = 50%)
TIMER       EQU 0x00        ; outer timer (0 = 256 iterations)

START:
    DI

    ; --- Initialise ---
    LD      HL, 0           ; accumulator (16-bit phase)
    LD      DE, NOTE_FREQ   ; frequency divider
    LD      C, START_DUTY   ; duty threshold

    ; Inner timer
    LD      B, TIMER

PLAY_LOOP:
    ; --- Accumulator step ---
    ADD     HL, DE          ; HL += freq divider (overflows at 16-bit boundary)

    ; --- Duty cycle comparison ---
    LD      A, C            ; A = duty threshold
    ADD     A, H            ; add accumulator high byte
                            ; carry set when H > (0x100 - duty)
    SBC     A, A            ; A = 0x00 (no carry) or 0xFF (carry)
    AND     0x10            ; mask to EAR bit only
    OUT     (0xFE), A       ; output to speaker

    ; --- Loop ---
    DJNZ    PLAY_LOOP       ; 256 iterations per "frame"

    ; --- Duty envelope: sweep duty down each frame ---
    DEC     C               ; thinner pulse each frame
    LD      A, C
    CP      0x10            ; stop at ~6% duty (near silent)
    JR      NC, PLAY_RESET
    LD      C, START_DUTY   ; reset to 50% for next sweep

PLAY_RESET:
    LD      B, TIMER        ; reload timer
    JP      PLAY_LOOP
