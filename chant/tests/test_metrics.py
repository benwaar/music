"""Tests for chant/metrics.py — musical coherence metrics."""

from __future__ import annotations

import math

import pytest

from chant.schema import NoteEvent
from chant.metrics import (
    channel_balance,
    compute_all_metrics,
    pitch_entropy,
    repetition_score,
    rhythm_regularity,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def note(pitch_hz: float = 440.0, duration_ms: float = 100.0, channel: int = 0, volume: float | None = None) -> NoteEvent:
    return NoteEvent(pitch_hz=pitch_hz, duration_ms=duration_ms, channel=channel, volume=volume)


# ---------------------------------------------------------------------------
# pitch_entropy
# ---------------------------------------------------------------------------

class TestPitchEntropy:
    def test_empty_returns_zero(self):
        assert pitch_entropy([]) == 0.0

    def test_single_event_returns_zero(self):
        assert pitch_entropy([note(440.0)]) == 0.0

    def test_two_identical_pitches_returns_zero(self):
        assert pitch_entropy([note(440.0), note(440.0)]) == 0.0

    def test_two_different_pitches_returns_one_bit(self):
        # A4=440 and A5=880 are different MIDI notes → entropy = 1.0 bit
        result = pitch_entropy([note(440.0), note(880.0)])
        assert abs(result - 1.0) < 1e-9

    def test_varied_pitches_greater_than_zero(self):
        events = [note(440.0), note(494.0), note(523.0), note(587.0)]
        assert pitch_entropy(events) > 0.0

    def test_more_variety_higher_entropy(self):
        few = [note(440.0), note(440.0), note(880.0), note(880.0)]
        many = [note(440.0), note(494.0), note(523.0), note(587.0)]
        assert pitch_entropy(many) > pitch_entropy(few)


# ---------------------------------------------------------------------------
# rhythm_regularity
# ---------------------------------------------------------------------------

class TestRhythmRegularity:
    def test_empty_returns_zero(self):
        assert rhythm_regularity([]) == 0.0

    def test_single_event_returns_zero(self):
        assert rhythm_regularity([note(duration_ms=100.0)]) == 0.0

    def test_all_same_duration_returns_zero(self):
        events = [note(duration_ms=100.0) for _ in range(5)]
        assert rhythm_regularity(events) == 0.0

    def test_varied_durations_greater_than_zero(self):
        events = [note(duration_ms=d) for d in [100.0, 200.0, 50.0, 400.0]]
        assert rhythm_regularity(events) > 0.0

    def test_higher_variation_higher_cv(self):
        low_var = [note(duration_ms=d) for d in [100.0, 110.0, 90.0, 105.0]]
        high_var = [note(duration_ms=d) for d in [50.0, 500.0, 25.0, 1000.0]]
        assert rhythm_regularity(high_var) > rhythm_regularity(low_var)

    def test_two_events_different_durations(self):
        events = [note(duration_ms=100.0), note(duration_ms=300.0)]
        assert rhythm_regularity(events) > 0.0


# ---------------------------------------------------------------------------
# channel_balance
# ---------------------------------------------------------------------------

class TestChannelBalance:
    def test_empty_returns_zero(self):
        assert channel_balance([]) == 0.0

    def test_single_event_returns_zero(self):
        assert channel_balance([note(channel=0)]) == 0.0

    def test_all_same_channel_returns_zero(self):
        events = [note(channel=0) for _ in range(4)]
        assert channel_balance(events) == 0.0

    def test_two_channels_equal_returns_one(self):
        events = [note(channel=0), note(channel=1), note(channel=0), note(channel=1)]
        assert abs(channel_balance(events) - 1.0) < 1e-9

    def test_two_channels_unbalanced_between_zero_and_one(self):
        # 3 on ch0, 1 on ch1 — unequal
        events = [note(channel=0), note(channel=0), note(channel=0), note(channel=1)]
        result = channel_balance(events)
        assert 0.0 < result < 1.0

    def test_three_channels_equal_returns_one(self):
        events = [note(channel=c) for c in [0, 1, 2, 0, 1, 2]]
        assert abs(channel_balance(events) - 1.0) < 1e-9

    def test_single_note_single_channel_returns_zero(self):
        assert channel_balance([note(channel=2)]) == 0.0


# ---------------------------------------------------------------------------
# repetition_score
# ---------------------------------------------------------------------------

class TestRepetitionScore:
    def test_empty_returns_zero(self):
        assert repetition_score([]) == 0.0

    def test_single_event_returns_zero(self):
        assert repetition_score([note()]) == 0.0

    def test_all_identical_returns_one(self):
        events = [note(440.0, 100.0, 0) for _ in range(5)]
        assert abs(repetition_score(events) - 1.0) < 1e-9

    def test_all_different_returns_zero(self):
        events = [
            note(440.0, 100.0, 0),
            note(880.0, 200.0, 1),
            note(523.0, 150.0, 2),
            note(294.0, 300.0, 0),
        ]
        assert repetition_score(events) == 0.0

    def test_mixed_partial_repetition(self):
        # pairs: (A,A) match, (A,B) no, (B,B) match → 2/3
        a = note(440.0, 100.0, 0)
        b = note(880.0, 200.0, 1)
        events = [a, a, b, b]
        result = repetition_score(events)
        assert abs(result - 2 / 3) < 1e-9

    def test_volume_included_in_identity_check(self):
        # Same pitch/duration/channel but different volume → not identical
        e1 = note(440.0, 100.0, 0, volume=0.5)
        e2 = note(440.0, 100.0, 0, volume=1.0)
        assert repetition_score([e1, e2]) == 0.0

    def test_volume_none_matches_volume_none(self):
        e1 = note(440.0, 100.0, 0, volume=None)
        e2 = note(440.0, 100.0, 0, volume=None)
        assert abs(repetition_score([e1, e2]) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# compute_all_metrics
# ---------------------------------------------------------------------------

class TestComputeAllMetrics:
    def test_returns_all_four_keys(self):
        events = [note(440.0, 100.0, 0), note(880.0, 200.0, 1)]
        result = compute_all_metrics(events)
        assert set(result.keys()) == {
            "pitch_entropy",
            "rhythm_regularity",
            "channel_balance",
            "repetition_score",
        }

    def test_values_are_floats(self):
        events = [note(440.0, 100.0, 0), note(880.0, 200.0, 1)]
        result = compute_all_metrics(events)
        for key, val in result.items():
            assert isinstance(val, float), f"{key} should be float, got {type(val)}"

    def test_empty_list_all_zero(self):
        result = compute_all_metrics([])
        assert all(v == 0.0 for v in result.values())

    def test_single_event_all_zero(self):
        result = compute_all_metrics([note()])
        assert all(v == 0.0 for v in result.values())

    def test_values_match_individual_functions(self):
        events = [note(440.0, 100.0, 0), note(880.0, 200.0, 1), note(523.0, 150.0, 0)]
        result = compute_all_metrics(events)
        assert result["pitch_entropy"] == pitch_entropy(events)
        assert result["rhythm_regularity"] == rhythm_regularity(events)
        assert result["channel_balance"] == channel_balance(events)
        assert result["repetition_score"] == repetition_score(events)
