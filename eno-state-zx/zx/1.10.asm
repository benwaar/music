; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.
; Current exercise: 1.10 (compared against reference/1ch_tone.asm)

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

SENTINEL EQU 0xFF           ; end-of-table marker

    ; --- main program ---

    DI                  ; disable interrupts                                  4 T
    LD HL, scale_up_down ; point to tune data                                10 T
    CALL play_tune      ; play the tune, then return here                    17 T
    HALT                ; done — CPU stops (DI active)

; =====================================================================
; play_tune — 1ch tone engine (compared against reference/1ch_tone.asm)
;
; Entry: HL = address of note table (pairs of duration, period; 0xFF sentinel)
; Exit:  returns when sentinel reached
; Clobbers: A, B, C, D, E
;
; Differences from reference:
;   - Reference uses IY for table pointer; we use HL + E (no IY needed)
;   - Reference does OUT every iteration; we OUT only on toggle (fewer OUTs,
;     same pitch accuracy since the inner loop timing is constant either way)
;   - We adopted XOR 0x18 from reference (drives EAR+MIC = louder)
;
; Register allocation:
;   A  = speaker state (XOR / OUT)
;   B  = inner duration counter (0 = 256 toggles)
;   C  = outer duration counter (from table)
;   D  = period countdown (decrements each tick)
;   E  = period value (constant per note, reloads D)
;   HL = note table pointer (advances through entries)
; =====================================================================

play_tune:

.next_note:
    LD A, (HL)          ; load duration byte from table                       7 T
    CP SENTINEL         ; is it 0xFF?                                         7 T
    RET Z               ; sentinel found — return to caller                  11/5 T
    LD C, A             ; C = outer duration counter                          4 T
    INC HL              ; advance to period byte                              6 T
    LD E, (HL)          ; E = period value (kept for reloading D)             7 T
    INC HL              ; advance to next note entry                          6 T
    LD B, 0             ; inner duration counter (0 = 256)                    7 T
                        ; B counts 256 toggles (~0.2s), C multiplies it
                        ; total note length = C × 256 toggles
    LD D, E             ; D = period countdown (first load)                   4 T
    XOR A               ; reset speaker state to OFF                          4 T

.loop:
    DEC D               ; count down the period                              4 T
    NOP                 ; timing padding — slows the loop so lower            4 T
    NOP                 ; notes fit in an 8-bit period register               4 T
    JR NZ, .loop        ; not zero yet — keep counting                      12 T (taken)
                        ; inner loop = 24 T per iteration

    ; --- toggle (D hit zero) ---
    LD D, E             ; reload period from E                                4 T
    XOR 0x18            ; flip bits 3+4 (EAR+MIC — louder than 0x10)         7 T
    OUT (0xFE), A       ; send to speaker                                   11 T

    ; --- duration tracking ---
    DEC B               ; count this toggle (inner)                          4 T
    JR NZ, .loop        ; 256 toggles not done — keep going                 12 T (taken)

    DEC C               ; one group of 256 done (outer)                      4 T
    JR Z, .next_note    ; note finished — load next from table              12/7 T

    LD B, 0             ; reload inner counter (0 = 256)                     7 T
    JR .loop            ; next group                                        12 T

; --- note data: D major scale up and down ---
;
;   Note  Freq(Hz)  Period    (period ≈ 1,750,000 / (freq × 24))
;   D4    293.66    248
;   E4    329.63    221
;   F#4   369.99    197
;   G4    392.00    186
;   A4    440.00    166
;   B4    493.88    148
;   C#5   554.37    132
;   D5    587.33    124
;   REST  —         0

scale_up_down:
    ; ascending
    DEFB 3, 248         ; D4
    DEFB 3, 221         ; E4
    DEFB 3, 197         ; F#4
    DEFB 3, 186         ; G4
    DEFB 3, 166         ; A4
    DEFB 3, 148         ; B4
    DEFB 3, 132         ; C#5
    DEFB 6, 124         ; D5 (held)
    ; descending
    DEFB 3, 124         ; D5
    DEFB 3, 132         ; C#5
    DEFB 3, 148         ; B4
    DEFB 3, 166         ; A4
    DEFB 3, 186         ; G4
    DEFB 3, 197         ; F#4
    DEFB 3, 221         ; E4
    DEFB 6, 248         ; D4 (held)
    DEFB 0xFF           ; end of tune

; T-state analysis (exercise 1.10):
;   inner period loop: DEC D (4) + NOP (4) + NOP (4) + JR NZ (12) = 24 T
;   toggle path: DEC D (4) + NOP (4) + NOP (4) + JR NZ (7)
;       + LD D,E (4) + XOR (7) + OUT (11) + DEC B (4) + JR NZ (12) = 57 T
;   half-cycle = ((period-1) × 24) + 57 T
;   freq = 3,500,000 / (2 × ((period-1) × 24 + 57))

scr_data:
    INCBIN "screen.scr"
