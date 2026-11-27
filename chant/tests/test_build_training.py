"""Tests for the training data pipeline."""

import json
import tempfile
from pathlib import Path

import pytest

from chant.build_training import (
    build_training_data,
    format_training_example,
    save_jsonl,
    _record_to_table,
)
from chant.schema import NoteEvent, Waveform


def _make_jsonl(records: list[dict], tmp_path: Path) -> Path:
    path = tmp_path / "test.jsonl"
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return path


def _sample_record(num_events: int = 20) -> dict:
    events = [
        {"pitch_hz": 440.0, "duration_ms": 120.0, "channel": i % 4,
         "waveform": "pcm", "volume": 0.8}
        for i in range(num_events)
    ]
    return {
        "caption": "Test track, 4-channel, 20 notes",
        "source_format": "mod",
        "source_path": "test.mod",
        "title": "Test",
        "author": "",
        "channels": 4,
        "num_events": num_events,
        "events": events,
    }


def test_format_training_example():
    result = format_training_example("a caption", "<BOS> N60 D120 C0 V7 <EOS>")
    assert result["prompt"] == "### Instruction:\na caption\n### Response:\n"
    assert result["completion"] == "<BOS> N60 D120 C0 V7 <EOS>"


def test_record_to_table():
    record = _sample_record(5)
    table = _record_to_table(record)
    assert len(table.events) == 5
    assert table.events[0].pitch_hz == 440.0
    assert table.events[0].waveform == Waveform.PCM


def test_record_to_table_none_waveform():
    record = _sample_record(1)
    record["events"][0]["waveform"] = None
    table = _record_to_table(record)
    assert table.events[0].waveform is None


def test_build_skips_short_tracks(tmp_path):
    records = [_sample_record(3), _sample_record(20)]
    path = _make_jsonl(records, tmp_path)
    examples, skipped = build_training_data(path, min_events=10)
    assert len(examples) == 1
    assert skipped == 1


def test_build_training_data_format(tmp_path):
    records = [_sample_record(15)]
    path = _make_jsonl(records, tmp_path)
    examples, _ = build_training_data(path, min_events=5)
    assert len(examples) == 1
    ex = examples[0]
    assert "### Instruction:" in ex["prompt"]
    assert "<BOS>" in ex["completion"]
    assert "<EOS>" in ex["completion"]
    assert " | " in ex["completion"]


def test_save_and_reload(tmp_path):
    examples = [format_training_example("cap", "<BOS> N60 D120 C0 V7 <EOS>")]
    out = tmp_path / "out.jsonl"
    save_jsonl(examples, out)
    with open(out) as f:
        loaded = json.loads(f.readline())
    assert loaded["prompt"] == examples[0]["prompt"]
    assert loaded["completion"] == examples[0]["completion"]


@pytest.mark.skipif(
    not Path("_data/dataset/train.jsonl").exists(),
    reason="Dataset not built",
)
def test_real_data_produces_examples():
    examples, skipped = build_training_data(Path("_data/dataset/train.jsonl"))
    assert len(examples) > 100
    assert all("<BOS>" in ex["completion"] for ex in examples[:10])
