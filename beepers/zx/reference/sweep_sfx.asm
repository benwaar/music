; sweep_sfx.asm — rising pitch sweep (laser / explosion effect)
;
; Technique: period counter decrements each audio cycle.
; Shrinking period = faster toggling = rising pitch.
;
; One audio cycle = HIGH phase (wait C counts) + LOW phase (wait C counts).
; After each cycle: DEC C → period shrinks → pitch rises.
; When C reaches 1 → JP START to restart sweep.
;
; Sound character depends on starting period:
;   high start (0xFF) → long sweep, bass up to treble
;   low start  (0x20) → short sweep, mid to treble
;   rapid DEC  (DEC C twice per cycle) → faster sweep = "laser up"
;   replace DEC with INC → falling pitch = "explosion / power down"
;
; Entry: no args — standalone, loops via JP START.

    ORG     0x8000

START_PERIOD    EQU 0xC0    ; starting period (high = low pitch)
INNER_WAIT      EQU 4       ; B count for inner delay loop

START:
    LD      C, START_PERIOD
    DI

; One outer iteration = one audio cycle at current period C
SWEEP_LOOP:
    ; --- HIGH phase ---
    LD      A, 0x11         ; EAR high + border blue
    OUT     (0xFE), A
    LD      B, INNER_WAIT
HI_WAIT:
    DJNZ    HI_WAIT         ; wait B×13 T-states
    ; Extra delay proportional to C
    LD      B, C
HI_C_WAIT:
    DJNZ    HI_C_WAIT

    ; --- LOW phase ---
    LD      A, 0x01         ; EAR low + border blue
    OUT     (0xFE), A
    LD      B, INNER_WAIT
LO_WAIT:
    DJNZ    LO_WAIT
    LD      B, C
LO_C_WAIT:
    DJNZ    LO_C_WAIT

    ; --- Sweep: shrink period ---
    DEC     C               ; smaller period → higher pitch
    JR      NZ, SWEEP_LOOP  ; until C reaches 0

    ; --- Gap between sweeps ---
    LD      A, 0x00         ; speaker off
    OUT     (0xFE), A
    LD      HL, 0x1800
GAP:
    DEC     HL
    LD      A, H
    OR      L
    JR      NZ, GAP

    EI
    JP      START           ; next sweep
