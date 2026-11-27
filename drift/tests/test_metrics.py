"""Tests for drift.metrics."""

import torch
import pytest

from drift.metrics import (
    autocorrelation,
    batch_autocorrelation,
    mean_spectral_distance,
    mean_spectral_distance_global,
)


def test_identical_spectrograms_have_zero_distance():
    specs = torch.randn(10, 1, 128, 176)
    assert mean_spectral_distance(specs, specs) == pytest.approx(0.0, abs=1e-5)


def test_identical_distributions_have_zero_global_distance():
    specs = torch.randn(10, 1, 128, 176)
    assert mean_spectral_distance_global(specs, specs) == pytest.approx(0.0, abs=1e-5)


def test_noise_vs_real_has_positive_distance():
    real = torch.zeros(10, 1, 128, 176)
    generated = torch.randn(5, 1, 128, 176)
    dist = mean_spectral_distance(real, generated)
    assert dist > 0.0


def test_closer_samples_have_lower_distance():
    real = torch.zeros(10, 1, 128, 176)
    close = torch.randn(5, 1, 128, 176) * 0.1
    far = torch.randn(5, 1, 128, 176) * 2.0
    dist_close = mean_spectral_distance(real, close)
    dist_far = mean_spectral_distance(real, far)
    assert dist_close < dist_far


def test_global_distance_symmetry():
    a = torch.randn(10, 1, 128, 176)
    b = torch.randn(10, 1, 128, 176)
    d_ab = mean_spectral_distance_global(a, b)
    d_ba = mean_spectral_distance_global(b, a)
    assert d_ab == pytest.approx(d_ba, abs=1e-5)


# --- Autocorrelation tests ---


def test_repeating_signal_has_high_autocorrelation():
    """A spectrogram with a repeating pattern should have a strong peak."""
    pattern = torch.randn(1, 128, 20)
    # Repeat the pattern ~8 times to fill 160 frames
    spec = pattern.repeat(1, 1, 8)
    lag, strength = autocorrelation(spec, min_lag=5)
    assert lag == pytest.approx(20, abs=2)
    assert strength > 0.5


def test_random_noise_has_low_autocorrelation():
    """Pure noise should have weak autocorrelation."""
    spec = torch.randn(1, 128, 176)
    _, strength = autocorrelation(spec, min_lag=5)
    assert strength < 0.3


def test_autocorrelation_handles_2d_input():
    spec = torch.randn(128, 176)
    lag, strength = autocorrelation(spec, min_lag=5)
    assert isinstance(lag, int)
    assert 0.0 <= strength <= 1.0


def test_batch_autocorrelation_length():
    specs = torch.randn(5, 1, 128, 176)
    results = batch_autocorrelation(specs, min_lag=5)
    assert len(results) == 5
    for lag, strength in results:
        assert isinstance(lag, int)
        assert 0.0 <= strength <= 1.0
