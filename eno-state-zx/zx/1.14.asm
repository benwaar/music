; beeper.asm — master beeper file
; Screen loader + beeper engine. Add engine code below the screen setup.
; Current exercise: 1.14 (Manic Miner Blue Danube through our 2ch engine)

    ORG 0x8000

    ; load screen.scr into display memory
    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

SENTINEL EQU 0xFF           ; end-of-table marker

    ; --- main program ---

    DI                  ; disable interrupts                                  4 T
    LD IY, blue_danube  ; point to tune data                                14 T
    CALL play_tune      ; play the tune, then return here                    17 T
    HALT                ; done — CPU stops (DI active)

; =====================================================================
; play_tune — 2ch interleave engine (improved)
;
; Entry: IY = note table (3-byte entries: duration, ch1_period, ch2_period; 0xFF sentinel)
; Exit:  returns when sentinel reached
; Clobbers: A, B, C, D, E, H, L
;
; Improvements over reference (Manic Miner, 1983):
;   - OUT only on toggle (original OUTs every iteration — redundant)
;   - Register reload: LD D,H (4T) vs LD D,(IY+1) (19T) — 15T faster
;   - Speaker carries over between notes via PUSH/POP AF (no clicks)
;   - Toggle overhead 17T vs original's 21T — better pitch stability
;   - REST (period 0) handled explicitly — substituted with 255 at load time
;     (original wraps 0→255 by accident, fires stray toggles)
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
    LD A, D             ; check for period 0 (rest)                           4 T
    OR A                ;                                                      4 T
    JR NZ, .ch1_ok      ;                                                    12/7 T
    LD D, 255           ; period 0 → 255 (near-silent, no stray XOR mess)     7 T
.ch1_ok:
    LD H, D             ; H = ch1 reload                                      4 T
    LD E, (IY+2)        ; E = ch2 period countdown                           19 T
    LD A, E             ; check for period 0 (rest)                           4 T
    OR A                ;                                                      4 T
    JR NZ, .ch2_ok      ;                                                    12/7 T
    LD E, 255           ; period 0 → 255 (near-silent)                        7 T
.ch2_ok:
    LD L, E             ; L = ch2 reload                                      4 T
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

; --- The Blue Danube (Manic Miner, 1983) ---
;
;   Original data from Matthew Smith's Manic Miner.
;   Periods were tuned for the original 56T loop.
;   Our engine runs at ~45T, so everything plays ~24% sharper.
;   That's ok for now — we're testing the engine, not the tuning.

blue_danube:
    DB $50,$80,$81       ;  0  intro
    DB $50,$66,$67       ;  1
    DB $50,$56,$57       ;  2
    DB $32,$56,$57       ;  3
    DB $32,$AB,$CB       ;  4
    DB $32,$2B,$33       ;  5
    DB $32,$2B,$33       ;  6
    DB $32,$AB,$CB       ;  7
    DB $32,$33,$40       ;  8
    DB $32,$33,$40       ;  9
    DB $32,$AB,$CB       ; 10
    DB $32,$80,$81       ; 11
    DB $32,$80,$81       ; 12
    DB $32,$66,$67       ; 13
    DB $32,$56,$57       ; 14
    DB $32,$60,$56       ; 15
    DB $32,$AB,$C0       ; 16
    DB $32,$2B,$30       ; 17
    DB $32,$2B,$30       ; 18
    DB $32,$AB,$C0       ; 19
    DB $32,$30,$44       ; 20
    DB $32,$30,$44       ; 21
    DB $32,$AB,$C0       ; 22
    DB $32,$88,$89       ; 23
    DB $32,$88,$89       ; 24
    DB $32,$72,$73       ; 25
    DB $32,$4C,$4D       ; 26
    DB $32,$4C,$4D       ; 27
    DB $32,$AB,$C0       ; 28
    DB $32,$26,$30       ; 29
    DB $32,$26,$30       ; 30
    DB $32,$AB,$C0       ; 31
    DB $32,$30,$44       ; 32
    DB $32,$30,$44       ; 33
    DB $32,$AB,$C0       ; 34
    DB $32,$88,$89       ; 35
    DB $32,$88,$89       ; 36
    DB $32,$72,$73       ; 37
    DB $32,$4C,$4D       ; 38
    DB $32,$4C,$4D       ; 39
    DB $32,$AB,$CB       ; 40
    DB $32,$26,$33       ; 41
    DB $32,$26,$33       ; 42
    DB $32,$AB,$CB       ; 43
    DB $32,$33,$40       ; 44
    DB $32,$33,$40       ; 45
    DB $32,$AB,$CB       ; 46
    DB $32,$80,$81       ; 47
    DB $32,$80,$81       ; 48
    DB $32,$66,$67       ; 49
    DB $32,$56,$57       ; 50
    DB $32,$40,$41       ; 51
    DB $32,$80,$AB       ; 52
    DB $32,$20,$2B       ; 53
    DB $32,$20,$2B       ; 54
    DB $32,$80,$AB       ; 55
    DB $32,$2B,$33       ; 56
    DB $32,$2B,$33       ; 57
    DB $32,$80,$AB       ; 58
    DB $32,$80,$81       ; 59
    DB $32,$80,$81       ; 60
    DB $32,$66,$67       ; 61
    DB $32,$56,$57       ; 62
    DB $32,$40,$41       ; 63
    DB $32,$80,$98       ; 64
    DB $32,$20,$26       ; 65
    DB $32,$20,$26       ; 66
    DB $32,$80,$98       ; 67
    DB $32,$26,$30       ; 68
    DB $32,$26,$30       ; 69
    DB $32,$00,$00       ; 70  REST
    DB $32,$72,$73       ; 71
    DB $32,$72,$73       ; 72
    DB $32,$60,$61       ; 73
    DB $32,$4C,$4D       ; 74
    DB $32,$4C,$99       ; 75
    DB $32,$4C,$4D       ; 76
    DB $32,$4C,$4D       ; 77
    DB $32,$4C,$99       ; 78
    DB $32,$5B,$5C       ; 79
    DB $32,$56,$57       ; 80
    DB $32,$33,$CD       ; 81
    DB $32,$33,$34       ; 82
    DB $32,$33,$34       ; 83
    DB $32,$33,$CD       ; 84
    DB $32,$40,$41       ; 85
    DB $32,$66,$67       ; 86
    DB $64,$66,$67       ; 87
    DB $32,$72,$73       ; 88
    DB $64,$4C,$4D       ; 89
    DB $32,$56,$57       ; 90
    DB $32,$80,$CB       ; 91
    DB $19,$80,$00       ; 92
    DB $19,$80,$81       ; 93
    DB $32,$80,$CB       ; 94
    DB $FF               ; end

; T-state analysis (2ch interleave — improved):
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
