"""XM pattern data parser — extract NoteEvent objects from FastTracker II files.

Parses all patterns referenced in the song order table, decoding XM's
run-length-style note compression into pitch/channel/volume/duration events.

Usage:
    events, info = extract_xm_events(data)
"""

from __future__ import annotations

import math
import struct

from chant.schema import NoteEvent, Waveform


# --- Header constants -----------------------------------------------------------

_XM_ID = b"Extended Module: "
_XM_ID_LEN = 17
_HEADER_SIZE_OFFSET = 60        # u32 LE — typically 276
_SONG_LENGTH_OFFSET = 64        # u16 LE
_NUM_CHANNELS_OFFSET = 68       # u16 LE
_NUM_PATTERNS_OFFSET = 70       # u16 LE
_SPEED_OFFSET = 76              # u16 LE (default ticks/row)
_BPM_OFFSET = 78                # u16 LE (default BPM)
_ORDER_TABLE_OFFSET = 80        # 256 bytes
_HEADER_BASE = 60               # patterns start at this + header_size

# --- Note constants -------------------------------------------------------------

_NOTE_OFF = 97
_VOLUME_SET_MIN = 0x10
_VOLUME_SET_MAX = 0x50

# XM compression flag bits
_FLAG_NOTE   = 0x01
_FLAG_INST   = 0x02
_FLAG_VOL    = 0x04
_FLAG_FX     = 0x08
_FLAG_FXPARM = 0x10

# Effect numbers
_FX_SET_SPEED = 0x0F
_FX_PATTERN_BREAK = 0x0D

# Speed/BPM threshold for Fxx effect
_FX_SPEED_THRESHOLD = 0x20

# Duration formula constant (matches MOD convention)
_MS_PER_TICK = 2500  # numerator; divide by BPM, multiply by speed (ticks/row)


# --- Public API -----------------------------------------------------------------


def extract_xm_events(data: bytes) -> tuple[list[NoteEvent], dict]:
    """Parse XM bytes and return (events, info).

    info keys: bpm, speed, num_channels, num_patterns, song_length, header_size.
    Skips unparseable patterns rather than raising.
    """
    if len(data) < 80:
        raise ValueError(f"XM data too short: {len(data)} bytes")

    if data[:_XM_ID_LEN] != _XM_ID:
        raise ValueError("Not an XM file: bad ID header")

    header_size = struct.unpack_from("<I", data, _HEADER_SIZE_OFFSET)[0]
    song_length = struct.unpack_from("<H", data, _SONG_LENGTH_OFFSET)[0]
    num_channels = struct.unpack_from("<H", data, _NUM_CHANNELS_OFFSET)[0]
    num_patterns = struct.unpack_from("<H", data, _NUM_PATTERNS_OFFSET)[0]
    speed = struct.unpack_from("<H", data, _SPEED_OFFSET)[0]
    bpm = struct.unpack_from("<H", data, _BPM_OFFSET)[0]

    # Guard against corrupt headers
    if num_channels == 0 or bpm == 0:
        raise ValueError(f"Invalid XM header: channels={num_channels} bpm={bpm}")
    if speed == 0:
        speed = 6  # sensible fallback

    order_table = list(data[_ORDER_TABLE_OFFSET: _ORDER_TABLE_OFFSET + song_length])

    # Read all pattern blocks sequentially from the data
    patterns: list[bytes] = _read_all_patterns(data, _HEADER_BASE + header_size, num_patterns)

    events: list[NoteEvent] = []
    cur_bpm = bpm
    cur_speed = speed

    for order_index, pattern_index in enumerate(order_table):
        if pattern_index >= len(patterns):
            continue
        packed = patterns[pattern_index]
        if not packed:
            continue
        try:
            pat_events, cur_bpm, cur_speed = _parse_pattern(
                packed, num_channels, cur_bpm, cur_speed
            )
        except Exception:
            # Malformed pattern — skip and continue
            continue
        events.extend(pat_events)

    info = {
        "bpm": bpm,
        "speed": speed,
        "num_channels": num_channels,
        "num_patterns": num_patterns,
        "song_length": song_length,
        "header_size": header_size,
    }
    return events, info


# --- Internal helpers -----------------------------------------------------------


