"""Tests for the VGM parser."""

import gzip
import struct
from pathlib import Path

import pytest

from chant.parsers.vgm import parse_vgm
from chant.schema import ChipType


def _make_vgm(
    sn76489_clock: int = 3579545,
    ym2612_clock: int = 0,
    gd3_strings: list[str] | None = None,
) -> bytes:
    """Build a minimal valid VGM file for testing."""
    header = bytearray(0x40)
    header[0:4] = b"Vgm "
    struct.pack_into("<I", header, 0x0C, sn76489_clock)
    struct.pack_into("<I", header, 0x2C, ym2612_clock)

    if gd3_strings is None:
        struct.pack_into("<I", header, 0x14, 0)  # no GD3
        return bytes(header)

    # Build GD3 tag
    gd3_body = b""
    for s in gd3_strings:
        gd3_body += s.encode("utf-16-le") + b"\x00\x00"
    # Pad to 11 strings
    for _ in range(11 - len(gd3_strings)):
        gd3_body += b"\x00\x00"

    gd3_tag = b"Gd3 " + struct.pack("<II", 0x0100, len(gd3_body)) + gd3_body

    # GD3 offset relative to 0x14
    struct.pack_into("<I", header, 0x14, len(header) - 0x14)

    return bytes(header) + gd3_tag


def test_parse_vgm_with_gd3(tmp_path: Path):
    gd3 = ["Azure Lake", "", "Sonic 3", "", "SMS", "", "Composer", "", "1994", "Ripper", ""]
    f = tmp_path / "test.vgm"
    f.write_bytes(_make_vgm(gd3_strings=gd3))

    table = parse_vgm(f)
    assert table.metadata.title == "Azure Lake"
    assert table.metadata.author == "Composer"
    assert table.metadata.source_format == "vgm"
    assert table.metadata.chip == ChipType.SN76489
    assert table.metadata.channels == 4
    assert table.metadata.extra["gd3"]["game_en"] == "Sonic 3"


def test_parse_vgm_no_gd3(tmp_path: Path):
    f = tmp_path / "test song.vgm"
    f.write_bytes(_make_vgm())

    table = parse_vgm(f)
    assert table.metadata.title == "test song"
    assert table.metadata.author == ""


def test_parse_vgm_ym2612(tmp_path: Path):
    f = tmp_path / "test.vgm"
    f.write_bytes(_make_vgm(sn76489_clock=3579545, ym2612_clock=7670454))

    table = parse_vgm(f)
    assert table.metadata.chip == ChipType.YM2612
    assert table.metadata.channels == 10


def test_parse_vgz(tmp_path: Path):
    gd3 = ["Compressed Track", "", "", "", "", "", "Author", "", "", "", ""]
    vgm_data = _make_vgm(gd3_strings=gd3)
    f = tmp_path / "test.vgz"
    f.write_bytes(gzip.compress(vgm_data))

    table = parse_vgm(f)
    assert table.metadata.title == "Compressed Track"
    assert table.metadata.extra["is_compressed"] is True


def test_reject_non_vgm(tmp_path: Path):
    f = tmp_path / "test.vgm"
    f.write_bytes(b"NOT A VGM FILE" + b"\x00" * 200)

    with pytest.raises(ValueError, match="Not a VGM file"):
        parse_vgm(f)


def test_reject_truncated(tmp_path: Path):
    f = tmp_path / "test.vgm"
    f.write_bytes(b"Vgm \x00\x00")

    with pytest.raises(ValueError, match="too short"):
        parse_vgm(f)


def test_parse_real_vgm_files():
    """Parse actual VGM files from drift's corpus if available."""
    vgm_dir = Path("_data/vgm")
    if not vgm_dir.exists():
        pytest.skip("drift data not symlinked")

    vgm_files = list(vgm_dir.rglob("*.vgm"))[:10]
    assert len(vgm_files) > 0, "No VGM files found"

    for f in vgm_files:
        table = parse_vgm(f)
        assert table.metadata.source_format == "vgm"
        assert table.metadata.title


def test_parse_real_vgz_files():
    """Parse actual VGZ files from drift's corpus if available."""
    vgm_dir = Path("_data/vgm")
    if not vgm_dir.exists():
        pytest.skip("drift data not symlinked")

    vgz_files = list(vgm_dir.rglob("*.vgz"))[:10]
    if not vgz_files:
        pytest.skip("No VGZ files found")

    for f in vgz_files:
        table = parse_vgm(f)
        assert table.metadata.source_format == "vgm"
        assert table.metadata.extra["is_compressed"] is True
