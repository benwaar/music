"""Tests for the Griffin-Lim vocoder."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import pytest
import soundfile as sf

from drift.dataset import HOP_LENGTH, N_FFT, N_MELS, SR
from drift.vocoder import (
    denormalise_spectrogram,
    mel_to_audio,
    save_audio,
    spectrogram_to_audio,
)

GLOBAL_MIN = -80.0
GLOBAL_MAX = 0.0


def _make_mel_db(n_frames: int = 50) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.uniform(GLOBAL_MIN, GLOBAL_MAX, size=(N_MELS, n_frames)).astype(
        np.float32
    )


def _normalise(spec_db: np.ndarray) -> np.ndarray:
    return 2.0 * (spec_db - GLOBAL_MIN) / (GLOBAL_MAX - GLOBAL_MIN) - 1.0


def test_denormalise_roundtrip() -> None:
    spec_db = _make_mel_db()
    normalised = _normalise(spec_db)
    recovered = denormalise_spectrogram(normalised, GLOBAL_MIN, GLOBAL_MAX)
    np.testing.assert_allclose(recovered, spec_db, atol=1e-4)


def test_denormalise_channel_dim_squeezed() -> None:
    spec_db = _make_mel_db()
    normalised = _normalise(spec_db)[np.newaxis, :, :]  # (1, 128, T)
    recovered = denormalise_spectrogram(normalised, GLOBAL_MIN, GLOBAL_MAX)
    assert recovered.ndim == 2


def test_spectrogram_to_audio_returns_float32() -> None:
    spec_db = _make_mel_db()
    normalised = _normalise(spec_db)
    waveform = spectrogram_to_audio(normalised, GLOBAL_MIN, GLOBAL_MAX)
    assert isinstance(waveform, np.ndarray)
    assert waveform.dtype == np.float32


def test_spectrogram_to_audio_output_length() -> None:
    n_frames = 50
    spec_db = _make_mel_db(n_frames)
    normalised = _normalise(spec_db)
    waveform = spectrogram_to_audio(normalised, GLOBAL_MIN, GLOBAL_MAX)
    expected = n_frames * HOP_LENGTH
    assert abs(len(waveform) - expected) <= HOP_LENGTH


def test_spectrogram_to_audio_accepts_torch_tensor() -> None:
    torch = pytest.importorskip("torch")
    spec_db = _make_mel_db()
    normalised = _normalise(spec_db)
    tensor = torch.from_numpy(normalised[np.newaxis, :, :])  # (1, 128, T)
    waveform = spectrogram_to_audio(tensor, GLOBAL_MIN, GLOBAL_MAX)
    assert isinstance(waveform, np.ndarray)
    assert waveform.dtype == np.float32


def test_sine_wave_roundtrip_dominant_frequency() -> None:
    freq = 440.0
    duration = 2.0
    t = np.linspace(0, duration, int(SR * duration), endpoint=False)
    sine = (np.sin(2 * np.pi * freq * t) * 0.9).astype(np.float32)

    mel = librosa.feature.melspectrogram(
        y=sine, sr=SR, n_fft=N_FFT, hop_length=HOP_LENGTH, n_mels=N_MELS
    )
    spec_db = librosa.power_to_db(mel, ref=np.max)

    normalised = _normalise(spec_db)
    recovered = spectrogram_to_audio(
        normalised, GLOBAL_MIN, GLOBAL_MAX, n_iter=64
    )

    fft = np.fft.rfft(recovered)
    freqs = np.fft.rfftfreq(len(recovered), d=1.0 / SR)
    dominant = freqs[np.argmax(np.abs(fft))]
    assert abs(dominant - freq) < 50.0, f"dominant freq {dominant:.1f} Hz, expected ~440 Hz"


def test_save_audio_creates_file(tmp_path: Path) -> None:
    waveform = np.zeros(SR, dtype=np.float32)
    out = tmp_path / "subdir" / "test.wav"
    save_audio(waveform, out)
    assert out.exists()
    data, rate = sf.read(str(out))
    assert rate == SR
    assert len(data) == SR
