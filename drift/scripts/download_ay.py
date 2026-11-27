#!/usr/bin/env python3
"""
Download AY (ZX Spectrum) music files from Modland.

Modland hosts ~10,000+ AY Emul files (.emul = ZXAYEMUL format), organised by artist.
These are playable by Game_Music_Emu (libgme), aylet, and sidplayfp.

Usage:
    python scripts/download_ay.py
    python scripts/download_ay.py --limit 200
    python scripts/download_ay.py --out _data/ay
"""
import argparse
import re
import time
import urllib.request
from pathlib import Path

BASE_URL = "https://modland.com/pub/modules/AY%20Emul/"
DEFAULT_OUT = Path("_data/ay")
THROTTLE_SECONDS = 0.1


def list_artists() -> list[str]:
    with urllib.request.urlopen(BASE_URL, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")
    dirs = re.findall(r'href="([^"]+/)"', html)
    return [d for d in dirs if d not in ("../", "?C=N&O=A", "?C=N&O=D", "?C=S&O=A", "?C=S&O=D", "?C=M&O=A", "?C=M&O=D")]


def list_files(artist_path: str) -> list[str]:
    url = BASE_URL + artist_path
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    return re.findall(r'href="([^"]+\.emul)"', html)


def download_ay(out: Path, limit: int) -> None:
    out.mkdir(parents=True, exist_ok=True)

    print("Fetching artist list from Modland AY Emul...")
    artists = list_artists()
    print(f"  {len(artists)} artists")

    downloaded = 0
    for artist_path in artists:
        if downloaded >= limit:
            break

        artist_name = urllib.parse.unquote(artist_path.rstrip("/"))
        files = list_files(artist_path)

        for fname_enc in files:
            if downloaded >= limit:
                break

            fname = urllib.parse.unquote(fname_enc)
            dest = out / artist_name / fname
            if dest.exists():
                downloaded += 1
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            url = BASE_URL + artist_path + fname_enc
            try:
                time.sleep(THROTTLE_SECONDS)
                urllib.request.urlretrieve(url, dest)
                downloaded += 1
                print(f"\r  {downloaded}/{limit} — {artist_name}/{fname}", end="", flush=True)
            except Exception as exc:
                print(f"\n  Failed {fname}: {exc}")

    print(f"\nDone — {downloaded} .emul files in {out}")


def main() -> None:
    import urllib.parse  # noqa: F401 — needed at module level for unquote

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=500, help="max files to download (default: 500)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: _data/ay)")
    args = parser.parse_args()
    download_ay(args.out, args.limit)


if __name__ == "__main__":
    import urllib.parse
    main()
