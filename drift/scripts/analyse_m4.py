"""Analyse M4 conditional training progression across epochs.

Generates samples per chip type at each checkpoint, measures:
- Mean Spectral Distance (MSD) vs real data per chip type
- Autocorrelation (repetition) per chip type
- Cross-chip MSD (are conditioned outputs distinguishable?)

Usage:
    python scripts/analyse_m4.py
    python scripts/analyse_m4.py --n-samples 5 --epochs 2,10,20
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from drift.dataset import CHIP_TYPES, get_dataloader
from drift.metrics import autocorrelation, mean_spectral_distance
from drift.sampler import generate_and_crop
from drift.scheduler import DDIMScheduler
from drift.train import get_device, target_width_for_duration
from drift.unet import UNet

CKPT_DIR = Path("_data/checkpoints_m4_conditional")
DATA_DIR = Path("_data/segments_loops")
OUT_DIR = Path("_data/analysis_m4")

CHIP_INDEX = {name: i for i, name in enumerate(CHIP_TYPES)}


def load_model(ckpt_path: Path, device: torch.device) -> tuple[UNet, dict]:
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    config = ckpt.get("config", {})
    base_ch = config.get("base_ch", 64)
    num_classes = config.get("num_classes", 4)
    model = UNet(base_ch=base_ch, num_classes=num_classes).to(device)
    if "ema_state" in ckpt and ckpt["ema_state"]:
        model.load_state_dict(ckpt["ema_state"], strict=False)
    else:
        model.load_state_dict(ckpt["model_state"])
    model.eval()
    return model, config


def load_real_per_chip(
    data_dir: Path, n_per_chip: int, duration: int = 8, device: str = "cpu"
) -> dict[str, torch.Tensor]:
    tw = target_width_for_duration(duration)
    original_width = -(-duration * 22050 // 512)
    result = {}
    loader = get_dataloader(
        data_dir, duration=duration, split="train",
        batch_size=min(n_per_chip * len(CHIP_TYPES), 64),
        num_workers=0, shuffle=True,
    )
    # Accumulate per-chip
    per_chip: dict[str, list[torch.Tensor]] = {c: [] for c in CHIP_TYPES}
    for specs, labels in loader:
        for i, label in enumerate(labels):
            chip = CHIP_TYPES[label.item()]
            if len(per_chip[chip]) < n_per_chip:
                spec = specs[i:i+1]
                if spec.shape[-1] < tw:
                    spec = torch.nn.functional.pad(spec, (0, tw - spec.shape[-1]))
                per_chip[chip].append(spec[:, :, :, :original_width])
        if all(len(v) >= n_per_chip for v in per_chip.values()):
            break
    for chip, specs_list in per_chip.items():
        if specs_list:
            result[chip] = torch.cat(specs_list, dim=0)
    return result


def generate_per_chip(
    model: UNet, config: dict, n_per_chip: int, device: torch.device,
    guidance_scale: float = 3.0,
) -> dict[str, torch.Tensor]:
    duration = config.get("duration", 8)
    tw = target_width_for_duration(duration)
    original_width = -(-duration * 22050 // 512)
    scheduler = DDIMScheduler(num_train_steps=1000, num_inference_steps=50, eta=1.0).to(device)
    result = {}
    for chip_name, chip_idx in CHIP_INDEX.items():
        label = torch.full((n_per_chip,), chip_idx, dtype=torch.long)
        specs = generate_and_crop(
            model, scheduler, n_per_chip, device,
            original_width=original_width,
            class_label=label, guidance_scale=guidance_scale,
        )
        result[chip_name] = specs
    return result


def compute_autocorrelation(specs: torch.Tensor) -> float:
    values = []
    for i in range(specs.shape[0]):
        _lag, strength = autocorrelation(specs[i])
        values.append(strength)
    return float(np.mean(values))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", default=None, help="Comma-separated epochs (default: all)")
    parser.add_argument("--n-samples", type=int, default=4, help="Samples per chip per epoch")
    parser.add_argument("--guidance-scale", type=float, default=3.0)
    args = parser.parse_args()

    device = get_device()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find epochs
    if args.epochs:
        epochs = [int(e) for e in args.epochs.split(",")]
    else:
        epochs = sorted(
            int(p.stem.split("_")[1])
            for p in CKPT_DIR.glob("epoch_*.pt")
        )

    print(f"Analysing epochs: {epochs}")
    print(f"Samples per chip: {args.n_samples}")
    print(f"Guidance scale: {args.guidance_scale}")
    print()

    # Load real data
    print("Loading real samples per chip type...")
    real_per_chip = load_real_per_chip(DATA_DIR, args.n_samples * 2, device=str(device))
    for chip, specs in real_per_chip.items():
        print(f"  {chip}: {specs.shape[0]} real samples")

    # Real autocorrelation baseline
    real_autocorr = {}
    for chip, specs in real_per_chip.items():
        real_autocorr[chip] = compute_autocorrelation(specs)
    print(f"\nReal autocorrelation: {', '.join(f'{c}={v:.3f}' for c, v in real_autocorr.items())}")

    # Sweep epochs
    results: dict[int, dict] = {}
    for epoch in epochs:
        ckpt_path = CKPT_DIR / f"epoch_{epoch:04d}.pt"
        if not ckpt_path.exists():
            print(f"Skipping epoch {epoch} — no checkpoint")
            continue

        print(f"\n{'='*60}")
        print(f"  Epoch {epoch}")
        print(f"{'='*60}")

        model, config = load_model(ckpt_path, device)
        gen_per_chip = generate_per_chip(
            model, config, args.n_samples, device,
            guidance_scale=args.guidance_scale,
        )

        epoch_results = {"msd": {}, "autocorr": {}, "cross_msd": {}}

        # Per-chip MSD and autocorrelation
        for chip in CHIP_TYPES:
            if chip not in gen_per_chip or chip not in real_per_chip:
                continue
            gen = gen_per_chip[chip]
            real = real_per_chip[chip][:args.n_samples]

            msd = mean_spectral_distance(real, gen.cpu())
            ac = compute_autocorrelation(gen.cpu())
            epoch_results["msd"][chip] = float(msd)
            epoch_results["autocorr"][chip] = float(ac)
            print(f"  {chip:12s}  MSD={msd:.4f}  autocorr={ac:.3f} (real={real_autocorr.get(chip, 0):.3f})")

        # Cross-chip MSD: how different are the chip outputs from each other?
        chips = list(gen_per_chip.keys())
        for i, c1 in enumerate(chips):
            for c2 in chips[i+1:]:
                cross = mean_spectral_distance(
                    gen_per_chip[c1].cpu(),
                    gen_per_chip[c2].cpu(),
                )
                epoch_results["cross_msd"][f"{c1}_vs_{c2}"] = float(cross)

        avg_cross = np.mean(list(epoch_results["cross_msd"].values())) if epoch_results["cross_msd"] else 0
        print(f"  cross-chip MSD (avg): {avg_cross:.4f}")

        results[epoch] = epoch_results
        del model
        torch.mps.empty_cache() if device.type == "mps" else None

    # Plot results
    print(f"\n{'='*60}")
    print("  Plotting")
    print(f"{'='*60}")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # 1: MSD per chip over epochs
    ax = axes[0, 0]
    for chip in CHIP_TYPES:
        vals = [results[e]["msd"].get(chip, None) for e in epochs if e in results]
        ep = [e for e in epochs if e in results]
        ax.plot(ep, vals, "o-", label=chip)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("MSD (lower = closer to real)")
    ax.set_title("Mean Spectral Distance vs Real Data")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2: Autocorrelation per chip over epochs
    ax = axes[0, 1]
    for chip in CHIP_TYPES:
        vals = [results[e]["autocorr"].get(chip, None) for e in epochs if e in results]
        ep = [e for e in epochs if e in results]
        ax.plot(ep, vals, "o-", label=f"{chip} (gen)")
        if chip in real_autocorr:
            ax.axhline(y=real_autocorr[chip], color=ax.get_lines()[-1].get_color(),
                       linestyle="--", alpha=0.4, label=f"{chip} (real)")
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Autocorrelation (higher = more repetition)")
    ax.set_title("Repetition: Generated vs Real")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, alpha=0.3)

    # 3: Cross-chip MSD over epochs
    ax = axes[1, 0]
    avg_cross_by_epoch = []
    for e in epochs:
        if e in results and results[e]["cross_msd"]:
            avg_cross_by_epoch.append(np.mean(list(results[e]["cross_msd"].values())))
        else:
            avg_cross_by_epoch.append(None)
    ep_valid = [e for e, v in zip(epochs, avg_cross_by_epoch) if v is not None]
    vals_valid = [v for v in avg_cross_by_epoch if v is not None]
    ax.plot(ep_valid, vals_valid, "o-", color="purple", linewidth=2)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Cross-chip MSD (higher = more distinct)")
    ax.set_title("Conditioning Effectiveness: How Different Are Chip Outputs?")
    ax.grid(True, alpha=0.3)

    # 4: Summary table
    ax = axes[1, 1]
    ax.axis("off")
    rows = []
    for chip in CHIP_TYPES:
        if epochs[-1] in results and chip in results[epochs[-1]]["msd"]:
            final = results[epochs[-1]]
            rows.append([
                chip,
                f"{final['msd'].get(chip, 0):.4f}",
                f"{final['autocorr'].get(chip, 0):.3f}",
                f"{real_autocorr.get(chip, 0):.3f}",
            ])
    table = ax.table(
        cellText=rows,
        colLabels=["Chip", "MSD", "Gen AC", "Real AC"],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(True)
    table.scale(1, 1.5)
    ax.set_title("Epoch 20 Summary", fontweight="bold", y=0.85)

    fig.suptitle("M4 Conditional Training Analysis", fontsize=14, fontweight="bold")
    fig.tight_layout()
    out_path = OUT_DIR / "m4_progression.png"
    fig.savefig(str(out_path), dpi=150)
    plt.close(fig)
    print(f"\nSaved: {out_path}")

    # Print final summary
    print(f"\n{'='*60}")
    print("  Summary")
    print(f"{'='*60}")
    if epochs[-1] in results:
        final = results[epochs[-1]]
        for chip in CHIP_TYPES:
            msd = final["msd"].get(chip, 0)
            ac = final["autocorr"].get(chip, 0)
            real_ac = real_autocorr.get(chip, 0)
            print(f"  {chip:12s}  MSD={msd:.4f}  autocorr={ac:.3f} (real={real_ac:.3f}, gap={abs(ac - real_ac):.3f})")
        print(f"  cross-chip MSD (avg): {np.mean(list(final['cross_msd'].values())):.4f}")


if __name__ == "__main__":
    main()
