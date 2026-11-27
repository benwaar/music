"""LoRA fine-tuning of SmolLM2-360M on chant note sequences.

Loads the base model, attaches LoRA adapters to attention layers,
and trains on prompt/completion pairs from the tokenised dataset.
CPU-only — no CUDA required.

Usage:
    python -m chant.train [--epochs 3] [--batch-size 1] [--max-tokens 2048]
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import torch
from peft import LoraConfig, PeftModel, TaskType, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_MODEL = "HuggingFaceTB/SmolLM2-360M"
CHECKPOINT_DIR = Path("_data/chant_checkpoints")
COMMITTED_ADAPTER = Path("models/lora_adapter")

@dataclass
class TrainConfig:
    base_model: str = BASE_MODEL
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    target_modules: list[str] = field(
        default_factory=lambda: ["q_proj", "v_proj"]
    )
    epochs: int = 3
    batch_size: int = 1
    max_tokens: int = 2048
    learning_rate: float = 2e-4
    checkpoint_dir: Path = CHECKPOINT_DIR
    log_every: int = 10
    max_examples: int | None = None
    resume: bool = False


# ---------------------------------------------------------------------------
# Step 1: Load base model + tokenizer
# ---------------------------------------------------------------------------

def load_base_model(model_name: str) -> tuple:
    """Load SmolLM2-360M and its tokenizer in float32 for CPU training."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.float32,
    )
    return model, tokenizer


# ---------------------------------------------------------------------------
# Step 2: Attach LoRA adapters
# ---------------------------------------------------------------------------

def attach_lora(model, config: TrainConfig):
    """Freeze base weights and attach LoRA adapters to attention layers.

    Returns a PeftModel — same interface, but only adapter params are trainable.
    """
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_rank,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.target_modules,
    )
    peft_model = get_peft_model(model, lora_config)
    return peft_model


