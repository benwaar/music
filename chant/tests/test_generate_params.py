"""Tests for generate_sequence / generate_batch signatures and format_prompt."""

from __future__ import annotations

import inspect

from chant.generate import format_prompt, generate_batch, generate_sequence


# ---------------------------------------------------------------------------
# Signature: generate_sequence
# ---------------------------------------------------------------------------

def test_generate_sequence_accepts_repetition_penalty():
    sig = inspect.signature(generate_sequence)
    assert "repetition_penalty" in sig.parameters


def test_generate_sequence_repetition_penalty_default():
    sig = inspect.signature(generate_sequence)
    assert sig.parameters["repetition_penalty"].default == 1.1


# ---------------------------------------------------------------------------
# Signature: generate_batch
# ---------------------------------------------------------------------------

def test_generate_batch_accepts_repetition_penalty():
    sig = inspect.signature(generate_batch)
    assert "repetition_penalty" in sig.parameters


def test_generate_batch_repetition_penalty_default():
    sig = inspect.signature(generate_batch)
    assert sig.parameters["repetition_penalty"].default == 1.1


# ---------------------------------------------------------------------------
# format_prompt
# ---------------------------------------------------------------------------

def test_format_prompt_structure():
    caption = "A fast 4-channel MOD with arpeggios"
    result = format_prompt(caption)
    assert result == f"### Instruction:\n{caption}\n### Response:\n"


def test_format_prompt_contains_caption():
    caption = "Slow ambient SID tune in C minor"
    assert caption in format_prompt(caption)


def test_format_prompt_starts_with_instruction_header():
    result = format_prompt("anything")
    assert result.startswith("### Instruction:\n")


def test_format_prompt_ends_with_response_header():
    result = format_prompt("anything")
    assert result.endswith("### Response:\n")
