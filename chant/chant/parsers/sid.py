"""SID file parser — extract metadata from C64 SID files.

SID files contain 6502 machine code that programs the MOS6581/8580 SID chip.
The header has fixed-offset metadata fields. Actual note event extraction
requires emulation (not implemented in M1 — metadata only).
"""

from __future__ import annotations

import struct
from pathlib import Path

from chant.schema import ChipType, NoteTable, TrackMetadata


# SID header offsets (v1/v2/v3/v4 — all share the same base layout)
_MAGIC_OFFSET = 0x00          # 4 bytes: PSID or RSID
_VERSION_OFFSET = 0x04        # uint16 big-endian
_NUM_SONGS_OFFSET = 0x0E      # uint16 big-endian
_TITLE_OFFSET = 0x16          # 32 bytes ASCII null-padded
_AUTHOR_OFFSET = 0x36         # 32 bytes ASCII null-padded
_RELEASED_OFFSET = 0x56       # 32 bytes ASCII null-padded
_FLAGS_OFFSET = 0x76          # uint16 big-endian (v2+)


def _read_string(data: bytes, offset: int, length: int) -> str:
    raw = data[offset : offset + length]
    return raw.split(b"\x00", 1)[0].decode("latin-1", errors="replace").strip()


def _parse_chip(flags: int) -> ChipType:
    sid_model = (flags >> 4) & 0x03
    if sid_model == 2:
        return ChipType.MOS8580
    return ChipType.MOS6581


def parse_sid(path: Path) -> NoteTable:
    """Parse a SID file into a NoteTable (metadata only, no events)."""
    data = path.read_bytes()

    if len(data) < 0x76:
        raise ValueError(f"SID file too short: {len(data)} bytes")

    magic = data[_MAGIC_OFFSET : _MAGIC_OFFSET + 4]
    if magic not in (b"PSID", b"RSID"):
        raise ValueError(f"Not a SID file: magic={magic!r}")

    version = struct.unpack_from(">H", data, _VERSION_OFFSET)[0]
    num_songs = struct.unpack_from(">H", data, _NUM_SONGS_OFFSET)[0]

    title = _read_string(data, _TITLE_OFFSET, 32)
    author = _read_string(data, _AUTHOR_OFFSET, 32)
    released = _read_string(data, _RELEASED_OFFSET, 32)

    chip = ChipType.MOS6581
    if version >= 2 and len(data) > _FLAGS_OFFSET + 2:
        flags = struct.unpack_from(">H", data, _FLAGS_OFFSET)[0]
        chip = _parse_chip(flags)

    channels = 3
    if version >= 3 and len(data) > 0x7C:
        second_sid = data[0x7A]
        if second_sid > 0:
            channels = 6

    metadata = TrackMetadata(
        source_format="sid",
        source_path=str(path),
        title=title,
        author=author,
        chip=chip,
        channels=channels,
        sub_songs=num_songs,
        extra={
            "magic": magic.decode("ascii"),
            "version": version,
            "released": released,
        },
    )

    return NoteTable(metadata=metadata, events=[])
