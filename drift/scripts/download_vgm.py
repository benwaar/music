#!/usr/bin/env python3
"""
Download VGM files (SN76489 / Sega Master System) from archive.org.

Uses the Dv2 VGM collection on archive.org — 280 VGM files from SMS/Game Gear titles.
SN76489 is the primary chip for Sega Master System, Game Gear, and BBC Micro.

Usage:
    python scripts/download_vgm.py
    python scripts/download_vgm.py --limit 50
    python scripts/download_vgm.py --out _data/vgm
"""
import argparse
import time
import urllib.parse
import urllib.request
from pathlib import Path

ARCHIVE_ID = "dv2-description-downloads-archive"
METADATA_URL = f"https://archive.org/metadata/{ARCHIVE_ID}"
DEFAULT_OUT = Path("_data/vgm")
THROTTLE_SECONDS = 0.2


def fetch_vgm_file_list() -> list[str]:
    import json
    with urllib.request.urlopen(METADATA_URL, timeout=15) as r:
        data = json.loads(r.read())
    files = data.get("files", [])
    return [f["name"] for f in files if f["name"].lower().endswith((".vgm", ".vgz"))]


def download_vgm(out: Path, limit: int) -> None:
    out.mkdir(parents=True, exist_ok=True)

    print(f"Fetching file list from archive.org ({ARCHIVE_ID})...")
    vgm_files = fetch_vgm_file_list()
    print(f"  {len(vgm_files)} VGM files available")

    to_download = vgm_files[:limit]
    downloaded = 0

    for fname in to_download:
        dest = out / Path(fname).name
        if dest.exists():
            downloaded += 1
            continue

        encoded = urllib.parse.quote(fname)
        url = f"https://archive.org/download/{ARCHIVE_ID}/{encoded}"

        try:
            time.sleep(THROTTLE_SECONDS)
            urllib.request.urlretrieve(url, dest)
            downloaded += 1
            print(f"\r  {downloaded}/{len(to_download)} — {Path(fname).name}", end="", flush=True)
        except Exception as exc:
            print(f"\n  Failed {Path(fname).name}: {exc}")

    print(f"\nDone — {downloaded} VGM files in {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=280, help="max files to download (default: all 280)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: _data/vgm)")
    args = parser.parse_args()
    download_vgm(args.out, args.limit)


if __name__ == "__main__":
    main()
