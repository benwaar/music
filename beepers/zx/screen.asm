; screen.asm — load screen.scr into display memory then fall through
; Used by build.sh: assembled as a wrapper around the exercise code.

    ORG $8000

    LD      HL, scr_data
    LD      DE, $4000
    LD      BC, 6912
    LDIR

    INCLUDE "_exercise.asm"

scr_data:
    INCBIN  "screen.scr"
