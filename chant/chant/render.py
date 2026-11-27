"""Audio rendering via MIDI → chant-host → WAV pipeline.

Converts chant NoteEvents to a MIDI file, then calls the chant-host
binary (which uses eno-state-zx from crates.io) to render beeper audio.

Usage:
    python -m chant.render "A slow 4-channel MOD"
    python -m chant.render "A fast SID tune" -o out.wav --sample-rate 44100
    python -m chant.render --from-val 3
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import tempfile
from pathlib import Path

from chant.schema import NoteEvent, Waveform

# ---------------------------------------------------------------------------
# Binary discovery
# ---------------------------------------------------------------------------

_DEFAULT_HOST_PATH = Path(__file__).resolve().parent.parent / "synth" / "target" / "release" / "chant-host"

CHANT_HOST_PATH: Path = Path(
    os.environ.get("CHANT_HOST_PATH", str(_DEFAULT_HOST_PATH))
)

# ---------------------------------------------------------------------------
# MIDI constants
# ---------------------------------------------------------------------------

MIDI_PPQ = 480
MIDI_BPM = 120
_MS_PER_TICK = (60_000.0 / MIDI_BPM) / MIDI_PPQ  # ~1.0417 ms/tick

# MIDI CC numbers for metadata (ignored by chant-host, preserved for future engines)
CC_WAVEFORM = 70
CC_VOLUME = 7
CC_DUTY_CYCLE = 71

_WAVEFORM_CC_MAP: dict[Waveform | None, int] = {
    None: 0,
    Waveform.SQUARE: 0,
    Waveform.PULSE: 1,
    Waveform.TRIANGLE: 2,
    Waveform.SAWTOOTH: 3,
    Waveform.NOISE: 4,
    Waveform.FM: 5,
    Waveform.PCM: 6,
}

# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def hz_to_midi_note(hz: float) -> int:
    """Convert frequency in Hz to the nearest MIDI note number (0-127)."""
    if hz <= 0:
        return 0
    note = 69 + 12 * math.log2(hz / 440.0)
    return max(0, min(127, round(note)))


def ms_to_midi_ticks(ms: float) -> int:
    """Convert milliseconds to MIDI ticks at MIDI_PPQ / MIDI_BPM."""
    if ms <= 0:
        return 1
    return max(1, round(ms / _MS_PER_TICK))


def _volume_to_cc(volume: float | None) -> int:
    """Convert volume (0.0-1.0) to MIDI CC value (0-127). None → 100."""
    if volume is None:
        return 100
    return max(0, min(127, round(volume * 127)))


def _duty_to_cc(duty: float | None) -> int:
    """Convert duty cycle (0.0-1.0) to MIDI CC value (0-127). None → 64."""
    if duty is None:
        return 64
    return max(0, min(127, round(duty * 127)))


# ---------------------------------------------------------------------------
# MIDI file writing (raw bytes, no mido dependency)
# ---------------------------------------------------------------------------


def _write_vlq(value: int) -> bytes:
    """Encode an integer as MIDI variable-length quantity."""
    if value < 0:
        value = 0
    result = []
    result.append(value & 0x7F)
    value >>= 7
    while value > 0:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(result))


def _midi_tempo_bytes(bpm: int) -> bytes:
    """Create a MIDI Set Tempo meta event (microseconds per beat)."""
    us_per_beat = 60_000_000 // bpm
    return (
        b"\x00\xFF\x51\x03"
        + us_per_beat.to_bytes(3, "big")
    )


def events_to_midi(events: list[NoteEvent]) -> bytes:
    """Convert chant NoteEvents to a complete MIDI file (bytes).

    Single track, format 0. Includes CC messages for waveform, volume,
    and duty cycle metadata.
    """
    track_data = bytearray()

    # Tempo event at tick 0
    track_data += _midi_tempo_bytes(MIDI_BPM)

    for event in events:
        note = hz_to_midi_note(event.pitch_hz)
        ticks = ms_to_midi_ticks(event.duration_ms)
        channel = min(15, event.channel)

        # CC: waveform
        wf_cc = _WAVEFORM_CC_MAP.get(event.waveform, 0)
        track_data += _write_vlq(0)  # delta = 0
        track_data += bytes([0xB0 | channel, CC_WAVEFORM, wf_cc])

        # CC: volume
        track_data += _write_vlq(0)
        track_data += bytes([0xB0 | channel, CC_VOLUME, _volume_to_cc(event.volume)])

        # CC: duty cycle
        track_data += _write_vlq(0)
        track_data += bytes([0xB0 | channel, CC_DUTY_CYCLE, _duty_to_cc(event.duty_cycle)])

        # Note on (velocity 100)
        track_data += _write_vlq(0)
        track_data += bytes([0x90 | channel, note, 100])

        # Note off after duration
        track_data += _write_vlq(ticks)
        track_data += bytes([0x80 | channel, note, 0])

    # End of track
    track_data += b"\x00\xFF\x2F\x00"

    # Assemble: header + track
    track_bytes = bytes(track_data)
    header = (
        b"MThd"
        + (6).to_bytes(4, "big")       # header length
        + (0).to_bytes(2, "big")        # format 0
        + (1).to_bytes(2, "big")        # 1 track
        + MIDI_PPQ.to_bytes(2, "big")   # ticks per beat
    )
    track_chunk = (
        b"MTrk"
        + len(track_bytes).to_bytes(4, "big")
        + track_bytes
    )
    return header + track_chunk


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_to_wav(
    events: list[NoteEvent],
    output_path: Path,
    sample_rate: int = 44100,
    two_ch: bool = False,
    host_path: Path = CHANT_HOST_PATH,
) -> Path:
    """Render NoteEvents to a WAV file via MIDI → chant-host pipeline.

    Raises:
        FileNotFoundError: if the chant-host binary does not exist.
        RuntimeError: if chant-host exits with a non-zero return code.
    """
    resolved = host_path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"chant-host binary not found at {resolved}. "
            "Build it with `cargo build --release` in synth/, "
            "or set the CHANT_HOST_PATH environment variable."
        )

    midi_bytes = events_to_midi(events)

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".mid", delete=False
    ) as tmp:
        tmp.write(midi_bytes)
        tmp_path = Path(tmp.name)

    try:
        cmd = [
            str(resolved),
            str(tmp_path),
            "-o",
            str(output_path),
            "--sample-rate",
            str(sample_rate),
        ]
        if two_ch:
            cmd.append("--2ch")

        result = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"chant-host failed (exit {result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    return output_path


# ---------------------------------------------------------------------------
# Convenience: generate + render
# ---------------------------------------------------------------------------


def generate_and_render(
    prompt: str,
    output_path: Path,
    sample_rate: int = 44100,
    max_new_tokens: int = 512,
    temperature: float = 0.8,
    top_p: float = 0.9,
    host_path: Path = CHANT_HOST_PATH,
) -> Path:
    """Generate a NoteTable from a text prompt, then render to WAV."""
    from chant.generate import generate_sequence  # noqa: PLC0415

    result = generate_sequence(
        prompt,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
    )
    return render_to_wav(
        result.note_table.events,
        output_path,
        sample_rate=sample_rate,
        host_path=host_path,
    )


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

_RENDERS_DIR = Path("_data/chant_checkpoints/renders")


def _render_val_examples(n: int, sample_rate: int, host_path: Path) -> None:
    """Generate and render N val examples to _data/chant_checkpoints/renders/."""
    from chant.generate import _load_val_examples  # noqa: PLC0415

    captions = _load_val_examples(n)
    if not captions:
        print("No val examples found.")
        return

    _RENDERS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Rendering {len(captions)} val example(s) → {_RENDERS_DIR}\n")

    for i, caption in enumerate(captions, 1):
        out = _RENDERS_DIR / f"val_{i:03d}.wav"
        print(f"[{i}/{len(captions)}] {caption[:70]}")
        try:
            generate_and_render(
                caption,
                out,
                sample_rate=sample_rate,
                host_path=host_path,
            )
            print(f"  → {out}")
        except Exception as exc:
            print(f"  ERROR: {exc}")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate chip-tune audio from a text description"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Text description to generate and render",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("output.wav"),
        help="Output WAV file path (default: output.wav)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=44100,
        help="Sample rate in Hz (default: 44100)",
    )
    parser.add_argument(
        "--from-val",
        type=int,
        metavar="N",
        help=(
            "Generate and render N held-out val examples "
            f"to {_RENDERS_DIR}/"
        ),
    )
    parser.add_argument(
        "--host-path",
        type=Path,
        default=CHANT_HOST_PATH,
        help="Path to chant-host binary",
    )
    parser.add_argument(
        "--2ch",
        dest="two_ch",
        action="store_true",
        help="Use 2-channel beeper engine",
    )
    args = parser.parse_args()

    if args.from_val is not None:
        _render_val_examples(args.from_val, args.sample_rate, args.host_path)
    elif args.prompt:
        print(f"Generating and rendering: {args.prompt!r}")
        out = generate_and_render(
            args.prompt,
            args.output,
            sample_rate=args.sample_rate,
            host_path=args.host_path,
        )
        print(f"Written to {out}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
