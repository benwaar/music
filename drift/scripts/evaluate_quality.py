"""Evaluate generation quality across checkpoints using mean spectral distance.

Generates samples at selected checkpoints, compares against real training data,
and plots the quality improvement curve.

Usage:
    python scripts/evaluate_quality.py                           # defaults
    python scripts/evaluate_quality.py --epochs 10,20,35,50      # specific epochs
    python scripts/evaluate_quality.py --n-samples 10            # more samples (slower)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import torch

from drift.dataset import ChiptuneSpectrogramDataset, get_dataloader
from drift.metrics import mean_spectral_distance, mean_spectral_distance_global
from drift.sampler import generate_and_crop
from drift.scheduler import DDPMScheduler
from drift.train import TARGET_WIDTH, get_device, pad_to_target
from drift.unet import UNet


def load_real_samples(
    data_dir: Path, n_samples: int, device: torch.device
) -> torch.Tensor:
    """Load n real spectrograms from the training set."""
    loader = get_dataloader(
        data_dir,
        duration=4,
        split="train",
        batch_size=n_samples,
        num_workers=0,
        shuffle=True,
    )
    specs, _labels = next(iter(loader))
    specs = pad_to_target(specs, TARGET_WIDTH)
    # Crop back to match generated output shape
    return specs[:, :, :, :173]


def generate_from_checkpoint(
    ckpt_path: Path, n_samples: int, device: torch.device
) -> torch.Tensor:
    """Load a checkpoint and generate n samples."""
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)

    model = UNet(base_ch=32).to(device)
    scheduler = DDPMScheduler(num_steps=1000).to(device)

    if "ema_state" in ckpt and ckpt["ema_state"]:
        model.load_state_dict(ckpt["ema_state"], strict=False)
    else:
        model.load_state_dict(ckpt["model_state"])

    model.eval()
    return generate_and_crop(model, scheduler, n_samples, device)


def plot_quality_curve(
    results: list[dict],
    output_path: Path,
) -> None:
    """Plot epoch vs MSD and save."""
    epochs = [r["epoch"] for r in results]
    msd = [r["msd"] for r in results]
    msd_global = [r["msd_global"] for r in results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Nearest-neighbour MSD
    ax1.plot(epochs, msd, "o-", color="#6c5ce7", linewidth=2, markersize=8)
    ax1.set_xlabel("Epoch", fontsize=12)
    ax1.set_ylabel("Mean Spectral Distance (L1)", fontsize=12)
    ax1.set_title("Quality: Nearest-Neighbour MSD", fontsize=14)
    ax1.grid(True, alpha=0.3)

    if len(msd) >= 2:
        drop = msd[0] - msd[-1]
        pct = (drop / msd[0]) * 100
        ax1.annotate(
            f"Improved {pct:.1f}%",
            xy=(epochs[-1], msd[-1]),
            xytext=(-100, 30),
            textcoords="offset points",
            fontsize=10,
            arrowprops={"arrowstyle": "->", "color": "#636e72"},
            bbox={"boxstyle": "round,pad=0.3", "facecolor": "#dfe6e9"},
        )

    # Global centroid MSD
    ax2.plot(epochs, msd_global, "s-", color="#00b894", linewidth=2, markersize=8)
    ax2.set_xlabel("Epoch", fontsize=12)
    ax2.set_ylabel("Centroid L1 Distance", fontsize=12)
    ax2.set_title("Quality: Centroid MSD", fontsize=14)
    ax2.grid(True, alpha=0.3)

    fig.suptitle("Generation Quality Over Training", fontsize=16, y=1.02)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Plot saved: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate generation quality across checkpoints")
    parser.add_argument("--checkpoint-dir", default="_data/checkpoints", dest="checkpoint_dir")
    parser.add_argument("--data", default="_data/segments")
    parser.add_argument("--epochs", default="10,20,35,50", help="Comma-separated epochs to evaluate")
    parser.add_argument("--n-samples", type=int, default=5, dest="n_samples")
    parser.add_argument("--n-real", type=int, default=100, dest="n_real")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--output", default="_data/eval/quality_history.json")
    parser.add_argument("--plot", default="docs/images/m2b-quality-curve.png")
    args = parser.parse_args()

    device = get_device() if args.device == "auto" else torch.device(args.device)
    target_epochs = [int(e.strip()) for e in args.epochs.split(",")]

    ckpt_dir = Path(args.checkpoint_dir)

    print(f"Loading {args.n_real} real samples for comparison...")
    real = load_real_samples(Path(args.data), args.n_real, device)
    print(f"  Real samples shape: {real.shape}")
    print()

    results = []
    for epoch in target_epochs:
        ckpt_path = ckpt_dir / f"epoch_{epoch:04d}.pt"
        if not ckpt_path.exists():
            print(f"  Epoch {epoch}: checkpoint not found, skipping")
            continue

        print(f"  Epoch {epoch}: generating {args.n_samples} samples...")
        generated = generate_from_checkpoint(ckpt_path, args.n_samples, device)

        # Move to CPU for metric computation
        real_cpu = real.cpu()
        gen_cpu = generated.cpu()

        msd = mean_spectral_distance(real_cpu, gen_cpu)
        msd_g = mean_spectral_distance_global(real_cpu, gen_cpu)

        results.append({
            "epoch": epoch,
            "msd": round(msd, 6),
            "msd_global": round(msd_g, 6),
            "n_generated": args.n_samples,
            "n_real": args.n_real,
        })
        print(f"           MSD = {msd:.4f}  |  Centroid MSD = {msd_g:.4f}")

    # Save JSON
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2) + "\n")
    print(f"\nResults saved: {out_path}")

    # Plot
    if results:
        plot_quality_curve(results, Path(args.plot))

    # Summary
    if len(results) >= 2:
        first_msd = results[0]["msd"]
        last_msd = results[-1]["msd"]
        improvement = (first_msd - last_msd) / first_msd * 100
        trend = "improving" if last_msd < first_msd else "degrading"
        print(f"\nSummary:")
        print(f"  MSD: {first_msd:.4f} → {last_msd:.4f} ({improvement:+.1f}%, {trend})")
        print(f"  Trend: {'More training would help' if trend == 'improving' else 'Quality not improving — consider architectural changes'}")


if __name__ == "__main__":
    main()
