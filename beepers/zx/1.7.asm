; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.
; Current exercise: 1.7 (note table)

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

SENTINEL EQU 0xFF           ; end-of-table marker

    ; --- beeper engine starts here ---
    ;
    ; Register allocation:
    ;   A  = speaker state (XOR / OUT)
    ;   B  = inner duration counter (0 = 256 toggles)
    ;   C  = outer duration counter (from table)
    ;   D  = period countdown (decrements each tick)
    ;   E  = period value (constant per note, reloads D)
    ;   HL = note table pointer

    DI                  ; disable interrupts                                  4 T
    LD HL, note_table   ; point to start of note data                        10 T

next_note:
    LD A, (HL)          ; load duration byte from table                       7 T
    CP SENTINEL         ; is it 0xFF? (subtracts but doesn't change A)        7 T
    JR Z, done          ; sentinel found — end of tune                       12/7 T
    LD C, A             ; C = outer duration counter                          4 T
    INC HL              ; advance to period byte                              6 T
    LD E, (HL)          ; E = period value (kept for reloading D)             7 T
    INC HL              ; advance to next note entry                          6 T
    LD B, 0             ; inner duration counter (0 = 256)                    7 T
                        ; B counts 256 toggles (~0.2s), C multiplies it
                        ; total note length = C × 256 toggles
    LD D, E             ; D = period countdown (first load)                   4 T
    XOR A               ; reset speaker state to OFF                          4 T

loop:
    DEC D               ; count down the period                              4 T
    JR NZ, loop         ; not zero yet — keep counting                      12 T (taken)

    ; --- toggle (D hit zero) ---
    LD D, E             ; reload period from E                                4 T
    XOR 0x10            ; flip bit 4 (speaker toggle)                        7 T
    OUT (0xFE), A       ; send to speaker                                   11 T

    ; --- duration tracking ---
    DEC B               ; count this toggle (inner)                          4 T
    JR NZ, loop         ; 256 toggles not done — keep going                 12 T (taken)

    DEC C               ; one group of 256 done (outer)                      4 T
    JR Z, next_note     ; note finished — load next from table              12/7 T

    LD B, 0             ; reload inner counter (0 = 256)                     7 T
    JR loop             ; next group                                        12 T

done:
    HALT                ; tune finished — silence (DI active, CPU stops)

; --- note table: pairs of (duration, period), ended by 0xFF ---
; duration = how long (C × 256 toggles). period = pitch (smaller = higher).

note_table:
    DEFB 3, 120         ; low note,  medium length
    DEFB 3, 100         ; slightly higher
    DEFB 3, 86          ; higher still
    DEFB 3, 72          ; even higher
    DEFB 3, 60          ; high note
    DEFB 6, 86          ; back to middle, held longer
    DEFB 0xFF           ; end of tune

; T-state analysis (exercise 1.7):
;   inner period loop (D not zero): DEC D (4) + JR NZ (12) = 16 T
;   toggle path (D=0, B≠0): DEC D (4) + JR NZ (7) + LD D,E (4) + XOR (7)
;       + OUT (11) + DEC B (4) + JR NZ (12) = 49 T
;   half-cycle = ((period-1) × 16) + 49 T
;   for period=86: (85 × 16) + 49 = 1409 T
;   full cycle = 2 × 1409 = 2818 T
;   freq = 3,500,000 / 2818 ≈ 1242 Hz

scr_data:
    INCBIN "screen.scr"
