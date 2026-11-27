; 1ch_duty.asm — 1-channel duty-cycle beeper engine
;
; Our improved version of the sp83 technique (Splat!, 1983).
; Same algorithm — explicit hi/lo wait loops — but with a clean
; educational note table instead of raw game data.
;
; Each note is 3 bytes: (hi_period, lo_period, duration).
; - hi_period + lo_period = total cycle time (pitch)
; - hi_period / (hi_period + lo_period) = duty cycle (timbre)
; - duration = how many full cycles to play
;
; Sentinel: 0xFF ends the tune.
;
; Differences from sp83_duty_cycle.asm:
;   - 3-byte note entries (adds duration per note, sp83 uses global frame count)
;   - 0xFF sentinel (sp83 uses DE frame counter)
;   - Clean note table: D major scale with deliberate duty variations
;   - Same inner loop structure (B=3 DJNZ, DEC C)
;
; Compare: `reference/sp83_duty_cycle.asm` (original game extraction)
;          `reference/squeeker_duty.asm` (threshold approach, different technique)

    ORG     0x8000

    DI
    LD      IY, NOTE_TABLE
    CALL    play_tune
    JR      $               ; halt

; -------------------------------------------------------------------
; play_tune — walk the note table, play each note
; -------------------------------------------------------------------
play_tune:
    LD      A, (IY)
    CP      0xFF
    RET     Z               ; sentinel → done

    LD      D, (IY+2)      ; D = duration (number of full cycles)

note_cycle:
    ; --- HIGH phase ---
    LD      C, (IY)         ; C = hi_period
    LD      A, 0x11         ; EAR high + border blue
    OUT     (0xFE), A

hi_wait:
    LD      B, 3
hi_loop:
    DJNZ    hi_loop         ; inner delay × 3
    DEC     C
    JR      NZ, hi_wait

    ; --- LOW phase ---
    LD      C, (IY+1)      ; C = lo_period
    LD      A, 0x01         ; EAR low + border blue
    OUT     (0xFE), A

lo_wait:
    LD      B, 3
lo_loop:
    DJNZ    lo_loop         ; inner delay × 3
    DEC     C
    JR      NZ, lo_wait

    ; --- Next cycle ---
    DEC     D
    JR      NZ, note_cycle

    ; --- Next note ---
    INC     IY
    INC     IY
    INC     IY              ; advance by 3 bytes
    JR      play_tune

