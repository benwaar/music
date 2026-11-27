"""VGM/VGZ file parser — extract metadata from Video Game Music files.

VGM files encode raw register writes for various sound chips. VGZ files are
gzip-compressed VGM. The GD3 tag (when present) has 11 UTF-16LE strings
with track, game, system, and author info. Some older files have garbled
UTF-16 encoding.
"""

from __future__ import annotations

import gzip
import struct
from pathlib import Path

from chant.schema import ChipType, NoteTable, TrackMetadata


_GD3_FIELDS = [
    "track_en", "track_jp",
    "game_en", "game_jp",
    "system_en", "system_jp",
    "author_en", "author_jp",
    "date", "ripper", "notes",
]


def _load_vgm(path: Path) -> bytes:
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def _parse_gd3(data: bytes, gd3_abs: int) -> dict[str, str]:
    if gd3_abs + 12 > len(data):
        return {}

    magic = data[gd3_abs : gd3_abs + 4]
    if magic != b"Gd3 ":
        return {}

    gd3_length = struct.unpack_from("<I", data, gd3_abs + 8)[0]
    gd3_data = data[gd3_abs + 12 : gd3_abs + 12 + gd3_length]

    result: dict[str, str] = {}
    pos = 0
    for field_name in _GD3_FIELDS:
        end = gd3_data.find(b"\x00\x00", pos)
        if end == -1:
            break
        if end % 2 != 0:
            end += 1
        try:
            value = gd3_data[pos:end].decode("utf-16-le", errors="replace").strip()
        except (UnicodeDecodeError, ValueError):
            value = ""
        if value:
            result[field_name] = value
        pos = end + 2

    return result


def _detect_chip(data: bytes) -> tuple[ChipType | None, int]:
    """Detect the primary chip and estimate channel count."""
    sn76489_clock = struct.unpack_from("<I", data, 0x0C)[0] if len(data) > 0x10 else 0
    ym2612_clock = struct.unpack_from("<I", data, 0x2C)[0] if len(data) > 0x30 else 0

    if ym2612_clock and sn76489_clock:
        return ChipType.YM2612, 10  # 6 FM + 4 PSG
    if ym2612_clock:
        return ChipType.YM2612, 6
    if sn76489_clock:
        return ChipType.SN76489, 4
    return None, 0


def parse_vgm(path: Path) -> NoteTable:
    """Parse a VGM/VGZ file into a NoteTable (metadata only)."""
    data = _load_vgm(path)

    if len(data) < 0x40:
        raise ValueError(f"VGM file too short: {len(data)} bytes")

    magic = data[0:4]
    if magic != b"Vgm ":
        raise ValueError(f"Not a VGM file: magic={magic!r}")

    gd3_rel = struct.unpack_from("<I", data, 0x14)[0]
    gd3 = _parse_gd3(data, 0x14 + gd3_rel) if gd3_rel else {}

    chip, channels = _detect_chip(data)

    title = gd3.get("track_en", "")
    author = gd3.get("author_en", "")

    metadata = TrackMetadata(
        source_format="vgm",
        source_path=str(path),
        title=title if title else path.stem,
        author=author,
        chip=chip,
        channels=channels,
        extra={
            "gd3": gd3,
            "is_compressed": path.suffix.lower() == ".vgz",
        },
    )

    return NoteTable(metadata=metadata, events=[])
