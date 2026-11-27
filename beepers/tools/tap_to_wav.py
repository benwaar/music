#!/usr/bin/env python3
"""tap_to_wav.py — render a ZX Spectrum TAP file to WAV via Z80 emulation.

Loads the CODE block from a TAP, runs it in the z80 Python emulator,
captures every OUT ($FE) with its T-state timestamp, and downsamples
the 1-bit speaker output to a WAV file.

This is the true independent reference — it runs YOUR assembled binary,
not a reimplementation of the algorithm.

Requires: pip install z80
"""

import argparse
import os
import struct
import wave

CPU_CLOCK = 3_500_000
MEM_OFFSET = 44  # z80 library: state_view has 44 bytes of CPU state before 64K memory


def parse_tap(tap_path):
    """Extract CODE block from a TAP file. Returns (data, load_addr)."""
    with open(tap_path, 'rb') as f:
        raw = f.read()

    pos = 0
    header_info = None

    while pos < len(raw):
        if pos + 2 > len(raw):
            break
        block_len = int.from_bytes(raw[pos:pos+2], 'little')
        pos += 2
        if pos + block_len > len(raw):
            break

        block = raw[pos:pos+block_len]
        pos += block_len

        flag = block[0]

        if flag == 0x00 and len(block) >= 18:
            # header block
            block_type = block[1]
            filename = block[2:12].decode('ascii', errors='replace').strip()
            data_len = int.from_bytes(block[12:14], 'little')
            param1 = int.from_bytes(block[14:16], 'little')
            param2 = int.from_bytes(block[16:18], 'little')
            if block_type == 3:  # CODE block
                header_info = {'name': filename, 'len': data_len, 'addr': param1}

        elif flag == 0xFF and header_info is not None:
            # data block following a CODE header
            data = block[1:-1]  # strip flag and checksum
            return data, header_info['addr']

    raise ValueError(f'no CODE block found in {tap_path}')


def emulate_and_capture(binary, load_addr, max_seconds=30):
    """Run binary in Z80 emulator, capture speaker toggles.

    Returns list of (t_state, speaker_bit) tuples.
    """
    from z80._machine import Z80Machine

    FRAME_TICKS = 69888  # T-states per Spectrum frame

    m = Z80Machine()
    sv = m.get_state_view()

    # clear memory
    for i in range(65536):
        sv[MEM_OFFSET + i] = 0

    # load binary at load_addr
    for i, b in enumerate(binary):
        sv[MEM_OFFSET + load_addr + i] = b

    # skip screen loader — start at DI (0xF3)
    engine_start = load_addr
    for i in range(len(binary) - 1):
        if binary[i] == 0xF3:
            engine_start = load_addr + i
            break

    m.pc = engine_start
    m.sp = 0xFFFF

    # track absolute T-states via frame_tick deltas
    # frame_tick wraps at ~100000 (not the Spectrum's 69888 — emulator internal)
    FRAME_SIZE = 100000
    toggles = []
    speaker = False
    total_t = [0]
    prev_tick = [m.frame_tick]

    def update_t():
        tick = m.frame_tick
        if tick >= prev_tick[0]:
            total_t[0] += tick - prev_tick[0]
        else:
            total_t[0] += (FRAME_SIZE - prev_tick[0]) + tick
        prev_tick[0] = tick

    def on_output(addr, val):
        nonlocal speaker
        update_t()
        port = addr & 0xFF
        if port == 0xFE:
            new_speaker = bool(val & 0x18)
            if new_speaker != speaker:
                speaker = new_speaker
                toggles.append(total_t[0])

    m.set_output_callback(on_output)

    # run until HALT or time limit
    max_t = max_seconds * CPU_CLOCK
    halted = False
    halt_opcode = 0x76

    while True:
        if sv[MEM_OFFSET + m.pc] == halt_opcode:
            halted = True
            break
        m.step_over_breakpoint()
        update_t()
        if total_t[0] >= max_t:
            break

    return toggles, total_t[0], halted


def downsample(toggles, total_ticks, sample_rate=44100):
    """Convert toggle timestamps to audio samples."""
    num_samples = int(total_ticks * sample_rate / CPU_CLOCK)
    output = []

    toggle_idx = 0
    speaker = False

    for s in range(num_samples):
        t_sample = (s * CPU_CLOCK) // sample_rate

        while toggle_idx < len(toggles) and toggles[toggle_idx] <= t_sample:
            speaker = not speaker
            toggle_idx += 1

        output.append(1.0 if speaker else -1.0)

    return output


def write_wav(path, samples, sample_rate=44100):
    """Write samples as 16-bit mono WAV."""
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            wf.writeframes(struct.pack('<h', int(clamped * 32767)))


def main():
    parser = argparse.ArgumentParser(
        description='Render a ZX Spectrum TAP to WAV via Z80 emulation')
    parser.add_argument('tap', help='Input TAP file')
    parser.add_argument('-o', '--output', default=None,
                        help='Output WAV path (default: <tap-name>.wav)')
    parser.add_argument('--sample-rate', type=int, default=44100)
    parser.add_argument('--max-seconds', type=int, default=30,
                        help='Max emulation time (default: 30s)')
    args = parser.parse_args()

    output = args.output or args.tap.rsplit('.', 1)[0] + '.wav'

    print(f'loading {args.tap}...')
    binary, load_addr = parse_tap(args.tap)
    print(f'  CODE block: {len(binary)} bytes at 0x{load_addr:04X}')

    print(f'emulating Z80 (max {args.max_seconds}s)...')
    toggles, total_ticks, halted = emulate_and_capture(
        binary, load_addr, args.max_seconds)
    seconds = total_ticks / CPU_CLOCK
    print(f'  {"HALTed" if halted else "timed out"} at {total_ticks} T-states ({seconds:.2f}s)')
    print(f'  captured {len(toggles)} speaker toggles')

    print(f'downsampling to {args.sample_rate} Hz...')
    samples = downsample(toggles, total_ticks, args.sample_rate)

    os.makedirs(os.path.dirname(output) or '.', exist_ok=True)
    write_wav(output, samples, args.sample_rate)
    print(f'wrote {len(samples)} samples ({len(samples)/args.sample_rate:.2f}s) to {output}')


if __name__ == '__main__':
    main()