; -------------------------------------------------------------------
; Note table: (hi_period, lo_period, duration)
;
; Pitch: total period = hi + lo. Same formula as 1ch_tone but split.
; Timbre: duty = hi / (hi + lo).
;   50% = square wave (neutral)
;   25% = thin pulse (quiet, nasal)
;   75% = fat pulse (loud, buzzy)
;
; Scale up: D major, 50% duty (square wave baseline)
; Scale down: same notes, varying duty to demonstrate timbre control
; -------------------------------------------------------------------
NOTE_TABLE:
    ; --- The Blue Danube (Manic Miner, 1983) ---
    ; Converted from 2ch interleave to 1ch duty cycle.
    ; ch1 melody only. Bass notes get 65% duty (fatter),
    ; waltz beat 1 gets 58% duty (accent), others 50%.
    ; (hi_period, lo_period, duration)

    DEFB    134, 72,  80         ;  0 bass
    DEFB    82, 82, 100          ;  1
    DEFB    69, 69, 119          ;  2
    DEFB    80, 58,  74          ;  3
    DEFB    178, 96,  38         ;  4 bass
    DEFB    34, 34, 149          ;  5
    DEFB    39, 29, 149          ;  6
    DEFB    178, 96,  38         ;  7 bass
    DEFB    41, 41, 124          ;  8
    DEFB    48, 34, 124          ;  9
    DEFB    178, 96,  38         ; 10 bass
    DEFB    134, 72,  50         ; 11 bass
    DEFB    134, 72,  50         ; 12 bass
    DEFB    82, 82,  62          ; 13
    DEFB    69, 69,  74          ; 14
    DEFB    89, 65,  67          ; 15
    DEFB    178, 96,  38         ; 16 bass
    DEFB    34, 34, 149          ; 17
    DEFB    39, 29, 149          ; 18
    DEFB    178, 96,  38         ; 19 bass
    DEFB    38, 38, 134          ; 20
    DEFB    44, 32, 134          ; 21
    DEFB    178, 96,  38         ; 22 bass
    DEFB    142, 76,  47         ; 23 bass
    DEFB    142, 76,  47         ; 24 bass
    DEFB    91, 91,  56          ; 25
    DEFB    61, 61,  84          ; 26
    DEFB    71, 51,  84          ; 27
    DEFB    178, 96,  38         ; 28 bass
    DEFB    30, 30, 169          ; 29
    DEFB    35, 25, 169          ; 30
    DEFB    178, 96,  38         ; 31 bass
    DEFB    38, 38, 134          ; 32
    DEFB    44, 32, 134          ; 33
    DEFB    178, 96,  38         ; 34 bass
    DEFB    142, 76,  47         ; 35 bass
    DEFB    142, 76,  47         ; 36 bass
    DEFB    91, 91,  56          ; 37
    DEFB    61, 61,  84          ; 38
    DEFB    71, 51,  84          ; 39
    DEFB    178, 96,  38         ; 40 bass
    DEFB    30, 30, 169          ; 41
    DEFB    35, 25, 169          ; 42
    DEFB    178, 96,  38         ; 43 bass
    DEFB    41, 41, 124          ; 44
    DEFB    48, 34, 124          ; 45
    DEFB    178, 96,  38         ; 46 bass
    DEFB    134, 72,  50         ; 47 bass
    DEFB    134, 72,  50         ; 48 bass
    DEFB    82, 82,  62          ; 49
    DEFB    69, 69,  74          ; 50
    DEFB    59, 43, 100          ; 51
    DEFB    134, 72,  50         ; 52 bass
    DEFB    25, 25, 201          ; 53
    DEFB    29, 21, 201          ; 54
    DEFB    134, 72,  50         ; 55 bass
    DEFB    34, 34, 149          ; 56
    DEFB    39, 29, 149          ; 57
    DEFB    134, 72,  50         ; 58 bass
    DEFB    134, 72,  50         ; 59 bass
    DEFB    134, 72,  50         ; 60 bass
    DEFB    82, 82,  62          ; 61
    DEFB    82, 82,  62          ; 62
    DEFB    59, 43, 100          ; 63
    DEFB    134, 72,  50         ; 64 bass
    DEFB    25, 25, 201          ; 65
    DEFB    29, 21, 201          ; 66
    DEFB    134, 72,  50         ; 67 bass
    DEFB    30, 30, 169          ; 68
    DEFB    35, 25, 169          ; 69
    DEFB    1, 1,  20            ; 70 REST
    DEFB    91, 91,  56          ; 71
    DEFB    106, 76,  56         ; 72
    DEFB    77, 77,  67          ; 73
    DEFB    61, 61,  84          ; 74
    DEFB    71, 51,  84          ; 75
    DEFB    61, 61,  84          ; 76
    DEFB    61, 61,  84          ; 77
    DEFB    71, 51,  84          ; 78
    DEFB    73, 73,  70          ; 79
    DEFB    69, 69,  74          ; 80
    DEFB    48, 34, 124          ; 81
    DEFB    41, 41, 124          ; 82
    DEFB    41, 41, 124          ; 83
    DEFB    48, 34, 124          ; 84
    DEFB    51, 51, 100          ; 85
    DEFB    82, 82,  62          ; 86
    DEFB    95, 69, 125          ; 87 held
    DEFB    91, 91,  56          ; 88
    DEFB    61, 61, 168          ; 89 held
    DEFB    80, 58,  74          ; 90
    DEFB    134, 72,  50         ; 91 bass
    DEFB    134, 72,  25         ; 92 bass
    DEFB    134, 72,  25         ; 93 bass
    DEFB    134, 72,  50         ; 94 bass

    DEFB    0xFF                 ; end sentinel
