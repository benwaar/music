"""Chip-tune Mel-spectrogram dataset for diffusion model training."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Literal

import librosa
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

SR = 22050
N_FFT = 2048
HOP_LENGTH = 512
N_MELS = 128
CHIP_TYPES = ["modarchive", "sid", "vgm", "ay"]


class ChiptuneSpectrogramDataset(Dataset):
    """PyTorch Dataset for chip-tune Mel-spectrograms.

    Loads pre-sliced segment wav files, converts to normalised Mel-spectrograms,
    and returns (spectrogram_tensor, chip_type_index) pairs.

    Args:
        segments_dir: Root of _data/segments/.
        duration: Segment duration to use — 4 or 8 seconds.
        split: Dataset split — "train", "val", or "test".
        metadata_path: Path to metadata JSON.
                       Defaults to segments_dir / "metadata.json".
    """

    def __init__(
        self,
        segments_dir: Path,
        split: Literal["train", "val", "test"] | None = "train",
        duration: int | None = None,
        metadata_path: Path | None = None,
        metadata: dict | None = None,
        duration_filter: int | None = None,
    ) -> None:
        self.segments_dir = Path(segments_dir)
        self.split = split

        dur = duration_filter or duration
        self.duration = dur

        if metadata is not None:
            meta = metadata
        else:
            meta_path = metadata_path or self.segments_dir / "metadata.json"
            with open(meta_path) as fh:
                meta = json.load(fh)

        self.global_min: float = meta["normalisation"]["min"]
        self.global_max: float = meta["normalisation"]["max"]
        self.chip_types: list[str] = meta["chip_types"]

        if split is None:
            all_paths: list[str] = []
            for paths in meta["splits"].values():
                all_paths.extend(paths)
        else:
            all_paths = meta["splits"][split]

        if dur is not None:
            suffix = f"_{dur}s.wav"
            all_paths = [p for p in all_paths if p.endswith(suffix)]

        self.files: list[Path] = [self.segments_dir / p for p in all_paths]

    def __len__(self) -> int:
        return len(self.files)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, int]:
        path = self.files[idx]

        # Derive chip type from parent directory name.
        chip_type = path.parent.name
        chip_idx = self.chip_types.index(chip_type)

        # Load audio.
        y, _ = librosa.load(str(path), sr=SR, mono=True)

        # Mel-spectrogram → dB scale.
        S = librosa.feature.melspectrogram(
            y=y, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
        )
        S_db = librosa.power_to_db(S, ref=np.max)

        # Normalise to [-1, 1] using dataset-wide statistics.
        S_norm = (
            2.0 * (S_db - self.global_min) / (self.global_max - self.global_min) - 1.0
        )

        # Shape: (1, 128, T).
        tensor = torch.FloatTensor(S_norm).unsqueeze(0)
        return tensor, chip_idx


def build_metadata(
    segments_dir: Path,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    balance: bool = True,
) -> dict:
    """Scan segment wav files, compute global stats, and build train/val/test splits.

    Splits are stratified by chip type. When balance=True, each chip type is
    capped to the size of the smallest type so no type dominates training.
    Normalisation stats are estimated from a random sample of up to 500 files.

    Args:
        segments_dir: Root directory containing {chip_type}/ subdirectories.
        train_ratio: Fraction of files for the training split.
        val_ratio: Fraction of files for the validation split.
                   The remainder goes to the test split.

    Returns:
        Metadata dict (also written to segments_dir / "metadata.json").
    """
    segments_dir = Path(segments_dir)

    # Collect all wav files grouped by chip type.
    files_by_type: dict[str, list[Path]] = {}
    for chip_type in CHIP_TYPES:
        chip_dir = segments_dir / chip_type
        if chip_dir.exists():
            files_by_type[chip_type] = sorted(chip_dir.glob("*.wav"))
        else:
            files_by_type[chip_type] = []

    all_files: list[Path] = [f for files in files_by_type.values() for f in files]
    if not all_files:
        raise ValueError(f"No wav files found under {segments_dir}")

    # Balance: cap each chip type to the smallest.
    if balance:
        non_empty = [len(f) for f in files_by_type.values() if f]
        cap = min(non_empty) if non_empty else 0
        for chip_type in files_by_type:
            if len(files_by_type[chip_type]) > cap:
                files_by_type[chip_type] = random.sample(files_by_type[chip_type], cap)
        all_files = [f for files in files_by_type.values() for f in files]
        print(f"  Balanced to {cap:,} files per chip type ({len(all_files):,} total)")

    # Sample up to 500 files for normalisation stats.
    sample_size = min(500, len(all_files))
    sample = random.sample(all_files, sample_size)

    db_min_vals: list[float] = []
    db_max_vals: list[float] = []
    for path in sample:
        y, _ = librosa.load(str(path), sr=SR, mono=True)
        S = librosa.feature.melspectrogram(
            y=y, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
        )
        S_db = librosa.power_to_db(S, ref=np.max)
        db_min_vals.append(float(S_db.min()))
        db_max_vals.append(float(S_db.max()))

    global_min = float(np.min(db_min_vals))
    global_max = float(np.max(db_max_vals))

    # Stratified split.
    splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}
    for chip_type, files in files_by_type.items():
        if not files:
            continue
        shuffled = files[:]
        random.shuffle(shuffled)
        n = len(shuffled)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        for f in shuffled[:n_train]:
            splits["train"].append(str(f.relative_to(segments_dir)))
        for f in shuffled[n_train : n_train + n_val]:
            splits["val"].append(str(f.relative_to(segments_dir)))
        for f in shuffled[n_train + n_val :]:
            splits["test"].append(str(f.relative_to(segments_dir)))

    metadata = {
        "normalisation": {"min": global_min, "max": global_max},
        "splits": splits,
        "chip_types": CHIP_TYPES,
    }

    out_path = segments_dir / "metadata.json"
    with open(out_path, "w") as fh:
        json.dump(metadata, fh, indent=2)

    print(f"Metadata written to {out_path}")
    print(
        f"  Normalisation  min={global_min:.2f} dB  max={global_max:.2f} dB "
        f"(sampled {sample_size} files)"
    )
    for split_name, paths in splits.items():
        print(f"  {split_name:5s}: {len(paths)} files")

    return metadata


def get_dataloader(
    segments_dir_or_dataset: Path | ChiptuneSpectrogramDataset,
    duration: int | None = None,
    split: Literal["train", "val", "test"] | None = "train",
    batch_size: int = 32,
    num_workers: int = 4,
    shuffle: bool | None = None,
) -> DataLoader:
    """Convenience wrapper — creates dataset (or accepts one) and returns a DataLoader."""
    if isinstance(segments_dir_or_dataset, ChiptuneSpectrogramDataset):
        dataset = segments_dir_or_dataset
    else:
        dataset = ChiptuneSpectrogramDataset(
            segments_dir=Path(segments_dir_or_dataset),
            duration=duration,
            split=split,
        )
    if shuffle is None:
        shuffle = (split == "train")
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=torch.cuda.is_available(),
    )
