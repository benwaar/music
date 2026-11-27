; mm83_minimal.asm — minimal 2-channel beeper engine
; Pure audio: no screen setup, no attribute bars, no visuals.
; Same tune, same timing (46 T-states/iteration).

    ORG 0x8000

    DI
    LD IY, note_table
    XOR A
    CALL play_tune
    JR $

play_tune:
    LD A, (IY)
    CP 0xFF
    RET Z
    LD C, A
    LD B, 0
    XOR A
    LD D, (IY+1)
    LD E, (IY+2)

tone_loop:
    OUT (0xFE), A
    DEC D
    JR NZ, skip_d
    LD D, (IY+1)
    XOR 0x18
skip_d:
    DEC E
    JR NZ, skip_e
    LD E, (IY+2)
    XOR 0x18
skip_e:
    DJNZ tone_loop
    DEC C
    JR NZ, tone_loop

    INC IY
    INC IY
    INC IY
    JR play_tune

note_table:
    DEFB 80, 128, 129       ;  0  D4/D4 (intro)
    DEFB 80, 102, 103       ;  1  F#4/F#4 (intro)
    DEFB 80, 86, 87         ;  2  A4/A4 (intro)
    DEFB 50, 86, 87         ;  3  A4/A4
    DEFB 50, 171, 203       ;  4  A3/F#3
    DEFB 50, 43, 51         ;  5  A5/F#5
    DEFB 50, 43, 51         ;  6  A5/F#5
    DEFB 50, 171, 203       ;  7  A3/F#3
    DEFB 50, 51, 64         ;  8  F#5/D5
    DEFB 50, 51, 64         ;  9  F#5/D5
    DEFB 50, 171, 203       ; 10  A3/F#3
    DEFB 50, 128, 129       ; 11  D4/D4
    DEFB 50, 128, 129       ; 12  D4/D4
    DEFB 50, 102, 103       ; 13  F#4/F#4
    DEFB 50, 86, 87         ; 14  A4/A4
    DEFB 50, 96, 86         ; 15  G4/A4
    DEFB 50, 171, 192       ; 16  A3/G3
    DEFB 50, 43, 48         ; 17  A5/G5
    DEFB 50, 43, 48         ; 18  A5/G5
    DEFB 50, 171, 192       ; 19  A3/G3
    DEFB 50, 48, 68         ; 20  G5/C#5
    DEFB 50, 48, 68         ; 21  G5/C#5
    DEFB 50, 171, 192       ; 22  A3/G3
    DEFB 50, 136, 137       ; 23  C#4/C#4
    DEFB 50, 136, 137       ; 24  C#4/C#4
    DEFB 50, 114, 115       ; 25  E4/E4
    DEFB 50, 76, 77         ; 26  B4/B4
    DEFB 50, 76, 77         ; 27  B4/B4
    DEFB 50, 171, 192       ; 28  A3/G3
    DEFB 50, 38, 48         ; 29  B5/G5
    DEFB 50, 38, 48         ; 30  B5/G5
    DEFB 50, 171, 192       ; 31  A3/G3
    DEFB 50, 48, 68         ; 32  G5/C#5
    DEFB 50, 48, 68         ; 33  G5/C#5
    DEFB 50, 171, 192       ; 34  A3/G3
    DEFB 50, 136, 137       ; 35  C#4/C#4
    DEFB 50, 136, 137       ; 36  C#4/C#4
    DEFB 50, 114, 115       ; 37  E4/E4
    DEFB 50, 76, 77         ; 38  B4/B4
    DEFB 50, 76, 77         ; 39  B4/B4
    DEFB 50, 171, 203       ; 40  A3/F#3
    DEFB 50, 38, 51         ; 41  B5/F#5
    DEFB 50, 38, 51         ; 42  B5/F#5
    DEFB 50, 171, 203       ; 43  A3/F#3
    DEFB 50, 51, 64         ; 44  F#5/D5
    DEFB 50, 51, 64         ; 45  F#5/D5
    DEFB 50, 171, 203       ; 46  A3/F#3
    DEFB 50, 128, 129       ; 47  D4/D4
    DEFB 50, 128, 129       ; 48  D4/D4
    DEFB 50, 102, 103       ; 49  F#4/F#4
    DEFB 50, 86, 87         ; 50  A4/A4
    DEFB 50, 64, 65         ; 51  D5/D5
    DEFB 50, 128, 171       ; 52  D4/A3
    DEFB 50, 32, 43         ; 53  D6/A5
    DEFB 50, 32, 43         ; 54  D6/A5
    DEFB 50, 128, 171       ; 55  D4/A3
    DEFB 50, 43, 51         ; 56  A5/F#5
    DEFB 50, 43, 51         ; 57  A5/F#5
    DEFB 50, 128, 171       ; 58  D4/A3
    DEFB 50, 128, 129       ; 59  D4/D4
    DEFB 50, 128, 129       ; 60  D4/D4
    DEFB 50, 102, 103       ; 61  F#4/F#4
    DEFB 50, 86, 87         ; 62  A4/A4
    DEFB 50, 64, 65         ; 63  D5/D5
    DEFB 50, 128, 152       ; 64  D4/B3
    DEFB 50, 32, 38         ; 65  D6/B5
    DEFB 50, 32, 38         ; 66  D6/B5
    DEFB 50, 128, 152       ; 67  D4/B3
    DEFB 50, 38, 48         ; 68  B5/G5
    DEFB 50, 38, 48         ; 69  B5/G5
    DEFB 50, 0, 0           ; 70  REST
    DEFB 50, 114, 115       ; 71  E4/E4
    DEFB 50, 114, 115       ; 72  E4/E4
    DEFB 50, 96, 97         ; 73  G4/G4
    DEFB 50, 76, 77         ; 74  B4/B4
    DEFB 50, 76, 153        ; 75  B4/B3
    DEFB 50, 76, 77         ; 76  B4/B4
    DEFB 50, 76, 77         ; 77  B4/B4
    DEFB 50, 76, 153        ; 78  B4/B3
    DEFB 50, 91, 92         ; 79  G#4/G#4
    DEFB 50, 86, 87         ; 80  A4/A4
    DEFB 50, 51, 205        ; 81  F#5/F#3
    DEFB 50, 51, 52         ; 82  F#5/F#5
    DEFB 50, 51, 52         ; 83  F#5/F#5
    DEFB 50, 51, 205        ; 84  F#5/F#3
    DEFB 50, 64, 65         ; 85  D5/D5
    DEFB 50, 102, 103       ; 86  F#4/F#4
    DEFB 100, 102, 103      ; 87  F#4/F#4 (sustained)
    DEFB 50, 114, 115       ; 88  E4/E4
    DEFB 100, 76, 77        ; 89  B4/B4 (sustained)
    DEFB 50, 86, 87         ; 90  A4/A4
    DEFB 50, 128, 203       ; 91  D4/F#3
    DEFB 25, 128, 0         ; 92  D4 mono (short)
    DEFB 25, 128, 129       ; 93  D4/D4 (short)
    DEFB 50, 128, 203       ; 94  D4/F#3 (final)
    DEFB 0xFF               ; end
