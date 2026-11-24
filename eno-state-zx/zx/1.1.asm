; 1.1.asm — bare toggle loop
; Toggle the speaker as fast as possible. No pitch control, no notes.
; Just: flip bit 4 of port 0xFE, forever.

    ORG 0x8000

    DI
    XOR A               ; A = 0x00 (speaker low)

loop:
    XOR 0x10            ; flip bit 4: 0x00 → 0x10 → 0x00 → ...
    OUT (0xFE), A       ; send to speaker
    JR loop             ; repeat forever
