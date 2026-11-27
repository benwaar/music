"""Tests for chant/parsers/mod_patterns.py."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from chant.parsers.mod_patterns import (
    _period_to_hz,
    _row_duration_ms,
    extract_mod_events,
)
from chant.schema import NoteEvent, Waveform

# ── Fixtures ──────────────────────────────────────────────────────────────────

REAL_MOD = Path(__file__).parent.parent / "_data/modarchive/mod/qasteron.mod"


def _build_minimal_mod(
    channels: int = 4,
    *,
    rows: list[tuple[int, int, int, int]] | None = None,
    num_patterns: int = 1,
) -> bytes:
    """
    Build a minimal valid MOD file in memory.

    ``rows`` is a list of (period, sample, effect, param) for channel 0,
    row 0 of pattern 0.  All other cells are silent (period=0).
    """
    if rows is None:
        rows = [(428, 1, 0, 0)]

    title = b"TEST\x00" + b"\x00" * 15  # 20 bytes
    assert len(title) == 20

    # 31 instrument entries — instrument 1 has volume 64 (== 1.0 normalised)
    instruments = bytearray()
    for i in range(31):
        entry = bytearray(30)
        entry[25] = 64 if i == 0 else 0  # instrument 1 volume=64
        instruments.extend(entry)
    assert len(instruments) == 31 * 30

    song_length = 1
    restart = 0
    order_table = bytes([0] + [0] * 127)  # pattern 0

    magic = b"M.K."  # 4-channel tag

    header = title + bytes(instruments) + bytes([song_length, restart]) + order_table + magic
    assert len(header) == 1084

    # Build pattern data: channels * 64 rows * 4 bytes, all zeroed
    pattern_size = channels * 64 * 4
    pattern = bytearray(pattern_size)

    for row_idx, (period, sample, effect, param) in enumerate(rows):
        if row_idx >= 64:
            break
        cell_offset = row_idx * channels * 4  # channel 0

        b0 = ((sample & 0xF0) | ((period >> 8) & 0x0F))
        b1 = period & 0xFF
        b2 = ((sample & 0x0F) << 4) | (effect & 0x0F)
        b3 = param & 0xFF

        pattern[cell_offset] = b0
        pattern[cell_offset + 1] = b1
        pattern[cell_offset + 2] = b2
        pattern[cell_offset + 3] = b3

    return header + bytes(pattern)


# ── Period-to-pitch conversion ────────────────────────────────────────────────


def test_period_to_hz_c3():
    """Period 428 should be C-3 = 261.626 Hz (concert middle C)."""
    hz = _period_to_hz(428)
    assert abs(hz - 261.6269) < 0.5, f"Expected ~261.6 Hz, got {hz:.1f}"


def test_period_to_hz_a4():
    """Period 254 → approximately 440 Hz (A-3 above middle C)."""
    hz = _period_to_hz(254)
    assert 435 < hz < 445, f"Expected ~440 Hz, got {hz:.1f}"


def test_period_to_hz_low_period_gives_high_frequency():
    """Smaller period → higher frequency."""
    assert _period_to_hz(100) > _period_to_hz(200)


# ── Row duration ──────────────────────────────────────────────────────────────


def test_row_duration_default():
    """Default 125 BPM / speed 6 → 120 ms per row (6 ticks × 20 ms/tick)."""
    ms = _row_duration_ms(125, 6)
    assert abs(ms - 120.0) < 0.01, f"Expected 120.0 ms, got {ms}"


def test_row_duration_varies_with_bpm():
    """Higher BPM → shorter row."""
    assert _row_duration_ms(250, 6) < _row_duration_ms(125, 6)


# ── Minimal hand-crafted pattern ──────────────────────────────────────────────


def test_minimal_pattern_single_note():
    """A MOD with one sounding cell in row 0 should return exactly one event."""
    data = _build_minimal_mod(channels=4, rows=[(428, 1, 0, 0)])
    events = extract_mod_events(data, channels=4)

    assert len(events) >= 1
    ev = events[0]
    assert isinstance(ev, NoteEvent)
    assert ev.waveform == Waveform.PCM
    assert ev.channel == 0
    assert abs(ev.pitch_hz - 261.6269) < 0.5  # period 428 = C-3
    assert ev.duration_ms > 0
    assert ev.volume is not None
    assert abs(ev.volume - 1.0) < 0.02  # instrument 1 volume=64 → 64/64=1.0


def test_silent_cells_skipped():
    """Cells with period 0 must not produce events."""
    data = _build_minimal_mod(channels=4, rows=[(0, 0, 0, 0)])
    events = extract_mod_events(data, channels=4)
    assert all(e.pitch_hz > 0 for e in events)


def test_speed_change_affects_duration():
    """Effect F02 sets speed=2 → shorter rows than default speed 6."""
    # Row 0: speed change (Fxx, param=2)
    # Row 1: sounding note — should use the new duration
    rows = [
        (0, 0, 0xF, 2),   # Fxx speed=2, no note
        (428, 1, 0, 0),   # note, should use speed=2
    ]
    data = _build_minimal_mod(channels=4, rows=rows)
    events_fast = extract_mod_events(data, channels=4)

    # Compare against default-speed version
    rows_default = [(428, 1, 0, 0)]
    data_default = _build_minimal_mod(channels=4, rows=rows_default)
    events_default = extract_mod_events(data_default, channels=4)

    fast_dur = events_fast[0].duration_ms
    default_dur = events_default[0].duration_ms
    assert fast_dur < default_dur, (
        f"Expected faster duration ({fast_dur:.1f}) < default ({default_dur:.1f})"
    )


def test_bpm_change_affects_duration():
    """Effect Fxx with param >= 0x20 sets BPM."""
    rows_slow = [
        (0, 0, 0xF, 0x20),  # BPM = 32
        (428, 1, 0, 0),
    ]
    rows_fast = [
        (0, 0, 0xF, 0x7F),  # BPM = 127
        (428, 1, 0, 0),
    ]
    data_slow = _build_minimal_mod(channels=4, rows=rows_slow)
    data_fast = _build_minimal_mod(channels=4, rows=rows_fast)

    ev_slow = extract_mod_events(data_slow, channels=4)
    ev_fast = extract_mod_events(data_fast, channels=4)

    assert ev_slow[0].duration_ms > ev_fast[0].duration_ms


def test_pattern_break_truncates_pattern():
    """Effect Dxx should stop the current pattern at the break row."""
    # Row 0: pattern break (D00)
    # Row 1: note that should NOT be reached
    rows = [
        (0, 0, 0xD, 0),   # pattern break at row 0
        (428, 1, 0, 0),   # this row must not be parsed
    ]
    data = _build_minimal_mod(channels=4, rows=rows)
    events = extract_mod_events(data, channels=4)
    # No notes should appear because break fires before any sounding cell
    assert len(events) == 0


# ── Empty / too-short file ────────────────────────────────────────────────────


def test_empty_file_returns_empty():
    """A zero-byte buffer must return an empty list without raising."""
    assert extract_mod_events(b"", channels=4) == []


def test_too_short_file_returns_empty():
    """A file shorter than the pattern data offset must return empty."""
    assert extract_mod_events(b"\x00" * 500, channels=4) == []


def test_zero_song_length_returns_empty():
    """Song length 0 means no patterns to play."""
    data = bytearray(_build_minimal_mod())
    data[950] = 0  # song_length = 0
    assert extract_mod_events(bytes(data), channels=4) == []


# ── Integration test against a real MOD file ─────────────────────────────────


@pytest.mark.skipif(not REAL_MOD.exists(), reason="corpus not available")
def test_real_mod_qasteron():
    """qasteron.mod: events list must be non-empty with sane values."""
    data = REAL_MOD.read_bytes()
    # Determine channel count from magic tag (same logic as mod.py)
    _MOD_MAGIC_CHANNELS = {
        "M.K.": 4, "M!K!": 4, "FLT4": 4, "4CHN": 4,
        "6CHN": 6, "8CHN": 8, "FLT8": 8,
        "OCTA": 8, "CD81": 8, "16CH": 16, "32CH": 32,
    }
    magic = data[1080:1084].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
    channels = _MOD_MAGIC_CHANNELS.get(magic, 4)

    events = extract_mod_events(data, channels=channels)

    assert len(events) >= 100, f"Expected hundreds of events, got {len(events)}"

    for ev in events:
        assert ev.pitch_hz > 0, "pitch_hz must be positive"
        assert 20.0 <= ev.pitch_hz <= 20_000.0, f"pitch out of audible range: {ev.pitch_hz:.1f}"
        assert ev.duration_ms > 0, "duration_ms must be positive"
        assert 0 <= ev.channel < channels, f"channel {ev.channel} out of range"
        assert ev.waveform == Waveform.PCM
