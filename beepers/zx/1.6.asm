; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.
; Current exercise: 1.6 (duration counter)

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

PERIOD   EQU 86             ; pitch: 86 ≈ A4 (440 Hz). 43 = A5, 171 = A3.
DURATION EQU 4              ; note length: total toggles = DURATION × 256
                            ; 4 × 256 = 1024 toggles ≈ 0.4s at period 86

    ; --- beeper engine starts here ---

    DI                  ; disable interrupts — no 50Hz tick messing with timing
    XOR A               ; zero A (A XOR A = 0) — clean speaker state

    LD C, DURATION      ; outer duration counter                             7 T
    LD B, 0             ; inner duration counter — 0 means 256!              7 T
                        ; (DEC B wraps 0→255, counts 256 times to zero)
    LD D, PERIOD        ; initial period load                                7 T

loop:
    DEC D               ; count down the period                              4 T
    JR NZ, loop         ; not zero yet — keep counting                      12 T (taken)

    ; --- toggle (D hit zero) ---
    LD D, PERIOD        ; reload period for next half-cycle                   7 T
    XOR 0x10            ; flip bit 4 (speaker toggle)                        7 T
    OUT (0xFE), A       ; send to speaker                                   11 T

    ; --- duration tracking ---
    DEC B               ; count this toggle (inner)                          4 T
    JR NZ, loop         ; 256 toggles not done — keep going                 12 T (taken)

    ; B hit zero — one group of 256 toggles done
    DEC C               ; count this group (outer)                           4 T
    JR Z, done          ; all groups done — stop                            12 T (taken) / 7 T (not taken)

    LD B, 0             ; reload inner counter (0 = 256 again)               7 T
    JR loop             ; next group                                        12 T

done:
    HALT                ; duration expired — silence
                        ; (DI is active so CPU stops permanently — that's fine)

; T-state analysis (exercise 1.6):
;   inner period loop (D not zero): DEC D (4) + JR NZ (12) = 16 T
;   toggle path (D=0, B≠0): DEC D (4) + JR NZ (7) + LD D (7) + XOR (7)
;       + OUT (11) + DEC B (4) + JR NZ (12) = 52 T
;   half-cycle = ((PERIOD-1) × 16) + 52 T
;   for PERIOD=86: (85 × 16) + 52 = 1412 T
;   full cycle = 2 × 1412 = 2824 T
;   freq = 3,500,000 / 2824 ≈ 1239 Hz
;
;   duration: DURATION × 256 toggles = 512 full cycles
;   note length = 512 × 2824 T = 1,445,888 T ≈ 0.41 seconds

    ; --- screen data (appended at end) ---

scr_data:
    INCBIN "screen.scr"
