"""TAP file writer for ZX Spectrum.

ZX Spectrum TAP format: each block is a 2-byte little-endian length prefix
followed by the block data. Block data is: flag byte + payload + XOR checksum.

Header block (flag=0x00): type (1) + 10-char filename + data_len (2) + param1 (2) + param2 (2)
Data block (flag=0xFF): raw bytes.
"""

import sys
from pathlib import Path


def _xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result


def _make_header_block(
    block_type: int,
    filename: str,
    data_len: int,
    param1: int,
    param2: int,
) -> bytes:
    name_bytes = filename.encode("ascii")[:10].ljust(10, b" ")
    payload = bytes([block_type]) + name_bytes
    payload += data_len.to_bytes(2, "little")
    payload += param1.to_bytes(2, "little")
    payload += param2.to_bytes(2, "little")

    flag = 0x00
    content = bytes([flag]) + payload
    checksum = _xor_checksum(content)
    block = content + bytes([checksum])
    return len(block).to_bytes(2, "little") + block


def _make_data_block(payload: bytes) -> bytes:
    flag = 0xFF
    content = bytes([flag]) + payload
    checksum = _xor_checksum(content)
    block = content + bytes([checksum])
    return len(block).to_bytes(2, "little") + block


def _int5(value: int) -> bytes:
    """Spectrum 5-byte integer: 0x00 + sign + lo + hi + 0x00."""
    sign = 0xFF if value < 0 else 0x00
    unsigned = value & 0xFFFF
    return bytes([0x00, sign, unsigned & 0xFF, (unsigned >> 8) & 0xFF, 0x00])


def _basic_line(line_num: int, body: bytes) -> bytes:
    terminated = body + bytes([0x0D])
    return (
        line_num.to_bytes(2, "big")
        + len(terminated).to_bytes(2, "little")
        + terminated
    )


def _make_basic_loader(start_addr: int) -> bytes:
    """Build tokenised BASIC: 10 CLEAR <addr-1>: LOAD ""CODE: RANDOMIZE USR <addr>"""
    clear_val = start_addr - 1
    clear_str = str(clear_val).encode("ascii")
    addr_str = str(start_addr).encode("ascii")

    body = bytearray()
    body += bytes([0xFD])
    body += clear_str + bytes([0x0E]) + _int5(clear_val)
    body += bytes([0x3A, 0xEF, 0x22, 0x22, 0xAF])
    body += bytes([0x3A, 0xF9, 0xC0])
    body += addr_str + bytes([0x0E]) + _int5(start_addr)

    return _basic_line(10, bytes(body))


def write_tap(
    binary_path: str,
    tap_path: str,
    name: str = "beeper",
    start_addr: int = 0x8000,
) -> None:
    """Write a full Spectrum TAP: BASIC auto-loader + CODE block."""
    binary_data = Path(binary_path).read_bytes()
    basic = _make_basic_loader(start_addr)

    tap = bytearray()
    tap += _make_header_block(0, name, len(basic), 10, len(basic))
    tap += _make_data_block(basic)
    tap += _make_header_block(3, name, len(binary_data), start_addr, 0x8000)
    tap += _make_data_block(binary_data)
    Path(tap_path).write_bytes(bytes(tap))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: tap.py <input.bin> <output.tap>", file=sys.stderr)
        sys.exit(1)
    write_tap(sys.argv[1], sys.argv[2])
