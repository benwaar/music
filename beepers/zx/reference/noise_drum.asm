; noise_drum.asm — 1-bit noise burst (percussion via PRNG)
;
; Technique: pseudo-random number generator drives speaker toggle.
; Random toggling = broadband noise = percussion sound.
;
; PRNG: "el cheapo" by Shiru — HL += DE each step, then rotate H.
; Fast, small, sounds convincingly noisy.
;
; The period between toggles controls the noise pitch:
;   short delay → high-frequency noise → hiss / hi-hat
;   long delay  → low-frequency noise  → thud / kick body
;
; Structure:
;   BURST: 64 random toggles at a fixed pitch → one drum hit
;   GAP:   silence between hits
;   loops forever
;
; Entry: no args — standalone, loops via JP START.

    ORG     0x8000

PRNG_INC    EQU 0x2157  ; increment for el cheapo PRNG (Shiru)
BURST_LEN   EQU 80      ; toggles per hit (longer = longer drum hit)
PITCH       EQU 3       ; delay between toggles (smaller = higher pitched)

START:
    LD      HL, 0x0001  ; PRNG seed (any non-zero)
    LD      DE, PRNG_INC
    LD      B, BURST_LEN
    DI

NOISE_LOOP:
    ; --- PRNG step ---
    ADD     HL, DE      ; HL = HL + DE (wraps 16-bit: linear congruential)
    RLC     H           ; rotate H left: spreads high bits into low bits

    ; --- Speaker output ---
    LD      A, H
    AND     0x10        ; extract bit 4 of H → 0x00 or 0x10 (EAR bit)
    ADD     A, 0x01     ; border = 1 (blue) so border flickers are subtle
    OUT     (0xFE), A

    ; --- Pitch delay ---
    LD      C, PITCH
PITCH_WAIT:
    DEC     C
    JR      NZ, PITCH_WAIT

    DJNZ    NOISE_LOOP  ; count BURST_LEN toggles

    ; --- Silence gap between hits ---
    LD      HL, 0x2000
GAP:
    DEC     HL
    LD      A, H
    OR      L
    JR      NZ, GAP

    JP      START       ; next hit
