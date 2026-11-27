"""Tests for the MOD/XM parser."""

import struct
from pathlib import Path

import pytest

from chant.parsers.mod import parse_mod, parse_xm
from chant.schema import ChipType


def _make_mod(
    title: str = "Test Module",
    instruments: list[str] | None = None,
    magic: str = "M.K.",
) -> bytes:
    """Build a minimal valid MOD file for testing."""
    if instruments is None:
        instruments = ["inst1", "inst2"]

    buf = bytearray(1084)
    t = title.encode("ascii")[:20].ljust(20, b"\x00")
    buf[0:20] = t

    for i, name in enumerate(instruments[:31]):
        offset = 20 + i * 30
        n = name.encode("ascii")[:22].ljust(22, b"\x00")
        buf[offset : offset + 22] = n

    buf[1080:1084] = magic.encode("ascii")[:4].ljust(4, b"\x00")
    return bytes(buf)


def _make_xm(
    name: str = "Test XM",
    tracker: str = "FastTracker v2.00",
    channels: int = 4,
    instruments: int = 10,
    bpm: int = 125,
) -> bytes:
    """Build a minimal valid XM file for testing."""
    buf = bytearray(80)
    buf[0:17] = b"Extended Module: "
    buf[17] = 0x1A  # DOS EOF marker

    n = name.encode("ascii")[:20].ljust(20, b"\x00")
    buf[17:37] = n
    buf[17] = n[0]  # overwrite the 0x1A with actual name start

    # Re-do: XM header is id (17) + name (20) + 0x1a (1) + tracker (20) + version (2) + header_size (4) + ...
    # Let me just build it properly
    buf = bytearray(80)
    buf[0:17] = b"Extended Module: "
    nm = name.encode("ascii")[:20].ljust(20, b"\x00")
    buf[17:37] = nm
    buf[37] = 0x1A
    tr = tracker.encode("ascii")[:20].ljust(20, b"\x00")
    buf[38:58] = tr
    struct.pack_into("<H", buf, 58, 0x0104)  # version
    struct.pack_into("<I", buf, 60, 276)  # header size
    struct.pack_into("<H", buf, 68, channels)
    struct.pack_into("<H", buf, 72, instruments)
    struct.pack_into("<H", buf, 78, bpm)
    return bytes(buf)


def test_parse_mod_basic(tmp_path: Path):
    f = tmp_path / "test.mod"
    f.write_bytes(_make_mod())

    table = parse_mod(f)
    assert table.metadata.title == "Test Module"
    assert table.metadata.source_format == "mod"
    assert table.metadata.chip == ChipType.MOD
    assert table.metadata.channels == 4
    assert "inst1" in table.metadata.extra["instruments"]
    assert table.events == []


def test_parse_mod_8_channel(tmp_path: Path):
    f = tmp_path / "test.mod"
    f.write_bytes(_make_mod(magic="8CHN"))

    table = parse_mod(f)
    assert table.metadata.channels == 8


def test_parse_mod_instruments(tmp_path: Path):
    insts = ["bass drum", "snare", "hihat", "lead synth"]
    f = tmp_path / "test.mod"
    f.write_bytes(_make_mod(instruments=insts))

    table = parse_mod(f)
    assert table.metadata.extra["instruments"] == insts


def test_parse_xm_basic(tmp_path: Path):
    f = tmp_path / "test.xm"
    f.write_bytes(_make_xm())

    table = parse_xm(f)
    assert table.metadata.title == "Test XM"
    assert table.metadata.source_format == "xm"
    assert table.metadata.chip == ChipType.XM
    assert table.metadata.channels == 4
    assert table.metadata.extra["bpm"] == 125
    assert table.metadata.extra["num_instruments"] == 10
    assert table.events == []


def test_parse_xm_32_channels(tmp_path: Path):
    f = tmp_path / "test.xm"
    f.write_bytes(_make_xm(channels=32, bpm=80))

    table = parse_xm(f)
    assert table.metadata.channels == 32
    assert table.metadata.extra["bpm"] == 80


def test_reject_non_xm(tmp_path: Path):
    f = tmp_path / "test.xm"
    f.write_bytes(b"Not an XM file at all" + b"\x00" * 200)

    with pytest.raises(ValueError, match="Not an XM file"):
        parse_xm(f)


def test_reject_truncated_xm(tmp_path: Path):
    f = tmp_path / "test.xm"
    f.write_bytes(b"Extended Module: short")

    with pytest.raises(ValueError, match="too short"):
        parse_xm(f)


def test_parse_real_mod_files():
    """Parse actual MOD files from drift's corpus if available."""
    mod_dir = Path("_data/modarchive")
    if not mod_dir.exists():
        pytest.skip("drift data not symlinked")

    mod_files = list(mod_dir.rglob("*.mod"))[:10]
    assert len(mod_files) > 0, "No MOD files found"

    for f in mod_files:
        table = parse_mod(f)
        assert table.metadata.source_format == "mod"
        assert table.metadata.channels >= 4


def test_parse_real_xm_files():
    """Parse actual XM files from drift's corpus if available."""
    mod_dir = Path("_data/modarchive")
    if not mod_dir.exists():
        pytest.skip("drift data not symlinked")

    xm_files = list(mod_dir.rglob("*.xm"))[:10]
    assert len(xm_files) > 0, "No XM files found"

    for f in xm_files:
        table = parse_xm(f)
        assert table.metadata.source_format == "xm"
        assert table.metadata.channels >= 1
        assert table.metadata.extra["bpm"] >= 1
