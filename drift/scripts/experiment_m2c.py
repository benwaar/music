"""M2c experiment: noise source × strength grid.

Generates samples for 3 noise sources at 3 strength levels,
saves spectrograms + audio, and produces a comparison grid image.

Usage:
    python scripts/experiment_m2c.py
    python scripts/experiment_m2c.py --checkpoint _data/checkpoints/epoch_0050.pt
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import torch

from drift.metrics import mean_spectral_distance
from drift.sampler import generate_and_crop
from drift.scheduler import DDPMScheduler
from drift.train import TARGET_WIDTH, get_device
from drift.unet import UNet
from drift.vocoder import save_audio, spectrogram_to_audio
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from generate import load_checkpoint, load_noise_as_spectrogram, save_spectrogram_image

NOISE_SOURCES = ["road", "rain", "machine"]
STRENGTHS = [0.3, 0.5, 0.7]
N_SAMPLES = 2


def run_experiment(
    model: UNet,
    scheduler: DDPMScheduler,
    device: torch.device,
    noise_dir: Path,
    out_dir: Path,
    global_min: float,
    global_max: float,
) -> list[dict]:
    """Run the full 3×3 grid and return results."""
    results = []

    for source in NOISE_SOURCES:
        wav_path = noise_dir / f"{source}.wav"
        if not wav_path.exists():
            print(f"  Skipping {source}: {wav_path} not found")
            continue

        input_spec = load_noise_as_spectrogram(wav_path, global_min, global_max)

        for strength in STRENGTHS:
            label = f"{source}_s{strength:.1f}"
            sample_dir = out_dir / label
            sample_dir.mkdir(parents=True, exist_ok=True)

            print(f"  {source} × strength {strength} → {sample_dir}/")

            start = input_spec.repeat(N_SAMPLES, 1, 1, 1)
            specs = generate_and_crop(
                model, scheduler, N_SAMPLES, device,
                start_noise=start, strength=strength,
            )

            for i in range(N_SAMPLES):
                spec = specs[i]
                audio = spectrogram_to_audio(spec, global_min, global_max)
                save_audio(audio, sample_dir / f"sample_{i:03d}.wav")
                save_spectrogram_image(
                    spec, sample_dir / f"sample_{i:03d}.png",
                    title=f"{source} s={strength:.1f} #{i}",
                )

            results.append({
                "source": source,
                "strength": strength,
                "n_samples": N_SAMPLES,
                "output_dir": str(sample_dir),
            })

    return results


def build_grid_image(
    out_dir: Path,
    output_path: Path,
) -> None:
    """Build a comparison grid: rows=noise sources, columns=strengths."""
    fig, axes = plt.subplots(
        len(NOISE_SOURCES), len(STRENGTHS),
        figsize=(4 * len(STRENGTHS), 3.5 * len(NOISE_SOURCES)),
    )

    for r, source in enumerate(NOISE_SOURCES):
        for c, strength in enumerate(STRENGTHS):
            ax = axes[r][c]
            label = f"{source}_s{strength:.1f}"
            img_path = out_dir / label / "sample_000.png"

            if img_path.exists():
                img = plt.imread(str(img_path))
                ax.imshow(img)
            ax.set_xticks([])
            ax.set_yticks([])

            if r == 0:
                ax.set_title(f"strength={strength}", fontsize=12)
            if c == 0:
                ax.set_ylabel(source, fontsize=12, rotation=90)

    fig.suptitle("M2c: Noise Source × Denoising Strength", fontsize=14, y=1.01)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Grid image saved: {output_path}")


def compute_steering_metric(
    model: UNet,
    scheduler: DDPMScheduler,
    device: torch.device,
    noise_dir: Path,
    real_specs: torch.Tensor,
    global_min: float,
    global_max: float,
) -> list[dict]:
    """Measure how different noise sources produce different outputs at each strength."""
    metrics = []

    for strength in STRENGTHS:
        outputs_by_source: dict[str, torch.Tensor] = {}

        for source in NOISE_SOURCES:
            wav_path = noise_dir / f"{source}.wav"
            if not wav_path.exists():
                continue
            input_spec = load_noise_as_spectrogram(wav_path, global_min, global_max)
            start = input_spec.repeat(N_SAMPLES, 1, 1, 1)
            specs = generate_and_crop(
                model, scheduler, N_SAMPLES, device,
                start_noise=start, strength=strength,
            )
            outputs_by_source[source] = specs.cpu()

        # Cross-source distance: how different are outputs from different sources?
        sources = list(outputs_by_source.keys())
        cross_distances = []
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                a = outputs_by_source[sources[i]]
                b = outputs_by_source[sources[j]]
                dist = mean_spectral_distance(a, b)
                cross_distances.append({
                    "pair": f"{sources[i]}-{sources[j]}",
                    "distance": round(dist, 4),
                })

        avg_cross = np.mean([d["distance"] for d in cross_distances])
        metrics.append({
            "strength": strength,
            "avg_cross_source_distance": round(float(avg_cross), 4),
            "pairs": cross_distances,
        })
        print(f"  Strength {strength}: avg cross-source MSD = {avg_cross:.4f}")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="M2c noise × strength experiment")
    parser.add_argument("--checkpoint", default="_data/checkpoints/epoch_0050.pt")
    parser.add_argument("--noise-dir", default="_data/noise", dest="noise_dir")
    parser.add_argument("--output", default="_data/generated/m2c")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--global-min", type=float, default=-80.0, dest="global_min")
    parser.add_argument("--global-max", type=float, default=0.0, dest="global_max")
    args = parser.parse_args()

    device = get_device() if args.device == "auto" else torch.device(args.device)
    out_dir = Path(args.output)
    noise_dir = Path(args.noise_dir)

    model, scheduler, config = load_checkpoint(args.checkpoint, device)

    print("=== Phase 1: Generate samples ===")
    results = run_experiment(
        model, scheduler, device, noise_dir, out_dir,
        args.global_min, args.global_max,
    )

    # Save results
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2) + "\n")

    print("\n=== Phase 2: Build comparison grid ===")
    build_grid_image(out_dir, Path("docs/images/m2c-strength-grid.png"))

    print("\n=== Phase 3: Steering metric ===")
    steering = compute_steering_metric(
        model, scheduler, device, noise_dir,
        torch.zeros(1),  # placeholder — not used directly
        args.global_min, args.global_max,
    )
    (out_dir / "steering_metrics.json").write_text(json.dumps(steering, indent=2) + "\n")

    # Summary
    print("\n=== Summary ===")
    print("Cross-source distance by strength (higher = noise source steers more):")
    for s in steering:
        print(f"  strength={s['strength']:.1f}  avg_cross_msd={s['avg_cross_source_distance']:.4f}")

    if len(steering) >= 2:
        low_s = min(steering, key=lambda x: x["strength"])
        high_s = max(steering, key=lambda x: x["strength"])
        if low_s["avg_cross_source_distance"] > high_s["avg_cross_source_distance"]:
            print("\n  Lower strength → more steering. Input noise character is preserved.")
        else:
            print("\n  Higher strength → more steering. Model dominates at low strength.")


if __name__ == "__main__":
    main()
