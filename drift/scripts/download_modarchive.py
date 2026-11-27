#!/usr/bin/env python3
"""
Download tracker modules (MOD/XM) from The Mod Archive.

Scrapes the alphabetical browse list to get module IDs, then downloads
files in the requested formats. Filters by file extension from the
download URL, so you only get the formats you ask for.

Usage:
    python scripts/download_modarchive.py
    python scripts/download_modarchive.py --count 100
    python scripts/download_modarchive.py --formats mod xm
    python scripts/download_modarchive.py --out _data/modarchive
"""
import argparse
import re
import sys
import time
import urllib.request
from pathlib import Path

BROWSE_URL = "https://modarchive.org/index.php?request=view_by_list&query={letter}"
DOWNLOAD_URL = "https://api.modarchive.org/downloads.php?moduleid={mod_id}"
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
ALLOWED_FORMATS = {"mod", "xm", "it", "s3m"}
DEFAULT_FORMATS = {"mod", "xm"}
THROTTLE_SECONDS = 0.3
DEFAULT_OUT = Path("_data/modarchive")


def scrape_ids_for_letter(letter: str) -> list[tuple[str, str]]:
    """Return list of (module_id, filename) for one browse letter."""
    url = BROWSE_URL.format(letter=letter)
    req = urllib.request.Request(url, headers={"User-Agent": "drift-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    return re.findall(r'moduleid=(\d+)#([^"]+)', html)


def download_module(mod_id: str, filename: str, out: Path) -> bool:
    ext = Path(filename).suffix.lstrip(".").lower()
    dest = out / ext / filename
    if dest.exists():
        return True

    dest.parent.mkdir(parents=True, exist_ok=True)
    url = DOWNLOAD_URL.format(mod_id=mod_id)
    req = urllib.request.Request(url, headers={"User-Agent": "drift-research/1.0"})
    try:
        time.sleep(THROTTLE_SECONDS)
        with urllib.request.urlopen(req, timeout=15) as r:
            dest.write_bytes(r.read())
        return True
    except Exception as exc:
        print(f"\n  Failed {filename}: {exc}", file=sys.stderr)
        return False


def download_modarchive(out: Path, count: int, formats: set[str]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    print(f"Downloading up to {count} modules (formats: {', '.join(sorted(formats))}) → {out}")

    downloaded = 0
    for letter in LETTERS:
        if downloaded >= count:
            break

        entries = scrape_ids_for_letter(letter)
        for mod_id, raw_filename in entries:
            if downloaded >= count:
                break
            filename = urllib.parse.unquote(raw_filename) if "%" in raw_filename else raw_filename
            ext = Path(filename).suffix.lstrip(".").lower()
            if ext not in formats:
                continue
            if download_module(mod_id, filename, out):
                downloaded += 1
                print(f"\r  {downloaded}/{count} — {filename}", end="", flush=True)

    print(f"\nDone — {downloaded} modules")
    for fmt in sorted(formats):
        fmt_dir = out / fmt
        if fmt_dir.exists():
            n = len(list(fmt_dir.glob(f"*.{fmt}")))
            if n:
                print(f"  {fmt.upper()}: {n:,} files")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--count", type=int, default=500, help="number of modules to download (default: 500)")
    parser.add_argument("--formats", nargs="+", choices=sorted(ALLOWED_FORMATS), default=sorted(DEFAULT_FORMATS), help="module formats to keep (default: mod xm)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: _data/modarchive)")
    args = parser.parse_args()
    download_modarchive(args.out, args.count, set(args.formats))


if __name__ == "__main__":
    import urllib.parse
    main()
