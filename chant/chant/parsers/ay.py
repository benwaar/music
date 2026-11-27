"""AY (.emul) file parser — extract metadata from ZX Spectrum AY files.

ZXAYEMUL files contain AY-3-8910 chip music. The header uses relative
pointers (big-endian) to null-terminated strings. In practice, the
author field is often blank — the parent directory name and filename
carry the real title/author.
"""

from __future__ import annotations

import struct
from pathlib import Path

from chant.schema import ChipType, NoteTable, TrackMetadata


def _read_cstr(data: bytes, offset: int) -> str:
    try:
        end = data.index(0, offset)
        return data[offset:end].decode("ascii", errors="replace").strip()
    except (ValueError, IndexError):
        return ""


def parse_ay(path: Path) -> NoteTable:
    """Parse an AY (.emul) file into a NoteTable (metadata only, no events)."""
    data = path.read_bytes()

    if len(data) < 18:
        raise ValueError(f"AY file too short: {len(data)} bytes")

    magic = data[:8]
    if magic != b"ZXAYEMUL":
        raise ValueError(f"Not an AY file: magic={magic!r}")

    file_version = data[8]
    player_version = data[9]

    author_ptr = struct.unpack_from(">H", data, 10)[0]
    author = _read_cstr(data, 10 + author_ptr)

    misc_ptr = struct.unpack_from(">H", data, 12)[0]
    misc = _read_cstr(data, 12 + misc_ptr)

    num_songs = data[14] + 1

    # Song name from the song table (first entry)
    song_name = ""
    song_table_ptr = struct.unpack_from(">H", data, 16)[0]
    song_table_abs = 16 + song_table_ptr
    if song_table_abs + 2 <= len(data):
        name_ptr = struct.unpack_from(">H", data, song_table_abs)[0]
        song_name = _read_cstr(data, song_table_abs + name_ptr)

    # Author is usually blank — fall back to parent directory name
    effective_author = author
    if not effective_author:
        effective_author = path.parent.name

    # Title: prefer song name from header, fall back to filename
    effective_title = song_name if song_name else path.stem

    metadata = TrackMetadata(
        source_format="ay",
        source_path=str(path),
        title=effective_title,
        author=effective_author,
        chip=ChipType.AY3_8910,
        channels=3,
        sub_songs=num_songs,
        extra={
            "file_version": file_version,
            "player_version": player_version,
            "misc": misc,
            "raw_author": author,
            "raw_song_name": song_name,
        },
    )

    return NoteTable(metadata=metadata, events=[])
