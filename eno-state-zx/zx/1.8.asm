; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.
; Current exercise: 1.8 (D major scale)

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
    NOP                 ; timing padding — slows the loop so lower            4 T
    NOP                 ; notes fit in an 8-bit period register               4 T
    JR NZ, loop         ; not zero yet — keep counting                      12 T (taken)
                        ; inner loop = 24 T per iteration (was 16 T without NOPs)

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

; --- note table: D major scale (D4 → D5) ---
; Each entry: DEFB duration, period
; period = 1,750,000 / (freq × 24)  (simplified formula)
;
;   Note  Freq(Hz)  Period  Check: 3500000/(2×(P-1)×24+57) ≈ Hz
;   D4    293.66    248     → 293.8 Hz ✓
;   E4    329.63    221     → 329.2 Hz ✓
;   F#4   369.99    197     → 370.0 Hz ✓
;   G4    392.00    186     → 391.8 Hz ✓
;   A4    440.00    166     → 438.6 Hz ✓
;   B4    493.88    148     → 492.2 Hz ✓
;   C#5   554.37    132     → 551.4 Hz ✓
;   D5    587.33    124     → 588.9 Hz ✓

note_table:
    DEFB 3, 248         ; D4
    DEFB 3, 221         ; E4
    DEFB 3, 197         ; F#4
    DEFB 3, 186         ; G4
    DEFB 3, 166         ; A4
    DEFB 3, 148         ; B4
    DEFB 3, 132         ; C#5
    DEFB 6, 124         ; D5 (held longer)
    DEFB 0xFF           ; end of tune

; T-state analysis (exercise 1.8):
;   inner period loop (D not zero): DEC D (4) + NOP (4) + NOP (4) + JR NZ (12) = 24 T
;   toggle path (D=0, B≠0): DEC D (4) + NOP (4) + NOP (4) + JR NZ (7)
;       + LD D,E (4) + XOR (7) + OUT (11) + DEC B (4) + JR NZ (12) = 57 T
;   half-cycle = ((period-1) × 24) + 57 T
;
;   Frequency formula:
;     freq = 3,500,000 / (2 × half-cycle)
;     freq = 3,500,000 / (2 × ((period-1) × 24 + 57))
;     simplified: period ≈ 1,750,000 / (freq × 24)
;
;   Range with 8-bit period:
;     period=255 → ~244 Hz (B3)     lowest reachable note
;     period=1   → ~30,702 Hz       way above audible

scr_data:
    INCBIN "screen.scr"
