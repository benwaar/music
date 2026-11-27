# Z80 Assembly — Quick Reference

Picked up while building beeper engines. Not exhaustive — just what's come up so far.

---

## Syntax basics

```asm
    ORG 0x8000          ; directives and instructions are indented
    LD A, 5             ; semicolon starts a comment (rest of line ignored)

loop:                   ; labels start at column 1, end with a colon
    DEC D               ; instructions must be indented (space or tab)
    JR NZ, loop         ; labels are case-sensitive: "loop" ≠ "Loop"

PERIOD  EQU 86          ; EQU constants also start at column 1
```

**Gotchas:**
- Indent with any whitespace (tab or spaces) — pasmo doesn't care. This project uses 4 spaces.
- Instructions at column 1 (no indent) → pasmo treats them as labels and you get weird errors
- Labels must start at column 1 — indented labels are silently ignored or misread
- No quotes around label names in jumps: `JR loop` not `JR "loop"`
- Commas separate operands: `LD A, 5` — missing the comma is an error
- Hex: `0x10` or `$10` or `10h` all work in pasmo. This project uses `0x` and `$` style.

---

## Registers

The Z80 has 8-bit registers: **A, B, C, D, E, H, L**.

- **A** (accumulator) — the main working register. Most arithmetic and all I/O goes through it (`OUT`, `XOR`, `AND`, `OR`, `CP`).
- **B, C, D, E, H, L** — general purpose. Used for counters, addresses, data.
- Registers pair up for 16-bit work: **BC**, **DE**, **HL**. HL is the most versatile pair — it can address memory directly.

---

## Key instructions

| Instruction | What it does |
|-------------|-------------|
| `LD dst, src` | Copy src into dst. Source unchanged. |
| `XOR val` | A = A XOR val. `XOR A` zeros A. `XOR 0x10` flips bit 4. |
| `OUT (port), A` | Send A to a hardware port. `OUT (0xFE), A` drives the speaker. |
| `DEC r` | Subtract 1 from register r. |
| `DJNZ label` | Decrement B, jump to label if B ≠ 0. A one-instruction delay loop. |
| `JR label` | Jump relative (short jump, ±127 bytes). |
| `JR NZ, label` | Jump if last result was not zero. |
| `JR Z, label` | Jump if last result WAS zero. |
| `HALT` | Stop the CPU until an interrupt. With DI active, stops permanently. |
| `LD A, (HL)` | Load A from the memory address HL points to. How you read data tables. 7 T. |
| `INC HL` | Increment HL by 1. Walks a pointer forward through memory. 6 T. |
| `CP val` | Compare: subtracts val from A but **doesn't change A** — only sets flags. `CP 0xFF` checks if A is 0xFF. 7 T. |
| `NOP` | Do nothing. 4 T. Used as timing padding to slow a loop down. |
| `CALL label` | Push return address onto the stack, jump to label. 17 T. Like a function call. |
| `RET` | Pop return address from the stack, jump back. 10 T. Returns from a CALL. |
| `RET Z` | Conditional return — only returns if the Z flag is set. 11 T (taken) / 5 T (not taken). |
| `PUSH rr` | Save a register pair (AF, BC, DE, HL) onto the stack. 11 T. |
| `POP rr` | Restore a register pair from the stack. 10 T. |
| `DI` | Disable interrupts. Stops the 50Hz system tick from messing with timing. |
| `LDIR` | Block copy: copies (HL) → (DE), increments both, decrements BC, repeats until BC=0. The Z80's `memcpy`. |

---

## T-states

A T-state is one tick of the Z80's clock. The Spectrum runs at 3.5 MHz, so 1 T-state ≈ 286 nanoseconds.

Every instruction takes a fixed number of T-states. Simple ones like `XOR` take 7. `DJNZ` takes 13 when looping, 8 on fall-through. `LDIR` takes thousands (it loops internally).

Counting T-states matters because the total directly determines the pitch — more T-states between toggles = lower frequency.

