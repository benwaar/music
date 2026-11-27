"""M5 analysis: measure how real-world noise sources steer generation.

Three analyses:
1. Cross-source: are road/rain/machine outputs measurably different at each strength?
2. Conditioning × noise interaction: does noise source affect chip separation?
3. Gaussian vs noise: how much does the noise source steer vs Gaussian starts?

Also produces frequency analysis of input vs output spectrograms.

Usage:
    python scripts/analyse_m5.py
    python scripts/analyse_m5.py --data-dir _data/generated/m5_noise --output _data/generated/m5_noise/analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import librosa
import matplotlib.pyplot as plt
import numpy as np
import torch

from drift.dataset import CHIP_TYPES, HOP_LENGTH, N_FFT, N_MELS, SR
from drift.metrics import autocorrelation, mean_spectral_distance_global


NOISE_SOURCES = ["road", "rain", "machine"]
STRENGTHS = [0.3, 0.5, 0.7]
GLOBAL_MIN = -80.0
GLOBAL_MAX = 0.0


def wav_to_spectrogram(wav_path: Path) -> torch.Tensor:
    """Load a WAV file and convert to normalised Mel-spectrogram tensor (1, 128, W)."""
    y, _ = librosa.load(str(wav_path), sr=SR, mono=True)
    S = librosa.feature.melspectrogram(
        y=y, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS,
    )
    S_db = librosa.power_to_db(S, ref=np.max)
    S_norm = 2.0 * (S_db - GLOBAL_MIN) / (GLOBAL_MAX - GLOBAL_MIN) - 1.0
    return torch.FloatTensor(S_norm).unsqueeze(0)


def load_spectrograms(sample_dir: Path) -> torch.Tensor | None:
    """Load spectrograms from WAV files in a sample directory.

    Returns (N, 1, 128, W) tensor or None if no files found.
    """
    wav_files = sorted(sample_dir.glob("sample_*.wav"))
    if not wav_files:
        return None

    specs = []
    for p in wav_files:
        specs.append(wav_to_spectrogram(p))

    min_w = min(s.shape[-1] for s in specs)
    specs = [s[:, :, :min_w] for s in specs]
    return torch.stack(specs)


def load_input_spectrogram(noise_wav_path: Path) -> torch.Tensor | None:
    """Load a noise source WAV and convert to spectrogram tensor (1, 1, 128, W)."""
    if not noise_wav_path.exists():
        return None
    return wav_to_spectrogram(noise_wav_path).unsqueeze(0)


def cross_source_analysis(
    data_dir: Path,
) -> list[dict]:
    """Compute MSD between outputs from different noise sources at each strength."""
    results = []

    for strength in STRENGTHS:
        outputs_by_source: dict[str, torch.Tensor] = {}

        for source in NOISE_SOURCES:
            sample_dir = data_dir / source / f"uncond_s{strength}"
            specs = load_spectrograms(sample_dir)
            if specs is not None:
                outputs_by_source[source] = specs

        sources = list(outputs_by_source.keys())
        pairs = []
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                dist = mean_spectral_distance_global(
                    outputs_by_source[sources[i]],
                    outputs_by_source[sources[j]],
                )
                pairs.append({
                    "pair": f"{sources[i]}-{sources[j]}",
                    "msd": round(dist, 4),
                })

        avg = np.mean([p["msd"] for p in pairs]) if pairs else 0.0
        results.append({
            "strength": strength,
            "avg_cross_source_msd": round(float(avg), 4),
            "pairs": pairs,
        })

    return results


def conditioning_noise_interaction(
    data_dir: Path,
) -> list[dict]:
    """Measure cross-chip MSD per noise source — does noise affect chip separation?"""
    results = []

    for source in NOISE_SOURCES + ["gaussian"]:
        for strength in STRENGTHS:
            outputs_by_chip: dict[str, torch.Tensor] = {}

            for chip in CHIP_TYPES:
                if source == "gaussian":
                    sample_dir = data_dir / "gaussian" / chip
                else:
                    sample_dir = data_dir / source / f"{chip}_s{strength}"
                specs = load_spectrograms(sample_dir)
                if specs is not None:
                    outputs_by_chip[chip] = specs

            chips = list(outputs_by_chip.keys())
            pairs = []
            for i in range(len(chips)):
                for j in range(i + 1, len(chips)):
                    dist = mean_spectral_distance_global(
                        outputs_by_chip[chips[i]],
                        outputs_by_chip[chips[j]],
                    )
                    pairs.append({
                        "pair": f"{chips[i]}-{chips[j]}",
                        "msd": round(dist, 4),
                    })

            avg = np.mean([p["msd"] for p in pairs]) if pairs else 0.0
            results.append({
                "source": source,
                "strength": strength,
                "avg_cross_chip_msd": round(float(avg), 4),
                "pairs": pairs,
            })

            if source == "gaussian":
                break  # gaussian has no strength dimension

    return results


def gaussian_vs_noise_comparison(
    data_dir: Path,
) -> list[dict]:
    """MSD between Gaussian-start and noise-start outputs."""
    results = []

    gaussian_uncond = load_spectrograms(data_dir / "gaussian" / "uncond")

    for source in NOISE_SOURCES:
        for strength in STRENGTHS:
            noise_specs = load_spectrograms(
                data_dir / source / f"uncond_s{strength}"
            )
            if noise_specs is None or gaussian_uncond is None:
                continue

            dist = mean_spectral_distance_global(gaussian_uncond, noise_specs)
            results.append({
                "source": source,
                "strength": strength,
                "msd_vs_gaussian": round(dist, 4),
            })

    return results


def frequency_analysis(
    data_dir: Path,
) -> list[dict]:
    """Compare energy profile of input noise vs generated output.

    For each noise source at each strength, compute mean energy per Mel bin
    (frequency band) for the input and output. Shows what frequency ranges
    the model preserves vs overrides.
    """
    results = []

    noise_dir = Path("_data/noise")
    for source in NOISE_SOURCES:
        input_spec = load_input_spectrogram(noise_dir / f"{source}.wav")
        if input_spec is None:
            continue

        input_energy = input_spec.squeeze().mean(dim=1).numpy()

        for strength in STRENGTHS:
            output_specs = load_spectrograms(
                data_dir / source / f"uncond_s{strength}"
            )
            if output_specs is None:
                continue

            output_energy = output_specs.squeeze().mean(dim=-1).mean(dim=0).numpy()

            correlation = float(np.corrcoef(input_energy, output_energy)[0, 1])

            results.append({
                "source": source,
                "strength": strength,
                "input_energy_mean": round(float(input_energy.mean()), 4),
                "output_energy_mean": round(float(output_energy.mean()), 4),
                "frequency_correlation": round(correlation, 4),
            })

    return results


def autocorrelation_analysis(
    data_dir: Path,
) -> list[dict]:
    """Compute autocorrelation (repetition) for each condition."""
    results = []

    for source in NOISE_SOURCES + ["gaussian"]:
        if source == "gaussian":
            specs = load_spectrograms(data_dir / "gaussian" / "uncond")
            if specs is not None:
                for i in range(specs.shape[0]):
                    lag, strength = autocorrelation(specs[i])
                    results.append({
                        "source": "gaussian",
                        "strength": 1.0,
                        "chip": "uncond",
                        "autocorr_lag": lag,
                        "autocorr_strength": round(strength, 4),
                    })
        else:
            for s in STRENGTHS:
                specs = load_spectrograms(data_dir / source / f"uncond_s{s}")
                if specs is None:
                    continue
                for i in range(specs.shape[0]):
                    lag, ac_strength = autocorrelation(specs[i])
                    results.append({
                        "source": source,
                        "strength": s,
                        "chip": "uncond",
                        "autocorr_lag": lag,
                        "autocorr_strength": round(ac_strength, 4),
                    })

    return results


def build_comparison_grid(
    data_dir: Path, output_path: Path,
) -> None:
    """Build a comparison grid: rows = noise sources + gaussian, cols = strengths."""
    sources = NOISE_SOURCES + ["gaussian"]
    fig, axes = plt.subplots(
        len(sources), len(STRENGTHS),
        figsize=(4 * len(STRENGTHS), 3.5 * len(sources)),
    )

    for r, source in enumerate(sources):
        for c, strength in enumerate(STRENGTHS):
            ax = axes[r][c]

            if source == "gaussian":
                img_path = data_dir / "gaussian" / "uncond" / "sample_000.png"
            else:
                img_path = data_dir / source / f"uncond_s{strength}" / "sample_000.png"

            if img_path.exists():
                img = plt.imread(str(img_path))
                ax.imshow(img)
            ax.set_xticks([])
            ax.set_yticks([])

            if r == 0:
                ax.set_title(f"strength={strength}", fontsize=12)
            if c == 0:
                ax.set_ylabel(source, fontsize=12, rotation=90)

    fig.suptitle(
        "M5: Noise Source × Denoising Strength (8s conditional model)",
        fontsize=14, y=1.01,
    )
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def build_chip_grid(
    data_dir: Path, output_path: Path, strength: float = 0.5,
) -> None:
    """Grid: rows = noise sources, cols = chip types at a fixed strength."""
    sources = NOISE_SOURCES + ["gaussian"]
    chips = CHIP_TYPES

    fig, axes = plt.subplots(
        len(sources), len(chips),
        figsize=(3.5 * len(chips), 3 * len(sources)),
    )

    for r, source in enumerate(sources):
        for c, chip in enumerate(chips):
            ax = axes[r][c]

            if source == "gaussian":
                img_path = data_dir / "gaussian" / chip / "sample_000.png"
            else:
                img_path = data_dir / source / f"{chip}_s{strength}" / "sample_000.png"

            if img_path.exists():
                img = plt.imread(str(img_path))
                ax.imshow(img)
            ax.set_xticks([])
            ax.set_yticks([])

            if r == 0:
                ax.set_title(chip, fontsize=11)
            if c == 0:
                ax.set_ylabel(source, fontsize=11, rotation=90)

    fig.suptitle(
        f"M5: Noise Source × Chip Type (strength={strength})",
        fontsize=13, y=1.01,
    )
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(output_path), dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="M5 noise steering analysis")
    parser.add_argument("--data-dir", default="_data/generated/m5_noise", dest="data_dir")
    parser.add_argument("--output", default="_data/generated/m5_noise/analysis")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== Analysis 1: Cross-source steering ===")
    cross = cross_source_analysis(data_dir)
    (out_dir / "cross_source.json").write_text(json.dumps(cross, indent=2) + "\n")
    for r in cross:
        print(f"  strength={r['strength']:.1f}  avg_cross_msd={r['avg_cross_source_msd']:.4f}")

    print("\n=== Analysis 2: Conditioning × noise interaction ===")
    cond = conditioning_noise_interaction(data_dir)
    (out_dir / "conditioning_interaction.json").write_text(json.dumps(cond, indent=2) + "\n")
    for r in cond:
        print(f"  {r['source']:10s} s={r['strength']:.1f}  avg_cross_chip_msd={r['avg_cross_chip_msd']:.4f}")

    print("\n=== Analysis 3: Gaussian vs noise ===")
    gauss = gaussian_vs_noise_comparison(data_dir)
    (out_dir / "gaussian_vs_noise.json").write_text(json.dumps(gauss, indent=2) + "\n")
    for r in gauss:
        print(f"  {r['source']:10s} s={r['strength']:.1f}  msd_vs_gaussian={r['msd_vs_gaussian']:.4f}")

    print("\n=== Analysis 4: Frequency profile ===")
    freq = frequency_analysis(data_dir)
    (out_dir / "frequency_analysis.json").write_text(json.dumps(freq, indent=2) + "\n")
    for r in freq:
        print(f"  {r['source']:10s} s={r['strength']:.1f}  freq_corr={r['frequency_correlation']:.4f}")

    print("\n=== Analysis 5: Autocorrelation ===")
    ac = autocorrelation_analysis(data_dir)
    (out_dir / "autocorrelation.json").write_text(json.dumps(ac, indent=2) + "\n")
    for r in ac:
        print(f"  {r['source']:10s} s={r['strength']:.1f}  autocorr={r['autocorr_strength']:.4f}")

    print("\n=== Building comparison grids ===")
    build_comparison_grid(data_dir, Path("docs/explainers/images/m5-noise-strength-grid.png"))
    print("  Saved: docs/explainers/images/m5-noise-strength-grid.png")

    build_chip_grid(data_dir, Path("docs/explainers/images/m5-noise-chip-grid.png"), strength=0.5)
    print("  Saved: docs/explainers/images/m5-noise-chip-grid.png")

    print("\n=== Summary ===")
    if cross:
        best_strength = max(cross, key=lambda x: x["avg_cross_source_msd"])
        print(f"Best steering at strength={best_strength['strength']:.1f} (MSD={best_strength['avg_cross_source_msd']:.4f})")

    if gauss:
        max_steer = max(gauss, key=lambda x: x["msd_vs_gaussian"])
        print(f"Strongest divergence from Gaussian: {max_steer['source']} s={max_steer['strength']:.1f} (MSD={max_steer['msd_vs_gaussian']:.4f})")

    summary = {
        "cross_source": cross,
        "conditioning_interaction": cond,
        "gaussian_vs_noise": gauss,
        "frequency_analysis": freq,
        "autocorrelation": ac,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nAll results saved to {out_dir}/")


if __name__ == "__main__":
    main()
