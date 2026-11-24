# Quirks — things the original engines got "wrong" that we fixed

Some of these are genuine bugs. Others add character. The beeper scene often prefers the charming version over the correct one. Several of these quirks are accidental versions of techniques taught in later engines — noted with **→ see Engine N**.

---

## 1ch engine (vs reference/1ch_tone.asm)

### OUT every iteration
The reference does `OUT (0xFE), A` on every loop pass, even when the speaker state hasn't changed. We OUT only on toggle. The redundant OUTs don't affect pitch, but they do keep the border colour refreshed every iteration — some engines use this for visual effects (colour bars synced to the music).

**→ see Engine 2 (duty cycle).** Constant OUT is not a quirk there — it's required. The hi/lo phase split means you output 0x11 during the high phase and 0x01 during the low phase, every pass. Our "OUT only on toggle" optimisation would break duty cycle engines.

### XOR 0x10 vs XOR 0x18
Early exercises used `XOR 0x10` (EAR bit only). The reference uses `XOR 0x18` (EAR + MIC bits). Driving both is louder on real hardware — the MIC output adds a second signal path through the tape socket. On emulators the difference is subtle.

**→ see Engine 4 (accent, 4.8–4.10).** This is a two-level volume trick: XOR 0x18 (loud, both bits) vs XOR 0x10 (quiet, one bit). The reference always uses 0x18. Engine 4 makes the choice per-note — accented notes get 0x18, unaccented get 0x10.

### Speaker reset between notes
The reference does `XOR A` before each note, resetting the speaker to OFF. This causes a click at every note boundary. We let the speaker state carry over — smoother transitions, but the initial phase of each note is unpredictable (depends on where the previous note left off). The clicks give the original a more percussive, rhythmic feel.

**→ see Engine 4 (accent, 4.8–4.10).** The note-boundary click is an accidental accent — a brief transient that the ear uses to separate notes. Engine 4 makes this deliberate: an accent flag per note controls whether the attack is sharp or smooth.

---

## 2ch engine (vs Manic Miner, 1983)

### IY reload (19T) vs register reload (4T)
The original reloads period from `(IY+1)` at 19T per toggle. We copy the period into H/L at note start and reload from register at 4T. Faster — but the original's slower reload contributes to its characteristic sluggish, warm tone. The extra T-states per toggle slightly detune the note in a way that changes with pitch (higher notes have more toggles per second, so the detuning effect is stronger).

**→ see Engine 2 (duty cycle, 2.1–2.8).** The toggle overhead makes the ON phase slightly longer than the OFF phase — an accidental duty cycle shift. Engine 2 makes this explicit: separate hi_period and lo_period values control the phase ratio, shaping timbre from the same pitch.

### OUT every iteration (the "always-on speaker" sound)
The original outputs the speaker state every single loop pass. Even when nothing has toggled, the OUT refreshes the hardware. On real Spectrums with imperfect signal paths, this constant refreshing produces a faint background hum — the characteristic "beeper hiss" that tells you the engine is running. Our OUT-on-toggle approach is cleaner but loses this texture.

**→ see Engine 2 (duty cycle).** Same as the 1ch quirk — constant OUT is the foundation of duty cycle engines, not a waste.

### XOR A note reset (the clicks)
Same as 1ch — the original resets speaker state to 0 at each note start. The click this produces is part of the Manic Miner sound. Without it, notes blend into each other more smoothly, which sounds "better" in isolation but loses the rhythmic articulation that made the Blue Danube recognisable on the Spectrum.

**→ see Engine 4 (accent, 4.8–4.10).** Same connection as the 1ch version — accidental articulation that Engine 4 makes controllable.

### REST by overflow (period 0)
When both periods are 0, `DEC D` wraps 0→255 and counts down for 255 iterations before hitting zero and firing one stray toggle. The original relies on this — it's not intentional silence, it's "so quiet you barely notice." For single-channel rest (e.g. note 92: ch1=128, ch2=0), ch2 fires ~25 stray toggles during the note, adding a faint high-pitched artefact. We substitute 255 for period 0, which still fires one toggle per 255 iterations but does so predictably.

**→ see Engine 3 (noise, 3.1–3.3).** The stray toggles from period-0 wrapping are irregular, low-energy clicks — a faint noise artefact. Engine 3 makes this deliberate: a PRNG drives the speaker randomly, producing hiss, snare, and kick drum sounds. The accidental rest noise is a baby version of a noise channel.

### Unbalanced toggle paths
The original's toggle path is 33T (JR fall + LD + XOR = 7+19+7) vs no-toggle path 12T (JR taken). That 21T difference means the loop runs slower whenever a channel toggles. Since toggles happen at the note's frequency, higher-pitched notes slow the loop more — a subtle pitch compression where high notes play slightly flatter than calculated. Our engine has the same asymmetry (22T vs 12T) but less of it (17T overhead vs 21T).

**→ see Engine 4 (vibrato/LFO, 4.4–4.7).** The pitch-dependent timing jitter is an accidental vibrato — the pitch wobbles as the toggle overhead varies cycle to cycle. Engine 4 makes this deliberate: add/subtract from the period on a schedule to create controlled pitch wobble (vibrato) or pitch sweep.

### The "46T" myth
The original Manic Miner code comment and various references claim the loop is 46 T-states. It's actually 56T (OUT 11 + DEC D 4 + JR NZ 12 + DEC E 4 + JR NZ 12 + DJNZ 13). The periods in the note table were likely tuned by ear against the game, not calculated from the formula. This means the original Blue Danube is pitched about a major third flat of concert pitch — but it sounds right because all the intervals are internally consistent.

---

## Duty cycle engine (vs reference/sp83_duty_cycle.asm, Splat! 1983)

### Global frame counter vs per-note duration
The original uses DE as a global frame counter (216 frames) — every frame is the same length, and the entire tune is a flat stream of hi/lo pairs with no note boundaries. Our `1ch_duty.asm` adds a duration byte per note (3-byte entries: hi, lo, duration), so notes can be held or shortened. The original approach is simpler but means tempo is locked to frame rate — you can't hold a note longer without duplicating frames in the table.

### No sentinel
The original relies on DE counting down to zero — no 0xFF end marker. If DE is wrong, playback runs off the end of the note table into whatever's in memory. Our engine uses 0xFF sentinel (consistent with Engine 1). The sentinel costs 7T per note (CP 0xFF + RET Z) but makes the engine self-terminating regardless of table length.

### Raw game data vs musical note table
The sp83 note table is 216 frames of data extracted directly from the Splat! game binary. The duty ratios look arbitrary because they encode the actual game sound effects (not a musical scale). Our reference uses deliberate duty ratios on a D major scale to make the timbre differences audible and educational. The sp83 extraction is kept as-is for authenticity.
