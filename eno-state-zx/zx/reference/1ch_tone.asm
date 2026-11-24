; 1ch_tone.asm — simplest possible beeper engine
; Single channel, note table driven. Plays a D major scale.
; 58 bytes engine, no visuals, no key check.

    ORG 0x8000

    DI
    LD IY, note_table
    CALL play_tune
    JR $

play_tune:
    LD A, (IY)
    CP 0xFF
    RET Z
    LD C, A             ; C = duration
    LD B, 0             ; B = 0 → 256 iterations per C
    LD D, (IY+1)        ; D = period
    XOR A               ; speaker low

tone_loop:
    OUT (0xFE), A
    DEC D
    JR NZ, skip
    LD D, (IY+1)        ; reload period
    XOR 0x18            ; toggle speaker
skip:
    DJNZ tone_loop
    DEC C
    JR NZ, tone_loop

    INC IY
    INC IY              ; advance by 2 (pairs, not triplets)
    JR play_tune

; (duration, period) pairs
; freq = 3,500,000 / (2 × period × 33)  [33 T-states per iteration]
; T-states: OUT=11, DEC D=4, JR NZ=7, DJNZ=13 → 35 (no toggle)
;   actually: OUT=11, DEC=4, JR NZ taken=12, DJNZ taken=13 = 40
;   no-toggle path: OUT=11, DEC=4, JR NZ not-taken=7, DJNZ=13 = 35

note_table:
    DEFB 40, 152         ; D4  ~329 Hz
    DEFB 40, 135         ; E4  ~370 Hz
    DEFB 40, 121         ; F#4 ~414 Hz
    DEFB 40, 114         ; G4  ~439 Hz
    DEFB 40, 101         ; A4  ~495 Hz
    DEFB 40, 90          ; B4  ~556 Hz
    DEFB 40, 80          ; C#5 ~625 Hz
    DEFB 80, 76          ; D5  ~658 Hz (held)
    DEFB 20, 0           ; REST (short silence)
    DEFB 40, 76          ; D5
    DEFB 40, 80          ; C#5
    DEFB 40, 90          ; B4
    DEFB 40, 101         ; A4
    DEFB 40, 114         ; G4
    DEFB 40, 121         ; F#4
    DEFB 40, 135         ; E4
    DEFB 80, 152         ; D4  (held)
    DEFB 0xFF            ; end