---

## Assembler directives

Directives are instructions to the assembler (pasmo), not to the Z80. They produce no opcodes at runtime.

| Directive | What it does |
|-----------|-------------|
| `ORG 0x8000` | "Put this code at address 32768." All labels and jumps are calculated from this base. |
| `EQU` | Compile-time constant. `PERIOD EQU 86` replaces every `PERIOD` with `86` before generating bytes. Like `#define` in C. Zero cost at runtime. |
| `INCBIN "file"` | Include raw binary data from a file. Used to embed screen data. |
| `DEFB val` | Define a byte of data inline. Used for note tables. |

---

## Memory map

| Address | What's there |
|---------|-------------|
| `$0000–$3FFF` | ROM — read only, can't use it |
| `$4000–$7FFF` | Screen RAM + system vars — writing here corrupts the display |
| `$8000+` | Free RAM — where your code goes (`ORG 0x8000`) |

---

## Speaker

- Port `$FE`, bit 4 (EAR output) drives the speaker.
- `XOR 0x10` flips the speaker state each call.
- `OUT (0xFE), A` sends the state to hardware.
- Toggle fast = high pitch. Toggle slow = low pitch. That's it.

---

## Nested loops and the LD B, 0 trick

When you need to count higher than 256, nest two counters:

```asm
    LD C, 4         ; outer counter — 4 groups
    LD B, 0         ; inner counter — 0 means 256!

inner:
    ; ... do work ...
    DEC B
    JR NZ, inner    ; 256 iterations per group

    DEC C
    JR Z, done      ; all groups finished
    LD B, 0         ; reload inner
    JR inner

done:
```

**Why `LD B, 0` = 256:** `DEC B` on 0 wraps to 255 (unsigned), then counts 255 → 254 → ... → 1 → 0. That's 256 decrements. Classic Z80 trick — saves a register and gives you a bigger range.

**Total iterations** = C × 256. With C=4, that's 1024.

---

## Flags and CP (compare)

The Z80 has a **flags register** (F) that's set automatically by most instructions. The key flag so far:

- **Z (zero flag)** — set when the result is zero. `DEC B` sets Z when B becomes 0. `CP 0xFF` sets Z when A equals 0xFF.

`CP` is "compare" — it subtracts a value from A but **throws away the result**. Only the flags change. This lets you test a value in A without destroying it:

```asm
    LD A, (HL)      ; load a byte from memory
    CP 0xFF         ; is it the sentinel?
    JR Z, done      ; yes — Z flag is set because A - 0xFF = 0
    LD C, A         ; no — A still holds the original value (CP didn't change it)
```

---

## Data tables with DEFB

`DEFB` places raw bytes into the assembled binary. Use it to build tables of data the engine reads at runtime:

```asm
note_table:
    DEFB 3, 86      ; duration=3, period=86
    DEFB 3, 60      ; duration=3, period=60
    DEFB 0xFF       ; sentinel — end of table
```

Walk the table with HL as a pointer: `LD A, (HL)` reads the current byte, `INC HL` moves to the next. The **sentinel pattern** (0xFF = "stop here") avoids needing to know the table length in advance.

---

## Frequency formula

The Spectrum runs at 3.5 MHz. The pitch of a beeper note depends on how many T-states pass between speaker toggles:

```
freq (Hz) = 3,500,000 / (2 × half-cycle T-states)
```

Factor of 2: one full wave = two toggles (HIGH then LOW).

For our engine, the half-cycle has two parts:
1. **Inner loop** — runs (period−1) times at some cost per iteration
2. **Toggle overhead** — runs once when the period hits zero

```
half-cycle = ((period − 1) × T-per-iteration) + toggle-overhead
```

**To find the period for a target note:**

```
period ≈ 1,750,000 / (freq × T-per-iteration)
```

This simplified version ignores the toggle overhead (fine for large periods). The exact version:

