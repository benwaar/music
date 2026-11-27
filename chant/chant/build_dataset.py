"""Build the M1 dataset — parse all files, generate captions, split train/val.

Walks _data/ subdirectories, dispatches to the right parser per format,
generates a caption for each, and saves as JSONL with a 90/10 train/val split.

Usage:
    python -m chant.build_dataset [--data-dir _data] [--output-dir _data/dataset] [--seed 42]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import asdict
from pathlib import Path

from chant.caption import caption
from chant.parsers.ay import parse_ay
from chant.parsers.mod import parse_mod, parse_xm
from chant.parsers.sid import parse_sid
from chant.parsers.vgm import parse_vgm
from chant.schema import NoteTable


_PARSERS: dict[str, tuple[str, callable]] = {
    ".sid": ("hvsc", parse_sid),
    ".emul": ("ay", parse_ay),
    ".mod": ("modarchive", parse_mod),
    ".xm": ("modarchive", parse_xm),
    ".vgm": ("vgm", parse_vgm),
    ".vgz": ("vgm", parse_vgm),
}


def _to_record(table: NoteTable, text: str) -> dict:
    m = table.metadata
    events_data = [
        {
            "pitch_hz": e.pitch_hz,
            "duration_ms": e.duration_ms,
            "channel": e.channel,
            "waveform": e.waveform.value if e.waveform else None,
            "volume": e.volume,
        }
        for e in table.events
    ]
    return {
        "caption": text,
        "source_format": m.source_format,
        "source_path": m.source_path,
        "title": m.title,
        "author": m.author,
        "chip": m.chip.value if m.chip else None,
        "channels": m.channels,
        "sub_songs": m.sub_songs,
        "extra": m.extra,
        "num_events": len(table.events),
        "events": events_data,
    }


def build_dataset(data_dir: Path) -> list[dict]:
    """Parse all files and return a list of (caption, metadata) records."""
    records: list[dict] = []
    errors: list[str] = []

    for ext, (subdir, parser) in _PARSERS.items():
        source_dir = data_dir / subdir
        if not source_dir.exists():
            print(f"  skip {subdir}/ (not found)")
            continue

        files = sorted(source_dir.rglob(f"*{ext}"))
        parsed = 0
        for f in files:
            try:
                table = parser(f)
                text = caption(table)
                records.append(_to_record(table, text))
                parsed += 1
            except Exception as e:
                errors.append(f"{f}: {e}")

        print(f"  {subdir}/ {ext}: {parsed}/{len(files)} parsed")

    if errors:
        print(f"\n  {len(errors)} errors (first 5):")
        for err in errors[:5]:
            print(f"    {err}")

    return records


def split_and_save(
    records: list[dict],
    output_dir: Path,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[int, int]:
    """Shuffle, split, and save as JSONL files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    shuffled = list(records)
    rng.shuffle(shuffled)

    val_size = max(1, int(len(shuffled) * val_ratio))
    val_records = shuffled[:val_size]
    train_records = shuffled[val_size:]

    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"

    for path, data in [(train_path, train_records), (val_path, val_records)]:
        with open(path, "w") as f:
            for record in data:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return len(train_records), len(val_records)


def main():
    parser = argparse.ArgumentParser(description="Build the M1 dataset")
    parser.add_argument("--data-dir", type=Path, default=Path("_data"))
    parser.add_argument("--output-dir", type=Path, default=Path("_data/dataset"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print("Building dataset...")
    records = build_dataset(args.data_dir)
    print(f"\nTotal records: {len(records)}")

    if not records:
        print("No records — nothing to save.")
        sys.exit(1)

    train_n, val_n = split_and_save(records, args.output_dir, seed=args.seed)
    print(f"Saved: {train_n} train, {val_n} val → {args.output_dir}/")


if __name__ == "__main__":
    main()
