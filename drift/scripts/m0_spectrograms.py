#!/usr/bin/env python3
"""
M0 spectrogram comparison — real-world noise vs chip-tune.

Generates a 2×3 figure:
  Top row:    road noise, rain noise, machine noise
  Bottom row: 3 MOD chip-tunes rendered to .wav

Saves to docs/images/m0-spectrogram-comparison.png

Usage:
    python scripts/m0_spectrograms.py
"""
from pathlib import Path

import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

NOISE_DIR = Path("_data/noise")
CHIPTUNE_DIR = Path("_data/chiptune_wav")
OUTPUT = Path("docs/images/m0-spectrogram-comparison.png")

NOISE_FILES = [
    ("Road", NOISE_DIR / "road.wav"),
    ("Rain", NOISE_DIR / "rain.wav"),
    ("Machine", NOISE_DIR / "machine.wav"),
]

SR = 22050
N_FFT = 2048
HOP_LENGTH = 512
N_MELS = 128
DURATION = 10.0  # seconds to display


def load_mel(path: Path) -> np.ndarray:
    y, sr = librosa.load(path, sr=SR, duration=DURATION, mono=True)
    S = librosa.feature.melspectrogram(
        y=y, sr=sr, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
    )
    return librosa.power_to_db(S, ref=np.max)


def main() -> None:
    chiptune_wavs = sorted(CHIPTUNE_DIR.glob("*.wav"))[:3]
    if len(chiptune_wavs) < 3:
        raise FileNotFoundError(
            f"Need 3 chip-tune .wav files in {CHIPTUNE_DIR}, found {len(chiptune_wavs)}"
        )

    chiptune_files = [(p.stem.replace("_", " ").title(), p) for p in chiptune_wavs]

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    fig.suptitle(
        "M0 — Real-world noise vs chip-tune spectrograms",
        fontsize=14,
        fontweight="bold",
    )

    vmin, vmax = -80, 0

    for col, (label, path) in enumerate(NOISE_FILES):
        S_db = load_mel(path)
        img = librosa.display.specshow(
            S_db,
            sr=SR,
            hop_length=HOP_LENGTH,
            x_axis="time",
            y_axis="mel",
            ax=axes[0, col],
            vmin=vmin,
            vmax=vmax,
            cmap="magma",
        )
        axes[0, col].set_title(f"{label}", fontsize=11)
        if col > 0:
            axes[0, col].set_ylabel("")

    for col, (label, path) in enumerate(chiptune_files):
        S_db = load_mel(path)
        img = librosa.display.specshow(
            S_db,
            sr=SR,
            hop_length=HOP_LENGTH,
            x_axis="time",
            y_axis="mel",
            ax=axes[1, col],
            vmin=vmin,
            vmax=vmax,
            cmap="magma",
        )
        axes[1, col].set_title(f"{label}", fontsize=11)
        if col > 0:
            axes[1, col].set_ylabel("")

    axes[0, 0].annotate(
        "Noise",
        xy=(-0.25, 0.5),
        xycoords="axes fraction",
        fontsize=12,
        fontweight="bold",
        rotation=90,
        va="center",
    )
    axes[1, 0].annotate(
        "Chip-tune",
        xy=(-0.25, 0.5),
        xycoords="axes fraction",
        fontsize=12,
        fontweight="bold",
        rotation=90,
        va="center",
    )

    fig.subplots_adjust(left=0.07, right=0.88, top=0.91, bottom=0.08, wspace=0.25, hspace=0.35)
    cbar_ax = fig.add_axes([0.90, 0.15, 0.015, 0.7])
    fig.colorbar(img, cax=cbar_ax, format="%+2.0f dB")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {OUTPUT}")


if __name__ == "__main__":
    main()
