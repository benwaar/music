"""Batch evaluation of the chant LoRA model against held-out val prompts.

Loads the trained adapter once, generates a sequence per val prompt,
validates each result, and aggregates into an EvaluationReport saved as JSON.

Usage:
    python -m chant.evaluate [--num-samples 66] [--max-new-tokens 512]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from chant.generate import generate_sequence
from chant.metrics import compute_all_metrics
from chant.train import BASE_MODEL, CHECKPOINT_DIR, load_trained_model
from chant.validate import validate_events


# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

VAL_JSONL = Path("_data/dataset/training/val.jsonl")
EVAL_REPORT_PATH = CHECKPOINT_DIR / "eval_report.json"


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------

@dataclass
class EvaluationReport:
    """Aggregated evaluation metrics across a batch of generated samples."""

    num_samples: int
    num_valid: int
    pass_rate: float
    avg_events: float
    avg_generation_time_s: float
    pitch_range: Optional[tuple[float, float]]
    channel_distribution: dict[int, int]
    failure_reasons: dict[str, int]
    avg_metrics: dict[str, float]
    per_sample: list[dict]


# ---------------------------------------------------------------------------
# Val loader
# ---------------------------------------------------------------------------

def _load_val_prompts(val_path: Path, num_samples: int) -> list[str]:
    """Load up to num_samples raw captions from the val JSONL.

    Each line has a ``prompt`` field that wraps the caption in the
    ``### Instruction:`` / ``### Response:`` training format; this strips
    that wrapper to recover the bare caption text.
    """
    if not val_path.exists():
        raise FileNotFoundError(
            f"{val_path} not found — run `python -m chant.build_training` first"
        )

    captions: list[str] = []
    with open(val_path) as fh:
        for line in fh:
            if len(captions) >= num_samples:
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
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate_model(
    num_samples: int = 66,
    max_new_tokens: int = 512,
    checkpoint_dir: Path = CHECKPOINT_DIR,
    base_model: str = BASE_MODEL,
    val_path: Path = VAL_JSONL,
) -> EvaluationReport:
    """Evaluate the trained model on held-out val prompts.

    - Loads the model once.
    - Generates one sequence per prompt.
    - Validates each sequence with validate_events.
    - Prints per-sample progress.
    - Aggregates into an EvaluationReport and saves it as JSON.

    Returns the EvaluationReport.
    """
    prompts = _load_val_prompts(val_path, num_samples)
    total = len(prompts)
    if total == 0:
        raise ValueError(f"No prompts found in {val_path}")

    model, tokenizer = load_trained_model(checkpoint_dir, base_model)

    num_valid = 0
    total_events = 0
    total_time = 0.0
    all_pitch_mins: list[float] = []
    all_pitch_maxs: list[float] = []
    channel_distribution: dict[int, int] = {}
    failure_reasons: dict[str, int] = {}
    all_metrics: list[dict[str, float]] = []
    per_sample: list[dict] = []

    for idx, prompt in enumerate(prompts, start=1):
        result = generate_sequence(
            prompt,
            max_new_tokens=max_new_tokens,
            model=model,
            tokenizer=tokenizer,
        )

        events = result.note_table.events
        vr = validate_events(events)

        total_events += vr.num_events
        total_time += result.generation_time_s

        if vr.valid:
            num_valid += 1
            status = "PASS"
            if vr.pitch_range is not None:
                all_pitch_mins.append(vr.pitch_range[0])
                all_pitch_maxs.append(vr.pitch_range[1])
            for ch in vr.channels_used:
                channel_distribution[ch] = channel_distribution.get(ch, 0) + 1
            all_metrics.append(compute_all_metrics(events))
        else:
            status = "FAIL"
            reason = vr.issues[0] if vr.issues else "unknown"
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

        print(
            f"[{idx}/{total}] {status} — {vr.num_events} events"
            + (f" ({vr.issues[0]})" if not vr.valid and vr.issues else "")
        )

        per_sample.append({
            "index": idx,
            "prompt": prompt[:80],
            "valid": vr.valid,
            "num_events": vr.num_events,
            "issues": vr.issues,
        })

    pitch_range: Optional[tuple[float, float]] = None
    if all_pitch_mins:
        pitch_range = (min(all_pitch_mins), max(all_pitch_maxs))

    avg_metrics: dict[str, float] = {}
    if all_metrics:
        keys = all_metrics[0].keys()
        avg_metrics = {
            k: sum(m[k] for m in all_metrics) / len(all_metrics)
            for k in keys
        }

    report = EvaluationReport(
        num_samples=total,
        num_valid=num_valid,
        pass_rate=num_valid / total,
        avg_events=total_events / total,
        avg_generation_time_s=total_time / total,
        pitch_range=pitch_range,
        channel_distribution=channel_distribution,
        failure_reasons=failure_reasons,
        avg_metrics=avg_metrics,
        per_sample=per_sample,
    )

    _save_report(report, EVAL_REPORT_PATH)
    return report


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _report_to_dict(report: EvaluationReport) -> dict:
    """Convert EvaluationReport to a JSON-serialisable dict."""
    d = asdict(report)
    # tuple → list for JSON; int keys → str for JSON compliance
    if d["pitch_range"] is not None:
        d["pitch_range"] = list(d["pitch_range"])
    d["channel_distribution"] = {
        str(k): v for k, v in d["channel_distribution"].items()
    }
    return d


def _save_report(report: EvaluationReport, path: Path) -> None:
    """Save the report as pretty-printed JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        json.dump(_report_to_dict(report), fh, indent=2)
    print(f"\nReport saved → {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the chant LoRA model on held-out val prompts"
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=66,
        help="Number of val examples to evaluate (default: 66)",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=512,
        help="Max new tokens per generation (default: 512)",
    )
    parser.add_argument(
        "--checkpoint-dir",
        type=Path,
        default=CHECKPOINT_DIR,
    )
    parser.add_argument("--base-model", default=BASE_MODEL)
    args = parser.parse_args()

    report = evaluate_model(
        num_samples=args.num_samples,
        max_new_tokens=args.max_new_tokens,
        checkpoint_dir=args.checkpoint_dir,
        base_model=args.base_model,
    )

    print(f"\n--- Evaluation Summary ---")
    print(f"Samples:       {report.num_samples}")
    print(f"Pass rate:     {report.pass_rate:.1%}  ({report.num_valid}/{report.num_samples})")
    print(f"Avg events:    {report.avg_events:.1f}")
    print(f"Avg time/seq:  {report.avg_generation_time_s:.1f}s")
    if report.pitch_range:
        print(f"Pitch range:   {report.pitch_range[0]:.1f}–{report.pitch_range[1]:.1f} Hz")
    if report.failure_reasons:
        print("Failure reasons:")
        for reason, count in sorted(report.failure_reasons.items(), key=lambda x: -x[1]):
            print(f"  {count:3d}x  {reason}")


if __name__ == "__main__":
    main()
