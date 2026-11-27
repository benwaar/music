; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.
; Current exercise: 1.13 (PUSH/POP speaker preservation + detuned unison test)

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

SENTINEL EQU 0xFF           ; end-of-table marker

    ; --- main program ---

    DI                  ; disable interrupts                                  4 T
    LD IY, tune_data    ; point to tune data                                 14 T
    CALL play_tune      ; play the tune, then return here                    17 T
    HALT                ; done — CPU stops (DI active)

; =====================================================================
; play_tune — 2ch interleave engine (PUSH/POP speaker preservation)
;
; Entry: IY = note table (3-byte entries: duration, ch1_period, ch2_period; 0xFF sentinel)
; Exit:  returns when sentinel reached
; Clobbers: A, B, C, D, E, H, L, F (via PUSH/POP AF)
;
; Improvements over reference (mm83_minimal):
;   - OUT only on toggle (reference OUTs every iteration — redundant)
;   - Register reload: LD D,H (4T) vs LD D,(IY+1) (19T) — 15T faster
;   - Speaker carries over between notes via PUSH/POP AF (no clicks)
;   - Toggle overhead 17T vs reference's 21T — better pitch stability
;   - Detuned unison test isolates chorus shimmer before scale
;
; Register allocation:
;   A  = speaker state (XOR / OUT)
;   B  = inner duration counter (0 = 256 iterations)
;   C  = outer duration counter (from table)
;   D  = ch1 period countdown
;   E  = ch2 period countdown
;   H  = ch1 period reload (constant per note)
;   L  = ch2 period reload (constant per note)
;   IY = note table pointer (advances between notes)
; =====================================================================

play_tune:

.next_note:
    PUSH AF             ; save speaker state (A is about to be clobbered)    11 T
    LD A, (IY+0)        ; load duration byte from table                      19 T
    CP SENTINEL         ; is it 0xFF?                                         7 T
    JR Z, .done         ; sentinel found — clean up and return               12/7 T
    LD C, A             ; C = outer duration counter                          4 T
    LD D, (IY+1)        ; D = ch1 period countdown                           19 T
    LD H, D             ; H = ch1 reload (copy of period)                     4 T
    LD E, (IY+2)        ; E = ch2 period countdown                           19 T
    LD L, E             ; L = ch2 reload (copy of period)                     4 T
    LD B, 0             ; inner duration counter (0 = 256)                    7 T
    POP AF              ; restore speaker state — no click between notes     10 T

.loop:
    ; --- channel 1 ---
    DEC D               ; ch1 countdown                                       4 T
    JR NZ, .skip_d      ; not zero — skip toggle                            12/7 T
    LD D, H             ; reload ch1 from register (4T, not 19T)              4 T
    XOR 0x18            ; flip speaker (EAR+MIC)                              7 T
    OUT (0xFE), A       ; output only when state changes                     11 T
.skip_d:

    ; --- channel 2 ---
    DEC E               ; ch2 countdown                                       4 T
    JR NZ, .skip_e      ; not zero — skip toggle                            12/7 T
    LD E, L             ; reload ch2 from register (4T, not 19T)              4 T
    XOR 0x18            ; flip speaker (EAR+MIC)                              7 T
    OUT (0xFE), A       ; output only when state changes                     11 T
.skip_e:

    ; --- duration tracking ---
    DJNZ .loop          ; 256 iterations not done — keep going               13/8 T

    DEC C               ; one group of 256 done (outer)                      4 T
    JR NZ, .loop        ; more groups — keep going                          12/7 T

.advance:
    INC IY              ; skip past 3-byte entry                            10 T
    INC IY              ;                                                    10 T
    INC IY              ;                                                    10 T
    JR .next_note       ; load next note                                    12 T

.done:
    POP AF              ; balance the PUSH from .next_note                  10 T
    RET                 ; return to caller                                  10 T

; --- note data: detuned unison then D major scale (3-byte entries) ---
;
;   Each entry: duration, ch1_period, ch2_period
;   Ch2 offset by +1 (detuned unison — avoids XOR cancellation)
;
;   Part 1: detuned A4 unison — hear the chorus shimmer in isolation.
;   Two channels at nearly the same frequency beat against each other.
;   The slight detuning (period 86 vs 87) produces the characteristic
;   Spectrum shimmer — same pitch, slight chorus effect.
;
;   Part 2: D major scale with chorus — same shimmer on every note.
;
;   Effective loop ≈ 46 T (45T base + toggle overhead averaged across period)
;   period ≈ 1,750,000 / (freq × 46)
;
;   Note  Freq(Hz)  Period
;   D4    293.66    130
;   E4    329.63    115
;   F#4   369.99    103
;   G4    392.00     97
;   A4    440.00     86
;   B4    493.88     77
;   C#5   554.37     69
;   D5    587.33     65

tune_data:
    ; --- Part 1: detuned unison (A4/A4 shimmer) ---
    ;         dur  ch1  ch2
    DEFB 200,  86,  87   ; A4/A4 detuned — chorus shimmer
    DEFB 200,  86,  87   ; (repeat to hear the beating)

    ; --- Part 2: D major scale up and down ---
    ;         dur  ch1  ch2
    ; ascending
    DEFB 120, 130, 131   ; D4
    DEFB 120, 115, 116   ; E4
    DEFB 120, 103, 104   ; F#4
    DEFB 120,  97,  98   ; G4
    DEFB 120,  86,  87   ; A4
    DEFB 120,  77,  78   ; B4
    DEFB 120,  69,  70   ; C#5
    DEFB 240,  65,  66   ; D5 (held)
    ; descending
    DEFB 120,  65,  66   ; D5
    DEFB 120,  69,  70   ; C#5
    DEFB 120,  77,  78   ; B4
    DEFB 120,  86,  87   ; A4
    DEFB 120,  97,  98   ; G4
    DEFB 120, 103, 104   ; F#4
    DEFB 120, 115, 116   ; E4
    DEFB 240, 130, 131   ; D4 (held)
    DEFB 0xFF            ; end of tune

; T-state analysis (2ch interleave — PUSH/POP preserved):
;   PUSH/POP AF only at note boundaries — not in the hot loop — zero overhead.
;
;   normal path (no toggles, DJNZ taken):
;     DEC D (4) + JR NZ (12) + DEC E (4) + JR NZ (12) + DJNZ (13) = 45 T
;   ch1 toggle (D hits zero):
;     DEC D (4) + JR NZ fall (7) + LD D,H (4) + XOR (7) + OUT (11)
;         + DEC E (4) + JR NZ (12) + DJNZ (13) = 62 T
;   ch2 toggle (E hits zero): same structure, 62 T
;   both toggle: 79 T (rare — only when both counters hit zero same iteration)
;
;   Toggle overhead: 17 T (vs 21 T in reference — 19% less jitter)
;   Effective avg ≈ 46 T (accounting for both channels' toggle overhead)
;   period ≈ 1,750,000 / (freq × 46)

scr_data:
    INCBIN "screen.scr"
