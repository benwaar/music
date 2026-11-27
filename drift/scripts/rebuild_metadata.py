"""Rebuild metadata.json for the loop-filtered dataset without balancing.

Usage:
    python scripts/rebuild_metadata.py --data _data/segments_loops
    python scripts/rebuild_metadata.py --data _data/segments_loops --balance  # balanced mode
"""

from __future__ import annotations

import argparse
from pathlib import Path

from drift.dataset import build_metadata, CHIP_TYPES


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild metadata.json for a segments directory.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("_data/segments_loops"),
        help="Path to segments directory (default: _data/segments_loops)",
    )
    parser.add_argument(
        "--balance",
        action="store_true",
        default=False,
        help="Cap each chip type to the smallest count (default: unbalanced)",
    )
    args = parser.parse_args()

    print(f"Rebuilding metadata for: {args.data}")
    print(f"Balance mode: {args.balance}")
    print()

    metadata = build_metadata(Path(args.data), balance=args.balance)

    splits = metadata["splits"]
    total = sum(len(v) for v in splits.values())

    print()
    print("Summary:")
    print(f"  Total files : {total:,}")

    # Per-chip-type counts across all splits.
    all_paths = [p for paths in splits.values() for p in paths]
    for chip_type in CHIP_TYPES:
        count = sum(1 for p in all_paths if p.startswith(f"{chip_type}/"))
        if count:
            print(f"  {chip_type:<12}: {count:,}")

    print()
    print("Split sizes:")
    for split_name, paths in splits.items():
        print(f"  {split_name:<6}: {len(paths):,}")


if __name__ == "__main__":
    main()
