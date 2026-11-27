"""PNG to ZX Spectrum .scr converter.

Resizes to 256x192, quantises to the 15-colour Spectrum palette,
and writes the 6912-byte SCR format (6144 bitmap + 768 attributes).

The bitmap uses the Spectrum's interleaved row order:
  address = third(2 bits) << 11 | char_line(3 bits) << 8 | char_row(3 bits) << 5 | col(5 bits)
"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("error: pip install Pillow", file=sys.stderr)
    sys.exit(1)


SPECTRUM_PALETTE = [
    (0x00, 0x00, 0x00),  # 0 black
    (0x00, 0x00, 0xCD),  # 1 blue
    (0xCD, 0x00, 0x00),  # 2 red
    (0xCD, 0x00, 0xCD),  # 3 magenta
    (0x00, 0xCD, 0x00),  # 4 green
    (0x00, 0xCD, 0xCD),  # 5 cyan
    (0xCD, 0xCD, 0x00),  # 6 yellow
    (0xCD, 0xCD, 0xCD),  # 7 white
    (0x00, 0x00, 0x00),  # 8 bright black
    (0x00, 0x00, 0xFF),  # 9 bright blue
    (0xFF, 0x00, 0x00),  # 10 bright red
    (0xFF, 0x00, 0xFF),  # 11 bright magenta
    (0x00, 0xFF, 0x00),  # 12 bright green
    (0x00, 0xFF, 0xFF),  # 13 bright cyan
    (0xFF, 0xFF, 0x00),  # 14 bright yellow
    (0xFF, 0xFF, 0xFF),  # 15 bright white
]


def _colour_dist_sq(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def _nearest_colour(pixel: tuple[int, ...]) -> int:
    return min(range(16), key=lambda i: _colour_dist_sq(pixel, SPECTRUM_PALETTE[i]))


def _attr_byte(ink: int, paper: int) -> int:
    bright = 1 if ink >= 8 or paper >= 8 else 0
    return (bright << 6) | ((paper & 7) << 3) | (ink & 7)


def _pixel_row_offset(y: int) -> int:
    third = y // 64
    char_row = (y % 64) // 8
    char_line = y % 8
    return (third << 11) | (char_line << 8) | (char_row << 5)


def convert(png_path: str, scr_path: str) -> None:
    img = Image.open(png_path).convert("RGB")

    # fit within 256x192 maintaining aspect ratio, black letterbox
    img.thumbnail((256, 192), Image.LANCZOS)
    canvas = Image.new("RGB", (256, 192), (0, 0, 0))
    x_off = (256 - img.width) // 2
    y_off = (192 - img.height) // 2
    canvas.paste(img, (x_off, y_off))
    img = canvas

    pixels = list(img.tobytes())
    pixels = [tuple(pixels[i:i+3]) for i in range(0, len(pixels), 3)]
    indexed = [_nearest_colour(pixels[i]) for i in range(256 * 192)]

    bitmap = bytearray(6144)
    attrs = bytearray(768)

    for char_y in range(24):
        for char_x in range(32):
            cell_colours: dict[int, int] = {}
            for py in range(8):
                for px in range(8):
                    c = indexed[(char_y * 8 + py) * 256 + char_x * 8 + px]
                    cell_colours[c] = cell_colours.get(c, 0) + 1

            sorted_colours = sorted(cell_colours, key=cell_colours.__getitem__, reverse=True)
            ink = sorted_colours[0]
            paper = sorted_colours[1] if len(sorted_colours) > 1 else 0

            attrs[char_y * 32 + char_x] = _attr_byte(ink, paper)

            for py in range(8):
                byte_val = 0
                for px in range(8):
                    c = indexed[(char_y * 8 + py) * 256 + char_x * 8 + px]
                    ink_dist = _colour_dist_sq(SPECTRUM_PALETTE[c], SPECTRUM_PALETTE[ink])
                    paper_dist = _colour_dist_sq(SPECTRUM_PALETTE[c], SPECTRUM_PALETTE[paper])
                    if ink_dist <= paper_dist:
                        byte_val |= (1 << (7 - px))
                offset = _pixel_row_offset(char_y * 8 + py) + char_x
                bitmap[offset] = byte_val

    Path(scr_path).write_bytes(bytes(bitmap + attrs))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: png2scr.py <input.png> <output.scr>", file=sys.stderr)
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
    print(f"{sys.argv[2]}: 6912 bytes")
