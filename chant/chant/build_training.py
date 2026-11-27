"""Build tokenised training data from the M1+M2 dataset.

Reads the parsed JSONL (caption + events), tokenises note sequences,
and outputs prompt/completion pairs for causal LM fine-tuning.

Usage:
    python -m chant.build_training [--input-dir _data/dataset] [--output-dir _data/dataset/training]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from chant.schema import NoteEvent, NoteTable, TrackMetadata, Waveform
from chant.tokeniser import encode


def _record_to_table(record: dict) -> NoteTable:
    """Reconstruct a NoteTable from a JSONL record."""
    events = []
    for e in record.get("events", []):
        waveform = Waveform(e["waveform"]) if e.get("waveform") else None
        events.append(NoteEvent(
            pitch_hz=e["pitch_hz"],
            duration_ms=e["duration_ms"],
            channel=e["channel"],
            waveform=waveform,
            volume=e.get("volume"),
        ))

    metadata = TrackMetadata(
        source_format=record["source_format"],
        source_path=record.get("source_path", ""),
        title=record.get("title", ""),
        author=record.get("author", ""),
        channels=record.get("channels", 0),
    )

    return NoteTable(metadata=metadata, events=events)


def format_training_example(caption: str, token_sequence: str) -> dict:
    """Create a prompt/completion pair for causal LM training.

    Format:
        prompt:     "### Instruction:\\n{caption}\\n### Response:\\n"
        completion: "{token_sequence}"
    """
    prompt = f"### Instruction:\n{caption}\n### Response:\n"
    return {
        "prompt": prompt,
        "completion": token_sequence,
    }


def build_training_data(input_path: Path, min_events: int = 10) -> list[dict]:
    """Read JSONL, tokenise events, return prompt/completion pairs.

    Skips tracks with fewer than min_events (too short to learn from).
    """
    examples: list[dict] = []
    skipped = 0

    with open(input_path) as f:
        for line in f:
            record = json.loads(line)
            num_events = record.get("num_events", 0)

            if num_events < min_events:
                skipped += 1
                continue

            table = _record_to_table(record)
            token_seq = encode(table)
            caption = record["caption"]

            examples.append(format_training_example(caption, token_seq))

    return examples, skipped


def save_jsonl(examples: list[dict], output_path: Path) -> None:
    """Write prompt/completion pairs as JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")


def build_hf_dataset(output_dir: Path) -> None:
    """Load training JSONL into a HuggingFace DatasetDict and save to disk.

    Reads train.jsonl and val.jsonl from output_dir, creates a DatasetDict
    with 'train' and 'validation' splits, saves as Arrow format.
    """
    from datasets import Dataset, DatasetDict

    splits = {}
    for split_name, filename in [("train", "train.jsonl"), ("validation", "val.jsonl")]:
        path = output_dir / filename
        if not path.exists():
            continue
        records = []
        with open(path) as f:
            for line in f:
                records.append(json.loads(line))
        splits[split_name] = Dataset.from_list(records)

    ds = DatasetDict(splits)
    ds_path = output_dir / "hf_dataset"
    ds.save_to_disk(str(ds_path))
    return ds


def main():
    parser = argparse.ArgumentParser(description="Build tokenised training data")
    parser.add_argument("--input-dir", type=Path, default=Path("_data/dataset"))
    parser.add_argument("--output-dir", type=Path, default=Path("_data/dataset/training"))
    parser.add_argument("--min-events", type=int, default=10)
    args = parser.parse_args()

    print("Building tokenised training data...")

    for split in ("train", "val"):
        input_path = args.input_dir / f"{split}.jsonl"
        if not input_path.exists():
            print(f"  {split}.jsonl not found, skipping")
            continue

        examples, skipped = build_training_data(input_path, args.min_events)
        output_path = args.output_dir / f"{split}.jsonl"
        save_jsonl(examples, output_path)

        print(f"  {split}: {len(examples)} examples ({skipped} skipped, <{args.min_events} events)")

    print(f"\nSaved JSONL to {args.output_dir}/")

    print("Building HuggingFace Dataset...")
    ds = build_hf_dataset(args.output_dir)
    print(f"  {ds}")
    print(f"  Saved to {args.output_dir}/hf_dataset/")


if __name__ == "__main__":
    main()
