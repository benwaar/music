"""MOD pattern data parser — extract NoteEvent objects from ProTracker files.

Parses all patterns referenced in the song order table, decoding 4-byte cell
format into pitch, volume, channel, and duration.  Speed/BPM state is tracked
via effect Fxx; pattern break (Dxx) truncates the current pattern early.
"""

from __future__ import annotations

import struct

from chant.schema import NoteEvent, Waveform

# ── Layout constants ──────────────────────────────────────────────────────────

_TITLE_LEN = 20
_INST_COUNT = 31
_INST_ENTRY_LEN = 30
_SONG_LENGTH_OFFSET = 950
_RESTART_OFFSET = 951
_ORDER_TABLE_OFFSET = 952
_ORDER_TABLE_LEN = 128
_MAGIC_OFFSET = 1080
_PATTERN_DATA_OFFSET = 1084

_ROWS_PER_PATTERN = 64
_BYTES_PER_CELL = 4

# Instrument entry field offsets (within the 30-byte entry)
_INST_VOLUME_OFFSET = 25

# Timing defaults (ProTracker)
_DEFAULT_BPM = 125
_DEFAULT_SPEED = 6  # ticks per row

# Effect nibbles
_EFFECT_SPEED_BPM = 0xF  # Fxx — set speed (<0x20) or BPM (>=0x20)
_EFFECT_PATTERN_BREAK = 0xD  # Dxx — jump to next pattern at row xx


def _period_to_hz(period: int) -> float:
    """Convert a MOD period value to musical pitch in Hz.

    Uses the note-table convention where period 428 = C-3 = 261.626 Hz
    (concert middle C).  The relationship is linear: halving the period
    doubles the frequency (one octave up).

    Note: period 0 is "no note" — callers must guard before calling.
    """
    # Reference: ProTracker C-3 period 428 ≡ 261.626 Hz (A4=440 Hz tuning)
    _C3_HZ = 261.6269
    _C3_PERIOD = 428
    return _C3_HZ * _C3_PERIOD / period


def _row_duration_ms(bpm: int, speed: int) -> float:
    """Duration of one row in milliseconds given current BPM and speed."""
    # One beat = 60000/bpm ms; one row = speed ticks; 24 ticks per beat
    return (60_000.0 / bpm) * speed / 24.0


def _read_instrument_volumes(data: bytes) -> list[float]:
    """Return normalised volumes (0.0–1.0) for all 31 instruments (1-indexed)."""
    volumes: list[float] = [0.0]  # index 0 unused — instruments are 1-based
    for i in range(_INST_COUNT):
        offset = _TITLE_LEN + i * _INST_ENTRY_LEN + _INST_VOLUME_OFFSET
        raw = data[offset] if offset < len(data) else 0
        volumes.append(raw / 64.0)
    return volumes


def extract_mod_events(data: bytes, channels: int) -> list[NoteEvent]:
    """Parse all pattern data from a MOD file and return NoteEvent objects.

    Args:
        data:     Raw bytes of the full MOD file.
        channels: Channel count derived from the magic tag (4, 6, 8, …).

    Returns:
        Ordered list of NoteEvent objects (one per sounding cell, skipping
        period-0 / empty cells).
    """
    if len(data) < _PATTERN_DATA_OFFSET:
        return []

    song_length = data[_SONG_LENGTH_OFFSET]
    order_table = data[_ORDER_TABLE_OFFSET : _ORDER_TABLE_OFFSET + _ORDER_TABLE_LEN]

    # Determine which patterns to decode and in which order.
    pattern_sequence = list(order_table[:song_length])
    if not pattern_sequence:
        return []

    num_patterns = max(pattern_sequence) + 1
    pattern_size = channels * _ROWS_PER_PATTERN * _BYTES_PER_CELL

    inst_volumes = _read_instrument_volumes(data)

    events: list[NoteEvent] = []
    bpm = _DEFAULT_BPM
    speed = _DEFAULT_SPEED

    visited: set[int] = set()

    for pattern_idx in pattern_sequence:
        if pattern_idx in visited:
            # Skip already-decoded patterns to avoid duplicating looped intros,
            # but only on second+ visit at song level (simple loop guard).
            pass
        visited.add(pattern_idx)

        pat_offset = _PATTERN_DATA_OFFSET + pattern_idx * pattern_size
        if pat_offset + pattern_size > len(data):
            # Truncated file — stop here.
            break

        end_row = _ROWS_PER_PATTERN
        for row in range(end_row):
            row_ms = _row_duration_ms(bpm, speed)
            pattern_break = False

            for ch in range(channels):
                cell_offset = pat_offset + (row * channels + ch) * _BYTES_PER_CELL
                b0, b1, b2, b3 = struct.unpack_from("4B", data, cell_offset)

                sample_hi = (b0 & 0xF0)
                period = ((b0 & 0x0F) << 8) | b1
                sample_lo = (b2 & 0xF0) >> 4
                effect = (b2 & 0x0F)
                param = b3

                sample_num = (sample_hi >> 4) | sample_lo  # 1-based, 0 = none

                # Handle speed/BPM changes immediately (before note output)
                if effect == _EFFECT_SPEED_BPM:
                    if param == 0:
                        pass  # Fxx with param 0 is a no-op in ProTracker
                    elif param < 0x20:
                        speed = param
                        row_ms = _row_duration_ms(bpm, speed)
                    else:
                        bpm = param
                        row_ms = _row_duration_ms(bpm, speed)

                # Pattern break — finish this row then stop the pattern
                if effect == _EFFECT_PATTERN_BREAK:
                    pattern_break = True

                if period == 0:
                    continue  # no note

                pitch = _period_to_hz(period)
                volume: float
                if sample_num > 0 and sample_num < len(inst_volumes):
                    volume = inst_volumes[sample_num]
                else:
                    volume = 1.0

                events.append(
                    NoteEvent(
                        pitch_hz=pitch,
                        duration_ms=row_ms,
                        channel=ch,
                        waveform=Waveform.PCM,
                        volume=volume,
                    )
                )

            if pattern_break:
                break

    return events
