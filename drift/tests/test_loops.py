"""Tests for drift.loops — loop detection on raw waveforms."""

from __future__ import annotations

import numpy as np
import pytest

from drift.loops import detect_loop, detect_loop_fft, filter_looping_segments


def _make_sine_loop(freq_hz: float = 4.0, sr: int = 22050, duration_s: float = 8.0) -> np.ndarray:
    """Sine wave that loops every 1/freq_hz seconds."""
    t = np.arange(int(sr * duration_s)) / sr
    return np.sin(2 * np.pi * freq_hz * t).astype(np.float32)


def _make_noise(sr: int = 22050, duration_s: float = 8.0) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.normal(size=int(sr * duration_s)).astype(np.float32)


class TestDetectLoop:
    def test_sine_loop_detected(self):
        wav = _make_sine_loop(freq_hz=2.0, sr=22050, duration_s=8.0)
        _, loop_len, conf = detect_loop(wav, sr=22050)
        expected_period = 22050 // 2  # 0.5s period
        assert abs(loop_len - expected_period) <= 2
        assert conf > 0.8

    def test_noise_low_confidence(self):
        wav = _make_noise()
        _, _, conf = detect_loop(wav, sr=22050)
        assert conf < 0.3

    def test_silent_input(self):
        wav = np.zeros(22050 * 4, dtype=np.float32)
        _, loop_len, conf = detect_loop(wav, sr=22050)
        assert conf == 0.0

    def test_short_input(self):
        wav = np.ones(100, dtype=np.float32)
        _, _, conf = detect_loop(wav, sr=22050, min_period_s=0.5)
        assert conf == 0.0


class TestDetectLoopFFT:
    def test_matches_naive(self):
        wav = _make_sine_loop(freq_hz=3.0, sr=22050, duration_s=4.0)
        _, len_naive, conf_naive = detect_loop(wav, sr=22050)
        _, len_fft, conf_fft = detect_loop_fft(wav, sr=22050)
        assert len_naive == len_fft
        assert abs(conf_naive - conf_fft) < 0.01

    def test_sine_loop_detected(self):
        wav = _make_sine_loop(freq_hz=2.0, sr=22050, duration_s=8.0)
        _, loop_len, conf = detect_loop_fft(wav, sr=22050)
        expected_period = 22050 // 2
        assert abs(loop_len - expected_period) <= 2
        assert conf > 0.8

    def test_noise_low_confidence(self):
        wav = _make_noise()
        _, _, conf = detect_loop_fft(wav, sr=22050)
        assert conf < 0.3


class TestFilterLoopingSegments:
    def test_no_files_returns_empty(self, tmp_path):
        result = filter_looping_segments(tmp_path, duration=8)
        assert result == []
