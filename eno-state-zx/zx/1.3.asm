; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

    ; --- beeper engine starts here ---

    DI                  ; disable interrupts — no 50Hz tick messing with timing
    XOR A               ; zero A (A XOR A = 0) — clean speaker state
                        ; A = accumulator, the Z80's main working register

loop:
    XOR 0x10            ; flip bit 4 (speaker toggle: on↔off each pass)    7 T
    OUT (0xFE), A       ; send A to port $FE — drives the speaker         11 T
    LD B, 128           ; delay counter — smaller B = higher pitch          7 T

delay:
    DJNZ delay          ; B--, loop until B=0                    127×13 + 8 = 1659 T
    JR loop             ; back to toggle                                   12 T

; T-state analysis (exercise 1.3):
;   half-cycle = 7 + 11 + 7 + 1659 + 12 = 1696 T
;   full cycle = 2 × 1696 = 3392 T
;   freq = 3,500,000 / 3392 ≈ 1032 Hz (roughly C6)

    ; --- screen data (appended at end) ---

scr_data:
    INCBIN "screen.scr"
