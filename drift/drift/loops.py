"""Loop detection for chip-tune audio segments.

Heuristic autocorrelation on raw waveforms to find repeating patterns.
Chip-tunes are programmed to loop — autocorrelation peaks reveal the
loop period. Use to filter training data to loop-only segments.
"""

from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np


def detect_loop(
    wav: np.ndarray,
    sr: int = 22050,
    min_period_s: float = 0.5,
    max_period_s: float = 4.0,
) -> tuple[int, int, float]:
    """Find the dominant loop period in an audio waveform.

    Args:
        wav: 1D audio array (mono).
        sr: Sample rate.
        min_period_s: Shortest loop to detect (seconds).
        max_period_s: Longest loop to detect (seconds).

    Returns:
        (loop_start_sample, loop_length_samples, confidence) where:
        - loop_start_sample: always 0 (full-segment analysis)
        - loop_length_samples: detected period in samples
        - confidence: peak autocorrelation strength (0.0–1.0)
    """
    wav = wav.astype(np.float32)
    wav = wav - wav.mean()

    norm = np.dot(wav, wav)
    if norm < 1e-8:
        return 0, 0, 0.0

    min_lag = int(min_period_s * sr)
    max_lag = min(int(max_period_s * sr), len(wav) // 2)

    if min_lag >= max_lag:
        return 0, 0, 0.0

    best_lag = min_lag
    best_corr = -1.0

    for lag in range(min_lag, max_lag):
        c = np.dot(wav[: len(wav) - lag], wav[lag:]) / norm
        if c > best_corr:
            best_corr = c
            best_lag = lag

    return 0, best_lag, max(0.0, float(best_corr))


def detect_loop_fft(
    wav: np.ndarray,
    sr: int = 22050,
    min_period_s: float = 0.5,
    max_period_s: float = 4.0,
) -> tuple[int, int, float]:
    """FFT-accelerated loop detection — same interface, much faster for long segments."""
    wav = wav.astype(np.float32)
    wav = wav - wav.mean()

    norm = np.dot(wav, wav)
    if norm < 1e-8:
        return 0, 0, 0.0

    n = len(wav)
    fft_size = 1
    while fft_size < 2 * n:
        fft_size *= 2

    fft_wav = np.fft.rfft(wav, n=fft_size)
    acf = np.fft.irfft(fft_wav * np.conj(fft_wav), n=fft_size)[:n]
    acf = acf / norm

    min_lag = int(min_period_s * sr)
    max_lag = min(int(max_period_s * sr), n // 2)

    if min_lag >= max_lag:
        return 0, 0, 0.0

    search = acf[min_lag:max_lag]
    best_idx = int(np.argmax(search))
    best_lag = min_lag + best_idx
    best_corr = float(search[best_idx])

    return 0, best_lag, max(0.0, best_corr)


def filter_looping_segments(
    segment_dir: Path,
    duration: int = 8,
    min_confidence: float = 0.3,
    sr: int = 22050,
) -> list[tuple[Path, int, float]]:
    """Scan segments and return those with a detectable loop.

    Args:
        segment_dir: Root directory containing chip_type subdirs.
        duration: Segment duration suffix to filter (seconds).
        min_confidence: Minimum autocorrelation peak to count as looping.
        sr: Sample rate.

    Returns:
        List of (path, loop_length_samples, confidence) for segments
        that pass the confidence threshold, sorted by confidence descending.
    """
    results = []
    pattern = f"*_{duration}s.wav"

    for wav_path in sorted(segment_dir.rglob(pattern)):
        wav, _ = librosa.load(str(wav_path), sr=sr, mono=True)
        _, loop_len, conf = detect_loop_fft(wav, sr)
        if conf >= min_confidence:
            results.append((wav_path, loop_len, conf))

    results.sort(key=lambda x: x[2], reverse=True)
    return results
