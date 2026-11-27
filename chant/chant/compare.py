"""Conditioned vs unconditioned comparison for chant.

Measures whether text conditioning improves generation quality vs
a generic "Generate a chip-tune note sequence" prompt.

Usage:
    python -m chant.compare [--num-samples 20] [--max-new-tokens 512]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

from chant.generate import generate_sequence
from chant.train import BASE_MODEL, CHECKPOINT_DIR, load_trained_model
from chant.validate import compare_conditioned_vs_unconditioned, validate_events

UNCONDITIONED_PROMPT = "Generate a chip-tune note sequence"
VAL_PATH = Path("_data/dataset/training/val.jsonl")

DIVERSITY_METRICS = (
    "pitch_diversity",
    "duration_diversity",
    "channel_spread",
)


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class ComparisonReport:
    """Aggregated results of a conditioned vs unconditioned comparison run."""

    num_samples: int
    conditioned_valid: int
    unconditioned_valid: int
    conditioned_avg_events: float
    unconditioned_avg_events: float
    diversity_comparison: dict = field(default_factory=dict)
    conditioned_wins: dict[str, int] = field(default_factory=dict)
    summary: str = ""


# ---------------------------------------------------------------------------
# Val prompt loading
# ---------------------------------------------------------------------------


def _load_val_captions(n: int) -> list[str]:
    """Load n raw captions from val.jsonl."""
    if not VAL_PATH.exists():
        raise FileNotFoundError(
            f"{VAL_PATH} not found — run `python -m chant.build_training` first"
        )
    captions: list[str] = []
    with open(VAL_PATH) as f:
        for line in f:
            if len(captions) >= n:
                break
            ex = json.loads(line)
            caption = ex["prompt"]
            if caption.startswith("### Instruction:\n"):
                caption = caption[len("### Instruction:\n"):]
            if caption.endswith("\n### Response:\n"):
                caption = caption[: -len("\n### Response:\n")]
            captions.append(caption.strip())
    return captions


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _make_diversity_comparison(per_sample: list[dict]) -> dict:
    """Average per-metric diversity across all samples."""
    if not per_sample:
        return {}

    result: dict[str, float] = {}
    for metric in DIVERSITY_METRICS:
        cond_key = f"{metric}_conditioned"
        uncond_key = f"{metric}_unconditioned"
        result[cond_key] = sum(s[cond_key] for s in per_sample) / len(per_sample)
        result[uncond_key] = sum(s[uncond_key] for s in per_sample) / len(per_sample)
    return result


def _count_wins(per_sample: list[dict]) -> dict[str, int]:
    """Count how many samples conditioned > unconditioned per metric."""
    wins: dict[str, int] = {m: 0 for m in DIVERSITY_METRICS}
    for sample in per_sample:
        for metric in DIVERSITY_METRICS:
            if sample[f"{metric}_conditioned"] > sample[f"{metric}_unconditioned"]:
                wins[metric] += 1
    return wins


def _make_summary(conditioned_wins: dict[str, int], num_samples: int) -> str:
    """One-line verdict based on win counts."""
    if num_samples == 0:
        return "No samples — cannot determine conditioning benefit."
    num_metrics = len(DIVERSITY_METRICS)
    total_possible = num_metrics * num_samples
    total_wins = sum(conditioned_wins.values())
    win_ratio = total_wins / total_possible if total_possible > 0 else 0.0
    dominant = sum(
        1 for m in DIVERSITY_METRICS
        if conditioned_wins.get(m, 0) > num_samples / 2
    )
    if dominant >= 2:
        return (
            f"Conditioning helps: conditioned wins {total_wins}/{total_possible} "
            f"metric-samples ({win_ratio:.0%})."
        )
    return (
        f"No clear benefit: conditioned wins only {total_wins}/{total_possible} "
        f"metric-samples ({win_ratio:.0%})."
    )


# ---------------------------------------------------------------------------
# Main comparison runner
# ---------------------------------------------------------------------------


def run_comparison(
    num_samples: int = 20,
    max_new_tokens: int = 512,
    checkpoint_dir: Path = CHECKPOINT_DIR,
    base_model: str = BASE_MODEL,
) -> ComparisonReport:
    """Run conditioned vs unconditioned comparison over val prompts.

    Loads the model once, then for each val caption generates:
      - conditioned: using the real caption
      - unconditioned: using UNCONDITIONED_PROMPT

    Returns a ComparisonReport aggregating results across all samples.
    """
    print(f"Loading model from {checkpoint_dir}...")
    model, tokenizer = load_trained_model(checkpoint_dir, base_model)

    captions = _load_val_captions(num_samples)
    actual_samples = len(captions)
    if actual_samples < num_samples:
        print(f"Warning: only {actual_samples} val captions available.")

    conditioned_valid = 0
    unconditioned_valid = 0
    conditioned_event_counts: list[int] = []
    unconditioned_event_counts: list[int] = []
    per_sample_diversity: list[dict] = []

    for i, caption in enumerate(captions, 1):
        print(f"[{i}/{actual_samples}] Generating conditioned + unconditioned...")

        cond_result = generate_sequence(
            caption,
            max_new_tokens=max_new_tokens,
            model=model,
            tokenizer=tokenizer,
        )
        uncond_result = generate_sequence(
            UNCONDITIONED_PROMPT,
            max_new_tokens=max_new_tokens,
            model=model,
            tokenizer=tokenizer,
        )

        cond_vr = validate_events(cond_result.note_table.events)
        uncond_vr = validate_events(uncond_result.note_table.events)

        if cond_vr.valid:
            conditioned_valid += 1
        if uncond_vr.valid:
            unconditioned_valid += 1

        conditioned_event_counts.append(cond_result.num_events)
        unconditioned_event_counts.append(uncond_result.num_events)

        # Compare diversity only when both have events
        cond_events = cond_result.note_table.events
        uncond_events = uncond_result.note_table.events
        if cond_events or uncond_events:
            diversity = compare_conditioned_vs_unconditioned(cond_events, uncond_events)
            per_sample_diversity.append(diversity)
            print(
                f"  cond events={cond_result.num_events} valid={cond_vr.valid} | "
                f"uncond events={uncond_result.num_events} valid={uncond_vr.valid}"
            )

    diversity_comparison = _make_diversity_comparison(per_sample_diversity)
    conditioned_wins = _count_wins(per_sample_diversity)

    cond_avg = (
        sum(conditioned_event_counts) / actual_samples if actual_samples else 0.0
    )
    uncond_avg = (
        sum(unconditioned_event_counts) / actual_samples if actual_samples else 0.0
    )

    summary = _make_summary(conditioned_wins, len(per_sample_diversity))

    report = ComparisonReport(
        num_samples=actual_samples,
        conditioned_valid=conditioned_valid,
        unconditioned_valid=unconditioned_valid,
        conditioned_avg_events=cond_avg,
        unconditioned_avg_events=uncond_avg,
        diversity_comparison=diversity_comparison,
        conditioned_wins=conditioned_wins,
        summary=summary,
    )

    print(f"\n{'=' * 60}")
    print(f"Samples:          {actual_samples}")
    print(f"Conditioned valid:   {conditioned_valid}/{actual_samples}")
    print(f"Unconditioned valid: {unconditioned_valid}/{actual_samples}")
    print(f"Avg events (cond):   {cond_avg:.1f}")
    print(f"Avg events (uncond): {uncond_avg:.1f}")
    if diversity_comparison:
        print("\nAvg diversity:")
        for metric in DIVERSITY_METRICS:
            c = diversity_comparison.get(f"{metric}_conditioned", 0)
            u = diversity_comparison.get(f"{metric}_unconditioned", 0)
            wins = conditioned_wins.get(metric, 0)
            print(f"  {metric:25s}  cond={c:.2f}  uncond={u:.2f}  wins={wins}")
    print(f"\n{summary}")
    print("=" * 60)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare conditioned vs unconditioned chant generation"
    )
    parser.add_argument("--num-samples", type=int, default=20)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--checkpoint-dir", type=Path, default=CHECKPOINT_DIR)
    parser.add_argument("--base-model", default=BASE_MODEL)
    args = parser.parse_args()

    run_comparison(
        num_samples=args.num_samples,
        max_new_tokens=args.max_new_tokens,
        checkpoint_dir=args.checkpoint_dir,
        base_model=args.base_model,
    )


if __name__ == "__main__":
    main()
