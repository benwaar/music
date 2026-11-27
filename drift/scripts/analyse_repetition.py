"""Analyse repetition in real vs generated spectrograms using autocorrelation.

Loads real training samples and generated samples, computes autocorrelation
for each, and plots a comparison histogram.

Usage:
    python scripts/analyse_repetition.py
    python scripts/analyse_repetition.py --n-real 100 --n-gen 20
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from drift.dataset import get_dataloader
from drift.metrics import autocorrelation, batch_autocorrelation
from drift.sampler import generate_and_crop
from drift.scheduler import DDPMScheduler
from drift.train import TARGET_WIDTH, get_device, pad_to_target, target_width_for_duration
from drift.unet import UNet


def load_real_specs(data_dir: Path, n: int, duration: int = 4) -> torch.Tensor:
    tw = target_width_for_duration(duration)
    loader = get_dataloader(
        data_dir, duration=duration, split="train",
        batch_size=n, num_workers=0, shuffle=True,
    )
    specs, _ = next(iter(loader))
    specs = pad_to_target(specs, tw)
    original_width = -(-duration * 22050 // 512)
    return specs[:, :, :, :original_width]


def load_and_generate(
    ckpt_path: Path, n: int, device: torch.device,
    attn_levels: set[int] | None = None,
) -> torch.Tensor:
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    config = ckpt.get("config", {})
    levels = attn_levels or set(config.get("attn_levels", []))
    base_ch = config.get("base_ch", 32)
    model = UNet(base_ch=base_ch, attn_levels=levels).to(device)
    scheduler = DDPMScheduler(num_steps=1000).to(device)
    if "ema_state" in ckpt and ckpt["ema_state"]:
        model.load_state_dict(ckpt["ema_state"], strict=False)
    else:
        model.load_state_dict(ckpt["model_state"])
    model.eval()
    duration = config.get("duration", 4)
    original_width = -(-duration * 22050 // 512)
    return generate_and_crop(model, scheduler, n, device, original_width=original_width)


def plot_comparison(
    real_results: list[tuple[int, float]],
    gen_results: list[tuple[int, float]],
    output_path: Path,
) -> None:
    real_strengths = [s for _, s in real_results]
    gen_strengths = [s for _, s in gen_results]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Histogram of peak strengths
    ax = axes[0]
    bins = np.linspace(0, 1, 25)
    ax.hist(real_strengths, bins=bins, alpha=0.7, label="Real", color="#6c5ce7")
    ax.hist(gen_strengths, bins=bins, alpha=0.7, label="Generated", color="#e84118")
    ax.set_xlabel("Peak Autocorrelation Strength", fontsize=12)
    ax.set_ylabel("Count", fontsize=12)
    ax.set_title("Repetition: Real vs Generated", fontsize=14)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    real_mean = np.mean(real_strengths)
    gen_mean = np.mean(gen_strengths)
    ax.axvline(real_mean, color="#6c5ce7", linestyle="--", linewidth=2, label=f"Real mean: {real_mean:.3f}")
    ax.axvline(gen_mean, color="#e84118", linestyle="--", linewidth=2, label=f"Gen mean: {gen_mean:.3f}")
    ax.legend(fontsize=10)

    # Scatter: peak lag vs peak strength
    ax2 = axes[1]
    real_lags = [l for l, _ in real_results]
    gen_lags = [l for l, _ in gen_results]
    ax2.scatter(real_lags, real_strengths, alpha=0.6, label="Real", color="#6c5ce7", s=30)
    ax2.scatter(gen_lags, gen_strengths, alpha=0.6, label="Generated", color="#e84118", s=30)
    ax2.set_xlabel("Peak Lag (frames)", fontsize=12)
    ax2.set_ylabel("Peak Strength", fontsize=12)
    ax2.set_title("Repetition Period vs Strength", fontsize=14)
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150)
    plt.close(fig)
    print(f"Plot saved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse repetition in real vs generated spectrograms")
    parser.add_argument("--data", default="_data/segments")
    parser.add_argument("--checkpoint", default="_data/checkpoints/epoch_0050.pt")
    parser.add_argument("--n-real", type=int, default=50, dest="n_real")
    parser.add_argument("--n-gen", type=int, default=20, dest="n_gen")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", default="_data/eval/repetition.json")
    parser.add_argument("--plot", default="docs/images/m2d-autocorrelation.png")
    parser.add_argument("--attn-levels", type=int, nargs="*", default=None, dest="attn_levels")
    parser.add_argument("--duration", type=int, default=4, help="Segment duration for real samples (s)")
    args = parser.parse_args()

    device = get_device() if args.device == "auto" else torch.device(args.device)

    print(f"Loading {args.n_real} real samples ({args.duration}s)...")
    real = load_real_specs(Path(args.data), args.n_real, duration=args.duration)
    real_results = batch_autocorrelation(real.cpu(), min_lag=5)

    real_strengths = [s for _, s in real_results]
    print(f"  Real: mean peak strength = {np.mean(real_strengths):.3f}, "
          f"median = {np.median(real_strengths):.3f}")

    print(f"\nGenerating {args.n_gen} samples from {args.checkpoint}...")
    attn = set(args.attn_levels) if args.attn_levels else None
    gen = load_and_generate(Path(args.checkpoint), args.n_gen, device, attn_levels=attn)
    gen_results = batch_autocorrelation(gen.cpu(), min_lag=5)

    gen_strengths = [s for _, s in gen_results]
    print(f"  Generated: mean peak strength = {np.mean(gen_strengths):.3f}, "
          f"median = {np.median(gen_strengths):.3f}")

    # Save JSON
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results = {
        "real": {
            "n": args.n_real,
            "mean_strength": round(float(np.mean(real_strengths)), 4),
            "median_strength": round(float(np.median(real_strengths)), 4),
            "samples": [{"lag": l, "strength": round(s, 4)} for l, s in real_results],
        },
        "generated": {
            "n": args.n_gen,
            "checkpoint": args.checkpoint,
            "mean_strength": round(float(np.mean(gen_strengths)), 4),
            "median_strength": round(float(np.median(gen_strengths)), 4),
            "samples": [{"lag": l, "strength": round(s, 4)} for l, s in gen_results],
        },
    }
    out_path.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nResults saved: {out_path}")

    # Plot
    plot_comparison(real_results, gen_results, Path(args.plot))

    # Summary
    gap = np.mean(real_strengths) - np.mean(gen_strengths)
    print(f"\nSummary:")
    print(f"  Real mean:      {np.mean(real_strengths):.3f}")
    print(f"  Generated mean: {np.mean(gen_strengths):.3f}")
    print(f"  Gap:            {gap:.3f}")
    if gap > 0.1:
        print(f"  → Real samples are significantly more repetitive. Model hasn't learned looping.")
    elif gap > 0.03:
        print(f"  → Real samples are somewhat more repetitive. Model shows some structure.")
    else:
        print(f"  → Similar repetition levels. Model may have learned some periodicity.")


if __name__ == "__main__":
    main()
