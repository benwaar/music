; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

PERIOD  EQU 86              ; change this one value to tune pitch
                            ; 86 ≈ A4 (440 Hz). Try 43 for A5, 171 for A3.

    ; --- beeper engine starts here ---

    DI                  ; disable interrupts — no 50Hz tick messing with timing
    XOR A               ; zero A (A XOR A = 0) — clean speaker state
                        ; A = accumulator, the Z80's main working register

    LD D, PERIOD        ; initial period load

loop:
    DEC D               ; count down the period                              4 T
    JR NZ, loop         ; not zero yet — keep counting                      12 T (taken)

    LD D, PERIOD        ; reload period — ready for next half-cycle           7 T
    XOR 0x10            ; flip bit 4 (speaker toggle)                        7 T
    OUT (0xFE), A       ; send to speaker                                   11 T
    JR loop             ; back to counting                                  12 T

; T-state analysis (exercise 1.4):
;   inner loop iteration (D not zero): DEC D (4) + JR NZ (12) = 16 T
;   when D hits zero: DEC D (4) + JR NZ (7, not taken) + LD D (7) + XOR (7) + OUT (11) + JR (12) = 48 T
;   half-cycle = (85 × 16) + 48 = 1408 T
;   full cycle = 2 × 1408 = 2816 T
;   freq = 3,500,000 / 2816 ≈ 1243 Hz
;   change D to tune: bigger D = lower pitch, smaller D = higher pitch

    ; --- screen data (appended at end) ---

scr_data:
    INCBIN "screen.scr"