def print_trainable_params(model) -> None:
    """Print trainable vs total parameters."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    pct = 100 * trainable / total
    print(f"  Trainable: {trainable:,} / {total:,} ({pct:.2f}%)")


def load_trained_model(
    checkpoint_dir: Path = CHECKPOINT_DIR,
    base_model: str = BASE_MODEL,
) -> tuple:
    """Load a trained LoRA adapter on top of the base model.

    Returns (model, tokenizer) ready for inference.
    """
    adapter_path = checkpoint_dir / "lora_adapter"
    if not adapter_path.exists() and COMMITTED_ADAPTER.exists():
        adapter_path = COMMITTED_ADAPTER
    if not adapter_path.exists():
        raise FileNotFoundError(
            f"LoRA adapter not found at {adapter_path} or {COMMITTED_ADAPTER}. "
            "Run `python -m chant.train` first."
        )

    tokenizer = AutoTokenizer.from_pretrained(str(adapter_path))
    base = AutoModelForCausalLM.from_pretrained(
        base_model, dtype=torch.float32,
    )
    model = PeftModel.from_pretrained(base, str(adapter_path))
    model.eval()
    return model, tokenizer


# ---------------------------------------------------------------------------
# Step 3: Data loading + training loop
# ---------------------------------------------------------------------------

def load_examples(jsonl_path: Path) -> list[dict]:
    """Load prompt/completion pairs from JSONL."""
    examples = []
    with open(jsonl_path) as f:
        for line in f:
            examples.append(json.loads(line))
    return examples


def tokenize_example(
    prompt: str, completion: str, tokenizer, max_tokens: int
) -> dict | None:
    """Tokenize a prompt/completion pair for causal LM training.

    The full text is prompt + completion. Labels mask the prompt tokens
    with -100 so loss is only computed on the completion.
    Returns None if the example is empty after tokenization.
    """
    full_text = prompt + completion
    encoded = tokenizer(
        full_text,
        truncation=True,
        max_length=max_tokens,
        return_tensors="pt",
    )

    prompt_ids = tokenizer(
        prompt,
        truncation=True,
        max_length=max_tokens,
        return_tensors="pt",
    )
    prompt_len = prompt_ids["input_ids"].shape[1]

    input_ids = encoded["input_ids"]
    labels = input_ids.clone()
    labels[0, :prompt_len] = -100

    if (labels != -100).sum() == 0:
        return None

    return {
        "input_ids": input_ids,
        "attention_mask": encoded["attention_mask"],
        "labels": labels,
    }


def batched(examples: list, batch_size: int) -> Iterator[list]:
    """Yield successive batches from a list."""
    for i in range(0, len(examples), batch_size):
        yield examples[i : i + batch_size]


def train(config: TrainConfig) -> list[float]:
    """Run the full training pipeline. Returns per-step loss history."""
    print(f"=== chant LoRA training ===")
    print(f"  Base model: {config.base_model}")
    print(f"  LoRA rank: {config.lora_rank}, alpha: {config.lora_alpha}")
    print(f"  Target modules: {config.target_modules}")
    print(f"  Max tokens: {config.max_tokens}")
    print(f"  Epochs: {config.epochs}, batch size: {config.batch_size}")
    print(f"  Learning rate: {config.learning_rate}")
    print()

    # Step 1
    print("Loading base model...")
    t0 = time.time()
    model, tokenizer = load_base_model(config.base_model)
    print(f"  Loaded in {time.time() - t0:.1f}s")

    # Step 2
    print("Attaching LoRA adapters...")
    model = attach_lora(model, config)
    print_trainable_params(model)
    print()

    # Load data
    train_path = Path("_data/dataset/training/train.jsonl")
    if not train_path.exists():
        raise FileNotFoundError(
            f"{train_path} not found — run `python -m chant.build_training` first"
        )

    print("Loading training data...")
    raw_examples = load_examples(train_path)
    if config.max_examples is not None:
        raw_examples = raw_examples[: config.max_examples]
    print(f"  {len(raw_examples)} raw examples")

    # Pre-tokenize (filter out empties)
    examples = []
    for ex in raw_examples:
        tok_ex = tokenize_example(
            ex["prompt"], ex["completion"], tokenizer, config.max_tokens
        )
        if tok_ex is not None:
            examples.append(tok_ex)
    print(f"  {len(examples)} after tokenization (max {config.max_tokens} tokens)")
    print()

    # Training loop
    model.train()
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate
    )

    loss_history: list[float] = []
    global_step = 0
    start_epoch = 0

    # Resume from last epoch checkpoint if requested
    if config.resume:
        state_path = config.checkpoint_dir / "training_state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text())
            start_epoch = state["completed_epochs"]
            loss_history = state.get("loss_history", [])
            global_step = state.get("global_step", 0)

            adapter_path = config.checkpoint_dir / "lora_adapter"
            if adapter_path.exists():
                from peft import PeftModel as _PM
                model = model.base_model.model
                model = _PM.from_pretrained(model, str(adapter_path))
                model.train()
                optimizer = torch.optim.AdamW(
                    model.parameters(), lr=config.learning_rate
                )
                print(f"  Resumed from epoch {start_epoch}, step {global_step}")
        else:
            print("  No checkpoint to resume from — starting fresh")

    if start_epoch >= config.epochs:
        print(f"  Already completed {start_epoch} epochs — nothing to do")
        return loss_history

    for epoch in range(start_epoch, config.epochs):
        epoch_loss = 0.0
        epoch_steps = 0
        t_epoch = time.time()

        for batch in batched(examples, config.batch_size):
            optimizer.zero_grad()

            batch_loss = torch.tensor(0.0)
            for ex in batch:
                outputs = model(
                    input_ids=ex["input_ids"],
                    attention_mask=ex["attention_mask"],
                    labels=ex["labels"],
                )
                batch_loss = batch_loss + outputs.loss

            batch_loss = batch_loss / len(batch)
            batch_loss.backward()
            optimizer.step()

            loss_val = batch_loss.item()
            loss_history.append(loss_val)
            epoch_loss += loss_val
            epoch_steps += 1
            global_step += 1

            if global_step % config.log_every == 0:
                avg = epoch_loss / epoch_steps
                print(
                    f"  epoch {epoch+1}/{config.epochs}  "
                    f"step {global_step}  "
                    f"loss {loss_val:.4f}  "
                    f"avg {avg:.4f}"
                )

        elapsed = time.time() - t_epoch
        avg_loss = epoch_loss / max(epoch_steps, 1)
        print(
            f"  Epoch {epoch+1} done — "
            f"avg loss {avg_loss:.4f}, "
            f"{elapsed:.0f}s, "
            f"{epoch_steps} steps"
        )

        # Per-epoch checkpoint
        config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        save_path = config.checkpoint_dir / "lora_adapter"
        model.save_pretrained(str(save_path))
        tokenizer.save_pretrained(str(save_path))

        state_path = config.checkpoint_dir / "training_state.json"
        with open(state_path, "w") as f:
            json.dump({
                "completed_epochs": epoch + 1,
                "total_epochs": config.epochs,
                "global_step": global_step,
                "loss_history": loss_history,
                "avg_loss": avg_loss,
            }, f)
        print(f"  Checkpoint saved (epoch {epoch+1})")

    print()
    print(f"Training complete — {global_step} total steps")
    print(f"  Final loss: {loss_history[-1]:.4f}")
    print(f"  Best loss:  {min(loss_history):.4f}")
    print(f"  Adapter at {config.checkpoint_dir / 'lora_adapter'}/")

    return loss_history


# ---------------------------------------------------------------------------
# Step 5: Quality gate
# ---------------------------------------------------------------------------

@dataclass
class QualityResult:
    caption: str
    generated: str
    parseable: bool
    num_events: int
    pitch_in_range: bool
    duration_in_range: bool
    channels_in_range: bool


def quality_gate(
    num_samples: int = 10,
    max_new_tokens: int = 512,
    checkpoint_dir: Path = CHECKPOINT_DIR,
    base_model: str = BASE_MODEL,
) -> list[QualityResult]:
    """Generate sequences from held-out captions and check quality.

    Returns a list of QualityResult for each sample.
    """
    from chant.tokeniser import decode

    print("=== Quality gate ===")
    print(f"  Samples: {num_samples}")
    print(f"  Max new tokens: {max_new_tokens}")
    print()

    # Load model
    print("Loading trained model...")
    model, tokenizer = load_trained_model(checkpoint_dir, base_model)
    print("  Loaded.")

    # Load val prompts
    val_path = Path("_data/dataset/training/val.jsonl")
    if not val_path.exists():
        raise FileNotFoundError(f"{val_path} not found")

    val_examples = load_examples(val_path)[:num_samples]
    print(f"  Using {len(val_examples)} val examples")
    print()

    results: list[QualityResult] = []

    for i, ex in enumerate(val_examples):
        prompt = ex["prompt"]
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)

        with torch.no_grad():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                temperature=0.8,
                top_p=0.9,
                pad_token_id=tokenizer.eos_token_id,
            )

        generated_text = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1]:],
            skip_special_tokens=False,
        )

        # Try to parse
        events = []
        parseable = False
        try:
            events = decode(generated_text)
            parseable = len(events) > 0
        except Exception:
            parseable = False

        pitch_ok = all(20.0 <= e.pitch_hz <= 20000.0 for e in events) if events else False
        dur_ok = all(e.duration_ms > 0 for e in events) if events else False
        ch_ok = all(0 <= e.channel <= 31 for e in events) if events else False

        result = QualityResult(
            caption=prompt[:80] + "...",
            generated=generated_text[:100] + "..." if len(generated_text) > 100 else generated_text,
            parseable=parseable,
            num_events=len(events),
            pitch_in_range=pitch_ok,
            duration_in_range=dur_ok,
            channels_in_range=ch_ok,
        )
        results.append(result)

        status = "PASS" if (parseable and pitch_ok and dur_ok and ch_ok) else "FAIL"
        print(f"  [{i+1}/{len(val_examples)}] {status} — {len(events)} events, parseable={parseable}")

    # Summary
    passed = sum(
        1 for r in results
        if r.parseable and r.pitch_in_range and r.duration_in_range and r.channels_in_range
    )
    print()
    print(f"Quality gate: {passed}/{len(results)} passed")
    print(f"  Parseable: {sum(r.parseable for r in results)}/{len(results)}")
    print(f"  Pitch in range: {sum(r.pitch_in_range for r in results)}/{len(results)}")
    print(f"  Duration in range: {sum(r.duration_in_range for r in results)}/{len(results)}")
    print(f"  Channels in range: {sum(r.channels_in_range for r in results)}/{len(results)}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LoRA fine-tune SmolLM2-360M")
    parser.add_argument("--quality-gate", action="store_true",
                        help="Run quality gate on existing checkpoint instead of training")
    parser.add_argument("--num-samples", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-rank", type=int, default=8)
    parser.add_argument("--log-every", type=int, default=10)
    parser.add_argument("--max-examples", type=int, default=None)
    parser.add_argument("--resume", action="store_true",
                        help="Resume from last epoch checkpoint")
    args = parser.parse_args()

    if args.quality_gate:
        quality_gate(num_samples=args.num_samples)
        return

    config = TrainConfig(
        epochs=args.epochs,
        batch_size=args.batch_size,
        max_tokens=args.max_tokens,
        learning_rate=args.lr,
        lora_rank=args.lora_rank,
        log_every=args.log_every,
        max_examples=args.max_examples,
        resume=args.resume,
    )

    train(config)


if __name__ == "__main__":
    main()