def note_to_pitch(note: int) -> float:
    """Convert XM note number (1-96) to Hz.

    Note 49 = A-4 = 440 Hz. Formula: 440 * 2^((note - 49) / 12).
    """
    return 440.0 * math.pow(2.0, (note - 49) / 12.0)


def row_duration_ms(bpm: int, speed: int) -> float:
    """Duration of one row in milliseconds."""
    return (_MS_PER_TICK / bpm) * speed


def _read_all_patterns(data: bytes, start: int, num_patterns: int) -> list[bytes]:
    """Walk the data sequentially and collect packed pattern bytes for each slot."""
    patterns: list[bytes] = []
    offset = start
    for _ in range(num_patterns):
        if offset + 9 > len(data):
            break
        pat_header_len = struct.unpack_from("<I", data, offset)[0]
        num_rows = struct.unpack_from("<H", data, offset + 5)[0]
        packed_size = struct.unpack_from("<H", data, offset + 7)[0]
        body_start = offset + pat_header_len
        body_end = body_start + packed_size
        if packed_size > 0 and body_end <= len(data):
            patterns.append(data[body_start:body_end])
        else:
            patterns.append(b"")
        offset = body_end
    return patterns


def _decode_note_slot(packed: bytes, pos: int) -> tuple[int, int, int, int, int, int]:
    """Decode one note slot from packed data starting at pos.

    Returns (note, instrument, volume, effect_type, effect_param, bytes_consumed).
    Missing fields are 0.
    """
    if pos >= len(packed):
        return 0, 0, 0, 0, 0, 0

    first = packed[pos]
    if first & 0x80:
        # Compression flag byte
        flags = first
        idx = pos + 1
        note = inst = vol = fx = fxp = 0
        if flags & _FLAG_NOTE:
            note = packed[idx]; idx += 1
        if flags & _FLAG_INST:
            inst = packed[idx]; idx += 1
        if flags & _FLAG_VOL:
            vol = packed[idx]; idx += 1
        if flags & _FLAG_FX:
            fx = packed[idx]; idx += 1
        if flags & _FLAG_FXPARM:
            fxp = packed[idx]; idx += 1
        return note, inst, vol, fx, fxp, idx - pos
    else:
        # All 5 fields present
        if pos + 5 > len(packed):
            return 0, 0, 0, 0, 0, len(packed) - pos
        note = first
        inst = packed[pos + 1]
        vol  = packed[pos + 2]
        fx   = packed[pos + 3]
        fxp  = packed[pos + 4]
        return note, inst, vol, fx, fxp, 5


def _parse_pattern(
    packed: bytes,
    num_channels: int,
    bpm: int,
    speed: int,
) -> tuple[list[NoteEvent], int, int]:
    """Decode a packed pattern and return (events, updated_bpm, updated_speed)."""
    events: list[NoteEvent] = []
    pos = 0

    while pos < len(packed):
        # One full row: num_channels slots
        row_events: list[NoteEvent] = []
        row_bpm = bpm
        row_speed = speed

        for ch in range(num_channels):
            note, _inst, vol, fx, fxp, consumed = _decode_note_slot(packed, pos)
            pos += consumed

            # Handle Fxx speed/BPM change — applies from this row onwards
            if fx == _FX_SET_SPEED and fxp > 0:
                if fxp < _FX_SPEED_THRESHOLD:
                    row_speed = fxp
                else:
                    row_bpm = fxp

            # Pattern break — stop parsing this pattern
            if fx == _FX_PATTERN_BREAK:
                bpm = row_bpm
                speed = row_speed
                return events, bpm, speed

            # Skip no-note (0) and note-off (97)
            if note == 0 or note == _NOTE_OFF:
                continue

            pitch = note_to_pitch(note)
            dur = row_duration_ms(row_bpm, row_speed)

            volume: float | None = None
            if _VOLUME_SET_MIN <= vol <= _VOLUME_SET_MAX:
                volume = (vol - _VOLUME_SET_MIN) / 64.0

            row_events.append(NoteEvent(
                pitch_hz=pitch,
                duration_ms=dur,
                channel=ch,
                waveform=Waveform.PCM,
                volume=volume,
            ))

        bpm = row_bpm
        speed = row_speed
        events.extend(row_events)

    return events, bpm, speed
