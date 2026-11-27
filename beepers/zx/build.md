# Build pipelines

## Setup

```bash
./setup.sh    # check/install all dependencies
```

Installs pasmo, Fuse, Rust wasm32 target, binaryen, and vsti npm deps. Run once on a new machine.

## TAP target (standalone / Fuse)

`.asm` → `.bin` → `.tap` → Fuse

If `screen.jpg` exists, the build auto-converts it to `.scr` (via `png2scr.py`) and wraps each exercise with a screen loader (`screen.asm` INCBINs the SCR data and LDIRs it to `$4000`).

### 1. Assemble

`pasmo --bin 1.1.asm 1.1.bin`

Pasmo takes Z80 assembly and produces raw machine code bytes. No headers, no metadata — just the opcodes.

### 2. Wrap in TAP

`tap.py` wraps the binary in a TAP file with four blocks:

| Block | Type | Contents |
|-------|------|----------|
| 1 | BASIC header | "here comes a program called beeper" |
| 2 | BASIC data | `10 CLEAR 32767: LOAD ""CODE: RANDOMIZE USR 32768` |
| 3 | CODE header | "here comes N bytes of code for address 32768" |
| 4 | CODE data | your machine code bytes |

The BASIC loader does three things on one line:
- **CLEAR 32767** — moves RAMTOP below 0x8000 so BASIC won't overwrite the code
- **LOAD ""CODE** — loads the next tape block (your binary) into memory at 0x8000
- **RANDOMIZE USR 32768** — jumps to it

### 3. Run in Fuse

`./play.sh 1.1` builds and opens the TAP in the Fuse ZX Spectrum emulator (`brew install --cask fredm-fuse`).

### Usage

```bash
./build.sh 1.1       # build only
./play.sh 1.1        # build + open in Fuse
./play.sh             # build latest .asm + open in Fuse
```

---

## VSTi target (openDAW)

`.bin` → WASM Z80 core → AudioWorklet → openDAW instrument

The VSTi wraps a Z80 CPU emulator (Rust → WASM) inside a Web Audio AudioWorklet. MIDI noteOn/noteOff from openDAW's piano roll drives the beeper engine at the requested pitch.

### Architecture

```
Piano Roll → [beeper-node.ts] → AudioWorklet → [chip-synth-processor.ts]
                                                       ↓
                                               [z80-core.wasm]
                                                       ↓
                                              OUT ($FE) speaker bit
                                                       ↓
                                              1-bit audio → mixer
```

### Build

```bash
./build-vsti.sh              # full build (WASM + worklet + host)
./build-vsti.sh --skip-wasm  # TypeScript only (faster iteration)
```

All prerequisites are handled by `./setup.sh`.
