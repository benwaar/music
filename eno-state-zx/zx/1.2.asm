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
    XOR 0x10            ; flip bit 4 (speaker toggle: on↔off each pass)
    OUT (0xFE), A       ; send A to port $FE — drives the speaker
    LD B, 128           ; delay counter — smaller B = higher pitch

delay:
    DJNZ delay          ; B--, loop until B=0 (13 T-states per iteration)
    JR loop             ; back to toggle — one full cycle = two toggles

    ; --- screen data (appended at end) ---

scr_data:
    INCBIN "screen.scr"
