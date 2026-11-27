"""Quality metrics for evaluating generated spectrograms against real data.

Mean Spectral Distance (MSD): average L1 distance between real and generated
Mel-spectrograms. Lower is better — generated spectrograms look more like
the training distribution.

Autocorrelation: measures self-similarity along the time axis. Peaks indicate
periodic (looping) structure — higher peak strength means more repetition.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


def mean_spectral_distance(
    real: torch.Tensor,
    generated: torch.Tensor,
) -> float:
    """Compute mean L1 distance between real and generated spectrograms.

    Compares each generated sample against the nearest real sample (by L1),
    then averages. This avoids penalising diversity — a generated sample only
    needs to be close to *some* real sample, not all of them.

    Args:
        real: (N_real, 1, H, W) tensor of real spectrograms.
        generated: (N_gen, 1, H, W) tensor of generated spectrograms.

    Returns:
        Mean of per-sample minimum L1 distances (float).
    """
    # Flatten spatial dims: (N, 1, H, W) → (N, H*W)
    real_flat = real.reshape(real.shape[0], -1)
    gen_flat = generated.reshape(generated.shape[0], -1)

    min_distances = []
    for g in gen_flat:
        # L1 distance from this generated sample to every real sample
        dists = (real_flat - g.unsqueeze(0)).abs().mean(dim=1)
        min_distances.append(dists.min().item())

    return sum(min_distances) / len(min_distances)


def mean_spectral_distance_global(
    real: torch.Tensor,
    generated: torch.Tensor,
) -> float:
    """Simpler variant: mean L1 across all pixel positions, averaged over pairs.

    Computes the element-wise mean of real vs generated distribution centroids.
    Faster but doesn't capture diversity — use for quick comparisons.

    Args:
        real: (N_real, 1, H, W) tensor.
        generated: (N_gen, 1, H, W) tensor.

    Returns:
        L1 distance between the mean real and mean generated spectrogram.
    """
    real_mean = real.mean(dim=0)
    gen_mean = generated.mean(dim=0)
    return (real_mean - gen_mean).abs().mean().item()


def autocorrelation(spec: torch.Tensor, min_lag: int = 5) -> tuple[int, float]:
    """Compute autocorrelation along the time axis of a spectrogram.

    Averages across Mel bins, then computes normalised autocorrelation at
    each lag. Returns the strongest peak beyond min_lag (to skip the trivial
    lag-0 self-correlation and very short lags from frame-to-frame similarity).

    Args:
        spec: (1, H, W) or (H, W) spectrogram tensor.
        min_lag: Minimum lag to consider (frames). Default 5 (~0.1s at 22050/512).

    Returns:
        (peak_lag, peak_strength) where:
        - peak_lag: frame offset of the strongest repeating pattern
        - peak_strength: normalised correlation at that lag (0.0–1.0).
          Higher = more repetitive.
    """
    if spec.dim() == 3:
        spec = spec.squeeze(0)

    # Average across Mel bins → 1D signal along time
    signal = spec.mean(dim=0).float()
    signal = signal - signal.mean()

    n = signal.shape[0]
    if n <= min_lag:
        return 0, 0.0

    # Normalised autocorrelation via dot products
    norm = (signal * signal).sum().item()
    if norm < 1e-8:
        return 0, 0.0

    correlations = []
    for lag in range(min_lag, n // 2):
        c = (signal[:n - lag] * signal[lag:]).sum().item() / norm
        correlations.append((lag, c))

    if not correlations:
        return 0, 0.0

    peak_lag, peak_strength = max(correlations, key=lambda x: x[1])
    return peak_lag, max(0.0, peak_strength)


def batch_autocorrelation(
    specs: torch.Tensor, min_lag: int = 5
) -> list[tuple[int, float]]:
    """Compute autocorrelation for a batch of spectrograms.

    Args:
        specs: (N, 1, H, W) tensor.
        min_lag: Minimum lag to consider.

    Returns:
        List of (peak_lag, peak_strength) per sample.
    """
    return [autocorrelation(specs[i], min_lag) for i in range(specs.shape[0])]
