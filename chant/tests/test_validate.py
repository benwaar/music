"""Tests for chant.validate — structural validation of note sequences."""

from __future__ import annotations

import pytest

from chant.schema import NoteEvent, NoteTable, TrackMetadata
from chant import tokeniser
from chant.validate import (
    ValidationResult,
    compare_conditioned_vs_unconditioned,
    validate_events,
    validate_token_string,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_event(
    pitch_hz: float = 440.0,
    duration_ms: float = 500.0,
    channel: int = 0,
    volume: float | None = 1.0,
) -> NoteEvent:
    return NoteEvent(pitch_hz=pitch_hz, duration_ms=duration_ms, channel=channel, volume=volume)


def valid_events() -> list[NoteEvent]:
    """Two distinct, well-formed NoteEvents."""
    return [
        make_event(pitch_hz=440.0, duration_ms=500.0, channel=0),
        make_event(pitch_hz=880.0, duration_ms=250.0, channel=1),
    ]


def _token_string_from_events(events: list[NoteEvent]) -> str:
    """Encode a list of NoteEvents to a token string via a dummy NoteTable."""
    meta = TrackMetadata(source_format="test", source_path="test")
    table = NoteTable(metadata=meta, events=events)
    return tokeniser.encode(table)


# ---------------------------------------------------------------------------
# validate_events — happy path
# ---------------------------------------------------------------------------

class TestValidateEventsValid:
    def test_returns_valid_result(self):
        result = validate_events(valid_events())
        assert result.valid is True

    def test_num_events(self):
        result = validate_events(valid_events())
        assert result.num_events == 2

    def test_no_issues(self):
        result = validate_events(valid_events())
        assert result.issues == []

    def test_pitch_range_populated(self):
        result = validate_events(valid_events())
        assert result.pitch_range == pytest.approx((440.0, 880.0))

    def test_duration_range_populated(self):
        result = validate_events(valid_events())
        assert result.duration_range == pytest.approx((250.0, 500.0))

    def test_channels_used(self):
        result = validate_events(valid_events())
        assert result.channels_used == {0, 1}

    def test_boolean_flags_all_true(self):
        result = validate_events(valid_events())
        assert result.pitch_in_range is True
        assert result.duration_in_range is True
        assert result.channels_in_range is True
        assert result.has_variety is True


# ---------------------------------------------------------------------------
# validate_events — empty input
# ---------------------------------------------------------------------------

class TestValidateEventsEmpty:
    def test_invalid(self):
        assert validate_events([]).valid is False

    def test_zero_events(self):
        assert validate_events([]).num_events == 0

    def test_issue_message(self):
        result = validate_events([])
        assert any("empty" in issue for issue in result.issues)


# ---------------------------------------------------------------------------
# validate_events — out-of-range pitch
# ---------------------------------------------------------------------------

class TestValidateEventsPitch:
    def test_pitch_below_minimum(self):
        events = [
            make_event(pitch_hz=10.0, duration_ms=100.0),   # below 20 Hz
            make_event(pitch_hz=880.0, duration_ms=100.0),
        ]
        result = validate_events(events)
        assert result.valid is False
        assert result.pitch_in_range is False
        assert any("20" in issue and "Hz" in issue for issue in result.issues)

    def test_pitch_above_maximum(self):
        events = [
            make_event(pitch_hz=25_000.0, duration_ms=100.0),  # above 20 kHz
            make_event(pitch_hz=440.0, duration_ms=100.0),
        ]
        result = validate_events(events)
        assert result.valid is False
        assert result.pitch_in_range is False
        assert any("20000" in issue or "20,000" in issue or "Hz" in issue for issue in result.issues)

    def test_pitch_at_boundary_valid(self):
        events = [
            make_event(pitch_hz=20.0, duration_ms=100.0),
            make_event(pitch_hz=20_000.0, duration_ms=100.0),
        ]
        result = validate_events(events)
        assert result.pitch_in_range is True


# ---------------------------------------------------------------------------
# validate_events — duration
# ---------------------------------------------------------------------------

class TestValidateEventsDuration:
    def test_zero_duration_invalid(self):
        events = [
            make_event(pitch_hz=440.0, duration_ms=0.0),
            make_event(pitch_hz=880.0, duration_ms=100.0),
        ]
        result = validate_events(events)
        assert result.valid is False
        assert result.duration_in_range is False

    def test_negative_duration_invalid(self):
        events = [
            make_event(pitch_hz=440.0, duration_ms=-50.0),
            make_event(pitch_hz=880.0, duration_ms=100.0),
        ]
        result = validate_events(events)
        assert result.valid is False
        assert result.duration_in_range is False
        assert any("0" in issue for issue in result.issues)

    def test_duration_exceeds_max(self):
        events = [
            make_event(pitch_hz=440.0, duration_ms=35_000.0),  # > 30 s
            make_event(pitch_hz=880.0, duration_ms=100.0),
        ]
        result = validate_events(events)
        assert result.valid is False
        assert result.duration_in_range is False

    def test_duration_at_max_valid(self):
        events = [
            make_event(pitch_hz=440.0, duration_ms=30_000.0),
            make_event(pitch_hz=880.0, duration_ms=100.0),
        ]
        result = validate_events(events)
        assert result.duration_in_range is True


# ---------------------------------------------------------------------------
# validate_events — channel range
# ---------------------------------------------------------------------------

class TestValidateEventsChannel:
    def test_channel_above_31_invalid(self):
        events = [
            make_event(pitch_hz=440.0, duration_ms=100.0, channel=32),
            make_event(pitch_hz=880.0, duration_ms=100.0, channel=0),
        ]
        result = validate_events(events)
        assert result.valid is False
        assert result.channels_in_range is False
        assert any("32" in issue for issue in result.issues)

    def test_channel_31_valid(self):
        events = [
            make_event(pitch_hz=440.0, duration_ms=100.0, channel=31),
            make_event(pitch_hz=880.0, duration_ms=100.0, channel=0),
        ]
        result = validate_events(events)
        assert result.channels_in_range is True


# ---------------------------------------------------------------------------
# validate_events — variety
# ---------------------------------------------------------------------------

class TestValidateEventsVariety:
    def test_all_identical_events_invalid(self):
        events = [make_event() for _ in range(5)]  # all same pitch/dur/ch/vol
        result = validate_events(events)
        assert result.valid is False
        assert result.has_variety is False
        assert any("identical" in issue or "variety" in issue for issue in result.issues)

    def test_single_distinct_event_no_variety(self):
        result = validate_events([make_event()])
        assert result.has_variety is False

    def test_two_different_pitches_has_variety(self):
        events = [
            make_event(pitch_hz=440.0),
            make_event(pitch_hz=880.0),
        ]
        result = validate_events(events)
        assert result.has_variety is True


# ---------------------------------------------------------------------------
# validate_token_string
# ---------------------------------------------------------------------------

class TestValidateTokenString:
    def test_valid_token_string(self):
        token_str = _token_string_from_events(valid_events())
        result = validate_token_string(token_str)
        assert result.valid is True
        assert result.num_events == 2

    def test_garbage_input_invalid(self):
        result = validate_token_string("this is complete garbage @@@@")
        assert result.valid is False
        assert any("unparseable" in issue for issue in result.issues)

    def test_empty_string_invalid(self):
        result = validate_token_string("")
        assert result.valid is False
        assert any("unparseable" in issue for issue in result.issues)

    def test_bos_eos_only_invalid(self):
        # Encodes to '<BOS> <EOS>' — no events
        result = validate_token_string("<BOS> <EOS>")
        assert result.valid is False
        assert any("unparseable" in issue for issue in result.issues)

    def test_single_valid_event(self):
        events = [
            make_event(pitch_hz=440.0, duration_ms=500.0, channel=0),
            make_event(pitch_hz=880.0, duration_ms=250.0, channel=1),
        ]
        token_str = _token_string_from_events(events)
        result = validate_token_string(token_str)
        assert result.valid is True


# ---------------------------------------------------------------------------
# compare_conditioned_vs_unconditioned
# ---------------------------------------------------------------------------

class TestCompareConditionedVsUnconditioned:
    @pytest.fixture()
    def conditioned(self) -> list[NoteEvent]:
        return [
            make_event(pitch_hz=440.0, duration_ms=100.0, channel=0),
            make_event(pitch_hz=494.0, duration_ms=200.0, channel=0),
            make_event(pitch_hz=523.0, duration_ms=300.0, channel=1),
        ]

    @pytest.fixture()
    def unconditioned(self) -> list[NoteEvent]:
        return [
            make_event(pitch_hz=440.0, duration_ms=100.0, channel=0),
            make_event(pitch_hz=440.0, duration_ms=100.0, channel=0),
        ]

    def test_returns_all_expected_keys(self, conditioned, unconditioned):
        metrics = compare_conditioned_vs_unconditioned(conditioned, unconditioned)
        expected_keys = {
            "pitch_diversity_conditioned",
            "pitch_diversity_unconditioned",
            "duration_diversity_conditioned",
            "duration_diversity_unconditioned",
            "channel_spread_conditioned",
            "channel_spread_unconditioned",
        }
        assert set(metrics.keys()) == expected_keys

    def test_values_are_integers(self, conditioned, unconditioned):
        metrics = compare_conditioned_vs_unconditioned(conditioned, unconditioned)
        for key, value in metrics.items():
            assert isinstance(value, int), f"{key} should be int, got {type(value)}"

    def test_conditioned_has_more_pitch_diversity(self, conditioned, unconditioned):
        metrics = compare_conditioned_vs_unconditioned(conditioned, unconditioned)
        assert (
            metrics["pitch_diversity_conditioned"]
            > metrics["pitch_diversity_unconditioned"]
        )

    def test_conditioned_has_more_duration_diversity(self, conditioned, unconditioned):
        metrics = compare_conditioned_vs_unconditioned(conditioned, unconditioned)
        assert (
            metrics["duration_diversity_conditioned"]
            > metrics["duration_diversity_unconditioned"]
        )

    def test_conditioned_has_more_channel_spread(self, conditioned, unconditioned):
        metrics = compare_conditioned_vs_unconditioned(conditioned, unconditioned)
        assert (
            metrics["channel_spread_conditioned"]
            > metrics["channel_spread_unconditioned"]
        )

    def test_empty_lists_return_zeros(self):
        metrics = compare_conditioned_vs_unconditioned([], [])
        for value in metrics.values():
            assert value == 0

    def test_identical_sequences_equal_metrics(self):
        events = valid_events()
        metrics = compare_conditioned_vs_unconditioned(events, events)
        assert (
            metrics["pitch_diversity_conditioned"]
            == metrics["pitch_diversity_unconditioned"]
        )
        assert (
            metrics["channel_spread_conditioned"]
            == metrics["channel_spread_unconditioned"]
        )
