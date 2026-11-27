"""Unit tests for the M1 spectrogram dataset pipeline.

All tests are self-contained — synthetic wav files are generated via numpy/soundfile,
no real data required.
"""

import math
import numpy as np
import pytest
import soundfile as sf
import torch
from pathlib import Path
from torch.utils.data import DataLoader

from drift.dataset import (
    ChiptuneSpectrogramDataset,
    build_metadata,
    get_dataloader,
    SR,
    N_MELS,
    HOP_LENGTH,
    N_FFT,
    CHIP_TYPES,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sine(freq: float, duration_s: float, sr: int = SR) -> np.ndarray:
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    return np.sin(2 * np.pi * freq * t).astype(np.float32)


def _write_wav(path: Path, freq: float, duration_s: float, sr: int = SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), _sine(freq, duration_s, sr), sr)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_segments_dir(tmp_path: Path) -> Path:
    """Temp directory containing synthetic segment wavs across three chip types."""
    segs = tmp_path / "segments"

    _write_wav(segs / "modarchive" / "test_track_000_4s.wav", 440.0, 4.0)
    _write_wav(segs / "modarchive" / "test_track_001_4s.wav", 880.0, 4.0)
    _write_wav(segs / "modarchive" / "test_track_000_8s.wav", 440.0, 8.0)

    _write_wav(segs / "sid" / "sid_track_000_4s.wav", 660.0, 4.0)
    _write_wav(segs / "sid" / "sid_track_000_8s.wav", 660.0, 8.0)

    _write_wav(segs / "vgm" / "vgm_track_000_4s.wav", 550.0, 4.0)

    return segs


@pytest.fixture
def tmp_metadata(tmp_segments_dir: Path):
    """Build and return metadata dict for the synthetic segments directory."""
    return build_metadata(tmp_segments_dir)


# ---------------------------------------------------------------------------
# build_metadata tests
# ---------------------------------------------------------------------------

def test_build_metadata_creates_json(tmp_segments_dir: Path, tmp_metadata):
    metadata_path = tmp_segments_dir / "metadata.json"
    assert metadata_path.exists(), "metadata.json should be created alongside segments"
    assert "normalisation" in tmp_metadata
    assert "splits" in tmp_metadata
    assert "chip_types" in tmp_metadata


def test_build_metadata_splits_are_disjoint(tmp_metadata):
    splits = tmp_metadata["splits"]
    train = set(splits.get("train", []))
    val = set(splits.get("val", []))
    test = set(splits.get("test", []))

    assert train.isdisjoint(val), "train and val splits must not overlap"
    assert train.isdisjoint(test), "train and test splits must not overlap"
    assert val.isdisjoint(test), "val and test splits must not overlap"


def test_build_metadata_normalisation_range(tmp_metadata):
    norm = tmp_metadata["normalisation"]
    lo = norm["min"]
    hi = norm["max"]
    assert math.isfinite(lo), "normalisation min must be finite"
    assert math.isfinite(hi), "normalisation max must be finite"
    assert lo < hi, "normalisation min must be less than max"


# ---------------------------------------------------------------------------
# ChiptuneSpectrogramDataset tests
# ---------------------------------------------------------------------------

def test_dataset_length(tmp_segments_dir: Path, tmp_metadata):
    for split in ("train", "val", "test"):
        files = tmp_metadata["splits"].get(split, [])
        ds = ChiptuneSpectrogramDataset(
            tmp_segments_dir, split=split, metadata=tmp_metadata
        )
        assert len(ds) == len(files), (
            f"dataset length for split '{split}' should equal number of files in that split"
        )


def test_dataset_getitem_shape_4s(tmp_segments_dir: Path, tmp_metadata):
    """4-second segments → (1, N_MELS, 173) tensors."""
    expected_frames = 1 + (int(SR * 4.0)) // HOP_LENGTH  # 173 with center=True
    ds = ChiptuneSpectrogramDataset(
        tmp_segments_dir, split=None, metadata=tmp_metadata, duration_filter=4
    )
    assert len(ds) > 0, "need at least one 4s segment to test shape"
    spec, _ = ds[0]
    assert isinstance(spec, torch.Tensor)
    assert spec.shape == (1, N_MELS, expected_frames), (
        f"expected shape (1, {N_MELS}, {expected_frames}), got {tuple(spec.shape)}"
    )


def test_dataset_getitem_shape_8s(tmp_segments_dir: Path, tmp_metadata):
    """8-second segments → (1, N_MELS, 345) tensors."""
    expected_frames = 1 + (int(SR * 8.0)) // HOP_LENGTH  # 345 with center=True
    ds = ChiptuneSpectrogramDataset(
        tmp_segments_dir, split=None, metadata=tmp_metadata, duration_filter=8
    )
    assert len(ds) > 0, "need at least one 8s segment to test shape"
    spec, _ = ds[0]
    assert isinstance(spec, torch.Tensor)
    assert spec.shape == (1, N_MELS, expected_frames), (
        f"expected shape (1, {N_MELS}, {expected_frames}), got {tuple(spec.shape)}"
    )


