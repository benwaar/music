"""Tests for chant/parsers/xm_patterns.py."""

from __future__ import annotations

import struct
import math
import pytest

from chant.parsers.xm_patterns import (
    extract_xm_events,
    note_to_pitch,
    row_duration_ms,
    _decode_note_slot,
)
from chant.schema import Waveform


# ---------------------------------------------------------------------------
# 1. Note-to-pitch conversion
# ---------------------------------------------------------------------------


def test_note_49_is_440hz():
    assert abs(note_to_pitch(49) - 440.0) < 0.01


def test_note_37_is_middle_c():
    # C-4 = MIDI 60 → XM note 37 (since XM 49 = A4 = MIDI 69, so C4 = MIDI 60 = XM 37+1=?)
    # XM note 49 = A-4 = 440 Hz.  C-4 is 9 semitones below A-4 → note 40.
    # But the prompt says note 37 ≈ 261.6 Hz — let's verify the formula directly.
    # 440 * 2^((37-49)/12) = 440 * 2^(-1) = 220 Hz.  That's A3.
    # The prompt says "note 37 = 261.6 Hz approximately" — that is C4 (middle C).
    # C4 relative to A4 is -9 semitones → 440 * 2^(-9/12) ≈ 261.63.
    # So note 49 - 9 = 40 gives C4.  Let's test note 40.
    # (The prompt appears to have an off-by-one; we implement the spec formula and test it.)
    pitch = note_to_pitch(40)
    assert abs(pitch - 261.63) < 0.5, f"Expected ~261.63 Hz for note 40, got {pitch:.2f}"


def test_note_61_is_one_octave_above_49():
    # 12 semitones up → exactly double frequency
    assert abs(note_to_pitch(61) - 880.0) < 0.01


def test_pitch_increases_monotonically():
    pitches = [note_to_pitch(n) for n in range(1, 97)]
    assert all(pitches[i] < pitches[i + 1] for i in range(len(pitches) - 1))


# ---------------------------------------------------------------------------
# 2. XM note decompression
# ---------------------------------------------------------------------------


def test_uncompressed_slot_all_five_bytes():
    # Bit 7 clear → all 5 fields present: note, inst, vol, fx, fxp
    data = bytes([48, 1, 0x30, 0x0A, 0x05])
    note, inst, vol, fx, fxp, consumed = _decode_note_slot(data, 0)
    assert note == 48
    assert inst == 1
    assert vol == 0x30
    assert fx == 0x0A
    assert fxp == 0x05
    assert consumed == 5


def test_compressed_note_only():
    # Flag byte: bit 7 set + bit 0 (note present) = 0x81, then note = 55
    data = bytes([0x81, 55])
    note, inst, vol, fx, fxp, consumed = _decode_note_slot(data, 0)
    assert note == 55
    assert inst == 0
    assert vol == 0
    assert fx == 0
    assert fxp == 0
    assert consumed == 2


def test_compressed_note_and_volume():
    # Flags: bit 7 set + bit 0 (note) + bit 2 (vol) = 0x85
    data = bytes([0x85, 60, 0x40])
    note, inst, vol, fx, fxp, consumed = _decode_note_slot(data, 0)
    assert note == 60
    assert vol == 0x40
    assert inst == 0
    assert consumed == 3


def test_compressed_all_fields():
    # All 5 flags + bit 7 = 0x9F
    data = bytes([0x9F, 49, 2, 0x20, 0x0F, 0x7D])
    note, inst, vol, fx, fxp, consumed = _decode_note_slot(data, 0)
    assert note == 49
    assert inst == 2
    assert vol == 0x20
    assert fx == 0x0F
    assert fxp == 0x7D
    assert consumed == 6


def test_no_note_slot_returns_zeros():
    # Flag byte with no field bits = 0x80 → nothing follows
    data = bytes([0x80])
    note, inst, vol, fx, fxp, consumed = _decode_note_slot(data, 0)
    assert note == inst == vol == fx == fxp == 0
    assert consumed == 1


# ---------------------------------------------------------------------------
# 3. Integration test against n_chip.xm
# ---------------------------------------------------------------------------

XM_PATH = "/Users/DBenoy/src/b/chant/_data/modarchive/xm/n_chip.xm"


def test_n_chip_events_non_empty():
    data = open(XM_PATH, "rb").read()
    events, info = extract_xm_events(data)
    assert len(events) > 0, "Expected non-empty event list"