```
period = (1,750,000 / freq − toggle-overhead) / T-per-iteration + 1
```

**Why NOPs matter:** with a 16T inner loop, period=255 only reaches ~425 Hz. Adding 2 NOPs (→ 24T) slows each iteration enough that D4 (294 Hz) fits at period=248.

---

## Subroutines (CALL / RET)

`CALL label` is a function call — it pushes the return address onto the **stack** (a region of memory at the top of RAM) and jumps to `label`. `RET` pops that address and jumps back.

```asm
    LD HL, my_data      ; set up arguments in registers
    CALL play_tune      ; call the subroutine
    HALT                ; execution continues here after RET

play_tune:
    ; ... engine code, uses HL ...
    RET                 ; return to the instruction after CALL
```

`RET Z` is a conditional return — it only returns if the Z flag is set. Useful for sentinel checks: `CP 0xFF / RET Z` means "if end of table, return."

**The stack:** CALL pushes 2 bytes (the return address), RET pops them. The stack grows downward from high memory. You don't need to set it up — the Spectrum's BASIC loader leaves it in a usable state.

---

## Local labels (pasmo)

Labels prefixed with `.` are **local** — scoped to the enclosing global label. This stops name collisions when you have multiple subroutines with inner loops:

```asm
play_tune:
.loop:                  ; this is play_tune's .loop
    JR NZ, .loop        ; jumps to play_tune's .loop

other_routine:
.loop:                  ; different .loop — no collision
    JR NZ, .loop        ; jumps to other_routine's .loop
```

Without the `.` prefix, two labels named `loop` would be an assembler error. Local labels keep subroutines self-contained.

---

## PUSH / POP (saving registers)

When you need a register for two things — say A is the speaker state but you also need A to read a byte from memory — save it to the stack first:

```asm
    PUSH AF             ; save A + flags onto the stack     11 T
    LD A, (IY+0)        ; A is now free to use              19 T
    CP 0xFF             ; do work with A...                  7 T
    LD C, A             ; ...move the value somewhere safe   4 T
    POP AF              ; restore A to what it was before   10 T
    ; A is back to the speaker state — no data lost
```

**Rules:**
- PUSH and POP must be **balanced** — every PUSH needs exactly one POP
- They work on register **pairs**: AF, BC, DE, HL (not individual registers)
- Last-in-first-out: if you PUSH AF then PUSH BC, POP BC first, then POP AF
- Watch out for `RET` — if you PUSH'd something, you can't `RET` until you POP it (the stack is unbalanced and RET would jump to garbage)

---

## Index registers (IY)

The Z80 has two 16-bit **index registers**: **IX** and **IY**. They support **indexed addressing** — read memory at a fixed offset from the register:

```asm
    LD A, (IY+0)        ; load byte at address IY points to       19 T
    LD D, (IY+1)        ; load byte at IY+1 into D                19 T
    LD E, (IY+2)        ; load byte at IY+2 into E                19 T
```

**Why use IY instead of HL?** When you need a pointer that stays put while the loop runs. HL can only do `LD A, (HL)` — you have to `INC HL` to reach the next byte, which moves the pointer. IY lets you read any offset without moving: `(IY+0)`, `(IY+1)`, `(IY+2)` all work from the same base address.

The tradeoff: indexed reads are **slow** (19T vs 7T for `LD A, (HL)`). Fine for note-loading between notes or occasional reloads, bad for tight inner loops.

**Advancing IY:** there's no `ADD IY, 3`. You increment one at a time:

```asm
    INC IY              ; advance by 1                             10 T
    INC IY              ; advance by 2                             10 T
    INC IY              ; advance by 3                             10 T
```

| Instruction | T-states | Notes |
|-------------|----------|-------|
| `LD IY, addr` | 14 | Load 16-bit immediate into IY |
| `LD r, (IY+n)` | 19 | Read memory at IY+offset into any register |
| `INC IY` | 10 | Increment IY by 1 |
