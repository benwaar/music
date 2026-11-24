#!/usr/bin/env python3
"""test_plugin.py — headless VST3 test for Eno State ZX.

Loads the plugin, sends a MIDI scale, renders to WAV.
Used to verify the plugin works after each build.

Usage:
    python3 -I tools/test_plugin.py [path-to-vst3]

Default path: vsti/target/bundled/eno-state-zx.vst3
Requires: pip install pedalboard numpy
"""

import sys
from pathlib import Path

try:
    import numpy as np
    import pedalboard
    from pedalboard import load_plugin
    from pedalboard.io import AudioFile
except ImportError:
    print("error: pip install pedalboard numpy")
    sys.exit(1)

SAMPLE_RATE = 44100
NOTE_DURATION = 0.4
GAP_DURATION = 0.05
D_MAJOR = [62, 64, 66, 67, 69, 71, 73, 74]

DEFAULT_VST3 = Path(__file__).resolve().parent.parent / "vsti" / "target" / "bundled" / "eno-state-zx.vst3"


def main():
    vst3_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_VST3

    if not vst3_path.exists():
        print(f"error: {vst3_path} not found")
        print("build with: cd vsti && cargo xtask bundle eno-state-zx --features plugin")
        sys.exit(1)

    print(f"loading: {vst3_path}")
    plugin = load_plugin(str(vst3_path))
    print(f"plugin: {plugin.name} (instrument={plugin.is_instrument})")

    for name in plugin.parameters.keys():
        print(f"  param: {name} = {getattr(plugin, name, '?')}")

    # MIDI messages as (bytes, timestamp_seconds) tuples
    messages = []
    t = 0.0

    for note in D_MAJOR:
        messages.append((bytes([0x90, note, 100]), t))
        t += NOTE_DURATION
        messages.append((bytes([0x80, note, 0]), t))
        t += GAP_DURATION

    for note in reversed(D_MAJOR[:-1]):
        messages.append((bytes([0x90, note, 100]), t))
        t += NOTE_DURATION
        messages.append((bytes([0x80, note, 0]), t))
        t += GAP_DURATION

    total_duration = t + 0.5

    print(f"sending {len(messages)} MIDI messages over {total_duration:.1f}s...")
    output = plugin(
        messages,
        duration=total_duration,
        sample_rate=SAMPLE_RATE,
        num_channels=2,
    )

    peak = np.max(np.abs(output))
    print(f"rendered: {output.shape[1]} samples ({total_duration:.1f}s), peak={peak:.3f}")

    if peak < 0.01:
        print("WARNING: output is near-silent — plugin may not be responding to MIDI")
        sys.exit(1)

    out_path = Path(__file__).resolve().parent.parent / "vsti" / "test_plugin_output.wav"
    with AudioFile(str(out_path), "w", SAMPLE_RATE, num_channels=2) as f:
        f.write(output)
    print(f"wrote: {out_path}")
    print("PASS")


if __name__ == "__main__":
    main()
