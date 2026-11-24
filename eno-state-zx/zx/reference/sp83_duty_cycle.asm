; sp83_duty_cycle.asm — 1-channel duty-cycle beeper engine (Splat!, 1983)
;
; Technique: single channel, variable duty cycle.
; Two bytes per note frame: HIGH phase period + LOW phase period.
; Varying hi/lo ratio shapes the perceived timbre.
;
; Source: Splat! (Incentive Software, 1983). Block 0 @ 0xE000.
; Extracted by dig from sp83.tap, entry confirmed at 0xE290.
; Original note table @ 0xE2F4 (216 frames).

    ORG     0x8000

START:
    LD      HL, NOTE_TABLE  ; point to note data
    LD      DE, 0x00D8    ; 216 frames
    DI                      ; disable interrupts

NEXT_FRAME:
    LD      C, (HL)         ; C = high-phase period
    LD      A, 0x11         ; ear + mic bits high
    OUT     (0xFE), A

HI_WAIT:
    LD      B, 3
HI_LOOP:
    DJNZ    HI_LOOP
    DEC     C
    JR      NZ, HI_WAIT

    INC     HL
    LD      C, (HL)         ; C = low-phase period
    LD      A, 0x01         ; ear bit low
    OUT     (0xFE), A

LO_WAIT:
    LD      B, 3
LO_LOOP:
    DJNZ    LO_LOOP
    DEC     C
    JR      NZ, LO_WAIT

    INC     HL
    DEC     DE
    LD      A, D
    OR      E
    JR      NZ, NEXT_FRAME  ; loop until DE == 0

    EI
    JP      START           ; loop forever

