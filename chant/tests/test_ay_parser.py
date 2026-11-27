"""Tests for the AY parser."""

import struct
from pathlib import Path

import pytest

from chant.parsers.ay import parse_ay
from chant.schema import ChipType


def _make_ay(
    author: str = "Test Author",
    misc: str = "Test Misc",
    song_name: str = "Test Song",
    num_songs: int = 1,
) -> bytes:
    """Build a minimal valid AY file for testing."""
    # Strings placed after the 18-byte header
    strings_start = 18
    author_bytes = author.encode("ascii") + b"\x00"
    misc_bytes = misc.encode("ascii") + b"\x00"
    song_name_bytes = song_name.encode("ascii") + b"\x00"

    # Layout: header (18) | author | misc | song_table (2) | song_name
    author_offset = strings_start
    misc_offset = author_offset + len(author_bytes)
    song_table_offset = misc_offset + len(misc_bytes)
    song_name_offset = song_table_offset + 2

    buf = bytearray(song_name_offset + len(song_name_bytes))
    buf[0:8] = b"ZXAYEMUL"
    buf[8] = 0   # file version
    buf[9] = 0   # player version

    # Relative pointers
    struct.pack_into(">H", buf, 10, author_offset - 10)
    struct.pack_into(">H", buf, 12, misc_offset - 12)
    buf[14] = num_songs - 1  # 0-based
    buf[15] = 0  # first song
    struct.pack_into(">H", buf, 16, song_table_offset - 16)

    # Strings
    buf[author_offset : author_offset + len(author_bytes)] = author_bytes
    buf[misc_offset : misc_offset + len(misc_bytes)] = misc_bytes

    # Song table: pointer to song name (relative to song_table_offset)
    struct.pack_into(">H", buf, song_table_offset, song_name_offset - song_table_offset)
    buf[song_name_offset : song_name_offset + len(song_name_bytes)] = song_name_bytes

    return bytes(buf)


def test_parse_minimal_ay(tmp_path: Path):
    ay_file = tmp_path / "author_dir" / "test.emul"
    ay_file.parent.mkdir()
    ay_file.write_bytes(_make_ay())

    table = parse_ay(ay_file)
    assert table.metadata.title == "Test Song"
    assert table.metadata.author == "Test Author"
    assert table.metadata.source_format == "ay"
    assert table.metadata.chip == ChipType.AY3_8910
    assert table.metadata.channels == 3
    assert table.metadata.sub_songs == 1
    assert table.events == []


def test_fallback_to_dirname_for_author(tmp_path: Path):
    ay_file = tmp_path / "Fred Gray" / "test.emul"
    ay_file.parent.mkdir()
    ay_file.write_bytes(_make_ay(author=""))

    table = parse_ay(ay_file)
    assert table.metadata.author == "Fred Gray"


def test_fallback_to_filename_for_title(tmp_path: Path):
    ay_file = tmp_path / "author" / "cool song.emul"
    ay_file.parent.mkdir()
    ay_file.write_bytes(_make_ay(song_name=""))

    table = parse_ay(ay_file)
    assert table.metadata.title == "cool song"


def test_multiple_songs(tmp_path: Path):
    ay_file = tmp_path / "author" / "test.emul"
    ay_file.parent.mkdir()
    ay_file.write_bytes(_make_ay(num_songs=5))

    table = parse_ay(ay_file)
    assert table.metadata.sub_songs == 5


def test_misc_in_extra(tmp_path: Path):
    ay_file = tmp_path / "author" / "test.emul"
    ay_file.parent.mkdir()
    ay_file.write_bytes(_make_ay(misc="Composed by Someone 1996"))

    table = parse_ay(ay_file)
    assert table.metadata.extra["misc"] == "Composed by Someone 1996"


def test_reject_non_ay(tmp_path: Path):
    f = tmp_path / "test.emul"
    f.write_bytes(b"NOT AN AY FILE" + b"\x00" * 200)

    with pytest.raises(ValueError, match="Not an AY file"):
        parse_ay(f)


def test_reject_truncated(tmp_path: Path):
    f = tmp_path / "test.emul"
    f.write_bytes(b"ZXAYEMUL\x00")

    with pytest.raises(ValueError, match="too short"):
        parse_ay(f)


def test_parse_real_ay_files():
    """Parse actual AY files from drift's corpus if available."""
    ay_dir = Path("_data/ay")
    if not ay_dir.exists():
        pytest.skip("drift data not symlinked")

    ay_files = list(ay_dir.rglob("*.emul"))[:10]
    assert len(ay_files) > 0, "No AY files found"

    for ay_file in ay_files:
        table = parse_ay(ay_file)
        assert table.metadata.source_format == "ay"
        assert table.metadata.chip == ChipType.AY3_8910
        assert table.metadata.channels == 3
        assert table.metadata.sub_songs >= 1
        assert table.metadata.title  # should always have a title (fallback to filename)
        assert table.metadata.author  # should always have an author (fallback to dirname)