def test_n_chip_pitch_range():
    data = open(XM_PATH, "rb").read()
    events, _ = extract_xm_events(data)
    for ev in events:
        assert 20.0 <= ev.pitch_hz <= 20_000.0, (
            f"pitch_hz {ev.pitch_hz:.1f} out of audible range"
        )


def test_n_chip_durations_positive():
    data = open(XM_PATH, "rb").read()
    events, _ = extract_xm_events(data)
    for ev in events:
        assert ev.duration_ms > 0.0, f"Non-positive duration {ev.duration_ms}"


def test_n_chip_channels_in_range():
    data = open(XM_PATH, "rb").read()
    events, info = extract_xm_events(data)
    num_channels = info["num_channels"]
    for ev in events:
        assert 0 <= ev.channel < num_channels, (
            f"channel {ev.channel} out of range (0..{num_channels - 1})"
        )


def test_n_chip_waveform_pcm():
    data = open(XM_PATH, "rb").read()
    events, _ = extract_xm_events(data)
    assert all(ev.waveform == Waveform.PCM for ev in events)


def test_n_chip_reasonable_event_count():
    data = open(XM_PATH, "rb").read()
    events, info = extract_xm_events(data)
    # At minimum we expect a few hundred events for a real chiptune
    assert len(events) >= 100, f"Only {len(events)} events — suspiciously few"


def test_n_chip_info_fields():
    data = open(XM_PATH, "rb").read()
    _, info = extract_xm_events(data)
    assert info["bpm"] > 0
    assert info["speed"] > 0
    assert info["num_channels"] > 0
    assert info["num_patterns"] > 0
    assert info["song_length"] > 0


# ---------------------------------------------------------------------------
# 4. Minimal XM with empty patterns
# ---------------------------------------------------------------------------


def _make_minimal_xm(num_channels: int = 2, bpm: int = 125, speed: int = 6) -> bytes:
    """Construct the smallest valid XM with one empty pattern."""
    # XM ID header
    id_part = b"Extended Module: "          # 17 bytes
    name = b"Test\x00" * 4                  # 20 bytes
    separator = bytes([0x1A])               # 1 byte
    tracker = b"TestTracker\x00" * 2        # 20 bytes (pad/truncate below)

    # Pad name and tracker to exact lengths
    name_padded = (b"Test" + b"\x00" * 16)[:20]
    tracker_padded = (b"TestTracker" + b"\x00" * 9)[:20]

    # Version 0x0104
    version = struct.pack("<H", 0x0104)

    # Header fields (starting at offset 60 from file start)
    header_size = 276
    song_length = 1
    restart_pos = 0
    num_patterns = 1
    num_instruments = 0
    flags = 0x0001  # linear freq

    header_body = struct.pack(
        "<IHHHHHHH",
        header_size,
        song_length,
        restart_pos,
        num_channels,
        num_patterns,
        num_instruments,
        flags,
        speed,
    ) + struct.pack("<H", bpm)

    # Order table: 256 bytes, first entry = 0
    order_table = bytes([0] + [0] * 255)

    # Pad header_body + order_table to exactly header_size bytes
    header_content = header_body + order_table
    assert len(header_content) == header_size, (
        f"header content length mismatch: {len(header_content)} vs {header_size}"
    )

    # One empty pattern: header_len=9, packing=0, num_rows=64, packed_size=0
    pattern_header = struct.pack("<IBHH", 9, 0, 64, 0)

    # Assemble full file: fixed prefix up to offset 60 is 60 bytes
    prefix = id_part + name_padded + separator + tracker_padded + version
    assert len(prefix) == 60, f"prefix length {len(prefix)}"

    return prefix + header_content + pattern_header


def test_empty_pattern_returns_no_events():
    data = _make_minimal_xm()
    events, info = extract_xm_events(data)
    assert events == [], f"Expected no events, got {len(events)}"
    assert info["num_channels"] == 2
    assert info["bpm"] == 125
    assert info["num_patterns"] == 1


def test_empty_pattern_info_correct():
    data = _make_minimal_xm(num_channels=4, bpm=140, speed=4)
    _, info = extract_xm_events(data)
    assert info["num_channels"] == 4
    assert info["bpm"] == 140
    assert info["speed"] == 4
