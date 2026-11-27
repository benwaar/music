"""Integration tests for the dataset builder."""

import json
from pathlib import Path

import pytest

from chant.build_dataset import build_dataset, split_and_save


def test_build_dataset_from_real_data():
    """Build dataset from drift's corpus if available."""
    data_dir = Path("_data")
    if not data_dir.exists():
        pytest.skip("drift data not symlinked")

    records = build_dataset(data_dir)
    assert len(records) > 100, f"Expected 100+ records, got {len(records)}"

    # Every record has required fields
    for r in records[:50]:
        assert r["caption"], f"Empty caption for {r['source_path']}"
        assert r["source_format"] in ("sid", "ay", "mod", "xm", "vgm")
        assert r["source_path"]
        assert r["channels"] > 0

    # All formats represented
    formats = {r["source_format"] for r in records}
    assert formats == {"sid", "ay", "mod", "xm", "vgm"}


def test_split_and_save(tmp_path: Path):
    records = [
        {"caption": f"test {i}", "source_format": "sid", "title": f"t{i}"}
        for i in range(100)
    ]

    train_n, val_n = split_and_save(records, tmp_path, val_ratio=0.1, seed=42)
    assert train_n == 90
    assert val_n == 10

    train_path = tmp_path / "train.jsonl"
    val_path = tmp_path / "val.jsonl"
    assert train_path.exists()
    assert val_path.exists()

    with open(train_path) as f:
        train_records = [json.loads(line) for line in f]
    assert len(train_records) == 90

    with open(val_path) as f:
        val_records = [json.loads(line) for line in f]
    assert len(val_records) == 10


def test_split_is_deterministic(tmp_path: Path):
    records = [{"caption": f"test {i}", "i": i} for i in range(50)]

    dir1 = tmp_path / "run1"
    dir2 = tmp_path / "run2"
    split_and_save(records, dir1, seed=42)
    split_and_save(records, dir2, seed=42)

    with open(dir1 / "train.jsonl") as f:
        run1 = f.read()
    with open(dir2 / "train.jsonl") as f:
        run2 = f.read()
    assert run1 == run2
