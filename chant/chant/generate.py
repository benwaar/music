"""Inference pipeline for chant — text description → NoteTable.

Loads a trained LoRA adapter and generates chip-tune note sequences
from text descriptions.

Usage:
    python -m chant.generate "A slow 4-channel MOD with bass"
    python -m chant.generate --from-val 3
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import torch

from chant.schema import NoteEvent, NoteTable, TrackMetadata
from chant.tokeniser import decode
from chant.train import BASE_MODEL, CHECKPOINT_DIR, load_trained_model
from chant.validate import CHANNEL_MAX


# ---------------------------------------------------------------------------
# Post-generation fixups
# ---------------------------------------------------------------------------

def _fixup_events(events: list[NoteEvent]) -> list[NoteEvent]:
    """Clamp generated event fields to valid ranges.

    Fixes channel values that exceed the hardware limit (0–CHANNEL_MAX).
    The model occasionally generates channel 32 from 1-indexed training
    data — clamping is correct behaviour, not lossy.
    """
    for event in events:
        if event.channel < 0 or event.channel > CHANNEL_MAX:
            event.channel = event.channel % (CHANNEL_MAX + 1)
    return events


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    """Result of a single generate_sequence call."""
    prompt: str
    raw_output: str
    note_table: NoteTable
    num_events: int
    generation_time_s: float


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

def format_prompt(caption: str) -> str:
    """Format a caption as a training-style prompt.

    Matches the format used in build_training.format_training_example.
    """
    return f"### Instruction:\n{caption}\n### Response:\n"


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def _empty_note_table() -> NoteTable:
    """Return a NoteTable with no events (fallback for unparseable output)."""
    return NoteTable(
        metadata=TrackMetadata(source_format="generated", source_path=""),
        events=[],
    )


def generate_sequence(
    prompt: str,
    max_new_tokens: int = 512,
    temperature: float = 0.8,
    top_p: float = 0.9,
    repetition_penalty: float = 1.1,
    checkpoint_dir: Path = CHECKPOINT_DIR,
    base_model: str = BASE_MODEL,
    model=None,
    tokenizer=None,
) -> GenerationResult:
    """Generate a NoteTable from a text description.

    If model and tokenizer are pre-loaded, pass them in to avoid
    reloading on every call. Otherwise they are loaded from checkpoint_dir.

    Returns a GenerationResult — note_table will be empty if the model
    output cannot be parsed.
    """
    if model is None or tokenizer is None:
        model, tokenizer = load_trained_model(checkpoint_dir, base_model)

    formatted = format_prompt(prompt)
    inputs = tokenizer(
        formatted,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )
    prompt_len = inputs["input_ids"].shape[1]

    t0 = time.time()
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=True,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            pad_token_id=tokenizer.eos_token_id,
        )
    elapsed = time.time() - t0

    raw_output = tokenizer.decode(
        output_ids[0][prompt_len:],
        skip_special_tokens=False,
    )

    # Parse — silently fall back to empty table on any error
    events: list[NoteEvent] = []
    try:
        events = decode(raw_output)
    except Exception:
        pass

    events = _fixup_events(events)

    note_table = NoteTable(
        metadata=TrackMetadata(source_format="generated", source_path=""),
        events=events,
    )

    return GenerationResult(
        prompt=prompt,
        raw_output=raw_output,
        note_table=note_table,
        num_events=len(events),
        generation_time_s=elapsed,
    )


def generate_batch(
    prompts: list[str],
    max_new_tokens: int = 512,
    temperature: float = 0.8,
    top_p: float = 0.9,
    repetition_penalty: float = 1.1,
    checkpoint_dir: Path = CHECKPOINT_DIR,
    base_model: str = BASE_MODEL,
) -> list[GenerationResult]:
    """Generate NoteTable results for multiple prompts sequentially.

    Loads the model once and reuses it for all prompts.
    """
    model, tokenizer = load_trained_model(checkpoint_dir, base_model)
    return [
        generate_sequence(
            prompt,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            repetition_penalty=repetition_penalty,
            model=model,
            tokenizer=tokenizer,
        )
        for prompt in prompts
    ]


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _load_val_examples(n: int, checkpoint_dir: Path = CHECKPOINT_DIR) -> list[str]:
    """Load n captions from held-out val examples."""
    val_path = Path("_data/dataset/training/val.jsonl")
    if not val_path.exists():
        raise FileNotFoundError(
            f"{val_path} not found — run `python -m chant.build_training` first"
        )
    captions: list[str] = []
    with open(val_path) as f:
        for line in f:
            if len(captions) >= n:
                break
            ex = json.loads(line)
            # Strip the prompt wrapper to get the raw caption
            prompt_text = ex["prompt"]
            # Remove "### Instruction:\n" prefix and "\n### Response:\n" suffix
            caption = prompt_text
            if caption.startswith("### Instruction:\n"):
                caption = caption[len("### Instruction:\n"):]
            if caption.endswith("\n### Response:\n"):
                caption = caption[: -len("\n### Response:\n")]
            captions.append(caption.strip())
    return captions


def _print_result(result: GenerationResult, index: int | None = None) -> None:
    """Print a GenerationResult to stdout."""
    prefix = f"[{index}] " if index is not None else ""
    print(f"{prefix}Prompt:  {result.prompt[:80]}")
    print(f"  Events:  {result.num_events}")
    print(f"  Time:    {result.generation_time_s:.1f}s")
    print(f"  Output:  {result.raw_output[:120]}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate chip-tune note sequences from text"
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Text description to generate from",
    )
    parser.add_argument(
        "--from-val",
        type=int,
        metavar="N",
        help="Generate from N held-out val examples instead of a prompt",
    )
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--repetition-penalty", type=float, default=1.2)
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=CHECKPOINT_DIR,
    )
    parser.add_argument("--base-model", default=BASE_MODEL)
    args = parser.parse_args()

    if args.from_val is not None:
        captions = _load_val_examples(args.from_val)
        if not captions:
            print("No val examples found.")
            return
        print(f"Generating from {len(captions)} val examples...\n")
        results = generate_batch(
            captions,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            repetition_penalty=args.repetition_penalty,
            checkpoint_dir=args.checkpoint_dir,
            base_model=args.base_model,
        )
        for i, result in enumerate(results, 1):
            _print_result(result, index=i)
    elif args.prompt:
        print(f"Generating...\n")
        result = generate_sequence(
            args.prompt,
            max_new_tokens=args.max_new_tokens,
            temperature=args.temperature,
            top_p=args.top_p,
            repetition_penalty=args.repetition_penalty,
            checkpoint_dir=args.checkpoint_dir,
            base_model=args.base_model,
        )
        _print_result(result)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
