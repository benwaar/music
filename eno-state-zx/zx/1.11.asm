; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.
; Current exercise: 1.11 (2ch structure: IY table pointer, 3-byte entries)

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

SENTINEL EQU 0xFF           ; end-of-table marker

    ; --- main program ---

    DI                  ; disable interrupts                                  4 T
    LD IY, scale_up_down ; point to tune data                                14 T
    CALL play_tune      ; play the tune, then return here                    17 T
    HALT                ; done — CPU stops (DI active)

; =====================================================================
; play_tune — 1ch tone engine (2ch table structure, ch2 loaded but unused)
;
; Entry: IY = address of note table (3-byte entries: duration, ch1_period,
;             ch2_period; 0xFF sentinel)
; Exit:  returns when sentinel reached
; Clobbers: A, B, C, D, E
;
; Differences from reference:
;   - Reference uses IY for table pointer; we now also use IY
;   - Reference does OUT every iteration; we OUT only on toggle (fewer OUTs,
;     same pitch accuracy since the inner loop timing is constant either way)
;   - We adopted XOR 0x18 from reference (drives EAR+MIC = louder)
;
; Register allocation:
;   A  = speaker state (XOR / OUT)
;   B  = inner duration counter (0 = 256 toggles)
;   C  = outer duration counter (from table)
;   D  = period countdown (decrements each tick) — loaded from (IY+1)
;   E  = ch2 period (loaded from (IY+2), unused in loop)
;   IY = note table pointer (3 bytes per entry; advance by 3 at .advance)
; =====================================================================

play_tune:

.next_note:
    LD A, (IY+0)        ; load duration byte from table                      19 T
    CP SENTINEL         ; is it 0xFF?                                          7 T
    RET Z               ; sentinel found — return to caller                 11/5 T
    LD C, A             ; C = outer duration counter                           4 T
    LD D, (IY+1)        ; D = ch1 period (period countdown, first load)      19 T
    LD E, (IY+2)        ; E = ch2 period (loaded but unused in loop)         19 T
    LD B, 0             ; inner duration counter (0 = 256)                    7 T
                        ; B counts 256 toggles (~0.2s), C multiplies it
                        ; total note length = C × 256 toggles
    XOR A               ; reset speaker state to OFF                          4 T

.loop:
    DEC D               ; count down the period                              4 T
    NOP                 ; timing padding — slows the loop so lower            4 T
    NOP                 ; notes fit in an 8-bit period register               4 T
    JR NZ, .loop        ; not zero yet — keep counting                      12 T (taken)
                        ; inner loop = 24 T per iteration

    ; --- toggle (D hit zero) ---
    LD D, (IY+1)        ; reload period from table                           19 T
    XOR 0x18            ; flip bits 3+4 (EAR+MIC — louder than 0x10)         7 T
    OUT (0xFE), A       ; send to speaker                                   11 T

    ; --- duration tracking ---
    DEC B               ; count this toggle (inner)                          4 T
    JR NZ, .loop        ; 256 toggles not done — keep going                 12 T (taken)

    DEC C               ; one group of 256 done (outer)                      4 T
    JR Z, .advance      ; note finished — advance table pointer            12/7 T

    LD B, 0             ; reload inner counter (0 = 256)                     7 T
    JR .loop            ; next group                                        12 T

.advance:
    INC IY              ; advance past duration byte                         10 T
    INC IY              ; advance past ch1 period byte                       10 T
    INC IY              ; advance past ch2 period byte                       10 T
    JR .next_note       ; load next note                                     12 T

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
;
; 3-byte entries: duration, ch1_period, ch2_period
; ch2 period = ch1 period (same note, unused in this engine)

scale_up_down:
    ; ascending
    DEFB 3, 248, 248    ; D4
    DEFB 3, 221, 221    ; E4
    DEFB 3, 197, 197    ; F#4
    DEFB 3, 186, 186    ; G4
    DEFB 3, 166, 166    ; A4
    DEFB 3, 148, 148    ; B4
    DEFB 3, 132, 132    ; C#5
    DEFB 6, 124, 124    ; D5 (held)
    ; descending
    DEFB 3, 124, 124    ; D5
    DEFB 3, 132, 132    ; C#5
    DEFB 3, 148, 148    ; B4
    DEFB 3, 166, 166    ; A4
    DEFB 3, 186, 186    ; G4
    DEFB 3, 197, 197    ; F#4
    DEFB 3, 221, 221    ; E4
    DEFB 6, 248, 248    ; D4 (held)
    DEFB 0xFF           ; end of tune

; T-state analysis (exercise 1.11):
;   inner period loop: DEC D (4) + NOP (4) + NOP (4) + JR NZ (12) = 24 T
;   toggle path: DEC D (4) + NOP (4) + NOP (4) + JR NZ (7)
;       + LD D,(IY+1) (19) + XOR (7) + OUT (11) + DEC B (4) + JR NZ (12) = 72 T
;   half-cycle = ((period-1) × 24) + 72 T
;   freq = 3,500,000 / (2 × ((period-1) × 24 + 72))
;   note: toggle path is 15T longer than 1.10 (LD D,E=4T → LD D,(IY+1)=19T)
;         periods would need recalculating for exact pitch match

scr_data:
    INCBIN "screen.scr"
