#!/usr/bin/env python3
"""
Download SID files from the High Voltage SID Collection (HVSC).

Downloads the latest HVSC update pack (~3 MB, ~600 SID files) from hvsc.brona.dk.
For the full collection (~84 MB, ~50k SID files) pass --full.

Requires: p7zip (`brew install p7zip` — needed to extract BCJ2-compressed 7z archives)

Usage:
    python scripts/download_hvsc.py
    python scripts/download_hvsc.py --full
    python scripts/download_hvsc.py --out _data/hvsc
"""
import argparse
import subprocess
import sys
import urllib.request
from pathlib import Path

HVSC_VERSION_URL = "https://www.hvsc.c64.org/api/v1/version/7z"
DEFAULT_OUT = Path("_data/hvsc")


def fetch_version() -> dict:
    import json
    with urllib.request.urlopen(HVSC_VERSION_URL, timeout=10) as r:
        return json.loads(r.read())


def download_hvsc(out: Path, full: bool) -> None:
    out.mkdir(parents=True, exist_ok=True)

    _check_7za()

    version = fetch_version()
    if full:
        url = version["complete"]["url"]
        label = f"HVSC complete (v{version['version']})"
    else:
        url = version["update"]["url"]
        label = f"HVSC update #{version['version']}"

    archive_name = Path(url).name
    archive = out / archive_name

    if not archive.exists():
        print(f"Downloading {label} → {archive}")
        urllib.request.urlretrieve(url, archive, reporthook=_progress)
        print()
    else:
        print(f"Archive already present: {archive}")

    sid_dir = out / "sid"
    sid_dir.mkdir(exist_ok=True)

    print(f"Extracting .sid files → {sid_dir}")
    result = subprocess.run(
        ["7za", "e", str(archive), "-o" + str(sid_dir), "*.sid", "-r", "-y"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"7za error: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    count = len(list(sid_dir.rglob("*.sid")))
    print(f"Done — {count:,} .sid files in {sid_dir}")


def _check_7za() -> None:
    try:
        subprocess.run(["7za", "--help"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: 7za not found. Install with: brew install p7zip", file=sys.stderr)
        sys.exit(1)


def _progress(block_num: int, block_size: int, total: int) -> None:
    if total <= 0:
        return
    pct = min(100, block_num * block_size * 100 // total)
    bar = "#" * (pct // 2) + "-" * (50 - pct // 2)
    print(f"\r  [{bar}] {pct}%", end="", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--full", action="store_true", help="download complete collection (~84 MB, ~50k SIDs) instead of latest update")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: _data/hvsc)")
    args = parser.parse_args()
    download_hvsc(args.out, args.full)


if __name__ == "__main__":
    main()
