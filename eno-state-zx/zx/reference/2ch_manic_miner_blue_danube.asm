; manic_miner_blue_danube.asm — Manic Miner title screen music
; Original by Matthew Smith (1983). Disassembly by William Humphreys.
; Source: github.com/WHumphreys/Manic-Miner-Source-Code
;
; 2-channel beeper engine: two period counters (D, E) in one loop.
; OUT every iteration. IY indexed reload. XOR 0x18 (EAR+MIC).
; The Blue Danube waltz by Johann Strauss II.
;
; This is the original engine from the game — the first documented
; 2-channel beeper engine on the ZX Spectrum.
;
; Normal path: OUT(11) + DEC D(4) + JR NZ(12) + DEC E(4) + JR NZ(12) + DJNZ(13) = 56 T
; freq ≈ 3,500,000 / (2 × period × 56)

    ORG 0x8000

    DI
    LD IY, blue_danube
    XOR A
    CALL play_tune
    HALT

play_tune:
    LD A, (IY+0)
    CP 0xFF
    RET Z
    LD C, A             ; duration
    LD B, 0             ; inner counter (256)
    XOR A
    LD D, (IY+1)        ; ch1 period
    LD E, (IY+2)        ; ch2 period

.loop:
    OUT (0xFE), A       ; output every iteration             11 T
    DEC D               ;                                     4 T
    JR NZ, .skip_d      ;                                    12/7 T
    LD D, (IY+1)        ; reload ch1 from table              19 T
    XOR 0x18            ; toggle speaker                      7 T
.skip_d:
    DEC E               ;                                     4 T
    JR NZ, .skip_e      ;                                    12/7 T
    LD E, (IY+2)        ; reload ch2 from table              19 T
    XOR 0x18            ; toggle speaker                      7 T
.skip_e:
    DJNZ .loop          ;                                    13/8 T
    DEC C               ;                                     4 T
    JR NZ, .loop        ;                                    12/7 T

    INC IY
    INC IY
    INC IY
    JR play_tune

; The Blue Danube — 95 notes, 3 bytes each (duration, ch1_period, ch2_period)
; Original data from Manic Miner (1983) by Matthew Smith.

blue_danube:
    DB $50,$80,$81       ;  0
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
