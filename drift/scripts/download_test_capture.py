#!/usr/bin/env python3
"""
Download a single CC-licensed ambient recording from archive.org for M7 pipeline testing.

Grabs a stream field recording (~10 MB MP3) to prove the generate-from-noise
pipeline works before real field captures are ready.

Source: aporee / radio aporee — CC BY-NC-ND 3.0
https://archive.org/details/aporee_73794_86247

Usage:
    python scripts/download_test_capture.py
"""
import subprocess
import sys
import urllib.request
from pathlib import Path

URL = "https://archive.org/download/aporee_73794_86247/soundmap202610064.mp3"
OUT_DIR = Path("_data/captures/test")
OUT_MP3 = OUT_DIR / "audio.mp3"
OUT_WAV = OUT_DIR / "audio.wav"


def _progress(block_num: int, block_size: int, total: int) -> None:
    if total <= 0:
        return
    pct = min(100, block_num * block_size * 100 // total)
    bar = "#" * (pct // 2) + "-" * (50 - pct // 2)
    print(f"\r  [{bar}] {pct}%", end="", flush=True)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if OUT_WAV.exists():
        print(f"Already present: {OUT_WAV}")
        return

    if not OUT_MP3.exists():
        print(f"Downloading test capture → {OUT_MP3}")
        urllib.request.urlretrieve(URL, OUT_MP3, reporthook=_progress)
        print()
    else:
        print(f"MP3 already present: {OUT_MP3}")

    print(f"Converting to WAV (first 30s) → {OUT_WAV}")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(OUT_MP3), "-t", "30", "-ar", "22050", "-ac", "1", str(OUT_WAV)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"Done — {OUT_WAV} ({OUT_WAV.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
