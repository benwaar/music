"""Griffin-Lim vocoder: normalised spectrogram → audio waveform."""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from drift.dataset import HOP_LENGTH, N_FFT, N_MELS, SR


def denormalise_spectrogram(
    spec: np.ndarray,
    global_min: float,
    global_max: float,
) -> np.ndarray:
    arr = np.array(spec, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr.squeeze(0)
    return (arr + 1.0) / 2.0 * (global_max - global_min) + global_min


def mel_to_audio(
    spec_db: np.ndarray,
    sr: int = SR,
    n_fft: int = N_FFT,
    hop_length: int = HOP_LENGTH,
    n_mels: int = N_MELS,
    n_iter: int = 64,
) -> np.ndarray:
    s_power = librosa.db_to_power(spec_db)
    s_linear = librosa.feature.inverse.mel_to_stft(
        s_power, sr=sr, n_fft=n_fft
    )
    waveform = librosa.griffinlim(
        s_linear, n_iter=n_iter, hop_length=hop_length, n_fft=n_fft
    )
    return waveform.astype(np.float32)


def spectrogram_to_audio(
    spec: np.ndarray,
    global_min: float,
    global_max: float,
    **kwargs,
) -> np.ndarray:
    try:
        import torch
        if isinstance(spec, torch.Tensor):
            spec = spec.squeeze(0).cpu().numpy()
    except ImportError:
        pass

    spec_db = denormalise_spectrogram(spec, global_min, global_max)
    spec_db = np.clip(spec_db, global_min, global_max)
    return mel_to_audio(spec_db, **kwargs)


def save_audio(waveform: np.ndarray, path: str | Path, sr: int = SR) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), waveform, sr)
