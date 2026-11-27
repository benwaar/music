"""MOD/XM tracker module parser — extract metadata from ProTracker and FastTracker files.

MOD files have a title (20 bytes), 31 instrument names (22 bytes each), and a
magic tag at offset 1080 encoding the channel count. XM files have a proper
header with module name, tracker name, channel/instrument counts, and BPM.

Both formats embed rich instrument-level metadata — the tracker community used
instrument name fields as liner notes, credits, and greetings.
"""

from __future__ import annotations

import struct
from pathlib import Path

from chant.schema import ChipType, NoteTable, TrackMetadata
from chant.parsers.mod_patterns import extract_mod_events
from chant.parsers.xm_patterns import extract_xm_events


_MOD_MAGIC_CHANNELS: dict[str, int] = {
    "M.K.": 4, "M!K!": 4, "FLT4": 4, "4CHN": 4,
    "6CHN": 6, "8CHN": 8, "FLT8": 8,
    "OCTA": 8, "CD81": 8, "16CH": 16, "32CH": 32,
}

_MOD_TITLE_LEN = 20
_MOD_INST_COUNT = 31
_MOD_INST_ENTRY_LEN = 30
_MOD_INST_NAME_LEN = 22
_MOD_MAGIC_OFFSET = 1080


def _read_fixed(data: bytes, offset: int, length: int) -> str:
    raw = data[offset : offset + length]
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def parse_mod(path: Path) -> NoteTable:
    """Parse a MOD file into a NoteTable (metadata only)."""
    data = path.read_bytes()

    if len(data) < _MOD_MAGIC_OFFSET + 4:
        raise ValueError(f"MOD file too short: {len(data)} bytes")

    magic = _read_fixed(data, _MOD_MAGIC_OFFSET, 4)
    channels = _MOD_MAGIC_CHANNELS.get(magic, 4)

    title = _read_fixed(data, 0, _MOD_TITLE_LEN)

    instruments: list[str] = []
    for i in range(_MOD_INST_COUNT):
        offset = _MOD_TITLE_LEN + i * _MOD_INST_ENTRY_LEN
        name = _read_fixed(data, offset, _MOD_INST_NAME_LEN)
        if name:
            instruments.append(name)

    metadata = TrackMetadata(
        source_format="mod",
        source_path=str(path),
        title=title if title else path.stem,
        author="",
        chip=ChipType.MOD,
        channels=channels,
        extra={
            "magic": magic,
            "instruments": instruments,
        },
    )

    events = extract_mod_events(data, channels)
    return NoteTable(metadata=metadata, events=events)


_XM_ID = "Extended Module: "
_XM_ID_LEN = 17
_XM_NAME_OFFSET = 17
_XM_NAME_LEN = 20
_XM_TRACKER_OFFSET = 38
_XM_TRACKER_LEN = 20
_XM_CHANNELS_OFFSET = 68
_XM_INSTRUMENTS_OFFSET = 72
_XM_BPM_OFFSET = 78


def parse_xm(path: Path) -> NoteTable:
    """Parse an XM file into a NoteTable (metadata only)."""
    data = path.read_bytes()

    if len(data) < 80:
        raise ValueError(f"XM file too short: {len(data)} bytes")

    id_text = data[:_XM_ID_LEN].decode("ascii", errors="replace")
    if id_text != _XM_ID:
        raise ValueError(f"Not an XM file: id={id_text!r}")

    name = _read_fixed(data, _XM_NAME_OFFSET, _XM_NAME_LEN)
    tracker = _read_fixed(data, _XM_TRACKER_OFFSET, _XM_TRACKER_LEN)
    num_channels = struct.unpack_from("<H", data, _XM_CHANNELS_OFFSET)[0]
    num_instruments = struct.unpack_from("<H", data, _XM_INSTRUMENTS_OFFSET)[0]
    bpm = struct.unpack_from("<H", data, _XM_BPM_OFFSET)[0]

    metadata = TrackMetadata(
        source_format="xm",
        source_path=str(path),
        title=name if name else path.stem,
        author="",
        chip=ChipType.XM,
        channels=num_channels,
        extra={
            "tracker": tracker,
            "num_instruments": num_instruments,
            "bpm": bpm,
        },
    )

    events, _info = extract_xm_events(data)
    return NoteTable(metadata=metadata, events=events)
