"""Tests for the SID parser."""

import struct
from pathlib import Path

import pytest

from chant.parsers.sid import parse_sid
from chant.schema import ChipType


def _make_sid(
    title: str = "Test Song",
    author: str = "Test Author",
    released: str = "2026",
    num_songs: int = 1,
    version: int = 2,
    flags: int = 0x0000,
) -> bytes:
    """Build a minimal valid SID file for testing."""
    buf = bytearray(0x7E)
    buf[0:4] = b"PSID"
    struct.pack_into(">H", buf, 0x04, version)
    struct.pack_into(">H", buf, 0x06, 0x7C)  # data offset
    struct.pack_into(">H", buf, 0x0E, num_songs)

    t = title.encode("ascii")[:32].ljust(32, b"\x00")
    buf[0x16 : 0x16 + 32] = t

    a = author.encode("ascii")[:32].ljust(32, b"\x00")
    buf[0x36 : 0x36 + 32] = a

    r = released.encode("ascii")[:32].ljust(32, b"\x00")
    buf[0x56 : 0x56 + 32] = r

    struct.pack_into(">H", buf, 0x76, flags)
    return bytes(buf)


def test_parse_minimal_sid(tmp_path: Path):
    sid_file = tmp_path / "test.sid"
    sid_file.write_bytes(_make_sid())

    table = parse_sid(sid_file)
    assert table.metadata.title == "Test Song"
    assert table.metadata.author == "Test Author"
    assert table.metadata.source_format == "sid"
    assert table.metadata.chip == ChipType.MOS6581
    assert table.metadata.channels == 3
    assert table.metadata.sub_songs == 1
    assert table.events == []


def test_parse_8580_chip(tmp_path: Path):
    sid_file = tmp_path / "test.sid"
    sid_file.write_bytes(_make_sid(flags=0x0020))

    table = parse_sid(sid_file)
    assert table.metadata.chip == ChipType.MOS8580


def test_parse_multiple_songs(tmp_path: Path):
    sid_file = tmp_path / "test.sid"
    sid_file.write_bytes(_make_sid(num_songs=5))

    table = parse_sid(sid_file)
    assert table.metadata.sub_songs == 5


def test_parse_rsid(tmp_path: Path):
    data = bytearray(_make_sid())
    data[0:4] = b"RSID"
    sid_file = tmp_path / "test.sid"
    sid_file.write_bytes(bytes(data))

    table = parse_sid(sid_file)
    assert table.metadata.extra["magic"] == "RSID"


def test_reject_non_sid(tmp_path: Path):
    sid_file = tmp_path / "test.sid"
    sid_file.write_bytes(b"NOT A SID FILE AT ALL" + b"\x00" * 200)

    with pytest.raises(ValueError, match="Not a SID file"):
        parse_sid(sid_file)


def test_reject_truncated(tmp_path: Path):
    sid_file = tmp_path / "test.sid"
    sid_file.write_bytes(b"PSID\x00\x02")

    with pytest.raises(ValueError, match="too short"):
        parse_sid(sid_file)


def test_parse_real_sid_files():
    """Parse actual SID files from drift's corpus if available."""
    hvsc = Path("_data/hvsc")
    if not hvsc.exists():
        pytest.skip("drift data not symlinked")

    sid_files = list(hvsc.rglob("*.sid"))[:10]
    assert len(sid_files) > 0, "No SID files found"

    for sid_file in sid_files:
        table = parse_sid(sid_file)
        assert table.metadata.source_format == "sid"
        assert table.metadata.channels in (3, 6)
        assert table.metadata.sub_songs >= 1
