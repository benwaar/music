"""Filter 8s segments to loop-only subset and report stats.

Usage:
    python scripts/filter_loops.py [--min-confidence 0.3] [--duration 8]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from drift.loops import filter_looping_segments


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter segments by loop confidence")
    parser.add_argument("--data", default="_data/segments")
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--min-confidence", type=float, default=0.3, dest="min_confidence")
    parser.add_argument("--output", default="_data/eval/loop_filter.json")
    args = parser.parse_args()

    print(f"Scanning {args.duration}s segments (min confidence: {args.min_confidence})...")
    results = filter_looping_segments(
        Path(args.data), duration=args.duration, min_confidence=args.min_confidence,
    )

    total_files = len(list(Path(args.data).rglob(f"*_{args.duration}s.wav")))
    print(f"\n  Total {args.duration}s segments: {total_files}")
    print(f"  Looping (conf >= {args.min_confidence}): {len(results)}")
    print(f"  Pass rate: {len(results) / max(total_files, 1) * 100:.1f}%")

    if results:
        confs = [c for _, _, c in results]
        print(f"  Confidence range: {min(confs):.3f} – {max(confs):.3f}")
        print(f"  Mean confidence: {sum(confs) / len(confs):.3f}")

        # Breakdown by chip type
        by_chip: dict[str, int] = {}
        for p, _, _ in results:
            chip = p.parent.name
            by_chip[chip] = by_chip.get(chip, 0) + 1
        print(f"\n  By chip type:")
        for chip, count in sorted(by_chip.items()):
            print(f"    {chip}: {count}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "duration": args.duration,
        "min_confidence": args.min_confidence,
        "total": total_files,
        "looping": len(results),
        "files": [
            {"path": str(p), "loop_length": ll, "confidence": round(c, 4)}
            for p, ll, c in results
        ],
    }
    out_path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"\n  Saved: {out_path}")


if __name__ == "__main__":
    main()