def test_dataset_getitem_range(tmp_segments_dir: Path, tmp_metadata):
    """Normalised spectrograms should live in [-1, 1]."""
    ds = ChiptuneSpectrogramDataset(tmp_segments_dir, split=None, metadata=tmp_metadata)
    assert len(ds) > 0
    spec, _ = ds[0]
    assert spec.min().item() >= -1.0 - 1e-5, "values should be >= -1"
    assert spec.max().item() <= 1.0 + 1e-5, "values should be <= 1"


def test_dataset_getitem_returns_chip_type(tmp_segments_dir: Path, tmp_metadata):
    """Second element of each item is a valid chip-type index."""
    ds = ChiptuneSpectrogramDataset(tmp_segments_dir, split=None, metadata=tmp_metadata)
    assert len(ds) > 0
    for i in range(len(ds)):
        _, chip_idx = ds[i]
        assert isinstance(chip_idx, int), "chip type should be an int"
        assert 0 <= chip_idx < len(CHIP_TYPES), (
            f"chip_idx {chip_idx} out of range [0, {len(CHIP_TYPES)})"
        )


# ---------------------------------------------------------------------------
# DataLoader test
# ---------------------------------------------------------------------------

def test_dataloader_batch(tmp_segments_dir: Path, tmp_metadata):
    """DataLoader should yield (specs, labels) batches with correct shapes."""
    ds = ChiptuneSpectrogramDataset(
        tmp_segments_dir, split=None, metadata=tmp_metadata, duration_filter=4
    )
    assert len(ds) >= 2, "need at least 2 samples to form a batch"

    batch_size = 2
    expected_frames = 1 + (int(SR * 4.0)) // HOP_LENGTH
    loader = get_dataloader(ds, batch_size=batch_size, shuffle=False, num_workers=0)

    specs, labels = next(iter(loader))
    assert specs.shape == (batch_size, 1, N_MELS, expected_frames), (
        f"expected batch shape ({batch_size}, 1, {N_MELS}, {expected_frames}), got {tuple(specs.shape)}"
    )
    assert labels.shape == (batch_size,), "labels tensor should be 1-D with length == batch_size"


# ---------------------------------------------------------------------------
# Segment-slicing logic tests
# ---------------------------------------------------------------------------

def test_silence_detection(tmp_path: Path):
    """A silent wav (all zeros) should have RMS below the silence threshold."""
    silent = np.zeros(SR * 4, dtype=np.float32)
    path = tmp_path / "silent.wav"
    sf.write(str(path), silent, SR)

    data, _ = sf.read(str(path))
    rms = float(np.sqrt(np.mean(data ** 2)))
    assert rms < 0.005, f"silent wav RMS {rms:.6f} should be < 0.005"


def test_non_silent_segment(tmp_path: Path):
    """A sine-wave wav should have RMS well above the silence threshold."""
    tone = _sine(440.0, 4.0)
    path = tmp_path / "tone.wav"
    sf.write(str(path), tone, SR)

    data, _ = sf.read(str(path))
    rms = float(np.sqrt(np.mean(data ** 2)))
    assert rms > 0.005, f"sine wav RMS {rms:.6f} should be > 0.005"


# ---------------------------------------------------------------------------
# Unbalanced dataset tests
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_uneven_segments_dir(tmp_path: Path) -> Path:
    """Segments directory with uneven chip-type counts (5 mod, 2 sid, 1 vgm)."""
    segs = tmp_path / "uneven_segments"

    for i in range(5):
        _write_wav(segs / "modarchive" / f"mod_{i:03d}_4s.wav", 440.0 + i * 10, 4.0)

    for i in range(2):
        _write_wav(segs / "sid" / f"sid_{i:03d}_4s.wav", 660.0 + i * 10, 4.0)

    _write_wav(segs / "vgm" / "vgm_000_4s.wav", 550.0, 4.0)

    return segs


def test_unbalanced_metadata_preserves_all_files(tmp_uneven_segments_dir: Path) -> None:
    """build_metadata with balance=False must include all files, not cap to smallest."""
    meta = build_metadata(tmp_uneven_segments_dir, balance=False)
    all_paths = [p for paths in meta["splits"].values() for p in paths]
    # 5 mod + 2 sid + 1 vgm = 8 total
    assert len(all_paths) == 8, (
        f"unbalanced build should include all 8 files, got {len(all_paths)}"
    )


def test_balanced_vs_unbalanced_counts(tmp_uneven_segments_dir: Path) -> None:
    """Balanced build caps to smallest type; unbalanced does not."""
    balanced = build_metadata(tmp_uneven_segments_dir, balance=True)
    unbalanced = build_metadata(tmp_uneven_segments_dir, balance=False)

    balanced_total = sum(len(v) for v in balanced["splits"].values())
    unbalanced_total = sum(len(v) for v in unbalanced["splits"].values())

    # Balanced: 3 types × 1 file each = 3
    assert balanced_total == 3, (
        f"balanced build should cap to 1 per type (3 total), got {balanced_total}"
    )
    # Unbalanced: all 8 files
    assert unbalanced_total == 8, (
        f"unbalanced build should include all 8 files, got {unbalanced_total}"
    )
    assert unbalanced_total > balanced_total, "unbalanced should include more files than balanced"
