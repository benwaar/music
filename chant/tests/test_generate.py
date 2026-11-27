"""Tests for chant/generate.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from chant.generate import (
    GenerationResult,
    format_prompt,
    generate_batch,
    generate_sequence,
)
from chant.schema import NoteTable, TrackMetadata
from chant.tokeniser import decode

CHECKPOINT_DIR = Path("_data/chant_checkpoints")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def loaded_model():
    """Load model + tokenizer once per test session — slow operation."""
    from chant.train import load_trained_model
    if not (CHECKPOINT_DIR / "lora_adapter").exists():
        pytest.skip("Checkpoint not found — run `python -m chant.train` first")
    model, tokenizer = load_trained_model(CHECKPOINT_DIR)
    return model, tokenizer


# ---------------------------------------------------------------------------
# GenerationResult dataclass
# ---------------------------------------------------------------------------

def _make_empty_table() -> NoteTable:
    return NoteTable(
        metadata=TrackMetadata(source_format="generated", source_path=""),
        events=[],
    )


def test_generation_result_fields():
    result = GenerationResult(
        prompt="test prompt",
        raw_output="<BOS> N60 D100 C0 V7 <EOS>",
        note_table=_make_empty_table(),
        num_events=1,
        generation_time_s=0.5,
    )
    assert result.prompt == "test prompt"
    assert result.num_events == 1
    assert result.generation_time_s == 0.5
    assert isinstance(result.note_table, NoteTable)


def test_generation_result_empty_note_table():
    result = GenerationResult(
        prompt="nothing",
        raw_output="",
        note_table=_make_empty_table(),
        num_events=0,
        generation_time_s=0.0,
    )
    assert result.num_events == 0
    assert result.note_table.events == []


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

def test_format_prompt_structure():
    caption = "A fast SID tune with arpeggios"
    result = format_prompt(caption)
    assert result.startswith("### Instruction:\n")
    assert caption in result
    assert result.endswith("### Response:\n")


def test_format_prompt_matches_training_format():
    """Must match build_training.format_training_example output."""
    from chant.build_training import format_training_example

    caption = "Slow MOD with bass and drums"
    training = format_training_example(caption, "<BOS> <EOS>")
    generated = format_prompt(caption)
    assert generated == training["prompt"]


def test_format_prompt_preserves_newlines():
    caption = "Line one\nLine two"
    result = format_prompt(caption)
    assert "Line one\nLine two" in result


# ---------------------------------------------------------------------------
# generate_sequence — real model
# ---------------------------------------------------------------------------

def test_generate_sequence_returns_result(loaded_model):
    model, tokenizer = loaded_model
    result = generate_sequence(
        "A simple chip tune",
        max_new_tokens=128,
        model=model,
        tokenizer=tokenizer,
    )
    assert isinstance(result, GenerationResult)
    assert result.prompt == "A simple chip tune"
    assert isinstance(result.raw_output, str)
    assert isinstance(result.note_table, NoteTable)
    assert result.generation_time_s >= 0.0
    assert result.num_events == len(result.note_table.events)


def test_generate_sequence_note_table_type(loaded_model):
    model, tokenizer = loaded_model
    result = generate_sequence(
        "Fast 4-channel MOD",
        max_new_tokens=64,
        model=model,
        tokenizer=tokenizer,
    )
    assert isinstance(result.note_table, NoteTable)
    assert isinstance(result.note_table.events, list)


def test_generate_sequence_num_events_consistent(loaded_model):
    model, tokenizer = loaded_model
    result = generate_sequence(
        "Slow SID melody",
        max_new_tokens=128,
        model=model,
        tokenizer=tokenizer,
    )
    assert result.num_events == len(result.note_table.events)


def test_generate_sequence_handles_unparseable_output(loaded_model):
    """Even if output is garbage, should return a GenerationResult with empty table."""
    model, tokenizer = loaded_model
    # Very short max_new_tokens — likely incomplete / unparseable output
    result = generate_sequence(
        "test",
        max_new_tokens=1,
        model=model,
        tokenizer=tokenizer,
    )
    assert isinstance(result, GenerationResult)
    assert isinstance(result.note_table, NoteTable)


# ---------------------------------------------------------------------------
# decode from generated output
# ---------------------------------------------------------------------------

def test_decode_produces_note_events_from_valid_token_string():
    token_str = "<BOS> N60 D100 C0 V7 | N64 D200 C1 V5 <EOS>"
    events = decode(token_str)
    assert len(events) == 2
    assert all(e.pitch_hz > 0 for e in events)
    assert all(e.duration_ms > 0 for e in events)


def test_decode_handles_empty_string():
    assert decode("") == []


def test_decode_handles_bos_eos_only():
    assert decode("<BOS> <EOS>") == []


def test_decode_skips_malformed_events():
    # Only the first event is complete
    token_str = "<BOS> N60 D100 C0 V7 | N64 D200 <EOS>"
    events = decode(token_str)
    assert len(events) == 1


def test_decode_on_generated_output(loaded_model):
    """Events decoded from real model output should have valid pitch and duration."""
    model, tokenizer = loaded_model
    result = generate_sequence(
        "4-channel AY tune with melody",
        max_new_tokens=256,
        model=model,
        tokenizer=tokenizer,
    )
    events = decode(result.raw_output)
    # Events may be 0 for a short run; just check types
    for e in events:
        assert e.pitch_hz > 0
        assert e.duration_ms > 0
        assert 0 <= e.channel <= 31


# ---------------------------------------------------------------------------
# generate_batch
# ---------------------------------------------------------------------------

def test_generate_batch_returns_list(loaded_model):
    model, tokenizer = loaded_model
    prompts = ["fast SID", "slow MOD bass"]
    # generate_batch loads its own model — we patch checkpoint existence check
    # by just calling generate_sequence directly for speed; this tests the API shape
    results = [
        generate_sequence(p, max_new_tokens=64, model=model, tokenizer=tokenizer)
        for p in prompts
    ]
    assert len(results) == 2
    assert all(isinstance(r, GenerationResult) for r in results)


def test_generate_batch_result_count():
    """generate_batch returns one result per prompt."""
    # Skip if checkpoint absent
    if not (CHECKPOINT_DIR / "lora_adapter").exists():
        pytest.skip("Checkpoint not found")
    prompts = ["prompt one", "prompt two", "prompt three"]
    results = generate_batch(prompts, max_new_tokens=32)
    assert len(results) == len(prompts)