NOTE_TABLE:
    DEFB    0x09, 0x13  ; frame 0
    DEFB    0x07, 0x08  ; frame 1
    DEFB    0x06, 0xC9  ; frame 2
    DEFB    0x0B, 0x0A  ; frame 3
    DEFB    0x52, 0x04  ; frame 4
    DEFB    0x0A, 0x2A  ; frame 5
    DEFB    0x03, 0xDF  ; frame 6
    DEFB    0x03, 0x12  ; frame 7
    DEFB    0x0A, 0x08  ; frame 8
    DEFB    0x07, 0x1B  ; frame 9
    DEFB    0x05, 0x27  ; frame 10
    DEFB    0x09, 0x0F  ; frame 11
    DEFB    0x0C, 0x09  ; frame 12
    DEFB    0x07, 0x09  ; frame 13
    DEFB    0x06, 0x17  ; frame 14
    DEFB    0x03, 0x0A  ; frame 15
    DEFB    0x05, 0x09  ; frame 16
    DEFB    0x06, 0x0A  ; frame 17
    DEFB    0x04, 0x22  ; frame 18
    DEFB    0x15, 0x0C  ; frame 19
    DEFB    0x44, 0x07  ; frame 20
    DEFB    0x07, 0x0A  ; frame 21
    DEFB    0x01, 0x33  ; frame 22
    DEFB    0x00, 0x12  ; frame 23
    DEFB    0x05, 0x4D  ; frame 24
    DEFB    0x01, 0x41  ; frame 25
    DEFB    0x06, 0x47  ; frame 26
    DEFB    0x0A, 0x08  ; frame 27
    DEFB    0x08, 0x10  ; frame 28
    DEFB    0x12, 0x08  ; frame 29
    DEFB    0x0A, 0x09  ; frame 30
    DEFB    0x08, 0x0B  ; frame 31
    DEFB    0x06, 0x0B  ; frame 32
    DEFB    0x04, 0x0B  ; frame 33
    DEFB    0x04, 0x0F  ; frame 34
    DEFB    0x06, 0x0B  ; frame 35
    DEFB    0x0A, 0x11  ; frame 36
    DEFB    0x09, 0x09  ; frame 37
    DEFB    0x08, 0x21  ; frame 38
    DEFB    0x05, 0x08  ; frame 39
    DEFB    0x07, 0x0B  ; frame 40
    DEFB    0x3B, 0x04  ; frame 41
    DEFB    0x1D, 0x73  ; frame 42
    DEFB    0x04, 0x09  ; frame 43
    DEFB    0x07, 0x06  ; frame 44
    DEFB    0x09, 0x08  ; frame 45
    DEFB    0x08, 0x11  ; frame 46
    DEFB    0x05, 0x61  ; frame 47
    DEFB    0x32, 0x05  ; frame 48
    DEFB    0x0A, 0x09  ; frame 49
    DEFB    0x03, 0x51  ; frame 50
    DEFB    0x41, 0x6F  ; frame 51
    DEFB    0x37, 0x5D  ; frame 52
    DEFB    0x3A, 0x75  ; frame 53
    DEFB    0x3A, 0x63  ; frame 54
    DEFB    0x46, 0x54  ; frame 55
    DEFB    0x02, 0x07  ; frame 56
    DEFB    0x0A, 0x07  ; frame 57
    DEFB    0x12, 0x06  ; frame 58
    DEFB    0x09, 0x23  ; frame 59
    DEFB    0x03, 0x0B  ; frame 60
    DEFB    0x4A, 0x4B  ; frame 61
    DEFB    0x04, 0x0B  ; frame 62
    DEFB    0x09, 0x07  ; frame 63
    DEFB    0x23, 0x00  ; frame 64
    DEFB    0x00, 0x5D  ; frame 65
    DEFB    0x08, 0x08  ; frame 66
    DEFB    0x11, 0x03  ; frame 67
    DEFB    0x11, 0x03  ; frame 68
    DEFB    0x0D, 0x34  ; frame 69
    DEFB    0x01, 0x0E  ; frame 70
    DEFB    0x08, 0x07  ; frame 71
    DEFB    0x2F, 0x3C  ; frame 72
    DEFB    0x03, 0x0E  ; frame 73
    DEFB    0x07, 0x09  ; frame 74
    DEFB    0x0C, 0x07  ; frame 75
    DEFB    0x0E, 0x07  ; frame 76
    DEFB    0x0B, 0x2D  ; frame 77
    DEFB    0x07, 0x0A  ; frame 78
    DEFB    0x0B, 0x06  ; frame 79
    DEFB    0x20, 0x4A  ; frame 80
    DEFB    0x04, 0x0E  ; frame 81
    DEFB    0x09, 0x07  ; frame 82
    DEFB    0x28, 0x43  ; frame 83
    DEFB    0x02, 0x10  ; frame 84
    DEFB    0x05, 0x07  ; frame 85
    DEFB    0x2F, 0x3B  ; frame 86
    DEFB    0x02, 0x10  ; frame 87
    DEFB    0x05, 0x08  ; frame 88
    DEFB    0x08, 0x02  ; frame 89
    DEFB    0x2F, 0x18  ; frame 90
    DEFB    0x02, 0x10  ; frame 91
    DEFB    0x03, 0x1F  ; frame 92
    DEFB    0x04, 0x06  ; frame 93
    DEFB    0x0A, 0x03  ; frame 94
    DEFB    0x09, 0x05  ; frame 95
    DEFB    0x0A, 0x0B  ; frame 96
    DEFB    0x01, 0x0B  ; frame 97
    DEFB    0x06, 0x0D  ; frame 98
    DEFB    0x06, 0x0D  ; frame 99
    DEFB    0x0A, 0x08  ; frame 100
    DEFB    0x27, 0x25  ; frame 101
    DEFB    0x06, 0x0D  ; frame 102
    DEFB    0x06, 0x0D  ; frame 103
    DEFB    0x07, 0x04  ; frame 104
    DEFB    0x07, 0x04  ; frame 105
    DEFB    0x1B, 0x2B  ; frame 106
    DEFB    0x06, 0x0E  ; frame 107
    DEFB    0x05, 0x11  ; frame 108
    DEFB    0x06, 0x0D  ; frame 109
    DEFB    0x1A, 0x02  ; frame 110
    DEFB    0x0D, 0x1C  ; frame 111
    DEFB    0x04, 0x0F  ; frame 112
    DEFB    0x05, 0x10  ; frame 113
    DEFB    0x06, 0x0E  ; frame 114
    DEFB    0x2D, 0x18  ; frame 115
    DEFB    0x07, 0x0E  ; frame 116
    DEFB    0x05, 0x11  ; frame 117
    DEFB    0x08, 0x0C  ; frame 118
    DEFB    0x0B, 0x0B  ; frame 119
    DEFB    0x0D, 0x1F  ; frame 120
    DEFB    0x04, 0x0E  ; frame 121
    DEFB    0x06, 0x0D  ; frame 122
    DEFB    0x09, 0x0F  ; frame 123
    DEFB    0x14, 0x03  ; frame 124
    DEFB    0x11, 0x16  ; frame 125
    DEFB    0x08, 0x0D  ; frame 126
    DEFB    0x07, 0x0E  ; frame 127
    DEFB    0x08, 0x0D  ; frame 128
    DEFB    0x28, 0x21  ; frame 129
    DEFB    0x00, 0x10  ; frame 130
    DEFB    0x05, 0x0F  ; frame 131
    DEFB    0x08, 0x0D  ; frame 132
    DEFB    0x13, 0x06  ; frame 133
    DEFB    0x0E, 0x1C  ; frame 134
    DEFB    0x02, 0x0F  ; frame 135
    DEFB    0x06, 0x0F  ; frame 136
    DEFB    0x09, 0x0B  ; frame 137
    DEFB    0x2B, 0x18  ; frame 138
    DEFB    0x03, 0x10  ; frame 139
    DEFB    0x05, 0x10  ; frame 140
    DEFB    0x07, 0x0D  ; frame 141
    DEFB    0x17, 0x02  ; frame 142
    DEFB    0x0C, 0x19  ; frame 143
    DEFB    0x02, 0x13  ; frame 144
    DEFB    0x05, 0x15  ; frame 145
    DEFB    0x06, 0x06  ; frame 146
    DEFB    0x16, 0x04  ; frame 147
    DEFB    0x11, 0x0C  ; frame 148
    DEFB    0x08, 0x12  ; frame 149
    DEFB    0x07, 0x0D  ; frame 150
    DEFB    0x10, 0x07  ; frame 151
    DEFB    0x1F, 0x00  ; frame 152
    DEFB    0x01, 0x1B  ; frame 153
    DEFB    0x0A, 0x0D  ; frame 154
    DEFB    0x07, 0x10  ; frame 155
    DEFB    0x0A, 0x0A  ; frame 156
    DEFB    0x13, 0x05  ; frame 157
    DEFB    0x0E, 0x15  ; frame 158
    DEFB    0x03, 0x12  ; frame 159
    DEFB    0x05, 0x12  ; frame 160
    DEFB    0x0B, 0x08  ; frame 161
    DEFB    0x19, 0x01  ; frame 162
    DEFB    0x0F, 0x0F  ; frame 163
    DEFB    0x07, 0x11  ; frame 164
    DEFB    0x04, 0x13  ; frame 165
    DEFB    0x09, 0x0A  ; frame 166
    DEFB    0x18, 0x04  ; frame 167
    DEFB    0x0C, 0x10  ; frame 168
    DEFB    0x07, 0x13  ; frame 169
    DEFB    0x01, 0x17  ; frame 170
    DEFB    0x07, 0x09  ; frame 171
    DEFB    0x18, 0x05  ; frame 172
    DEFB    0x0C, 0x0E  ; frame 173
    DEFB    0x08, 0x0E  ; frame 174
    DEFB    0x05, 0x0F  ; frame 175
    DEFB    0x37, 0x1F  ; frame 176
    DEFB    0x07, 0x10  ; frame 177
    DEFB    0x05, 0x11  ; frame 178
    DEFB    0x0B, 0x06  ; frame 179
    DEFB    0x25, 0x1C  ; frame 180
    DEFB    0x04, 0x12  ; frame 181
    DEFB    0x02, 0x13  ; frame 182
    DEFB    0x09, 0x05  ; frame 183
    DEFB    0x2B, 0x17  ; frame 184
    DEFB    0x04, 0x11  ; frame 185
    DEFB    0x05, 0x12  ; frame 186
    DEFB    0x0A, 0x04  ; frame 187
    DEFB    0x28, 0x34  ; frame 188
    DEFB    0x03, 0x10  ; frame 189
    DEFB    0x1E, 0x15  ; frame 190
    DEFB    0x05, 0x2D  ; frame 191
    DEFB    0x27, 0x03  ; frame 192
    DEFB    0x12, 0x08  ; frame 193
    DEFB    0x0F, 0x2A  ; frame 194
    DEFB    0x06, 0x2F  ; frame 195
    DEFB    0x10, 0x08  ; frame 196
    DEFB    0x0A, 0x60  ; frame 197
    DEFB    0x11, 0x04  ; frame 198
    DEFB    0x12, 0x0B  ; frame 199
    DEFB    0x03, 0x2F  ; frame 200
    DEFB    0x07, 0x09  ; frame 201
    DEFB    0x2C, 0x44  ; frame 202
    DEFB    0x31, 0x07  ; frame 203
    DEFB    0x05, 0x41  ; frame 204
    DEFB    0x44, 0x61  ; frame 205
    DEFB    0x09, 0xE5  ; frame 206
    DEFB    0x3E, 0x4E  ; frame 207
    DEFB    0x05, 0x0C  ; frame 208
    DEFB    0x25, 0x4F  ; frame 209
    DEFB    0x04, 0x08  ; frame 210
    DEFB    0x0D, 0x0B  ; frame 211
    DEFB    0x4C, 0x06  ; frame 212
    DEFB    0x11, 0x0B  ; frame 213
    DEFB    0x0C, 0xE9  ; frame 214
    DEFB    0x07, 0x0E  ; frame 215
